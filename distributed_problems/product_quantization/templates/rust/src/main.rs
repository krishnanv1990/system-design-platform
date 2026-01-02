//! # Product Quantization (PQ) Vector Search Server
//!
//! This module implements a gRPC server for approximate nearest neighbor search
//! using Product Quantization. PQ compresses vectors into compact codes while
//! enabling fast approximate distance computation, dramatically reducing memory
//! usage and improving search speed.
//!
//! ## Algorithm Overview
//!
//! Product Quantization works by:
//!
//! ### Vector Decomposition
//! 1. Split each D-dimensional vector into M subvectors of D/M dimensions each
//! 2. Each subvector is quantized independently
//!
//! ### Training Phase
//! 1. For each subspace m (0 to M-1):
//!    a. Collect the m-th subvector from all training vectors
//!    b. Run K-means to learn K centroids (codebook with K codewords)
//! 2. Result: M codebooks, each with K centroids of dimension D/M
//!
//! ### Encoding
//! 1. For each vector, for each subspace m:
//!    a. Find nearest centroid in codebook m
//!    b. Store its index (requires log2(K) bits)
//! 2. Result: M codes per vector (typically M bytes if K=256)
//!
//! ### Distance Computation
//! 1. Precompute distance table: for each subspace, compute distances
//!    from query subvector to all K centroids
//! 2. For each database vector: sum up M table lookups
//!
//! ## Key Parameters
//!
//! - `M`: Number of subquantizers (subspaces), typically 8-64
//! - `K`: Number of centroids per subquantizer (typically 256 for 8-bit codes)
//! - `D`: Vector dimension (must be divisible by M)
//!
//! ## Complexity
//!
//! - Training: O(N * M * K * (D/M) * iterations)
//! - Encoding: O(M * K * D/M) = O(K * D) per vector
//! - Search: O(K * D) for distance table + O(N * M) for scanning
//! - Memory: O(N * M * log2(K) bits) for codes + O(M * K * D/M) for codebooks
//!
//! ## References
//!
//! Jegou, H., Douze, M., & Schmid, C. (2011). Product quantization for
//! nearest neighbor search. IEEE TPAMI.

use std::collections::{BinaryHeap, HashMap};
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

/// Default number of subquantizers
const DEFAULT_M: usize = 8;

/// Default number of centroids per subquantizer (256 for 8-bit codes)
const DEFAULT_KSUB: usize = 256;

/// Default vector dimensionality
const DEFAULT_DIMENSION: usize = 128;

/// Default number of K-means iterations for training
const DEFAULT_KMEANS_ITERATIONS: usize = 25;

/// Default gRPC server port
const DEFAULT_PORT: u16 = 50053;

/// Convergence threshold for K-means
const KMEANS_CONVERGENCE_THRESHOLD: f32 = 1e-6;

// ============================================================================
// Data Structures
// ============================================================================

/// Represents a search result with distance for priority queue operations.
#[derive(Debug, Clone)]
pub struct DistancedResult {
    /// Unique identifier of the vector
    pub id: u64,
    /// Approximate distance from the query vector
    pub distance: f32,
}

impl PartialEq for DistancedResult {
    fn eq(&self, other: &Self) -> bool {
        self.distance == other.distance
    }
}

impl Eq for DistancedResult {}

impl PartialOrd for DistancedResult {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for DistancedResult {
    fn cmp(&self, other: &Self) -> Ordering {
        // Reverse for min-heap behavior
        other.distance.partial_cmp(&self.distance).unwrap_or(Ordering::Equal)
    }
}

/// A codebook for a single subquantizer.
///
/// Contains K centroids (codewords) of dimension dsub = D/M.
/// Each centroid represents a region in the subspace.
#[derive(Debug, Clone)]
pub struct Codebook {
    /// Subquantizer index (0 to M-1)
    pub subquantizer_id: usize,

    /// Centroids (codewords) for this subquantizer
    /// Shape: K x dsub
    pub centroids: Vec<Vec<f32>>,

    /// Dimension of each centroid (D/M)
    pub dsub: usize,

    /// Number of centroids
    pub k: usize,
}

impl Codebook {
    /// Creates a new empty codebook.
    pub fn new(subquantizer_id: usize, k: usize, dsub: usize) -> Self {
        Self {
            subquantizer_id,
            centroids: Vec::with_capacity(k),
            dsub,
            k,
        }
    }

    /// Creates a codebook with random centroids.
    pub fn random(subquantizer_id: usize, k: usize, dsub: usize) -> Self {
        let mut rng = rand::thread_rng();
        let centroids = (0..k)
            .map(|_| (0..dsub).map(|_| rng.gen::<f32>() - 0.5).collect())
            .collect();

        Self {
            subquantizer_id,
            centroids,
            dsub,
            k,
        }
    }

    /// Returns the centroid at the given index.
    pub fn get_centroid(&self, index: usize) -> Option<&Vec<f32>> {
        self.centroids.get(index)
    }
}

/// A PQ code representing a compressed vector.
///
/// Contains M code indices, one for each subquantizer.
/// With K=256, each index fits in a u8 (1 byte).
#[derive(Debug, Clone)]
pub struct PQCode {
    /// Unique identifier for the original vector
    pub id: u64,

    /// Quantization codes (M indices into the codebooks)
    /// codes[m] is the index of the nearest centroid in codebook m
    pub codes: Vec<u8>,

    /// Optional metadata
    pub metadata: HashMap<String, String>,
}

impl PQCode {
    /// Creates a new PQ code.
    pub fn new(id: u64, codes: Vec<u8>) -> Self {
        Self {
            id,
            codes,
            metadata: HashMap::new(),
        }
    }

    /// Returns the memory footprint in bytes.
    pub fn memory_bytes(&self) -> usize {
        std::mem::size_of::<u64>() + self.codes.len()
    }
}

/// Configuration for the PQ index.
#[derive(Debug, Clone)]
pub struct PQConfig {
    /// Number of subquantizers
    pub m: usize,

    /// Number of centroids per subquantizer
    pub ksub: usize,

    /// Vector dimensionality
    pub dimension: usize,

    /// Dimension of each subvector (dimension / m)
    pub dsub: usize,

    /// Number of K-means iterations for training
    pub kmeans_iterations: usize,
}

impl PQConfig {
    /// Creates a new PQ configuration.
    ///
    /// # Panics
    ///
    /// Panics if dimension is not divisible by m.
    pub fn new(m: usize, ksub: usize, dimension: usize) -> Self {
        assert!(
            dimension % m == 0,
            "Dimension {} must be divisible by M {}",
            dimension,
            m
        );

        Self {
            m,
            ksub,
            dimension,
            dsub: dimension / m,
            kmeans_iterations: DEFAULT_KMEANS_ITERATIONS,
        }
    }
}

impl Default for PQConfig {
    fn default() -> Self {
        Self::new(DEFAULT_M, DEFAULT_KSUB, DEFAULT_DIMENSION)
    }
}

/// Distance table for asymmetric distance computation.
///
/// Stores precomputed distances from query subvectors to all centroids.
/// Shape: M x K, where entry [m][k] is the squared distance from
/// the m-th query subvector to the k-th centroid of codebook m.
#[derive(Debug, Clone)]
pub struct DistanceTable {
    /// Precomputed distances: table[m][k] = ||q_m - c_{m,k}||^2
    pub table: Vec<Vec<f32>>,

    /// Number of subquantizers
    pub m: usize,

    /// Number of centroids per subquantizer
    pub k: usize,
}

impl DistanceTable {
    /// Creates a new distance table.
    pub fn new(m: usize, k: usize) -> Self {
        Self {
            table: vec![vec![0.0; k]; m],
            m,
            k,
        }
    }

    /// Gets the precomputed distance for subquantizer m and centroid k.
    #[inline]
    pub fn get(&self, m: usize, k: usize) -> f32 {
        self.table[m][k]
    }

    /// Sets the distance for subquantizer m and centroid k.
    #[inline]
    pub fn set(&mut self, m: usize, k: usize, distance: f32) {
        self.table[m][k] = distance;
    }
}

/// The main Product Quantization index structure.
///
/// This structure maintains:
/// - Trained codebooks (one per subquantizer)
/// - Encoded vectors as PQ codes
/// - Configuration parameters
#[derive(Debug)]
pub struct PQIndex {
    /// Codebooks for each subquantizer (None until trained)
    pub codebooks: RwLock<Option<Vec<Codebook>>>,

    /// Encoded vectors
    pub codes: DashMap<u64, PQCode>,

    /// Optional: store original vectors for re-ranking
    pub original_vectors: DashMap<u64, Vec<f32>>,

    /// Configuration parameters
    pub config: PQConfig,

    /// Whether the index has been trained
    pub is_trained: RwLock<bool>,

    /// Next available vector ID
    pub next_id: RwLock<u64>,
}

impl PQIndex {
    /// Creates a new untrained PQ index.
    pub fn new(config: PQConfig) -> Self {
        Self {
            codebooks: RwLock::new(None),
            codes: DashMap::new(),
            original_vectors: DashMap::new(),
            config,
            is_trained: RwLock::new(false),
            next_id: RwLock::new(0),
        }
    }

    /// Creates a new index with default configuration.
    pub fn with_defaults() -> Self {
        Self::new(PQConfig::default())
    }

    /// Extracts the m-th subvector from a full vector.
    ///
    /// # Arguments
    ///
    /// * `vector` - The full D-dimensional vector
    /// * `m` - The subquantizer index
    ///
    /// # Returns
    ///
    /// Slice of the m-th subvector (dsub dimensions)
    fn get_subvector<'a>(&self, vector: &'a [f32], m: usize) -> &'a [f32] {
        let start = m * self.config.dsub;
        let end = start + self.config.dsub;
        &vector[start..end]
    }

    /// Computes squared Euclidean distance between two subvectors.
    fn compute_distance_squared(&self, a: &[f32], b: &[f32]) -> f32 {
        a.iter()
            .zip(b.iter())
            .map(|(x, y)| (x - y).powi(2))
            .sum()
    }

    /// Trains the subquantizers using K-means clustering.
    ///
    /// # Algorithm
    ///
    /// For each subquantizer m (0 to M-1):
    /// 1. Extract the m-th subvector from all training vectors
    /// 2. Run K-means clustering to find ksub centroids
    /// 3. Store centroids in codebook m
    ///
    /// # Arguments
    ///
    /// * `training_vectors` - Vectors to use for training
    ///
    /// # Returns
    ///
    /// Ok(()) if training succeeded
    ///
    /// # TODO
    ///
    /// Implement the subquantizer training algorithm.
    #[instrument(skip(self, training_vectors))]
    pub fn train_subquantizers(&self, training_vectors: &[Vec<f32>]) -> Result<(), String> {
        todo!("Implement subquantizer training: \
               1. Validate dimension of training vectors \
               2. For each subquantizer m in 0..M: \
                  a. Extract m-th subvectors from all training vectors \
                  b. Run K-means clustering with ksub clusters \
                  c. Create Codebook with trained centroids \
               3. Store codebooks in self.codebooks \
               4. Set self.is_trained to true")
    }

    /// Runs K-means clustering on subvectors.
    ///
    /// # Arguments
    ///
    /// * `subvectors` - Subvectors to cluster
    /// * `k` - Number of clusters
    ///
    /// # Returns
    ///
    /// Vector of K centroids
    ///
    /// # TODO
    ///
    /// Implement K-means for subvector clustering.
    fn kmeans_subvectors(
        &self,
        subvectors: &[Vec<f32>],
        k: usize,
    ) -> Vec<Vec<f32>> {
        todo!("Implement K-means for subvectors: \
               1. Initialize centroids (random or K-means++) \
               2. Iterate until convergence: \
                  a. Assign each subvector to nearest centroid \
                  b. Update centroids as cluster means \
               3. Return final centroids")
    }

    /// Encodes a vector into a PQ code.
    ///
    /// # Algorithm
    ///
    /// For each subquantizer m:
    /// 1. Extract the m-th subvector
    /// 2. Find the nearest centroid in codebook m
    /// 3. Store the centroid index as codes[m]
    ///
    /// # Arguments
    ///
    /// * `vector` - The vector to encode
    ///
    /// # Returns
    ///
    /// The PQ code (M indices)
    ///
    /// # TODO
    ///
    /// Implement vector encoding.
    pub fn encode_vector(&self, vector: &[f32]) -> Result<Vec<u8>, String> {
        todo!("Implement vector encoding: \
               1. Ensure index is trained \
               2. For each subquantizer m: \
                  a. Get the m-th subvector \
                  b. Compute distance to all centroids in codebook m \
                  c. Find index of nearest centroid \
                  d. Store index in codes[m] \
               3. Return the M-dimensional code")
    }

    /// Decodes a PQ code back to an approximate vector.
    ///
    /// # Algorithm
    ///
    /// For each subquantizer m:
    /// 1. Look up centroid codes[m] in codebook m
    /// 2. Concatenate centroids to form the reconstructed vector
    ///
    /// # Arguments
    ///
    /// * `codes` - The PQ code to decode
    ///
    /// # Returns
    ///
    /// The reconstructed D-dimensional vector
    ///
    /// # TODO
    ///
    /// Implement vector decoding.
    pub fn decode_vector(&self, codes: &[u8]) -> Result<Vec<f32>, String> {
        todo!("Implement vector decoding: \
               1. Ensure index is trained \
               2. Initialize result vector of dimension D \
               3. For each subquantizer m: \
                  a. Get centroid index from codes[m] \
                  b. Look up centroid in codebook m \
                  c. Copy centroid values to result[m*dsub..(m+1)*dsub] \
               4. Return the reconstructed vector")
    }

    /// Computes the distance table for a query vector.
    ///
    /// The distance table enables fast approximate distance computation
    /// by precomputing distances from query subvectors to all centroids.
    ///
    /// # Algorithm
    ///
    /// For each subquantizer m:
    /// 1. Extract the m-th query subvector
    /// 2. For each centroid k in codebook m:
    ///    a. Compute ||q_m - c_{m,k}||^2
    ///    b. Store in table[m][k]
    ///
    /// # Arguments
    ///
    /// * `query` - The query vector
    ///
    /// # Returns
    ///
    /// The M x K distance table
    ///
    /// # TODO
    ///
    /// Implement distance table computation.
    pub fn compute_distance_table(&self, query: &[f32]) -> Result<DistanceTable, String> {
        todo!("Implement distance table computation: \
               1. Ensure index is trained \
               2. Create DistanceTable of size M x K \
               3. For each subquantizer m: \
                  a. Get m-th query subvector \
                  b. For each centroid k in codebook m: \
                     - Compute squared distance from subvector to centroid \
                     - Store in table[m][k] \
               4. Return the distance table")
    }

    /// Computes approximate distance from a query to a PQ code.
    ///
    /// Uses the precomputed distance table for O(M) lookup.
    ///
    /// # Arguments
    ///
    /// * `table` - Precomputed distance table for the query
    /// * `code` - The PQ code to compute distance to
    ///
    /// # Returns
    ///
    /// Approximate squared L2 distance
    #[inline]
    pub fn compute_distance_with_table(&self, table: &DistanceTable, code: &PQCode) -> f32 {
        code.codes
            .iter()
            .enumerate()
            .map(|(m, &k)| table.get(m, k as usize))
            .sum()
    }

    /// Inserts a vector into the index.
    ///
    /// # Arguments
    ///
    /// * `vector` - The vector to insert
    /// * `store_original` - Whether to store the original vector for re-ranking
    ///
    /// # Returns
    ///
    /// The assigned vector ID
    pub fn insert_vector(
        &self,
        vector: Vec<f32>,
        store_original: bool,
    ) -> Result<u64, String> {
        if !*self.is_trained.read() {
            return Err("Index must be trained before inserting vectors".to_string());
        }

        // Encode the vector
        let codes = self.encode_vector(&vector)?;

        // Generate ID
        let id = {
            let mut next_id = self.next_id.write();
            let id = *next_id;
            *next_id += 1;
            id
        };

        // Store PQ code
        self.codes.insert(id, PQCode::new(id, codes));

        // Optionally store original vector
        if store_original {
            self.original_vectors.insert(id, vector);
        }

        Ok(id)
    }

    /// Searches for the K nearest neighbors using PQ distance computation.
    ///
    /// # Algorithm
    ///
    /// 1. Compute distance table for the query
    /// 2. For each PQ code in the index:
    ///    a. Compute approximate distance using table lookups
    ///    b. Maintain top-K candidates
    /// 3. Optionally re-rank with exact distances
    ///
    /// # Arguments
    ///
    /// * `query` - The query vector
    /// * `k` - Number of nearest neighbors to return
    /// * `rerank` - Whether to re-rank with exact distances (requires original vectors)
    ///
    /// # Returns
    ///
    /// Vector of (id, distance) pairs
    ///
    /// # TODO
    ///
    /// Implement PQ search algorithm.
    #[instrument(skip(self, query))]
    pub fn search_with_pq(
        &self,
        query: &[f32],
        k: usize,
        rerank: bool,
    ) -> Result<Vec<(u64, f32)>, String> {
        todo!("Implement PQ search: \
               1. Compute distance table for query \
               2. For each PQ code in the index: \
                  a. Compute approximate distance using table \
                  b. Maintain min-heap of top-k candidates \
               3. If rerank is true and original vectors stored: \
                  a. Compute exact distances for top candidates \
                  b. Re-sort by exact distance \
               4. Return top K results")
    }

    /// Deletes a vector from the index.
    pub fn delete_vector(&self, id: u64) -> bool {
        let removed_code = self.codes.remove(&id).is_some();
        self.original_vectors.remove(&id);
        removed_code
    }

    /// Returns the number of vectors in the index.
    pub fn len(&self) -> usize {
        self.codes.len()
    }

    /// Returns true if the index is empty.
    pub fn is_empty(&self) -> bool {
        self.codes.is_empty()
    }

    /// Returns true if the index has been trained.
    pub fn is_trained(&self) -> bool {
        *self.is_trained.read()
    }

    /// Returns the compression ratio.
    ///
    /// Original: D * 4 bytes (float32)
    /// Compressed: M bytes (assuming K=256)
    pub fn compression_ratio(&self) -> f32 {
        let original_bytes = self.config.dimension * 4;
        let compressed_bytes = self.config.m;
        original_bytes as f32 / compressed_bytes as f32
    }

    /// Computes the reconstruction error for a vector.
    ///
    /// The reconstruction error measures the loss of information
    /// due to quantization.
    pub fn reconstruction_error(&self, original: &[f32], codes: &[u8]) -> Result<f32, String> {
        let reconstructed = self.decode_vector(codes)?;

        let error: f32 = original
            .iter()
            .zip(reconstructed.iter())
            .map(|(a, b)| (a - b).powi(2))
            .sum();

        Ok(error.sqrt())
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
    pub m: Option<u32>,
    pub ksub: Option<u32>,
}

/// Response from training.
#[derive(Debug, Clone)]
pub struct TrainResponse {
    pub success: bool,
    pub num_subquantizers: u32,
    pub num_centroids: u32,
    pub message: String,
}

/// Request to insert a vector.
#[derive(Debug, Clone)]
pub struct InsertRequest {
    pub vector: Vector,
    pub store_original: bool,
}

/// Response from insert operation.
#[derive(Debug, Clone)]
pub struct InsertResponse {
    pub id: u64,
    pub success: bool,
    pub codes: Vec<u8>,
}

/// Request to encode a vector.
#[derive(Debug, Clone)]
pub struct EncodeRequest {
    pub vector: Vec<f32>,
}

/// Response from encode operation.
#[derive(Debug, Clone)]
pub struct EncodeResponse {
    pub codes: Vec<u8>,
    pub success: bool,
}

/// Request to decode a PQ code.
#[derive(Debug, Clone)]
pub struct DecodeRequest {
    pub codes: Vec<u8>,
}

/// Response from decode operation.
#[derive(Debug, Clone)]
pub struct DecodeResponse {
    pub vector: Vec<f32>,
    pub success: bool,
}

/// Request to search for nearest neighbors.
#[derive(Debug, Clone)]
pub struct SearchRequest {
    pub query: Vec<f32>,
    pub k: u32,
    pub rerank: bool,
}

/// A single search result.
#[derive(Debug, Clone)]
pub struct SearchResult {
    pub id: u64,
    pub distance: f32,
    pub codes: Vec<u8>,
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
    pub num_subquantizers: u32,
    pub num_centroids: u32,
    pub dimension: u32,
    pub compression_ratio: f32,
    pub is_trained: bool,
    pub memory_usage_mb: f32,
}

// ============================================================================
// gRPC Service Implementation
// ============================================================================

/// The PQ gRPC service implementation.
pub struct PQService {
    /// The PQ index
    index: Arc<PQIndex>,

    /// Node identifier in a distributed setting
    node_id: String,

    /// Peer addresses for distributed queries
    peers: Vec<String>,
}

impl PQService {
    /// Creates a new PQ service with the given configuration.
    pub fn new(config: PQConfig, node_id: String, peers: Vec<String>) -> Self {
        Self {
            index: Arc::new(PQIndex::new(config)),
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
               2. Call index.train_subquantizers \
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
               4. Return InsertResponse with codes")
    }

    /// Handles vector encoding.
    ///
    /// # TODO
    ///
    /// Implement gRPC handler for encode operation.
    pub async fn encode(&self, request: EncodeRequest) -> Result<EncodeResponse, Status> {
        todo!("Implement encode gRPC handler: \
               1. Check if index is trained \
               2. Call index.encode_vector \
               3. Return EncodeResponse with codes")
    }

    /// Handles PQ code decoding.
    ///
    /// # TODO
    ///
    /// Implement gRPC handler for decode operation.
    pub async fn decode(&self, request: DecodeRequest) -> Result<DecodeResponse, Status> {
        todo!("Implement decode gRPC handler: \
               1. Check if index is trained \
               2. Call index.decode_vector \
               3. Return DecodeResponse with reconstructed vector")
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
               3. Call index.search_with_pq \
               4. Return SearchResponse with results")
    }

    /// Handles vector deletion.
    pub async fn delete(&self, request: DeleteRequest) -> Result<DeleteResponse, Status> {
        let success = self.index.delete_vector(request.id);
        Ok(DeleteResponse { success })
    }

    /// Returns index statistics.
    pub async fn get_stats(&self, _request: StatsRequest) -> Result<StatsResponse, Status> {
        let num_vectors = self.index.len() as u64;
        let memory_codes = num_vectors * self.index.config.m as u64;
        let memory_codebooks = (self.index.config.m * self.index.config.ksub * self.index.config.dsub * 4) as u64;
        let memory_mb = (memory_codes + memory_codebooks) as f32 / (1024.0 * 1024.0);

        Ok(StatsResponse {
            num_vectors,
            num_subquantizers: self.index.config.m as u32,
            num_centroids: self.index.config.ksub as u32,
            dimension: self.index.config.dimension as u32,
            compression_ratio: self.index.compression_ratio(),
            is_trained: self.index.is_trained(),
            memory_usage_mb: memory_mb,
        })
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

    /// Number of subquantizers
    pub m: usize,

    /// Number of centroids per subquantizer
    pub ksub: usize,

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
        let mut m = DEFAULT_M;
        let mut ksub = DEFAULT_KSUB;
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
                "--m" | "--num-subquantizers" => {
                    if i + 1 < args.len() {
                        m = args[i + 1].parse().unwrap_or(DEFAULT_M);
                        i += 2;
                    } else {
                        i += 1;
                    }
                }
                "--ksub" | "--num-centroids" => {
                    if i + 1 < args.len() {
                        ksub = args[i + 1].parse().unwrap_or(DEFAULT_KSUB);
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
            ksub,
            dimension,
        }
    }
}

// ============================================================================
// Utility Functions
// ============================================================================

/// Computes the mean of a set of vectors.
pub fn compute_mean(vectors: &[&[f32]]) -> Vec<f32> {
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

/// Estimates memory usage for a PQ index.
///
/// # Arguments
///
/// * `num_vectors` - Number of vectors to store
/// * `m` - Number of subquantizers
/// * `ksub` - Centroids per subquantizer
/// * `dsub` - Dimension per subquantizer
///
/// # Returns
///
/// Estimated memory in bytes
pub fn estimate_memory(num_vectors: usize, m: usize, ksub: usize, dsub: usize) -> usize {
    // Codes: num_vectors * M bytes
    let codes_memory = num_vectors * m;

    // Codebooks: M * K * dsub * 4 bytes (float32)
    let codebook_memory = m * ksub * dsub * 4;

    codes_memory + codebook_memory
}

// ============================================================================
// Main Entry Point
// ============================================================================

/// Main entry point for the PQ gRPC server.
///
/// This function:
/// 1. Parses command-line arguments
/// 2. Initializes the PQ index
/// 3. Creates the gRPC service
/// 4. Starts the server
///
/// # Usage
///
/// ```bash
/// pq-server --node-id node-1 --port 50053 --m 8 --ksub 256 --dimension 128
/// ```
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing for logging
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("pq_server=info".parse()?)
        )
        .init();

    // Parse configuration
    let config = ServerConfig::from_args();

    info!(
        "Starting PQ server: node_id={}, port={}, peers={:?}",
        config.node_id, config.port, config.peers
    );

    // Validate configuration
    if config.dimension % config.m != 0 {
        error!(
            "Dimension {} must be divisible by M {}",
            config.dimension, config.m
        );
        return Err(format!(
            "Dimension {} must be divisible by M {}",
            config.dimension, config.m
        ).into());
    }

    // Create PQ configuration
    let pq_config = PQConfig::new(config.m, config.ksub, config.dimension);

    info!(
        "PQ config: M={}, Ksub={}, dimension={}, dsub={}",
        pq_config.m, pq_config.ksub, pq_config.dimension, pq_config.dsub
    );
    info!(
        "Compression ratio: {}x ({}D float32 -> {}B codes)",
        pq_config.dimension * 4 / pq_config.m,
        pq_config.dimension,
        pq_config.m
    );

    // Create the service
    let service = PQService::new(
        pq_config,
        config.node_id.clone(),
        config.peers.clone(),
    );

    // Create socket address
    let addr: SocketAddr = format!("0.0.0.0:{}", config.port).parse()?;

    info!("PQ gRPC server listening on {}", addr);

    // TODO: Register the service with tonic and start the server
    // When proto file is available, uncomment:
    // Server::builder()
    //     .add_service(PQSearchServiceServer::new(service))
    //     .serve(addr)
    //     .await?;

    // For now, just keep the server running
    info!("Server initialized. Waiting for gRPC service implementation...");

    // Keep the main task alive
    tokio::signal::ctrl_c().await?;
    info!("Shutting down PQ server");

    Ok(())
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pq_config_creation() {
        let config = PQConfig::new(8, 256, 128);
        assert_eq!(config.m, 8);
        assert_eq!(config.ksub, 256);
        assert_eq!(config.dimension, 128);
        assert_eq!(config.dsub, 16); // 128 / 8
    }

    #[test]
    #[should_panic]
    fn test_pq_config_invalid_dimension() {
        // Should panic because 128 is not divisible by 7
        PQConfig::new(7, 256, 128);
    }

    #[test]
    fn test_pq_config_default() {
        let config = PQConfig::default();
        assert_eq!(config.m, DEFAULT_M);
        assert_eq!(config.ksub, DEFAULT_KSUB);
        assert_eq!(config.dimension, DEFAULT_DIMENSION);
    }

    #[test]
    fn test_codebook_creation() {
        let codebook = Codebook::new(0, 256, 16);
        assert_eq!(codebook.subquantizer_id, 0);
        assert_eq!(codebook.k, 256);
        assert_eq!(codebook.dsub, 16);
        assert!(codebook.centroids.is_empty());
    }

    #[test]
    fn test_codebook_random() {
        let codebook = Codebook::random(0, 256, 16);
        assert_eq!(codebook.centroids.len(), 256);
        assert_eq!(codebook.centroids[0].len(), 16);
    }

    #[test]
    fn test_pq_code_creation() {
        let codes = vec![0u8, 1, 2, 3, 4, 5, 6, 7];
        let pq_code = PQCode::new(42, codes.clone());

        assert_eq!(pq_code.id, 42);
        assert_eq!(pq_code.codes, codes);
        assert_eq!(pq_code.memory_bytes(), 8 + 8); // u64 + 8 bytes
    }

    #[test]
    fn test_distance_table() {
        let mut table = DistanceTable::new(8, 256);
        assert_eq!(table.m, 8);
        assert_eq!(table.k, 256);

        table.set(0, 5, 1.5);
        assert_eq!(table.get(0, 5), 1.5);
    }

    #[test]
    fn test_pq_index_creation() {
        let index = PQIndex::with_defaults();
        assert!(index.is_empty());
        assert!(!index.is_trained());
    }

    #[test]
    fn test_compression_ratio() {
        let config = PQConfig::new(8, 256, 128);
        let index = PQIndex::new(config);

        // Original: 128 * 4 = 512 bytes
        // Compressed: 8 bytes
        // Ratio: 64
        assert_eq!(index.compression_ratio(), 64.0);
    }

    #[test]
    fn test_estimate_memory() {
        let memory = estimate_memory(1_000_000, 8, 256, 16);

        // Codes: 1M * 8 = 8MB
        // Codebooks: 8 * 256 * 16 * 4 = 128KB
        // Total: ~8.125MB
        assert!(memory > 8_000_000);
        assert!(memory < 9_000_000);
    }

    #[test]
    fn test_distanced_result_ordering() {
        let a = DistancedResult { id: 1, distance: 1.0 };
        let b = DistancedResult { id: 2, distance: 2.0 };

        assert!(a > b); // For min-heap behavior
    }

    #[test]
    fn test_compute_mean() {
        let v1 = vec![1.0f32, 2.0];
        let v2 = vec![3.0f32, 4.0];
        let vectors: Vec<&[f32]> = vec![&v1, &v2];

        let mean = compute_mean(&vectors);
        assert_eq!(mean, vec![2.0, 3.0]);
    }
}
