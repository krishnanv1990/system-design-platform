//! Sliding Window Counter Rate Limiter Implementation - Rust Template
//!
//! This template provides the basic structure for implementing the Sliding Window Counter
//! rate limiting algorithm. You need to implement the TODO sections.
//!
//! The sliding window counter algorithm is a hybrid approach:
//! 1. Combines fixed window counter with sliding window
//! 2. Maintains counters for current and previous windows
//! 3. Uses weighted average based on position in current window
//! 4. Formula: count = prev_count * (1 - elapsed/window) + curr_count
//!
//! Trade-off: Low memory (only 2 counters) with good accuracy
//!
//! Usage:
//!     cargo run -- --node-id node1 --port 50051 --peers node2:50052,node3:50053

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tonic::{transport::Server, Request, Response, Status};
use clap::Parser;

// Include generated protobuf code
pub mod sliding_window_counter {
    tonic::include_proto!("sliding_window_counter");
}

use sliding_window_counter::rate_limiter_service_server::{RateLimiterService, RateLimiterServiceServer};
use sliding_window_counter::node_service_server::{NodeService, NodeServiceServer};
use sliding_window_counter::node_service_client::NodeServiceClient;
use sliding_window_counter::{
    AllowRequestRequest, AllowRequestResponse,
    GetWindowStatusRequest, GetWindowStatusResponse,
    ConfigureLimitRequest, ConfigureLimitResponse,
    DeleteLimitRequest, DeleteLimitResponse,
    GetLeaderRequest, GetLeaderResponse,
    GetClusterStatusRequest, GetClusterStatusResponse,
    SyncWindowRequest, SyncWindowResponse,
    IncrementCounterRequest, IncrementCounterResponse,
    HeartbeatRequest, HeartbeatResponse,
    GetLocalWindowsRequest, GetLocalWindowsResponse,
    LimitConfig, WindowState, NodeInfo,
};

/// Sliding window counter state for a single rate limit
#[derive(Clone, Debug)]
pub struct SlidingWindowCounter {
    pub limit_id: String,
    pub max_requests: u64,
    pub window_size_ms: u64,

    // Current window
    pub current_window_start: i64,
    pub current_count: u64,

    // Previous window
    pub previous_window_start: i64,
    pub previous_count: u64,

    // Statistics
    pub total_requests: u64,
    pub total_allowed: u64,
    pub total_rejected: u64,
}

impl SlidingWindowCounter {
    pub fn new(config: &LimitConfig) -> Self {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis() as i64;

        let window_size = config.window_size_ms as i64;
        let current_window_start = (now / window_size) * window_size;
        let previous_window_start = current_window_start - window_size;

        Self {
            limit_id: config.limit_id.clone(),
            max_requests: config.max_requests,
            window_size_ms: config.window_size_ms,
            current_window_start,
            current_count: 0,
            previous_window_start,
            previous_count: 0,
            total_requests: 0,
            total_allowed: 0,
            total_rejected: 0,
        }
    }

    /// Rotate windows if we've moved to a new time window.
    ///
    /// TODO: Implement window rotation
    /// 1. Get current timestamp
    /// 2. Calculate which window we should be in
    /// 3. If we've moved to a new window:
    ///    - Shift current window to previous
    ///    - Start new current window with count 0
    /// 4. If we've skipped multiple windows, reset both counters
    pub fn maybe_rotate_window(&mut self) {
        // TODO: Implement window rotation
        // 1. Get current time
        // 2. Calculate expected current_window_start
        // 3. If different from actual, rotate windows
        // Hint: Consider the case where multiple windows have passed
        todo!("Implement window rotation logic")
    }

    /// Calculate the sliding window estimate.
    ///
    /// TODO: Implement sliding window calculation
    /// Formula: estimate = previous_count * (1 - elapsed_ratio) + current_count
    /// Where elapsed_ratio = (now - current_window_start) / window_size
    ///
    /// This gives a weighted average that smoothly transitions between windows
    pub fn calculate_sliding_estimate(&self) -> f64 {
        // TODO: Implement sliding window estimate calculation
        // 1. Calculate elapsed time in current window
        // 2. Calculate ratio: elapsed / window_size
        // 3. Weight previous window by (1 - ratio)
        // 4. Add current window count
        // Return: previous_count * (1 - ratio) + current_count
        todo!("Implement sliding window estimate calculation")
    }

    /// Try to increment the counter for a request.
    ///
    /// TODO: Implement request counting
    /// 1. First call maybe_rotate_window() to ensure windows are current
    /// 2. Calculate sliding window estimate
    /// 3. Check if estimate + cost <= max_requests
    /// 4. If yes, increment current_count and return true
    /// 5. If no, return false
    pub fn try_increment(&mut self, cost: u64) -> bool {
        // TODO: Implement counter increment
        // 1. Rotate window if needed
        // 2. Calculate sliding estimate
        // 3. Check if we have capacity
        // 4. Increment current_count if allowed
        let _ = cost; // Remove this line when implementing
        todo!("Implement counter increment logic")
    }

    /// Get approximate remaining requests.
    pub fn get_remaining(&self) -> u64 {
        let estimate = self.calculate_sliding_estimate();
        if estimate >= self.max_requests as f64 {
            0
        } else {
            (self.max_requests as f64 - estimate) as u64
        }
    }

    /// Get time when current window ends.
    pub fn get_reset_time(&self) -> i64 {
        self.current_window_start + self.window_size_ms as i64
    }

    pub fn to_proto(&self) -> WindowState {
        WindowState {
            limit_id: self.limit_id.clone(),
            window_size_ms: self.window_size_ms,
            max_requests: self.max_requests,
            current_window_start: self.current_window_start,
            current_count: self.current_count,
            previous_window_start: self.previous_window_start,
            previous_count: self.previous_count,
            sliding_estimate: self.calculate_sliding_estimate(),
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

    // Window storage
    windows: RwLock<HashMap<String, SlidingWindowCounter>>,

    // Cluster state
    peer_clients: RwLock<HashMap<String, NodeServiceClient<tonic::transport::Channel>>>,
    peer_health: RwLock<HashMap<String, bool>>,

    // Statistics
    total_requests_processed: RwLock<u64>,
}

impl RateLimiterNode {
    pub fn new(node_id: String, port: u16, peers: Vec<String>) -> Self {
        Self {
            node_id,
            port,
            peers,
            is_leader: RwLock::new(false),
            windows: RwLock::new(HashMap::new()),
            peer_clients: RwLock::new(HashMap::new()),
            peer_health: RwLock::new(HashMap::new()),
            total_requests_processed: RwLock::new(0),
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

    /// Synchronize window state to all peers.
    ///
    /// TODO: Implement window synchronization
    pub async fn sync_window_to_peers(&self, _window: &SlidingWindowCounter) {
        // TODO: Implement peer synchronization
        todo!("Implement window synchronization to peers")
    }

    /// Atomically increment counter across cluster.
    ///
    /// TODO: Implement distributed counter increment
    pub async fn distributed_increment(&self, _limit_id: &str, _window_start: i64, _increment: u64) -> Result<u64, String> {
        // TODO: Implement distributed counter increment
        todo!("Implement distributed counter increment")
    }
}

#[tonic::async_trait]
impl RateLimiterService for Arc<RateLimiterNode> {
    /// Handle AllowRequest RPC - check if request should be allowed.
    ///
    /// TODO: Implement the rate limiting check:
    /// 1. Look up or create window for limit_id
    /// 2. Use provided timestamp or current time
    /// 3. Try to increment counter with request cost
    /// 4. Update statistics
    /// 5. Return result with sliding count and remaining
    async fn allow_request(
        &self,
        request: Request<AllowRequestRequest>,
    ) -> Result<Response<AllowRequestResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement rate limiting logic
        // 1. Get or create window
        // 2. Try to increment counter
        // 3. Build response with sliding_count

        let _ = req; // Remove this line when implementing
        todo!("Implement allow_request handler")
    }

    async fn get_window_status(
        &self,
        request: Request<GetWindowStatusRequest>,
    ) -> Result<Response<GetWindowStatusResponse>, Status> {
        let req = request.into_inner();
        let windows = self.windows.read().await;

        let response = if let Some(window) = windows.get(&req.limit_id) {
            GetWindowStatusResponse {
                window: Some(window.to_proto()),
                found: true,
                error: String::new(),
            }
        } else {
            GetWindowStatusResponse {
                window: None,
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
        let mut windows = self.windows.write().await;

        let removed = windows.remove(&req.limit_id).is_some();

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
        let windows = self.windows.read().await;
        let peer_health = self.peer_health.read().await;
        let total_requests = *self.total_requests_processed.read().await;

        let healthy_count = peer_health.values().filter(|&&h| h).count() as u32;

        let members: Vec<NodeInfo> = self.peers.iter().map(|peer| {
            NodeInfo {
                node_id: peer.clone(),
                address: peer.clone(),
                is_healthy: *peer_health.get(peer).unwrap_or(&false),
                limits_count: 0,
                last_heartbeat: 0,
            }
        }).collect();

        Ok(Response::new(GetClusterStatusResponse {
            node_id: self.node_id.clone(),
            node_address: format!("{}:{}", self.node_id, self.port),
            is_leader,
            total_nodes: (self.peers.len() + 1) as u32,
            healthy_nodes: healthy_count + 1,
            total_limits: windows.len() as u64,
            total_requests_processed: total_requests,
            members,
        }))
    }
}

#[tonic::async_trait]
impl NodeService for Arc<RateLimiterNode> {
    /// Handle SyncWindow RPC - synchronize window state from another node.
    ///
    /// TODO: Implement window sync handling
    async fn sync_window(
        &self,
        request: Request<SyncWindowRequest>,
    ) -> Result<Response<SyncWindowResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement window synchronization from peer
        let _ = req; // Remove this line when implementing
        todo!("Implement sync_window handler")
    }

    /// Handle IncrementCounter RPC - atomically increment counter.
    ///
    /// TODO: Implement counter increment handling
    async fn increment_counter(
        &self,
        request: Request<IncrementCounterRequest>,
    ) -> Result<Response<IncrementCounterResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement counter increment
        let _ = req; // Remove this line when implementing
        todo!("Implement increment_counter handler")
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

    async fn get_local_windows(
        &self,
        _request: Request<GetLocalWindowsRequest>,
    ) -> Result<Response<GetLocalWindowsResponse>, Status> {
        let windows = self.windows.read().await;

        let window_states: Vec<WindowState> = windows.values()
            .map(|w| w.to_proto())
            .collect();

        Ok(Response::new(GetLocalWindowsResponse {
            windows: window_states.clone(),
            total_count: window_states.len() as u64,
        }))
    }
}

#[derive(Parser, Debug)]
#[command(name = "sliding-window-counter-server")]
#[command(about = "Sliding Window Counter Rate Limiter Server")]
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

    println!("Starting Sliding Window Counter Rate Limiter node {} on port {}", args.node_id, args.port);

    Server::builder()
        .add_service(RateLimiterServiceServer::new(node.clone()))
        .add_service(NodeServiceServer::new(node.clone()))
        .serve(addr)
        .await?;

    Ok(())
}
