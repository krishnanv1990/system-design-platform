// Sliding Window Log Rate Limiter - Go Template
//
// This template provides the basic structure for implementing a distributed
// sliding window log rate limiter.
//
// Key concepts:
// 1. Timestamp Log - Keep a log of request timestamps
// 2. Sliding Window - Window slides with current time
// 3. Precise Counting - Count requests in the sliding window
// 4. Memory Usage - Need to clean up old timestamps
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
	"sort"
	"strings"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	pb "github.com/sdp/sliding_window_log"
)

// WindowState holds the state of a sliding window log
type WindowState struct {
	CounterID    string
	Timestamps   []int64 // Timestamps in milliseconds
	WindowSizeMs uint64
	RequestLimit uint64
	mu           sync.Mutex
}

// SlidingWindowLogRateLimiter implements the sliding window log algorithm
type SlidingWindowLogRateLimiter struct {
	pb.UnimplementedRateLimiterServiceServer
	pb.UnimplementedNodeServiceServer

	nodeID      string
	port        int
	peers       []string
	counters    map[string]*WindowState
	mu          sync.RWMutex
	peerClients map[string]pb.NodeServiceClient
}

// NewSlidingWindowLogRateLimiter creates a new rate limiter node
func NewSlidingWindowLogRateLimiter(nodeID string, port int, peers []string) *SlidingWindowLogRateLimiter {
	return &SlidingWindowLogRateLimiter{
		nodeID:      nodeID,
		port:        port,
		peers:       peers,
		counters:    make(map[string]*WindowState),
		peerClients: make(map[string]pb.NodeServiceClient),
	}
}

// Initialize sets up connections to peer nodes
func (r *SlidingWindowLogRateLimiter) Initialize() error {
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

// GetOrCreateCounter gets an existing counter or creates a new one
func (r *SlidingWindowLogRateLimiter) GetOrCreateCounter(counterID string, windowSizeMs, requestLimit uint64) *WindowState {
	r.mu.Lock()
	defer r.mu.Unlock()

	if counter, exists := r.counters[counterID]; exists {
		return counter
	}

	counter := &WindowState{
		CounterID:    counterID,
		Timestamps:   make([]int64, 0),
		WindowSizeMs: windowSizeMs,
		RequestLimit: requestLimit,
	}
	r.counters[counterID] = counter
	return counter
}

// CleanupOldTimestamps removes timestamps outside the sliding window
//
// TODO: Implement cleanup logic:
// 1. Calculate the window start (current_time - window_size)
// 2. Remove all timestamps before window start
// 3. Maintain sorted order for efficient cleanup
func (r *SlidingWindowLogRateLimiter) CleanupOldTimestamps(counter *WindowState) {
	counter.mu.Lock()
	defer counter.mu.Unlock()

	now := time.Now().UnixMilli()
	windowStart := now - int64(counter.WindowSizeMs)

	// TODO: Find first timestamp within the window using binary search
	idx := sort.Search(len(counter.Timestamps), func(i int) bool {
		return counter.Timestamps[i] >= windowStart
	})

	// TODO: Remove old timestamps
	if idx > 0 {
		counter.Timestamps = counter.Timestamps[idx:]
	}
}

// CountRequestsInWindow counts requests in the current sliding window
//
// TODO: Implement counting logic:
// 1. First cleanup old timestamps
// 2. Return the count of remaining timestamps
func (r *SlidingWindowLogRateLimiter) CountRequestsInWindow(counter *WindowState) uint64 {
	r.CleanupOldTimestamps(counter)

	counter.mu.Lock()
	defer counter.mu.Unlock()

	return uint64(len(counter.Timestamps))
}

// TryRecord attempts to record a request
//
// TODO: Implement recording logic:
// 1. Cleanup old timestamps
// 2. Check if adding new request would exceed limit
// 3. If within limit, add current timestamp and return true
// 4. If would exceed, return false
func (r *SlidingWindowLogRateLimiter) TryRecord(counter *WindowState, count uint64) bool {
	r.CleanupOldTimestamps(counter)

	counter.mu.Lock()
	defer counter.mu.Unlock()

	// TODO: Check if requests would exceed limit
	if uint64(len(counter.Timestamps))+count > counter.RequestLimit {
		return false
	}

	// TODO: Record new timestamps
	now := time.Now().UnixMilli()
	for i := uint64(0); i < count; i++ {
		counter.Timestamps = append(counter.Timestamps, now)
	}

	return true
}

// =============================================================================
// RateLimiterService RPC Implementations
// =============================================================================

func (r *SlidingWindowLogRateLimiter) CreateCounter(ctx context.Context, req *pb.CreateCounterRequest) (*pb.CreateCounterResponse, error) {
	counter := r.GetOrCreateCounter(req.CounterId, req.Config.WindowSizeMs, req.Config.RequestLimit)

	counter.mu.Lock()
	timestamps := make([]uint64, len(counter.Timestamps))
	for i, ts := range counter.Timestamps {
		timestamps[i] = uint64(ts)
	}
	counter.mu.Unlock()

	return &pb.CreateCounterResponse{
		Success: true,
		State: &pb.WindowState{
			CounterId:    counter.CounterID,
			Timestamps:   timestamps,
			WindowSizeMs: counter.WindowSizeMs,
			RequestLimit: counter.RequestLimit,
		},
	}, nil
}

func (r *SlidingWindowLogRateLimiter) AllowRequest(ctx context.Context, req *pb.AllowRequestRequest) (*pb.AllowRequestResponse, error) {
	r.mu.RLock()
	counter, exists := r.counters[req.CounterId]
	r.mu.RUnlock()

	if !exists {
		return &pb.AllowRequestResponse{
			Allowed: false,
			Error:   "Counter not found",
		}, nil
	}

	count := req.Count
	if count == 0 {
		count = 1
	}

	allowed := r.TryRecord(counter, count)

	currentCount := r.CountRequestsInWindow(counter)

	counter.mu.Lock()
	limit := counter.RequestLimit
	var oldestTs int64
	if len(counter.Timestamps) > 0 {
		oldestTs = counter.Timestamps[0]
	}
	counter.mu.Unlock()

	retryAfter := uint64(0)
	if !allowed && oldestTs > 0 {
		// Calculate when oldest request will expire
		retryAfter = uint64(oldestTs + int64(counter.WindowSizeMs) - time.Now().UnixMilli())
	}

	return &pb.AllowRequestResponse{
		Allowed:        allowed,
		CurrentCount:   currentCount,
		RemainingCount: limit - currentCount,
		RetryAfterMs:   retryAfter,
	}, nil
}

func (r *SlidingWindowLogRateLimiter) GetCounterState(ctx context.Context, req *pb.GetCounterStateRequest) (*pb.GetCounterStateResponse, error) {
	r.mu.RLock()
	counter, exists := r.counters[req.CounterId]
	r.mu.RUnlock()

	if !exists {
		return &pb.GetCounterStateResponse{}, nil
	}

	r.CleanupOldTimestamps(counter)

	counter.mu.Lock()
	timestamps := make([]uint64, len(counter.Timestamps))
	for i, ts := range counter.Timestamps {
		timestamps[i] = uint64(ts)
	}
	state := &pb.WindowState{
		CounterId:    counter.CounterID,
		Timestamps:   timestamps,
		WindowSizeMs: counter.WindowSizeMs,
		RequestLimit: counter.RequestLimit,
	}
	counter.mu.Unlock()

	return &pb.GetCounterStateResponse{
		State: state,
	}, nil
}

func (r *SlidingWindowLogRateLimiter) DeleteCounter(ctx context.Context, req *pb.DeleteCounterRequest) (*pb.DeleteCounterResponse, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.counters[req.CounterId]; exists {
		delete(r.counters, req.CounterId)
		return &pb.DeleteCounterResponse{Success: true}, nil
	}

	return &pb.DeleteCounterResponse{
		Success: false,
		Error:   "Counter not found",
	}, nil
}

// =============================================================================
// NodeService RPC Implementations
// =============================================================================

func (r *SlidingWindowLogRateLimiter) SyncState(ctx context.Context, req *pb.SyncStateRequest) (*pb.SyncStateResponse, error) {
	for _, state := range req.States {
		r.mu.Lock()
		if counter, exists := r.counters[state.CounterId]; exists {
			counter.mu.Lock()
			// Merge timestamps (union of both logs)
			timestampSet := make(map[int64]bool)
			for _, ts := range counter.Timestamps {
				timestampSet[ts] = true
			}
			for _, ts := range state.Timestamps {
				timestampSet[int64(ts)] = true
			}
			counter.Timestamps = make([]int64, 0, len(timestampSet))
			for ts := range timestampSet {
				counter.Timestamps = append(counter.Timestamps, ts)
			}
			sort.Slice(counter.Timestamps, func(i, j int) bool {
				return counter.Timestamps[i] < counter.Timestamps[j]
			})
			counter.mu.Unlock()
		} else {
			timestamps := make([]int64, len(state.Timestamps))
			for i, ts := range state.Timestamps {
				timestamps[i] = int64(ts)
			}
			sort.Slice(timestamps, func(i, j int) bool {
				return timestamps[i] < timestamps[j]
			})
			r.counters[state.CounterId] = &WindowState{
				CounterID:    state.CounterId,
				Timestamps:   timestamps,
				WindowSizeMs: state.WindowSizeMs,
				RequestLimit: state.RequestLimit,
			}
		}
		r.mu.Unlock()
	}

	return &pb.SyncStateResponse{
		Success: true,
		NodeId:  r.nodeID,
	}, nil
}

func (r *SlidingWindowLogRateLimiter) Heartbeat(ctx context.Context, req *pb.HeartbeatRequest) (*pb.HeartbeatResponse, error) {
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

	limiter := NewSlidingWindowLogRateLimiter(*nodeID, *port, peers)
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

	log.Printf("Starting Sliding Window Log Rate Limiter node %s on port %d", *nodeID, *port)

	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
