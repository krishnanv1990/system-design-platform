/**
 * Raft Consensus Implementation - C++ Template
 *
 * This template provides the basic structure for implementing the Raft
 * consensus algorithm. You need to implement the TODO sections.
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

/**
 * Raft consensus node implementation.
 *
 * TODO: Implement the core Raft algorithm:
 * 1. Leader election
 * 2. Log replication
 * 3. Safety (election restriction, commitment rules)
 */
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
            std::shared_ptr<grpc::Channel> channel;
            // Cloud Run URLs with :443 require SSL credentials
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

    // --- Helper Methods ---
    uint64_t GetLastLogIndex() const { return state_.log.back().index; }
    uint64_t GetLastLogTerm() const { return state_.log.back().term; }

    /**
     * Reset the election timeout with a random duration.
     *
     * TODO: Implement election timer reset
     * - Set a new deadline using a random timeout between
     *   election_timeout_min_ and election_timeout_max_
     */
    void ResetElectionTimer() {
        std::unique_lock<std::mutex> lock(timer_mutex_);
        // TODO: Calculate random timeout and set election_deadline_
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

    /**
     * Start a new leader election.
     *
     * TODO: Implement the election process:
     * 1. Increment current_term
     * 2. Change state to CANDIDATE
     * 3. Vote for self
     * 4. Reset election timer
     * 5. Send RequestVote RPCs to all peers in parallel
     * 6. If votes received from majority, become leader
     * 7. If AppendEntries received from new leader, become follower
     * 8. If election timeout elapses, start new election
     */
    void StartElection() {
        // TODO: Implement election logic
        std::cout << "Node " << node_id_ << " starting election for term " << state_.current_term + 1 << std::endl;
    }

    /**
     * Transition to leader state.
     *
     * TODO: Implement leader initialization:
     * - Set node_state_ to LEADER
     * - Initialize next_index for all peers to last log index + 1
     * - Initialize match_index for all peers to 0
     */
    void BecomeLeader() {
        // TODO: Implement leader transition
    }

    /**
     * Step down to follower state.
     *
     * TODO: Implement step down:
     * - Update current_term to new_term
     * - Clear voted_for
     * - Set node_state_ to FOLLOWER
     * - Reset election timer
     */
    void StepDown(uint64_t new_term) {
        // TODO: Implement step down logic
    }

    void HeartbeatLoop() {
        while (!stop_threads_) {
            std::this_thread::sleep_for(std::chrono::milliseconds(heartbeat_interval_));
            std::unique_lock<std::shared_mutex> lock(mutex_);
            if (node_state_ == NodeState::LEADER) SendAppendEntriesToAll();
        }
    }

    /**
     * Send AppendEntries RPCs to all peers.
     *
     * TODO: Implement log replication:
     * - For each peer, send AppendEntries with appropriate entries
     * - Handle responses to update next_index and match_index
     * - Update commit_index when entries are replicated to majority
     */
    void SendAppendEntriesToAll() {
        // TODO: Implement sending AppendEntries to all peers
    }

    /**
     * Update commit index based on match_index values.
     *
     * TODO: Implement commit index update:
     * - Find N such that N > commitIndex, a majority of match_index[i] >= N,
     *   and log[N].term == currentTerm
     * - Set commitIndex = N
     * - Apply committed entries to state machine
     */
    void UpdateCommitIndex() {
        // TODO: Implement commit index update logic
    }

    /**
     * Apply committed entries to the state machine.
     *
     * TODO: Implement state machine application:
     * - Apply all entries from last_applied + 1 to commit_index
     * - For "put" commands: parse "key:value" and store in kv_store_
     * - For "delete" commands: remove key from kv_store_
     */
    void ApplyToStateMachine() {
        // TODO: Implement state machine application
    }

    // --- RaftService RPC Implementations ---

    /**
     * Handle RequestVote RPC from a candidate.
     *
     * TODO: Implement vote handling per Raft specification:
     * 1. Reply false if term < currentTerm
     * 2. If votedFor is null or candidateId, and candidate's log is at
     *    least as up-to-date as receiver's log, grant vote
     */
    Status RequestVote(ServerContext* context, const RequestVoteRequest* request, RequestVoteResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement RequestVote logic
        response->set_term(state_.current_term);
        response->set_vote_granted(false);

        return Status::OK;
    }

    /**
     * Handle AppendEntries RPC from leader.
     *
     * TODO: Implement log replication per Raft specification:
     * 1. Reply false if term < currentTerm
     * 2. Reply false if log doesn't contain an entry at prevLogIndex
     *    whose term matches prevLogTerm
     * 3. If an existing entry conflicts with a new one, delete the
     *    existing entry and all that follow it
     * 4. Append any new entries not already in the log
     * 5. If leaderCommit > commitIndex, set commitIndex =
     *    min(leaderCommit, index of last new entry)
     */
    Status AppendEntries(ServerContext* context, const AppendEntriesRequest* request, AppendEntriesResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement AppendEntries logic
        response->set_term(state_.current_term);
        response->set_success(false);
        response->set_match_index(GetLastLogIndex());

        return Status::OK;
    }

    /**
     * Handle InstallSnapshot RPC from leader.
     *
     * TODO: Implement snapshot installation:
     * 1. Reply immediately if term < currentTerm
     * 2. Create new snapshot file if first chunk
     * 3. Write data into snapshot file at given offset
     * 4. Reply and wait for more chunks if done is false
     * 5. Save snapshot file, discard any existing snapshot
     * 6. If existing log entry has same index and term as last entry
     *    in snapshot, discard entries before it
     * 7. Discard entire log and reset state machine with snapshot
     */
    Status InstallSnapshot(ServerContext* context, const InstallSnapshotRequest* request, InstallSnapshotResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // TODO: Implement InstallSnapshot logic
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

    /**
     * Handle Put RPC - stores key-value pair.
     *
     * TODO: Implement consensus-based put:
     * 1. If not leader, return leader_hint
     * 2. Append entry to local log
     * 3. Replicate to followers via AppendEntries
     * 4. Once committed (majority replicated), apply to state machine
     * 5. Return success to client
     */
    Status Put(ServerContext* context, const PutRequest* request, PutResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        std::unique_lock<std::shared_mutex> lock(mutex_);

        if (node_state_ != NodeState::LEADER) {
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

    /**
     * Handle Delete RPC - removes key.
     *
     * TODO: Implement consensus-based delete (similar to put)
     */
    Status Delete(ServerContext* context, const DeleteRequest* request, DeleteResponse* response) override {
        (void)context;  // Suppress unused parameter warning
        std::unique_lock<std::shared_mutex> lock(mutex_);

        if (node_state_ != NodeState::LEADER) {
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
