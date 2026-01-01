/**
 * Token Bucket Rate Limiter - C++ Template
 *
 * This template provides the basic structure for implementing the Token Bucket
 * rate limiting algorithm. You need to implement the TODO sections.
 *
 * The token bucket algorithm works by:
 * 1. A bucket holds tokens up to a maximum capacity
 * 2. Tokens are added at a fixed rate (refill rate)
 * 3. Each request consumes one or more tokens
 * 4. If insufficient tokens, the request is rejected or queued
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
#include "token_bucket.grpc.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;
using grpc::Channel;
using grpc::ClientContext;

namespace token_bucket {

/**
 * Token Bucket state for a single bucket.
 * Stores configuration and current token count.
 */
struct Bucket {
    std::string bucket_id;
    double current_tokens;      // Current number of tokens (can be fractional)
    uint64_t capacity;          // Maximum tokens the bucket can hold
    double refill_rate;         // Tokens added per second
    int64_t last_refill_time;   // Unix timestamp in milliseconds
    uint64_t total_requests;    // Total requests received
    uint64_t allowed_requests;  // Total requests allowed
    uint64_t rejected_requests; // Total requests rejected
};

/**
 * Token Bucket Rate Limiter implementation.
 *
 * TODO: Implement the core token bucket algorithm:
 * 1. Token refill based on elapsed time
 * 2. Token consumption for requests
 * 3. Distributed synchronization between nodes
 */
class TokenBucketRateLimiter final : public RateLimiterService::Service,
                                      public NodeService::Service {
public:
    TokenBucketRateLimiter(const std::string& node_id, int port, const std::vector<std::string>& peers)
        : node_id_(node_id), port_(port), peers_(peers), is_leader_(false) {
    }

    ~TokenBucketRateLimiter() = default;

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
     * Refill tokens for a bucket based on elapsed time.
     *
     * TODO: Implement token refill logic
     * 1. Calculate elapsed time since last refill
     * 2. Calculate tokens to add: elapsed_seconds * refill_rate
     * 3. Add tokens up to capacity (don't exceed)
     * 4. Update last_refill_time
     */
    void RefillTokens(Bucket& bucket) {
        // TODO: Implement token refill
        // 1. Get current time
        // 2. Calculate elapsed time since last_refill_time
        // 3. Calculate new tokens: elapsed_seconds * refill_rate
        // 4. Update current_tokens (capped at capacity)
        // 5. Update last_refill_time
    }

    /**
     * Try to consume tokens from a bucket.
     *
     * TODO: Implement token consumption
     * 1. First refill tokens based on elapsed time
     * 2. Check if enough tokens are available
     * 3. If yes, consume tokens and return true
     * 4. If no, return false
     */
    bool TryConsumeTokens(Bucket& bucket, uint64_t tokens_requested) {
        // TODO: Implement token consumption
        // 1. Call RefillTokens first
        // 2. Check if current_tokens >= tokens_requested
        // 3. If yes, subtract tokens and return true
        // 4. If no, return false
        return false;  // Stub
    }

    /**
     * Calculate retry delay when tokens are insufficient.
     *
     * TODO: Implement retry delay calculation
     * Returns the time in milliseconds until enough tokens will be available.
     */
    uint64_t CalculateRetryAfterMs(const Bucket& bucket, uint64_t tokens_needed) {
        // TODO: Implement retry delay calculation
        // 1. Calculate tokens deficit: tokens_needed - current_tokens
        // 2. Calculate time to refill: deficit / refill_rate
        // 3. Convert to milliseconds and return
        return 1000;  // Stub: default 1 second
    }

    // --- RateLimiterService RPC Implementations ---

    /**
     * Handle AllowRequest RPC - check if a request should be allowed.
     *
     * TODO: Implement the main rate limiting logic:
     * 1. Find or create the bucket
     * 2. Try to consume tokens
     * 3. Return result with remaining tokens and retry info
     */
    Status AllowRequest(ServerContext* context,
                        const AllowRequestRequest* request,
                        AllowRequestResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement AllowRequest
        // 1. Get bucket_id from request
        // 2. Find bucket or return error if not found
        // 3. Get tokens_requested (default to 1)
        // 4. Call TryConsumeTokens
        // 5. Set response fields: allowed, tokens_remaining, retry_after_ms
        // 6. Update bucket statistics

        response->set_allowed(false);
        response->set_error("Not implemented");
        response->set_served_by(node_id_);

        return Status::OK;
    }

    /**
     * Handle GetBucketStatus RPC - return current bucket state.
     */
    Status GetBucketStatus(ServerContext* context,
                           const GetBucketStatusRequest* request,
                           GetBucketStatusResponse* response) override {
        (void)context;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        auto it = buckets_.find(request->bucket_id());
        if (it == buckets_.end()) {
            response->set_found(false);
            response->set_error("Bucket not found");
            return Status::OK;
        }

        // TODO: Implement GetBucketStatus
        // 1. Refill tokens first (to get accurate count)
        // 2. Copy bucket state to response

        response->set_found(true);
        return Status::OK;
    }

    /**
     * Handle ConfigureBucket RPC - create or update a bucket.
     *
     * TODO: Implement bucket configuration:
     * 1. Create new bucket or update existing
     * 2. Initialize with capacity and refill rate
     * 3. Sync to peer nodes
     */
    Status ConfigureBucket(ServerContext* context,
                           const ConfigureBucketRequest* request,
                           ConfigureBucketResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement ConfigureBucket
        // 1. Check if bucket exists and if overwrite is allowed
        // 2. Create or update bucket with config
        // 3. Initialize tokens (use initial_tokens or capacity)
        // 4. Set last_refill_time to current time
        // 5. Sync to peers if distributed

        response->set_success(false);
        response->set_error("Not implemented");

        return Status::OK;
    }

    /**
     * Handle DeleteBucket RPC - remove a bucket.
     */
    Status DeleteBucket(ServerContext* context,
                        const DeleteBucketRequest* request,
                        DeleteBucketResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement DeleteBucket
        // 1. Find and remove bucket
        // 2. Sync deletion to peers

        auto it = buckets_.find(request->bucket_id());
        if (it == buckets_.end()) {
            response->set_success(false);
            response->set_error("Bucket not found");
            return Status::OK;
        }

        buckets_.erase(it);
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
        response->set_healthy_nodes(peers_.size() + 1);  // TODO: Track actual health
        response->set_total_buckets(buckets_.size());

        uint64_t total_requests = 0;
        for (const auto& [id, bucket] : buckets_) {
            total_requests += bucket.total_requests;
        }
        response->set_total_requests_processed(total_requests);

        return Status::OK;
    }

    // --- NodeService RPC Implementations ---

    /**
     * Handle SyncBucket RPC - sync bucket state from another node.
     *
     * TODO: Implement bucket synchronization
     * 1. Receive bucket state from peer
     * 2. Merge with local state (use lower token count for safety)
     */
    Status SyncBucket(ServerContext* context,
                      const SyncBucketRequest* request,
                      SyncBucketResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement SyncBucket
        // 1. Get bucket state from request
        // 2. If bucket exists locally, merge states
        // 3. If bucket doesn't exist, create it
        // 4. Use minimum token count for consistency

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
     * Handle GetLocalBuckets RPC - return all local buckets.
     */
    Status GetLocalBuckets(ServerContext* context,
                           const GetLocalBucketsRequest* request,
                           GetLocalBucketsResponse* response) override {
        (void)context;
        (void)request;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement GetLocalBuckets
        // 1. Iterate through all buckets
        // 2. Add each bucket state to response

        response->set_total_count(buckets_.size());

        return Status::OK;
    }

private:
    std::string node_id_;
    int port_;
    std::vector<std::string> peers_;
    bool is_leader_;

    // Bucket storage: bucket_id -> Bucket
    std::map<std::string, Bucket> buckets_;

    // Thread safety
    mutable std::shared_mutex mutex_;

    // Peer connections
    std::map<std::string, std::unique_ptr<NodeService::Stub>> peer_stubs_;
};

}  // namespace token_bucket

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

    token_bucket::TokenBucketRateLimiter limiter(node_id, port, peers);
    limiter.Initialize();

    std::string server_address = "0.0.0.0:" + std::to_string(port);
    ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
    builder.RegisterService(static_cast<token_bucket::RateLimiterService::Service*>(&limiter));
    builder.RegisterService(static_cast<token_bucket::NodeService::Service*>(&limiter));

    std::unique_ptr<Server> server(builder.BuildAndStart());
    std::cout << "Token Bucket Rate Limiter " << node_id << " listening on port " << port << std::endl;

    server->Wait();
    return 0;
}
