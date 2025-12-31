/**
 * Two-Phase Commit (2PC) Implementation - C++ Template
 *
 * This template provides the basic structure for implementing the Two-Phase Commit
 * protocol for distributed transactions. You need to implement the TODO sections.
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

#include <grpcpp/grpcpp.h>
#include "two_phase_commit.grpc.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;

namespace tpc {

enum class NodeRole { COORDINATOR, PARTICIPANT };
enum class TxnState { UNKNOWN, ACTIVE, PREPARING, PREPARED, COMMITTING, COMMITTED, ABORTING, ABORTED };

std::string roleToString(NodeRole role) {
    return role == NodeRole::COORDINATOR ? "coordinator" : "participant";
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

struct Transaction {
    std::string id;
    TxnState state = TxnState::ACTIVE;
    std::vector<std::string> participants;
    std::map<std::string, bool> votes;
};

struct ParticipantTxnState {
    std::string transaction_id;
    TxnState state = TxnState::ACTIVE;
    std::vector<std::string> locks_held;
};

class TwoPhaseCommitNode final :
    public two_phase_commit::CoordinatorService::Service,
    public two_phase_commit::ParticipantService::Service,
    public two_phase_commit::KeyValueService::Service {
public:
    TwoPhaseCommitNode(const std::string& node_id, int port, NodeRole role,
                       const std::vector<std::string>& participants,
                       const std::string& coordinator)
        : node_id_(node_id), port_(port), role_(role),
          participants_(participants), coordinator_addr_(coordinator) {}

    void Initialize() {
        if (role_ == NodeRole::COORDINATOR) {
            for (const auto& p : participants_) {
                auto channel = grpc::CreateChannel(p, grpc::InsecureChannelCredentials());
                participant_stubs_[p] = two_phase_commit::ParticipantService::NewStub(channel);
            }
            std::cout << "Coordinator " << node_id_ << " initialized with " << participants_.size() << " participants" << std::endl;
        } else {
            std::cout << "Participant " << node_id_ << " initialized" << std::endl;
        }
    }

    // CoordinatorService
    Status BeginTransaction(ServerContext* ctx, const two_phase_commit::BeginTransactionRequest* req,
                           two_phase_commit::BeginTransactionResponse* res) override {
        (void)ctx; (void)req;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        std::string txn_id = generateUUID();
        transactions_[txn_id] = Transaction{txn_id, TxnState::ACTIVE, participants_, {}};

        res->set_success(true);
        res->set_transaction_id(txn_id);
        return Status::OK;
    }

    Status CommitTransaction(ServerContext* ctx, const two_phase_commit::CommitTransactionRequest* req,
                            two_phase_commit::CommitTransactionResponse* res) override {
        (void)ctx;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        if (transactions_.find(req->transaction_id()) == transactions_.end()) {
            res->set_success(false);
            res->set_error("Transaction not found");
            return Status::OK;
        }

        // TODO: Implement 2PC protocol
        res->set_success(false);
        res->set_error("Not implemented");
        return Status::OK;
    }

    Status AbortTransaction(ServerContext* ctx, const two_phase_commit::AbortTransactionRequest* req,
                           two_phase_commit::AbortTransactionResponse* res) override {
        (void)ctx; (void)req;
        res->set_success(true);
        return Status::OK;
    }

    Status GetTransactionStatus(ServerContext* ctx, const two_phase_commit::GetTransactionStatusRequest* req,
                               two_phase_commit::GetTransactionStatusResponse* res) override {
        (void)ctx;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        auto it = transactions_.find(req->transaction_id());
        if (it != transactions_.end()) {
            res->set_found(true);
            res->set_transaction_id(it->second.id);
            res->set_state(static_cast<two_phase_commit::TransactionState>(it->second.state));
        } else {
            res->set_found(false);
        }
        return Status::OK;
    }

    Status ExecuteOperation(ServerContext* ctx, const two_phase_commit::ExecuteOperationRequest* req,
                           two_phase_commit::ExecuteOperationResponse* res) override {
        (void)ctx; (void)req;
        res->set_success(false);
        res->set_error("Not implemented");
        return Status::OK;
    }

    // ParticipantService
    Status Prepare(ServerContext* ctx, const two_phase_commit::PrepareRequest* req,
                   two_phase_commit::PrepareResponse* res) override {
        (void)ctx; (void)req;
        res->set_vote(false);
        return Status::OK;
    }

    Status Commit(ServerContext* ctx, const two_phase_commit::CommitRequest* req,
                  two_phase_commit::CommitResponse* res) override {
        (void)ctx; (void)req;
        res->set_success(true);
        return Status::OK;
    }

    Status Abort(ServerContext* ctx, const two_phase_commit::AbortRequest* req,
                 two_phase_commit::AbortResponse* res) override {
        (void)ctx; (void)req;
        res->set_success(true);
        return Status::OK;
    }

    Status GetStatus(ServerContext* ctx, const two_phase_commit::GetStatusRequest* req,
                     two_phase_commit::GetStatusResponse* res) override {
        (void)ctx;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        auto it = participant_states_.find(req->transaction_id());
        if (it != participant_states_.end()) {
            res->set_found(true);
            res->set_state(static_cast<two_phase_commit::TransactionState>(it->second.state));
        } else {
            res->set_found(false);
        }
        return Status::OK;
    }

    Status ExecuteLocal(ServerContext* ctx, const two_phase_commit::ExecuteLocalRequest* req,
                        two_phase_commit::ExecuteLocalResponse* res) override {
        (void)ctx; (void)req;
        res->set_success(false);
        res->set_error("Not implemented");
        return Status::OK;
    }

    // KeyValueService
    Status Get(ServerContext* ctx, const two_phase_commit::GetRequest* req,
               two_phase_commit::GetResponse* res) override {
        (void)ctx;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        auto it = kv_store_.find(req->key());
        if (it != kv_store_.end()) {
            res->set_value(it->second);
            res->set_found(true);
        } else {
            res->set_found(false);
        }
        return Status::OK;
    }

    Status Put(ServerContext* ctx, const two_phase_commit::PutRequest* req,
               two_phase_commit::PutResponse* res) override {
        (void)ctx; (void)req;
        if (role_ != NodeRole::COORDINATOR) {
            res->set_success(false);
            res->set_error("Not the coordinator");
            res->set_coordinator_hint(coordinator_addr_);
            return Status::OK;
        }
        res->set_success(false);
        res->set_error("Not implemented");
        return Status::OK;
    }

    Status Delete(ServerContext* ctx, const two_phase_commit::DeleteRequest* req,
                  two_phase_commit::DeleteResponse* res) override {
        (void)ctx; (void)req;
        if (role_ != NodeRole::COORDINATOR) {
            res->set_success(false);
            res->set_error("Not the coordinator");
            res->set_coordinator_hint(coordinator_addr_);
            return Status::OK;
        }
        res->set_success(false);
        res->set_error("Not implemented");
        return Status::OK;
    }

    Status GetLeader(ServerContext* ctx, const two_phase_commit::GetLeaderRequest* req,
                     two_phase_commit::GetLeaderResponse* res) override {
        (void)ctx; (void)req;
        res->set_coordinator_id(node_id_);
        res->set_is_coordinator(role_ == NodeRole::COORDINATOR);
        return Status::OK;
    }

    Status GetClusterStatus(ServerContext* ctx, const two_phase_commit::GetClusterStatusRequest* req,
                            two_phase_commit::GetClusterStatusResponse* res) override {
        (void)ctx; (void)req;
        res->set_node_id(node_id_);
        res->set_role(roleToString(role_));
        for (const auto& p : participants_) {
            auto* member = res->add_members();
            member->set_address(p);
            member->set_role("participant");
        }
        return Status::OK;
    }

private:
    std::string node_id_;
    int port_;
    NodeRole role_;
    std::vector<std::string> participants_;
    std::string coordinator_addr_;

    std::map<std::string, Transaction> transactions_;
    std::map<std::string, ParticipantTxnState> participant_states_;
    std::map<std::string, std::string> kv_store_;

    mutable std::shared_mutex mutex_;
    std::map<std::string, std::unique_ptr<two_phase_commit::ParticipantService::Stub>> participant_stubs_;
};

}  // namespace tpc

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
        std::cerr << "Usage: " << argv[0] << " --node-id <id> --port <port> --role <coordinator|participant>" << std::endl;
        return 1;
    }

    tpc::NodeRole role = (role_str == "coordinator") ? tpc::NodeRole::COORDINATOR : tpc::NodeRole::PARTICIPANT;
    std::vector<std::string> participants = split(participants_str, ',');

    tpc::TwoPhaseCommitNode node(node_id, port, role, participants, coordinator);
    node.Initialize();

    std::string server_address = "0.0.0.0:" + std::to_string(port);
    ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());

    if (role == tpc::NodeRole::COORDINATOR) {
        builder.RegisterService(static_cast<two_phase_commit::CoordinatorService::Service*>(&node));
    } else {
        builder.RegisterService(static_cast<two_phase_commit::ParticipantService::Service*>(&node));
    }
    builder.RegisterService(static_cast<two_phase_commit::KeyValueService::Service*>(&node));

    std::unique_ptr<Server> server(builder.BuildAndStart());
    std::cout << "Starting 2PC " << role_str << " node " << node_id << " on port " << port << std::endl;

    server->Wait();
    return 0;
}
