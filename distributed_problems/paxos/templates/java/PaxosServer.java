/**
 * Paxos Consensus Implementation - Java Template
 *
 * This template provides the basic structure for implementing the Multi-Paxos
 * consensus algorithm. You need to implement the TODO sections.
 *
 * For the full Paxos specification, see: "Paxos Made Simple" by Leslie Lamport
 *
 * Usage:
 *     java PaxosServer --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

package com.sdp.paxos;

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

public class PaxosServer {
    private static final Logger logger = Logger.getLogger(PaxosServer.class.getName());

    // Node roles
    public enum NodeRole {
        PROPOSER("proposer"),
        ACCEPTOR("acceptor"),
        LEARNER("learner"),
        LEADER("leader");

        private final String value;

        NodeRole(String value) {
            this.value = value;
        }

        @Override
        public String toString() {
            return value;
        }
    }

    // Proposal number for ordering
    public static class ProposalNumber implements Comparable<ProposalNumber> {
        public long round;
        public String proposerId;

        public ProposalNumber(long round, String proposerId) {
            this.round = round;
            this.proposerId = proposerId;
        }

        @Override
        public int compareTo(ProposalNumber other) {
            if (this.round != other.round) {
                return Long.compare(this.round, other.round);
            }
            return this.proposerId.compareTo(other.proposerId);
        }

        @Override
        public boolean equals(Object obj) {
            if (!(obj instanceof ProposalNumber)) return false;
            ProposalNumber other = (ProposalNumber) obj;
            return this.round == other.round && this.proposerId.equals(other.proposerId);
        }

        public Paxos.ProposalNumber toProto() {
            return Paxos.ProposalNumber.newBuilder()
                    .setRound(round)
                    .setProposerId(proposerId)
                    .build();
        }

        public static ProposalNumber fromProto(Paxos.ProposalNumber proto) {
            return new ProposalNumber(proto.getRound(), proto.getProposerId());
        }
    }

    // Acceptor state for each slot
    public static class AcceptorState {
        public ProposalNumber highestPromised;
        public ProposalNumber acceptedProposal;
        public byte[] acceptedValue;
    }

    // Paxos state
    public static class PaxosState {
        public long currentRound = 0;
        public Map<Long, AcceptorState> acceptorStates = new ConcurrentHashMap<>();
        public Map<Long, byte[]> learnedValues = new ConcurrentHashMap<>();
        public long firstUnchosenSlot = 0;
        public long lastExecutedSlot = 0;
    }

    // Main Paxos node implementation
    public static class PaxosNode extends PaxosServiceGrpc.PaxosServiceImplBase
            implements KeyValueServiceGrpc.KeyValueServiceImplBase {

        private final String nodeId;
        private final int port;
        private final List<String> peers;
        private final PaxosState state;
        private volatile NodeRole role;
        private volatile String leaderId;

        // Key-value store (state machine)
        private final Map<String, String> kvStore = new ConcurrentHashMap<>();

        // Timing configuration
        private static final double HEARTBEAT_INTERVAL = 0.1;  // 100ms
        private static final double LEADER_TIMEOUT = 0.5;     // 500ms

        // Synchronization
        private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

        // gRPC clients for peer communication
        private final Map<String, PaxosServiceGrpc.PaxosServiceBlockingStub> peerStubs = new ConcurrentHashMap<>();

        public PaxosNode(String nodeId, int port, List<String> peers) {
            this.nodeId = nodeId;
            this.port = port;
            this.peers = peers;
            this.state = new PaxosState();
            this.role = NodeRole.ACCEPTOR;
        }

        public void initialize() {
            for (String peer : peers) {
                ManagedChannel channel = ManagedChannelBuilder.forTarget(peer)
                        .usePlaintext()
                        .build();
                peerStubs.put(peer, PaxosServiceGrpc.newBlockingStub(channel));
            }
            logger.info("Node " + nodeId + " initialized with peers: " + peers);
        }

        public AcceptorState getAcceptorState(long slot) {
            return state.acceptorStates.computeIfAbsent(slot, k -> new AcceptorState());
        }

        public ProposalNumber generateProposalNumber() {
            state.currentRound++;
            return new ProposalNumber(state.currentRound, nodeId);
        }

        // =========================================================================
        // Phase 1: Prepare
        // =========================================================================

        /**
         * Send Prepare requests to all acceptors.
         *
         * TODO: Implement Phase 1a of Paxos:
         * 1. Send Prepare(n) to all acceptors
         * 2. Wait for responses from a majority
         * 3. If majority promise, return (true, highest_accepted_value)
         * 4. If any acceptor has accepted a value, use that value
         */
        public Object[] sendPrepare(long slot, ProposalNumber proposal) {
            return new Object[]{false, null};
        }

        /**
         * Handle Prepare RPC from a proposer.
         *
         * TODO: Implement Phase 1b of Paxos:
         * 1. If n > highest_promised, update highest_promised and promise
         * 2. Return (promised=True, accepted_proposal, accepted_value)
         * 3. Otherwise return (promised=False, highest_promised)
         */
        @Override
        public void prepare(Paxos.PrepareRequest request,
                            StreamObserver<Paxos.PrepareResponse> responseObserver) {
            lock.writeLock().lock();
            try {
                Paxos.PrepareResponse.Builder response = Paxos.PrepareResponse.newBuilder();

                long slot = request.getSlot();
                ProposalNumber proposal = ProposalNumber.fromProto(request.getProposalNumber());
                AcceptorState acceptorState = getAcceptorState(slot);

                // TODO: Implement prepare logic
                response.setPromised(false);

                responseObserver.onNext(response.build());
                responseObserver.onCompleted();
            } finally {
                lock.writeLock().unlock();
            }
        }

        // =========================================================================
        // Phase 2: Accept
        // =========================================================================

        /**
         * Send Accept requests to all acceptors.
         *
         * TODO: Implement Phase 2a of Paxos:
         * 1. Send Accept(n, v) to all acceptors
         * 2. Wait for responses from a majority
         * 3. If majority accept, value is chosen - notify learners
         * 4. Return true if value was chosen
         */
        public boolean sendAccept(long slot, ProposalNumber proposal, byte[] value) {
            return false;
        }

        /**
         * Handle Accept RPC from a proposer.
         *
         * TODO: Implement Phase 2b of Paxos:
         * 1. If n >= highest_promised, accept the value
         * 2. Update accepted_proposal and accepted_value
         * 3. Return (accepted=True)
         * 4. Otherwise return (accepted=False, highest_promised)
         */
        @Override
        public void accept(Paxos.AcceptRequest request,
                           StreamObserver<Paxos.AcceptResponse> responseObserver) {
            lock.writeLock().lock();
            try {
                Paxos.AcceptResponse.Builder response = Paxos.AcceptResponse.newBuilder();

                long slot = request.getSlot();
                ProposalNumber proposal = ProposalNumber.fromProto(request.getProposalNumber());
                AcceptorState acceptorState = getAcceptorState(slot);

                // TODO: Implement accept logic
                response.setAccepted(false);

                responseObserver.onNext(response.build());
                responseObserver.onCompleted();
            } finally {
                lock.writeLock().unlock();
            }
        }

        // =========================================================================
        // Learning
        // =========================================================================

        /**
         * Handle Learn RPC - a value has been chosen.
         *
         * TODO: Implement learning:
         * 1. Store the learned value for the slot
         * 2. If this fills a gap, execute commands in order
         */
        @Override
        public void learn(Paxos.LearnRequest request,
                          StreamObserver<Paxos.LearnResponse> responseObserver) {
            lock.writeLock().lock();
            try {
                Paxos.LearnResponse.Builder response = Paxos.LearnResponse.newBuilder();

                long slot = request.getSlot();
                byte[] value = request.getValue().toByteArray();

                // TODO: Implement learn logic
                response.setSuccess(true);

                responseObserver.onNext(response.build());
                responseObserver.onCompleted();
            } finally {
                lock.writeLock().unlock();
            }
        }

        public void applyCommand(byte[] command, String commandType) {
            // TODO: Parse and apply the command
        }

        // =========================================================================
        // Multi-Paxos Leader Election
        // =========================================================================

        @Override
        public void heartbeat(Paxos.HeartbeatRequest request,
                              StreamObserver<Paxos.HeartbeatResponse> responseObserver) {
            lock.writeLock().lock();
            try {
                Paxos.HeartbeatResponse.Builder response = Paxos.HeartbeatResponse.newBuilder();
                // TODO: Implement leader acknowledgment
                response.setAcknowledged(true);
                responseObserver.onNext(response.build());
                responseObserver.onCompleted();
            } finally {
                lock.writeLock().unlock();
            }
        }

        /**
         * Run as the Multi-Paxos leader.
         *
         * TODO: Implement Multi-Paxos optimization:
         * 1. Skip Phase 1 for consecutive slots after becoming leader
         * 2. Send heartbeats to maintain leadership
         * 3. Handle client requests directly
         */
        public void runAsLeader() {
            // TODO: Implement leader logic
        }

        // =========================================================================
        // KeyValueService RPC Implementations
        // =========================================================================

        public void get(Paxos.GetRequest request,
                        StreamObserver<Paxos.GetResponse> responseObserver) {
            lock.readLock().lock();
            try {
                Paxos.GetResponse.Builder response = Paxos.GetResponse.newBuilder();
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
         * 2. Run Paxos to agree on this operation
         * 3. Apply to state machine once chosen
         */
        public void put(Paxos.PutRequest request,
                        StreamObserver<Paxos.PutResponse> responseObserver) {
            lock.writeLock().lock();
            try {
                Paxos.PutResponse.Builder response = Paxos.PutResponse.newBuilder();

                if (role != NodeRole.LEADER) {
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

        public void delete(Paxos.DeleteRequest request,
                           StreamObserver<Paxos.DeleteResponse> responseObserver) {
            lock.writeLock().lock();
            try {
                Paxos.DeleteResponse.Builder response = Paxos.DeleteResponse.newBuilder();

                if (role != NodeRole.LEADER) {
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

        public void getLeader(Paxos.GetLeaderRequest request,
                              StreamObserver<Paxos.GetLeaderResponse> responseObserver) {
            lock.readLock().lock();
            try {
                Paxos.GetLeaderResponse.Builder response = Paxos.GetLeaderResponse.newBuilder();
                response.setLeaderId(leaderId != null ? leaderId : "");
                response.setIsLeader(role == NodeRole.LEADER);

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

        public void getClusterStatus(Paxos.GetClusterStatusRequest request,
                                     StreamObserver<Paxos.GetClusterStatusResponse> responseObserver) {
            lock.readLock().lock();
            try {
                Paxos.GetClusterStatusResponse.Builder response = Paxos.GetClusterStatusResponse.newBuilder();
                response.setNodeId(nodeId);
                response.setRole(role.toString());
                response.setCurrentSlot(state.firstUnchosenSlot);
                response.setHighestPromisedRound(state.currentRound);
                response.setFirstUnchosenSlot(state.firstUnchosenSlot);
                response.setLastExecutedSlot(state.lastExecutedSlot);

                for (String peer : peers) {
                    Paxos.ClusterMember.Builder member = Paxos.ClusterMember.newBuilder();
                    member.setAddress(peer);
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
            System.err.println("Usage: java PaxosServer --node-id <id> --port <port> --peers <peer1:port1,peer2:port2>");
            System.exit(1);
        }

        List<String> peers = new ArrayList<>();
        for (String peer : peersStr.split(",")) {
            peers.add(peer.trim());
        }

        PaxosNode node = new PaxosNode(nodeId, port, peers);
        node.initialize();

        Server server = ServerBuilder.forPort(port)
                .addService(node)
                .build()
                .start();

        logger.info("Starting Paxos node " + nodeId + " on port " + port);

        server.awaitTermination();
    }
}
