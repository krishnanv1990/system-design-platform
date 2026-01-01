// Fixed Window Counter Rate Limiter - Go Template
//
// This template provides the basic structure for implementing a distributed
// fixed window counter rate limiter.
//
// Key concepts:
// 1. Fixed Windows - Time is divided into fixed intervals (e.g., 1 minute)
// 2. Counter - Each window has a counter for requests
// 3. Limit - Maximum requests allowed per window
// 4. Reset - Counter resets at the start of each new window
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

	pb "github.com/sdp/fixed_window_counter"
)

// WindowState holds the state of a fixed window counter
type WindowState struct {
	CounterID     string
	WindowStart   time.Time
	WindowSizeMs  uint64
	RequestCount  uint64
	RequestLimit  uint64
	mu            sync.Mutex
}

// FixedWindowRateLimiter implements the fixed window counter algorithm
type FixedWindowRateLimiter struct {
	pb.UnimplementedRateLimiterServiceServer
	pb.UnimplementedNodeServiceServer

	nodeID      string
	port        int
	peers       []string
	counters    map[string]*WindowState
	mu          sync.RWMutex
	peerClients map[string]pb.NodeServiceClient
}

// NewFixedWindowRateLimiter creates a new rate limiter node
func NewFixedWindowRateLimiter(nodeID string, port int, peers []string) *FixedWindowRateLimiter {
	return &FixedWindowRateLimiter{
		nodeID:      nodeID,
		port:        port,
		peers:       peers,
		counters:    make(map[string]*WindowState),
		peerClients: make(map[string]pb.NodeServiceClient),
	}
}

// Initialize sets up connections to peer nodes
func (r *FixedWindowRateLimiter) Initialize() error {
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
func (r *FixedWindowRateLimiter) GetOrCreateCounter(counterID string, windowSizeMs, requestLimit uint64) *WindowState {
	r.mu.Lock()
	defer r.mu.Unlock()

	if counter, exists := r.counters[counterID]; exists {
		return counter
	}

	counter := &WindowState{
		CounterID:    counterID,
		WindowStart:  time.Now(),
		WindowSizeMs: windowSizeMs,
		RequestCount: 0,
		RequestLimit: requestLimit,
	}
	r.counters[counterID] = counter
	return counter
}

// GetCurrentWindow calculates the current window start time
//
// TODO: Implement window calculation:
// 1. Get the current timestamp in milliseconds
// 2. Calculate which window we're in: window_num = current_time / window_size
// 3. Return window start: window_start = window_num * window_size
func (r *FixedWindowRateLimiter) GetCurrentWindow(windowSizeMs uint64) time.Time {
	// TODO: Implement this method
	return time.Time{}
}

// CheckAndRotateWindow rotates to new window if needed
//
// TODO: Implement window rotation:
// 1. Calculate the current window start
// 2. If window has changed, reset the counter
// 3. Update window start time
func (r *FixedWindowRateLimiter) CheckAndRotateWindow(counter *WindowState) {
	// TODO: Implement this method
}

// TryIncrement attempts to increment the counter
//
// TODO: Implement counter increment:
// 1. First check and rotate window if needed
// 2. Check if incrementing would exceed limit
// 3. If within limit, increment and return true
// 4. If would exceed, return false
func (r *FixedWindowRateLimiter) TryIncrement(counter *WindowState, count uint64) bool {
	// TODO: Implement this method
	return false
}

// =============================================================================
// RateLimiterService RPC Implementations
// =============================================================================

func (r *FixedWindowRateLimiter) CreateCounter(ctx context.Context, req *pb.CreateCounterRequest) (*pb.CreateCounterResponse, error) {
	counter := r.GetOrCreateCounter(req.CounterId, req.Config.WindowSizeMs, req.Config.RequestLimit)

	return &pb.CreateCounterResponse{
		Success: true,
		State: &pb.WindowState{
			CounterId:    counter.CounterID,
			WindowStart:  uint64(counter.WindowStart.UnixMilli()),
			WindowSizeMs: counter.WindowSizeMs,
			RequestCount: counter.RequestCount,
			RequestLimit: counter.RequestLimit,
		},
	}, nil
}

func (r *FixedWindowRateLimiter) AllowRequest(ctx context.Context, req *pb.AllowRequestRequest) (*pb.AllowRequestResponse, error) {
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

	counter.mu.Lock()
	currentCount := counter.RequestCount
	limit := counter.RequestLimit
	windowEnd := counter.WindowStart.Add(time.Duration(counter.WindowSizeMs) * time.Millisecond)
	counter.mu.Unlock()

	retryAfter := uint64(0)
	if !allowed {
		retryAfter = uint64(time.Until(windowEnd).Milliseconds())
	}

	return &pb.AllowRequestResponse{
		Allowed:        allowed,
		CurrentCount:   currentCount,
		RemainingCount: limit - currentCount,
		RetryAfterMs:   retryAfter,
	}, nil
}

func (r *FixedWindowRateLimiter) GetCounterState(ctx context.Context, req *pb.GetCounterStateRequest) (*pb.GetCounterStateResponse, error) {
	r.mu.RLock()
	counter, exists := r.counters[req.CounterId]
	r.mu.RUnlock()

	if !exists {
		return &pb.GetCounterStateResponse{}, nil
	}

	r.CheckAndRotateWindow(counter)

	counter.mu.Lock()
	state := &pb.WindowState{
		CounterId:    counter.CounterID,
		WindowStart:  uint64(counter.WindowStart.UnixMilli()),
		WindowSizeMs: counter.WindowSizeMs,
		RequestCount: counter.RequestCount,
		RequestLimit: counter.RequestLimit,
	}
	counter.mu.Unlock()

	return &pb.GetCounterStateResponse{
		State: state,
	}, nil
}

func (r *FixedWindowRateLimiter) DeleteCounter(ctx context.Context, req *pb.DeleteCounterRequest) (*pb.DeleteCounterResponse, error) {
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

func (r *FixedWindowRateLimiter) SyncState(ctx context.Context, req *pb.SyncStateRequest) (*pb.SyncStateResponse, error) {
	for _, state := range req.States {
		r.mu.Lock()
		if counter, exists := r.counters[state.CounterId]; exists {
			counter.mu.Lock()
			// For same window, use higher count (more conservative)
			if state.WindowStart == uint64(counter.WindowStart.UnixMilli()) {
				if state.RequestCount > counter.RequestCount {
					counter.RequestCount = state.RequestCount
				}
			} else if state.WindowStart > uint64(counter.WindowStart.UnixMilli()) {
				// Newer window, adopt it
				counter.WindowStart = time.UnixMilli(int64(state.WindowStart))
				counter.RequestCount = state.RequestCount
			}
			counter.mu.Unlock()
		} else {
			r.counters[state.CounterId] = &WindowState{
				CounterID:    state.CounterId,
				WindowStart:  time.UnixMilli(int64(state.WindowStart)),
				WindowSizeMs: state.WindowSizeMs,
				RequestCount: state.RequestCount,
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

func (r *FixedWindowRateLimiter) Heartbeat(ctx context.Context, req *pb.HeartbeatRequest) (*pb.HeartbeatResponse, error) {
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

	limiter := NewFixedWindowRateLimiter(*nodeID, *port, peers)
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

	log.Printf("Starting Fixed Window Counter Rate Limiter node %s on port %d", *nodeID, *port)

	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
