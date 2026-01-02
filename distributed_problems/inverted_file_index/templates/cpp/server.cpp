/**
 * Inverted File Index (IVF) Vector Search Server
 *
 * This template implements a gRPC server for distributed IVF index operations.
 *
 * ALGORITHM OVERVIEW:
 * ===================
 * IVF is a partition-based approximate nearest neighbor search algorithm that:
 * 1. Partitions the vector space into K clusters using K-means
 * 2. Assigns each vector to its nearest cluster centroid
 * 3. During search, only examines vectors in the nprobe nearest clusters
 *
 * Key operations:
 * 1. TRAIN: Run K-means to find cluster centroids
 * 2. ADD: Assign vectors to their nearest clusters
 * 3. SEARCH: Find nearest clusters, then search within them
 *
 * DISTRIBUTED CONSIDERATIONS:
 * ===========================
 * - Each node can hold a subset of clusters (sharding by cluster)
 * - Or each node can hold all clusters for a subset of vectors
 * - Cross-shard searches require coordination via NodeService
 *
 * TODO: Implement the core algorithm methods marked with TODO comments
 */

#include <grpcpp/grpcpp.h>
#include <grpcpp/server.h>
#include <grpcpp/server_builder.h>
#include <grpcpp/server_context.h>

// TODO: Include generated proto headers
// #include "ivf.grpc.pb.h"
// #include "node.grpc.pb.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <functional>
#include <iostream>
#include <limits>
#include <memory>
#include <mutex>
#include <numeric>
#include <optional>
#include <queue>
#include <random>
#include <shared_mutex>
#include <sstream>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

// ============================================================================
// Configuration Constants
// ============================================================================

namespace ivf_config {
    // Number of clusters (centroids)
    constexpr size_t N_CLUSTERS = 256;

    // Number of clusters to probe during search
    constexpr size_t N_PROBE = 8;

    // Maximum K-means iterations
    constexpr size_t MAX_KMEANS_ITERATIONS = 100;

    // K-means convergence threshold
    constexpr float KMEANS_TOLERANCE = 1e-4f;

    // Default vector dimension
    constexpr size_t DEFAULT_DIMENSION = 128;

    // Minimum vectors for training
    constexpr size_t MIN_TRAINING_VECTORS = 1000;
}

// ============================================================================
// Forward Declarations
// ============================================================================

class Centroid;
class InvertedList;
class IVFIndex;
class IVFServiceImpl;
class NodeServiceImpl;

// ============================================================================
// Data Structures
// ============================================================================

/**
 * Represents a single centroid in the IVF index
 *
 * Each centroid stores:
 * - A unique identifier (cluster ID)
 * - The centroid vector (mean of cluster)
 * - Statistics about the cluster
 */
class Centroid {
public:
    using ClusterId = uint32_t;
    using Vector = std::vector<float>;

    Centroid(ClusterId id, Vector vector)
        : id_(id)
        , vector_(std::move(vector))
        , count_(0) {
    }

    Centroid(ClusterId id, size_t dimension)
        : id_(id)
        , vector_(dimension, 0.0f)
        , count_(0) {
    }

    ~Centroid() = default;

    // Getters
    ClusterId getId() const { return id_; }
    const Vector& getVector() const { return vector_; }
    size_t getCount() const { return count_.load(); }

    // Setters
    void setVector(Vector vector) {
        std::unique_lock<std::mutex> lock(mutex_);
        vector_ = std::move(vector);
    }

    void incrementCount() {
        count_.fetch_add(1);
    }

    void setCount(size_t count) {
        count_.store(count);
    }

    /**
     * Reset centroid for K-means iteration
     */
    void reset() {
        std::unique_lock<std::mutex> lock(mutex_);
        std::fill(vector_.begin(), vector_.end(), 0.0f);
        count_.store(0);
    }

    /**
     * Add a vector to the running sum (for K-means)
     */
    void addToSum(const Vector& vec) {
        std::unique_lock<std::mutex> lock(mutex_);
        for (size_t i = 0; i < vector_.size() && i < vec.size(); ++i) {
            vector_[i] += vec[i];
        }
        count_.fetch_add(1);
    }

    /**
     * Finalize centroid by dividing by count (for K-means)
     */
    void finalize() {
        std::unique_lock<std::mutex> lock(mutex_);
        size_t n = count_.load();
        if (n > 0) {
            for (float& v : vector_) {
                v /= static_cast<float>(n);
            }
        }
    }

private:
    ClusterId id_;
    Vector vector_;
    std::atomic<size_t> count_;
    std::mutex mutex_;
};

/**
 * An inverted list holds all vectors assigned to a particular cluster
 */
class InvertedList {
public:
    using VectorId = uint64_t;
    using Vector = std::vector<float>;

    struct Entry {
        VectorId id;
        Vector vector;
    };

    InvertedList() = default;
    ~InvertedList() = default;

    /**
     * Add a vector to this inverted list
     */
    void add(VectorId id, Vector vector) {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        entries_.push_back({id, std::move(vector)});
    }

    /**
     * Get all entries (for search)
     */
    std::vector<Entry> getEntries() const {
        std::shared_lock<std::shared_mutex> lock(mutex_);
        return entries_;
    }

    /**
     * Get the number of entries
     */
    size_t size() const {
        std::shared_lock<std::shared_mutex> lock(mutex_);
        return entries_.size();
    }

    /**
     * Clear all entries
     */
    void clear() {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        entries_.clear();
    }

private:
    std::vector<Entry> entries_;
    mutable std::shared_mutex mutex_;
};

/**
 * Distance result for search operations
 */
struct DistanceResult {
    uint64_t vector_id;
    float distance;

    bool operator<(const DistanceResult& other) const {
        return distance < other.distance;
    }

    bool operator>(const DistanceResult& other) const {
        return distance > other.distance;
    }
};

/**
 * Cluster distance result
 */
struct ClusterDistance {
    Centroid::ClusterId cluster_id;
    float distance;

    bool operator<(const ClusterDistance& other) const {
        return distance < other.distance;
    }
};

/**
 * The main IVF index structure
 *
 * Maintains:
 * - K centroids (cluster centers)
 * - K inverted lists (one per cluster)
 * - Training state
 */
class IVFIndex {
public:
    using VectorId = uint64_t;
    using Vector = std::vector<float>;
    using ClusterId = Centroid::ClusterId;

    IVFIndex(size_t dimension, size_t n_clusters = ivf_config::N_CLUSTERS)
        : dimension_(dimension)
        , n_clusters_(n_clusters)
        , n_probe_(ivf_config::N_PROBE)
        , is_trained_(false)
        , rng_(std::random_device{}()) {

        // Initialize empty centroids and inverted lists
        centroids_.reserve(n_clusters_);
        inverted_lists_.resize(n_clusters_);
    }

    ~IVFIndex() = default;

    // Getters
    size_t dimension() const { return dimension_; }
    size_t numClusters() const { return n_clusters_; }
    size_t numProbe() const { return n_probe_; }
    bool isTrained() const { return is_trained_.load(); }

    void setNumProbe(size_t n_probe) {
        n_probe_ = std::min(n_probe, n_clusters_);
    }

    /**
     * Get total number of vectors in the index
     */
    size_t size() const {
        size_t total = 0;
        for (const auto& list : inverted_lists_) {
            total += list.size();
        }
        return total;
    }

    /**
     * Compute L2 distance between two vectors
     */
    float computeDistance(const Vector& a, const Vector& b) const {
        if (a.size() != b.size()) {
            return std::numeric_limits<float>::max();
        }

        float dist = 0.0f;
        for (size_t i = 0; i < a.size(); ++i) {
            float diff = a[i] - b[i];
            dist += diff * diff;
        }
        return std::sqrt(dist);
    }

    // ========================================================================
    // Core Algorithm Methods - TO BE IMPLEMENTED
    // ========================================================================

    /**
     * Train the IVF index using K-means clustering
     *
     * Algorithm:
     * 1. Initialize K centroids (random selection or K-means++)
     * 2. Repeat until convergence:
     *    a. Assign each training vector to nearest centroid
     *    b. Update centroids to be mean of assigned vectors
     *    c. Check for convergence (centroid movement < threshold)
     *
     * @param training_vectors Vectors to use for training
     * @return true if training was successful
     */
    bool trainKMeans(const std::vector<Vector>& training_vectors) {
        // TODO: Implement K-means clustering for centroid initialization
        //
        // Step 1: Validate input
        // if (training_vectors.size() < n_clusters_) {
        //     return false;  // Not enough vectors
        // }
        //
        // Step 2: Initialize centroids (e.g., random selection)
        // initializeCentroidsRandom(training_vectors);
        // // or: initializeCentroidsPlusPlus(training_vectors);
        //
        // Step 3: K-means iterations
        // for (size_t iter = 0; iter < ivf_config::MAX_KMEANS_ITERATIONS; ++iter) {
        //     // Reset centroid accumulators
        //     for (auto& centroid : centroids_) {
        //         centroid->reset();
        //     }
        //
        //     // Assign vectors to clusters and accumulate
        //     for (const auto& vec : training_vectors) {
        //         ClusterId nearest = findNearestCentroid(vec);
        //         centroids_[nearest]->addToSum(vec);
        //     }
        //
        //     // Update centroids (compute means)
        //     float max_movement = 0.0f;
        //     for (auto& centroid : centroids_) {
        //         Vector old_center = centroid->getVector();
        //         centroid->finalize();
        //         float movement = computeDistance(old_center, centroid->getVector());
        //         max_movement = std::max(max_movement, movement);
        //     }
        //
        //     // Check convergence
        //     if (max_movement < ivf_config::KMEANS_TOLERANCE) {
        //         break;
        //     }
        // }
        //
        // is_trained_ = true;
        // return true;

        // Stub implementation: Random centroid initialization without proper K-means
        std::unique_lock<std::shared_mutex> lock(index_mutex_);

        if (training_vectors.size() < n_clusters_) {
            std::cerr << "Not enough training vectors" << std::endl;
            return false;
        }

        // Shuffle and pick random vectors as centroids
        std::vector<size_t> indices(training_vectors.size());
        std::iota(indices.begin(), indices.end(), 0);
        std::shuffle(indices.begin(), indices.end(), rng_);

        centroids_.clear();
        for (size_t i = 0; i < n_clusters_; ++i) {
            centroids_.push_back(std::make_shared<Centroid>(
                static_cast<ClusterId>(i),
                training_vectors[indices[i]]
            ));
        }

        is_trained_ = true;
        return true;
    }

    /**
     * Initialize centroids using K-means++ algorithm
     *
     * K-means++ provides better initial centroids by:
     * 1. Choosing first centroid randomly
     * 2. For each subsequent centroid:
     *    - Compute distance from each point to nearest existing centroid
     *    - Choose new centroid with probability proportional to distance squared
     *
     * @param training_vectors Vectors to use for initialization
     */
    void initializeCentroidsPlusPlus(const std::vector<Vector>& training_vectors) {
        // TODO: Implement K-means++ initialization
        //
        // centroids_.clear();
        //
        // // Choose first centroid randomly
        // std::uniform_int_distribution<size_t> dist(0, training_vectors.size() - 1);
        // size_t first_idx = dist(rng_);
        // centroids_.push_back(std::make_shared<Centroid>(0, training_vectors[first_idx]));
        //
        // // Choose remaining centroids
        // std::vector<float> min_distances(training_vectors.size(),
        //                                  std::numeric_limits<float>::max());
        //
        // for (size_t k = 1; k < n_clusters_; ++k) {
        //     // Update minimum distances
        //     float total_dist = 0.0f;
        //     for (size_t i = 0; i < training_vectors.size(); ++i) {
        //         float d = computeDistance(training_vectors[i],
        //                                   centroids_.back()->getVector());
        //         min_distances[i] = std::min(min_distances[i], d);
        //         total_dist += min_distances[i] * min_distances[i];
        //     }
        //
        //     // Sample new centroid proportional to distance squared
        //     std::uniform_real_distribution<float> uniform(0.0f, total_dist);
        //     float threshold = uniform(rng_);
        //
        //     float cumulative = 0.0f;
        //     size_t chosen_idx = 0;
        //     for (size_t i = 0; i < training_vectors.size(); ++i) {
        //         cumulative += min_distances[i] * min_distances[i];
        //         if (cumulative >= threshold) {
        //             chosen_idx = i;
        //             break;
        //         }
        //     }
        //
        //     centroids_.push_back(std::make_shared<Centroid>(
        //         static_cast<ClusterId>(k),
        //         training_vectors[chosen_idx]
        //     ));
        // }
    }

    /**
     * Assign a vector to its nearest cluster
     *
     * @param vector The vector to assign
     * @return The cluster ID of the nearest centroid
     */
    ClusterId assignToCluster(const Vector& vector) {
        // TODO: Implement cluster assignment
        //
        // if (!is_trained_) {
        //     throw std::runtime_error("Index not trained");
        // }
        //
        // ClusterId nearest = 0;
        // float min_distance = std::numeric_limits<float>::max();
        //
        // for (size_t i = 0; i < centroids_.size(); ++i) {
        //     float dist = computeDistance(vector, centroids_[i]->getVector());
        //     if (dist < min_distance) {
        //         min_distance = dist;
        //         nearest = static_cast<ClusterId>(i);
        //     }
        // }
        //
        // return nearest;

        // Stub: Return first cluster
        return 0;
    }

    /**
     * Find the nprobe nearest clusters to a query vector
     *
     * @param query The query vector
     * @param nprobe Number of clusters to return
     * @return Vector of (cluster_id, distance) pairs, sorted by distance
     */
    std::vector<ClusterDistance> findNearestClusters(const Vector& query, size_t nprobe) {
        // TODO: Implement cluster search
        //
        // std::vector<ClusterDistance> distances;
        // distances.reserve(centroids_.size());
        //
        // for (size_t i = 0; i < centroids_.size(); ++i) {
        //     float dist = computeDistance(query, centroids_[i]->getVector());
        //     distances.push_back({static_cast<ClusterId>(i), dist});
        // }
        //
        // // Partial sort to get top nprobe
        // size_t n = std::min(nprobe, distances.size());
        // std::partial_sort(distances.begin(), distances.begin() + n,
        //                   distances.end());
        // distances.resize(n);
        //
        // return distances;

        // Stub: Return first nprobe clusters
        std::vector<ClusterDistance> result;
        for (size_t i = 0; i < std::min(nprobe, n_clusters_); ++i) {
            result.push_back({static_cast<ClusterId>(i), 0.0f});
        }
        return result;
    }

    /**
     * Add a vector to the index
     *
     * @param id Unique identifier for the vector
     * @param vector The vector data
     * @return true if addition was successful
     */
    bool add(VectorId id, Vector vector) {
        if (!is_trained_) {
            std::cerr << "Index not trained" << std::endl;
            return false;
        }

        // Find nearest cluster and add to inverted list
        ClusterId cluster = assignToCluster(vector);

        if (cluster < inverted_lists_.size()) {
            inverted_lists_[cluster].add(id, std::move(vector));
            return true;
        }

        return false;
    }

    /**
     * Search within a single cluster's inverted list
     *
     * @param query The query vector
     * @param cluster_id The cluster to search
     * @param k Maximum results to return
     * @return Vector of (vector_id, distance) pairs
     */
    std::vector<DistanceResult> searchCluster(
        const Vector& query,
        ClusterId cluster_id,
        size_t k
    ) {
        // TODO: Implement cluster search
        //
        // if (cluster_id >= inverted_lists_.size()) {
        //     return {};
        // }
        //
        // auto entries = inverted_lists_[cluster_id].getEntries();
        //
        // // Max-heap to keep k smallest distances
        // std::priority_queue<DistanceResult> max_heap;
        //
        // for (const auto& entry : entries) {
        //     float dist = computeDistance(query, entry.vector);
        //
        //     if (max_heap.size() < k) {
        //         max_heap.push({entry.id, dist});
        //     } else if (dist < max_heap.top().distance) {
        //         max_heap.pop();
        //         max_heap.push({entry.id, dist});
        //     }
        // }
        //
        // // Convert to sorted vector
        // std::vector<DistanceResult> results;
        // results.reserve(max_heap.size());
        // while (!max_heap.empty()) {
        //     results.push_back(max_heap.top());
        //     max_heap.pop();
        // }
        // std::reverse(results.begin(), results.end());
        //
        // return results;

        // Stub: Return empty results
        std::vector<DistanceResult> results;
        return results;
    }

    /**
     * Search for k nearest neighbors across the index
     *
     * Algorithm:
     * 1. Find nprobe nearest clusters to query
     * 2. Search within each cluster
     * 3. Merge results and return top k
     *
     * @param query The query vector
     * @param k Number of nearest neighbors to return
     * @param nprobe Number of clusters to search (0 = use default)
     * @return Vector of (vector_id, distance) pairs, sorted by distance
     */
    std::vector<DistanceResult> search(const Vector& query, size_t k, size_t nprobe = 0) {
        // TODO: Implement full IVF search
        //
        // if (!is_trained_) {
        //     return {};
        // }
        //
        // if (nprobe == 0) {
        //     nprobe = n_probe_;
        // }
        //
        // // Find nearest clusters
        // auto clusters = findNearestClusters(query, nprobe);
        //
        // // Search each cluster and merge results
        // std::priority_queue<DistanceResult> max_heap;
        //
        // for (const auto& cluster : clusters) {
        //     auto cluster_results = searchCluster(query, cluster.cluster_id, k);
        //
        //     for (const auto& result : cluster_results) {
        //         if (max_heap.size() < k) {
        //             max_heap.push(result);
        //         } else if (result.distance < max_heap.top().distance) {
        //             max_heap.pop();
        //             max_heap.push(result);
        //         }
        //     }
        // }
        //
        // // Convert to sorted vector
        // std::vector<DistanceResult> results;
        // results.reserve(max_heap.size());
        // while (!max_heap.empty()) {
        //     results.push_back(max_heap.top());
        //     max_heap.pop();
        // }
        // std::reverse(results.begin(), results.end());
        //
        // return results;

        // Stub: Linear scan (inefficient - for template purposes only)
        std::vector<DistanceResult> results;

        for (const auto& list : inverted_lists_) {
            for (const auto& entry : list.getEntries()) {
                float dist = computeDistance(query, entry.vector);
                results.push_back({entry.id, dist});
            }
        }

        std::sort(results.begin(), results.end());
        if (results.size() > k) {
            results.resize(k);
        }

        return results;
    }

private:
    size_t dimension_;
    size_t n_clusters_;
    size_t n_probe_;
    std::atomic<bool> is_trained_;

    std::vector<std::shared_ptr<Centroid>> centroids_;
    std::vector<InvertedList> inverted_lists_;

    mutable std::shared_mutex index_mutex_;
    std::mt19937 rng_;
};

// ============================================================================
// gRPC Service Implementations
// ============================================================================

/**
 * Implementation of the IVF gRPC service
 *
 * Handles vector operations: Train, Add, Search
 */
class IVFServiceImpl final /* : public IVFService::Service */ {
public:
    explicit IVFServiceImpl(std::shared_ptr<IVFIndex> index)
        : index_(std::move(index)) {
    }

    /**
     * Train the index with K-means
     *
     * TODO: Implement proper proto request/response handling
     */
    grpc::Status TrainKMeans(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with TrainRequest*
        void* response        // TODO: Replace with TrainResponse*
    ) {
        // TODO: Implement TrainKMeans RPC
        //
        // 1. Parse training vectors from request
        // std::vector<IVFIndex::Vector> training_vectors;
        // for (const auto& proto_vec : request->vectors()) {
        //     training_vectors.emplace_back(proto_vec.values().begin(),
        //                                   proto_vec.values().end());
        // }
        //
        // 2. Train the index
        // bool success = index_->trainKMeans(training_vectors);
        //
        // 3. Set response
        // response->set_success(success);
        // response->set_num_clusters(index_->numClusters());

        return grpc::Status::OK;
    }

    /**
     * Assign vector to cluster
     */
    grpc::Status AssignToCluster(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with AssignRequest*
        void* response        // TODO: Replace with AssignResponse*
    ) {
        // TODO: Implement AssignToCluster RPC
        //
        // 1. Parse vector from request
        // IVFIndex::Vector vector(request->vector().begin(),
        //                         request->vector().end());
        //
        // 2. Assign to cluster
        // auto cluster_id = index_->assignToCluster(vector);
        //
        // 3. Set response
        // response->set_cluster_id(cluster_id);

        return grpc::Status::OK;
    }

    /**
     * Add a vector to the index
     */
    grpc::Status AddVector(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with AddRequest*
        void* response        // TODO: Replace with AddResponse*
    ) {
        // TODO: Implement AddVector RPC
        //
        // 1. Parse vector from request
        // IVFIndex::Vector vector(request->vector().values().begin(),
        //                         request->vector().values().end());
        //
        // 2. Add to index
        // bool success = index_->add(request->id(), std::move(vector));
        //
        // 3. Set response
        // response->set_success(success);

        return grpc::Status::OK;
    }

    /**
     * Search a specific cluster
     */
    grpc::Status SearchCluster(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with SearchClusterRequest*
        void* response        // TODO: Replace with SearchClusterResponse*
    ) {
        // TODO: Implement SearchCluster RPC
        //
        // 1. Parse query from request
        // IVFIndex::Vector query(request->query().begin(),
        //                        request->query().end());
        //
        // 2. Search cluster
        // auto results = index_->searchCluster(query, request->cluster_id(),
        //                                      request->k());
        //
        // 3. Build response
        // for (const auto& result : results) {
        //     auto* neighbor = response->add_neighbors();
        //     neighbor->set_id(result.vector_id);
        //     neighbor->set_distance(result.distance);
        // }

        return grpc::Status::OK;
    }

    /**
     * Search for k nearest neighbors
     */
    grpc::Status Search(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with SearchRequest*
        void* response        // TODO: Replace with SearchResponse*
    ) {
        // TODO: Implement Search RPC
        //
        // 1. Parse query from request
        // IVFIndex::Vector query(request->query().begin(),
        //                        request->query().end());
        //
        // 2. Perform search
        // auto results = index_->search(query, request->k(), request->nprobe());
        //
        // 3. Build response
        // for (const auto& result : results) {
        //     auto* neighbor = response->add_neighbors();
        //     neighbor->set_id(result.vector_id);
        //     neighbor->set_distance(result.distance);
        // }

        return grpc::Status::OK;
    }

private:
    std::shared_ptr<IVFIndex> index_;
};

/**
 * Implementation of the Node coordination service
 *
 * Handles distributed operations: health checks, data transfer, coordination
 */
class NodeServiceImpl final /* : public NodeService::Service */ {
public:
    NodeServiceImpl(
        const std::string& node_id,
        const std::vector<std::string>& peer_addresses
    )
        : node_id_(node_id)
        , peer_addresses_(peer_addresses) {
    }

    /**
     * Health check RPC
     */
    grpc::Status HealthCheck(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with HealthRequest*
        void* response        // TODO: Replace with HealthResponse*
    ) {
        // TODO: Implement health check
        // response->set_status(HealthStatus::HEALTHY);
        // response->set_node_id(node_id_);

        return grpc::Status::OK;
    }

    /**
     * Forward search to peer nodes
     */
    grpc::Status ForwardSearch(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with ForwardSearchRequest*
        void* response        // TODO: Replace with ForwardSearchResponse*
    ) {
        // TODO: Implement distributed search forwarding
        //
        // For cluster-sharded deployment:
        // 1. Determine which peers own the target clusters
        // 2. Forward search to those peers
        // 3. Merge results and respond

        return grpc::Status::OK;
    }

    /**
     * Receive centroid updates (for distributed training)
     */
    grpc::Status UpdateCentroids(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with UpdateCentroidsRequest*
        void* response        // TODO: Replace with UpdateCentroidsResponse*
    ) {
        // TODO: Implement centroid synchronization
        // For distributed K-means training

        return grpc::Status::OK;
    }

    /**
     * Transfer inverted list data (for rebalancing)
     */
    grpc::Status TransferInvertedList(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with TransferRequest*
        void* response        // TODO: Replace with TransferResponse*
    ) {
        // TODO: Implement data transfer for cluster rebalancing

        return grpc::Status::OK;
    }

private:
    std::string node_id_;
    std::vector<std::string> peer_addresses_;
};

// ============================================================================
// Server Setup and Main
// ============================================================================

/**
 * Parse command line arguments
 */
struct ServerConfig {
    std::string node_id = "node-1";
    int port = 50051;
    std::vector<std::string> peers;
    size_t dimension = ivf_config::DEFAULT_DIMENSION;
    size_t n_clusters = ivf_config::N_CLUSTERS;
    size_t n_probe = ivf_config::N_PROBE;

    static ServerConfig parse(int argc, char** argv) {
        ServerConfig config;

        for (int i = 1; i < argc; ++i) {
            std::string arg = argv[i];

            if (arg == "--node-id" && i + 1 < argc) {
                config.node_id = argv[++i];
            } else if (arg == "--port" && i + 1 < argc) {
                config.port = std::stoi(argv[++i]);
            } else if (arg == "--peer" && i + 1 < argc) {
                config.peers.push_back(argv[++i]);
            } else if (arg == "--dimension" && i + 1 < argc) {
                config.dimension = std::stoul(argv[++i]);
            } else if (arg == "--clusters" && i + 1 < argc) {
                config.n_clusters = std::stoul(argv[++i]);
            } else if (arg == "--nprobe" && i + 1 < argc) {
                config.n_probe = std::stoul(argv[++i]);
            } else if (arg == "--help") {
                std::cout << "Usage: " << argv[0] << " [options]\n"
                          << "Options:\n"
                          << "  --node-id ID      Node identifier (default: node-1)\n"
                          << "  --port PORT       Port to listen on (default: 50051)\n"
                          << "  --peer ADDR       Peer address (can be repeated)\n"
                          << "  --dimension DIM   Vector dimension (default: 128)\n"
                          << "  --clusters N      Number of clusters (default: 256)\n"
                          << "  --nprobe N        Clusters to probe (default: 8)\n"
                          << "  --help            Show this help message\n";
                std::exit(0);
            }
        }

        return config;
    }
};

/**
 * Run the gRPC server
 */
void runServer(const ServerConfig& config) {
    // Create the IVF index
    auto index = std::make_shared<IVFIndex>(config.dimension, config.n_clusters);
    index->setNumProbe(config.n_probe);

    // Create service implementations
    IVFServiceImpl ivf_service(index);
    NodeServiceImpl node_service(config.node_id, config.peers);

    // Build and start server
    grpc::ServerBuilder builder;

    std::string server_address = "0.0.0.0:" + std::to_string(config.port);
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());

    // TODO: Register services with builder
    // builder.RegisterService(&ivf_service);
    // builder.RegisterService(&node_service);

    std::unique_ptr<grpc::Server> server(builder.BuildAndStart());

    std::cout << "IVF Server [" << config.node_id << "] listening on "
              << server_address << std::endl;
    std::cout << "Index configuration:" << std::endl;
    std::cout << "  Dimension: " << config.dimension << std::endl;
    std::cout << "  Clusters: " << config.n_clusters << std::endl;
    std::cout << "  N_probe: " << config.n_probe << std::endl;
    std::cout << "Peers: ";
    for (const auto& peer : config.peers) {
        std::cout << peer << " ";
    }
    std::cout << std::endl;

    // Wait for shutdown signal
    server->Wait();
}

/**
 * Main entry point
 */
int main(int argc, char** argv) {
    // Parse command line arguments
    ServerConfig config = ServerConfig::parse(argc, argv);

    // Run the server
    runServer(config);

    return 0;
}

// ============================================================================
// Additional Notes for Implementation
// ============================================================================

/*
 * PROTO FILE SUGGESTIONS (ivf.proto):
 * ===================================
 *
 * syntax = "proto3";
 *
 * service IVFService {
 *     rpc TrainKMeans(TrainRequest) returns (TrainResponse);
 *     rpc AssignToCluster(AssignRequest) returns (AssignResponse);
 *     rpc AddVector(AddRequest) returns (AddResponse);
 *     rpc SearchCluster(SearchClusterRequest) returns (SearchClusterResponse);
 *     rpc Search(SearchRequest) returns (SearchResponse);
 * }
 *
 * message TrainRequest {
 *     repeated Vector vectors = 1;
 * }
 *
 * message TrainResponse {
 *     bool success = 1;
 *     uint32 num_clusters = 2;
 *     string error_message = 3;
 * }
 *
 * message AssignRequest {
 *     repeated float vector = 1;
 * }
 *
 * message AssignResponse {
 *     uint32 cluster_id = 1;
 * }
 *
 * message SearchRequest {
 *     repeated float query = 1;
 *     uint32 k = 2;
 *     uint32 nprobe = 3;
 * }
 *
 * message SearchResponse {
 *     repeated Neighbor neighbors = 1;
 * }
 *
 *
 * DISTRIBUTED DEPLOYMENT STRATEGIES:
 * ==================================
 * 1. Cluster Sharding: Each node owns a subset of clusters
 *    - Good for large number of clusters
 *    - Requires coordination for multi-cluster searches
 *
 * 2. Data Sharding: Each node has all clusters but subset of vectors
 *    - Simpler implementation
 *    - Requires result merging from all nodes
 *
 * 3. Hybrid: Replicate centroids, shard inverted lists
 *    - Best of both worlds
 *    - More complex but scalable
 *
 *
 * OPTIMIZATION OPPORTUNITIES:
 * ===========================
 * 1. SIMD for distance computation
 * 2. Multi-threaded K-means training
 * 3. Product quantization for compact storage (IVF-PQ)
 * 4. Residual quantization for improved accuracy
 * 5. GPU acceleration for training and search
 */
