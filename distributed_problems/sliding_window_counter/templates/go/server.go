// Sliding Window Counter Rate Limiter - Go Template
//
// This template provides the basic structure for implementing a distributed
// sliding window counter rate limiter.
//
// Key concepts:
// 1. Hybrid Approach - Combines fixed window efficiency with sliding window accuracy
// 2. Weighted Average - Previous window count weighted by overlap percentage
// 3. Memory Efficient - Only stores two counters, not individual timestamps
// 4. Approximate - Not 100% accurate but good enough for most use cases
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

	pb "github.com/sdp/sliding_window_counter"
)

// WindowState holds the state of a sliding window counter
type WindowState struct {
	CounterID          string
	PreviousCount      uint64
	CurrentCount       uint64
	CurrentWindowStart time.Time
	WindowSizeMs       uint64
	RequestLimit       uint64
	mu                 sync.Mutex
}

// SlidingWindowCounterRateLimiter implements the sliding window counter algorithm
type SlidingWindowCounterRateLimiter struct {
	pb.UnimplementedRateLimiterServiceServer
	pb.UnimplementedNodeServiceServer

	nodeID      string
	port        int
	peers       []string
	counters    map[string]*WindowState
	mu          sync.RWMutex
	peerClients map[string]pb.NodeServiceClient
}

// NewSlidingWindowCounterRateLimiter creates a new rate limiter node
func NewSlidingWindowCounterRateLimiter(nodeID string, port int, peers []string) *SlidingWindowCounterRateLimiter {
	return &SlidingWindowCounterRateLimiter{
		nodeID:      nodeID,
		port:        port,
		peers:       peers,
		counters:    make(map[string]*WindowState),
		peerClients: make(map[string]pb.NodeServiceClient),
	}
}

// Initialize sets up connections to peer nodes
func (r *SlidingWindowCounterRateLimiter) Initialize() error {
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
func (r *SlidingWindowCounterRateLimiter) GetOrCreateCounter(counterID string, windowSizeMs, requestLimit uint64) *WindowState {
	r.mu.Lock()
	defer r.mu.Unlock()

	if counter, exists := r.counters[counterID]; exists {
		return counter
	}

	counter := &WindowState{
		CounterID:          counterID,
		PreviousCount:      0,
		CurrentCount:       0,
		CurrentWindowStart: time.Now(),
		WindowSizeMs:       windowSizeMs,
		RequestLimit:       requestLimit,
	}
	r.counters[counterID] = counter
	return counter
}

// GetCurrentWindowStart calculates the current window start time
func (r *SlidingWindowCounterRateLimiter) GetCurrentWindowStart(windowSizeMs uint64) time.Time {
	now := time.Now()
	windowNum := now.UnixMilli() / int64(windowSizeMs)
	return time.UnixMilli(windowNum * int64(windowSizeMs))
}

// CheckAndRotateWindow rotates windows if needed
//
// TODO: Implement window rotation:
// 1. Calculate the current fixed window start
// 2. If we've moved to a new window:
//    a. Move current count to previous count
//    b. Reset current count
//    c. Update window start
// 3. If we've moved past two windows:
//    a. Reset both counts (too old)
func (r *SlidingWindowCounterRateLimiter) CheckAndRotateWindow(counter *WindowState) {
	// TODO: Implement this method
}

// CalculateWeightedCount calculates the weighted request count
//
// TODO: Implement weighted count calculation:
// 1. Calculate how far we are into the current window (0.0 to 1.0)
// 2. Weight the previous window by the overlap: prev_count * (1 - position)
// 3. Add current window count: current_count * 1.0
// 4. Return total weighted count
func (r *SlidingWindowCounterRateLimiter) CalculateWeightedCount(counter *WindowState) float64 {
	// TODO: Implement this method
	return 0.0
}

// TryIncrement attempts to increment the counter
//
// TODO: Implement increment logic:
// 1. Calculate the current weighted count
// 2. Check if adding new request would exceed limit
// 3. If within limit, increment current count and return true
// 4. If would exceed, return false
func (r *SlidingWindowCounterRateLimiter) TryIncrement(counter *WindowState, count uint64) bool {
	// TODO: Implement this method
	return false
}

// =============================================================================
// RateLimiterService RPC Implementations
// =============================================================================

func (r *SlidingWindowCounterRateLimiter) CreateCounter(ctx context.Context, req *pb.CreateCounterRequest) (*pb.CreateCounterResponse, error) {
	counter := r.GetOrCreateCounter(req.CounterId, req.Config.WindowSizeMs, req.Config.RequestLimit)

	counter.mu.Lock()
	state := &pb.WindowState{
		CounterId:          counter.CounterID,
		PreviousCount:      counter.PreviousCount,
		CurrentCount:       counter.CurrentCount,
		CurrentWindowStart: uint64(counter.CurrentWindowStart.UnixMilli()),
		WindowSizeMs:       counter.WindowSizeMs,
		RequestLimit:       counter.RequestLimit,
	}
	counter.mu.Unlock()

	return &pb.CreateCounterResponse{
		Success: true,
		State:   state,
	}, nil
}

func (r *SlidingWindowCounterRateLimiter) AllowRequest(ctx context.Context, req *pb.AllowRequestRequest) (*pb.AllowRequestResponse, error) {
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

	allowed := r.TryIncrement(counter, count)
	weightedCount := r.CalculateWeightedCount(counter)

	counter.mu.Lock()
	limit := counter.RequestLimit
	windowEnd := counter.CurrentWindowStart.Add(time.Duration(counter.WindowSizeMs) * time.Millisecond)
	counter.mu.Unlock()

	retryAfter := uint64(0)
	if !allowed {
		retryAfter = uint64(time.Until(windowEnd).Milliseconds())
	}

	return &pb.AllowRequestResponse{
		Allowed:        allowed,
		WeightedCount:  weightedCount,
		RemainingCount: float64(limit) - weightedCount,
		RetryAfterMs:   retryAfter,
	}, nil
}

func (r *SlidingWindowCounterRateLimiter) GetCounterState(ctx context.Context, req *pb.GetCounterStateRequest) (*pb.GetCounterStateResponse, error) {
	r.mu.RLock()
	counter, exists := r.counters[req.CounterId]
	r.mu.RUnlock()

	if !exists {
		return &pb.GetCounterStateResponse{}, nil
	}

	r.CheckAndRotateWindow(counter)

	counter.mu.Lock()
	state := &pb.WindowState{
		CounterId:          counter.CounterID,
		PreviousCount:      counter.PreviousCount,
		CurrentCount:       counter.CurrentCount,
		CurrentWindowStart: uint64(counter.CurrentWindowStart.UnixMilli()),
		WindowSizeMs:       counter.WindowSizeMs,
		RequestLimit:       counter.RequestLimit,
	}
	counter.mu.Unlock()

	return &pb.GetCounterStateResponse{
		State: state,
	}, nil
}

func (r *SlidingWindowCounterRateLimiter) DeleteCounter(ctx context.Context, req *pb.DeleteCounterRequest) (*pb.DeleteCounterResponse, error) {
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

func (r *SlidingWindowCounterRateLimiter) SyncState(ctx context.Context, req *pb.SyncStateRequest) (*pb.SyncStateResponse, error) {
	for _, state := range req.States {
		r.mu.Lock()
		if counter, exists := r.counters[state.CounterId]; exists {
			counter.mu.Lock()
			// For same window, use higher counts (more conservative)
			if state.CurrentWindowStart == uint64(counter.CurrentWindowStart.UnixMilli()) {
				if state.CurrentCount > counter.CurrentCount {
					counter.CurrentCount = state.CurrentCount
				}
				if state.PreviousCount > counter.PreviousCount {
					counter.PreviousCount = state.PreviousCount
				}
			} else if state.CurrentWindowStart > uint64(counter.CurrentWindowStart.UnixMilli()) {
				// Newer window, adopt it
				counter.CurrentWindowStart = time.UnixMilli(int64(state.CurrentWindowStart))
				counter.CurrentCount = state.CurrentCount
				counter.PreviousCount = state.PreviousCount
			}
			counter.mu.Unlock()
		} else {
			r.counters[state.CounterId] = &WindowState{
				CounterID:          state.CounterId,
				PreviousCount:      state.PreviousCount,
				CurrentCount:       state.CurrentCount,
				CurrentWindowStart: time.UnixMilli(int64(state.CurrentWindowStart)),
				WindowSizeMs:       state.WindowSizeMs,
				RequestLimit:       state.RequestLimit,
			}
		}
		r.mu.Unlock()
	}

	return &pb.SyncStateResponse{
		Success: true,
		NodeId:  r.nodeID,
	}, nil
}

func (r *SlidingWindowCounterRateLimiter) Heartbeat(ctx context.Context, req *pb.HeartbeatRequest) (*pb.HeartbeatResponse, error) {
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

	limiter := NewSlidingWindowCounterRateLimiter(*nodeID, *port, peers)
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

	log.Printf("Starting Sliding Window Counter Rate Limiter node %s on port %d", *nodeID, *port)

	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
