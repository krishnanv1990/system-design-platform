// Leaky Bucket Rate Limiter - Go Template
//
// This template provides the basic structure for implementing a distributed
// leaky bucket rate limiter.
//
// Key concepts:
// 1. Leaky Bucket - Requests enter a queue that drains at a constant rate
// 2. Queue Size - Maximum number of pending requests
// 3. Leak Rate - Constant rate at which requests are processed
// 4. Overflow - When queue is full, new requests are rejected
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
	"google.golang.org/grpc/credentials/insecure"

	pb "github.com/sdp/leaky_bucket"
)

// BucketState holds the state of a leaky bucket
type BucketState struct {
	BucketID     string
	QueueSize    float64
	Capacity     float64
	LeakRate     float64
	LastLeakTime time.Time
	mu           sync.Mutex
}

// LeakyBucketRateLimiter implements the leaky bucket algorithm
type LeakyBucketRateLimiter struct {
	pb.UnimplementedRateLimiterServiceServer
	pb.UnimplementedNodeServiceServer

	nodeID      string
	port        int
	peers       []string
	buckets     map[string]*BucketState
	mu          sync.RWMutex
	peerClients map[string]pb.NodeServiceClient
}

// NewLeakyBucketRateLimiter creates a new rate limiter node
func NewLeakyBucketRateLimiter(nodeID string, port int, peers []string) *LeakyBucketRateLimiter {
	return &LeakyBucketRateLimiter{
		nodeID:      nodeID,
		port:        port,
		peers:       peers,
		buckets:     make(map[string]*BucketState),
		peerClients: make(map[string]pb.NodeServiceClient),
	}
}

// Initialize sets up connections to peer nodes
func (r *LeakyBucketRateLimiter) Initialize() error {
	for _, peer := range r.peers {
		conn, err := grpc.Dial(peer, grpc.WithTransportCredentials(insecure.NewCredentials()))
		if err != nil {
			log.Printf("Warning: Failed to connect to peer %s: %v", peer, err)
			continue
		}
		r.peerClients[peer] = pb.NewNodeServiceClient(conn)
	}

	log.Printf("Node %s initialized with peers: %v", r.nodeID, r.peers)
	return nil
}

// GetOrCreateBucket gets an existing bucket or creates a new one
func (r *LeakyBucketRateLimiter) GetOrCreateBucket(bucketID string, capacity, leakRate float64) *BucketState {
	r.mu.Lock()
	defer r.mu.Unlock()

	if bucket, exists := r.buckets[bucketID]; exists {
		return bucket
	}

	bucket := &BucketState{
		BucketID:     bucketID,
		QueueSize:    0,
		Capacity:     capacity,
		LeakRate:     leakRate,
		LastLeakTime: time.Now(),
	}
	r.buckets[bucketID] = bucket
	return bucket
}

// Leak drains the bucket based on elapsed time
//
// TODO: Implement leak logic:
// 1. Calculate time elapsed since last leak
// 2. Calculate how many requests have leaked: leaked = elapsed_seconds * leak_rate
// 3. Reduce queue size by leaked amount (minimum 0)
// 4. Update last leak time
func (r *LeakyBucketRateLimiter) Leak(bucket *BucketState) {
	// TODO: Implement this method
}

// TryEnqueue attempts to add a request to the queue
//
// TODO: Implement enqueue logic:
// 1. First leak the bucket based on elapsed time
// 2. Check if queue has space (queue_size < capacity)
// 3. If yes, increment queue size and return true
// 4. If no, return false (request should be rejected)
func (r *LeakyBucketRateLimiter) TryEnqueue(bucket *BucketState, count float64) bool {
	// TODO: Implement this method
	return false
}

// =============================================================================
// RateLimiterService RPC Implementations
// =============================================================================

func (r *LeakyBucketRateLimiter) CreateBucket(ctx context.Context, req *pb.CreateBucketRequest) (*pb.CreateBucketResponse, error) {
	bucket := r.GetOrCreateBucket(req.BucketId, req.Config.Capacity, req.Config.LeakRate)

	return &pb.CreateBucketResponse{
		Success: true,
		State: &pb.BucketState{
			BucketId:     bucket.BucketID,
			QueueSize:    bucket.QueueSize,
			Capacity:     bucket.Capacity,
			LeakRate:     bucket.LeakRate,
			LastLeakTime: uint64(bucket.LastLeakTime.UnixMilli()),
		},
	}, nil
}

func (r *LeakyBucketRateLimiter) AllowRequest(ctx context.Context, req *pb.AllowRequestRequest) (*pb.AllowRequestResponse, error) {
	r.mu.RLock()
	bucket, exists := r.buckets[req.BucketId]
	r.mu.RUnlock()

	if !exists {
		return &pb.AllowRequestResponse{
			Allowed: false,
			Error:   "Bucket not found",
		}, nil
	}

	count := req.Count
	if count == 0 {
		count = 1
	}

	allowed := r.TryEnqueue(bucket, count)

	bucket.mu.Lock()
	queueSize := bucket.QueueSize
	capacity := bucket.Capacity
	bucket.mu.Unlock()

	return &pb.AllowRequestResponse{
		Allowed:        allowed,
		CurrentQueue:   queueSize,
		RemainingSpace: capacity - queueSize,
	}, nil
}

func (r *LeakyBucketRateLimiter) GetBucketState(ctx context.Context, req *pb.GetBucketStateRequest) (*pb.GetBucketStateResponse, error) {
	r.mu.RLock()
	bucket, exists := r.buckets[req.BucketId]
	r.mu.RUnlock()

	if !exists {
		return &pb.GetBucketStateResponse{}, nil
	}

	r.Leak(bucket)

	bucket.mu.Lock()
	state := &pb.BucketState{
		BucketId:     bucket.BucketID,
		QueueSize:    bucket.QueueSize,
		Capacity:     bucket.Capacity,
		LeakRate:     bucket.LeakRate,
		LastLeakTime: uint64(bucket.LastLeakTime.UnixMilli()),
	}
	bucket.mu.Unlock()

	return &pb.GetBucketStateResponse{
		State: state,
	}, nil
}

func (r *LeakyBucketRateLimiter) DeleteBucket(ctx context.Context, req *pb.DeleteBucketRequest) (*pb.DeleteBucketResponse, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.buckets[req.BucketId]; exists {
		delete(r.buckets, req.BucketId)
		return &pb.DeleteBucketResponse{Success: true}, nil
	}

	return &pb.DeleteBucketResponse{
		Success: false,
		Error:   "Bucket not found",
	}, nil
}

// =============================================================================
// NodeService RPC Implementations
// =============================================================================

func (r *LeakyBucketRateLimiter) SyncState(ctx context.Context, req *pb.SyncStateRequest) (*pb.SyncStateResponse, error) {
	for _, state := range req.States {
		r.mu.Lock()
		if bucket, exists := r.buckets[state.BucketId]; exists {
			bucket.mu.Lock()
			// Use state with higher queue size (more conservative)
			if state.QueueSize > bucket.QueueSize {
				bucket.QueueSize = state.QueueSize
			}
			bucket.mu.Unlock()
		} else {
			r.buckets[state.BucketId] = &BucketState{
				BucketID:     state.BucketId,
				QueueSize:    state.QueueSize,
				Capacity:     state.Capacity,
				LeakRate:     state.LeakRate,
				LastLeakTime: time.UnixMilli(int64(state.LastLeakTime)),
			}
		}
		r.mu.Unlock()
	}

	return &pb.SyncStateResponse{
		Success: true,
		NodeId:  r.nodeID,
	}, nil
}

func (r *LeakyBucketRateLimiter) Heartbeat(ctx context.Context, req *pb.HeartbeatRequest) (*pb.HeartbeatResponse, error) {
	return &pb.HeartbeatResponse{
		Acknowledged: true,
		Timestamp:    uint64(time.Now().UnixMilli()),
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

	limiter := NewLeakyBucketRateLimiter(*nodeID, *port, peers)
	if err := limiter.Initialize(); err != nil {
		log.Fatalf("Failed to initialize node: %v", err)
	}

	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	server := grpc.NewServer()
	pb.RegisterRateLimiterServiceServer(server, limiter)
	pb.RegisterNodeServiceServer(server, limiter)

	log.Printf("Starting Leaky Bucket Rate Limiter node %s on port %d", *nodeID, *port)

	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
