// Inverted File Index (IVF) for Vector Search - Go Template
//
// This template provides the structure for implementing a distributed IVF index
// for approximate nearest neighbor search. IVF is a clustering-based index that:
// - Partitions the vector space using k-means clustering
// - Assigns each vector to its nearest centroid (cluster)
// - Maintains inverted lists: centroid -> list of vectors in that cluster
// - Searches only the most promising clusters (controlled by nprobe)
//
// Key Algorithm Steps:
// 1. TRAIN: Run k-means on sample vectors to learn cluster centroids
// 2. ADD: Assign each vector to nearest centroid, store in inverted list
// 3. SEARCH: Find nearest centroids, search within those clusters only
//
// Key Parameters:
// - nClusters (nlist): Number of clusters/centroids (typically sqrt(n) to 4*sqrt(n))
// - nProbe: Number of clusters to search (trade-off accuracy vs speed)
//
// Complexity Analysis:
// - Training: O(n * k * iterations) where k = nClusters
// - Add: O(k) to find nearest centroid
// - Search: O(nProbe * n/k + k) - search within selected clusters
//
// Reference: https://www.pinecone.io/learn/vector-indexes/
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

	pb "github.com/sdp/ivf"
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

// Centroid represents a cluster center learned during training
type Centroid struct {
	ID          int       `json:"id"`
	Values      []float32 `json:"values"`
	VectorCount int64     `json:"vector_count"` // Number of vectors assigned to this cluster
}

// StoredVector represents a vector stored in an inverted list
type StoredVector struct {
	ID       string            `json:"id"`
	Values   []float32         `json:"values"`
	Metadata map[string]string `json:"metadata,omitempty"`
}

// InvertedList contains all vectors assigned to a particular centroid
type InvertedList struct {
	ClusterID int             `json:"cluster_id"`
	Vectors   []StoredVector  `json:"vectors"`
}

// SearchCandidate represents a candidate during search
type SearchCandidate struct {
	ID        string
	ClusterID int
	Distance  float32
}

// IVFIndex is the main index structure
type IVFIndex struct {
	Dimension    int                     `json:"dimension"`
	NClusters    int                     `json:"n_clusters"`
	DistanceType DistanceType            `json:"distance_type"`
	IsTrained    bool                    `json:"is_trained"`

	Centroids    []Centroid              `json:"centroids"`
	Lists        map[int]*InvertedList   `json:"lists"`        // ClusterID -> InvertedList
	VectorToCluster map[string]int       `json:"vector_to_cluster"` // VectorID -> ClusterID

	// Training statistics
	Inertia      float32                 `json:"inertia"`       // Sum of squared distances to centroids
}

// =============================================================================
// IVF Server Implementation
// =============================================================================

// IVFServer implements both IVFService and NodeService
type IVFServer struct {
	pb.UnimplementedIVFServiceServer
	pb.UnimplementedNodeServiceServer

	nodeID      string
	port        int
	peers       []string
	index       *IVFIndex

	mu          sync.RWMutex
	peerClients map[string]pb.NodeServiceClient

	// Distributed cluster ownership (which clusters this node is responsible for)
	ownedClusters map[int]bool
}

// NewIVFServer creates a new IVF server instance
func NewIVFServer(nodeID string, port int, peers []string) *IVFServer {
	return &IVFServer{
		nodeID:        nodeID,
		port:          port,
		peers:         peers,
		peerClients:   make(map[string]pb.NodeServiceClient),
		ownedClusters: make(map[int]bool),
	}
}

// Initialize sets up connections to peer nodes for distributed operation
func (s *IVFServer) Initialize() error {
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

// ComputeDistance calculates distance between two vectors
//
// TODO: Implement distance computation for each metric type:
// - Euclidean: sqrt(sum((a[i] - b[i])^2))
// - Cosine: 1 - (dot(a,b) / (norm(a) * norm(b)))
// - InnerProduct: -dot(a,b)
func (s *IVFServer) ComputeDistance(a, b []float32) float32 {
	// TODO: Implement distance computation based on s.index.DistanceType
	return 0.0
}

// =============================================================================
// Core IVF Algorithm Functions
// =============================================================================

// TrainKMeans trains k-means clustering on the provided vectors
// This is the key training step that determines cluster centroids
//
// TODO: Implement k-means clustering (Lloyd's algorithm):
// 1. Initialize centroids:
//    - Option A: Random initialization - pick k random vectors as initial centroids
//    - Option B: k-means++ - smarter initialization for better convergence
// 2. Repeat for nIterations:
//    a. Assignment step: Assign each vector to nearest centroid
//    b. Update step: Recalculate centroid as mean of assigned vectors
//    c. Check for convergence (centroids stopped moving significantly)
// 3. Calculate inertia (sum of squared distances to assigned centroids)
// 4. Set s.index.Centroids and mark index as trained
//
// k-means++ initialization (recommended):
// - Choose first centroid uniformly at random
// - For each subsequent centroid:
//   - Compute D(x) = distance from x to nearest existing centroid
//   - Choose new centroid with probability proportional to D(x)^2
func (s *IVFServer) TrainKMeans(vectors []StoredVector, nIterations int) (float32, error) {
	// TODO: Implement k-means training
	return 0.0, nil
}

// AssignToCluster finds the nearest centroid for a vector
//
// TODO: Implement cluster assignment:
// 1. Compute distance from vector to each centroid
// 2. Return the index of the closest centroid
// 3. This is O(k) where k = number of clusters
func (s *IVFServer) AssignToCluster(vector []float32) int {
	// TODO: Find nearest centroid for the given vector
	return 0
}

// FindNearestCentroids finds the nProbe closest centroids to a query
//
// TODO: Implement centroid search:
// 1. Compute distance from query to all centroids
// 2. Return indices of nProbe closest centroids
// 3. Can use partial sort or heap for efficiency when nProbe << nClusters
func (s *IVFServer) FindNearestCentroids(query []float32, nProbe int) []int {
	// TODO: Return indices of nProbe nearest centroids
	return nil
}

// SearchCluster searches within a single cluster for nearest neighbors
//
// TODO: Implement intra-cluster search:
// 1. Get all vectors in the specified cluster from inverted list
// 2. Compute distance from query to each vector
// 3. Return top-k candidates (or all if fewer than k)
// 4. Apply metadata filter if specified
func (s *IVFServer) SearchCluster(query []float32, clusterID int, k int, filter map[string]string) []SearchCandidate {
	// TODO: Search within a single cluster's inverted list
	return nil
}

// SearchIVF performs IVF search across multiple clusters
//
// TODO: Implement full IVF search:
// 1. Find nProbe nearest centroids using FindNearestCentroids
// 2. For each selected cluster:
//    - Search within cluster using SearchCluster
//    - Collect all candidates
// 3. Merge results from all clusters
// 4. Sort by distance and return top k
//
// Optimization: Can search clusters in parallel for better latency
func (s *IVFServer) SearchIVF(query []float32, k int, nProbe int, filter map[string]string) ([]SearchCandidate, []int) {
	// TODO: Implement multi-cluster IVF search
	return nil, nil
}

// =============================================================================
// IVFService gRPC Implementation
// =============================================================================

// CreateIndex creates a new IVF index with specified parameters
func (s *IVFServer) CreateIndex(ctx context.Context, req *pb.CreateIndexRequest) (*pb.CreateIndexResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	distType := Euclidean
	switch req.DistanceType {
	case "cosine":
		distType = Cosine
	case "inner_product":
		distType = InnerProduct
	}

	s.index = &IVFIndex{
		Dimension:       int(req.Dimension),
		NClusters:       int(req.NClusters),
		DistanceType:    distType,
		IsTrained:       false,
		Centroids:       make([]Centroid, 0),
		Lists:           make(map[int]*InvertedList),
		VectorToCluster: make(map[string]int),
	}

	// Initialize empty inverted lists
	for i := 0; i < int(req.NClusters); i++ {
		s.index.Lists[i] = &InvertedList{
			ClusterID: i,
			Vectors:   make([]StoredVector, 0),
		}
	}

	log.Printf("Created IVF index: dim=%d, nClusters=%d", req.Dimension, req.NClusters)

	return &pb.CreateIndexResponse{
		Success: true,
		IndexId: fmt.Sprintf("ivf-%s-%d", s.nodeID, time.Now().UnixNano()),
	}, nil
}

// Train trains the index on a set of vectors
func (s *IVFServer) Train(ctx context.Context, req *pb.TrainRequest) (*pb.TrainResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.index == nil {
		return &pb.TrainResponse{Success: false, Error: "Index not created"}, nil
	}

	if len(req.TrainingVectors) < s.index.NClusters {
		return &pb.TrainResponse{
			Success: false,
			Error:   fmt.Sprintf("Need at least %d training vectors, got %d", s.index.NClusters, len(req.TrainingVectors)),
		}, nil
	}

	// Convert proto vectors to internal format
	vectors := make([]StoredVector, len(req.TrainingVectors))
	for i, v := range req.TrainingVectors {
		vectors[i] = StoredVector{
			ID:       v.Id,
			Values:   v.Values,
			Metadata: v.Metadata,
		}
	}

	nIterations := int(req.NIterations)
	if nIterations == 0 {
		nIterations = 25 // Default iterations
	}

	inertia, err := s.TrainKMeans(vectors, nIterations)
	if err != nil {
		return &pb.TrainResponse{Success: false, Error: err.Error()}, nil
	}

	s.index.IsTrained = true

	return &pb.TrainResponse{
		Success:   true,
		NClusters: int32(s.index.NClusters),
		Inertia:   inertia,
	}, nil
}

// Add adds a vector to the index
func (s *IVFServer) Add(ctx context.Context, req *pb.AddRequest) (*pb.AddResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.index == nil {
		return &pb.AddResponse{Success: false, Error: "Index not created"}, nil
	}

	if !s.index.IsTrained {
		return &pb.AddResponse{Success: false, Error: "Index not trained"}, nil
	}

	if len(req.Vector) != s.index.Dimension {
		return &pb.AddResponse{
			Success: false,
			Error:   fmt.Sprintf("Vector dimension mismatch: expected %d, got %d", s.index.Dimension, len(req.Vector)),
		}, nil
	}

	// Assign vector to nearest cluster
	clusterID := s.AssignToCluster(req.Vector)

	// Add to inverted list
	vec := StoredVector{
		ID:       req.Id,
		Values:   req.Vector,
		Metadata: req.Metadata,
	}

	if s.index.Lists[clusterID] == nil {
		s.index.Lists[clusterID] = &InvertedList{
			ClusterID: clusterID,
			Vectors:   make([]StoredVector, 0),
		}
	}

	s.index.Lists[clusterID].Vectors = append(s.index.Lists[clusterID].Vectors, vec)
	s.index.VectorToCluster[req.Id] = clusterID
	s.index.Centroids[clusterID].VectorCount++

	return &pb.AddResponse{
		Success:         true,
		AssignedCluster: int32(clusterID),
	}, nil
}

// BatchAdd adds multiple vectors
func (s *IVFServer) BatchAdd(ctx context.Context, req *pb.BatchAddRequest) (*pb.BatchAddResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.index == nil {
		return &pb.BatchAddResponse{Success: false, Error: "Index not created"}, nil
	}

	if !s.index.IsTrained {
		return &pb.BatchAddResponse{Success: false, Error: "Index not trained"}, nil
	}

	added := 0
	var failedIDs []string

	for _, v := range req.Vectors {
		if len(v.Values) != s.index.Dimension {
			failedIDs = append(failedIDs, v.Id)
			continue
		}

		clusterID := s.AssignToCluster(v.Values)

		vec := StoredVector{
			ID:       v.Id,
			Values:   v.Values,
			Metadata: v.Metadata,
		}

		s.index.Lists[clusterID].Vectors = append(s.index.Lists[clusterID].Vectors, vec)
		s.index.VectorToCluster[v.Id] = clusterID
		s.index.Centroids[clusterID].VectorCount++
		added++
	}

	return &pb.BatchAddResponse{
		Success:    len(failedIDs) == 0,
		AddedCount: int32(added),
		FailedIds:  failedIDs,
	}, nil
}

// Search finds k nearest neighbors
func (s *IVFServer) Search(ctx context.Context, req *pb.SearchRequest) (*pb.SearchResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.index == nil || !s.index.IsTrained {
		return &pb.SearchResponse{}, nil
	}

	startTime := time.Now()

	nProbe := int(req.NProbe)
	if nProbe == 0 {
		nProbe = 1 // Default: search only nearest cluster
	}
	if nProbe > s.index.NClusters {
		nProbe = s.index.NClusters
	}

	candidates, clustersSearched := s.SearchIVF(req.QueryVector, int(req.K), nProbe, req.Filter)

	results := make([]*pb.SearchResult, 0, len(candidates))
	for _, c := range candidates {
		results = append(results, &pb.SearchResult{
			Id:        c.ID,
			Distance:  c.Distance,
			ClusterId: int32(c.ClusterID),
		})
	}

	// Convert cluster IDs to int32
	clustersInt32 := make([]int32, len(clustersSearched))
	for i, c := range clustersSearched {
		clustersInt32[i] = int32(c)
	}

	return &pb.SearchResponse{
		Results:          results,
		SearchTimeUs:     time.Since(startTime).Microseconds(),
		ClustersSearched: clustersInt32,
	}, nil
}

// Remove removes a vector from the index
//
// TODO: Implement vector removal:
// - Find which cluster the vector belongs to
// - Remove from inverted list
// - Update centroid count
func (s *IVFServer) Remove(ctx context.Context, req *pb.RemoveRequest) (*pb.RemoveResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	// TODO: Implement vector removal
	return &pb.RemoveResponse{Success: false, Found: false, Error: "Not implemented"}, nil
}

// GetStats returns index statistics
func (s *IVFServer) GetStats(ctx context.Context, req *pb.GetStatsRequest) (*pb.GetStatsResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.index == nil {
		return &pb.GetStatsResponse{Stats: &pb.IndexStats{}}, nil
	}

	// Calculate total vectors and cluster sizes
	totalVectors := int64(0)
	clusterSizes := make([]int64, len(s.index.Centroids))
	for i, c := range s.index.Centroids {
		clusterSizes[i] = c.VectorCount
		totalVectors += c.VectorCount
	}

	return &pb.GetStatsResponse{
		Stats: &pb.IndexStats{
			TotalVectors: totalVectors,
			NClusters:    int32(s.index.NClusters),
			Dimension:    int32(s.index.Dimension),
			IsTrained:    s.index.IsTrained,
			ClusterSizes: clusterSizes,
		},
	}, nil
}

// GetCentroids returns all cluster centroids
func (s *IVFServer) GetCentroids(ctx context.Context, req *pb.GetCentroidsRequest) (*pb.GetCentroidsResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.index == nil {
		return &pb.GetCentroidsResponse{}, nil
	}

	centroids := make([]*pb.Centroid, len(s.index.Centroids))
	for i, c := range s.index.Centroids {
		centroids[i] = &pb.Centroid{
			ClusterId:   int32(c.ID),
			Values:      c.Values,
			VectorCount: c.VectorCount,
		}
	}

	return &pb.GetCentroidsResponse{Centroids: centroids}, nil
}

// GetClusterVectors returns vectors in a specific cluster
func (s *IVFServer) GetClusterVectors(ctx context.Context, req *pb.GetClusterVectorsRequest) (*pb.GetClusterVectorsResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.index == nil {
		return &pb.GetClusterVectorsResponse{}, nil
	}

	list, ok := s.index.Lists[int(req.ClusterId)]
	if !ok {
		return &pb.GetClusterVectorsResponse{}, nil
	}

	// Apply offset and limit
	start := int(req.Offset)
	if start >= len(list.Vectors) {
		return &pb.GetClusterVectorsResponse{TotalInCluster: int32(len(list.Vectors))}, nil
	}

	end := len(list.Vectors)
	if req.Limit > 0 && start+int(req.Limit) < end {
		end = start + int(req.Limit)
	}

	vectors := make([]*pb.Vector, end-start)
	for i := start; i < end; i++ {
		v := list.Vectors[i]
		vectors[i-start] = &pb.Vector{
			Id:       v.ID,
			Values:   v.Values,
			Metadata: v.Metadata,
		}
	}

	return &pb.GetClusterVectorsResponse{
		Vectors:        vectors,
		TotalInCluster: int32(len(list.Vectors)),
	}, nil
}

// =============================================================================
// NodeService gRPC Implementation (Distributed Operations)
// =============================================================================

// SyncCentroids synchronizes centroids from another node
//
// TODO: Implement centroid synchronization for distributed IVF:
// - Update local centroids with incoming data
// - Handle version conflicts
func (s *IVFServer) SyncCentroids(ctx context.Context, req *pb.SyncCentroidsRequest) (*pb.SyncCentroidsResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	// TODO: Implement centroid synchronization
	return &pb.SyncCentroidsResponse{Success: false, CentroidsSynced: 0}, nil
}

// ForwardSearch forwards a search request to this node for specific clusters
//
// TODO: Implement search forwarding for distributed queries:
// - Search only within target clusters
// - Return partial results
func (s *IVFServer) ForwardSearch(ctx context.Context, req *pb.ForwardSearchRequest) (*pb.ForwardSearchResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	// TODO: Search within target clusters and return results
	return &pb.ForwardSearchResponse{
		Results:  nil,
		ServedBy: s.nodeID,
	}, nil
}

// TransferVectors handles vector transfer during rebalancing
//
// TODO: Implement vector transfer for cluster rebalancing:
// - Receive vectors from another node
// - Add to local inverted lists
func (s *IVFServer) TransferVectors(ctx context.Context, req *pb.TransferVectorsRequest) (*pb.TransferVectorsResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	// TODO: Implement vector transfer
	return &pb.TransferVectorsResponse{Success: false, TransferredCount: 0}, nil
}

// Heartbeat handles health check requests
func (s *IVFServer) Heartbeat(ctx context.Context, req *pb.HeartbeatRequest) (*pb.HeartbeatResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	log.Printf("Heartbeat from %s: %d vectors, owns clusters %v",
		req.NodeId, req.VectorCount, req.OwnedClusters)

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

	server := NewIVFServer(*nodeID, *port, peers)
	if err := server.Initialize(); err != nil {
		log.Fatalf("Failed to initialize server: %v", err)
	}

	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	grpcServer := grpc.NewServer()
	pb.RegisterIVFServiceServer(grpcServer, server)
	pb.RegisterNodeServiceServer(grpcServer, server)

	log.Printf("Starting IVF server %s on port %d", *nodeID, *port)
	log.Printf("IVF Algorithm Summary:")
	log.Printf("  - Partition vectors into clusters via k-means")
	log.Printf("  - Search only nearest clusters (nProbe parameter)")
	log.Printf("  - Trade-off: more clusters = faster search, less accuracy")

	if err := grpcServer.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
