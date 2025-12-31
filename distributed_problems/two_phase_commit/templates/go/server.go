// Two-Phase Commit (2PC) Implementation - Go Template
//
// This template provides the basic structure for implementing the Two-Phase Commit
// protocol for distributed transactions. You need to implement the TODO sections.
//
// Usage:
//     go run server.go --node-id coord --port 50051 --role coordinator --participants p1:50052,p2:50053
//     go run server.go --node-id p1 --port 50052 --role participant --coordinator coord:50051

package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net"
	"strings"
	"sync"

	"github.com/google/uuid"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	pb "github.com/sdp/tpc"
)

// NodeRole represents the role of a 2PC node
type NodeRole int

const (
	Coordinator NodeRole = iota
	Participant
)

func (r NodeRole) String() string {
	switch r {
	case Coordinator:
		return "coordinator"
	case Participant:
		return "participant"
	default:
		return "unknown"
	}
}

// TransactionState represents the state of a transaction
type TransactionState int

const (
	StateUnknown TransactionState = iota
	StateActive
	StatePreparing
	StatePrepared
	StateCommitting
	StateCommitted
	StateAborting
	StateAborted
)

// Operation represents a single operation in a transaction
type Operation struct {
	Type          string
	Key           string
	Value         string
	ParticipantID string
}

// Transaction represents a distributed transaction
type Transaction struct {
	ID               string
	State            TransactionState
	Participants     []string
	Operations       map[string][]Operation // participant_id -> operations
	ParticipantVotes map[string]bool
	TimeoutMs        int
}

// ParticipantState holds state for a transaction at a participant
type ParticipantState struct {
	TransactionID string
	State         TransactionState
	Operations    []Operation
	LocksHeld     map[string]bool
}

// TwoPhaseCommitNode implements the 2PC protocol
type TwoPhaseCommitNode struct {
	pb.UnimplementedCoordinatorServiceServer
	pb.UnimplementedParticipantServiceServer
	pb.UnimplementedKeyValueServiceServer

	nodeID          string
	port            int
	role            NodeRole
	participants    []string
	coordinatorAddr string

	// Transaction state
	transactions      map[string]*Transaction
	participantStates map[string]*ParticipantState

	// Key-value store
	kvStore map[string]string

	// Locks for concurrency control
	keyLocks map[string]string // key -> transaction_id

	// Synchronization
	mu sync.RWMutex

	// gRPC clients
	participantStubs map[string]pb.ParticipantServiceClient
	coordinatorStub  pb.CoordinatorServiceClient
}

// NewTwoPhaseCommitNode creates a new 2PC node
func NewTwoPhaseCommitNode(nodeID string, port int, role NodeRole, participants []string, coordinator string) *TwoPhaseCommitNode {
	return &TwoPhaseCommitNode{
		nodeID:            nodeID,
		port:              port,
		role:              role,
		participants:      participants,
		coordinatorAddr:   coordinator,
		transactions:      make(map[string]*Transaction),
		participantStates: make(map[string]*ParticipantState),
		kvStore:           make(map[string]string),
		keyLocks:          make(map[string]string),
		participantStubs:  make(map[string]pb.ParticipantServiceClient),
	}
}

// Initialize sets up connections to other nodes
func (n *TwoPhaseCommitNode) Initialize() error {
	if n.role == Coordinator {
		for _, participant := range n.participants {
			conn, err := grpc.Dial(participant, grpc.WithTransportCredentials(insecure.NewCredentials()))
			if err != nil {
				log.Printf("Warning: Failed to connect to participant %s: %v", participant, err)
				continue
			}
			n.participantStubs[participant] = pb.NewParticipantServiceClient(conn)
		}
		log.Printf("Coordinator %s initialized with participants: %v", n.nodeID, n.participants)
	} else {
		if n.coordinatorAddr != "" {
			conn, err := grpc.Dial(n.coordinatorAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
			if err != nil {
				log.Printf("Warning: Failed to connect to coordinator: %v", err)
			} else {
				n.coordinatorStub = pb.NewCoordinatorServiceClient(conn)
			}
		}
		log.Printf("Participant %s initialized with coordinator: %s", n.nodeID, n.coordinatorAddr)
	}
	return nil
}

// =============================================================================
// Coordinator Methods
// =============================================================================

// BeginTransaction starts a new distributed transaction
func (n *TwoPhaseCommitNode) BeginTransaction(ctx context.Context, req *pb.BeginTransactionRequest) (*pb.BeginTransactionResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	txnID := uuid.New().String()

	// TODO: Implement transaction initialization
	n.transactions[txnID] = &Transaction{
		ID:               txnID,
		State:            StateActive,
		Participants:     n.participants,
		Operations:       make(map[string][]Operation),
		ParticipantVotes: make(map[string]bool),
		TimeoutMs:        5000,
	}

	return &pb.BeginTransactionResponse{
		Success:       true,
		TransactionId: txnID,
	}, nil
}

// CommitTransaction commits using 2PC protocol
//
// TODO: Implement the Two-Phase Commit protocol:
// Phase 1 (Prepare):
// 1. Send Prepare to all participants
// 2. Wait for all votes (with timeout)
// 3. If all vote COMMIT, proceed to Phase 2 commit
// 4. If any vote ABORT or timeout, proceed to Phase 2 abort
//
// Phase 2 (Commit/Abort):
// 1. Send Commit or Abort to all participants
// 2. Wait for acknowledgments
// 3. Mark transaction as complete
func (n *TwoPhaseCommitNode) CommitTransaction(ctx context.Context, req *pb.CommitTransactionRequest) (*pb.CommitTransactionResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	txnID := req.TransactionId
	txn, exists := n.transactions[txnID]
	if !exists {
		return &pb.CommitTransactionResponse{
			Success: false,
			Error:   "Transaction not found",
		}, nil
	}

	// TODO: Implement 2PC protocol
	_ = txn
	return &pb.CommitTransactionResponse{
		Success: false,
		Error:   "Not implemented",
	}, nil
}

// AbortTransaction aborts a distributed transaction
func (n *TwoPhaseCommitNode) AbortTransaction(ctx context.Context, req *pb.AbortTransactionRequest) (*pb.AbortTransactionResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	// TODO: Implement abort logic
	return &pb.AbortTransactionResponse{
		Success: true,
	}, nil
}

// ExecuteOperation executes an operation within a transaction
func (n *TwoPhaseCommitNode) ExecuteOperation(ctx context.Context, req *pb.ExecuteOperationRequest) (*pb.ExecuteOperationResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	// TODO: Implement operation execution
	return &pb.ExecuteOperationResponse{
		Success: false,
		Error:   "Not implemented",
	}, nil
}

// GetTransactionStatus returns the status of a transaction
func (n *TwoPhaseCommitNode) GetTransactionStatus(ctx context.Context, req *pb.GetTransactionStatusRequest) (*pb.GetTransactionStatusResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	txn, exists := n.transactions[req.TransactionId]
	if !exists {
		return &pb.GetTransactionStatusResponse{Found: false}, nil
	}

	return &pb.GetTransactionStatusResponse{
		Found:         true,
		TransactionId: txn.ID,
		State:         pb.TransactionState(txn.State),
		Participants:  txn.Participants,
	}, nil
}

// =============================================================================
// Participant Methods
// =============================================================================

// Prepare handles the prepare phase
//
// TODO: Implement prepare phase:
// 1. Check if all operations can be executed
// 2. Acquire necessary locks
// 3. Write to WAL (prepare record)
// 4. Vote COMMIT if ready, ABORT otherwise
func (n *TwoPhaseCommitNode) Prepare(ctx context.Context, req *pb.PrepareRequest) (*pb.PrepareResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	// TODO: Implement prepare logic
	return &pb.PrepareResponse{
		Vote: false, // VOTE_ABORT
	}, nil
}

// Commit handles the commit phase
func (n *TwoPhaseCommitNode) Commit(ctx context.Context, req *pb.CommitRequest) (*pb.CommitResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	// TODO: Implement commit logic
	return &pb.CommitResponse{
		Success: true,
	}, nil
}

// Abort handles the abort phase
func (n *TwoPhaseCommitNode) Abort(ctx context.Context, req *pb.AbortRequest) (*pb.AbortResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	// TODO: Implement abort logic
	return &pb.AbortResponse{
		Success: true,
	}, nil
}

// GetStatus returns participant's view of a transaction
func (n *TwoPhaseCommitNode) GetStatus(ctx context.Context, req *pb.GetStatusRequest) (*pb.GetStatusResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	state, exists := n.participantStates[req.TransactionId]
	if !exists {
		return &pb.GetStatusResponse{Found: false}, nil
	}

	return &pb.GetStatusResponse{
		Found: true,
		State: pb.TransactionState(state.State),
	}, nil
}

// ExecuteLocal executes an operation locally
func (n *TwoPhaseCommitNode) ExecuteLocal(ctx context.Context, req *pb.ExecuteLocalRequest) (*pb.ExecuteLocalResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	// TODO: Implement local execution
	return &pb.ExecuteLocalResponse{
		Success: false,
		Error:   "Not implemented",
	}, nil
}

// =============================================================================
// KeyValueService RPC Implementations
// =============================================================================

func (n *TwoPhaseCommitNode) Get(ctx context.Context, req *pb.GetRequest) (*pb.GetResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	if value, ok := n.kvStore[req.Key]; ok {
		return &pb.GetResponse{Value: value, Found: true}, nil
	}
	return &pb.GetResponse{Found: false}, nil
}

func (n *TwoPhaseCommitNode) Put(ctx context.Context, req *pb.PutRequest) (*pb.PutResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	if n.role != Coordinator {
		return &pb.PutResponse{
			Success:         false,
			Error:           "Not the coordinator",
			CoordinatorHint: n.coordinatorAddr,
		}, nil
	}

	// TODO: Implement transactional put
	return &pb.PutResponse{
		Success: false,
		Error:   "Not implemented",
	}, nil
}

func (n *TwoPhaseCommitNode) Delete(ctx context.Context, req *pb.DeleteRequest) (*pb.DeleteResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	if n.role != Coordinator {
		return &pb.DeleteResponse{
			Success:         false,
			Error:           "Not the coordinator",
			CoordinatorHint: n.coordinatorAddr,
		}, nil
	}

	// TODO: Implement transactional delete
	return &pb.DeleteResponse{
		Success: false,
		Error:   "Not implemented",
	}, nil
}

func (n *TwoPhaseCommitNode) GetLeader(ctx context.Context, req *pb.GetLeaderRequest) (*pb.GetLeaderResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	return &pb.GetLeaderResponse{
		CoordinatorId:      n.nodeID,
		CoordinatorAddress: fmt.Sprintf("localhost:%d", n.port),
		IsCoordinator:      n.role == Coordinator,
	}, nil
}

func (n *TwoPhaseCommitNode) GetClusterStatus(ctx context.Context, req *pb.GetClusterStatusRequest) (*pb.GetClusterStatusResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	response := &pb.GetClusterStatusResponse{
		NodeId: n.nodeID,
		Role:   n.role.String(),
	}

	if n.role == Coordinator {
		for _, p := range n.participants {
			response.Members = append(response.Members, &pb.ClusterMember{
				Address: p,
				Role:    "participant",
			})
		}
	}

	return response, nil
}

// =============================================================================
// Main Entry Point
// =============================================================================

func main() {
	nodeID := flag.String("node-id", "", "Unique node identifier")
	port := flag.Int("port", 50051, "Port to listen on")
	roleStr := flag.String("role", "", "Node role (coordinator or participant)")
	participantsStr := flag.String("participants", "", "Comma-separated list of participant addresses")
	coordinator := flag.String("coordinator", "", "Coordinator address")
	flag.Parse()

	if *nodeID == "" || *roleStr == "" {
		log.Fatal("--node-id and --role are required")
	}

	var role NodeRole
	if *roleStr == "coordinator" {
		role = Coordinator
	} else {
		role = Participant
	}

	var participants []string
	if *participantsStr != "" {
		participants = strings.Split(*participantsStr, ",")
		for i, p := range participants {
			participants[i] = strings.TrimSpace(p)
		}
	}

	node := NewTwoPhaseCommitNode(*nodeID, *port, role, participants, *coordinator)
	if err := node.Initialize(); err != nil {
		log.Fatalf("Failed to initialize node: %v", err)
	}

	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	server := grpc.NewServer()

	if role == Coordinator {
		pb.RegisterCoordinatorServiceServer(server, node)
	} else {
		pb.RegisterParticipantServiceServer(server, node)
	}
	pb.RegisterKeyValueServiceServer(server, node)

	log.Printf("Starting 2PC %s node %s on port %d", *roleStr, *nodeID, *port)

	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
