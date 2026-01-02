// HNSW (Hierarchical Navigable Small World) Index - Go Template
//
// This template provides the structure for implementing a distributed HNSW index
// for approximate nearest neighbor search. HNSW builds a hierarchical graph where:
// - Each layer is a proximity graph with skip-list like structure
// - Higher layers have exponentially fewer nodes (controlled by mL parameter)
// - Search starts from top layer entry point and descends to find neighbors
// - Layer 0 contains all nodes, upper layers provide fast navigation
//
// Key Algorithm Steps:
// 1. INSERT: Assign random level, find neighbors at each layer using greedy search
// 2. SEARCH: Start at entry point, greedily descend through layers to layer 0
// 3. SELECT NEIGHBORS: Choose diverse set of neighbors (simple or heuristic)
//
// Key Parameters:
// - M: Maximum connections per node per layer (M0 = 2*M for layer 0)
// - efConstruction: Dynamic candidate list size during construction
// - efSearch: Dynamic candidate list size during search (higher = more accurate)
// - mL: Level generation factor (typically 1/ln(M))
//
// Reference: https://arxiv.org/abs/1603.09320
//
// Usage:
//     go run server.go --node-id node1 --port 50051 --peers node2:50052,node3:50053

package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"math"
	"net"
	"strings"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"

	pb "github.com/sdp/hnsw"
)

// =============================================================================
// Core Data Structures
// =============================================================================

// DistanceType represents the distance metric to use
type DistanceType int

const (
	Euclidean DistanceType = iota
	Cosine
	InnerProduct
)

// HNSWNode represents a node in the HNSW graph
// Each node exists in layers 0..level, with connections at each layer
type HNSWNode struct {
	ID       string             `json:"id"`
	Vector   []float32          `json:"vector"`
	Level    int                `json:"level"`              // Maximum layer this node appears in
	Neighbors map[int][]string  `json:"neighbors"`          // Layer -> list of neighbor IDs
	Metadata map[string]string  `json:"metadata,omitempty"`
}

// Candidate represents a node during search with its distance to query
type Candidate struct {
	ID       string
	Distance float32
}

// CandidateHeap is a min-heap of candidates ordered by distance
// Used for efficient nearest neighbor tracking during search
type CandidateHeap struct {
	items    []Candidate
	isMaxHeap bool  // true for result set (want farthest), false for candidates (want nearest)
}

// HNSWIndex is the main index structure containing all nodes and graph connections
type HNSWIndex struct {
	Dimension       int                      `json:"dimension"`
	M               int                      `json:"m"`                // Max connections per layer (M0 = 2*M for layer 0)
	EfConstruction  int                      `json:"ef_construction"`  // Search depth during construction
	DistanceType    DistanceType             `json:"distance_type"`

	Nodes           map[string]*HNSWNode     `json:"nodes"`           // ID -> Node
	EntryPoint      string                   `json:"entry_point"`     // ID of entry point node
	MaxLevel        int                      `json:"max_level"`       // Current maximum level in graph

	// Derived parameters
	ML              float64                  `json:"-"`               // Level multiplier: 1/ln(M)
	M0              int                      `json:"-"`               // Max connections for layer 0
}

// =============================================================================
// HNSW Server Implementation
// =============================================================================

// HNSWServer implements both HNSWService and NodeService
type HNSWServer struct {
	pb.UnimplementedHNSWServiceServer
	pb.UnimplementedNodeServiceServer

	nodeID      string
	port        int
	peers       []string
	index       *HNSWIndex

	mu          sync.RWMutex
	peerClients map[string]pb.NodeServiceClient
}

// NewHNSWServer creates a new HNSW server instance
func NewHNSWServer(nodeID string, port int, peers []string) *HNSWServer {
	return &HNSWServer{
		nodeID:      nodeID,
		port:        port,
		peers:       peers,
		peerClients: make(map[string]pb.NodeServiceClient),
	}
}

// Initialize sets up connections to peer nodes for distributed operation
func (s *HNSWServer) Initialize() error {
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

// ComputeDistance calculates distance between two vectors based on configured metric
//
// TODO: Implement distance computation for each metric type:
// - Euclidean: sqrt(sum((a[i] - b[i])^2))
// - Cosine: 1 - (dot(a,b) / (norm(a) * norm(b)))
// - InnerProduct: -dot(a,b)  (negative for min-heap compatibility)
func (s *HNSWServer) ComputeDistance(a, b []float32) float32 {
	// TODO: Implement based on s.index.DistanceType
	return 0.0
}

// =============================================================================
// Core HNSW Algorithm Functions
// =============================================================================

// GenerateRandomLevel generates a random level for a new node
// Uses exponential distribution with parameter mL = 1/ln(M)
// Probability of level l: P(l) = (1/M)^l * (1 - 1/M)
//
// TODO: Implement level generation:
// - Generate uniform random number u in (0, 1)
// - Return floor(-ln(u) * mL)
// - Cap at reasonable maximum (e.g., 16) to prevent outliers
func (s *HNSWServer) GenerateRandomLevel() int {
	// TODO: Implement random level generation using exponential distribution
	return 0
}

// SearchLayer performs greedy search within a single layer of the graph
// Returns the ef closest nodes to the query vector
//
// TODO: Implement layer search (Algorithm 2 in HNSW paper):
// 1. Initialize candidates heap with entry points
// 2. Initialize results with entry points
// 3. While candidates is not empty:
//    a. Get closest candidate c
//    b. Get furthest result f
//    c. If distance(c, query) > distance(f, query), break (all remaining are worse)
//    d. For each neighbor e of c at this layer:
//       - If e not visited:
//         - Mark e visited
//         - Get furthest result f
//         - If distance(e, query) < distance(f, query) or |results| < ef:
//           - Add e to candidates and results
//           - If |results| > ef, remove furthest from results
// 4. Return results
func (s *HNSWServer) SearchLayer(query []float32, entryPoints []string, ef int, layer int) []Candidate {
	// TODO: Implement greedy search within a layer
	return nil
}

// SelectNeighbors chooses which nodes to connect to a new node
// This is the key quality-determining step in HNSW construction
//
// TODO: Implement neighbor selection (two options):
//
// Simple selection (Algorithm 3):
// - Return M closest candidates by distance
//
// Heuristic selection (Algorithm 4) - better quality:
// - Start with empty result R
// - While |candidates| > 0 and |R| < M:
//   a. Get closest candidate e
//   b. If e is closer to query than any node in R: add e to R
//   c. This ensures diverse neighbors, not just closest ones
// - Return R
//
// The heuristic prevents the "curse of hub nodes" and improves recall
func (s *HNSWServer) SelectNeighbors(query []float32, candidates []Candidate, m int, layer int, extendCandidates bool, keepPruned bool) []string {
	// TODO: Implement neighbor selection (simple or heuristic)
	return nil
}

// InsertVector inserts a new vector into the HNSW index
//
// TODO: Implement insertion (Algorithm 1 in HNSW paper):
// 1. Get node's level l using GenerateRandomLevel()
// 2. If graph is empty, make this the entry point and return
// 3. Find entry point ep for the search
// 4. For layers L down to l+1 (above node's max level):
//    - Search for 1 nearest neighbor starting from ep
//    - Update ep to be that nearest neighbor
// 5. For layers min(L, l) down to 0:
//    - Search for efConstruction nearest neighbors from ep
//    - Select M best neighbors using SelectNeighbors
//    - Create bidirectional connections
//    - For each neighbor: if they exceed M connections, prune their connections
//    - Update ep to be closest found node
// 6. If l > L, update entry point and max level
func (s *HNSWServer) InsertVector(id string, vector []float32, metadata map[string]string) (int, error) {
	// TODO: Implement vector insertion into HNSW graph
	return 0, nil
}

// SearchKNN finds k nearest neighbors for a query vector
//
// TODO: Implement k-NN search (Algorithm 5 in HNSW paper):
// 1. Start at entry point ep
// 2. For layers L down to 1:
//    - Search for 1 nearest neighbor from ep
//    - Update ep to that neighbor (greedy descent)
// 3. At layer 0:
//    - Search for ef neighbors from ep
//    - Return top k from results
func (s *HNSWServer) SearchKNN(query []float32, k int, efSearch int) ([]Candidate, int) {
	// TODO: Implement k-NN search
	return nil, 0
}

// =============================================================================
// HNSWService gRPC Implementation
// =============================================================================

// CreateIndex creates a new HNSW index with specified parameters
func (s *HNSWServer) CreateIndex(ctx context.Context, req *pb.CreateIndexRequest) (*pb.CreateIndexResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	m := int(req.M)
	if m == 0 {
		m = 16 // Default M
	}
	efConstruction := int(req.EfConstruction)
	if efConstruction == 0 {
		efConstruction = 200 // Default efConstruction
	}

	distType := Euclidean
	switch req.DistanceType {
	case "cosine":
		distType = Cosine
	case "inner_product":
		distType = InnerProduct
	}

	s.index = &HNSWIndex{
		Dimension:      int(req.Dimension),
		M:              m,
		M0:             2 * m,  // Layer 0 has 2*M connections
		EfConstruction: efConstruction,
		DistanceType:   distType,
		Nodes:          make(map[string]*HNSWNode),
		MaxLevel:       -1,
		ML:             1.0 / math.Log(float64(m)),  // mL = 1/ln(M)
	}

	log.Printf("Created HNSW index: dim=%d, M=%d, efConstruction=%d",
		req.Dimension, m, efConstruction)

	return &pb.CreateIndexResponse{
		Success: true,
		IndexId: fmt.Sprintf("hnsw-%s-%d", s.nodeID, time.Now().UnixNano()),
	}, nil
}

// Insert inserts a vector into the index
func (s *HNSWServer) Insert(ctx context.Context, req *pb.InsertRequest) (*pb.InsertResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.index == nil {
		return &pb.InsertResponse{Success: false, Error: "Index not created"}, nil
	}

	if len(req.Vector) != s.index.Dimension {
		return &pb.InsertResponse{
			Success: false,
			Error:   fmt.Sprintf("Vector dimension mismatch: expected %d, got %d", s.index.Dimension, len(req.Vector)),
		}, nil
	}

	level, err := s.InsertVector(req.Id, req.Vector, req.Metadata)
	if err != nil {
		return &pb.InsertResponse{Success: false, Error: err.Error()}, nil
	}

	return &pb.InsertResponse{Success: true, Level: int32(level)}, nil
}

// BatchInsert inserts multiple vectors
func (s *HNSWServer) BatchInsert(ctx context.Context, req *pb.BatchInsertRequest) (*pb.BatchInsertResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.index == nil {
		return &pb.BatchInsertResponse{Success: false, Error: "Index not created"}, nil
	}

	inserted := 0
	var failedIDs []string

	for _, vec := range req.Vectors {
		if len(vec.Values) != s.index.Dimension {
			failedIDs = append(failedIDs, vec.Id)
			continue
		}

		_, err := s.InsertVector(vec.Id, vec.Values, vec.Metadata)
		if err != nil {
			failedIDs = append(failedIDs, vec.Id)
			continue
		}
		inserted++
	}

	return &pb.BatchInsertResponse{
		Success:       len(failedIDs) == 0,
		InsertedCount: int32(inserted),
		FailedIds:     failedIDs,
	}, nil
}

// Search finds k nearest neighbors
func (s *HNSWServer) Search(ctx context.Context, req *pb.SearchRequest) (*pb.SearchResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.index == nil {
		return &pb.SearchResponse{}, nil
	}

	startTime := time.Now()

	efSearch := int(req.EfSearch)
	if efSearch == 0 {
		efSearch = int(req.K) * 2 // Default: 2x requested results
	}

	candidates, nodesVisited := s.SearchKNN(req.QueryVector, int(req.K), efSearch)

	results := make([]*pb.SearchResult, 0, len(candidates))
	for _, c := range candidates {
		node := s.index.Nodes[c.ID]
		if node == nil {
			continue
		}

		// Apply metadata filter if specified
		if len(req.Filter) > 0 {
			match := true
			for k, v := range req.Filter {
				if node.Metadata[k] != v {
					match = false
					break
				}
			}
			if !match {
				continue
			}
		}

		results = append(results, &pb.SearchResult{
			Id:       c.ID,
			Distance: c.Distance,
			Vector:   node.Vector,
			Metadata: node.Metadata,
		})
	}

	return &pb.SearchResponse{
		Results:      results,
		SearchTimeUs: time.Since(startTime).Microseconds(),
		NodesVisited: int32(nodesVisited),
	}, nil
}

// Delete removes a vector from the index
//
// TODO: Implement deletion (optional - can mark as deleted or fully remove):
// - Mark node as deleted (soft delete) for simple implementation
// - For hard delete: remove node and repair all neighbor connections
func (s *HNSWServer) Delete(ctx context.Context, req *pb.DeleteRequest) (*pb.DeleteResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.index == nil {
		return &pb.DeleteResponse{Success: false, Error: "Index not created"}, nil
	}

	// TODO: Implement vector deletion
	return &pb.DeleteResponse{Success: false, Found: false, Error: "Not implemented"}, nil
}

// GetStats returns index statistics
func (s *HNSWServer) GetStats(ctx context.Context, req *pb.GetStatsRequest) (*pb.GetStatsResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.index == nil {
		return &pb.GetStatsResponse{Stats: &pb.IndexStats{}}, nil
	}

	return &pb.GetStatsResponse{
		Stats: &pb.IndexStats{
			TotalVectors:   int64(len(s.index.Nodes)),
			MaxLevel:       int32(s.index.MaxLevel),
			Dimension:      int32(s.index.Dimension),
			M:              int32(s.index.M),
			EfConstruction: int32(s.index.EfConstruction),
		},
	}, nil
}

// GetVector retrieves a specific vector by ID
func (s *HNSWServer) GetVector(ctx context.Context, req *pb.GetVectorRequest) (*pb.GetVectorResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.index == nil {
		return &pb.GetVectorResponse{Found: false}, nil
	}

	node, ok := s.index.Nodes[req.Id]
	if !ok {
		return &pb.GetVectorResponse{Found: false}, nil
	}

	return &pb.GetVectorResponse{
		Found: true,
		Vector: &pb.Vector{
			Id:       node.ID,
			Values:   node.Vector,
			Metadata: node.Metadata,
		},
	}, nil
}

// =============================================================================
// NodeService gRPC Implementation (Distributed Operations)
// =============================================================================

// SyncGraph synchronizes graph structure from another node
//
// TODO: Implement graph synchronization for distributed HNSW:
// - Merge incoming nodes with local graph
// - Resolve conflicts (e.g., by timestamp)
// - Update connections as needed
func (s *HNSWServer) SyncGraph(ctx context.Context, req *pb.SyncGraphRequest) (*pb.SyncGraphResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	// TODO: Implement graph synchronization
	return &pb.SyncGraphResponse{Success: false, NodesSynced: 0}, nil
}

// ForwardSearch forwards a search request to this node
//
// TODO: Implement search forwarding for distributed queries:
// - Perform local search
// - Return results to requesting node
func (s *HNSWServer) ForwardSearch(ctx context.Context, req *pb.ForwardSearchRequest) (*pb.ForwardSearchResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	// TODO: Implement search forwarding
	return &pb.ForwardSearchResponse{
		Results:  nil,
		ServedBy: s.nodeID,
	}, nil
}

// Heartbeat handles health check requests
func (s *HNSWServer) Heartbeat(ctx context.Context, req *pb.HeartbeatRequest) (*pb.HeartbeatResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	vectorCount := int64(0)
	if s.index != nil {
		vectorCount = int64(len(s.index.Nodes))
	}

	log.Printf("Heartbeat from %s: %d vectors", req.NodeId, req.VectorCount)

	return &pb.HeartbeatResponse{
		Acknowledged: true,
		Timestamp:    time.Now().UnixNano(),
	}, nil
}

// =============================================================================
// Heap Helper Functions
// =============================================================================

// NewCandidateHeap creates a new candidate heap
func NewCandidateHeap(isMaxHeap bool) *CandidateHeap {
	return &CandidateHeap{
		items:     make([]Candidate, 0),
		isMaxHeap: isMaxHeap,
	}
}

// Push adds a candidate to the heap
//
// TODO: Implement heap push operation
func (h *CandidateHeap) Push(c Candidate) {
	// TODO: Add element and bubble up to maintain heap property
}

// Pop removes and returns the top element
//
// TODO: Implement heap pop operation
func (h *CandidateHeap) Pop() Candidate {
	// TODO: Remove top, replace with last, and bubble down
	return Candidate{}
}

// Peek returns the top element without removing
func (h *CandidateHeap) Peek() Candidate {
	if len(h.items) == 0 {
		return Candidate{}
	}
	return h.items[0]
}

// Len returns the number of elements
func (h *CandidateHeap) Len() int {
	return len(h.items)
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

	server := NewHNSWServer(*nodeID, *port, peers)
	if err := server.Initialize(); err != nil {
		log.Fatalf("Failed to initialize server: %v", err)
	}

	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	grpcServer := grpc.NewServer()
	pb.RegisterHNSWServiceServer(grpcServer, server)
	pb.RegisterNodeServiceServer(grpcServer, server)

	log.Printf("Starting HNSW server %s on port %d", *nodeID, *port)
	log.Printf("HNSW Algorithm Summary:")
	log.Printf("  - Hierarchical graph with skip-list structure")
	log.Printf("  - Greedy search from top layer to bottom")
	log.Printf("  - Key params: M (connections), efConstruction (build quality)")

	if err := grpcServer.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
