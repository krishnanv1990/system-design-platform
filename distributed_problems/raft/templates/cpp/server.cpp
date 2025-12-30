/**
 * Raft Consensus Implementation - C++ Template
 *
 * This template provides the basic structure for implementing the Raft
 * consensus algorithm.
 *
 * For the full Raft specification, see: https://raft.github.io/raft.pdf
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
#include <random>
#include <chrono>
#include <thread>
#include <atomic>
#include <sstream>
#include <algorithm>
#include <condition_variable>

#include <grpcpp/grpcpp.h>
#include "raft.grpc.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;
using grpc::Channel;
using grpc::ClientContext;

namespace raft {

enum class NodeState { FOLLOWER, CANDIDATE, LEADER };

std::string nodeStateToString(NodeState state) {
    switch (state) {
        case NodeState::FOLLOWER: return "follower";
        case NodeState::CANDIDATE: return "candidate";
        case NodeState::LEADER: return "leader";
        default: return "unknown";
    }
}

// Internal structure to avoid collision with Protobuf Raft::LogEntry
struct RaftLogEntry {
    uint64_t index;
    uint64_t term;
    std::vector<uint8_t> command;
    std::string command_type;
};

// Internal state storage
struct RaftStateStore {
    uint64_t current_term = 0;
    std::string voted_for = "";
    std::vector<RaftLogEntry> log;
    uint64_t commit_index = 0;
    uint64_t last_applied = 0;
    std::map<std::string, uint64_t> next_index;
    std::map<std::string, uint64_t> match_index;
};

class RaftNode final : public RaftService::Service, public KeyValueService::Service {
public:
    RaftNode(const std::string& node_id, int port, const std::vector<std::string>& peers)
        : node_id_(node_id), port_(port), peers_(peers),
          node_state_(NodeState::FOLLOWER),
          election_timeout_min_(150), election_timeout_max_(300),
          heartbeat_interval_(50), stop_threads_(false) {

        // 1-based indexing: dummy entry at index 0
        RaftLogEntry dummy;
        dummy.index = 0;
        dummy.term = 0;
        state_.log.push_back(dummy);
    }

    ~RaftNode() {
        stop_threads_ = true;
        if (timer_thread_.joinable()) timer_thread_.join();
        if (heartbeat_thread_.joinable()) heartbeat_thread_.join();
    }

    void Initialize() {
        for (const auto& peer : peers_) {
            auto channel = grpc::CreateChannel(peer, grpc::InsecureChannelCredentials());
            peer_stubs_[peer] = RaftService::NewStub(channel);
        }
        timer_thread_ = std::thread(&RaftNode::ElectionTimerLoop, this);
        heartbeat_thread_ = std::thread(&RaftNode::HeartbeatLoop, this);
    }

    // --- Helper Methods ---
    uint64_t GetLastLogIndex() const { return state_.log.back().index; }
    uint64_t GetLastLogTerm() const { return state_.log.back().term; }

    void ResetElectionTimer() {
        std::unique_lock<std::mutex> lock(timer_mutex_);
        auto timeout = std::chrono::milliseconds(election_timeout_min_ + (rand() % (election_timeout_max_ - election_timeout_min_)));
        election_deadline_ = std::chrono::steady_clock::now() + timeout;
    }

    // --- Core Raft Logic Loops ---
    void ElectionTimerLoop() {
        ResetElectionTimer();
        while (!stop_threads_) {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            auto now = std::chrono::steady_clock::now();

            std::unique_lock<std::shared_mutex> lock(mutex_);
            if (node_state_ != NodeState::LEADER && now >= election_deadline_) {
                StartElection();
            }
        }
    }

    void StartElection() {
        node_state_ = NodeState::CANDIDATE;
        state_.current_term++;
        state_.voted_for = node_id_;
        ResetElectionTimer();

        uint64_t term = state_.current_term;
        uint64_t last_idx = GetLastLogIndex();
        uint64_t last_term = GetLastLogTerm();

        auto votes_received = std::make_shared<std::atomic<int>>(1);
        int majority = static_cast<int>((peers_.size() + 1) / 2 + 1);

        for (const auto& peer : peers_) {
            std::thread([this, peer, term, last_idx, last_term, votes_received, majority]() {
                RequestVoteRequest request;
                request.set_term(term);
                request.set_candidate_id(node_id_);
                request.set_last_log_index(last_idx);
                request.set_last_log_term(last_term);

                RequestVoteResponse response;
                ClientContext context;
                context.set_deadline(std::chrono::system_clock::now() + std::chrono::milliseconds(100));

                if (peer_stubs_[peer]->RequestVote(&context, request, &response).ok()) {
                    std::unique_lock<std::shared_mutex> lock(mutex_);
                    if (response.term() > state_.current_term) {
                        StepDown(response.term());
                    } else if (node_state_ == NodeState::CANDIDATE && response.vote_granted() && term == state_.current_term) {
                        if (++(*votes_received) >= majority) BecomeLeader();
                    }
                }
            }).detach();
        }
    }

    void BecomeLeader() {
        if (node_state_ != NodeState::CANDIDATE) return;
        node_state_ = NodeState::LEADER;
        leader_id_ = node_id_;
        for (const auto& peer : peers_) {
            state_.next_index[peer] = GetLastLogIndex() + 1;
            state_.match_index[peer] = 0;
        }
    }

    void StepDown(uint64_t new_term) {
        state_.current_term = new_term;
        state_.voted_for = "";
        node_state_ = NodeState::FOLLOWER;
        ResetElectionTimer();
    }

    void HeartbeatLoop() {
        while (!stop_threads_) {
            std::this_thread::sleep_for(std::chrono::milliseconds(heartbeat_interval_));
            std::unique_lock<std::shared_mutex> lock(mutex_);
            if (node_state_ == NodeState::LEADER) SendAppendEntriesToAll();
        }
    }

    void SendAppendEntriesToAll() {
        for (const auto& peer : peers_) {
            uint64_t next = state_.next_index[peer];
            uint64_t prev_idx = next - 1;
            uint64_t prev_term = state_.log[prev_idx].term;

            auto request = std::make_shared<AppendEntriesRequest>();
            request->set_term(state_.current_term);
            request->set_leader_id(node_id_);
            request->set_prev_log_index(prev_idx);
            request->set_prev_log_term(prev_term);
            request->set_leader_commit(state_.commit_index);

            for (size_t i = next; i < state_.log.size(); ++i) {
                auto* entry = request->add_entries();
                entry->set_index(state_.log[i].index);
                entry->set_term(state_.log[i].term);
                entry->set_command_type(state_.log[i].command_type);
                entry->set_command(state_.log[i].command.data(), state_.log[i].command.size());
            }

            std::thread([this, peer, request]() {
                AppendEntriesResponse response;
                ClientContext context;
                context.set_deadline(std::chrono::system_clock::now() + std::chrono::milliseconds(100));

                if (peer_stubs_[peer]->AppendEntries(&context, *request, &response).ok()) {
                    std::unique_lock<std::shared_mutex> lock(mutex_);
                    if (response.term() > state_.current_term) {
                        StepDown(response.term());
                    } else if (node_state_ == NodeState::LEADER && request->term() == state_.current_term) {
                        if (response.success()) {
                            state_.next_index[peer] = request->prev_log_index() + static_cast<uint64_t>(request->entries_size()) + 1;
                            state_.match_index[peer] = state_.next_index[peer] - 1;
                            UpdateCommitIndex();
                        } else {
                            state_.next_index[peer] = std::max(static_cast<uint64_t>(1), state_.next_index[peer] - 1);
                        }
                    }
                }
            }).detach();
        }
    }

    void UpdateCommitIndex() {
        for (uint64_t n = state_.commit_index + 1; n < state_.log.size(); ++n) {
            if (state_.log[n].term != state_.current_term) continue;
            size_t count = 1;
            for (const auto& peer : peers_) if (state_.match_index[peer] >= n) count++;
            if (count >= (peers_.size() + 1) / 2 + 1) {
                state_.commit_index = n;
                ApplyToStateMachine();
            }
        }
    }

    void ApplyToStateMachine() {
        while (state_.last_applied < state_.commit_index) {
            state_.last_applied++;
            auto& entry = state_.log[state_.last_applied];
            std::string cmd(entry.command.begin(), entry.command.end());
            if (entry.command_type == "put") {
                size_t sep = cmd.find(':');
                if (sep != std::string::npos) kv_store_[cmd.substr(0, sep)] = cmd.substr(sep + 1);
            } else if (entry.command_type == "delete") {
                kv_store_.erase(cmd);
            }
        }
        cv_apply_.notify_all();
    }

    // --- RaftService RPC Implementations ---
    Status RequestVote(ServerContext* context, const RequestVoteRequest* request, RequestVoteResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        std::unique_lock<std::shared_mutex> lock(mutex_);
        if (request->term() > state_.current_term) StepDown(request->term());

        bool log_ok = (request->last_log_term() > GetLastLogTerm()) ||
                      (request->last_log_term() == GetLastLogTerm() && request->last_log_index() >= GetLastLogIndex());

        if (request->term() == state_.current_term && log_ok && (state_.voted_for.empty() || state_.voted_for == request->candidate_id())) {
            state_.voted_for = request->candidate_id();
            response->set_vote_granted(true);
            ResetElectionTimer();
        } else {
            response->set_vote_granted(false);
        }
        response->set_term(state_.current_term);
        return Status::OK;
    }

    Status AppendEntries(ServerContext* context, const AppendEntriesRequest* request, AppendEntriesResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        std::unique_lock<std::shared_mutex> lock(mutex_);
        if (request->term() > state_.current_term) StepDown(request->term());

        response->set_term(state_.current_term);
        if (request->term() < state_.current_term) {
            response->set_success(false);
            return Status::OK;
        }

        leader_id_ = request->leader_id();
        ResetElectionTimer();

        if (request->prev_log_index() >= state_.log.size() || state_.log[request->prev_log_index()].term != request->prev_log_term()) {
            response->set_success(false);
            return Status::OK;
        }

        size_t log_ptr = request->prev_log_index() + 1;
        for (int i = 0; i < request->entries_size(); ++i, ++log_ptr) {
            if (log_ptr < state_.log.size() && state_.log[log_ptr].term != static_cast<uint64_t>(request->entries(i).term())) {
                state_.log.erase(state_.log.begin() + static_cast<long>(log_ptr), state_.log.end());
            }
            if (log_ptr >= state_.log.size()) {
                RaftLogEntry entry;
                entry.index = request->entries(i).index();
                entry.term = request->entries(i).term();
                entry.command_type = request->entries(i).command_type();
                entry.command.assign(request->entries(i).command().begin(), request->entries(i).command().end());
                state_.log.push_back(entry);
            }
        }

        if (request->leader_commit() > state_.commit_index) {
            state_.commit_index = std::min(request->leader_commit(), GetLastLogIndex());
            ApplyToStateMachine();
        }

        response->set_success(true);
        return Status::OK;
    }

    Status InstallSnapshot(ServerContext* context, const InstallSnapshotRequest* request, InstallSnapshotResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        (void)request;  // Suppress unused parameter warning
        std::unique_lock<std::shared_mutex> lock(mutex_);
        response->set_term(state_.current_term);
        return Status::OK;
    }

    // --- KeyValueService RPC Implementations ---
    Status Get(ServerContext* context, const GetRequest* request, GetResponse* response) override {
        (void)context;  // Suppress unused parameter warning
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

    Status Put(ServerContext* context, const PutRequest* request, PutResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        std::unique_lock<std::shared_mutex> lock(mutex_);
        if (node_state_ != NodeState::LEADER) {
            response->set_leader_hint(leader_id_);
            return Status::OK;
        }

        RaftLogEntry entry;
        entry.index = GetLastLogIndex() + 1;
        entry.term = state_.current_term;
        entry.command_type = "put";
        std::string cmd = request->key() + ":" + request->value();
        entry.command.assign(cmd.begin(), cmd.end());
        state_.log.push_back(entry);

        uint64_t wait_idx = entry.index;
        cv_apply_.wait(lock, [this, wait_idx] { return state_.last_applied >= wait_idx || node_state_ != NodeState::LEADER; });

        response->set_success(state_.last_applied >= wait_idx);
        return Status::OK;
    }

    Status Delete(ServerContext* context, const DeleteRequest* request, DeleteResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        std::unique_lock<std::shared_mutex> lock(mutex_);
        if (node_state_ != NodeState::LEADER) {
            response->set_leader_hint(leader_id_);
            return Status::OK;
        }

        RaftLogEntry entry;
        entry.index = GetLastLogIndex() + 1;
        entry.term = state_.current_term;
        entry.command_type = "delete";
        entry.command.assign(request->key().begin(), request->key().end());
        state_.log.push_back(entry);

        uint64_t wait_idx = entry.index;
        cv_apply_.wait(lock, [this, wait_idx] { return state_.last_applied >= wait_idx || node_state_ != NodeState::LEADER; });

        response->set_success(state_.last_applied >= wait_idx);
        return Status::OK;
    }

    Status GetLeader(ServerContext* context, const GetLeaderRequest* request, GetLeaderResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        (void)request;  // Suppress unused parameter warning
        std::shared_lock<std::shared_mutex> lock(mutex_);

        response->set_leader_id(leader_id_);
        response->set_is_leader(node_state_ == NodeState::LEADER);

        for (const auto& peer : peers_) {
            if (peer.find(leader_id_) != std::string::npos) {
                response->set_leader_address(peer);
                break;
            }
        }

        return Status::OK;
    }

    Status GetClusterStatus(ServerContext* context, const GetClusterStatusRequest* request, GetClusterStatusResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        (void)request;  // Suppress unused parameter warning
        std::shared_lock<std::shared_mutex> lock(mutex_);

        response->set_node_id(node_id_);
        response->set_state(nodeStateToString(node_state_));
        response->set_current_term(state_.current_term);
        response->set_voted_for(state_.voted_for);
        response->set_commit_index(state_.commit_index);
        response->set_last_applied(state_.last_applied);
        response->set_log_length(state_.log.size());
        response->set_last_log_term(GetLastLogTerm());

        for (const auto& peer : peers_) {
            auto* member = response->add_members();
            member->set_address(peer);
            if (node_state_ == NodeState::LEADER) {
                auto match_it = state_.match_index.find(peer);
                if (match_it != state_.match_index.end()) {
                    member->set_match_index(match_it->second);
                }
                auto next_it = state_.next_index.find(peer);
                if (next_it != state_.next_index.end()) {
                    member->set_next_index(next_it->second);
                }
            }
        }

        return Status::OK;
    }

private:
    std::string node_id_;
    int port_;
    std::vector<std::string> peers_;
    RaftStateStore state_;
    std::atomic<NodeState> node_state_;
    std::string leader_id_;
    std::map<std::string, std::string> kv_store_;
    int election_timeout_min_, election_timeout_max_, heartbeat_interval_;
    mutable std::shared_mutex mutex_;
    std::mutex timer_mutex_;
    std::chrono::steady_clock::time_point election_deadline_;
    std::condition_variable_any cv_apply_;
    std::atomic<bool> stop_threads_;
    std::thread timer_thread_, heartbeat_thread_;
    std::map<std::string, std::unique_ptr<RaftService::Stub>> peer_stubs_;
};

}  // namespace raft

// Helper function to split string by delimiter
std::vector<std::string> split(const std::string& s, char delimiter) {
    std::vector<std::string> tokens;
    std::string token;
    std::istringstream tokenStream(s);
    while (std::getline(tokenStream, token, delimiter)) {
        // Trim whitespace
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

    raft::RaftNode node(node_id, port, peers);
    node.Initialize();

    std::string server_address = "0.0.0.0:" + std::to_string(port);
    ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
    builder.RegisterService(static_cast<raft::RaftService::Service*>(&node));
    builder.RegisterService(static_cast<raft::KeyValueService::Service*>(&node));

    std::unique_ptr<Server> server(builder.BuildAndStart());
    std::cout << "Starting Raft node " << node_id << " on port " << port << std::endl;

    server->Wait();
    return 0;
}
