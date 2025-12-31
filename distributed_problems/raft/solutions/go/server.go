// Raft Consensus Implementation - Go Solution
//
// A complete implementation of the Raft consensus algorithm supporting:
// - Leader election with randomized timeouts
// - Log replication with consistency guarantees
// - Heartbeat mechanism for leader authority
// - Key-value store as the state machine
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
	"google.golang.org/grpc/credentials/insecure"

	pb "github.com/sdp/raft"
)

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

type LogEntry struct {
	Index       uint64
	Term        uint64
	Command     []byte
	CommandType string
}

type RaftState struct {
	CurrentTerm uint64
	VotedFor    string
	Log         []LogEntry
	CommitIndex uint64
	LastApplied uint64
	NextIndex   map[string]uint64
	MatchIndex  map[string]uint64
}

type RaftNode struct {
	pb.UnimplementedRaftServiceServer
	pb.UnimplementedKeyValueServiceServer

	nodeID    string
	port      int
	peers     []string
	state     RaftState
	nodeState NodeState
	leaderID  string

	kvStore map[string]string

	electionTimeoutMin time.Duration
	electionTimeoutMax time.Duration
	heartbeatInterval  time.Duration

	mu               sync.RWMutex
	electionDeadline time.Time
	applyCond        *sync.Cond
	stopChan         chan struct{}

	peerClients map[string]pb.RaftServiceClient
}

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

func (n *RaftNode) Initialize() error {
	for _, peer := range n.peers {
		conn, err := grpc.Dial(peer, grpc.WithTransportCredentials(insecure.NewCredentials()))
		if err != nil {
			log.Printf("Warning: Failed to connect to peer %s: %v", peer, err)
			continue
		}
		n.peerClients[peer] = pb.NewRaftServiceClient(conn)
	}
	log.Printf("Node %s initialized with peers: %v", n.nodeID, n.peers)
	return nil
}

func (n *RaftNode) GetLastLogIndex() uint64 {
	if len(n.state.Log) == 0 {
		return 0
	}
	return n.state.Log[len(n.state.Log)-1].Index
}

func (n *RaftNode) GetLastLogTerm() uint64 {
	if len(n.state.Log) == 0 {
		return 0
	}
	return n.state.Log[len(n.state.Log)-1].Term
}

func (n *RaftNode) randomTimeout() time.Duration {
	return n.electionTimeoutMin + time.Duration(rand.Int63n(int64(n.electionTimeoutMax-n.electionTimeoutMin)))
}

func (n *RaftNode) ResetElectionTimer() {
	n.electionDeadline = time.Now().Add(n.randomTimeout())
}

func (n *RaftNode) StepDown(newTerm uint64) {
	n.state.CurrentTerm = newTerm
	n.state.VotedFor = ""
	n.nodeState = Follower
	n.ResetElectionTimer()
}

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

func (n *RaftNode) BecomeLeader() {
	if n.nodeState != Candidate {
		return
	}
	n.nodeState = Leader
	n.leaderID = n.nodeID
	log.Printf("Node %s became leader for term %d", n.nodeID, n.state.CurrentTerm)

	for _, peer := range n.peers {
		n.state.NextIndex[peer] = n.GetLastLogIndex() + 1
		n.state.MatchIndex[peer] = 0
	}
}

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
					if n.state.NextIndex[p] > 1 {
						n.state.NextIndex[p]--
					}
				}
			}
		}(peer)
	}
}

func (n *RaftNode) UpdateCommitIndex() {
	for i := n.state.CommitIndex + 1; i < uint64(len(n.state.Log)); i++ {
		if n.state.Log[i].Term != n.state.CurrentTerm {
			continue
		}
		count := 1
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

func (n *RaftNode) ApplyToStateMachine() {
	for n.state.LastApplied < n.state.CommitIndex {
		n.state.LastApplied++
		entry := n.state.Log[n.state.LastApplied]
		cmd := string(entry.Command)

		if entry.CommandType == "put" {
			idx := strings.Index(cmd, ":")
			if idx != -1 {
				key, value := cmd[:idx], cmd[idx+1:]
				n.kvStore[key] = value
			}
		} else if entry.CommandType == "delete" {
			delete(n.kvStore, cmd)
		}
	}
	n.applyCond.Broadcast()
}

// RaftService RPCs

func (n *RaftNode) RequestVote(ctx context.Context, req *pb.RequestVoteRequest) (*pb.RequestVoteResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	if req.Term > n.state.CurrentTerm {
		n.StepDown(req.Term)
	}

	logOk := req.LastLogTerm > n.GetLastLogTerm() ||
		(req.LastLogTerm == n.GetLastLogTerm() && req.LastLogIndex >= n.GetLastLogIndex())

	voteGranted := false
	if req.Term == n.state.CurrentTerm && logOk &&
		(n.state.VotedFor == "" || n.state.VotedFor == req.CandidateId) {
		n.state.VotedFor = req.CandidateId
		voteGranted = true
		n.ResetElectionTimer()
	}

	return &pb.RequestVoteResponse{
		Term:        n.state.CurrentTerm,
		VoteGranted: voteGranted,
	}, nil
}

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

	n.leaderID = req.LeaderId
	n.nodeState = Follower
	n.ResetElectionTimer()

	if req.PrevLogIndex >= uint64(len(n.state.Log)) ||
		n.state.Log[req.PrevLogIndex].Term != req.PrevLogTerm {
		return &pb.AppendEntriesResponse{
			Term:       n.state.CurrentTerm,
			Success:    false,
			MatchIndex: n.GetLastLogIndex(),
		}, nil
	}

	logPtr := req.PrevLogIndex + 1
	for _, entry := range req.Entries {
		if logPtr < uint64(len(n.state.Log)) {
			if n.state.Log[logPtr].Term != entry.Term {
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

func (n *RaftNode) InstallSnapshot(ctx context.Context, req *pb.InstallSnapshotRequest) (*pb.InstallSnapshotResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	if req.Term > n.state.CurrentTerm {
		n.StepDown(req.Term)
	}

	return &pb.InstallSnapshotResponse{Term: n.state.CurrentTerm}, nil
}

// KeyValueService RPCs

func (n *RaftNode) Get(ctx context.Context, req *pb.GetRequest) (*pb.GetResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	if value, ok := n.kvStore[req.Key]; ok {
		return &pb.GetResponse{Value: value, Found: true}, nil
	}
	return &pb.GetResponse{Found: false}, nil
}

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

	entry := LogEntry{
		Index:       n.GetLastLogIndex() + 1,
		Term:        n.state.CurrentTerm,
		Command:     []byte(req.Key + ":" + req.Value),
		CommandType: "put",
	}
	n.state.Log = append(n.state.Log, entry)
	waitIdx := entry.Index

	for n.state.LastApplied < waitIdx && n.nodeState == Leader {
		n.applyCond.Wait()
	}

	success := n.state.LastApplied >= waitIdx
	n.mu.Unlock()

	return &pb.PutResponse{Success: success}, nil
}

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

	for n.state.LastApplied < waitIdx && n.nodeState == Leader {
		n.applyCond.Wait()
	}

	success := n.state.LastApplied >= waitIdx
	n.mu.Unlock()

	return &pb.DeleteResponse{Success: success}, nil
}

func (n *RaftNode) GetLeader(ctx context.Context, req *pb.GetLeaderRequest) (*pb.GetLeaderResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	resp := &pb.GetLeaderResponse{
		LeaderId: n.leaderID,
		IsLeader: n.nodeState == Leader,
	}

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

	rand.Seed(time.Now().UnixNano())

	node := NewRaftNode(*nodeID, *port, peers)
	if err := node.Initialize(); err != nil {
		log.Fatalf("Failed to initialize node: %v", err)
	}

	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	server := grpc.NewServer()
	pb.RegisterRaftServiceServer(server, node)
	pb.RegisterKeyValueServiceServer(server, node)

	go node.ElectionTimerLoop()
	go node.HeartbeatLoop()

	log.Printf("Starting Raft node %s on port %d", *nodeID, *port)
	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
