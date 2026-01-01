//! Raft Consensus Implementation - Rust Solution
//!
//! A complete implementation of the Raft consensus algorithm supporting:
//! - Leader election with randomized timeouts
//! - Log replication with consistency guarantees
//! - Heartbeat mechanism for leader authority
//! - Key-value store as the state machine
//!
//! For the full Raft specification, see: https://raft.github.io/raft.pdf
//!
//! Key Raft Properties:
//! - Election Safety: At most one leader per term
//! - Leader Append-Only: Leader never overwrites/deletes log entries
//! - Log Matching: Same index+term means identical prefix
//! - Leader Completeness: Committed entries appear in future leaders
//! - State Machine Safety: Same commands applied in same order
//!
//! Usage:
//!     cargo run -- --node-id node1 --port 50051 --peers node2:50052,node3:50053

use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::{Mutex, RwLock, Notify};
use tokio::time;
use tonic::{transport::Server, Request, Response, Status};
use rand::Rng;
use clap::Parser;

// Include generated protobuf code
pub mod raft {
    tonic::include_proto!("raft");
}

use raft::raft_service_server::{RaftService, RaftServiceServer};
use raft::key_value_service_server::{KeyValueService, KeyValueServiceServer};
use raft::raft_service_client::RaftServiceClient;
use raft::*;

// =============================================================================
// Node States - A node can be in one of three states
// =============================================================================
#[derive(Clone, Copy, PartialEq, Debug)]
enum NodeState {
    Follower,   // Default state, receives entries from leader
    Candidate,  // Seeking votes to become leader
    Leader,     // Manages log replication
}

impl NodeState {
    fn as_str(&self) -> &'static str {
        match self {
            NodeState::Follower => "follower",
            NodeState::Candidate => "candidate",
            NodeState::Leader => "leader",
        }
    }
}

// =============================================================================
// Log Entry - Represents a single entry in the replicated log
// =============================================================================
#[derive(Clone)]
struct LogEntryData {
    index: u64,          // Position in log (1-indexed)
    term: u64,           // Term when entry was received
    command: Vec<u8>,    // Command to apply to state machine
    command_type: String, // Type of command (put/delete)
}

// =============================================================================
// Raft State - Persistent and volatile state per Raft paper
// =============================================================================
struct RaftStateStore {
    // Persistent state on all servers (updated before responding to RPCs)
    current_term: u64,              // Latest term server has seen
    voted_for: Option<String>,      // CandidateId that received vote in current term
    log: Vec<LogEntryData>,         // Log entries

    // Volatile state on all servers
    commit_index: u64,              // Index of highest log entry known to be committed
    last_applied: u64,              // Index of highest log entry applied to state machine

    // Volatile state on leaders (reinitialized after election)
    next_index: HashMap<String, u64>,   // For each peer, next log index to send
    match_index: HashMap<String, u64>,  // For each peer, highest replicated index
}

impl RaftStateStore {
    fn new() -> Self {
        let mut state = Self {
            current_term: 0,
            voted_for: None,
            log: Vec::new(),
            commit_index: 0,
            last_applied: 0,
            next_index: HashMap::new(),
            match_index: HashMap::new(),
        };
        // Dummy entry at index 0 (Raft logs are 1-indexed)
        state.log.push(LogEntryData {
            index: 0,
            term: 0,
            command: Vec::new(),
            command_type: String::new(),
        });
        state
    }
}

// =============================================================================
// Raft Node Implementation
// =============================================================================
struct RaftNode {
    node_id: String,
    port: u16,
    peers: Vec<String>,
    state: RwLock<RaftStateStore>,
    node_state: RwLock<NodeState>,
    leader_id: RwLock<String>,

    // Key-value store (state machine)
    kv_store: RwLock<HashMap<String, String>>,

    // Election timer
    election_deadline: Mutex<Instant>,

    // Notification for applied entries
    apply_notify: Notify,

    // Stop flag for graceful shutdown
    stop_flag: RwLock<bool>,
}

impl RaftNode {
    pub fn new(node_id: String, port: u16, peers: Vec<String>) -> Self {
        Self {
            node_id,
            port,
            peers,
            state: RwLock::new(RaftStateStore::new()),
            node_state: RwLock::new(NodeState::Follower),
            leader_id: RwLock::new(String::new()),
            kv_store: RwLock::new(HashMap::new()),
            election_deadline: Mutex::new(Instant::now() + Self::random_timeout()),
            apply_notify: Notify::new(),
            stop_flag: RwLock::new(false),
        }
    }

    // =========================================================================
    // Helper Methods
    // =========================================================================

    /// Generate a random election timeout between 150-300ms.
    /// This prevents split votes by randomizing when candidates start elections.
    fn random_timeout() -> Duration {
        let mut rng = rand::thread_rng();
        Duration::from_millis(rng.gen_range(150..300))
    }

    async fn get_last_log_index(&self) -> u64 {
        let state = self.state.read().await;
        state.log.last().map(|e| e.index).unwrap_or(0)
    }

    async fn get_last_log_term(&self) -> u64 {
        let state = self.state.read().await;
        state.log.last().map(|e| e.term).unwrap_or(0)
    }

    // =========================================================================
    // Election Timer Management
    // =========================================================================

    /// Reset the election timeout with a random duration.
    async fn reset_election_timer(&self) {
        let mut deadline = self.election_deadline.lock().await;
        *deadline = Instant::now() + Self::random_timeout();
    }

    /// Step down to follower state when we see a higher term.
    /// This is a key safety property in Raft.
    async fn step_down(&self, new_term: u64) {
        let mut state = self.state.write().await;
        let mut node_state = self.node_state.write().await;
        state.current_term = new_term;
        state.voted_for = None;
        *node_state = NodeState::Follower;
        drop(state);
        drop(node_state);
        self.reset_election_timer().await;
    }

    /// Election timer loop - monitors for election timeout.
    /// If timeout elapses without hearing from leader, start election.
    async fn election_timer_loop(self: Arc<Self>) {
        self.reset_election_timer().await;
        loop {
            time::sleep(Duration::from_millis(10)).await;

            if *self.stop_flag.read().await {
                break;
            }

            let deadline = *self.election_deadline.lock().await;
            let node_state = *self.node_state.read().await;

            if node_state != NodeState::Leader && Instant::now() >= deadline {
                self.start_election().await;
            }
        }
    }

    // =========================================================================
    // Leader Election
    // =========================================================================

    /// Start a new leader election.
    ///
    /// Per Raft specification:
    /// 1. Increment currentTerm
    /// 2. Vote for self
    /// 3. Reset election timer
    /// 4. Send RequestVote RPCs to all other servers
    /// 5. If votes received from majority: become leader
    /// 6. If AppendEntries received from new leader: convert to follower
    /// 7. If election timeout elapses: start new election
    async fn start_election(self: &Arc<Self>) {
        {
            let mut state = self.state.write().await;
            let mut node_state = self.node_state.write().await;

            *node_state = NodeState::Candidate;
            state.current_term += 1;
            state.voted_for = Some(self.node_id.clone());
        }

        self.reset_election_timer().await;

        let (term, last_idx, last_term) = {
            let state = self.state.read().await;
            (state.current_term, self.get_last_log_index().await, self.get_last_log_term().await)
        };

        println!("Node {} starting election for term {}", self.node_id, term);

        let votes_received = Arc::new(tokio::sync::Mutex::new(1_usize)); // Vote for self
        let majority = (self.peers.len() + 1) / 2 + 1;

        let mut handles = vec![];

        // Send RequestVote RPCs to all peers in parallel
        for peer in &self.peers {
            let peer = peer.clone();
            let node = Arc::clone(self);
            let votes = Arc::clone(&votes_received);
            let node_id = self.node_id.clone();

            handles.push(tokio::spawn(async move {
                // Cloud Run URLs require HTTPS for secure communication
                let addr = if peer.contains(".run.app") {
                    format!("https://{}", peer)
                } else {
                    format!("http://{}", peer)
                };

                if let Ok(mut client) = RaftServiceClient::connect(addr).await {
                    let request = RequestVoteRequest {
                        term,
                        candidate_id: node_id,
                        last_log_index: last_idx,
                        last_log_term: last_term,
                    };

                    if let Ok(response) = tokio::time::timeout(
                        Duration::from_millis(100),
                        client.request_vote(request)
                    ).await {
                        if let Ok(resp) = response {
                            let resp = resp.into_inner();

                            let current_term = node.state.read().await.current_term;
                            if resp.term > current_term {
                                // Discovered higher term, step down
                                node.step_down(resp.term).await;
                            } else {
                                let node_state = *node.node_state.read().await;
                                let state_term = node.state.read().await.current_term;

                                if node_state == NodeState::Candidate && resp.vote_granted && term == state_term {
                                    // Count vote and check for majority
                                    let mut votes = votes.lock().await;
                                    *votes += 1;
                                    if *votes >= majority {
                                        node.become_leader().await;
                                    }
                                }
                            }
                        }
                    }
                }
            }));
        }

        for handle in handles {
            let _ = handle.await;
        }
    }

    /// Transition to leader state after winning election.
    /// Initialize nextIndex and matchIndex for all peers.
    async fn become_leader(&self) {
        let mut node_state = self.node_state.write().await;
        if *node_state != NodeState::Candidate {
            return;
        }
        *node_state = NodeState::Leader;

        let mut leader_id = self.leader_id.write().await;
        *leader_id = self.node_id.clone();

        let last_idx = self.get_last_log_index().await;

        // Initialize leader volatile state
        let mut state = self.state.write().await;
        for peer in &self.peers {
            state.next_index.insert(peer.clone(), last_idx + 1);
            state.match_index.insert(peer.clone(), 0);
        }

        println!("Node {} became leader for term {}", self.node_id, state.current_term);
    }

    // =========================================================================
    // Heartbeat and Log Replication
    // =========================================================================

    /// Heartbeat loop - sends periodic AppendEntries to maintain leadership.
    async fn heartbeat_loop(self: Arc<Self>) {
        loop {
            time::sleep(Duration::from_millis(50)).await;

            if *self.stop_flag.read().await {
                break;
            }

            if *self.node_state.read().await == NodeState::Leader {
                self.send_append_entries_to_all().await;
            }
        }
    }

    /// Send AppendEntries RPCs to all peers.
    /// Handles both heartbeats (empty entries) and log replication.
    async fn send_append_entries_to_all(&self) {
        for peer in &self.peers {
            let peer = peer.clone();
            let node_id = self.node_id.clone();

            let (term, prev_idx, prev_term, entries, leader_commit) = {
                let state = self.state.read().await;
                let next_idx = *state.next_index.get(&peer).unwrap_or(&1);
                let prev_idx = next_idx - 1;
                let prev_term = if (prev_idx as usize) < state.log.len() {
                    state.log[prev_idx as usize].term
                } else {
                    0
                };

                // Build entries to replicate
                let entries: Vec<LogEntry> = state.log.iter()
                    .skip(next_idx as usize)
                    .map(|e| LogEntry {
                        index: e.index,
                        term: e.term,
                        command: e.command.clone(),
                        command_type: e.command_type.clone(),
                    })
                    .collect();

                (state.current_term, prev_idx, prev_term, entries, state.commit_index)
            };

            let entries_len = entries.len() as u64;
            let node_state_ref = &self.node_state;

            // Cloud Run URLs require HTTPS for secure communication
            let addr = if peer.contains(".run.app") {
                format!("https://{}", peer)
            } else {
                format!("http://{}", peer)
            };

            if let Ok(mut client) = RaftServiceClient::connect(addr).await {
                let request = AppendEntriesRequest {
                    term,
                    leader_id: node_id,
                    prev_log_index: prev_idx,
                    prev_log_term: prev_term,
                    entries,
                    leader_commit,
                };

                if let Ok(response) = tokio::time::timeout(
                    Duration::from_millis(100),
                    client.append_entries(request)
                ).await {
                    if let Ok(resp) = response {
                        let resp = resp.into_inner();

                        let current_term = self.state.read().await.current_term;
                        if resp.term > current_term {
                            self.step_down(resp.term).await;
                        } else if *node_state_ref.read().await == NodeState::Leader {
                            let mut state = self.state.write().await;
                            if resp.success {
                                // Update nextIndex and matchIndex for follower
                                state.next_index.insert(peer.clone(), prev_idx + entries_len + 1);
                                state.match_index.insert(peer.clone(), prev_idx + entries_len);
                                drop(state);
                                self.update_commit_index().await;
                            } else {
                                // Decrement nextIndex and retry
                                let next = state.next_index.get(&peer).copied().unwrap_or(1);
                                state.next_index.insert(peer, next.saturating_sub(1).max(1));
                            }
                        }
                    }
                }
            }
        }
    }

    /// Update commitIndex based on matchIndex of peers.
    /// An entry is committed when replicated on a majority of servers.
    async fn update_commit_index(&self) {
        let mut state = self.state.write().await;
        let log_len = state.log.len() as u64;

        for n in (state.commit_index + 1)..log_len {
            // Only commit entries from current term (Raft safety property)
            if state.log[n as usize].term != state.current_term {
                continue;
            }

            let mut count = 1; // Self
            for peer in &self.peers {
                if *state.match_index.get(peer).unwrap_or(&0) >= n {
                    count += 1;
                }
            }

            if count >= (self.peers.len() + 1) / 2 + 1 {
                state.commit_index = n;
            }
        }

        // Apply committed entries to state machine (key-value store)
        while state.last_applied < state.commit_index {
            state.last_applied += 1;
            let entry = &state.log[state.last_applied as usize];
            let cmd = String::from_utf8_lossy(&entry.command).to_string();

            if entry.command_type == "put" {
                if let Some(sep) = cmd.find(':') {
                    let (key, value) = cmd.split_at(sep);
                    drop(state);
                    let mut kv = self.kv_store.write().await;
                    kv.insert(key.to_string(), value[1..].to_string());
                    state = self.state.write().await;
                }
            } else if entry.command_type == "delete" {
                drop(state);
                let mut kv = self.kv_store.write().await;
                kv.remove(&cmd);
                state = self.state.write().await;
            }
        }

        // Signal waiting threads that entries have been applied
        self.apply_notify.notify_waiters();
    }
}

// =============================================================================
// RaftService RPC Implementation
// =============================================================================
#[tonic::async_trait]
impl RaftService for Arc<RaftNode> {
    /// Handle RequestVote RPC from a candidate.
    ///
    /// Per Raft specification:
    /// 1. Reply false if term < currentTerm
    /// 2. If votedFor is null or candidateId, and candidate's log is at
    ///    least as up-to-date as receiver's log, grant vote
    async fn request_vote(
        &self,
        request: Request<RequestVoteRequest>,
    ) -> Result<Response<RequestVoteResponse>, Status> {
        let req = request.into_inner();

        // Update term if we see a higher term
        {
            let current_term = self.state.read().await.current_term;
            if req.term > current_term {
                self.step_down(req.term).await;
            }
        }

        let mut state = self.state.write().await;
        let last_log_term = self.get_last_log_term().await;
        let last_log_index = self.get_last_log_index().await;

        // Check if candidate's log is at least as up-to-date as ours
        let log_ok = req.last_log_term > last_log_term ||
            (req.last_log_term == last_log_term && req.last_log_index >= last_log_index);

        let vote_granted = req.term == state.current_term && log_ok &&
            (state.voted_for.is_none() || state.voted_for.as_ref() == Some(&req.candidate_id));

        if vote_granted {
            state.voted_for = Some(req.candidate_id);
            drop(state);
            self.reset_election_timer().await;
        }

        let term = self.state.read().await.current_term;
        Ok(Response::new(RequestVoteResponse { term, vote_granted }))
    }

    /// Handle AppendEntries RPC from leader.
    ///
    /// Per Raft specification:
    /// 1. Reply false if term < currentTerm
    /// 2. Reply false if log doesn't contain entry at prevLogIndex with prevLogTerm
    /// 3. If existing entry conflicts with new one, delete it and all that follow
    /// 4. Append any new entries not already in the log
    /// 5. If leaderCommit > commitIndex, set commitIndex = min(leaderCommit, last new entry index)
    async fn append_entries(
        &self,
        request: Request<AppendEntriesRequest>,
    ) -> Result<Response<AppendEntriesResponse>, Status> {
        let req = request.into_inner();

        // Update term if we see a higher term
        {
            let current_term = self.state.read().await.current_term;
            if req.term > current_term {
                self.step_down(req.term).await;
            }
        }

        // Reply false if term < currentTerm
        let current_term = self.state.read().await.current_term;
        if req.term < current_term {
            return Ok(Response::new(AppendEntriesResponse {
                term: current_term,
                success: false,
                match_index: self.get_last_log_index().await,
            }));
        }

        // Valid AppendEntries from leader - update state
        *self.leader_id.write().await = req.leader_id;
        *self.node_state.write().await = NodeState::Follower;
        self.reset_election_timer().await;

        let mut state = self.state.write().await;

        // Check log consistency
        if req.prev_log_index as usize >= state.log.len() ||
            state.log[req.prev_log_index as usize].term != req.prev_log_term {
            return Ok(Response::new(AppendEntriesResponse {
                term: state.current_term,
                success: false,
                match_index: state.log.last().map(|e| e.index).unwrap_or(0),
            }));
        }

        // Append new entries
        let mut log_ptr = (req.prev_log_index + 1) as usize;
        for entry in req.entries {
            if log_ptr < state.log.len() {
                // Conflict detection - delete conflicting entries
                if state.log[log_ptr].term != entry.term {
                    state.log.truncate(log_ptr);
                }
            }
            if log_ptr >= state.log.len() {
                state.log.push(LogEntryData {
                    index: entry.index,
                    term: entry.term,
                    command: entry.command,
                    command_type: entry.command_type,
                });
            }
            log_ptr += 1;
        }

        // Update commit index
        if req.leader_commit > state.commit_index {
            let last_idx = state.log.last().map(|e| e.index).unwrap_or(0);
            state.commit_index = req.leader_commit.min(last_idx);
        }

        let match_idx = state.log.last().map(|e| e.index).unwrap_or(0);
        let term = state.current_term;
        drop(state);

        self.update_commit_index().await;

        Ok(Response::new(AppendEntriesResponse {
            term,
            success: true,
            match_index: match_idx,
        }))
    }

    /// Handle InstallSnapshot RPC from leader.
    /// Used when leader needs to bring a far-behind follower up to date.
    async fn install_snapshot(
        &self,
        request: Request<InstallSnapshotRequest>,
    ) -> Result<Response<InstallSnapshotResponse>, Status> {
        let req = request.into_inner();
        let current_term = self.state.read().await.current_term;

        if req.term > current_term {
            self.step_down(req.term).await;
        }

        Ok(Response::new(InstallSnapshotResponse {
            term: self.state.read().await.current_term,
        }))
    }
}

// =============================================================================
// KeyValueService RPC Implementation
// =============================================================================
#[tonic::async_trait]
impl KeyValueService for Arc<RaftNode> {
    /// Handle Get RPC - reads from local key-value store.
    /// Reads can be served by any node (eventual consistency).
    async fn get(&self, request: Request<GetRequest>) -> Result<Response<GetResponse>, Status> {
        let req = request.into_inner();
        let kv = self.kv_store.read().await;

        if let Some(value) = kv.get(&req.key) {
            Ok(Response::new(GetResponse {
                value: value.clone(),
                found: true,
                error: String::new(),
            }))
        } else {
            Ok(Response::new(GetResponse {
                value: String::new(),
                found: false,
                error: String::new(),
            }))
        }
    }

    /// Handle Put RPC - stores key-value pair through consensus.
    /// Only the leader can accept writes.
    async fn put(&self, request: Request<PutRequest>) -> Result<Response<PutResponse>, Status> {
        let req = request.into_inner();

        // Redirect to leader if we're not the leader
        if *self.node_state.read().await != NodeState::Leader {
            return Ok(Response::new(PutResponse {
                success: false,
                error: "Not the leader".to_string(),
                leader_hint: self.leader_id.read().await.clone(),
            }));
        }

        // Append to log
        let wait_idx = {
            let mut state = self.state.write().await;
            let index = state.log.last().map(|e| e.index).unwrap_or(0) + 1;
            state.log.push(LogEntryData {
                index,
                term: state.current_term,
                command: format!("{}:{}", req.key, req.value).into_bytes(),
                command_type: "put".to_string(),
            });
            index
        };

        // Wait for entry to be committed and applied
        loop {
            let last_applied = self.state.read().await.last_applied;
            if last_applied >= wait_idx {
                return Ok(Response::new(PutResponse {
                    success: true,
                    error: String::new(),
                    leader_hint: String::new(),
                }));
            }
            if *self.node_state.read().await != NodeState::Leader {
                return Ok(Response::new(PutResponse {
                    success: false,
                    error: "Lost leadership".to_string(),
                    leader_hint: self.leader_id.read().await.clone(),
                }));
            }
            time::sleep(Duration::from_millis(10)).await;
        }
    }

    /// Handle Delete RPC - removes key through consensus.
    /// Only the leader can accept writes.
    async fn delete(&self, request: Request<DeleteRequest>) -> Result<Response<DeleteResponse>, Status> {
        let req = request.into_inner();

        // Redirect to leader if we're not the leader
        if *self.node_state.read().await != NodeState::Leader {
            return Ok(Response::new(DeleteResponse {
                success: false,
                error: "Not the leader".to_string(),
                leader_hint: self.leader_id.read().await.clone(),
            }));
        }

        // Append to log
        let wait_idx = {
            let mut state = self.state.write().await;
            let index = state.log.last().map(|e| e.index).unwrap_or(0) + 1;
            state.log.push(LogEntryData {
                index,
                term: state.current_term,
                command: req.key.into_bytes(),
                command_type: "delete".to_string(),
            });
            index
        };

        // Wait for entry to be committed and applied
        loop {
            let last_applied = self.state.read().await.last_applied;
            if last_applied >= wait_idx {
                return Ok(Response::new(DeleteResponse {
                    success: true,
                    error: String::new(),
                    leader_hint: String::new(),
                }));
            }
            if *self.node_state.read().await != NodeState::Leader {
                return Ok(Response::new(DeleteResponse {
                    success: false,
                    error: "Lost leadership".to_string(),
                    leader_hint: self.leader_id.read().await.clone(),
                }));
            }
            time::sleep(Duration::from_millis(10)).await;
        }
    }

    /// Handle GetLeader RPC - returns current leader information.
    async fn get_leader(&self, _request: Request<GetLeaderRequest>) -> Result<Response<GetLeaderResponse>, Status> {
        let leader_id = self.leader_id.read().await.clone();
        let is_leader = *self.node_state.read().await == NodeState::Leader;

        let mut leader_address = String::new();
        for peer in &self.peers {
            if peer.contains(&leader_id) {
                leader_address = peer.clone();
                break;
            }
        }

        if is_leader {
            leader_address = format!("localhost:{}", self.port);
        }

        Ok(Response::new(GetLeaderResponse {
            leader_id,
            leader_address,
            is_leader,
        }))
    }

    /// Handle GetClusterStatus RPC - returns detailed cluster state.
    async fn get_cluster_status(&self, _request: Request<GetClusterStatusRequest>) -> Result<Response<GetClusterStatusResponse>, Status> {
        let state = self.state.read().await;
        let node_state = *self.node_state.read().await;

        let mut members = Vec::new();
        for peer in &self.peers {
            let mut member = ClusterMember {
                node_id: String::new(),
                address: peer.clone(),
                state: String::new(),
                match_index: 0,
                next_index: 0,
            };
            if node_state == NodeState::Leader {
                member.match_index = *state.match_index.get(peer).unwrap_or(&0);
                member.next_index = *state.next_index.get(peer).unwrap_or(&1);
            }
            members.push(member);
        }

        Ok(Response::new(GetClusterStatusResponse {
            node_id: self.node_id.clone(),
            state: node_state.as_str().to_string(),
            current_term: state.current_term,
            voted_for: state.voted_for.clone().unwrap_or_default(),
            commit_index: state.commit_index,
            last_applied: state.last_applied,
            log_length: state.log.len() as u64,
            last_log_term: state.log.last().map(|e| e.term).unwrap_or(0),
            members,
        }))
    }
}

// =============================================================================
// Command Line Arguments
// =============================================================================
#[derive(Parser, Debug)]
#[command(author, version, about = "Raft Consensus Server", long_about = None)]
struct Args {
    /// Unique node identifier
    #[arg(long)]
    node_id: String,

    /// Port to listen on
    #[arg(long, default_value_t = 50051)]
    port: u16,

    /// Comma-separated list of peer addresses
    #[arg(long)]
    peers: String,
}

// =============================================================================
// Main Entry Point
// =============================================================================
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    let peers: Vec<String> = args.peers
        .split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    println!("Node {} initializing with peers: {:?}", args.node_id, peers);

    let node = Arc::new(RaftNode::new(args.node_id.clone(), args.port, peers));

    // Start background tasks for election and heartbeat
    let election_node = Arc::clone(&node);
    tokio::spawn(async move {
        election_node.election_timer_loop().await;
    });

    let heartbeat_node = Arc::clone(&node);
    tokio::spawn(async move {
        heartbeat_node.heartbeat_loop().await;
    });

    let addr = format!("0.0.0.0:{}", args.port).parse()?;
    println!("Starting Raft node {} on port {}", args.node_id, args.port);

    Server::builder()
        .add_service(RaftServiceServer::new(Arc::clone(&node)))
        .add_service(KeyValueServiceServer::new(node))
        .serve(addr)
        .await?;

    Ok(())
}
