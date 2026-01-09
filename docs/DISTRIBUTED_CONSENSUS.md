# Distributed Consensus Architecture

This document describes the architecture for distributed consensus problems.

## Overview

Distributed consensus problems (Raft, Paxos, etc.) require deploying user code
across multiple nodes that communicate via gRPC.

```
┌─────────────────────────────────────────────────────────────┐
│                    Submission Flow                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  User Code    Build      Deploy         Test                │
│  ────────► Container ► 5 Nodes ► Chaos Scenarios           │
│                          │                                  │
│                    ┌─────┴─────┐                           │
│                    ▼     ▼     ▼                           │
│                 Node0  Node1  Node2...                     │
│                    │     │     │                           │
│                    └──gRPC────┘                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Cluster Architecture

Each submission deploys a 3 or 5-node cluster depending on the problem:

| Node | Role | Purpose |
|------|------|---------|
| node-0 | Initial Leader | Starts as leader candidate |
| node-1 to node-4 | Followers | Join cluster, participate in consensus |

### Node Communication

Nodes communicate via gRPC using the service definition provided in each problem.

```protobuf
service ConsensusNode {
  rpc RequestVote(VoteRequest) returns (VoteResponse);
  rpc AppendEntries(AppendRequest) returns (AppendResponse);
  rpc ClientRequest(ClientRequest) returns (ClientResponse);
}
```

## Available Problems

| ID | Problem | Difficulty | Description |
|----|---------|------------|-------------|
| 1 | Raft Consensus | Hard | Leader election, log replication |
| 2 | Multi-Paxos | Hard | Proposer/acceptor/learner roles |
| 3 | Two-Phase Commit | Medium | Distributed transactions |
| 4 | Chandy-Lamport | Medium | Global snapshots |
| 5 | Consistent Hashing | Medium | Key distribution |
| 6 | Rendezvous Hashing | Medium | Highest random weight hashing |
| 7-10 | Rate Limiters | Medium | Token bucket, leaky bucket, etc. |
| 11-19 | Vector Clocks, CRDT, etc. | Medium-Hard | Advanced distributed algorithms |

## Build Pipeline

1. **Code Validation** - Syntax check, import verification
2. **Container Build** - Multi-stage Docker build via Cloud Build
3. **Image Push** - Push to Artifact Registry
4. **Cluster Deploy** - Deploy N Cloud Run services
5. **Health Check** - Verify all nodes responding
6. **Test Execution** - Run test scenarios

### Build Configuration

```yaml
# cloudbuild-distributed.yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '$_IMAGE', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '$_IMAGE']
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: 'gcloud'
    args: ['run', 'deploy', ...]
```

## Test Scenarios

Each problem includes chaos scenarios:

| Scenario | Description |
|----------|-------------|
| `leader_election` | Kill leader, verify new election |
| `network_partition` | Split cluster, verify consistency |
| `log_replication` | Write to leader, verify replication |
| `client_redirect` | Client contacts follower, verify redirect |
| `concurrent_requests` | Multiple simultaneous writes |
| `node_recovery` | Node crashes and recovers |

## Language Support

Templates provided for:
- Python (reference implementation)
- Go
- Rust
- Java
- C++

Get templates via API:
```bash
GET /api/distributed/problems/{problem_id}/template/{language}
```

## Submission Status Flow

```
building → deploying → testing → completed
    │           │          │
    ▼           ▼          ▼
build_failed  deploy_failed  failed
```

## Local Development

```bash
# Start local 5-node cluster
docker-compose -f docker-compose.distributed.yml up

# Run tests against local cluster
pytest tests/distributed/ --cluster-url=localhost
```

## API Reference

See [API.md](./API.md#distributed-consensus-api) for full endpoint documentation.

### Key Endpoints

- `GET /api/distributed/problems` - List problems
- `GET /api/distributed/problems/{id}` - Get problem details
- `POST /api/distributed/submissions` - Submit code
- `GET /api/distributed/submissions/{id}/tests` - Get test results
- `POST /api/distributed/submissions/{id}/teardown` - Clean up cluster

## Cluster Resource Limits

Each node is deployed with:
- CPU: 1 vCPU
- Memory: 512Mi
- Max instances: 1 (per node)
- Timeout: 300s

Clusters are automatically torn down after 30 minutes of inactivity.
