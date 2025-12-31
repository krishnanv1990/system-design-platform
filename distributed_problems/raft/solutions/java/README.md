# Raft Consensus - Java Solution

A complete implementation of the Raft consensus algorithm in Java.

## Features

- **Leader Election**: Randomized election timeouts with ExecutorService
- **Log Replication**: Thread-safe log replication
- **Heartbeat Mechanism**: Scheduled periodic heartbeats
- **Key-Value Store**: ConcurrentHashMap-based state machine
- **gRPC Communication**: High-performance RPC with Netty

## Prerequisites

- Java 17+
- Gradle 8+
- Protocol Buffers compiler (protoc)

## Building

```bash
# Build with Gradle
./gradlew build

# Create fat JAR
./gradlew jar
```

## Running

Start a 3-node cluster:

```bash
# Terminal 1 - Node 1
java -jar build/libs/raft-1.0-SNAPSHOT.jar --node-id node1 --port 50051 --peers localhost:50052,localhost:50053

# Terminal 2 - Node 2
java -jar build/libs/raft-1.0-SNAPSHOT.jar --node-id node2 --port 50052 --peers localhost:50051,localhost:50053

# Terminal 3 - Node 3
java -jar build/libs/raft-1.0-SNAPSHOT.jar --node-id node3 --port 50053 --peers localhost:50051,localhost:50052
```

Or run with Gradle:

```bash
./gradlew run --args="--node-id node1 --port 50051 --peers localhost:50052,localhost:50053"
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

### Thread Model

- **ScheduledExecutorService**: Manages background tasks
- **ReentrantLock + Condition**: Thread-safe state access
- **ConcurrentHashMap**: Lock-free key-value store

### Key Implementation Details

```java
// Election timer with randomized timeout
private int randomTimeout() {
    return electionTimeoutMin + random.nextInt(electionTimeoutMax - electionTimeoutMin);
}

// Vote granting logic
boolean logOk = request.getLastLogTerm() > getLastLogTerm() ||
    (request.getLastLogTerm() == getLastLogTerm() &&
     request.getLastLogIndex() >= getLastLogIndex());

// Commit index update
for (long n = state.commitIndex + 1; n < state.log.size(); n++) {
    if (state.log.get((int) n).term != state.currentTerm) continue;
    int count = 1;
    for (String peer : peers) {
        if (state.matchIndex.getOrDefault(peer, 0L) >= n) count++;
    }
    if (count >= (peers.size() + 1) / 2 + 1) {
        state.commitIndex = n;
        applyToStateMachine();
    }
}
```

## Test Scenarios

This implementation passes all:
- **Functional Tests**: Leader election, log replication, key-value operations
- **Performance Tests**: High throughput with Java's concurrency
- **Chaos Tests**: Leader failure, node failure, network partitions

## License

MIT License
