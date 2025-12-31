//! Raft Consensus Implementation - Rust Solution
//!
//! A complete implementation of the Raft consensus algorithm supporting:
//! - Leader election with randomized timeouts
//! - Log replication with consistency guarantees
//! - Heartbeat mechanism for leader authority
//! - Key-value store as the state machine
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

pub mod raft {
    tonic::include_proto!("raft");
}

use raft::raft_service_server::{RaftService, RaftServiceServer};
use raft::key_value_service_server::{KeyValueService, KeyValueServiceServer};
use raft::raft_service_client::RaftServiceClient;
use raft::*;

#[derive(Clone, Copy, PartialEq, Debug)]
enum NodeState {
    Follower,
    Candidate,
    Leader,
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

#[derive(Clone)]
struct LogEntryData {
    index: u64,
    term: u64,
    command: Vec<u8>,
    command_type: String,
}

struct RaftStateStore {
    current_term: u64,
    voted_for: Option<String>,
    log: Vec<LogEntryData>,
    commit_index: u64,
    last_applied: u64,
    next_index: HashMap<String, u64>,
    match_index: HashMap<String, u64>,
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
        // Dummy entry at index 0
        state.log.push(LogEntryData {
            index: 0,
            term: 0,
            command: Vec::new(),
            command_type: String::new(),
        });
        state
    }
}

struct RaftNode {
    node_id: String,
    port: u16,
    peers: Vec<String>,
    state: RwLock<RaftStateStore>,
    node_state: RwLock<NodeState>,
    leader_id: RwLock<String>,
    kv_store: RwLock<HashMap<String, String>>,
    election_deadline: Mutex<Instant>,
    apply_notify: Notify,
    stop_flag: RwLock<bool>,
}

impl RaftNode {
    fn new(node_id: String, port: u16, peers: Vec<String>) -> Self {
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

    async fn reset_election_timer(&self) {
        let mut deadline = self.election_deadline.lock().await;
        *deadline = Instant::now() + Self::random_timeout();
    }

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

        let votes_received = Arc::new(tokio::sync::Mutex::new(1_usize));
        let majority = (self.peers.len() + 1) / 2 + 1;

        let mut handles = vec![];

        for peer in &self.peers {
            let peer = peer.clone();
            let node = Arc::clone(self);
            let votes = Arc::clone(&votes_received);
            let node_id = self.node_id.clone();

            handles.push(tokio::spawn(async move {
                let addr = format!("http://{}", peer);
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
                                node.step_down(resp.term).await;
                            } else {
                                let node_state = *node.node_state.read().await;
                                let state_term = node.state.read().await.current_term;

                                if node_state == NodeState::Candidate && resp.vote_granted && term == state_term {
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

    async fn become_leader(&self) {
        let mut node_state = self.node_state.write().await;
        if *node_state != NodeState::Candidate {
            return;
        }
        *node_state = NodeState::Leader;

        let mut leader_id = self.leader_id.write().await;
        *leader_id = self.node_id.clone();

        let last_idx = self.get_last_log_index().await;

        let mut state = self.state.write().await;
        for peer in &self.peers {
            state.next_index.insert(peer.clone(), last_idx + 1);
            state.match_index.insert(peer.clone(), 0);
        }

        println!("Node {} became leader for term {}", self.node_id, state.current_term);
    }

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
            let state = Arc::new(RwLock::new(&self.state));
            let node_state_ref = &self.node_state;

            let addr = format!("http://{}", peer);
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
                                state.next_index.insert(peer.clone(), prev_idx + entries_len + 1);
                                state.match_index.insert(peer.clone(), prev_idx + entries_len);
                                drop(state);
                                self.update_commit_index().await;
                            } else {
                                let next = state.next_index.get(&peer).copied().unwrap_or(1);
                                state.next_index.insert(peer, next.saturating_sub(1).max(1));
                            }
                        }
                    }
                }
            }
        }
    }

    async fn update_commit_index(&self) {
        let mut state = self.state.write().await;
        let log_len = state.log.len() as u64;

        for n in (state.commit_index + 1)..log_len {
            if state.log[n as usize].term != state.current_term {
                continue;
            }
            let mut count = 1;
            for peer in &self.peers {
                if *state.match_index.get(peer).unwrap_or(&0) >= n {
                    count += 1;
                }
            }
            if count >= (self.peers.len() + 1) / 2 + 1 {
                state.commit_index = n;
            }
        }

        // Apply to state machine
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

        self.apply_notify.notify_waiters();
    }
}

#[tonic::async_trait]
impl RaftService for Arc<RaftNode> {
    async fn request_vote(
        &self,
        request: Request<RequestVoteRequest>,
    ) -> Result<Response<RequestVoteResponse>, Status> {
        let req = request.into_inner();

        {
            let current_term = self.state.read().await.current_term;
            if req.term > current_term {
                self.step_down(req.term).await;
            }
        }

        let mut state = self.state.write().await;
        let last_log_term = self.get_last_log_term().await;
        let last_log_index = self.get_last_log_index().await;

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

    async fn append_entries(
        &self,
        request: Request<AppendEntriesRequest>,
    ) -> Result<Response<AppendEntriesResponse>, Status> {
        let req = request.into_inner();

        {
            let current_term = self.state.read().await.current_term;
            if req.term > current_term {
                self.step_down(req.term).await;
            }
        }

        let current_term = self.state.read().await.current_term;
        if req.term < current_term {
            return Ok(Response::new(AppendEntriesResponse {
                term: current_term,
                success: false,
                match_index: self.get_last_log_index().await,
            }));
        }

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

        // Append entries
        let mut log_ptr = (req.prev_log_index + 1) as usize;
        for entry in req.entries {
            if log_ptr < state.log.len() {
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

#[tonic::async_trait]
impl KeyValueService for Arc<RaftNode> {
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

    async fn put(&self, request: Request<PutRequest>) -> Result<Response<PutResponse>, Status> {
        let req = request.into_inner();

        if *self.node_state.read().await != NodeState::Leader {
            return Ok(Response::new(PutResponse {
                success: false,
                error: "Not the leader".to_string(),
                leader_hint: self.leader_id.read().await.clone(),
            }));
        }

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

    async fn delete(&self, request: Request<DeleteRequest>) -> Result<Response<DeleteResponse>, Status> {
        let req = request.into_inner();

        if *self.node_state.read().await != NodeState::Leader {
            return Ok(Response::new(DeleteResponse {
                success: false,
                error: "Not the leader".to_string(),
                leader_hint: self.leader_id.read().await.clone(),
            }));
        }

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

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    #[arg(long)]
    node_id: String,

    #[arg(long, default_value_t = 50051)]
    port: u16,

    #[arg(long)]
    peers: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    let peers: Vec<String> = args.peers
        .split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    let node = Arc::new(RaftNode::new(args.node_id.clone(), args.port, peers));

    // Start background tasks
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
