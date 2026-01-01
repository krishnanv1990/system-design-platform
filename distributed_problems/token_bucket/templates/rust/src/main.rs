//! Token Bucket Rate Limiter Implementation - Rust Template
//!
//! This template provides the basic structure for implementing the Token Bucket
//! rate limiting algorithm. You need to implement the TODO sections.
//!
//! The token bucket algorithm works by:
//! 1. A bucket holds tokens up to a maximum capacity
//! 2. Tokens are added at a fixed rate (refill rate)
//! 3. Each request consumes one or more tokens
//! 4. If insufficient tokens, the request is rejected or queued
//!
//! Usage:
//!     cargo run -- --node-id node1 --port 50051 --peers node2:50052,node3:50053

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tonic::{transport::Server, Request, Response, Status};
use clap::Parser;

// Include generated protobuf code
pub mod token_bucket {
    tonic::include_proto!("token_bucket");
}

use token_bucket::rate_limiter_service_server::{RateLimiterService, RateLimiterServiceServer};
use token_bucket::node_service_server::{NodeService, NodeServiceServer};
use token_bucket::node_service_client::NodeServiceClient;
use token_bucket::{
    AllowRequestRequest, AllowRequestResponse,
    GetBucketStatusRequest, GetBucketStatusResponse,
    ConfigureBucketRequest, ConfigureBucketResponse,
    DeleteBucketRequest, DeleteBucketResponse,
    GetLeaderRequest, GetLeaderResponse,
    GetClusterStatusRequest, GetClusterStatusResponse,
    SyncBucketRequest, SyncBucketResponse,
    HeartbeatRequest, HeartbeatResponse,
    GetLocalBucketsRequest, GetLocalBucketsResponse,
    BucketConfig, BucketState, NodeInfo,
};

/// Token bucket state for a single bucket
#[derive(Clone, Debug)]
pub struct TokenBucket {
    pub bucket_id: String,
    pub current_tokens: f64,
    pub capacity: u64,
    pub refill_rate: f64,
    pub last_refill_time: i64,
    pub total_requests: u64,
    pub allowed_requests: u64,
    pub rejected_requests: u64,
}

impl TokenBucket {
    pub fn new(config: &BucketConfig) -> Self {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis() as i64;

        Self {
            bucket_id: config.bucket_id.clone(),
            current_tokens: config.initial_tokens as f64,
            capacity: config.capacity,
            refill_rate: config.refill_rate,
            last_refill_time: now,
            total_requests: 0,
            allowed_requests: 0,
            rejected_requests: 0,
        }
    }

    /// Refill tokens based on elapsed time since last refill.
    ///
    /// TODO: Implement token refill logic
    /// 1. Calculate elapsed time since last_refill_time
    /// 2. Calculate tokens to add based on refill_rate
    /// 3. Add tokens, capping at capacity
    /// 4. Update last_refill_time
    pub fn refill(&mut self) {
        // TODO: Implement token refill
        // Hint: tokens_to_add = elapsed_seconds * refill_rate
        // current_tokens = min(current_tokens + tokens_to_add, capacity)
        todo!("Implement token refill logic")
    }

    /// Try to consume tokens for a request.
    ///
    /// TODO: Implement token consumption
    /// 1. First call refill() to update token count
    /// 2. Check if enough tokens are available
    /// 3. If yes, consume tokens and return true
    /// 4. If no, return false
    pub fn try_consume(&mut self, tokens: u64) -> bool {
        // TODO: Implement token consumption
        // 1. Refill tokens first
        // 2. Check if enough tokens
        // 3. Consume and return true, or return false
        todo!("Implement token consumption")
    }

    /// Calculate retry time if request was rejected.
    ///
    /// TODO: Implement retry time calculation
    /// Returns milliseconds until enough tokens will be available
    pub fn calculate_retry_after(&self, tokens_needed: u64) -> u64 {
        // TODO: Calculate when enough tokens will be available
        // Hint: time_needed = (tokens_needed - current_tokens) / refill_rate
        todo!("Implement retry time calculation")
    }

    pub fn to_proto(&self) -> BucketState {
        BucketState {
            bucket_id: self.bucket_id.clone(),
            current_tokens: self.current_tokens,
            capacity: self.capacity,
            refill_rate: self.refill_rate,
            last_refill_time: self.last_refill_time,
            total_requests: self.total_requests,
            allowed_requests: self.allowed_requests,
            rejected_requests: self.rejected_requests,
        }
    }
}

/// Rate limiter node state
pub struct RateLimiterNode {
    node_id: String,
    port: u16,
    peers: Vec<String>,
    is_leader: RwLock<bool>,

    // Bucket storage
    buckets: RwLock<HashMap<String, TokenBucket>>,

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
            buckets: RwLock::new(HashMap::new()),
            peer_clients: RwLock::new(HashMap::new()),
            peer_health: RwLock::new(HashMap::new()),
            total_requests_processed: RwLock::new(0),
        }
    }

    pub async fn initialize(&self) -> Result<(), Box<dyn std::error::Error>> {
        // Initialize peer connections
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

        // First node becomes leader by default
        if self.peers.is_empty() {
            *self.is_leader.write().await = true;
        }

        println!("Node {} initialized on port {}", self.node_id, self.port);
        Ok(())
    }

    /// Synchronize bucket state to all peers.
    ///
    /// TODO: Implement bucket synchronization
    /// - Send SyncBucket RPC to all healthy peers
    /// - Handle failures gracefully
    pub async fn sync_bucket_to_peers(&self, _bucket: &TokenBucket) {
        // TODO: Implement peer synchronization
        // 1. Get list of healthy peer clients
        // 2. Send SyncBucket RPC to each peer
        // 3. Handle any errors
        todo!("Implement bucket synchronization to peers")
    }
}

#[tonic::async_trait]
impl RateLimiterService for Arc<RateLimiterNode> {
    /// Handle AllowRequest RPC - check if request should be allowed.
    ///
    /// TODO: Implement the rate limiting check:
    /// 1. Look up or create bucket for bucket_id
    /// 2. Try to consume requested tokens
    /// 3. Update statistics
    /// 4. Optionally sync state to peers
    /// 5. Return result with remaining tokens or retry time
    async fn allow_request(
        &self,
        request: Request<AllowRequestRequest>,
    ) -> Result<Response<AllowRequestResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement rate limiting logic
        // 1. Get or create bucket
        // 2. Try to consume tokens
        // 3. Build response

        let _ = req; // Remove this line when implementing
        todo!("Implement allow_request handler")
    }

    /// Handle GetBucketStatus RPC - return bucket state.
    async fn get_bucket_status(
        &self,
        request: Request<GetBucketStatusRequest>,
    ) -> Result<Response<GetBucketStatusResponse>, Status> {
        let req = request.into_inner();
        let buckets = self.buckets.read().await;

        let response = if let Some(bucket) = buckets.get(&req.bucket_id) {
            GetBucketStatusResponse {
                bucket: Some(bucket.to_proto()),
                found: true,
                error: String::new(),
            }
        } else {
            GetBucketStatusResponse {
                bucket: None,
                found: false,
                error: String::new(),
            }
        };

        Ok(Response::new(response))
    }

    /// Handle ConfigureBucket RPC - create or update a bucket.
    ///
    /// TODO: Implement bucket configuration:
    /// 1. Validate configuration
    /// 2. Create new bucket or update existing
    /// 3. Sync to peers if leader
    async fn configure_bucket(
        &self,
        request: Request<ConfigureBucketRequest>,
    ) -> Result<Response<ConfigureBucketResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement bucket configuration
        // 1. Validate config
        // 2. Create or update bucket
        // 3. Sync to peers

        let _ = req; // Remove this line when implementing
        todo!("Implement configure_bucket handler")
    }

    /// Handle DeleteBucket RPC - remove a bucket.
    async fn delete_bucket(
        &self,
        request: Request<DeleteBucketRequest>,
    ) -> Result<Response<DeleteBucketResponse>, Status> {
        let req = request.into_inner();
        let mut buckets = self.buckets.write().await;

        let removed = buckets.remove(&req.bucket_id).is_some();

        Ok(Response::new(DeleteBucketResponse {
            success: removed,
            error: if removed { String::new() } else { "Bucket not found".to_string() },
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
        let buckets = self.buckets.read().await;
        let peer_health = self.peer_health.read().await;
        let total_requests = *self.total_requests_processed.read().await;

        let healthy_count = peer_health.values().filter(|&&h| h).count() as u32;

        let members: Vec<NodeInfo> = self.peers.iter().map(|peer| {
            NodeInfo {
                node_id: peer.clone(),
                address: peer.clone(),
                is_healthy: *peer_health.get(peer).unwrap_or(&false),
                buckets_count: 0,
                last_heartbeat: 0,
            }
        }).collect();

        Ok(Response::new(GetClusterStatusResponse {
            node_id: self.node_id.clone(),
            node_address: format!("{}:{}", self.node_id, self.port),
            is_leader,
            total_nodes: (self.peers.len() + 1) as u32,
            healthy_nodes: healthy_count + 1,
            total_buckets: buckets.len() as u64,
            total_requests_processed: total_requests,
            members,
        }))
    }
}

#[tonic::async_trait]
impl NodeService for Arc<RateLimiterNode> {
    /// Handle SyncBucket RPC - synchronize bucket state from another node.
    ///
    /// TODO: Implement bucket sync handling:
    /// 1. Validate the incoming bucket state
    /// 2. Merge with local state (handle conflicts)
    /// 3. Return success/failure
    async fn sync_bucket(
        &self,
        request: Request<SyncBucketRequest>,
    ) -> Result<Response<SyncBucketResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement bucket synchronization from peer
        // 1. Get the bucket state from request
        // 2. Update local bucket state
        // 3. Handle merge conflicts if needed

        let _ = req; // Remove this line when implementing
        todo!("Implement sync_bucket handler")
    }

    async fn heartbeat(
        &self,
        request: Request<HeartbeatRequest>,
    ) -> Result<Response<HeartbeatResponse>, Status> {
        let req = request.into_inner();

        // Update peer health status
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

    async fn get_local_buckets(
        &self,
        _request: Request<GetLocalBucketsRequest>,
    ) -> Result<Response<GetLocalBucketsResponse>, Status> {
        let buckets = self.buckets.read().await;

        let bucket_states: Vec<BucketState> = buckets.values()
            .map(|b| b.to_proto())
            .collect();

        Ok(Response::new(GetLocalBucketsResponse {
            buckets: bucket_states.clone(),
            total_count: bucket_states.len() as u64,
        }))
    }
}

#[derive(Parser, Debug)]
#[command(name = "token-bucket-server")]
#[command(about = "Token Bucket Rate Limiter Server")]
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

    println!("Starting Token Bucket Rate Limiter node {} on port {}", args.node_id, args.port);

    Server::builder()
        .add_service(RateLimiterServiceServer::new(node.clone()))
        .add_service(NodeServiceServer::new(node.clone()))
        .serve(addr)
        .await?;

    Ok(())
}
