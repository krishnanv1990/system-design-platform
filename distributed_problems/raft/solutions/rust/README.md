# Raft Consensus - Rust Solution

A complete async implementation of the Raft consensus algorithm in Rust.

## Features

- **Leader Election**: Randomized election timeouts with async/await
- **Log Replication**: Lock-free concurrent log replication
- **Heartbeat Mechanism**: Tokio-based periodic heartbeats
- **Key-Value Store**: Thread-safe state machine with RwLock
- **gRPC Communication**: High-performance RPC with Tonic

## Prerequisites

- Rust 1.70+
- Protocol Buffers compiler (protoc)

## Building

```bash
# Build the server
cargo build --release
```

## Running

Start a 3-node cluster:

```bash
# Terminal 1 - Node 1
cargo run --release -- --node-id node1 --port 50051 --peers localhost:50052,localhost:50053

# Terminal 2 - Node 2
cargo run --release -- --node-id node2 --port 50052 --peers localhost:50051,localhost:50053

# Terminal 3 - Node 3
cargo run --release -- --node-id node3 --port 50053 --peers localhost:50051,localhost:50052
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

### Async Design

- **Tokio Runtime**: Full async/await support
- **RwLock**: Reader-writer locks for concurrent access
- **Arc**: Reference-counted shared ownership
- **Notify**: Signaling between async tasks

### Key Implementation Details

```rust
// Election timer with randomized timeout
fn random_timeout() -> Duration {
    let mut rng = rand::thread_rng();
    Duration::from_millis(rng.gen_range(150..300))
}

// Vote granting logic
let log_ok = req.last_log_term > last_log_term ||
    (req.last_log_term == last_log_term && req.last_log_index >= last_log_index);

// Commit index update
for n in (state.commit_index + 1)..log_len {
    if state.log[n as usize].term != state.current_term {
        continue;
    }
    let mut count = 1;
    for peer in &self.peers {
        if *state.match_index.get(peer).unwrap_or(&0) >= n {
            count += 1;
        }
    }
    if count >= (self.peers.len() + 1) / 2 + 1 {
        state.commit_index = n;
    }
}
```

## Safety Features

- **Memory Safety**: Rust's ownership system prevents data races
- **No Unsafe Code**: Pure safe Rust implementation
- **Error Handling**: Comprehensive Result-based error handling

## Test Scenarios

This implementation passes all:
- **Functional Tests**: Leader election, log replication, key-value operations
- **Performance Tests**: High throughput with Rust's zero-cost abstractions
- **Chaos Tests**: Leader failure, node failure, network partitions

## License

MIT License
