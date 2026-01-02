//! # Inverted File Index (IVF) Vector Search Server
//!
//! This module implements a gRPC server for approximate nearest neighbor search
//! using the Inverted File Index (IVF) algorithm. IVF partitions the vector space
//! into Voronoi cells using K-means clustering, enabling fast search by only
//! examining vectors in nearby clusters.
//!
//! ## Algorithm Overview
//!
//! IVF works in two phases:
//!
//! ### Training Phase
//! 1. Sample a subset of training vectors
//! 2. Run K-means clustering to find `nlist` centroids
//! 3. Each centroid defines a Voronoi cell (cluster)
//!
//! ### Indexing Phase
//! 1. For each vector, find its nearest centroid
//! 2. Store the vector in that centroid's inverted list
//!
//! ### Search Phase
//! 1. Find the `nprobe` nearest centroids to the query
//! 2. Search only within those clusters' inverted lists
//! 3. Return the top K results
//!
//! ## Key Parameters
//!
//! - `nlist`: Number of clusters/centroids (typically sqrt(N) to N/10)
//! - `nprobe`: Number of clusters to search (trade-off: accuracy vs speed)
//!
//! ## Complexity
//!
//! - Training: O(N * nlist * iterations * D) for K-means
//! - Indexing: O(nlist * D) per vector
//! - Search: O(nprobe * (N/nlist) * D) average case
//!
//! ## References
//!
//! Jegou, H., Douze, M., & Schmid, C. (2011). Product quantization for
//! nearest neighbor search.

use std::collections::{BinaryHeap, HashMap, HashSet};
use std::cmp::Ordering;
use std::net::SocketAddr;
use std::sync::Arc;

use dashmap::DashMap;
use parking_lot::RwLock;
use rand::seq::SliceRandom;
use rand::Rng;
use tokio::sync::mpsc;
use tonic::{transport::Server, Request, Response, Status};
use tracing::{info, warn, error, debug, instrument};

// ============================================================================
// Configuration Constants
// ============================================================================

/// Default number of clusters (centroids)
const DEFAULT_NLIST: usize = 100;

/// Default number of clusters to probe during search
const DEFAULT_NPROBE: usize = 10;

/// Default number of K-means iterations
const DEFAULT_KMEANS_ITERATIONS: usize = 25;

/// Default vector dimensionality
const DEFAULT_DIMENSION: usize = 128;

/// Default gRPC server port
const DEFAULT_PORT: u16 = 50052;

/// Convergence threshold for K-means
const KMEANS_CONVERGENCE_THRESHOLD: f32 = 1e-6;

// ============================================================================
// Data Structures
// ============================================================================

/// Represents a vector with its distance for priority queue operations.
#[derive(Debug, Clone)]
pub struct DistancedVector {
    /// Unique identifier of the vector
    pub id: u64,
    /// Distance from the query vector
    pub distance: f32,
}

impl PartialEq for DistancedVector {
    fn eq(&self, other: &Self) -> bool {
        self.distance == other.distance
    }
}

impl Eq for DistancedVector {}

impl PartialOrd for DistancedVector {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for DistancedVector {
    fn cmp(&self, other: &Self) -> Ordering {
        // Reverse ordering for min-heap behavior
        other.distance.partial_cmp(&self.distance).unwrap_or(Ordering::Equal)
    }
}

/// Represents a centroid in the IVF index.
///
/// Each centroid is the center of a Voronoi cell (cluster) and
/// has an associated inverted list of vectors assigned to it.
#[derive(Debug, Clone)]
pub struct Centroid {
    /// Unique identifier for this centroid
    pub id: usize,

    /// The centroid vector (mean of assigned vectors)
    pub vector: Vec<f32>,

    /// Number of vectors assigned to this centroid
    pub count: usize,
}

impl Centroid {
    /// Creates a new centroid with the given ID and vector.
    pub fn new(id: usize, vector: Vec<f32>) -> Self {
        Self {
            id,
            vector,
            count: 0,
        }
    }

    /// Creates a zero-initialized centroid.
    pub fn zeros(id: usize, dimension: usize) -> Self {
        Self {
            id,
            vector: vec![0.0; dimension],
            count: 0,
        }
    }
}

/// Represents a stored vector in an inverted list.
#[derive(Debug, Clone)]
pub struct StoredVector {
    /// Unique identifier
    pub id: u64,

    /// The vector data
    pub vector: Vec<f32>,

    /// Optional metadata
    pub metadata: HashMap<String, String>,
}

/// An inverted list storing vectors assigned to a centroid.
///
/// This is essentially the posting list for a centroid, containing
/// all vectors that are closest to this centroid.
#[derive(Debug, Clone)]
pub struct InvertedList {
    /// The centroid ID this list belongs to
    pub centroid_id: usize,

    /// Vectors stored in this list
    pub vectors: Vec<StoredVector>,
}

impl InvertedList {
    /// Creates a new empty inverted list for the given centroid.
    pub fn new(centroid_id: usize) -> Self {
        Self {
            centroid_id,
            vectors: Vec::new(),
        }
    }

    /// Adds a vector to this inverted list.
    pub fn add(&mut self, vector: StoredVector) {
        self.vectors.push(vector);
    }

    /// Returns the number of vectors in this list.
    pub fn len(&self) -> usize {
        self.vectors.len()
    }

    /// Returns true if the list is empty.
    pub fn is_empty(&self) -> bool {
        self.vectors.is_empty()
    }
}

/// Configuration for the IVF index.
#[derive(Debug, Clone)]
pub struct IVFConfig {
    /// Number of clusters/centroids
    pub nlist: usize,

    /// Number of clusters to probe during search
    pub nprobe: usize,

    /// Number of K-means iterations for training
    pub kmeans_iterations: usize,

    /// Vector dimensionality
    pub dimension: usize,
}

impl Default for IVFConfig {
    fn default() -> Self {
        Self {
            nlist: DEFAULT_NLIST,
            nprobe: DEFAULT_NPROBE,
            kmeans_iterations: DEFAULT_KMEANS_ITERATIONS,
            dimension: DEFAULT_DIMENSION,
        }
    }
}

/// The main IVF index structure.
///
/// This structure maintains:
/// - The trained centroids (cluster centers)
/// - Inverted lists for each centroid
/// - Configuration parameters
/// - Training state
#[derive(Debug)]
pub struct IVFIndex {
    /// Trained centroids (None until trained)
    pub centroids: RwLock<Option<Vec<Centroid>>>,

    /// Inverted lists for each centroid
    /// Key: centroid ID, Value: inverted list
    pub inverted_lists: DashMap<usize, InvertedList>,

    /// Configuration parameters
    pub config: IVFConfig,

    /// Whether the index has been trained
    pub is_trained: RwLock<bool>,

    /// Next available vector ID
    pub next_id: RwLock<u64>,

    /// Total number of indexed vectors
    pub num_vectors: RwLock<usize>,
}

impl IVFIndex {
    /// Creates a new untrained IVF index with the given configuration.
    pub fn new(config: IVFConfig) -> Self {
        Self {
            centroids: RwLock::new(None),
            inverted_lists: DashMap::new(),
            config,
            is_trained: RwLock::new(false),
            next_id: RwLock::new(0),
            num_vectors: RwLock::new(0),
        }
    }

    /// Creates a new index with default configuration.
    pub fn with_defaults() -> Self {
        Self::new(IVFConfig::default())
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
    /// The L2 (Euclidean) distance
    pub fn compute_distance(&self, a: &[f32], b: &[f32]) -> f32 {
        a.iter()
            .zip(b.iter())
            .map(|(x, y)| (x - y).powi(2))
            .sum::<f32>()
            .sqrt()
    }

    /// Trains the IVF index using K-means clustering.
    ///
    /// # Algorithm
    ///
    /// 1. Initialize centroids (random selection or K-means++)
    /// 2. Repeat until convergence or max iterations:
    ///    a. Assign each vector to its nearest centroid
    ///    b. Update centroids as mean of assigned vectors
    ///    c. Check for convergence (centroids not moving)
    ///
    /// # Arguments
    ///
    /// * `training_vectors` - Vectors to use for training
    ///
    /// # Returns
    ///
    /// Ok(()) if training succeeded, Err if insufficient vectors
    ///
    /// # TODO
    ///
    /// Implement the K-means clustering algorithm.
    #[instrument(skip(self, training_vectors))]
    pub fn train_kmeans(&self, training_vectors: &[Vec<f32>]) -> Result<(), String> {
        todo!("Implement K-means training: \
               1. Initialize centroids (random or K-means++) \
               2. Iterate: assign vectors to nearest centroid \
               3. Update centroids as cluster means \
               4. Check convergence and repeat \
               5. Store final centroids in self.centroids")
    }

    /// Initializes centroids using K-means++ algorithm.
    ///
    /// K-means++ provides better initial centroids by:
    /// 1. Choosing first centroid randomly
    /// 2. For each subsequent centroid, choose with probability
    ///    proportional to squared distance from nearest existing centroid
    ///
    /// # Arguments
    ///
    /// * `vectors` - Training vectors
    /// * `k` - Number of centroids to initialize
    ///
    /// # Returns
    ///
    /// Initial centroid vectors
    ///
    /// # TODO
    ///
    /// Implement K-means++ initialization.
    fn initialize_centroids_kmeans_plus_plus(
        &self,
        vectors: &[Vec<f32>],
        k: usize,
    ) -> Vec<Vec<f32>> {
        todo!("Implement K-means++ initialization: \
               1. Select first centroid randomly \
               2. For each new centroid: \
                  a. Compute D(x)^2 for each point (distance to nearest centroid) \
                  b. Select new centroid with probability proportional to D(x)^2 \
               3. Return k initial centroids")
    }

    /// Assigns a vector to its nearest centroid.
    ///
    /// # Arguments
    ///
    /// * `vector` - The vector to assign
    ///
    /// # Returns
    ///
    /// Tuple of (centroid_id, distance)
    ///
    /// # TODO
    ///
    /// Implement centroid assignment.
    pub fn assign_to_cluster(&self, vector: &[f32]) -> Result<(usize, f32), String> {
        todo!("Implement cluster assignment: \
               1. Ensure index is trained \
               2. Compute distance to each centroid \
               3. Return ID and distance of nearest centroid")
    }

    /// Finds the nprobe nearest centroids to a query vector.
    ///
    /// # Arguments
    ///
    /// * `query` - The query vector
    /// * `nprobe` - Number of centroids to return
    ///
    /// # Returns
    ///
    /// Vector of (centroid_id, distance) pairs, sorted by distance
    fn find_nearest_centroids(&self, query: &[f32], nprobe: usize) -> Vec<(usize, f32)> {
        let centroids = self.centroids.read();
        let centroids = match centroids.as_ref() {
            Some(c) => c,
            None => return Vec::new(),
        };

        let mut distances: Vec<(usize, f32)> = centroids
            .iter()
            .map(|c| (c.id, self.compute_distance(query, &c.vector)))
            .collect();

        distances.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(Ordering::Equal));
        distances.truncate(nprobe);

        distances
    }

    /// Inserts a vector into the index.
    ///
    /// # Arguments
    ///
    /// * `vector` - The vector to insert
    /// * `metadata` - Optional metadata for the vector
    ///
    /// # Returns
    ///
    /// The assigned vector ID
    ///
    /// # Errors
    ///
    /// Returns error if index is not trained
    pub fn insert_vector(
        &self,
        vector: Vec<f32>,
        metadata: HashMap<String, String>,
    ) -> Result<u64, String> {
        if !*self.is_trained.read() {
            return Err("Index must be trained before inserting vectors".to_string());
        }

        // Assign to nearest cluster
        let (centroid_id, _distance) = self.assign_to_cluster(&vector)?;

        // Generate ID
        let id = {
            let mut next_id = self.next_id.write();
            let id = *next_id;
            *next_id += 1;
            id
        };

        // Create stored vector
        let stored_vector = StoredVector {
            id,
            vector,
            metadata,
        };

        // Add to inverted list
        self.inverted_lists
            .entry(centroid_id)
            .or_insert_with(|| InvertedList::new(centroid_id))
            .add(stored_vector);

        // Update count
        *self.num_vectors.write() += 1;

        Ok(id)
    }

    /// Searches for the K nearest neighbors within a specific cluster.
    ///
    /// This method performs exhaustive search within a single inverted list.
    ///
    /// # Arguments
    ///
    /// * `query` - The query vector
    /// * `centroid_id` - The cluster to search
    /// * `k` - Number of results to return
    ///
    /// # Returns
    ///
    /// Vector of (id, distance) pairs
    ///
    /// # TODO
    ///
    /// Implement cluster search.
    pub fn search_cluster(
        &self,
        query: &[f32],
        centroid_id: usize,
        k: usize,
    ) -> Vec<(u64, f32)> {
        todo!("Implement cluster search: \
               1. Get the inverted list for centroid_id \
               2. Compute distance from query to each vector \
               3. Use a max-heap to track top-k results \
               4. Return sorted results")
    }

    /// Searches for the K nearest neighbors across multiple clusters.
    ///
    /// # Algorithm
    ///
    /// 1. Find the nprobe nearest centroids to the query
    /// 2. For each cluster, search for candidates
    /// 3. Merge results and return top K
    ///
    /// # Arguments
    ///
    /// * `query` - The query vector
    /// * `k` - Number of nearest neighbors to return
    /// * `nprobe` - Number of clusters to search (overrides default)
    ///
    /// # Returns
    ///
    /// Vector of (id, distance) pairs for the K nearest neighbors
    #[instrument(skip(self, query))]
    pub fn search_knn(
        &self,
        query: &[f32],
        k: usize,
        nprobe: Option<usize>,
    ) -> Result<Vec<(u64, f32)>, String> {
        if !*self.is_trained.read() {
            return Err("Index must be trained before searching".to_string());
        }

        let nprobe = nprobe.unwrap_or(self.config.nprobe);

        // Find nearest centroids
        let nearest_centroids = self.find_nearest_centroids(query, nprobe);

        // Search each cluster and collect results
        let mut all_results: Vec<(u64, f32)> = Vec::new();

        for (centroid_id, _centroid_distance) in nearest_centroids {
            let cluster_results = self.search_cluster(query, centroid_id, k);
            all_results.extend(cluster_results);
        }

        // Sort and truncate to k results
        all_results.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(Ordering::Equal));
        all_results.truncate(k);

        Ok(all_results)
    }

    /// Deletes a vector from the index.
    ///
    /// # Note
    ///
    /// This operation requires scanning inverted lists to find the vector.
    /// For frequent deletions, consider maintaining a separate ID->centroid map.
    ///
    /// # Arguments
    ///
    /// * `id` - The ID of the vector to delete
    ///
    /// # Returns
    ///
    /// true if the vector was found and deleted
    pub fn delete_vector(&self, id: u64) -> bool {
        for mut list in self.inverted_lists.iter_mut() {
            let original_len = list.vectors.len();
            list.vectors.retain(|v| v.id != id);
            if list.vectors.len() < original_len {
                *self.num_vectors.write() -= 1;
                return true;
            }
        }
        false
    }

    /// Returns the number of vectors in the index.
    pub fn len(&self) -> usize {
        *self.num_vectors.read()
    }

    /// Returns true if the index is empty.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Returns true if the index has been trained.
    pub fn is_trained(&self) -> bool {
        *self.is_trained.read()
    }

    /// Returns statistics about cluster sizes.
    pub fn get_cluster_stats(&self) -> Vec<(usize, usize)> {
        self.inverted_lists
            .iter()
            .map(|entry| (*entry.key(), entry.value().len()))
            .collect()
    }
}

// ============================================================================
// gRPC Message Types
// ============================================================================

/// Represents a vector in gRPC messages.
#[derive(Debug, Clone)]
pub struct Vector {
    pub id: u64,
    pub values: Vec<f32>,
    pub metadata: HashMap<String, String>,
}

/// Request to train the index.
#[derive(Debug, Clone)]
pub struct TrainRequest {
    pub vectors: Vec<Vec<f32>>,
    pub nlist: Option<u32>,
}

/// Response from training.
#[derive(Debug, Clone)]
pub struct TrainResponse {
    pub success: bool,
    pub num_centroids: u32,
    pub message: String,
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
    pub assigned_cluster: u32,
}

/// Request to search for nearest neighbors.
#[derive(Debug, Clone)]
pub struct SearchRequest {
    pub query: Vec<f32>,
    pub k: u32,
    pub nprobe: Option<u32>,
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
    pub clusters_searched: u32,
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
    pub num_centroids: u32,
    pub is_trained: bool,
    pub dimension: u32,
    pub nprobe: u32,
    pub cluster_sizes: Vec<u32>,
}

// ============================================================================
// gRPC Service Implementation
// ============================================================================

/// The IVF gRPC service implementation.
pub struct IVFService {
    /// The IVF index
    index: Arc<IVFIndex>,

    /// Node identifier in a distributed setting
    node_id: String,

    /// Peer addresses for distributed queries
    peers: Vec<String>,
}

impl IVFService {
    /// Creates a new IVF service with the given configuration.
    pub fn new(config: IVFConfig, node_id: String, peers: Vec<String>) -> Self {
        Self {
            index: Arc::new(IVFIndex::new(config)),
            node_id,
            peers,
        }
    }

    /// Handles index training.
    ///
    /// # TODO
    ///
    /// Implement gRPC handler for training operation.
    pub async fn train(&self, request: TrainRequest) -> Result<TrainResponse, Status> {
        todo!("Implement train gRPC handler: \
               1. Extract training vectors from request \
               2. Call index.train_kmeans \
               3. Return TrainResponse with results")
    }

    /// Handles vector insertion.
    ///
    /// # TODO
    ///
    /// Implement gRPC handler for insert operation.
    pub async fn insert(&self, request: InsertRequest) -> Result<InsertResponse, Status> {
        todo!("Implement insert gRPC handler: \
               1. Check if index is trained \
               2. Extract vector from request \
               3. Call index.insert_vector \
               4. Return InsertResponse with assigned cluster")
    }

    /// Handles KNN search.
    ///
    /// # TODO
    ///
    /// Implement gRPC handler for search operation.
    pub async fn search(&self, request: SearchRequest) -> Result<SearchResponse, Status> {
        todo!("Implement search gRPC handler: \
               1. Check if index is trained \
               2. Extract query and parameters \
               3. Call index.search_knn \
               4. Return SearchResponse with results")
    }

    /// Handles vector deletion.
    pub async fn delete(&self, request: DeleteRequest) -> Result<DeleteResponse, Status> {
        let success = self.index.delete_vector(request.id);
        Ok(DeleteResponse { success })
    }

    /// Returns index statistics.
    pub async fn get_stats(&self, _request: StatsRequest) -> Result<StatsResponse, Status> {
        let cluster_stats = self.index.get_cluster_stats();
        let cluster_sizes: Vec<u32> = cluster_stats.iter().map(|(_, size)| *size as u32).collect();

        Ok(StatsResponse {
            num_vectors: self.index.len() as u64,
            num_centroids: self.index.config.nlist as u32,
            is_trained: self.index.is_trained(),
            dimension: self.index.config.dimension as u32,
            nprobe: self.index.config.nprobe as u32,
            cluster_sizes,
        })
    }

    /// Rebalances clusters by reassigning vectors.
    ///
    /// Useful when clusters become imbalanced after many insertions/deletions.
    ///
    /// # TODO
    ///
    /// Implement cluster rebalancing.
    pub async fn rebalance(&self) -> Result<(), Status> {
        todo!("Implement cluster rebalancing: \
               1. Collect all vectors from all inverted lists \
               2. Clear all inverted lists \
               3. Retrain centroids or keep existing \
               4. Reassign all vectors to nearest centroids")
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

    /// Number of clusters
    pub nlist: usize,

    /// Number of clusters to probe
    pub nprobe: usize,

    /// Vector dimension
    pub dimension: usize,
}

impl ServerConfig {
    /// Parses configuration from command-line arguments.
    pub fn from_args() -> Self {
        let args: Vec<String> = std::env::args().collect();

        let mut node_id = String::from("node-1");
        let mut port = DEFAULT_PORT;
        let mut peers = Vec::new();
        let mut nlist = DEFAULT_NLIST;
        let mut nprobe = DEFAULT_NPROBE;
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
                "--nlist" => {
                    if i + 1 < args.len() {
                        nlist = args[i + 1].parse().unwrap_or(DEFAULT_NLIST);
                        i += 2;
                    } else {
                        i += 1;
                    }
                }
                "--nprobe" => {
                    if i + 1 < args.len() {
                        nprobe = args[i + 1].parse().unwrap_or(DEFAULT_NPROBE);
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
            nlist,
            nprobe,
            dimension,
        }
    }
}

// ============================================================================
// Utility Functions
// ============================================================================

/// Computes the mean of a set of vectors.
///
/// # Arguments
///
/// * `vectors` - Slice of vectors to average
///
/// # Returns
///
/// The component-wise mean vector
pub fn compute_mean(vectors: &[&Vec<f32>]) -> Vec<f32> {
    if vectors.is_empty() {
        return Vec::new();
    }

    let dim = vectors[0].len();
    let mut mean = vec![0.0f32; dim];

    for v in vectors {
        for (i, val) in v.iter().enumerate() {
            mean[i] += val;
        }
    }

    let n = vectors.len() as f32;
    for val in mean.iter_mut() {
        *val /= n;
    }

    mean
}

/// Computes variance within clusters (intra-cluster variance).
///
/// Lower variance indicates better clustering.
pub fn compute_intra_cluster_variance(
    vectors: &[Vec<f32>],
    centroids: &[Centroid],
    assignments: &[usize],
) -> f32 {
    let mut total_variance = 0.0f32;

    for (i, vector) in vectors.iter().enumerate() {
        let centroid = &centroids[assignments[i]];
        let distance: f32 = vector
            .iter()
            .zip(centroid.vector.iter())
            .map(|(a, b)| (a - b).powi(2))
            .sum();
        total_variance += distance;
    }

    total_variance / vectors.len() as f32
}

// ============================================================================
// Main Entry Point
// ============================================================================

/// Main entry point for the IVF gRPC server.
///
/// This function:
/// 1. Parses command-line arguments
/// 2. Initializes the IVF index
/// 3. Creates the gRPC service
/// 4. Starts the server
///
/// # Usage
///
/// ```bash
/// ivf-server --node-id node-1 --port 50052 --nlist 100 --nprobe 10
/// ```
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing for logging
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("ivf_server=info".parse()?)
        )
        .init();

    // Parse configuration
    let config = ServerConfig::from_args();

    info!(
        "Starting IVF server: node_id={}, port={}, peers={:?}",
        config.node_id, config.port, config.peers
    );

    // Create IVF configuration
    let ivf_config = IVFConfig {
        nlist: config.nlist,
        nprobe: config.nprobe,
        kmeans_iterations: DEFAULT_KMEANS_ITERATIONS,
        dimension: config.dimension,
    };

    info!(
        "IVF config: nlist={}, nprobe={}, dimension={}",
        ivf_config.nlist, ivf_config.nprobe, ivf_config.dimension
    );

    // Create the service
    let service = IVFService::new(
        ivf_config,
        config.node_id.clone(),
        config.peers.clone(),
    );

    // Create socket address
    let addr: SocketAddr = format!("0.0.0.0:{}", config.port).parse()?;

    info!("IVF gRPC server listening on {}", addr);

    // TODO: Register the service with tonic and start the server
    // When proto file is available, uncomment:
    // Server::builder()
    //     .add_service(IVFSearchServiceServer::new(service))
    //     .serve(addr)
    //     .await?;

    // For now, just keep the server running
    info!("Server initialized. Waiting for gRPC service implementation...");

    // Keep the main task alive
    tokio::signal::ctrl_c().await?;
    info!("Shutting down IVF server");

    Ok(())
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_centroid_creation() {
        let centroid = Centroid::new(0, vec![1.0, 2.0, 3.0]);
        assert_eq!(centroid.id, 0);
        assert_eq!(centroid.vector.len(), 3);
        assert_eq!(centroid.count, 0);
    }

    #[test]
    fn test_centroid_zeros() {
        let centroid = Centroid::zeros(1, 5);
        assert_eq!(centroid.id, 1);
        assert_eq!(centroid.vector, vec![0.0; 5]);
    }

    #[test]
    fn test_inverted_list() {
        let mut list = InvertedList::new(0);
        assert!(list.is_empty());

        list.add(StoredVector {
            id: 1,
            vector: vec![1.0, 2.0],
            metadata: HashMap::new(),
        });

        assert_eq!(list.len(), 1);
        assert!(!list.is_empty());
    }

    #[test]
    fn test_ivf_config_default() {
        let config = IVFConfig::default();
        assert_eq!(config.nlist, DEFAULT_NLIST);
        assert_eq!(config.nprobe, DEFAULT_NPROBE);
    }

    #[test]
    fn test_ivf_index_creation() {
        let index = IVFIndex::with_defaults();
        assert!(index.is_empty());
        assert!(!index.is_trained());
    }

    #[test]
    fn test_compute_distance() {
        let index = IVFIndex::with_defaults();
        let a = vec![0.0, 0.0];
        let b = vec![3.0, 4.0];

        let distance = index.compute_distance(&a, &b);
        assert!((distance - 5.0).abs() < 1e-6);
    }

    #[test]
    fn test_compute_mean() {
        let v1 = vec![1.0, 2.0];
        let v2 = vec![3.0, 4.0];
        let vectors: Vec<&Vec<f32>> = vec![&v1, &v2];

        let mean = compute_mean(&vectors);
        assert_eq!(mean, vec![2.0, 3.0]);
    }

    #[test]
    fn test_distanced_vector_ordering() {
        let a = DistancedVector { id: 1, distance: 1.0 };
        let b = DistancedVector { id: 2, distance: 2.0 };

        assert!(a > b); // For min-heap behavior
    }
}
