/**
 * Sliding Window Log Rate Limiter - C++ Template
 *
 * This template provides the basic structure for implementing the Sliding Window
 * Log rate limiting algorithm. You need to implement the TODO sections.
 *
 * The sliding window log algorithm works by:
 * 1. Each request's timestamp is stored in a sorted log
 * 2. When a request arrives, remove entries older than the window
 * 3. Count remaining entries; if under limit, allow and add new entry
 * 4. Provides precise rate limiting with no boundary issues
 *
 * Trade-off: More memory usage (stores all timestamps) but more accurate
 *
 * Usage:
 *     ./server --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <list>
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
#include "sliding_window_log.grpc.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;
using grpc::Channel;
using grpc::ClientContext;

namespace sliding_window_log {

/**
 * Log entry representing a single request timestamp.
 */
struct LogEntryItem {
    int64_t timestamp;          // Request timestamp in milliseconds
    std::string request_id;     // Optional request identifier
};

/**
 * Log state for a single rate limit.
 * Stores configuration and timestamp log.
 */
struct Log {
    std::string limit_id;
    uint64_t window_size_ms;    // Window size in milliseconds
    uint64_t max_requests;      // Maximum requests per window
    std::list<LogEntryItem> entries; // Timestamps within current window (sorted)
    uint64_t total_requests;    // Total requests across all time
    uint64_t total_allowed;     // Total requests allowed
    uint64_t total_rejected;    // Total requests rejected
};

/**
 * Sliding Window Log Rate Limiter implementation.
 *
 * TODO: Implement the core sliding window log algorithm:
 * 1. Maintain sorted log of request timestamps
 * 2. Prune expired entries on each request
 * 3. Distributed synchronization between nodes
 */
class SlidingWindowLogRateLimiter final : public RateLimiterService::Service,
                                           public NodeService::Service {
public:
    SlidingWindowLogRateLimiter(const std::string& node_id, int port, const std::vector<std::string>& peers)
        : node_id_(node_id), port_(port), peers_(peers), is_leader_(false) {
    }

    ~SlidingWindowLogRateLimiter() = default;

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
     * Remove expired entries from the log.
     *
     * TODO: Implement log cleanup
     * 1. Calculate the cutoff time (current_time - window_size_ms)
     * 2. Remove all entries with timestamp < cutoff
     */
    void PruneExpiredEntries(Log& log, int64_t current_time) {
        // TODO: Implement log pruning
        // 1. Calculate cutoff = current_time - window_size_ms
        // 2. Remove entries from front of list where timestamp < cutoff
        // (entries are sorted, so remove from front until finding valid entry)
    }

    /**
     * Try to add a request to the log.
     *
     * TODO: Implement request addition
     * 1. Prune expired entries first
     * 2. Check if adding request would exceed max_requests
     * 3. If yes, reject; if no, add entry to log
     */
    bool TryAddEntry(Log& log, const std::string& request_id, int64_t timestamp) {
        // TODO: Implement entry addition
        // 1. If timestamp is 0, use current time
        // 2. Call PruneExpiredEntries
        // 3. Check if entries.size() < max_requests
        // 4. If yes, add new entry and return true
        // 5. If no, return false
        return false;  // Stub
    }

    /**
     * Get the oldest entry timestamp in the log.
     *
     * TODO: Implement oldest entry lookup
     * Returns 0 if log is empty.
     */
    int64_t GetOldestEntryTimestamp(const Log& log) {
        // TODO: Implement oldest entry lookup
        // Return the timestamp of the first entry in the list
        // Return 0 if empty
        return 0;  // Stub
    }

    // --- RateLimiterService RPC Implementations ---

    /**
     * Handle AllowRequest RPC - check if a request should be allowed.
     *
     * TODO: Implement the main rate limiting logic:
     * 1. Find or create the log
     * 2. Try to add entry to log
     * 3. Return result with current count and remaining
     */
    Status AllowRequest(ServerContext* context,
                        const AllowRequestRequest* request,
                        AllowRequestResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement AllowRequest
        // 1. Get limit_id from request
        // 2. Find log or return error if not found
        // 3. Get timestamp (use current time if 0)
        // 4. Call TryAddEntry
        // 5. Set response fields: allowed, current_count, remaining, oldest_entry
        // 6. Update log statistics

        response->set_allowed(false);
        response->set_error("Not implemented");
        response->set_served_by(node_id_);

        return Status::OK;
    }

    /**
     * Handle GetLogStatus RPC - return current log state.
     */
    Status GetLogStatus(ServerContext* context,
                        const GetLogStatusRequest* request,
                        GetLogStatusResponse* response) override {
        (void)context;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        auto it = logs_.find(request->limit_id());
        if (it == logs_.end()) {
            response->set_found(false);
            response->set_error("Log not found");
            return Status::OK;
        }

        // TODO: Implement GetLogStatus
        // 1. Prune expired entries first
        // 2. Copy log state to response
        // 3. If include_entries is true, add all entries to response

        response->set_found(true);
        return Status::OK;
    }

    /**
     * Handle ConfigureLimit RPC - create or update a rate limit.
     *
     * TODO: Implement limit configuration:
     * 1. Create new log or update existing
     * 2. Initialize with max_requests and window_size_ms
     * 3. Sync to peer nodes
     */
    Status ConfigureLimit(ServerContext* context,
                          const ConfigureLimitRequest* request,
                          ConfigureLimitResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement ConfigureLimit
        // 1. Check if log exists and if overwrite is allowed
        // 2. Create or update log with config
        // 3. Clear entries list if new
        // 4. Sync to peers if distributed

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

        auto it = logs_.find(request->limit_id());
        if (it == logs_.end()) {
            response->set_success(false);
            response->set_error("Limit not found");
            return Status::OK;
        }

        logs_.erase(it);
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
        response->set_total_limits(logs_.size());

        uint64_t total_entries = 0;
        uint64_t total_requests = 0;
        for (const auto& [id, log] : logs_) {
            total_entries += log.entries.size();
            total_requests += log.total_requests;
        }
        response->set_total_log_entries(total_entries);
        response->set_total_requests_processed(total_requests);

        return Status::OK;
    }

    // --- NodeService RPC Implementations ---

    /**
     * Handle SyncLog RPC - sync log state from another node.
     *
     * TODO: Implement log synchronization
     * 1. Receive log state from peer
     * 2. Merge entries (union of all timestamps)
     */
    Status SyncLog(ServerContext* context,
                   const SyncLogRequest* request,
                   SyncLogResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement SyncLog
        // 1. Get log state from request
        // 2. If log exists locally, merge entries (sorted union)
        // 3. If log doesn't exist, create it

        response->set_success(false);
        response->set_error("Not implemented");

        return Status::OK;
    }

    /**
     * Handle AddEntry RPC - add a timestamp entry across nodes.
     *
     * TODO: Implement distributed entry addition
     * 1. Add entry to local log
     * 2. Prune expired entries
     */
    Status AddEntry(ServerContext* context,
                    const AddEntryRequest* request,
                    AddEntryResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement AddEntry
        // 1. Find log by limit_id
        // 2. Add entry to log
        // 3. Prune expired entries
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
     * Handle GetLocalLogs RPC - return all local logs.
     */
    Status GetLocalLogs(ServerContext* context,
                        const GetLocalLogsRequest* request,
                        GetLocalLogsResponse* response) override {
        (void)context;
        (void)request;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement GetLocalLogs
        // 1. Iterate through all logs
        // 2. Add each log state to response

        response->set_total_count(logs_.size());

        return Status::OK;
    }

private:
    std::string node_id_;
    int port_;
    std::vector<std::string> peers_;
    bool is_leader_;

    // Log storage: limit_id -> Log
    std::map<std::string, Log> logs_;

    // Thread safety
    mutable std::shared_mutex mutex_;

    // Peer connections
    std::map<std::string, std::unique_ptr<NodeService::Stub>> peer_stubs_;
};

}  // namespace sliding_window_log

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

    sliding_window_log::SlidingWindowLogRateLimiter limiter(node_id, port, peers);
    limiter.Initialize();

    std::string server_address = "0.0.0.0:" + std::to_string(port);
    ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
    builder.RegisterService(static_cast<sliding_window_log::RateLimiterService::Service*>(&limiter));
    builder.RegisterService(static_cast<sliding_window_log::NodeService::Service*>(&limiter));

    std::unique_ptr<Server> server(builder.BuildAndStart());
    std::cout << "Sliding Window Log Rate Limiter " << node_id << " listening on port " << port << std::endl;

    server->Wait();
    return 0;
}
