// Chandy-Lamport Snapshot Algorithm Implementation - Go Template
//
// This template provides the basic structure for implementing the Chandy-Lamport
// algorithm for capturing consistent global snapshots.
//
// Based on: "Distributed Snapshots: Determining Global States of Distributed Systems"
// by K. Mani Chandy and Leslie Lamport (1985)
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

	"github.com/google/uuid"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	pb "github.com/sdp/snapshot"
)

// ChannelState holds messages recorded on a channel during snapshot
type ChannelState struct {
	FromProcess string
	ToProcess   string
	Messages    []*pb.ApplicationMessage
	IsRecording bool
}

// SnapshotState holds state for an ongoing snapshot
type SnapshotState struct {
	SnapshotID        string
	InitiatorID       string
	LocalStateRecorded bool
	LogicalClock      uint64
	AccountBalances   map[string]int64
	KVState           map[string]string
	ChannelStates     map[string]*ChannelState
	MarkersReceived   map[string]bool
	RecordingComplete bool
	InitiatedAt       time.Time
	CompletedAt       time.Time
}

// ChandyLamportNode implements the Chandy-Lamport snapshot algorithm
type ChandyLamportNode struct {
	pb.UnimplementedSnapshotServiceServer
	pb.UnimplementedBankServiceServer
	pb.UnimplementedKeyValueServiceServer

	nodeID string
	port   int
	peers  []string

	// Logical clock
	logicalClock uint64

	// Snapshot state
	snapshots         map[string]*SnapshotState
	currentSnapshotID string

	// Application state
	accountBalances map[string]int64
	kvStore         map[string]string

	// Statistics
	snapshotsInitiated    uint64
	snapshotsParticipated uint64

	// Synchronization
	mu sync.RWMutex

	// gRPC clients
	peerClients map[string]pb.SnapshotServiceClient
}

// NewChandyLamportNode creates a new node
func NewChandyLamportNode(nodeID string, port int, peers []string) *ChandyLamportNode {
	return &ChandyLamportNode{
		nodeID:          nodeID,
		port:            port,
		peers:           peers,
		snapshots:       make(map[string]*SnapshotState),
		accountBalances: map[string]int64{nodeID + "_account": 1000},
		kvStore:         make(map[string]string),
		peerClients:     make(map[string]pb.SnapshotServiceClient),
	}
}

// Initialize sets up connections
func (n *ChandyLamportNode) Initialize() error {
	for _, peer := range n.peers {
		conn, err := grpc.Dial(peer, grpc.WithTransportCredentials(insecure.NewCredentials()))
		if err != nil {
			log.Printf("Warning: Failed to connect to peer %s: %v", peer, err)
			continue
		}
		n.peerClients[peer] = pb.NewSnapshotServiceClient(conn)
	}
	log.Printf("Node %s initialized with peers: %v", n.nodeID, n.peers)
	return nil
}

func (n *ChandyLamportNode) incrementClock() uint64 {
	n.logicalClock++
	return n.logicalClock
}

func (n *ChandyLamportNode) updateClock(received uint64) {
	if received > n.logicalClock {
		n.logicalClock = received
	}
	n.logicalClock++
}

// InitiateSnapshot starts a new global snapshot
func (n *ChandyLamportNode) InitiateSnapshot(ctx context.Context, req *pb.InitiateSnapshotRequest) (*pb.InitiateSnapshotResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	snapshotID := req.SnapshotId
	if snapshotID == "" {
		snapshotID = uuid.New().String()
	}

	// TODO: Implement snapshot initiation
	// - Record local state
	// - Create SnapshotState
	// - Start recording on all incoming channels
	// - Send markers to all peers

	n.snapshotsInitiated++

	return &pb.InitiateSnapshotResponse{
		Success:     true,
		SnapshotId:  snapshotID,
		InitiatedAt: uint64(time.Now().UnixMilli()),
	}, nil
}

// ReceiveMarker handles incoming marker
func (n *ChandyLamportNode) ReceiveMarker(ctx context.Context, req *pb.MarkerMessage) (*pb.MarkerResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	n.updateClock(req.LogicalClock)
	snapshotID := req.SnapshotId
	firstMarker := n.snapshots[snapshotID] == nil

	if firstMarker {
		// TODO: First marker handling
		n.snapshotsParticipated++
	} else {
		// TODO: Subsequent marker handling
	}

	return &pb.MarkerResponse{
		Success:     true,
		FirstMarker: firstMarker,
		ProcessId:   n.nodeID,
	}, nil
}

// SendMessage handles application messages
func (n *ChandyLamportNode) SendMessage(ctx context.Context, req *pb.ApplicationMessage) (*pb.SendMessageResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	n.incrementClock()
	return &pb.SendMessageResponse{Success: true}, nil
}

// GetSnapshot returns local snapshot state
func (n *ChandyLamportNode) GetSnapshot(ctx context.Context, req *pb.GetSnapshotRequest) (*pb.GetSnapshotResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	snapshot, exists := n.snapshots[req.SnapshotId]
	if !exists {
		return &pb.GetSnapshotResponse{Found: false}, nil
	}

	localState := &pb.ProcessState{
		ProcessId:       n.nodeID,
		LogicalClock:    snapshot.LogicalClock,
		AccountBalances: snapshot.AccountBalances,
		KvState:         snapshot.KVState,
	}

	var channelStates []*pb.ChannelState
	for _, cs := range snapshot.ChannelStates {
		channelStates = append(channelStates, &pb.ChannelState{
			FromProcess: cs.FromProcess,
			ToProcess:   cs.ToProcess,
			Messages:    cs.Messages,
		})
	}

	return &pb.GetSnapshotResponse{
		Found:             true,
		SnapshotId:        req.SnapshotId,
		LocalState:        localState,
		ChannelStates:     channelStates,
		RecordingComplete: snapshot.RecordingComplete,
	}, nil
}

// GetGlobalSnapshot collects global snapshot
func (n *ChandyLamportNode) GetGlobalSnapshot(ctx context.Context, req *pb.GetGlobalSnapshotRequest) (*pb.GetGlobalSnapshotResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	if _, exists := n.snapshots[req.SnapshotId]; !exists {
		return &pb.GetGlobalSnapshotResponse{Success: false, Error: "Snapshot not found"}, nil
	}

	// TODO: Collect from all peers
	return &pb.GetGlobalSnapshotResponse{Success: false, Error: "Not implemented"}, nil
}

// Bank service methods
func (n *ChandyLamportNode) GetBalance(ctx context.Context, req *pb.GetBalanceRequest) (*pb.GetBalanceResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	if balance, ok := n.accountBalances[req.AccountId]; ok {
		return &pb.GetBalanceResponse{Balance: balance, Found: true}, nil
	}
	return &pb.GetBalanceResponse{Found: false}, nil
}

func (n *ChandyLamportNode) Transfer(ctx context.Context, req *pb.TransferRequest) (*pb.TransferResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	if _, ok := n.accountBalances[req.FromAccount]; !ok {
		return &pb.TransferResponse{Success: false, Error: "Source account not found"}, nil
	}
	if n.accountBalances[req.FromAccount] < req.Amount {
		return &pb.TransferResponse{Success: false, Error: "Insufficient funds"}, nil
	}

	n.accountBalances[req.FromAccount] -= req.Amount
	n.accountBalances[req.ToAccount] += req.Amount

	return &pb.TransferResponse{
		Success:     true,
		FromBalance: n.accountBalances[req.FromAccount],
		ToBalance:   n.accountBalances[req.ToAccount],
	}, nil
}

func (n *ChandyLamportNode) Deposit(ctx context.Context, req *pb.DepositRequest) (*pb.DepositResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	n.accountBalances[req.AccountId] += req.Amount
	return &pb.DepositResponse{Success: true, NewBalance: n.accountBalances[req.AccountId]}, nil
}

func (n *ChandyLamportNode) Withdraw(ctx context.Context, req *pb.WithdrawRequest) (*pb.WithdrawResponse, error) {
	return &pb.WithdrawResponse{Success: false, Error: "Not implemented"}, nil
}

// KeyValue service methods
func (n *ChandyLamportNode) Get(ctx context.Context, req *pb.GetRequest) (*pb.GetResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	if value, ok := n.kvStore[req.Key]; ok {
		return &pb.GetResponse{Value: value, Found: true}, nil
	}
	return &pb.GetResponse{Found: false}, nil
}

func (n *ChandyLamportNode) Put(ctx context.Context, req *pb.PutRequest) (*pb.PutResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	n.kvStore[req.Key] = req.Value
	return &pb.PutResponse{Success: true}, nil
}

func (n *ChandyLamportNode) Delete(ctx context.Context, req *pb.DeleteRequest) (*pb.DeleteResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	delete(n.kvStore, req.Key)
	return &pb.DeleteResponse{Success: true}, nil
}

func (n *ChandyLamportNode) GetLeader(ctx context.Context, req *pb.GetLeaderRequest) (*pb.GetLeaderResponse, error) {
	return &pb.GetLeaderResponse{InitiatorId: n.nodeID, IsInitiator: true}, nil
}

func (n *ChandyLamportNode) GetClusterStatus(ctx context.Context, req *pb.GetClusterStatusRequest) (*pb.GetClusterStatusResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	var members []*pb.ClusterMember
	for _, peer := range n.peers {
		members = append(members, &pb.ClusterMember{Address: peer, IsHealthy: true})
	}

	return &pb.GetClusterStatusResponse{
		NodeId:               n.nodeID,
		LogicalClock:         n.logicalClock,
		IsRecording:          n.currentSnapshotID != "",
		CurrentSnapshotId:    n.currentSnapshotID,
		SnapshotsInitiated:   n.snapshotsInitiated,
		SnapshotsParticipated: n.snapshotsParticipated,
		Members:              members,
	}, nil
}

func main() {
	nodeID := flag.String("node-id", "", "Unique node identifier")
	port := flag.Int("port", 50051, "Port to listen on")
	peersStr := flag.String("peers", "", "Comma-separated list of peer addresses")
	flag.Parse()

	if *nodeID == "" || *peersStr == "" {
		log.Fatal("--node-id and --peers are required")
	}

	peers := strings.Split(*peersStr, ",")
	for i, p := range peers {
		peers[i] = strings.TrimSpace(p)
	}

	node := NewChandyLamportNode(*nodeID, *port, peers)
	if err := node.Initialize(); err != nil {
		log.Fatalf("Failed to initialize: %v", err)
	}

	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	server := grpc.NewServer()
	pb.RegisterSnapshotServiceServer(server, node)
	pb.RegisterBankServiceServer(server, node)
	pb.RegisterKeyValueServiceServer(server, node)

	log.Printf("Starting Chandy-Lamport node %s on port %d", *nodeID, *port)

	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
