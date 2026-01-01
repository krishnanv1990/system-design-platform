//! Rendezvous Hashing (Highest Random Weight) Implementation in Rust
//!
//! Rendezvous hashing assigns keys to nodes by computing a deterministic weight
//! for each (key, node) pair and selecting the node with the maximum weight.
//!
//! Key benefits:
//! - O(n) lookup where n is number of nodes (acceptable for moderate cluster sizes)
//! - Minimal disruption: only keys on removed node are redistributed
//! - No virtual nodes needed for even distribution
//! - Trivial to implement weighted nodes (multiply weight by capacity factor)
//!
//! Your task: Implement the weight calculation and node selection logic.

use md5::{Md5, Digest};
use std::collections::HashMap;
use std::env;
use std::fs;
use std::sync::Arc;
use tokio::sync::RwLock;
use tonic::{transport::Server, Request, Response, Status};
use tonic::transport::{Identity, ServerTlsConfig};

pub mod rendezvous_hashing {
    tonic::include_proto!("rendezvous_hashing");
}

use rendezvous_hashing::{
    node_registry_service_server::{NodeRegistryService, NodeRegistryServiceServer},
    rendezvous_service_server::{RendezvousService, RendezvousServiceServer},
    key_value_service_server::{KeyValueService, KeyValueServiceServer},
    AddNodeRequest, AddNodeResponse,
    RemoveNodeRequest, RemoveNodeResponse,
    ListNodesRequest, ListNodesResponse,
    GetNodeInfoRequest, GetNodeInfoResponse,
    GetNodeForKeyRequest, GetNodeForKeyResponse,
    GetNodesForKeyRequest, GetNodesForKeyResponse,
    CalculateWeightRequest, CalculateWeightResponse,
    PutRequest, PutResponse,
    GetRequest, GetResponse,
    DeleteRequest, DeleteResponse,
    NodeInfo, NodeWithWeight,
};

/// State for the Rendezvous Hashing node
#[derive(Debug)]
pub struct RendezvousHashingNode {
    node_id: String,
    nodes: Arc<RwLock<HashMap<String, NodeInfo>>>,
    local_store: Arc<RwLock<HashMap<String, Vec<u8>>>>,
}

impl RendezvousHashingNode {
    pub fn new(node_id: String) -> Self {
        RendezvousHashingNode {
            node_id,
            nodes: Arc::new(RwLock::new(HashMap::new())),
            local_store: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Calculate the weight for a key-node pair.
    ///
    /// The weight should be deterministic and uniformly distributed.
    /// Common approach: hash(key + node_id) converted to f64.
    ///
    /// # Arguments
    /// * `key` - The key to calculate weight for
    /// * `node_id` - The node identifier
    /// * `capacity_weight` - Multiplier for node capacity (default 1.0)
    ///
    /// # Returns
    /// A floating point weight value
    ///
    /// TODO: Implement the weight calculation
    /// Hint: Use md5 to hash key + node_id, convert first 8 bytes to u64,
    ///       normalize to [0, 1), multiply by capacity_weight
    pub fn calculate_weight(&self, key: &str, node_id: &str, capacity_weight: f64) -> f64 {
        // TODO: Implement weight calculation
        // 1. Concatenate key and node_id
        // 2. Hash the concatenated string using MD5
        // 3. Convert hash bytes to a f64 in range [0, 1)
        // 4. Multiply by capacity_weight
        0.0
    }

    /// Get the node with the highest weight for a given key.
    ///
    /// # Arguments
    /// * `key` - The key to look up
    /// * `nodes` - Reference to nodes map (already locked)
    ///
    /// # Returns
    /// Option of (node_id, weight) or None if no nodes
    ///
    /// TODO: Implement rendezvous hashing node selection
    pub fn get_node_for_key(&self, key: &str, nodes: &HashMap<String, NodeInfo>) -> Option<(String, f64)> {
        if nodes.is_empty() {
            return None;
        }

        // TODO: Implement rendezvous hashing
        // 1. For each active node, calculate weight(key, node_id)
        // 2. Return the node with the highest weight
        None
    }

    /// Get the top N nodes for a key (useful for replication).
    ///
    /// # Arguments
    /// * `key` - The key to look up
    /// * `count` - Number of nodes to return
    /// * `nodes` - Reference to nodes map (already locked)
    ///
    /// # Returns
    /// Vector of (node_id, weight) tuples, sorted by weight descending
    ///
    /// TODO: Implement multi-node selection
    pub fn get_nodes_for_key(&self, key: &str, count: usize, nodes: &HashMap<String, NodeInfo>) -> Vec<(String, f64)> {
        if nodes.is_empty() {
            return vec![];
        }

        // TODO: Implement top-N node selection
        // 1. Calculate weights for all active nodes
        // 2. Sort by weight descending
        // 3. Return top 'count' nodes
        vec![]
    }
}

// Clone implementation for service handlers
impl Clone for RendezvousHashingNode {
    fn clone(&self) -> Self {
        RendezvousHashingNode {
            node_id: self.node_id.clone(),
            nodes: Arc::clone(&self.nodes),
            local_store: Arc::clone(&self.local_store),
        }
    }
}

#[tonic::async_trait]
impl NodeRegistryService for RendezvousHashingNode {
    async fn add_node(
        &self,
        request: Request<AddNodeRequest>,
    ) -> Result<Response<AddNodeResponse>, Status> {
        let req = request.into_inner();
        let capacity_weight = if req.capacity_weight > 0.0 {
            req.capacity_weight
        } else {
            1.0
        };

        let node_info = NodeInfo {
            node_id: req.node_id.clone(),
            address: req.address,
            port: req.port,
            capacity_weight,
            is_active: true,
        };

        let mut nodes = self.nodes.write().await;
        nodes.insert(req.node_id.clone(), node_info);

        Ok(Response::new(AddNodeResponse {
            success: true,
            message: format!("Node {} added successfully", req.node_id),
        }))
    }

    async fn remove_node(
        &self,
        request: Request<RemoveNodeRequest>,
    ) -> Result<Response<RemoveNodeResponse>, Status> {
        let req = request.into_inner();
        let mut nodes = self.nodes.write().await;

        if nodes.remove(&req.node_id).is_some() {
            Ok(Response::new(RemoveNodeResponse {
                success: true,
                message: format!("Node {} removed", req.node_id),
                keys_to_redistribute: 0,
            }))
        } else {
            Ok(Response::new(RemoveNodeResponse {
                success: false,
                message: format!("Node {} not found", req.node_id),
                keys_to_redistribute: 0,
            }))
        }
    }

    async fn list_nodes(
        &self,
        _request: Request<ListNodesRequest>,
    ) -> Result<Response<ListNodesResponse>, Status> {
        let nodes = self.nodes.read().await;
        let node_list: Vec<NodeInfo> = nodes.values().cloned().collect();

        Ok(Response::new(ListNodesResponse { nodes: node_list }))
    }

    async fn get_node_info(
        &self,
        request: Request<GetNodeInfoRequest>,
    ) -> Result<Response<GetNodeInfoResponse>, Status> {
        let req = request.into_inner();
        let nodes = self.nodes.read().await;

        if let Some(node) = nodes.get(&req.node_id) {
            Ok(Response::new(GetNodeInfoResponse {
                node: Some(node.clone()),
                found: true,
            }))
        } else {
            Ok(Response::new(GetNodeInfoResponse {
                node: None,
                found: false,
            }))
        }
    }
}

#[tonic::async_trait]
impl RendezvousService for RendezvousHashingNode {
    async fn get_node_for_key(
        &self,
        request: Request<GetNodeForKeyRequest>,
    ) -> Result<Response<GetNodeForKeyResponse>, Status> {
        let req = request.into_inner();
        let nodes = self.nodes.read().await;

        match self.get_node_for_key(&req.key, &nodes) {
            Some((node_id, weight)) => Ok(Response::new(GetNodeForKeyResponse {
                node_id,
                weight,
            })),
            None => Err(Status::not_found("No nodes available")),
        }
    }

    async fn get_nodes_for_key(
        &self,
        request: Request<GetNodesForKeyRequest>,
    ) -> Result<Response<GetNodesForKeyResponse>, Status> {
        let req = request.into_inner();
        let nodes = self.nodes.read().await;

        let result = self.get_nodes_for_key(&req.key, req.count as usize, &nodes);

        Ok(Response::new(GetNodesForKeyResponse {
            nodes: result
                .into_iter()
                .map(|(node_id, weight)| NodeWithWeight { node_id, weight })
                .collect(),
        }))
    }

    async fn calculate_weight(
        &self,
        request: Request<CalculateWeightRequest>,
    ) -> Result<Response<CalculateWeightResponse>, Status> {
        let req = request.into_inner();
        let nodes = self.nodes.read().await;

        let capacity = nodes
            .get(&req.node_id)
            .map(|n| n.capacity_weight)
            .unwrap_or(1.0);

        let weight = self.calculate_weight(&req.key, &req.node_id, capacity);

        Ok(Response::new(CalculateWeightResponse { weight }))
    }
}

#[tonic::async_trait]
impl KeyValueService for RendezvousHashingNode {
    async fn put(
        &self,
        request: Request<PutRequest>,
    ) -> Result<Response<PutResponse>, Status> {
        let req = request.into_inner();
        let mut store = self.local_store.write().await;
        store.insert(req.key, req.value);

        Ok(Response::new(PutResponse {
            success: true,
            stored_on_nodes: vec![self.node_id.clone()],
        }))
    }

    async fn get(
        &self,
        request: Request<GetRequest>,
    ) -> Result<Response<GetResponse>, Status> {
        let req = request.into_inner();
        let store = self.local_store.read().await;

        if let Some(value) = store.get(&req.key) {
            Ok(Response::new(GetResponse {
                found: true,
                value: value.clone(),
                served_by_node: self.node_id.clone(),
            }))
        } else {
            Ok(Response::new(GetResponse {
                found: false,
                value: vec![],
                served_by_node: String::new(),
            }))
        }
    }

    async fn delete(
        &self,
        request: Request<DeleteRequest>,
    ) -> Result<Response<DeleteResponse>, Status> {
        let req = request.into_inner();
        let mut store = self.local_store.write().await;

        let deleted = if store.remove(&req.key).is_some() { 1 } else { 0 };

        Ok(Response::new(DeleteResponse {
            success: true,
            deleted_from_nodes: deleted,
        }))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let node_id = env::var("NODE_ID").unwrap_or_else(|_| "node-0".to_string());
    let port = env::var("PORT").unwrap_or_else(|_| "50051".to_string());
    let use_tls = env::var("USE_TLS").unwrap_or_else(|_| "false".to_string()) == "true";

    let addr = format!("0.0.0.0:{}", port).parse()?;
    let node = RendezvousHashingNode::new(node_id.clone());

    let mut builder = Server::builder();

    if use_tls {
        let cert_path = env::var("TLS_CERT_PATH").unwrap_or_else(|_| "/certs/server.crt".to_string());
        let key_path = env::var("TLS_KEY_PATH").unwrap_or_else(|_| "/certs/server.key".to_string());

        let cert = fs::read_to_string(&cert_path)?;
        let key = fs::read_to_string(&key_path)?;

        let identity = Identity::from_pem(cert, key);
        let tls_config = ServerTlsConfig::new().identity(identity);
        builder = builder.tls_config(tls_config)?;

        println!("Rendezvous Hashing node {} starting with TLS on port {}", node_id, port);
    } else {
        println!("Rendezvous Hashing node {} starting on port {}", node_id, port);
    }

    builder
        .add_service(NodeRegistryServiceServer::new(node.clone()))
        .add_service(RendezvousServiceServer::new(node.clone()))
        .add_service(KeyValueServiceServer::new(node))
        .serve(addr)
        .await?;

    Ok(())
}
