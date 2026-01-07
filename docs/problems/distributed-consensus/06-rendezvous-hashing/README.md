# Rendezvous Hashing (HRW)

## Problem Overview

Implement Rendezvous Hashing (Highest Random Weight) for distributed key-to-node mapping with minimal disruption on node changes.

**Difficulty:** Medium (L5 - Senior Engineer)

---

## Best Solution

### Algorithm Overview

Rendezvous hashing (HRW) works by:
1. For each key, compute a weight for each node: hash(key, node_id)
2. Assign the key to the node with the highest weight
3. Provides consistent assignment with minimal redistribution
4. Simpler than consistent hashing (no ring structure)

### Implementation

```python
import hashlib
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class NodeInfo:
    node_id: str
    address: str
    port: int
    capacity_weight: float = 1.0
    is_active: bool = True

class RendezvousHasher:
    def __init__(self, replication_factor: int = 3):
        self.nodes: Dict[str, NodeInfo] = {}
        self.replication_factor = replication_factor
        self.data: Dict[str, Dict[str, bytes]] = {}  # node_id -> {key: value}

    def _compute_weight(self, key: str, node_id: str) -> float:
        """Compute weight for a key-node pair."""
        combined = f"{key}:{node_id}"
        hash_val = int(hashlib.sha256(combined.encode()).hexdigest(), 16)

        # Normalize to [0, 1) and apply capacity weight
        normalized = hash_val / (2**256)
        capacity = self.nodes[node_id].capacity_weight

        # Use -log(normalized) * capacity for weighted distribution
        import math
        return -math.log(normalized + 1e-10) * capacity

    def add_node(self, node_id: str, address: str, port: int,
                 capacity_weight: float = 1.0) -> bool:
        """Add a node to the hash ring."""
        if node_id in self.nodes:
            return False

        self.nodes[node_id] = NodeInfo(
            node_id=node_id,
            address=address,
            port=port,
            capacity_weight=capacity_weight,
            is_active=True
        )
        self.data[node_id] = {}

        # Rebalance existing keys
        self._rebalance()

        return True

    def remove_node(self, node_id: str) -> int:
        """Remove a node and redistribute its keys."""
        if node_id not in self.nodes:
            return 0

        keys_to_redistribute = list(self.data.get(node_id, {}).items())
        keys_redistributed = 0

        del self.nodes[node_id]
        del self.data[node_id]

        # Redistribute keys to new owners
        for key, value in keys_to_redistribute:
            new_node = self.get_node_for_key(key)
            if new_node:
                self.data[new_node][key] = value
                keys_redistributed += 1

        return keys_redistributed

    def get_node_for_key(self, key: str) -> Optional[str]:
        """Get the node with highest weight for a key."""
        if not self.nodes:
            return None

        active_nodes = [n for n in self.nodes.values() if n.is_active]
        if not active_nodes:
            return None

        best_node = None
        best_weight = -float('inf')

        for node in active_nodes:
            weight = self._compute_weight(key, node.node_id)
            if weight > best_weight:
                best_weight = weight
                best_node = node.node_id

        return best_node

    def get_nodes_for_key(self, key: str, count: int) -> List[tuple]:
        """Get top N nodes for a key (for replication)."""
        if not self.nodes:
            return []

        active_nodes = [n for n in self.nodes.values() if n.is_active]

        # Compute weights for all nodes
        weighted = [
            (self._compute_weight(key, node.node_id), node.node_id)
            for node in active_nodes
        ]

        # Sort by weight descending
        weighted.sort(reverse=True)

        return [(node_id, weight) for weight, node_id in weighted[:count]]

    def put(self, key: str, value: bytes, replication_factor: int = None) -> bool:
        """Store a key-value pair with replication."""
        rf = replication_factor or self.replication_factor

        target_nodes = self.get_nodes_for_key(key, rf)
        if not target_nodes:
            return False

        for node_id, _ in target_nodes:
            self.data[node_id][key] = value

        return True

    def get(self, key: str) -> Optional[bytes]:
        """Retrieve a value by key."""
        node = self.get_node_for_key(key)
        if not node:
            return None

        return self.data.get(node, {}).get(key)

    def _rebalance(self):
        """Rebalance all keys after topology change."""
        all_keys = []
        for node_id, node_data in self.data.items():
            all_keys.extend((key, value) for key, value in node_data.items())

        # Clear and redistribute
        for node_id in self.data:
            self.data[node_id] = {}

        for key, value in all_keys:
            target_nodes = self.get_nodes_for_key(key, self.replication_factor)
            for node_id, _ in target_nodes:
                self.data[node_id][key] = value
```

### Distributed Node Implementation

```python
class RendezvousNode:
    """Distributed rendezvous hashing node."""

    def __init__(self, node_id: str, peers: List[str]):
        self.node_id = node_id
        self.peers = peers
        self.hasher = RendezvousHasher()
        self.local_data: Dict[str, bytes] = {}

    async def handle_get_node_for_key(self, key: str) -> str:
        """Return the responsible node for a key."""
        return self.hasher.get_node_for_key(key)

    async def handle_put(self, key: str, value: bytes,
                        replication_factor: int = 3) -> List[str]:
        """Store with replication to appropriate nodes."""
        target_nodes = self.hasher.get_nodes_for_key(key, replication_factor)
        stored_on = []

        for node_id, _ in target_nodes:
            if node_id == self.node_id:
                self.local_data[key] = value
                stored_on.append(node_id)
            else:
                # Forward to peer
                success = await self.rpc_client.StoreLocal(node_id, key, value)
                if success:
                    stored_on.append(node_id)

        return stored_on

    async def handle_get(self, key: str) -> Optional[bytes]:
        """Retrieve from appropriate node."""
        node = self.hasher.get_node_for_key(key)

        if node == self.node_id:
            return self.local_data.get(key)
        else:
            return await self.rpc_client.GetLocal(node, key)
```

---

## Platform Deployment

### Cluster Configuration

- **5-node cluster** for high availability and load distribution
- All nodes maintain registry of active nodes
- Gossip protocol for membership
- Weighted capacity support
- Tolerates 2 node failures

### gRPC Services

```protobuf
service NodeRegistryService {
    rpc AddNode(AddNodeRequest) returns (AddNodeResponse);
    rpc RemoveNode(RemoveNodeRequest) returns (RemoveNodeResponse);
    rpc ListNodes(ListNodesRequest) returns (ListNodesResponse);
    rpc GetNodeInfo(GetNodeInfoRequest) returns (GetNodeInfoResponse);
}

service RendezvousService {
    rpc GetNodeForKey(GetNodeForKeyRequest) returns (GetNodeForKeyResponse);
    rpc GetNodesForKey(GetNodesForKeyRequest) returns (GetNodesForKeyResponse);
    rpc CalculateWeight(CalculateWeightRequest) returns (CalculateWeightResponse);
}

service KeyValueService {
    rpc Put(PutRequest) returns (PutResponse);
    rpc Get(GetRequest) returns (GetResponse);
    rpc Delete(DeleteRequest) returns (DeleteResponse);
}
```

---

## Realistic Testing

### Functional Tests

```python
class TestRendezvousHashing:
    async def test_deterministic_mapping(self, cluster):
        """Same key always maps to same node."""
        node1 = await cluster[0].GetNodeForKey(key="test_key")
        node2 = await cluster[1].GetNodeForKey(key="test_key")
        node3 = await cluster[2].GetNodeForKey(key="test_key")

        assert node1.node_id == node2.node_id == node3.node_id

    async def test_minimal_redistribution(self, cluster):
        """Adding node only affects keys moving to new node."""
        # Insert keys
        keys = [f"key_{i}" for i in range(1000)]
        for key in keys:
            await cluster[0].Put(key=key, value=b"data")

        # Record current mapping
        before = {}
        for key in keys:
            resp = await cluster[0].GetNodeForKey(key=key)
            before[key] = resp.node_id

        # Add new node
        new_node = await platform_api.add_node()
        await cluster[0].AddNode(
            node_id=new_node.node_id,
            address=new_node.address,
            port=8080
        )

        # Check new mapping
        after = {}
        for key in keys:
            resp = await cluster[0].GetNodeForKey(key=key)
            after[key] = resp.node_id

        # Only keys assigned to new node should change
        changed = sum(1 for k in keys if before[k] != after[k])
        to_new_node = sum(1 for k in keys if after[k] == new_node.node_id)

        # All changed keys should be assigned to new node
        assert changed == to_new_node
        # Should be approximately 1/N of keys
        assert 0.5 * (1000/4) < to_new_node < 1.5 * (1000/4)

    async def test_weighted_distribution(self, cluster):
        """Nodes with higher weight get more keys."""
        # Set different weights
        await cluster[0].AddNode("node_A", "addr_a", 8080, capacity_weight=1.0)
        await cluster[0].AddNode("node_B", "addr_b", 8080, capacity_weight=2.0)
        await cluster[0].AddNode("node_C", "addr_c", 8080, capacity_weight=3.0)

        # Insert keys
        for i in range(3000):
            await cluster[0].Put(key=f"key_{i}", value=b"data")

        # Check distribution
        status = await cluster[0].ListNodes()

        # B should have ~2x keys of A, C should have ~3x keys of A
        a_keys = next(n for n in status.nodes if n.node_id == "node_A")
        b_keys = next(n for n in status.nodes if n.node_id == "node_B")
        c_keys = next(n for n in status.nodes if n.node_id == "node_C")

        # Allow 20% variance
        assert 1.6 < (b_keys / a_keys) < 2.4
        assert 2.4 < (c_keys / a_keys) < 3.6

    async def test_replication(self, cluster):
        """Data replicated to top N nodes."""
        await cluster[0].Put(
            key="replicated",
            value=b"important_data",
            replication_factor=3
        )

        # Get replica nodes
        resp = await cluster[0].GetNodesForKey(key="replicated", count=3)

        assert len(resp.nodes) == 3

        # All replicas should have the data
        for node in resp.nodes:
            data = await get_from_specific_node(node.node_id, "replicated")
            assert data == b"important_data"
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Deterministic | All nodes agree on key mapping |
| Minimal Disruption | Only 1/N keys move on node add |
| Weighted Distribution | Keys proportional to weights |
| Replication | All replicas contain data |
