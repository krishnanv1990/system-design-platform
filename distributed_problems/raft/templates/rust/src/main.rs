//! Raft Consensus Implementation - Rust Template
//!
//! This template provides the basic structure for implementing the Raft
//! consensus algorithm. You need to implement the TODO sections.
//!
//! For the full Raft specification, see: https://raft.github.io/raft.pdf
//!
//! Usage:
//!     cargo run -- --node-id node1 --port 50051 --peers node2:50052,node3:50053

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tonic::{transport::Server, Request, Response, Status};
use clap::Parser;
use rand::Rng;

// Include generated protobuf code
pub mod raft {
    tonic::include_proto!("raft");
}

use raft::raft_service_server::{RaftService, RaftServiceServer};
use raft::key_value_service_server::{KeyValueService, KeyValueServiceServer};
use raft::raft_service_client::RaftServiceClient;
use raft::{
    RequestVoteRequest, RequestVoteResponse,
    AppendEntriesRequest, AppendEntriesResponse,
    InstallSnapshotRequest, InstallSnapshotResponse,
    GetRequest, GetResponse,
    PutRequest, PutResponse,
    DeleteRequest, DeleteResponse,
    GetLeaderRequest, GetLeaderResponse,
    GetClusterStatusRequest, GetClusterStatusResponse,
    ClusterMember,
};

/// Node states
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum NodeState {
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

/// Log entry structure
#[derive(Clone, Debug)]
pub struct LogEntry {
    pub index: u64,
    pub term: u64,
    pub command: Vec<u8>,
    pub command_type: String,
}

/// Raft state structure
#[derive(Default)]
pub struct RaftState {
    // Persistent state
    pub current_term: u64,
    pub voted_for: Option<String>,
    pub log: Vec<LogEntry>,

    // Volatile state on all servers
    pub commit_index: u64,
    pub last_applied: u64,

    // Volatile state on leaders
    pub next_index: HashMap<String, u64>,
    pub match_index: HashMap<String, u64>,
}

/// Raft node implementation
pub struct RaftNode {
    node_id: String,
    port: u16,
    peers: Vec<String>,
    state: RwLock<RaftState>,
    node_state: RwLock<NodeState>,
    leader_id: RwLock<Option<String>>,

    // Key-value store (state machine)
    kv_store: RwLock<HashMap<String, String>>,

    // Timing configuration
    election_timeout_min: Duration,
    election_timeout_max: Duration,
    heartbeat_interval: Duration,

    // gRPC clients for peer communication
    peer_clients: RwLock<HashMap<String, RaftServiceClient<tonic::transport::Channel>>>,
}

impl RaftNode {
    pub fn new(node_id: String, port: u16, peers: Vec<String>) -> Self {
        Self {
            node_id,
            port,
            peers,
            state: RwLock::new(RaftState::default()),
            node_state: RwLock::new(NodeState::Follower),
            leader_id: RwLock::new(None),
            kv_store: RwLock::new(HashMap::new()),
            election_timeout_min: Duration::from_millis(150),
            election_timeout_max: Duration::from_millis(300),
            heartbeat_interval: Duration::from_millis(50),
            peer_clients: RwLock::new(HashMap::new()),
        }
    }

    pub async fn initialize(&self) -> Result<(), Box<dyn std::error::Error>> {
        let mut clients = self.peer_clients.write().await;
        for peer in &self.peers {
            let addr = format!("http://{}", peer);
            match RaftServiceClient::connect(addr.clone()).await {
                Ok(client) => {
                    clients.insert(peer.clone(), client);
                }
                Err(e) => {
                    eprintln!("Warning: Failed to connect to peer {}: {}", peer, e);
                }
            }
        }
        println!("Node {} initialized with peers: {:?}", self.node_id, self.peers);
        Ok(())
    }

    async fn get_last_log_index(&self) -> u64 {
        let state = self.state.read().await;
        state.log.last().map(|e| e.index).unwrap_or(0)
    }

    async fn get_last_log_term(&self) -> u64 {
        let state = self.state.read().await;
        state.log.last().map(|e| e.term).unwrap_or(0)
    }

    /// Reset the election timeout with a random duration.
    ///
    /// TODO: Implement election timer reset
    /// - Cancel any existing timer
    /// - Start a new timer with random timeout between
    ///   election_timeout_min and election_timeout_max
    /// - When timer fires, call start_election()
    pub async fn reset_election_timer(&self) {
        // TODO: Implement election timer reset
    }

    /// Start a new leader election.
    ///
    /// TODO: Implement the election process:
    /// 1. Increment current_term
    /// 2. Change state to CANDIDATE
    /// 3. Vote for self
    /// 4. Reset election timer
    /// 5. Send RequestVote RPCs to all peers in parallel
    /// 6. If votes received from majority, become leader
    /// 7. If AppendEntries received from new leader, become follower
    /// 8. If election timeout elapses, start new election
    pub async fn start_election(&self) {
        // TODO: Implement election logic
    }

    /// Send heartbeat AppendEntries RPCs to all followers.
    ///
    /// TODO: Implement heartbeat mechanism:
    /// - Only run if this node is the leader
    /// - Send AppendEntries (empty for heartbeat) to all peers
    /// - Process responses to update match_index and next_index
    /// - Repeat at heartbeat_interval
    pub async fn send_heartbeats(&self) {
        // TODO: Implement heartbeat logic
    }

    /// Apply a command to the state machine (key-value store).
    ///
    /// TODO: Implement command application:
    /// - Parse the command
    /// - Apply to kv_store (put/delete operations)
    pub async fn apply_command(&self, command: &[u8], command_type: &str) {
        // TODO: Implement command application
    }
}

#[tonic::async_trait]
impl RaftService for Arc<RaftNode> {
    /// Handle RequestVote RPC from a candidate.
    ///
    /// TODO: Implement vote handling per Raft specification:
    /// 1. Reply false if term < currentTerm
    /// 2. If votedFor is null or candidateId, and candidate's log is at
    ///    least as up-to-date as receiver's log, grant vote
    async fn request_vote(
        &self,
        request: Request<RequestVoteRequest>,
    ) -> Result<Response<RequestVoteResponse>, Status> {
        let _req = request.into_inner();
        let state = self.state.read().await;

        // TODO: Implement voting logic
        let response = RequestVoteResponse {
            term: state.current_term,
            vote_granted: false,
        };

        Ok(Response::new(response))
    }

    /// Handle AppendEntries RPC from leader.
    ///
    /// TODO: Implement log replication per Raft specification:
    /// 1. Reply false if term < currentTerm
    /// 2. Reply false if log doesn't contain an entry at prevLogIndex
    ///    whose term matches prevLogTerm
    /// 3. If an existing entry conflicts with a new one, delete the
    ///    existing entry and all that follow it
    /// 4. Append any new entries not already in the log
    /// 5. If leaderCommit > commitIndex, set commitIndex =
    ///    min(leaderCommit, index of last new entry)
    async fn append_entries(
        &self,
        request: Request<AppendEntriesRequest>,
    ) -> Result<Response<AppendEntriesResponse>, Status> {
        let _req = request.into_inner();
        let state = self.state.read().await;
        let last_log_index = state.log.last().map(|e| e.index).unwrap_or(0);

        // TODO: Implement AppendEntries logic
        let response = AppendEntriesResponse {
            term: state.current_term,
            success: false,
            match_index: last_log_index,
        };

        Ok(Response::new(response))
    }

    /// Handle InstallSnapshot RPC from leader.
    ///
    /// TODO: Implement snapshot installation
    async fn install_snapshot(
        &self,
        request: Request<InstallSnapshotRequest>,
    ) -> Result<Response<InstallSnapshotResponse>, Status> {
        let _req = request.into_inner();
        let state = self.state.read().await;

        let response = InstallSnapshotResponse {
            term: state.current_term,
        };

        Ok(Response::new(response))
    }
}

#[tonic::async_trait]
impl KeyValueService for Arc<RaftNode> {
    async fn get(
        &self,
        request: Request<GetRequest>,
    ) -> Result<Response<GetResponse>, Status> {
        let req = request.into_inner();
        let kv_store = self.kv_store.read().await;

        let response = if let Some(value) = kv_store.get(&req.key) {
            GetResponse {
                value: value.clone(),
                found: true,
                error: String::new(),
            }
        } else {
            GetResponse {
                value: String::new(),
                found: false,
                error: String::new(),
            }
        };

        Ok(Response::new(response))
    }

    /// Handle Put RPC - stores key-value pair.
    ///
    /// TODO: Implement consensus-based put:
    /// 1. If not leader, return leader_hint
    /// 2. Append entry to local log
    /// 3. Replicate to followers via AppendEntries
    /// 4. Once committed (majority replicated), apply to state machine
    /// 5. Return success to client
    async fn put(
        &self,
        request: Request<PutRequest>,
    ) -> Result<Response<PutResponse>, Status> {
        let _req = request.into_inner();
        let node_state = self.node_state.read().await;

        if *node_state != NodeState::Leader {
            let leader_id = self.leader_id.read().await;
            return Ok(Response::new(PutResponse {
                success: false,
                error: "Not the leader".to_string(),
                leader_hint: leader_id.clone().unwrap_or_default(),
            }));
        }

        // TODO: Implement consensus-based put
        Ok(Response::new(PutResponse {
            success: false,
            error: "Not implemented".to_string(),
            leader_hint: String::new(),
        }))
    }

    /// Handle Delete RPC - removes key.
    ///
    /// TODO: Implement consensus-based delete (similar to put)
    async fn delete(
        &self,
        request: Request<DeleteRequest>,
    ) -> Result<Response<DeleteResponse>, Status> {
        let _req = request.into_inner();
        let node_state = self.node_state.read().await;

        if *node_state != NodeState::Leader {
            let leader_id = self.leader_id.read().await;
            return Ok(Response::new(DeleteResponse {
                success: false,
                error: "Not the leader".to_string(),
                leader_hint: leader_id.clone().unwrap_or_default(),
            }));
        }

        // TODO: Implement consensus-based delete
        Ok(Response::new(DeleteResponse {
            success: false,
            error: "Not implemented".to_string(),
            leader_hint: String::new(),
        }))
    }

    async fn get_leader(
        &self,
        _request: Request<GetLeaderRequest>,
    ) -> Result<Response<GetLeaderResponse>, Status> {
        let node_state = self.node_state.read().await;
        let leader_id = self.leader_id.read().await;

        let mut response = GetLeaderResponse {
            leader_id: leader_id.clone().unwrap_or_default(),
            leader_address: String::new(),
            is_leader: *node_state == NodeState::Leader,
        };

        if let Some(ref lid) = *leader_id {
            for peer in &self.peers {
                if peer.contains(lid) {
                    response.leader_address = peer.clone();
                    break;
                }
            }
        }

        Ok(Response::new(response))
    }

    async fn get_cluster_status(
        &self,
        _request: Request<GetClusterStatusRequest>,
    ) -> Result<Response<GetClusterStatusResponse>, Status> {
        let state = self.state.read().await;
        let node_state = self.node_state.read().await;

        let mut response = GetClusterStatusResponse {
            node_id: self.node_id.clone(),
            state: node_state.as_str().to_string(),
            current_term: state.current_term,
            voted_for: state.voted_for.clone().unwrap_or_default(),
            commit_index: state.commit_index,
            last_applied: state.last_applied,
            log_length: state.log.len() as u64,
            last_log_term: state.log.last().map(|e| e.term).unwrap_or(0),
            members: Vec::new(),
        };

        for peer in &self.peers {
            let mut member = ClusterMember {
                node_id: String::new(),
                address: peer.clone(),
                state: String::new(),
                match_index: 0,
                next_index: 0,
            };
            if *node_state == NodeState::Leader {
                member.match_index = *state.match_index.get(peer).unwrap_or(&0);
                member.next_index = *state.next_index.get(peer).unwrap_or(&1);
            }
            response.members.push(member);
        }

        Ok(Response::new(response))
    }
}

#[derive(Parser, Debug)]
#[command(name = "raft-server")]
#[command(about = "Raft Consensus Server")]
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

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    let peers: Vec<String> = args.peers
        .split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    let node = Arc::new(RaftNode::new(args.node_id.clone(), args.port, peers));
    node.initialize().await?;

    let addr = format!("0.0.0.0:{}", args.port).parse()?;

    println!("Starting Raft node {} on port {}", args.node_id, args.port);

    // Start election timer
    {
        let node_clone = node.clone();
        tokio::spawn(async move {
            node_clone.reset_election_timer().await;
        });
    }

    Server::builder()
        .add_service(RaftServiceServer::new(node.clone()))
        .add_service(KeyValueServiceServer::new(node.clone()))
        .serve(addr)
        .await?;

    Ok(())
}
