//! Distributed KV Store with B+ Tree - Rust Template
//!
//! This template provides the basic structure for implementing a distributed
//! key-value store using B+ Tree storage.
//!
//! B+ Tree Architecture:
//! 1. All values stored in leaf nodes (internal nodes only have keys)
//! 2. Leaf nodes are linked for efficient range scans
//! 3. Balanced tree ensures O(log n) operations
//! 4. Page-based storage with buffer pool for caching
//! 5. WAL for durability, transactions for ACID
//!
//! Similar to: InnoDB, PostgreSQL, SQLite, BoltDB
//!
//! You need to implement the TODO sections.
//!
//! Usage:
//!     cargo run -- --node-id node1 --port 50051 --data-dir /tmp/kvbtree --peers node2:50052,node3:50053

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tonic::{transport::Server, Request, Response, Status};
use clap::Parser;

pub mod kvbtree {
    tonic::include_proto!("kv_store_btree");
}

use kvbtree::kv_service_server::{KvService, KvServiceServer};
use kvbtree::storage_service_server::{StorageService, StorageServiceServer};
use kvbtree::replication_service_server::{ReplicationService, ReplicationServiceServer};
use kvbtree::replication_service_client::ReplicationServiceClient;
use kvbtree::*;

// =============================================================================
// B+ Tree Types
// =============================================================================

/// Page types in B+ Tree
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum BTreePageType {
    Internal,
    Leaf,
    Overflow,
}

/// WAL entry types
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum WalEntryType {
    Put,
    Delete,
    Commit,
    Rollback,
    Checkpoint,
    PageSplit,
    PageMerge,
}

/// Transaction state
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum TxnState {
    Active,
    Committed,
    Aborted,
}

/// Isolation levels
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum TxnIsolationLevel {
    ReadUncommitted,
    ReadCommitted,
    RepeatableRead,
    Serializable,
}

/// B+ Tree page
#[derive(Clone, Debug)]
pub struct BTreePage {
    pub page_id: u64,
    pub page_type: BTreePageType,
    pub level: u32,               // 0 = leaf
    pub keys: Vec<String>,
    pub values: Vec<Vec<u8>>,     // Only for leaf pages
    pub children: Vec<u64>,       // Only for internal pages
    pub next_leaf: Option<u64>,   // Only for leaf pages
    pub prev_leaf: Option<u64>,   // Only for leaf pages
    pub is_dirty: bool,
    pub lsn: u64,                 // Log sequence number
}

impl BTreePage {
    pub fn new_leaf(page_id: u64) -> Self {
        Self {
            page_id,
            page_type: BTreePageType::Leaf,
            level: 0,
            keys: Vec::new(),
            values: Vec::new(),
            children: Vec::new(),
            next_leaf: None,
            prev_leaf: None,
            is_dirty: false,
            lsn: 0,
        }
    }

    pub fn new_internal(page_id: u64, level: u32) -> Self {
        Self {
            page_id,
            page_type: BTreePageType::Internal,
            level,
            keys: Vec::new(),
            values: Vec::new(),
            children: Vec::new(),
            next_leaf: None,
            prev_leaf: None,
            is_dirty: false,
            lsn: 0,
        }
    }
}

/// WAL entry
#[derive(Clone, Debug)]
pub struct LocalWalEntry {
    pub lsn: u64,
    pub transaction_id: u64,
    pub entry_type: WalEntryType,
    pub data: Vec<u8>,
    pub timestamp: u64,
}

/// Transaction information
#[derive(Clone, Debug)]
pub struct LocalTransaction {
    pub id: u64,
    pub state: TxnState,
    pub start_lsn: u64,
    pub start_timestamp: u64,
    pub modified_keys: Vec<String>,
    pub isolation_level: TxnIsolationLevel,
}

// =============================================================================
// Buffer Pool
// =============================================================================

pub struct BufferPool {
    pages: RwLock<HashMap<u64, BTreePage>>,
    pool_size: usize,

    // Statistics
    cache_hits: RwLock<u64>,
    cache_misses: RwLock<u64>,
    evictions: RwLock<u64>,
}

impl BufferPool {
    pub fn new(pool_size: usize) -> Self {
        Self {
            pages: RwLock::new(HashMap::new()),
            pool_size,
            cache_hits: RwLock::new(0),
            cache_misses: RwLock::new(0),
            evictions: RwLock::new(0),
        }
    }

    pub async fn get_page(&self, _page_id: u64) -> Option<BTreePage> {
        // TODO: Get page from buffer pool
        // 1. Check if page is in cache
        // 2. If not, read from disk and add to cache
        // 3. Update LRU order
        // 4. Evict if necessary
        todo!("Implement buffer pool get_page")
    }

    pub async fn put_page(&self, _page: BTreePage) {
        // TODO: Put page in buffer pool
        // 1. Add/update page in cache
        // 2. Mark as dirty if modified
        // 3. Evict if necessary
        todo!("Implement buffer pool put_page")
    }

    pub async fn flush_page(&self, _page_id: u64) -> Result<(), String> {
        // TODO: Flush page to disk
        // 1. Get page from cache
        // 2. Write to disk
        // 3. Clear dirty flag
        todo!("Implement buffer pool flush_page")
    }

    pub async fn flush_all_dirty(&self) -> Result<u64, String> {
        // TODO: Flush all dirty pages
        // 1. Iterate through cache
        // 2. Write all dirty pages to disk
        // 3. Return count of flushed pages
        todo!("Implement buffer pool flush_all_dirty")
    }
}

// =============================================================================
// B+ Tree Implementation
// =============================================================================

pub struct BPlusTree {
    data_dir: String,
    buffer_pool: BufferPool,

    root_page_id: RwLock<u64>,
    next_page_id: RwLock<u64>,
    height: RwLock<u32>,
    branching_factor: u32,

    // WAL
    current_lsn: RwLock<u64>,

    // Transaction management
    next_txn_id: RwLock<u64>,
    active_transactions: RwLock<HashMap<u64, LocalTransaction>>,
}

impl BPlusTree {
    pub fn new(data_dir: String, branching_factor: u32, buffer_pool_size: usize) -> Self {
        Self {
            data_dir,
            buffer_pool: BufferPool::new(buffer_pool_size),
            root_page_id: RwLock::new(0),
            next_page_id: RwLock::new(1),
            height: RwLock::new(1),
            branching_factor,
            current_lsn: RwLock::new(0),
            next_txn_id: RwLock::new(1),
            active_transactions: RwLock::new(HashMap::new()),
        }
    }

    pub async fn initialize(&self) -> Result<(), String> {
        // TODO: Initialize B+ Tree
        // 1. Create data directory
        // 2. Recover from WAL if exists
        // 3. Load or create root page
        // 4. Initialize buffer pool
        todo!("Implement B+ Tree initialization")
    }

    pub async fn get(&self, _key: &str, _txn_id: Option<u64>) -> Result<Option<Vec<u8>>, String> {
        // TODO: Implement B+ Tree lookup
        // 1. Start from root
        // 2. Navigate to correct leaf page
        // 3. Binary search in leaf for key
        // 4. Handle MVCC for transactions
        todo!("Implement B+ Tree get")
    }

    pub async fn put(&self, _key: String, _value: Vec<u8>, _txn_id: Option<u64>) -> Result<u64, String> {
        // TODO: Implement B+ Tree insert
        // 1. Write to WAL
        // 2. Navigate to correct leaf page
        // 3. Insert key-value pair
        // 4. Split page if overflow
        // 5. Propagate splits up the tree
        // 6. Return LSN
        todo!("Implement B+ Tree put")
    }

    pub async fn delete(&self, _key: &str, _txn_id: Option<u64>) -> Result<(bool, u64), String> {
        // TODO: Implement B+ Tree delete
        // 1. Write to WAL
        // 2. Navigate to correct leaf page
        // 3. Remove key-value pair
        // 4. Merge/redistribute pages if underflow
        // 5. Return (existed, LSN)
        todo!("Implement B+ Tree delete")
    }

    pub async fn scan(
        &self,
        _start_key: &str,
        _end_key: Option<&str>,
        _limit: u32,
        _reverse: bool,
        _txn_id: Option<u64>,
    ) -> Result<Vec<(String, Vec<u8>)>, String> {
        // TODO: Implement range scan
        // 1. Navigate to start key leaf
        // 2. Follow leaf links to scan range
        // 3. Use reverse links if reverse=true
        todo!("Implement B+ Tree scan")
    }

    async fn split_leaf(&self, _page: &mut BTreePage) -> Result<BTreePage, String> {
        // TODO: Split a full leaf page
        // 1. Create new leaf page
        // 2. Move half the entries to new page
        // 3. Update leaf links
        // 4. Return new page (caller inserts into parent)
        todo!("Implement leaf split")
    }

    async fn split_internal(&self, _page: &mut BTreePage) -> Result<(String, BTreePage), String> {
        // TODO: Split a full internal page
        // 1. Create new internal page
        // 2. Move half the keys/children to new page
        // 3. Return (middle key, new page)
        todo!("Implement internal split")
    }

    async fn merge_or_redistribute(&self, _page: &mut BTreePage, _parent: &mut BTreePage) -> Result<(), String> {
        // TODO: Handle underflow
        // 1. Try to redistribute with sibling
        // 2. If not possible, merge with sibling
        // 3. Update parent
        todo!("Implement merge/redistribute")
    }

    // Transaction methods
    pub async fn begin_transaction(&self, _isolation: TxnIsolationLevel) -> Result<u64, String> {
        // TODO: Begin a new transaction
        // 1. Allocate transaction ID
        // 2. Record start LSN
        // 3. Create transaction entry
        todo!("Implement begin transaction")
    }

    pub async fn commit_transaction(&self, _txn_id: u64) -> Result<u64, String> {
        // TODO: Commit transaction
        // 1. Write commit record to WAL
        // 2. Update transaction state
        // 3. Return commit LSN
        todo!("Implement commit transaction")
    }

    pub async fn rollback_transaction(&self, _txn_id: u64) -> Result<(), String> {
        // TODO: Rollback transaction
        // 1. Undo all changes made by transaction
        // 2. Write rollback record to WAL
        // 3. Update transaction state
        todo!("Implement rollback transaction")
    }

    pub async fn checkpoint(&self) -> Result<(u64, u64), String> {
        // TODO: Perform checkpoint
        // 1. Flush all dirty pages
        // 2. Write checkpoint record to WAL
        // 3. Return (checkpoint_lsn, pages_flushed)
        todo!("Implement checkpoint")
    }

    async fn get_next_lsn(&self) -> u64 {
        let mut lsn = self.current_lsn.write().await;
        *lsn += 1;
        *lsn
    }

    fn get_current_timestamp(&self) -> u64 {
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis() as u64
    }
}

// =============================================================================
// Node Role for Replication
// =============================================================================

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum NodeRole {
    Leader,
    Follower,
    Candidate,
}

// =============================================================================
// Main Node Structure
// =============================================================================

pub struct KvBTreeNode {
    node_id: String,
    port: u16,
    peers: Vec<String>,
    tree: Arc<BPlusTree>,

    // Replication state
    role: RwLock<NodeRole>,
    current_term: RwLock<u64>,
    voted_for: RwLock<Option<String>>,
    leader_id: RwLock<Option<String>>,
    commit_lsn: RwLock<u64>,

    // Transaction stats
    committed_transactions: RwLock<u64>,
    aborted_transactions: RwLock<u64>,

    // Peer clients
    peer_clients: RwLock<HashMap<String, ReplicationServiceClient<tonic::transport::Channel>>>,
}

impl KvBTreeNode {
    pub fn new(node_id: String, port: u16, peers: Vec<String>, data_dir: String) -> Self {
        let tree = Arc::new(BPlusTree::new(data_dir, 128, 1024)); // 128 keys per page, 1024 pages in buffer
        Self {
            node_id,
            port,
            peers,
            tree,
            role: RwLock::new(NodeRole::Follower),
            current_term: RwLock::new(0),
            voted_for: RwLock::new(None),
            leader_id: RwLock::new(None),
            commit_lsn: RwLock::new(0),
            committed_transactions: RwLock::new(0),
            aborted_transactions: RwLock::new(0),
            peer_clients: RwLock::new(HashMap::new()),
        }
    }

    pub async fn initialize(&self) -> Result<(), Box<dyn std::error::Error>> {
        // TODO: Initialize node
        // 1. Initialize B+ Tree storage
        // 2. Connect to peers
        // 3. Start election timer
        // 4. Start background checkpoint
        todo!("Implement node initialization")
    }

    fn get_current_timestamp(&self) -> i64 {
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis() as i64
    }
}

// =============================================================================
// KVService Implementation
// =============================================================================

#[tonic::async_trait]
impl KvService for Arc<KvBTreeNode> {
    async fn get(&self, request: Request<GetRequest>) -> Result<Response<GetResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement get
        // 1. Look up in B+ Tree
        // 2. Handle transaction isolation if txn_id provided

        let _ = (req.key, req.transaction_id);

        Ok(Response::new(GetResponse {
            value: vec![],
            found: false,
            error: "TODO: Implement get".to_string(),
            served_by: self.node_id.clone(),
        }))
    }

    async fn put(&self, request: Request<PutRequest>) -> Result<Response<PutResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement put
        // 1. If not leader, redirect
        // 2. Write to B+ Tree
        // 3. Replicate to followers

        let role = *self.role.read().await;
        if role != NodeRole::Leader {
            let leader = self.leader_id.read().await;
            return Ok(Response::new(PutResponse {
                success: false,
                lsn: 0,
                error: format!("Not leader. Leader is: {:?}", leader),
                served_by: self.node_id.clone(),
            }));
        }

        let _ = (req.key, req.value, req.transaction_id);

        Ok(Response::new(PutResponse {
            success: false,
            lsn: 0,
            error: "TODO: Implement put".to_string(),
            served_by: self.node_id.clone(),
        }))
    }

    async fn delete(&self, request: Request<DeleteRequest>) -> Result<Response<DeleteResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement delete

        let role = *self.role.read().await;
        if role != NodeRole::Leader {
            return Ok(Response::new(DeleteResponse {
                success: false,
                existed: false,
                lsn: 0,
                error: "Not leader".to_string(),
                served_by: self.node_id.clone(),
            }));
        }

        let _ = (req.key, req.transaction_id);

        Ok(Response::new(DeleteResponse {
            success: false,
            existed: false,
            lsn: 0,
            error: "TODO: Implement delete".to_string(),
            served_by: self.node_id.clone(),
        }))
    }

    async fn scan(&self, request: Request<ScanRequest>) -> Result<Response<ScanResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement range scan
        // B+ Trees are efficient for range scans via leaf links

        let _ = (req.start_key, req.end_key, req.limit, req.reverse, req.transaction_id);

        Ok(Response::new(ScanResponse {
            entries: vec![],
            has_more: false,
            next_key: String::new(),
            error: "TODO: Implement scan".to_string(),
        }))
    }

    async fn begin_transaction(&self, request: Request<BeginTransactionRequest>) -> Result<Response<BeginTransactionResponse>, Status> {
        let req = request.into_inner();

        // TODO: Begin transaction
        // 1. Allocate transaction ID
        // 2. Set isolation level

        let _isolation = match req.isolation_level {
            0 => TxnIsolationLevel::ReadUncommitted,
            1 => TxnIsolationLevel::ReadCommitted,
            2 => TxnIsolationLevel::RepeatableRead,
            _ => TxnIsolationLevel::Serializable,
        };

        Ok(Response::new(BeginTransactionResponse {
            success: false,
            transaction_id: 0,
            error: "TODO: Implement begin transaction".to_string(),
        }))
    }

    async fn commit_transaction(&self, request: Request<CommitTransactionRequest>) -> Result<Response<CommitTransactionResponse>, Status> {
        let req = request.into_inner();

        // TODO: Commit transaction

        let _ = req.transaction_id;

        Ok(Response::new(CommitTransactionResponse {
            success: false,
            commit_lsn: 0,
            error: "TODO: Implement commit transaction".to_string(),
        }))
    }

    async fn rollback_transaction(&self, request: Request<RollbackTransactionRequest>) -> Result<Response<RollbackTransactionResponse>, Status> {
        let req = request.into_inner();

        // TODO: Rollback transaction

        let _ = req.transaction_id;

        Ok(Response::new(RollbackTransactionResponse {
            success: false,
            error: "TODO: Implement rollback transaction".to_string(),
        }))
    }

    async fn get_leader(&self, _request: Request<GetLeaderRequest>) -> Result<Response<GetLeaderResponse>, Status> {
        let role = *self.role.read().await;
        let leader = self.leader_id.read().await;

        Ok(Response::new(GetLeaderResponse {
            node_id: leader.clone().unwrap_or_else(|| self.node_id.clone()),
            node_address: format!("localhost:{}", self.port),
            is_leader: role == NodeRole::Leader,
        }))
    }

    async fn get_cluster_status(&self, _request: Request<GetClusterStatusRequest>) -> Result<Response<GetClusterStatusResponse>, Status> {
        let role = *self.role.read().await;
        let lsn = *self.tree.current_lsn.read().await;

        let members: Vec<NodeInfo> = self.peers.iter().map(|p| {
            NodeInfo {
                node_id: String::new(),
                address: p.clone(),
                is_healthy: true,
                is_leader: false,
                lsn: 0,
                last_heartbeat: 0,
            }
        }).collect();

        Ok(Response::new(GetClusterStatusResponse {
            node_id: self.node_id.clone(),
            node_address: format!("localhost:{}", self.port),
            is_leader: role == NodeRole::Leader,
            total_nodes: (self.peers.len() + 1) as u32,
            healthy_nodes: (self.peers.len() + 1) as u32,
            total_keys: 0, // TODO: Track this
            current_lsn: lsn,
            members,
        }))
    }
}

// =============================================================================
// StorageService Implementation
// =============================================================================

#[tonic::async_trait]
impl StorageService for Arc<KvBTreeNode> {
    async fn checkpoint(&self, request: Request<CheckpointRequest>) -> Result<Response<CheckpointResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement checkpoint
        // 1. Flush all dirty pages
        // 2. Write checkpoint record

        let _ = req.wait_for_completion;

        Ok(Response::new(CheckpointResponse {
            success: false,
            checkpoint_lsn: 0,
            pages_flushed: 0,
            error: "TODO: Implement checkpoint".to_string(),
        }))
    }

    async fn get_tree_stats(&self, _request: Request<GetTreeStatsRequest>) -> Result<Response<GetTreeStatsResponse>, Status> {
        let height = *self.tree.height.read().await;

        // TODO: Collect actual tree statistics

        Ok(Response::new(GetTreeStatsResponse {
            stats: Some(kvbtree::TreeStats {
                root_page_id: *self.tree.root_page_id.read().await,
                height,
                total_pages: 0,
                internal_pages: 0,
                leaf_pages: 0,
                overflow_pages: 0,
                total_keys: 0,
                fill_factor_percent: 0,
                branching_factor: self.tree.branching_factor,
            }),
            error: String::new(),
        }))
    }

    async fn get_buffer_pool_stats(&self, _request: Request<GetBufferPoolStatsRequest>) -> Result<Response<GetBufferPoolStatsResponse>, Status> {
        let cache_hits = *self.tree.buffer_pool.cache_hits.read().await;
        let cache_misses = *self.tree.buffer_pool.cache_misses.read().await;
        let evictions = *self.tree.buffer_pool.evictions.read().await;
        let pages = self.tree.buffer_pool.pages.read().await;

        let total = cache_hits + cache_misses;
        let hit_ratio = if total > 0 { cache_hits as f64 / total as f64 } else { 0.0 };

        Ok(Response::new(GetBufferPoolStatsResponse {
            stats: Some(kvbtree::BufferPoolStats {
                pool_size_pages: self.tree.buffer_pool.pool_size as u64,
                pages_in_use: pages.len() as u64,
                dirty_pages: pages.values().filter(|p| p.is_dirty).count() as u64,
                cache_hits,
                cache_misses,
                hit_ratio,
                evictions,
            }),
            error: String::new(),
        }))
    }

    async fn get_storage_stats(&self, _request: Request<GetStorageStatsRequest>) -> Result<Response<GetStorageStatsResponse>, Status> {
        let current_lsn = *self.tree.current_lsn.read().await;
        let committed = *self.committed_transactions.read().await;
        let aborted = *self.aborted_transactions.read().await;
        let active = self.tree.active_transactions.read().await;

        // TODO: Collect complete storage stats

        Ok(Response::new(GetStorageStatsResponse {
            tree: None,
            buffer_pool: None,
            wal_size_bytes: 0,
            current_lsn,
            checkpoint_lsn: 0,
            active_transactions: active.len() as u64,
            committed_transactions: committed,
            aborted_transactions: aborted,
            pages_read: 0,
            pages_written: 0,
            error: String::new(),
        }))
    }
}

// =============================================================================
// ReplicationService Implementation
// =============================================================================

#[tonic::async_trait]
impl ReplicationService for Arc<KvBTreeNode> {
    async fn append_entries(&self, request: Request<AppendEntriesRequest>) -> Result<Response<AppendEntriesResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement AppendEntries
        // 1. Check term
        // 2. Apply WAL entries
        // 3. Update commit LSN

        let current_term = *self.current_term.read().await;

        if req.term < current_term {
            return Ok(Response::new(AppendEntriesResponse {
                term: current_term,
                success: false,
                match_lsn: 0,
                error: "Term is stale".to_string(),
            }));
        }

        let _ = (req.leader_id, req.prev_lsn, req.prev_term, req.entries, req.leader_commit_lsn);

        Ok(Response::new(AppendEntriesResponse {
            term: current_term,
            success: false,
            match_lsn: 0,
            error: "TODO: Implement append entries".to_string(),
        }))
    }

    async fn request_vote(&self, request: Request<RequestVoteRequest>) -> Result<Response<RequestVoteResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement RequestVote

        let current_term = *self.current_term.read().await;

        if req.term < current_term {
            return Ok(Response::new(RequestVoteResponse {
                term: current_term,
                vote_granted: false,
            }));
        }

        let _ = (req.candidate_id, req.last_lsn, req.last_term);

        Ok(Response::new(RequestVoteResponse {
            term: current_term,
            vote_granted: false,
        }))
    }

    async fn transfer_page(&self, request: Request<TransferPageRequest>) -> Result<Response<TransferPageResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement page transfer
        // 1. Receive page from leader
        // 2. Add to buffer pool
        // 3. Mark as dirty for later flush

        let _ = (req.leader_id, req.page);

        Ok(Response::new(TransferPageResponse {
            success: false,
            error: "TODO: Implement page transfer".to_string(),
        }))
    }

    async fn heartbeat(&self, request: Request<HeartbeatRequest>) -> Result<Response<HeartbeatResponse>, Status> {
        let req = request.into_inner();

        // TODO: Handle heartbeat
        // 1. Update last seen time
        // 2. Reset election timer

        let _ = (req.node_id, req.timestamp, req.lsn);

        Ok(Response::new(HeartbeatResponse {
            acknowledged: true,
            timestamp: self.get_current_timestamp(),
        }))
    }
}

// =============================================================================
// Command Line Arguments
// =============================================================================

#[derive(Parser, Debug)]
#[command(name = "kv-store-btree-server")]
#[command(about = "Distributed KV Store with B+ Tree")]
struct Args {
    /// Unique identifier for this node
    #[arg(long)]
    node_id: String,

    /// Port to listen on
    #[arg(long, default_value_t = 50051)]
    port: u16,

    /// Directory for data storage
    #[arg(long, default_value = "/tmp/kvbtree")]
    data_dir: String,

    /// Comma-separated list of peer addresses
    #[arg(long, default_value = "")]
    peers: String,
}

// =============================================================================
// Main Entry Point
// =============================================================================

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    let peers: Vec<String> = args
        .peers
        .split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    let node = Arc::new(KvBTreeNode::new(
        args.node_id.clone(),
        args.port,
        peers,
        args.data_dir,
    ));

    // Note: initialize() needs to be implemented
    // node.initialize().await?;

    let addr = format!("0.0.0.0:{}", args.port).parse()?;
    println!(
        "Starting KV Store (B+ Tree) node {} on port {}",
        args.node_id, args.port
    );

    Server::builder()
        .add_service(KvServiceServer::new(node.clone()))
        .add_service(StorageServiceServer::new(node.clone()))
        .add_service(ReplicationServiceServer::new(node.clone()))
        .serve(addr)
        .await?;

    Ok(())
}
