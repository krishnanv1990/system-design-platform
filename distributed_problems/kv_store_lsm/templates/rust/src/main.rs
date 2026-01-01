//! Distributed KV Store with LSM Tree - Rust Template
//!
//! This template provides the basic structure for implementing a distributed
//! key-value store using Log-Structured Merge Tree storage.
//!
//! LSM Tree Architecture:
//! 1. MemTable: In-memory sorted structure (e.g., red-black tree, skip list)
//! 2. WAL: Write-ahead log for durability
//! 3. SSTables: Immutable sorted string tables on disk
//! 4. Levels: SSTables organized in levels (L0, L1, ..., Ln)
//! 5. Compaction: Merge SSTables across levels to reduce read amplification
//!
//! Similar to: LevelDB, RocksDB, Cassandra, HBase
//!
//! You need to implement the TODO sections.
//!
//! Usage:
//!     cargo run -- --node-id node1 --port 50051 --data-dir /tmp/kvlsm --peers node2:50052,node3:50053

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tonic::{transport::Server, Request, Response, Status};
use clap::Parser;

pub mod kvlsm {
    tonic::include_proto!("kv_store_lsm");
}

use kvlsm::kv_service_server::{KvService, KvServiceServer};
use kvlsm::storage_service_server::{StorageService, StorageServiceServer};
use kvlsm::replication_service_server::{ReplicationService, ReplicationServiceServer};
use kvlsm::replication_service_client::ReplicationServiceClient;
use kvlsm::*;

// =============================================================================
// LSM Tree Types
// =============================================================================

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum WriteEntryType {
    Put,
    Delete,
}

/// Entry in the MemTable
#[derive(Clone, Debug)]
pub struct MemTableEntry {
    pub key: String,
    pub value: Vec<u8>,
    pub sequence_number: u64,
    pub entry_type: WriteEntryType,
    pub timestamp: u64,
}

/// WAL Entry for durability
#[derive(Clone, Debug)]
pub struct WalEntry {
    pub sequence_number: u64,
    pub entry_type: WriteEntryType,
    pub key: String,
    pub value: Vec<u8>,
    pub timestamp: u64,
}

/// SSTable metadata
#[derive(Clone, Debug)]
pub struct SSTableMeta {
    pub id: String,
    pub level: u32,
    pub filename: String,
    pub size_bytes: u64,
    pub entry_count: u64,
    pub min_key: String,
    pub max_key: String,
    pub min_sequence: u64,
    pub max_sequence: u64,
    pub has_bloom_filter: bool,
    pub created_at: i64,
}

/// Level information
#[derive(Clone, Debug)]
pub struct LevelMeta {
    pub level: u32,
    pub sstables: Vec<SSTableMeta>,
    pub total_size_bytes: u64,
    pub target_size_bytes: u64,
}

// =============================================================================
// MemTable Implementation
// =============================================================================

pub struct MemTable {
    // Using BTreeMap for sorted order
    entries: std::collections::BTreeMap<String, MemTableEntry>,
    size_bytes: u64,
    max_size_bytes: u64,
    oldest_sequence: u64,
    newest_sequence: u64,
}

impl MemTable {
    pub fn new(max_size_bytes: u64) -> Self {
        Self {
            entries: std::collections::BTreeMap::new(),
            size_bytes: 0,
            max_size_bytes,
            oldest_sequence: 0,
            newest_sequence: 0,
        }
    }

    pub fn put(&mut self, _key: String, _value: Vec<u8>, _seq: u64) {
        // TODO: Insert entry into MemTable
        // 1. Create entry with sequence number
        // 2. Update size tracking
        // 3. Update sequence number range
        todo!("Implement MemTable put")
    }

    pub fn delete(&mut self, _key: String, _seq: u64) {
        // TODO: Insert tombstone into MemTable
        // 1. Create delete entry with sequence number
        // 2. Update size tracking
        todo!("Implement MemTable delete")
    }

    pub fn get(&self, _key: &str) -> Option<&MemTableEntry> {
        // TODO: Look up key in MemTable
        // Return the entry if found
        todo!("Implement MemTable get")
    }

    pub fn is_full(&self) -> bool {
        self.size_bytes >= self.max_size_bytes
    }

    pub fn iter(&self) -> impl Iterator<Item = (&String, &MemTableEntry)> {
        self.entries.iter()
    }
}

// =============================================================================
// Bloom Filter Implementation
// =============================================================================

pub struct BloomFilter {
    bits: Vec<bool>,
    num_hash_functions: u32,
    num_elements: u64,
}

impl BloomFilter {
    pub fn new(_expected_elements: u64, _false_positive_rate: f64) -> Self {
        // TODO: Calculate optimal size and hash functions
        // 1. Calculate bit array size: m = -n * ln(p) / (ln(2)^2)
        // 2. Calculate hash functions: k = (m/n) * ln(2)
        todo!("Implement Bloom filter creation")
    }

    pub fn add(&mut self, _key: &str) {
        // TODO: Add key to bloom filter
        // 1. Hash key with each hash function
        // 2. Set corresponding bits
        todo!("Implement Bloom filter add")
    }

    pub fn may_contain(&self, _key: &str) -> bool {
        // TODO: Check if key might be in set
        // 1. Hash key with each hash function
        // 2. Check if all bits are set
        // 3. Return false if any bit is 0 (definitely not in set)
        // 4. Return true if all bits are 1 (might be in set)
        todo!("Implement Bloom filter lookup")
    }
}

// =============================================================================
// LSM Storage Engine
// =============================================================================

pub struct LsmStorage {
    data_dir: String,
    node_id: String,

    // MemTable (active)
    memtable: RwLock<MemTable>,

    // Immutable MemTable (being flushed)
    immutable_memtable: RwLock<Option<MemTable>>,

    // SSTable levels
    levels: RwLock<Vec<LevelMeta>>,

    // Sequence number
    sequence_number: RwLock<u64>,

    // Compaction state
    is_compacting: RwLock<bool>,
    compaction_progress: RwLock<f64>,
}

impl LsmStorage {
    pub fn new(data_dir: String, node_id: String) -> Self {
        Self {
            data_dir,
            node_id,
            memtable: RwLock::new(MemTable::new(4 * 1024 * 1024)), // 4MB default
            immutable_memtable: RwLock::new(None),
            levels: RwLock::new(Vec::new()),
            sequence_number: RwLock::new(0),
            is_compacting: RwLock::new(false),
            compaction_progress: RwLock::new(0.0),
        }
    }

    pub async fn initialize(&self) -> Result<(), String> {
        // TODO: Initialize LSM storage
        // 1. Create data directory
        // 2. Replay WAL to recover MemTable
        // 3. Scan for existing SSTables
        // 4. Build level metadata
        // 5. Load bloom filters
        todo!("Implement LSM storage initialization")
    }

    pub async fn get(&self, _key: &str) -> Result<Option<(Vec<u8>, u64)>, String> {
        // TODO: Implement get operation
        // Search order (newest to oldest):
        // 1. Check active MemTable
        // 2. Check immutable MemTable (if any)
        // 3. Check L0 SSTables (may overlap, check all)
        // 4. Check L1+ SSTables (non-overlapping, binary search)
        // Use bloom filters to skip SSTables
        todo!("Implement LSM get")
    }

    pub async fn put(&self, _key: String, _value: Vec<u8>, _sync: bool) -> Result<u64, String> {
        // TODO: Implement put operation
        // 1. Write to WAL (if sync, fsync)
        // 2. Insert into MemTable
        // 3. If MemTable is full, trigger flush
        // 4. Return sequence number
        todo!("Implement LSM put")
    }

    pub async fn delete(&self, _key: String, _sync: bool) -> Result<u64, String> {
        // TODO: Implement delete operation
        // 1. Write tombstone to WAL
        // 2. Insert tombstone into MemTable
        // 3. Return sequence number
        todo!("Implement LSM delete")
    }

    pub async fn scan(
        &self,
        _start_key: &str,
        _end_key: Option<&str>,
        _limit: u32,
        _reverse: bool,
    ) -> Result<Vec<(String, Vec<u8>, u64)>, String> {
        // TODO: Implement range scan
        // 1. Create merge iterator over all sources
        // 2. Filter by key range
        // 3. Skip tombstones
        // 4. Return up to limit entries
        todo!("Implement LSM scan")
    }

    pub async fn flush_memtable(&self) -> Result<String, String> {
        // TODO: Implement MemTable flush
        // 1. Make current MemTable immutable
        // 2. Create new active MemTable
        // 3. Write immutable MemTable to SSTable in L0
        // 4. Create bloom filter for SSTable
        // 5. Update level metadata
        // 6. Clear WAL
        todo!("Implement MemTable flush")
    }

    pub async fn trigger_compaction(&self, _level: u32, _force: bool) -> Result<String, String> {
        // TODO: Trigger compaction
        // 1. Select SSTables to compact
        // 2. Start compaction in background
        // 3. Return job ID
        todo!("Implement compaction trigger")
    }

    pub async fn run_compaction(&self, _level: u32) -> Result<(), String> {
        // TODO: Run level compaction
        // For L0: Merge all L0 SSTables with overlapping L1 SSTables
        // For L1+: Pick SSTable, merge with overlapping SSTables in next level
        //
        // Steps:
        // 1. Select input SSTables
        // 2. Create merge iterator
        // 3. Write merged entries to new SSTable(s)
        // 4. Update level metadata atomically
        // 5. Delete old SSTable files
        todo!("Implement level compaction")
    }

    async fn get_next_sequence(&self) -> u64 {
        let mut seq = self.sequence_number.write().await;
        *seq += 1;
        *seq
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

pub struct KvLsmNode {
    node_id: String,
    port: u16,
    peers: Vec<String>,
    storage: Arc<LsmStorage>,

    // Replication state
    role: RwLock<NodeRole>,
    current_term: RwLock<u64>,
    voted_for: RwLock<Option<String>>,
    leader_id: RwLock<Option<String>>,
    commit_sequence: RwLock<u64>,

    // Peer clients
    peer_clients: RwLock<HashMap<String, ReplicationServiceClient<tonic::transport::Channel>>>,
}

impl KvLsmNode {
    pub fn new(node_id: String, port: u16, peers: Vec<String>, data_dir: String) -> Self {
        let storage = Arc::new(LsmStorage::new(data_dir, node_id.clone()));
        Self {
            node_id,
            port,
            peers,
            storage,
            role: RwLock::new(NodeRole::Follower),
            current_term: RwLock::new(0),
            voted_for: RwLock::new(None),
            leader_id: RwLock::new(None),
            commit_sequence: RwLock::new(0),
            peer_clients: RwLock::new(HashMap::new()),
        }
    }

    pub async fn initialize(&self) -> Result<(), Box<dyn std::error::Error>> {
        // TODO: Initialize node
        // 1. Initialize storage
        // 2. Connect to peers
        // 3. Start election timer
        // 4. Start background compaction
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
impl KvService for Arc<KvLsmNode> {
    async fn get(&self, request: Request<GetRequest>) -> Result<Response<GetResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement get
        // 1. Search through LSM levels
        // 2. Return most recent value

        let _ = (req.key, req.read_from_memtable_only);

        Ok(Response::new(GetResponse {
            value: vec![],
            found: false,
            sequence_number: 0,
            source: String::new(),
            error: "TODO: Implement get".to_string(),
            served_by: self.node_id.clone(),
        }))
    }

    async fn put(&self, request: Request<PutRequest>) -> Result<Response<PutResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement put
        // 1. If not leader, redirect
        // 2. Write to WAL and MemTable
        // 3. Replicate to followers
        // 4. Return after commit

        let role = *self.role.read().await;
        if role != NodeRole::Leader {
            let leader = self.leader_id.read().await;
            return Ok(Response::new(PutResponse {
                success: false,
                sequence_number: 0,
                error: format!("Not leader. Leader is: {:?}", leader),
                served_by: self.node_id.clone(),
            }));
        }

        let _ = (req.key, req.value, req.sync);

        Ok(Response::new(PutResponse {
            success: false,
            sequence_number: 0,
            error: "TODO: Implement put".to_string(),
            served_by: self.node_id.clone(),
        }))
    }

    async fn delete(&self, request: Request<DeleteRequest>) -> Result<Response<DeleteResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement delete
        // 1. If not leader, redirect
        // 2. Write tombstone
        // 3. Replicate to followers

        let role = *self.role.read().await;
        if role != NodeRole::Leader {
            return Ok(Response::new(DeleteResponse {
                success: false,
                sequence_number: 0,
                error: "Not leader".to_string(),
                served_by: self.node_id.clone(),
            }));
        }

        let _ = (req.key, req.sync);

        Ok(Response::new(DeleteResponse {
            success: false,
            sequence_number: 0,
            error: "TODO: Implement delete".to_string(),
            served_by: self.node_id.clone(),
        }))
    }

    async fn scan(&self, request: Request<ScanRequest>) -> Result<Response<ScanResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement scan
        // 1. Create merge iterator
        // 2. Scan in order

        let _ = (req.start_key, req.end_key, req.limit, req.reverse);

        Ok(Response::new(ScanResponse {
            entries: vec![],
            has_more: false,
            next_key: String::new(),
            error: "TODO: Implement scan".to_string(),
        }))
    }

    async fn batch_write(&self, request: Request<BatchWriteRequest>) -> Result<Response<BatchWriteResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement batch write
        // 1. Write all operations atomically
        // 2. Replicate batch to followers

        let role = *self.role.read().await;
        if role != NodeRole::Leader {
            return Ok(Response::new(BatchWriteResponse {
                success: false,
                sequence_number: 0,
                operations_count: 0,
                error: "Not leader".to_string(),
            }));
        }

        let _ = (req.operations, req.sync);

        Ok(Response::new(BatchWriteResponse {
            success: false,
            sequence_number: 0,
            operations_count: 0,
            error: "TODO: Implement batch write".to_string(),
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
        let sequence = *self.storage.sequence_number.read().await;

        let members: Vec<NodeInfo> = self.peers.iter().map(|p| {
            NodeInfo {
                node_id: String::new(),
                address: p.clone(),
                is_healthy: true,
                is_leader: false,
                sequence_number: 0,
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
            sequence_number: sequence,
            members,
        }))
    }
}

// =============================================================================
// StorageService Implementation
// =============================================================================

#[tonic::async_trait]
impl StorageService for Arc<KvLsmNode> {
    async fn flush_mem_table(&self, request: Request<FlushMemTableRequest>) -> Result<Response<FlushMemTableResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement MemTable flush
        // 1. Trigger flush
        // 2. Wait if requested

        let _ = req.wait_for_completion;

        Ok(Response::new(FlushMemTableResponse {
            success: false,
            sstable_id: String::new(),
            error: "TODO: Implement flush".to_string(),
        }))
    }

    async fn trigger_compaction(&self, request: Request<TriggerCompactionRequest>) -> Result<Response<TriggerCompactionResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement compaction trigger

        let _ = (req.level, req.force);

        Ok(Response::new(TriggerCompactionResponse {
            started: false,
            compaction_id: String::new(),
            error: "TODO: Implement compaction".to_string(),
        }))
    }

    async fn get_compaction_status(&self, request: Request<GetCompactionStatusRequest>) -> Result<Response<GetCompactionStatusResponse>, Status> {
        let _ = request.into_inner().compaction_id;
        let is_running = *self.storage.is_compacting.read().await;
        let progress = *self.storage.compaction_progress.read().await;

        Ok(Response::new(GetCompactionStatusResponse {
            is_running,
            current_level: 0,
            progress_percent: progress,
            input_bytes: 0,
            output_bytes: 0,
            entries_processed: 0,
            started_at: 0,
            completed_at: 0,
            error: String::new(),
        }))
    }

    async fn get_storage_stats(&self, _request: Request<GetStorageStatsRequest>) -> Result<Response<GetStorageStatsResponse>, Status> {
        let sequence = *self.storage.sequence_number.read().await;

        // TODO: Collect actual stats from storage

        Ok(Response::new(GetStorageStatsResponse {
            total_keys: 0,
            sequence_number: sequence,
            memtable: None,
            immutable_memtable: None,
            total_sstables: 0,
            total_storage_bytes: 0,
            live_data_bytes: 0,
            write_amplification: 0.0,
            read_amplification: 0.0,
            space_amplification: 0.0,
            last_compaction: 0,
            compaction_count: 0,
            bytes_compacted: 0,
        }))
    }

    async fn get_levels(&self, _request: Request<GetLevelsRequest>) -> Result<Response<GetLevelsResponse>, Status> {
        // TODO: Return level information

        Ok(Response::new(GetLevelsResponse {
            levels: vec![],
            memtable: None,
            total_sstables: 0,
        }))
    }
}

// =============================================================================
// ReplicationService Implementation
// =============================================================================

#[tonic::async_trait]
impl ReplicationService for Arc<KvLsmNode> {
    async fn append_entries(&self, request: Request<AppendEntriesRequest>) -> Result<Response<AppendEntriesResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement AppendEntries
        // 1. Check term
        // 2. Apply WAL entries
        // 3. Update commit index

        let current_term = *self.current_term.read().await;

        if req.term < current_term {
            return Ok(Response::new(AppendEntriesResponse {
                term: current_term,
                success: false,
                match_sequence: 0,
                error: "Term is stale".to_string(),
            }));
        }

        let _ = (req.leader_id, req.prev_sequence, req.prev_term, req.entries, req.leader_commit);

        Ok(Response::new(AppendEntriesResponse {
            term: current_term,
            success: false,
            match_sequence: 0,
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

        let _ = (req.candidate_id, req.last_sequence, req.last_term);

        Ok(Response::new(RequestVoteResponse {
            term: current_term,
            vote_granted: false,
        }))
    }

    async fn transfer_ss_table(&self, request: Request<TransferSsTableRequest>) -> Result<Response<TransferSsTableResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement SSTable transfer
        // 1. Receive SSTable chunks
        // 2. Write to disk
        // 3. Update metadata when complete

        let _ = (req.leader_id, req.metadata, req.data, req.offset, req.done);

        Ok(Response::new(TransferSsTableResponse {
            success: false,
            error: "TODO: Implement SSTable transfer".to_string(),
        }))
    }

    async fn heartbeat(&self, request: Request<HeartbeatRequest>) -> Result<Response<HeartbeatResponse>, Status> {
        let req = request.into_inner();

        // TODO: Handle heartbeat
        // 1. Update last seen time
        // 2. Reset election timer

        let _ = (req.node_id, req.timestamp, req.sequence_number);

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
#[command(name = "kv-store-lsm-server")]
#[command(about = "Distributed KV Store with LSM Tree")]
struct Args {
    /// Unique identifier for this node
    #[arg(long)]
    node_id: String,

    /// Port to listen on
    #[arg(long, default_value_t = 50051)]
    port: u16,

    /// Directory for data storage
    #[arg(long, default_value = "/tmp/kvlsm")]
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

    let node = Arc::new(KvLsmNode::new(
        args.node_id.clone(),
        args.port,
        peers,
        args.data_dir,
    ));

    // Note: initialize() needs to be implemented
    // node.initialize().await?;

    let addr = format!("0.0.0.0:{}", args.port).parse()?;
    println!(
        "Starting KV Store (LSM) node {} on port {}",
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
