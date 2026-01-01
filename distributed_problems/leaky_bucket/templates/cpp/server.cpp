/**
 * Leaky Bucket Rate Limiter - C++ Template
 *
 * This template provides the basic structure for implementing the Leaky Bucket
 * rate limiting algorithm. You need to implement the TODO sections.
 *
 * The leaky bucket algorithm works by:
 * 1. Requests enter a queue (bucket) with fixed capacity
 * 2. Requests are processed (leak) at a constant rate
 * 3. If the bucket is full, new requests are rejected
 * 4. Provides smooth, consistent output rate
 *
 * Usage:
 *     ./server --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <queue>
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
#include "leaky_bucket.grpc.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;
using grpc::Channel;
using grpc::ClientContext;

namespace leaky_bucket {

/**
 * Queued request waiting in the bucket.
 */
struct QueuedRequestItem {
    std::string request_id;
    int64_t enqueue_time;       // When the request was queued
    int64_t estimated_process_time; // When it will be processed
};

/**
 * Leaky Bucket state for a single bucket.
 * Stores configuration and queue state.
 */
struct Bucket {
    std::string bucket_id;
    uint64_t capacity;          // Maximum queue size
    double leak_rate;           // Requests processed per second
    int64_t last_leak_time;     // Unix timestamp in milliseconds
    uint64_t total_requests;    // Total requests received
    uint64_t allowed_requests;  // Total requests queued
    uint64_t rejected_requests; // Total requests rejected (overflow)
    uint64_t processed_requests; // Total requests leaked/processed
    std::queue<QueuedRequestItem> queue; // Request queue
};

/**
 * Leaky Bucket Rate Limiter implementation.
 *
 * TODO: Implement the core leaky bucket algorithm:
 * 1. Queue management with capacity limits
 * 2. Leak (process) requests at constant rate
 * 3. Distributed synchronization between nodes
 */
class LeakyBucketRateLimiter final : public RateLimiterService::Service,
                                      public NodeService::Service {
public:
    LeakyBucketRateLimiter(const std::string& node_id, int port, const std::vector<std::string>& peers)
        : node_id_(node_id), port_(port), peers_(peers), is_leader_(false), stop_threads_(false) {
    }

    ~LeakyBucketRateLimiter() {
        stop_threads_ = true;
        if (leak_thread_.joinable()) {
            leak_thread_.join();
        }
    }

    void Initialize() {
        // Initialize connections to peer nodes
        for (const auto& peer : peers_) {
            auto channel = grpc::CreateChannel(peer, grpc::InsecureChannelCredentials());
            peer_stubs_[peer] = NodeService::NewStub(channel);
            std::cout << "Connected to peer: " << peer << std::endl;
        }

        // Start the leak processing thread
        leak_thread_ = std::thread(&LeakyBucketRateLimiter::LeakLoop, this);

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
     * Process leaked requests from a bucket.
     *
     * TODO: Implement leak processing
     * 1. Calculate how many requests should have leaked since last_leak_time
     * 2. Remove that many requests from the front of the queue
     * 3. Update processed_requests count
     * 4. Update last_leak_time
     */
    void ProcessLeaks(Bucket& bucket) {
        // TODO: Implement leak processing
        // 1. Get current time
        // 2. Calculate elapsed time since last_leak_time
        // 3. Calculate requests to leak: elapsed_seconds * leak_rate
        // 4. Remove requests from queue (up to calculated amount)
        // 5. Update processed_requests count
        // 6. Update last_leak_time
    }

    /**
     * Leak loop - continuously processes requests from all buckets.
     */
    void LeakLoop() {
        while (!stop_threads_) {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));

            std::unique_lock<std::shared_mutex> lock(mutex_);
            for (auto& [id, bucket] : buckets_) {
                ProcessLeaks(bucket);
            }
        }
    }

    /**
     * Try to add a request to the bucket queue.
     *
     * TODO: Implement queue addition
     * 1. Process any pending leaks first
     * 2. Check if queue has space (queue.size() < capacity)
     * 3. If yes, add request to queue and return true
     * 4. If no, return false (reject)
     */
    bool TryEnqueue(Bucket& bucket, const std::string& request_id) {
        // TODO: Implement request enqueuing
        // 1. Call ProcessLeaks first
        // 2. Check if queue.size() < capacity
        // 3. If yes, create QueuedRequestItem and add to queue
        // 4. Update allowed_requests count
        // 5. Return true if queued, false if rejected
        return false;  // Stub
    }

    /**
     * Calculate estimated wait time for a new request.
     *
     * TODO: Implement wait time calculation
     * Returns the estimated time in milliseconds until the request would be processed.
     */
    uint64_t CalculateEstimatedWaitMs(const Bucket& bucket) {
        // TODO: Implement wait time calculation
        // 1. Queue position = queue.size()
        // 2. Wait time = queue_position / leak_rate * 1000 (convert to ms)
        return 1000;  // Stub: default 1 second
    }

    // --- RateLimiterService RPC Implementations ---

    /**
     * Handle AllowRequest RPC - check if a request can be queued.
     *
     * TODO: Implement the main rate limiting logic:
     * 1. Find or create the bucket
     * 2. Try to enqueue the request
     * 3. Return result with queue position and wait time
     */
    Status AllowRequest(ServerContext* context,
                        const AllowRequestRequest* request,
                        AllowRequestResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement AllowRequest
        // 1. Get bucket_id from request
        // 2. Find bucket or return error if not found
        // 3. Call TryEnqueue
        // 4. Set response fields: allowed, queue_position, estimated_wait_ms
        // 5. Update bucket statistics

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
        // 1. Process leaks first (to get accurate queue size)
        // 2. Copy bucket state to response
        // 3. Include queued requests if needed

        response->set_found(true);
        return Status::OK;
    }

    /**
     * Handle ConfigureBucket RPC - create or update a bucket.
     *
     * TODO: Implement bucket configuration:
     * 1. Create new bucket or update existing
     * 2. Initialize with capacity and leak rate
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
        // 3. Initialize empty queue
        // 4. Set last_leak_time to current time
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
        response->set_healthy_nodes(peers_.size() + 1);
        response->set_total_buckets(buckets_.size());

        uint64_t total_queued = 0;
        uint64_t total_processed = 0;
        for (const auto& [id, bucket] : buckets_) {
            total_queued += bucket.queue.size();
            total_processed += bucket.processed_requests;
        }
        response->set_total_queued_requests(total_queued);
        response->set_total_processed_requests(total_processed);

        return Status::OK;
    }

    // --- NodeService RPC Implementations ---

    /**
     * Handle SyncBucket RPC - sync bucket state from another node.
     *
     * TODO: Implement bucket synchronization
     * 1. Receive bucket state from peer
     * 2. Merge with local state
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

    // Background leak processing
    std::atomic<bool> stop_threads_;
    std::thread leak_thread_;

    // Peer connections
    std::map<std::string, std::unique_ptr<NodeService::Stub>> peer_stubs_;
};

}  // namespace leaky_bucket

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

    leaky_bucket::LeakyBucketRateLimiter limiter(node_id, port, peers);
    limiter.Initialize();

    std::string server_address = "0.0.0.0:" + std::to_string(port);
    ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
    builder.RegisterService(static_cast<leaky_bucket::RateLimiterService::Service*>(&limiter));
    builder.RegisterService(static_cast<leaky_bucket::NodeService::Service*>(&limiter));

    std::unique_ptr<Server> server(builder.BuildAndStart());
    std::cout << "Leaky Bucket Rate Limiter " << node_id << " listening on port " << port << std::endl;

    server->Wait();
    return 0;
}
