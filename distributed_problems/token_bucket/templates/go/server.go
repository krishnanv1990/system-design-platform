// Token Bucket Rate Limiter - Go Template
//
// This template provides the basic structure for implementing a distributed
// token bucket rate limiter.
//
// Key concepts:
// 1. Token Bucket - Requests consume tokens; tokens refill at a fixed rate
// 2. Burst Capacity - Maximum tokens that can accumulate
// 3. Refill Rate - How quickly tokens are replenished
// 4. Distributed Coordination - Share state across nodes
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

	pb "github.com/sdp/token_bucket"
)

// BucketState holds the state of a token bucket
type BucketState struct {
	BucketID       string
	Tokens         float64
	Capacity       float64
	RefillRate     float64
	LastRefillTime time.Time
	mu             sync.Mutex
}

// TokenBucketRateLimiter implements the token bucket algorithm
type TokenBucketRateLimiter struct {
	pb.UnimplementedRateLimiterServiceServer
	pb.UnimplementedNodeServiceServer

	nodeID      string
	port        int
	peers       []string
	buckets     map[string]*BucketState
	mu          sync.RWMutex
	peerClients map[string]pb.NodeServiceClient
}

// NewTokenBucketRateLimiter creates a new rate limiter node
func NewTokenBucketRateLimiter(nodeID string, port int, peers []string) *TokenBucketRateLimiter {
	return &TokenBucketRateLimiter{
		nodeID:      nodeID,
		port:        port,
		peers:       peers,
		buckets:     make(map[string]*BucketState),
		peerClients: make(map[string]pb.NodeServiceClient),
	}
}

// Initialize sets up connections to peer nodes
func (r *TokenBucketRateLimiter) Initialize() error {
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
func (r *TokenBucketRateLimiter) GetOrCreateBucket(bucketID string, capacity, refillRate float64) *BucketState {
	r.mu.Lock()
	defer r.mu.Unlock()

	if bucket, exists := r.buckets[bucketID]; exists {
		return bucket
	}

	bucket := &BucketState{
		BucketID:       bucketID,
		Tokens:         capacity,
		Capacity:       capacity,
		RefillRate:     refillRate,
		LastRefillTime: time.Now(),
	}
	r.buckets[bucketID] = bucket
	return bucket
}

// RefillTokens adds tokens based on elapsed time
//
// TODO: Implement token refill logic:
// 1. Calculate time elapsed since last refill
// 2. Add tokens based on refill rate: tokens += elapsed_seconds * refill_rate
// 3. Cap tokens at capacity
// 4. Update last refill time
func (r *TokenBucketRateLimiter) RefillTokens(bucket *BucketState) {
	bucket.mu.Lock()
	defer bucket.mu.Unlock()

	now := time.Now()
	elapsed := now.Sub(bucket.LastRefillTime).Seconds()

	// TODO: Calculate tokens to add based on elapsed time and refill rate
	tokensToAdd := elapsed * bucket.RefillRate

	// TODO: Add tokens but don't exceed capacity
	bucket.Tokens = min(bucket.Tokens+tokensToAdd, bucket.Capacity)

	bucket.LastRefillTime = now
}

// TryConsume attempts to consume tokens from the bucket
//
// TODO: Implement token consumption:
// 1. First refill tokens based on elapsed time
// 2. Check if enough tokens are available
// 3. If yes, deduct tokens and return true
// 4. If no, return false (request should be rate limited)
func (r *TokenBucketRateLimiter) TryConsume(bucket *BucketState, tokens float64) bool {
	r.RefillTokens(bucket)

	bucket.mu.Lock()
	defer bucket.mu.Unlock()

	// TODO: Check if enough tokens and consume
	if bucket.Tokens >= tokens {
		bucket.Tokens -= tokens
		return true
	}
	return false
}

// =============================================================================
// RateLimiterService RPC Implementations
// =============================================================================

func (r *TokenBucketRateLimiter) CreateBucket(ctx context.Context, req *pb.CreateBucketRequest) (*pb.CreateBucketResponse, error) {
	bucket := r.GetOrCreateBucket(req.BucketId, req.Config.Capacity, req.Config.RefillRate)

	return &pb.CreateBucketResponse{
		Success: true,
		State: &pb.BucketState{
			BucketId:       bucket.BucketID,
			CurrentTokens:  bucket.Tokens,
			Capacity:       bucket.Capacity,
			RefillRate:     bucket.RefillRate,
			LastRefillTime: uint64(bucket.LastRefillTime.UnixMilli()),
		},
	}, nil
}

func (r *TokenBucketRateLimiter) AllowRequest(ctx context.Context, req *pb.AllowRequestRequest) (*pb.AllowRequestResponse, error) {
	r.mu.RLock()
	bucket, exists := r.buckets[req.BucketId]
	r.mu.RUnlock()

	if !exists {
		return &pb.AllowRequestResponse{
			Allowed: false,
			Error:   "Bucket not found",
		}, nil
	}

	tokens := req.TokensRequested
	if tokens == 0 {
		tokens = 1
	}

	allowed := r.TryConsume(bucket, tokens)

	bucket.mu.Lock()
	remaining := bucket.Tokens
	bucket.mu.Unlock()

	return &pb.AllowRequestResponse{
		Allowed:         allowed,
		RemainingTokens: remaining,
	}, nil
}

func (r *TokenBucketRateLimiter) GetBucketState(ctx context.Context, req *pb.GetBucketStateRequest) (*pb.GetBucketStateResponse, error) {
	r.mu.RLock()
	bucket, exists := r.buckets[req.BucketId]
	r.mu.RUnlock()

	if !exists {
		return &pb.GetBucketStateResponse{}, nil
	}

	r.RefillTokens(bucket)

	bucket.mu.Lock()
	state := &pb.BucketState{
		BucketId:       bucket.BucketID,
		CurrentTokens:  bucket.Tokens,
		Capacity:       bucket.Capacity,
		RefillRate:     bucket.RefillRate,
		LastRefillTime: uint64(bucket.LastRefillTime.UnixMilli()),
	}
	bucket.mu.Unlock()

	return &pb.GetBucketStateResponse{
		State: state,
	}, nil
}

func (r *TokenBucketRateLimiter) DeleteBucket(ctx context.Context, req *pb.DeleteBucketRequest) (*pb.DeleteBucketResponse, error) {
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

func (r *TokenBucketRateLimiter) SyncState(ctx context.Context, req *pb.SyncStateRequest) (*pb.SyncStateResponse, error) {
	for _, state := range req.States {
		r.mu.Lock()
		if bucket, exists := r.buckets[state.BucketId]; exists {
			bucket.mu.Lock()
			// Use state with lower token count (more conservative)
			if state.CurrentTokens < bucket.Tokens {
				bucket.Tokens = state.CurrentTokens
			}
			bucket.mu.Unlock()
		} else {
			r.buckets[state.BucketId] = &BucketState{
				BucketID:       state.BucketId,
				Tokens:         state.CurrentTokens,
				Capacity:       state.Capacity,
				RefillRate:     state.RefillRate,
				LastRefillTime: time.UnixMilli(int64(state.LastRefillTime)),
			}
		}
		r.mu.Unlock()
	}

	return &pb.SyncStateResponse{
		Success: true,
		NodeId:  r.nodeID,
	}, nil
}

func (r *TokenBucketRateLimiter) Heartbeat(ctx context.Context, req *pb.HeartbeatRequest) (*pb.HeartbeatResponse, error) {
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

	limiter := NewTokenBucketRateLimiter(*nodeID, *port, peers)
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

	log.Printf("Starting Token Bucket Rate Limiter node %s on port %d", *nodeID, *port)

	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
