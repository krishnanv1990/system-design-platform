//! Sliding Window Log Rate Limiter Implementation - Rust Template
//!
//! This template provides the basic structure for implementing the Sliding Window Log
//! rate limiting algorithm. You need to implement the TODO sections.
//!
//! The sliding window log algorithm works by:
//! 1. Each request's timestamp is stored in a sorted log
//! 2. When a request arrives, remove entries older than the window
//! 3. Count remaining entries; if under limit, allow and add new entry
//! 4. Provides precise rate limiting with no boundary issues
//!
//! Trade-off: More memory usage (stores all timestamps) but more accurate
//!
//! Usage:
//!     cargo run -- --node-id node1 --port 50051 --peers node2:50052,node3:50053

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tonic::{transport::Server, Request, Response, Status};
use clap::Parser;

// Include generated protobuf code
pub mod sliding_window_log {
    tonic::include_proto!("sliding_window_log");
}

use sliding_window_log::rate_limiter_service_server::{RateLimiterService, RateLimiterServiceServer};
use sliding_window_log::node_service_server::{NodeService, NodeServiceServer};
use sliding_window_log::node_service_client::NodeServiceClient;
use sliding_window_log::{
    AllowRequestRequest, AllowRequestResponse,
    GetLogStatusRequest, GetLogStatusResponse,
    ConfigureLimitRequest, ConfigureLimitResponse,
    DeleteLimitRequest, DeleteLimitResponse,
    GetLeaderRequest, GetLeaderResponse,
    GetClusterStatusRequest, GetClusterStatusResponse,
    SyncLogRequest, SyncLogResponse,
    AddEntryRequest, AddEntryResponse,
    HeartbeatRequest, HeartbeatResponse,
    GetLocalLogsRequest, GetLocalLogsResponse,
    LimitConfig, LogState, LogEntry, NodeInfo,
};

/// Entry in the sliding window log
#[derive(Clone, Debug)]
pub struct TimestampEntry {
    pub timestamp: i64,
    pub request_id: String,
}

/// Sliding window log state for a single rate limit
#[derive(Clone, Debug)]
pub struct SlidingLog {
    pub limit_id: String,
    pub max_requests: u64,
    pub window_size_ms: u64,
    pub entries: Vec<TimestampEntry>,
    pub total_requests: u64,
    pub total_allowed: u64,
    pub total_rejected: u64,
}

impl SlidingLog {
    pub fn new(config: &LimitConfig) -> Self {
        Self {
            limit_id: config.limit_id.clone(),
            max_requests: config.max_requests,
            window_size_ms: config.window_size_ms,
            entries: Vec::new(),
            total_requests: 0,
            total_allowed: 0,
            total_rejected: 0,
        }
    }

    /// Remove entries older than the sliding window.
    ///
    /// TODO: Implement cleanup of old entries
    /// 1. Get current timestamp
    /// 2. Calculate window start time (now - window_size_ms)
    /// 3. Remove all entries with timestamp < window_start
    pub fn cleanup_old_entries(&mut self) {
        // TODO: Implement entry cleanup
        // 1. Get current time in milliseconds
        // 2. Calculate cutoff time (now - window_size_ms)
        // 3. Remove entries older than cutoff
        // Hint: entries.retain(|e| e.timestamp >= cutoff)
        todo!("Implement cleanup of old entries")
    }

    /// Try to add a new request entry.
    ///
    /// TODO: Implement request logging
    /// 1. First call cleanup_old_entries() to remove stale entries
    /// 2. Check if entries.len() < max_requests
    /// 3. If yes, add new entry and return true
    /// 4. If no, return false
    pub fn try_add_entry(&mut self, request_id: String, timestamp: i64) -> bool {
        // TODO: Implement entry addition
        // 1. Cleanup old entries first
        // 2. Check if we have capacity
        // 3. Add entry if allowed
        let _ = (request_id, timestamp); // Remove this line when implementing
        todo!("Implement entry addition logic")
    }

    /// Get the current count of entries in the window.
    pub fn get_current_count(&self) -> u64 {
        self.entries.len() as u64
    }

    /// Get remaining capacity in the window.
    pub fn get_remaining(&self) -> u64 {
        let count = self.entries.len() as u64;
        if count >= self.max_requests {
            0
        } else {
            self.max_requests - count
        }
    }

    /// Get the oldest entry timestamp.
    pub fn get_oldest_entry(&self) -> Option<i64> {
        self.entries.first().map(|e| e.timestamp)
    }

    pub fn to_proto(&self, include_entries: bool) -> LogState {
        let entries = if include_entries {
            self.entries.iter().map(|e| LogEntry {
                timestamp: e.timestamp,
                request_id: e.request_id.clone(),
            }).collect()
        } else {
            Vec::new()
        };

        LogState {
            limit_id: self.limit_id.clone(),
            window_size_ms: self.window_size_ms,
            max_requests: self.max_requests,
            entries,
            current_count: self.entries.len() as u64,
            total_requests: self.total_requests,
            total_allowed: self.total_allowed,
            total_rejected: self.total_rejected,
        }
    }
}

/// Rate limiter node state
pub struct RateLimiterNode {
    node_id: String,
    port: u16,
    peers: Vec<String>,
    is_leader: RwLock<bool>,

    // Log storage
    logs: RwLock<HashMap<String, SlidingLog>>,

    // Cluster state
    peer_clients: RwLock<HashMap<String, NodeServiceClient<tonic::transport::Channel>>>,
    peer_health: RwLock<HashMap<String, bool>>,

    // Statistics
    total_requests_processed: RwLock<u64>,
    total_log_entries: RwLock<u64>,
}

impl RateLimiterNode {
    pub fn new(node_id: String, port: u16, peers: Vec<String>) -> Self {
        Self {
            node_id,
            port,
            peers,
            is_leader: RwLock::new(false),
            logs: RwLock::new(HashMap::new()),
            peer_clients: RwLock::new(HashMap::new()),
            peer_health: RwLock::new(HashMap::new()),
            total_requests_processed: RwLock::new(0),
            total_log_entries: RwLock::new(0),
        }
    }

    pub async fn initialize(&self) -> Result<(), Box<dyn std::error::Error>> {
        let mut clients = self.peer_clients.write().await;
        let mut health = self.peer_health.write().await;

        for peer in &self.peers {
            let addr = if peer.contains(".run.app") {
                format!("https://{}", peer)
            } else {
                format!("http://{}", peer)
            };

            match NodeServiceClient::connect(addr.clone()).await {
                Ok(client) => {
                    clients.insert(peer.clone(), client);
                    health.insert(peer.clone(), true);
                    println!("Connected to peer: {}", peer);
                }
                Err(e) => {
                    health.insert(peer.clone(), false);
                    eprintln!("Warning: Failed to connect to peer {}: {}", peer, e);
                }
            }
        }

        if self.peers.is_empty() {
            *self.is_leader.write().await = true;
        }

        println!("Node {} initialized on port {}", self.node_id, self.port);
        Ok(())
    }

    /// Synchronize log state to all peers.
    ///
    /// TODO: Implement log synchronization
    pub async fn sync_log_to_peers(&self, _log: &SlidingLog) {
        // TODO: Implement peer synchronization
        todo!("Implement log synchronization to peers")
    }

    /// Add entry across all nodes in cluster.
    ///
    /// TODO: Implement distributed entry addition
    /// - Send AddEntry RPC to all peers
    /// - Handle failures gracefully
    pub async fn distributed_add_entry(&self, _limit_id: &str, _entry: &TimestampEntry) -> Result<u64, String> {
        // TODO: Implement distributed entry addition
        todo!("Implement distributed entry addition")
    }

    /// Start background cleanup task.
    ///
    /// TODO: Implement periodic cleanup
    /// - Periodically call cleanup_old_entries() on all logs
    /// - Helps keep memory usage in check
    pub async fn start_cleanup_task(&self) {
        // TODO: Implement background cleanup
        todo!("Implement background cleanup task")
    }
}

#[tonic::async_trait]
impl RateLimiterService for Arc<RateLimiterNode> {
    /// Handle AllowRequest RPC - check if request should be allowed.
    ///
    /// TODO: Implement the rate limiting check:
    /// 1. Look up or create log for limit_id
    /// 2. Use provided timestamp or current time
    /// 3. Try to add entry to log
    /// 4. Update statistics
    /// 5. Return result with current count and remaining
    async fn allow_request(
        &self,
        request: Request<AllowRequestRequest>,
    ) -> Result<Response<AllowRequestResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement rate limiting logic
        // 1. Get or create log
        // 2. Determine timestamp (use provided or current time)
        // 3. Try to add entry
        // 4. Build response

        let _ = req; // Remove this line when implementing
        todo!("Implement allow_request handler")
    }

    async fn get_log_status(
        &self,
        request: Request<GetLogStatusRequest>,
    ) -> Result<Response<GetLogStatusResponse>, Status> {
        let req = request.into_inner();
        let logs = self.logs.read().await;

        let response = if let Some(log) = logs.get(&req.limit_id) {
            GetLogStatusResponse {
                log: Some(log.to_proto(req.include_entries)),
                found: true,
                error: String::new(),
            }
        } else {
            GetLogStatusResponse {
                log: None,
                found: false,
                error: String::new(),
            }
        };

        Ok(Response::new(response))
    }

    /// Handle ConfigureLimit RPC - create or update a rate limit.
    ///
    /// TODO: Implement limit configuration
    async fn configure_limit(
        &self,
        request: Request<ConfigureLimitRequest>,
    ) -> Result<Response<ConfigureLimitResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement limit configuration
        let _ = req; // Remove this line when implementing
        todo!("Implement configure_limit handler")
    }

    async fn delete_limit(
        &self,
        request: Request<DeleteLimitRequest>,
    ) -> Result<Response<DeleteLimitResponse>, Status> {
        let req = request.into_inner();
        let mut logs = self.logs.write().await;

        let removed = logs.remove(&req.limit_id).is_some();

        Ok(Response::new(DeleteLimitResponse {
            success: removed,
            error: if removed { String::new() } else { "Limit not found".to_string() },
        }))
    }

    async fn get_leader(
        &self,
        _request: Request<GetLeaderRequest>,
    ) -> Result<Response<GetLeaderResponse>, Status> {
        let is_leader = *self.is_leader.read().await;

        Ok(Response::new(GetLeaderResponse {
            node_id: self.node_id.clone(),
            node_address: format!("{}:{}", self.node_id, self.port),
            is_leader,
        }))
    }

    async fn get_cluster_status(
        &self,
        _request: Request<GetClusterStatusRequest>,
    ) -> Result<Response<GetClusterStatusResponse>, Status> {
        let is_leader = *self.is_leader.read().await;
        let logs = self.logs.read().await;
        let peer_health = self.peer_health.read().await;
        let total_requests = *self.total_requests_processed.read().await;
        let total_entries = *self.total_log_entries.read().await;

        let healthy_count = peer_health.values().filter(|&&h| h).count() as u32;

        let members: Vec<NodeInfo> = self.peers.iter().map(|peer| {
            NodeInfo {
                node_id: peer.clone(),
                address: peer.clone(),
                is_healthy: *peer_health.get(peer).unwrap_or(&false),
                limits_count: 0,
                entries_count: 0,
                last_heartbeat: 0,
            }
        }).collect();

        Ok(Response::new(GetClusterStatusResponse {
            node_id: self.node_id.clone(),
            node_address: format!("{}:{}", self.node_id, self.port),
            is_leader,
            total_nodes: (self.peers.len() + 1) as u32,
            healthy_nodes: healthy_count + 1,
            total_limits: logs.len() as u64,
            total_log_entries: total_entries,
            total_requests_processed: total_requests,
            members,
        }))
    }
}

#[tonic::async_trait]
impl NodeService for Arc<RateLimiterNode> {
    /// Handle SyncLog RPC - synchronize log state from another node.
    ///
    /// TODO: Implement log sync handling
    async fn sync_log(
        &self,
        request: Request<SyncLogRequest>,
    ) -> Result<Response<SyncLogResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement log synchronization from peer
        // 1. Get the log state from request
        // 2. Merge with local state (handle conflicts)
        // 3. Return success/failure

        let _ = req; // Remove this line when implementing
        todo!("Implement sync_log handler")
    }

    /// Handle AddEntry RPC - add a timestamp entry.
    ///
    /// TODO: Implement entry addition handling
    async fn add_entry(
        &self,
        request: Request<AddEntryRequest>,
    ) -> Result<Response<AddEntryResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement entry addition
        let _ = req; // Remove this line when implementing
        todo!("Implement add_entry handler")
    }

    async fn heartbeat(
        &self,
        request: Request<HeartbeatRequest>,
    ) -> Result<Response<HeartbeatResponse>, Status> {
        let req = request.into_inner();

        let mut health = self.peer_health.write().await;
        health.insert(req.node_id.clone(), true);

        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis() as i64;

        Ok(Response::new(HeartbeatResponse {
            acknowledged: true,
            timestamp: now,
        }))
    }

    async fn get_local_logs(
        &self,
        _request: Request<GetLocalLogsRequest>,
    ) -> Result<Response<GetLocalLogsResponse>, Status> {
        let logs = self.logs.read().await;

        let log_states: Vec<LogState> = logs.values()
            .map(|l| l.to_proto(false))
            .collect();

        Ok(Response::new(GetLocalLogsResponse {
            logs: log_states.clone(),
            total_count: log_states.len() as u64,
        }))
    }
}

#[derive(Parser, Debug)]
#[command(name = "sliding-window-log-server")]
#[command(about = "Sliding Window Log Rate Limiter Server")]
struct Args {
    /// Unique node identifier
    #[arg(long)]
    node_id: String,

    /// Port to listen on
    #[arg(long, default_value_t = 50051)]
    port: u16,

    /// Comma-separated list of peer addresses
    #[arg(long, default_value = "")]
    peers: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    let peers: Vec<String> = args.peers
        .split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    let node = Arc::new(RateLimiterNode::new(args.node_id.clone(), args.port, peers));
    node.initialize().await?;

    let addr = format!("0.0.0.0:{}", args.port).parse()?;

    println!("Starting Sliding Window Log Rate Limiter node {} on port {}", args.node_id, args.port);

    // Start background cleanup task
    {
        let node_clone = node.clone();
        tokio::spawn(async move {
            node_clone.start_cleanup_task().await;
        });
    }

    Server::builder()
        .add_service(RateLimiterServiceServer::new(node.clone()))
        .add_service(NodeServiceServer::new(node.clone()))
        .serve(addr)
        .await?;

    Ok(())
}
