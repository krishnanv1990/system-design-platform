# Two-Phase Commit (2PC)

## Problem Overview

Implement the Two-Phase Commit protocol for distributed transactions across multiple participants.

**Difficulty:** Medium (L6 - Staff Engineer)

---

## Best Solution

### Protocol Overview

**Phase 1 - Prepare:**
- Coordinator sends PREPARE to all participants
- Participants acquire locks and vote COMMIT or ABORT

**Phase 2 - Commit/Abort:**
- If all vote COMMIT: Coordinator sends COMMIT to all
- If any votes ABORT: Coordinator sends ABORT to all

### Implementation

```python
class TwoPhaseCommitCoordinator:
    def __init__(self, participants: List[str]):
        self.participants = participants
        self.transactions: Dict[str, Transaction] = {}

    async def begin_transaction(self) -> str:
        """Start a new distributed transaction."""
        tx_id = str(uuid.uuid4())
        self.transactions[tx_id] = Transaction(
            id=tx_id,
            state="active",
            participants=self.participants.copy()
        )
        return tx_id

    async def commit_transaction(self, tx_id: str) -> bool:
        """Commit a transaction using 2PC."""
        tx = self.transactions[tx_id]

        # Phase 1: Prepare
        tx.state = "preparing"
        votes = await self.send_prepare(tx_id, tx.operations)

        if all(v.vote == "commit" for v in votes):
            # Phase 2: Commit
            tx.state = "committing"
            await self.send_commit(tx_id)
            tx.state = "committed"
            return True
        else:
            # Phase 2: Abort
            tx.state = "aborting"
            await self.send_abort(tx_id)
            tx.state = "aborted"
            return False

    async def send_prepare(self, tx_id: str, operations: List) -> List:
        """Send Prepare to all participants."""
        tasks = [
            self.rpc_client.Prepare(p, PrepareRequest(
                transaction_id=tx_id,
                operations=operations[p]
            ))
            for p in self.participants
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)


class TwoPhaseCommitParticipant:
    def __init__(self):
        self.pending_txs: Dict[str, PendingTransaction] = {}
        self.locks: Dict[str, str] = {}  # key -> tx_id

    async def handle_prepare(self, request: PrepareRequest) -> PrepareResponse:
        """Handle Prepare request from coordinator."""
        tx_id = request.transaction_id

        # Try to acquire locks
        for op in request.operations:
            if op.key in self.locks:
                # Key already locked
                return PrepareResponse(vote="abort", reason="lock conflict")

        # Acquire locks and persist to WAL
        for op in request.operations:
            self.locks[op.key] = tx_id

        await self.wal.write(tx_id, "prepared", request.operations)

        self.pending_txs[tx_id] = PendingTransaction(
            id=tx_id,
            operations=request.operations,
            state="prepared"
        )

        return PrepareResponse(vote="commit")

    async def handle_commit(self, request: CommitRequest) -> CommitResponse:
        """Handle Commit request from coordinator."""
        tx_id = request.transaction_id
        tx = self.pending_txs.get(tx_id)

        if tx:
            # Apply operations
            for op in tx.operations:
                await self.apply_operation(op)
                del self.locks[op.key]

            await self.wal.write(tx_id, "committed")
            del self.pending_txs[tx_id]

        return CommitResponse(success=True)
```

---

## Platform Deployment

### Cluster Configuration

- 1 Coordinator node
- 2+ Participant nodes
- Each node implements both roles for flexibility

### gRPC Services

```protobuf
service CoordinatorService {
    rpc BeginTransaction(BeginTransactionRequest) returns (BeginTransactionResponse);
    rpc CommitTransaction(CommitTransactionRequest) returns (CommitTransactionResponse);
    rpc AbortTransaction(AbortTransactionRequest) returns (AbortTransactionResponse);
}

service ParticipantService {
    rpc Prepare(PrepareRequest) returns (PrepareResponse);
    rpc Commit(CommitRequest) returns (CommitResponse);
    rpc Abort(AbortRequest) returns (AbortResponse);
}
```

---

## Realistic Testing

```python
class TestTwoPhaseCommit:
    async def test_successful_commit(self, cluster):
        """All participants agree to commit."""
        coordinator = cluster[0]
        tx_id = await coordinator.BeginTransaction()

        await coordinator.ExecuteOperation(tx_id, "put", "key1", "value1")
        await coordinator.ExecuteOperation(tx_id, "put", "key2", "value2")

        result = await coordinator.CommitTransaction(tx_id)
        assert result.success

        # Verify both keys exist
        assert await cluster[1].Get("key1") == "value1"
        assert await cluster[2].Get("key2") == "value2"

    async def test_abort_on_conflict(self, cluster):
        """Transaction aborts on lock conflict."""
        coordinator = cluster[0]

        tx1 = await coordinator.BeginTransaction()
        tx2 = await coordinator.BeginTransaction()

        await coordinator.ExecuteOperation(tx1, "put", "shared_key", "v1")
        await coordinator.ExecuteOperation(tx2, "put", "shared_key", "v2")

        # Commit tx1 first
        r1 = await coordinator.CommitTransaction(tx1)
        assert r1.success

        # tx2 should abort (lock conflict)
        r2 = await coordinator.CommitTransaction(tx2)
        assert not r2.success

    async def test_coordinator_failure_recovery(self, cluster):
        """Recovery after coordinator crashes during commit."""
        coordinator = cluster[0]
        tx_id = await coordinator.BeginTransaction()
        await coordinator.ExecuteOperation(tx_id, "put", "key", "value")

        # Crash coordinator after prepare
        await coordinator.send_prepare(tx_id)
        await platform_api.stop_service(coordinator.node_id)

        # Participants should be in uncertain state
        # Recovery requires coordinator restart or timeout
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Happy Path | All operations committed atomically |
| Lock Conflict | Transaction properly aborted |
| Partial Failure | Consistent abort across all participants |
