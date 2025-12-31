// Raft Consensus Implementation - Go Template
//
// This template provides the basic structure for implementing the Raft
// consensus algorithm. You need to implement the TODO sections.
//
// For the full Raft specification, see: https://raft.github.io/raft.pdf
//
// Usage:
//     go run server.go --node-id node1 --port 50051 --peers node2:50052,node3:50053

package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"math/rand"
	"net"
	"strings"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"

	pb "github.com/sdp/raft"
)

// NodeState represents the state of a Raft node
type NodeState int

const (
	Follower NodeState = iota
	Candidate
	Leader
)

func (s NodeState) String() string {
	switch s {
	case Follower:
		return "follower"
	case Candidate:
		return "candidate"
	case Leader:
		return "leader"
	default:
		return "unknown"
	}
}

// LogEntry represents an entry in the Raft log
type LogEntry struct {
	Index       uint64
	Term        uint64
	Command     []byte
	CommandType string
}

// RaftState holds the persistent and volatile state for a Raft node
type RaftState struct {
	// Persistent state (should be saved to disk in production)
	CurrentTerm uint64
	VotedFor    string
	Log         []LogEntry

	// Volatile state on all servers
	CommitIndex uint64
	LastApplied uint64

	// Volatile state on leaders (reinitialized after election)
	NextIndex  map[string]uint64
	MatchIndex map[string]uint64
}

// RaftNode implements the Raft consensus algorithm
type RaftNode struct {
	pb.UnimplementedRaftServiceServer
	pb.UnimplementedKeyValueServiceServer

	nodeID    string
	port      int
	peers     []string
	state     RaftState
	nodeState NodeState
	leaderID  string

	// Key-value store (state machine)
	kvStore map[string]string

	// Timing configuration
	electionTimeoutMin time.Duration
	electionTimeoutMax time.Duration
	heartbeatInterval  time.Duration

	// Synchronization
	mu            sync.RWMutex
	electionTimer *time.Timer

	// gRPC clients for peer communication
	peerClients map[string]pb.RaftServiceClient
}

// NewRaftNode creates a new Raft node
func NewRaftNode(nodeID string, port int, peers []string) *RaftNode {
	return &RaftNode{
		nodeID:    nodeID,
		port:      port,
		peers:     peers,
		state: RaftState{
			NextIndex:  make(map[string]uint64),
			MatchIndex: make(map[string]uint64),
		},
		nodeState:          Follower,
		kvStore:            make(map[string]string),
		electionTimeoutMin: 150 * time.Millisecond,
		electionTimeoutMax: 300 * time.Millisecond,
		heartbeatInterval:  50 * time.Millisecond,
		peerClients:        make(map[string]pb.RaftServiceClient),
	}
}

// Initialize sets up connections to peer nodes
func (n *RaftNode) Initialize() error {
	for _, peer := range n.peers {
		var conn *grpc.ClientConn
		var err error

		// Cloud Run URLs require TLS credentials
		if strings.Contains(peer, ".run.app") {
			// Use TLS for Cloud Run endpoints
			creds := credentials.NewClientTLSFromCert(nil, "")
			conn, err = grpc.Dial(peer, grpc.WithTransportCredentials(creds))
			log.Printf("Using TLS for peer: %s", peer)
		} else {
			// Use insecure credentials for local development
			conn, err = grpc.Dial(peer, grpc.WithTransportCredentials(insecure.NewCredentials()))
			log.Printf("Using insecure channel for peer: %s", peer)
		}

		if err != nil {
			log.Printf("Warning: Failed to connect to peer %s: %v", peer, err)
			continue
		}
		n.peerClients[peer] = pb.NewRaftServiceClient(conn)
	}
	log.Printf("Node %s initialized with peers: %v", n.nodeID, n.peers)
	return nil
}

// GetLastLogIndex returns the index of the last log entry
func (n *RaftNode) GetLastLogIndex() uint64 {
	if len(n.state.Log) == 0 {
		return 0
	}
	return n.state.Log[len(n.state.Log)-1].Index
}

// GetLastLogTerm returns the term of the last log entry
func (n *RaftNode) GetLastLogTerm() uint64 {
	if len(n.state.Log) == 0 {
		return 0
	}
	return n.state.Log[len(n.state.Log)-1].Term
}

// ResetElectionTimer resets the election timeout with a random duration
func (n *RaftNode) ResetElectionTimer() {
	// TODO: Implement election timer reset
	// - Stop any existing timer
	// - Start a new timer with random timeout between
	//   electionTimeoutMin and electionTimeoutMax
	// - When timer fires, call StartElection()
}

// StartElection starts a new leader election
//
// TODO: Implement the election process:
// 1. Increment current_term
// 2. Change state to CANDIDATE
// 3. Vote for self
// 4. Reset election timer
// 5. Send RequestVote RPCs to all peers in parallel
// 6. If votes received from majority, become leader
// 7. If AppendEntries received from new leader, become follower
// 8. If election timeout elapses, start new election
func (n *RaftNode) StartElection() {
}

// SendHeartbeats sends heartbeat AppendEntries RPCs to all followers
//
// TODO: Implement heartbeat mechanism:
// - Only run if this node is the leader
// - Send AppendEntries (empty for heartbeat) to all peers
// - Process responses to update match_index and next_index
// - Repeat at heartbeat_interval
func (n *RaftNode) SendHeartbeats() {
}

// ApplyCommand applies a command to the state machine
//
// TODO: Implement command application:
// - Parse the command
// - Apply to kvStore (put/delete operations)
func (n *RaftNode) ApplyCommand(command []byte, commandType string) {
}

// =============================================================================
// RaftService RPC Implementations
// =============================================================================

// RequestVote handles RequestVote RPC from a candidate
//
// TODO: Implement vote handling per Raft specification:
// 1. Reply false if term < currentTerm
// 2. If votedFor is null or candidateId, and candidate's log is at
//    least as up-to-date as receiver's log, grant vote
func (n *RaftNode) RequestVote(ctx context.Context, req *pb.RequestVoteRequest) (*pb.RequestVoteResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	response := &pb.RequestVoteResponse{
		Term:        n.state.CurrentTerm,
		VoteGranted: false,
	}

	// TODO: Implement voting logic

	return response, nil
}

// AppendEntries handles AppendEntries RPC from leader
//
// TODO: Implement log replication per Raft specification:
// 1. Reply false if term < currentTerm
// 2. Reply false if log doesn't contain an entry at prevLogIndex
//    whose term matches prevLogTerm
// 3. If an existing entry conflicts with a new one, delete the
//    existing entry and all that follow it
// 4. Append any new entries not already in the log
// 5. If leaderCommit > commitIndex, set commitIndex =
//    min(leaderCommit, index of last new entry)
func (n *RaftNode) AppendEntries(ctx context.Context, req *pb.AppendEntriesRequest) (*pb.AppendEntriesResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	response := &pb.AppendEntriesResponse{
		Term:       n.state.CurrentTerm,
		Success:    false,
		MatchIndex: n.GetLastLogIndex(),
	}

	// TODO: Implement AppendEntries logic

	return response, nil
}

// InstallSnapshot handles InstallSnapshot RPC from leader
//
// TODO: Implement snapshot installation
func (n *RaftNode) InstallSnapshot(ctx context.Context, req *pb.InstallSnapshotRequest) (*pb.InstallSnapshotResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	response := &pb.InstallSnapshotResponse{
		Term: n.state.CurrentTerm,
	}

	return response, nil
}

// =============================================================================
// KeyValueService RPC Implementations
// =============================================================================

// Get returns value for key from state machine
func (n *RaftNode) Get(ctx context.Context, req *pb.GetRequest) (*pb.GetResponse, error) {
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
// 2. Append entry to local log
// 3. Replicate to followers via AppendEntries
// 4. Once committed (majority replicated), apply to state machine
// 5. Return success to client
func (n *RaftNode) Put(ctx context.Context, req *pb.PutRequest) (*pb.PutResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	response := &pb.PutResponse{}
	if n.nodeState != Leader {
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
//
// TODO: Implement consensus-based delete (similar to put)
func (n *RaftNode) Delete(ctx context.Context, req *pb.DeleteRequest) (*pb.DeleteResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	response := &pb.DeleteResponse{}
	if n.nodeState != Leader {
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
func (n *RaftNode) GetLeader(ctx context.Context, req *pb.GetLeaderRequest) (*pb.GetLeaderResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	response := &pb.GetLeaderResponse{
		LeaderId: n.leaderID,
		IsLeader: n.nodeState == Leader,
	}

	// Find leader address from peers
	for _, peer := range n.peers {
		if strings.Contains(peer, n.leaderID) {
			response.LeaderAddress = peer
			break
		}
	}

	return response, nil
}

// GetClusterStatus returns cluster status information
func (n *RaftNode) GetClusterStatus(ctx context.Context, req *pb.GetClusterStatusRequest) (*pb.GetClusterStatusResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	response := &pb.GetClusterStatusResponse{
		NodeId:      n.nodeID,
		State:       n.nodeState.String(),
		CurrentTerm: n.state.CurrentTerm,
		VotedFor:    n.state.VotedFor,
		CommitIndex: n.state.CommitIndex,
		LastApplied: n.state.LastApplied,
		LogLength:   uint64(len(n.state.Log)),
		LastLogTerm: n.GetLastLogTerm(),
	}

	// Add cluster members
	for _, peer := range n.peers {
		member := &pb.ClusterMember{
			Address: peer,
		}
		if n.nodeState == Leader {
			member.MatchIndex = n.state.MatchIndex[peer]
			member.NextIndex = n.state.NextIndex[peer]
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

	// Seed random for election timeouts
	rand.Seed(time.Now().UnixNano())

	node := NewRaftNode(*nodeID, *port, peers)
	if err := node.Initialize(); err != nil {
		log.Fatalf("Failed to initialize node: %v", err)
	}

	// Create gRPC server
	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	server := grpc.NewServer()
	pb.RegisterRaftServiceServer(server, node)
	pb.RegisterKeyValueServiceServer(server, node)

	log.Printf("Starting Raft node %s on port %d", *nodeID, *port)

	// Start election timer
	node.ResetElectionTimer()

	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
