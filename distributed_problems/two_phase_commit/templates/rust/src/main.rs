//! Two-Phase Commit (2PC) Implementation - Rust Template
//!
//! This template provides the basic structure for implementing the Two-Phase Commit
//! protocol for distributed transactions. You need to implement the TODO sections.
//!
//! Usage:
//!     cargo run -- --node-id coord --port 50051 --role coordinator --participants p1:50052,p2:50053
//!     cargo run -- --node-id p1 --port 50052 --role participant --coordinator coord:50051

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tonic::{transport::Server, Request, Response, Status};
use clap::Parser;
use uuid::Uuid;

pub mod tpc {
    tonic::include_proto!("two_phase_commit");
}

use tpc::coordinator_service_server::{CoordinatorService, CoordinatorServiceServer};
use tpc::participant_service_server::{ParticipantService, ParticipantServiceServer};
use tpc::key_value_service_server::{KeyValueService, KeyValueServiceServer};
use tpc::participant_service_client::ParticipantServiceClient;
use tpc::*;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum NodeRole {
    Coordinator,
    Participant,
}

impl NodeRole {
    fn as_str(&self) -> &'static str {
        match self {
            NodeRole::Coordinator => "coordinator",
            NodeRole::Participant => "participant",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum TxnState {
    Unknown,
    Active,
    Preparing,
    Prepared,
    Committing,
    Committed,
    Aborting,
    Aborted,
}

#[derive(Clone, Debug)]
pub struct Transaction {
    pub id: String,
    pub state: TxnState,
    pub participants: Vec<String>,
    pub votes: HashMap<String, bool>,
}

#[derive(Clone, Debug)]
pub struct ParticipantTxnState {
    pub transaction_id: String,
    pub state: TxnState,
    pub locks_held: Vec<String>,
}

pub struct TwoPhaseCommitNode {
    node_id: String,
    port: u16,
    role: NodeRole,
    participants: Vec<String>,
    coordinator_addr: Option<String>,

    transactions: RwLock<HashMap<String, Transaction>>,
    participant_states: RwLock<HashMap<String, ParticipantTxnState>>,
    kv_store: RwLock<HashMap<String, String>>,
    key_locks: RwLock<HashMap<String, String>>,

    participant_clients: RwLock<HashMap<String, ParticipantServiceClient<tonic::transport::Channel>>>,
}

impl TwoPhaseCommitNode {
    pub fn new(node_id: String, port: u16, role: NodeRole, participants: Vec<String>, coordinator: Option<String>) -> Self {
        Self {
            node_id,
            port,
            role,
            participants,
            coordinator_addr: coordinator,
            transactions: RwLock::new(HashMap::new()),
            participant_states: RwLock::new(HashMap::new()),
            kv_store: RwLock::new(HashMap::new()),
            key_locks: RwLock::new(HashMap::new()),
            participant_clients: RwLock::new(HashMap::new()),
        }
    }

    pub async fn initialize(&self) -> Result<(), Box<dyn std::error::Error>> {
        if self.role == NodeRole::Coordinator {
            let mut clients = self.participant_clients.write().await;
            for participant in &self.participants {
                let addr = format!("http://{}", participant);
                match ParticipantServiceClient::connect(addr.clone()).await {
                    Ok(client) => { clients.insert(participant.clone(), client); }
                    Err(e) => { eprintln!("Warning: Failed to connect to {}: {}", participant, e); }
                }
            }
            println!("Coordinator {} initialized with participants: {:?}", self.node_id, self.participants);
        } else {
            println!("Participant {} initialized with coordinator: {:?}", self.node_id, self.coordinator_addr);
        }
        Ok(())
    }
}

#[tonic::async_trait]
impl CoordinatorService for Arc<TwoPhaseCommitNode> {
    async fn begin_transaction(&self, _request: Request<BeginTransactionRequest>) -> Result<Response<BeginTransactionResponse>, Status> {
        let txn_id = Uuid::new_v4().to_string();
        let mut transactions = self.transactions.write().await;
        transactions.insert(txn_id.clone(), Transaction {
            id: txn_id.clone(),
            state: TxnState::Active,
            participants: self.participants.clone(),
            votes: HashMap::new(),
        });

        Ok(Response::new(BeginTransactionResponse {
            success: true,
            transaction_id: txn_id,
            error: String::new(),
        }))
    }

    async fn commit_transaction(&self, request: Request<CommitTransactionRequest>) -> Result<Response<CommitTransactionResponse>, Status> {
        let req = request.into_inner();
        let transactions = self.transactions.read().await;
        if !transactions.contains_key(&req.transaction_id) {
            return Ok(Response::new(CommitTransactionResponse {
                success: false,
                final_state: TransactionState::TransactionStateUnknown as i32,
                error: "Transaction not found".to_string(),
                participant_results: HashMap::new(),
            }));
        }

        // TODO: Implement 2PC protocol
        Ok(Response::new(CommitTransactionResponse {
            success: false,
            final_state: TransactionState::TransactionStateUnknown as i32,
            error: "Not implemented".to_string(),
            participant_results: HashMap::new(),
        }))
    }

    async fn abort_transaction(&self, _request: Request<AbortTransactionRequest>) -> Result<Response<AbortTransactionResponse>, Status> {
        Ok(Response::new(AbortTransactionResponse {
            success: true,
            error: String::new(),
        }))
    }

    async fn get_transaction_status(&self, request: Request<GetTransactionStatusRequest>) -> Result<Response<GetTransactionStatusResponse>, Status> {
        let req = request.into_inner();
        let transactions = self.transactions.read().await;
        if let Some(txn) = transactions.get(&req.transaction_id) {
            Ok(Response::new(GetTransactionStatusResponse {
                found: true,
                transaction_id: txn.id.clone(),
                state: txn.state as i32,
                participants: txn.participants.clone(),
                participant_states: HashMap::new(),
                created_at: 0,
                updated_at: 0,
            }))
        } else {
            Ok(Response::new(GetTransactionStatusResponse {
                found: false,
                ..Default::default()
            }))
        }
    }

    async fn execute_operation(&self, _request: Request<ExecuteOperationRequest>) -> Result<Response<ExecuteOperationResponse>, Status> {
        Ok(Response::new(ExecuteOperationResponse {
            success: false,
            value: String::new(),
            error: "Not implemented".to_string(),
        }))
    }
}

#[tonic::async_trait]
impl ParticipantService for Arc<TwoPhaseCommitNode> {
    async fn prepare(&self, _request: Request<PrepareRequest>) -> Result<Response<PrepareResponse>, Status> {
        Ok(Response::new(PrepareResponse {
            vote: false,
            error: String::new(),
            prepared_state: vec![],
        }))
    }

    async fn commit(&self, _request: Request<CommitRequest>) -> Result<Response<CommitResponse>, Status> {
        Ok(Response::new(CommitResponse {
            success: true,
            error: String::new(),
        }))
    }

    async fn abort(&self, _request: Request<AbortRequest>) -> Result<Response<AbortResponse>, Status> {
        Ok(Response::new(AbortResponse {
            success: true,
            error: String::new(),
        }))
    }

    async fn get_status(&self, request: Request<GetStatusRequest>) -> Result<Response<GetStatusResponse>, Status> {
        let req = request.into_inner();
        let states = self.participant_states.read().await;
        if let Some(state) = states.get(&req.transaction_id) {
            Ok(Response::new(GetStatusResponse {
                found: true,
                state: state.state as i32,
            }))
        } else {
            Ok(Response::new(GetStatusResponse {
                found: false,
                state: 0,
            }))
        }
    }

    async fn execute_local(&self, _request: Request<ExecuteLocalRequest>) -> Result<Response<ExecuteLocalResponse>, Status> {
        Ok(Response::new(ExecuteLocalResponse {
            success: false,
            value: String::new(),
            error: "Not implemented".to_string(),
        }))
    }
}

#[tonic::async_trait]
impl KeyValueService for Arc<TwoPhaseCommitNode> {
    async fn get(&self, request: Request<GetRequest>) -> Result<Response<GetResponse>, Status> {
        let req = request.into_inner();
        let kv = self.kv_store.read().await;
        if let Some(value) = kv.get(&req.key) {
            Ok(Response::new(GetResponse { value: value.clone(), found: true, error: String::new() }))
        } else {
            Ok(Response::new(GetResponse { value: String::new(), found: false, error: String::new() }))
        }
    }

    async fn put(&self, _request: Request<PutRequest>) -> Result<Response<PutResponse>, Status> {
        if self.role != NodeRole::Coordinator {
            return Ok(Response::new(PutResponse {
                success: false,
                error: "Not the coordinator".to_string(),
                coordinator_hint: self.coordinator_addr.clone().unwrap_or_default(),
            }));
        }
        Ok(Response::new(PutResponse { success: false, error: "Not implemented".to_string(), coordinator_hint: String::new() }))
    }

    async fn delete(&self, _request: Request<DeleteRequest>) -> Result<Response<DeleteResponse>, Status> {
        if self.role != NodeRole::Coordinator {
            return Ok(Response::new(DeleteResponse {
                success: false,
                error: "Not the coordinator".to_string(),
                coordinator_hint: self.coordinator_addr.clone().unwrap_or_default(),
            }));
        }
        Ok(Response::new(DeleteResponse { success: false, error: "Not implemented".to_string(), coordinator_hint: String::new() }))
    }

    async fn get_leader(&self, _request: Request<GetLeaderRequest>) -> Result<Response<GetLeaderResponse>, Status> {
        Ok(Response::new(GetLeaderResponse {
            coordinator_id: self.node_id.clone(),
            coordinator_address: format!("localhost:{}", self.port),
            is_coordinator: self.role == NodeRole::Coordinator,
        }))
    }

    async fn get_cluster_status(&self, _request: Request<GetClusterStatusRequest>) -> Result<Response<GetClusterStatusResponse>, Status> {
        let members: Vec<ClusterMember> = self.participants.iter().map(|p| ClusterMember {
            node_id: String::new(),
            address: p.clone(),
            role: "participant".to_string(),
            is_healthy: true,
            last_heartbeat: 0,
        }).collect();

        Ok(Response::new(GetClusterStatusResponse {
            node_id: self.node_id.clone(),
            role: self.role.as_str().to_string(),
            active_transactions: 0,
            committed_transactions: 0,
            aborted_transactions: 0,
            prepared_transactions: 0,
            pending_operations: 0,
            members,
        }))
    }
}

#[derive(Parser, Debug)]
#[command(name = "tpc-server")]
struct Args {
    #[arg(long)]
    node_id: String,
    #[arg(long, default_value_t = 50051)]
    port: u16,
    #[arg(long)]
    role: String,
    #[arg(long, default_value = "")]
    participants: String,
    #[arg(long, default_value = "")]
    coordinator: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    let role = if args.role == "coordinator" { NodeRole::Coordinator } else { NodeRole::Participant };
    let participants: Vec<String> = args.participants.split(',').map(|s| s.trim().to_string()).filter(|s| !s.is_empty()).collect();
    let coordinator = if args.coordinator.is_empty() { None } else { Some(args.coordinator) };

    let node = Arc::new(TwoPhaseCommitNode::new(args.node_id.clone(), args.port, role, participants, coordinator));
    node.initialize().await?;

    let addr = format!("0.0.0.0:{}", args.port).parse()?;
    println!("Starting 2PC {} node {} on port {}", args.role, args.node_id, args.port);

    let mut builder = Server::builder();
    if role == NodeRole::Coordinator {
        builder = builder.add_service(CoordinatorServiceServer::new(node.clone()));
    } else {
        builder = builder.add_service(ParticipantServiceServer::new(node.clone()));
    }
    builder.add_service(KeyValueServiceServer::new(node.clone())).serve(addr).await?;

    Ok(())
}
