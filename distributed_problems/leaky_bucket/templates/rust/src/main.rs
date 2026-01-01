//! Leaky Bucket Rate Limiter Implementation - Rust Template
//!
//! This template provides the basic structure for implementing the Leaky Bucket
//! rate limiting algorithm. You need to implement the TODO sections.
//!
//! The leaky bucket algorithm works by:
//! 1. Requests enter a queue (bucket) with fixed capacity
//! 2. Requests are processed (leak) at a constant rate
//! 3. If the bucket is full, new requests are rejected
//! 4. Provides smooth, consistent output rate
//!
//! Usage:
//!     cargo run -- --node-id node1 --port 50051 --peers node2:50052,node3:50053

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tonic::{transport::Server, Request, Response, Status};
use clap::Parser;

// Include generated protobuf code
pub mod leaky_bucket {
    tonic::include_proto!("leaky_bucket");
}

use leaky_bucket::rate_limiter_service_server::{RateLimiterService, RateLimiterServiceServer};
use leaky_bucket::node_service_server::{NodeService, NodeServiceServer};
use leaky_bucket::node_service_client::NodeServiceClient;
use leaky_bucket::{
    AllowRequestRequest, AllowRequestResponse,
    GetBucketStatusRequest, GetBucketStatusResponse,
    ConfigureBucketRequest, ConfigureBucketResponse,
    DeleteBucketRequest, DeleteBucketResponse,
    GetLeaderRequest, GetLeaderResponse,
    GetClusterStatusRequest, GetClusterStatusResponse,
    SyncBucketRequest, SyncBucketResponse,
    HeartbeatRequest, HeartbeatResponse,
    GetLocalBucketsRequest, GetLocalBucketsResponse,
    BucketConfig, BucketState, QueuedRequest, NodeInfo,
};

/// Represents a request in the queue
#[derive(Clone, Debug)]
pub struct QueueEntry {
    pub request_id: String,
    pub enqueue_time: i64,
}

/// Leaky bucket state for a single bucket
#[derive(Clone, Debug)]
pub struct LeakyBucket {
    pub bucket_id: String,
    pub capacity: u64,
    pub leak_rate: f64,
    pub last_leak_time: i64,
    pub queue: Vec<QueueEntry>,
    pub total_requests: u64,
    pub allowed_requests: u64,
    pub rejected_requests: u64,
    pub processed_requests: u64,
}

impl LeakyBucket {
    pub fn new(config: &BucketConfig) -> Self {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis() as i64;

        Self {
            bucket_id: config.bucket_id.clone(),
            capacity: config.capacity,
            leak_rate: config.leak_rate,
            last_leak_time: now,
            queue: Vec::new(),
            total_requests: 0,
            allowed_requests: 0,
            rejected_requests: 0,
            processed_requests: 0,
        }
    }

    /// Process (leak) requests from the bucket based on elapsed time.
    ///
    /// TODO: Implement leak logic
    /// 1. Calculate elapsed time since last_leak_time
    /// 2. Calculate how many requests can be processed (leaked)
    /// 3. Remove processed requests from the front of the queue
    /// 4. Update last_leak_time and processed_requests counter
    pub fn leak(&mut self) {
        // TODO: Implement leak processing
        // Hint: requests_to_leak = floor(elapsed_seconds * leak_rate)
        // Remove that many requests from front of queue
        todo!("Implement leak processing logic")
    }

    /// Try to enqueue a new request.
    ///
    /// TODO: Implement enqueue logic
    /// 1. First call leak() to process any pending requests
    /// 2. Check if queue has capacity
    /// 3. If yes, add request to queue and return true
    /// 4. If no, return false (bucket full)
    pub fn try_enqueue(&mut self, request_id: String) -> bool {
        // TODO: Implement request enqueuing
        // 1. Leak first to free up space
        // 2. Check if queue.len() < capacity
        // 3. If yes, push to queue and return true
        // 4. If no, return false
        let _ = request_id; // Remove this line when implementing
        todo!("Implement enqueue logic")
    }

    /// Get current queue position for a request.
    pub fn get_queue_position(&self, request_id: &str) -> Option<usize> {
        self.queue.iter().position(|r| r.request_id == request_id)
    }

    /// Calculate estimated wait time for a new request.
    ///
    /// TODO: Implement wait time calculation
    /// Returns milliseconds until a request at current queue end would be processed
    pub fn calculate_estimated_wait(&self) -> u64 {
        // TODO: Calculate estimated wait time
        // Hint: wait_time = (queue.len() + 1) / leak_rate * 1000
        todo!("Implement wait time calculation")
    }

    pub fn to_proto(&self) -> BucketState {
        BucketState {
            bucket_id: self.bucket_id.clone(),
            queue_size: self.queue.len() as u64,
            capacity: self.capacity,
            leak_rate: self.leak_rate,
            last_leak_time: self.last_leak_time,
            total_requests: self.total_requests,
            allowed_requests: self.allowed_requests,
            rejected_requests: self.rejected_requests,
            processed_requests: self.processed_requests,
        }
    }

    pub fn get_queued_requests(&self) -> Vec<QueuedRequest> {
        self.queue.iter().enumerate().map(|(i, entry)| {
            let wait_per_request = if self.leak_rate > 0.0 {
                (1000.0 / self.leak_rate) as i64
            } else {
                0
            };
            QueuedRequest {
                request_id: entry.request_id.clone(),
                enqueue_time: entry.enqueue_time,
                estimated_process_time: entry.enqueue_time + (i as i64 + 1) * wait_per_request,
            }
        }).collect()
    }
}

/// Rate limiter node state
pub struct RateLimiterNode {
    node_id: String,
    port: u16,
    peers: Vec<String>,
    is_leader: RwLock<bool>,

    // Bucket storage
    buckets: RwLock<HashMap<String, LeakyBucket>>,

    // Cluster state
    peer_clients: RwLock<HashMap<String, NodeServiceClient<tonic::transport::Channel>>>,
    peer_health: RwLock<HashMap<String, bool>>,

    // Statistics
    total_queued_requests: RwLock<u64>,
    total_processed_requests: RwLock<u64>,
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
            total_queued_requests: RwLock::new(0),
            total_processed_requests: RwLock::new(0),
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

    /// Synchronize bucket state to all peers.
    ///
    /// TODO: Implement bucket synchronization
    pub async fn sync_bucket_to_peers(&self, _bucket: &LeakyBucket) {
        // TODO: Implement peer synchronization
        todo!("Implement bucket synchronization to peers")
    }

    /// Start background leak processor.
    ///
    /// TODO: Implement background processing
    /// - Periodically call leak() on all buckets
    /// - Run at appropriate interval based on leak rates
    pub async fn start_leak_processor(&self) {
        // TODO: Implement background leak processor
        // This should run in a loop, periodically processing all buckets
        todo!("Implement background leak processor")
    }
}

#[tonic::async_trait]
impl RateLimiterService for Arc<RateLimiterNode> {
    /// Handle AllowRequest RPC - check if request can be queued.
    ///
    /// TODO: Implement the rate limiting check:
    /// 1. Look up or create bucket for bucket_id
    /// 2. Try to enqueue the request
    /// 3. Update statistics
    /// 4. Return result with queue position or rejection
    async fn allow_request(
        &self,
        request: Request<AllowRequestRequest>,
    ) -> Result<Response<AllowRequestResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement rate limiting logic
        // 1. Get or create bucket
        // 2. Try to enqueue request
        // 3. Build response with queue position or rejection

        let _ = req; // Remove this line when implementing
        todo!("Implement allow_request handler")
    }

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
                queued_requests: bucket.get_queued_requests(),
            }
        } else {
            GetBucketStatusResponse {
                bucket: None,
                found: false,
                error: String::new(),
                queued_requests: Vec::new(),
            }
        };

        Ok(Response::new(response))
    }

    /// Handle ConfigureBucket RPC - create or update a bucket.
    ///
    /// TODO: Implement bucket configuration
    async fn configure_bucket(
        &self,
        request: Request<ConfigureBucketRequest>,
    ) -> Result<Response<ConfigureBucketResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement bucket configuration
        let _ = req; // Remove this line when implementing
        todo!("Implement configure_bucket handler")
    }

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
        let total_queued = *self.total_queued_requests.read().await;
        let total_processed = *self.total_processed_requests.read().await;

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
            total_queued_requests: total_queued,
            total_processed_requests: total_processed,
            members,
        }))
    }
}

#[tonic::async_trait]
impl NodeService for Arc<RateLimiterNode> {
    /// Handle SyncBucket RPC - synchronize bucket state from another node.
    ///
    /// TODO: Implement bucket sync handling
    async fn sync_bucket(
        &self,
        request: Request<SyncBucketRequest>,
    ) -> Result<Response<SyncBucketResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement bucket synchronization from peer
        let _ = req; // Remove this line when implementing
        todo!("Implement sync_bucket handler")
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
#[command(name = "leaky-bucket-server")]
#[command(about = "Leaky Bucket Rate Limiter Server")]
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

    println!("Starting Leaky Bucket Rate Limiter node {} on port {}", args.node_id, args.port);

    // Start background leak processor
    {
        let node_clone = node.clone();
        tokio::spawn(async move {
            node_clone.start_leak_processor().await;
        });
    }

    Server::builder()
        .add_service(RateLimiterServiceServer::new(node.clone()))
        .add_service(NodeServiceServer::new(node.clone()))
        .serve(addr)
        .await?;

    Ok(())
}
