# Raft Consensus - Python Solution

A complete asynchronous implementation of the Raft consensus algorithm in Python.

## Features

- **Leader Election**: Randomized election timeouts with async vote collection
- **Log Replication**: Consistent log replication using asyncio
- **Heartbeat Mechanism**: Periodic heartbeats to maintain leadership
- **Key-Value Store**: Simple state machine for demonstration
- **gRPC Communication**: Async gRPC for high-performance RPC

## Prerequisites

- Python 3.8+
- grpcio and grpcio-tools
- protobuf

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Generate protobuf files
python -m grpc_tools.protoc -I../../proto --python_out=. --grpc_python_out=. ../../proto/raft.proto
```

## Running

Start a 3-node cluster:

```bash
# Terminal 1 - Node 1
python server.py --node-id node1 --port 50051 --peers localhost:50052,localhost:50053

# Terminal 2 - Node 2
python server.py --node-id node2 --port 50052 --peers localhost:50051,localhost:50053

# Terminal 3 - Node 3
python server.py --node-id node3 --port 50053 --peers localhost:50051,localhost:50052
```

## Testing with grpcurl

```bash
# Get cluster status
grpcurl -plaintext localhost:50051 raft.KeyValueService/GetClusterStatus

# Put a value (must be leader)
grpcurl -plaintext -d '{"key": "foo", "value": "bar"}' localhost:50051 raft.KeyValueService/Put

# Get a value
grpcurl -plaintext -d '{"key": "foo"}' localhost:50051 raft.KeyValueService/Get
```

## Architecture

### Async Design

This implementation uses Python's `asyncio` for concurrent operations:
- Election timer runs as a background task
- Heartbeat loop runs as a background task
- All RPC handlers are async for non-blocking operation
- Lock uses `asyncio.Lock` for thread-safe state access

### Key Components

```python
# Election timer with randomized timeout
def reset_election_timer(self):
    self.election_deadline = time.time() + random.uniform(
        self.election_timeout_min,
        self.election_timeout_max
    )

# Vote granting logic
log_ok = (request.last_log_term > self.get_last_log_term() or
         (request.last_log_term == self.get_last_log_term() and
          request.last_log_index >= self.get_last_log_index()))

# Commit index update
for n in range(self.state.commit_index + 1, len(self.state.log)):
    if self.state.log[n].term != self.state.current_term:
        continue
    count = 1
    for peer in self.peers:
        if self.state.match_index.get(peer, 0) >= n:
            count += 1
    if count >= (len(self.peers) + 1) // 2 + 1:
        self.state.commit_index = n
        self.apply_to_state_machine()
```

## Test Scenarios

This implementation passes all:
- **Functional Tests**: Leader election, log replication, key-value operations
- **Performance Tests**: Throughput under load, latency measurements
- **Chaos Tests**: Leader failure, node failure, network partitions

## License

MIT License
