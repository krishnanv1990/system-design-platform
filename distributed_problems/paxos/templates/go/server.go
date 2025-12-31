// Paxos Consensus Implementation - Go Template
//
// This template provides the basic structure for implementing the Multi-Paxos
// consensus algorithm. You need to implement the TODO sections.
//
// For the full Paxos specification, see: "Paxos Made Simple" by Leslie Lamport
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

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	pb "github.com/sdp/paxos"
)

// NodeRole represents the role of a Paxos node
type NodeRole int

const (
	Proposer NodeRole = iota
	Acceptor
	Learner
	Leader
)

func (r NodeRole) String() string {
	switch r {
	case Proposer:
		return "proposer"
	case Acceptor:
		return "acceptor"
	case Learner:
		return "learner"
	case Leader:
		return "leader"
	default:
		return "unknown"
	}
}

// ProposalNumber represents a proposal number for ordering
type ProposalNumber struct {
	Round      uint64
	ProposerID string
}

// Less returns true if this proposal number is less than other
func (p ProposalNumber) Less(other ProposalNumber) bool {
	if p.Round != other.Round {
		return p.Round < other.Round
	}
	return p.ProposerID < other.ProposerID
}

// LessOrEqual returns true if this proposal number is less than or equal to other
func (p ProposalNumber) LessOrEqual(other ProposalNumber) bool {
	return p == other || p.Less(other)
}

// ToProto converts to protobuf message
func (p ProposalNumber) ToProto() *pb.ProposalNumber {
	return &pb.ProposalNumber{Round: p.Round, ProposerId: p.ProposerID}
}

// ProposalNumberFromProto creates a ProposalNumber from protobuf message
func ProposalNumberFromProto(proto *pb.ProposalNumber) ProposalNumber {
	if proto == nil {
		return ProposalNumber{}
	}
	return ProposalNumber{Round: proto.Round, ProposerID: proto.ProposerId}
}

// AcceptorState holds state maintained by an acceptor for each slot
type AcceptorState struct {
	HighestPromised  *ProposalNumber
	AcceptedProposal *ProposalNumber
	AcceptedValue    []byte
}

// PaxosState holds persistent and volatile state for a Paxos node
type PaxosState struct {
	// Current round number for proposals
	CurrentRound uint64

	// Per-slot acceptor state
	AcceptorStates map[uint64]*AcceptorState

	// Learned values per slot
	LearnedValues map[uint64][]byte

	// First slot that hasn't been chosen yet
	FirstUnchosenSlot uint64

	// Last slot that was executed on the state machine
	LastExecutedSlot uint64
}

// PaxosNode implements the Paxos consensus algorithm
type PaxosNode struct {
	pb.UnimplementedPaxosServiceServer
	pb.UnimplementedKeyValueServiceServer

	nodeID   string
	port     int
	peers    []string
	state    PaxosState
	role     NodeRole
	leaderID string

	// Key-value store (state machine)
	kvStore map[string]string

	// Timing configuration
	heartbeatInterval float64
	leaderTimeout     float64

	// Synchronization
	mu sync.RWMutex

	// gRPC clients for peer communication
	peerClients map[string]pb.PaxosServiceClient
}

// NewPaxosNode creates a new Paxos node
func NewPaxosNode(nodeID string, port int, peers []string) *PaxosNode {
	return &PaxosNode{
		nodeID: nodeID,
		port:   port,
		peers:  peers,
		state: PaxosState{
			AcceptorStates: make(map[uint64]*AcceptorState),
			LearnedValues:  make(map[uint64][]byte),
		},
		role:              Acceptor,
		kvStore:           make(map[string]string),
		heartbeatInterval: 0.1, // 100ms
		leaderTimeout:     0.5, // 500ms
		peerClients:       make(map[string]pb.PaxosServiceClient),
	}
}

// Initialize sets up connections to peer nodes
func (n *PaxosNode) Initialize() error {
	for _, peer := range n.peers {
		conn, err := grpc.Dial(peer, grpc.WithTransportCredentials(insecure.NewCredentials()))
		if err != nil {
			log.Printf("Warning: Failed to connect to peer %s: %v", peer, err)
			continue
		}
		n.peerClients[peer] = pb.NewPaxosServiceClient(conn)
	}
	log.Printf("Node %s initialized with peers: %v", n.nodeID, n.peers)
	return nil
}

// GetAcceptorState returns or creates acceptor state for a slot
func (n *PaxosNode) GetAcceptorState(slot uint64) *AcceptorState {
	if _, ok := n.state.AcceptorStates[slot]; !ok {
		n.state.AcceptorStates[slot] = &AcceptorState{}
	}
	return n.state.AcceptorStates[slot]
}

// GenerateProposalNumber generates a new proposal number higher than any seen
func (n *PaxosNode) GenerateProposalNumber() ProposalNumber {
	n.state.CurrentRound++
	return ProposalNumber{Round: n.state.CurrentRound, ProposerID: n.nodeID}
}

// =============================================================================
// Phase 1: Prepare
// =============================================================================

// SendPrepare sends Prepare requests to all acceptors
//
// TODO: Implement Phase 1a of Paxos:
// 1. Send Prepare(n) to all acceptors
// 2. Wait for responses from a majority
// 3. If majority promise, return (true, highest_accepted_value)
// 4. If any acceptor has accepted a value, use that value
func (n *PaxosNode) SendPrepare(slot uint64, proposal ProposalNumber) (bool, []byte) {
	return false, nil
}

// Prepare handles Prepare RPC from a proposer
//
// TODO: Implement Phase 1b of Paxos:
// 1. If n > highest_promised, update highest_promised and promise
// 2. Return (promised=True, accepted_proposal, accepted_value)
// 3. Otherwise return (promised=False, highest_promised)
func (n *PaxosNode) Prepare(ctx context.Context, req *pb.PrepareRequest) (*pb.PrepareResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	response := &pb.PrepareResponse{
		Promised: false,
	}

	slot := req.Slot
	proposal := ProposalNumberFromProto(req.ProposalNumber)
	acceptorState := n.GetAcceptorState(slot)

	// TODO: Implement prepare logic
	_ = proposal
	_ = acceptorState

	return response, nil
}

// =============================================================================
// Phase 2: Accept
// =============================================================================

// SendAccept sends Accept requests to all acceptors
//
// TODO: Implement Phase 2a of Paxos:
// 1. Send Accept(n, v) to all acceptors
// 2. Wait for responses from a majority
// 3. If majority accept, value is chosen - notify learners
// 4. Return true if value was chosen
func (n *PaxosNode) SendAccept(slot uint64, proposal ProposalNumber, value []byte) bool {
	return false
}

// Accept handles Accept RPC from a proposer
//
// TODO: Implement Phase 2b of Paxos:
// 1. If n >= highest_promised, accept the value
// 2. Update accepted_proposal and accepted_value
// 3. Return (accepted=True)
// 4. Otherwise return (accepted=False, highest_promised)
func (n *PaxosNode) Accept(ctx context.Context, req *pb.AcceptRequest) (*pb.AcceptResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	response := &pb.AcceptResponse{
		Accepted: false,
	}

	slot := req.Slot
	proposal := ProposalNumberFromProto(req.ProposalNumber)
	acceptorState := n.GetAcceptorState(slot)

	// TODO: Implement accept logic
	_ = proposal
	_ = acceptorState

	return response, nil
}

// =============================================================================
// Learning
// =============================================================================

// Learn handles Learn RPC - a value has been chosen
//
// TODO: Implement learning:
// 1. Store the learned value for the slot
// 2. If this fills a gap, execute commands in order
func (n *PaxosNode) Learn(ctx context.Context, req *pb.LearnRequest) (*pb.LearnResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	response := &pb.LearnResponse{
		Success: true,
	}

	slot := req.Slot
	value := req.Value

	// TODO: Implement learn logic
	_ = slot
	_ = value

	return response, nil
}

// ApplyCommand applies a command to the state machine
func (n *PaxosNode) ApplyCommand(command []byte, commandType string) {
	// TODO: Parse and apply the command
}

// =============================================================================
// Multi-Paxos Leader Election
// =============================================================================

// Heartbeat handles heartbeat from current leader
func (n *PaxosNode) Heartbeat(ctx context.Context, req *pb.HeartbeatRequest) (*pb.HeartbeatResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	response := &pb.HeartbeatResponse{
		Acknowledged: true,
	}

	// TODO: Implement leader acknowledgment

	return response, nil
}

// RunAsLeader runs as the Multi-Paxos leader
//
// TODO: Implement Multi-Paxos optimization:
// 1. Skip Phase 1 for consecutive slots after becoming leader
// 2. Send heartbeats to maintain leadership
// 3. Handle client requests directly
func (n *PaxosNode) RunAsLeader() {
}

// =============================================================================
// KeyValueService RPC Implementations
// =============================================================================

// Get returns value for key from state machine
func (n *PaxosNode) Get(ctx context.Context, req *pb.GetRequest) (*pb.GetResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	response := &pb.GetResponse{}
	if value, ok := n.kvStore[req.Key]; ok {
		response.Value = value
		response.Found = true
	}
	return response, nil
}

// Put stores key-value pair (requires consensus)
//
// TODO: Implement consensus-based put:
// 1. If not leader, return leader_hint
// 2. Run Paxos to agree on this operation
// 3. Apply to state machine once chosen
func (n *PaxosNode) Put(ctx context.Context, req *pb.PutRequest) (*pb.PutResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	response := &pb.PutResponse{}
	if n.role != Leader {
		response.Success = false
		response.Error = "Not the leader"
		response.LeaderHint = n.leaderID
		return response, nil
	}

	// TODO: Implement consensus-based put
	response.Success = false
	response.Error = "Not implemented"

	return response, nil
}

// Delete removes key (requires consensus)
func (n *PaxosNode) Delete(ctx context.Context, req *pb.DeleteRequest) (*pb.DeleteResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	response := &pb.DeleteResponse{}
	if n.role != Leader {
		response.Success = false
		response.Error = "Not the leader"
		response.LeaderHint = n.leaderID
		return response, nil
	}

	// TODO: Implement consensus-based delete
	response.Success = false
	response.Error = "Not implemented"

	return response, nil
}

// GetLeader returns current leader information
func (n *PaxosNode) GetLeader(ctx context.Context, req *pb.GetLeaderRequest) (*pb.GetLeaderResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	response := &pb.GetLeaderResponse{
		LeaderId: n.leaderID,
		IsLeader: n.role == Leader,
	}

	for _, peer := range n.peers {
		if strings.Contains(peer, n.leaderID) {
			response.LeaderAddress = peer
			break
		}
	}

	return response, nil
}

// GetClusterStatus returns cluster status information
func (n *PaxosNode) GetClusterStatus(ctx context.Context, req *pb.GetClusterStatusRequest) (*pb.GetClusterStatusResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	response := &pb.GetClusterStatusResponse{
		NodeId:               n.nodeID,
		Role:                 n.role.String(),
		CurrentSlot:          n.state.FirstUnchosenSlot,
		HighestPromisedRound: n.state.CurrentRound,
		FirstUnchosenSlot:    n.state.FirstUnchosenSlot,
		LastExecutedSlot:     n.state.LastExecutedSlot,
	}

	for _, peer := range n.peers {
		member := &pb.ClusterMember{
			Address: peer,
		}
		response.Members = append(response.Members, member)
	}

	return response, nil
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
	if *peersStr == "" {
		log.Fatal("--peers is required")
	}

	peers := strings.Split(*peersStr, ",")
	for i, p := range peers {
		peers[i] = strings.TrimSpace(p)
	}

	node := NewPaxosNode(*nodeID, *port, peers)
	if err := node.Initialize(); err != nil {
		log.Fatalf("Failed to initialize node: %v", err)
	}

	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	server := grpc.NewServer()
	pb.RegisterPaxosServiceServer(server, node)
	pb.RegisterKeyValueServiceServer(server, node)

	log.Printf("Starting Paxos node %s on port %d", *nodeID, *port)

	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
