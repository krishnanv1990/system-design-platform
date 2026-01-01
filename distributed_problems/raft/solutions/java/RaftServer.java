/**
 * Raft Consensus Implementation - Java Solution
 *
 * A complete implementation of the Raft consensus algorithm supporting:
 * - Leader election with randomized timeouts
 * - Log replication with consistency guarantees
 * - Heartbeat mechanism for leader authority
 * - Key-value store as the state machine
 *
 * For the full Raft specification, see: https://raft.github.io/raft.pdf
 *
 * Key Raft Properties:
 * - Election Safety: At most one leader per term
 * - Leader Append-Only: Leader never overwrites/deletes log entries
 * - Log Matching: Same index+term means identical prefix
 * - Leader Completeness: Committed entries appear in future leaders
 * - State Machine Safety: Same commands applied in same order
 *
 * Usage:
 *     java RaftServer --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

package com.sdp.raft;

import io.grpc.*;
import io.grpc.stub.StreamObserver;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.locks.ReentrantLock;
import java.util.concurrent.locks.Condition;
import java.util.logging.Logger;

public class RaftServer {
    private static final Logger logger = Logger.getLogger(RaftServer.class.getName());

    // =========================================================================
    // Node States - A node can be in one of three states
    // =========================================================================
    enum NodeState {
        FOLLOWER("follower"),    // Default state, receives entries from leader
        CANDIDATE("candidate"),  // Seeking votes to become leader
        LEADER("leader");        // Manages log replication

        private final String value;
        NodeState(String value) { this.value = value; }
        public String getValue() { return value; }
    }

    // =========================================================================
    // Log Entry - Represents a single entry in the replicated log
    // =========================================================================
    static class LogEntry {
        long index;        // Position in log (1-indexed)
        long term;         // Term when entry was received
        byte[] command;    // Command to apply to state machine
        String commandType; // Type of command (put/delete)

        LogEntry(long index, long term, byte[] command, String commandType) {
            this.index = index;
            this.term = term;
            this.command = command;
            this.commandType = commandType;
        }
    }

    // =========================================================================
    // Raft State - Persistent and volatile state per Raft paper
    // =========================================================================
    static class RaftState {
        // Persistent state on all servers (updated before responding to RPCs)
        long currentTerm = 0;      // Latest term server has seen
        String votedFor = null;    // CandidateId that received vote in current term
        List<LogEntry> log = new ArrayList<>();  // Log entries

        // Volatile state on all servers
        long commitIndex = 0;      // Index of highest log entry known to be committed
        long lastApplied = 0;      // Index of highest log entry applied to state machine

        // Volatile state on leaders (reinitialized after election)
        Map<String, Long> nextIndex = new ConcurrentHashMap<>();   // For each peer, next log index to send
        Map<String, Long> matchIndex = new ConcurrentHashMap<>();  // For each peer, highest replicated index

        RaftState() {
            // Dummy entry at index 0 (Raft logs are 1-indexed)
            log.add(new LogEntry(0, 0, new byte[0], ""));
        }
    }

    // =========================================================================
    // Instance Variables
    // =========================================================================
    private final String nodeId;
    private final int port;
    private final List<String> peers;
    private final RaftState state = new RaftState();
    private volatile NodeState nodeState = NodeState.FOLLOWER;
    private volatile String leaderId = "";

    // Key-value store (state machine)
    private final Map<String, String> kvStore = new ConcurrentHashMap<>();

    // Timing configuration (in milliseconds)
    private static final int ELECTION_TIMEOUT_MIN_MS = 150;
    private static final int ELECTION_TIMEOUT_MAX_MS = 300;
    private static final int HEARTBEAT_INTERVAL_MS = 50;

    // Synchronization
    private final ReentrantLock lock = new ReentrantLock();
    private final Condition applyCondition = lock.newCondition();
    private volatile long electionDeadline;
    private volatile boolean running = true;

    // gRPC clients for peer communication
    private final Map<String, ManagedChannel> channels = new ConcurrentHashMap<>();
    private final Map<String, RaftServiceGrpc.RaftServiceBlockingStub> peerStubs = new ConcurrentHashMap<>();
    private final Random random = new Random();
    private final ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(4);

    // =========================================================================
    // Constructor
    // =========================================================================
    public RaftServer(String nodeId, int port, List<String> peers) {
        this.nodeId = nodeId;
        this.port = port;
        this.peers = peers;
    }

    // =========================================================================
    // Initialization - Set up gRPC channels to peers
    // =========================================================================
    public void initialize() {
        for (String peer : peers) {
            ManagedChannel channel;
            // Cloud Run URLs require TLS for secure communication
            if (peer.contains(".run.app")) {
                channel = ManagedChannelBuilder.forTarget(peer)
                        .useTransportSecurity()
                        .build();
                logger.info("Using TLS for peer: " + peer);
            } else {
                // Use plaintext for local development
                channel = ManagedChannelBuilder.forTarget(peer)
                        .usePlaintext()
                        .build();
                logger.info("Using plaintext for peer: " + peer);
            }
            channels.put(peer, channel);
            peerStubs.put(peer, RaftServiceGrpc.newBlockingStub(channel));
        }
        logger.info("Node " + nodeId + " initialized with peers: " + peers);
    }

    // =========================================================================
    // Log Helper Methods
    // =========================================================================
    private long getLastLogIndex() {
        return state.log.isEmpty() ? 0 : state.log.get(state.log.size() - 1).index;
    }

    private long getLastLogTerm() {
        return state.log.isEmpty() ? 0 : state.log.get(state.log.size() - 1).term;
    }

    private int randomTimeout() {
        return ELECTION_TIMEOUT_MIN_MS + random.nextInt(ELECTION_TIMEOUT_MAX_MS - ELECTION_TIMEOUT_MIN_MS);
    }

    // =========================================================================
    // Election Timer Management
    // =========================================================================

    /**
     * Reset the election timeout with a random duration.
     * This prevents split votes by randomizing when candidates start elections.
     */
    private void resetElectionTimer() {
        electionDeadline = System.currentTimeMillis() + randomTimeout();
    }

    /**
     * Step down to follower state when we see a higher term.
     * This is a key safety property in Raft.
     */
    private void stepDown(long newTerm) {
        state.currentTerm = newTerm;
        state.votedFor = null;
        nodeState = NodeState.FOLLOWER;
        resetElectionTimer();
    }

    /**
     * Election timer loop - monitors for election timeout.
     * If timeout elapses without hearing from leader, start election.
     */
    private void electionTimerLoop() {
        resetElectionTimer();
        while (running) {
            try {
                Thread.sleep(10);
                lock.lock();
                try {
                    if (nodeState != NodeState.LEADER && System.currentTimeMillis() >= electionDeadline) {
                        startElection();
                    }
                } finally {
                    lock.unlock();
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
    }

    // =========================================================================
    // Leader Election
    // =========================================================================

    /**
     * Start a new leader election.
     *
     * Per Raft specification:
     * 1. Increment currentTerm
     * 2. Vote for self
     * 3. Reset election timer
     * 4. Send RequestVote RPCs to all other servers
     * 5. If votes received from majority: become leader
     * 6. If AppendEntries received from new leader: convert to follower
     * 7. If election timeout elapses: start new election
     */
    private void startElection() {
        nodeState = NodeState.CANDIDATE;
        state.currentTerm++;
        state.votedFor = nodeId;
        resetElectionTimer();

        long term = state.currentTerm;
        long lastIdx = getLastLogIndex();
        long lastTerm = getLastLogTerm();

        logger.info("Node " + nodeId + " starting election for term " + term);

        AtomicInteger votesReceived = new AtomicInteger(1); // Vote for self
        int majority = (peers.size() + 1) / 2 + 1;

        // Send RequestVote RPCs to all peers in parallel
        for (String peer : peers) {
            scheduler.submit(() -> {
                try {
                    RaftServiceGrpc.RaftServiceBlockingStub stub = peerStubs.get(peer)
                            .withDeadlineAfter(100, TimeUnit.MILLISECONDS);

                    RequestVoteResponse response = stub.requestVote(RequestVoteRequest.newBuilder()
                            .setTerm(term)
                            .setCandidateId(nodeId)
                            .setLastLogIndex(lastIdx)
                            .setLastLogTerm(lastTerm)
                            .build());

                    lock.lock();
                    try {
                        if (response.getTerm() > state.currentTerm) {
                            // Discovered higher term, step down
                            stepDown(response.getTerm());
                        } else if (nodeState == NodeState.CANDIDATE &&
                                response.getVoteGranted() &&
                                term == state.currentTerm) {
                            // Count vote and check for majority
                            if (votesReceived.incrementAndGet() >= majority) {
                                becomeLeader();
                            }
                        }
                    } finally {
                        lock.unlock();
                    }
                } catch (Exception e) {
                    // Peer unavailable, continue with other votes
                }
            });
        }
    }

    /**
     * Transition to leader state after winning election.
     * Initialize nextIndex and matchIndex for all peers.
     */
    private void becomeLeader() {
        if (nodeState != NodeState.CANDIDATE) return;
        nodeState = NodeState.LEADER;
        leaderId = nodeId;
        logger.info("Node " + nodeId + " became leader for term " + state.currentTerm);

        // Initialize leader volatile state
        for (String peer : peers) {
            state.nextIndex.put(peer, getLastLogIndex() + 1);
            state.matchIndex.put(peer, 0L);
        }
    }

    // =========================================================================
    // Heartbeat and Log Replication
    // =========================================================================

    /**
     * Heartbeat loop - sends periodic AppendEntries to maintain leadership.
     */
    private void heartbeatLoop() {
        while (running) {
            try {
                Thread.sleep(HEARTBEAT_INTERVAL_MS);
                lock.lock();
                try {
                    if (nodeState == NodeState.LEADER) {
                        sendAppendEntriesToAll();
                    }
                } finally {
                    lock.unlock();
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
    }

    /**
     * Send AppendEntries RPCs to all peers.
     * Handles both heartbeats (empty entries) and log replication.
     */
    private void sendAppendEntriesToAll() {
        for (String peer : peers) {
            long nextIdx = state.nextIndex.getOrDefault(peer, 1L);
            long prevIdx = nextIdx - 1;
            long prevTerm = prevIdx < state.log.size() ? state.log.get((int) prevIdx).term : 0;

            // Build AppendEntries request
            AppendEntriesRequest.Builder reqBuilder = AppendEntriesRequest.newBuilder()
                    .setTerm(state.currentTerm)
                    .setLeaderId(nodeId)
                    .setPrevLogIndex(prevIdx)
                    .setPrevLogTerm(prevTerm)
                    .setLeaderCommit(state.commitIndex);

            // Add new entries to replicate
            for (int i = (int) nextIdx; i < state.log.size(); i++) {
                LogEntry entry = state.log.get(i);
                reqBuilder.addEntries(com.sdp.raft.LogEntry.newBuilder()
                        .setIndex(entry.index)
                        .setTerm(entry.term)
                        .setCommand(com.google.protobuf.ByteString.copyFrom(entry.command))
                        .setCommandType(entry.commandType)
                        .build());
            }

            AppendEntriesRequest req = reqBuilder.build();
            long term = state.currentTerm;
            int entriesCount = req.getEntriesCount();

            // Send asynchronously
            scheduler.submit(() -> {
                try {
                    RaftServiceGrpc.RaftServiceBlockingStub stub = peerStubs.get(peer)
                            .withDeadlineAfter(100, TimeUnit.MILLISECONDS);

                    AppendEntriesResponse response = stub.appendEntries(req);

                    lock.lock();
                    try {
                        if (response.getTerm() > state.currentTerm) {
                            stepDown(response.getTerm());
                        } else if (nodeState == NodeState.LEADER && term == state.currentTerm) {
                            if (response.getSuccess()) {
                                // Update nextIndex and matchIndex for follower
                                state.nextIndex.put(peer, prevIdx + entriesCount + 1);
                                state.matchIndex.put(peer, state.nextIndex.get(peer) - 1);
                                updateCommitIndex();
                            } else {
                                // Decrement nextIndex and retry
                                state.nextIndex.put(peer, Math.max(1, state.nextIndex.get(peer) - 1));
                            }
                        }
                    } finally {
                        lock.unlock();
                    }
                } catch (Exception e) {
                    // Peer unavailable
                }
            });
        }
    }

    /**
     * Update commitIndex based on matchIndex of peers.
     * An entry is committed when replicated on a majority of servers.
     */
    private void updateCommitIndex() {
        for (long n = state.commitIndex + 1; n < state.log.size(); n++) {
            // Only commit entries from current term (Raft safety property)
            if (state.log.get((int) n).term != state.currentTerm) continue;

            int count = 1; // Self
            for (String peer : peers) {
                if (state.matchIndex.getOrDefault(peer, 0L) >= n) count++;
            }

            if (count >= (peers.size() + 1) / 2 + 1) {
                state.commitIndex = n;
                applyToStateMachine();
            }
        }
    }

    /**
     * Apply committed entries to the state machine (key-value store).
     */
    private void applyToStateMachine() {
        while (state.lastApplied < state.commitIndex) {
            state.lastApplied++;
            LogEntry entry = state.log.get((int) state.lastApplied);
            String cmd = new String(entry.command);

            if ("put".equals(entry.commandType)) {
                int sep = cmd.indexOf(':');
                if (sep != -1) {
                    String key = cmd.substring(0, sep);
                    String value = cmd.substring(sep + 1);
                    kvStore.put(key, value);
                }
            } else if ("delete".equals(entry.commandType)) {
                kvStore.remove(cmd);
            }
        }
        // Signal waiting threads that entries have been applied
        applyCondition.signalAll();
    }

    // =========================================================================
    // RaftService RPC Implementation
    // =========================================================================
    class RaftServiceImpl extends RaftServiceGrpc.RaftServiceImplBase {

        /**
         * Handle RequestVote RPC from a candidate.
         *
         * Per Raft specification:
         * 1. Reply false if term < currentTerm
         * 2. If votedFor is null or candidateId, and candidate's log is at
         *    least as up-to-date as receiver's log, grant vote
         */
        @Override
        public void requestVote(RequestVoteRequest request, StreamObserver<RequestVoteResponse> responseObserver) {
            lock.lock();
            try {
                // Update term if we see a higher term
                if (request.getTerm() > state.currentTerm) {
                    stepDown(request.getTerm());
                }

                // Check if candidate's log is at least as up-to-date as ours
                boolean logOk = request.getLastLogTerm() > getLastLogTerm() ||
                        (request.getLastLogTerm() == getLastLogTerm() &&
                                request.getLastLogIndex() >= getLastLogIndex());

                boolean voteGranted = false;
                if (request.getTerm() == state.currentTerm && logOk &&
                        (state.votedFor == null || state.votedFor.equals(request.getCandidateId()))) {
                    state.votedFor = request.getCandidateId();
                    voteGranted = true;
                    resetElectionTimer();
                }

                responseObserver.onNext(RequestVoteResponse.newBuilder()
                        .setTerm(state.currentTerm)
                        .setVoteGranted(voteGranted)
                        .build());
                responseObserver.onCompleted();
            } finally {
                lock.unlock();
            }
        }

        /**
         * Handle AppendEntries RPC from leader.
         *
         * Per Raft specification:
         * 1. Reply false if term < currentTerm
         * 2. Reply false if log doesn't contain entry at prevLogIndex with prevLogTerm
         * 3. If existing entry conflicts with new one, delete it and all that follow
         * 4. Append any new entries not already in the log
         * 5. If leaderCommit > commitIndex, set commitIndex = min(leaderCommit, last new entry index)
         */
        @Override
        public void appendEntries(AppendEntriesRequest request, StreamObserver<AppendEntriesResponse> responseObserver) {
            lock.lock();
            try {
                // Update term if we see a higher term
                if (request.getTerm() > state.currentTerm) {
                    stepDown(request.getTerm());
                }

                // Reply false if term < currentTerm
                if (request.getTerm() < state.currentTerm) {
                    responseObserver.onNext(AppendEntriesResponse.newBuilder()
                            .setTerm(state.currentTerm)
                            .setSuccess(false)
                            .setMatchIndex(getLastLogIndex())
                            .build());
                    responseObserver.onCompleted();
                    return;
                }

                // Valid AppendEntries from leader - update state
                leaderId = request.getLeaderId();
                nodeState = NodeState.FOLLOWER;
                resetElectionTimer();

                // Check log consistency
                if (request.getPrevLogIndex() >= state.log.size() ||
                        state.log.get((int) request.getPrevLogIndex()).term != request.getPrevLogTerm()) {
                    responseObserver.onNext(AppendEntriesResponse.newBuilder()
                            .setTerm(state.currentTerm)
                            .setSuccess(false)
                            .setMatchIndex(getLastLogIndex())
                            .build());
                    responseObserver.onCompleted();
                    return;
                }

                // Append new entries
                int logPtr = (int) request.getPrevLogIndex() + 1;
                for (com.sdp.raft.LogEntry entry : request.getEntriesList()) {
                    if (logPtr < state.log.size()) {
                        // Conflict detection - delete conflicting entries
                        if (state.log.get(logPtr).term != entry.getTerm()) {
                            state.log.subList(logPtr, state.log.size()).clear();
                        }
                    }
                    if (logPtr >= state.log.size()) {
                        state.log.add(new LogEntry(
                                entry.getIndex(),
                                entry.getTerm(),
                                entry.getCommand().toByteArray(),
                                entry.getCommandType()
                        ));
                    }
                    logPtr++;
                }

                // Update commit index
                if (request.getLeaderCommit() > state.commitIndex) {
                    state.commitIndex = Math.min(request.getLeaderCommit(), getLastLogIndex());
                    applyToStateMachine();
                }

                responseObserver.onNext(AppendEntriesResponse.newBuilder()
                        .setTerm(state.currentTerm)
                        .setSuccess(true)
                        .setMatchIndex(getLastLogIndex())
                        .build());
                responseObserver.onCompleted();
            } finally {
                lock.unlock();
            }
        }

        /**
         * Handle InstallSnapshot RPC from leader.
         * Used when leader needs to bring a far-behind follower up to date.
         */
        @Override
        public void installSnapshot(InstallSnapshotRequest request, StreamObserver<InstallSnapshotResponse> responseObserver) {
            lock.lock();
            try {
                if (request.getTerm() > state.currentTerm) {
                    stepDown(request.getTerm());
                }
                responseObserver.onNext(InstallSnapshotResponse.newBuilder()
                        .setTerm(state.currentTerm)
                        .build());
                responseObserver.onCompleted();
            } finally {
                lock.unlock();
            }
        }
    }

    // =========================================================================
    // KeyValueService RPC Implementation
    // =========================================================================
    class KeyValueServiceImpl extends KeyValueServiceGrpc.KeyValueServiceImplBase {

        /**
         * Handle Get RPC - reads from local key-value store.
         * Reads can be served by any node (eventual consistency).
         */
        @Override
        public void get(GetRequest request, StreamObserver<GetResponse> responseObserver) {
            String value = kvStore.get(request.getKey());
            responseObserver.onNext(GetResponse.newBuilder()
                    .setValue(value != null ? value : "")
                    .setFound(value != null)
                    .build());
            responseObserver.onCompleted();
        }

        /**
         * Handle Put RPC - stores key-value pair through consensus.
         * Only the leader can accept writes.
         */
        @Override
        public void put(PutRequest request, StreamObserver<PutResponse> responseObserver) {
            lock.lock();
            try {
                // Redirect to leader if we're not the leader
                if (nodeState != NodeState.LEADER) {
                    responseObserver.onNext(PutResponse.newBuilder()
                            .setSuccess(false)
                            .setError("Not the leader")
                            .setLeaderHint(leaderId)
                            .build());
                    responseObserver.onCompleted();
                    return;
                }

                // Append to log
                LogEntry entry = new LogEntry(
                        getLastLogIndex() + 1,
                        state.currentTerm,
                        (request.getKey() + ":" + request.getValue()).getBytes(),
                        "put"
                );
                state.log.add(entry);
                long waitIdx = entry.index;

                // Wait for entry to be committed and applied
                while (state.lastApplied < waitIdx && nodeState == NodeState.LEADER) {
                    try {
                        applyCondition.await(100, TimeUnit.MILLISECONDS);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                }

                boolean success = state.lastApplied >= waitIdx;
                responseObserver.onNext(PutResponse.newBuilder()
                        .setSuccess(success)
                        .build());
                responseObserver.onCompleted();
            } finally {
                lock.unlock();
            }
        }

        /**
         * Handle Delete RPC - removes key through consensus.
         * Only the leader can accept writes.
         */
        @Override
        public void delete(DeleteRequest request, StreamObserver<DeleteResponse> responseObserver) {
            lock.lock();
            try {
                // Redirect to leader if we're not the leader
                if (nodeState != NodeState.LEADER) {
                    responseObserver.onNext(DeleteResponse.newBuilder()
                            .setSuccess(false)
                            .setError("Not the leader")
                            .setLeaderHint(leaderId)
                            .build());
                    responseObserver.onCompleted();
                    return;
                }

                // Append to log
                LogEntry entry = new LogEntry(
                        getLastLogIndex() + 1,
                        state.currentTerm,
                        request.getKey().getBytes(),
                        "delete"
                );
                state.log.add(entry);
                long waitIdx = entry.index;

                // Wait for entry to be committed and applied
                while (state.lastApplied < waitIdx && nodeState == NodeState.LEADER) {
                    try {
                        applyCondition.await(100, TimeUnit.MILLISECONDS);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                }

                boolean success = state.lastApplied >= waitIdx;
                responseObserver.onNext(DeleteResponse.newBuilder()
                        .setSuccess(success)
                        .build());
                responseObserver.onCompleted();
            } finally {
                lock.unlock();
            }
        }

        /**
         * Handle GetLeader RPC - returns current leader information.
         */
        @Override
        public void getLeader(GetLeaderRequest request, StreamObserver<GetLeaderResponse> responseObserver) {
            lock.lock();
            try {
                GetLeaderResponse.Builder builder = GetLeaderResponse.newBuilder()
                        .setLeaderId(leaderId)
                        .setIsLeader(nodeState == NodeState.LEADER);

                for (String peer : peers) {
                    if (peer.contains(leaderId)) {
                        builder.setLeaderAddress(peer);
                        break;
                    }
                }

                if (nodeState == NodeState.LEADER) {
                    builder.setLeaderAddress("localhost:" + port);
                }

                responseObserver.onNext(builder.build());
                responseObserver.onCompleted();
            } finally {
                lock.unlock();
            }
        }

        /**
         * Handle GetClusterStatus RPC - returns detailed cluster state.
         */
        @Override
        public void getClusterStatus(GetClusterStatusRequest request, StreamObserver<GetClusterStatusResponse> responseObserver) {
            lock.lock();
            try {
                GetClusterStatusResponse.Builder builder = GetClusterStatusResponse.newBuilder()
                        .setNodeId(nodeId)
                        .setState(nodeState.getValue())
                        .setCurrentTerm(state.currentTerm)
                        .setVotedFor(state.votedFor != null ? state.votedFor : "")
                        .setCommitIndex(state.commitIndex)
                        .setLastApplied(state.lastApplied)
                        .setLogLength(state.log.size())
                        .setLastLogTerm(getLastLogTerm());

                for (String peer : peers) {
                    ClusterMember.Builder memberBuilder = ClusterMember.newBuilder().setAddress(peer);
                    if (nodeState == NodeState.LEADER) {
                        memberBuilder.setMatchIndex(state.matchIndex.getOrDefault(peer, 0L));
                        memberBuilder.setNextIndex(state.nextIndex.getOrDefault(peer, 1L));
                    }
                    builder.addMembers(memberBuilder.build());
                }

                responseObserver.onNext(builder.build());
                responseObserver.onCompleted();
            } finally {
                lock.unlock();
            }
        }
    }

    // =========================================================================
    // Server Startup
    // =========================================================================
    public void start() throws IOException {
        Server server = ServerBuilder.forPort(port)
                .addService(new RaftServiceImpl())
                .addService(new KeyValueServiceImpl())
                .build()
                .start();

        // Start background threads for election and heartbeat
        scheduler.submit(this::electionTimerLoop);
        scheduler.submit(this::heartbeatLoop);

        logger.info("Starting Raft node " + nodeId + " on port " + port);

        // Graceful shutdown hook
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            running = false;
            scheduler.shutdown();
            server.shutdown();
        }));

        try {
            server.awaitTermination();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    // =========================================================================
    // Main Entry Point
    // =========================================================================
    public static void main(String[] args) {
        String nodeId = null;
        int port = 50051;
        String peersStr = null;

        // Parse command-line arguments
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

        List<String> peers = Arrays.asList(peersStr.split(","));
        peers.replaceAll(String::trim);

        RaftServer server = new RaftServer(nodeId, port, peers);
        server.initialize();

        try {
            server.start();
        } catch (IOException e) {
            e.printStackTrace();
            System.exit(1);
        }
    }
}
