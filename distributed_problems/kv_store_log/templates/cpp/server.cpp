/**
 * Distributed KV Store with Append-Only Log - C++ Template
 *
 * This template provides the basic structure for implementing a distributed
 * key-value store using log-structured storage. You need to implement the TODO sections.
 *
 * Architecture:
 * 1. All writes are appended to an immutable log (fast writes)
 * 2. An in-memory hash table (KeyDir) maps keys to log offsets (fast reads)
 * 3. Compaction removes outdated entries to reclaim space
 * 4. Segments: log is divided into segments for easier management
 *
 * Similar to: Bitcask (used by Riak), early versions of Kafka
 *
 * Usage:
 *     ./server --node-id node1 --port 50051 --data-dir /tmp/kvlog --peers node2:50052,node3:50053
 */

#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <memory>
#include <mutex>
#include <shared_mutex>
#include <sstream>
#include <random>
#include <chrono>
#include <fstream>
#include <filesystem>

#include <grpcpp/grpcpp.h>
#include "kv_store_log.grpc.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;
using grpc::Channel;
using grpc::ClientContext;

namespace kvlog {

// Entry types in the log
enum class EntryType {
    PUT,
    DELETE
};

std::string entryTypeToString(EntryType type) {
    return type == EntryType::PUT ? "PUT" : "DELETE";
}

int64_t currentTimeMillis() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
}

uint32_t computeCRC32(const std::string& data) {
    // TODO: Implement CRC32 checksum
    // For production, use a proper CRC32 implementation
    return 0;  // Stub
}

// Log entry structure
struct LogEntry {
    uint64_t offset;
    uint64_t timestamp;
    EntryType type;
    std::string key;
    std::vector<uint8_t> value;
    uint32_t checksum;

    size_t size() const {
        return sizeof(offset) + sizeof(timestamp) + sizeof(type) +
               key.size() + value.size() + sizeof(checksum);
    }
};

// KeyDir entry (in-memory index)
struct KeyDirEntry {
    std::string key;
    uint64_t segment_id;
    uint64_t offset;
    uint64_t size;
    uint64_t timestamp;
};

// Segment metadata
struct Segment {
    uint64_t id;
    std::string filename;
    uint64_t start_offset;
    uint64_t end_offset;
    uint64_t size_bytes;
    uint64_t entry_count;
    bool is_active;
    bool is_compacted;
    int64_t created_at;
    int64_t last_modified;
};

/**
 * LogStorage manages the append-only log and KeyDir
 */
class LogStorage {
public:
    LogStorage(const std::string& data_dir) : data_dir_(data_dir) {}

    bool Initialize() {
        // TODO: Implement storage initialization
        // 1. Create data directory if not exists
        // 2. Load existing segments
        // 3. Rebuild KeyDir from log files
        // 4. Create new active segment if needed
        return false;  // Stub
    }

    // TODO: Implement Put
    std::pair<bool, uint64_t> Put(const std::string& key, const std::vector<uint8_t>& value) {
        // TODO: Implement put operation
        // 1. Create log entry
        // 2. Append to active segment
        // 3. Update KeyDir
        // 4. Check if segment needs rotation
        return {false, 0};  // Stub
    }

    // TODO: Implement Get
    std::pair<bool, std::vector<uint8_t>> Get(const std::string& key) {
        // TODO: Implement get operation
        // 1. Look up key in KeyDir
        // 2. Read value from segment at offset
        // 3. Verify checksum
        return {false, {}};  // Stub
    }

    // TODO: Implement Delete
    std::pair<bool, bool> Delete(const std::string& key) {
        // TODO: Implement delete operation
        // 1. Check if key exists in KeyDir
        // 2. Append tombstone entry to log
        // 3. Remove key from KeyDir
        return {false, false};  // Stub
    }

    // TODO: Implement Scan
    std::vector<std::pair<std::string, std::vector<uint8_t>>> Scan(
            const std::string& start_key, const std::string& end_key, uint32_t limit) {
        // TODO: Implement range scan
        // 1. Iterate through KeyDir entries in range
        // 2. Read values from segments
        // 3. Return key-value pairs
        return {};  // Stub
    }

    // TODO: Implement Compaction
    bool TriggerCompaction(bool force, const std::vector<uint64_t>& segment_ids) {
        // TODO: Implement log compaction
        // 1. Select segments to compact
        // 2. For each key in KeyDir, check if it points to selected segments
        // 3. Write live entries to new segment
        // 4. Update KeyDir pointers
        // 5. Delete old segments
        return false;  // Stub
    }

    uint64_t GetTotalKeys() const { return key_dir_.size(); }
    uint64_t GetTotalSegments() const { return segments_.size(); }

private:
    std::string data_dir_;
    std::map<std::string, KeyDirEntry> key_dir_;
    std::map<uint64_t, Segment> segments_;
    uint64_t active_segment_id_ = 0;
    uint64_t current_offset_ = 0;
    mutable std::shared_mutex mutex_;
};

/**
 * KVLogNode implements all three gRPC services:
 * - KVService: handles client key-value operations
 * - StorageService: handles storage management operations
 * - ReplicationService: handles node-to-node replication
 */
class KVLogNode final :
    public kv_store_log::KVService::Service,
    public kv_store_log::StorageService::Service,
    public kv_store_log::ReplicationService::Service {
public:
    KVLogNode(const std::string& node_id, int port, const std::string& data_dir,
              const std::vector<std::string>& peers)
        : node_id_(node_id), port_(port), data_dir_(data_dir), peers_(peers),
          storage_(data_dir) {}

    void Initialize() {
        // TODO: Implement node initialization
        // 1. Initialize storage
        // 2. Create gRPC stubs for peers
        // 3. Start replication threads
        // 4. Participate in leader election

        if (!storage_.Initialize()) {
            std::cerr << "Failed to initialize storage" << std::endl;
        }

        for (const auto& peer : peers_) {
            auto channel = grpc::CreateChannel(peer, grpc::InsecureChannelCredentials());
            peer_stubs_[peer] = kv_store_log::ReplicationService::NewStub(channel);
        }

        std::cout << "KV Log node " << node_id_ << " initialized" << std::endl;
    }

    // ========================================================================
    // KVService Implementation
    // ========================================================================

    Status Get(ServerContext* ctx,
              const kv_store_log::GetRequest* req,
              kv_store_log::GetResponse* res) override {
        (void)ctx;

        // TODO: Implement Get
        // 1. Look up key in storage
        // 2. Return value if found

        auto [found, value] = storage_.Get(req->key());
        res->set_found(found);
        if (found) {
            res->set_value(std::string(value.begin(), value.end()));
            res->set_timestamp(currentTimeMillis());
        }
        res->set_served_by(node_id_);
        return Status::OK;
    }

    Status Put(ServerContext* ctx,
              const kv_store_log::PutRequest* req,
              kv_store_log::PutResponse* res) override {
        (void)ctx;

        // TODO: Implement Put
        // 1. Check if we're the leader
        // 2. Append entry to log
        // 3. Replicate to followers
        // 4. Wait for acknowledgments (if required)

        if (!is_leader_) {
            res->set_success(false);
            res->set_error("Not the leader");
            return Status::OK;
        }

        std::vector<uint8_t> value(req->value().begin(), req->value().end());
        auto [success, offset] = storage_.Put(req->key(), value);

        res->set_success(success);
        if (success) {
            res->set_offset(offset);
        } else {
            res->set_error("Failed to put value");
        }
        res->set_served_by(node_id_);
        return Status::OK;
    }

    Status Delete(ServerContext* ctx,
                 const kv_store_log::DeleteRequest* req,
                 kv_store_log::DeleteResponse* res) override {
        (void)ctx;

        // TODO: Implement Delete
        // 1. Check if we're the leader
        // 2. Write tombstone entry
        // 3. Replicate to followers

        if (!is_leader_) {
            res->set_success(false);
            res->set_error("Not the leader");
            return Status::OK;
        }

        auto [success, existed] = storage_.Delete(req->key());
        res->set_success(success);
        res->set_existed(existed);
        res->set_served_by(node_id_);
        return Status::OK;
    }

    Status Scan(ServerContext* ctx,
               const kv_store_log::ScanRequest* req,
               kv_store_log::ScanResponse* res) override {
        (void)ctx;

        // TODO: Implement Scan
        auto entries = storage_.Scan(req->start_key(), req->end_key(), req->limit());

        for (const auto& [key, value] : entries) {
            auto* kv = res->add_entries();
            kv->set_key(key);
            kv->set_value(std::string(value.begin(), value.end()));
        }

        res->set_has_more(false);  // TODO: Implement pagination
        return Status::OK;
    }

    Status BatchPut(ServerContext* ctx,
                   const kv_store_log::BatchPutRequest* req,
                   kv_store_log::BatchPutResponse* res) override {
        (void)ctx;

        // TODO: Implement BatchPut
        // 1. Check if we're the leader
        // 2. Append all entries atomically
        // 3. Replicate to followers

        if (!is_leader_) {
            res->set_success(false);
            res->set_error("Not the leader");
            return Status::OK;
        }

        // Stub: Not implemented
        res->set_success(false);
        res->set_error("Not implemented - implement batch put");
        return Status::OK;
    }

    Status GetLeader(ServerContext* ctx,
                    const kv_store_log::GetLeaderRequest* req,
                    kv_store_log::GetLeaderResponse* res) override {
        (void)ctx; (void)req;

        res->set_node_id(node_id_);
        res->set_node_address("0.0.0.0:" + std::to_string(port_));
        res->set_is_leader(is_leader_);
        return Status::OK;
    }

    Status GetClusterStatus(ServerContext* ctx,
                           const kv_store_log::GetClusterStatusRequest* req,
                           kv_store_log::GetClusterStatusResponse* res) override {
        (void)ctx; (void)req;

        res->set_node_id(node_id_);
        res->set_node_address("0.0.0.0:" + std::to_string(port_));
        res->set_is_leader(is_leader_);
        res->set_total_nodes(static_cast<uint32_t>(peers_.size() + 1));
        res->set_total_keys(storage_.GetTotalKeys());
        res->set_total_segments(storage_.GetTotalSegments());

        for (const auto& peer : peers_) {
            auto* member = res->add_members();
            member->set_address(peer);
        }

        return Status::OK;
    }

    // ========================================================================
    // StorageService Implementation
    // ========================================================================

    Status TriggerCompaction(ServerContext* ctx,
                            const kv_store_log::TriggerCompactionRequest* req,
                            kv_store_log::TriggerCompactionResponse* res) override {
        (void)ctx;

        // TODO: Implement compaction trigger
        std::vector<uint64_t> segment_ids(req->segment_ids().begin(), req->segment_ids().end());
        bool started = storage_.TriggerCompaction(req->force(), segment_ids);

        res->set_started(started);
        if (!started) {
            res->set_error("Compaction could not be started");
        }
        return Status::OK;
    }

    Status GetCompactionStatus(ServerContext* ctx,
                              const kv_store_log::GetCompactionStatusRequest* req,
                              kv_store_log::GetCompactionStatusResponse* res) override {
        (void)ctx; (void)req;

        // TODO: Implement compaction status
        res->set_is_running(false);
        return Status::OK;
    }

    Status GetStorageStats(ServerContext* ctx,
                          const kv_store_log::GetStorageStatsRequest* req,
                          kv_store_log::GetStorageStatsResponse* res) override {
        (void)ctx; (void)req;

        // TODO: Implement storage stats
        res->set_total_keys(storage_.GetTotalKeys());
        res->set_total_segments(storage_.GetTotalSegments());
        return Status::OK;
    }

    Status GetSegments(ServerContext* ctx,
                      const kv_store_log::GetSegmentsRequest* req,
                      kv_store_log::GetSegmentsResponse* res) override {
        (void)ctx; (void)req;

        // TODO: Implement get segments
        return Status::OK;
    }

    // ========================================================================
    // ReplicationService Implementation
    // ========================================================================

    Status AppendEntries(ServerContext* ctx,
                        const kv_store_log::AppendEntriesRequest* req,
                        kv_store_log::AppendEntriesResponse* res) override {
        (void)ctx;

        // TODO: Implement AppendEntries (Raft-style replication)
        // 1. Check term
        // 2. Verify prev_log_offset and prev_log_term
        // 3. Append new entries
        // 4. Update commit offset

        std::unique_lock<std::shared_mutex> lock(mutex_);

        if (req->term() < current_term_) {
            res->set_term(current_term_);
            res->set_success(false);
            return Status::OK;
        }

        // Stub: Accept entries without verification
        res->set_term(current_term_);
        res->set_success(false);
        res->set_error("Not implemented - implement AppendEntries");
        return Status::OK;
    }

    Status RequestVote(ServerContext* ctx,
                      const kv_store_log::RequestVoteRequest* req,
                      kv_store_log::RequestVoteResponse* res) override {
        (void)ctx;

        // TODO: Implement RequestVote (Raft leader election)
        // 1. Check term
        // 2. Check if we've already voted
        // 3. Check if candidate's log is up-to-date
        // 4. Grant or deny vote

        std::unique_lock<std::shared_mutex> lock(mutex_);

        res->set_term(current_term_);
        res->set_vote_granted(false);  // Stub: Always deny
        return Status::OK;
    }

    Status InstallSnapshot(ServerContext* ctx,
                          const kv_store_log::InstallSnapshotRequest* req,
                          kv_store_log::InstallSnapshotResponse* res) override {
        (void)ctx;

        // TODO: Implement InstallSnapshot
        // 1. Check term
        // 2. Save snapshot chunk
        // 3. If done, apply snapshot and update state

        res->set_term(current_term_);
        res->set_success(false);
        return Status::OK;
    }

    Status Heartbeat(ServerContext* ctx,
                    const kv_store_log::HeartbeatRequest* req,
                    kv_store_log::HeartbeatResponse* res) override {
        (void)ctx; (void)req;

        res->set_acknowledged(true);
        res->set_timestamp(currentTimeMillis());
        return Status::OK;
    }

private:
    std::string node_id_;
    int port_;
    std::string data_dir_;
    std::vector<std::string> peers_;
    LogStorage storage_;

    bool is_leader_ = true;  // Default to leader for single-node testing
    uint64_t current_term_ = 0;
    std::string voted_for_;

    std::map<std::string, std::unique_ptr<kv_store_log::ReplicationService::Stub>> peer_stubs_;
    mutable std::shared_mutex mutex_;
};

}  // namespace kvlog

std::vector<std::string> split(const std::string& s, char delimiter) {
    std::vector<std::string> tokens;
    std::string token;
    std::istringstream tokenStream(s);
    while (std::getline(tokenStream, token, delimiter)) {
        token.erase(0, token.find_first_not_of(" \t"));
        token.erase(token.find_last_not_of(" \t") + 1);
        if (!token.empty()) tokens.push_back(token);
    }
    return tokens;
}

int main(int argc, char** argv) {
    std::string node_id, data_dir = "/tmp/kvlog", peers_str;
    int port = 50051;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--node-id" && i + 1 < argc) node_id = argv[++i];
        else if (arg == "--port" && i + 1 < argc) port = std::stoi(argv[++i]);
        else if (arg == "--data-dir" && i + 1 < argc) data_dir = argv[++i];
        else if (arg == "--peers" && i + 1 < argc) peers_str = argv[++i];
    }

    if (node_id.empty()) {
        std::cerr << "Usage: " << argv[0]
                  << " --node-id <id> --port <port> [--data-dir <dir>] [--peers peer1:port,peer2:port]"
                  << std::endl;
        return 1;
    }

    std::vector<std::string> peers = split(peers_str, ',');

    kvlog::KVLogNode node(node_id, port, data_dir, peers);
    node.Initialize();

    std::string server_address = "0.0.0.0:" + std::to_string(port);
    ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());

    builder.RegisterService(static_cast<kv_store_log::KVService::Service*>(&node));
    builder.RegisterService(static_cast<kv_store_log::StorageService::Service*>(&node));
    builder.RegisterService(static_cast<kv_store_log::ReplicationService::Service*>(&node));

    std::unique_ptr<Server> server(builder.BuildAndStart());
    std::cout << "Starting KV Log node " << node_id << " on port " << port << std::endl;

    server->Wait();
    return 0;
}
