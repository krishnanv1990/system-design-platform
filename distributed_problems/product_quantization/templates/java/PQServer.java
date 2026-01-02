package distributed_problems.product_quantization;

import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.stub.StreamObserver;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
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
 * Product Quantization (PQ) gRPC Server Template.
 *
 * <p>Product Quantization is a vector compression technique that enables efficient
 * approximate nearest neighbor search by decomposing high-dimensional vectors into
 * subvectors and quantizing each subvector independently. Key concepts:
 *
 * <ul>
 *   <li><b>Subspace Decomposition:</b> A D-dimensional vector is split into M subvectors,
 *       each of dimension D/M. This allows for independent quantization of each subspace.</li>
 *   <li><b>Codebook:</b> For each subspace, a codebook of K centroids is learned via k-means.
 *       Each subvector is then represented by its nearest centroid's index.</li>
 *   <li><b>PQ Code:</b> A vector is compressed to M bytes (assuming K=256), where each byte
 *       is the centroid index for that subspace. This achieves massive compression.</li>
 *   <li><b>Asymmetric Distance Computation (ADC):</b> During search, distances are computed
 *       between the exact query and the quantized database vectors using precomputed
 *       distance tables, enabling fast approximate distance calculation.</li>
 *   <li><b>Memory Efficiency:</b> A 128-dim float vector (512 bytes) can be compressed to
 *       just 16 bytes with M=16, K=256, achieving 32x compression.</li>
 * </ul>
 *
 * <p>PQ is often combined with IVF (IVF-PQ) where IVF provides coarse quantization
 * and PQ provides fine-grained compression within each cluster.
 *
 * <p>This template provides the structure for implementing a distributed PQ index.
 *
 * @see <a href="https://ieeexplore.ieee.org/document/5432202">Original PQ Paper</a>
 */
public class PQServer {

    private static final Logger logger = Logger.getLogger(PQServer.class.getName());

    private final String nodeId;
    private final int port;
    private final List<String> peers;
    private Server server;
    private final PQIndex index;

    /**
     * Represents a codebook for a single subspace.
     *
     * <p>Each codebook contains K centroids learned via k-means on the subvectors
     * from that subspace. The codebook enables encoding subvectors as centroid indices
     * and provides the lookup table for distance computation.
     */
    public static class Codebook {
        private final int subspaceId;
        private final int subspaceDimension;
        private final int numCentroids;
        private float[][] centroids;
        private final ReadWriteLock lock;

        /**
         * Creates a new codebook for a subspace.
         *
         * @param subspaceId The ID of the subspace (0 to M-1)
         * @param subspaceDimension The dimension of this subspace (D/M)
         * @param numCentroids Number of centroids K (typically 256 for 8-bit codes)
         */
        public Codebook(int subspaceId, int subspaceDimension, int numCentroids) {
            this.subspaceId = subspaceId;
            this.subspaceDimension = subspaceDimension;
            this.numCentroids = numCentroids;
            this.centroids = new float[numCentroids][subspaceDimension];
            this.lock = new ReentrantReadWriteLock();
        }

        public int getSubspaceId() { return subspaceId; }
        public int getSubspaceDimension() { return subspaceDimension; }
        public int getNumCentroids() { return numCentroids; }

        /**
         * Gets a centroid by index.
         *
         * @param index The centroid index (0 to K-1)
         * @return Copy of the centroid vector
         */
        public float[] getCentroid(int index) {
            lock.readLock().lock();
            try {
                if (index >= 0 && index < numCentroids) {
                    return centroids[index].clone();
                }
                return null;
            } finally {
                lock.readLock().unlock();
            }
        }

        /**
         * Sets a centroid at a specific index.
         *
         * @param index The centroid index
         * @param centroid The centroid vector
         */
        public void setCentroid(int index, float[] centroid) {
            lock.writeLock().lock();
            try {
                if (index >= 0 && index < numCentroids) {
                    centroids[index] = centroid.clone();
                }
            } finally {
                lock.writeLock().unlock();
            }
        }

        /**
         * Gets all centroids.
         *
         * @return Copy of the centroids array
         */
        public float[][] getAllCentroids() {
            lock.readLock().lock();
            try {
                float[][] copy = new float[numCentroids][];
                for (int i = 0; i < numCentroids; i++) {
                    copy[i] = centroids[i].clone();
                }
                return copy;
            } finally {
                lock.readLock().unlock();
            }
        }

        /**
         * Finds the nearest centroid to a subvector.
         *
         * @param subvector The subvector to quantize
         * @return The index of the nearest centroid
         */
        public int findNearestCentroid(float[] subvector) {
            // TODO: Implement nearest centroid finding
            // This is a helper method that can be used during encoding
            throw new UnsupportedOperationException("TODO: Implement findNearestCentroid");
        }
    }

    /**
     * Represents a PQ-encoded vector.
     *
     * <p>A PQ code consists of M bytes, where each byte represents the centroid index
     * for the corresponding subspace. This achieves significant compression compared
     * to storing the full vector.
     */
    public static class PQCode {
        private final long vectorId;
        private final byte[] codes;

        /**
         * Creates a new PQ code.
         *
         * @param vectorId The original vector's ID
         * @param codes Array of M centroid indices (one per subspace)
         */
        public PQCode(long vectorId, byte[] codes) {
            this.vectorId = vectorId;
            this.codes = codes.clone();
        }

        public long getVectorId() { return vectorId; }
        public byte[] getCodes() { return codes.clone(); }
        public int getNumSubspaces() { return codes.length; }

        /**
         * Gets the centroid index for a specific subspace.
         *
         * @param subspaceId The subspace index (0 to M-1)
         * @return The centroid index (0 to K-1), as unsigned byte
         */
        public int getCode(int subspaceId) {
            if (subspaceId >= 0 && subspaceId < codes.length) {
                return codes[subspaceId] & 0xFF; // Unsigned byte
            }
            return -1;
        }
    }

    /**
     * Represents a stored vector entry with its PQ code and optional original data.
     */
    public static class PQEntry {
        private final long id;
        private final PQCode pqCode;
        private final float[] originalVector; // Optional, for exact reranking

        /**
         * Creates a PQ entry with only the compressed code.
         *
         * @param id Vector ID
         * @param pqCode The PQ-encoded representation
         */
        public PQEntry(long id, PQCode pqCode) {
            this.id = id;
            this.pqCode = pqCode;
            this.originalVector = null;
        }

        /**
         * Creates a PQ entry with both compressed code and original vector.
         *
         * @param id Vector ID
         * @param pqCode The PQ-encoded representation
         * @param originalVector The original vector for exact reranking
         */
        public PQEntry(long id, PQCode pqCode, float[] originalVector) {
            this.id = id;
            this.pqCode = pqCode;
            this.originalVector = originalVector != null ? originalVector.clone() : null;
        }

        public long getId() { return id; }
        public PQCode getPqCode() { return pqCode; }
        public float[] getOriginalVector() {
            return originalVector != null ? originalVector.clone() : null;
        }
        public boolean hasOriginalVector() { return originalVector != null; }
    }

    /**
     * Represents a search result with approximate distance.
     */
    public static class SearchResult implements Comparable<SearchResult> {
        public final long vectorId;
        public final float approximateDistance;
        public final PQCode pqCode;

        public SearchResult(long vectorId, float approximateDistance, PQCode pqCode) {
            this.vectorId = vectorId;
            this.approximateDistance = approximateDistance;
            this.pqCode = pqCode;
        }

        @Override
        public int compareTo(SearchResult other) {
            return Float.compare(this.approximateDistance, other.approximateDistance);
        }
    }

    /**
     * The Product Quantization index structure.
     *
     * <p>Contains the codebooks for all subspaces and the encoded database vectors.
     */
    public static class PQIndex {
        /** Vector dimensionality */
        private final int dimension;

        /** Number of subspaces (M) */
        private final int numSubspaces;

        /** Dimension of each subspace (D/M) */
        private final int subspaceDimension;

        /** Number of centroids per codebook (K, typically 256) */
        private final int numCentroids;

        /** Codebooks for each subspace */
        private final Codebook[] codebooks;

        /** Stored PQ codes for all indexed vectors */
        private final ConcurrentHashMap<Long, PQEntry> entries;

        /** Whether the codebooks have been trained */
        private final AtomicBoolean isTrained;

        /** Counter for generating unique vector IDs */
        private final AtomicLong idCounter;

        /** Random number generator */
        private final Random random;

        /** Number of k-means iterations for training */
        private int nIterations = 20;

        /**
         * Creates a new PQ index.
         *
         * @param dimension Vector dimensionality (must be divisible by numSubspaces)
         * @param numSubspaces Number of subspaces M
         * @param numCentroids Number of centroids K per subspace (typically 256)
         */
        public PQIndex(int dimension, int numSubspaces, int numCentroids) {
            if (dimension % numSubspaces != 0) {
                throw new IllegalArgumentException(
                    "Dimension must be divisible by numSubspaces: " +
                    dimension + " % " + numSubspaces + " != 0");
            }

            this.dimension = dimension;
            this.numSubspaces = numSubspaces;
            this.subspaceDimension = dimension / numSubspaces;
            this.numCentroids = numCentroids;
            this.codebooks = new Codebook[numSubspaces];
            this.entries = new ConcurrentHashMap<>();
            this.isTrained = new AtomicBoolean(false);
            this.idCounter = new AtomicLong(0);
            this.random = new Random();

            // Initialize codebooks
            for (int i = 0; i < numSubspaces; i++) {
                codebooks[i] = new Codebook(i, subspaceDimension, numCentroids);
            }
        }

        public int getDimension() { return dimension; }
        public int getNumSubspaces() { return numSubspaces; }
        public int getSubspaceDimension() { return subspaceDimension; }
        public int getNumCentroids() { return numCentroids; }
        public boolean isTrained() { return isTrained.get(); }
        public Codebook[] getCodebooks() { return codebooks; }
        public ConcurrentHashMap<Long, PQEntry> getEntries() { return entries; }

        public void setTrained(boolean trained) { isTrained.set(trained); }
        public void setNIterations(int n) { this.nIterations = n; }
        public int getNIterations() { return nIterations; }

        /**
         * Gets the codebook for a specific subspace.
         *
         * @param subspaceId The subspace index (0 to M-1)
         * @return The codebook
         */
        public Codebook getCodebook(int subspaceId) {
            if (subspaceId >= 0 && subspaceId < numSubspaces) {
                return codebooks[subspaceId];
            }
            return null;
        }

        /**
         * Generates a new unique vector ID.
         *
         * @return A unique ID
         */
        public long generateId() {
            return idCounter.incrementAndGet();
        }

        /**
         * Gets the total number of indexed vectors.
         *
         * @return Vector count
         */
        public long size() {
            return entries.size();
        }

        /**
         * Extracts a subvector from a full vector.
         *
         * @param vector The full vector
         * @param subspaceId The subspace index
         * @return The subvector for that subspace
         */
        public float[] extractSubvector(float[] vector, int subspaceId) {
            float[] subvector = new float[subspaceDimension];
            int offset = subspaceId * subspaceDimension;
            System.arraycopy(vector, offset, subvector, 0, subspaceDimension);
            return subvector;
        }
    }

    /**
     * Creates a new PQ server instance.
     *
     * @param nodeId Unique identifier for this server node
     * @param port The port to listen on
     * @param peers List of peer node addresses
     * @param dimension Vector dimensionality
     * @param numSubspaces Number of subspaces M
     * @param numCentroids Number of centroids K per subspace
     */
    public PQServer(String nodeId, int port, List<String> peers,
                    int dimension, int numSubspaces, int numCentroids) {
        this.nodeId = nodeId;
        this.port = port;
        this.peers = peers != null ? new ArrayList<>(peers) : new ArrayList<>();
        this.index = new PQIndex(dimension, numSubspaces, numCentroids);
    }

    /**
     * Starts the gRPC server.
     *
     * @throws IOException if the server fails to start
     */
    public void start() throws IOException {
        server = ServerBuilder.forPort(port)
                .addService(new PQServiceImpl())
                .addService(new NodeServiceImpl())
                .build()
                .start();

        logger.info("PQ Server started, listening on port " + port);

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            logger.info("Shutting down gRPC server...");
            try {
                PQServer.this.stop();
            } catch (InterruptedException e) {
                logger.log(Level.WARNING, "Error during shutdown", e);
            }
        }));
    }

    /**
     * Stops the gRPC server.
     *
     * @throws InterruptedException if interrupted while waiting
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
    // PQ Service Implementation
    // =========================================================================

    /**
     * Implementation of the PQ gRPC service.
     */
    private class PQServiceImpl extends PQServiceGrpc.PQServiceImplBase {

        /**
         * Trains the PQ codebooks using k-means on training vectors.
         *
         * <p>Training process:
         * <ol>
         *   <li>For each subspace m (0 to M-1):</li>
         *   <li>  Extract all subvectors for that subspace</li>
         *   <li>  Run k-means to learn K centroids</li>
         *   <li>  Store centroids in the codebook</li>
         * </ol>
         *
         * @param request Training request with vectors
         * @param responseObserver Response observer
         */
        @Override
        public void train(TrainRequest request, StreamObserver<TrainResponse> responseObserver) {
            // TODO: Implement PQ training
            //
            // Steps to implement:
            // 1. Extract training vectors from request
            // 2. Validate vector dimensions match index.dimension
            // 3. Call trainSubquantizers() with training vectors
            // 4. Set index as trained
            // 5. Return success response

            throw new UnsupportedOperationException("TODO: Implement train");
        }

        /**
         * Encodes and inserts a vector into the PQ index.
         *
         * @param request Insert request with vector
         * @param responseObserver Response observer
         */
        @Override
        public void insertVector(InsertRequest request, StreamObserver<InsertResponse> responseObserver) {
            // TODO: Implement vector insertion
            //
            // Steps to implement:
            // 1. Check that index is trained
            // 2. Extract vector from request
            // 3. Generate new vector ID
            // 4. Encode vector using encodeVector()
            // 5. Store PQ entry in index
            // 6. Return success response with vector ID

            throw new UnsupportedOperationException("TODO: Implement insertVector");
        }

        /**
         * Searches for k nearest neighbors using PQ approximate distances.
         *
         * <p>Search process:
         * <ol>
         *   <li>Compute distance table from query to all centroids in each subspace</li>
         *   <li>For each stored PQ code, sum up distances using table lookups</li>
         *   <li>Return top k results by approximate distance</li>
         * </ol>
         *
         * @param request Search request with query vector and k
         * @param responseObserver Response observer
         */
        @Override
        public void searchKNN(SearchRequest request, StreamObserver<SearchResponse> responseObserver) {
            // TODO: Implement k-nearest neighbor search with PQ
            //
            // Steps to implement:
            // 1. Check that index is trained
            // 2. Extract query vector and k from request
            // 3. Compute distance tables using computeDistanceTable()
            // 4. Search all entries using searchWithPQ()
            // 5. Optionally rerank top candidates with exact distances
            // 6. Return top k results

            throw new UnsupportedOperationException("TODO: Implement searchKNN");
        }

        /**
         * Decodes a PQ code back to an approximate vector.
         *
         * @param request Decode request with PQ code
         * @param responseObserver Response observer
         */
        @Override
        public void decode(DecodeRequest request, StreamObserver<DecodeResponse> responseObserver) {
            // TODO: Implement PQ decoding
            //
            // Steps to implement:
            // 1. Extract PQ code from request
            // 2. Call decodeVector() to reconstruct approximate vector
            // 3. Return the reconstructed vector

            throw new UnsupportedOperationException("TODO: Implement decode");
        }

        /**
         * Gets statistics about the PQ index.
         *
         * @param request Stats request
         * @param responseObserver Response observer
         */
        @Override
        public void getStats(StatsRequest request, StreamObserver<StatsResponse> responseObserver) {
            // TODO: Implement stats reporting
            // Return index size, compression ratio, codebook info, etc.

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
        public void syncCodebooks(SyncCodebooksRequest request,
                                  StreamObserver<SyncCodebooksResponse> responseObserver) {
            // TODO: Implement codebook synchronization across nodes
            throw new UnsupportedOperationException("TODO: Implement syncCodebooks");
        }

        @Override
        public void forwardSearch(ForwardSearchRequest request,
                                  StreamObserver<ForwardSearchResponse> responseObserver) {
            // TODO: Implement forwarded search for distributed querying
            throw new UnsupportedOperationException("TODO: Implement forwardSearch");
        }
    }

    // =========================================================================
    // Core PQ Algorithm Methods (to be implemented)
    // =========================================================================

    /**
     * Trains the subquantizers (codebooks) for all subspaces.
     *
     * <p>For each subspace:
     * <ol>
     *   <li>Extract all subvectors from training data</li>
     *   <li>Run k-means clustering to find K centroids</li>
     *   <li>Store centroids in the codebook</li>
     * </ol>
     *
     * @param trainingVectors The training vectors
     * @return true if training succeeded
     */
    private boolean trainSubquantizers(List<float[]> trainingVectors) {
        // TODO: Implement subquantizer training
        //
        // Algorithm:
        // 1. For each subspace m = 0 to M-1:
        //    a. Extract subvectors: for each training vector, extract the m-th subvector
        //       using index.extractSubvector(vector, m)
        //    b. Run k-means on these subvectors:
        //       - Initialize K centroids (random or k-means++)
        //       - Iterate: assign subvectors to nearest centroid, update centroids
        //    c. Store the K centroids in codebooks[m]
        // 2. Return true on success
        //
        // Note: Each subspace is trained independently, so this can be parallelized

        throw new UnsupportedOperationException("TODO: Implement trainSubquantizers");
    }

    /**
     * Encodes a vector into a PQ code.
     *
     * <p>For each subspace, finds the nearest centroid and records its index.
     * The result is a compact code of M bytes.
     *
     * @param vector The vector to encode
     * @return The PQ code
     */
    private byte[] encodeVector(float[] vector) {
        // TODO: Implement vector encoding
        //
        // Algorithm:
        // 1. Create byte array of size numSubspaces
        // 2. For each subspace m = 0 to M-1:
        //    a. Extract subvector using index.extractSubvector(vector, m)
        //    b. Find nearest centroid in codebooks[m]:
        //       - For each centroid c = 0 to K-1:
        //         * Compute distance from subvector to centroid
        //       - Record index of nearest centroid
        //    c. Store centroid index as codes[m]
        // 3. Return codes
        //
        // Optimization: This can be vectorized using SIMD operations

        throw new UnsupportedOperationException("TODO: Implement encodeVector");
    }

    /**
     * Decodes a PQ code back to an approximate vector.
     *
     * <p>Reconstructs the vector by concatenating the centroids indicated
     * by each code byte. The result is an approximation of the original vector.
     *
     * @param pqCode The PQ code to decode
     * @return The reconstructed approximate vector
     */
    private float[] decodeVector(PQCode pqCode) {
        // TODO: Implement PQ decoding
        //
        // Algorithm:
        // 1. Create result array of size dimension
        // 2. For each subspace m = 0 to M-1:
        //    a. Get centroid index from pqCode.getCode(m)
        //    b. Get centroid vector from codebooks[m].getCentroid(index)
        //    c. Copy centroid to result[m*subspaceDimension : (m+1)*subspaceDimension]
        // 3. Return result

        throw new UnsupportedOperationException("TODO: Implement decodeVector");
    }

    /**
     * Computes the distance lookup table for asymmetric distance computation.
     *
     * <p>Creates a table of size M x K containing the squared distance from each
     * subvector of the query to each centroid in each subspace. This table enables
     * fast approximate distance computation using only table lookups and additions.
     *
     * @param query The query vector
     * @return Distance table of size [M][K]
     */
    private float[][] computeDistanceTable(float[] query) {
        // TODO: Implement distance table computation
        //
        // Algorithm:
        // 1. Create table of size [numSubspaces][numCentroids]
        // 2. For each subspace m = 0 to M-1:
        //    a. Extract query subvector using index.extractSubvector(query, m)
        //    b. For each centroid c = 0 to K-1:
        //       - Get centroid vector from codebooks[m].getCentroid(c)
        //       - Compute squared distance from query subvector to centroid
        //       - Store in table[m][c]
        // 3. Return table
        //
        // Note: Using squared distances avoids sqrt() and is sufficient for comparison

        throw new UnsupportedOperationException("TODO: Implement computeDistanceTable");
    }

    /**
     * Computes approximate distance from query to a PQ-encoded vector using ADC.
     *
     * <p>Uses the precomputed distance table to sum up partial distances:
     * distance = sum over m of distanceTable[m][codes[m]]
     *
     * @param distanceTable Precomputed distance table for the query
     * @param pqCode The PQ code of the database vector
     * @return Approximate squared distance
     */
    private float computeApproximateDistance(float[][] distanceTable, PQCode pqCode) {
        // TODO: Implement approximate distance computation
        //
        // Algorithm:
        // 1. Initialize distance = 0
        // 2. For each subspace m = 0 to M-1:
        //    a. Get centroid index from pqCode.getCode(m)
        //    b. Add distanceTable[m][centroidIndex] to distance
        // 3. Return distance
        //
        // This is O(M) instead of O(D) for exact distance computation!

        throw new UnsupportedOperationException("TODO: Implement computeApproximateDistance");
    }

    /**
     * Searches all indexed vectors using PQ approximate distances.
     *
     * @param distanceTable Precomputed distance table for the query
     * @param k Number of results to return
     * @return Top k results by approximate distance
     */
    private List<SearchResult> searchWithPQ(float[][] distanceTable, int k) {
        // TODO: Implement PQ search
        //
        // Algorithm:
        // 1. Create max-heap of size k for results
        // 2. For each entry in index.entries:
        //    a. Compute approximate distance using computeApproximateDistance()
        //    b. If heap has fewer than k elements or distance < heap top:
        //       - Add to heap
        //       - If heap size > k, remove maximum
        // 3. Extract results from heap in sorted order
        // 4. Return results
        //
        // Optimization: Use SIMD for batch distance computation

        throw new UnsupportedOperationException("TODO: Implement searchWithPQ");
    }

    /**
     * Computes squared Euclidean distance between two vectors.
     *
     * @param a First vector
     * @param b Second vector
     * @return Squared Euclidean distance
     */
    private float computeSquaredDistance(float[] a, float[] b) {
        // TODO: Implement squared distance computation
        //
        // float sum = 0;
        // for (int i = 0; i < a.length; i++) {
        //     float diff = a[i] - b[i];
        //     sum += diff * diff;
        // }
        // return sum;

        throw new UnsupportedOperationException("TODO: Implement computeSquaredDistance");
    }

    /**
     * Runs k-means clustering on a set of vectors.
     *
     * <p>This is a helper method used for training individual codebooks.
     *
     * @param vectors The vectors to cluster
     * @param k Number of clusters
     * @param nIterations Number of iterations
     * @return Array of k centroid vectors
     */
    private float[][] runKMeans(List<float[]> vectors, int k, int nIterations) {
        // TODO: Implement k-means clustering
        //
        // Algorithm:
        // 1. Initialize k centroids:
        //    - Option A: Random selection from vectors
        //    - Option B: K-means++ initialization
        // 2. For each iteration:
        //    a. Assign each vector to nearest centroid
        //    b. Update centroids as mean of assigned vectors
        //    c. Handle empty clusters (reinitialize randomly)
        // 3. Return final centroids

        throw new UnsupportedOperationException("TODO: Implement runKMeans");
    }

    // =========================================================================
    // Main Entry Point
    // =========================================================================

    /**
     * Main entry point for the PQ server.
     *
     * <p>Command line arguments:
     * <ul>
     *   <li>--node-id: Unique node identifier (default: node-1)</li>
     *   <li>--port: Port to listen on (default: 50051)</li>
     *   <li>--peers: Comma-separated peer addresses</li>
     *   <li>--dimension: Vector dimensionality (default: 128)</li>
     *   <li>--num-subspaces: Number of subspaces M (default: 8)</li>
     *   <li>--num-centroids: Centroids per subspace K (default: 256)</li>
     * </ul>
     *
     * @param args Command line arguments
     * @throws IOException if server fails to start
     * @throws InterruptedException if interrupted
     */
    public static void main(String[] args) throws IOException, InterruptedException {
        String nodeId = "node-1";
        int port = 50051;
        List<String> peers = new ArrayList<>();
        int dimension = 128;
        int numSubspaces = 8;
        int numCentroids = 256;

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
                case "--dimension":
                    if (i + 1 < args.length) {
                        dimension = Integer.parseInt(args[++i]);
                    }
                    break;
                case "--num-subspaces":
                    if (i + 1 < args.length) {
                        numSubspaces = Integer.parseInt(args[++i]);
                    }
                    break;
                case "--num-centroids":
                    if (i + 1 < args.length) {
                        numCentroids = Integer.parseInt(args[++i]);
                    }
                    break;
                case "--help":
                    printUsage();
                    return;
                default:
                    logger.warning("Unknown argument: " + args[i]);
            }
        }

        logger.info("Starting PQ Server with nodeId=" + nodeId + ", port=" + port +
                   ", dimension=" + dimension + ", numSubspaces=" + numSubspaces +
                   ", numCentroids=" + numCentroids);

        PQServer server = new PQServer(nodeId, port, peers, dimension, numSubspaces, numCentroids);
        server.start();
        server.blockUntilShutdown();
    }

    /**
     * Prints usage information for the server.
     */
    private static void printUsage() {
        System.out.println("PQ Server - Product Quantization for Vector Compression and Search");
        System.out.println();
        System.out.println("Usage: java PQServer [options]");
        System.out.println();
        System.out.println("Options:");
        System.out.println("  --node-id <id>           Unique node identifier (default: node-1)");
        System.out.println("  --port <port>            Port to listen on (default: 50051)");
        System.out.println("  --peers <addr,addr>      Comma-separated peer addresses");
        System.out.println("  --dimension <d>          Vector dimensionality (default: 128)");
        System.out.println("  --num-subspaces <m>      Number of subspaces M (default: 8)");
        System.out.println("  --num-centroids <k>      Centroids per subspace K (default: 256)");
        System.out.println("  --help                   Show this help message");
        System.out.println();
        System.out.println("Notes:");
        System.out.println("  - Dimension must be divisible by num-subspaces");
        System.out.println("  - Typical values: M=8-16, K=256 for 8-bit codes");
        System.out.println("  - Compression ratio = dimension * 4 / M bytes");
    }

    // =========================================================================
    // Stub classes for gRPC services (to be generated from .proto files)
    // =========================================================================

    /** Stub base class for PQ service - replace with generated class */
    public static class PQServiceGrpc {
        public static class PQServiceImplBase {
            public void train(TrainRequest req, StreamObserver<TrainResponse> obs) {}
            public void insertVector(InsertRequest req, StreamObserver<InsertResponse> obs) {}
            public void searchKNN(SearchRequest req, StreamObserver<SearchResponse> obs) {}
            public void decode(DecodeRequest req, StreamObserver<DecodeResponse> obs) {}
            public void getStats(StatsRequest req, StreamObserver<StatsResponse> obs) {}
        }
    }

    /** Stub base class for Node service - replace with generated class */
    public static class NodeServiceGrpc {
        public static class NodeServiceImplBase {
            public void healthCheck(HealthRequest req, StreamObserver<HealthResponse> obs) {}
            public void syncCodebooks(SyncCodebooksRequest req, StreamObserver<SyncCodebooksResponse> obs) {}
            public void forwardSearch(ForwardSearchRequest req, StreamObserver<ForwardSearchResponse> obs) {}
        }
    }

    // Stub request/response classes - replace with generated classes
    public static class TrainRequest { public List<List<Float>> getVectorsList() { return null; } }
    public static class TrainResponse {}
    public static class InsertRequest {
        public List<Float> getVectorList() { return null; }
        public boolean getStoreOriginal() { return false; }
    }
    public static class InsertResponse {}
    public static class SearchRequest {
        public List<Float> getVectorList() { return null; }
        public int getK() { return 0; }
        public boolean getRerank() { return false; }
        public int getRerankK() { return 0; }
    }
    public static class SearchResponse {}
    public static class DecodeRequest { public List<Integer> getCodesList() { return null; } }
    public static class DecodeResponse {}
    public static class StatsRequest {}
    public static class StatsResponse {}
    public static class HealthRequest {}
    public static class HealthResponse {}
    public static class SyncCodebooksRequest {}
    public static class SyncCodebooksResponse {}
    public static class ForwardSearchRequest {}
    public static class ForwardSearchResponse {}
}
