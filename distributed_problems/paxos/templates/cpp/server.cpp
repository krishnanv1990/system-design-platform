/**
 * Paxos Consensus Implementation - C++ Template
 *
 * This template provides the basic structure for implementing the Multi-Paxos
 * consensus algorithm. You need to implement the TODO sections.
 *
 * For the full Paxos specification, see: "Paxos Made Simple" by Leslie Lamport
 *
 * Usage:
 *     ./server --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <memory>
#include <mutex>
#include <shared_mutex>
#include <chrono>
#include <thread>
#include <atomic>
#include <sstream>
#include <algorithm>
#include <optional>

#include <grpcpp/grpcpp.h>
#include "paxos.grpc.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;
using grpc::Channel;
using grpc::ClientContext;

namespace paxos {

enum class NodeRole { PROPOSER, ACCEPTOR, LEARNER, LEADER };

std::string nodeRoleToString(NodeRole role) {
    switch (role) {
        case NodeRole::PROPOSER: return "proposer";
        case NodeRole::ACCEPTOR: return "acceptor";
        case NodeRole::LEARNER: return "learner";
        case NodeRole::LEADER: return "leader";
        default: return "unknown";
    }
}

// Internal structure for proposal numbers
struct ProposalNum {
    uint64_t round;
    std::string proposer_id;

    bool operator<(const ProposalNum& other) const {
        if (round != other.round) return round < other.round;
        return proposer_id < other.proposer_id;
    }

    bool operator<=(const ProposalNum& other) const {
        return *this < other || *this == other;
    }

    bool operator==(const ProposalNum& other) const {
        return round == other.round && proposer_id == other.proposer_id;
    }

    ::paxos::ProposalNumber toProto() const {
        ::paxos::ProposalNumber proto;
        proto.set_round(round);
        proto.set_proposer_id(proposer_id);
        return proto;
    }

    static ProposalNum fromProto(const ::paxos::ProposalNumber& proto) {
        return {proto.round(), proto.proposer_id()};
    }
};

// Acceptor state for each slot
struct AcceptorState {
    std::optional<ProposalNum> highest_promised;
    std::optional<ProposalNum> accepted_proposal;
    std::optional<std::vector<uint8_t>> accepted_value;
};

// Persistent and volatile state
struct PaxosStateStore {
    uint64_t current_round = 0;
    std::map<uint64_t, AcceptorState> acceptor_states;
    std::map<uint64_t, std::vector<uint8_t>> learned_values;
    uint64_t first_unchosen_slot = 0;
    uint64_t last_executed_slot = 0;
};

/**
 * Paxos consensus node implementation.
 *
 * TODO: Implement the core Paxos algorithm:
 * 1. Phase 1 (Prepare): Proposer sends prepare, acceptors promise
 * 2. Phase 2 (Accept): Proposer sends accept, acceptors accept
 * 3. Learning: Once value is chosen, notify learners
 * 4. Multi-Paxos: Leader election and optimization
 */
class PaxosNode final : public PaxosService::Service, public KeyValueService::Service {
public:
    PaxosNode(const std::string& node_id, int port, const std::vector<std::string>& peers)
        : node_id_(node_id), port_(port), peers_(peers),
          role_(NodeRole::ACCEPTOR),
          heartbeat_interval_(100), leader_timeout_(500),
          stop_threads_(false) {}

    ~PaxosNode() {
        stop_threads_ = true;
    }

    void Initialize() {
        for (const auto& peer : peers_) {
            auto channel = grpc::CreateChannel(peer, grpc::InsecureChannelCredentials());
            peer_stubs_[peer] = PaxosService::NewStub(channel);
        }
        std::cout << "Node " << node_id_ << " initialized with " << peers_.size() << " peers" << std::endl;
    }

    AcceptorState& GetAcceptorState(uint64_t slot) {
        if (state_.acceptor_states.find(slot) == state_.acceptor_states.end()) {
            state_.acceptor_states[slot] = AcceptorState{};
        }
        return state_.acceptor_states[slot];
    }

    ProposalNum GenerateProposalNumber() {
        state_.current_round++;
        return {state_.current_round, node_id_};
    }

    // =========================================================================
    // Phase 1: Prepare
    // =========================================================================

    /**
     * Send Prepare requests to all acceptors.
     *
     * TODO: Implement Phase 1a of Paxos:
     * 1. Send Prepare(n) to all acceptors
     * 2. Wait for responses from a majority
     * 3. If majority promise, return (true, highest_accepted_value)
     * 4. If any acceptor has accepted a value, use that value
     */
    std::pair<bool, std::optional<std::vector<uint8_t>>> SendPrepare(uint64_t slot, const ProposalNum& proposal) {
        return {false, std::nullopt};
    }

    /**
     * Handle Prepare RPC from a proposer.
     *
     * TODO: Implement Phase 1b of Paxos:
     * 1. If n > highest_promised, update highest_promised and promise
     * 2. Return (promised=True, accepted_proposal, accepted_value)
     * 3. Otherwise return (promised=False, highest_promised)
     */
    Status Prepare(ServerContext* context, const PrepareRequest* request, PrepareResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        uint64_t slot = request->slot();
        ProposalNum proposal = ProposalNum::fromProto(request->proposal_number());
        AcceptorState& acceptor_state = GetAcceptorState(slot);

        // TODO: Implement prepare logic
        (void)proposal;
        (void)acceptor_state;
        response->set_promised(false);

        return Status::OK;
    }

    // =========================================================================
    // Phase 2: Accept
    // =========================================================================

    /**
     * Send Accept requests to all acceptors.
     *
     * TODO: Implement Phase 2a of Paxos:
     * 1. Send Accept(n, v) to all acceptors
     * 2. Wait for responses from a majority
     * 3. If majority accept, value is chosen - notify learners
     * 4. Return true if value was chosen
     */
    bool SendAccept(uint64_t slot, const ProposalNum& proposal, const std::vector<uint8_t>& value) {
        return false;
    }

    /**
     * Handle Accept RPC from a proposer.
     *
     * TODO: Implement Phase 2b of Paxos:
     * 1. If n >= highest_promised, accept the value
     * 2. Update accepted_proposal and accepted_value
     * 3. Return (accepted=True)
     * 4. Otherwise return (accepted=False, highest_promised)
     */
    Status Accept(ServerContext* context, const AcceptRequest* request, AcceptResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        uint64_t slot = request->slot();
        ProposalNum proposal = ProposalNum::fromProto(request->proposal_number());
        AcceptorState& acceptor_state = GetAcceptorState(slot);

        // TODO: Implement accept logic
        (void)proposal;
        (void)acceptor_state;
        response->set_accepted(false);

        return Status::OK;
    }

    // =========================================================================
    // Learning
    // =========================================================================

    /**
     * Handle Learn RPC - a value has been chosen.
     *
     * TODO: Implement learning:
     * 1. Store the learned value for the slot
     * 2. If this fills a gap, execute commands in order
     */
    Status Learn(ServerContext* context, const LearnRequest* request, LearnResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        uint64_t slot = request->slot();
        std::string value_str = request->value();

        // TODO: Implement learn logic
        (void)slot;
        (void)value_str;
        response->set_success(true);

        return Status::OK;
    }

    void ApplyCommand(const std::vector<uint8_t>& command, const std::string& command_type) {
        // TODO: Parse and apply the command
        (void)command;
        (void)command_type;
    }

    // =========================================================================
    // Multi-Paxos Leader Election
    // =========================================================================

    Status Heartbeat(ServerContext* context, const HeartbeatRequest* request, HeartbeatResponse* response) override {
        (void)context;
        (void)request;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement leader acknowledgment
        response->set_acknowledged(true);

        return Status::OK;
    }

    /**
     * Run as the Multi-Paxos leader.
     *
     * TODO: Implement Multi-Paxos optimization:
     * 1. Skip Phase 1 for consecutive slots after becoming leader
     * 2. Send heartbeats to maintain leadership
     * 3. Handle client requests directly
     */
    void RunAsLeader() {
        // TODO: Implement leader logic
    }

    // =========================================================================
    // KeyValueService RPC Implementations
    // =========================================================================

    Status Get(ServerContext* context, const GetRequest* request, GetResponse* response) override {
        (void)context;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        auto it = kv_store_.find(request->key());
        if (it != kv_store_.end()) {
            response->set_value(it->second);
            response->set_found(true);
        } else {
            response->set_found(false);
        }
        return Status::OK;
    }

    /**
     * Handle Put RPC - stores key-value pair.
     *
     * TODO: Implement consensus-based put:
     * 1. If not leader, return leader_hint
     * 2. Run Paxos to agree on this operation
     * 3. Apply to state machine once chosen
     */
    Status Put(ServerContext* context, const PutRequest* request, PutResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        if (role_ != NodeRole::LEADER) {
            response->set_success(false);
            response->set_error("Not the leader");
            response->set_leader_hint(leader_id_);
            return Status::OK;
        }

        // TODO: Implement consensus-based put
        response->set_success(false);
        response->set_error("Not implemented");

        return Status::OK;
    }

    Status Delete(ServerContext* context, const DeleteRequest* request, DeleteResponse* response) override {
        (void)context;
        std::unique_lock<std::shared_mutex> lock(mutex_);

        if (role_ != NodeRole::LEADER) {
            response->set_success(false);
            response->set_error("Not the leader");
            response->set_leader_hint(leader_id_);
            return Status::OK;
        }

        // TODO: Implement consensus-based delete
        response->set_success(false);
        response->set_error("Not implemented");

        return Status::OK;
    }

    Status GetLeader(ServerContext* context, const GetLeaderRequest* request, GetLeaderResponse* response) override {
        (void)context;
        (void)request;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        response->set_leader_id(leader_id_);
        response->set_is_leader(role_ == NodeRole::LEADER);

        for (const auto& peer : peers_) {
            if (peer.find(leader_id_) != std::string::npos) {
                response->set_leader_address(peer);
                break;
            }
        }

        return Status::OK;
    }

    Status GetClusterStatus(ServerContext* context, const GetClusterStatusRequest* request, GetClusterStatusResponse* response) override {
        (void)context;
        (void)request;
        std::shared_lock<std::shared_mutex> lock(mutex_);

        response->set_node_id(node_id_);
        response->set_role(nodeRoleToString(role_));
        response->set_current_slot(state_.first_unchosen_slot);
        response->set_highest_promised_round(state_.current_round);
        response->set_first_unchosen_slot(state_.first_unchosen_slot);
        response->set_last_executed_slot(state_.last_executed_slot);

        for (const auto& peer : peers_) {
            auto* member = response->add_members();
            member->set_address(peer);
        }

        return Status::OK;
    }

private:
    std::string node_id_;
    int port_;
    std::vector<std::string> peers_;
    PaxosStateStore state_;
    NodeRole role_;
    std::string leader_id_;
    std::map<std::string, std::string> kv_store_;
    int heartbeat_interval_, leader_timeout_;
    mutable std::shared_mutex mutex_;
    std::atomic<bool> stop_threads_;
    std::map<std::string, std::unique_ptr<PaxosService::Stub>> peer_stubs_;
};

}  // namespace paxos

std::vector<std::string> split(const std::string& s, char delimiter) {
    std::vector<std::string> tokens;
    std::string token;
    std::istringstream tokenStream(s);
    while (std::getline(tokenStream, token, delimiter)) {
        token.erase(0, token.find_first_not_of(" \t"));
        token.erase(token.find_last_not_of(" \t") + 1);
        if (!token.empty()) {
            tokens.push_back(token);
        }
    }
    return tokens;
}

int main(int argc, char** argv) {
    std::string node_id;
    int port = 50051;
    std::string peers_str;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--node-id" && i + 1 < argc) {
            node_id = argv[++i];
        } else if (arg == "--port" && i + 1 < argc) {
            port = std::stoi(argv[++i]);
        } else if (arg == "--peers" && i + 1 < argc) {
            peers_str = argv[++i];
        }
    }

    if (node_id.empty() || peers_str.empty()) {
        std::cerr << "Usage: " << argv[0]
                  << " --node-id <id> --port <port> --peers <peer1:port1,peer2:port2>"
                  << std::endl;
        return 1;
    }

    std::vector<std::string> peers = split(peers_str, ',');

    paxos::PaxosNode node(node_id, port, peers);
    node.Initialize();

    std::string server_address = "0.0.0.0:" + std::to_string(port);
    ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
    builder.RegisterService(static_cast<paxos::PaxosService::Service*>(&node));
    builder.RegisterService(static_cast<paxos::KeyValueService::Service*>(&node));

    std::unique_ptr<Server> server(builder.BuildAndStart());
    std::cout << "Starting Paxos node " << node_id << " on port " << port << std::endl;

    server->Wait();
    return 0;
}
