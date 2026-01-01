//! Three-Phase Commit (3PC) Implementation - Rust Template
//!
//! This template provides the basic structure for implementing the Three-Phase Commit
//! protocol for distributed transactions. 3PC improves on 2PC by adding a pre-commit
//! phase to achieve non-blocking atomic commitment.
//!
//! The three phases are:
//! 1. CanCommit: Coordinator asks if participants can commit
//! 2. PreCommit: If all agree, coordinator sends pre-commit
//! 3. DoCommit: Coordinator sends final commit/abort
//!
//! You need to implement the TODO sections.
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
    tonic::include_proto!("three_phase_commit");
}

use tpc::coordinator_service_server::{CoordinatorService, CoordinatorServiceServer};
use tpc::participant_service_server::{ParticipantService, ParticipantServiceServer};
use tpc::node_service_server::{NodeService, NodeServiceServer};
use tpc::participant_service_client::ParticipantServiceClient;
use tpc::node_service_client::NodeServiceClient;
use tpc::*;

// =============================================================================
// Node Role and State Types
// =============================================================================

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

/// Transaction state as seen by the coordinator
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum CoordinatorTxnState {
    Unknown,
    Initiated,
    Waiting,
    PreCommit,
    Committing,
    Committed,
    Aborting,
    Aborted,
}

/// Local state of a participant
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum LocalParticipantState {
    Unknown,
    Initial,
    Uncertain,     // Voted YES in CanCommit, waiting for PreCommit
    PreCommitted,  // Received PreCommit, ready to commit
    Committed,
    Aborted,
}

// =============================================================================
// Transaction and State Structures
// =============================================================================

#[derive(Clone, Debug)]
pub struct CoordinatorTransaction {
    pub id: String,
    pub state: CoordinatorTxnState,
    pub participants: Vec<String>,
    pub votes: HashMap<String, bool>,
    pub precommit_acks: HashMap<String, bool>,
    pub data: HashMap<String, String>,
    pub start_time: i64,
    pub timeout_ms: u32,
}

#[derive(Clone, Debug)]
pub struct ParticipantTxnInfo {
    pub transaction_id: String,
    pub state: LocalParticipantState,
    pub vote: bool,
    pub data: HashMap<String, String>,
    pub last_update: i64,
}

// =============================================================================
// Main Node Structure
// =============================================================================

pub struct ThreePhaseCommitNode {
    node_id: String,
    port: u16,
    role: NodeRole,
    participants: Vec<String>,
    coordinator_addr: Option<String>,
    current_term: RwLock<i64>,
    is_coordinator: RwLock<bool>,

    // Coordinator state
    transactions: RwLock<HashMap<String, CoordinatorTransaction>>,

    // Participant state
    participant_states: RwLock<HashMap<String, ParticipantTxnInfo>>,

    // Clients for communication
    participant_clients: RwLock<HashMap<String, ParticipantServiceClient<tonic::transport::Channel>>>,
    node_clients: RwLock<HashMap<String, NodeServiceClient<tonic::transport::Channel>>>,
}

impl ThreePhaseCommitNode {
    pub fn new(
        node_id: String,
        port: u16,
        role: NodeRole,
        participants: Vec<String>,
        coordinator: Option<String>,
    ) -> Self {
        Self {
            node_id,
            port,
            role,
            participants,
            coordinator_addr: coordinator,
            current_term: RwLock::new(0),
            is_coordinator: RwLock::new(role == NodeRole::Coordinator),
            transactions: RwLock::new(HashMap::new()),
            participant_states: RwLock::new(HashMap::new()),
            participant_clients: RwLock::new(HashMap::new()),
            node_clients: RwLock::new(HashMap::new()),
        }
    }

    pub async fn initialize(&self) -> Result<(), Box<dyn std::error::Error>> {
        // TODO: Initialize connections to other nodes
        // 1. Connect to all participant nodes (if coordinator)
        // 2. Connect to coordinator and peer nodes (if participant)
        // 3. Start heartbeat mechanism
        // 4. Initialize recovery from persistent log
        todo!("Implement node initialization")
    }

    // =========================================================================
    // Coordinator Protocol Methods (TODO: Implement these)
    // =========================================================================

    async fn execute_can_commit_phase(&self, _txn_id: &str) -> Result<bool, String> {
        // TODO: Implement Phase 1 (CanCommit)
        // 1. Send CanCommit request to all participants
        // 2. Wait for votes with timeout
        // 3. If any participant votes NO or times out, return false
        // 4. If all vote YES, return true
        // 5. Log the phase transition
        todo!("Implement CanCommit phase")
    }

    async fn execute_precommit_phase(&self, _txn_id: &str) -> Result<bool, String> {
        // TODO: Implement Phase 2 (PreCommit)
        // 1. Send PreCommit to all participants that voted YES
        // 2. Wait for acknowledgments with timeout
        // 3. If any participant fails to acknowledge, prepare for abort
        // 4. Log the pre-commit decision
        todo!("Implement PreCommit phase")
    }

    async fn execute_do_commit_phase(&self, _txn_id: &str) -> Result<(), String> {
        // TODO: Implement Phase 3 (DoCommit)
        // 1. Send DoCommit to all pre-committed participants
        // 2. Wait for commit confirmations
        // 3. Mark transaction as committed
        // 4. Log the final commit
        todo!("Implement DoCommit phase")
    }

    async fn execute_abort_phase(&self, _txn_id: &str, _reason: &str) -> Result<(), String> {
        // TODO: Implement Abort procedure
        // 1. Send DoAbort to all participants
        // 2. Wait for abort acknowledgments
        // 3. Mark transaction as aborted
        // 4. Log the abort
        todo!("Implement abort phase")
    }

    // =========================================================================
    // Participant Protocol Methods (TODO: Implement these)
    // =========================================================================

    fn can_commit_transaction(&self, _txn_id: &str, _data: &HashMap<String, String>) -> bool {
        // TODO: Validate if this transaction can be committed
        // 1. Check if resources are available
        // 2. Validate transaction data
        // 3. Acquire necessary locks
        // 4. Log the vote decision
        todo!("Implement can_commit validation")
    }

    fn apply_precommit(&self, _txn_id: &str) -> Result<(), String> {
        // TODO: Apply pre-commit state
        // 1. Transition to pre-committed state
        // 2. Log the pre-commit
        // 3. Start timeout for DoCommit
        todo!("Implement pre-commit application")
    }

    fn apply_commit(&self, _txn_id: &str) -> Result<(), String> {
        // TODO: Apply final commit
        // 1. Make changes permanent
        // 2. Release locks
        // 3. Clean up transaction state
        todo!("Implement commit application")
    }

    fn apply_abort(&self, _txn_id: &str) -> Result<(), String> {
        // TODO: Apply abort
        // 1. Rollback any changes
        // 2. Release locks
        // 3. Clean up transaction state
        todo!("Implement abort application")
    }

    // =========================================================================
    // Recovery and Failure Handling (TODO: Implement these)
    // =========================================================================

    async fn recover_from_failure(&self) -> Result<(), String> {
        // TODO: Implement recovery protocol
        // 1. Read transaction log
        // 2. For each in-progress transaction, query other nodes
        // 3. Complete or abort based on discovered state
        // 4. This is where 3PC's non-blocking property helps
        todo!("Implement failure recovery")
    }

    async fn handle_coordinator_failure(&self) -> Result<(), String> {
        // TODO: Handle coordinator failure (3PC advantage)
        // 1. Detect coordinator failure via heartbeat timeout
        // 2. Query other participants for transaction states
        // 3. If any participant is in COMMITTED state, commit
        // 4. If any participant is in ABORTED state, abort
        // 5. If all are in UNCERTAIN state, can safely abort
        // 6. If any is in PRECOMMITTED, need election
        todo!("Implement coordinator failure handling")
    }

    async fn elect_new_coordinator(&self) -> Result<String, String> {
        // TODO: Implement coordinator election
        // 1. Participate in election protocol
        // 2. Vote for candidate with highest term
        // 3. Return new coordinator ID
        todo!("Implement coordinator election")
    }
}

// =============================================================================
// CoordinatorService Implementation
// =============================================================================

#[tonic::async_trait]
impl CoordinatorService for Arc<ThreePhaseCommitNode> {
    async fn begin_transaction(
        &self,
        request: Request<BeginTransactionRequest>,
    ) -> Result<Response<BeginTransactionResponse>, Status> {
        let req = request.into_inner();
        let txn_id = Uuid::new_v4().to_string();

        // TODO: Implement transaction initialization
        // 1. Create transaction record with participants
        // 2. Store transaction data
        // 3. Log transaction start
        // 4. Return transaction ID

        let mut transactions = self.transactions.write().await;
        transactions.insert(txn_id.clone(), CoordinatorTransaction {
            id: txn_id.clone(),
            state: CoordinatorTxnState::Initiated,
            participants: req.participants.clone(),
            votes: HashMap::new(),
            precommit_acks: HashMap::new(),
            data: req.data.clone(),
            start_time: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_millis() as i64,
            timeout_ms: req.timeout_ms,
        });

        Ok(Response::new(BeginTransactionResponse {
            success: true,
            transaction_id: txn_id,
            error: String::new(),
        }))
    }

    async fn commit_transaction(
        &self,
        request: Request<CommitTransactionRequest>,
    ) -> Result<Response<CommitTransactionResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement full 3PC commit protocol
        // 1. Execute Phase 1 (CanCommit) - collect votes
        // 2. If all vote YES, execute Phase 2 (PreCommit)
        // 3. If all acknowledge PreCommit, execute Phase 3 (DoCommit)
        // 4. Handle timeouts and failures at each phase
        // 5. Return final transaction state

        let transactions = self.transactions.read().await;
        if !transactions.contains_key(&req.transaction_id) {
            return Ok(Response::new(CommitTransactionResponse {
                success: false,
                final_state: TransactionState::Unknown as i32,
                error: "Transaction not found".to_string(),
                participant_states: HashMap::new(),
            }));
        }
        drop(transactions);

        // Stub: Return not implemented
        Ok(Response::new(CommitTransactionResponse {
            success: false,
            final_state: TransactionState::Unknown as i32,
            error: "TODO: Implement 3PC protocol".to_string(),
            participant_states: HashMap::new(),
        }))
    }

    async fn abort_transaction(
        &self,
        request: Request<AbortTransactionRequest>,
    ) -> Result<Response<AbortTransactionResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement transaction abort
        // 1. Send abort to all participants
        // 2. Update transaction state
        // 3. Log the abort

        let _ = (req.transaction_id, req.reason);

        Ok(Response::new(AbortTransactionResponse {
            success: false,
            error: "TODO: Implement abort".to_string(),
        }))
    }

    async fn get_transaction_status(
        &self,
        request: Request<GetTransactionStatusRequest>,
    ) -> Result<Response<GetTransactionStatusResponse>, Status> {
        let req = request.into_inner();
        let transactions = self.transactions.read().await;

        if let Some(txn) = transactions.get(&req.transaction_id) {
            let state = match txn.state {
                CoordinatorTxnState::Initiated => TransactionState::Initiated,
                CoordinatorTxnState::Waiting => TransactionState::Waiting,
                CoordinatorTxnState::PreCommit => TransactionState::Precommit,
                CoordinatorTxnState::Committing => TransactionState::Committing,
                CoordinatorTxnState::Committed => TransactionState::Committed,
                CoordinatorTxnState::Aborting => TransactionState::Aborting,
                CoordinatorTxnState::Aborted => TransactionState::Aborted,
                CoordinatorTxnState::Unknown => TransactionState::Unknown,
            };

            Ok(Response::new(GetTransactionStatusResponse {
                transaction: Some(Transaction {
                    transaction_id: txn.id.clone(),
                    state: state as i32,
                    participants: txn.participants.clone(),
                    coordinator: self.node_id.clone(),
                    start_time: txn.start_time,
                    last_update: txn.start_time,
                    data: txn.data.clone(),
                    timeout_ms: txn.timeout_ms,
                }),
                found: true,
                error: String::new(),
                participant_states: HashMap::new(),
            }))
        } else {
            Ok(Response::new(GetTransactionStatusResponse {
                transaction: None,
                found: false,
                error: String::new(),
                participant_states: HashMap::new(),
            }))
        }
    }

    async fn get_leader(
        &self,
        _request: Request<GetLeaderRequest>,
    ) -> Result<Response<GetLeaderResponse>, Status> {
        let is_coord = *self.is_coordinator.read().await;

        Ok(Response::new(GetLeaderResponse {
            node_id: self.node_id.clone(),
            node_address: format!("localhost:{}", self.port),
            is_coordinator: is_coord,
        }))
    }

    async fn get_cluster_status(
        &self,
        _request: Request<GetClusterStatusRequest>,
    ) -> Result<Response<GetClusterStatusResponse>, Status> {
        let is_coord = *self.is_coordinator.read().await;
        let transactions = self.transactions.read().await;

        let members: Vec<NodeInfo> = self.participants.iter().map(|p| {
            NodeInfo {
                node_id: String::new(),
                address: p.clone(),
                is_healthy: true,
                is_coordinator: false,
                last_heartbeat: 0,
            }
        }).collect();

        let committed = transactions.values()
            .filter(|t| matches!(t.state, CoordinatorTxnState::Committed))
            .count() as u64;
        let aborted = transactions.values()
            .filter(|t| matches!(t.state, CoordinatorTxnState::Aborted))
            .count() as u64;
        let active = transactions.len() as u64 - committed - aborted;

        Ok(Response::new(GetClusterStatusResponse {
            node_id: self.node_id.clone(),
            node_address: format!("localhost:{}", self.port),
            is_coordinator: is_coord,
            total_nodes: (self.participants.len() + 1) as u32,
            healthy_nodes: (self.participants.len() + 1) as u32,
            active_transactions: active,
            committed_transactions: committed,
            aborted_transactions: aborted,
            members,
        }))
    }
}

// =============================================================================
// ParticipantService Implementation
// =============================================================================

#[tonic::async_trait]
impl ParticipantService for Arc<ThreePhaseCommitNode> {
    async fn can_commit(
        &self,
        request: Request<CanCommitRequest>,
    ) -> Result<Response<CanCommitResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement Phase 1 participant response
        // 1. Validate if we can commit this transaction
        // 2. Acquire necessary locks
        // 3. Store transaction data
        // 4. Return YES/NO vote
        // 5. If YES, transition to UNCERTAIN state

        let _ = (req.transaction_id, req.coordinator, req.data, req.timeout_ms);

        Ok(Response::new(CanCommitResponse {
            vote: false,
            error: "TODO: Implement CanCommit".to_string(),
        }))
    }

    async fn pre_commit(
        &self,
        request: Request<PreCommitRequest>,
    ) -> Result<Response<PreCommitResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement Phase 2 participant response
        // 1. Verify we're in UNCERTAIN state for this transaction
        // 2. Transition to PRECOMMITTED state
        // 3. Log the pre-commit
        // 4. Return acknowledgment

        let _ = req.transaction_id;

        Ok(Response::new(PreCommitResponse {
            acknowledged: false,
            error: "TODO: Implement PreCommit".to_string(),
        }))
    }

    async fn do_commit(
        &self,
        request: Request<DoCommitRequest>,
    ) -> Result<Response<DoCommitResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement Phase 3 participant response
        // 1. Verify we're in PRECOMMITTED state
        // 2. Apply the transaction (make changes permanent)
        // 3. Release locks
        // 4. Transition to COMMITTED state
        // 5. Log the commit

        let _ = req.transaction_id;

        Ok(Response::new(DoCommitResponse {
            success: false,
            error: "TODO: Implement DoCommit".to_string(),
        }))
    }

    async fn do_abort(
        &self,
        request: Request<DoAbortRequest>,
    ) -> Result<Response<DoAbortResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement abort handling
        // 1. Rollback any changes for this transaction
        // 2. Release locks
        // 3. Transition to ABORTED state
        // 4. Log the abort

        let _ = (req.transaction_id, req.reason);

        Ok(Response::new(DoAbortResponse {
            acknowledged: false,
            error: "TODO: Implement DoAbort".to_string(),
        }))
    }

    async fn get_state(
        &self,
        request: Request<GetStateRequest>,
    ) -> Result<Response<GetStateResponse>, Status> {
        let req = request.into_inner();
        let states = self.participant_states.read().await;

        if let Some(info) = states.get(&req.transaction_id) {
            let state = match info.state {
                LocalParticipantState::Initial => ParticipantState::PInitial,
                LocalParticipantState::Uncertain => ParticipantState::PUncertain,
                LocalParticipantState::PreCommitted => ParticipantState::PPrecommitted,
                LocalParticipantState::Committed => ParticipantState::PCommitted,
                LocalParticipantState::Aborted => ParticipantState::PAborted,
                LocalParticipantState::Unknown => ParticipantState::PUnknown,
            };

            Ok(Response::new(GetStateResponse {
                info: Some(tpc::ParticipantInfo {
                    node_id: self.node_id.clone(),
                    transaction_id: info.transaction_id.clone(),
                    state: state as i32,
                    vote: info.vote,
                    last_update: info.last_update,
                }),
                found: true,
            }))
        } else {
            Ok(Response::new(GetStateResponse {
                info: None,
                found: false,
            }))
        }
    }
}

// =============================================================================
// NodeService Implementation (Inter-node communication)
// =============================================================================

#[tonic::async_trait]
impl NodeService for Arc<ThreePhaseCommitNode> {
    async fn query_state(
        &self,
        request: Request<QueryStateRequest>,
    ) -> Result<Response<QueryStateResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement state query for recovery
        // This is used by other participants to determine transaction state
        // when recovering from coordinator failure

        let states = self.participant_states.read().await;
        if let Some(info) = states.get(&req.transaction_id) {
            let state = match info.state {
                LocalParticipantState::Initial => ParticipantState::PInitial,
                LocalParticipantState::Uncertain => ParticipantState::PUncertain,
                LocalParticipantState::PreCommitted => ParticipantState::PPrecommitted,
                LocalParticipantState::Committed => ParticipantState::PCommitted,
                LocalParticipantState::Aborted => ParticipantState::PAborted,
                LocalParticipantState::Unknown => ParticipantState::PUnknown,
            };

            Ok(Response::new(QueryStateResponse {
                state: state as i32,
                found: true,
            }))
        } else {
            Ok(Response::new(QueryStateResponse {
                state: ParticipantState::PUnknown as i32,
                found: false,
            }))
        }
    }

    async fn heartbeat(
        &self,
        request: Request<HeartbeatRequest>,
    ) -> Result<Response<HeartbeatResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement heartbeat handling
        // 1. Update last seen timestamp for the sender
        // 2. Detect coordinator failures
        // 3. Trigger election if coordinator is down

        let _ = (req.node_id, req.timestamp, req.is_coordinator);

        Ok(Response::new(HeartbeatResponse {
            acknowledged: true,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_millis() as i64,
        }))
    }

    async fn elect_coordinator(
        &self,
        request: Request<ElectCoordinatorRequest>,
    ) -> Result<Response<ElectCoordinatorResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement coordinator election voting
        // 1. Compare candidate term with current term
        // 2. Vote for candidate if term is higher
        // 3. Update current coordinator if election succeeds

        let current_term = *self.current_term.read().await;

        let _ = req.candidate_id;

        Ok(Response::new(ElectCoordinatorResponse {
            vote_granted: false,
            current_coordinator: self.node_id.clone(),
            current_term,
        }))
    }
}

// =============================================================================
// Command Line Arguments
// =============================================================================

#[derive(Parser, Debug)]
#[command(name = "three-phase-commit-server")]
#[command(about = "Three-Phase Commit protocol implementation")]
struct Args {
    /// Unique identifier for this node
    #[arg(long)]
    node_id: String,

    /// Port to listen on
    #[arg(long, default_value_t = 50051)]
    port: u16,

    /// Role of this node (coordinator or participant)
    #[arg(long)]
    role: String,

    /// Comma-separated list of participant addresses (for coordinator)
    #[arg(long, default_value = "")]
    participants: String,

    /// Coordinator address (for participant)
    #[arg(long, default_value = "")]
    coordinator: String,
}

// =============================================================================
// Main Entry Point
// =============================================================================

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    let role = if args.role == "coordinator" {
        NodeRole::Coordinator
    } else {
        NodeRole::Participant
    };

    let participants: Vec<String> = args
        .participants
        .split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    let coordinator = if args.coordinator.is_empty() {
        None
    } else {
        Some(args.coordinator)
    };

    let node = Arc::new(ThreePhaseCommitNode::new(
        args.node_id.clone(),
        args.port,
        role,
        participants,
        coordinator,
    ));

    // Note: initialize() needs to be implemented
    // node.initialize().await?;

    let addr = format!("0.0.0.0:{}", args.port).parse()?;
    println!(
        "Starting 3PC {} node {} on port {}",
        args.role, args.node_id, args.port
    );

    let mut builder = Server::builder();

    // Add appropriate services based on role
    if role == NodeRole::Coordinator {
        builder = builder.add_service(CoordinatorServiceServer::new(node.clone()));
    }

    // Both coordinator and participant can handle participant and node services
    builder
        .add_service(ParticipantServiceServer::new(node.clone()))
        .add_service(NodeServiceServer::new(node.clone()))
        .serve(addr)
        .await?;

    Ok(())
}
