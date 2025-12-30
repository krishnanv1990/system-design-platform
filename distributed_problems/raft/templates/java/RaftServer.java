/**
 * Raft Consensus Implementation - Java Template
 *
 * This template provides the basic structure for implementing the Raft
 * consensus algorithm. You need to implement the TODO sections.
 *
 * For the full Raft specification, see: https://raft.github.io/raft.pdf
 *
 * Usage:
 *     java RaftServer --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

package com.sdp.raft;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.stub.StreamObserver;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.logging.Logger;

public class RaftServer {
    private static final Logger logger = Logger.getLogger(RaftServer.class.getName());

    // Node states
    public enum NodeState {
        FOLLOWER("follower"),
        CANDIDATE("candidate"),
        LEADER("leader");

        private final String value;

        NodeState(String value) {
            this.value = value;
        }

        @Override
        public String toString() {
            return value;
        }
    }

    // Log entry
    public static class LogEntry {
        public long index;
        public long term;
        public byte[] command;
        public String commandType;

        public LogEntry(long index, long term, byte[] command, String commandType) {
            this.index = index;
            this.term = term;
            this.command = command;
            this.commandType = commandType;
        }
    }

    // Raft state
    public static class RaftState {
        // Persistent state
        public long currentTerm = 0;
        public String votedFor = null;
        public List<LogEntry> log = new ArrayList<>();

        // Volatile state on all servers
        public long commitIndex = 0;
        public long lastApplied = 0;

        // Volatile state on leaders
        public Map<String, Long> nextIndex = new ConcurrentHashMap<>();
        public Map<String, Long> matchIndex = new ConcurrentHashMap<>();
    }

    // Main Raft node implementation
    public static class RaftNode extends RaftServiceGrpc.RaftServiceImplBase
            implements KeyValueServiceGrpc.KeyValueServiceImplBase {

        private final String nodeId;
        private final int port;
        private final List<String> peers;
        private final RaftState state;
        private volatile NodeState nodeState;
        private volatile String leaderId;

        // Key-value store (state machine)
        private final Map<String, String> kvStore = new ConcurrentHashMap<>();

        // Timing configuration
        private static final long ELECTION_TIMEOUT_MIN_MS = 150;
        private static final long ELECTION_TIMEOUT_MAX_MS = 300;
        private static final long HEARTBEAT_INTERVAL_MS = 50;

        // Synchronization
        private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();
        private final ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(2);
        private ScheduledFuture<?> electionTimer;
        private final Random random = new Random();

        // gRPC clients for peer communication
        private final Map<String, RaftServiceGrpc.RaftServiceBlockingStub> peerStubs = new ConcurrentHashMap<>();

        public RaftNode(String nodeId, int port, List<String> peers) {
            this.nodeId = nodeId;
            this.port = port;
            this.peers = peers;
            this.state = new RaftState();
            this.nodeState = NodeState.FOLLOWER;
        }

        public void initialize() {
            for (String peer : peers) {
                ManagedChannel channel = ManagedChannelBuilder.forTarget(peer)
                        .usePlaintext()
                        .build();
                peerStubs.put(peer, RaftServiceGrpc.newBlockingStub(channel));
            }
            logger.info("Node " + nodeId + " initialized with peers: " + peers);
        }

        public long getLastLogIndex() {
            return state.log.isEmpty() ? 0 : state.log.get(state.log.size() - 1).index;
        }

        public long getLastLogTerm() {
            return state.log.isEmpty() ? 0 : state.log.get(state.log.size() - 1).term;
        }

        /**
         * Reset the election timeout with a random duration.
         *
         * TODO: Implement election timer reset
         * - Cancel any existing timer
         * - Start a new timer with random timeout between
         *   ELECTION_TIMEOUT_MIN_MS and ELECTION_TIMEOUT_MAX_MS
         * - When timer fires, call startElection()
         */
        public void resetElectionTimer() {
            // TODO: Implement election timer reset
        }

        /**
         * Start a new leader election.
         *
         * TODO: Implement the election process:
         * 1. Increment current_term
         * 2. Change state to CANDIDATE
         * 3. Vote for self
         * 4. Reset election timer
         * 5. Send RequestVote RPCs to all peers in parallel
         * 6. If votes received from majority, become leader
         * 7. If AppendEntries received from new leader, become follower
         * 8. If election timeout elapses, start new election
         */
        public void startElection() {
            // TODO: Implement election logic
        }

        /**
         * Send heartbeat AppendEntries RPCs to all followers.
         *
         * TODO: Implement heartbeat mechanism:
         * - Only run if this node is the leader
         * - Send AppendEntries (empty for heartbeat) to all peers
         * - Process responses to update match_index and next_index
         * - Repeat at HEARTBEAT_INTERVAL_MS
         */
        public void sendHeartbeats() {
            // TODO: Implement heartbeat logic
        }

        /**
         * Apply a command to the state machine (key-value store).
         *
         * TODO: Implement command application:
         * - Parse the command
         * - Apply to kvStore (put/delete operations)
         */
        public void applyCommand(byte[] command, String commandType) {
            // TODO: Implement command application
        }

        // =========================================================================
        // RaftService RPC Implementations
        // =========================================================================

        /**
         * Handle RequestVote RPC from a candidate.
         *
         * TODO: Implement vote handling per Raft specification:
         * 1. Reply false if term < currentTerm
         * 2. If votedFor is null or candidateId, and candidate's log is at
         *    least as up-to-date as receiver's log, grant vote
         */
        @Override
        public void requestVote(Raft.RequestVoteRequest request,
                                StreamObserver<Raft.RequestVoteResponse> responseObserver) {
            lock.writeLock().lock();
            try {
                Raft.RequestVoteResponse.Builder response = Raft.RequestVoteResponse.newBuilder();

                // TODO: Implement voting logic
                response.setTerm(state.currentTerm);
                response.setVoteGranted(false);

                responseObserver.onNext(response.build());
                responseObserver.onCompleted();
            } finally {
                lock.writeLock().unlock();
            }
        }

        /**
         * Handle AppendEntries RPC from leader.
         *
         * TODO: Implement log replication per Raft specification:
         * 1. Reply false if term < currentTerm
         * 2. Reply false if log doesn't contain an entry at prevLogIndex
         *    whose term matches prevLogTerm
         * 3. If an existing entry conflicts with a new one, delete the
         *    existing entry and all that follow it
         * 4. Append any new entries not already in the log
         * 5. If leaderCommit > commitIndex, set commitIndex =
         *    min(leaderCommit, index of last new entry)
         */
        @Override
        public void appendEntries(Raft.AppendEntriesRequest request,
                                  StreamObserver<Raft.AppendEntriesResponse> responseObserver) {
            lock.writeLock().lock();
            try {
                Raft.AppendEntriesResponse.Builder response = Raft.AppendEntriesResponse.newBuilder();

                // TODO: Implement AppendEntries logic
                response.setTerm(state.currentTerm);
                response.setSuccess(false);
                response.setMatchIndex(getLastLogIndex());

                responseObserver.onNext(response.build());
                responseObserver.onCompleted();
            } finally {
                lock.writeLock().unlock();
            }
        }

        /**
         * Handle InstallSnapshot RPC from leader.
         *
         * TODO: Implement snapshot installation
         */
        @Override
        public void installSnapshot(Raft.InstallSnapshotRequest request,
                                    StreamObserver<Raft.InstallSnapshotResponse> responseObserver) {
            lock.writeLock().lock();
            try {
                Raft.InstallSnapshotResponse.Builder response = Raft.InstallSnapshotResponse.newBuilder();
                response.setTerm(state.currentTerm);

                responseObserver.onNext(response.build());
                responseObserver.onCompleted();
            } finally {
                lock.writeLock().unlock();
            }
        }

        // =========================================================================
        // KeyValueService RPC Implementations
        // =========================================================================

        public void get(Raft.GetRequest request,
                        StreamObserver<Raft.GetResponse> responseObserver) {
            lock.readLock().lock();
            try {
                Raft.GetResponse.Builder response = Raft.GetResponse.newBuilder();
                String value = kvStore.get(request.getKey());
                if (value != null) {
                    response.setValue(value);
                    response.setFound(true);
                } else {
                    response.setFound(false);
                }
                responseObserver.onNext(response.build());
                responseObserver.onCompleted();
            } finally {
                lock.readLock().unlock();
            }
        }

        /**
         * Handle Put RPC - stores key-value pair.
         *
         * TODO: Implement consensus-based put:
         * 1. If not leader, return leader_hint
         * 2. Append entry to local log
         * 3. Replicate to followers via AppendEntries
         * 4. Once committed (majority replicated), apply to state machine
         * 5. Return success to client
         */
        public void put(Raft.PutRequest request,
                        StreamObserver<Raft.PutResponse> responseObserver) {
            lock.writeLock().lock();
            try {
                Raft.PutResponse.Builder response = Raft.PutResponse.newBuilder();

                if (nodeState != NodeState.LEADER) {
                    response.setSuccess(false);
                    response.setError("Not the leader");
                    response.setLeaderHint(leaderId != null ? leaderId : "");
                    responseObserver.onNext(response.build());
                    responseObserver.onCompleted();
                    return;
                }

                // TODO: Implement consensus-based put
                response.setSuccess(false);
                response.setError("Not implemented");

                responseObserver.onNext(response.build());
                responseObserver.onCompleted();
            } finally {
                lock.writeLock().unlock();
            }
        }

        /**
         * Handle Delete RPC - removes key.
         *
         * TODO: Implement consensus-based delete (similar to put)
         */
        public void delete(Raft.DeleteRequest request,
                           StreamObserver<Raft.DeleteResponse> responseObserver) {
            lock.writeLock().lock();
            try {
                Raft.DeleteResponse.Builder response = Raft.DeleteResponse.newBuilder();

                if (nodeState != NodeState.LEADER) {
                    response.setSuccess(false);
                    response.setError("Not the leader");
                    response.setLeaderHint(leaderId != null ? leaderId : "");
                    responseObserver.onNext(response.build());
                    responseObserver.onCompleted();
                    return;
                }

                // TODO: Implement consensus-based delete
                response.setSuccess(false);
                response.setError("Not implemented");

                responseObserver.onNext(response.build());
                responseObserver.onCompleted();
            } finally {
                lock.writeLock().unlock();
            }
        }

        public void getLeader(Raft.GetLeaderRequest request,
                              StreamObserver<Raft.GetLeaderResponse> responseObserver) {
            lock.readLock().lock();
            try {
                Raft.GetLeaderResponse.Builder response = Raft.GetLeaderResponse.newBuilder();
                response.setLeaderId(leaderId != null ? leaderId : "");
                response.setIsLeader(nodeState == NodeState.LEADER);

                if (leaderId != null) {
                    for (String peer : peers) {
                        if (peer.contains(leaderId)) {
                            response.setLeaderAddress(peer);
                            break;
                        }
                    }
                }

                responseObserver.onNext(response.build());
                responseObserver.onCompleted();
            } finally {
                lock.readLock().unlock();
            }
        }

        public void getClusterStatus(Raft.GetClusterStatusRequest request,
                                     StreamObserver<Raft.GetClusterStatusResponse> responseObserver) {
            lock.readLock().lock();
            try {
                Raft.GetClusterStatusResponse.Builder response = Raft.GetClusterStatusResponse.newBuilder();
                response.setNodeId(nodeId);
                response.setState(nodeState.toString());
                response.setCurrentTerm(state.currentTerm);
                response.setVotedFor(state.votedFor != null ? state.votedFor : "");
                response.setCommitIndex(state.commitIndex);
                response.setLastApplied(state.lastApplied);
                response.setLogLength(state.log.size());
                response.setLastLogTerm(getLastLogTerm());

                for (String peer : peers) {
                    Raft.ClusterMember.Builder member = Raft.ClusterMember.newBuilder();
                    member.setAddress(peer);
                    if (nodeState == NodeState.LEADER) {
                        member.setMatchIndex(state.matchIndex.getOrDefault(peer, 0L));
                        member.setNextIndex(state.nextIndex.getOrDefault(peer, 1L));
                    }
                    response.addMembers(member.build());
                }

                responseObserver.onNext(response.build());
                responseObserver.onCompleted();
            } finally {
                lock.readLock().unlock();
            }
        }
    }

    // =========================================================================
    // Main Entry Point
    // =========================================================================

    public static void main(String[] args) throws IOException, InterruptedException {
        String nodeId = null;
        int port = 50051;
        String peersStr = null;

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--node-id":
                    nodeId = args[++i];
                    break;
                case "--port":
                    port = Integer.parseInt(args[++i]);
                    break;
                case "--peers":
                    peersStr = args[++i];
                    break;
            }
        }

        if (nodeId == null || peersStr == null) {
            System.err.println("Usage: java RaftServer --node-id <id> --port <port> --peers <peer1:port1,peer2:port2>");
            System.exit(1);
        }

        List<String> peers = new ArrayList<>();
        for (String peer : peersStr.split(",")) {
            peers.add(peer.trim());
        }

        RaftNode node = new RaftNode(nodeId, port, peers);
        node.initialize();

        Server server = ServerBuilder.forPort(port)
                .addService(node)
                .build()
                .start();

        logger.info("Starting Raft node " + nodeId + " on port " + port);

        // Start election timer
        node.resetElectionTimer();

        server.awaitTermination();
    }
}
