//! Distributed KV Store with Append-Only Log - Rust Template
//!
//! This template provides the basic structure for implementing a distributed
//! key-value store using log-structured storage.
//!
//! Architecture:
//! 1. All writes are appended to an immutable log (fast writes)
//! 2. An in-memory hash table (KeyDir) maps keys to log offsets (fast reads)
//! 3. Compaction removes outdated entries to reclaim space
//! 4. Segments: log is divided into segments for easier management
//!
//! Similar to: Bitcask (used by Riak), early versions of Kafka
//!
//! You need to implement the TODO sections.
//!
//! Usage:
//!     cargo run -- --node-id node1 --port 50051 --data-dir /tmp/kvlog --peers node2:50052,node3:50053

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tonic::{transport::Server, Request, Response, Status};
use clap::Parser;

pub mod kvlog {
    tonic::include_proto!("kv_store_log");
}

use kvlog::kv_service_server::{KvService, KvServiceServer};
use kvlog::storage_service_server::{StorageService, StorageServiceServer};
use kvlog::replication_service_server::{ReplicationService, ReplicationServiceServer};
use kvlog::replication_service_client::ReplicationServiceClient;
use kvlog::*;

// =============================================================================
// Log Entry Types
// =============================================================================

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum LogEntryType {
    Put,
    Delete,
}

/// Represents a single entry in the append-only log
#[derive(Clone, Debug)]
pub struct LocalLogEntry {
    pub offset: u64,
    pub timestamp: u64,
    pub entry_type: LogEntryType,
    pub key: String,
    pub value: Vec<u8>,
    pub checksum: u32,
}

/// KeyDir entry - maps key to log location
#[derive(Clone, Debug)]
pub struct KeyDirEntry {
    pub segment_id: u64,
    pub offset: u64,
    pub size: u64,
    pub timestamp: u64,
}

/// Segment metadata
#[derive(Clone, Debug)]
pub struct SegmentMeta {
    pub id: u64,
    pub filename: String,
    pub start_offset: u64,
    pub end_offset: u64,
    pub size_bytes: u64,
    pub entry_count: u64,
    pub is_active: bool,
    pub is_compacted: bool,
    pub created_at: i64,
    pub last_modified: i64,
}

// =============================================================================
// Log-Structured Storage Engine
// =============================================================================

pub struct LogStorage {
    data_dir: String,
    node_id: String,

    // In-memory index (KeyDir)
    key_dir: RwLock<HashMap<String, KeyDirEntry>>,

    // Segment management
    segments: RwLock<Vec<SegmentMeta>>,
    active_segment_id: RwLock<u64>,
    current_offset: RwLock<u64>,

    // Compaction state
    is_compacting: RwLock<bool>,
    compaction_progress: RwLock<f64>,
}

impl LogStorage {
    pub fn new(data_dir: String, node_id: String) -> Self {
        Self {
            data_dir,
            node_id,
            key_dir: RwLock::new(HashMap::new()),
            segments: RwLock::new(Vec::new()),
            active_segment_id: RwLock::new(0),
            current_offset: RwLock::new(0),
            is_compacting: RwLock::new(false),
            compaction_progress: RwLock::new(0.0),
        }
    }

    pub async fn initialize(&self) -> Result<(), String> {
        // TODO: Initialize storage engine
        // 1. Create data directory if it doesn't exist
        // 2. Scan existing segments and build KeyDir from log
        // 3. Open or create active segment
        // 4. Recover from crash if needed
        todo!("Implement storage initialization")
    }

    pub async fn get(&self, _key: &str) -> Result<Option<(Vec<u8>, u64)>, String> {
        // TODO: Implement get operation
        // 1. Look up key in KeyDir
        // 2. If found, read value from log at the stored offset
        // 3. Verify checksum
        // 4. Return value and timestamp
        todo!("Implement get operation")
    }

    pub async fn put(&self, _key: &str, _value: &[u8], _ttl_ms: Option<u64>) -> Result<u64, String> {
        // TODO: Implement put operation
        // 1. Create log entry with timestamp and checksum
        // 2. Append entry to active segment
        // 3. Update KeyDir with new offset
        // 4. Check if segment needs rotation
        // 5. Return offset of written entry
        todo!("Implement put operation")
    }

    pub async fn delete(&self, _key: &str) -> Result<bool, String> {
        // TODO: Implement delete operation
        // 1. Check if key exists in KeyDir
        // 2. Write tombstone entry to log
        // 3. Remove key from KeyDir
        // 4. Return whether key existed
        todo!("Implement delete operation")
    }

    pub async fn scan(
        &self,
        _start_key: &str,
        _end_key: Option<&str>,
        _limit: u32,
    ) -> Result<Vec<(String, Vec<u8>, u64)>, String> {
        // TODO: Implement range scan
        // 1. Iterate through KeyDir entries in sorted order
        // 2. Filter by key range
        // 3. Read values from log
        // 4. Return up to limit entries
        // Note: This is inefficient with hash-based KeyDir, consider using a sorted structure
        todo!("Implement scan operation")
    }

    pub async fn trigger_compaction(&self, _force: bool) -> Result<String, String> {
        // TODO: Implement compaction trigger
        // 1. Check if compaction is already running
        // 2. Select segments to compact
        // 3. Start compaction in background
        // 4. Return compaction job ID
        todo!("Implement compaction trigger")
    }

    pub async fn run_compaction(&self, _segment_ids: Vec<u64>) -> Result<(), String> {
        // TODO: Implement compaction process
        // 1. Read all entries from selected segments
        // 2. Keep only the latest version of each key
        // 3. Write live entries to new segment
        // 4. Update KeyDir to point to new locations
        // 5. Mark old segments for deletion
        // 6. Delete old segment files
        todo!("Implement compaction")
    }

    fn calculate_checksum(&self, _data: &[u8]) -> u32 {
        // TODO: Implement CRC32 checksum calculation
        todo!("Implement checksum calculation")
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

pub struct KvLogNode {
    node_id: String,
    port: u16,
    peers: Vec<String>,
    storage: Arc<LogStorage>,

    // Replication state (Raft-like)
    role: RwLock<NodeRole>,
    current_term: RwLock<u64>,
    voted_for: RwLock<Option<String>>,
    leader_id: RwLock<Option<String>>,
    commit_offset: RwLock<u64>,

    // Peer clients
    peer_clients: RwLock<HashMap<String, ReplicationServiceClient<tonic::transport::Channel>>>,
}

impl KvLogNode {
    pub fn new(node_id: String, port: u16, peers: Vec<String>, data_dir: String) -> Self {
        let storage = Arc::new(LogStorage::new(data_dir, node_id.clone()));
        Self {
            node_id,
            port,
            peers,
            storage,
            role: RwLock::new(NodeRole::Follower),
            current_term: RwLock::new(0),
            voted_for: RwLock::new(None),
            leader_id: RwLock::new(None),
            commit_offset: RwLock::new(0),
            peer_clients: RwLock::new(HashMap::new()),
        }
    }

    pub async fn initialize(&self) -> Result<(), Box<dyn std::error::Error>> {
        // TODO: Initialize node
        // 1. Initialize storage
        // 2. Connect to peers
        // 3. Start election timer
        // 4. Start heartbeat sender (if leader)
        todo!("Implement node initialization")
    }

    async fn replicate_entry(&self, _entry: &LocalLogEntry) -> Result<bool, String> {
        // TODO: Replicate log entry to followers
        // 1. Send AppendEntries to all followers
        // 2. Wait for majority acknowledgment
        // 3. Commit entry if majority achieved
        todo!("Implement entry replication")
    }

    async fn start_election(&self) -> Result<bool, String> {
        // TODO: Implement leader election
        // 1. Increment term
        // 2. Vote for self
        // 3. Send RequestVote to all peers
        // 4. Become leader if majority votes received
        todo!("Implement leader election")
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
impl KvService for Arc<KvLogNode> {
    async fn get(&self, request: Request<GetRequest>) -> Result<Response<GetResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement get
        // 1. Read from local storage
        // 2. Return value if found

        let _ = req.key;

        Ok(Response::new(GetResponse {
            value: vec![],
            found: false,
            timestamp: 0,
            error: "TODO: Implement get".to_string(),
            served_by: self.node_id.clone(),
        }))
    }

    async fn put(&self, request: Request<PutRequest>) -> Result<Response<PutResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement put
        // 1. If not leader, redirect to leader
        // 2. Write to local log
        // 3. Replicate to followers
        // 4. Wait for commit
        // 5. Return success

        let role = *self.role.read().await;
        if role != NodeRole::Leader {
            let leader = self.leader_id.read().await;
            return Ok(Response::new(PutResponse {
                success: false,
                offset: 0,
                error: format!("Not leader. Leader is: {:?}", leader),
                served_by: self.node_id.clone(),
            }));
        }

        let _ = (req.key, req.value, req.ttl_ms);

        Ok(Response::new(PutResponse {
            success: false,
            offset: 0,
            error: "TODO: Implement put".to_string(),
            served_by: self.node_id.clone(),
        }))
    }

    async fn delete(&self, request: Request<DeleteRequest>) -> Result<Response<DeleteResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement delete
        // 1. If not leader, redirect to leader
        // 2. Write tombstone to log
        // 3. Replicate to followers
        // 4. Return success

        let role = *self.role.read().await;
        if role != NodeRole::Leader {
            let leader = self.leader_id.read().await;
            return Ok(Response::new(DeleteResponse {
                success: false,
                existed: false,
                error: format!("Not leader. Leader is: {:?}", leader),
                served_by: self.node_id.clone(),
            }));
        }

        let _ = req.key;

        Ok(Response::new(DeleteResponse {
            success: false,
            existed: false,
            error: "TODO: Implement delete".to_string(),
            served_by: self.node_id.clone(),
        }))
    }

    async fn scan(&self, request: Request<ScanRequest>) -> Result<Response<ScanResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement scan
        // 1. Scan local storage
        // 2. Return matching entries

        let _ = (req.start_key, req.end_key, req.limit);

        Ok(Response::new(ScanResponse {
            entries: vec![],
            has_more: false,
            next_key: String::new(),
            error: "TODO: Implement scan".to_string(),
        }))
    }

    async fn batch_put(&self, request: Request<BatchPutRequest>) -> Result<Response<BatchPutResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement batch put
        // 1. If not leader, redirect to leader
        // 2. Write all entries to log atomically
        // 3. Replicate to followers
        // 4. Return success

        let role = *self.role.read().await;
        if role != NodeRole::Leader {
            return Ok(Response::new(BatchPutResponse {
                success: false,
                entries_written: 0,
                error: "Not leader".to_string(),
            }));
        }

        let _ = req.entries;

        Ok(Response::new(BatchPutResponse {
            success: false,
            entries_written: 0,
            error: "TODO: Implement batch put".to_string(),
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
        let key_dir = self.storage.key_dir.read().await;
        let segments = self.storage.segments.read().await;

        let members: Vec<NodeInfo> = self.peers.iter().map(|p| {
            NodeInfo {
                node_id: String::new(),
                address: p.clone(),
                is_healthy: true,
                is_leader: false,
                keys_count: 0,
                log_offset: 0,
                last_heartbeat: 0,
            }
        }).collect();

        Ok(Response::new(GetClusterStatusResponse {
            node_id: self.node_id.clone(),
            node_address: format!("localhost:{}", self.port),
            is_leader: role == NodeRole::Leader,
            total_nodes: (self.peers.len() + 1) as u32,
            healthy_nodes: (self.peers.len() + 1) as u32,
            total_keys: key_dir.len() as u64,
            total_segments: segments.len() as u64,
            storage_bytes: segments.iter().map(|s| s.size_bytes).sum(),
            members,
        }))
    }
}

// =============================================================================
// StorageService Implementation
// =============================================================================

#[tonic::async_trait]
impl StorageService for Arc<KvLogNode> {
    async fn trigger_compaction(&self, request: Request<TriggerCompactionRequest>) -> Result<Response<TriggerCompactionResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement compaction trigger
        // 1. Start compaction in background
        // 2. Return job ID

        let _ = (req.force, req.segment_ids);

        Ok(Response::new(TriggerCompactionResponse {
            started: false,
            compaction_id: String::new(),
            error: "TODO: Implement compaction trigger".to_string(),
        }))
    }

    async fn get_compaction_status(&self, request: Request<GetCompactionStatusRequest>) -> Result<Response<GetCompactionStatusResponse>, Status> {
        let _ = request.into_inner().compaction_id;
        let is_running = *self.storage.is_compacting.read().await;
        let progress = *self.storage.compaction_progress.read().await;

        Ok(Response::new(GetCompactionStatusResponse {
            is_running,
            progress_percent: progress,
            entries_processed: 0,
            entries_removed: 0,
            bytes_reclaimed: 0,
            started_at: 0,
            completed_at: 0,
            error: String::new(),
        }))
    }

    async fn get_storage_stats(&self, _request: Request<GetStorageStatsRequest>) -> Result<Response<GetStorageStatsResponse>, Status> {
        let key_dir = self.storage.key_dir.read().await;
        let segments = self.storage.segments.read().await;

        let total_entries: u64 = segments.iter().map(|s| s.entry_count).sum();
        let total_storage: u64 = segments.iter().map(|s| s.size_bytes).sum();

        Ok(Response::new(GetStorageStatsResponse {
            total_keys: key_dir.len() as u64,
            total_entries,
            total_segments: segments.len() as u64,
            active_segment_size: segments.iter().find(|s| s.is_active).map(|s| s.size_bytes).unwrap_or(0),
            total_storage_bytes: total_storage,
            live_data_bytes: 0, // TODO: Calculate live data
            space_amplification: 0.0,
            last_compaction: 0,
            compaction_count: 0,
        }))
    }

    async fn get_segments(&self, _request: Request<GetSegmentsRequest>) -> Result<Response<GetSegmentsResponse>, Status> {
        // TODO: Return segment information
        // Convert local segments to proto format

        Ok(Response::new(GetSegmentsResponse {
            segments: vec![],
            total_count: 0,
        }))
    }
}

// =============================================================================
// ReplicationService Implementation
// =============================================================================

#[tonic::async_trait]
impl ReplicationService for Arc<KvLogNode> {
    async fn append_entries(&self, request: Request<AppendEntriesRequest>) -> Result<Response<AppendEntriesResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement AppendEntries (Raft-like)
        // 1. Check term
        // 2. Verify log consistency
        // 3. Append new entries
        // 4. Update commit index

        let current_term = *self.current_term.read().await;

        if req.term < current_term {
            return Ok(Response::new(AppendEntriesResponse {
                term: current_term,
                success: false,
                match_offset: 0,
                error: "Term is stale".to_string(),
            }));
        }

        let _ = (req.leader_id, req.prev_log_offset, req.prev_log_term, req.entries, req.leader_commit);

        Ok(Response::new(AppendEntriesResponse {
            term: current_term,
            success: false,
            match_offset: 0,
            error: "TODO: Implement append entries".to_string(),
        }))
    }

    async fn request_vote(&self, request: Request<RequestVoteRequest>) -> Result<Response<RequestVoteResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement RequestVote (Raft-like)
        // 1. Check term
        // 2. Check if already voted
        // 3. Check log completeness
        // 4. Grant vote if appropriate

        let current_term = *self.current_term.read().await;

        if req.term < current_term {
            return Ok(Response::new(RequestVoteResponse {
                term: current_term,
                vote_granted: false,
            }));
        }

        let _ = (req.candidate_id, req.last_log_offset, req.last_log_term);

        Ok(Response::new(RequestVoteResponse {
            term: current_term,
            vote_granted: false,
        }))
    }

    async fn install_snapshot(&self, request: Request<InstallSnapshotRequest>) -> Result<Response<InstallSnapshotResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement snapshot installation
        // 1. Verify term
        // 2. Write snapshot data to disk
        // 3. Rebuild KeyDir from snapshot
        // 4. Truncate log if needed

        let current_term = *self.current_term.read().await;

        let _ = (req.leader_id, req.last_included_offset, req.last_included_term, req.data, req.offset, req.done);

        Ok(Response::new(InstallSnapshotResponse {
            term: current_term,
            success: false,
        }))
    }

    async fn heartbeat(&self, request: Request<HeartbeatRequest>) -> Result<Response<HeartbeatResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement heartbeat handling
        // 1. Update last seen time for sender
        // 2. Reset election timer if from leader

        let _ = (req.node_id, req.timestamp, req.log_offset);

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
#[command(name = "kv-store-log-server")]
#[command(about = "Distributed KV Store with append-only log")]
struct Args {
    /// Unique identifier for this node
    #[arg(long)]
    node_id: String,

    /// Port to listen on
    #[arg(long, default_value_t = 50051)]
    port: u16,

    /// Directory for data storage
    #[arg(long, default_value = "/tmp/kvlog")]
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

    let node = Arc::new(KvLogNode::new(
        args.node_id.clone(),
        args.port,
        peers,
        args.data_dir,
    ));

    // Note: initialize() needs to be implemented
    // node.initialize().await?;

    let addr = format!("0.0.0.0:{}", args.port).parse()?;
    println!(
        "Starting KV Store (Log) node {} on port {}",
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
