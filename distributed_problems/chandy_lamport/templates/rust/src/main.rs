/**
 * Chandy-Lamport Snapshot Algorithm Implementation - Rust Template
 *
 * This template provides the basic structure for implementing the Chandy-Lamport
 * algorithm for capturing consistent global snapshots. You need to implement the TODO sections.
 *
 * Based on: "Distributed Snapshots: Determining Global States of Distributed Systems"
 * by K. Mani Chandy and Leslie Lamport (1985)
 *
 * Usage:
 *     cargo run -- --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

use clap::Parser;
use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::sync::RwLock;
use tonic::{transport::Server, Request, Response, Status};
use uuid::Uuid;

pub mod chandy_lamport {
    tonic::include_proto!("chandy_lamport");
}

use chandy_lamport::snapshot_service_server::{SnapshotService, SnapshotServiceServer};
use chandy_lamport::bank_service_server::{BankService, BankServiceServer};
use chandy_lamport::key_value_service_server::{KeyValueService, KeyValueServiceServer};
use chandy_lamport::*;

// ============================================================================
// Data Structures
// ============================================================================

#[derive(Clone, Default)]
struct ChannelState {
    from_process: String,
    to_process: String,
    messages: Vec<ApplicationMessage>,
    is_recording: bool,
}

#[derive(Clone, Default)]
struct SnapshotState {
    snapshot_id: String,
    initiator_id: String,
    local_state_recorded: bool,
    logical_clock: u64,
    account_balances: HashMap<String, i64>,
    kv_state: HashMap<String, String>,
    channel_states: HashMap<String, ChannelState>,
    markers_received: HashSet<String>,
    recording_complete: bool,
    initiated_at: u64,
    completed_at: u64,
}

struct ChandyLamportNode {
    node_id: String,
    port: u16,
    peers: Vec<String>,

    logical_clock: u64,
    snapshots: HashMap<String, SnapshotState>,
    current_snapshot_id: Option<String>,

    incoming_channels: HashMap<String, ChannelState>,
    account_balances: HashMap<String, i64>,
    kv_store: HashMap<String, String>,

    snapshots_initiated: u64,
    snapshots_participated: u64,
}

impl ChandyLamportNode {
    fn new(node_id: String, port: u16, peers: Vec<String>) -> Self {
        let mut account_balances = HashMap::new();
        account_balances.insert(format!("{}_account", node_id), 1000);

        ChandyLamportNode {
            node_id,
            port,
            peers,
            logical_clock: 0,
            snapshots: HashMap::new(),
            current_snapshot_id: None,
            incoming_channels: HashMap::new(),
            account_balances,
            kv_store: HashMap::new(),
            snapshots_initiated: 0,
            snapshots_participated: 0,
        }
    }

    fn increment_clock(&mut self) -> u64 {
        self.logical_clock += 1;
        self.logical_clock
    }

    fn update_clock(&mut self, received_clock: u64) {
        self.logical_clock = std::cmp::max(self.logical_clock, received_clock) + 1;
    }

    fn current_time_ms() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_millis() as u64
    }
}

type SharedNode = Arc<RwLock<ChandyLamportNode>>;

// ============================================================================
// Snapshot Service Implementation
// ============================================================================

struct SnapshotServiceImpl {
    node: SharedNode,
}

#[tonic::async_trait]
impl SnapshotService for SnapshotServiceImpl {
    /// Initiate a new global snapshot.
    ///
    /// TODO: Implement snapshot initiation:
    /// 1. Generate unique snapshot ID
    /// 2. Record local state immediately
    /// 3. Start recording on all incoming channels
    /// 4. Send marker on all outgoing channels
    async fn initiate_snapshot(
        &self,
        request: Request<InitiateSnapshotRequest>,
    ) -> Result<Response<InitiateSnapshotResponse>, Status> {
        let mut node = self.node.write().await;
        let req = request.into_inner();

        let snapshot_id = if req.snapshot_id.is_empty() {
            Uuid::new_v4().to_string()
        } else {
            req.snapshot_id
        };

        // TODO: Implement snapshot initiation
        // - Record local state (account balances, kv_store, logical clock)
        // - Create SnapshotState
        // - Start recording on all incoming channels
        // - Send markers to all peers

        node.snapshots_initiated += 1;

        Ok(Response::new(InitiateSnapshotResponse {
            success: true,
            snapshot_id,
            error: String::new(),
            initiated_at: ChandyLamportNode::current_time_ms(),
        }))
    }

    /// Handle incoming marker message.
    ///
    /// TODO: Implement marker handling:
    /// 1. If first marker for this snapshot:
    ///    - Record local state
    ///    - Mark sender's channel as empty
    ///    - Start recording on other incoming channels
    ///    - Send markers on all outgoing channels
    /// 2. If not first marker:
    ///    - Stop recording on sender's channel
    ///    - Check if snapshot is complete
    async fn receive_marker(
        &self,
        request: Request<MarkerMessage>,
    ) -> Result<Response<MarkerResponse>, Status> {
        let mut node = self.node.write().await;
        let req = request.into_inner();

        let snapshot_id = req.snapshot_id.clone();
        let _sender_id = req.sender_id.clone();

        node.update_clock(req.logical_clock);

        let first_marker = !node.snapshots.contains_key(&snapshot_id);

        if first_marker {
            // TODO: Implement first marker handling
            node.snapshots_participated += 1;
        } else {
            // TODO: Implement subsequent marker handling
        }

        Ok(Response::new(MarkerResponse {
            success: true,
            first_marker,
            process_id: node.node_id.clone(),
        }))
    }

    async fn send_message(
        &self,
        request: Request<ApplicationMessage>,
    ) -> Result<Response<SendMessageResponse>, Status> {
        let mut node = self.node.write().await;
        node.increment_clock();

        // TODO: Forward message to destination

        Ok(Response::new(SendMessageResponse {
            success: true,
            error: String::new(),
        }))
    }

    async fn get_snapshot(
        &self,
        request: Request<GetSnapshotRequest>,
    ) -> Result<Response<GetSnapshotResponse>, Status> {
        let node = self.node.read().await;
        let req = request.into_inner();

        if let Some(snapshot) = node.snapshots.get(&req.snapshot_id) {
            let local_state = ProcessState {
                process_id: node.node_id.clone(),
                state_data: vec![],
                logical_clock: snapshot.logical_clock,
                account_balances: snapshot.account_balances.clone(),
                kv_state: snapshot.kv_state.clone(),
            };

            let channel_states: Vec<chandy_lamport::ChannelState> = snapshot
                .channel_states
                .values()
                .map(|cs| chandy_lamport::ChannelState {
                    from_process: cs.from_process.clone(),
                    to_process: cs.to_process.clone(),
                    messages: cs.messages.clone(),
                })
                .collect();

            Ok(Response::new(GetSnapshotResponse {
                found: true,
                snapshot_id: req.snapshot_id,
                local_state: Some(local_state),
                channel_states,
                recording_complete: snapshot.recording_complete,
                error: String::new(),
            }))
        } else {
            Ok(Response::new(GetSnapshotResponse {
                found: false,
                snapshot_id: req.snapshot_id,
                local_state: None,
                channel_states: vec![],
                recording_complete: false,
                error: String::new(),
            }))
        }
    }

    async fn get_global_snapshot(
        &self,
        request: Request<GetGlobalSnapshotRequest>,
    ) -> Result<Response<GetGlobalSnapshotResponse>, Status> {
        let node = self.node.read().await;
        let req = request.into_inner();

        if !node.snapshots.contains_key(&req.snapshot_id) {
            return Ok(Response::new(GetGlobalSnapshotResponse {
                success: false,
                snapshot_id: req.snapshot_id,
                process_states: vec![],
                channel_states: vec![],
                initiated_at: 0,
                completed_at: 0,
                initiator_id: String::new(),
                is_complete: false,
                error: "Snapshot not found".to_string(),
                total_value: 0,
            }));
        }

        // TODO: Collect snapshots from all peers and combine
        Ok(Response::new(GetGlobalSnapshotResponse {
            success: false,
            snapshot_id: req.snapshot_id,
            process_states: vec![],
            channel_states: vec![],
            initiated_at: 0,
            completed_at: 0,
            initiator_id: String::new(),
            is_complete: false,
            error: "Not implemented".to_string(),
            total_value: 0,
        }))
    }
}

// ============================================================================
// Bank Service Implementation
// ============================================================================

struct BankServiceImpl {
    node: SharedNode,
}

#[tonic::async_trait]
impl BankService for BankServiceImpl {
    async fn get_balance(
        &self,
        request: Request<GetBalanceRequest>,
    ) -> Result<Response<GetBalanceResponse>, Status> {
        let node = self.node.read().await;
        let req = request.into_inner();

        let balance = node.account_balances.get(&req.account_id);
        Ok(Response::new(GetBalanceResponse {
            balance: balance.copied().unwrap_or(0),
            found: balance.is_some(),
            error: String::new(),
        }))
    }

    async fn transfer(
        &self,
        request: Request<TransferRequest>,
    ) -> Result<Response<TransferResponse>, Status> {
        let mut node = self.node.write().await;
        let req = request.into_inner();

        let from_balance = node.account_balances.get(&req.from_account).copied();
        if from_balance.is_none() {
            return Ok(Response::new(TransferResponse {
                success: false,
                error: "Source account not found".to_string(),
                from_balance: 0,
                to_balance: 0,
            }));
        }

        let from_balance = from_balance.unwrap();
        if from_balance < req.amount {
            return Ok(Response::new(TransferResponse {
                success: false,
                error: "Insufficient funds".to_string(),
                from_balance,
                to_balance: 0,
            }));
        }

        // TODO: For cross-process transfers, send message to destination
        node.account_balances.insert(req.from_account.clone(), from_balance - req.amount);
        let to_balance = node.account_balances.entry(req.to_account.clone()).or_insert(0);
        *to_balance += req.amount;

        Ok(Response::new(TransferResponse {
            success: true,
            error: String::new(),
            from_balance: from_balance - req.amount,
            to_balance: *to_balance,
        }))
    }

    async fn deposit(
        &self,
        request: Request<DepositRequest>,
    ) -> Result<Response<DepositResponse>, Status> {
        let mut node = self.node.write().await;
        let req = request.into_inner();

        let balance = node.account_balances.entry(req.account_id).or_insert(0);
        *balance += req.amount;

        Ok(Response::new(DepositResponse {
            success: true,
            new_balance: *balance,
            error: String::new(),
        }))
    }

    async fn withdraw(
        &self,
        _request: Request<WithdrawRequest>,
    ) -> Result<Response<WithdrawResponse>, Status> {
        Ok(Response::new(WithdrawResponse {
            success: false,
            new_balance: 0,
            error: "Not implemented".to_string(),
        }))
    }
}

// ============================================================================
// KeyValue Service Implementation
// ============================================================================

struct KeyValueServiceImpl {
    node: SharedNode,
}

#[tonic::async_trait]
impl KeyValueService for KeyValueServiceImpl {
    async fn get(
        &self,
        request: Request<GetRequest>,
    ) -> Result<Response<GetResponse>, Status> {
        let node = self.node.read().await;
        let req = request.into_inner();

        let value = node.kv_store.get(&req.key);
        Ok(Response::new(GetResponse {
            value: value.cloned().unwrap_or_default(),
            found: value.is_some(),
            error: String::new(),
        }))
    }

    async fn put(
        &self,
        request: Request<PutRequest>,
    ) -> Result<Response<PutResponse>, Status> {
        let mut node = self.node.write().await;
        let req = request.into_inner();

        node.kv_store.insert(req.key, req.value);
        Ok(Response::new(PutResponse {
            success: true,
            error: String::new(),
            leader_hint: String::new(),
        }))
    }

    async fn delete(
        &self,
        request: Request<DeleteRequest>,
    ) -> Result<Response<DeleteResponse>, Status> {
        let mut node = self.node.write().await;
        let req = request.into_inner();

        node.kv_store.remove(&req.key);
        Ok(Response::new(DeleteResponse {
            success: true,
            error: String::new(),
            leader_hint: String::new(),
        }))
    }

    async fn get_leader(
        &self,
        _request: Request<GetLeaderRequest>,
    ) -> Result<Response<GetLeaderResponse>, Status> {
        let node = self.node.read().await;
        Ok(Response::new(GetLeaderResponse {
            initiator_id: node.node_id.clone(),
            initiator_address: String::new(),
            is_initiator: true,
        }))
    }

    async fn get_cluster_status(
        &self,
        _request: Request<GetClusterStatusRequest>,
    ) -> Result<Response<GetClusterStatusResponse>, Status> {
        let node = self.node.read().await;

        let members: Vec<ClusterMember> = node
            .peers
            .iter()
            .map(|peer| ClusterMember {
                node_id: String::new(),
                address: peer.clone(),
                is_healthy: true,
                last_seen_clock: 0,
            })
            .collect();

        Ok(Response::new(GetClusterStatusResponse {
            node_id: node.node_id.clone(),
            logical_clock: node.logical_clock,
            is_recording: node.current_snapshot_id.is_some(),
            current_snapshot_id: node.current_snapshot_id.clone().unwrap_or_default(),
            channel_recording: vec![],
            snapshots_initiated: node.snapshots_initiated,
            snapshots_participated: node.snapshots_participated,
            members,
        }))
    }
}

// ============================================================================
// Main Entry Point
// ============================================================================

#[derive(Parser)]
#[command(name = "Chandy-Lamport Server")]
struct Args {
    #[arg(long)]
    node_id: String,

    #[arg(long, default_value = "50051")]
    port: u16,

    #[arg(long)]
    peers: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    let peers: Vec<String> = args
        .peers
        .split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    let node = Arc::new(RwLock::new(ChandyLamportNode::new(
        args.node_id.clone(),
        args.port,
        peers,
    )));

    let addr = format!("0.0.0.0:{}", args.port).parse()?;

    println!(
        "Starting Chandy-Lamport node {} on {}",
        args.node_id, addr
    );

    Server::builder()
        .add_service(SnapshotServiceServer::new(SnapshotServiceImpl {
            node: node.clone(),
        }))
        .add_service(BankServiceServer::new(BankServiceImpl {
            node: node.clone(),
        }))
        .add_service(KeyValueServiceServer::new(KeyValueServiceImpl {
            node: node.clone(),
        }))
        .serve(addr)
        .await?;

    Ok(())
}
