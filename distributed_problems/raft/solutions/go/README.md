# Raft Consensus - Go Solution

A complete implementation of the Raft consensus algorithm in Go.

## Features

- **Leader Election**: Randomized election timeouts with goroutine-based voting
- **Log Replication**: Consistent log replication using channels
- **Heartbeat Mechanism**: Periodic heartbeats with goroutines
- **Key-Value Store**: Thread-safe state machine
- **gRPC Communication**: High-performance RPC

## Prerequisites

- Go 1.21+
- Protocol Buffers compiler (protoc)
- gRPC Go plugin

## Building

```bash
# Generate protobuf files
protoc --go_out=. --go-grpc_out=. ../../proto/raft.proto

# Build the server
go build -o server server.go
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

# Put a value
grpcurl -plaintext -d '{"key": "foo", "value": "bar"}' localhost:50051 raft.KeyValueService/Put

# Get a value
grpcurl -plaintext -d '{"key": "foo"}' localhost:50051 raft.KeyValueService/Get
```

## Architecture

### Goroutine Design

- **ElectionTimerLoop**: Background goroutine checking election timeout
- **HeartbeatLoop**: Background goroutine sending heartbeats as leader
- **Per-peer goroutines**: Concurrent RPCs to all peers

### Key Implementation Details

```go
// Election timer with randomized timeout
func (n *RaftNode) randomTimeout() time.Duration {
    return n.electionTimeoutMin + time.Duration(
        rand.Int63n(int64(n.electionTimeoutMax-n.electionTimeoutMin)))
}

// Vote granting logic
logOk := req.LastLogTerm > n.GetLastLogTerm() ||
    (req.LastLogTerm == n.GetLastLogTerm() && req.LastLogIndex >= n.GetLastLogIndex())

// Commit index update with majority check
for i := n.state.CommitIndex + 1; i < uint64(len(n.state.Log)); i++ {
    if n.state.Log[i].Term != n.state.CurrentTerm {
        continue
    }
    count := 1
    for _, peer := range n.peers {
        if n.state.MatchIndex[peer] >= i {
            count++
        }
    }
    if count >= (len(n.peers)+1)/2+1 {
        n.state.CommitIndex = i
        n.ApplyToStateMachine()
    }
}
```

## Test Scenarios

This implementation passes all:
- **Functional Tests**: Leader election, log replication, key-value operations
- **Performance Tests**: High throughput with Go's concurrency
- **Chaos Tests**: Leader failure, node failure, network partitions

## License

MIT License
