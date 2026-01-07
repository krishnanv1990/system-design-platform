# Conflict-free Replicated Data Types (CRDTs)

## Problem Overview

Implement distributed CRDTs for eventual consistency without coordination, allowing concurrent updates on any replica that automatically merge without conflicts.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution

### CRDT Types Overview

CRDTs guarantee eventual consistency by ensuring all merge operations are:
- **Commutative:** order doesn't matter
- **Associative:** grouping doesn't matter
- **Idempotent:** duplicate merges are safe

### Implementation

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Set, List, Optional, Any
import time
import uuid

# ==========================================
# G-Counter (Grow-only Counter)
# ==========================================

class GCounter:
    """Grow-only counter - can only increment."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.counts: Dict[str, int] = {}

    def increment(self, amount: int = 1):
        """Increment the counter for this node."""
        self.counts[self.node_id] = self.counts.get(self.node_id, 0) + amount

    def value(self) -> int:
        """Get the current value (sum of all node counts)."""
        return sum(self.counts.values())

    def merge(self, other: 'GCounter'):
        """Merge another G-Counter into this one."""
        for node_id, count in other.counts.items():
            self.counts[node_id] = max(
                self.counts.get(node_id, 0),
                count
            )

    def to_state(self) -> Dict[str, int]:
        """Serialize state for transmission."""
        return self.counts.copy()

    @classmethod
    def from_state(cls, node_id: str, state: Dict[str, int]) -> 'GCounter':
        """Create from serialized state."""
        counter = cls(node_id)
        counter.counts = state.copy()
        return counter


# ==========================================
# PN-Counter (Positive-Negative Counter)
# ==========================================

class PNCounter:
    """Counter that supports both increment and decrement."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.positive = GCounter(node_id)
        self.negative = GCounter(node_id)

    def increment(self, amount: int = 1):
        """Increment the counter."""
        self.positive.increment(amount)

    def decrement(self, amount: int = 1):
        """Decrement the counter."""
        self.negative.increment(amount)

    def value(self) -> int:
        """Get current value (positive - negative)."""
        return self.positive.value() - self.negative.value()

    def merge(self, other: 'PNCounter'):
        """Merge another PN-Counter."""
        self.positive.merge(other.positive)
        self.negative.merge(other.negative)


# ==========================================
# G-Set (Grow-only Set)
# ==========================================

class GSet:
    """Grow-only set - can only add elements."""

    def __init__(self):
        self.elements: Set[str] = set()

    def add(self, element: str):
        """Add an element to the set."""
        self.elements.add(element)

    def contains(self, element: str) -> bool:
        """Check if element is in set."""
        return element in self.elements

    def value(self) -> Set[str]:
        """Get all elements."""
        return self.elements.copy()

    def merge(self, other: 'GSet'):
        """Merge another G-Set (union)."""
        self.elements = self.elements.union(other.elements)


# ==========================================
# OR-Set (Observed-Remove Set)
# ==========================================

@dataclass
class ORSetElement:
    value: str
    unique_tag: str
    added_by: str

class ORSet:
    """Set that supports both add and remove operations."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.elements: Dict[str, Set[str]] = {}  # value -> set of unique_tags
        self.tombstones: Set[str] = set()  # removed unique_tags

    def add(self, value: str):
        """Add an element with a unique tag."""
        unique_tag = f"{self.node_id}:{uuid.uuid4()}"

        if value not in self.elements:
            self.elements[value] = set()
        self.elements[value].add(unique_tag)

    def remove(self, value: str) -> bool:
        """Remove all instances of an element."""
        if value not in self.elements:
            return False

        # Add all tags to tombstones
        tags = self.elements[value]
        self.tombstones.update(tags)
        del self.elements[value]
        return True

    def contains(self, value: str) -> bool:
        """Check if value is in set."""
        return value in self.elements and len(self.elements[value]) > 0

    def value(self) -> Set[str]:
        """Get all current elements."""
        return set(self.elements.keys())

    def merge(self, other: 'ORSet'):
        """Merge another OR-Set."""
        # Merge tombstones
        self.tombstones.update(other.tombstones)

        # Merge elements
        for value, tags in other.elements.items():
            if value not in self.elements:
                self.elements[value] = set()
            self.elements[value].update(tags)

        # Remove tombstoned elements
        for value in list(self.elements.keys()):
            self.elements[value] -= self.tombstones
            if not self.elements[value]:
                del self.elements[value]


# ==========================================
# LWW-Register (Last-Writer-Wins Register)
# ==========================================

class LWWRegister:
    """Register where last write (by timestamp) wins."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.value: Optional[str] = None
        self.timestamp: int = 0
        self.writer: Optional[str] = None

    def set(self, value: str, timestamp: int = None):
        """Set the register value."""
        ts = timestamp or int(time.time() * 1000000)  # microseconds

        if ts > self.timestamp:
            self.value = value
            self.timestamp = ts
            self.writer = self.node_id

    def get(self) -> Optional[str]:
        """Get current value."""
        return self.value

    def merge(self, other: 'LWWRegister'):
        """Merge - keep value with higher timestamp."""
        if other.timestamp > self.timestamp:
            self.value = other.value
            self.timestamp = other.timestamp
            self.writer = other.writer


# ==========================================
# MV-Register (Multi-Value Register)
# ==========================================

@dataclass
class VectorClock:
    clock: Dict[str, int] = field(default_factory=dict)

    def increment(self, node_id: str):
        self.clock[node_id] = self.clock.get(node_id, 0) + 1

    def merge(self, other: 'VectorClock'):
        for node_id, time in other.clock.items():
            self.clock[node_id] = max(self.clock.get(node_id, 0), time)

    def __le__(self, other: 'VectorClock') -> bool:
        """Check if this clock is dominated by other."""
        for node_id, time in self.clock.items():
            if time > other.clock.get(node_id, 0):
                return False
        return True

    def concurrent_with(self, other: 'VectorClock') -> bool:
        """Check if clocks are concurrent (neither dominates)."""
        return not (self <= other) and not (other <= self)


class MVRegister:
    """Register that keeps all concurrent values."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.values: List[tuple] = []  # List of (value, VectorClock)
        self.clock = VectorClock()

    def set(self, value: str):
        """Set a new value, superseding old ones."""
        self.clock.increment(self.node_id)

        # Remove all values dominated by new clock
        new_clock = VectorClock()
        new_clock.clock = self.clock.clock.copy()

        self.values = [(value, new_clock)]

    def get(self) -> List[str]:
        """Get all current values (may be multiple if concurrent)."""
        return [v for v, _ in self.values]

    def merge(self, other: 'MVRegister'):
        """Merge - keep all concurrent values."""
        self.clock.merge(other.clock)

        all_values = self.values + other.values
        result = []

        for value, clock in all_values:
            # Keep if not dominated by any other
            dominated = False
            for other_value, other_clock in all_values:
                if clock != other_clock and clock <= other_clock:
                    dominated = True
                    break

            if not dominated:
                # Check for duplicates
                is_dup = any(
                    v == value and c.clock == clock.clock
                    for v, c in result
                )
                if not is_dup:
                    result.append((value, clock))

        self.values = result
```

---

## Platform Deployment

### Cluster Configuration

- **5-node cluster** (CRDTs are leaderless, highly partition tolerant)
- Periodic sync between nodes
- Each node accepts writes locally
- Tolerates 2 node failures (continues operating even during partitions)

### gRPC Services

```protobuf
service CRDTService {
    // Counter operations
    rpc IncrementCounter(IncrementCounterRequest) returns (IncrementCounterResponse);
    rpc DecrementCounter(DecrementCounterRequest) returns (DecrementCounterResponse);
    rpc GetCounter(GetCounterRequest) returns (GetCounterResponse);

    // Set operations
    rpc AddToSet(AddToSetRequest) returns (AddToSetResponse);
    rpc RemoveFromSet(RemoveFromSetRequest) returns (RemoveFromSetResponse);
    rpc GetSet(GetSetRequest) returns (GetSetResponse);

    // Register operations
    rpc SetRegister(SetRegisterRequest) returns (SetRegisterResponse);
    rpc GetRegister(GetRegisterRequest) returns (GetRegisterResponse);
}

service ReplicationService {
    rpc Merge(MergeRequest) returns (MergeResponse);
    rpc SyncAll(SyncAllRequest) returns (SyncAllResponse);
}
```

---

## Realistic Testing

### Functional Tests

```python
class TestCRDT:
    async def test_g_counter_convergence(self, cluster):
        """G-Counters converge after concurrent updates."""
        counter_id = "test_counter"

        # Each node increments concurrently
        await asyncio.gather(
            cluster[0].IncrementCounter(counter_id, amount=10),
            cluster[1].IncrementCounter(counter_id, amount=20),
            cluster[2].IncrementCounter(counter_id, amount=30),
        )

        # Trigger sync
        await trigger_sync(cluster)
        await asyncio.sleep(1)

        # All nodes should have same value
        values = await asyncio.gather(*[
            node.GetCounter(counter_id)
            for node in cluster
        ])

        assert all(v.value == 60 for v in values)

    async def test_pn_counter_with_decrements(self, cluster):
        """PN-Counter handles increments and decrements."""
        counter_id = "pn_counter"

        # Concurrent increments and decrements
        await asyncio.gather(
            cluster[0].IncrementCounter(counter_id, amount=100),
            cluster[1].DecrementCounter(counter_id, amount=30),
            cluster[2].IncrementCounter(counter_id, amount=50),
        )

        await trigger_sync(cluster)
        await asyncio.sleep(1)

        values = await asyncio.gather(*[
            node.GetCounter(counter_id)
            for node in cluster
        ])

        # 100 - 30 + 50 = 120
        assert all(v.value == 120 for v in values)

    async def test_or_set_add_remove(self, cluster):
        """OR-Set handles concurrent add and remove."""
        set_id = "test_set"

        # Add on node 0
        await cluster[0].AddToSet(set_id, element="apple")

        await trigger_sync(cluster)

        # Concurrent: node 1 adds, node 2 removes
        await asyncio.gather(
            cluster[1].AddToSet(set_id, element="apple"),  # Re-add
            cluster[2].RemoveFromSet(set_id, element="apple"),
        )

        await trigger_sync(cluster)
        await asyncio.sleep(1)

        # Add wins (add-wins semantics) - apple should be present
        # Because node 1's add has a new unique tag
        results = await asyncio.gather(*[
            node.GetSet(set_id)
            for node in cluster
        ])

        assert all("apple" in r.elements for r in results)

    async def test_lww_register_last_write_wins(self, cluster):
        """LWW-Register keeps value with highest timestamp."""
        register_id = "lww_test"

        # Write at different times
        await cluster[0].SetRegister(register_id, value="first", timestamp=1000)
        await cluster[1].SetRegister(register_id, value="second", timestamp=2000)
        await cluster[2].SetRegister(register_id, value="third", timestamp=1500)

        await trigger_sync(cluster)
        await asyncio.sleep(1)

        results = await asyncio.gather(*[
            node.GetRegister(register_id)
            for node in cluster
        ])

        # "second" has highest timestamp
        assert all(r.values == ["second"] for r in results)

    async def test_mv_register_concurrent_values(self, cluster):
        """MV-Register keeps all concurrent values."""
        register_id = "mv_test"

        # Concurrent writes (no causal relationship)
        await asyncio.gather(
            cluster[0].SetRegister(register_id, value="alice"),
            cluster[1].SetRegister(register_id, value="bob"),
        )

        await trigger_sync(cluster)
        await asyncio.sleep(1)

        results = await asyncio.gather(*[
            node.GetRegister(register_id)
            for node in cluster
        ])

        # Both values should be present (concurrent)
        for r in results:
            assert "alice" in r.values
            assert "bob" in r.values

    async def test_partition_and_heal(self, cluster):
        """CRDTs converge after network partition heals."""
        counter_id = "partition_test"

        # Partition node 2
        await platform_api.partition_node(cluster[2].node_id)

        # Updates on both sides of partition
        await cluster[0].IncrementCounter(counter_id, amount=100)
        await cluster[2].IncrementCounter(counter_id, amount=50)

        # Heal partition
        await platform_api.heal_partition()
        await trigger_sync(cluster)
        await asyncio.sleep(2)

        # All should converge
        values = await asyncio.gather(*[
            node.GetCounter(counter_id)
            for node in cluster
        ])

        assert all(v.value == 150 for v in values)
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Counter Convergence | All nodes agree after sync |
| OR-Set Add/Remove | Add-wins semantics work |
| LWW Register | Highest timestamp wins |
| MV Register | Concurrent values preserved |
| Partition Healing | Converges after partition |
