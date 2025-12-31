# Raft Consensus - C++ Solution

A complete implementation of the Raft consensus algorithm in C++.

## Features

- **Leader Election**: Randomized election timeouts with vote collection
- **Log Replication**: Consistent log replication across all nodes
- **Heartbeat Mechanism**: Periodic heartbeats to maintain leadership
- **Key-Value Store**: Simple state machine for demonstration
- **gRPC Communication**: High-performance RPC between nodes

## Prerequisites

- CMake 3.16+
- C++17 compiler (GCC 8+ or Clang 7+)
- gRPC and Protocol Buffers
- Abseil library

## Building

```bash
# Create build directory
mkdir build && cd build

# Configure with CMake
cmake ..

# Build
make -j$(nproc)
```

### Build Options

```bash
# Enable Address Sanitizer
cmake .. -DENABLE_ASAN=ON

# Enable Thread Sanitizer
cmake .. -DENABLE_TSAN=ON

# Build tests
cmake .. -DBUILD_TESTS=ON
make -j$(nproc)
ctest
```

## Running

Start a 3-node cluster:

```bash
# Terminal 1 - Node 1
./server --node-id node1 --port 50051 --peers localhost:50052,localhost:50053

# Terminal 2 - Node 2
./server --node-id node2 --port 50052 --peers localhost:50051,localhost:50053

# Terminal 3 - Node 3
./server --node-id node3 --port 50053 --peers localhost:50051,localhost:50052
```

## Testing with grpcurl

```bash
# Get cluster status
grpcurl -plaintext localhost:50051 raft.KeyValueService/GetClusterStatus

# Put a value (must be leader)
grpcurl -plaintext -d '{"key": "foo", "value": "bar"}' localhost:50051 raft.KeyValueService/Put

# Get a value
grpcurl -plaintext -d '{"key": "foo"}' localhost:50051 raft.KeyValueService/Get

# Get leader info
grpcurl -plaintext localhost:50051 raft.KeyValueService/GetLeader
```

## Architecture

### Core Components

1. **RaftNode**: Main class implementing both `RaftService` and `KeyValueService`
2. **RaftStateStore**: Persistent state (term, votedFor, log)
3. **Election Timer Loop**: Background thread for election timeouts
4. **Heartbeat Loop**: Background thread for leader heartbeats

### Raft Protocol Implementation

#### Leader Election
- Nodes start as followers with randomized election timeout (150-300ms)
- On timeout, node becomes candidate and requests votes
- Candidate with majority votes becomes leader
- Leader sends heartbeats to maintain authority

#### Log Replication
- Client requests go to leader
- Leader appends to local log and replicates to followers
- Entry committed when majority has replicated
- Committed entries applied to state machine

#### Safety Guarantees
- Election restriction: Only candidates with up-to-date logs can win
- Leader completeness: Committed entries preserved across leader changes
- State machine safety: All nodes apply same commands in same order

## Key Implementation Details

```cpp
// Election timer with randomized timeout
void ResetElectionTimer() {
    auto timeout = std::chrono::milliseconds(
        election_timeout_min_ + (rand() % (election_timeout_max_ - election_timeout_min_))
    );
    election_deadline_ = std::chrono::steady_clock::now() + timeout;
}

// Vote granting logic
bool log_ok = (request->last_log_term() > GetLastLogTerm()) ||
              (request->last_log_term() == GetLastLogTerm() &&
               request->last_log_index() >= GetLastLogIndex());

// Commit index advancement
for (uint64_t n = state_.commit_index + 1; n < state_.log.size(); ++n) {
    if (state_.log[n].term != state_.current_term) continue;
    size_t count = 1;
    for (const auto& peer : peers_)
        if (state_.match_index[peer] >= n) count++;
    if (count >= (peers_.size() + 1) / 2 + 1) {
        state_.commit_index = n;
        ApplyToStateMachine();
    }
}
```

## Test Scenarios

This implementation passes all:
- **Functional Tests**: Leader election, log replication, key-value operations
- **Performance Tests**: Throughput under load, latency measurements
- **Chaos Tests**: Leader failure, node failure, network partitions

## License

MIT License
