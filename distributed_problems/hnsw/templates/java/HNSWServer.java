package distributed_problems.hnsw;

import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.stub.StreamObserver;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.PriorityQueue;
import java.util.Random;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * HNSW (Hierarchical Navigable Small World) gRPC Server Template.
 *
 * <p>HNSW is an algorithm for approximate nearest neighbor search that builds a multi-layer
 * graph structure. The key concepts are:
 *
 * <ul>
 *   <li><b>Hierarchical Structure:</b> Multiple layers where higher layers have fewer nodes,
 *       allowing for fast coarse-grained search that progressively refines.</li>
 *   <li><b>Small World Graph:</b> Each layer maintains a navigable small world graph where
 *       nodes are connected to their nearest neighbors.</li>
 *   <li><b>Greedy Search:</b> Search proceeds by greedily moving to the neighbor closest
 *       to the query until a local minimum is found.</li>
 *   <li><b>M Parameter:</b> Controls the maximum number of connections per node (affects
 *       memory usage and search quality).</li>
 *   <li><b>efConstruction:</b> Controls index build quality (higher = better quality, slower build).</li>
 *   <li><b>efSearch:</b> Controls search quality at query time (higher = better recall, slower search).</li>
 * </ul>
 *
 * <p>The algorithm achieves O(log N) search complexity with high recall rates.
 *
 * <p>This template provides the structure for implementing a distributed HNSW index
 * where vectors can be partitioned across multiple nodes.
 *
 * @see <a href="https://arxiv.org/abs/1603.09320">Original HNSW Paper</a>
 */
public class HNSWServer {

    private static final Logger logger = Logger.getLogger(HNSWServer.class.getName());

    private final String nodeId;
    private final int port;
    private final List<String> peers;
    private Server server;
    private final HNSWIndex index;

    /**
     * Represents a node in the HNSW graph.
     *
     * <p>Each node contains a vector and maintains connections to neighbors at each layer.
     * The layer assignment follows an exponential distribution to ensure the hierarchical
     * property of the graph.
     */
    public static class HNSWNode {
        private final long id;
        private final float[] vector;
        private final int maxLayer;
        private final Map<Integer, Set<Long>> neighbors; // layer -> set of neighbor IDs

        /**
         * Creates a new HNSW node.
         *
         * @param id Unique identifier for this node
         * @param vector The feature vector associated with this node
         * @param maxLayer The maximum layer this node appears in (0 is the base layer)
         */
        public HNSWNode(long id, float[] vector, int maxLayer) {
            this.id = id;
            this.vector = vector.clone();
            this.maxLayer = maxLayer;
            this.neighbors = new ConcurrentHashMap<>();
            for (int i = 0; i <= maxLayer; i++) {
                this.neighbors.put(i, ConcurrentHashMap.newKeySet());
            }
        }

        public long getId() {
            return id;
        }

        public float[] getVector() {
            return vector.clone();
        }

        public int getMaxLayer() {
            return maxLayer;
        }

        /**
         * Gets the neighbors of this node at a specific layer.
         *
         * @param layer The layer to get neighbors for
         * @return Set of neighbor node IDs, or empty set if layer doesn't exist
         */
        public Set<Long> getNeighbors(int layer) {
            return neighbors.getOrDefault(layer, Collections.emptySet());
        }

        /**
         * Adds a neighbor connection at a specific layer.
         *
         * @param layer The layer to add the connection
         * @param neighborId The ID of the neighbor node
         */
        public void addNeighbor(int layer, long neighborId) {
            Set<Long> layerNeighbors = neighbors.get(layer);
            if (layerNeighbors != null) {
                layerNeighbors.add(neighborId);
            }
        }

        /**
         * Removes a neighbor connection at a specific layer.
         *
         * @param layer The layer to remove the connection from
         * @param neighborId The ID of the neighbor node to remove
         */
        public void removeNeighbor(int layer, long neighborId) {
            Set<Long> layerNeighbors = neighbors.get(layer);
            if (layerNeighbors != null) {
                layerNeighbors.remove(neighborId);
            }
        }
    }

    /**
     * Represents a candidate node during search with its distance to the query.
     */
    public static class Candidate implements Comparable<Candidate> {
        public final long nodeId;
        public final float distance;

        public Candidate(long nodeId, float distance) {
            this.nodeId = nodeId;
            this.distance = distance;
        }

        @Override
        public int compareTo(Candidate other) {
            return Float.compare(this.distance, other.distance);
        }
    }

    /**
     * The HNSW index structure containing all nodes and graph layers.
     *
     * <p>This class manages the hierarchical graph structure and provides thread-safe
     * access to nodes across all layers.
     */
    public static class HNSWIndex {
        /** Maximum number of connections per node at each layer (M parameter) */
        private final int M;

        /** Maximum connections for layer 0 (typically 2*M) */
        private final int M0;

        /** Size of dynamic candidate list during construction */
        private final int efConstruction;

        /** Normalization factor for layer selection (1/ln(M)) */
        private final double mL;

        /** All nodes in the index, keyed by ID */
        private final ConcurrentHashMap<Long, HNSWNode> nodes;

        /** Current entry point node ID (node at highest layer) */
        private volatile Long entryPointId;

        /** Current maximum layer in the index */
        private volatile int maxLayer;

        /** Counter for generating unique node IDs */
        private final AtomicLong idCounter;

        /** Random number generator for layer selection */
        private final Random random;

        /**
         * Creates a new HNSW index with specified parameters.
         *
         * @param M Maximum number of connections per node
         * @param efConstruction Size of dynamic candidate list during construction
         */
        public HNSWIndex(int M, int efConstruction) {
            this.M = M;
            this.M0 = 2 * M;
            this.efConstruction = efConstruction;
            this.mL = 1.0 / Math.log(M);
            this.nodes = new ConcurrentHashMap<>();
            this.entryPointId = null;
            this.maxLayer = -1;
            this.idCounter = new AtomicLong(0);
            this.random = new Random();
        }

        public int getM() { return M; }
        public int getM0() { return M0; }
        public int getEfConstruction() { return efConstruction; }
        public ConcurrentHashMap<Long, HNSWNode> getNodes() { return nodes; }
        public Long getEntryPointId() { return entryPointId; }
        public int getMaxLayer() { return maxLayer; }

        public void setEntryPointId(Long id) { this.entryPointId = id; }
        public void setMaxLayer(int layer) { this.maxLayer = layer; }

        /**
         * Generates a random layer for a new node using exponential distribution.
         *
         * <p>Higher layers are exponentially less likely to be selected, ensuring
         * the hierarchical structure where each layer has roughly M times fewer
         * nodes than the layer below.
         *
         * @return The layer number (0 is minimum)
         */
        public int getRandomLayer() {
            return (int) (-Math.log(random.nextDouble()) * mL);
        }

        /**
         * Gets a node by ID.
         *
         * @param id The node ID
         * @return The node, or null if not found
         */
        public HNSWNode getNode(long id) {
            return nodes.get(id);
        }

        /**
         * Adds a node to the index.
         *
         * @param node The node to add
         */
        public void addNode(HNSWNode node) {
            nodes.put(node.getId(), node);
        }

        /**
         * Generates a new unique node ID.
         *
         * @return A unique node ID
         */
        public long generateId() {
            return idCounter.incrementAndGet();
        }
    }

    /**
     * Creates a new HNSW server instance.
     *
     * @param nodeId Unique identifier for this server node in the cluster
     * @param port The port to listen on
     * @param peers List of peer node addresses (host:port format)
     * @param M Maximum connections per node
     * @param efConstruction Construction-time candidate list size
     */
    public HNSWServer(String nodeId, int port, List<String> peers, int M, int efConstruction) {
        this.nodeId = nodeId;
        this.port = port;
        this.peers = peers != null ? new ArrayList<>(peers) : new ArrayList<>();
        this.index = new HNSWIndex(M, efConstruction);
    }

    /**
     * Starts the gRPC server.
     *
     * @throws IOException if the server fails to start
     */
    public void start() throws IOException {
        server = ServerBuilder.forPort(port)
                .addService(new HNSWServiceImpl())
                .addService(new NodeServiceImpl())
                .build()
                .start();

        logger.info("HNSW Server started, listening on port " + port);

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            logger.info("Shutting down gRPC server...");
            try {
                HNSWServer.this.stop();
            } catch (InterruptedException e) {
                logger.log(Level.WARNING, "Error during shutdown", e);
            }
        }));
    }

    /**
     * Stops the gRPC server.
     *
     * @throws InterruptedException if interrupted while waiting for shutdown
     */
    public void stop() throws InterruptedException {
        if (server != null) {
            server.shutdown().awaitTermination(30, TimeUnit.SECONDS);
        }
    }

    /**
     * Blocks until the server is terminated.
     *
     * @throws InterruptedException if interrupted while waiting
     */
    public void blockUntilShutdown() throws InterruptedException {
        if (server != null) {
            server.awaitTermination();
        }
    }

    // =========================================================================
    // HNSW Service Implementation
    // =========================================================================

    /**
     * Implementation of the HNSW gRPC service.
     *
     * <p>This service handles the core HNSW operations including vector insertion
     * and k-nearest neighbor search.
     */
    private class HNSWServiceImpl extends HNSWServiceGrpc.HNSWServiceImplBase {

        /**
         * Inserts a vector into the HNSW index.
         *
         * <p>The insertion algorithm:
         * <ol>
         *   <li>Assign a random layer to the new node</li>
         *   <li>If this is the first node, make it the entry point</li>
         *   <li>Search from entry point down to the node's layer, finding the closest node</li>
         *   <li>For each layer from the node's layer to 0, find and connect to neighbors</li>
         *   <li>If node's layer is higher than current max, update entry point</li>
         * </ol>
         *
         * @param request The insert request containing the vector
         * @param responseObserver Observer to send the response
         */
        @Override
        public void insertVector(InsertRequest request, StreamObserver<InsertResponse> responseObserver) {
            // TODO: Implement vector insertion into HNSW index
            //
            // Steps to implement:
            // 1. Extract vector from request: request.getVectorList()
            // 2. Generate a new node ID using index.generateId()
            // 3. Calculate the layer for this node using index.getRandomLayer()
            // 4. Create a new HNSWNode with the ID, vector, and layer
            // 5. If this is the first node (entryPointId is null):
            //    - Set this node as the entry point
            //    - Set maxLayer to this node's layer
            //    - Add node to index and return
            // 6. Otherwise, perform the insertion:
            //    a. Start from the entry point
            //    b. Greedily search from top layer to (node's layer + 1)
            //    c. For each layer from min(node's layer, maxLayer) to 0:
            //       - Find efConstruction nearest neighbors using searchLayer()
            //       - Select M (or M0 for layer 0) neighbors using selectNeighbors()
            //       - Connect the new node to selected neighbors (bidirectional)
            //       - Shrink neighbor lists if they exceed M
            // 7. If node's layer > maxLayer, update entry point and maxLayer
            // 8. Add node to index
            // 9. Return success response with the assigned node ID

            throw new UnsupportedOperationException("TODO: Implement insertVector");
        }

        /**
         * Searches for the k nearest neighbors to a query vector.
         *
         * <p>The search algorithm:
         * <ol>
         *   <li>Start from the entry point at the highest layer</li>
         *   <li>Greedily descend through layers, finding closest nodes</li>
         *   <li>At layer 0, perform a more thorough search with efSearch candidates</li>
         *   <li>Return the top k results</li>
         * </ol>
         *
         * @param request The search request containing query vector and k
         * @param responseObserver Observer to send the response
         */
        @Override
        public void searchKNN(SearchRequest request, StreamObserver<SearchResponse> responseObserver) {
            // TODO: Implement k-nearest neighbor search
            //
            // Steps to implement:
            // 1. Extract query vector and k from request
            // 2. Extract efSearch parameter (defaults to k if not provided)
            // 3. If index is empty, return empty result
            // 4. Start from entry point at maxLayer
            // 5. For each layer from maxLayer to 1:
            //    - Use searchLayer with ef=1 to greedily find closest node
            //    - Use that node as entry for next layer
            // 6. At layer 0, use searchLayer with ef=efSearch
            // 7. Take top k results from the candidates
            // 8. Build and return SearchResponse with results

            throw new UnsupportedOperationException("TODO: Implement searchKNN");
        }

        /**
         * Deletes a vector from the HNSW index.
         *
         * @param request The delete request containing the vector ID
         * @param responseObserver Observer to send the response
         */
        @Override
        public void deleteVector(DeleteRequest request, StreamObserver<DeleteResponse> responseObserver) {
            // TODO: Implement vector deletion (optional - can be deferred)
            // Note: HNSW deletion is complex and often handled via tombstones
            // or periodic rebuilding of the index

            throw new UnsupportedOperationException("TODO: Implement deleteVector");
        }
    }

    // =========================================================================
    // Node Service Implementation (for distributed coordination)
    // =========================================================================

    /**
     * Implementation of the Node gRPC service for distributed coordination.
     *
     * <p>This service handles inter-node communication in a distributed HNSW setup,
     * including health checks, data synchronization, and cluster management.
     */
    private class NodeServiceImpl extends NodeServiceGrpc.NodeServiceImplBase {

        /**
         * Health check endpoint.
         *
         * @param request The health check request
         * @param responseObserver Observer to send the response
         */
        @Override
        public void healthCheck(HealthRequest request, StreamObserver<HealthResponse> responseObserver) {
            // TODO: Implement health check
            // Return node status, index size, memory usage, etc.

            throw new UnsupportedOperationException("TODO: Implement healthCheck");
        }

        /**
         * Synchronizes index data with peer nodes.
         *
         * @param request The sync request
         * @param responseObserver Observer to send the response
         */
        @Override
        public void syncData(SyncRequest request, StreamObserver<SyncResponse> responseObserver) {
            // TODO: Implement data synchronization
            // Handle receiving nodes/edges from peer nodes during rebalancing

            throw new UnsupportedOperationException("TODO: Implement syncData");
        }

        /**
         * Forwards a search request to this node for partial results.
         *
         * @param request The forward request
         * @param responseObserver Observer to send the response
         */
        @Override
        public void forwardSearch(ForwardSearchRequest request,
                                  StreamObserver<ForwardSearchResponse> responseObserver) {
            // TODO: Implement forwarded search handling
            // Search local index and return partial results

            throw new UnsupportedOperationException("TODO: Implement forwardSearch");
        }
    }

    // =========================================================================
    // Core HNSW Algorithm Methods (to be implemented)
    // =========================================================================

    /**
     * Searches a single layer of the HNSW graph to find nearest neighbors.
     *
     * <p>This implements the greedy search with a dynamic candidate list.
     * The algorithm maintains two sets:
     * <ul>
     *   <li>Candidates: nodes to explore, ordered by distance (min-heap)</li>
     *   <li>Results: best nodes found so far, ordered by distance (max-heap for pruning)</li>
     * </ul>
     *
     * @param query The query vector
     * @param entryPoints Initial entry points for the search
     * @param ef Size of the dynamic candidate list
     * @param layer The layer to search in
     * @return List of candidates ordered by distance (closest first)
     */
    private List<Candidate> searchLayer(float[] query, List<Long> entryPoints, int ef, int layer) {
        // TODO: Implement layer search algorithm
        //
        // Algorithm:
        // 1. Initialize visited set with entry points
        // 2. Initialize candidates (min-heap) with entry points and their distances
        // 3. Initialize results (max-heap of size ef) with entry points
        // 4. While candidates is not empty:
        //    a. Pop closest candidate c
        //    b. Get furthest element f in results
        //    c. If distance(c) > distance(f), stop (no improvement possible)
        //    d. For each neighbor of c at this layer:
        //       - If not visited:
        //         * Mark as visited
        //         * Calculate distance to query
        //         * If distance < furthest in results OR results.size < ef:
        //           - Add to candidates
        //           - Add to results
        //           - If results.size > ef, remove furthest
        // 5. Return results as sorted list

        throw new UnsupportedOperationException("TODO: Implement searchLayer");
    }

    /**
     * Selects the best neighbors from candidates for a node.
     *
     * <p>This can use simple selection (take closest M) or heuristic selection
     * that considers the diversity of the neighbor set to improve graph connectivity.
     *
     * @param node The node to select neighbors for
     * @param candidates The candidate neighbors sorted by distance
     * @param M Maximum number of neighbors to select
     * @param layer The layer for which neighbors are being selected
     * @param extendCandidates Whether to extend candidates by including their neighbors
     * @param keepPrunedConnections Whether to keep some pruned connections
     * @return List of selected neighbor IDs
     */
    private List<Long> selectNeighbors(HNSWNode node, List<Candidate> candidates,
                                       int M, int layer, boolean extendCandidates,
                                       boolean keepPrunedConnections) {
        // TODO: Implement neighbor selection algorithm
        //
        // Simple approach: Take M closest candidates
        //
        // Heuristic approach (recommended):
        // 1. If extendCandidates is true:
        //    - For each candidate, add their neighbors to the candidate set
        //    - Remove duplicates and the node itself
        // 2. Create result list R (empty)
        // 3. Create working queue W from candidates (min-heap by distance)
        // 4. While W is not empty and R.size < M:
        //    a. Pop closest element e from W
        //    b. If e is closer to node than to any element in R:
        //       - Add e to R
        //    c. Else if keepPrunedConnections:
        //       - Add e to a discarded list
        // 5. If keepPrunedConnections and R.size < M:
        //    - Add elements from discarded list to fill R up to M
        // 6. Return R

        throw new UnsupportedOperationException("TODO: Implement selectNeighbors");
    }

    /**
     * Computes the distance between two vectors.
     *
     * <p>Common distance metrics:
     * <ul>
     *   <li>Euclidean (L2): sqrt(sum((a[i] - b[i])^2))</li>
     *   <li>Inner Product: -sum(a[i] * b[i]) (negated for min-heap compatibility)</li>
     *   <li>Cosine: 1 - (a . b) / (||a|| * ||b||)</li>
     * </ul>
     *
     * @param a First vector
     * @param b Second vector
     * @return The distance between the vectors
     */
    private float computeDistance(float[] a, float[] b) {
        // TODO: Implement distance computation
        // Default implementation uses Euclidean distance
        //
        // float sum = 0;
        // for (int i = 0; i < a.length; i++) {
        //     float diff = a[i] - b[i];
        //     sum += diff * diff;
        // }
        // return (float) Math.sqrt(sum);

        throw new UnsupportedOperationException("TODO: Implement computeDistance");
    }

    /**
     * Shrinks a node's neighbor list to at most M connections.
     *
     * <p>Called when a node accumulates too many neighbors after insertions.
     * Uses the same neighbor selection heuristic as during insertion.
     *
     * @param node The node whose neighbors to shrink
     * @param layer The layer to shrink neighbors for
     * @param M Maximum number of neighbors to keep
     */
    private void shrinkNeighbors(HNSWNode node, int layer, int M) {
        // TODO: Implement neighbor shrinking
        //
        // 1. Get current neighbors at this layer
        // 2. If count <= M, return (nothing to do)
        // 3. Create candidates from current neighbors with their distances
        // 4. Use selectNeighbors to pick the best M neighbors
        // 5. Update node's neighbor set for this layer

        throw new UnsupportedOperationException("TODO: Implement shrinkNeighbors");
    }

    // =========================================================================
    // Main Entry Point
    // =========================================================================

    /**
     * Main entry point for the HNSW server.
     *
     * <p>Command line arguments:
     * <ul>
     *   <li>--node-id: Unique identifier for this node (required)</li>
     *   <li>--port: Port to listen on (default: 50051)</li>
     *   <li>--peers: Comma-separated list of peer addresses (optional)</li>
     *   <li>--M: Maximum connections per node (default: 16)</li>
     *   <li>--ef-construction: Construction candidate list size (default: 200)</li>
     * </ul>
     *
     * @param args Command line arguments
     * @throws IOException if server fails to start
     * @throws InterruptedException if interrupted while running
     */
    public static void main(String[] args) throws IOException, InterruptedException {
        String nodeId = "node-1";
        int port = 50051;
        List<String> peers = new ArrayList<>();
        int M = 16;
        int efConstruction = 200;

        // Parse command line arguments
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--node-id":
                    if (i + 1 < args.length) {
                        nodeId = args[++i];
                    }
                    break;
                case "--port":
                    if (i + 1 < args.length) {
                        port = Integer.parseInt(args[++i]);
                    }
                    break;
                case "--peers":
                    if (i + 1 < args.length) {
                        String[] peerList = args[++i].split(",");
                        for (String peer : peerList) {
                            if (!peer.trim().isEmpty()) {
                                peers.add(peer.trim());
                            }
                        }
                    }
                    break;
                case "--M":
                    if (i + 1 < args.length) {
                        M = Integer.parseInt(args[++i]);
                    }
                    break;
                case "--ef-construction":
                    if (i + 1 < args.length) {
                        efConstruction = Integer.parseInt(args[++i]);
                    }
                    break;
                case "--help":
                    printUsage();
                    return;
                default:
                    logger.warning("Unknown argument: " + args[i]);
            }
        }

        logger.info("Starting HNSW Server with nodeId=" + nodeId + ", port=" + port +
                   ", M=" + M + ", efConstruction=" + efConstruction);

        HNSWServer server = new HNSWServer(nodeId, port, peers, M, efConstruction);
        server.start();
        server.blockUntilShutdown();
    }

    /**
     * Prints usage information for the server.
     */
    private static void printUsage() {
        System.out.println("HNSW Server - Hierarchical Navigable Small World Index");
        System.out.println();
        System.out.println("Usage: java HNSWServer [options]");
        System.out.println();
        System.out.println("Options:");
        System.out.println("  --node-id <id>          Unique node identifier (default: node-1)");
        System.out.println("  --port <port>           Port to listen on (default: 50051)");
        System.out.println("  --peers <addr,addr>     Comma-separated peer addresses");
        System.out.println("  --M <value>             Max connections per node (default: 16)");
        System.out.println("  --ef-construction <val> Construction candidate size (default: 200)");
        System.out.println("  --help                  Show this help message");
    }

    // =========================================================================
    // Stub classes for gRPC services (to be generated from .proto files)
    // =========================================================================

    // These are placeholder classes. In a real implementation, these would be
    // generated from Protocol Buffer definitions.

    /** Stub base class for HNSW service - replace with generated class */
    public static class HNSWServiceGrpc {
        public static class HNSWServiceImplBase {
            public void insertVector(InsertRequest request, StreamObserver<InsertResponse> observer) {}
            public void searchKNN(SearchRequest request, StreamObserver<SearchResponse> observer) {}
            public void deleteVector(DeleteRequest request, StreamObserver<DeleteResponse> observer) {}
        }
    }

    /** Stub base class for Node service - replace with generated class */
    public static class NodeServiceGrpc {
        public static class NodeServiceImplBase {
            public void healthCheck(HealthRequest request, StreamObserver<HealthResponse> observer) {}
            public void syncData(SyncRequest request, StreamObserver<SyncResponse> observer) {}
            public void forwardSearch(ForwardSearchRequest request, StreamObserver<ForwardSearchResponse> observer) {}
        }
    }

    // Stub request/response classes - replace with generated classes
    public static class InsertRequest { public List<Float> getVectorList() { return null; } }
    public static class InsertResponse {}
    public static class SearchRequest {
        public List<Float> getVectorList() { return null; }
        public int getK() { return 0; }
        public int getEfSearch() { return 0; }
    }
    public static class SearchResponse {}
    public static class DeleteRequest { public long getVectorId() { return 0; } }
    public static class DeleteResponse {}
    public static class HealthRequest {}
    public static class HealthResponse {}
    public static class SyncRequest {}
    public static class SyncResponse {}
    public static class ForwardSearchRequest {}
    public static class ForwardSearchResponse {}
}
