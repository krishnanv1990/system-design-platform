//! CRDT (Conflict-free Replicated Data Types) Implementation - Rust Template
//!
//! This template provides the basic structure for implementing CRDTs for
//! eventual consistency without coordination.
//!
//! CRDTs are data structures that can be replicated across nodes where:
//! 1. Updates can happen concurrently on any replica
//! 2. Replicas can merge states without conflicts
//! 3. All replicas converge to the same state eventually
//!
//! Supported CRDT types:
//! - G-Counter (grow-only counter)
//! - PN-Counter (positive-negative counter)
//! - G-Set (grow-only set)
//! - OR-Set (observed-remove set)
//! - LWW-Register (last-writer-wins register)
//! - MV-Register (multi-value register)
//!
//! You need to implement the TODO sections.
//!
//! Usage:
//!     cargo run -- --node-id node1 --port 50051 --peers node2:50052,node3:50053

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tonic::{transport::Server, Request, Response, Status};
use clap::Parser;
use uuid::Uuid;

pub mod crdt {
    tonic::include_proto!("crdt");
}

use crdt::crdt_service_server::{CrdtService, CrdtServiceServer};
use crdt::replication_service_server::{ReplicationService, ReplicationServiceServer};
use crdt::replication_service_client::ReplicationServiceClient;
use crdt::*;

// =============================================================================
// CRDT Type Definitions
// =============================================================================

/// Vector clock for tracking causality
#[derive(Clone, Debug, Default)]
pub struct LocalVectorClock {
    pub clock: HashMap<String, u64>,
}

impl LocalVectorClock {
    pub fn new() -> Self {
        Self { clock: HashMap::new() }
    }

    pub fn increment(&mut self, _node_id: &str) {
        // TODO: Increment the clock for the given node
        todo!("Implement vector clock increment")
    }

    pub fn merge(&mut self, _other: &LocalVectorClock) {
        // TODO: Merge with another vector clock (take max of each entry)
        todo!("Implement vector clock merge")
    }

    pub fn compare(&self, _other: &LocalVectorClock) -> std::cmp::Ordering {
        // TODO: Compare two vector clocks
        // Returns Less if self happened-before other
        // Returns Greater if other happened-before self
        // Returns Equal if concurrent
        todo!("Implement vector clock comparison")
    }
}

/// G-Counter (grow-only counter)
#[derive(Clone, Debug, Default)]
pub struct GCounter {
    pub counts: HashMap<String, u64>,
}

impl GCounter {
    pub fn new() -> Self {
        Self { counts: HashMap::new() }
    }

    pub fn increment(&mut self, _node_id: &str, _amount: u64) {
        // TODO: Increment the counter for this node
        // Each node only increments its own entry
        todo!("Implement G-Counter increment")
    }

    pub fn value(&self) -> u64 {
        // TODO: Return the total value (sum of all nodes' counts)
        todo!("Implement G-Counter value")
    }

    pub fn merge(&mut self, _other: &GCounter) {
        // TODO: Merge with another G-Counter (take max of each entry)
        todo!("Implement G-Counter merge")
    }
}

/// PN-Counter (positive-negative counter)
#[derive(Clone, Debug, Default)]
pub struct PNCounter {
    pub positive: GCounter,
    pub negative: GCounter,
}

impl PNCounter {
    pub fn new() -> Self {
        Self {
            positive: GCounter::new(),
            negative: GCounter::new(),
        }
    }

    pub fn increment(&mut self, _node_id: &str, _amount: u64) {
        // TODO: Increment the positive counter
        todo!("Implement PN-Counter increment")
    }

    pub fn decrement(&mut self, _node_id: &str, _amount: u64) {
        // TODO: Increment the negative counter
        todo!("Implement PN-Counter decrement")
    }

    pub fn value(&self) -> i64 {
        // TODO: Return positive.value() - negative.value()
        todo!("Implement PN-Counter value")
    }

    pub fn merge(&mut self, _other: &PNCounter) {
        // TODO: Merge both positive and negative counters
        todo!("Implement PN-Counter merge")
    }
}

/// G-Set (grow-only set)
#[derive(Clone, Debug, Default)]
pub struct GSet {
    pub elements: std::collections::HashSet<String>,
}

impl GSet {
    pub fn new() -> Self {
        Self { elements: std::collections::HashSet::new() }
    }

    pub fn add(&mut self, _element: String) {
        // TODO: Add element to the set
        todo!("Implement G-Set add")
    }

    pub fn contains(&self, _element: &str) -> bool {
        // TODO: Check if element is in the set
        todo!("Implement G-Set contains")
    }

    pub fn merge(&mut self, _other: &GSet) {
        // TODO: Union of the two sets
        todo!("Implement G-Set merge")
    }
}

/// OR-Set element with unique tag
#[derive(Clone, Debug)]
pub struct ORSetElement {
    pub value: String,
    pub unique_tag: String,
    pub added_by: String,
}

/// OR-Set (observed-remove set)
#[derive(Clone, Debug, Default)]
pub struct ORSet {
    pub elements: Vec<ORSetElement>,
    pub tombstones: std::collections::HashSet<String>,
}

impl ORSet {
    pub fn new() -> Self {
        Self {
            elements: Vec::new(),
            tombstones: std::collections::HashSet::new(),
        }
    }

    pub fn add(&mut self, _value: String, _node_id: &str) {
        // TODO: Add element with unique tag
        // Generate unique tag for this add operation
        todo!("Implement OR-Set add")
    }

    pub fn remove(&mut self, _value: &str) {
        // TODO: Remove element by adding all its tags to tombstones
        // This removes all versions of the element seen so far
        todo!("Implement OR-Set remove")
    }

    pub fn contains(&self, _value: &str) -> bool {
        // TODO: Check if any non-tombstoned version of element exists
        todo!("Implement OR-Set contains")
    }

    pub fn elements(&self) -> Vec<String> {
        // TODO: Return all unique values that are not tombstoned
        todo!("Implement OR-Set elements")
    }

    pub fn merge(&mut self, _other: &ORSet) {
        // TODO: Merge two OR-Sets
        // 1. Union of all elements
        // 2. Union of all tombstones
        // 3. Filter out tombstoned elements
        todo!("Implement OR-Set merge")
    }
}

/// LWW-Register (last-writer-wins register)
#[derive(Clone, Debug, Default)]
pub struct LWWRegister {
    pub value: String,
    pub timestamp: i64,
    pub writer: String,
}

impl LWWRegister {
    pub fn new() -> Self {
        Self {
            value: String::new(),
            timestamp: 0,
            writer: String::new(),
        }
    }

    pub fn set(&mut self, _value: String, _timestamp: i64, _writer: &str) {
        // TODO: Set value if timestamp is newer
        todo!("Implement LWW-Register set")
    }

    pub fn get(&self) -> &str {
        // TODO: Return current value
        todo!("Implement LWW-Register get")
    }

    pub fn merge(&mut self, _other: &LWWRegister) {
        // TODO: Keep the value with the higher timestamp
        // Use writer ID as tiebreaker if timestamps are equal
        todo!("Implement LWW-Register merge")
    }
}

/// MV-Register value with version
#[derive(Clone, Debug)]
pub struct MVRegisterValue {
    pub value: String,
    pub version: LocalVectorClock,
}

/// MV-Register (multi-value register)
#[derive(Clone, Debug, Default)]
pub struct MVRegister {
    pub values: Vec<MVRegisterValue>,
}

impl MVRegister {
    pub fn new() -> Self {
        Self { values: Vec::new() }
    }

    pub fn set(&mut self, _value: String, _version: LocalVectorClock) {
        // TODO: Set value with version
        // Remove any values that are dominated by this version
        todo!("Implement MV-Register set")
    }

    pub fn get(&self) -> Vec<String> {
        // TODO: Return all concurrent values
        todo!("Implement MV-Register get")
    }

    pub fn merge(&mut self, _other: &MVRegister) {
        // TODO: Merge two MV-Registers
        // Keep only values that are not dominated by any other
        todo!("Implement MV-Register merge")
    }
}

// =============================================================================
// CRDT Wrapper Enum
// =============================================================================

#[derive(Clone, Debug)]
pub enum CrdtData {
    GCounter(GCounter),
    PNCounter(PNCounter),
    GSet(GSet),
    ORSet(ORSet),
    LWWRegister(LWWRegister),
    MVRegister(MVRegister),
}

#[derive(Clone, Debug)]
pub struct CrdtEntry {
    pub id: String,
    pub data: CrdtData,
    pub version: LocalVectorClock,
    pub created_at: i64,
    pub last_updated: i64,
}

// =============================================================================
// Main Node Structure
// =============================================================================

pub struct CrdtNode {
    node_id: String,
    port: u16,
    peers: Vec<String>,

    // CRDT storage
    crdts: RwLock<HashMap<String, CrdtEntry>>,

    // Statistics
    total_merges: RwLock<u64>,

    // Peer clients for replication
    peer_clients: RwLock<HashMap<String, ReplicationServiceClient<tonic::transport::Channel>>>,
}

impl CrdtNode {
    pub fn new(node_id: String, port: u16, peers: Vec<String>) -> Self {
        Self {
            node_id,
            port,
            peers,
            crdts: RwLock::new(HashMap::new()),
            total_merges: RwLock::new(0),
            peer_clients: RwLock::new(HashMap::new()),
        }
    }

    pub async fn initialize(&self) -> Result<(), Box<dyn std::error::Error>> {
        // TODO: Initialize peer connections and start background sync
        // 1. Connect to all peers
        // 2. Start periodic sync task
        // 3. Start anti-entropy protocol
        todo!("Implement node initialization")
    }

    async fn replicate_to_peers(&self, _crdt_id: &str) -> Result<(), String> {
        // TODO: Replicate CRDT state to all peers
        // 1. Get current CRDT state
        // 2. Send merge request to all peers
        // 3. Handle failures gracefully
        todo!("Implement peer replication")
    }

    fn get_current_timestamp(&self) -> i64 {
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis() as i64
    }
}

// =============================================================================
// CRDTService Implementation
// =============================================================================

#[tonic::async_trait]
impl CrdtService for Arc<CrdtNode> {
    // =========================================================================
    // Counter Operations
    // =========================================================================

    async fn increment_counter(
        &self,
        request: Request<IncrementCounterRequest>,
    ) -> Result<Response<IncrementCounterResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement counter increment
        // 1. Get or create counter (G-Counter or PN-Counter)
        // 2. Increment by amount
        // 3. Update version
        // 4. Replicate to peers

        let _ = (req.counter_id, req.amount);

        Ok(Response::new(IncrementCounterResponse {
            success: false,
            value: 0,
            error: "TODO: Implement counter increment".to_string(),
            served_by: self.node_id.clone(),
        }))
    }

    async fn decrement_counter(
        &self,
        request: Request<DecrementCounterRequest>,
    ) -> Result<Response<DecrementCounterResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement counter decrement (PN-Counter only)
        // 1. Get or create PN-Counter
        // 2. Decrement by amount
        // 3. Update version
        // 4. Replicate to peers

        let _ = (req.counter_id, req.amount);

        Ok(Response::new(DecrementCounterResponse {
            success: false,
            value: 0,
            error: "TODO: Implement counter decrement".to_string(),
            served_by: self.node_id.clone(),
        }))
    }

    async fn get_counter(
        &self,
        request: Request<GetCounterRequest>,
    ) -> Result<Response<GetCounterResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement get counter value
        // 1. Look up counter
        // 2. Return current value

        let _ = req.counter_id;

        Ok(Response::new(GetCounterResponse {
            value: 0,
            found: false,
            r#type: CrdtType::GCounter as i32,
            error: "TODO: Implement get counter".to_string(),
        }))
    }

    // =========================================================================
    // Set Operations
    // =========================================================================

    async fn add_to_set(
        &self,
        request: Request<AddToSetRequest>,
    ) -> Result<Response<AddToSetResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement set add
        // 1. Get or create set (G-Set or OR-Set)
        // 2. Add element
        // 3. Update version
        // 4. Replicate to peers

        let _ = (req.set_id, req.element);

        Ok(Response::new(AddToSetResponse {
            success: false,
            size: 0,
            error: "TODO: Implement set add".to_string(),
            served_by: self.node_id.clone(),
        }))
    }

    async fn remove_from_set(
        &self,
        request: Request<RemoveFromSetRequest>,
    ) -> Result<Response<RemoveFromSetResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement set remove (OR-Set only)
        // 1. Get OR-Set
        // 2. Remove element (add to tombstones)
        // 3. Update version
        // 4. Replicate to peers

        let _ = (req.set_id, req.element);

        Ok(Response::new(RemoveFromSetResponse {
            success: false,
            was_present: false,
            size: 0,
            error: "TODO: Implement set remove".to_string(),
            served_by: self.node_id.clone(),
        }))
    }

    async fn get_set(
        &self,
        request: Request<GetSetRequest>,
    ) -> Result<Response<GetSetResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement get set elements
        // 1. Look up set
        // 2. Return all elements

        let _ = req.set_id;

        Ok(Response::new(GetSetResponse {
            elements: vec![],
            size: 0,
            found: false,
            r#type: CrdtType::GSet as i32,
            error: "TODO: Implement get set".to_string(),
        }))
    }

    async fn contains_in_set(
        &self,
        request: Request<ContainsInSetRequest>,
    ) -> Result<Response<ContainsInSetResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement set contains check
        // 1. Look up set
        // 2. Check if element is present

        let _ = (req.set_id, req.element);

        Ok(Response::new(ContainsInSetResponse {
            contains: false,
            found: false,
            error: "TODO: Implement contains check".to_string(),
        }))
    }

    // =========================================================================
    // Register Operations
    // =========================================================================

    async fn set_register(
        &self,
        request: Request<SetRegisterRequest>,
    ) -> Result<Response<SetRegisterResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement register set
        // 1. Get or create register (LWW or MV)
        // 2. Set value with timestamp
        // 3. Update version
        // 4. Replicate to peers

        let _ = (req.register_id, req.value, req.timestamp);

        Ok(Response::new(SetRegisterResponse {
            success: false,
            error: "TODO: Implement register set".to_string(),
            served_by: self.node_id.clone(),
        }))
    }

    async fn get_register(
        &self,
        request: Request<GetRegisterRequest>,
    ) -> Result<Response<GetRegisterResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement get register value
        // 1. Look up register
        // 2. Return value(s)

        let _ = req.register_id;

        Ok(Response::new(GetRegisterResponse {
            values: vec![],
            found: false,
            r#type: CrdtType::LwwRegister as i32,
            error: "TODO: Implement get register".to_string(),
        }))
    }

    // =========================================================================
    // Generic CRDT Operations
    // =========================================================================

    async fn create_crdt(
        &self,
        request: Request<CreateCrdtRequest>,
    ) -> Result<Response<CreateCrdtResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement CRDT creation
        // 1. Check if CRDT already exists
        // 2. Create new CRDT of specified type
        // 3. Initialize with empty state

        let _ = (req.crdt_id, req.r#type);

        Ok(Response::new(CreateCrdtResponse {
            success: false,
            already_exists: false,
            error: "TODO: Implement CRDT creation".to_string(),
        }))
    }

    async fn delete_crdt(
        &self,
        request: Request<DeleteCrdtRequest>,
    ) -> Result<Response<DeleteCrdtResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement CRDT deletion
        // Note: Deleting a CRDT is tricky in a distributed system
        // Consider using a tombstone approach

        let _ = req.crdt_id;

        Ok(Response::new(DeleteCrdtResponse {
            success: false,
            error: "TODO: Implement CRDT deletion".to_string(),
        }))
    }

    async fn get_crdt_state(
        &self,
        request: Request<GetCrdtStateRequest>,
    ) -> Result<Response<GetCrdtStateResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement get CRDT state
        // 1. Look up CRDT
        // 2. Serialize state to proto format

        let _ = req.crdt_id;

        Ok(Response::new(GetCrdtStateResponse {
            state: None,
            found: false,
            error: "TODO: Implement get CRDT state".to_string(),
        }))
    }

    // =========================================================================
    // Cluster Operations
    // =========================================================================

    async fn get_leader(
        &self,
        _request: Request<GetLeaderRequest>,
    ) -> Result<Response<GetLeaderResponse>, Status> {
        // Note: CRDTs are leaderless, but we track a coordinator for admin
        Ok(Response::new(GetLeaderResponse {
            node_id: self.node_id.clone(),
            node_address: format!("localhost:{}", self.port),
            is_coordinator: true, // All nodes are equal in CRDT
        }))
    }

    async fn get_cluster_status(
        &self,
        _request: Request<GetClusterStatusRequest>,
    ) -> Result<Response<GetClusterStatusResponse>, Status> {
        let crdts = self.crdts.read().await;
        let total_merges = *self.total_merges.read().await;

        let members: Vec<NodeInfo> = self.peers.iter().map(|p| {
            NodeInfo {
                node_id: String::new(),
                address: p.clone(),
                is_healthy: true,
                crdts_count: 0,
                last_heartbeat: 0,
            }
        }).collect();

        Ok(Response::new(GetClusterStatusResponse {
            node_id: self.node_id.clone(),
            node_address: format!("localhost:{}", self.port),
            is_coordinator: true,
            total_nodes: (self.peers.len() + 1) as u32,
            healthy_nodes: (self.peers.len() + 1) as u32,
            total_crdts: crdts.len() as u64,
            total_merges,
            members,
        }))
    }
}

// =============================================================================
// ReplicationService Implementation
// =============================================================================

#[tonic::async_trait]
impl ReplicationService for Arc<CrdtNode> {
    async fn merge(
        &self,
        request: Request<MergeRequest>,
    ) -> Result<Response<MergeResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement CRDT merge
        // 1. Deserialize incoming state
        // 2. Merge with local state using CRDT merge semantics
        // 3. Return merged state

        let _ = (req.source_node, req.state);

        Ok(Response::new(MergeResponse {
            success: false,
            merged_state: None,
            error: "TODO: Implement merge".to_string(),
        }))
    }

    async fn sync_all(
        &self,
        request: Request<SyncAllRequest>,
    ) -> Result<Response<SyncAllResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement full sync
        // 1. Merge all incoming states
        // 2. Track new and merged counts

        let _ = (req.source_node, req.states);

        Ok(Response::new(SyncAllResponse {
            success: false,
            merged_count: 0,
            new_count: 0,
            error: "TODO: Implement sync all".to_string(),
        }))
    }

    async fn heartbeat(
        &self,
        request: Request<HeartbeatRequest>,
    ) -> Result<Response<HeartbeatResponse>, Status> {
        let req = request.into_inner();

        // TODO: Implement heartbeat handling
        // 1. Update peer health status
        // 2. Trigger sync if needed

        let _ = (req.node_id, req.timestamp, req.crdts_count);

        Ok(Response::new(HeartbeatResponse {
            acknowledged: true,
            timestamp: self.get_current_timestamp(),
        }))
    }

    async fn get_local_crdts(
        &self,
        _request: Request<GetLocalCrdtsRequest>,
    ) -> Result<Response<GetLocalCrdtsResponse>, Status> {
        // TODO: Implement get all local CRDTs
        // 1. Serialize all local CRDT states

        Ok(Response::new(GetLocalCrdtsResponse {
            crdts: vec![],
            total_count: 0,
        }))
    }
}

// =============================================================================
// Command Line Arguments
// =============================================================================

#[derive(Parser, Debug)]
#[command(name = "crdt-server")]
#[command(about = "CRDT server implementation")]
struct Args {
    /// Unique identifier for this node
    #[arg(long)]
    node_id: String,

    /// Port to listen on
    #[arg(long, default_value_t = 50051)]
    port: u16,

    /// Comma-separated list of peer addresses
    #[arg(long, default_value = "")]
    peers: String,
}

// =============================================================================
// Main Entry Point
// =============================================================================

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    let peers: Vec<String> = args
        .peers
        .split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    let node = Arc::new(CrdtNode::new(
        args.node_id.clone(),
        args.port,
        peers,
    ));

    // Note: initialize() needs to be implemented
    // node.initialize().await?;

    let addr = format!("0.0.0.0:{}", args.port).parse()?;
    println!(
        "Starting CRDT node {} on port {}",
        args.node_id, args.port
    );

    Server::builder()
        .add_service(CrdtServiceServer::new(node.clone()))
        .add_service(ReplicationServiceServer::new(node.clone()))
        .serve(addr)
        .await?;

    Ok(())
}
