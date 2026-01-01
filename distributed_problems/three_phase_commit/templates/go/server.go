// Three-Phase Commit Protocol - Go Template
//
// This template provides the basic structure for implementing
// a non-blocking atomic commitment protocol.
//
// Key concepts:
// 1. CanCommit Phase - Coordinator asks if participants can commit
// 2. PreCommit Phase - Coordinator tells participants to prepare
// 3. DoCommit Phase - Coordinator tells participants to commit
// 4. Timeouts - Handles failures without blocking
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

	pb "github.com/sdp/three_phase_commit"
)

// TransactionState represents the state of a transaction
type TransactionState int

const (
	StateNone TransactionState = iota
	StateWaiting
	StatePreCommitted
	StateCommitted
	StateAborted
)

// Transaction holds the state of a distributed transaction
type Transaction struct {
	TransactionID string
	State         TransactionState
	Data          map[string]string
	Participants  []string
	Timestamp     time.Time
	mu            sync.Mutex
}

// ThreePhaseCommitNode implements the 3PC protocol
type ThreePhaseCommitNode struct {
	pb.UnimplementedCoordinatorServiceServer
	pb.UnimplementedParticipantServiceServer
	pb.UnimplementedNodeServiceServer

	nodeID       string
	port         int
	peers        []string
	transactions map[string]*Transaction
	dataStore    map[string]string
	mu           sync.RWMutex
	peerClients  map[string]pb.ParticipantServiceClient
}

// NewThreePhaseCommitNode creates a new 3PC node
func NewThreePhaseCommitNode(nodeID string, port int, peers []string) *ThreePhaseCommitNode {
	return &ThreePhaseCommitNode{
		nodeID:       nodeID,
		port:         port,
		peers:        peers,
		transactions: make(map[string]*Transaction),
		dataStore:    make(map[string]string),
		peerClients:  make(map[string]pb.ParticipantServiceClient),
	}
}

// Initialize sets up connections to peer nodes
func (n *ThreePhaseCommitNode) Initialize() error {
	for _, peer := range n.peers {
		conn, err := grpc.Dial(peer, grpc.WithTransportCredentials(insecure.NewCredentials()))
		if err != nil {
			log.Printf("Warning: Failed to connect to peer %s: %v", peer, err)
			continue
		}
		n.peerClients[peer] = pb.NewParticipantServiceClient(conn)
	}

	log.Printf("Node %s initialized with peers: %v", n.nodeID, n.peers)
	return nil
}

// =============================================================================
// Coordinator Methods
// =============================================================================

// ExecuteTransaction runs the full 3PC protocol as coordinator
//
// TODO: Implement the 3PC protocol:
// 1. Phase 1 (CanCommit): Ask all participants if they can commit
// 2. If all say yes, Phase 2 (PreCommit): Tell all to prepare
// 3. If all acknowledge, Phase 3 (DoCommit): Tell all to commit
// 4. Handle failures and timeouts appropriately
func (n *ThreePhaseCommitNode) ExecuteTransaction(txID string, data map[string]string, participants []string) (bool, string) {
	// TODO: Implement this method
	return false, "Not implemented"
}

func (n *ThreePhaseCommitNode) abortTransaction(tx *Transaction) {
	// TODO: Implement this method
}

// =============================================================================
// CoordinatorService RPC Implementations
// =============================================================================

func (n *ThreePhaseCommitNode) BeginTransaction(ctx context.Context, req *pb.BeginTransactionRequest) (*pb.BeginTransactionResponse, error) {
	txID := fmt.Sprintf("tx-%s-%d", n.nodeID, time.Now().UnixNano())

	success, errMsg := n.ExecuteTransaction(txID, req.Data, req.Participants)

	return &pb.BeginTransactionResponse{
		TransactionId: txID,
		Success:       success,
		Error:         errMsg,
	}, nil
}

func (n *ThreePhaseCommitNode) GetTransactionStatus(ctx context.Context, req *pb.GetTransactionStatusRequest) (*pb.GetTransactionStatusResponse, error) {
	n.mu.RLock()
	tx, exists := n.transactions[req.TransactionId]
	n.mu.RUnlock()

	if !exists {
		return &pb.GetTransactionStatusResponse{
			State: pb.TransactionState_UNKNOWN,
		}, nil
	}

	tx.mu.Lock()
	state := tx.State
	tx.mu.Unlock()

	var pbState pb.TransactionState
	switch state {
	case StateWaiting:
		pbState = pb.TransactionState_WAITING
	case StatePreCommitted:
		pbState = pb.TransactionState_PRE_COMMITTED
	case StateCommitted:
		pbState = pb.TransactionState_COMMITTED
	case StateAborted:
		pbState = pb.TransactionState_ABORTED
	default:
		pbState = pb.TransactionState_UNKNOWN
	}

	return &pb.GetTransactionStatusResponse{
		TransactionId: tx.TransactionID,
		State:         pbState,
		Participants:  tx.Participants,
	}, nil
}

// =============================================================================
// ParticipantService RPC Implementations
// =============================================================================

func (n *ThreePhaseCommitNode) CanCommit(ctx context.Context, req *pb.CanCommitRequest) (*pb.CanCommitResponse, error) {
	// TODO: Check if we can commit this transaction
	// In a real implementation, check for conflicts, locks, etc.
	return &pb.CanCommitResponse{
		Vote:   false,
		NodeId: n.nodeID,
	}, nil
}

func (n *ThreePhaseCommitNode) PreCommit(ctx context.Context, req *pb.PreCommitRequest) (*pb.PreCommitResponse, error) {
	// TODO: Implement pre-commit phase
	return &pb.PreCommitResponse{
		Acknowledged: false,
		NodeId:       n.nodeID,
	}, nil
}

func (n *ThreePhaseCommitNode) DoCommit(ctx context.Context, req *pb.DoCommitRequest) (*pb.DoCommitResponse, error) {
	// TODO: Implement do-commit phase
	return &pb.DoCommitResponse{
		Success: false,
		NodeId:  n.nodeID,
	}, nil
}

func (n *ThreePhaseCommitNode) Abort(ctx context.Context, req *pb.AbortRequest) (*pb.AbortResponse, error) {
	// TODO: Implement abort phase
	return &pb.AbortResponse{
		Acknowledged: false,
		NodeId:       n.nodeID,
	}, nil
}

// =============================================================================
// NodeService RPC Implementations
// =============================================================================

func (n *ThreePhaseCommitNode) Heartbeat(ctx context.Context, req *pb.HeartbeatRequest) (*pb.HeartbeatResponse, error) {
	return &pb.HeartbeatResponse{
		Acknowledged: true,
		Timestamp:    uint64(time.Now().UnixMilli()),
	}, nil
}

func (n *ThreePhaseCommitNode) GetNodeState(ctx context.Context, req *pb.GetNodeStateRequest) (*pb.GetNodeStateResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	txStates := make([]*pb.TransactionInfo, 0, len(n.transactions))
	for _, tx := range n.transactions {
		tx.mu.Lock()
		var pbState pb.TransactionState
		switch tx.State {
		case StateWaiting:
			pbState = pb.TransactionState_WAITING
		case StatePreCommitted:
			pbState = pb.TransactionState_PRE_COMMITTED
		case StateCommitted:
			pbState = pb.TransactionState_COMMITTED
		case StateAborted:
			pbState = pb.TransactionState_ABORTED
		default:
			pbState = pb.TransactionState_UNKNOWN
		}
		txStates = append(txStates, &pb.TransactionInfo{
			TransactionId: tx.TransactionID,
			State:         pbState,
			Timestamp:     uint64(tx.Timestamp.UnixMilli()),
		})
		tx.mu.Unlock()
	}

	return &pb.GetNodeStateResponse{
		NodeId:       n.nodeID,
		Transactions: txStates,
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

	node := NewThreePhaseCommitNode(*nodeID, *port, peers)
	if err := node.Initialize(); err != nil {
		log.Fatalf("Failed to initialize node: %v", err)
	}

	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	server := grpc.NewServer()
	pb.RegisterCoordinatorServiceServer(server, node)
	pb.RegisterParticipantServiceServer(server, node)
	pb.RegisterNodeServiceServer(server, node)

	log.Printf("Starting Three-Phase Commit node %s on port %d", *nodeID, *port)

	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
