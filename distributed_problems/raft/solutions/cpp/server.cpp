/**
 * Raft Consensus Implementation - C++ Solution
 *
 * A complete implementation of the Raft consensus algorithm supporting:
 * - Leader election with randomized timeouts
 * - Log replication with consistency guarantees
 * - Heartbeat mechanism for leader authority
 * - Key-value store as the state machine
 *
 * For the full Raft specification, see: https://raft.github.io/raft.pdf
 *
 * Key Raft Properties:
 * - Election Safety: At most one leader per term
 * - Leader Append-Only: Leader never overwrites/deletes log entries
 * - Log Matching: Same index+term means identical prefix
 * - Leader Completeness: Committed entries appear in future leaders
 * - State Machine Safety: Same commands applied in same order
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

// =============================================================================
// Node States - A node can be in one of three states
// =============================================================================
enum class NodeState { FOLLOWER, CANDIDATE, LEADER };

std::string nodeStateToString(NodeState state) {
    switch (state) {
        case NodeState::FOLLOWER: return "follower";
        case NodeState::CANDIDATE: return "candidate";
        case NodeState::LEADER: return "leader";
        default: return "unknown";
    }
}

// =============================================================================
// Log Entry - Represents a single entry in the replicated log
// =============================================================================
// Internal structure to avoid collision with Protobuf Raft::LogEntry
struct RaftLogEntry {
    uint64_t index;                   // Position in log (1-indexed)
    uint64_t term;                    // Term when entry was received
    std::vector<uint8_t> command;     // Command to apply to state machine
    std::string command_type;         // Type of command (put/delete)
};

// =============================================================================
// Raft State - Persistent and volatile state per Raft paper
// =============================================================================
struct RaftStateStore {
    // Persistent state on all servers (updated before responding to RPCs)
    uint64_t current_term = 0;        // Latest term server has seen
    std::string voted_for = "";       // CandidateId that received vote in current term
    std::vector<RaftLogEntry> log;    // Log entries

    // Volatile state on all servers
    uint64_t commit_index = 0;        // Index of highest log entry known to be committed
    uint64_t last_applied = 0;        // Index of highest log entry applied to state machine

    // Volatile state on leaders (reinitialized after election)
    std::map<std::string, uint64_t> next_index;   // For each peer, next log index to send
    std::map<std::string, uint64_t> match_index;  // For each peer, highest replicated index
};

// =============================================================================
// Raft Node Implementation
// =============================================================================
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

    // =========================================================================
    // Initialization - Set up gRPC channels to peers
    // =========================================================================
    void Initialize() {
        for (const auto& peer : peers_) {
            std::shared_ptr<grpc::Channel> channel;
            // Cloud Run URLs require SSL credentials for secure communication
            if (peer.find(".run.app:443") != std::string::npos ||
                peer.find(".run.app") != std::string::npos) {
                // Use SSL credentials for Cloud Run endpoints
                grpc::SslCredentialsOptions ssl_opts;
                auto creds = grpc::SslCredentials(ssl_opts);
                channel = grpc::CreateChannel(peer, creds);
                std::cout << "Using SSL for peer: " << peer << std::endl;
            } else {
                // Use insecure credentials for local development
                channel = grpc::CreateChannel(peer, grpc::InsecureChannelCredentials());
                std::cout << "Using insecure channel for peer: " << peer << std::endl;
            }
            peer_stubs_[peer] = RaftService::NewStub(channel);
        }
        timer_thread_ = std::thread(&RaftNode::ElectionTimerLoop, this);
        heartbeat_thread_ = std::thread(&RaftNode::HeartbeatLoop, this);
        std::cout << "Node " << node_id_ << " initialized with " << peers_.size() << " peers" << std::endl;
    }

    // =========================================================================
    // Log Helper Methods
    // =========================================================================
    uint64_t GetLastLogIndex() const { return state_.log.back().index; }
    uint64_t GetLastLogTerm() const { return state_.log.back().term; }

    // =========================================================================
    // Election Timer Management
    // =========================================================================

    /**
     * Reset the election timeout with a random duration.
     * This prevents split votes by randomizing when candidates start elections.
     */
    void ResetElectionTimer() {
        std::unique_lock<std::mutex> lock(timer_mutex_);
        auto timeout = std::chrono::milliseconds(election_timeout_min_ + (rand() % (election_timeout_max_ - election_timeout_min_)));
        election_deadline_ = std::chrono::steady_clock::now() + timeout;
    }

    /**
     * Step down to follower state when we see a higher term.
     * This is a key safety property in Raft.
     */
    void StepDown(uint64_t new_term) {
        state_.current_term = new_term;
        state_.voted_for = "";
        node_state_ = NodeState::FOLLOWER;
        ResetElectionTimer();
    }

    /**
     * Election timer loop - monitors for election timeout.
     * If timeout elapses without hearing from leader, start election.
     */
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

    // =========================================================================
    // Leader Election
    // =========================================================================

    /**
     * Start a new leader election.
     *
     * Per Raft specification:
     * 1. Increment currentTerm
     * 2. Vote for self
     * 3. Reset election timer
     * 4. Send RequestVote RPCs to all other servers
     * 5. If votes received from majority: become leader
     * 6. If AppendEntries received from new leader: convert to follower
     * 7. If election timeout elapses: start new election
     */
    void StartElection() {
        node_state_ = NodeState::CANDIDATE;
        state_.current_term++;
        state_.voted_for = node_id_;
        ResetElectionTimer();

        uint64_t term = state_.current_term;
        uint64_t last_idx = GetLastLogIndex();
        uint64_t last_term = GetLastLogTerm();

        std::cout << "Node " << node_id_ << " starting election for term " << term << std::endl;

        auto votes_received = std::make_shared<std::atomic<int>>(1); // Vote for self
        int majority = static_cast<int>((peers_.size() + 1) / 2 + 1);

        // Send RequestVote RPCs to all peers in parallel
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
                        // Discovered higher term, step down
                        StepDown(response.term());
                    } else if (node_state_ == NodeState::CANDIDATE && response.vote_granted() && term == state_.current_term) {
                        // Count vote and check for majority
                        if (++(*votes_received) >= majority) BecomeLeader();
                    }
                }
            }).detach();
        }
    }

    /**
     * Transition to leader state after winning election.
     * Initialize nextIndex and matchIndex for all peers.
     */
    void BecomeLeader() {
        if (node_state_ != NodeState::CANDIDATE) return;
        node_state_ = NodeState::LEADER;
        leader_id_ = node_id_;
        std::cout << "Node " << node_id_ << " became leader for term " << state_.current_term << std::endl;

        // Initialize leader volatile state
        for (const auto& peer : peers_) {
            state_.next_index[peer] = GetLastLogIndex() + 1;
            state_.match_index[peer] = 0;
        }
    }

    // =========================================================================
    // Heartbeat and Log Replication
    // =========================================================================

    /**
     * Heartbeat loop - sends periodic AppendEntries to maintain leadership.
     */
    void HeartbeatLoop() {
        while (!stop_threads_) {
            std::this_thread::sleep_for(std::chrono::milliseconds(heartbeat_interval_));
            std::unique_lock<std::shared_mutex> lock(mutex_);
            if (node_state_ == NodeState::LEADER) SendAppendEntriesToAll();
        }
    }

    /**
     * Send AppendEntries RPCs to all peers.
     * Handles both heartbeats (empty entries) and log replication.
     */
    void SendAppendEntriesToAll() {
        for (const auto& peer : peers_) {
            uint64_t next = state_.next_index[peer];
            uint64_t prev_idx = next - 1;
            uint64_t prev_term = state_.log[prev_idx].term;

            // Build AppendEntries request
            auto request = std::make_shared<AppendEntriesRequest>();
            request->set_term(state_.current_term);
            request->set_leader_id(node_id_);
            request->set_prev_log_index(prev_idx);
            request->set_prev_log_term(prev_term);
            request->set_leader_commit(state_.commit_index);

            // Add new entries to replicate
            for (size_t i = next; i < state_.log.size(); ++i) {
                auto* entry = request->add_entries();
                entry->set_index(state_.log[i].index);
                entry->set_term(state_.log[i].term);
                entry->set_command_type(state_.log[i].command_type);
                entry->set_command(state_.log[i].command.data(), state_.log[i].command.size());
            }

            // Send asynchronously
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
                            // Update nextIndex and matchIndex for follower
                            state_.next_index[peer] = request->prev_log_index() + static_cast<uint64_t>(request->entries_size()) + 1;
                            state_.match_index[peer] = state_.next_index[peer] - 1;
                            UpdateCommitIndex();
                        } else {
                            // Decrement nextIndex and retry
                            state_.next_index[peer] = std::max(static_cast<uint64_t>(1), state_.next_index[peer] - 1);
                        }
                    }
                }
            }).detach();
        }
    }

    /**
     * Update commitIndex based on matchIndex of peers.
     * An entry is committed when replicated on a majority of servers.
     */
    void UpdateCommitIndex() {
        for (uint64_t n = state_.commit_index + 1; n < state_.log.size(); ++n) {
            // Only commit entries from current term (Raft safety property)
            if (state_.log[n].term != state_.current_term) continue;

            size_t count = 1; // Self
            for (const auto& peer : peers_) {
                if (state_.match_index[peer] >= n) count++;
            }

            if (count >= (peers_.size() + 1) / 2 + 1) {
                state_.commit_index = n;
                ApplyToStateMachine();
            }
        }
    }

    /**
     * Apply committed entries to the state machine (key-value store).
     */
    void ApplyToStateMachine() {
        while (state_.last_applied < state_.commit_index) {
            state_.last_applied++;
            auto& entry = state_.log[state_.last_applied];
            std::string cmd(entry.command.begin(), entry.command.end());

            if (entry.command_type == "put") {
                size_t sep = cmd.find(':');
                if (sep != std::string::npos) {
                    kv_store_[cmd.substr(0, sep)] = cmd.substr(sep + 1);
                }
            } else if (entry.command_type == "delete") {
                kv_store_.erase(cmd);
            }
        }
        // Signal waiting threads that entries have been applied
        cv_apply_.notify_all();
    }

    // =========================================================================
    // RaftService RPC Implementations
    // =========================================================================

    /**
     * Handle RequestVote RPC from a candidate.
     *
     * Per Raft specification:
     * 1. Reply false if term < currentTerm
     * 2. If votedFor is null or candidateId, and candidate's log is at
     *    least as up-to-date as receiver's log, grant vote
     */
    Status RequestVote(ServerContext* context, const RequestVoteRequest* request, RequestVoteResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // Update term if we see a higher term
        if (request->term() > state_.current_term) StepDown(request->term());

        // Check if candidate's log is at least as up-to-date as ours
        bool log_ok = (request->last_log_term() > GetLastLogTerm()) ||
                      (request->last_log_term() == GetLastLogTerm() && request->last_log_index() >= GetLastLogIndex());

        bool vote_granted = false;
        if (request->term() == state_.current_term && log_ok &&
            (state_.voted_for.empty() || state_.voted_for == request->candidate_id())) {
            state_.voted_for = request->candidate_id();
            vote_granted = true;
            ResetElectionTimer();
        }

        response->set_term(state_.current_term);
        response->set_vote_granted(vote_granted);
        return Status::OK;
    }

    /**
     * Handle AppendEntries RPC from leader.
     *
     * Per Raft specification:
     * 1. Reply false if term < currentTerm
     * 2. Reply false if log doesn't contain entry at prevLogIndex with prevLogTerm
     * 3. If existing entry conflicts with new one, delete it and all that follow
     * 4. Append any new entries not already in the log
     * 5. If leaderCommit > commitIndex, set commitIndex = min(leaderCommit, last new entry index)
     */
    Status AppendEntries(ServerContext* context, const AppendEntriesRequest* request, AppendEntriesResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // Update term if we see a higher term
        if (request->term() > state_.current_term) StepDown(request->term());

        response->set_term(state_.current_term);

        // Reply false if term < currentTerm
        if (request->term() < state_.current_term) {
            response->set_success(false);
            return Status::OK;
        }

        // Valid AppendEntries from leader - update state
        leader_id_ = request->leader_id();
        ResetElectionTimer();

        // Check log consistency
        if (request->prev_log_index() >= state_.log.size() ||
            state_.log[request->prev_log_index()].term != request->prev_log_term()) {
            response->set_success(false);
            response->set_match_index(GetLastLogIndex());
            return Status::OK;
        }

        // Append new entries
        size_t log_ptr = request->prev_log_index() + 1;
        for (int i = 0; i < request->entries_size(); ++i, ++log_ptr) {
            if (log_ptr < state_.log.size() &&
                state_.log[log_ptr].term != static_cast<uint64_t>(request->entries(i).term())) {
                // Conflict detection - delete conflicting entries
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

        // Update commit index
        if (request->leader_commit() > state_.commit_index) {
            state_.commit_index = std::min(request->leader_commit(), GetLastLogIndex());
            ApplyToStateMachine();
        }

        response->set_success(true);
        response->set_match_index(GetLastLogIndex());
        return Status::OK;
    }

    /**
     * Handle InstallSnapshot RPC from leader.
     * Used when leader needs to bring a far-behind follower up to date.
     */
    Status InstallSnapshot(ServerContext* context, const InstallSnapshotRequest* request, InstallSnapshotResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        std::unique_lock<std::shared_mutex> lock(mutex_);

        if (request->term() > state_.current_term) {
            StepDown(request->term());
        }

        response->set_term(state_.current_term);

        if (request->term() < state_.current_term) {
            return Status::OK;
        }

        leader_id_ = request->leader_id();
        ResetElectionTimer();

        // Handle snapshot installation
        if (request->done()) {
            // Apply snapshot to state machine
            state_.commit_index = request->last_included_index();
            state_.last_applied = request->last_included_index();

            // Trim log to only include entries after snapshot
            if (request->last_included_index() < state_.log.size() &&
                state_.log[request->last_included_index()].term == request->last_included_term()) {
                // Keep entries after snapshot
                state_.log.erase(state_.log.begin(), state_.log.begin() + static_cast<long>(request->last_included_index()));
            } else {
                // Discard entire log and start fresh
                state_.log.clear();
                RaftLogEntry dummy;
                dummy.index = request->last_included_index();
                dummy.term = request->last_included_term();
                state_.log.push_back(dummy);
            }
        }

        return Status::OK;
    }

    // =========================================================================
    // KeyValueService RPC Implementations
    // =========================================================================

    /**
     * Handle Get RPC - reads from local key-value store.
     * Reads can be served by any node (eventual consistency).
     */
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

    /**
     * Handle Put RPC - stores key-value pair through consensus.
     * Only the leader can accept writes.
     */
    Status Put(ServerContext* context, const PutRequest* request, PutResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // Redirect to leader if we're not the leader
        if (node_state_ != NodeState::LEADER) {
            response->set_success(false);
            response->set_error("Not the leader");
            response->set_leader_hint(leader_id_);
            return Status::OK;
        }

        // Append to log
        RaftLogEntry entry;
        entry.index = GetLastLogIndex() + 1;
        entry.term = state_.current_term;
        entry.command_type = "put";
        std::string cmd = request->key() + ":" + request->value();
        entry.command.assign(cmd.begin(), cmd.end());
        state_.log.push_back(entry);

        uint64_t wait_idx = entry.index;

        // Wait for entry to be committed and applied
        cv_apply_.wait(lock, [this, wait_idx] {
            return state_.last_applied >= wait_idx || node_state_ != NodeState::LEADER;
        });

        response->set_success(state_.last_applied >= wait_idx);
        return Status::OK;
    }

    /**
     * Handle Delete RPC - removes key through consensus.
     * Only the leader can accept writes.
     */
    Status Delete(ServerContext* context, const DeleteRequest* request, DeleteResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // Redirect to leader if we're not the leader
        if (node_state_ != NodeState::LEADER) {
            response->set_success(false);
            response->set_error("Not the leader");
            response->set_leader_hint(leader_id_);
            return Status::OK;
        }

        // Append to log
        RaftLogEntry entry;
        entry.index = GetLastLogIndex() + 1;
        entry.term = state_.current_term;
        entry.command_type = "delete";
        entry.command.assign(request->key().begin(), request->key().end());
        state_.log.push_back(entry);

        uint64_t wait_idx = entry.index;

        // Wait for entry to be committed and applied
        cv_apply_.wait(lock, [this, wait_idx] {
            return state_.last_applied >= wait_idx || node_state_ != NodeState::LEADER;
        });

        response->set_success(state_.last_applied >= wait_idx);
        return Status::OK;
    }

    /**
     * Handle GetLeader RPC - returns current leader information.
     */
    Status GetLeader(ServerContext* context, const GetLeaderRequest* request, GetLeaderResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        (void)request;  // Suppress unused parameter warning
        std::shared_lock<std::shared_mutex> lock(mutex_);

        response->set_leader_id(leader_id_);
        response->set_is_leader(node_state_ == NodeState::LEADER);

        // Find leader address from peers
        for (const auto& peer : peers_) {
            if (peer.find(leader_id_) != std::string::npos) {
                response->set_leader_address(peer);
                break;
            }
        }

        // If we are the leader, set our own address
        if (node_state_ == NodeState::LEADER) {
            response->set_leader_address("localhost:" + std::to_string(port_));
        }

        return Status::OK;
    }

    /**
     * Handle GetClusterStatus RPC - returns detailed cluster state.
     */
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

// =============================================================================
// Helper Functions
// =============================================================================

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

// =============================================================================
// Main Entry Point
// =============================================================================
int main(int argc, char** argv) {
    std::string node_id;
    int port = 50051;
    std::string peers_str;

    // Parse command-line arguments
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
