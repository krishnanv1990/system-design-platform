//! Fixed Window Counter Rate Limiter Implementation - Rust Template
//!
//! This template provides the basic structure for implementing the Fixed Window Counter
//! rate limiting algorithm. You need to implement the TODO sections.
//!
//! The fixed window counter algorithm works by:
//! 1. Time is divided into fixed windows (e.g., 1 minute each)
//! 2. Each window has a counter that tracks requests
//! 3. When a new window starts, the counter resets to zero
//! 4. Requests are rejected when counter exceeds the limit
//!
//! Note: This algorithm has the "boundary problem" - traffic can spike at window edges
//!
//! Usage:
//!     cargo run -- --node-id node1 --port 50051 --peers node2:50052,node3:50053

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tonic::{transport::Server, Request, Response, Status};
use clap::Parser;

// Include generated protobuf code
pub mod fixed_window_counter {
    tonic::include_proto!("fixed_window_counter");
}

use fixed_window_counter::rate_limiter_service_server::{RateLimiterService, RateLimiterServiceServer};
use fixed_window_counter::node_service_server::{NodeService, NodeServiceServer};
use fixed_window_counter::node_service_client::NodeServiceClient;
use fixed_window_counter::{
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

/// Fixed window state for a single rate limit
#[derive(Clone, Debug)]
pub struct FixedWindow {
    pub limit_id: String,
    pub max_requests: u64,
    pub window_size_ms: u64,
    pub window_start: u64,
    pub window_end: u64,
    pub current_count: u64,
    pub total_requests: u64,
    pub total_allowed: u64,
    pub total_rejected: u64,
}

impl FixedWindow {
    pub fn new(config: &LimitConfig) -> Self {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis() as u64;

        let window_start = (now / config.window_size_ms) * config.window_size_ms;
        let window_end = window_start + config.window_size_ms;

        Self {
            limit_id: config.limit_id.clone(),
            max_requests: config.max_requests,
            window_size_ms: config.window_size_ms,
            window_start,
            window_end,
            current_count: 0,
            total_requests: 0,
            total_allowed: 0,
            total_rejected: 0,
        }
    }

    /// Check if we need to start a new window and reset counter.
    ///
    /// TODO: Implement window rotation
    /// 1. Get current timestamp
    /// 2. Check if current time is past window_end
    /// 3. If yes, calculate new window boundaries and reset counter
    pub fn maybe_rotate_window(&mut self) {
        // TODO: Implement window rotation
        // 1. Get current time
        // 2. If now >= window_end, start new window
        // 3. Calculate new window_start and window_end
        // 4. Reset current_count to 0
        todo!("Implement window rotation logic")
    }

    /// Try to increment the counter for a request.
    ///
    /// TODO: Implement request counting
    /// 1. First call maybe_rotate_window() to ensure we're in the right window
    /// 2. Check if current_count + cost <= max_requests
    /// 3. If yes, increment counter and return true
    /// 4. If no, return false
    pub fn try_increment(&mut self, cost: u64) -> bool {
        // TODO: Implement counter increment
        // 1. Rotate window if needed
        // 2. Check if we have capacity
        // 3. Increment counter if allowed
        let _ = cost; // Remove this line when implementing
        todo!("Implement counter increment logic")
    }

    /// Get remaining requests in current window.
    pub fn get_remaining(&self) -> u64 {
        if self.current_count >= self.max_requests {
            0
        } else {
            self.max_requests - self.current_count
        }
    }

    /// Get time until window resets.
    pub fn get_reset_time(&self) -> u64 {
        self.window_end
    }

    pub fn to_proto(&self) -> WindowState {
        WindowState {
            limit_id: self.limit_id.clone(),
            window_start: self.window_start,
            window_end: self.window_end,
            current_count: self.current_count,
            max_requests: self.max_requests,
            window_size_ms: self.window_size_ms,
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
    windows: RwLock<HashMap<String, FixedWindow>>,

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
    pub async fn sync_window_to_peers(&self, _window: &FixedWindow) {
        // TODO: Implement peer synchronization
        todo!("Implement window synchronization to peers")
    }

    /// Atomically increment counter across cluster.
    ///
    /// TODO: Implement distributed counter increment
    /// - Send IncrementCounter RPC to all peers
    /// - Wait for majority acknowledgment
    /// - Return aggregated count
    pub async fn distributed_increment(&self, _limit_id: &str, _window_start: u64, _increment: u64) -> Result<u64, String> {
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
    /// 2. Try to increment counter with request cost
    /// 3. Update statistics
    /// 4. Optionally sync state to peers
    /// 5. Return result with current count and remaining
    async fn allow_request(
        &self,
        request: Request<AllowRequestRequest>,
    ) -> Result<Response<AllowRequestResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement rate limiting logic
        // 1. Get or create window
        // 2. Try to increment counter
        // 3. Build response

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
    /// 1. Verify window_start matches current window
    /// 2. Increment the counter
    /// 3. Return new count
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
#[command(name = "fixed-window-counter-server")]
#[command(about = "Fixed Window Counter Rate Limiter Server")]
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

    println!("Starting Fixed Window Counter Rate Limiter node {} on port {}", args.node_id, args.port);

    Server::builder()
        .add_service(RateLimiterServiceServer::new(node.clone()))
        .add_service(NodeServiceServer::new(node.clone()))
        .serve(addr)
        .await?;

    Ok(())
}
