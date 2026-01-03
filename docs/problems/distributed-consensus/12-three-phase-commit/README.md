# Three-Phase Commit (3PC)

## Problem Overview

Implement the Three-Phase Commit protocol for non-blocking atomic commitment in distributed transactions.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution

### Protocol Overview

3PC improves on 2PC by adding a pre-commit phase:
1. **Phase 1 (CanCommit):** Coordinator asks if participants can commit
2. **Phase 2 (PreCommit):** If all agree, coordinator sends pre-commit
3. **Phase 3 (DoCommit):** Coordinator sends final commit/abort

**Key advantage:** Participants can recover from coordinator failure by communicating with each other (non-blocking property).

### Implementation

```python
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional
import asyncio

class TransactionState(Enum):
    INITIATED = "initiated"
    WAITING = "waiting"
    PRECOMMIT = "precommit"
    COMMITTING = "committing"
    COMMITTED = "committed"
    ABORTING = "aborting"
    ABORTED = "aborted"

class ParticipantState(Enum):
    INITIAL = "initial"
    UNCERTAIN = "uncertain"      # Voted YES, waiting for decision
    PRECOMMITTED = "precommitted"
    COMMITTED = "committed"
    ABORTED = "aborted"

@dataclass
class Transaction:
    transaction_id: str
    state: TransactionState
    participants: List[str]
    coordinator: str
    data: Dict[str, str]
    timeout_ms: int = 30000

class ThreePhaseCommitCoordinator:
    def __init__(self, node_id: str, participants: List[str]):
        self.node_id = node_id
        self.participants = participants
        self.transactions: Dict[str, Transaction] = {}

    async def begin_transaction(self, data: Dict[str, str],
                                timeout_ms: int = 30000) -> str:
        """Start a new distributed transaction."""
        tx_id = f"tx_{self.node_id}_{int(time.time() * 1000)}"

        self.transactions[tx_id] = Transaction(
            transaction_id=tx_id,
            state=TransactionState.INITIATED,
            participants=self.participants.copy(),
            coordinator=self.node_id,
            data=data,
            timeout_ms=timeout_ms
        )

        return tx_id

    async def commit_transaction(self, tx_id: str) -> bool:
        """Commit a transaction using 3PC."""
        tx = self.transactions.get(tx_id)
        if not tx:
            return False

        try:
            # Phase 1: CanCommit
            tx.state = TransactionState.WAITING
            can_commit = await self._phase1_can_commit(tx)

            if not can_commit:
                await self._abort(tx, "Participant voted NO")
                return False

            # Phase 2: PreCommit
            tx.state = TransactionState.PRECOMMIT
            pre_commit_ok = await self._phase2_pre_commit(tx)

            if not pre_commit_ok:
                await self._abort(tx, "PreCommit failed")
                return False

            # Phase 3: DoCommit
            tx.state = TransactionState.COMMITTING
            await self._phase3_do_commit(tx)

            tx.state = TransactionState.COMMITTED
            return True

        except asyncio.TimeoutError:
            await self._abort(tx, "Timeout")
            return False

    async def _phase1_can_commit(self, tx: Transaction) -> bool:
        """Phase 1: Ask all participants if they can commit."""
        tasks = [
            self._send_can_commit(p, tx)
            for p in tx.participants
        ]

        try:
            responses = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=tx.timeout_ms / 1000
            )

            # All must vote YES
            return all(
                r is True
                for r in responses
                if not isinstance(r, Exception)
            ) and not any(isinstance(r, Exception) for r in responses)

        except asyncio.TimeoutError:
            return False

    async def _phase2_pre_commit(self, tx: Transaction) -> bool:
        """Phase 2: Send PreCommit to all participants."""
        tasks = [
            self._send_pre_commit(p, tx)
            for p in tx.participants
        ]

        try:
            responses = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=tx.timeout_ms / 1000
            )

            return all(
                r is True
                for r in responses
                if not isinstance(r, Exception)
            )

        except asyncio.TimeoutError:
            return False

    async def _phase3_do_commit(self, tx: Transaction):
        """Phase 3: Send DoCommit to all participants."""
        tasks = [
            self._send_do_commit(p, tx)
            for p in tx.participants
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _abort(self, tx: Transaction, reason: str):
        """Abort the transaction."""
        tx.state = TransactionState.ABORTING

        tasks = [
            self._send_abort(p, tx, reason)
            for p in tx.participants
        ]

        await asyncio.gather(*tasks, return_exceptions=True)
        tx.state = TransactionState.ABORTED


class ThreePhaseCommitParticipant:
    """Participant in 3PC protocol."""

    def __init__(self, node_id: str, peers: List[str]):
        self.node_id = node_id
        self.peers = peers
        self.transactions: Dict[str, ParticipantState] = {}
        self.tx_data: Dict[str, Dict] = {}

    async def handle_can_commit(self, tx_id: str, coordinator: str,
                                data: Dict) -> bool:
        """Handle CanCommit request (Phase 1)."""
        # Validate we can commit
        can_commit = await self._validate_transaction(data)

        if can_commit:
            self.transactions[tx_id] = ParticipantState.UNCERTAIN
            self.tx_data[tx_id] = data
            return True
        else:
            self.transactions[tx_id] = ParticipantState.ABORTED
            return False

    async def handle_pre_commit(self, tx_id: str) -> bool:
        """Handle PreCommit request (Phase 2)."""
        if self.transactions.get(tx_id) != ParticipantState.UNCERTAIN:
            return False

        self.transactions[tx_id] = ParticipantState.PRECOMMITTED
        return True

    async def handle_do_commit(self, tx_id: str) -> bool:
        """Handle DoCommit request (Phase 3)."""
        if self.transactions.get(tx_id) != ParticipantState.PRECOMMITTED:
            return False

        # Apply the transaction
        await self._apply_transaction(tx_id)

        self.transactions[tx_id] = ParticipantState.COMMITTED
        return True

    async def handle_abort(self, tx_id: str):
        """Handle Abort request."""
        # Rollback any prepared state
        if tx_id in self.tx_data:
            del self.tx_data[tx_id]

        self.transactions[tx_id] = ParticipantState.ABORTED

    async def recover_from_timeout(self, tx_id: str):
        """Recovery protocol when coordinator fails."""
        state = self.transactions.get(tx_id)

        if state == ParticipantState.INITIAL:
            # Never received CanCommit - safe to abort
            self.transactions[tx_id] = ParticipantState.ABORTED
            return

        if state == ParticipantState.UNCERTAIN:
            # Coordinator might have aborted or sent PreCommit
            # Query peers to determine outcome
            peer_states = await self._query_peer_states(tx_id)

            if any(s == ParticipantState.ABORTED for s in peer_states):
                self.transactions[tx_id] = ParticipantState.ABORTED
            elif any(s == ParticipantState.COMMITTED for s in peer_states):
                await self._apply_transaction(tx_id)
                self.transactions[tx_id] = ParticipantState.COMMITTED
            elif any(s == ParticipantState.PRECOMMITTED for s in peer_states):
                # At least one is precommitted - continue to commit
                self.transactions[tx_id] = ParticipantState.PRECOMMITTED
                await self._apply_transaction(tx_id)
                self.transactions[tx_id] = ParticipantState.COMMITTED
            else:
                # All uncertain - safe to abort
                self.transactions[tx_id] = ParticipantState.ABORTED

        if state == ParticipantState.PRECOMMITTED:
            # We were precommitted - coordinator likely wants commit
            # Query peers to confirm
            peer_states = await self._query_peer_states(tx_id)

            if any(s == ParticipantState.COMMITTED for s in peer_states):
                await self._apply_transaction(tx_id)
                self.transactions[tx_id] = ParticipantState.COMMITTED
            elif all(s in [ParticipantState.PRECOMMITTED, ParticipantState.COMMITTED]
                    for s in peer_states if s):
                # Everyone is precommitted or committed - commit
                await self._apply_transaction(tx_id)
                self.transactions[tx_id] = ParticipantState.COMMITTED
            # If someone aborted, we have inconsistency - should not happen

    async def _query_peer_states(self, tx_id: str) -> List[ParticipantState]:
        """Query other participants for their state."""
        tasks = [
            self.rpc_client.QueryState(peer, tx_id)
            for peer in self.peers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r.state for r in results if not isinstance(r, Exception)]
```

---

## Platform Deployment

### Cluster Configuration

- 1 Coordinator + N Participants
- Each node can detect coordinator failure
- Participants can communicate for recovery

### gRPC Services

```protobuf
service CoordinatorService {
    rpc BeginTransaction(BeginTransactionRequest) returns (BeginTransactionResponse);
    rpc CommitTransaction(CommitTransactionRequest) returns (CommitTransactionResponse);
    rpc AbortTransaction(AbortTransactionRequest) returns (AbortTransactionResponse);
    rpc GetTransactionStatus(GetTransactionStatusRequest) returns (GetTransactionStatusResponse);
}

service ParticipantService {
    rpc CanCommit(CanCommitRequest) returns (CanCommitResponse);
    rpc PreCommit(PreCommitRequest) returns (PreCommitResponse);
    rpc DoCommit(DoCommitRequest) returns (DoCommitResponse);
    rpc DoAbort(DoAbortRequest) returns (DoAbortResponse);
}

service NodeService {
    rpc QueryState(QueryStateRequest) returns (QueryStateResponse);
    rpc Heartbeat(HeartbeatRequest) returns (HeartbeatResponse);
}
```

---

## Realistic Testing

### Functional Tests

```python
class TestThreePhaseCommit:
    async def test_successful_commit(self, cluster):
        """All participants agree to commit."""
        coordinator = cluster[0]
        tx_id = await coordinator.BeginTransaction(
            data={"key": "value"}
        )

        result = await coordinator.CommitTransaction(tx_id)
        assert result.success
        assert result.final_state == "COMMITTED"

        # Verify all participants committed
        for participant in cluster[1:]:
            state = await participant.GetState(tx_id)
            assert state.state == "COMMITTED"

    async def test_abort_on_no_vote(self, cluster):
        """Transaction aborts if any participant votes NO."""
        coordinator = cluster[0]

        # Configure one participant to reject
        await cluster[1].SetRejectNext(True)

        tx_id = await coordinator.BeginTransaction(
            data={"key": "value"}
        )

        result = await coordinator.CommitTransaction(tx_id)
        assert not result.success
        assert result.final_state == "ABORTED"

        # All participants should be aborted
        for participant in cluster[1:]:
            state = await participant.GetState(tx_id)
            assert state.state == "ABORTED"

    async def test_coordinator_failure_recovery(self, cluster):
        """Participants can recover after coordinator failure."""
        coordinator = cluster[0]

        tx_id = await coordinator.BeginTransaction(
            data={"key": "value"}
        )

        # Phase 1: CanCommit succeeds
        for p in cluster[1:]:
            await p.handle_can_commit(tx_id, coordinator.node_id, {"key": "value"})

        # Phase 2: PreCommit succeeds for first participant
        await cluster[1].handle_pre_commit(tx_id)

        # Coordinator crashes before PreCommit to others
        await platform_api.stop_service(coordinator.node_id)

        # Participants detect timeout and run recovery
        await asyncio.sleep(5)

        # Cluster[1] is precommitted, others are uncertain
        # Recovery should result in commit (someone is precommitted)
        for p in cluster[1:]:
            await p.recover_from_timeout(tx_id)

        # All should have committed
        for p in cluster[1:]:
            state = await p.GetState(tx_id)
            assert state.state == "COMMITTED"

    async def test_all_uncertain_aborts(self, cluster):
        """If all uncertain during recovery, abort."""
        coordinator = cluster[0]

        tx_id = await coordinator.BeginTransaction(
            data={"key": "value"}
        )

        # Phase 1 completes - all are uncertain
        for p in cluster[1:]:
            await p.handle_can_commit(tx_id, coordinator.node_id, {"key": "value"})

        # Coordinator crashes before PreCommit
        await platform_api.stop_service(coordinator.node_id)

        # Recovery - all uncertain, so abort
        for p in cluster[1:]:
            await p.recover_from_timeout(tx_id)

        # All should have aborted
        for p in cluster[1:]:
            state = await p.GetState(tx_id)
            assert state.state == "ABORTED"
```

### Comparison with 2PC

```python
async def test_non_blocking_vs_2pc(self, cluster):
    """3PC is non-blocking unlike 2PC."""
    # In 2PC: if coordinator fails after Prepare, participants block
    # In 3PC: participants can query each other and decide

    coordinator = cluster[0]
    tx_id = await coordinator.BeginTransaction({"key": "value"})

    # Get all to precommitted state
    for p in cluster[1:]:
        await p.handle_can_commit(tx_id, coordinator.node_id, {"key": "value"})
        await p.handle_pre_commit(tx_id)

    # Coordinator crashes
    await platform_api.stop_service(coordinator.node_id)

    # In 2PC: participants would block waiting for decision
    # In 3PC: participants can query each other
    # Since all are precommitted, they can decide to commit

    for p in cluster[1:]:
        await p.recover_from_timeout(tx_id)
        state = await p.GetState(tx_id)
        assert state.state == "COMMITTED"
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Happy Path | All participants commit atomically |
| Vote NO | Transaction aborts on any NO vote |
| Coordinator Failure | Participants recover via peer query |
| Non-blocking | No blocking with precommitted state |
