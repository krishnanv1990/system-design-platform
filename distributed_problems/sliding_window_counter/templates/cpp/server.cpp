/**
 * Sliding Window Counter Rate Limiter - C++ Template
 *
 * This template provides the basic structure for implementing the Sliding Window
 * Counter rate limiting algorithm. You need to implement the TODO sections.
 *
 * The sliding window counter algorithm is a hybrid approach:
 * 1. Combines fixed window counter with sliding window
 * 2. Maintains counters for current and previous windows
 * 3. Uses weighted average based on position in current window
 * 4. Formula: count = prev_count * (1 - elapsed/window) + curr_count
 *
 * Trade-off: Low memory (only 2 counters) with good accuracy
 *
 * Usage:
 *     ./server --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <memory>
#include <mutex>
#include <shared_mutex>
#include <chrono>
#include <thread>
#include <atomic>
#include <sstream>
#include <algorithm>
#include <cmath>

#include <grpcpp/grpcpp.h>
#include "sliding_window_counter.grpc.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;
using grpc::Channel;
using grpc::ClientContext;

namespace sliding_window_counter {

/**
 * Window state for a single rate limit.
 * Stores configuration and counters for current and previous windows.
 */
struct Window {
    std::string limit_id;
    uint64_t window_size_ms;    // Window size in milliseconds
    uint64_t max_requests;      // Maximum requests per window

    // Current window
    int64_t current_window_start; // Current window start timestamp (ms)
    uint64_t current_count;     // Count in current window

    // Previous window
    int64_t previous_window_start; // Previous window start timestamp (ms)
    uint64_t previous_count;    // Count in previous window

    // Statistics
    uint64_t total_requests;    // Total requests across all time
    uint64_t total_allowed;     // Total requests allowed
    uint64_t total_rejected;    // Total requests rejected
};

/**
 * Sliding Window Counter Rate Limiter implementation.
 *
 * TODO: Implement the core sliding window counter algorithm:
 * 1. Maintain current and previous window counters
 * 2. Calculate weighted sliding estimate
 * 3. Distributed synchronization between nodes
 */
class SlidingWindowCounterRateLimiter final : public RateLimiterService::Service,
                                               public NodeService::Service {
public:
    SlidingWindowCounterRateLimiter(const std::string& node_id, int port, const std::vector<std::string>& peers)
        : node_id_(node_id), port_(port), peers_(peers), is_leader_(false) {
    }

    ~SlidingWindowCounterRateLimiter() = default;

    void Initialize() {
        // Initialize connections to peer nodes
        for (const auto& peer : peers_) {
            auto channel = grpc::CreateChannel(peer, grpc::InsecureChannelCredentials());
            peer_stubs_[peer] = NodeService::NewStub(channel);
            std::cout << "Connected to peer: " << peer << std::endl;
        }
        std::cout << "Node " << node_id_ << " initialized with " << peers_.size() << " peers" << std::endl;
    }

    // --- Helper Methods ---

    /**
     * Get current time in milliseconds.
     */
    int64_t GetCurrentTimeMs() const {
        return std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()
        ).count();
    }

    /**
     * Calculate window start time for a given timestamp.
     *
     * TODO: Implement window start calculation
     * Returns the start time of the window that contains the given timestamp.
     */
    int64_t CalculateWindowStart(int64_t timestamp_ms, uint64_t window_size_ms) {
        // TODO: Implement window start calculation
        // Formula: floor(timestamp / window_size) * window_size
        return 0;  // Stub
    }

    /**
     * Update window state based on current time.
     *
     * TODO: Implement window transition logic
     * 1. Calculate current window start
     * 2. If we're in a new window:
     *    - Shift current to previous
     *    - Reset current counter
     * 3. If we're two or more windows ahead:
     *    - Clear both counters
     */
    void UpdateWindowState(Window& window, int64_t current_time) {
        // TODO: Implement window state update
        // 1. Calculate new_window_start = CalculateWindowStart(current_time, window_size_ms)
        // 2. If new_window_start == current_window_start: no change needed
        // 3. If new_window_start == current_window_start + window_size_ms:
        //    - previous_count = current_count
        //    - previous_window_start = current_window_start
        //    - current_count = 0
        //    - current_window_start = new_window_start
        // 4. If new_window_start > current_window_start + window_size_ms:
        //    - previous_count = 0
        //    - current_count = 0
        //    - Update window starts
    }

    /**
     * Calculate the sliding window estimate.
     *
     * TODO: Implement sliding estimate calculation
     * Formula: prev_count * (1 - elapsed_ratio) + curr_count
     * where elapsed_ratio = (current_time - current_window_start) / window_size_ms
     */
    double CalculateSlidingEstimate(const Window& window, int64_t current_time) {
        // TODO: Implement sliding estimate
        // 1. Calculate elapsed time in current window
        // 2. Calculate elapsed_ratio = elapsed / window_size_ms (0.0 to 1.0)
        // 3. Calculate weight for previous window = (1 - elapsed_ratio)
        // 4. Return: previous_count * weight + current_count
        return 0.0;  // Stub
    }

    /**
     * Try to increment the counter for a request.
     *
     * TODO: Implement request handling
     * 1. Update window state
     * 2. Calculate sliding estimate
     * 3. Check if adding cost would exceed max_requests
     * 4. If yes, reject; if no, increment current counter
     */
    bool TryIncrement(Window& window, uint64_t cost, int64_t timestamp) {
        // TODO: Implement request handling
        // 1. If timestamp is 0, use current time
        // 2. Call UpdateWindowState
        // 3. Calculate sliding estimate
        // 4. Check if estimate + cost <= max_requests
        // 5. If yes, increment current_count and return true
        // 6. If no, return false
        return false;  // Stub
    }

    // --- RateLimiterService RPC Implementations ---

    /**
     * Handle AllowRequest RPC - check if a request should be allowed.
     *
     * TODO: Implement the main rate limiting logic:
     * 1. Find or create the window
     * 2. Try to increment counter
     * 3. Return result with sliding count and remaining
     */
    Status AllowRequest(ServerContext* context,
                        const AllowRequestRequest* request,
                        AllowRequestResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement AllowRequest
        // 1. Get limit_id from request
        // 2. Find window or return error if not found
        // 3. Get cost (default to 1) and timestamp
        // 4. Call TryIncrement
        // 5. Calculate sliding_count
        // 6. Set response fields: allowed, sliding_count, remaining, reset_at
        // 7. Update window statistics

        response->set_allowed(false);
        response->set_error("Not implemented");
        response->set_served_by(node_id_);

        return Status::OK;
    }

    /**
     * Handle GetWindowStatus RPC - return current window state.
     */
    Status GetWindowStatus(ServerContext* context,
                           const GetWindowStatusRequest* request,
                           GetWindowStatusResponse* response) override {
        (void)context;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        auto it = windows_.find(request->limit_id());
        if (it == windows_.end()) {
            response->set_found(false);
            response->set_error("Window not found");
            return Status::OK;
        }

        // TODO: Implement GetWindowStatus
        // 1. Update window state first
        // 2. Calculate sliding estimate
        // 3. Copy window state to response

        response->set_found(true);
        return Status::OK;
    }

    /**
     * Handle ConfigureLimit RPC - create or update a rate limit.
     *
     * TODO: Implement limit configuration:
     * 1. Create new window or update existing
     * 2. Initialize with max_requests and window_size_ms
     * 3. Sync to peer nodes
     */
    Status ConfigureLimit(ServerContext* context,
                          const ConfigureLimitRequest* request,
                          ConfigureLimitResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement ConfigureLimit
        // 1. Check if window exists and if overwrite is allowed
        // 2. Create or update window with config
        // 3. Initialize window starts to current window
        // 4. Reset both counters to 0
        // 5. Sync to peers if distributed

        response->set_success(false);
        response->set_error("Not implemented");

        return Status::OK;
    }

    /**
     * Handle DeleteLimit RPC - remove a rate limit.
     */
    Status DeleteLimit(ServerContext* context,
                       const DeleteLimitRequest* request,
                       DeleteLimitResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        auto it = windows_.find(request->limit_id());
        if (it == windows_.end()) {
            response->set_success(false);
            response->set_error("Limit not found");
            return Status::OK;
        }

        windows_.erase(it);
        response->set_success(true);
        return Status::OK;
    }

    /**
     * Handle GetLeader RPC - return leader information.
     */
    Status GetLeader(ServerContext* context,
                     const GetLeaderRequest* request,
                     GetLeaderResponse* response) override {
        (void)context;
        (void)request;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        response->set_node_id(node_id_);
        response->set_node_address("localhost:" + std::to_string(port_));
        response->set_is_leader(is_leader_);

        return Status::OK;
    }

    /**
     * Handle GetClusterStatus RPC - return cluster health.
     */
    Status GetClusterStatus(ServerContext* context,
                            const GetClusterStatusRequest* request,
                            GetClusterStatusResponse* response) override {
        (void)context;
        (void)request;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        response->set_node_id(node_id_);
        response->set_node_address("localhost:" + std::to_string(port_));
        response->set_is_leader(is_leader_);
        response->set_total_nodes(peers_.size() + 1);
        response->set_healthy_nodes(peers_.size() + 1);
        response->set_total_limits(windows_.size());

        uint64_t total_requests = 0;
        for (const auto& [id, window] : windows_) {
            total_requests += window.total_requests;
        }
        response->set_total_requests_processed(total_requests);

        return Status::OK;
    }

    // --- NodeService RPC Implementations ---

    /**
     * Handle SyncWindow RPC - sync window state from another node.
     *
     * TODO: Implement window synchronization
     * 1. Receive window state from peer
     * 2. Merge counters (use max for same windows)
     */
    Status SyncWindow(ServerContext* context,
                      const SyncWindowRequest* request,
                      SyncWindowResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement SyncWindow
        // 1. Get window state from request
        // 2. If window exists locally and windows match, take max of counts
        // 3. If window doesn't exist, create it

        response->set_success(false);
        response->set_error("Not implemented");

        return Status::OK;
    }

    /**
     * Handle IncrementCounter RPC - atomically increment counter.
     *
     * TODO: Implement distributed counter increment
     * 1. Verify window_start matches current window
     * 2. Atomically increment current counter
     */
    Status IncrementCounter(ServerContext* context,
                            const IncrementCounterRequest* request,
                            IncrementCounterResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement IncrementCounter
        // 1. Find window by limit_id
        // 2. Verify window_start matches current window
        // 3. Increment current_count
        // 4. Return new count

        response->set_success(false);
        response->set_error("Not implemented");

        return Status::OK;
    }

    /**
     * Handle Heartbeat RPC - health check from peer.
     */
    Status Heartbeat(ServerContext* context,
                     const HeartbeatRequest* request,
                     HeartbeatResponse* response) override {
        (void)context;
        (void)request;

        response->set_acknowledged(true);
        response->set_timestamp(GetCurrentTimeMs());

        return Status::OK;
    }

    /**
     * Handle GetLocalWindows RPC - return all local windows.
     */
    Status GetLocalWindows(ServerContext* context,
                           const GetLocalWindowsRequest* request,
                           GetLocalWindowsResponse* response) override {
        (void)context;
        (void)request;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement GetLocalWindows
        // 1. Iterate through all windows
        // 2. Add each window state to response

        response->set_total_count(windows_.size());

        return Status::OK;
    }

private:
    std::string node_id_;
    int port_;
    std::vector<std::string> peers_;
    bool is_leader_;

    // Window storage: limit_id -> Window
    std::map<std::string, Window> windows_;

    // Thread safety
    mutable std::shared_mutex mutex_;

    // Peer connections
    std::map<std::string, std::unique_ptr<NodeService::Stub>> peer_stubs_;
};

}  // namespace sliding_window_counter

// Helper function to split string by delimiter
std::vector<std::string> split(const std::string& s, char delimiter) {
    std::vector<std::string> tokens;
    std::string token;
    std::istringstream tokenStream(s);
    while (std::getline(tokenStream, token, delimiter)) {
        token.erase(0, token.find_first_not_of(" \t"));
        token.erase(token.find_last_not_of(" \t") + 1);
        if (!token.empty()) {
            tokens.push_back(token);
        }
    }
    return tokens;
}

int main(int argc, char** argv) {
    std::string node_id;
    int port = 50051;
    std::string peers_str;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--node-id" && i + 1 < argc) {
            node_id = argv[++i];
        } else if (arg == "--port" && i + 1 < argc) {
            port = std::stoi(argv[++i]);
        } else if (arg == "--peers" && i + 1 < argc) {
            peers_str = argv[++i];
        }
    }

    if (node_id.empty()) {
        std::cerr << "Usage: " << argv[0]
                  << " --node-id <id> --port <port> [--peers <peer1:port1,peer2:port2>]"
                  << std::endl;
        return 1;
    }

    std::vector<std::string> peers;
    if (!peers_str.empty()) {
        peers = split(peers_str, ',');
    }

    sliding_window_counter::SlidingWindowCounterRateLimiter limiter(node_id, port, peers);
    limiter.Initialize();

    std::string server_address = "0.0.0.0:" + std::to_string(port);
    ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
    builder.RegisterService(static_cast<sliding_window_counter::RateLimiterService::Service*>(&limiter));
    builder.RegisterService(static_cast<sliding_window_counter::NodeService::Service*>(&limiter));

    std::unique_ptr<Server> server(builder.BuildAndStart());
    std::cout << "Sliding Window Counter Rate Limiter " << node_id << " listening on port " << port << std::endl;

    server->Wait();
    return 0;
}
