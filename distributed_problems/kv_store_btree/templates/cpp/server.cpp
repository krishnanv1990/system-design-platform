/**
 * Distributed KV Store with B+ Tree - C++ Template
 *
 * This template provides the basic structure for implementing a distributed
 * key-value store using B+ Tree storage. You need to implement the TODO sections.
 *
 * B+ Tree Architecture:
 * 1. Internal nodes: Only store keys (routing information)
 * 2. Leaf nodes: Store keys + values, linked for range scans
 * 3. Buffer pool: Page caching with LRU eviction
 * 4. WAL: Write-ahead logging for durability
 * 5. Transactions: ACID properties with isolation levels
 *
 * Similar to: InnoDB, PostgreSQL, SQLite, BoltDB
 *
 * Usage:
 *     ./server --node-id node1 --port 50051 --data-dir /tmp/kvbtree --peers node2:50052,node3:50053
 */

#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <unordered_map>
#include <memory>
#include <mutex>
#include <shared_mutex>
#include <sstream>
#include <random>
#include <chrono>
#include <fstream>
#include <filesystem>
#include <set>
#include <list>
#include <optional>
#include <atomic>

#include <grpcpp/grpcpp.h>
#include "kv_store_btree.grpc.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;
using grpc::Channel;
using grpc::ClientContext;

namespace kvbtree {

// Constants for B+ Tree configuration
constexpr uint32_t PAGE_SIZE = 4096;           // 4KB pages
constexpr uint32_t DEFAULT_BRANCHING_FACTOR = 128;
constexpr uint64_t DEFAULT_BUFFER_POOL_SIZE = 1024;  // Number of pages

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

// ============================================================================
// Page Types and Structures
// ============================================================================

enum class PageType {
    INTERNAL,   // Internal node (keys only, pointers to children)
    LEAF,       // Leaf node (keys + values, linked list pointers)
    OVERFLOW    // Overflow page for large values
};

/**
 * Page represents a B+ tree page in memory
 * TODO: Implement page structure with proper serialization
 */
struct Page {
    uint64_t page_id;
    PageType type;
    uint32_t level;                     // 0 = leaf, increases toward root
    std::vector<std::string> keys;
    std::vector<std::vector<uint8_t>> values;  // Only for leaf pages
    std::vector<uint64_t> children;            // Only for internal pages
    uint64_t next_leaf;                        // Only for leaf pages (linked list)
    uint64_t prev_leaf;                        // Only for leaf pages
    bool is_dirty;
    uint64_t lsn;                              // Log sequence number

    Page() : page_id(0), type(PageType::LEAF), level(0),
             next_leaf(0), prev_leaf(0), is_dirty(false), lsn(0) {}
};

/**
 * WAL Entry for durability
 */
struct WALEntry {
    uint64_t lsn;
    uint64_t transaction_id;
    kv_store_btree::WALEntryType type;
    std::vector<uint8_t> data;
    uint64_t timestamp;
};

/**
 * Transaction state tracking
 */
struct Transaction {
    uint64_t transaction_id;
    kv_store_btree::TransactionState state;
    uint64_t start_lsn;
    uint64_t start_timestamp;
    std::vector<std::string> modified_keys;
    kv_store_btree::IsolationLevel isolation_level;
};

// ============================================================================
// Buffer Pool - Page Caching with LRU Eviction
// ============================================================================

/**
 * BufferPool manages page caching with LRU eviction
 * TODO: Implement buffer pool with proper page management
 */
class BufferPool {
public:
    BufferPool(uint64_t pool_size_pages = DEFAULT_BUFFER_POOL_SIZE)
        : pool_size_(pool_size_pages) {}

    // TODO: Implement GetPage - fetch page from cache or disk
    std::shared_ptr<Page> GetPage(uint64_t page_id) {
        // TODO: Implement page retrieval
        // 1. Check if page is in cache
        // 2. If not, load from disk
        // 3. Update LRU list
        // 4. If cache full, evict LRU page (flush if dirty)
        return nullptr;  // Stub
    }

    // TODO: Implement NewPage - allocate a new page
    std::shared_ptr<Page> NewPage() {
        // TODO: Implement new page allocation
        // 1. Find free page slot
        // 2. If cache full, evict LRU page
        // 3. Initialize new page
        return nullptr;  // Stub
    }

    // TODO: Implement MarkDirty - mark page as modified
    void MarkDirty(uint64_t page_id) {
        // TODO: Implement dirty page tracking
    }

    // TODO: Implement FlushPage - write page to disk
    bool FlushPage(uint64_t page_id) {
        // TODO: Implement page flush
        return false;  // Stub
    }

    // TODO: Implement FlushAllDirty - flush all dirty pages
    uint64_t FlushAllDirty() {
        // TODO: Implement flush all dirty pages
        return 0;  // Stub
    }

    // TODO: Implement GetStats - return buffer pool statistics
    kv_store_btree::BufferPoolStats GetStats() const {
        kv_store_btree::BufferPoolStats stats;
        // TODO: Populate actual statistics
        stats.set_pool_size_pages(pool_size_);
        stats.set_pages_in_use(0);
        stats.set_dirty_pages(0);
        stats.set_cache_hits(cache_hits_);
        stats.set_cache_misses(cache_misses_);
        stats.set_hit_ratio(cache_hits_ + cache_misses_ > 0 ?
            static_cast<double>(cache_hits_) / (cache_hits_ + cache_misses_) : 0.0);
        stats.set_evictions(evictions_);
        return stats;
    }

private:
    uint64_t pool_size_;
    std::unordered_map<uint64_t, std::shared_ptr<Page>> pages_;
    std::list<uint64_t> lru_list_;  // Front = most recently used
    std::unordered_map<uint64_t, std::list<uint64_t>::iterator> lru_map_;

    // Statistics
    mutable uint64_t cache_hits_ = 0;
    mutable uint64_t cache_misses_ = 0;
    uint64_t evictions_ = 0;

    mutable std::shared_mutex mutex_;
};

// ============================================================================
// Write-Ahead Log (WAL) for Durability
// ============================================================================

/**
 * WriteAheadLog provides durability through logging
 * TODO: Implement WAL with proper recovery
 */
class WriteAheadLog {
public:
    WriteAheadLog(const std::string& data_dir) : data_dir_(data_dir) {}

    // TODO: Implement Initialize - set up WAL file
    bool Initialize() {
        // TODO: Implement WAL initialization
        // 1. Create WAL file if not exists
        // 2. Recover entries from existing WAL
        // 3. Set current LSN based on last entry
        return false;  // Stub
    }

    // TODO: Implement Append - add entry to WAL
    uint64_t Append(const WALEntry& entry) {
        // TODO: Implement WAL append
        // 1. Serialize entry
        // 2. Write to WAL file
        // 3. Optionally sync to disk
        // 4. Return assigned LSN
        return 0;  // Stub
    }

    // TODO: Implement Sync - force WAL to disk
    bool Sync() {
        // TODO: Implement WAL sync
        return false;  // Stub
    }

    // TODO: Implement Truncate - remove old entries
    bool Truncate(uint64_t lsn) {
        // TODO: Implement WAL truncation after checkpoint
        return false;  // Stub
    }

    // TODO: Implement Recover - replay WAL entries
    std::vector<WALEntry> Recover() {
        // TODO: Implement WAL recovery
        return {};  // Stub
    }

    uint64_t GetCurrentLSN() const { return current_lsn_; }

private:
    std::string data_dir_;
    std::ofstream wal_file_;
    uint64_t current_lsn_ = 0;
    mutable std::mutex mutex_;
};

// ============================================================================
// B+ Tree Implementation
// ============================================================================

/**
 * BPlusTree implements the B+ tree index structure
 * TODO: Implement B+ tree operations with proper balancing
 */
class BPlusTree {
public:
    BPlusTree(BufferPool& buffer_pool, uint32_t branching_factor = DEFAULT_BRANCHING_FACTOR)
        : buffer_pool_(buffer_pool), branching_factor_(branching_factor) {}

    // TODO: Implement Initialize - create root page
    bool Initialize() {
        // TODO: Implement tree initialization
        // 1. Create root page (leaf initially)
        // 2. Set tree metadata
        return false;  // Stub
    }

    // TODO: Implement Insert - insert key-value pair
    bool Insert(const std::string& key, const std::vector<uint8_t>& value) {
        // TODO: Implement B+ tree insertion
        // 1. Find leaf node for key
        // 2. Insert into leaf
        // 3. If leaf overflows, split
        // 4. Propagate splits up the tree
        // 5. Update parent pointers
        return false;  // Stub
    }

    // TODO: Implement Search - find value by key
    std::pair<bool, std::vector<uint8_t>> Search(const std::string& key) {
        // TODO: Implement B+ tree search
        // 1. Start at root
        // 2. Navigate to leaf using binary search in internal nodes
        // 3. Binary search in leaf for key
        return {false, {}};  // Stub
    }

    // TODO: Implement Delete - remove key from tree
    bool Delete(const std::string& key) {
        // TODO: Implement B+ tree deletion
        // 1. Find leaf node containing key
        // 2. Remove key from leaf
        // 3. If leaf underflows, rebalance (redistribute or merge)
        // 4. Propagate changes up the tree
        return false;  // Stub
    }

    // TODO: Implement RangeScan - scan keys in range using linked leaves
    std::vector<std::pair<std::string, std::vector<uint8_t>>> RangeScan(
            const std::string& start_key, const std::string& end_key,
            uint32_t limit, bool reverse) {
        // TODO: Implement range scan using leaf linked list
        // 1. Find starting leaf
        // 2. Follow next_leaf/prev_leaf pointers
        // 3. Collect entries until end_key or limit
        return {};  // Stub
    }

    // TODO: Implement GetStats - return tree statistics
    kv_store_btree::TreeStats GetStats() const {
        kv_store_btree::TreeStats stats;
        // TODO: Populate actual statistics
        stats.set_root_page_id(root_page_id_);
        stats.set_height(height_);
        stats.set_total_pages(total_pages_);
        stats.set_internal_pages(internal_pages_);
        stats.set_leaf_pages(leaf_pages_);
        stats.set_overflow_pages(overflow_pages_);
        stats.set_total_keys(total_keys_);
        stats.set_fill_factor_percent(0);  // TODO: Calculate
        stats.set_branching_factor(branching_factor_);
        return stats;
    }

private:
    BufferPool& buffer_pool_;
    uint32_t branching_factor_;

    uint64_t root_page_id_ = 0;
    uint32_t height_ = 1;
    uint64_t total_pages_ = 0;
    uint64_t internal_pages_ = 0;
    uint64_t leaf_pages_ = 0;
    uint64_t overflow_pages_ = 0;
    uint64_t total_keys_ = 0;

    mutable std::shared_mutex mutex_;

    // TODO: Implement helper methods
    // std::shared_ptr<Page> FindLeaf(const std::string& key);
    // void SplitLeaf(std::shared_ptr<Page> leaf);
    // void SplitInternal(std::shared_ptr<Page> internal);
    // void MergeNodes(std::shared_ptr<Page> left, std::shared_ptr<Page> right);
    // void RedistributeKeys(std::shared_ptr<Page> left, std::shared_ptr<Page> right);
};

// ============================================================================
// Transaction Manager
// ============================================================================

/**
 * TransactionManager handles ACID transactions
 * TODO: Implement transaction management with proper isolation
 */
class TransactionManager {
public:
    TransactionManager(WriteAheadLog& wal) : wal_(wal) {}

    // TODO: Implement BeginTransaction
    uint64_t BeginTransaction(kv_store_btree::IsolationLevel isolation_level) {
        // TODO: Implement transaction begin
        // 1. Generate transaction ID
        // 2. Record start LSN
        // 3. Create transaction state
        return 0;  // Stub
    }

    // TODO: Implement CommitTransaction
    std::pair<bool, uint64_t> CommitTransaction(uint64_t transaction_id) {
        // TODO: Implement transaction commit
        // 1. Write commit record to WAL
        // 2. Ensure WAL is synced
        // 3. Update transaction state
        // 4. Release locks
        return {false, 0};  // Stub
    }

    // TODO: Implement RollbackTransaction
    bool RollbackTransaction(uint64_t transaction_id) {
        // TODO: Implement transaction rollback
        // 1. Write rollback record to WAL
        // 2. Undo changes using WAL
        // 3. Release locks
        return false;  // Stub
    }

    // TODO: Implement GetTransaction
    std::optional<Transaction> GetTransaction(uint64_t transaction_id) const {
        // TODO: Implement transaction lookup
        return std::nullopt;  // Stub
    }

    uint64_t GetActiveTransactionCount() const { return active_transactions_.size(); }
    uint64_t GetCommittedCount() const { return committed_count_; }
    uint64_t GetAbortedCount() const { return aborted_count_; }

private:
    WriteAheadLog& wal_;
    std::unordered_map<uint64_t, Transaction> active_transactions_;
    std::atomic<uint64_t> next_transaction_id_{1};
    uint64_t committed_count_ = 0;
    uint64_t aborted_count_ = 0;
    mutable std::shared_mutex mutex_;
};

// ============================================================================
// B+ Tree Storage Engine
// ============================================================================

/**
 * BTreeStorage manages the complete B+ tree storage engine
 * TODO: Implement storage engine integrating all components
 */
class BTreeStorage {
public:
    BTreeStorage(const std::string& data_dir)
        : data_dir_(data_dir),
          wal_(data_dir),
          buffer_pool_(DEFAULT_BUFFER_POOL_SIZE),
          tree_(buffer_pool_),
          tx_manager_(wal_) {}

    // TODO: Implement Initialize
    bool Initialize() {
        // TODO: Implement storage initialization
        // 1. Initialize WAL
        // 2. Initialize buffer pool
        // 3. Initialize B+ tree
        // 4. Recover from WAL if needed
        return false;  // Stub
    }

    // TODO: Implement Put
    std::pair<bool, uint64_t> Put(const std::string& key, const std::vector<uint8_t>& value,
                                   uint64_t transaction_id = 0) {
        // TODO: Implement put operation
        // 1. Write to WAL
        // 2. Insert into B+ tree
        // 3. Track in transaction if transactional
        return {false, 0};  // Stub
    }

    // TODO: Implement Get
    std::tuple<bool, std::vector<uint8_t>, std::string> Get(const std::string& key,
                                                             uint64_t transaction_id = 0) {
        // TODO: Implement get operation
        // 1. Search B+ tree
        // 2. Apply transaction isolation rules
        return {false, {}, ""};  // Stub: (found, value, error)
    }

    // TODO: Implement Delete
    std::pair<bool, uint64_t> Delete(const std::string& key, uint64_t transaction_id = 0) {
        // TODO: Implement delete operation
        // 1. Write to WAL
        // 2. Delete from B+ tree
        // 3. Track in transaction if transactional
        return {false, 0};  // Stub
    }

    // TODO: Implement Scan
    std::vector<std::pair<std::string, std::vector<uint8_t>>> Scan(
            const std::string& start_key, const std::string& end_key,
            uint32_t limit, bool reverse, uint64_t transaction_id = 0) {
        // TODO: Implement range scan
        return tree_.RangeScan(start_key, end_key, limit, reverse);
    }

    // TODO: Implement Checkpoint
    std::tuple<bool, uint64_t, uint64_t> Checkpoint(bool wait_for_completion) {
        // TODO: Implement checkpoint
        // 1. Flush all dirty pages
        // 2. Record checkpoint LSN
        // 3. Optionally truncate WAL
        return {false, 0, 0};  // Stub: (success, checkpoint_lsn, pages_flushed)
    }

    // Transaction operations
    uint64_t BeginTransaction(kv_store_btree::IsolationLevel isolation_level) {
        return tx_manager_.BeginTransaction(isolation_level);
    }

    std::pair<bool, uint64_t> CommitTransaction(uint64_t transaction_id) {
        return tx_manager_.CommitTransaction(transaction_id);
    }

    bool RollbackTransaction(uint64_t transaction_id) {
        return tx_manager_.RollbackTransaction(transaction_id);
    }

    // Statistics
    kv_store_btree::TreeStats GetTreeStats() const { return tree_.GetStats(); }
    kv_store_btree::BufferPoolStats GetBufferPoolStats() const { return buffer_pool_.GetStats(); }
    uint64_t GetCurrentLSN() const { return wal_.GetCurrentLSN(); }
    uint64_t GetTotalKeys() const { return total_keys_; }

    uint64_t GetActiveTransactions() const { return tx_manager_.GetActiveTransactionCount(); }
    uint64_t GetCommittedTransactions() const { return tx_manager_.GetCommittedCount(); }
    uint64_t GetAbortedTransactions() const { return tx_manager_.GetAbortedCount(); }

private:
    std::string data_dir_;
    WriteAheadLog wal_;
    BufferPool buffer_pool_;
    BPlusTree tree_;
    TransactionManager tx_manager_;

    uint64_t total_keys_ = 0;
    uint64_t checkpoint_lsn_ = 0;
    uint64_t pages_read_ = 0;
    uint64_t pages_written_ = 0;

    mutable std::shared_mutex mutex_;
};

// ============================================================================
// gRPC Service Implementation
// ============================================================================

/**
 * KVBTreeNode implements all three gRPC services:
 * - KVService: handles client key-value operations
 * - StorageService: handles B+ tree management operations
 * - ReplicationService: handles node-to-node replication
 */
class KVBTreeNode final :
    public kv_store_btree::KVService::Service,
    public kv_store_btree::StorageService::Service,
    public kv_store_btree::ReplicationService::Service {
public:
    KVBTreeNode(const std::string& node_id, int port, const std::string& data_dir,
                const std::vector<std::string>& peers)
        : node_id_(node_id), port_(port), data_dir_(data_dir), peers_(peers),
          storage_(data_dir) {}

    void Initialize() {
        // TODO: Implement node initialization
        // 1. Initialize storage
        // 2. Create gRPC stubs for peers
        // 3. Participate in leader election

        if (!storage_.Initialize()) {
            std::cerr << "Failed to initialize storage" << std::endl;
        }

        for (const auto& peer : peers_) {
            auto channel = grpc::CreateChannel(peer, grpc::InsecureChannelCredentials());
            peer_stubs_[peer] = kv_store_btree::ReplicationService::NewStub(channel);
        }

        std::cout << "KV B+ Tree node " << node_id_ << " initialized" << std::endl;
    }

    // ========================================================================
    // KVService Implementation
    // ========================================================================

    Status Get(ServerContext* ctx,
              const kv_store_btree::GetRequest* req,
              kv_store_btree::GetResponse* res) override {
        (void)ctx;

        // TODO: Implement Get
        auto [found, value, error] = storage_.Get(req->key(), req->transaction_id());

        res->set_found(found);
        if (found) {
            res->set_value(std::string(value.begin(), value.end()));
        }
        if (!error.empty()) {
            res->set_error(error);
        }
        res->set_served_by(node_id_);
        return Status::OK;
    }

    Status Put(ServerContext* ctx,
              const kv_store_btree::PutRequest* req,
              kv_store_btree::PutResponse* res) override {
        (void)ctx;

        // TODO: Implement Put
        if (!is_leader_) {
            res->set_success(false);
            res->set_error("Not the leader");
            return Status::OK;
        }

        std::vector<uint8_t> value(req->value().begin(), req->value().end());
        auto [success, lsn] = storage_.Put(req->key(), value, req->transaction_id());

        res->set_success(success);
        if (success) {
            res->set_lsn(lsn);
        } else {
            res->set_error("Failed to put value");
        }
        res->set_served_by(node_id_);
        return Status::OK;
    }

    Status Delete(ServerContext* ctx,
                 const kv_store_btree::DeleteRequest* req,
                 kv_store_btree::DeleteResponse* res) override {
        (void)ctx;

        // TODO: Implement Delete
        if (!is_leader_) {
            res->set_success(false);
            res->set_error("Not the leader");
            return Status::OK;
        }

        auto [success, lsn] = storage_.Delete(req->key(), req->transaction_id());
        res->set_success(success);
        if (success) {
            res->set_lsn(lsn);
        }
        res->set_served_by(node_id_);
        return Status::OK;
    }

    Status Scan(ServerContext* ctx,
               const kv_store_btree::ScanRequest* req,
               kv_store_btree::ScanResponse* res) override {
        (void)ctx;

        // TODO: Implement Scan
        auto entries = storage_.Scan(req->start_key(), req->end_key(),
                                     req->limit(), req->reverse(), req->transaction_id());

        for (const auto& [key, value] : entries) {
            auto* kv = res->add_entries();
            kv->set_key(key);
            kv->set_value(std::string(value.begin(), value.end()));
        }

        res->set_has_more(false);  // TODO: Implement pagination
        return Status::OK;
    }

    Status BeginTransaction(ServerContext* ctx,
                           const kv_store_btree::BeginTransactionRequest* req,
                           kv_store_btree::BeginTransactionResponse* res) override {
        (void)ctx;

        // TODO: Implement BeginTransaction
        uint64_t tx_id = storage_.BeginTransaction(req->isolation_level());

        if (tx_id > 0) {
            res->set_success(true);
            res->set_transaction_id(tx_id);
        } else {
            res->set_success(false);
            res->set_error("Failed to begin transaction");
        }
        return Status::OK;
    }

    Status CommitTransaction(ServerContext* ctx,
                            const kv_store_btree::CommitTransactionRequest* req,
                            kv_store_btree::CommitTransactionResponse* res) override {
        (void)ctx;

        // TODO: Implement CommitTransaction
        auto [success, commit_lsn] = storage_.CommitTransaction(req->transaction_id());

        res->set_success(success);
        if (success) {
            res->set_commit_lsn(commit_lsn);
        } else {
            res->set_error("Failed to commit transaction");
        }
        return Status::OK;
    }

    Status RollbackTransaction(ServerContext* ctx,
                              const kv_store_btree::RollbackTransactionRequest* req,
                              kv_store_btree::RollbackTransactionResponse* res) override {
        (void)ctx;

        // TODO: Implement RollbackTransaction
        bool success = storage_.RollbackTransaction(req->transaction_id());

        res->set_success(success);
        if (!success) {
            res->set_error("Failed to rollback transaction");
        }
        return Status::OK;
    }

    Status GetLeader(ServerContext* ctx,
                    const kv_store_btree::GetLeaderRequest* req,
                    kv_store_btree::GetLeaderResponse* res) override {
        (void)ctx; (void)req;

        res->set_node_id(node_id_);
        res->set_node_address("0.0.0.0:" + std::to_string(port_));
        res->set_is_leader(is_leader_);
        return Status::OK;
    }

    Status GetClusterStatus(ServerContext* ctx,
                           const kv_store_btree::GetClusterStatusRequest* req,
                           kv_store_btree::GetClusterStatusResponse* res) override {
        (void)ctx; (void)req;

        res->set_node_id(node_id_);
        res->set_node_address("0.0.0.0:" + std::to_string(port_));
        res->set_is_leader(is_leader_);
        res->set_total_nodes(static_cast<uint32_t>(peers_.size() + 1));
        res->set_healthy_nodes(static_cast<uint32_t>(peers_.size() + 1));  // TODO: Check health
        res->set_total_keys(storage_.GetTotalKeys());
        res->set_current_lsn(storage_.GetCurrentLSN());

        for (const auto& peer : peers_) {
            auto* member = res->add_members();
            member->set_address(peer);
            member->set_is_healthy(true);  // TODO: Check health
        }

        return Status::OK;
    }

    // ========================================================================
    // StorageService Implementation
    // ========================================================================

    Status Checkpoint(ServerContext* ctx,
                     const kv_store_btree::CheckpointRequest* req,
                     kv_store_btree::CheckpointResponse* res) override {
        (void)ctx;

        // TODO: Implement Checkpoint
        auto [success, checkpoint_lsn, pages_flushed] = storage_.Checkpoint(req->wait_for_completion());

        res->set_success(success);
        if (success) {
            res->set_checkpoint_lsn(checkpoint_lsn);
            res->set_pages_flushed(pages_flushed);
        } else {
            res->set_error("Failed to complete checkpoint");
        }
        return Status::OK;
    }

    Status GetTreeStats(ServerContext* ctx,
                       const kv_store_btree::GetTreeStatsRequest* req,
                       kv_store_btree::GetTreeStatsResponse* res) override {
        (void)ctx; (void)req;

        // TODO: Implement GetTreeStats
        *res->mutable_stats() = storage_.GetTreeStats();
        return Status::OK;
    }

    Status GetBufferPoolStats(ServerContext* ctx,
                             const kv_store_btree::GetBufferPoolStatsRequest* req,
                             kv_store_btree::GetBufferPoolStatsResponse* res) override {
        (void)ctx; (void)req;

        // TODO: Implement GetBufferPoolStats
        *res->mutable_stats() = storage_.GetBufferPoolStats();
        return Status::OK;
    }

    Status GetStorageStats(ServerContext* ctx,
                          const kv_store_btree::GetStorageStatsRequest* req,
                          kv_store_btree::GetStorageStatsResponse* res) override {
        (void)ctx; (void)req;

        // TODO: Implement GetStorageStats
        *res->mutable_tree() = storage_.GetTreeStats();
        *res->mutable_buffer_pool() = storage_.GetBufferPoolStats();
        res->set_current_lsn(storage_.GetCurrentLSN());
        res->set_active_transactions(storage_.GetActiveTransactions());
        res->set_committed_transactions(storage_.GetCommittedTransactions());
        res->set_aborted_transactions(storage_.GetAbortedTransactions());
        return Status::OK;
    }

    // ========================================================================
    // ReplicationService Implementation
    // ========================================================================

    Status AppendEntries(ServerContext* ctx,
                        const kv_store_btree::AppendEntriesRequest* req,
                        kv_store_btree::AppendEntriesResponse* res) override {
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
                      const kv_store_btree::RequestVoteRequest* req,
                      kv_store_btree::RequestVoteResponse* res) override {
        (void)ctx;

        // TODO: Implement RequestVote (Raft leader election)

        std::unique_lock<std::shared_mutex> lock(mutex_);

        res->set_term(current_term_);
        res->set_vote_granted(false);  // Stub: Always deny
        return Status::OK;
    }

    Status TransferPage(ServerContext* ctx,
                       const kv_store_btree::TransferPageRequest* req,
                       kv_store_btree::TransferPageResponse* res) override {
        (void)ctx;

        // TODO: Implement TransferPage
        // 1. Receive B+ tree page
        // 2. Write to buffer pool
        // 3. Mark as dirty if needed

        res->set_success(false);
        res->set_error("Not implemented - implement page transfer");
        return Status::OK;
    }

    Status Heartbeat(ServerContext* ctx,
                    const kv_store_btree::HeartbeatRequest* req,
                    kv_store_btree::HeartbeatResponse* res) override {
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
    BTreeStorage storage_;

    bool is_leader_ = true;  // Default to leader for single-node testing
    uint64_t current_term_ = 0;
    std::string voted_for_;

    std::map<std::string, std::unique_ptr<kv_store_btree::ReplicationService::Stub>> peer_stubs_;
    mutable std::shared_mutex mutex_;
};

}  // namespace kvbtree

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
    std::string node_id, data_dir = "/tmp/kvbtree", peers_str;
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

    kvbtree::KVBTreeNode node(node_id, port, data_dir, peers);
    node.Initialize();

    std::string server_address = "0.0.0.0:" + std::to_string(port);
    ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());

    builder.RegisterService(static_cast<kv_store_btree::KVService::Service*>(&node));
    builder.RegisterService(static_cast<kv_store_btree::StorageService::Service*>(&node));
    builder.RegisterService(static_cast<kv_store_btree::ReplicationService::Service*>(&node));

    std::unique_ptr<Server> server(builder.BuildAndStart());
    std::cout << "Starting KV B+ Tree node " << node_id << " on port " << port << std::endl;

    server->Wait();
    return 0;
}
