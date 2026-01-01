/*
 * Rendezvous Hashing (Highest Random Weight) Implementation in Java
 *
 * Rendezvous hashing assigns keys to nodes by computing a weight for each
 * (key, node) pair and selecting the node with the maximum weight. This provides:
 *
 * - Deterministic mapping: Same key always maps to same node
 * - Minimal disruption: Only keys assigned to a removed node need remapping
 * - No virtual nodes: Simpler than consistent hashing
 * - Easy replication: Use top-N nodes for replica placement
 *
 * Your task: Implement the weight calculation and node selection logic.
 */

package com.systemdesign.rendezvous;

import io.grpc.*;
import io.grpc.netty.shaded.io.grpc.netty.GrpcSslContexts;
import io.grpc.netty.shaded.io.grpc.netty.NettyServerBuilder;
import io.grpc.stub.StreamObserver;

import java.io.File;
import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.nio.ByteBuffer;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

public class RendezvousHashingServer {

    private final String nodeId;
    private final ConcurrentHashMap<String, RendezvousHashingProto.NodeInfo> nodes;
    private final ConcurrentHashMap<String, byte[]> localStore;

    public RendezvousHashingServer(String nodeId) {
        this.nodeId = nodeId;
        this.nodes = new ConcurrentHashMap<>();
        this.localStore = new ConcurrentHashMap<>();
    }

    /**
     * Calculate the weight for a key-node pair.
     *
     * The weight should be deterministic and uniformly distributed.
     * Common approach: hash(key + nodeId) converted to a double.
     *
     * @param key The key to calculate weight for
     * @param nodeId The node identifier
     * @param capacityWeight Multiplier for node capacity (default 1.0)
     * @return A floating point weight value
     *
     * TODO: Implement the weight calculation
     * Hint: Use MessageDigest.getInstance("MD5") to hash key + nodeId,
     *       convert first 8 bytes to long, normalize to [0, 1), multiply by capacityWeight
     */
    public double calculateWeight(String key, String nodeId, double capacityWeight) {
        // TODO: Implement weight calculation
        // 1. Concatenate key and nodeId
        // 2. Hash the concatenated string using MD5
        // 3. Convert hash bytes to a double in range [0, 1)
        // 4. Multiply by capacityWeight
        return 0.0;
    }

    /**
     * Get the node with the highest weight for a given key.
     *
     * @param key The key to look up
     * @return Map.Entry with node ID and weight, or null if no nodes
     *
     * TODO: Implement rendezvous hashing node selection
     */
    public Map.Entry<String, Double> getNodeForKey(String key) {
        if (nodes.isEmpty()) {
            return null;
        }

        // TODO: Implement rendezvous hashing
        // 1. For each active node, calculate weight(key, nodeId)
        // 2. Return the node with the highest weight
        return null;
    }

    /**
     * Get the top N nodes for a key (useful for replication).
     *
     * @param key The key to look up
     * @param count Number of nodes to return
     * @return List of Map.Entry with node ID and weight, sorted by weight descending
     *
     * TODO: Implement multi-node selection
     */
    public List<Map.Entry<String, Double>> getNodesForKey(String key, int count) {
        if (nodes.isEmpty()) {
            return Collections.emptyList();
        }

        // TODO: Implement top-N node selection
        // 1. Calculate weights for all active nodes
        // 2. Sort by weight descending
        // 3. Return top 'count' nodes
        return Collections.emptyList();
    }

    // Node Registry Service Implementation
    class NodeRegistryServiceImpl extends NodeRegistryServiceGrpc.NodeRegistryServiceImplBase {

        @Override
        public void addNode(RendezvousHashingProto.AddNodeRequest request,
                           StreamObserver<RendezvousHashingProto.AddNodeResponse> responseObserver) {
            double capacityWeight = request.getCapacityWeight() > 0 ? request.getCapacityWeight() : 1.0;

            RendezvousHashingProto.NodeInfo nodeInfo = RendezvousHashingProto.NodeInfo.newBuilder()
                    .setNodeId(request.getNodeId())
                    .setAddress(request.getAddress())
                    .setPort(request.getPort())
                    .setCapacityWeight(capacityWeight)
                    .setIsActive(true)
                    .build();

            nodes.put(request.getNodeId(), nodeInfo);

            responseObserver.onNext(RendezvousHashingProto.AddNodeResponse.newBuilder()
                    .setSuccess(true)
                    .setMessage("Node " + request.getNodeId() + " added successfully")
                    .build());
            responseObserver.onCompleted();
        }

        @Override
        public void removeNode(RendezvousHashingProto.RemoveNodeRequest request,
                              StreamObserver<RendezvousHashingProto.RemoveNodeResponse> responseObserver) {
            if (nodes.remove(request.getNodeId()) != null) {
                responseObserver.onNext(RendezvousHashingProto.RemoveNodeResponse.newBuilder()
                        .setSuccess(true)
                        .setMessage("Node " + request.getNodeId() + " removed")
                        .build());
            } else {
                responseObserver.onNext(RendezvousHashingProto.RemoveNodeResponse.newBuilder()
                        .setSuccess(false)
                        .setMessage("Node " + request.getNodeId() + " not found")
                        .build());
            }
            responseObserver.onCompleted();
        }

        @Override
        public void listNodes(RendezvousHashingProto.ListNodesRequest request,
                             StreamObserver<RendezvousHashingProto.ListNodesResponse> responseObserver) {
            responseObserver.onNext(RendezvousHashingProto.ListNodesResponse.newBuilder()
                    .addAllNodes(nodes.values())
                    .build());
            responseObserver.onCompleted();
        }

        @Override
        public void getNodeInfo(RendezvousHashingProto.GetNodeInfoRequest request,
                               StreamObserver<RendezvousHashingProto.GetNodeInfoResponse> responseObserver) {
            RendezvousHashingProto.NodeInfo nodeInfo = nodes.get(request.getNodeId());
            if (nodeInfo != null) {
                responseObserver.onNext(RendezvousHashingProto.GetNodeInfoResponse.newBuilder()
                        .setNode(nodeInfo)
                        .setFound(true)
                        .build());
            } else {
                responseObserver.onNext(RendezvousHashingProto.GetNodeInfoResponse.newBuilder()
                        .setFound(false)
                        .build());
            }
            responseObserver.onCompleted();
        }
    }

    // Rendezvous Service Implementation
    class RendezvousServiceImpl extends RendezvousServiceGrpc.RendezvousServiceImplBase {

        @Override
        public void getNodeForKey(RendezvousHashingProto.GetNodeForKeyRequest request,
                                  StreamObserver<RendezvousHashingProto.GetNodeForKeyResponse> responseObserver) {
            Map.Entry<String, Double> result = RendezvousHashingServer.this.getNodeForKey(request.getKey());

            if (result != null) {
                responseObserver.onNext(RendezvousHashingProto.GetNodeForKeyResponse.newBuilder()
                        .setNodeId(result.getKey())
                        .setWeight(result.getValue())
                        .build());
            } else {
                responseObserver.onError(Status.NOT_FOUND
                        .withDescription("No nodes available")
                        .asRuntimeException());
                return;
            }
            responseObserver.onCompleted();
        }

        @Override
        public void getNodesForKey(RendezvousHashingProto.GetNodesForKeyRequest request,
                                   StreamObserver<RendezvousHashingProto.GetNodesForKeyResponse> responseObserver) {
            List<Map.Entry<String, Double>> results =
                    RendezvousHashingServer.this.getNodesForKey(request.getKey(), request.getCount());

            RendezvousHashingProto.GetNodesForKeyResponse.Builder builder =
                    RendezvousHashingProto.GetNodesForKeyResponse.newBuilder();

            for (Map.Entry<String, Double> entry : results) {
                builder.addNodes(RendezvousHashingProto.NodeWithWeight.newBuilder()
                        .setNodeId(entry.getKey())
                        .setWeight(entry.getValue())
                        .build());
            }

            responseObserver.onNext(builder.build());
            responseObserver.onCompleted();
        }

        @Override
        public void calculateWeight(RendezvousHashingProto.CalculateWeightRequest request,
                                    StreamObserver<RendezvousHashingProto.CalculateWeightResponse> responseObserver) {
            double capacity = 1.0;
            RendezvousHashingProto.NodeInfo nodeInfo = nodes.get(request.getNodeId());
            if (nodeInfo != null) {
                capacity = nodeInfo.getCapacityWeight();
            }

            double weight = RendezvousHashingServer.this.calculateWeight(
                    request.getKey(), request.getNodeId(), capacity);

            responseObserver.onNext(RendezvousHashingProto.CalculateWeightResponse.newBuilder()
                    .setWeight(weight)
                    .build());
            responseObserver.onCompleted();
        }
    }

    // Key-Value Service Implementation
    class KeyValueServiceImpl extends KeyValueServiceGrpc.KeyValueServiceImplBase {

        @Override
        public void put(RendezvousHashingProto.PutRequest request,
                       StreamObserver<RendezvousHashingProto.PutResponse> responseObserver) {
            localStore.put(request.getKey(), request.getValue().toByteArray());

            responseObserver.onNext(RendezvousHashingProto.PutResponse.newBuilder()
                    .setSuccess(true)
                    .addStoredOnNodes(nodeId)
                    .build());
            responseObserver.onCompleted();
        }

        @Override
        public void get(RendezvousHashingProto.GetRequest request,
                       StreamObserver<RendezvousHashingProto.GetResponse> responseObserver) {
            byte[] value = localStore.get(request.getKey());

            if (value != null) {
                responseObserver.onNext(RendezvousHashingProto.GetResponse.newBuilder()
                        .setFound(true)
                        .setValue(com.google.protobuf.ByteString.copyFrom(value))
                        .setServedByNode(nodeId)
                        .build());
            } else {
                responseObserver.onNext(RendezvousHashingProto.GetResponse.newBuilder()
                        .setFound(false)
                        .build());
            }
            responseObserver.onCompleted();
        }

        @Override
        public void delete(RendezvousHashingProto.DeleteRequest request,
                          StreamObserver<RendezvousHashingProto.DeleteResponse> responseObserver) {
            byte[] removed = localStore.remove(request.getKey());

            responseObserver.onNext(RendezvousHashingProto.DeleteResponse.newBuilder()
                    .setSuccess(true)
                    .setDeletedFromNodes(removed != null ? 1 : 0)
                    .build());
            responseObserver.onCompleted();
        }
    }

    public void start() throws IOException {
        String port = System.getenv("PORT");
        if (port == null || port.isEmpty()) {
            port = "50051";
        }

        boolean useTLS = "true".equals(System.getenv("USE_TLS"));

        ServerBuilder<?> serverBuilder;

        if (useTLS) {
            String certPath = System.getenv("TLS_CERT_PATH");
            if (certPath == null || certPath.isEmpty()) {
                certPath = "/certs/server.crt";
            }
            String keyPath = System.getenv("TLS_KEY_PATH");
            if (keyPath == null || keyPath.isEmpty()) {
                keyPath = "/certs/server.key";
            }

            serverBuilder = NettyServerBuilder.forPort(Integer.parseInt(port))
                    .sslContext(GrpcSslContexts.forServer(new File(certPath), new File(keyPath)).build());
            System.out.println("Rendezvous Hashing node " + nodeId + " starting with TLS on port " + port);
        } else {
            serverBuilder = ServerBuilder.forPort(Integer.parseInt(port));
            System.out.println("Rendezvous Hashing node " + nodeId + " starting on port " + port);
        }

        Server server = serverBuilder
                .addService(new NodeRegistryServiceImpl())
                .addService(new RendezvousServiceImpl())
                .addService(new KeyValueServiceImpl())
                .build()
                .start();

        Runtime.getRuntime().addShutdownHook(new Thread(server::shutdown));

        try {
            server.awaitTermination();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    public static void main(String[] args) throws IOException {
        String nodeId = System.getenv("NODE_ID");
        if (nodeId == null || nodeId.isEmpty()) {
            nodeId = "node-0";
        }

        new RendezvousHashingServer(nodeId).start();
    }
}
