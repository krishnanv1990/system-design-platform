/**
 * Distributed KV Store with LSM Tree - C++ Template
 *
 * This template provides the basic structure for implementing a distributed
 * key-value store using Log-Structured Merge Tree. You need to implement the TODO sections.
 *
 * LSM Tree Architecture:
 * 1. MemTable: In-memory sorted structure (e.g., red-black tree, skip list)
 * 2. WAL: Write-ahead log for durability
 * 3. SSTables: Immutable sorted string tables on disk
 * 4. Levels: SSTables organized in levels (L0, L1, ..., Ln)
 * 5. Compaction: Merge SSTables across levels to reduce read amplification
 *
 * Similar to: LevelDB, RocksDB, Cassandra, HBase
 *
 * Usage:
 *     ./server --node-id node1 --port 50051 --data-dir /tmp/kvlsm --peers node2:50052,node3:50053
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
#include <set>

#include <grpcpp/grpcpp.h>
#include "kv_store_lsm.grpc.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;
using grpc::Channel;
using grpc::ClientContext;

namespace kvlsm {

// Write types
enum class WriteType {
    PUT,
    DELETE
};

std::string writeTypeToString(WriteType type) {
    return type == WriteType::PUT ? "PUT" : "DELETE";
}

int64_t currentTimeMillis() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
}

std::string generateUUID() {
    static std::random_device rd;
    static std::mt19937 gen(rd());
    static std::uniform_int_distribution<> dis(0, 15);
    static const char* hex = "0123456789abcdef";

    std::string uuid(36, '-');
    for (int i = 0; i < 36; i++) {
        if (i == 8 || i == 13 || i == 18 || i == 23) continue;
        uuid[i] = hex[dis(gen)];
    }
    return uuid;
}

// WAL entry structure
struct WALEntry {
    uint64_t sequence_number;
    WriteType type;
    std::string key;
    std::vector<uint8_t> value;
    uint64_t timestamp;
};

// MemTable entry
struct MemTableEntry {
    std::string key;
    std::vector<uint8_t> value;
    uint64_t sequence_number;
    WriteType type;
};

// SSTable metadata
struct SSTableInfo {
    std::string id;
    uint32_t level;
    std::string filename;
    uint64_t size_bytes;
    uint64_t entry_count;
    std::string min_key;
    std::string max_key;
    uint64_t min_sequence;
    uint64_t max_sequence;
    bool has_bloom_filter;
    int64_t created_at;
};

// Bloom filter for SSTable
struct BloomFilter {
    std::vector<uint8_t> bits;
    uint32_t num_hash_functions;
    uint64_t num_elements;

    // TODO: Implement Bloom filter
    void add(const std::string& key) {
        // TODO: Implement add to Bloom filter
    }

    bool mayContain(const std::string& key) const {
        // TODO: Implement Bloom filter lookup
        return true;  // Stub: Always return true (no filtering)
    }
};

/**
 * MemTable - In-memory sorted structure
 */
class MemTable {
public:
    MemTable(uint64_t max_size = 4 * 1024 * 1024) : max_size_(max_size) {}

    // TODO: Implement Put
    bool Put(const std::string& key, const std::vector<uint8_t>& value, uint64_t seq) {
        // TODO: Implement put operation
        // 1. Insert into sorted map
        // 2. Track size
        // 3. Return true if memtable is full
        return false;  // Stub
    }

    // TODO: Implement Delete
    bool Delete(const std::string& key, uint64_t seq) {
        // TODO: Implement delete (insert tombstone)
        return false;  // Stub
    }

    // TODO: Implement Get
    std::pair<bool, std::vector<uint8_t>> Get(const std::string& key) const {
        // TODO: Implement get from memtable
        return {false, {}};  // Stub
    }

    bool IsFull() const { return current_size_ >= max_size_; }
    uint64_t Size() const { return current_size_; }
    uint64_t EntryCount() const { return entries_.size(); }

    const std::map<std::string, MemTableEntry>& Entries() const { return entries_; }

private:
    std::map<std::string, MemTableEntry> entries_;
    uint64_t max_size_;
    uint64_t current_size_ = 0;
};

/**
 * WriteAheadLog - Durability layer
 */
class WriteAheadLog {
public:
    WriteAheadLog(const std::string& data_dir) : data_dir_(data_dir) {}

    bool Initialize() {
        // TODO: Implement WAL initialization
        // 1. Create WAL file if not exists
        // 2. Recover entries from existing WAL
        return false;  // Stub
    }

    // TODO: Implement Append
    bool Append(const WALEntry& entry) {
        // TODO: Implement WAL append
        // 1. Serialize entry
        // 2. Write to WAL file
        // 3. Optionally sync to disk
        return false;  // Stub
    }

    // TODO: Implement Truncate
    bool Truncate(uint64_t sequence_number) {
        // TODO: Implement WAL truncation after flush
        return false;  // Stub
    }

private:
    std::string data_dir_;
    std::ofstream wal_file_;
};

/**
 * LSMStorage manages the LSM tree structure
 */
class LSMStorage {
public:
    LSMStorage(const std::string& data_dir) : data_dir_(data_dir), wal_(data_dir) {}

    bool Initialize() {
        // TODO: Implement storage initialization
        // 1. Initialize WAL
        // 2. Create active memtable
        // 3. Load SSTable metadata
        // 4. Recover from WAL if needed
        return false;  // Stub
    }

    // TODO: Implement Put
    std::pair<bool, uint64_t> Put(const std::string& key, const std::vector<uint8_t>& value, bool sync) {
        // TODO: Implement put operation
        // 1. Append to WAL
        // 2. Insert into memtable
        // 3. If memtable full, trigger flush
        return {false, 0};  // Stub
    }

    // TODO: Implement Get
    std::tuple<bool, std::vector<uint8_t>, std::string> Get(const std::string& key) {
        // TODO: Implement get operation (LSM read path)
        // 1. Check memtable
        // 2. Check immutable memtable
        // 3. Check L0 SSTables (in order)
        // 4. Check L1+ SSTables (binary search)
        // 5. Use Bloom filters to skip SSTables
        return {false, {}, ""};  // Stub: (found, value, source)
    }

    // TODO: Implement Delete
    std::pair<bool, uint64_t> Delete(const std::string& key, bool sync) {
        // TODO: Implement delete (write tombstone)
        return {false, 0};  // Stub
    }

    // TODO: Implement Scan
    std::vector<std::tuple<std::string, std::vector<uint8_t>, uint64_t>> Scan(
            const std::string& start_key, const std::string& end_key, uint32_t limit, bool reverse) {
        // TODO: Implement range scan with merge iterator
        // 1. Create iterators for memtable and all SSTables
        // 2. Merge iterators keeping most recent version of each key
        // 3. Skip tombstones
        return {};  // Stub
    }

    // TODO: Implement FlushMemTable
    std::pair<bool, std::string> FlushMemTable() {
        // TODO: Implement memtable flush
        // 1. Make current memtable immutable
        // 2. Create new active memtable
        // 3. Write immutable memtable to SSTable (L0)
        // 4. Update metadata
        // 5. Truncate WAL
        return {false, ""};  // Stub
    }

    // TODO: Implement Compaction
    bool TriggerCompaction(uint32_t level, bool force) {
        // TODO: Implement LSM compaction
        // 1. Select SSTables to compact
        // 2. Merge SSTables keeping newest versions
        // 3. Write to next level
        // 4. Update metadata
        // 5. Delete old SSTables
        return false;  // Stub
    }

    uint64_t GetSequenceNumber() const { return sequence_number_; }
    uint64_t GetTotalKeys() const { return total_keys_; }

private:
    std::string data_dir_;
    WriteAheadLog wal_;

    std::unique_ptr<MemTable> memtable_;
    std::unique_ptr<MemTable> immutable_memtable_;

    std::vector<std::vector<SSTableInfo>> levels_;  // levels_[level] = list of SSTables
    std::map<std::string, BloomFilter> bloom_filters_;

    uint64_t sequence_number_ = 0;
    uint64_t total_keys_ = 0;

    mutable std::shared_mutex mutex_;
};

/**
 * KVLSMNode implements all three gRPC services:
 * - KVService: handles client key-value operations
 * - StorageService: handles LSM tree management operations
 * - ReplicationService: handles node-to-node replication
 */
class KVLSMNode final :
    public kv_store_lsm::KVService::Service,
    public kv_store_lsm::StorageService::Service,
    public kv_store_lsm::ReplicationService::Service {
public:
    KVLSMNode(const std::string& node_id, int port, const std::string& data_dir,
              const std::vector<std::string>& peers)
        : node_id_(node_id), port_(port), data_dir_(data_dir), peers_(peers),
          storage_(data_dir) {}

    void Initialize() {
        // TODO: Implement node initialization
        // 1. Initialize storage
        // 2. Create gRPC stubs for peers
        // 3. Start background compaction thread
        // 4. Participate in leader election

        if (!storage_.Initialize()) {
            std::cerr << "Failed to initialize storage" << std::endl;
        }

        for (const auto& peer : peers_) {
            auto channel = grpc::CreateChannel(peer, grpc::InsecureChannelCredentials());
            peer_stubs_[peer] = kv_store_lsm::ReplicationService::NewStub(channel);
        }

        std::cout << "KV LSM node " << node_id_ << " initialized" << std::endl;
    }

    // ========================================================================
    // KVService Implementation
    // ========================================================================

    Status Get(ServerContext* ctx,
              const kv_store_lsm::GetRequest* req,
              kv_store_lsm::GetResponse* res) override {
        (void)ctx;

        // TODO: Implement Get
        auto [found, value, source] = storage_.Get(req->key());

        res->set_found(found);
        if (found) {
            res->set_value(std::string(value.begin(), value.end()));
            res->set_source(source);
        }
        res->set_served_by(node_id_);
        return Status::OK;
    }

    Status Put(ServerContext* ctx,
              const kv_store_lsm::PutRequest* req,
              kv_store_lsm::PutResponse* res) override {
        (void)ctx;

        // TODO: Implement Put
        if (!is_leader_) {
            res->set_success(false);
            res->set_error("Not the leader");
            return Status::OK;
        }

        std::vector<uint8_t> value(req->value().begin(), req->value().end());
        auto [success, seq] = storage_.Put(req->key(), value, req->sync());

        res->set_success(success);
        if (success) {
            res->set_sequence_number(seq);
        } else {
            res->set_error("Failed to put value");
        }
        res->set_served_by(node_id_);
        return Status::OK;
    }

    Status Delete(ServerContext* ctx,
                 const kv_store_lsm::DeleteRequest* req,
                 kv_store_lsm::DeleteResponse* res) override {
        (void)ctx;

        // TODO: Implement Delete
        if (!is_leader_) {
            res->set_success(false);
            res->set_error("Not the leader");
            return Status::OK;
        }

        auto [success, seq] = storage_.Delete(req->key(), req->sync());
        res->set_success(success);
        if (success) {
            res->set_sequence_number(seq);
        }
        res->set_served_by(node_id_);
        return Status::OK;
    }

    Status Scan(ServerContext* ctx,
               const kv_store_lsm::ScanRequest* req,
               kv_store_lsm::ScanResponse* res) override {
        (void)ctx;

        // TODO: Implement Scan
        auto entries = storage_.Scan(req->start_key(), req->end_key(), req->limit(), req->reverse());

        for (const auto& [key, value, seq] : entries) {
            auto* kv = res->add_entries();
            kv->set_key(key);
            kv->set_value(std::string(value.begin(), value.end()));
            kv->set_sequence_number(seq);
        }

        res->set_has_more(false);  // TODO: Implement pagination
        return Status::OK;
    }

    Status BatchWrite(ServerContext* ctx,
                     const kv_store_lsm::BatchWriteRequest* req,
                     kv_store_lsm::BatchWriteResponse* res) override {
        (void)ctx;

        // TODO: Implement BatchWrite
        if (!is_leader_) {
            res->set_success(false);
            res->set_error("Not the leader");
            return Status::OK;
        }

        // Stub: Not implemented
        res->set_success(false);
        res->set_error("Not implemented - implement batch write");
        return Status::OK;
    }

    Status GetLeader(ServerContext* ctx,
                    const kv_store_lsm::GetLeaderRequest* req,
                    kv_store_lsm::GetLeaderResponse* res) override {
        (void)ctx; (void)req;

        res->set_node_id(node_id_);
        res->set_node_address("0.0.0.0:" + std::to_string(port_));
        res->set_is_leader(is_leader_);
        return Status::OK;
    }

    Status GetClusterStatus(ServerContext* ctx,
                           const kv_store_lsm::GetClusterStatusRequest* req,
                           kv_store_lsm::GetClusterStatusResponse* res) override {
        (void)ctx; (void)req;

        res->set_node_id(node_id_);
        res->set_node_address("0.0.0.0:" + std::to_string(port_));
        res->set_is_leader(is_leader_);
        res->set_total_nodes(static_cast<uint32_t>(peers_.size() + 1));
        res->set_total_keys(storage_.GetTotalKeys());
        res->set_sequence_number(storage_.GetSequenceNumber());

        for (const auto& peer : peers_) {
            auto* member = res->add_members();
            member->set_address(peer);
        }

        return Status::OK;
    }

    // ========================================================================
    // StorageService Implementation
    // ========================================================================

    Status FlushMemTable(ServerContext* ctx,
                        const kv_store_lsm::FlushMemTableRequest* req,
                        kv_store_lsm::FlushMemTableResponse* res) override {
        (void)ctx; (void)req;

        // TODO: Implement flush memtable
        auto [success, sstable_id] = storage_.FlushMemTable();

        res->set_success(success);
        if (success) {
            res->set_sstable_id(sstable_id);
        } else {
            res->set_error("Failed to flush memtable");
        }
        return Status::OK;
    }

    Status TriggerCompaction(ServerContext* ctx,
                            const kv_store_lsm::TriggerCompactionRequest* req,
                            kv_store_lsm::TriggerCompactionResponse* res) override {
        (void)ctx;

        // TODO: Implement compaction trigger
        bool started = storage_.TriggerCompaction(req->level(), req->force());

        res->set_started(started);
        if (!started) {
            res->set_error("Compaction could not be started");
        }
        return Status::OK;
    }

    Status GetCompactionStatus(ServerContext* ctx,
                              const kv_store_lsm::GetCompactionStatusRequest* req,
                              kv_store_lsm::GetCompactionStatusResponse* res) override {
        (void)ctx; (void)req;

        // TODO: Implement compaction status
        res->set_is_running(false);
        return Status::OK;
    }

    Status GetStorageStats(ServerContext* ctx,
                          const kv_store_lsm::GetStorageStatsRequest* req,
                          kv_store_lsm::GetStorageStatsResponse* res) override {
        (void)ctx; (void)req;

        // TODO: Implement storage stats
        res->set_total_keys(storage_.GetTotalKeys());
        res->set_sequence_number(storage_.GetSequenceNumber());
        return Status::OK;
    }

    Status GetLevels(ServerContext* ctx,
                    const kv_store_lsm::GetLevelsRequest* req,
                    kv_store_lsm::GetLevelsResponse* res) override {
        (void)ctx; (void)req;

        // TODO: Implement get levels
        return Status::OK;
    }

    // ========================================================================
    // ReplicationService Implementation
    // ========================================================================

    Status AppendEntries(ServerContext* ctx,
                        const kv_store_lsm::AppendEntriesRequest* req,
                        kv_store_lsm::AppendEntriesResponse* res) override {
        (void)ctx;

        // TODO: Implement AppendEntries (Raft-style replication)

        std::unique_lock<std::shared_mutex> lock(mutex_);

        if (req->term() < current_term_) {
            res->set_term(current_term_);
            res->set_success(false);
            return Status::OK;
        }

        // Stub: Not implemented
        res->set_term(current_term_);
        res->set_success(false);
        res->set_error("Not implemented - implement AppendEntries");
        return Status::OK;
    }

    Status RequestVote(ServerContext* ctx,
                      const kv_store_lsm::RequestVoteRequest* req,
                      kv_store_lsm::RequestVoteResponse* res) override {
        (void)ctx;

        // TODO: Implement RequestVote (Raft leader election)

        std::unique_lock<std::shared_mutex> lock(mutex_);

        res->set_term(current_term_);
        res->set_vote_granted(false);  // Stub: Always deny
        return Status::OK;
    }

    Status TransferSSTable(ServerContext* ctx,
                          const kv_store_lsm::TransferSSTableRequest* req,
                          kv_store_lsm::TransferSSTableResponse* res) override {
        (void)ctx;

        // TODO: Implement SSTable transfer
        // 1. Receive SSTable chunk
        // 2. Write to disk
        // 3. If done, register SSTable metadata

        res->set_success(false);
        res->set_error("Not implemented - implement SSTable transfer");
        return Status::OK;
    }

    Status Heartbeat(ServerContext* ctx,
                    const kv_store_lsm::HeartbeatRequest* req,
                    kv_store_lsm::HeartbeatResponse* res) override {
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
    LSMStorage storage_;

    bool is_leader_ = true;  // Default to leader for single-node testing
    uint64_t current_term_ = 0;
    std::string voted_for_;

    std::map<std::string, std::unique_ptr<kv_store_lsm::ReplicationService::Stub>> peer_stubs_;
    mutable std::shared_mutex mutex_;
};

}  // namespace kvlsm

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
    std::string node_id, data_dir = "/tmp/kvlsm", peers_str;
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

    kvlsm::KVLSMNode node(node_id, port, data_dir, peers);
    node.Initialize();

    std::string server_address = "0.0.0.0:" + std::to_string(port);
    ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());

    builder.RegisterService(static_cast<kv_store_lsm::KVService::Service*>(&node));
    builder.RegisterService(static_cast<kv_store_lsm::StorageService::Service*>(&node));
    builder.RegisterService(static_cast<kv_store_lsm::ReplicationService::Service*>(&node));

    std::unique_ptr<Server> server(builder.BuildAndStart());
    std::cout << "Starting KV LSM node " << node_id << " on port " << port << std::endl;

    server->Wait();
    return 0;
}
