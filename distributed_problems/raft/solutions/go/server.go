// Raft Consensus Implementation - Go Solution
//
// A complete implementation of the Raft consensus algorithm supporting:
// - Leader election with randomized timeouts
// - Log replication with consistency guarantees
// - Heartbeat mechanism for leader authority
// - Key-value store as the state machine
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
	mu               sync.RWMutex
	electionDeadline time.Time
	applyCond        *sync.Cond
	stopChan         chan struct{}

	// gRPC clients for peer communication
	peerClients map[string]pb.RaftServiceClient
}

// NewRaftNode creates a new Raft node
func NewRaftNode(nodeID string, port int, peers []string) *RaftNode {
	node := &RaftNode{
		nodeID: nodeID,
		port:   port,
		peers:  peers,
		state: RaftState{
			NextIndex:  make(map[string]uint64),
			MatchIndex: make(map[string]uint64),
			Log:        []LogEntry{{Index: 0, Term: 0}}, // Dummy entry at index 0
		},
		nodeState:          Follower,
		kvStore:            make(map[string]string),
		electionTimeoutMin: 150 * time.Millisecond,
		electionTimeoutMax: 300 * time.Millisecond,
		heartbeatInterval:  50 * time.Millisecond,
		peerClients:        make(map[string]pb.RaftServiceClient),
		stopChan:           make(chan struct{}),
	}
	node.applyCond = sync.NewCond(&node.mu)
	return node
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

func (n *RaftNode) randomTimeout() time.Duration {
	return n.electionTimeoutMin + time.Duration(rand.Int63n(int64(n.electionTimeoutMax-n.electionTimeoutMin)))
}

// ResetElectionTimer resets the election timeout with a random duration
func (n *RaftNode) ResetElectionTimer() {
	n.electionDeadline = time.Now().Add(n.randomTimeout())
}

// StepDown transitions to follower state when we see a higher term
func (n *RaftNode) StepDown(newTerm uint64) {
	n.state.CurrentTerm = newTerm
	n.state.VotedFor = ""
	n.nodeState = Follower
	n.ResetElectionTimer()
}

// ElectionTimerLoop runs the election timer in a background goroutine
func (n *RaftNode) ElectionTimerLoop() {
	n.mu.Lock()
	n.ResetElectionTimer()
	n.mu.Unlock()

	for {
		select {
		case <-n.stopChan:
			return
		case <-time.After(10 * time.Millisecond):
			n.mu.Lock()
			if n.nodeState != Leader && time.Now().After(n.electionDeadline) {
				n.StartElection()
			}
			n.mu.Unlock()
		}
	}
}

// StartElection starts a new leader election
//
// Implementation:
// 1. Increment current_term
// 2. Change state to CANDIDATE
// 3. Vote for self
// 4. Reset election timer
// 5. Send RequestVote RPCs to all peers in parallel
// 6. If votes received from majority, become leader
func (n *RaftNode) StartElection() {
	n.nodeState = Candidate
	n.state.CurrentTerm++
	n.state.VotedFor = n.nodeID
	n.ResetElectionTimer()

	term := n.state.CurrentTerm
	lastIdx := n.GetLastLogIndex()
	lastTerm := n.GetLastLogTerm()

	log.Printf("Node %s starting election for term %d", n.nodeID, term)

	votesReceived := 1
	majority := (len(n.peers)+1)/2 + 1

	var wg sync.WaitGroup
	var voteMu sync.Mutex

	for _, peer := range n.peers {
		wg.Add(1)
		go func(p string) {
			defer wg.Done()

			ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
			defer cancel()

			resp, err := n.peerClients[p].RequestVote(ctx, &pb.RequestVoteRequest{
				Term:         term,
				CandidateId:  n.nodeID,
				LastLogIndex: lastIdx,
				LastLogTerm:  lastTerm,
			})

			if err != nil {
				return
			}

			n.mu.Lock()
			defer n.mu.Unlock()

			if resp.Term > n.state.CurrentTerm {
				n.StepDown(resp.Term)
				return
			}

			if n.nodeState == Candidate && resp.VoteGranted && term == n.state.CurrentTerm {
				voteMu.Lock()
				votesReceived++
				if votesReceived >= majority {
					n.BecomeLeader()
				}
				voteMu.Unlock()
			}
		}(peer)
	}

	go func() {
		wg.Wait()
	}()
}

// BecomeLeader transitions to leader state
func (n *RaftNode) BecomeLeader() {
	if n.nodeState != Candidate {
		return
	}
	n.nodeState = Leader
	n.leaderID = n.nodeID
	log.Printf("Node %s became leader for term %d", n.nodeID, n.state.CurrentTerm)

	// Initialize leader state (next_index and match_index for all peers)
	for _, peer := range n.peers {
		n.state.NextIndex[peer] = n.GetLastLogIndex() + 1
		n.state.MatchIndex[peer] = 0
	}
}

// HeartbeatLoop sends heartbeats as leader in a background goroutine
func (n *RaftNode) HeartbeatLoop() {
	for {
		select {
		case <-n.stopChan:
			return
		case <-time.After(n.heartbeatInterval):
			n.mu.Lock()
			if n.nodeState == Leader {
				n.SendAppendEntriesToAll()
			}
			n.mu.Unlock()
		}
	}
}

// SendAppendEntriesToAll sends AppendEntries (heartbeats or log replication) to all peers
func (n *RaftNode) SendAppendEntriesToAll() {
	for _, peer := range n.peers {
		go func(p string) {
			n.mu.RLock()
			nextIdx := n.state.NextIndex[p]
			prevIdx := nextIdx - 1
			var prevTerm uint64
			if prevIdx < uint64(len(n.state.Log)) {
				prevTerm = n.state.Log[prevIdx].Term
			}

			// Build entries to send
			var entries []*pb.LogEntry
			for i := nextIdx; i < uint64(len(n.state.Log)); i++ {
				entry := n.state.Log[i]
				entries = append(entries, &pb.LogEntry{
					Index:       entry.Index,
					Term:        entry.Term,
					Command:     entry.Command,
					CommandType: entry.CommandType,
				})
			}

			req := &pb.AppendEntriesRequest{
				Term:         n.state.CurrentTerm,
				LeaderId:     n.nodeID,
				PrevLogIndex: prevIdx,
				PrevLogTerm:  prevTerm,
				Entries:      entries,
				LeaderCommit: n.state.CommitIndex,
			}
			term := n.state.CurrentTerm
			n.mu.RUnlock()

			ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
			defer cancel()

			resp, err := n.peerClients[p].AppendEntries(ctx, req)
			if err != nil {
				return
			}

			n.mu.Lock()
			defer n.mu.Unlock()

			if resp.Term > n.state.CurrentTerm {
				n.StepDown(resp.Term)
				return
			}

			if n.nodeState == Leader && term == n.state.CurrentTerm {
				if resp.Success {
					n.state.NextIndex[p] = prevIdx + uint64(len(entries)) + 1
					n.state.MatchIndex[p] = n.state.NextIndex[p] - 1
					n.UpdateCommitIndex()
				} else {
					// Decrement next_index and retry
					if n.state.NextIndex[p] > 1 {
						n.state.NextIndex[p]--
					}
				}
			}
		}(peer)
	}
}

// UpdateCommitIndex updates commit index based on majority replication
func (n *RaftNode) UpdateCommitIndex() {
	for i := n.state.CommitIndex + 1; i < uint64(len(n.state.Log)); i++ {
		if n.state.Log[i].Term != n.state.CurrentTerm {
			continue
		}
		count := 1 // Count self
		for _, peer := range n.peers {
			if n.state.MatchIndex[peer] >= i {
				count++
			}
		}
		if count >= (len(n.peers)+1)/2+1 {
			n.state.CommitIndex = i
			n.ApplyToStateMachine()
		}
	}
}

// ApplyToStateMachine applies committed entries to state machine (key-value store)
func (n *RaftNode) ApplyToStateMachine() {
	for n.state.LastApplied < n.state.CommitIndex {
		n.state.LastApplied++
		entry := n.state.Log[n.state.LastApplied]
		n.ApplyCommand(entry.Command, entry.CommandType)
	}
	n.applyCond.Broadcast()
}

// ApplyCommand applies a command to the state machine
func (n *RaftNode) ApplyCommand(command []byte, commandType string) {
	cmd := string(command)
	if commandType == "put" {
		idx := strings.Index(cmd, ":")
		if idx != -1 {
			key, value := cmd[:idx], cmd[idx+1:]
			n.kvStore[key] = value
			log.Printf("Applied PUT %s=%s", key, value)
		}
	} else if commandType == "delete" {
		delete(n.kvStore, cmd)
		log.Printf("Applied DELETE %s", cmd)
	}
}

// =============================================================================
// RaftService RPC Implementations
// =============================================================================

// RequestVote handles RequestVote RPC from a candidate
//
// Per Raft specification:
// 1. Reply false if term < currentTerm
// 2. If votedFor is null or candidateId, and candidate's log is at
//    least as up-to-date as receiver's log, grant vote
func (n *RaftNode) RequestVote(ctx context.Context, req *pb.RequestVoteRequest) (*pb.RequestVoteResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	if req.Term > n.state.CurrentTerm {
		n.StepDown(req.Term)
	}

	// Check if candidate's log is at least as up-to-date
	logOk := req.LastLogTerm > n.GetLastLogTerm() ||
		(req.LastLogTerm == n.GetLastLogTerm() && req.LastLogIndex >= n.GetLastLogIndex())

	voteGranted := false
	if req.Term == n.state.CurrentTerm && logOk &&
		(n.state.VotedFor == "" || n.state.VotedFor == req.CandidateId) {
		n.state.VotedFor = req.CandidateId
		voteGranted = true
		n.ResetElectionTimer()
		log.Printf("Voted for %s in term %d", req.CandidateId, req.Term)
	}

	return &pb.RequestVoteResponse{
		Term:        n.state.CurrentTerm,
		VoteGranted: voteGranted,
	}, nil
}

// AppendEntries handles AppendEntries RPC from leader
//
// Per Raft specification:
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

	if req.Term > n.state.CurrentTerm {
		n.StepDown(req.Term)
	}

	if req.Term < n.state.CurrentTerm {
		return &pb.AppendEntriesResponse{
			Term:       n.state.CurrentTerm,
			Success:    false,
			MatchIndex: n.GetLastLogIndex(),
		}, nil
	}

	// Valid leader - reset election timer
	n.leaderID = req.LeaderId
	n.nodeState = Follower
	n.ResetElectionTimer()

	// Check log consistency
	if req.PrevLogIndex >= uint64(len(n.state.Log)) ||
		n.state.Log[req.PrevLogIndex].Term != req.PrevLogTerm {
		return &pb.AppendEntriesResponse{
			Term:       n.state.CurrentTerm,
			Success:    false,
			MatchIndex: n.GetLastLogIndex(),
		}, nil
	}

	// Append new entries (handling conflicts)
	logPtr := req.PrevLogIndex + 1
	for _, entry := range req.Entries {
		if logPtr < uint64(len(n.state.Log)) {
			if n.state.Log[logPtr].Term != entry.Term {
				// Conflict - delete this and all following entries
				n.state.Log = n.state.Log[:logPtr]
			}
		}
		if logPtr >= uint64(len(n.state.Log)) {
			n.state.Log = append(n.state.Log, LogEntry{
				Index:       entry.Index,
				Term:        entry.Term,
				Command:     entry.Command,
				CommandType: entry.CommandType,
			})
		}
		logPtr++
	}

	// Update commit index
	if req.LeaderCommit > n.state.CommitIndex {
		if req.LeaderCommit < n.GetLastLogIndex() {
			n.state.CommitIndex = req.LeaderCommit
		} else {
			n.state.CommitIndex = n.GetLastLogIndex()
		}
		n.ApplyToStateMachine()
	}

	return &pb.AppendEntriesResponse{
		Term:       n.state.CurrentTerm,
		Success:    true,
		MatchIndex: n.GetLastLogIndex(),
	}, nil
}

// InstallSnapshot handles InstallSnapshot RPC from leader
//
// Basic implementation - in production this would handle:
// 1. Saving snapshot data
// 2. Discarding old log entries
// 3. Resetting state machine from snapshot
func (n *RaftNode) InstallSnapshot(ctx context.Context, req *pb.InstallSnapshotRequest) (*pb.InstallSnapshotResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	if req.Term > n.state.CurrentTerm {
		n.StepDown(req.Term)
	}

	return &pb.InstallSnapshotResponse{Term: n.state.CurrentTerm}, nil
}

// =============================================================================
// KeyValueService RPC Implementations
// =============================================================================

// Get returns value for key from state machine
func (n *RaftNode) Get(ctx context.Context, req *pb.GetRequest) (*pb.GetResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	if value, ok := n.kvStore[req.Key]; ok {
		return &pb.GetResponse{Value: value, Found: true}, nil
	}
	return &pb.GetResponse{Found: false}, nil
}

// Put stores key-value pair (requires consensus)
//
// Implementation:
// 1. If not leader, return leader_hint
// 2. Append entry to local log
// 3. Replicate to followers via AppendEntries
// 4. Once committed (majority replicated), apply to state machine
// 5. Return success to client
func (n *RaftNode) Put(ctx context.Context, req *pb.PutRequest) (*pb.PutResponse, error) {
	n.mu.Lock()

	if n.nodeState != Leader {
		leaderID := n.leaderID
		n.mu.Unlock()
		return &pb.PutResponse{
			Success:    false,
			Error:      "Not the leader",
			LeaderHint: leaderID,
		}, nil
	}

	// Append to log
	entry := LogEntry{
		Index:       n.GetLastLogIndex() + 1,
		Term:        n.state.CurrentTerm,
		Command:     []byte(req.Key + ":" + req.Value),
		CommandType: "put",
	}
	n.state.Log = append(n.state.Log, entry)
	waitIdx := entry.Index

	// Wait for commit
	for n.state.LastApplied < waitIdx && n.nodeState == Leader {
		n.applyCond.Wait()
	}

	success := n.state.LastApplied >= waitIdx
	n.mu.Unlock()

	return &pb.PutResponse{Success: success}, nil
}

// Delete removes key (requires consensus)
//
// Similar to put - uses consensus for the delete operation
func (n *RaftNode) Delete(ctx context.Context, req *pb.DeleteRequest) (*pb.DeleteResponse, error) {
	n.mu.Lock()

	if n.nodeState != Leader {
		leaderID := n.leaderID
		n.mu.Unlock()
		return &pb.DeleteResponse{
			Success:    false,
			Error:      "Not the leader",
			LeaderHint: leaderID,
		}, nil
	}

	entry := LogEntry{
		Index:       n.GetLastLogIndex() + 1,
		Term:        n.state.CurrentTerm,
		Command:     []byte(req.Key),
		CommandType: "delete",
	}
	n.state.Log = append(n.state.Log, entry)
	waitIdx := entry.Index

	// Wait for commit
	for n.state.LastApplied < waitIdx && n.nodeState == Leader {
		n.applyCond.Wait()
	}

	success := n.state.LastApplied >= waitIdx
	n.mu.Unlock()

	return &pb.DeleteResponse{Success: success}, nil
}

// GetLeader returns current leader information
func (n *RaftNode) GetLeader(ctx context.Context, req *pb.GetLeaderRequest) (*pb.GetLeaderResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	resp := &pb.GetLeaderResponse{
		LeaderId: n.leaderID,
		IsLeader: n.nodeState == Leader,
	}

	// Find leader address from peers
	for _, peer := range n.peers {
		if strings.Contains(peer, n.leaderID) {
			resp.LeaderAddress = peer
			break
		}
	}

	if n.nodeState == Leader {
		resp.LeaderAddress = fmt.Sprintf("localhost:%d", n.port)
	}

	return resp, nil
}

// GetClusterStatus returns cluster status information
func (n *RaftNode) GetClusterStatus(ctx context.Context, req *pb.GetClusterStatusRequest) (*pb.GetClusterStatusResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	resp := &pb.GetClusterStatusResponse{
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
		member := &pb.ClusterMember{Address: peer}
		if n.nodeState == Leader {
			member.MatchIndex = n.state.MatchIndex[peer]
			member.NextIndex = n.state.NextIndex[peer]
		}
		resp.Members = append(resp.Members, member)
	}

	return resp, nil
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

	// Start background loops
	go node.ElectionTimerLoop()
	go node.HeartbeatLoop()

	log.Printf("Starting Raft node %s on port %d", *nodeID, *port)
	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
