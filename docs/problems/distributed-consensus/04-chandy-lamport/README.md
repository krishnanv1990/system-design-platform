# Chandy-Lamport Snapshot Algorithm

## Problem Overview

Implement the Chandy-Lamport distributed snapshot algorithm to capture consistent global states in distributed systems.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution

### Algorithm Overview

The Chandy-Lamport algorithm captures a consistent global snapshot by:
1. **Initiator** records its local state and sends markers on all outgoing channels
2. **Recipients** record state on first marker, then record messages on other channels
3. **Termination** when all processes have received markers on all channels

### Implementation

```python
from dataclasses import dataclass
from typing import Dict, List, Optional
import asyncio

@dataclass
class ProcessState:
    process_id: str
    state_data: bytes
    logical_clock: int
    kv_state: Dict[str, str]

@dataclass
class ChannelState:
    from_process: str
    to_process: str
    messages: List[bytes]

class ChandyLamportNode:
    def __init__(self, node_id: str, peers: List[str]):
        self.node_id = node_id
        self.peers = peers
        self.logical_clock = 0
        self.state: Dict[str, str] = {}

        # Snapshot state
        self.is_recording: Dict[str, bool] = {}  # snapshot_id -> recording
        self.recorded_state: Dict[str, ProcessState] = {}
        self.channel_states: Dict[str, Dict[str, ChannelState]] = {}
        self.marker_received: Dict[str, Dict[str, bool]] = {}

    async def initiate_snapshot(self, snapshot_id: str = None) -> str:
        """Start a new global snapshot."""
        if not snapshot_id:
            snapshot_id = f"{self.node_id}-{self.logical_clock}"

        # Record local state
        self.recorded_state[snapshot_id] = ProcessState(
            process_id=self.node_id,
            state_data=self.serialize_state(),
            logical_clock=self.logical_clock,
            kv_state=self.state.copy()
        )

        # Initialize channel recording
        self.channel_states[snapshot_id] = {}
        self.marker_received[snapshot_id] = {p: False for p in self.peers}

        # Start recording on all incoming channels
        for peer in self.peers:
            self.channel_states[snapshot_id][peer] = ChannelState(
                from_process=peer,
                to_process=self.node_id,
                messages=[]
            )

        # Send markers to all peers
        await self.send_markers(snapshot_id)

        return snapshot_id

    async def send_markers(self, snapshot_id: str):
        """Send marker messages to all peers."""
        marker = MarkerMessage(
            snapshot_id=snapshot_id,
            sender_id=self.node_id,
            logical_clock=self.logical_clock,
            initiator_id=self.node_id
        )

        tasks = [
            self.rpc_client.ReceiveMarker(peer, marker)
            for peer in self.peers
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def handle_marker(self, marker: MarkerMessage) -> MarkerResponse:
        """Handle incoming marker message."""
        snapshot_id = marker.snapshot_id
        sender = marker.sender_id

        first_marker = snapshot_id not in self.recorded_state

        if first_marker:
            # First marker for this snapshot - record local state
            self.recorded_state[snapshot_id] = ProcessState(
                process_id=self.node_id,
                state_data=self.serialize_state(),
                logical_clock=self.logical_clock,
                kv_state=self.state.copy()
            )

            # Initialize channel recording for other channels
            self.channel_states[snapshot_id] = {}
            self.marker_received[snapshot_id] = {p: False for p in self.peers}

            for peer in self.peers:
                if peer != sender:
                    self.channel_states[snapshot_id][peer] = ChannelState(
                        from_process=peer,
                        to_process=self.node_id,
                        messages=[]
                    )

            # Empty channel state for sender (no messages in transit)
            self.marker_received[snapshot_id][sender] = True

            # Propagate markers to all peers
            await self.send_markers(snapshot_id)
        else:
            # Stop recording on this channel
            self.marker_received[snapshot_id][sender] = True

        return MarkerResponse(
            success=True,
            first_marker=first_marker,
            process_id=self.node_id
        )

    async def record_message(self, snapshot_id: str, sender: str, msg: bytes):
        """Record message received during snapshot recording."""
        if snapshot_id in self.channel_states:
            if sender in self.channel_states[snapshot_id]:
                if not self.marker_received[snapshot_id].get(sender, False):
                    self.channel_states[snapshot_id][sender].messages.append(msg)

    def is_snapshot_complete(self, snapshot_id: str) -> bool:
        """Check if snapshot recording is complete."""
        if snapshot_id not in self.marker_received:
            return False
        return all(self.marker_received[snapshot_id].values())

    async def get_global_snapshot(self, snapshot_id: str) -> GlobalSnapshot:
        """Collect global snapshot from all nodes."""
        all_states = [self.recorded_state.get(snapshot_id)]
        all_channels = list(self.channel_states.get(snapshot_id, {}).values())

        # Collect from peers
        for peer in self.peers:
            response = await self.rpc_client.GetSnapshot(peer, snapshot_id)
            if response.found:
                all_states.append(response.local_state)
                all_channels.extend(response.channel_states)

        return GlobalSnapshot(
            snapshot_id=snapshot_id,
            process_states=all_states,
            channel_states=all_channels,
            is_complete=all(s is not None for s in all_states)
        )
```

---

## Platform Deployment

### Cluster Configuration

- 3+ node cluster
- Each node acts as both initiator and participant
- FIFO channels required for correctness
- gRPC streaming for message channels

### gRPC Services

```protobuf
service SnapshotService {
    rpc InitiateSnapshot(InitiateSnapshotRequest) returns (InitiateSnapshotResponse);
    rpc ReceiveMarker(MarkerMessage) returns (MarkerResponse);
    rpc SendMessage(ApplicationMessage) returns (SendMessageResponse);
    rpc GetSnapshot(GetSnapshotRequest) returns (GetSnapshotResponse);
    rpc GetGlobalSnapshot(GetGlobalSnapshotRequest) returns (GetGlobalSnapshotResponse);
}

service BankService {
    rpc GetBalance(GetBalanceRequest) returns (GetBalanceResponse);
    rpc Transfer(TransferRequest) returns (TransferResponse);
    rpc Deposit(DepositRequest) returns (DepositResponse);
    rpc Withdraw(WithdrawRequest) returns (WithdrawResponse);
}
```

---

## Realistic Testing

### Functional Tests

```python
class TestChandyLamport:
    async def test_basic_snapshot(self, cluster):
        """Snapshot captures consistent state."""
        # Initialize balances
        await cluster[0].Deposit(account_id="A", amount=1000)
        await cluster[1].Deposit(account_id="B", amount=1000)

        # Initiate snapshot
        response = await cluster[0].InitiateSnapshot()
        snapshot_id = response.snapshot_id

        # Wait for completion
        await asyncio.sleep(2)

        # Get global snapshot
        snapshot = await cluster[0].GetGlobalSnapshot(snapshot_id)

        assert snapshot.is_complete
        # Total value should be conserved
        total = sum(
            sum(s.account_balances.values())
            for s in snapshot.process_states
        )
        assert total == 2000

    async def test_snapshot_during_transfers(self, cluster):
        """Snapshot during concurrent transfers."""
        # Initialize
        await cluster[0].Deposit(account_id="A", amount=1000)
        await cluster[1].Deposit(account_id="B", amount=1000)

        # Start concurrent transfers
        async def transfers():
            for i in range(10):
                await cluster[0].Transfer(
                    from_account="A",
                    to_account="B",
                    to_process=cluster[1].node_id,
                    amount=100
                )
                await cluster[1].Transfer(
                    from_account="B",
                    to_account="A",
                    to_process=cluster[0].node_id,
                    amount=100
                )

        # Initiate snapshot during transfers
        task = asyncio.create_task(transfers())
        await asyncio.sleep(0.1)

        response = await cluster[2].InitiateSnapshot()
        await task

        # Snapshot should show consistent state
        snapshot = await cluster[2].GetGlobalSnapshot(response.snapshot_id)

        # Account for in-transit messages
        total_in_accounts = sum(
            sum(s.account_balances.values())
            for s in snapshot.process_states
        )
        total_in_channels = sum(
            sum(parse_transfer_amount(m) for m in c.messages)
            for c in snapshot.channel_states
        )

        assert total_in_accounts + total_in_channels == 2000

    async def test_concurrent_snapshots(self, cluster):
        """Multiple concurrent snapshot initiators."""
        # Start two snapshots from different nodes
        response1 = await cluster[0].InitiateSnapshot()
        response2 = await cluster[1].InitiateSnapshot()

        await asyncio.sleep(3)

        # Both should complete successfully
        snap1 = await cluster[0].GetGlobalSnapshot(response1.snapshot_id)
        snap2 = await cluster[1].GetGlobalSnapshot(response2.snapshot_id)

        assert snap1.is_complete
        assert snap2.is_complete
```

### Chaos Tests

```python
async def test_node_failure_during_snapshot(self, cluster):
    """Snapshot handles node failure gracefully."""
    await cluster[0].Deposit(account_id="A", amount=1000)

    # Start snapshot
    response = await cluster[0].InitiateSnapshot()

    # Kill a participant before it receives marker
    await asyncio.sleep(0.05)
    await platform_api.stop_service(cluster[2].node_id)

    # Snapshot should be marked incomplete
    await asyncio.sleep(2)
    snapshot = await cluster[0].GetGlobalSnapshot(response.snapshot_id)

    # Should have partial snapshot
    assert len(snapshot.process_states) == 2  # Only 2 of 3 nodes
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Basic Snapshot | Captures consistent global state |
| During Transfers | Total value conserved (state + channels) |
| Concurrent Snapshots | Multiple snapshots complete correctly |
| Node Failure | Partial snapshot reported |
