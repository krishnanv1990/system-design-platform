package distributed_problems.inverted_file_index;

import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.stub.StreamObserver;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.PriorityQueue;
import java.util.Random;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.ReadWriteLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Inverted File Index (IVF) gRPC Server Template.
 *
 * <p>IVF is a vector search algorithm that partitions the vector space into clusters
 * using k-means, then builds an inverted index mapping clusters to vectors. Key concepts:
 *
 * <ul>
 *   <li><b>Clustering:</b> Vectors are clustered using k-means. Each cluster has a centroid
 *       that represents the center of that region in the vector space.</li>
 *   <li><b>Inverted Lists:</b> Each cluster maintains a list of vectors assigned to it.
 *       During search, only relevant clusters are examined.</li>
 *   <li><b>nlist:</b> Number of clusters/partitions. Higher values mean more granular
 *       partitioning but require searching more clusters for good recall.</li>
 *   <li><b>nprobe:</b> Number of clusters to search at query time. Higher values
 *       improve recall but increase search time.</li>
 *   <li><b>Coarse Quantization:</b> Finding the nearest clusters is the "coarse"
 *       stage, followed by "fine" search within those clusters.</li>
 * </ul>
 *
 * <p>The algorithm trades off between search speed (fewer clusters to search) and
 * recall (more clusters means better coverage). IVF is often combined with
 * Product Quantization (IVF-PQ) for additional compression.
 *
 * <p>This template provides the structure for implementing a distributed IVF index
 * where clusters can be distributed across multiple nodes.
 *
 * @see <a href="https://hal.inria.fr/inria-00514462">Original IVF Paper</a>
 */
public class IVFServer {

    private static final Logger logger = Logger.getLogger(IVFServer.class.getName());

    private final String nodeId;
    private final int port;
    private final List<String> peers;
    private Server server;
    private final IVFIndex index;

    /**
     * Represents a centroid (cluster center) in the IVF index.
     *
     * <p>Each centroid represents the center of a Voronoi cell in the vector space.
     * Vectors are assigned to the nearest centroid during indexing.
     */
    public static class Centroid {
        private final int id;
        private float[] vector;
        private final ReadWriteLock lock;

        /**
         * Creates a new centroid.
         *
         * @param id Unique identifier for this centroid
         * @param vector The centroid's position in vector space
         */
        public Centroid(int id, float[] vector) {
            this.id = id;
            this.vector = vector.clone();
            this.lock = new ReentrantReadWriteLock();
        }

        public int getId() {
            return id;
        }

        public float[] getVector() {
            lock.readLock().lock();
            try {
                return vector.clone();
            } finally {
                lock.readLock().unlock();
            }
        }

        /**
         * Updates the centroid's position.
         *
         * @param newVector The new centroid position
         */
        public void updateVector(float[] newVector) {
            lock.writeLock().lock();
            try {
                this.vector = newVector.clone();
            } finally {
                lock.writeLock().unlock();
            }
        }
    }

    /**
     * Represents a vector entry stored in an inverted list.
     *
     * <p>Contains the vector ID, the original vector data, and optional
     * metadata for additional filtering during search.
     */
    public static class VectorEntry {
        private final long id;
        private final float[] vector;
        private final Map<String, Object> metadata;

        /**
         * Creates a new vector entry.
         *
         * @param id Unique identifier for this vector
         * @param vector The vector data
         */
        public VectorEntry(long id, float[] vector) {
            this.id = id;
            this.vector = vector.clone();
            this.metadata = new HashMap<>();
        }

        /**
         * Creates a new vector entry with metadata.
         *
         * @param id Unique identifier for this vector
         * @param vector The vector data
         * @param metadata Additional metadata for filtering
         */
        public VectorEntry(long id, float[] vector, Map<String, Object> metadata) {
            this.id = id;
            this.vector = vector.clone();
            this.metadata = metadata != null ? new HashMap<>(metadata) : new HashMap<>();
        }

        public long getId() { return id; }
        public float[] getVector() { return vector.clone(); }
        public Map<String, Object> getMetadata() { return new HashMap<>(metadata); }
    }

    /**
     * Represents an inverted list for a single cluster.
     *
     * <p>An inverted list contains all vectors assigned to a particular centroid.
     * Thread-safe for concurrent additions during indexing.
     */
    public static class InvertedList {
        private final int centroidId;
        private final List<VectorEntry> entries;
        private final ReadWriteLock lock;

        /**
         * Creates a new inverted list for a centroid.
         *
         * @param centroidId The ID of the centroid this list belongs to
         */
        public InvertedList(int centroidId) {
            this.centroidId = centroidId;
            this.entries = new ArrayList<>();
            this.lock = new ReentrantReadWriteLock();
        }

        public int getCentroidId() {
            return centroidId;
        }

        /**
         * Adds a vector to this inverted list.
         *
         * @param entry The vector entry to add
         */
        public void add(VectorEntry entry) {
            lock.writeLock().lock();
            try {
                entries.add(entry);
            } finally {
                lock.writeLock().unlock();
            }
        }

        /**
         * Gets all entries in this inverted list.
         *
         * @return A copy of the entries list
         */
        public List<VectorEntry> getEntries() {
            lock.readLock().lock();
            try {
                return new ArrayList<>(entries);
            } finally {
                lock.readLock().unlock();
            }
        }

        /**
         * Gets the number of vectors in this inverted list.
         *
         * @return The size of the list
         */
        public int size() {
            lock.readLock().lock();
            try {
                return entries.size();
            } finally {
                lock.readLock().unlock();
            }
        }

        /**
         * Clears all entries from this inverted list.
         */
        public void clear() {
            lock.writeLock().lock();
            try {
                entries.clear();
            } finally {
                lock.writeLock().unlock();
            }
        }
    }

    /**
     * Represents a search result candidate with its distance.
     */
    public static class SearchResult implements Comparable<SearchResult> {
        public final long vectorId;
        public final float distance;
        public final float[] vector;

        public SearchResult(long vectorId, float distance, float[] vector) {
            this.vectorId = vectorId;
            this.distance = distance;
            this.vector = vector;
        }

        @Override
        public int compareTo(SearchResult other) {
            return Float.compare(this.distance, other.distance);
        }
    }

    /**
     * The IVF index structure containing centroids and inverted lists.
     *
     * <p>This class manages the clustering structure and provides methods
     * for training, indexing, and searching.
     */
    public static class IVFIndex {
        /** Number of clusters (nlist parameter) */
        private final int nClusters;

        /** Dimensionality of vectors */
        private final int dimension;

        /** Array of cluster centroids */
        private Centroid[] centroids;

        /** Inverted lists, one per cluster */
        private InvertedList[] invertedLists;

        /** Whether the index has been trained */
        private final AtomicBoolean isTrained;

        /** Counter for generating unique vector IDs */
        private final AtomicLong idCounter;

        /** Random number generator for k-means initialization */
        private final Random random;

        /** Number of iterations for k-means training */
        private int nIterations = 20;

        /**
         * Creates a new IVF index.
         *
         * @param nClusters Number of clusters (nlist)
         * @param dimension Dimensionality of vectors
         */
        public IVFIndex(int nClusters, int dimension) {
            this.nClusters = nClusters;
            this.dimension = dimension;
            this.centroids = new Centroid[nClusters];
            this.invertedLists = new InvertedList[nClusters];
            this.isTrained = new AtomicBoolean(false);
            this.idCounter = new AtomicLong(0);
            this.random = new Random();

            // Initialize empty inverted lists
            for (int i = 0; i < nClusters; i++) {
                invertedLists[i] = new InvertedList(i);
            }
        }

        public int getNClusters() { return nClusters; }
        public int getDimension() { return dimension; }
        public boolean isTrained() { return isTrained.get(); }
        public Centroid[] getCentroids() { return centroids; }
        public InvertedList[] getInvertedLists() { return invertedLists; }

        public void setTrained(boolean trained) { isTrained.set(trained); }
        public void setNIterations(int iterations) { this.nIterations = iterations; }
        public int getNIterations() { return nIterations; }

        /**
         * Gets the centroid for a given cluster ID.
         *
         * @param clusterId The cluster ID
         * @return The centroid, or null if not trained
         */
        public Centroid getCentroid(int clusterId) {
            if (clusterId >= 0 && clusterId < nClusters) {
                return centroids[clusterId];
            }
            return null;
        }

        /**
         * Gets the inverted list for a given cluster ID.
         *
         * @param clusterId The cluster ID
         * @return The inverted list
         */
        public InvertedList getInvertedList(int clusterId) {
            if (clusterId >= 0 && clusterId < nClusters) {
                return invertedLists[clusterId];
            }
            return null;
        }

        /**
         * Generates a new unique vector ID.
         *
         * @return A unique vector ID
         */
        public long generateId() {
            return idCounter.incrementAndGet();
        }

        /**
         * Gets the total number of vectors in the index.
         *
         * @return Total vector count
         */
        public long getTotalVectors() {
            long total = 0;
            for (InvertedList list : invertedLists) {
                total += list.size();
            }
            return total;
        }
    }

    /**
     * Creates a new IVF server instance.
     *
     * @param nodeId Unique identifier for this server node in the cluster
     * @param port The port to listen on
     * @param peers List of peer node addresses (host:port format)
     * @param nClusters Number of clusters for the IVF index
     * @param dimension Dimensionality of vectors
     */
    public IVFServer(String nodeId, int port, List<String> peers, int nClusters, int dimension) {
        this.nodeId = nodeId;
        this.port = port;
        this.peers = peers != null ? new ArrayList<>(peers) : new ArrayList<>();
        this.index = new IVFIndex(nClusters, dimension);
    }

    /**
     * Starts the gRPC server.
     *
     * @throws IOException if the server fails to start
     */
    public void start() throws IOException {
        server = ServerBuilder.forPort(port)
                .addService(new IVFServiceImpl())
                .addService(new NodeServiceImpl())
                .build()
                .start();

        logger.info("IVF Server started, listening on port " + port);

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            logger.info("Shutting down gRPC server...");
            try {
                IVFServer.this.stop();
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
    // IVF Service Implementation
    // =========================================================================

    /**
     * Implementation of the IVF gRPC service.
     *
     * <p>This service handles the core IVF operations including training,
     * vector insertion, and k-nearest neighbor search.
     */
    private class IVFServiceImpl extends IVFServiceGrpc.IVFServiceImplBase {

        /**
         * Trains the IVF index using k-means clustering.
         *
         * <p>The training process:
         * <ol>
         *   <li>Initialize centroids (random selection or k-means++)</li>
         *   <li>Iterate until convergence or max iterations:</li>
         *   <li>  a. Assign each training vector to nearest centroid</li>
         *   <li>  b. Update centroids as mean of assigned vectors</li>
         *   <li>Mark index as trained</li>
         * </ol>
         *
         * @param request The train request containing training vectors
         * @param responseObserver Observer to send the response
         */
        @Override
        public void train(TrainRequest request, StreamObserver<TrainResponse> responseObserver) {
            // TODO: Implement k-means training
            //
            // Steps to implement:
            // 1. Extract training vectors from request
            // 2. Validate that we have enough vectors (at least nClusters)
            // 3. Call trainKMeans() with the training vectors
            // 4. Set index as trained
            // 5. Return success response with centroid information

            throw new UnsupportedOperationException("TODO: Implement train");
        }

        /**
         * Inserts a vector into the IVF index.
         *
         * <p>The insertion process:
         * <ol>
         *   <li>Find the nearest centroid to the vector</li>
         *   <li>Add the vector to that centroid's inverted list</li>
         * </ol>
         *
         * @param request The insert request containing the vector
         * @param responseObserver Observer to send the response
         */
        @Override
        public void insertVector(InsertRequest request, StreamObserver<InsertResponse> responseObserver) {
            // TODO: Implement vector insertion
            //
            // Steps to implement:
            // 1. Check that index is trained; if not, return error
            // 2. Extract vector from request
            // 3. Generate a new vector ID using index.generateId()
            // 4. Find the nearest centroid using assignToCluster()
            // 5. Add vector to that cluster's inverted list
            // 6. Return success response with assigned vector ID and cluster ID

            throw new UnsupportedOperationException("TODO: Implement insertVector");
        }

        /**
         * Searches for the k nearest neighbors to a query vector.
         *
         * <p>The search process:
         * <ol>
         *   <li>Find the nprobe nearest centroids to the query</li>
         *   <li>Search within those clusters' inverted lists</li>
         *   <li>Return the top k results</li>
         * </ol>
         *
         * @param request The search request containing query vector, k, and nprobe
         * @param responseObserver Observer to send the response
         */
        @Override
        public void searchKNN(SearchRequest request, StreamObserver<SearchResponse> responseObserver) {
            // TODO: Implement k-nearest neighbor search
            //
            // Steps to implement:
            // 1. Check that index is trained; if not, return error
            // 2. Extract query vector, k, and nprobe from request
            // 3. Find the nprobe nearest centroids to the query
            // 4. For each selected cluster, search its inverted list
            // 5. Merge results and return top k

            throw new UnsupportedOperationException("TODO: Implement searchKNN");
        }

        /**
         * Batch inserts multiple vectors into the IVF index.
         *
         * @param request The batch insert request
         * @param responseObserver Observer to send the response
         */
        @Override
        public void batchInsert(BatchInsertRequest request,
                                StreamObserver<BatchInsertResponse> responseObserver) {
            // TODO: Implement batch insertion for efficiency
            // Same as insertVector but for multiple vectors

            throw new UnsupportedOperationException("TODO: Implement batchInsert");
        }

        /**
         * Gets statistics about the index.
         *
         * @param request The stats request
         * @param responseObserver Observer to send the response
         */
        @Override
        public void getStats(StatsRequest request, StreamObserver<StatsResponse> responseObserver) {
            // TODO: Implement stats reporting
            // Return cluster sizes, total vectors, training status, etc.

            throw new UnsupportedOperationException("TODO: Implement getStats");
        }
    }

    // =========================================================================
    // Node Service Implementation (for distributed coordination)
    // =========================================================================

    /**
     * Implementation of the Node gRPC service for distributed coordination.
     */
    private class NodeServiceImpl extends NodeServiceGrpc.NodeServiceImplBase {

        @Override
        public void healthCheck(HealthRequest request, StreamObserver<HealthResponse> responseObserver) {
            // TODO: Implement health check
            throw new UnsupportedOperationException("TODO: Implement healthCheck");
        }

        @Override
        public void syncCentroids(SyncCentroidsRequest request,
                                  StreamObserver<SyncCentroidsResponse> responseObserver) {
            // TODO: Implement centroid synchronization across nodes
            throw new UnsupportedOperationException("TODO: Implement syncCentroids");
        }

        @Override
        public void forwardSearch(ForwardSearchRequest request,
                                  StreamObserver<ForwardSearchResponse> responseObserver) {
            // TODO: Implement forwarded search for distributed querying
            throw new UnsupportedOperationException("TODO: Implement forwardSearch");
        }

        @Override
        public void rebalanceClusters(RebalanceRequest request,
                                      StreamObserver<RebalanceResponse> responseObserver) {
            // TODO: Implement cluster rebalancing between nodes
            throw new UnsupportedOperationException("TODO: Implement rebalanceClusters");
        }
    }

    // =========================================================================
    // Core IVF Algorithm Methods (to be implemented)
    // =========================================================================

    /**
     * Trains k-means clustering on the provided training vectors.
     *
     * <p>The k-means algorithm:
     * <ol>
     *   <li>Initialize k centroids (using random selection or k-means++)</li>
     *   <li>Repeat until convergence or max iterations:
     *       <ul>
     *         <li>Assign each vector to the nearest centroid</li>
     *         <li>Update each centroid as the mean of assigned vectors</li>
     *       </ul>
     *   </li>
     * </ol>
     *
     * @param trainingVectors The vectors to train on
     * @return true if training succeeded, false otherwise
     */
    private boolean trainKMeans(List<float[]> trainingVectors) {
        // TODO: Implement k-means clustering algorithm
        //
        // Algorithm:
        // 1. Initialize centroids:
        //    Option A - Random: Select nClusters random vectors as initial centroids
        //    Option B - K-means++:
        //      a. Choose first centroid randomly
        //      b. For remaining centroids:
        //         - Compute D(x) = distance to nearest existing centroid
        //         - Choose next centroid with probability proportional to D(x)^2
        //
        // 2. For each iteration (up to nIterations):
        //    a. Create empty lists for each cluster
        //    b. For each training vector:
        //       - Find nearest centroid
        //       - Assign vector to that cluster
        //    c. For each cluster:
        //       - Compute new centroid as mean of assigned vectors
        //       - If no vectors assigned, reinitialize randomly
        //    d. Check for convergence (centroids stopped moving)
        //
        // 3. Create Centroid objects and store in index.centroids
        // 4. Return true on success

        throw new UnsupportedOperationException("TODO: Implement trainKMeans");
    }

    /**
     * Assigns a vector to its nearest cluster.
     *
     * <p>Computes distance from the vector to all centroids and returns
     * the ID of the nearest cluster.
     *
     * @param vector The vector to assign
     * @return The cluster ID of the nearest centroid
     */
    private int assignToCluster(float[] vector) {
        // TODO: Implement cluster assignment
        //
        // Algorithm:
        // 1. Initialize minDistance = infinity, nearestCluster = -1
        // 2. For each centroid:
        //    a. Compute distance from vector to centroid
        //    b. If distance < minDistance:
        //       - Update minDistance and nearestCluster
        // 3. Return nearestCluster

        throw new UnsupportedOperationException("TODO: Implement assignToCluster");
    }

    /**
     * Finds the nprobe nearest clusters to a query vector.
     *
     * <p>Used during search to identify which inverted lists to examine.
     *
     * @param query The query vector
     * @param nprobe Number of clusters to return
     * @return List of cluster IDs ordered by distance to query
     */
    private List<Integer> findNearestClusters(float[] query, int nprobe) {
        // TODO: Implement nearest cluster finding
        //
        // Algorithm:
        // 1. Compute distance from query to each centroid
        // 2. Create list of (clusterId, distance) pairs
        // 3. Sort by distance
        // 4. Return first nprobe cluster IDs
        //
        // Optimization: Use a max-heap of size nprobe instead of sorting all

        throw new UnsupportedOperationException("TODO: Implement findNearestClusters");
    }

    /**
     * Searches within a single cluster's inverted list.
     *
     * @param clusterId The cluster to search
     * @param query The query vector
     * @param k Maximum number of results to return
     * @return List of search results from this cluster
     */
    private List<SearchResult> searchCluster(int clusterId, float[] query, int k) {
        // TODO: Implement cluster search
        //
        // Algorithm:
        // 1. Get the inverted list for this cluster
        // 2. For each vector in the list:
        //    a. Compute distance to query
        //    b. Add to results (use max-heap for efficiency if many vectors)
        // 3. Return top k results

        throw new UnsupportedOperationException("TODO: Implement searchCluster");
    }

    /**
     * Computes the distance between two vectors.
     *
     * @param a First vector
     * @param b Second vector
     * @return The distance (L2/Euclidean by default)
     */
    private float computeDistance(float[] a, float[] b) {
        // TODO: Implement distance computation
        //
        // Euclidean distance:
        // float sum = 0;
        // for (int i = 0; i < a.length; i++) {
        //     float diff = a[i] - b[i];
        //     sum += diff * diff;
        // }
        // return (float) Math.sqrt(sum);

        throw new UnsupportedOperationException("TODO: Implement computeDistance");
    }

    /**
     * Computes the mean vector of a list of vectors.
     *
     * @param vectors The vectors to average
     * @return The mean vector, or null if empty
     */
    private float[] computeMean(List<float[]> vectors) {
        // TODO: Implement mean computation
        //
        // Algorithm:
        // 1. If vectors is empty, return null
        // 2. Create result array of same dimension
        // 3. For each dimension:
        //    a. Sum values across all vectors
        //    b. Divide by number of vectors
        // 4. Return result

        throw new UnsupportedOperationException("TODO: Implement computeMean");
    }

    // =========================================================================
    // Main Entry Point
    // =========================================================================

    /**
     * Main entry point for the IVF server.
     *
     * <p>Command line arguments:
     * <ul>
     *   <li>--node-id: Unique identifier for this node (required)</li>
     *   <li>--port: Port to listen on (default: 50051)</li>
     *   <li>--peers: Comma-separated list of peer addresses (optional)</li>
     *   <li>--nclusters: Number of clusters/partitions (default: 100)</li>
     *   <li>--dimension: Vector dimensionality (default: 128)</li>
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
        int nClusters = 100;
        int dimension = 128;

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
                case "--nclusters":
                    if (i + 1 < args.length) {
                        nClusters = Integer.parseInt(args[++i]);
                    }
                    break;
                case "--dimension":
                    if (i + 1 < args.length) {
                        dimension = Integer.parseInt(args[++i]);
                    }
                    break;
                case "--help":
                    printUsage();
                    return;
                default:
                    logger.warning("Unknown argument: " + args[i]);
            }
        }

        logger.info("Starting IVF Server with nodeId=" + nodeId + ", port=" + port +
                   ", nClusters=" + nClusters + ", dimension=" + dimension);

        IVFServer server = new IVFServer(nodeId, port, peers, nClusters, dimension);
        server.start();
        server.blockUntilShutdown();
    }

    /**
     * Prints usage information for the server.
     */
    private static void printUsage() {
        System.out.println("IVF Server - Inverted File Index for Vector Search");
        System.out.println();
        System.out.println("Usage: java IVFServer [options]");
        System.out.println();
        System.out.println("Options:");
        System.out.println("  --node-id <id>          Unique node identifier (default: node-1)");
        System.out.println("  --port <port>           Port to listen on (default: 50051)");
        System.out.println("  --peers <addr,addr>     Comma-separated peer addresses");
        System.out.println("  --nclusters <n>         Number of clusters (default: 100)");
        System.out.println("  --dimension <d>         Vector dimensionality (default: 128)");
        System.out.println("  --help                  Show this help message");
    }

    // =========================================================================
    // Stub classes for gRPC services (to be generated from .proto files)
    // =========================================================================

    /** Stub base class for IVF service - replace with generated class */
    public static class IVFServiceGrpc {
        public static class IVFServiceImplBase {
            public void train(TrainRequest req, StreamObserver<TrainResponse> obs) {}
            public void insertVector(InsertRequest req, StreamObserver<InsertResponse> obs) {}
            public void searchKNN(SearchRequest req, StreamObserver<SearchResponse> obs) {}
            public void batchInsert(BatchInsertRequest req, StreamObserver<BatchInsertResponse> obs) {}
            public void getStats(StatsRequest req, StreamObserver<StatsResponse> obs) {}
        }
    }

    /** Stub base class for Node service - replace with generated class */
    public static class NodeServiceGrpc {
        public static class NodeServiceImplBase {
            public void healthCheck(HealthRequest req, StreamObserver<HealthResponse> obs) {}
            public void syncCentroids(SyncCentroidsRequest req, StreamObserver<SyncCentroidsResponse> obs) {}
            public void forwardSearch(ForwardSearchRequest req, StreamObserver<ForwardSearchResponse> obs) {}
            public void rebalanceClusters(RebalanceRequest req, StreamObserver<RebalanceResponse> obs) {}
        }
    }

    // Stub request/response classes - replace with generated classes
    public static class TrainRequest { public List<List<Float>> getVectorsList() { return null; } }
    public static class TrainResponse {}
    public static class InsertRequest { public List<Float> getVectorList() { return null; } }
    public static class InsertResponse {}
    public static class SearchRequest {
        public List<Float> getVectorList() { return null; }
        public int getK() { return 0; }
        public int getNprobe() { return 0; }
    }
    public static class SearchResponse {}
    public static class BatchInsertRequest {}
    public static class BatchInsertResponse {}
    public static class StatsRequest {}
    public static class StatsResponse {}
    public static class HealthRequest {}
    public static class HealthResponse {}
    public static class SyncCentroidsRequest {}
    public static class SyncCentroidsResponse {}
    public static class ForwardSearchRequest {}
    public static class ForwardSearchResponse {}
    public static class RebalanceRequest {}
    public static class RebalanceResponse {}
}
