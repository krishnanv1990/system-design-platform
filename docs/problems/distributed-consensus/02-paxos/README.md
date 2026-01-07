# Paxos Consensus Algorithm

## Problem Overview

Implement the Paxos consensus algorithm to achieve agreement on a single value among a cluster of nodes, even with failures.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution

### Algorithm Overview

Paxos has three phases:
1. **Prepare:** Proposer requests promise from acceptors
2. **Accept:** Proposer sends accept request with value
3. **Learn:** Value is learned when majority accepts

### Roles

- **Proposer:** Proposes values and drives the protocol
- **Acceptor:** Votes on proposals and stores accepted values
- **Learner:** Learns the decided value

### Implementation

```python
@dataclass
class Proposal:
    number: int  # Proposal number (globally unique)
    value: Any

class PaxosNode:
    def __init__(self, node_id: str, peers: List[str]):
        self.node_id = node_id
        self.peers = peers

        # Acceptor state
        self.promised_number = 0
        self.accepted_proposal: Optional[Proposal] = None

        # Proposer state
        self.proposal_counter = 0

    # ===== Proposer =====

    async def propose(self, value: Any) -> Any:
        """Propose a value and drive consensus."""
        while True:
            # Generate proposal number
            proposal_num = self.generate_proposal_number()

            # Phase 1: Prepare
            promises = await self.send_prepare(proposal_num)

            if len(promises) < self.majority():
                continue  # Retry with higher number

            # Use highest accepted value, or our value
            value_to_propose = self.get_highest_value(promises) or value

            # Phase 2: Accept
            accepts = await self.send_accept(proposal_num, value_to_propose)

            if len(accepts) >= self.majority():
                return value_to_propose  # Consensus reached!

    async def send_prepare(self, proposal_num: int) -> List[PrepareResponse]:
        """Send Prepare to all acceptors."""
        promises = []
        for peer in self.all_nodes():
            try:
                response = await peer.Prepare(PrepareRequest(
                    proposal_number=proposal_num
                ))
                if response.promised:
                    promises.append(response)
            except Exception:
                pass
        return promises

    # ===== Acceptor =====

    async def handle_prepare(self, request: PrepareRequest) -> PrepareResponse:
        """Handle Prepare request."""
        if request.proposal_number > self.promised_number:
            self.promised_number = request.proposal_number

            return PrepareResponse(
                promised=True,
                accepted_proposal=self.accepted_proposal.number
                    if self.accepted_proposal else 0,
                accepted_value=self.accepted_proposal.value
                    if self.accepted_proposal else None
            )

        return PrepareResponse(promised=False)

    async def handle_accept(self, request: AcceptRequest) -> AcceptResponse:
        """Handle Accept request."""
        if request.proposal_number >= self.promised_number:
            self.promised_number = request.proposal_number
            self.accepted_proposal = Proposal(
                number=request.proposal_number,
                value=request.value
            )
            return AcceptResponse(accepted=True)

        return AcceptResponse(accepted=False)
```

### Multi-Paxos for Replication

```python
class MultiPaxosNode:
    """Multi-Paxos for replicated log."""

    def __init__(self):
        self.log: Dict[int, Proposal] = {}  # slot -> decided value
        self.next_slot = 0

    async def replicate(self, value: Any) -> int:
        """Replicate a value to the log."""
        slot = self.next_slot
        self.next_slot += 1

        decided_value = await self.paxos_instance(slot).propose(value)
        self.log[slot] = decided_value

        return slot
```

---

## Platform Deployment

### Deployment Configuration

- **5-node cluster** (recommended for production fault tolerance)
- Each node acts as proposer, acceptor, and learner
- gRPC communication between nodes
- Quorum: 3 nodes (majority of 5)
- Fault tolerance: 2 node failures

```yaml
# Deployed 5-node cluster
nodes:
  - id: node-0
    url: https://paxos-sub123-node0.run.app
    port: 8080
  - id: node-1
    url: https://paxos-sub123-node1.run.app
    port: 8080
  - id: node-2
    url: https://paxos-sub123-node2.run.app
    port: 8080
  - id: node-3
    url: https://paxos-sub123-node3.run.app
    port: 8080
  - id: node-4
    url: https://paxos-sub123-node4.run.app
    port: 8080
```

### gRPC Services

```protobuf
service PaxosService {
    rpc Prepare(PrepareRequest) returns (PrepareResponse);
    rpc Accept(AcceptRequest) returns (AcceptResponse);
}

service KeyValueService {
    rpc Get(GetRequest) returns (GetResponse);
    rpc Put(PutRequest) returns (PutResponse);
    rpc GetLeader(GetLeaderRequest) returns (GetLeaderResponse);
}
```

---

## Realistic Testing

### Functional Tests

```python
class TestPaxos:
    async def test_single_proposer(self, cluster):
        """Single proposer achieves consensus."""
        result = await cluster[0].propose("value1")
        assert result == "value1"

        # All nodes should learn the value
        for node in cluster:
            learned = await node.get_learned_value()
            assert learned == "value1"

    async def test_concurrent_proposers(self, cluster):
        """Concurrent proposers converge to same value."""
        # All nodes propose different values concurrently
        tasks = [
            node.propose(f"value_from_{i}")
            for i, node in enumerate(cluster)
        ]

        results = await asyncio.gather(*tasks)

        # All should agree on same value
        assert len(set(results)) == 1

    async def test_minority_failure(self, cluster):
        """Consensus achievable with minority failure."""
        # Kill one node
        await platform_api.stop_service(cluster[2].node_id)

        # Should still reach consensus
        result = await cluster[0].propose("surviving")
        assert result == "surviving"
```

### Chaos Tests

```python
async def test_proposer_crash_recovery(self, cluster):
    """New proposer completes after crash."""
    # Start proposal on node 0
    task = asyncio.create_task(cluster[0].propose("initial"))

    # Kill node 0 before completion
    await asyncio.sleep(0.1)
    await platform_api.stop_service(cluster[0].node_id)

    # Node 1 should complete consensus
    result = await cluster[1].propose("recovery")

    # Value should be consistent
    learned = await cluster[2].get_learned_value()
    assert learned in ["initial", "recovery"]
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Single Proposer | Reaches consensus |
| Concurrent Proposers | Same value chosen |
| Single Node Failure | Continues with 4/5 nodes |
| Double Node Failure | Continues with 3/5 nodes (quorum) |
| Majority Failure (3+) | Blocks until recovery |
| Proposer Crash | Recovery succeeds |
