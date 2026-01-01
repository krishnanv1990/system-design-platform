// CRDT (Conflict-free Replicated Data Types) - Go Template
//
// This template provides the basic structure for implementing
// various CRDTs for eventually consistent distributed systems.
//
// Key concepts:
// 1. Convergence - All replicas converge to the same state
// 2. Commutativity - Operations can be applied in any order
// 3. Idempotence - Applying the same operation twice has no effect
// 4. No Coordination - No consensus required for updates
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

	pb "github.com/sdp/crdt"
)

// =============================================================================
// G-Counter (Grow-only Counter)
// =============================================================================

// GCounter implements a grow-only counter CRDT
type GCounter struct {
	ID     string
	Counts map[string]uint64 // node_id -> count
	mu     sync.RWMutex
}

// NewGCounter creates a new G-Counter
func NewGCounter(id string) *GCounter {
	return &GCounter{
		ID:     id,
		Counts: make(map[string]uint64),
	}
}

// Increment increases this node's count
//
// TODO: Implement increment:
// - Only increment this node's counter
// - Each node maintains its own count
func (c *GCounter) Increment(nodeID string, amount uint64) {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.Counts[nodeID] += amount
}

// Value returns the total count across all nodes
//
// TODO: Implement value calculation:
// - Sum all node counters
func (c *GCounter) Value() uint64 {
	c.mu.RLock()
	defer c.mu.RUnlock()

	var total uint64
	for _, count := range c.Counts {
		total += count
	}
	return total
}

// Merge combines another G-Counter into this one
//
// TODO: Implement merge:
// - Take maximum of each node's counter
// - This ensures convergence
func (c *GCounter) Merge(other map[string]uint64) {
	c.mu.Lock()
	defer c.mu.Unlock()

	for nodeID, count := range other {
		if count > c.Counts[nodeID] {
			c.Counts[nodeID] = count
		}
	}
}

// =============================================================================
// PN-Counter (Positive-Negative Counter)
// =============================================================================

// PNCounter implements a counter that supports increment and decrement
type PNCounter struct {
	ID        string
	Positive  *GCounter
	Negative  *GCounter
}

// NewPNCounter creates a new PN-Counter
func NewPNCounter(id string) *PNCounter {
	return &PNCounter{
		ID:       id,
		Positive: NewGCounter(id + "-pos"),
		Negative: NewGCounter(id + "-neg"),
	}
}

// Increment increases the counter
func (c *PNCounter) Increment(nodeID string, amount uint64) {
	c.Positive.Increment(nodeID, amount)
}

// Decrement decreases the counter
func (c *PNCounter) Decrement(nodeID string, amount uint64) {
	c.Negative.Increment(nodeID, amount)
}

// Value returns P - N
//
// TODO: Implement value calculation:
// - Return positive.value() - negative.value()
func (c *PNCounter) Value() int64 {
	return int64(c.Positive.Value()) - int64(c.Negative.Value())
}

// =============================================================================
// G-Set (Grow-only Set)
// =============================================================================

// GSet implements a grow-only set CRDT
type GSet struct {
	ID       string
	Elements map[string]bool
	mu       sync.RWMutex
}

// NewGSet creates a new G-Set
func NewGSet(id string) *GSet {
	return &GSet{
		ID:       id,
		Elements: make(map[string]bool),
	}
}

// Add adds an element to the set
func (s *GSet) Add(element string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.Elements[element] = true
}

// Contains checks if element is in the set
func (s *GSet) Contains(element string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()

	return s.Elements[element]
}

// Merge combines another G-Set (union)
func (s *GSet) Merge(other map[string]bool) {
	s.mu.Lock()
	defer s.mu.Unlock()

	for element := range other {
		s.Elements[element] = true
	}
}

// =============================================================================
// OR-Set (Observed-Remove Set)
// =============================================================================

// ORSetElement represents an element with unique tags
type ORSetElement struct {
	Value string
	Tags  map[string]bool // unique add tags
}

// ORSet implements an observed-remove set CRDT
type ORSet struct {
	ID       string
	Elements map[string]*ORSetElement
	mu       sync.RWMutex
}

// NewORSet creates a new OR-Set
func NewORSet(id string) *ORSet {
	return &ORSet{
		ID:       id,
		Elements: make(map[string]*ORSetElement),
	}
}

// Add adds an element with a unique tag
//
// TODO: Implement add:
// - Generate unique tag (e.g., node_id + timestamp)
// - Add element with tag
func (s *ORSet) Add(element string, tag string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if _, exists := s.Elements[element]; !exists {
		s.Elements[element] = &ORSetElement{
			Value: element,
			Tags:  make(map[string]bool),
		}
	}
	s.Elements[element].Tags[tag] = true
}

// Remove removes all known tags for an element
//
// TODO: Implement remove:
// - Remove all currently known tags for the element
// - Concurrent adds with new tags will survive
func (s *ORSet) Remove(element string) []string {
	s.mu.Lock()
	defer s.mu.Unlock()

	elem, exists := s.Elements[element]
	if !exists {
		return nil
	}

	removedTags := make([]string, 0, len(elem.Tags))
	for tag := range elem.Tags {
		removedTags = append(removedTags, tag)
	}

	delete(s.Elements, element)
	return removedTags
}

// Contains checks if element is in the set
func (s *ORSet) Contains(element string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()

	elem, exists := s.Elements[element]
	return exists && len(elem.Tags) > 0
}

// =============================================================================
// LWW-Register (Last-Writer-Wins Register)
// =============================================================================

// LWWRegister implements a last-writer-wins register
type LWWRegister struct {
	ID        string
	Value     string
	Timestamp uint64
	mu        sync.RWMutex
}

// NewLWWRegister creates a new LWW-Register
func NewLWWRegister(id string) *LWWRegister {
	return &LWWRegister{
		ID:        id,
		Value:     "",
		Timestamp: 0,
	}
}

// Set updates the value if timestamp is newer
//
// TODO: Implement set:
// - Only update if new timestamp > current timestamp
// - This ensures last write wins
func (r *LWWRegister) Set(value string, timestamp uint64) bool {
	r.mu.Lock()
	defer r.mu.Unlock()

	if timestamp > r.Timestamp {
		r.Value = value
		r.Timestamp = timestamp
		return true
	}
	return false
}

// Get returns the current value
func (r *LWWRegister) Get() (string, uint64) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	return r.Value, r.Timestamp
}

// =============================================================================
// CRDTNode - Main Node Implementation
// =============================================================================

// CRDTNode implements the CRDT services
type CRDTNode struct {
	pb.UnimplementedCRDTServiceServer
	pb.UnimplementedReplicationServiceServer

	nodeID      string
	port        int
	peers       []string
	gCounters   map[string]*GCounter
	pnCounters  map[string]*PNCounter
	gSets       map[string]*GSet
	orSets      map[string]*ORSet
	lwwRegs     map[string]*LWWRegister
	mu          sync.RWMutex
	peerClients map[string]pb.ReplicationServiceClient
}

// NewCRDTNode creates a new CRDT node
func NewCRDTNode(nodeID string, port int, peers []string) *CRDTNode {
	return &CRDTNode{
		nodeID:      nodeID,
		port:        port,
		peers:       peers,
		gCounters:   make(map[string]*GCounter),
		pnCounters:  make(map[string]*PNCounter),
		gSets:       make(map[string]*GSet),
		orSets:      make(map[string]*ORSet),
		lwwRegs:     make(map[string]*LWWRegister),
		peerClients: make(map[string]pb.ReplicationServiceClient),
	}
}

// Initialize sets up connections to peer nodes
func (n *CRDTNode) Initialize() error {
	for _, peer := range n.peers {
		conn, err := grpc.Dial(peer, grpc.WithTransportCredentials(insecure.NewCredentials()))
		if err != nil {
			log.Printf("Warning: Failed to connect to peer %s: %v", peer, err)
			continue
		}
		n.peerClients[peer] = pb.NewReplicationServiceClient(conn)
	}

	log.Printf("Node %s initialized with peers: %v", n.nodeID, n.peers)
	return nil
}

// =============================================================================
// CRDTService RPC Implementations - G-Counter
// =============================================================================

func (n *CRDTNode) GCounterIncrement(ctx context.Context, req *pb.GCounterIncrementRequest) (*pb.GCounterIncrementResponse, error) {
	n.mu.Lock()
	counter, exists := n.gCounters[req.CounterId]
	if !exists {
		counter = NewGCounter(req.CounterId)
		n.gCounters[req.CounterId] = counter
	}
	n.mu.Unlock()

	amount := req.Amount
	if amount == 0 {
		amount = 1
	}
	counter.Increment(n.nodeID, amount)

	return &pb.GCounterIncrementResponse{
		Success:   true,
		NodeId:    n.nodeID,
		NodeCount: counter.Counts[n.nodeID],
	}, nil
}

func (n *CRDTNode) GCounterGet(ctx context.Context, req *pb.GCounterGetRequest) (*pb.GCounterGetResponse, error) {
	n.mu.RLock()
	counter, exists := n.gCounters[req.CounterId]
	n.mu.RUnlock()

	if !exists {
		return &pb.GCounterGetResponse{Value: 0}, nil
	}

	counter.mu.RLock()
	nodeCounts := make(map[string]uint64)
	for k, v := range counter.Counts {
		nodeCounts[k] = v
	}
	counter.mu.RUnlock()

	return &pb.GCounterGetResponse{
		Value:      counter.Value(),
		NodeCounts: nodeCounts,
	}, nil
}

// =============================================================================
// CRDTService RPC Implementations - PN-Counter
// =============================================================================

func (n *CRDTNode) PNCounterIncrement(ctx context.Context, req *pb.PNCounterIncrementRequest) (*pb.PNCounterIncrementResponse, error) {
	n.mu.Lock()
	counter, exists := n.pnCounters[req.CounterId]
	if !exists {
		counter = NewPNCounter(req.CounterId)
		n.pnCounters[req.CounterId] = counter
	}
	n.mu.Unlock()

	amount := req.Amount
	if amount == 0 {
		amount = 1
	}
	counter.Increment(n.nodeID, amount)

	return &pb.PNCounterIncrementResponse{
		Success: true,
		NodeId:  n.nodeID,
	}, nil
}

func (n *CRDTNode) PNCounterDecrement(ctx context.Context, req *pb.PNCounterDecrementRequest) (*pb.PNCounterDecrementResponse, error) {
	n.mu.Lock()
	counter, exists := n.pnCounters[req.CounterId]
	if !exists {
		counter = NewPNCounter(req.CounterId)
		n.pnCounters[req.CounterId] = counter
	}
	n.mu.Unlock()

	amount := req.Amount
	if amount == 0 {
		amount = 1
	}
	counter.Decrement(n.nodeID, amount)

	return &pb.PNCounterDecrementResponse{
		Success: true,
		NodeId:  n.nodeID,
	}, nil
}

func (n *CRDTNode) PNCounterGet(ctx context.Context, req *pb.PNCounterGetRequest) (*pb.PNCounterGetResponse, error) {
	n.mu.RLock()
	counter, exists := n.pnCounters[req.CounterId]
	n.mu.RUnlock()

	if !exists {
		return &pb.PNCounterGetResponse{Value: 0}, nil
	}

	return &pb.PNCounterGetResponse{
		Value: counter.Value(),
	}, nil
}

// =============================================================================
// CRDTService RPC Implementations - G-Set
// =============================================================================

func (n *CRDTNode) GSetAdd(ctx context.Context, req *pb.GSetAddRequest) (*pb.GSetAddResponse, error) {
	n.mu.Lock()
	set, exists := n.gSets[req.SetId]
	if !exists {
		set = NewGSet(req.SetId)
		n.gSets[req.SetId] = set
	}
	n.mu.Unlock()

	set.Add(req.Element)

	return &pb.GSetAddResponse{
		Success: true,
		NodeId:  n.nodeID,
	}, nil
}

func (n *CRDTNode) GSetContains(ctx context.Context, req *pb.GSetContainsRequest) (*pb.GSetContainsResponse, error) {
	n.mu.RLock()
	set, exists := n.gSets[req.SetId]
	n.mu.RUnlock()

	if !exists {
		return &pb.GSetContainsResponse{Contains: false}, nil
	}

	return &pb.GSetContainsResponse{
		Contains: set.Contains(req.Element),
	}, nil
}

func (n *CRDTNode) GSetElements(ctx context.Context, req *pb.GSetElementsRequest) (*pb.GSetElementsResponse, error) {
	n.mu.RLock()
	set, exists := n.gSets[req.SetId]
	n.mu.RUnlock()

	if !exists {
		return &pb.GSetElementsResponse{Elements: []string{}}, nil
	}

	set.mu.RLock()
	elements := make([]string, 0, len(set.Elements))
	for elem := range set.Elements {
		elements = append(elements, elem)
	}
	set.mu.RUnlock()

	return &pb.GSetElementsResponse{
		Elements: elements,
	}, nil
}

// =============================================================================
// CRDTService RPC Implementations - LWW-Register
// =============================================================================

func (n *CRDTNode) LWWRegisterSet(ctx context.Context, req *pb.LWWRegisterSetRequest) (*pb.LWWRegisterSetResponse, error) {
	n.mu.Lock()
	reg, exists := n.lwwRegs[req.RegisterId]
	if !exists {
		reg = NewLWWRegister(req.RegisterId)
		n.lwwRegs[req.RegisterId] = reg
	}
	n.mu.Unlock()

	timestamp := req.Timestamp
	if timestamp == 0 {
		timestamp = uint64(time.Now().UnixNano())
	}

	success := reg.Set(req.Value, timestamp)

	return &pb.LWWRegisterSetResponse{
		Success:   success,
		NodeId:    n.nodeID,
		Timestamp: timestamp,
	}, nil
}

func (n *CRDTNode) LWWRegisterGet(ctx context.Context, req *pb.LWWRegisterGetRequest) (*pb.LWWRegisterGetResponse, error) {
	n.mu.RLock()
	reg, exists := n.lwwRegs[req.RegisterId]
	n.mu.RUnlock()

	if !exists {
		return &pb.LWWRegisterGetResponse{Value: "", Timestamp: 0}, nil
	}

	value, timestamp := reg.Get()

	return &pb.LWWRegisterGetResponse{
		Value:     value,
		Timestamp: timestamp,
	}, nil
}

// =============================================================================
// ReplicationService RPC Implementations
// =============================================================================

func (n *CRDTNode) ReplicateGCounter(ctx context.Context, req *pb.ReplicateGCounterRequest) (*pb.ReplicateGCounterResponse, error) {
	n.mu.Lock()
	counter, exists := n.gCounters[req.CounterId]
	if !exists {
		counter = NewGCounter(req.CounterId)
		n.gCounters[req.CounterId] = counter
	}
	n.mu.Unlock()

	counter.Merge(req.NodeCounts)

	return &pb.ReplicateGCounterResponse{
		Success: true,
		NodeId:  n.nodeID,
	}, nil
}

func (n *CRDTNode) ReplicateGSet(ctx context.Context, req *pb.ReplicateGSetRequest) (*pb.ReplicateGSetResponse, error) {
	n.mu.Lock()
	set, exists := n.gSets[req.SetId]
	if !exists {
		set = NewGSet(req.SetId)
		n.gSets[req.SetId] = set
	}
	n.mu.Unlock()

	elemMap := make(map[string]bool)
	for _, elem := range req.Elements {
		elemMap[elem] = true
	}
	set.Merge(elemMap)

	return &pb.ReplicateGSetResponse{
		Success: true,
		NodeId:  n.nodeID,
	}, nil
}

func (n *CRDTNode) ReplicateLWWRegister(ctx context.Context, req *pb.ReplicateLWWRegisterRequest) (*pb.ReplicateLWWRegisterResponse, error) {
	n.mu.Lock()
	reg, exists := n.lwwRegs[req.RegisterId]
	if !exists {
		reg = NewLWWRegister(req.RegisterId)
		n.lwwRegs[req.RegisterId] = reg
	}
	n.mu.Unlock()

	success := reg.Set(req.Value, req.Timestamp)

	return &pb.ReplicateLWWRegisterResponse{
		Success: success,
		NodeId:  n.nodeID,
	}, nil
}

func (n *CRDTNode) Heartbeat(ctx context.Context, req *pb.HeartbeatRequest) (*pb.HeartbeatResponse, error) {
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

	node := NewCRDTNode(*nodeID, *port, peers)
	if err := node.Initialize(); err != nil {
		log.Fatalf("Failed to initialize node: %v", err)
	}

	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	server := grpc.NewServer()
	pb.RegisterCRDTServiceServer(server, node)
	pb.RegisterReplicationServiceServer(server, node)

	log.Printf("Starting CRDT node %s on port %d", *nodeID, *port)

	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
