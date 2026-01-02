/**
 * HNSW (Hierarchical Navigable Small World) Vector Search Server
 *
 * This template implements a gRPC server for distributed HNSW index operations.
 *
 * ALGORITHM OVERVIEW:
 * ===================
 * HNSW is a graph-based approximate nearest neighbor search algorithm that builds
 * a multi-layer graph structure where:
 * - Higher layers contain fewer nodes with longer-range connections (for fast traversal)
 * - Lower layers contain more nodes with shorter-range connections (for precision)
 * - Layer 0 contains all nodes
 *
 * Key operations:
 * 1. INSERT: Add a vector to the index at a randomly assigned layer
 * 2. SEARCH: Navigate from top layer down to find k nearest neighbors
 * 3. SELECT_NEIGHBORS: Choose which nodes to connect during insertion
 *
 * DISTRIBUTED CONSIDERATIONS:
 * ===========================
 * - Each node maintains a shard of the HNSW index
 * - Cross-shard searches require coordination via NodeService
 * - Graph connections may span across shards
 *
 * TODO: Implement the core algorithm methods marked with TODO comments
 */

#include <grpcpp/grpcpp.h>
#include <grpcpp/server.h>
#include <grpcpp/server_builder.h>
#include <grpcpp/server_context.h>

// TODO: Include generated proto headers
// #include "hnsw.grpc.pb.h"
// #include "node.grpc.pb.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <functional>
#include <iostream>
#include <memory>
#include <mutex>
#include <optional>
#include <queue>
#include <random>
#include <shared_mutex>
#include <sstream>
#include <string>
#include <thread>
#include <unordered_map>
#include <unordered_set>
#include <vector>

// ============================================================================
// Configuration Constants
// ============================================================================

namespace hnsw_config {
    // Maximum number of connections per node at layer 0
    constexpr size_t M = 16;

    // Maximum number of connections per node at layers > 0
    constexpr size_t M_MAX = 16;

    // Maximum number of connections per node at layer 0
    constexpr size_t M_MAX_0 = 32;

    // Size of dynamic candidate list during construction
    constexpr size_t EF_CONSTRUCTION = 200;

    // Size of dynamic candidate list during search
    constexpr size_t EF_SEARCH = 50;

    // Normalization factor for level generation (1/ln(M))
    constexpr double ML = 1.0 / std::log(16.0);

    // Default vector dimension
    constexpr size_t DEFAULT_DIMENSION = 128;
}

// ============================================================================
// Forward Declarations
// ============================================================================

class HNSWNode;
class HNSWIndex;
class HNSWServiceImpl;
class NodeServiceImpl;

// ============================================================================
// Data Structures
// ============================================================================

/**
 * Represents a single node in the HNSW graph
 *
 * Each node stores:
 * - A unique identifier
 * - The vector data
 * - Connections to neighbors at each layer
 */
class HNSWNode {
public:
    using NodeId = uint64_t;
    using Vector = std::vector<float>;
    using NeighborList = std::vector<NodeId>;

    HNSWNode(NodeId id, Vector vector, int max_layer)
        : id_(id)
        , vector_(std::move(vector))
        , max_layer_(max_layer)
        , neighbors_(max_layer + 1) {
    }

    ~HNSWNode() = default;

    // Getters
    NodeId getId() const { return id_; }
    const Vector& getVector() const { return vector_; }
    int getMaxLayer() const { return max_layer_; }

    // Thread-safe neighbor access
    NeighborList getNeighbors(int layer) const {
        std::shared_lock<std::shared_mutex> lock(mutex_);
        if (layer < 0 || layer > max_layer_) {
            return {};
        }
        return neighbors_[layer];
    }

    void setNeighbors(int layer, NeighborList neighbors) {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        if (layer >= 0 && layer <= max_layer_) {
            neighbors_[layer] = std::move(neighbors);
        }
    }

    void addNeighbor(int layer, NodeId neighbor_id) {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        if (layer >= 0 && layer <= max_layer_) {
            neighbors_[layer].push_back(neighbor_id);
        }
    }

private:
    NodeId id_;
    Vector vector_;
    int max_layer_;
    std::vector<NeighborList> neighbors_;
    mutable std::shared_mutex mutex_;
};

/**
 * Result of a distance calculation
 */
struct DistanceResult {
    HNSWNode::NodeId node_id;
    float distance;

    bool operator<(const DistanceResult& other) const {
        return distance < other.distance;
    }

    bool operator>(const DistanceResult& other) const {
        return distance > other.distance;
    }
};

/**
 * The main HNSW index structure
 *
 * Maintains:
 * - A map of all nodes (node_id -> HNSWNode)
 * - The entry point node (highest layer node)
 * - The current maximum layer in the index
 */
class HNSWIndex {
public:
    using NodeId = HNSWNode::NodeId;
    using Vector = HNSWNode::Vector;

    HNSWIndex(size_t dimension, size_t m = hnsw_config::M)
        : dimension_(dimension)
        , m_(m)
        , m_max_(hnsw_config::M_MAX)
        , m_max_0_(hnsw_config::M_MAX_0)
        , ef_construction_(hnsw_config::EF_CONSTRUCTION)
        , max_layer_(-1)
        , entry_point_(std::nullopt)
        , rng_(std::random_device{}())
        , level_dist_(hnsw_config::ML) {
    }

    ~HNSWIndex() = default;

    /**
     * Get index statistics
     */
    size_t size() const {
        std::shared_lock<std::shared_mutex> lock(index_mutex_);
        return nodes_.size();
    }

    size_t dimension() const { return dimension_; }
    int maxLayer() const { return max_layer_.load(); }

    /**
     * Get a node by ID
     */
    std::shared_ptr<HNSWNode> getNode(NodeId id) const {
        std::shared_lock<std::shared_mutex> lock(index_mutex_);
        auto it = nodes_.find(id);
        return (it != nodes_.end()) ? it->second : nullptr;
    }

    /**
     * Get the entry point node ID
     */
    std::optional<NodeId> getEntryPoint() const {
        std::shared_lock<std::shared_mutex> lock(index_mutex_);
        return entry_point_;
    }

    /**
     * Generate a random layer for a new node
     * Uses exponential distribution: floor(-ln(uniform(0,1)) * mL)
     */
    int generateRandomLayer() {
        std::unique_lock<std::shared_mutex> lock(level_mutex_);
        double r = level_dist_(rng_);
        return static_cast<int>(std::floor(r));
    }

    /**
     * Compute distance between two vectors
     *
     * TODO: This is a helper function - implement or use a library
     */
    float computeDistance(const Vector& a, const Vector& b) const {
        // TODO: Implement distance metric (L2, cosine, inner product)
        // Default: L2 (Euclidean) distance
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
     * Insert a vector into the HNSW index
     *
     * Algorithm:
     * 1. Generate random layer l for the new node
     * 2. If l > max_layer, set new entry point
     * 3. For each layer from max_layer down to l+1:
     *    - Search for 1 nearest neighbor (greedy)
     * 4. For each layer from min(l, max_layer) down to 0:
     *    - Search for ef_construction nearest neighbors
     *    - Select M neighbors using select_neighbors heuristic
     *    - Connect the new node to selected neighbors (bidirectional)
     *
     * @param id Unique identifier for the vector
     * @param vector The vector data to insert
     * @return true if insertion was successful
     */
    bool insert(NodeId id, Vector vector) {
        // TODO: Implement the HNSW insertion algorithm
        //
        // Step 1: Generate random layer for new node
        // int new_layer = generateRandomLayer();
        //
        // Step 2: Create the new node
        // auto new_node = std::make_shared<HNSWNode>(id, std::move(vector), new_layer);
        //
        // Step 3: If this is the first node, set as entry point
        // if (entry_point_ == std::nullopt) { ... }
        //
        // Step 4: Navigate from entry point down to new_layer + 1
        // NodeId current = entry_point_.value();
        // for (int layer = max_layer_; layer > new_layer; --layer) {
        //     current = searchLayer(new_node->getVector(), current, 1, layer)[0];
        // }
        //
        // Step 5: For layers min(new_layer, max_layer_) down to 0:
        // for (int layer = std::min(new_layer, max_layer_.load()); layer >= 0; --layer) {
        //     auto candidates = searchLayer(new_node->getVector(), current, ef_construction_, layer);
        //     auto neighbors = selectNeighbors(new_node->getVector(), candidates, m_layer, layer);
        //     // Connect new_node to neighbors (bidirectional)
        // }
        //
        // Step 6: Update entry point if new_layer > max_layer_

        std::unique_lock<std::shared_mutex> lock(index_mutex_);

        // Stub: Just store the node without proper graph construction
        int new_layer = generateRandomLayer();
        auto new_node = std::make_shared<HNSWNode>(id, std::move(vector), new_layer);
        nodes_[id] = new_node;

        if (!entry_point_.has_value()) {
            entry_point_ = id;
            max_layer_.store(new_layer);
        }

        return true;
    }

    /**
     * Search for k nearest neighbors
     *
     * Algorithm:
     * 1. Start from entry point at the top layer
     * 2. Greedily descend to layer 0, finding closest node at each layer
     * 3. At layer 0, expand search to find k nearest neighbors
     *
     * @param query The query vector
     * @param k Number of nearest neighbors to return
     * @param ef Size of dynamic candidate list (higher = more accurate but slower)
     * @return Vector of (node_id, distance) pairs, sorted by distance
     */
    std::vector<DistanceResult> searchKNN(const Vector& query, size_t k, size_t ef = 0) {
        // TODO: Implement the HNSW search algorithm
        //
        // if (ef == 0) ef = std::max(k, ef_search_);
        //
        // Step 1: Get entry point
        // auto ep = getEntryPoint();
        // if (!ep.has_value()) return {};
        //
        // Step 2: Traverse from top layer to layer 1
        // NodeId current = ep.value();
        // for (int layer = max_layer_; layer >= 1; --layer) {
        //     auto result = searchLayer(query, current, 1, layer);
        //     current = result[0].node_id;
        // }
        //
        // Step 3: Search layer 0 with expanded candidate list
        // auto candidates = searchLayer(query, current, ef, 0);
        //
        // Step 4: Return top-k results
        // std::sort(candidates.begin(), candidates.end());
        // if (candidates.size() > k) candidates.resize(k);
        // return candidates;

        std::vector<DistanceResult> results;

        std::shared_lock<std::shared_mutex> lock(index_mutex_);

        // Stub: Linear scan (inefficient - for template purposes only)
        for (const auto& [node_id, node] : nodes_) {
            float dist = computeDistance(query, node->getVector());
            results.push_back({node_id, dist});
        }

        std::sort(results.begin(), results.end());
        if (results.size() > k) {
            results.resize(k);
        }

        return results;
    }

    /**
     * Search within a single layer
     *
     * This is the core beam search operation used during both insertion and search.
     *
     * Algorithm (greedy search with beam width = ef):
     * 1. Initialize visited set and candidate min-heap
     * 2. Initialize result max-heap with entry point
     * 3. While candidates not empty:
     *    a. Pop closest candidate c
     *    b. If c is farther than the farthest result, stop
     *    c. For each neighbor of c at this layer:
     *       - If not visited, add to candidates and results
     *       - Prune results to size ef
     * 4. Return results
     *
     * @param query The query vector
     * @param entry_point Starting node for the search
     * @param ef Number of candidates to track
     * @param layer The layer to search
     * @return Vector of (node_id, distance) pairs
     */
    std::vector<DistanceResult> searchLayer(
        const Vector& query,
        NodeId entry_point,
        size_t ef,
        int layer
    ) {
        // TODO: Implement layer search algorithm
        //
        // std::unordered_set<NodeId> visited;
        //
        // // Min-heap for candidates (closest first)
        // std::priority_queue<DistanceResult, std::vector<DistanceResult>,
        //                     std::greater<DistanceResult>> candidates;
        //
        // // Max-heap for results (farthest first, for pruning)
        // std::priority_queue<DistanceResult> results;
        //
        // auto ep_node = getNode(entry_point);
        // float ep_dist = computeDistance(query, ep_node->getVector());
        //
        // candidates.push({entry_point, ep_dist});
        // results.push({entry_point, ep_dist});
        // visited.insert(entry_point);
        //
        // while (!candidates.empty()) {
        //     auto current = candidates.top();
        //     candidates.pop();
        //
        //     if (current.distance > results.top().distance) {
        //         break;  // All remaining candidates are farther
        //     }
        //
        //     auto current_node = getNode(current.node_id);
        //     for (NodeId neighbor_id : current_node->getNeighbors(layer)) {
        //         if (visited.count(neighbor_id)) continue;
        //         visited.insert(neighbor_id);
        //
        //         auto neighbor_node = getNode(neighbor_id);
        //         float dist = computeDistance(query, neighbor_node->getVector());
        //
        //         if (results.size() < ef || dist < results.top().distance) {
        //             candidates.push({neighbor_id, dist});
        //             results.push({neighbor_id, dist});
        //             if (results.size() > ef) results.pop();
        //         }
        //     }
        // }
        //
        // // Convert max-heap to sorted vector
        // std::vector<DistanceResult> result_vec;
        // while (!results.empty()) {
        //     result_vec.push_back(results.top());
        //     results.pop();
        // }
        // std::reverse(result_vec.begin(), result_vec.end());
        // return result_vec;

        // Stub implementation
        std::vector<DistanceResult> results;
        auto node = getNode(entry_point);
        if (node) {
            float dist = computeDistance(query, node->getVector());
            results.push_back({entry_point, dist});
        }
        return results;
    }

    /**
     * Select neighbors for a new node using the heuristic algorithm
     *
     * The simple approach just takes M closest candidates.
     * The heuristic approach (Algorithm 4 in the paper) considers diversity:
     * - Prefer candidates that are not only close to the query
     * - But also provide good coverage of different "directions"
     *
     * @param query The vector being inserted
     * @param candidates The candidate neighbors
     * @param m Maximum number of neighbors to select
     * @param layer The layer (affects m limit)
     * @return Selected neighbor IDs
     */
    std::vector<NodeId> selectNeighbors(
        const Vector& query,
        const std::vector<DistanceResult>& candidates,
        size_t m,
        int layer
    ) {
        // TODO: Implement neighbor selection heuristic
        //
        // Simple approach (select M closest):
        // auto sorted = candidates;
        // std::sort(sorted.begin(), sorted.end());
        //
        // std::vector<NodeId> selected;
        // for (size_t i = 0; i < std::min(m, sorted.size()); ++i) {
        //     selected.push_back(sorted[i].node_id);
        // }
        // return selected;
        //
        // Heuristic approach (Algorithm 4):
        // This provides better graph connectivity by considering:
        // - Diversity: don't just pick closest, pick neighbors that "cover" different areas
        // - For each candidate c, check if it's closer to query than to any already selected neighbor
        //
        // std::vector<NodeId> selected;
        // std::vector<DistanceResult> working = candidates;
        // std::sort(working.begin(), working.end());
        //
        // for (const auto& candidate : working) {
        //     if (selected.size() >= m) break;
        //
        //     bool should_add = true;
        //     auto candidate_node = getNode(candidate.node_id);
        //
        //     for (NodeId existing_id : selected) {
        //         auto existing_node = getNode(existing_id);
        //         float dist_to_existing = computeDistance(
        //             candidate_node->getVector(),
        //             existing_node->getVector()
        //         );
        //         if (dist_to_existing < candidate.distance) {
        //             should_add = false;
        //             break;
        //         }
        //     }
        //
        //     if (should_add) {
        //         selected.push_back(candidate.node_id);
        //     }
        // }
        // return selected;

        // Stub: Return first m candidates
        std::vector<NodeId> selected;
        for (size_t i = 0; i < std::min(m, candidates.size()); ++i) {
            selected.push_back(candidates[i].node_id);
        }
        return selected;
    }

private:
    size_t dimension_;
    size_t m_;
    size_t m_max_;
    size_t m_max_0_;
    size_t ef_construction_;

    std::atomic<int> max_layer_;
    std::optional<NodeId> entry_point_;

    std::unordered_map<NodeId, std::shared_ptr<HNSWNode>> nodes_;
    mutable std::shared_mutex index_mutex_;

    std::mt19937 rng_;
    std::exponential_distribution<double> level_dist_;
    mutable std::shared_mutex level_mutex_;
};

// ============================================================================
// gRPC Service Implementations
// ============================================================================

/**
 * Implementation of the HNSW gRPC service
 *
 * Handles vector operations: Insert, Search, Delete
 */
class HNSWServiceImpl final /* : public HNSWService::Service */ {
public:
    explicit HNSWServiceImpl(std::shared_ptr<HNSWIndex> index)
        : index_(std::move(index)) {
    }

    /**
     * Insert a vector into the index
     *
     * TODO: Implement proper proto request/response handling
     */
    grpc::Status InsertVector(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with InsertRequest*
        void* response        // TODO: Replace with InsertResponse*
    ) {
        // TODO: Implement InsertVector RPC
        //
        // 1. Parse vector from request
        // const auto& proto_vector = request->vector();
        // HNSWNode::Vector vector(proto_vector.begin(), proto_vector.end());
        //
        // 2. Call index insert
        // bool success = index_->insert(request->id(), std::move(vector));
        //
        // 3. Set response
        // response->set_success(success);

        return grpc::Status::OK;
    }

    /**
     * Search for k nearest neighbors
     *
     * TODO: Implement proper proto request/response handling
     */
    grpc::Status SearchKNN(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with SearchRequest*
        void* response        // TODO: Replace with SearchResponse*
    ) {
        // TODO: Implement SearchKNN RPC
        //
        // 1. Parse query vector from request
        // const auto& proto_query = request->query();
        // HNSWNode::Vector query(proto_query.begin(), proto_query.end());
        //
        // 2. Perform search
        // auto results = index_->searchKNN(query, request->k(), request->ef());
        //
        // 3. Build response
        // for (const auto& result : results) {
        //     auto* neighbor = response->add_neighbors();
        //     neighbor->set_id(result.node_id);
        //     neighbor->set_distance(result.distance);
        // }

        return grpc::Status::OK;
    }

    /**
     * Delete a vector from the index
     */
    grpc::Status DeleteVector(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with DeleteRequest*
        void* response        // TODO: Replace with DeleteResponse*
    ) {
        // TODO: Implement DeleteVector RPC
        // Note: HNSW deletion is complex - typically mark as deleted
        // and rebuild periodically

        return grpc::Status::OK;
    }

private:
    std::shared_ptr<HNSWIndex> index_;
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
     * Forward search to peer nodes (for distributed search)
     */
    grpc::Status ForwardSearch(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with ForwardSearchRequest*
        void* response        // TODO: Replace with ForwardSearchResponse*
    ) {
        // TODO: Implement distributed search forwarding
        //
        // 1. Parse the search request
        // 2. Search local index
        // 3. Optionally forward to peers if cross-shard search needed
        // 4. Merge results and respond

        return grpc::Status::OK;
    }

    /**
     * Sync graph state with peers
     */
    grpc::Status SyncGraph(
        grpc::ServerContext* context,
        const void* request,  // TODO: Replace with SyncRequest*
        void* response        // TODO: Replace with SyncResponse*
    ) {
        // TODO: Implement graph synchronization
        // For maintaining consistency across shards

        return grpc::Status::OK;
    }

private:
    std::string node_id_;
    std::vector<std::string> peer_addresses_;

    // TODO: Add gRPC stubs for peer communication
    // std::vector<std::unique_ptr<NodeService::Stub>> peer_stubs_;
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
    size_t dimension = hnsw_config::DEFAULT_DIMENSION;

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
            } else if (arg == "--help") {
                std::cout << "Usage: " << argv[0] << " [options]\n"
                          << "Options:\n"
                          << "  --node-id ID      Node identifier (default: node-1)\n"
                          << "  --port PORT       Port to listen on (default: 50051)\n"
                          << "  --peer ADDR       Peer address (can be repeated)\n"
                          << "  --dimension DIM   Vector dimension (default: 128)\n"
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
    // Create the HNSW index
    auto index = std::make_shared<HNSWIndex>(config.dimension);

    // Create service implementations
    HNSWServiceImpl hnsw_service(index);
    NodeServiceImpl node_service(config.node_id, config.peers);

    // Build and start server
    grpc::ServerBuilder builder;

    std::string server_address = "0.0.0.0:" + std::to_string(config.port);
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());

    // TODO: Register services with builder
    // builder.RegisterService(&hnsw_service);
    // builder.RegisterService(&node_service);

    std::unique_ptr<grpc::Server> server(builder.BuildAndStart());

    std::cout << "HNSW Server [" << config.node_id << "] listening on "
              << server_address << std::endl;
    std::cout << "Index dimension: " << config.dimension << std::endl;
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
 * PROTO FILE SUGGESTIONS (hnsw.proto):
 * ====================================
 *
 * syntax = "proto3";
 *
 * service HNSWService {
 *     rpc InsertVector(InsertRequest) returns (InsertResponse);
 *     rpc SearchKNN(SearchRequest) returns (SearchResponse);
 *     rpc DeleteVector(DeleteRequest) returns (DeleteResponse);
 * }
 *
 * message InsertRequest {
 *     uint64 id = 1;
 *     repeated float vector = 2;
 * }
 *
 * message InsertResponse {
 *     bool success = 1;
 *     string error_message = 2;
 * }
 *
 * message SearchRequest {
 *     repeated float query = 1;
 *     uint32 k = 2;
 *     uint32 ef = 3;
 * }
 *
 * message SearchResponse {
 *     repeated Neighbor neighbors = 1;
 * }
 *
 * message Neighbor {
 *     uint64 id = 1;
 *     float distance = 2;
 * }
 *
 *
 * TESTING SUGGESTIONS:
 * ====================
 * 1. Unit test distance computation
 * 2. Test layer generation distribution
 * 3. Test insert/search with small datasets
 * 4. Benchmark with standard datasets (SIFT, GloVe)
 * 5. Test distributed coordination between nodes
 *
 *
 * OPTIMIZATION OPPORTUNITIES:
 * ===========================
 * 1. SIMD vectorization for distance computation
 * 2. Memory-mapped storage for large indices
 * 3. Lock-free data structures for concurrent access
 * 4. Prefetching for cache optimization
 * 5. Quantization for memory reduction
 */
