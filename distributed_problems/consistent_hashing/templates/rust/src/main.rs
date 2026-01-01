//! Consistent Hashing Implementation - Rust Template
//!
//! This template provides the basic structure for implementing a
//! consistent hash ring for distributed key-value storage.
//!
//! Key concepts:
//! 1. Hash Ring - Keys and nodes are mapped to a circular hash space
//! 2. Virtual Nodes - Each physical node has multiple positions on the ring
//! 3. Lookup - Find the first node clockwise from the key's hash position
//! 4. Rebalancing - When nodes join/leave, only nearby keys need to move
//!
//! Usage:
//!     cargo run -- --node-id node1 --port 50051 --peers node2:50052,node3:50053

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tonic::{transport::Server, Request, Response, Status};
use clap::Parser;
use md5;

// Include generated protobuf code
pub mod consistent_hashing {
    tonic::include_proto!("consistent_hashing");
}

use consistent_hashing::hash_ring_service_server::{HashRingService, HashRingServiceServer};
use consistent_hashing::key_value_service_server::{KeyValueService, KeyValueServiceServer};
use consistent_hashing::node_service_server::{NodeService, NodeServiceServer};
use consistent_hashing::*;

const DEFAULT_VIRTUAL_NODES: u32 = 150;
const DEFAULT_REPLICATION_FACTOR: u32 = 3;

/// Virtual node on the hash ring
#[derive(Clone, Debug)]
pub struct VirtualNode {
    pub node_id: String,
    pub virtual_id: u32,
    pub hash_value: u64,
}

/// Physical node info
#[derive(Clone, Debug)]
pub struct NodeInfoInternal {
    pub node_id: String,
    pub address: String,
    pub virtual_nodes: u32,
    pub keys_count: u64,
    pub is_healthy: bool,
    pub last_heartbeat: u64,
}

/// Hash ring state
#[derive(Default)]
pub struct HashRingState {
    pub nodes: HashMap<String, NodeInfoInternal>,
    pub vnodes: Vec<VirtualNode>,
    pub replication_factor: u32,
    pub vnodes_per_node: u32,
}

/// Consistent hash ring implementation
pub struct ConsistentHashRingNode {
    node_id: String,
    port: u16,
    peers: Vec<String>,
    state: RwLock<HashRingState>,
    kv_store: RwLock<HashMap<String, String>>,
}

impl ConsistentHashRingNode {
    pub fn new(node_id: String, port: u16, peers: Vec<String>) -> Self {
        Self {
            node_id,
            port,
            peers,
            state: RwLock::new(HashRingState {
                nodes: HashMap::new(),
                vnodes: Vec::new(),
                replication_factor: DEFAULT_REPLICATION_FACTOR,
                vnodes_per_node: DEFAULT_VIRTUAL_NODES,
            }),
            kv_store: RwLock::new(HashMap::new()),
        }
    }

    pub async fn initialize(&self) -> Result<(), Box<dyn std::error::Error>> {
        // Add self to the ring
        let self_addr = format!("localhost:{}", self.port);
        self.add_node_internal(&self.node_id, &self_addr, DEFAULT_VIRTUAL_NODES).await;
        println!("Node {} initialized with peers: {:?}", self.node_id, self.peers);
        Ok(())
    }

    /// Hash a key to a position on the ring.
    ///
    /// TODO: Implement consistent hashing function:
    /// - Use a good hash function (MD5, SHA-1, etc.)
    /// - Return a value in the ring's hash space
    /// - Must be deterministic (same key always hashes to same position)
    pub fn hash(&self, key: &str) -> u64 {
        let digest = md5::compute(key.as_bytes());
        let bytes = digest.0;
        u64::from_be_bytes([
            bytes[0], bytes[1], bytes[2], bytes[3],
            bytes[4], bytes[5], bytes[6], bytes[7],
        ])
    }

    fn get_vnode_hash(&self, node_id: &str, virtual_id: u32) -> u64 {
        let key = format!("{}:{}", node_id, virtual_id);
        self.hash(&key)
    }

    /// Add a node to the hash ring.
    ///
    /// TODO: Implement node addition:
    /// 1. Create virtual nodes for this physical node
    /// 2. Insert virtual nodes into the ring (maintain sorted order)
    /// 3. Return list of added virtual nodes
    pub async fn add_node_internal(&self, node_id: &str, address: &str, num_vnodes: u32) -> Vec<VirtualNode> {
        let mut state = self.state.write().await;

        // Check if node already exists
        if state.nodes.contains_key(node_id) {
            return Vec::new();
        }

        // Create node info
        let node_info = NodeInfoInternal {
            node_id: node_id.to_string(),
            address: address.to_string(),
            virtual_nodes: num_vnodes,
            keys_count: 0,
            is_healthy: true,
            last_heartbeat: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_millis() as u64,
        };
        state.nodes.insert(node_id.to_string(), node_info);

        // Create virtual nodes
        let mut added_vnodes = Vec::new();
        for i in 0..num_vnodes {
            let vnode = VirtualNode {
                node_id: node_id.to_string(),
                virtual_id: i,
                hash_value: self.get_vnode_hash(node_id, i),
            };
            added_vnodes.push(vnode.clone());
            state.vnodes.push(vnode);
        }

        // Sort virtual nodes by hash value
        state.vnodes.sort_by_key(|v| v.hash_value);

        println!("Added node {} with {} virtual nodes", node_id, num_vnodes);
        added_vnodes
    }

    /// Remove a node from the hash ring.
    ///
    /// TODO: Implement node removal:
    /// 1. Remove all virtual nodes for this physical node
    /// 2. Update the ring structure
    /// 3. Return true if successful
    pub async fn remove_node_internal(&self, node_id: &str) -> bool {
        let mut state = self.state.write().await;

        if !state.nodes.contains_key(node_id) {
            return false;
        }

        // Remove virtual nodes
        state.vnodes.retain(|v| v.node_id != node_id);
        state.nodes.remove(node_id);

        println!("Removed node {}", node_id);
        true
    }

    /// Get the node responsible for a key.
    ///
    /// TODO: Implement key lookup:
    /// 1. Hash the key to find its position on the ring
    /// 2. Find the first node clockwise from that position
    /// 3. Handle wrap-around (if key hash > max vnode hash, use first node)
    pub async fn get_node_for_key(&self, key: &str) -> Option<NodeInfoInternal> {
        let state = self.state.read().await;

        if state.vnodes.is_empty() {
            return None;
        }

        let key_hash = self.hash(key);

        // Binary search for first vnode with hash >= key_hash
        let idx = match state.vnodes.binary_search_by_key(&key_hash, |v| v.hash_value) {
            Ok(i) => i,
            Err(i) => if i >= state.vnodes.len() { 0 } else { i },
        };

        let vnode = &state.vnodes[idx];
        state.nodes.get(&vnode.node_id).cloned()
    }

    /// Get multiple nodes for a key (for replication).
    ///
    /// TODO: Implement multi-node lookup:
    /// 1. Find the primary node for the key
    /// 2. Walk clockwise to find additional unique physical nodes
    /// 3. Return up to 'count' unique physical nodes
    pub async fn get_nodes_for_key(&self, key: &str, count: usize) -> Vec<NodeInfoInternal> {
        let state = self.state.read().await;

        if state.vnodes.is_empty() {
            return Vec::new();
        }

        let key_hash = self.hash(key);
        let start_idx = match state.vnodes.binary_search_by_key(&key_hash, |v| v.hash_value) {
            Ok(i) => i,
            Err(i) => if i >= state.vnodes.len() { 0 } else { i },
        };

        let mut result = Vec::new();
        let mut seen_nodes = std::collections::HashSet::new();

        for i in 0..state.vnodes.len() {
            if result.len() >= count {
                break;
            }
            let vnode = &state.vnodes[(start_idx + i) % state.vnodes.len()];
            if !seen_nodes.contains(&vnode.node_id) {
                seen_nodes.insert(vnode.node_id.clone());
                if let Some(node) = state.nodes.get(&vnode.node_id) {
                    result.push(node.clone());
                }
            }
        }

        result
    }
}

#[tonic::async_trait]
impl HashRingService for Arc<ConsistentHashRingNode> {
    async fn add_node(
        &self,
        request: Request<AddNodeRequest>,
    ) -> Result<Response<AddNodeResponse>, Status> {
        let req = request.into_inner();
        let num_vnodes = if req.virtual_nodes == 0 { DEFAULT_VIRTUAL_NODES } else { req.virtual_nodes };

        let vnodes = self.add_node_internal(&req.node_id, &req.address, num_vnodes).await;

        Ok(Response::new(AddNodeResponse {
            success: true,
            error: String::new(),
            added_vnodes: vnodes.iter().map(|v| consistent_hashing::VirtualNode {
                node_id: v.node_id.clone(),
                virtual_id: v.virtual_id,
                hash_value: v.hash_value,
            }).collect(),
            keys_to_transfer: 0,
        }))
    }

    async fn remove_node(
        &self,
        request: Request<RemoveNodeRequest>,
    ) -> Result<Response<RemoveNodeResponse>, Status> {
        let req = request.into_inner();
        let success = self.remove_node_internal(&req.node_id).await;

        Ok(Response::new(RemoveNodeResponse {
            success,
            error: if success { String::new() } else { "Node not found".to_string() },
            keys_transferred: 0,
        }))
    }

    async fn get_node(
        &self,
        request: Request<GetNodeRequest>,
    ) -> Result<Response<GetNodeResponse>, Status> {
        let req = request.into_inner();

        if let Some(node) = self.get_node_for_key(&req.key).await {
            Ok(Response::new(GetNodeResponse {
                node_id: node.node_id,
                node_address: node.address,
                key_hash: self.hash(&req.key),
            }))
        } else {
            Ok(Response::new(GetNodeResponse::default()))
        }
    }

    async fn get_nodes(
        &self,
        request: Request<GetNodesRequest>,
    ) -> Result<Response<GetNodesResponse>, Status> {
        let req = request.into_inner();
        let count = if req.count == 0 { 3 } else { req.count as usize };

        let nodes = self.get_nodes_for_key(&req.key, count).await;

        Ok(Response::new(GetNodesResponse {
            nodes: nodes.iter().map(|n| consistent_hashing::NodeInfo {
                node_id: n.node_id.clone(),
                address: n.address.clone(),
                virtual_nodes: n.virtual_nodes,
                keys_count: n.keys_count,
                is_healthy: n.is_healthy,
                last_heartbeat: n.last_heartbeat,
            }).collect(),
            key_hash: self.hash(&req.key),
        }))
    }

    async fn get_ring_state(
        &self,
        _request: Request<GetRingStateRequest>,
    ) -> Result<Response<GetRingStateResponse>, Status> {
        let state = self.state.read().await;

        let total_keys: u64 = state.nodes.values().map(|n| n.keys_count).sum();

        Ok(Response::new(GetRingStateResponse {
            nodes: state.nodes.values().map(|n| consistent_hashing::NodeInfo {
                node_id: n.node_id.clone(),
                address: n.address.clone(),
                virtual_nodes: n.virtual_nodes,
                keys_count: n.keys_count,
                is_healthy: n.is_healthy,
                last_heartbeat: n.last_heartbeat,
            }).collect(),
            vnodes: state.vnodes.iter().map(|v| consistent_hashing::VirtualNode {
                node_id: v.node_id.clone(),
                virtual_id: v.virtual_id,
                hash_value: v.hash_value,
            }).collect(),
            total_keys,
            replication_factor: state.replication_factor,
        }))
    }

    async fn rebalance(
        &self,
        _request: Request<RebalanceRequest>,
    ) -> Result<Response<RebalanceResponse>, Status> {
        // TODO: Implement rebalancing logic
        Ok(Response::new(RebalanceResponse {
            success: true,
            error: String::new(),
            keys_moved: 0,
            node_key_counts: HashMap::new(),
        }))
    }
}

#[tonic::async_trait]
impl KeyValueService for Arc<ConsistentHashRingNode> {
    async fn get(
        &self,
        request: Request<GetRequest>,
    ) -> Result<Response<GetResponse>, Status> {
        let req = request.into_inner();
        let kv_store = self.kv_store.read().await;

        if let Some(value) = kv_store.get(&req.key) {
            Ok(Response::new(GetResponse {
                value: value.clone(),
                found: true,
                error: String::new(),
                served_by: self.node_id.clone(),
            }))
        } else {
            Ok(Response::new(GetResponse {
                value: String::new(),
                found: false,
                error: String::new(),
                served_by: self.node_id.clone(),
            }))
        }
    }

    async fn put(
        &self,
        request: Request<PutRequest>,
    ) -> Result<Response<PutResponse>, Status> {
        let req = request.into_inner();

        {
            let mut kv_store = self.kv_store.write().await;
            kv_store.insert(req.key, req.value);
        }

        // Update keys count
        {
            let kv_store = self.kv_store.read().await;
            let mut state = self.state.write().await;
            if let Some(node) = state.nodes.get_mut(&self.node_id) {
                node.keys_count = kv_store.len() as u64;
            }
        }

        Ok(Response::new(PutResponse {
            success: true,
            error: String::new(),
            stored_on: self.node_id.clone(),
            replicated_to: Vec::new(),
        }))
    }

    async fn delete(
        &self,
        request: Request<DeleteRequest>,
    ) -> Result<Response<DeleteResponse>, Status> {
        let req = request.into_inner();

        let removed = {
            let mut kv_store = self.kv_store.write().await;
            kv_store.remove(&req.key).is_some()
        };

        if removed {
            let kv_store = self.kv_store.read().await;
            let mut state = self.state.write().await;
            if let Some(node) = state.nodes.get_mut(&self.node_id) {
                node.keys_count = kv_store.len() as u64;
            }
        }

        Ok(Response::new(DeleteResponse {
            success: removed,
            error: if removed { String::new() } else { "Key not found".to_string() },
        }))
    }

    async fn get_leader(
        &self,
        _request: Request<GetLeaderRequest>,
    ) -> Result<Response<GetLeaderResponse>, Status> {
        Ok(Response::new(GetLeaderResponse {
            node_id: self.node_id.clone(),
            node_address: format!("localhost:{}", self.port),
            is_coordinator: true,
        }))
    }

    async fn get_cluster_status(
        &self,
        _request: Request<GetClusterStatusRequest>,
    ) -> Result<Response<GetClusterStatusResponse>, Status> {
        let state = self.state.read().await;

        let total_keys: u64 = state.nodes.values().map(|n| n.keys_count).sum();
        let healthy_nodes = state.nodes.values().filter(|n| n.is_healthy).count() as u32;

        Ok(Response::new(GetClusterStatusResponse {
            node_id: self.node_id.clone(),
            node_address: format!("localhost:{}", self.port),
            is_coordinator: true,
            total_nodes: state.nodes.len() as u32,
            healthy_nodes,
            total_keys,
            replication_factor: state.replication_factor,
            virtual_nodes_per_node: state.vnodes_per_node,
            members: state.nodes.values().map(|n| consistent_hashing::NodeInfo {
                node_id: n.node_id.clone(),
                address: n.address.clone(),
                virtual_nodes: n.virtual_nodes,
                keys_count: n.keys_count,
                is_healthy: n.is_healthy,
                last_heartbeat: n.last_heartbeat,
            }).collect(),
            key_distribution_std_dev: 0.0,
        }))
    }
}

#[tonic::async_trait]
impl NodeService for Arc<ConsistentHashRingNode> {
    async fn transfer_keys(
        &self,
        request: Request<TransferKeysRequest>,
    ) -> Result<Response<TransferKeysResponse>, Status> {
        let req = request.into_inner();

        {
            let mut kv_store = self.kv_store.write().await;
            for kv in &req.keys {
                kv_store.insert(kv.key.clone(), kv.value.clone());
            }
        }

        // Update keys count
        {
            let kv_store = self.kv_store.read().await;
            let mut state = self.state.write().await;
            if let Some(node) = state.nodes.get_mut(&self.node_id) {
                node.keys_count = kv_store.len() as u64;
            }
        }

        Ok(Response::new(TransferKeysResponse {
            success: true,
            error: String::new(),
            keys_received: req.keys.len() as u64,
        }))
    }

    async fn heartbeat(
        &self,
        _request: Request<HeartbeatRequest>,
    ) -> Result<Response<HeartbeatResponse>, Status> {
        Ok(Response::new(HeartbeatResponse {
            acknowledged: true,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_millis() as u64,
        }))
    }

    async fn get_local_keys(
        &self,
        _request: Request<GetLocalKeysRequest>,
    ) -> Result<Response<GetLocalKeysResponse>, Status> {
        let kv_store = self.kv_store.read().await;

        Ok(Response::new(GetLocalKeysResponse {
            keys: kv_store.iter().map(|(k, v)| KeyValuePair {
                key: k.clone(),
                value: v.clone(),
                hash: self.hash(k),
            }).collect(),
            total_count: kv_store.len() as u64,
        }))
    }

    async fn store_local(
        &self,
        request: Request<StoreLocalRequest>,
    ) -> Result<Response<StoreLocalResponse>, Status> {
        let req = request.into_inner();

        {
            let mut kv_store = self.kv_store.write().await;
            kv_store.insert(req.key, req.value);
        }

        // Update keys count
        {
            let kv_store = self.kv_store.read().await;
            let mut state = self.state.write().await;
            if let Some(node) = state.nodes.get_mut(&self.node_id) {
                node.keys_count = kv_store.len() as u64;
            }
        }

        Ok(Response::new(StoreLocalResponse {
            success: true,
            error: String::new(),
        }))
    }

    async fn delete_local(
        &self,
        request: Request<DeleteLocalRequest>,
    ) -> Result<Response<DeleteLocalResponse>, Status> {
        let req = request.into_inner();

        let removed = {
            let mut kv_store = self.kv_store.write().await;
            kv_store.remove(&req.key).is_some()
        };

        if removed {
            let kv_store = self.kv_store.read().await;
            let mut state = self.state.write().await;
            if let Some(node) = state.nodes.get_mut(&self.node_id) {
                node.keys_count = kv_store.len() as u64;
            }
        }

        Ok(Response::new(DeleteLocalResponse {
            success: removed,
            error: if removed { String::new() } else { "Key not found".to_string() },
        }))
    }
}

#[derive(Parser, Debug)]
#[command(name = "consistent-hashing-server")]
#[command(about = "Consistent Hashing Server")]
struct Args {
    /// Unique node identifier
    #[arg(long)]
    node_id: String,

    /// Port to listen on
    #[arg(long, default_value_t = 50051)]
    port: u16,

    /// Comma-separated list of peer addresses
    #[arg(long)]
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

    let node = Arc::new(ConsistentHashRingNode::new(args.node_id.clone(), args.port, peers));
    node.initialize().await?;

    let addr = format!("0.0.0.0:{}", args.port).parse()?;

    println!("Starting Consistent Hashing node {} on port {}", args.node_id, args.port);

    Server::builder()
        .add_service(HashRingServiceServer::new(node.clone()))
        .add_service(KeyValueServiceServer::new(node.clone()))
        .add_service(NodeServiceServer::new(node.clone()))
        .serve(addr)
        .await?;

    Ok(())
}
