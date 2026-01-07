# Raft Consensus Algorithm

## Problem Overview

Implement the Raft consensus algorithm to maintain a replicated log across a cluster of nodes, ensuring strong consistency despite node failures.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution

### Algorithm Overview

Raft divides consensus into three sub-problems:
1. **Leader Election:** Elect a single leader for the cluster
2. **Log Replication:** Leader replicates log entries to followers
3. **Safety:** Ensure logs are consistent and committed entries are durable

### Key State

```python
class RaftNode:
    def __init__(self, node_id: str, peers: List[str]):
        # Persistent state
        self.current_term = 0
        self.voted_for = None
        self.log: List[LogEntry] = []

        # Volatile state
        self.commit_index = 0
        self.last_applied = 0
        self.state = "follower"  # follower, candidate, leader

        # Leader state
        self.next_index: Dict[str, int] = {}
        self.match_index: Dict[str, int] = {}
```

### Leader Election

```python
async def start_election(self):
    """Start leader election."""
    self.current_term += 1
    self.state = "candidate"
    self.voted_for = self.node_id

    votes = 1  # Vote for self
    last_log_index = len(self.log)
    last_log_term = self.log[-1].term if self.log else 0

    # Request votes from all peers
    for peer in self.peers:
        response = await self.send_request_vote(peer, RequestVoteRequest(
            term=self.current_term,
            candidate_id=self.node_id,
            last_log_index=last_log_index,
            last_log_term=last_log_term
        ))

        if response.vote_granted:
            votes += 1

    # Check if won election
    if votes > len(self.peers) // 2:
        self.become_leader()
```

### Log Replication

```python
async def append_entries(self, peer: str):
    """Send AppendEntries RPC to a peer."""
    prev_log_index = self.next_index[peer] - 1
    prev_log_term = self.log[prev_log_index].term if prev_log_index > 0 else 0

    entries = self.log[self.next_index[peer]:]

    response = await self.send_append_entries(peer, AppendEntriesRequest(
        term=self.current_term,
        leader_id=self.node_id,
        prev_log_index=prev_log_index,
        prev_log_term=prev_log_term,
        entries=entries,
        leader_commit=self.commit_index
    ))

    if response.success:
        self.next_index[peer] = len(self.log)
        self.match_index[peer] = len(self.log) - 1
        self.try_advance_commit_index()
    else:
        # Decrement next_index and retry
        self.next_index[peer] = max(1, self.next_index[peer] - 1)
```

### gRPC Service Definition

The platform expects implementations of these services from `raft.proto`:

```protobuf
service RaftService {
    rpc RequestVote(RequestVoteRequest) returns (RequestVoteResponse);
    rpc AppendEntries(AppendEntriesRequest) returns (AppendEntriesResponse);
    rpc InstallSnapshot(InstallSnapshotRequest) returns (InstallSnapshotResponse);
}

service KeyValueService {
    rpc Get(GetRequest) returns (GetResponse);
    rpc Put(PutRequest) returns (PutResponse);
    rpc Delete(DeleteRequest) returns (DeleteResponse);
    rpc GetLeader(GetLeaderRequest) returns (GetLeaderResponse);
    rpc GetClusterStatus(GetClusterStatusRequest) returns (GetClusterStatusResponse);
}
```

---

## Platform Deployment

### How the Platform Deploys This Solution

1. **Code Submission:** User submits implementation in Python, Go, Java, C++, or Rust
2. **Build Phase:**
   - Cloud Build compiles the code
   - Security analysis (race detection, memory checks)
   - Proto stubs generated for the language
3. **Deployment:**
   - 5-node cluster deployed on Cloud Run for higher fault tolerance
   - Each node runs as separate service with unique node ID
   - Nodes discover each other via environment variables
   - 5-node cluster tolerates 2 node failures (vs 1 for 3-node)
4. **Testing:**
   - Functional tests against the cluster
   - Chaos tests (node failures, network partitions)

### Cluster Configuration

```yaml
# Deployed 5-node cluster (tolerates 2 failures)
nodes:
  - id: node-0
    url: https://raft-sub123-node0.run.app
    port: 8080
  - id: node-1
    url: https://raft-sub123-node1.run.app
    port: 8080
  - id: node-2
    url: https://raft-sub123-node2.run.app
    port: 8080
  - id: node-3
    url: https://raft-sub123-node3.run.app
    port: 8080
  - id: node-4
    url: https://raft-sub123-node4.run.app
    port: 8080

# Quorum: 3 nodes (majority of 5)
# Fault tolerance: 2 node failures
```

---

## Realistic Testing

### 1. Functional Tests (Platform-Executed)

```python
class TestRaftConsensus:
    async def test_leader_election(self, cluster):
        """Verify cluster elects a single leader."""
        await asyncio.sleep(5)  # Wait for election

        leaders = []
        for node in cluster:
            status = await node.GetClusterStatus()
            if status.state == "leader":
                leaders.append(node.node_id)

        assert len(leaders) == 1

    async def test_basic_replication(self, cluster):
        """Test key-value replication."""
        leader = await find_leader(cluster)

        # Put value
        await leader.Put(key="test", value="hello")

        # Read from all nodes
        for node in cluster:
            response = await node.Get(key="test")
            assert response.value == "hello"

    async def test_leader_failover(self, cluster):
        """Test new leader elected when leader fails."""
        leader = await find_leader(cluster)
        original_leader_id = leader.node_id

        # Write some data
        await leader.Put(key="before_failover", value="data")

        # Kill leader
        await platform_api.stop_service(leader.node_id)

        # Wait for new election
        await asyncio.sleep(10)

        # Find new leader
        remaining_nodes = [n for n in cluster if n.node_id != original_leader_id]
        new_leader = await find_leader(remaining_nodes)

        assert new_leader.node_id != original_leader_id

        # Data should still be available
        response = await new_leader.Get(key="before_failover")
        assert response.value == "data"

    async def test_partition_healing(self, cluster):
        """Test cluster recovers after network partition."""
        leader = await find_leader(cluster)

        # Write data
        await leader.Put(key="pre_partition", value="exists")

        # Create partition (isolate one node)
        await platform_api.partition_node(cluster[2].node_id)

        # Should still work with majority
        await leader.Put(key="during_partition", value="works")

        # Heal partition
        await platform_api.heal_partition()
        await asyncio.sleep(5)

        # All nodes should have both keys
        for node in cluster:
            r1 = await node.Get(key="pre_partition")
            r2 = await node.Get(key="during_partition")
            assert r1.value == "exists"
            assert r2.value == "works"
```

### 2. Chaos Engineering Tests

```python
class TestRaftChaos:
    async def test_single_failure(self, cluster):
        """Cluster survives single node failure (5-node cluster)."""
        leader = await find_leader(cluster)

        # Kill one node - still have 4 nodes (quorum = 3)
        await platform_api.stop_service(cluster[1].node_id)

        # Operations should still work
        await leader.Put(key="single_fail", value="ok")
        response = await leader.Get(key="single_fail")
        assert response.value == "ok"

    async def test_double_failure(self, cluster):
        """Cluster survives two node failures (5-node cluster)."""
        leader = await find_leader(cluster)

        # Kill two nodes - still have 3 nodes (exactly quorum)
        await platform_api.stop_service(cluster[1].node_id)
        await platform_api.stop_service(cluster[2].node_id)

        # Operations should still work (3 nodes = quorum for 5-node cluster)
        await leader.Put(key="double_fail", value="ok")
        response = await leader.Get(key="double_fail")
        assert response.value == "ok"

    async def test_majority_failure_blocks(self, cluster):
        """Cluster blocks on majority failure (3+ nodes down in 5-node cluster)."""
        leader = await find_leader(cluster)

        # Kill three nodes (no longer have quorum)
        await platform_api.stop_service(cluster[1].node_id)
        await platform_api.stop_service(cluster[2].node_id)
        await platform_api.stop_service(cluster[3].node_id)

        # Operations should block or fail
        with pytest.raises(Exception):
            await asyncio.wait_for(
                leader.Put(key="should_fail", value="blocked"),
                timeout=5
            )

    async def test_log_consistency_under_stress(self, cluster):
        """Verify log consistency under concurrent operations."""
        leader = await find_leader(cluster)

        # Concurrent writes
        tasks = [
            leader.Put(key=f"key_{i}", value=f"val_{i}")
            for i in range(100)
        ]
        await asyncio.gather(*tasks)

        # Verify all nodes have consistent state
        await asyncio.sleep(2)

        statuses = [await n.GetClusterStatus() for n in cluster]
        log_lengths = [s.log_length for s in statuses]

        # All should have same log length
        assert len(set(log_lengths)) == 1
```

### 3. Performance Tests

```python
class TestRaftPerformance:
    async def test_write_throughput(self, cluster):
        """Measure write throughput."""
        leader = await find_leader(cluster)

        start = time.time()
        for i in range(1000):
            await leader.Put(key=f"perf_{i}", value=f"value_{i}")
        duration = time.time() - start

        writes_per_second = 1000 / duration
        assert writes_per_second > 100  # At least 100 writes/sec

    async def test_read_latency(self, cluster):
        """Measure read latency."""
        leader = await find_leader(cluster)
        await leader.Put(key="latency_test", value="data")

        latencies = []
        for _ in range(100):
            start = time.time()
            await leader.Get(key="latency_test")
            latencies.append(time.time() - start)

        p50 = sorted(latencies)[50]
        p99 = sorted(latencies)[99]

        assert p50 < 0.01  # 10ms p50
        assert p99 < 0.05  # 50ms p99
```

### 4. Manual Testing with gRPC

```bash
# Use grpcurl to interact with the cluster

# Check cluster status
grpcurl -plaintext \
  -d '{}' \
  raft-node0.run.app:443 raft.KeyValueService/GetClusterStatus

# Put a value
grpcurl -plaintext \
  -d '{"key": "mykey", "value": "myvalue"}' \
  raft-node0.run.app:443 raft.KeyValueService/Put

# Get a value
grpcurl -plaintext \
  -d '{"key": "mykey"}' \
  raft-node0.run.app:443 raft.KeyValueService/Get

# Find leader
grpcurl -plaintext \
  -d '{}' \
  raft-node0.run.app:443 raft.KeyValueService/GetLeader
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Leader Election | Elects single leader within 5 seconds |
| Log Replication | All 5 nodes converge to same state |
| Single Node Failure | Continues operating with 1 node down (4/5 nodes) |
| Double Node Failure | Continues operating with 2 nodes down (3/5 nodes = quorum) |
| Majority Failure | Blocks operations when 3+ nodes down (safety) |
| Partition Healing | Reconciles state after partition |
| Write Throughput | > 100 writes/second |
| Read Latency (p99) | < 50ms |

---

## Common Pitfalls

1. **Split brain:** Allowing multiple leaders in same term
2. **Log divergence:** Not properly checking prev_log_term
3. **Commit safety:** Committing entries from previous terms incorrectly
4. **Election timing:** Too aggressive election timeouts causing instability
5. **Missing persistence:** Not persisting state before responding
