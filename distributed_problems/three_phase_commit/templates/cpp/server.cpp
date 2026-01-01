/**
 * Three-Phase Commit (3PC) Implementation - C++ Template
 *
 * This template provides the basic structure for implementing the Three-Phase Commit
 * protocol for distributed transactions. You need to implement the TODO sections.
 *
 * Three-Phase Commit improves on 2PC by adding a pre-commit phase:
 * 1. Phase 1 (CanCommit): Coordinator asks if participants can commit
 * 2. Phase 2 (PreCommit): If all agree, coordinator sends pre-commit
 * 3. Phase 3 (DoCommit): Coordinator sends final commit/abort
 *
 * Key difference from 2PC: Participants can recover from coordinator failure
 * by communicating with each other (non-blocking property)
 *
 * Usage:
 *     ./server --node-id coord --port 50051 --role coordinator --participants p1:50052,p2:50053
 *     ./server --node-id p1 --port 50052 --role participant --coordinator coord:50051
 */

#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <memory>
#include <mutex>
#include <shared_mutex>
#include <sstream>
#include <random>
#include <chrono>

#include <grpcpp/grpcpp.h>
#include "three_phase_commit.grpc.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;
using grpc::Channel;
using grpc::ClientContext;

namespace tpc3 {

// Node role in the cluster
enum class NodeRole { COORDINATOR, PARTICIPANT };

// Transaction states from the coordinator perspective
enum class TxnState {
    UNKNOWN,
    INITIATED,
    WAITING,
    PRECOMMIT,
    COMMITTING,
    COMMITTED,
    ABORTING,
    ABORTED
};

// Participant states
enum class ParticipantState {
    INITIAL,
    UNCERTAIN,      // Received CanCommit, voted YES
    PRECOMMITTED,   // Received PreCommit
    COMMITTED,
    ABORTED
};

std::string roleToString(NodeRole role) {
    return role == NodeRole::COORDINATOR ? "coordinator" : "participant";
}

std::string stateToString(TxnState state) {
    switch (state) {
        case TxnState::UNKNOWN: return "UNKNOWN";
        case TxnState::INITIATED: return "INITIATED";
        case TxnState::WAITING: return "WAITING";
        case TxnState::PRECOMMIT: return "PRECOMMIT";
        case TxnState::COMMITTING: return "COMMITTING";
        case TxnState::COMMITTED: return "COMMITTED";
        case TxnState::ABORTING: return "ABORTING";
        case TxnState::ABORTED: return "ABORTED";
        default: return "UNKNOWN";
    }
}

std::string participantStateToString(ParticipantState state) {
    switch (state) {
        case ParticipantState::INITIAL: return "INITIAL";
        case ParticipantState::UNCERTAIN: return "UNCERTAIN";
        case ParticipantState::PRECOMMITTED: return "PRECOMMITTED";
        case ParticipantState::COMMITTED: return "COMMITTED";
        case ParticipantState::ABORTED: return "ABORTED";
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

// Coordinator-side transaction state
struct Transaction {
    std::string id;
    TxnState state = TxnState::INITIATED;
    std::vector<std::string> participants;
    std::string coordinator;
    std::map<std::string, bool> votes;
    std::map<std::string, std::string> data;
    int64_t start_time;
    int64_t last_update;
    uint32_t timeout_ms;
};

// Participant-side transaction state
struct ParticipantTxnInfo {
    std::string transaction_id;
    ParticipantState state = ParticipantState::INITIAL;
    bool vote = false;
    std::map<std::string, std::string> data;
    int64_t last_update;
};

/**
 * ThreePhaseCommitNode implements all three gRPC services:
 * - CoordinatorService: handles client transaction requests
 * - ParticipantService: handles coordinator requests
 * - NodeService: handles inter-node communication for failure recovery
 */
class ThreePhaseCommitNode final :
    public three_phase_commit::CoordinatorService::Service,
    public three_phase_commit::ParticipantService::Service,
    public three_phase_commit::NodeService::Service {
public:
    ThreePhaseCommitNode(const std::string& node_id, int port, NodeRole role,
                         const std::vector<std::string>& participants,
                         const std::string& coordinator)
        : node_id_(node_id), port_(port), role_(role),
          participants_(participants), coordinator_addr_(coordinator),
          is_coordinator_(role == NodeRole::COORDINATOR) {}

    /**
     * Initialize the node:
     * - For coordinator: create stubs to all participants
     * - For participant: create stub to coordinator and other participants
     */
    void Initialize() {
        // TODO: Implement initialization
        // 1. Create gRPC stubs for communicating with other nodes
        // 2. For coordinator: create ParticipantService stubs for all participants
        // 3. For participant: create NodeService stub for querying other participants
        // 4. Start background threads for heartbeat and timeout monitoring

        if (role_ == NodeRole::COORDINATOR) {
            for (const auto& p : participants_) {
                auto channel = grpc::CreateChannel(p, grpc::InsecureChannelCredentials());
                participant_stubs_[p] = three_phase_commit::ParticipantService::NewStub(channel);
            }
            std::cout << "Coordinator " << node_id_ << " initialized with "
                      << participants_.size() << " participants" << std::endl;
        } else {
            std::cout << "Participant " << node_id_ << " initialized, coordinator: "
                      << coordinator_addr_ << std::endl;
        }
    }

    // ========================================================================
    // CoordinatorService Implementation
    // ========================================================================

    Status BeginTransaction(ServerContext* ctx,
                           const three_phase_commit::BeginTransactionRequest* req,
                           three_phase_commit::BeginTransactionResponse* res) override {
        (void)ctx;

        // TODO: Implement begin transaction
        // 1. Generate a unique transaction ID
        // 2. Store transaction state as INITIATED
        // 3. Record participating nodes
        // 4. Return transaction ID to client

        std::unique_lock<std::shared_mutex> lock(mutex_);

        std::string txn_id = generateUUID();

        Transaction txn;
        txn.id = txn_id;
        txn.state = TxnState::INITIATED;
        txn.coordinator = node_id_;
        txn.start_time = currentTimeMillis();
        txn.last_update = txn.start_time;
        txn.timeout_ms = req->timeout_ms() > 0 ? req->timeout_ms() : 30000;

        // Use specified participants or default to all known participants
        if (req->participants_size() > 0) {
            for (const auto& p : req->participants()) {
                txn.participants.push_back(p);
            }
        } else {
            txn.participants = participants_;
        }

        for (const auto& [key, value] : req->data()) {
            txn.data[key] = value;
        }

        transactions_[txn_id] = txn;

        res->set_success(true);
        res->set_transaction_id(txn_id);
        return Status::OK;
    }

    Status CommitTransaction(ServerContext* ctx,
                            const three_phase_commit::CommitTransactionRequest* req,
                            three_phase_commit::CommitTransactionResponse* res) override {
        (void)ctx;

        // TODO: Implement 3PC protocol
        // Phase 1 (CanCommit):
        // 1. Send CanCommit to all participants
        // 2. Wait for votes from all participants
        // 3. If any votes NO or times out, abort
        //
        // Phase 2 (PreCommit):
        // 4. If all voted YES, send PreCommit to all participants
        // 5. Wait for acknowledgments
        // 6. If any fails, abort
        //
        // Phase 3 (DoCommit):
        // 7. Send DoCommit to all participants
        // 8. Wait for confirmations
        // 9. Mark transaction as committed

        std::unique_lock<std::shared_mutex> lock(mutex_);

        auto it = transactions_.find(req->transaction_id());
        if (it == transactions_.end()) {
            res->set_success(false);
            res->set_error("Transaction not found");
            return Status::OK;
        }

        // Stub: Not implemented
        res->set_success(false);
        res->set_error("Not implemented - implement 3PC protocol");
        return Status::OK;
    }

    Status AbortTransaction(ServerContext* ctx,
                           const three_phase_commit::AbortTransactionRequest* req,
                           three_phase_commit::AbortTransactionResponse* res) override {
        (void)ctx;

        // TODO: Implement abort
        // 1. Send DoAbort to all participants
        // 2. Update transaction state to ABORTED
        // 3. Clean up any held resources

        std::unique_lock<std::shared_mutex> lock(mutex_);

        auto it = transactions_.find(req->transaction_id());
        if (it == transactions_.end()) {
            res->set_success(false);
            res->set_error("Transaction not found");
            return Status::OK;
        }

        // Stub: Mark as aborted without notifying participants
        it->second.state = TxnState::ABORTED;
        it->second.last_update = currentTimeMillis();

        res->set_success(true);
        return Status::OK;
    }

    Status GetTransactionStatus(ServerContext* ctx,
                               const three_phase_commit::GetTransactionStatusRequest* req,
                               three_phase_commit::GetTransactionStatusResponse* res) override {
        (void)ctx;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        auto it = transactions_.find(req->transaction_id());
        if (it != transactions_.end()) {
            res->set_found(true);
            auto* txn = res->mutable_transaction();
            txn->set_transaction_id(it->second.id);
            txn->set_state(static_cast<three_phase_commit::TransactionState>(it->second.state));
            txn->set_coordinator(it->second.coordinator);
            txn->set_start_time(it->second.start_time);
            txn->set_last_update(it->second.last_update);
        } else {
            res->set_found(false);
        }
        return Status::OK;
    }

    Status GetLeader(ServerContext* ctx,
                    const three_phase_commit::GetLeaderRequest* req,
                    three_phase_commit::GetLeaderResponse* res) override {
        (void)ctx; (void)req;

        res->set_node_id(node_id_);
        res->set_node_address("0.0.0.0:" + std::to_string(port_));
        res->set_is_coordinator(is_coordinator_);
        return Status::OK;
    }

    Status GetClusterStatus(ServerContext* ctx,
                           const three_phase_commit::GetClusterStatusRequest* req,
                           three_phase_commit::GetClusterStatusResponse* res) override {
        (void)ctx; (void)req;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        res->set_node_id(node_id_);
        res->set_node_address("0.0.0.0:" + std::to_string(port_));
        res->set_is_coordinator(is_coordinator_);
        res->set_total_nodes(static_cast<uint32_t>(participants_.size() + 1));
        res->set_active_transactions(transactions_.size());

        for (const auto& p : participants_) {
            auto* member = res->add_members();
            member->set_address(p);
            member->set_is_coordinator(false);
        }

        return Status::OK;
    }

    // ========================================================================
    // ParticipantService Implementation
    // ========================================================================

    Status CanCommit(ServerContext* ctx,
                    const three_phase_commit::CanCommitRequest* req,
                    three_phase_commit::CanCommitResponse* res) override {
        (void)ctx;

        // TODO: Implement Phase 1 (CanCommit) participant logic
        // 1. Check if the transaction can be committed (validate data, check locks, etc.)
        // 2. If YES:
        //    - Acquire necessary locks
        //    - Log the CanCommit decision
        //    - Move to UNCERTAIN state
        //    - Vote YES
        // 3. If NO:
        //    - Vote NO with reason
        //    - Stay in INITIAL state

        std::unique_lock<std::shared_mutex> lock(mutex_);

        ParticipantTxnInfo info;
        info.transaction_id = req->transaction_id();
        info.state = ParticipantState::INITIAL;
        info.last_update = currentTimeMillis();

        for (const auto& [key, value] : req->data()) {
            info.data[key] = value;
        }

        participant_txns_[req->transaction_id()] = info;

        // Stub: Vote NO by default
        res->set_vote(false);
        res->set_error("Not implemented - implement CanCommit logic");
        return Status::OK;
    }

    Status PreCommit(ServerContext* ctx,
                    const three_phase_commit::PreCommitRequest* req,
                    three_phase_commit::PreCommitResponse* res) override {
        (void)ctx;

        // TODO: Implement Phase 2 (PreCommit) participant logic
        // 1. Verify we're in UNCERTAIN state
        // 2. Log the PreCommit
        // 3. Move to PRECOMMITTED state
        // 4. Acknowledge the PreCommit

        std::unique_lock<std::shared_mutex> lock(mutex_);

        auto it = participant_txns_.find(req->transaction_id());
        if (it == participant_txns_.end()) {
            res->set_acknowledged(false);
            res->set_error("Transaction not found");
            return Status::OK;
        }

        // Stub: Not implemented
        res->set_acknowledged(false);
        res->set_error("Not implemented - implement PreCommit logic");
        return Status::OK;
    }

    Status DoCommit(ServerContext* ctx,
                   const three_phase_commit::DoCommitRequest* req,
                   three_phase_commit::DoCommitResponse* res) override {
        (void)ctx;

        // TODO: Implement Phase 3 (DoCommit) participant logic
        // 1. Verify we're in PRECOMMITTED state
        // 2. Apply the changes permanently
        // 3. Release locks
        // 4. Move to COMMITTED state
        // 5. Log the commit

        std::unique_lock<std::shared_mutex> lock(mutex_);

        auto it = participant_txns_.find(req->transaction_id());
        if (it == participant_txns_.end()) {
            res->set_success(false);
            res->set_error("Transaction not found");
            return Status::OK;
        }

        // Stub: Not implemented
        res->set_success(false);
        res->set_error("Not implemented - implement DoCommit logic");
        return Status::OK;
    }

    Status DoAbort(ServerContext* ctx,
                  const three_phase_commit::DoAbortRequest* req,
                  three_phase_commit::DoAbortResponse* res) override {
        (void)ctx;

        // TODO: Implement abort participant logic
        // 1. Roll back any changes
        // 2. Release locks
        // 3. Move to ABORTED state
        // 4. Log the abort

        std::unique_lock<std::shared_mutex> lock(mutex_);

        auto it = participant_txns_.find(req->transaction_id());
        if (it == participant_txns_.end()) {
            res->set_acknowledged(true);  // Already cleaned up
            return Status::OK;
        }

        it->second.state = ParticipantState::ABORTED;
        it->second.last_update = currentTimeMillis();

        res->set_acknowledged(true);
        return Status::OK;
    }

    Status GetState(ServerContext* ctx,
                   const three_phase_commit::GetStateRequest* req,
                   three_phase_commit::GetStateResponse* res) override {
        (void)ctx;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        auto it = participant_txns_.find(req->transaction_id());
        if (it != participant_txns_.end()) {
            res->set_found(true);
            auto* info = res->mutable_info();
            info->set_node_id(node_id_);
            info->set_transaction_id(it->second.transaction_id);
            info->set_state(static_cast<three_phase_commit::ParticipantState>(it->second.state));
            info->set_vote(it->second.vote);
            info->set_last_update(it->second.last_update);
        } else {
            res->set_found(false);
        }
        return Status::OK;
    }

    // ========================================================================
    // NodeService Implementation (Inter-node communication for recovery)
    // ========================================================================

    Status QueryState(ServerContext* ctx,
                     const three_phase_commit::QueryStateRequest* req,
                     three_phase_commit::QueryStateResponse* res) override {
        (void)ctx;

        // TODO: Implement state query for failure recovery
        // 1. Look up the transaction state
        // 2. Return current participant state
        // This is used by other participants to determine outcome during coordinator failure

        std::shared_lock<std::shared_mutex> lock(mutex_);

        auto it = participant_txns_.find(req->transaction_id());
        if (it != participant_txns_.end()) {
            res->set_found(true);
            res->set_state(static_cast<three_phase_commit::ParticipantState>(it->second.state));
        } else {
            res->set_found(false);
        }
        return Status::OK;
    }

    Status Heartbeat(ServerContext* ctx,
                    const three_phase_commit::HeartbeatRequest* req,
                    three_phase_commit::HeartbeatResponse* res) override {
        (void)ctx; (void)req;

        res->set_acknowledged(true);
        res->set_timestamp(currentTimeMillis());
        return Status::OK;
    }

    Status ElectCoordinator(ServerContext* ctx,
                           const three_phase_commit::ElectCoordinatorRequest* req,
                           three_phase_commit::ElectCoordinatorResponse* res) override {
        (void)ctx;

        // TODO: Implement coordinator election
        // 1. Compare candidate's term with current term
        // 2. If candidate's term is higher and we haven't voted, grant vote
        // 3. Return current coordinator info

        std::unique_lock<std::shared_mutex> lock(mutex_);

        // Stub: Always deny vote
        res->set_vote_granted(false);
        res->set_current_coordinator(node_id_);
        res->set_current_term(current_term_);
        return Status::OK;
    }

private:
    std::string node_id_;
    int port_;
    NodeRole role_;
    std::vector<std::string> participants_;
    std::string coordinator_addr_;
    bool is_coordinator_;

    // Coordinator state
    std::map<std::string, Transaction> transactions_;
    std::map<std::string, std::unique_ptr<three_phase_commit::ParticipantService::Stub>> participant_stubs_;

    // Participant state
    std::map<std::string, ParticipantTxnInfo> participant_txns_;

    // Election state
    int64_t current_term_ = 0;

    mutable std::shared_mutex mutex_;
};

}  // namespace tpc3

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
    std::string node_id, role_str, participants_str, coordinator;
    int port = 50051;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--node-id" && i + 1 < argc) node_id = argv[++i];
        else if (arg == "--port" && i + 1 < argc) port = std::stoi(argv[++i]);
        else if (arg == "--role" && i + 1 < argc) role_str = argv[++i];
        else if (arg == "--participants" && i + 1 < argc) participants_str = argv[++i];
        else if (arg == "--coordinator" && i + 1 < argc) coordinator = argv[++i];
    }

    if (node_id.empty() || role_str.empty()) {
        std::cerr << "Usage: " << argv[0]
                  << " --node-id <id> --port <port> --role <coordinator|participant>"
                  << " [--participants p1:port,p2:port] [--coordinator addr:port]" << std::endl;
        return 1;
    }

    tpc3::NodeRole role = (role_str == "coordinator") ? tpc3::NodeRole::COORDINATOR : tpc3::NodeRole::PARTICIPANT;
    std::vector<std::string> participants = split(participants_str, ',');

    tpc3::ThreePhaseCommitNode node(node_id, port, role, participants, coordinator);
    node.Initialize();

    std::string server_address = "0.0.0.0:" + std::to_string(port);
    ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());

    // Register all services
    builder.RegisterService(static_cast<three_phase_commit::CoordinatorService::Service*>(&node));
    builder.RegisterService(static_cast<three_phase_commit::ParticipantService::Service*>(&node));
    builder.RegisterService(static_cast<three_phase_commit::NodeService::Service*>(&node));

    std::unique_ptr<Server> server(builder.BuildAndStart());
    std::cout << "Starting 3PC " << role_str << " node " << node_id << " on port " << port << std::endl;

    server->Wait();
    return 0;
}
