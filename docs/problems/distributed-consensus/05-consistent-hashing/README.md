# Consistent Hashing

## Problem Overview

Implement consistent hashing for distributed key-to-node mapping that minimizes key redistribution when nodes join or leave.

**Difficulty:** Medium (L5 - Senior Engineer)

---

## Best Solution

### Algorithm Overview

Consistent hashing maps both keys and nodes to a ring:
1. Hash nodes to positions on a ring (0 to 2^32-1)
2. Use virtual nodes for better load distribution
3. Map keys by finding the first node clockwise from key's hash
4. Only K/N keys move when adding/removing nodes

### Implementation

```python
import hashlib
from sortedcontainers import SortedDict
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class VirtualNode:
    node_id: str
    virtual_id: int
    hash_value: int

class ConsistentHashRing:
    def __init__(self, virtual_nodes: int = 150, replication_factor: int = 3):
        self.virtual_nodes = virtual_nodes
        self.replication_factor = replication_factor
        self.ring: SortedDict[int, str] = SortedDict()
        self.nodes: Dict[str, NodeInfo] = {}
        self.data: Dict[str, Dict[str, str]] = {}  # node_id -> {key: value}

    def _hash(self, key: str) -> int:
        """Generate hash value for a key."""
        return int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)

    def add_node(self, node_id: str, address: str) -> List[VirtualNode]:
        """Add a node with virtual nodes to the ring."""
        if node_id in self.nodes:
            return []

        added_vnodes = []
        self.nodes[node_id] = NodeInfo(
            node_id=node_id,
            address=address,
            virtual_nodes=self.virtual_nodes
        )
        self.data[node_id] = {}

        # Add virtual nodes
        for i in range(self.virtual_nodes):
            vnode_key = f"{node_id}:{i}"
            hash_val = self._hash(vnode_key)
            self.ring[hash_val] = node_id
            added_vnodes.append(VirtualNode(
                node_id=node_id,
                virtual_id=i,
                hash_value=hash_val
            ))

        # Rebalance keys
        self._rebalance_after_add(node_id)

        return added_vnodes

    def remove_node(self, node_id: str, graceful: bool = True) -> int:
        """Remove a node from the ring."""
        if node_id not in self.nodes:
            return 0

        keys_transferred = 0

        if graceful:
            # Transfer keys to new owners
            keys_to_transfer = list(self.data.get(node_id, {}).items())
            for key, value in keys_to_transfer:
                new_node = self._get_node_for_key_excluding(key, node_id)
                if new_node:
                    self.data[new_node][key] = value
                    keys_transferred += 1

        # Remove virtual nodes
        for i in range(self.virtual_nodes):
            vnode_key = f"{node_id}:{i}"
            hash_val = self._hash(vnode_key)
            if hash_val in self.ring:
                del self.ring[hash_val]

        del self.nodes[node_id]
        del self.data[node_id]

        return keys_transferred

    def get_node(self, key: str) -> Optional[str]:
        """Get the node responsible for a key."""
        if not self.ring:
            return None

        hash_val = self._hash(key)

        # Find first node clockwise from key's position
        idx = self.ring.bisect_left(hash_val)
        if idx == len(self.ring):
            idx = 0

        return self.ring.peekitem(idx)[1]

    def get_nodes(self, key: str, count: int) -> List[str]:
        """Get N nodes for replication."""
        if not self.ring:
            return []

        nodes = []
        seen = set()
        hash_val = self._hash(key)
        idx = self.ring.bisect_left(hash_val)

        while len(nodes) < count and len(seen) < len(self.nodes):
            if idx >= len(self.ring):
                idx = 0

            node_id = self.ring.peekitem(idx)[1]
            if node_id not in seen:
                nodes.append(node_id)
                seen.add(node_id)

            idx += 1

        return nodes

    def put(self, key: str, value: str) -> PutResponse:
        """Store a key-value pair with replication."""
        primary_node = self.get_node(key)
        if not primary_node:
            return PutResponse(success=False, error="No nodes available")

        replica_nodes = self.get_nodes(key, self.replication_factor)

        # Store on all replicas
        for node in replica_nodes:
            self.data[node][key] = value

        return PutResponse(
            success=True,
            stored_on=primary_node,
            replicated_to=replica_nodes[1:]
        )

    def get(self, key: str) -> GetResponse:
        """Retrieve a value by key."""
        node = self.get_node(key)
        if not node:
            return GetResponse(found=False, error="No nodes available")

        value = self.data.get(node, {}).get(key)
        return GetResponse(
            value=value,
            found=value is not None,
            served_by=node
        )

    def _rebalance_after_add(self, new_node: str):
        """Rebalance keys after adding a node."""
        keys_to_move = []

        for node_id, node_data in self.data.items():
            if node_id == new_node:
                continue

            for key in list(node_data.keys()):
                correct_node = self.get_node(key)
                if correct_node == new_node:
                    keys_to_move.append((key, node_data[key], node_id))

        for key, value, old_node in keys_to_move:
            self.data[new_node][key] = value
            del self.data[old_node][key]

    def get_key_distribution(self) -> Dict[str, int]:
        """Get number of keys per node."""
        return {
            node_id: len(data)
            for node_id, data in self.data.items()
        }
```

---

## Platform Deployment

### Cluster Configuration

- 3+ node cluster
- Each node maintains full ring state
- Gossip protocol for membership updates
- Virtual nodes configurable (default: 150)

### gRPC Services

```protobuf
service HashRingService {
    rpc AddNode(AddNodeRequest) returns (AddNodeResponse);
    rpc RemoveNode(RemoveNodeRequest) returns (RemoveNodeResponse);
    rpc GetNode(GetNodeRequest) returns (GetNodeResponse);
    rpc GetNodes(GetNodesRequest) returns (GetNodesResponse);
    rpc GetRingState(GetRingStateRequest) returns (GetRingStateResponse);
    rpc Rebalance(RebalanceRequest) returns (RebalanceResponse);
}

service KeyValueService {
    rpc Get(GetRequest) returns (GetResponse);
    rpc Put(PutRequest) returns (PutResponse);
    rpc Delete(DeleteRequest) returns (DeleteResponse);
}
```

---

## Realistic Testing

### Functional Tests

```python
class TestConsistentHashing:
    async def test_key_distribution(self, cluster):
        """Keys are distributed evenly across nodes."""
        # Insert 10000 keys
        for i in range(10000):
            await cluster[0].Put(key=f"key_{i}", value=f"value_{i}")

        # Check distribution
        status = await cluster[0].GetClusterStatus()
        counts = [m.keys_count for m in status.members]

        avg = sum(counts) / len(counts)
        std_dev = (sum((c - avg)**2 for c in counts) / len(counts)) ** 0.5

        # Standard deviation should be < 10% of average
        assert std_dev / avg < 0.10

    async def test_minimal_redistribution_on_add(self, cluster):
        """Adding a node moves only K/N keys."""
        # Insert keys
        for i in range(1000):
            await cluster[0].Put(key=f"key_{i}", value=f"value_{i}")

        # Record current distribution
        before = {}
        for node in cluster:
            keys = await node.GetLocalKeys()
            before[node.node_id] = set(k.key for k in keys.keys)

        # Add new node
        new_node = await platform_api.add_node()
        await cluster[0].AddNode(new_node.node_id, new_node.address)

        # Check redistribution
        after = {}
        for node in cluster + [new_node]:
            keys = await node.GetLocalKeys()
            after[node.node_id] = set(k.key for k in keys.keys)

        # Calculate keys moved
        keys_moved = 0
        for node_id in before:
            keys_moved += len(before[node_id] - after.get(node_id, set()))

        # Should move approximately 1000 / (N+1) keys
        expected_moves = 1000 / (len(cluster) + 1)
        assert 0.5 * expected_moves < keys_moved < 1.5 * expected_moves

    async def test_node_failure_data_available(self, cluster):
        """Data remains available after node failure (with replication)."""
        # Insert with replication
        await cluster[0].Put(key="important", value="data", replicas=3)

        # Verify all replicas
        nodes = await cluster[0].GetNodes(key="important", count=3)
        assert len(nodes.nodes) == 3

        # Kill one replica
        await platform_api.stop_service(nodes.nodes[0].node_id)

        # Data should still be available
        response = await cluster[1].Get(key="important")
        assert response.found
        assert response.value == "data"
```

### Performance Tests

```python
async def test_lookup_performance(self, cluster):
    """Lookup should be O(log N) in virtual nodes."""
    import time

    # Insert keys
    for i in range(10000):
        await cluster[0].Put(key=f"key_{i}", value=f"value_{i}")

    # Measure lookup time
    start = time.time()
    for i in range(1000):
        await cluster[0].Get(key=f"key_{i % 10000}")
    duration = time.time() - start

    # Should be < 5ms average per lookup
    assert duration / 1000 < 0.005
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Key Distribution | Std dev < 10% of average |
| Node Addition | Moves ~K/N keys only |
| Node Removal | Data preserved with replicas |
| Lookup Performance | < 5ms per lookup |
