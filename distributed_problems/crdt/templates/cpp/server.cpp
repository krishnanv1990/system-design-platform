/**
 * CRDT (Conflict-free Replicated Data Types) Implementation - C++ Template
 *
 * This template provides the basic structure for implementing distributed CRDTs
 * for eventual consistency without coordination. You need to implement the TODO sections.
 *
 * CRDTs are data structures that can be replicated across nodes where:
 * 1. Updates can happen concurrently on any replica
 * 2. Replicas can merge states without conflicts
 * 3. All replicas converge to the same state eventually
 *
 * Supported CRDT types:
 * - G-Counter (grow-only counter)
 * - PN-Counter (positive-negative counter)
 * - G-Set (grow-only set)
 * - OR-Set (observed-remove set)
 * - LWW-Register (last-writer-wins register)
 * - MV-Register (multi-value register)
 *
 * Usage:
 *     ./server --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <set>
#include <memory>
#include <mutex>
#include <shared_mutex>
#include <sstream>
#include <random>
#include <chrono>

#include <grpcpp/grpcpp.h>
#include "crdt.grpc.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;
using grpc::Channel;
using grpc::ClientContext;

namespace crdt_impl {

// CRDT types
enum class CRDTType {
    G_COUNTER,
    PN_COUNTER,
    G_SET,
    OR_SET,
    LWW_REGISTER,
    MV_REGISTER
};

std::string typeToString(CRDTType type) {
    switch (type) {
        case CRDTType::G_COUNTER: return "G_COUNTER";
        case CRDTType::PN_COUNTER: return "PN_COUNTER";
        case CRDTType::G_SET: return "G_SET";
        case CRDTType::OR_SET: return "OR_SET";
        case CRDTType::LWW_REGISTER: return "LWW_REGISTER";
        case CRDTType::MV_REGISTER: return "MV_REGISTER";
        default: return "UNKNOWN";
    }
}

std::string generateUUID() {
    static std::random_device rd;
    static std::mt19937 gen(rd());
    static std::uniform_int_distribution<> dis(0, 15);
    static const char* hex = "0123456789abcdef";

    std::string uuid(36, '-');
    for (int i = 0; i < 36; i++) {
        if (i == 8 || i == 13 || i == 18 || i == 23) continue;
        uuid[i] = hex[dis(gen)];
    }
    return uuid;
}

int64_t currentTimeMillis() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
}

// Vector clock for tracking causality
struct VectorClock {
    std::map<std::string, uint64_t> clock;

    void increment(const std::string& node_id) {
        clock[node_id]++;
    }

    uint64_t get(const std::string& node_id) const {
        auto it = clock.find(node_id);
        return it != clock.end() ? it->second : 0;
    }

    // TODO: Implement merge
    void merge(const VectorClock& other) {
        // TODO: Implement vector clock merge
        // For each entry in other, take the max with our entry
    }

    // TODO: Implement comparison
    bool happensBefore(const VectorClock& other) const {
        // TODO: Implement happens-before relation
        // Return true if this clock happens before other
        return false;  // Stub
    }

    bool concurrent(const VectorClock& other) const {
        // TODO: Implement concurrent check
        // Return true if neither clock happens before the other
        return false;  // Stub
    }
};

// G-Counter state (grow-only counter)
struct GCounter {
    std::map<std::string, uint64_t> counts;

    int64_t value() const {
        // TODO: Implement value computation
        // Sum all counts from all nodes
        return 0;  // Stub
    }

    void increment(const std::string& node_id, uint64_t amount = 1) {
        // TODO: Implement increment
        // Increment the count for this node
    }

    void merge(const GCounter& other) {
        // TODO: Implement merge
        // For each node, take the max count
    }
};

// PN-Counter state (positive-negative counter)
struct PNCounter {
    std::map<std::string, uint64_t> positive;
    std::map<std::string, uint64_t> negative;

    int64_t value() const {
        // TODO: Implement value computation
        // Sum(positive) - Sum(negative)
        return 0;  // Stub
    }

    void increment(const std::string& node_id, uint64_t amount = 1) {
        // TODO: Implement increment
    }

    void decrement(const std::string& node_id, uint64_t amount = 1) {
        // TODO: Implement decrement
    }

    void merge(const PNCounter& other) {
        // TODO: Implement merge
        // For each node, take the max of positive and negative counts
    }
};

// G-Set state (grow-only set)
struct GSet {
    std::set<std::string> elements;

    bool contains(const std::string& element) const {
        return elements.find(element) != elements.end();
    }

    void add(const std::string& element) {
        // TODO: Implement add
    }

    void merge(const GSet& other) {
        // TODO: Implement merge (union of sets)
    }
};

// OR-Set element with unique tag
struct ORSetElement {
    std::string value;
    std::string unique_tag;
    std::string added_by;
};

// OR-Set state (observed-remove set)
struct ORSet {
    std::map<std::string, ORSetElement> elements;  // tag -> element
    std::set<std::string> tombstones;              // removed tags

    std::set<std::string> getElements() const {
        // TODO: Implement get elements
        // Return values of elements not in tombstones
        return {};  // Stub
    }

    bool contains(const std::string& value) const {
        // TODO: Implement contains check
        return false;  // Stub
    }

    void add(const std::string& value, const std::string& node_id) {
        // TODO: Implement add
        // Generate unique tag and add element
    }

    void remove(const std::string& value) {
        // TODO: Implement remove
        // Find all tags for this value and add to tombstones
    }

    void merge(const ORSet& other) {
        // TODO: Implement merge
        // Union of elements, union of tombstones, then filter
    }
};

// LWW-Register state (last-writer-wins register)
struct LWWRegister {
    std::string value;
    int64_t timestamp = 0;
    std::string writer;

    void set(const std::string& new_value, const std::string& node_id, int64_t ts = 0) {
        // TODO: Implement set
        // Update value if ts > timestamp (or use current time if ts == 0)
    }

    void merge(const LWWRegister& other) {
        // TODO: Implement merge
        // Keep the value with the higher timestamp
    }
};

// MV-Register value
struct MVRegisterValue {
    std::string value;
    VectorClock version;
};

// MV-Register state (multi-value register)
struct MVRegister {
    std::vector<MVRegisterValue> values;

    std::vector<std::string> get() const {
        // TODO: Implement get
        // Return all concurrent values
        return {};  // Stub
    }

    void set(const std::string& value, const std::string& node_id, VectorClock& clock) {
        // TODO: Implement set
        // Increment clock and replace all values with new one
    }

    void merge(const MVRegister& other) {
        // TODO: Implement merge
        // Keep all concurrent values, remove dominated ones
    }
};

// Generic CRDT wrapper
struct CRDTState {
    std::string crdt_id;
    CRDTType type;
    VectorClock version;
    int64_t created_at;
    int64_t last_updated;

    // Type-specific state (only one will be used based on type)
    GCounter g_counter;
    PNCounter pn_counter;
    GSet g_set;
    ORSet or_set;
    LWWRegister lww_register;
    MVRegister mv_register;
};

/**
 * CRDTNode implements both gRPC services:
 * - CRDTService: handles client operations
 * - ReplicationService: handles node-to-node sync
 */
class CRDTNode final :
    public crdt::CRDTService::Service,
    public crdt::ReplicationService::Service {
public:
    CRDTNode(const std::string& node_id, int port, const std::vector<std::string>& peers)
        : node_id_(node_id), port_(port), peers_(peers) {}

    void Initialize() {
        // TODO: Implement initialization
        // 1. Create gRPC stubs for all peer nodes
        // 2. Start background sync thread for periodic state exchange
        // 3. Start anti-entropy protocol

        for (const auto& peer : peers_) {
            auto channel = grpc::CreateChannel(peer, grpc::InsecureChannelCredentials());
            peer_stubs_[peer] = crdt::ReplicationService::NewStub(channel);
        }

        std::cout << "CRDT node " << node_id_ << " initialized with "
                  << peers_.size() << " peers" << std::endl;
    }

    // ========================================================================
    // CRDTService - Counter Operations
    // ========================================================================

    Status IncrementCounter(ServerContext* ctx,
                           const crdt::IncrementCounterRequest* req,
                           crdt::IncrementCounterResponse* res) override {
        (void)ctx;

        // TODO: Implement counter increment
        // 1. Find or create the counter
        // 2. Increment the local count for this node
        // 3. Update version clock
        // 4. Trigger async replication to peers

        std::unique_lock<std::shared_mutex> lock(mutex_);

        auto it = crdts_.find(req->counter_id());
        if (it == crdts_.end()) {
            // Create new G-Counter
            CRDTState state;
            state.crdt_id = req->counter_id();
            state.type = CRDTType::G_COUNTER;
            state.created_at = currentTimeMillis();
            state.last_updated = state.created_at;
            crdts_[req->counter_id()] = state;
            it = crdts_.find(req->counter_id());
        }

        // Stub: Not implemented
        res->set_success(false);
        res->set_error("Not implemented - implement counter increment");
        res->set_served_by(node_id_);
        return Status::OK;
    }

    Status DecrementCounter(ServerContext* ctx,
                           const crdt::DecrementCounterRequest* req,
                           crdt::DecrementCounterResponse* res) override {
        (void)ctx;

        // TODO: Implement counter decrement (only for PN-Counter)
        // 1. Find the counter (must be PN-Counter type)
        // 2. Increment the negative count for this node
        // 3. Update version clock
        // 4. Trigger async replication to peers

        std::unique_lock<std::shared_mutex> lock(mutex_);

        auto it = crdts_.find(req->counter_id());
        if (it == crdts_.end()) {
            res->set_success(false);
            res->set_error("Counter not found");
            return Status::OK;
        }

        if (it->second.type != CRDTType::PN_COUNTER) {
            res->set_success(false);
            res->set_error("Decrement only supported for PN-Counter");
            return Status::OK;
        }

        // Stub: Not implemented
        res->set_success(false);
        res->set_error("Not implemented - implement counter decrement");
        res->set_served_by(node_id_);
        return Status::OK;
    }

    Status GetCounter(ServerContext* ctx,
                     const crdt::GetCounterRequest* req,
                     crdt::GetCounterResponse* res) override {
        (void)ctx;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        auto it = crdts_.find(req->counter_id());
        if (it == crdts_.end()) {
            res->set_found(false);
            return Status::OK;
        }

        res->set_found(true);
        if (it->second.type == CRDTType::G_COUNTER) {
            res->set_value(it->second.g_counter.value());
            res->set_type(crdt::CRDTType::G_COUNTER);
        } else if (it->second.type == CRDTType::PN_COUNTER) {
            res->set_value(it->second.pn_counter.value());
            res->set_type(crdt::CRDTType::PN_COUNTER);
        }
        return Status::OK;
    }

    // ========================================================================
    // CRDTService - Set Operations
    // ========================================================================

    Status AddToSet(ServerContext* ctx,
                   const crdt::AddToSetRequest* req,
                   crdt::AddToSetResponse* res) override {
        (void)ctx;

        // TODO: Implement set add
        // 1. Find or create the set
        // 2. Add element (with unique tag for OR-Set)
        // 3. Update version clock
        // 4. Trigger async replication to peers

        std::unique_lock<std::shared_mutex> lock(mutex_);

        // Stub: Not implemented
        res->set_success(false);
        res->set_error("Not implemented - implement set add");
        res->set_served_by(node_id_);
        return Status::OK;
    }

    Status RemoveFromSet(ServerContext* ctx,
                        const crdt::RemoveFromSetRequest* req,
                        crdt::RemoveFromSetResponse* res) override {
        (void)ctx;

        // TODO: Implement set remove (only for OR-Set)
        // 1. Find the set (must be OR-Set type)
        // 2. Add all tags for this element to tombstones
        // 3. Update version clock
        // 4. Trigger async replication to peers

        std::unique_lock<std::shared_mutex> lock(mutex_);

        auto it = crdts_.find(req->set_id());
        if (it == crdts_.end()) {
            res->set_success(false);
            res->set_error("Set not found");
            return Status::OK;
        }

        if (it->second.type != CRDTType::OR_SET) {
            res->set_success(false);
            res->set_error("Remove only supported for OR-Set");
            return Status::OK;
        }

        // Stub: Not implemented
        res->set_success(false);
        res->set_error("Not implemented - implement set remove");
        res->set_served_by(node_id_);
        return Status::OK;
    }

    Status GetSet(ServerContext* ctx,
                 const crdt::GetSetRequest* req,
                 crdt::GetSetResponse* res) override {
        (void)ctx;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        auto it = crdts_.find(req->set_id());
        if (it == crdts_.end()) {
            res->set_found(false);
            return Status::OK;
        }

        res->set_found(true);
        // TODO: Return elements based on set type
        return Status::OK;
    }

    Status ContainsInSet(ServerContext* ctx,
                        const crdt::ContainsInSetRequest* req,
                        crdt::ContainsInSetResponse* res) override {
        (void)ctx;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        auto it = crdts_.find(req->set_id());
        if (it == crdts_.end()) {
            res->set_found(false);
            return Status::OK;
        }

        res->set_found(true);
        // TODO: Check contains based on set type
        res->set_contains(false);  // Stub
        return Status::OK;
    }

    // ========================================================================
    // CRDTService - Register Operations
    // ========================================================================

    Status SetRegister(ServerContext* ctx,
                      const crdt::SetRegisterRequest* req,
                      crdt::SetRegisterResponse* res) override {
        (void)ctx;

        // TODO: Implement register set
        // 1. Find or create the register
        // 2. Update value with timestamp (LWW) or vector clock (MV)
        // 3. Trigger async replication to peers

        std::unique_lock<std::shared_mutex> lock(mutex_);

        // Stub: Not implemented
        res->set_success(false);
        res->set_error("Not implemented - implement register set");
        res->set_served_by(node_id_);
        return Status::OK;
    }

    Status GetRegister(ServerContext* ctx,
                      const crdt::GetRegisterRequest* req,
                      crdt::GetRegisterResponse* res) override {
        (void)ctx;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        auto it = crdts_.find(req->register_id());
        if (it == crdts_.end()) {
            res->set_found(false);
            return Status::OK;
        }

        res->set_found(true);
        // TODO: Return value(s) based on register type
        return Status::OK;
    }

    // ========================================================================
    // CRDTService - Generic Operations
    // ========================================================================

    Status CreateCRDT(ServerContext* ctx,
                     const crdt::CreateCRDTRequest* req,
                     crdt::CreateCRDTResponse* res) override {
        (void)ctx;

        // TODO: Implement CRDT creation
        // 1. Check if CRDT already exists
        // 2. Create new CRDT with specified type
        // 3. Initialize empty state

        std::unique_lock<std::shared_mutex> lock(mutex_);

        if (crdts_.find(req->crdt_id()) != crdts_.end()) {
            res->set_success(true);
            res->set_already_exists(true);
            return Status::OK;
        }

        CRDTState state;
        state.crdt_id = req->crdt_id();
        state.type = static_cast<CRDTType>(req->type());
        state.created_at = currentTimeMillis();
        state.last_updated = state.created_at;
        crdts_[req->crdt_id()] = state;

        res->set_success(true);
        res->set_already_exists(false);
        return Status::OK;
    }

    Status DeleteCRDT(ServerContext* ctx,
                     const crdt::DeleteCRDTRequest* req,
                     crdt::DeleteCRDTResponse* res) override {
        (void)ctx;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        auto it = crdts_.find(req->crdt_id());
        if (it == crdts_.end()) {
            res->set_success(false);
            res->set_error("CRDT not found");
            return Status::OK;
        }

        crdts_.erase(it);
        res->set_success(true);
        return Status::OK;
    }

    Status GetCRDTState(ServerContext* ctx,
                       const crdt::GetCRDTStateRequest* req,
                       crdt::GetCRDTStateResponse* res) override {
        (void)ctx;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        auto it = crdts_.find(req->crdt_id());
        if (it == crdts_.end()) {
            res->set_found(false);
            return Status::OK;
        }

        res->set_found(true);
        // TODO: Populate state message
        return Status::OK;
    }

    Status GetLeader(ServerContext* ctx,
                    const crdt::GetLeaderRequest* req,
                    crdt::GetLeaderResponse* res) override {
        (void)ctx; (void)req;

        // CRDTs are leaderless, but we track a coordinator for admin
        res->set_node_id(node_id_);
        res->set_node_address("0.0.0.0:" + std::to_string(port_));
        res->set_is_coordinator(is_coordinator_);
        return Status::OK;
    }

    Status GetClusterStatus(ServerContext* ctx,
                           const crdt::GetClusterStatusRequest* req,
                           crdt::GetClusterStatusResponse* res) override {
        (void)ctx; (void)req;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        res->set_node_id(node_id_);
        res->set_node_address("0.0.0.0:" + std::to_string(port_));
        res->set_is_coordinator(is_coordinator_);
        res->set_total_nodes(static_cast<uint32_t>(peers_.size() + 1));
        res->set_total_crdts(crdts_.size());
        res->set_total_merges(merge_count_);

        for (const auto& peer : peers_) {
            auto* member = res->add_members();
            member->set_address(peer);
        }

        return Status::OK;
    }

    // ========================================================================
    // ReplicationService Implementation
    // ========================================================================

    Status Merge(ServerContext* ctx,
                const crdt::MergeRequest* req,
                crdt::MergeResponse* res) override {
        (void)ctx;

        // TODO: Implement CRDT merge
        // 1. Get the incoming CRDT state
        // 2. Find or create local CRDT
        // 3. Merge states using CRDT-specific merge function
        // 4. Return merged state

        std::unique_lock<std::shared_mutex> lock(mutex_);

        // Stub: Not implemented
        res->set_success(false);
        res->set_error("Not implemented - implement CRDT merge");
        return Status::OK;
    }

    Status SyncAll(ServerContext* ctx,
                  const crdt::SyncAllRequest* req,
                  crdt::SyncAllResponse* res) override {
        (void)ctx;

        // TODO: Implement full sync
        // 1. For each incoming CRDT state, merge with local
        // 2. Track statistics

        std::unique_lock<std::shared_mutex> lock(mutex_);

        uint64_t merged = 0;
        uint64_t new_count = 0;

        // Stub: Not implemented
        res->set_success(false);
        res->set_error("Not implemented - implement full sync");
        res->set_merged_count(merged);
        res->set_new_count(new_count);
        return Status::OK;
    }

    Status Heartbeat(ServerContext* ctx,
                    const crdt::HeartbeatRequest* req,
                    crdt::HeartbeatResponse* res) override {
        (void)ctx; (void)req;

        res->set_acknowledged(true);
        res->set_timestamp(currentTimeMillis());
        return Status::OK;
    }

    Status GetLocalCRDTs(ServerContext* ctx,
                        const crdt::GetLocalCRDTsRequest* req,
                        crdt::GetLocalCRDTsResponse* res) override {
        (void)ctx; (void)req;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        res->set_total_count(crdts_.size());
        // TODO: Populate CRDT states
        return Status::OK;
    }

private:
    std::string node_id_;
    int port_;
    std::vector<std::string> peers_;
    bool is_coordinator_ = false;

    std::map<std::string, CRDTState> crdts_;
    std::map<std::string, std::unique_ptr<crdt::ReplicationService::Stub>> peer_stubs_;

    uint64_t merge_count_ = 0;

    mutable std::shared_mutex mutex_;
};

}  // namespace crdt_impl

std::vector<std::string> split(const std::string& s, char delimiter) {
    std::vector<std::string> tokens;
    std::string token;
    std::istringstream tokenStream(s);
    while (std::getline(tokenStream, token, delimiter)) {
        token.erase(0, token.find_first_not_of(" \t"));
        token.erase(token.find_last_not_of(" \t") + 1);
        if (!token.empty()) tokens.push_back(token);
    }
    return tokens;
}

int main(int argc, char** argv) {
    std::string node_id, peers_str;
    int port = 50051;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--node-id" && i + 1 < argc) node_id = argv[++i];
        else if (arg == "--port" && i + 1 < argc) port = std::stoi(argv[++i]);
        else if (arg == "--peers" && i + 1 < argc) peers_str = argv[++i];
    }

    if (node_id.empty()) {
        std::cerr << "Usage: " << argv[0]
                  << " --node-id <id> --port <port> [--peers peer1:port,peer2:port]" << std::endl;
        return 1;
    }

    std::vector<std::string> peers = split(peers_str, ',');

    crdt_impl::CRDTNode node(node_id, port, peers);
    node.Initialize();

    std::string server_address = "0.0.0.0:" + std::to_string(port);
    ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());

    builder.RegisterService(static_cast<crdt::CRDTService::Service*>(&node));
    builder.RegisterService(static_cast<crdt::ReplicationService::Service*>(&node));

    std::unique_ptr<Server> server(builder.BuildAndStart());
    std::cout << "Starting CRDT node " << node_id << " on port " << port << std::endl;

    server->Wait();
    return 0;
}
