//! # HNSW (Hierarchical Navigable Small World) Vector Search Server
//!
//! This module implements a gRPC server for approximate nearest neighbor search
//! using the HNSW algorithm. HNSW is a graph-based index structure that provides
//! logarithmic search complexity with high recall.
//!
//! ## Algorithm Overview
//!
//! HNSW builds a multi-layer graph where:
//! - Each layer is a navigable small world graph
//! - Higher layers have fewer nodes and longer-range connections
//! - Lower layers have more nodes and shorter-range connections
//! - Search starts at the top layer and greedily descends
//!
//! ## Key Parameters
//!
//! - `M`: Maximum number of connections per node (typically 16-64)
//! - `ef_construction`: Size of dynamic candidate list during construction
//! - `ef_search`: Size of dynamic candidate list during search
//! - `m_L`: Level generation factor (typically 1/ln(M))
//!
//! ## Complexity
//!
//! - Search: O(log N) average case
//! - Insert: O(log N) average case
//! - Memory: O(N * M * num_layers)
//!
//! ## References
//!
//! Malkov, Y. A., & Yashunin, D. A. (2018). Efficient and robust approximate
//! nearest neighbor search using Hierarchical Navigable Small World graphs.

use std::collections::{BinaryHeap, HashMap, HashSet};
use std::cmp::Ordering;
use std::net::SocketAddr;
use std::sync::Arc;

use dashmap::DashMap;
use parking_lot::RwLock;
use rand::Rng;
use tokio::sync::mpsc;
use tonic::{transport::Server, Request, Response, Status};
use tracing::{info, warn, error, debug, instrument};

// ============================================================================
// Configuration Constants
// ============================================================================

/// Default maximum connections per node in the graph
const DEFAULT_M: usize = 16;

/// Default maximum connections for layer 0 (typically 2 * M)
const DEFAULT_M_MAX_0: usize = 32;

/// Default size of dynamic candidate list during construction
const DEFAULT_EF_CONSTRUCTION: usize = 200;

/// Default size of dynamic candidate list during search
const DEFAULT_EF_SEARCH: usize = 50;

/// Default vector dimensionality
const DEFAULT_DIMENSION: usize = 128;

/// Default gRPC server port
const DEFAULT_PORT: u16 = 50051;

// ============================================================================
// Data Structures
// ============================================================================

/// Represents a vector ID with its distance for priority queue operations.
///
/// Used in both search and construction phases to maintain ordered candidates.
#[derive(Debug, Clone)]
pub struct DistancedNode {
    /// Unique identifier of the vector
    pub id: u64,
    /// Distance from the query vector
    pub distance: f32,
}

impl PartialEq for DistancedNode {
    fn eq(&self, other: &Self) -> bool {
        self.distance == other.distance
    }
}

impl Eq for DistancedNode {}

impl PartialOrd for DistancedNode {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for DistancedNode {
    fn cmp(&self, other: &Self) -> Ordering {
        // Reverse ordering for min-heap behavior
        other.distance.partial_cmp(&self.distance).unwrap_or(Ordering::Equal)
    }
}

/// Represents a node in the HNSW graph.
///
/// Each node stores:
/// - The vector data
/// - Connections to neighbors at each layer
/// - The maximum layer this node appears in
#[derive(Debug, Clone)]
pub struct HNSWNode {
    /// Unique identifier for this node
    pub id: u64,

    /// The vector data (dense floating-point values)
    pub vector: Vec<f32>,

    /// Maximum layer this node appears in (0-indexed)
    pub max_layer: usize,

    /// Connections at each layer: layer -> set of neighbor IDs
    /// Layer 0 has the most connections (M_max_0)
    /// Higher layers have at most M connections
    pub connections: Vec<HashSet<u64>>,
}

impl HNSWNode {
    /// Creates a new HNSW node with the given parameters.
    ///
    /// # Arguments
    ///
    /// * `id` - Unique identifier for the node
    /// * `vector` - The vector data
    /// * `max_layer` - Maximum layer this node will appear in
    pub fn new(id: u64, vector: Vec<f32>, max_layer: usize) -> Self {
        let connections = (0..=max_layer)
            .map(|_| HashSet::new())
            .collect();

        Self {
            id,
            vector,
            max_layer,
            connections,
        }
    }
}

/// Configuration parameters for the HNSW index.
#[derive(Debug, Clone)]
pub struct HNSWConfig {
    /// Maximum connections per node (except layer 0)
    pub m: usize,

    /// Maximum connections for layer 0
    pub m_max_0: usize,

    /// Size of dynamic candidate list during construction
    pub ef_construction: usize,

    /// Size of dynamic candidate list during search
    pub ef_search: usize,

    /// Vector dimensionality
    pub dimension: usize,

    /// Level multiplier for random level generation (1/ln(M))
    pub ml: f64,
}

impl Default for HNSWConfig {
    fn default() -> Self {
        Self {
            m: DEFAULT_M,
            m_max_0: DEFAULT_M_MAX_0,
            ef_construction: DEFAULT_EF_CONSTRUCTION,
            ef_search: DEFAULT_EF_SEARCH,
            dimension: DEFAULT_DIMENSION,
            ml: 1.0 / (DEFAULT_M as f64).ln(),
        }
    }
}

/// The main HNSW index structure.
///
/// This structure maintains:
/// - All nodes in the graph (using concurrent HashMap)
/// - The entry point (top-level node for search)
/// - Current maximum layer in the graph
/// - Configuration parameters
#[derive(Debug)]
pub struct HNSWIndex {
    /// All nodes in the index, keyed by ID
    /// Using DashMap for concurrent access
    pub nodes: DashMap<u64, HNSWNode>,

    /// Entry point node ID (node at the highest layer)
    pub entry_point: RwLock<Option<u64>>,

    /// Current maximum layer in the index
    pub max_layer: RwLock<usize>,

    /// Configuration parameters
    pub config: HNSWConfig,

    /// Next available node ID
    pub next_id: RwLock<u64>,
}

impl HNSWIndex {
    /// Creates a new empty HNSW index with the given configuration.
    pub fn new(config: HNSWConfig) -> Self {
        Self {
            nodes: DashMap::new(),
            entry_point: RwLock::new(None),
            max_layer: RwLock::new(0),
            config,
            next_id: RwLock::new(0),
        }
    }

    /// Creates a new index with default configuration.
    pub fn with_defaults() -> Self {
        Self::new(HNSWConfig::default())
    }

    /// Generates a random layer for a new node.
    ///
    /// The layer is chosen from an exponential distribution:
    /// floor(-ln(uniform(0,1)) * ml)
    ///
    /// This ensures that higher layers have exponentially fewer nodes.
    ///
    /// # Returns
    ///
    /// A random layer number (0 or greater)
    fn generate_random_layer(&self) -> usize {
        let mut rng = rand::thread_rng();
        let uniform: f64 = rng.gen();
        (-uniform.ln() * self.config.ml).floor() as usize
    }

    /// Computes the Euclidean distance between two vectors.
    ///
    /// # Arguments
    ///
    /// * `a` - First vector
    /// * `b` - Second vector
    ///
    /// # Returns
    ///
    /// The L2 (Euclidean) distance between the vectors
    ///
    /// # TODO
    ///
    /// Implement distance calculation. Consider:
    /// - Using SIMD for vectorized computation
    /// - Supporting other distance metrics (cosine, inner product)
    pub fn compute_distance(&self, a: &[f32], b: &[f32]) -> f32 {
        todo!("Implement Euclidean distance calculation between two vectors. \
               Sum the squared differences and return the square root.")
    }

    /// Inserts a new vector into the HNSW index.
    ///
    /// # Algorithm
    ///
    /// 1. Generate a random layer L for the new node
    /// 2. If the index is empty, make this the entry point
    /// 3. Find entry points for each layer from top to L+1 using greedy search
    /// 4. For layers L down to 0:
    ///    a. Search for ef_construction nearest neighbors
    ///    b. Select M best neighbors using the select_neighbors heuristic
    ///    c. Create bidirectional connections
    ///    d. Shrink neighbor connections if they exceed M_max
    ///
    /// # Arguments
    ///
    /// * `vector` - The vector to insert
    ///
    /// # Returns
    ///
    /// The ID assigned to the inserted vector
    ///
    /// # TODO
    ///
    /// Implement the full insertion algorithm following the HNSW paper.
    #[instrument(skip(self, vector))]
    pub fn insert_vector(&self, vector: Vec<f32>) -> u64 {
        todo!("Implement HNSW insertion algorithm: \
               1. Generate random layer for new node \
               2. Navigate from entry point through layers \
               3. At each layer, find and connect to nearest neighbors \
               4. Update entry point if new node has higher layer")
    }

    /// Searches for the K nearest neighbors of the query vector.
    ///
    /// # Algorithm
    ///
    /// 1. Start at the entry point
    /// 2. For each layer from top to 1:
    ///    a. Greedily move to the nearest neighbor
    ///    b. Continue until no closer neighbor exists
    /// 3. At layer 0:
    ///    a. Perform ef-search to find candidates
    ///    b. Return the K nearest from candidates
    ///
    /// # Arguments
    ///
    /// * `query` - The query vector
    /// * `k` - Number of nearest neighbors to return
    ///
    /// # Returns
    ///
    /// Vector of (id, distance) pairs for the K nearest neighbors
    ///
    /// # TODO
    ///
    /// Implement the search algorithm with proper layer traversal.
    #[instrument(skip(self, query))]
    pub fn search_knn(&self, query: &[f32], k: usize) -> Vec<(u64, f32)> {
        todo!("Implement HNSW KNN search: \
               1. Start from entry point at top layer \
               2. Greedily descend through layers to layer 1 \
               3. At layer 0, use search_layer with ef_search \
               4. Return top K results from candidates")
    }

    /// Searches for nearest neighbors within a single layer.
    ///
    /// This is the core search procedure used by both insertion and query.
    /// It maintains a dynamic candidate list and visited set.
    ///
    /// # Algorithm
    ///
    /// 1. Initialize candidates with entry points
    /// 2. Initialize results (W) with entry points
    /// 3. While candidates is not empty:
    ///    a. Extract nearest candidate c
    ///    b. Get furthest element f in results
    ///    c. If distance(c, q) > distance(f, q), break
    ///    d. For each neighbor e of c:
    ///       - If e not visited:
    ///         - Mark e as visited
    ///         - If distance(e, q) < distance(f, q) or |W| < ef:
    ///           - Add e to candidates and W
    ///           - If |W| > ef, remove furthest from W
    /// 4. Return W
    ///
    /// # Arguments
    ///
    /// * `query` - The query vector
    /// * `entry_points` - Initial entry points for the search
    /// * `ef` - Size of dynamic candidate list
    /// * `layer` - The layer to search in
    ///
    /// # Returns
    ///
    /// Set of nearest neighbor candidates with their distances
    ///
    /// # TODO
    ///
    /// Implement the layer search algorithm.
    pub fn search_layer(
        &self,
        query: &[f32],
        entry_points: &[u64],
        ef: usize,
        layer: usize,
    ) -> Vec<DistancedNode> {
        todo!("Implement single-layer search: \
               1. Initialize candidate and result heaps \
               2. Process candidates in order of distance \
               3. Expand search through neighbor connections \
               4. Maintain ef-size result set with pruning")
    }

    /// Selects the best neighbors for a node using the HNSW heuristic.
    ///
    /// This implements the SELECT-NEIGHBORS-HEURISTIC from the paper,
    /// which prefers neighbors that are diverse (not too close to each other).
    ///
    /// # Algorithm (Simple version)
    ///
    /// Return the M nearest neighbors from candidates.
    ///
    /// # Algorithm (Heuristic version)
    ///
    /// 1. Sort candidates by distance
    /// 2. For each candidate in order:
    ///    a. If candidate is closer to query than to any selected neighbor,
    ///       add it to the result
    ///    b. Stop when result has M neighbors
    ///
    /// # Arguments
    ///
    /// * `query` - The vector being inserted
    /// * `candidates` - Candidate neighbors
    /// * `m` - Maximum number of neighbors to select
    /// * `layer` - The layer (affects M_max)
    /// * `extend_candidates` - Whether to extend candidates with their neighbors
    /// * `keep_pruned` - Whether to keep pruned candidates as fallback
    ///
    /// # Returns
    ///
    /// Selected neighbor IDs
    ///
    /// # TODO
    ///
    /// Implement the neighbor selection heuristic.
    pub fn select_neighbors(
        &self,
        query: &[f32],
        candidates: &[DistancedNode],
        m: usize,
        layer: usize,
        extend_candidates: bool,
        keep_pruned: bool,
    ) -> Vec<u64> {
        todo!("Implement neighbor selection heuristic: \
               1. Optionally extend candidates with their neighbors \
               2. Sort candidates by distance to query \
               3. Select diverse neighbors using distance comparisons \
               4. Optionally include pruned candidates if under M")
    }

    /// Shrinks the connections of a node to not exceed M_max.
    ///
    /// Called when a node has too many connections after insertion.
    ///
    /// # Arguments
    ///
    /// * `node_id` - The node whose connections need shrinking
    /// * `layer` - The layer to shrink connections in
    /// * `m_max` - Maximum allowed connections
    fn shrink_connections(&self, node_id: u64, layer: usize, m_max: usize) {
        todo!("Implement connection shrinking: \
               1. Get current connections for the node at the layer \
               2. If count > m_max, select best m_max neighbors \
               3. Update the node's connections")
    }

    /// Deletes a vector from the index.
    ///
    /// # Note
    ///
    /// HNSW deletion is complex and can affect search quality.
    /// A simple approach marks nodes as deleted without removing edges.
    /// Full deletion requires reconnecting neighbors.
    ///
    /// # Arguments
    ///
    /// * `id` - The ID of the vector to delete
    ///
    /// # Returns
    ///
    /// true if the vector was found and deleted
    pub fn delete_vector(&self, id: u64) -> bool {
        todo!("Implement vector deletion: \
               1. Remove the node from the nodes map \
               2. Remove connections to this node from all neighbors \
               3. If deleted node was entry point, select new entry point")
    }

    /// Returns the number of vectors in the index.
    pub fn len(&self) -> usize {
        self.nodes.len()
    }

    /// Returns true if the index is empty.
    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty()
    }
}

// ============================================================================
// gRPC Service Definition (Manual, without proto file)
// ============================================================================

/// Represents a vector in gRPC messages.
#[derive(Debug, Clone)]
pub struct Vector {
    pub id: u64,
    pub values: Vec<f32>,
    pub metadata: HashMap<String, String>,
}

/// Request to insert a vector.
#[derive(Debug, Clone)]
pub struct InsertRequest {
    pub vector: Vector,
}

/// Response from insert operation.
#[derive(Debug, Clone)]
pub struct InsertResponse {
    pub id: u64,
    pub success: bool,
}

/// Request to search for nearest neighbors.
#[derive(Debug, Clone)]
pub struct SearchRequest {
    pub query: Vec<f32>,
    pub k: u32,
    pub ef_search: Option<u32>,
}

/// A single search result.
#[derive(Debug, Clone)]
pub struct SearchResult {
    pub id: u64,
    pub distance: f32,
    pub metadata: HashMap<String, String>,
}

/// Response from search operation.
#[derive(Debug, Clone)]
pub struct SearchResponse {
    pub results: Vec<SearchResult>,
    pub search_time_ms: f64,
}

/// Request to delete a vector.
#[derive(Debug, Clone)]
pub struct DeleteRequest {
    pub id: u64,
}

/// Response from delete operation.
#[derive(Debug, Clone)]
pub struct DeleteResponse {
    pub success: bool,
}

/// Request for index statistics.
#[derive(Debug, Clone)]
pub struct StatsRequest {}

/// Response with index statistics.
#[derive(Debug, Clone)]
pub struct StatsResponse {
    pub num_vectors: u64,
    pub num_layers: u32,
    pub dimension: u32,
    pub m: u32,
    pub ef_construction: u32,
}

// ============================================================================
// gRPC Service Implementation
// ============================================================================

/// The HNSW gRPC service implementation.
pub struct HNSWService {
    /// The HNSW index
    index: Arc<HNSWIndex>,

    /// Node identifier in a distributed setting
    node_id: String,

    /// Peer addresses for distributed queries
    peers: Vec<String>,
}

impl HNSWService {
    /// Creates a new HNSW service with the given configuration.
    pub fn new(config: HNSWConfig, node_id: String, peers: Vec<String>) -> Self {
        Self {
            index: Arc::new(HNSWIndex::new(config)),
            node_id,
            peers,
        }
    }

    /// Handles vector insertion.
    ///
    /// # TODO
    ///
    /// Implement gRPC handler for insert operation.
    pub async fn insert(&self, request: InsertRequest) -> Result<InsertResponse, Status> {
        todo!("Implement insert gRPC handler: \
               1. Extract vector from request \
               2. Call index.insert_vector \
               3. Return InsertResponse with assigned ID")
    }

    /// Handles KNN search.
    ///
    /// # TODO
    ///
    /// Implement gRPC handler for search operation.
    pub async fn search(&self, request: SearchRequest) -> Result<SearchResponse, Status> {
        todo!("Implement search gRPC handler: \
               1. Extract query and k from request \
               2. Call index.search_knn \
               3. Convert results to SearchResponse")
    }

    /// Handles vector deletion.
    ///
    /// # TODO
    ///
    /// Implement gRPC handler for delete operation.
    pub async fn delete(&self, request: DeleteRequest) -> Result<DeleteResponse, Status> {
        todo!("Implement delete gRPC handler: \
               1. Extract ID from request \
               2. Call index.delete_vector \
               3. Return DeleteResponse with success status")
    }

    /// Returns index statistics.
    pub async fn get_stats(&self, _request: StatsRequest) -> Result<StatsResponse, Status> {
        let max_layer = *self.index.max_layer.read();

        Ok(StatsResponse {
            num_vectors: self.index.len() as u64,
            num_layers: max_layer as u32 + 1,
            dimension: self.index.config.dimension as u32,
            m: self.index.config.m as u32,
            ef_construction: self.index.config.ef_construction as u32,
        })
    }

    /// Forwards a search request to peer nodes in a distributed setting.
    ///
    /// # TODO
    ///
    /// Implement distributed search across peer nodes.
    pub async fn distributed_search(
        &self,
        request: SearchRequest,
    ) -> Result<SearchResponse, Status> {
        todo!("Implement distributed search: \
               1. Send search request to all peers \
               2. Collect results from all nodes \
               3. Merge and re-rank results \
               4. Return top K across all nodes")
    }
}

// ============================================================================
// Server Configuration
// ============================================================================

/// Command-line arguments for the server.
#[derive(Debug, Clone)]
pub struct ServerConfig {
    /// Unique node identifier
    pub node_id: String,

    /// Port to listen on
    pub port: u16,

    /// Peer node addresses
    pub peers: Vec<String>,

    /// HNSW M parameter
    pub m: usize,

    /// HNSW ef_construction parameter
    pub ef_construction: usize,

    /// Vector dimension
    pub dimension: usize,
}

impl ServerConfig {
    /// Parses configuration from command-line arguments.
    ///
    /// Expected arguments:
    /// --node-id <id>
    /// --port <port>
    /// --peers <peer1,peer2,...>
    /// --m <m>
    /// --ef-construction <ef>
    /// --dimension <dim>
    pub fn from_args() -> Self {
        let args: Vec<String> = std::env::args().collect();

        let mut node_id = String::from("node-1");
        let mut port = DEFAULT_PORT;
        let mut peers = Vec::new();
        let mut m = DEFAULT_M;
        let mut ef_construction = DEFAULT_EF_CONSTRUCTION;
        let mut dimension = DEFAULT_DIMENSION;

        let mut i = 1;
        while i < args.len() {
            match args[i].as_str() {
                "--node-id" => {
                    if i + 1 < args.len() {
                        node_id = args[i + 1].clone();
                        i += 2;
                    } else {
                        i += 1;
                    }
                }
                "--port" => {
                    if i + 1 < args.len() {
                        port = args[i + 1].parse().unwrap_or(DEFAULT_PORT);
                        i += 2;
                    } else {
                        i += 1;
                    }
                }
                "--peers" => {
                    if i + 1 < args.len() {
                        peers = args[i + 1]
                            .split(',')
                            .map(|s| s.trim().to_string())
                            .filter(|s| !s.is_empty())
                            .collect();
                        i += 2;
                    } else {
                        i += 1;
                    }
                }
                "--m" => {
                    if i + 1 < args.len() {
                        m = args[i + 1].parse().unwrap_or(DEFAULT_M);
                        i += 2;
                    } else {
                        i += 1;
                    }
                }
                "--ef-construction" => {
                    if i + 1 < args.len() {
                        ef_construction = args[i + 1].parse().unwrap_or(DEFAULT_EF_CONSTRUCTION);
                        i += 2;
                    } else {
                        i += 1;
                    }
                }
                "--dimension" => {
                    if i + 1 < args.len() {
                        dimension = args[i + 1].parse().unwrap_or(DEFAULT_DIMENSION);
                        i += 2;
                    } else {
                        i += 1;
                    }
                }
                _ => {
                    i += 1;
                }
            }
        }

        Self {
            node_id,
            port,
            peers,
            m,
            ef_construction,
            dimension,
        }
    }
}

// ============================================================================
// Utility Functions
// ============================================================================

/// Normalizes a vector to unit length.
///
/// Useful for cosine similarity where normalized vectors allow
/// using dot product instead of full cosine calculation.
pub fn normalize_vector(v: &mut [f32]) {
    let norm: f32 = v.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm > 0.0 {
        for x in v.iter_mut() {
            *x /= norm;
        }
    }
}

/// Computes the dot product of two vectors.
pub fn dot_product(a: &[f32], b: &[f32]) -> f32 {
    a.iter().zip(b.iter()).map(|(x, y)| x * y).sum()
}

/// Computes cosine similarity between two vectors.
pub fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    let dot = dot_product(a, b);
    let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();

    if norm_a > 0.0 && norm_b > 0.0 {
        dot / (norm_a * norm_b)
    } else {
        0.0
    }
}

// ============================================================================
// Main Entry Point
// ============================================================================

/// Main entry point for the HNSW gRPC server.
///
/// This function:
/// 1. Parses command-line arguments
/// 2. Initializes the HNSW index
/// 3. Creates the gRPC service
/// 4. Starts the server
///
/// # Usage
///
/// ```bash
/// hnsw-server --node-id node-1 --port 50051 --peers localhost:50052,localhost:50053
/// ```
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing for logging
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("hnsw_server=info".parse()?)
        )
        .init();

    // Parse configuration
    let config = ServerConfig::from_args();

    info!(
        "Starting HNSW server: node_id={}, port={}, peers={:?}",
        config.node_id, config.port, config.peers
    );

    // Create HNSW configuration
    let hnsw_config = HNSWConfig {
        m: config.m,
        m_max_0: config.m * 2,
        ef_construction: config.ef_construction,
        ef_search: DEFAULT_EF_SEARCH,
        dimension: config.dimension,
        ml: 1.0 / (config.m as f64).ln(),
    };

    info!(
        "HNSW config: M={}, M_max_0={}, ef_construction={}, dimension={}",
        hnsw_config.m, hnsw_config.m_max_0, hnsw_config.ef_construction, hnsw_config.dimension
    );

    // Create the service
    let service = HNSWService::new(
        hnsw_config,
        config.node_id.clone(),
        config.peers.clone(),
    );

    // Create socket address
    let addr: SocketAddr = format!("0.0.0.0:{}", config.port).parse()?;

    info!("HNSW gRPC server listening on {}", addr);

    // TODO: Register the service with tonic and start the server
    // When proto file is available, uncomment:
    // Server::builder()
    //     .add_service(VectorSearchServiceServer::new(service))
    //     .serve(addr)
    //     .await?;

    // For now, just keep the server running
    info!("Server initialized. Waiting for gRPC service implementation...");

    // Keep the main task alive
    tokio::signal::ctrl_c().await?;
    info!("Shutting down HNSW server");

    Ok(())
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hnsw_node_creation() {
        let node = HNSWNode::new(1, vec![1.0, 2.0, 3.0], 2);
        assert_eq!(node.id, 1);
        assert_eq!(node.vector.len(), 3);
        assert_eq!(node.max_layer, 2);
        assert_eq!(node.connections.len(), 3); // layers 0, 1, 2
    }

    #[test]
    fn test_hnsw_config_default() {
        let config = HNSWConfig::default();
        assert_eq!(config.m, DEFAULT_M);
        assert_eq!(config.m_max_0, DEFAULT_M_MAX_0);
        assert_eq!(config.ef_construction, DEFAULT_EF_CONSTRUCTION);
    }

    #[test]
    fn test_hnsw_index_creation() {
        let index = HNSWIndex::with_defaults();
        assert!(index.is_empty());
        assert_eq!(index.len(), 0);
    }

    #[test]
    fn test_distanced_node_ordering() {
        let a = DistancedNode { id: 1, distance: 1.0 };
        let b = DistancedNode { id: 2, distance: 2.0 };

        // BinaryHeap is a max-heap, but we want min-heap behavior
        // So 'a' (smaller distance) should be "greater" for ordering
        assert!(a > b);
    }

    #[test]
    fn test_normalize_vector() {
        let mut v = vec![3.0, 4.0];
        normalize_vector(&mut v);

        let norm: f32 = v.iter().map(|x| x * x).sum::<f32>().sqrt();
        assert!((norm - 1.0).abs() < 1e-6);
    }

    #[test]
    fn test_cosine_similarity() {
        let a = vec![1.0, 0.0];
        let b = vec![1.0, 0.0];
        let c = vec![0.0, 1.0];

        assert!((cosine_similarity(&a, &b) - 1.0).abs() < 1e-6);
        assert!(cosine_similarity(&a, &c).abs() < 1e-6);
    }
}
