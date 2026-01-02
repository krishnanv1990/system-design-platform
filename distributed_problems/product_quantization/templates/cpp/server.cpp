/**
 * Product Quantization (PQ) Vector Search Server
 *
 * This template implements a gRPC server for distributed PQ index operations.
 *
 * ALGORITHM OVERVIEW:
 * ===================
 * Product Quantization is a vector compression technique that:
 * 1. Splits vectors into M subvectors
 * 2. Quantizes each subvector independently using K centroids (codebook)
 * 3. Represents each vector as M code values (M * log2(K) bits total)
 * 4. Uses asymmetric distance computation (ADC) for fast search
 *
 * Key concepts:
 * - Subquantizer: Codebook for one subspace (K centroids)
 * - PQ Code: Compact representation of a vector (M bytes if K=256)
 * - Distance Table: Precomputed distances from query to all centroids
 *
 * DISTRIBUTED CONSIDERATIONS:
 * ===========================
 * - Codebooks can be replicated across all nodes
 * - PQ codes can be sharded across nodes
 * - Search requires collecting results from all shards
 *
 * TODO: Implement the core algorithm methods marked with TODO comments
 */

#include <grpcpp/grpcpp.h>
#include <grpcpp/server.h>
#include <grpcpp/server_builder.h>
#include <grpcpp/server_context.h>

// TODO: Include generated proto headers
// #include "pq.grpc.pb.h"
// #include "node.grpc.pb.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
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

namespace pq_config {
    // Number of subquantizers (subspaces)
    constexpr size_t M = 8;

    // Number of centroids per subquantizer (typically 256 for 8-bit codes)
    constexpr size_t K = 256;

    // Default vector dimension (must be divisible by M)
    constexpr size_t DEFAULT_DIMENSION = 128;

    // Maximum K-means iterations for training
    constexpr size_t MAX_KMEANS_ITERATIONS = 100;

    // K-means convergence threshold
    constexpr float KMEANS_TOLERANCE = 1e-4f;

    // Minimum training vectors
    constexpr size_t MIN_TRAINING_VECTORS = 1000;
}

// ============================================================================
// Forward Declarations
// ============================================================================

class Codebook;
class PQCode;
class PQIndex;
class PQServiceImpl;
class NodeServiceImpl;

// ============================================================================
// Data Structures
// ============================================================================

/**
 * Codebook for a single subquantizer
 *
 * Contains K centroids for quantizing subvectors of dimension D/M
 */
class Codebook {
public:
    using Vector = std::vector<float>;
    using CodeValue = uint8_t;  // Supports up to 256 centroids

    Codebook(size_t subvector_dim, size_t k = pq_config::K)
        : subvector_dim_(subvector_dim)
        , k_(k)
        , centroids_(k, Vector(subvector_dim, 0.0f))
        , is_trained_(false) {
    }

    ~Codebook() = default;

    // Getters
    size_t subvectorDim() const { return subvector_dim_; }
    size_t numCentroids() const { return k_; }
    bool isTrained() const { return is_trained_.load(); }

    /**
     * Get centroid vector by code value
     */
    const Vector& getCentroid(CodeValue code) const {
        return centroids_[code];
    }

    /**
     * Set centroid vector
     */
    void setCentroid(CodeValue code, Vector centroid) {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        if (code < k_) {
            centroids_[code] = std::move(centroid);
        }
    }

    /**
     * Get all centroids (for serialization)
     */
    std::vector<Vector> getCentroids() const {
        std::shared_lock<std::shared_mutex> lock(mutex_);
        return centroids_;
    }

    /**
     * Set trained status
     */
    void setTrained(bool trained) {
        is_trained_.store(trained);
    }

    /**
     * Compute L2 distance between two subvectors
     */
    static float computeDistance(const float* a, const float* b, size_t dim) {
        float dist = 0.0f;
        for (size_t i = 0; i < dim; ++i) {
            float diff = a[i] - b[i];
            dist += diff * diff;
        }
        return dist;
    }

    /**
     * Find nearest centroid for a subvector
     *
     * @param subvector Pointer to subvector data
     * @return Code value (index of nearest centroid)
     */
    CodeValue encode(const float* subvector) const {
        // TODO: Implement encoding (find nearest centroid)
        //
        // CodeValue best_code = 0;
        // float min_dist = std::numeric_limits<float>::max();
        //
        // for (size_t i = 0; i < k_; ++i) {
        //     float dist = computeDistance(subvector, centroids_[i].data(),
        //                                  subvector_dim_);
        //     if (dist < min_dist) {
        //         min_dist = dist;
        //         best_code = static_cast<CodeValue>(i);
        //     }
        // }
        //
        // return best_code;

        // Stub: Return 0
        return 0;
    }

    /**
     * Compute distance table from query subvector to all centroids
     *
     * @param query_subvector Pointer to query subvector
     * @return Vector of K distances
     */
    std::vector<float> computeDistanceTable(const float* query_subvector) const {
        // TODO: Implement distance table computation
        //
        // std::vector<float> distances(k_);
        //
        // for (size_t i = 0; i < k_; ++i) {
        //     distances[i] = computeDistance(query_subvector,
        //                                    centroids_[i].data(),
        //                                    subvector_dim_);
        // }
        //
        // return distances;

        // Stub: Return zeros
        return std::vector<float>(k_, 0.0f);
    }

private:
    size_t subvector_dim_;
    size_t k_;
    std::vector<Vector> centroids_;
    std::atomic<bool> is_trained_;
    mutable std::shared_mutex mutex_;
};

/**
 * PQ Code: Compact representation of a vector
 *
 * Stores M code values (one per subquantizer)
 */
class PQCode {
public:
    using CodeValue = uint8_t;
    using VectorId = uint64_t;

    PQCode(size_t m = pq_config::M)
        : codes_(m, 0) {
    }

    PQCode(std::vector<CodeValue> codes)
        : codes_(std::move(codes)) {
    }

    ~PQCode() = default;

    // Getters
    size_t numSubquantizers() const { return codes_.size(); }

    CodeValue getCode(size_t m) const {
        return (m < codes_.size()) ? codes_[m] : 0;
    }

    const std::vector<CodeValue>& getCodes() const {
        return codes_;
    }

    // Setters
    void setCode(size_t m, CodeValue code) {
        if (m < codes_.size()) {
            codes_[m] = code;
        }
    }

    void setCodes(std::vector<CodeValue> codes) {
        codes_ = std::move(codes);
    }

    /**
     * Compute distance using precomputed distance tables
     *
     * @param distance_tables M distance tables (one per subquantizer)
     * @return Approximate squared L2 distance
     */
    float computeDistance(const std::vector<std::vector<float>>& distance_tables) const {
        // TODO: Implement ADC (Asymmetric Distance Computation)
        //
        // float total_dist = 0.0f;
        //
        // for (size_t m = 0; m < codes_.size(); ++m) {
        //     total_dist += distance_tables[m][codes_[m]];
        // }
        //
        // return total_dist;

        // Stub: Return 0
        return 0.0f;
    }

private:
    std::vector<CodeValue> codes_;
};

/**
 * Entry in the PQ index
 */
struct PQEntry {
    PQCode::VectorId id;
    PQCode code;

    // Optional: Store original vector for exact reranking
    std::optional<std::vector<float>> original_vector;
};

/**
 * Distance result for search operations
 */
struct DistanceResult {
    PQCode::VectorId vector_id;
    float distance;

    bool operator<(const DistanceResult& other) const {
        return distance < other.distance;
    }

    bool operator>(const DistanceResult& other) const {
        return distance > other.distance;
    }
};

/**
 * The main PQ Index structure
 *
 * Maintains:
 * - M codebooks (one per subquantizer)
 * - Collection of PQ codes with their IDs
 */
class PQIndex {
public:
    using VectorId = uint64_t;
    using Vector = std::vector<float>;
    using CodeValue = uint8_t;

    PQIndex(
        size_t dimension,
        size_t m = pq_config::M,
        size_t k = pq_config::K
    )
        : dimension_(dimension)
        , m_(m)
        , k_(k)
        , subvector_dim_(dimension / m)
        , is_trained_(false)
        , rng_(std::random_device{}()) {

        // Validate dimension is divisible by M
        if (dimension % m != 0) {
            throw std::invalid_argument(
                "Dimension must be divisible by number of subquantizers"
            );
        }

        // Initialize codebooks
        codebooks_.reserve(m_);
        for (size_t i = 0; i < m_; ++i) {
            codebooks_.push_back(std::make_shared<Codebook>(subvector_dim_, k_));
        }
    }

    ~PQIndex() = default;

    // Getters
    size_t dimension() const { return dimension_; }
    size_t numSubquantizers() const { return m_; }
    size_t numCentroids() const { return k_; }
    size_t subvectorDim() const { return subvector_dim_; }
    bool isTrained() const { return is_trained_.load(); }

    /**
     * Get number of vectors in the index
     */
    size_t size() const {
        std::shared_lock<std::shared_mutex> lock(index_mutex_);
        return entries_.size();
    }

    /**
     * Get a codebook by index
     */
    std::shared_ptr<Codebook> getCodebook(size_t m) const {
        return (m < codebooks_.size()) ? codebooks_[m] : nullptr;
    }

    // ========================================================================
    // Core Algorithm Methods - TO BE IMPLEMENTED
    // ========================================================================

    /**
     * Train all subquantizers using K-means
     *
     * Algorithm:
     * 1. For each subquantizer m:
     *    a. Extract subvectors from training data
     *    b. Run K-means to find K centroids
     *    c. Store centroids in codebook
     *
     * @param training_vectors Vectors to use for training
     * @return true if training was successful
     */
    bool trainSubquantizers(const std::vector<Vector>& training_vectors) {
        // TODO: Implement subquantizer training
        //
        // Step 1: Validate input
        // if (training_vectors.size() < pq_config::MIN_TRAINING_VECTORS) {
        //     return false;
        // }
        //
        // for (const auto& vec : training_vectors) {
        //     if (vec.size() != dimension_) {
        //         return false;
        //     }
        // }
        //
        // Step 2: Train each subquantizer independently
        // for (size_t m = 0; m < m_; ++m) {
        //     // Extract subvectors for this subquantizer
        //     std::vector<std::vector<float>> subvectors;
        //     subvectors.reserve(training_vectors.size());
        //
        //     for (const auto& vec : training_vectors) {
        //         std::vector<float> subvec(
        //             vec.begin() + m * subvector_dim_,
        //             vec.begin() + (m + 1) * subvector_dim_
        //         );
        //         subvectors.push_back(std::move(subvec));
        //     }
        //
        //     // Train codebook using K-means
        //     trainCodebook(m, subvectors);
        // }
        //
        // is_trained_ = true;
        // return true;

        // Stub: Initialize with random centroids
        std::unique_lock<std::shared_mutex> lock(index_mutex_);

        if (training_vectors.empty()) {
            return false;
        }

        // Random initialization for stub
        std::uniform_int_distribution<size_t> dist(0, training_vectors.size() - 1);

        for (size_t m = 0; m < m_; ++m) {
            for (size_t k = 0; k < k_; ++k) {
                size_t idx = dist(rng_);
                const auto& vec = training_vectors[idx];

                std::vector<float> centroid(
                    vec.begin() + m * subvector_dim_,
                    vec.begin() + (m + 1) * subvector_dim_
                );

                codebooks_[m]->setCentroid(static_cast<CodeValue>(k), std::move(centroid));
            }
            codebooks_[m]->setTrained(true);
        }

        is_trained_ = true;
        return true;
    }

    /**
     * Train a single codebook using K-means
     *
     * @param m Subquantizer index
     * @param subvectors Training subvectors for this subspace
     */
    void trainCodebook(size_t m, const std::vector<std::vector<float>>& subvectors) {
        // TODO: Implement K-means for codebook training
        //
        // auto& codebook = codebooks_[m];
        //
        // Step 1: Initialize centroids (random or K-means++)
        // std::vector<size_t> indices(subvectors.size());
        // std::iota(indices.begin(), indices.end(), 0);
        // std::shuffle(indices.begin(), indices.end(), rng_);
        //
        // for (size_t k = 0; k < k_; ++k) {
        //     codebook->setCentroid(k, subvectors[indices[k]]);
        // }
        //
        // Step 2: K-means iterations
        // std::vector<std::vector<float>> new_centroids(k_,
        //     std::vector<float>(subvector_dim_, 0.0f));
        // std::vector<size_t> counts(k_, 0);
        //
        // for (size_t iter = 0; iter < pq_config::MAX_KMEANS_ITERATIONS; ++iter) {
        //     // Reset accumulators
        //     for (auto& c : new_centroids) {
        //         std::fill(c.begin(), c.end(), 0.0f);
        //     }
        //     std::fill(counts.begin(), counts.end(), 0);
        //
        //     // Assign and accumulate
        //     for (const auto& subvec : subvectors) {
        //         CodeValue code = codebook->encode(subvec.data());
        //         counts[code]++;
        //         for (size_t d = 0; d < subvector_dim_; ++d) {
        //             new_centroids[code][d] += subvec[d];
        //         }
        //     }
        //
        //     // Update centroids
        //     float max_movement = 0.0f;
        //     for (size_t k = 0; k < k_; ++k) {
        //         if (counts[k] > 0) {
        //             for (size_t d = 0; d < subvector_dim_; ++d) {
        //                 new_centroids[k][d] /= counts[k];
        //             }
        //
        //             // Compute movement
        //             float movement = Codebook::computeDistance(
        //                 codebook->getCentroid(k).data(),
        //                 new_centroids[k].data(),
        //                 subvector_dim_
        //             );
        //             max_movement = std::max(max_movement, movement);
        //
        //             codebook->setCentroid(k, new_centroids[k]);
        //         }
        //     }
        //
        //     // Check convergence
        //     if (max_movement < pq_config::KMEANS_TOLERANCE) {
        //         break;
        //     }
        // }
        //
        // codebook->setTrained(true);
    }

    /**
     * Encode a vector into PQ codes
     *
     * @param vector The vector to encode
     * @return PQ code representation
     */
    PQCode encodeVector(const Vector& vector) const {
        // TODO: Implement vector encoding
        //
        // if (!is_trained_) {
        //     throw std::runtime_error("Index not trained");
        // }
        //
        // if (vector.size() != dimension_) {
        //     throw std::invalid_argument("Invalid vector dimension");
        // }
        //
        // PQCode code(m_);
        //
        // for (size_t m = 0; m < m_; ++m) {
        //     const float* subvec = vector.data() + m * subvector_dim_;
        //     CodeValue c = codebooks_[m]->encode(subvec);
        //     code.setCode(m, c);
        // }
        //
        // return code;

        // Stub: Return zero codes
        return PQCode(m_);
    }

    /**
     * Decode PQ codes back to an approximate vector
     *
     * @param code The PQ code to decode
     * @return Reconstructed vector (approximation)
     */
    Vector decodeVector(const PQCode& code) const {
        // TODO: Implement vector decoding (reconstruction)
        //
        // Vector reconstructed(dimension_);
        //
        // for (size_t m = 0; m < m_; ++m) {
        //     CodeValue c = code.getCode(m);
        //     const auto& centroid = codebooks_[m]->getCentroid(c);
        //
        //     std::copy(
        //         centroid.begin(),
        //         centroid.end(),
        //         reconstructed.begin() + m * subvector_dim_
        //     );
        // }
        //
        // return reconstructed;

        // Stub: Return zero vector
        return Vector(dimension_, 0.0f);
    }

    /**
     * Compute distance tables for a query vector
     *
     * Precomputes distances from each query subvector to all centroids.
     * This enables fast distance computation using only table lookups.
     *
     * @param query The query vector
     * @return M x K distance table
     */
    std::vector<std::vector<float>> computeDistanceTable(const Vector& query) const {
        // TODO: Implement distance table computation
        //
        // if (query.size() != dimension_) {
        //     throw std::invalid_argument("Invalid query dimension");
        // }
        //
        // std::vector<std::vector<float>> tables(m_);
        //
        // for (size_t m = 0; m < m_; ++m) {
        //     const float* query_subvec = query.data() + m * subvector_dim_;
        //     tables[m] = codebooks_[m]->computeDistanceTable(query_subvec);
        // }
        //
        // return tables;

        // Stub: Return zero tables
        std::vector<std::vector<float>> tables(m_);
        for (size_t m = 0; m < m_; ++m) {
            tables[m].resize(k_, 0.0f);
        }
        return tables;
    }

    /**
     * Add a vector to the index
     *
     * @param id Unique identifier for the vector
     * @param vector The vector data
     * @param store_original Whether to store the original vector for reranking
     * @return true if addition was successful
     */
    bool add(VectorId id, Vector vector, bool store_original = false) {
        if (!is_trained_) {
            std::cerr << "Index not trained" << std::endl;
            return false;
        }

        if (vector.size() != dimension_) {
            std::cerr << "Invalid vector dimension" << std::endl;
            return false;
        }

        // Encode the vector
        PQCode code = encodeVector(vector);

        // Create entry
        PQEntry entry;
        entry.id = id;
        entry.code = std::move(code);

        if (store_original) {
            entry.original_vector = std::move(vector);
        }

        // Add to index
        std::unique_lock<std::shared_mutex> lock(index_mutex_);
        entries_.push_back(std::move(entry));

        return true;
    }

    /**
     * Search for k nearest neighbors using PQ
     *
     * Algorithm (Asymmetric Distance Computation - ADC):
     * 1. Compute distance tables for query
     * 2. For each PQ code, compute approximate distance using table lookups
     * 3. Return top-k results
     *
     * @param query The query vector
     * @param k Number of nearest neighbors
     * @return Vector of (vector_id, distance) pairs
     */
    std::vector<DistanceResult> searchWithPQ(const Vector& query, size_t k) {
        // TODO: Implement PQ search
        //
        // if (!is_trained_) {
        //     return {};
        // }
        //
        // Step 1: Compute distance tables
        // auto distance_tables = computeDistanceTable(query);
        //
        // Step 2: Scan all codes and compute distances
        // std::priority_queue<DistanceResult> max_heap;  // Max-heap for top-k
        //
        // {
        //     std::shared_lock<std::shared_mutex> lock(index_mutex_);
        //
        //     for (const auto& entry : entries_) {
        //         float dist = entry.code.computeDistance(distance_tables);
        //
        //         if (max_heap.size() < k) {
        //             max_heap.push({entry.id, dist});
        //         } else if (dist < max_heap.top().distance) {
        //             max_heap.pop();
        //             max_heap.push({entry.id, dist});
        //         }
        //     }
        // }
        //
        // Step 3: Convert to sorted vector
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
     * Search with reranking using original vectors
     *
     * For improved accuracy:
     * 1. First pass: PQ search with larger candidate set
     * 2. Second pass: Exact distance computation on candidates
     *
     * @param query The query vector
     * @param k Number of final results
     * @param rerank_factor Multiplier for first-pass candidates
     * @return Vector of (vector_id, distance) pairs
     */
    std::vector<DistanceResult> searchWithReranking(
        const Vector& query,
        size_t k,
        size_t rerank_factor = 10
    ) {
        // TODO: Implement search with reranking
        //
        // Step 1: PQ search for k * rerank_factor candidates
        // auto candidates = searchWithPQ(query, k * rerank_factor);
        //
        // Step 2: Rerank using exact distances
        // std::vector<DistanceResult> reranked;
        // reranked.reserve(candidates.size());
        //
        // {
        //     std::shared_lock<std::shared_mutex> lock(index_mutex_);
        //
        //     for (const auto& candidate : candidates) {
        //         // Find the entry
        //         for (const auto& entry : entries_) {
        //             if (entry.id == candidate.vector_id &&
        //                 entry.original_vector.has_value()) {
        //
        //                 // Compute exact distance
        //                 float exact_dist = computeL2Distance(
        //                     query,
        //                     entry.original_vector.value()
        //                 );
        //                 reranked.push_back({entry.id, exact_dist});
        //                 break;
        //             }
        //         }
        //     }
        // }
        //
        // Step 3: Sort and return top-k
        // std::sort(reranked.begin(), reranked.end());
        // if (reranked.size() > k) {
        //     reranked.resize(k);
        // }
        //
        // return reranked;

        // Stub: Just call PQ search
        return searchWithPQ(query, k);
    }

    /**
     * Compute exact L2 distance between two vectors
     */
    static float computeL2Distance(const Vector& a, const Vector& b) {
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

private:
    size_t dimension_;
    size_t m_;               // Number of subquantizers
    size_t k_;               // Centroids per subquantizer
    size_t subvector_dim_;   // Dimension of each subvector

    std::atomic<bool> is_trained_;
    std::vector<std::shared_ptr<Codebook>> codebooks_;
    std::vector<PQEntry> entries_;

    mutable std::shared_mutex index_mutex_;
    std::mt19937 rng_;
};

// ============================================================================
// gRPC Service Implementations
// ============================================================================

/**
 * Implementation of the PQ gRPC service
 *
 * Handles vector operations: Train, Encode, Decode, Search
 */
class PQServiceImpl final /* : public PQService::Service */ {
public:
    explicit PQServiceImpl(std::shared_ptr<PQIndex> index)
        : index_(std::move(index)) {
    }

    /**
     * Train subquantizers
     *
     * TODO: Implement proper proto request/response handling
     */
    grpc::Status TrainSubquantizers(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with TrainRequest*
        void* response        // TODO: Replace with TrainResponse*
    ) {
        // TODO: Implement TrainSubquantizers RPC
        //
        // 1. Parse training vectors from request
        // std::vector<PQIndex::Vector> training_vectors;
        // for (const auto& proto_vec : request->vectors()) {
        //     training_vectors.emplace_back(proto_vec.values().begin(),
        //                                   proto_vec.values().end());
        // }
        //
        // 2. Train the index
        // bool success = index_->trainSubquantizers(training_vectors);
        //
        // 3. Set response
        // response->set_success(success);
        // response->set_num_subquantizers(index_->numSubquantizers());
        // response->set_num_centroids(index_->numCentroids());

        return grpc::Status::OK;
    }

    /**
     * Encode a vector
     */
    grpc::Status EncodeVector(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with EncodeRequest*
        void* response        // TODO: Replace with EncodeResponse*
    ) {
        // TODO: Implement EncodeVector RPC
        //
        // 1. Parse vector from request
        // PQIndex::Vector vector(request->vector().begin(),
        //                        request->vector().end());
        //
        // 2. Encode
        // PQCode code = index_->encodeVector(vector);
        //
        // 3. Set response
        // for (size_t m = 0; m < code.numSubquantizers(); ++m) {
        //     response->add_codes(code.getCode(m));
        // }

        return grpc::Status::OK;
    }

    /**
     * Decode a PQ code
     */
    grpc::Status DecodeVector(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with DecodeRequest*
        void* response        // TODO: Replace with DecodeResponse*
    ) {
        // TODO: Implement DecodeVector RPC
        //
        // 1. Parse codes from request
        // std::vector<uint8_t> codes(request->codes().begin(),
        //                            request->codes().end());
        // PQCode pq_code(codes);
        //
        // 2. Decode
        // auto vector = index_->decodeVector(pq_code);
        //
        // 3. Set response
        // for (float v : vector) {
        //     response->add_vector(v);
        // }

        return grpc::Status::OK;
    }

    /**
     * Compute distance table
     */
    grpc::Status ComputeDistanceTable(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with DistanceTableRequest*
        void* response        // TODO: Replace with DistanceTableResponse*
    ) {
        // TODO: Implement ComputeDistanceTable RPC
        //
        // 1. Parse query from request
        // PQIndex::Vector query(request->query().begin(),
        //                       request->query().end());
        //
        // 2. Compute tables
        // auto tables = index_->computeDistanceTable(query);
        //
        // 3. Set response
        // for (const auto& table : tables) {
        //     auto* proto_table = response->add_tables();
        //     for (float dist : table) {
        //         proto_table->add_distances(dist);
        //     }
        // }

        return grpc::Status::OK;
    }

    /**
     * Add a vector
     */
    grpc::Status AddVector(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with AddRequest*
        void* response        // TODO: Replace with AddResponse*
    ) {
        // TODO: Implement AddVector RPC
        //
        // 1. Parse from request
        // PQIndex::Vector vector(request->vector().values().begin(),
        //                        request->vector().values().end());
        //
        // 2. Add to index
        // bool success = index_->add(request->id(), std::move(vector),
        //                           request->store_original());
        //
        // 3. Set response
        // response->set_success(success);

        return grpc::Status::OK;
    }

    /**
     * Search with PQ
     */
    grpc::Status SearchWithPQ(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with SearchRequest*
        void* response        // TODO: Replace with SearchResponse*
    ) {
        // TODO: Implement SearchWithPQ RPC
        //
        // 1. Parse query from request
        // PQIndex::Vector query(request->query().begin(),
        //                       request->query().end());
        //
        // 2. Perform search
        // std::vector<DistanceResult> results;
        // if (request->use_reranking()) {
        //     results = index_->searchWithReranking(query, request->k(),
        //                                          request->rerank_factor());
        // } else {
        //     results = index_->searchWithPQ(query, request->k());
        // }
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
    std::shared_ptr<PQIndex> index_;
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
        // TODO: Implement distributed search
        //
        // 1. Search local index
        // 2. Forward to peers if needed
        // 3. Merge results

        return grpc::Status::OK;
    }

    /**
     * Sync codebooks with peers (for training consistency)
     */
    grpc::Status SyncCodebooks(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with SyncCodebooksRequest*
        void* response        // TODO: Replace with SyncCodebooksResponse*
    ) {
        // TODO: Implement codebook synchronization
        // All nodes should have the same codebooks after training

        return grpc::Status::OK;
    }

    /**
     * Transfer PQ codes (for data migration)
     */
    grpc::Status TransferCodes(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with TransferCodesRequest*
        void* response        // TODO: Replace with TransferCodesResponse*
    ) {
        // TODO: Implement PQ code transfer for rebalancing

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
    size_t dimension = pq_config::DEFAULT_DIMENSION;
    size_t m = pq_config::M;
    size_t k = pq_config::K;

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
            } else if (arg == "-m" && i + 1 < argc) {
                config.m = std::stoul(argv[++i]);
            } else if (arg == "-k" && i + 1 < argc) {
                config.k = std::stoul(argv[++i]);
            } else if (arg == "--help") {
                std::cout << "Usage: " << argv[0] << " [options]\n"
                          << "Options:\n"
                          << "  --node-id ID      Node identifier (default: node-1)\n"
                          << "  --port PORT       Port to listen on (default: 50051)\n"
                          << "  --peer ADDR       Peer address (can be repeated)\n"
                          << "  --dimension DIM   Vector dimension (default: 128)\n"
                          << "  -m NUM            Number of subquantizers (default: 8)\n"
                          << "  -k NUM            Centroids per subquantizer (default: 256)\n"
                          << "  --help            Show this help message\n";
                std::exit(0);
            }
        }

        // Validate dimension is divisible by m
        if (config.dimension % config.m != 0) {
            std::cerr << "Error: Dimension must be divisible by number of "
                      << "subquantizers (-m)" << std::endl;
            std::exit(1);
        }

        return config;
    }
};

/**
 * Run the gRPC server
 */
void runServer(const ServerConfig& config) {
    // Create the PQ index
    auto index = std::make_shared<PQIndex>(config.dimension, config.m, config.k);

    // Create service implementations
    PQServiceImpl pq_service(index);
    NodeServiceImpl node_service(config.node_id, config.peers);

    // Build and start server
    grpc::ServerBuilder builder;

    std::string server_address = "0.0.0.0:" + std::to_string(config.port);
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());

    // TODO: Register services with builder
    // builder.RegisterService(&pq_service);
    // builder.RegisterService(&node_service);

    std::unique_ptr<grpc::Server> server(builder.BuildAndStart());

    std::cout << "PQ Server [" << config.node_id << "] listening on "
              << server_address << std::endl;
    std::cout << "Index configuration:" << std::endl;
    std::cout << "  Dimension: " << config.dimension << std::endl;
    std::cout << "  Subquantizers (M): " << config.m << std::endl;
    std::cout << "  Centroids per subquantizer (K): " << config.k << std::endl;
    std::cout << "  Subvector dimension: " << config.dimension / config.m << std::endl;
    std::cout << "  Code size: " << config.m << " bytes" << std::endl;
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
 * PROTO FILE SUGGESTIONS (pq.proto):
 * ==================================
 *
 * syntax = "proto3";
 *
 * service PQService {
 *     rpc TrainSubquantizers(TrainRequest) returns (TrainResponse);
 *     rpc EncodeVector(EncodeRequest) returns (EncodeResponse);
 *     rpc DecodeVector(DecodeRequest) returns (DecodeResponse);
 *     rpc ComputeDistanceTable(DistanceTableRequest) returns (DistanceTableResponse);
 *     rpc AddVector(AddRequest) returns (AddResponse);
 *     rpc SearchWithPQ(SearchRequest) returns (SearchResponse);
 * }
 *
 * message EncodeRequest {
 *     repeated float vector = 1;
 * }
 *
 * message EncodeResponse {
 *     repeated uint32 codes = 1;  // M code values
 * }
 *
 * message DecodeRequest {
 *     repeated uint32 codes = 1;
 * }
 *
 * message DecodeResponse {
 *     repeated float vector = 1;  // Reconstructed vector
 * }
 *
 * message SearchRequest {
 *     repeated float query = 1;
 *     uint32 k = 2;
 *     bool use_reranking = 3;
 *     uint32 rerank_factor = 4;
 * }
 *
 *
 * ADVANCED TECHNIQUES:
 * ====================
 * 1. OPQ (Optimized Product Quantization)
 *    - Learn a rotation matrix to minimize quantization error
 *    - Rotate vectors before splitting into subvectors
 *
 * 2. LOPQ (Locally Optimized Product Quantization)
 *    - Different codebooks for different regions of space
 *    - Combine with IVF for better accuracy
 *
 * 3. Polysemous Codes
 *    - Arrange codebook so Hamming distance approximates L2 distance
 *    - Enables fast filtering with binary comparisons
 *
 *
 * OPTIMIZATION OPPORTUNITIES:
 * ===========================
 * 1. SIMD for distance table lookups
 * 2. Prefetching for sequential code scanning
 * 3. Multi-threaded search across code blocks
 * 4. GPU-accelerated training and search
 * 5. Memory-mapped code storage for large indices
 *
 *
 * COMPRESSION ANALYSIS:
 * =====================
 * For dimension D=128, M=8, K=256:
 * - Original vector: 128 * 4 = 512 bytes
 * - PQ code: 8 * 1 = 8 bytes
 * - Compression ratio: 64x
 *
 * Memory for 1 billion vectors:
 * - Original: ~500 GB
 * - PQ: ~8 GB (plus codebooks)
 */
