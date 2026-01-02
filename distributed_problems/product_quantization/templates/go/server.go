// Product Quantization (PQ) for Vector Compression - Go Template
//
// This template provides the structure for implementing a distributed PQ index
// for memory-efficient approximate nearest neighbor search. PQ compresses vectors by:
// - Splitting each D-dimensional vector into M subvectors of dimension D/M
// - Quantizing each subvector independently using a learned codebook
// - Representing each vector as M code indices (huge compression: D*4 bytes -> M bytes)
//
// Key Algorithm Steps:
// 1. TRAIN: Learn M codebooks, each with Ks centroids via k-means
// 2. ENCODE: Map each subvector to its nearest centroid code
// 3. SEARCH: Use precomputed distance tables for fast approximate distance
//
// Key Parameters:
// - M: Number of subquantizers (subvectors), typically 8-64
// - Ks: Number of centroids per subquantizer, typically 256 (8 bits per code)
// - nbits: Bits per code = log2(Ks), usually 8
//
// Distance Computation Modes:
// - Symmetric (SDC): Decode both vectors, compute exact distance
// - Asymmetric (ADC): Precompute distances from query to all centroids, sum per-subvector
//   ADC is faster and usually preferred
//
// Memory Analysis:
// - Original: D * 4 bytes (float32)
// - Compressed: M * (nbits/8) bytes
// - Compression ratio: (D * 4) / (M * 1) = 4D/M for 8-bit codes
//
// Reference: https://www.pinecone.io/learn/product-quantization/
//
// Usage:
//     go run server.go --node-id node1 --port 50051 --peers node2:50052,node3:50053

package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net"
	"strings"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"

	pb "github.com/sdp/pq"
)

// =============================================================================
// Core Data Structures
// =============================================================================

// DistanceType represents the distance metric to use
type DistanceType int

const (
	Euclidean DistanceType = iota
	InnerProduct
)

// Codebook represents a single subquantizer with its learned centroids
// Each codebook has Ks centroids, each of dimension Dsub = D/M
type Codebook struct {
	SubquantizerID int         `json:"subquantizer_id"`
	Ks             int         `json:"ks"`        // Number of centroids (typically 256)
	Dsub           int         `json:"dsub"`      // Subvector dimension
	Centroids      [][]float32 `json:"centroids"` // Ks centroids, each of dimension Dsub
}

// PQCode represents a compressed vector as M code indices
type PQCode struct {
	ID       string            `json:"id"`
	Codes    []uint32          `json:"codes"`    // M code indices (each 0 to Ks-1)
	Metadata map[string]string `json:"metadata,omitempty"`
}

// DistanceTable holds precomputed distances from query subvectors to all centroids
// Used for fast asymmetric distance computation
type DistanceTable struct {
	M      int         // Number of subquantizers
	Ks     int         // Centroids per subquantizer
	Values [][]float32 // [M][Ks] - distance from query subvector m to centroid k
}

// SearchCandidate represents a candidate during search
type SearchCandidate struct {
	ID            string
	Distance      float32 // Approximate distance from distance table
	ExactDistance float32 // Exact distance (if reranking enabled)
	Codes         []uint32
}

// PQIndex is the main index structure
type PQIndex struct {
	Dimension    int          `json:"dimension"`
	M            int          `json:"m"`            // Number of subquantizers
	Ks           int          `json:"ks"`           // Centroids per subquantizer
	Dsub         int          `json:"dsub"`         // Subvector dimension (D/M)
	Nbits        int          `json:"nbits"`        // Bits per code (log2(Ks))
	DistanceType DistanceType `json:"distance_type"`
	IsTrained    bool         `json:"is_trained"`

	Codebooks []Codebook       `json:"codebooks"` // M codebooks
	Codes     map[string]*PQCode `json:"codes"`     // ID -> PQCode

	// Training statistics
	QuantizationErrors []float32 `json:"quantization_errors"` // Per-subquantizer errors
	TotalError         float32   `json:"total_error"`
}

// =============================================================================
// PQ Server Implementation
// =============================================================================

// PQServer implements both PQService and NodeService
type PQServer struct {
	pb.UnimplementedPQServiceServer
	pb.UnimplementedNodeServiceServer

	nodeID      string
	port        int
	peers       []string
	index       *PQIndex

	mu          sync.RWMutex
	peerClients map[string]pb.NodeServiceClient
}

// NewPQServer creates a new PQ server instance
func NewPQServer(nodeID string, port int, peers []string) *PQServer {
	return &PQServer{
		nodeID:      nodeID,
		port:        port,
		peers:       peers,
		peerClients: make(map[string]pb.NodeServiceClient),
	}
}

// Initialize sets up connections to peer nodes for distributed operation
func (s *PQServer) Initialize() error {
	for _, peer := range s.peers {
		var conn *grpc.ClientConn
		var err error

		if strings.Contains(peer, ".run.app") {
			creds := credentials.NewClientTLSFromCert(nil, "")
			conn, err = grpc.Dial(peer, grpc.WithTransportCredentials(creds))
		} else {
			conn, err = grpc.Dial(peer, grpc.WithTransportCredentials(insecure.NewCredentials()))
		}

		if err != nil {
			log.Printf("Warning: Failed to connect to peer %s: %v", peer, err)
			continue
		}
		s.peerClients[peer] = pb.NewNodeServiceClient(conn)
	}
	log.Printf("Node %s initialized with peers: %v", s.nodeID, s.peers)
	return nil
}

// =============================================================================
// Distance Functions
// =============================================================================

// ComputeSubvectorDistance calculates distance between two subvectors
//
// TODO: Implement distance computation for each metric type:
// - Euclidean: sum((a[i] - b[i])^2)  (squared, no sqrt for efficiency)
// - InnerProduct: -sum(a[i] * b[i])
func (s *PQServer) ComputeSubvectorDistance(a, b []float32) float32 {
	// TODO: Implement distance computation based on s.index.DistanceType
	return 0.0
}

// ComputeFullDistance calculates distance between two full vectors
//
// TODO: Implement full distance computation:
// - Euclidean: sqrt(sum((a[i] - b[i])^2))
// - InnerProduct: -sum(a[i] * b[i])
func (s *PQServer) ComputeFullDistance(a, b []float32) float32 {
	// TODO: Implement full vector distance
	return 0.0
}

// =============================================================================
// Core PQ Algorithm Functions
// =============================================================================

// TrainSubquantizers trains the M codebooks using k-means on subvector slices
// Each subquantizer learns Ks centroids for its portion of the vector
//
// TODO: Implement subquantizer training:
// 1. Split each training vector into M subvectors:
//    - Subvector m starts at index m * Dsub
//    - Subvector m has dimension Dsub = D / M
// 2. For each subquantizer m (0 to M-1):
//    a. Extract subvector slice from all training vectors
//    b. Run k-means with Ks centroids on these subvectors
//    c. Store learned centroids in s.index.Codebooks[m]
//    d. Calculate quantization error (sum of squared distances to nearest centroid)
// 3. Store per-subquantizer errors and total error
// 4. Mark index as trained
//
// K-means for each subquantizer:
// - Initialize Ks centroids (random or k-means++)
// - Repeat for nIterations:
//   - Assign each subvector to nearest centroid
//   - Recompute centroids as mean of assigned subvectors
func (s *PQServer) TrainSubquantizers(vectors [][]float32, nIterations int) error {
	// TODO: Implement codebook training via k-means per subquantizer
	return nil
}

// EncodeVector encodes a full vector into M code indices
//
// TODO: Implement vector encoding:
// 1. Initialize codes array of size M
// 2. For each subquantizer m (0 to M-1):
//    a. Extract subvector: vector[m*Dsub : (m+1)*Dsub]
//    b. Find nearest centroid in codebook[m]
//    c. Store centroid index in codes[m]
// 3. Return codes array
//
// Complexity: O(M * Ks * Dsub) - for each of M subvectors, compare to Ks centroids
func (s *PQServer) EncodeVector(vector []float32) ([]uint32, error) {
	// TODO: Encode vector to PQ codes
	return nil, nil
}

// DecodeVector reconstructs an approximate vector from PQ codes
//
// TODO: Implement vector decoding:
// 1. Initialize result vector of size D
// 2. For each subquantizer m (0 to M-1):
//    a. Get centroid index from codes[m]
//    b. Copy codebook[m].Centroids[codes[m]] to result[m*Dsub : (m+1)*Dsub]
// 3. Return reconstructed vector
//
// Note: This is lossy reconstruction - information is lost during quantization
func (s *PQServer) DecodeVector(codes []uint32) ([]float32, error) {
	// TODO: Decode PQ codes back to approximate vector
	return nil, nil
}

// ComputeDistanceTable precomputes distances from query subvectors to all centroids
// This is the key optimization that makes PQ search fast
//
// TODO: Implement distance table computation:
// 1. Initialize table of size [M][Ks]
// 2. For each subquantizer m (0 to M-1):
//    a. Extract query subvector: query[m*Dsub : (m+1)*Dsub]
//    b. For each centroid k (0 to Ks-1):
//       - Compute distance from query subvector to codebook[m].Centroids[k]
//       - Store in table[m][k]
// 3. Return distance table
//
// Complexity: O(M * Ks * Dsub)
// This is done once per query, then reused for all database vectors
func (s *PQServer) ComputeDistanceTable(query []float32) (*DistanceTable, error) {
	// TODO: Precompute distance table for asymmetric distance computation
	return nil, nil
}

// ComputeApproximateDistance computes approximate distance using precomputed table
// This is the ADC (Asymmetric Distance Computation) approach
//
// TODO: Implement ADC distance:
// 1. Initialize distance = 0
// 2. For each subquantizer m (0 to M-1):
//    - Add table.Values[m][codes[m]] to distance
// 3. Return distance (take sqrt for Euclidean if needed)
//
// Complexity: O(M) - just M table lookups!
// This is why PQ is so fast: linear scan with O(M) distance computation
func (s *PQServer) ComputeApproximateDistance(table *DistanceTable, codes []uint32) float32 {
	// TODO: Use distance table for fast approximate distance
	return 0.0
}

// SearchWithPQ searches for k nearest neighbors using PQ
//
// TODO: Implement PQ search:
// 1. Compute distance table for query using ComputeDistanceTable
// 2. For each stored code in s.index.Codes:
//    - Compute approximate distance using ComputeApproximateDistance
//    - Track top k candidates (use heap for efficiency)
// 3. If reranking enabled:
//    a. Decode top rerank_k candidates to get approximate vectors
//    b. Compute exact distances to query
//    c. Re-sort by exact distance
//    d. Return top k
// 4. Return results
//
// Complexity without reranking: O(M*Ks*Dsub + n*M) = O(n*M) for large n
// The first term (table computation) is done once, second term is the scan
func (s *PQServer) SearchWithPQ(query []float32, k int, rerank bool, rerankK int) ([]SearchCandidate, error) {
	// TODO: Implement PQ search with optional reranking
	return nil, nil
}

// =============================================================================
// PQService gRPC Implementation
// =============================================================================

// CreateIndex creates a new PQ index with specified parameters
func (s *PQServer) CreateIndex(ctx context.Context, req *pb.CreateIndexRequest) (*pb.CreateIndexResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	m := int(req.M)
	if m == 0 {
		m = 8 // Default: 8 subquantizers
	}

	ks := int(req.Ks)
	if ks == 0 {
		ks = 256 // Default: 256 centroids (8 bits per code)
	}

	dim := int(req.Dimension)
	if dim%m != 0 {
		return &pb.CreateIndexResponse{
			Success: false,
			Error:   fmt.Sprintf("Dimension %d must be divisible by M %d", dim, m),
		}, nil
	}

	dsub := dim / m

	// Calculate nbits from ks
	nbits := 0
	for k := ks; k > 1; k >>= 1 {
		nbits++
	}

	distType := Euclidean
	if req.DistanceType == "inner_product" {
		distType = InnerProduct
	}

	s.index = &PQIndex{
		Dimension:    dim,
		M:            m,
		Ks:           ks,
		Dsub:         dsub,
		Nbits:        nbits,
		DistanceType: distType,
		IsTrained:    false,
		Codebooks:    make([]Codebook, m),
		Codes:        make(map[string]*PQCode),
	}

	// Initialize empty codebooks
	for i := 0; i < m; i++ {
		s.index.Codebooks[i] = Codebook{
			SubquantizerID: i,
			Ks:             ks,
			Dsub:           dsub,
			Centroids:      make([][]float32, 0),
		}
	}

	log.Printf("Created PQ index: dim=%d, M=%d, Ks=%d, Dsub=%d, nbits=%d",
		dim, m, ks, dsub, nbits)
	log.Printf("Compression ratio: %.1fx (%d bytes -> %d bytes per vector)",
		float64(dim*4)/float64(m), dim*4, m)

	return &pb.CreateIndexResponse{
		Success: true,
		IndexId: fmt.Sprintf("pq-%s-%d", s.nodeID, time.Now().UnixNano()),
		Dsub:    int32(dsub),
	}, nil
}

// Train trains the codebooks on training vectors
func (s *PQServer) Train(ctx context.Context, req *pb.TrainRequest) (*pb.TrainResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.index == nil {
		return &pb.TrainResponse{Success: false, Error: "Index not created"}, nil
	}

	if len(req.TrainingVectors) < s.index.Ks {
		return &pb.TrainResponse{
			Success: false,
			Error:   fmt.Sprintf("Need at least %d training vectors, got %d", s.index.Ks, len(req.TrainingVectors)),
		}, nil
	}

	// Convert proto vectors to float arrays
	vectors := make([][]float32, len(req.TrainingVectors))
	for i, v := range req.TrainingVectors {
		if len(v.Values) != s.index.Dimension {
			return &pb.TrainResponse{
				Success: false,
				Error:   fmt.Sprintf("Training vector %d has wrong dimension: expected %d, got %d", i, s.index.Dimension, len(v.Values)),
			}, nil
		}
		vectors[i] = v.Values
	}

	nIterations := int(req.NIterations)
	if nIterations == 0 {
		nIterations = 25
	}

	err := s.TrainSubquantizers(vectors, nIterations)
	if err != nil {
		return &pb.TrainResponse{Success: false, Error: err.Error()}, nil
	}

	s.index.IsTrained = true

	return &pb.TrainResponse{
		Success:             true,
		QuantizationErrors: s.index.QuantizationErrors,
		TotalError:         s.index.TotalError,
	}, nil
}

// Encode encodes a vector to PQ codes
func (s *PQServer) Encode(ctx context.Context, req *pb.EncodeRequest) (*pb.EncodeResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.index == nil || !s.index.IsTrained {
		return &pb.EncodeResponse{Success: false, Error: "Index not trained"}, nil
	}

	if len(req.Vector) != s.index.Dimension {
		return &pb.EncodeResponse{
			Success: false,
			Error:   fmt.Sprintf("Vector dimension mismatch: expected %d, got %d", s.index.Dimension, len(req.Vector)),
		}, nil
	}

	codes, err := s.EncodeVector(req.Vector)
	if err != nil {
		return &pb.EncodeResponse{Success: false, Error: err.Error()}, nil
	}

	return &pb.EncodeResponse{
		Success: true,
		Codes:   codes,
	}, nil
}

// Decode decodes PQ codes back to approximate vector
func (s *PQServer) Decode(ctx context.Context, req *pb.DecodeRequest) (*pb.DecodeResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.index == nil || !s.index.IsTrained {
		return &pb.DecodeResponse{Success: false, Error: "Index not trained"}, nil
	}

	if len(req.Codes) != s.index.M {
		return &pb.DecodeResponse{
			Success: false,
			Error:   fmt.Sprintf("Expected %d codes, got %d", s.index.M, len(req.Codes)),
		}, nil
	}

	vector, err := s.DecodeVector(req.Codes)
	if err != nil {
		return &pb.DecodeResponse{Success: false, Error: err.Error()}, nil
	}

	return &pb.DecodeResponse{
		Success: true,
		Vector:  vector,
	}, nil
}

// Add adds a vector to the index
func (s *PQServer) Add(ctx context.Context, req *pb.AddRequest) (*pb.AddResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.index == nil || !s.index.IsTrained {
		return &pb.AddResponse{Success: false, Error: "Index not trained"}, nil
	}

	if len(req.Vector) != s.index.Dimension {
		return &pb.AddResponse{
			Success: false,
			Error:   fmt.Sprintf("Vector dimension mismatch: expected %d, got %d", s.index.Dimension, len(req.Vector)),
		}, nil
	}

	codes, err := s.EncodeVector(req.Vector)
	if err != nil {
		return &pb.AddResponse{Success: false, Error: err.Error()}, nil
	}

	s.index.Codes[req.Id] = &PQCode{
		ID:       req.Id,
		Codes:    codes,
		Metadata: req.Metadata,
	}

	return &pb.AddResponse{
		Success: true,
		Codes:   codes,
	}, nil
}

// BatchAdd adds multiple vectors
func (s *PQServer) BatchAdd(ctx context.Context, req *pb.BatchAddRequest) (*pb.BatchAddResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.index == nil || !s.index.IsTrained {
		return &pb.BatchAddResponse{Success: false, Error: "Index not trained"}, nil
	}

	added := 0
	var failedIDs []string

	for _, v := range req.Vectors {
		if len(v.Values) != s.index.Dimension {
			failedIDs = append(failedIDs, v.Id)
			continue
		}

		codes, err := s.EncodeVector(v.Values)
		if err != nil {
			failedIDs = append(failedIDs, v.Id)
			continue
		}

		s.index.Codes[v.Id] = &PQCode{
			ID:       v.Id,
			Codes:    codes,
			Metadata: v.Metadata,
		}
		added++
	}

	return &pb.BatchAddResponse{
		Success:    len(failedIDs) == 0,
		AddedCount: int32(added),
		FailedIds:  failedIDs,
	}, nil
}

// Search finds k nearest neighbors
func (s *PQServer) Search(ctx context.Context, req *pb.SearchRequest) (*pb.SearchResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.index == nil || !s.index.IsTrained {
		return &pb.SearchResponse{}, nil
	}

	startTime := time.Now()

	rerankK := int(req.RerankK)
	if req.Rerank && rerankK == 0 {
		rerankK = int(req.K) * 10 // Default: rerank top 10x candidates
	}

	candidates, err := s.SearchWithPQ(req.QueryVector, int(req.K), req.Rerank, rerankK)
	if err != nil {
		return &pb.SearchResponse{}, nil
	}

	results := make([]*pb.SearchResult, 0, len(candidates))
	for _, c := range candidates {
		results = append(results, &pb.SearchResult{
			Id:            c.ID,
			Distance:      c.Distance,
			ExactDistance: c.ExactDistance,
			Codes:         c.Codes,
		})
	}

	return &pb.SearchResponse{
		Results:       results,
		SearchTimeUs:  time.Since(startTime).Microseconds(),
		UsedReranking: req.Rerank,
	}, nil
}

// Remove removes a vector from the index
//
// TODO: Implement code removal
func (s *PQServer) Remove(ctx context.Context, req *pb.RemoveRequest) (*pb.RemoveResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.index == nil {
		return &pb.RemoveResponse{Success: false, Error: "Index not created"}, nil
	}

	if _, ok := s.index.Codes[req.Id]; !ok {
		return &pb.RemoveResponse{Success: true, Found: false}, nil
	}

	delete(s.index.Codes, req.Id)
	return &pb.RemoveResponse{Success: true, Found: true}, nil
}

// GetStats returns index statistics
func (s *PQServer) GetStats(ctx context.Context, req *pb.GetStatsRequest) (*pb.GetStatsResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.index == nil {
		return &pb.GetStatsResponse{Stats: &pb.IndexStats{}}, nil
	}

	// Calculate compression ratio
	originalSize := float32(s.index.Dimension * 4) // float32
	compressedSize := float32(s.index.M)           // 1 byte per code for Ks=256
	compressionRatio := originalSize / compressedSize

	return &pb.GetStatsResponse{
		Stats: &pb.IndexStats{
			TotalVectors:     int64(len(s.index.Codes)),
			Dimension:        int32(s.index.Dimension),
			M:                int32(s.index.M),
			Ks:               int32(s.index.Ks),
			Nbits:            int32(s.index.Nbits),
			IsTrained:        s.index.IsTrained,
			CompressionRatio: compressionRatio,
		},
	}, nil
}

// GetCodebooks returns all codebooks
func (s *PQServer) GetCodebooks(ctx context.Context, req *pb.GetCodebooksRequest) (*pb.GetCodebooksResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.index == nil || !s.index.IsTrained {
		return &pb.GetCodebooksResponse{}, nil
	}

	codebooks := make([]*pb.Codebook, s.index.M)
	for i, cb := range s.index.Codebooks {
		// Flatten centroids for proto
		flatCentroids := make([]float32, 0, cb.Ks*cb.Dsub)
		for _, centroid := range cb.Centroids {
			flatCentroids = append(flatCentroids, centroid...)
		}

		codebooks[i] = &pb.Codebook{
			SubquantizerId: int32(cb.SubquantizerID),
			Ks:             int32(cb.Ks),
			Dsub:           int32(cb.Dsub),
			Centroids:      flatCentroids,
		}
	}

	return &pb.GetCodebooksResponse{Codebooks: codebooks}, nil
}

// ComputeDistanceTable computes and returns the distance table for a query
func (s *PQServer) ComputeDistanceTable(ctx context.Context, req *pb.ComputeDistanceTableRequest) (*pb.ComputeDistanceTableResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.index == nil || !s.index.IsTrained {
		return &pb.ComputeDistanceTableResponse{}, nil
	}

	table, err := s.ComputeDistanceTable(req.QueryVector)
	if err != nil {
		return &pb.ComputeDistanceTableResponse{}, nil
	}

	// Flatten table for proto
	flatTable := make([]float32, 0, s.index.M*s.index.Ks)
	for _, row := range table.Values {
		flatTable = append(flatTable, row...)
	}

	return &pb.ComputeDistanceTableResponse{
		DistanceTable: flatTable,
		M:             int32(s.index.M),
		Ks:            int32(s.index.Ks),
	}, nil
}

// =============================================================================
// NodeService gRPC Implementation (Distributed Operations)
// =============================================================================

// SyncCodebooks synchronizes codebooks from another node
//
// TODO: Implement codebook synchronization for distributed PQ:
// - All nodes must share the same codebooks for consistent encoding
// - Typically trained on one node and broadcast to others
func (s *PQServer) SyncCodebooks(ctx context.Context, req *pb.SyncCodebooksRequest) (*pb.SyncCodebooksResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	// TODO: Implement codebook synchronization
	return &pb.SyncCodebooksResponse{Success: false, CodebooksSynced: 0}, nil
}

// ForwardSearch forwards a search request to this node
//
// TODO: Implement search forwarding:
// - Receive precomputed distance table
// - Search local codes using the table
// - Return partial results
func (s *PQServer) ForwardSearch(ctx context.Context, req *pb.ForwardSearchRequest) (*pb.ForwardSearchResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	// TODO: Search local codes using provided distance table
	return &pb.ForwardSearchResponse{
		Results:  nil,
		ServedBy: s.nodeID,
	}, nil
}

// TransferCodes handles code transfer during rebalancing
//
// TODO: Implement code transfer for load balancing:
// - Receive PQ codes from another node
// - Store in local index
func (s *PQServer) TransferCodes(ctx context.Context, req *pb.TransferCodesRequest) (*pb.TransferCodesResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	// TODO: Implement code transfer
	return &pb.TransferCodesResponse{Success: false, TransferredCount: 0}, nil
}

// Heartbeat handles health check requests
func (s *PQServer) Heartbeat(ctx context.Context, req *pb.HeartbeatRequest) (*pb.HeartbeatResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	log.Printf("Heartbeat from %s: %d vectors", req.NodeId, req.VectorCount)

	return &pb.HeartbeatResponse{
		Acknowledged: true,
		Timestamp:    time.Now().UnixNano(),
	}, nil
}

// =============================================================================
// Main Entry Point
// =============================================================================

func main() {
	nodeID := flag.String("node-id", "", "Unique node identifier")
	port := flag.Int("port", 50051, "Port to listen on")
	peersStr := flag.String("peers", "", "Comma-separated list of peer addresses")
	flag.Parse()

	if *nodeID == "" {
		log.Fatal("--node-id is required")
	}

	var peers []string
	if *peersStr != "" {
		peers = strings.Split(*peersStr, ",")
		for i, p := range peers {
			peers[i] = strings.TrimSpace(p)
		}
	}

	server := NewPQServer(*nodeID, *port, peers)
	if err := server.Initialize(); err != nil {
		log.Fatalf("Failed to initialize server: %v", err)
	}

	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	grpcServer := grpc.NewServer()
	pb.RegisterPQServiceServer(grpcServer, server)
	pb.RegisterNodeServiceServer(grpcServer, server)

	log.Printf("Starting PQ server %s on port %d", *nodeID, *port)
	log.Printf("Product Quantization Summary:")
	log.Printf("  - Compress vectors by splitting into M subvectors")
	log.Printf("  - Each subvector mapped to nearest of Ks centroids")
	log.Printf("  - Fast search via precomputed distance tables (ADC)")

	if err := grpcServer.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
