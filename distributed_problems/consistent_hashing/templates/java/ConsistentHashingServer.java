/**
 * Consistent Hashing Implementation - Java Template
 *
 * This template provides the basic structure for implementing a
 * consistent hash ring for distributed key-value storage.
 *
 * Key concepts:
 * 1. Hash Ring - Keys and nodes are mapped to a circular hash space
 * 2. Virtual Nodes - Each physical node has multiple positions on the ring
 * 3. Lookup - Find the first node clockwise from the key's hash position
 * 4. Rebalancing - When nodes join/leave, only nearby keys need to move
 *
 * Usage:
 *     java ConsistentHashingServer --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

package com.sdp.chash;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.stub.StreamObserver;

import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.logging.Logger;

public class ConsistentHashingServer {
    private static final Logger logger = Logger.getLogger(ConsistentHashingServer.class.getName());

    private static final int DEFAULT_VIRTUAL_NODES = 150;
    private static final int DEFAULT_REPLICATION_FACTOR = 3;

    // Virtual node on the hash ring
    public static class VirtualNode implements Comparable<VirtualNode> {
        public final String nodeId;
        public final int virtualId;
        public final long hashValue;

        public VirtualNode(String nodeId, int virtualId, long hashValue) {
            this.nodeId = nodeId;
            this.virtualId = virtualId;
            this.hashValue = hashValue;
        }

        @Override
        public int compareTo(VirtualNode other) {
            return Long.compare(this.hashValue, other.hashValue);
        }
    }

    // Physical node info
    public static class NodeInfo {
        public String nodeId;
        public String address;
        public int virtualNodes;
        public long keysCount;
        public boolean isHealthy;
        public long lastHeartbeat;

        public NodeInfo(String nodeId, String address, int virtualNodes) {
            this.nodeId = nodeId;
            this.address = address;
            this.virtualNodes = virtualNodes;
            this.keysCount = 0;
            this.isHealthy = true;
            this.lastHeartbeat = System.currentTimeMillis();
        }
    }

    // Hash ring state
    public static class HashRingState {
        public Map<String, NodeInfo> nodes = new ConcurrentHashMap<>();
        public List<VirtualNode> vnodes = new ArrayList<>();
        public int replicationFactor = DEFAULT_REPLICATION_FACTOR;
        public int vnodesPerNode = DEFAULT_VIRTUAL_NODES;
    }

    // Main node implementation
    public static class ConsistentHashRingNode extends HashRingServiceGrpc.HashRingServiceImplBase {
        private final String nodeId;
        private final int port;
        private final List<String> peers;
        private final HashRingState state;
        private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

        // Key-value store
        private final Map<String, String> kvStore = new ConcurrentHashMap<>();

        // gRPC clients for peer communication
        private final Map<String, NodeServiceGrpc.NodeServiceBlockingStub> peerStubs = new ConcurrentHashMap<>();

        public ConsistentHashRingNode(String nodeId, int port, List<String> peers) {
            this.nodeId = nodeId;
            this.port = port;
            this.peers = peers;
            this.state = new HashRingState();
        }

        public void initialize() {
            for (String peer : peers) {
                ManagedChannel channel;
                // Cloud Run URLs require TLS
                if (peer.contains(".run.app")) {
                    channel = ManagedChannelBuilder.forTarget(peer)
                            .useTransportSecurity()
                            .build();
                    logger.info("Using TLS for peer: " + peer);
                } else {
                    channel = ManagedChannelBuilder.forTarget(peer)
                            .usePlaintext()
                            .build();
                    logger.info("Using plaintext for peer: " + peer);
                }
                peerStubs.put(peer, NodeServiceGrpc.newBlockingStub(channel));
            }

            // Add self to the ring
            String selfAddr = "localhost:" + port;
            addNodeInternal(nodeId, selfAddr, DEFAULT_VIRTUAL_NODES);
            logger.info("Node " + nodeId + " initialized with peers: " + peers);
        }

        /**
         * Hash a key to a position on the ring.
         *
         * TODO: Implement consistent hashing function:
         * - Use a good hash function (MD5, SHA-1, etc.)
         * - Return a value in the ring's hash space
         * - Must be deterministic (same key always hashes to same position)
         */
        public long hash(String key) {
            // TODO: Implement this method
            throw new UnsupportedOperationException("hash not implemented");
        }

        private long getVNodeHash(String nodeId, int virtualId) {
            return hash(nodeId + ":" + virtualId);
        }

        /**
         * Add a node to the hash ring.
         *
         * TODO: Implement node addition:
         * 1. Create virtual nodes for this physical node
         * 2. Insert virtual nodes into the ring (maintain sorted order)
         * 3. Return list of added virtual nodes
         */
        public List<VirtualNode> addNodeInternal(String nodeId, String address, int numVNodes) {
            // TODO: Implement this method
            throw new UnsupportedOperationException("addNodeInternal not implemented");
        }

        /**
         * Remove a node from the hash ring.
         *
         * TODO: Implement node removal:
         * 1. Remove all virtual nodes for this physical node
         * 2. Update the ring structure
         * 3. Return true if successful
         */
        public boolean removeNodeInternal(String nodeId) {
            // TODO: Implement this method
            throw new UnsupportedOperationException("removeNodeInternal not implemented");
        }

        /**
         * Get the node responsible for a key.
         *
         * TODO: Implement key lookup:
         * 1. Hash the key to find its position on the ring
         * 2. Find the first node clockwise from that position
         * 3. Handle wrap-around (if key hash > max vnode hash, use first node)
         */
        public NodeInfo getNodeForKey(String key) {
            // TODO: Implement this method
            return null;
        }

        /**
         * Get multiple nodes for a key (for replication).
         *
         * TODO: Implement multi-node lookup:
         * 1. Find the primary node for the key
         * 2. Walk clockwise to find additional unique physical nodes
         * 3. Return up to 'count' unique physical nodes
         */
        public List<NodeInfo> getNodesForKey(String key, int count) {
            // TODO: Implement this method
            return Collections.emptyList();
        }

        // =========================================================================
        // HashRingService RPC Implementations
        // =========================================================================

        @Override
        public void addNode(ConsistentHashing.AddNodeRequest request,
                           StreamObserver<ConsistentHashing.AddNodeResponse> responseObserver) {
            int numVNodes = request.getVirtualNodes();
            if (numVNodes == 0) numVNodes = DEFAULT_VIRTUAL_NODES;

            List<VirtualNode> vnodes = addNodeInternal(request.getNodeId(), request.getAddress(), numVNodes);

            ConsistentHashing.AddNodeResponse.Builder response = ConsistentHashing.AddNodeResponse.newBuilder();
            response.setSuccess(true);
            for (VirtualNode v : vnodes) {
                response.addAddedVnodes(ConsistentHashing.VirtualNode.newBuilder()
                    .setNodeId(v.nodeId)
                    .setVirtualId(v.virtualId)
                    .setHashValue(v.hashValue)
                    .build());
            }

            responseObserver.onNext(response.build());
            responseObserver.onCompleted();
        }

        @Override
        public void removeNode(ConsistentHashing.RemoveNodeRequest request,
                              StreamObserver<ConsistentHashing.RemoveNodeResponse> responseObserver) {
            boolean success = removeNodeInternal(request.getNodeId());

            responseObserver.onNext(ConsistentHashing.RemoveNodeResponse.newBuilder()
                .setSuccess(success)
                .setError(success ? "" : "Node not found")
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void getNode(ConsistentHashing.GetNodeRequest request,
                           StreamObserver<ConsistentHashing.GetNodeResponse> responseObserver) {
            NodeInfo node = getNodeForKey(request.getKey());

            ConsistentHashing.GetNodeResponse.Builder response = ConsistentHashing.GetNodeResponse.newBuilder();
            if (node != null) {
                response.setNodeId(node.nodeId);
                response.setNodeAddress(node.address);
                response.setKeyHash(hash(request.getKey()));
            }

            responseObserver.onNext(response.build());
            responseObserver.onCompleted();
        }

        @Override
        public void getNodes(ConsistentHashing.GetNodesRequest request,
                            StreamObserver<ConsistentHashing.GetNodesResponse> responseObserver) {
            int count = request.getCount();
            if (count == 0) count = 3;

            List<NodeInfo> nodes = getNodesForKey(request.getKey(), count);

            ConsistentHashing.GetNodesResponse.Builder response = ConsistentHashing.GetNodesResponse.newBuilder();
            for (NodeInfo n : nodes) {
                response.addNodes(ConsistentHashing.NodeInfo.newBuilder()
                    .setNodeId(n.nodeId)
                    .setAddress(n.address)
                    .setVirtualNodes(n.virtualNodes)
                    .setKeysCount(n.keysCount)
                    .setIsHealthy(n.isHealthy)
                    .build());
            }
            response.setKeyHash(hash(request.getKey()));

            responseObserver.onNext(response.build());
            responseObserver.onCompleted();
        }

        @Override
        public void getRingState(ConsistentHashing.GetRingStateRequest request,
                                StreamObserver<ConsistentHashing.GetRingStateResponse> responseObserver) {
            lock.readLock().lock();
            try {
                ConsistentHashing.GetRingStateResponse.Builder response = ConsistentHashing.GetRingStateResponse.newBuilder();

                long totalKeys = 0;
                for (NodeInfo n : state.nodes.values()) {
                    response.addNodes(ConsistentHashing.NodeInfo.newBuilder()
                        .setNodeId(n.nodeId)
                        .setAddress(n.address)
                        .setVirtualNodes(n.virtualNodes)
                        .setKeysCount(n.keysCount)
                        .setIsHealthy(n.isHealthy)
                        .build());
                    totalKeys += n.keysCount;
                }

                for (VirtualNode v : state.vnodes) {
                    response.addVnodes(ConsistentHashing.VirtualNode.newBuilder()
                        .setNodeId(v.nodeId)
                        .setVirtualId(v.virtualId)
                        .setHashValue(v.hashValue)
                        .build());
                }

                response.setTotalKeys(totalKeys);
                response.setReplicationFactor(state.replicationFactor);

                responseObserver.onNext(response.build());
                responseObserver.onCompleted();
            } finally {
                lock.readLock().unlock();
            }
        }

        @Override
        public void rebalance(ConsistentHashing.RebalanceRequest request,
                             StreamObserver<ConsistentHashing.RebalanceResponse> responseObserver) {
            // TODO: Implement rebalancing logic
            responseObserver.onNext(ConsistentHashing.RebalanceResponse.newBuilder()
                .setSuccess(true)
                .setKeysMoved(0)
                .build());
            responseObserver.onCompleted();
        }

        // Key-value store methods
        public String get(String key) {
            return kvStore.get(key);
        }

        public void put(String key, String value) {
            kvStore.put(key, value);
            lock.writeLock().lock();
            try {
                NodeInfo node = state.nodes.get(nodeId);
                if (node != null) {
                    node.keysCount = kvStore.size();
                }
            } finally {
                lock.writeLock().unlock();
            }
        }

        public boolean delete(String key) {
            if (kvStore.remove(key) != null) {
                lock.writeLock().lock();
                try {
                    NodeInfo node = state.nodes.get(nodeId);
                    if (node != null) {
                        node.keysCount = kvStore.size();
                    }
                } finally {
                    lock.writeLock().unlock();
                }
                return true;
            }
            return false;
        }

        public String getNodeId() {
            return nodeId;
        }

        public int getPort() {
            return port;
        }

        public Map<String, NodeInfo> getNodes() {
            return state.nodes;
        }

        public Map<String, String> getKvStore() {
            return kvStore;
        }
    }

    // KeyValueService implementation
    public static class KeyValueServiceImpl extends KeyValueServiceGrpc.KeyValueServiceImplBase {
        private final ConsistentHashRingNode ring;

        public KeyValueServiceImpl(ConsistentHashRingNode ring) {
            this.ring = ring;
        }

        @Override
        public void get(ConsistentHashing.GetRequest request,
                       StreamObserver<ConsistentHashing.GetResponse> responseObserver) {
            String value = ring.get(request.getKey());
            responseObserver.onNext(ConsistentHashing.GetResponse.newBuilder()
                .setValue(value != null ? value : "")
                .setFound(value != null)
                .setServedBy(ring.getNodeId())
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void put(ConsistentHashing.PutRequest request,
                       StreamObserver<ConsistentHashing.PutResponse> responseObserver) {
            ring.put(request.getKey(), request.getValue());
            responseObserver.onNext(ConsistentHashing.PutResponse.newBuilder()
                .setSuccess(true)
                .setStoredOn(ring.getNodeId())
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void delete(ConsistentHashing.DeleteRequest request,
                          StreamObserver<ConsistentHashing.DeleteResponse> responseObserver) {
            boolean success = ring.delete(request.getKey());
            responseObserver.onNext(ConsistentHashing.DeleteResponse.newBuilder()
                .setSuccess(success)
                .setError(success ? "" : "Key not found")
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void getLeader(ConsistentHashing.GetLeaderRequest request,
                             StreamObserver<ConsistentHashing.GetLeaderResponse> responseObserver) {
            responseObserver.onNext(ConsistentHashing.GetLeaderResponse.newBuilder()
                .setNodeId(ring.getNodeId())
                .setNodeAddress("localhost:" + ring.getPort())
                .setIsCoordinator(true)
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void getClusterStatus(ConsistentHashing.GetClusterStatusRequest request,
                                    StreamObserver<ConsistentHashing.GetClusterStatusResponse> responseObserver) {
            Map<String, ConsistentHashRingNode.NodeInfo> nodes = ring.getNodes();

            ConsistentHashing.GetClusterStatusResponse.Builder response = ConsistentHashing.GetClusterStatusResponse.newBuilder();
            response.setNodeId(ring.getNodeId());
            response.setNodeAddress("localhost:" + ring.getPort());
            response.setIsCoordinator(true);
            response.setTotalNodes(nodes.size());

            long totalKeys = 0;
            int healthyNodes = 0;
            for (ConsistentHashRingNode.NodeInfo n : nodes.values()) {
                response.addMembers(ConsistentHashing.NodeInfo.newBuilder()
                    .setNodeId(n.nodeId)
                    .setAddress(n.address)
                    .setVirtualNodes(n.virtualNodes)
                    .setKeysCount(n.keysCount)
                    .setIsHealthy(n.isHealthy)
                    .build());
                totalKeys += n.keysCount;
                if (n.isHealthy) healthyNodes++;
            }

            response.setHealthyNodes(healthyNodes);
            response.setTotalKeys(totalKeys);
            response.setReplicationFactor(DEFAULT_REPLICATION_FACTOR);
            response.setVirtualNodesPerNode(DEFAULT_VIRTUAL_NODES);

            responseObserver.onNext(response.build());
            responseObserver.onCompleted();
        }
    }

    // NodeService implementation
    public static class NodeServiceImpl extends NodeServiceGrpc.NodeServiceImplBase {
        private final ConsistentHashRingNode ring;

        public NodeServiceImpl(ConsistentHashRingNode ring) {
            this.ring = ring;
        }

        @Override
        public void transferKeys(ConsistentHashing.TransferKeysRequest request,
                                StreamObserver<ConsistentHashing.TransferKeysResponse> responseObserver) {
            for (ConsistentHashing.KeyValuePair kv : request.getKeysList()) {
                ring.put(kv.getKey(), kv.getValue());
            }
            responseObserver.onNext(ConsistentHashing.TransferKeysResponse.newBuilder()
                .setSuccess(true)
                .setKeysReceived(request.getKeysCount())
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void heartbeat(ConsistentHashing.HeartbeatRequest request,
                             StreamObserver<ConsistentHashing.HeartbeatResponse> responseObserver) {
            responseObserver.onNext(ConsistentHashing.HeartbeatResponse.newBuilder()
                .setAcknowledged(true)
                .setTimestamp(System.currentTimeMillis())
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void getLocalKeys(ConsistentHashing.GetLocalKeysRequest request,
                                StreamObserver<ConsistentHashing.GetLocalKeysResponse> responseObserver) {
            ConsistentHashing.GetLocalKeysResponse.Builder response = ConsistentHashing.GetLocalKeysResponse.newBuilder();
            Map<String, String> kvStore = ring.getKvStore();
            for (Map.Entry<String, String> entry : kvStore.entrySet()) {
                response.addKeys(ConsistentHashing.KeyValuePair.newBuilder()
                    .setKey(entry.getKey())
                    .setValue(entry.getValue())
                    .setHash(ring.hash(entry.getKey()))
                    .build());
            }
            response.setTotalCount(kvStore.size());
            responseObserver.onNext(response.build());
            responseObserver.onCompleted();
        }

        @Override
        public void storeLocal(ConsistentHashing.StoreLocalRequest request,
                              StreamObserver<ConsistentHashing.StoreLocalResponse> responseObserver) {
            ring.put(request.getKey(), request.getValue());
            responseObserver.onNext(ConsistentHashing.StoreLocalResponse.newBuilder()
                .setSuccess(true)
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void deleteLocal(ConsistentHashing.DeleteLocalRequest request,
                               StreamObserver<ConsistentHashing.DeleteLocalResponse> responseObserver) {
            boolean success = ring.delete(request.getKey());
            responseObserver.onNext(ConsistentHashing.DeleteLocalResponse.newBuilder()
                .setSuccess(success)
                .setError(success ? "" : "Key not found")
                .build());
            responseObserver.onCompleted();
        }
    }

    // =============================================================================
    // Main Entry Point
    // =============================================================================

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
            System.err.println("Usage: java ConsistentHashingServer --node-id <id> --port <port> --peers <peer1:port1,peer2:port2>");
            System.exit(1);
        }

        List<String> peers = new ArrayList<>();
        for (String peer : peersStr.split(",")) {
            peers.add(peer.trim());
        }

        ConsistentHashRingNode node = new ConsistentHashRingNode(nodeId, port, peers);
        node.initialize();

        Server server = ServerBuilder.forPort(port)
                .addService(node)
                .addService(new KeyValueServiceImpl(node))
                .addService(new NodeServiceImpl(node))
                .build()
                .start();

        logger.info("Starting Consistent Hashing node " + nodeId + " on port " + port);
        server.awaitTermination();
    }
}
