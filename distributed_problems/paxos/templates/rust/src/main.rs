//! Paxos Consensus Implementation - Rust Template
//!
//! This template provides the basic structure for implementing the Multi-Paxos
//! consensus algorithm. You need to implement the TODO sections.
//!
//! For the full Paxos specification, see: "Paxos Made Simple" by Leslie Lamport
//!
//! Usage:
//!     cargo run -- --node-id node1 --port 50051 --peers node2:50052,node3:50053

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tonic::{transport::Server, Request, Response, Status};
use clap::Parser;

// Include generated protobuf code
pub mod paxos {
    tonic::include_proto!("paxos");
}

use paxos::paxos_service_server::{PaxosService, PaxosServiceServer};
use paxos::key_value_service_server::{KeyValueService, KeyValueServiceServer};
use paxos::paxos_service_client::PaxosServiceClient;
use paxos::{
    PrepareRequest, PrepareResponse,
    AcceptRequest, AcceptResponse,
    LearnRequest, LearnResponse,
    HeartbeatRequest, HeartbeatResponse,
    GetRequest, GetResponse,
    PutRequest, PutResponse,
    DeleteRequest, DeleteResponse,
    GetLeaderRequest, GetLeaderResponse,
    GetClusterStatusRequest, GetClusterStatusResponse,
    ClusterMember, ProposalNumber,
};

/// Node roles
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum NodeRole {
    Proposer,
    Acceptor,
    Learner,
    Leader,
}

impl NodeRole {
    fn as_str(&self) -> &'static str {
        match self {
            NodeRole::Proposer => "proposer",
            NodeRole::Acceptor => "acceptor",
            NodeRole::Learner => "learner",
            NodeRole::Leader => "leader",
        }
    }
}

/// Internal proposal number structure
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ProposalNum {
    pub round: u64,
    pub proposer_id: String,
}

impl ProposalNum {
    fn to_proto(&self) -> ProposalNumber {
        ProposalNumber {
            round: self.round,
            proposer_id: self.proposer_id.clone(),
        }
    }

    fn from_proto(proto: &ProposalNumber) -> Self {
        Self {
            round: proto.round,
            proposer_id: proto.proposer_id.clone(),
        }
    }
}

impl PartialOrd for ProposalNum {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for ProposalNum {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        match self.round.cmp(&other.round) {
            std::cmp::Ordering::Equal => self.proposer_id.cmp(&other.proposer_id),
            other => other,
        }
    }
}

/// Acceptor state for each slot
#[derive(Clone, Debug, Default)]
pub struct AcceptorState {
    pub highest_promised: Option<ProposalNum>,
    pub accepted_proposal: Option<ProposalNum>,
    pub accepted_value: Option<Vec<u8>>,
}

/// Paxos state structure
#[derive(Default)]
pub struct PaxosState {
    pub current_round: u64,
    pub acceptor_states: HashMap<u64, AcceptorState>,
    pub learned_values: HashMap<u64, Vec<u8>>,
    pub first_unchosen_slot: u64,
    pub last_executed_slot: u64,
}

/// Paxos node implementation
pub struct PaxosNode {
    node_id: String,
    port: u16,
    peers: Vec<String>,
    state: RwLock<PaxosState>,
    role: RwLock<NodeRole>,
    leader_id: RwLock<Option<String>>,

    // Key-value store (state machine)
    kv_store: RwLock<HashMap<String, String>>,

    // gRPC clients for peer communication
    peer_clients: RwLock<HashMap<String, PaxosServiceClient<tonic::transport::Channel>>>,
}

impl PaxosNode {
    pub fn new(node_id: String, port: u16, peers: Vec<String>) -> Self {
        Self {
            node_id,
            port,
            peers,
            state: RwLock::new(PaxosState::default()),
            role: RwLock::new(NodeRole::Acceptor),
            leader_id: RwLock::new(None),
            kv_store: RwLock::new(HashMap::new()),
            peer_clients: RwLock::new(HashMap::new()),
        }
    }

    pub async fn initialize(&self) -> Result<(), Box<dyn std::error::Error>> {
        let mut clients = self.peer_clients.write().await;
        for peer in &self.peers {
            let addr = format!("http://{}", peer);
            match PaxosServiceClient::connect(addr.clone()).await {
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

    async fn get_acceptor_state(&self, slot: u64) -> AcceptorState {
        let mut state = self.state.write().await;
        state.acceptor_states.entry(slot).or_insert_with(AcceptorState::default).clone()
    }

    async fn generate_proposal_number(&self) -> ProposalNum {
        let mut state = self.state.write().await;
        state.current_round += 1;
        ProposalNum {
            round: state.current_round,
            proposer_id: self.node_id.clone(),
        }
    }

    /// Send Prepare requests to all acceptors.
    ///
    /// TODO: Implement Phase 1a of Paxos:
    /// 1. Send Prepare(n) to all acceptors
    /// 2. Wait for responses from a majority
    /// 3. If majority promise, return (true, highest_accepted_value)
    /// 4. If any acceptor has accepted a value, use that value
    pub async fn send_prepare(&self, _slot: u64, _proposal: ProposalNum) -> (bool, Option<Vec<u8>>) {
        (false, None)
    }

    /// Send Accept requests to all acceptors.
    ///
    /// TODO: Implement Phase 2a of Paxos:
    /// 1. Send Accept(n, v) to all acceptors
    /// 2. Wait for responses from a majority
    /// 3. If majority accept, value is chosen - notify learners
    /// 4. Return true if value was chosen
    pub async fn send_accept(&self, _slot: u64, _proposal: ProposalNum, _value: Vec<u8>) -> bool {
        false
    }

    /// Apply a command to the state machine.
    pub async fn apply_command(&self, _command: &[u8], _command_type: &str) {
        // TODO: Parse and apply the command
    }

    /// Run as the Multi-Paxos leader.
    ///
    /// TODO: Implement Multi-Paxos optimization:
    /// 1. Skip Phase 1 for consecutive slots after becoming leader
    /// 2. Send heartbeats to maintain leadership
    /// 3. Handle client requests directly
    pub async fn run_as_leader(&self) {
        // TODO: Implement leader logic
    }
}

#[tonic::async_trait]
impl PaxosService for Arc<PaxosNode> {
    /// Handle Prepare RPC from a proposer.
    ///
    /// TODO: Implement Phase 1b of Paxos:
    /// 1. If n > highest_promised, update highest_promised and promise
    /// 2. Return (promised=True, accepted_proposal, accepted_value)
    /// 3. Otherwise return (promised=False, highest_promised)
    async fn prepare(
        &self,
        request: Request<PrepareRequest>,
    ) -> Result<Response<PrepareResponse>, Status> {
        let req = request.into_inner();
        let _slot = req.slot;
        let _proposal = req.proposal_number.map(|p| ProposalNum::from_proto(&p));
        let _acceptor_state = self.get_acceptor_state(req.slot).await;

        // TODO: Implement prepare logic
        let response = PrepareResponse {
            promised: false,
            accepted_proposal: None,
            accepted_value: vec![],
            highest_promised: None,
        };

        Ok(Response::new(response))
    }

    /// Handle Accept RPC from a proposer.
    ///
    /// TODO: Implement Phase 2b of Paxos:
    /// 1. If n >= highest_promised, accept the value
    /// 2. Update accepted_proposal and accepted_value
    /// 3. Return (accepted=True)
    /// 4. Otherwise return (accepted=False, highest_promised)
    async fn accept(
        &self,
        request: Request<AcceptRequest>,
    ) -> Result<Response<AcceptResponse>, Status> {
        let req = request.into_inner();
        let _slot = req.slot;
        let _proposal = req.proposal_number.map(|p| ProposalNum::from_proto(&p));
        let _acceptor_state = self.get_acceptor_state(req.slot).await;

        // TODO: Implement accept logic
        let response = AcceptResponse {
            accepted: false,
            highest_promised: None,
        };

        Ok(Response::new(response))
    }

    /// Handle Learn RPC - a value has been chosen.
    ///
    /// TODO: Implement learning:
    /// 1. Store the learned value for the slot
    /// 2. If this fills a gap, execute commands in order
    async fn learn(
        &self,
        request: Request<LearnRequest>,
    ) -> Result<Response<LearnResponse>, Status> {
        let _req = request.into_inner();

        // TODO: Implement learn logic
        let response = LearnResponse {
            success: true,
        };

        Ok(Response::new(response))
    }

    async fn heartbeat(
        &self,
        _request: Request<HeartbeatRequest>,
    ) -> Result<Response<HeartbeatResponse>, Status> {
        // TODO: Implement leader acknowledgment
        let response = HeartbeatResponse {
            acknowledged: true,
            highest_seen: None,
        };

        Ok(Response::new(response))
    }
}

#[tonic::async_trait]
impl KeyValueService for Arc<PaxosNode> {
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
    /// 2. Run Paxos to agree on this operation
    /// 3. Apply to state machine once chosen
    async fn put(
        &self,
        _request: Request<PutRequest>,
    ) -> Result<Response<PutResponse>, Status> {
        let role = self.role.read().await;

        if *role != NodeRole::Leader {
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

    async fn delete(
        &self,
        _request: Request<DeleteRequest>,
    ) -> Result<Response<DeleteResponse>, Status> {
        let role = self.role.read().await;

        if *role != NodeRole::Leader {
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
        let role = self.role.read().await;
        let leader_id = self.leader_id.read().await;

        let mut response = GetLeaderResponse {
            leader_id: leader_id.clone().unwrap_or_default(),
            leader_address: String::new(),
            is_leader: *role == NodeRole::Leader,
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
        let role = self.role.read().await;

        let mut response = GetClusterStatusResponse {
            node_id: self.node_id.clone(),
            role: role.as_str().to_string(),
            current_slot: state.first_unchosen_slot,
            highest_promised_round: state.current_round,
            highest_accepted_round: 0,
            first_unchosen_slot: state.first_unchosen_slot,
            last_executed_slot: state.last_executed_slot,
            members: Vec::new(),
        };

        for peer in &self.peers {
            let member = ClusterMember {
                node_id: String::new(),
                address: peer.clone(),
                role: String::new(),
                last_seen_slot: 0,
            };
            response.members.push(member);
        }

        Ok(Response::new(response))
    }
}

#[derive(Parser, Debug)]
#[command(name = "paxos-server")]
#[command(about = "Paxos Consensus Server")]
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

    let node = Arc::new(PaxosNode::new(args.node_id.clone(), args.port, peers));
    node.initialize().await?;

    let addr = format!("0.0.0.0:{}", args.port).parse()?;

    println!("Starting Paxos node {} on port {}", args.node_id, args.port);

    Server::builder()
        .add_service(PaxosServiceServer::new(node.clone()))
        .add_service(KeyValueServiceServer::new(node.clone()))
        .serve(addr)
        .await?;

    Ok(())
}
