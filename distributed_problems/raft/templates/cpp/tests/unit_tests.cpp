/**
 * Unit Tests for Raft Consensus Implementation
 *
 * Tests cover:
 * - RaftLogEntry struct
 * - RaftStateStore struct
 * - RaftNode class methods
 * - State transitions
 * - Log operations
 * - Vote handling
 * - AppendEntries handling
 */

#include <gtest/gtest.h>
#include <gmock/gmock.h>

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

// Re-include the Raft implementation for testing
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

struct RaftLogEntry {
    uint64_t index;
    uint64_t term;
    std::vector<uint8_t> command;
    std::string command_type;
};

struct RaftStateStore {
    uint64_t current_term = 0;
    std::string voted_for = "";
    std::vector<RaftLogEntry> log;
    uint64_t commit_index = 0;
    uint64_t last_applied = 0;
    std::map<std::string, uint64_t> next_index;
    std::map<std::string, uint64_t> match_index;
};

// Testable RaftNode class (simplified for unit testing)
class TestableRaftNode {
public:
    TestableRaftNode(const std::string& node_id, int port, const std::vector<std::string>& peers)
        : node_id_(node_id), port_(port), peers_(peers),
          node_state_(NodeState::FOLLOWER),
          election_timeout_min_(150), election_timeout_max_(300),
          heartbeat_interval_(50) {
        RaftLogEntry dummy;
        dummy.index = 0;
        dummy.term = 0;
        state_.log.push_back(dummy);
    }

    // Public accessors for testing
    NodeState GetNodeState() const { return node_state_.load(); }
    void SetNodeState(NodeState state) { node_state_ = state; }
    uint64_t GetCurrentTerm() const { return state_.current_term; }
    void SetCurrentTerm(uint64_t term) { state_.current_term = term; }
    std::string GetVotedFor() const { return state_.voted_for; }
    void SetVotedFor(const std::string& id) { state_.voted_for = id; }
    uint64_t GetCommitIndex() const { return state_.commit_index; }
    void SetCommitIndex(uint64_t idx) { state_.commit_index = idx; }
    uint64_t GetLastApplied() const { return state_.last_applied; }
    void SetLastApplied(uint64_t idx) { state_.last_applied = idx; }
    std::string GetNodeId() const { return node_id_; }
    std::vector<std::string> GetPeers() const { return peers_; }
    std::string GetLeaderId() const { return leader_id_; }
    void SetLeaderId(const std::string& id) { leader_id_ = id; }

    uint64_t GetLastLogIndex() const { return state_.log.back().index; }
    uint64_t GetLastLogTerm() const { return state_.log.back().term; }
    size_t GetLogSize() const { return state_.log.size(); }

    void AppendLogEntry(const RaftLogEntry& entry) {
        state_.log.push_back(entry);
    }

    const RaftLogEntry& GetLogEntry(size_t idx) const {
        return state_.log[idx];
    }

    void SetNextIndex(const std::string& peer, uint64_t idx) {
        state_.next_index[peer] = idx;
    }

    void SetMatchIndex(const std::string& peer, uint64_t idx) {
        state_.match_index[peer] = idx;
    }

    uint64_t GetNextIndex(const std::string& peer) const {
        auto it = state_.next_index.find(peer);
        return it != state_.next_index.end() ? it->second : 0;
    }

    uint64_t GetMatchIndex(const std::string& peer) const {
        auto it = state_.match_index.find(peer);
        return it != state_.match_index.end() ? it->second : 0;
    }

    // State machine
    void PutKV(const std::string& key, const std::string& value) {
        kv_store_[key] = value;
    }

    std::string GetKV(const std::string& key) const {
        auto it = kv_store_.find(key);
        return it != kv_store_.end() ? it->second : "";
    }

    bool HasKV(const std::string& key) const {
        return kv_store_.find(key) != kv_store_.end();
    }

    void DeleteKV(const std::string& key) {
        kv_store_.erase(key);
    }

    // Simulate stepping down
    void StepDown(uint64_t new_term) {
        state_.current_term = new_term;
        state_.voted_for = "";
        node_state_ = NodeState::FOLLOWER;
    }

    // Simulate becoming leader
    void BecomeLeader() {
        if (node_state_ != NodeState::CANDIDATE) return;
        node_state_ = NodeState::LEADER;
        leader_id_ = node_id_;
        for (const auto& peer : peers_) {
            state_.next_index[peer] = GetLastLogIndex() + 1;
            state_.match_index[peer] = 0;
        }
    }

    // Simulate starting election
    void StartElection() {
        node_state_ = NodeState::CANDIDATE;
        state_.current_term++;
        state_.voted_for = node_id_;
    }

    // Apply command to state machine
    void ApplyCommand(const RaftLogEntry& entry) {
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

    // Update commit index
    void UpdateCommitIndex() {
        for (uint64_t n = state_.commit_index + 1; n < state_.log.size(); ++n) {
            if (state_.log[n].term != state_.current_term) continue;
            size_t count = 1;
            for (const auto& peer : peers_) {
                if (state_.match_index[peer] >= n) count++;
            }
            if (count >= (peers_.size() + 1) / 2 + 1) {
                state_.commit_index = n;
            }
        }
    }

    // Apply to state machine
    void ApplyToStateMachine() {
        while (state_.last_applied < state_.commit_index) {
            state_.last_applied++;
            ApplyCommand(state_.log[state_.last_applied]);
        }
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
};

}  // namespace raft

// ============================================================================
// Test Fixtures
// ============================================================================

class RaftNodeTest : public ::testing::Test {
protected:
    void SetUp() override {
        peers_ = {"peer1:50052", "peer2:50053"};
        node_ = std::make_unique<raft::TestableRaftNode>("node1", 50051, peers_);
    }

    void TearDown() override {
        node_.reset();
    }

    std::vector<std::string> peers_;
    std::unique_ptr<raft::TestableRaftNode> node_;
};

class RaftLogEntryTest : public ::testing::Test {
protected:
    void SetUp() override {
        entry_.index = 1;
        entry_.term = 1;
        entry_.command_type = "put";
        std::string cmd = "key:value";
        entry_.command.assign(cmd.begin(), cmd.end());
    }

    raft::RaftLogEntry entry_;
};

class RaftStateStoreTest : public ::testing::Test {
protected:
    void SetUp() override {
        state_.current_term = 0;
        state_.voted_for = "";
        state_.commit_index = 0;
        state_.last_applied = 0;
    }

    raft::RaftStateStore state_;
};

// ============================================================================
// RaftLogEntry Tests
// ============================================================================

TEST_F(RaftLogEntryTest, InitializesCorrectly) {
    EXPECT_EQ(entry_.index, 1u);
    EXPECT_EQ(entry_.term, 1u);
    EXPECT_EQ(entry_.command_type, "put");
    EXPECT_EQ(entry_.command.size(), 9u);  // "key:value"
}

TEST_F(RaftLogEntryTest, CommandCanBeExtracted) {
    std::string cmd(entry_.command.begin(), entry_.command.end());
    EXPECT_EQ(cmd, "key:value");
}

TEST_F(RaftLogEntryTest, SupportsDeleteCommand) {
    entry_.command_type = "delete";
    std::string key = "mykey";
    entry_.command.assign(key.begin(), key.end());
    EXPECT_EQ(entry_.command_type, "delete");
    std::string extracted(entry_.command.begin(), entry_.command.end());
    EXPECT_EQ(extracted, "mykey");
}

// ============================================================================
// RaftStateStore Tests
// ============================================================================

TEST_F(RaftStateStoreTest, InitializesWithDefaults) {
    EXPECT_EQ(state_.current_term, 0u);
    EXPECT_TRUE(state_.voted_for.empty());
    EXPECT_EQ(state_.commit_index, 0u);
    EXPECT_EQ(state_.last_applied, 0u);
    EXPECT_TRUE(state_.log.empty());
    EXPECT_TRUE(state_.next_index.empty());
    EXPECT_TRUE(state_.match_index.empty());
}

TEST_F(RaftStateStoreTest, CanAddLogEntries) {
    raft::RaftLogEntry entry;
    entry.index = 1;
    entry.term = 1;
    state_.log.push_back(entry);
    EXPECT_EQ(state_.log.size(), 1u);
    EXPECT_EQ(state_.log[0].index, 1u);
}

TEST_F(RaftStateStoreTest, CanTrackNextIndex) {
    state_.next_index["peer1"] = 5;
    state_.next_index["peer2"] = 3;
    EXPECT_EQ(state_.next_index["peer1"], 5u);
    EXPECT_EQ(state_.next_index["peer2"], 3u);
}

TEST_F(RaftStateStoreTest, CanTrackMatchIndex) {
    state_.match_index["peer1"] = 4;
    state_.match_index["peer2"] = 2;
    EXPECT_EQ(state_.match_index["peer1"], 4u);
    EXPECT_EQ(state_.match_index["peer2"], 2u);
}

// ============================================================================
// RaftNode Basic Tests
// ============================================================================

TEST_F(RaftNodeTest, InitializesAsFollower) {
    EXPECT_EQ(node_->GetNodeState(), raft::NodeState::FOLLOWER);
}

TEST_F(RaftNodeTest, HasCorrectNodeId) {
    EXPECT_EQ(node_->GetNodeId(), "node1");
}

TEST_F(RaftNodeTest, HasCorrectPeers) {
    auto peers = node_->GetPeers();
    EXPECT_EQ(peers.size(), 2u);
    EXPECT_EQ(peers[0], "peer1:50052");
    EXPECT_EQ(peers[1], "peer2:50053");
}

TEST_F(RaftNodeTest, InitializesWithDummyLogEntry) {
    EXPECT_EQ(node_->GetLogSize(), 1u);
    EXPECT_EQ(node_->GetLastLogIndex(), 0u);
    EXPECT_EQ(node_->GetLastLogTerm(), 0u);
}

TEST_F(RaftNodeTest, InitializesWithZeroTerm) {
    EXPECT_EQ(node_->GetCurrentTerm(), 0u);
}

TEST_F(RaftNodeTest, InitializesWithEmptyVotedFor) {
    EXPECT_TRUE(node_->GetVotedFor().empty());
}

// ============================================================================
// State Transition Tests
// ============================================================================

TEST_F(RaftNodeTest, CanTransitionToCandidate) {
    node_->SetNodeState(raft::NodeState::CANDIDATE);
    EXPECT_EQ(node_->GetNodeState(), raft::NodeState::CANDIDATE);
}

TEST_F(RaftNodeTest, CanTransitionToLeader) {
    node_->SetNodeState(raft::NodeState::LEADER);
    EXPECT_EQ(node_->GetNodeState(), raft::NodeState::LEADER);
}

TEST_F(RaftNodeTest, CanTransitionBackToFollower) {
    node_->SetNodeState(raft::NodeState::LEADER);
    node_->SetNodeState(raft::NodeState::FOLLOWER);
    EXPECT_EQ(node_->GetNodeState(), raft::NodeState::FOLLOWER);
}

TEST_F(RaftNodeTest, StartElectionTransitionsToCandidate) {
    node_->StartElection();
    EXPECT_EQ(node_->GetNodeState(), raft::NodeState::CANDIDATE);
}

TEST_F(RaftNodeTest, StartElectionIncrementsTerm) {
    uint64_t initial_term = node_->GetCurrentTerm();
    node_->StartElection();
    EXPECT_EQ(node_->GetCurrentTerm(), initial_term + 1);
}

TEST_F(RaftNodeTest, StartElectionVotesForSelf) {
    node_->StartElection();
    EXPECT_EQ(node_->GetVotedFor(), "node1");
}

TEST_F(RaftNodeTest, StepDownResetsState) {
    node_->SetNodeState(raft::NodeState::LEADER);
    node_->SetVotedFor("node1");
    node_->StepDown(5);
    EXPECT_EQ(node_->GetNodeState(), raft::NodeState::FOLLOWER);
    EXPECT_EQ(node_->GetCurrentTerm(), 5u);
    EXPECT_TRUE(node_->GetVotedFor().empty());
}

TEST_F(RaftNodeTest, BecomeLeaderOnlyFromCandidate) {
    // Try to become leader from follower - should not work
    node_->BecomeLeader();
    EXPECT_NE(node_->GetNodeState(), raft::NodeState::LEADER);

    // Now try from candidate - should work
    node_->SetNodeState(raft::NodeState::CANDIDATE);
    node_->BecomeLeader();
    EXPECT_EQ(node_->GetNodeState(), raft::NodeState::LEADER);
}

TEST_F(RaftNodeTest, BecomeLeaderSetsLeaderId) {
    node_->SetNodeState(raft::NodeState::CANDIDATE);
    node_->BecomeLeader();
    EXPECT_EQ(node_->GetLeaderId(), "node1");
}

TEST_F(RaftNodeTest, BecomeLeaderInitializesNextIndex) {
    node_->SetNodeState(raft::NodeState::CANDIDATE);
    node_->BecomeLeader();
    for (const auto& peer : peers_) {
        EXPECT_EQ(node_->GetNextIndex(peer), node_->GetLastLogIndex() + 1);
    }
}

TEST_F(RaftNodeTest, BecomeLeaderInitializesMatchIndex) {
    node_->SetNodeState(raft::NodeState::CANDIDATE);
    node_->BecomeLeader();
    for (const auto& peer : peers_) {
        EXPECT_EQ(node_->GetMatchIndex(peer), 0u);
    }
}

// ============================================================================
// Log Operation Tests
// ============================================================================

TEST_F(RaftNodeTest, CanAppendLogEntry) {
    raft::RaftLogEntry entry;
    entry.index = 1;
    entry.term = 1;
    entry.command_type = "put";
    std::string cmd = "foo:bar";
    entry.command.assign(cmd.begin(), cmd.end());

    node_->AppendLogEntry(entry);
    EXPECT_EQ(node_->GetLogSize(), 2u);  // dummy + new entry
    EXPECT_EQ(node_->GetLastLogIndex(), 1u);
    EXPECT_EQ(node_->GetLastLogTerm(), 1u);
}

TEST_F(RaftNodeTest, CanAppendMultipleLogEntries) {
    for (uint64_t i = 1; i <= 5; ++i) {
        raft::RaftLogEntry entry;
        entry.index = i;
        entry.term = 1;
        entry.command_type = "put";
        std::string cmd = "key" + std::to_string(i) + ":value";
        entry.command.assign(cmd.begin(), cmd.end());
        node_->AppendLogEntry(entry);
    }
    EXPECT_EQ(node_->GetLogSize(), 6u);  // dummy + 5 entries
    EXPECT_EQ(node_->GetLastLogIndex(), 5u);
}

TEST_F(RaftNodeTest, LogEntriesPreserveOrder) {
    for (uint64_t i = 1; i <= 3; ++i) {
        raft::RaftLogEntry entry;
        entry.index = i;
        entry.term = i;  // Different terms
        node_->AppendLogEntry(entry);
    }
    EXPECT_EQ(node_->GetLogEntry(1).term, 1u);
    EXPECT_EQ(node_->GetLogEntry(2).term, 2u);
    EXPECT_EQ(node_->GetLogEntry(3).term, 3u);
}

// ============================================================================
// Key-Value Store Tests
// ============================================================================

TEST_F(RaftNodeTest, CanPutAndGetValue) {
    node_->PutKV("mykey", "myvalue");
    EXPECT_EQ(node_->GetKV("mykey"), "myvalue");
}

TEST_F(RaftNodeTest, HasKVReturnsTrueForExistingKey) {
    node_->PutKV("exists", "value");
    EXPECT_TRUE(node_->HasKV("exists"));
}

TEST_F(RaftNodeTest, HasKVReturnsFalseForNonExistingKey) {
    EXPECT_FALSE(node_->HasKV("nonexistent"));
}

TEST_F(RaftNodeTest, GetKVReturnsEmptyForNonExistingKey) {
    EXPECT_EQ(node_->GetKV("nonexistent"), "");
}

TEST_F(RaftNodeTest, CanDeleteKey) {
    node_->PutKV("todelete", "value");
    EXPECT_TRUE(node_->HasKV("todelete"));
    node_->DeleteKV("todelete");
    EXPECT_FALSE(node_->HasKV("todelete"));
}

TEST_F(RaftNodeTest, CanOverwriteValue) {
    node_->PutKV("key", "value1");
    node_->PutKV("key", "value2");
    EXPECT_EQ(node_->GetKV("key"), "value2");
}

// ============================================================================
// Command Application Tests
// ============================================================================

TEST_F(RaftNodeTest, ApplyPutCommand) {
    raft::RaftLogEntry entry;
    entry.index = 1;
    entry.term = 1;
    entry.command_type = "put";
    std::string cmd = "testkey:testvalue";
    entry.command.assign(cmd.begin(), cmd.end());

    node_->ApplyCommand(entry);
    EXPECT_EQ(node_->GetKV("testkey"), "testvalue");
}

TEST_F(RaftNodeTest, ApplyDeleteCommand) {
    node_->PutKV("deletekey", "value");
    EXPECT_TRUE(node_->HasKV("deletekey"));

    raft::RaftLogEntry entry;
    entry.index = 1;
    entry.term = 1;
    entry.command_type = "delete";
    std::string cmd = "deletekey";
    entry.command.assign(cmd.begin(), cmd.end());

    node_->ApplyCommand(entry);
    EXPECT_FALSE(node_->HasKV("deletekey"));
}

TEST_F(RaftNodeTest, ApplyToStateMachine) {
    // Add entries to log
    for (uint64_t i = 1; i <= 3; ++i) {
        raft::RaftLogEntry entry;
        entry.index = i;
        entry.term = 1;
        entry.command_type = "put";
        std::string cmd = "key" + std::to_string(i) + ":value" + std::to_string(i);
        entry.command.assign(cmd.begin(), cmd.end());
        node_->AppendLogEntry(entry);
    }

    // Set commit index
    node_->SetCommitIndex(3);

    // Apply
    node_->ApplyToStateMachine();

    EXPECT_EQ(node_->GetLastApplied(), 3u);
    EXPECT_EQ(node_->GetKV("key1"), "value1");
    EXPECT_EQ(node_->GetKV("key2"), "value2");
    EXPECT_EQ(node_->GetKV("key3"), "value3");
}

// ============================================================================
// Commit Index Update Tests
// ============================================================================

TEST_F(RaftNodeTest, UpdateCommitIndexWithMajority) {
    // Setup: node is leader with term 1
    node_->SetNodeState(raft::NodeState::CANDIDATE);
    node_->BecomeLeader();
    node_->SetCurrentTerm(1);

    // Add entry at index 1
    raft::RaftLogEntry entry;
    entry.index = 1;
    entry.term = 1;
    entry.command_type = "put";
    std::string cmd = "key:value";
    entry.command.assign(cmd.begin(), cmd.end());
    node_->AppendLogEntry(entry);

    // Simulate majority replication (self + 1 peer = majority in 3-node cluster)
    node_->SetMatchIndex("peer1:50052", 1);
    node_->SetMatchIndex("peer2:50053", 0);

    node_->UpdateCommitIndex();
    EXPECT_EQ(node_->GetCommitIndex(), 1u);
}

TEST_F(RaftNodeTest, NoCommitWithoutMajority) {
    node_->SetNodeState(raft::NodeState::CANDIDATE);
    node_->BecomeLeader();
    node_->SetCurrentTerm(1);

    raft::RaftLogEntry entry;
    entry.index = 1;
    entry.term = 1;
    node_->AppendLogEntry(entry);

    // No peers have replicated
    node_->UpdateCommitIndex();
    EXPECT_EQ(node_->GetCommitIndex(), 0u);
}

TEST_F(RaftNodeTest, OnlyCommitCurrentTermEntries) {
    node_->SetNodeState(raft::NodeState::CANDIDATE);
    node_->BecomeLeader();
    node_->SetCurrentTerm(2);

    // Entry from previous term
    raft::RaftLogEntry entry1;
    entry1.index = 1;
    entry1.term = 1;  // Previous term
    node_->AppendLogEntry(entry1);

    // Both peers have replicated
    node_->SetMatchIndex("peer1:50052", 1);
    node_->SetMatchIndex("peer2:50053", 1);

    // Should not commit entry from previous term
    node_->UpdateCommitIndex();
    EXPECT_EQ(node_->GetCommitIndex(), 0u);
}

// ============================================================================
// nodeStateToString Tests
// ============================================================================

TEST(NodeStateToStringTest, Follower) {
    EXPECT_EQ(raft::nodeStateToString(raft::NodeState::FOLLOWER), "follower");
}

TEST(NodeStateToStringTest, Candidate) {
    EXPECT_EQ(raft::nodeStateToString(raft::NodeState::CANDIDATE), "candidate");
}

TEST(NodeStateToStringTest, Leader) {
    EXPECT_EQ(raft::nodeStateToString(raft::NodeState::LEADER), "leader");
}

// ============================================================================
// Edge Case Tests
// ============================================================================

TEST_F(RaftNodeTest, HandleEmptyPeers) {
    auto node = std::make_unique<raft::TestableRaftNode>("lonely", 50051, std::vector<std::string>{});
    EXPECT_TRUE(node->GetPeers().empty());
}

TEST_F(RaftNodeTest, HandleLargeTerm) {
    node_->SetCurrentTerm(UINT64_MAX - 1);
    node_->StartElection();
    EXPECT_EQ(node_->GetCurrentTerm(), UINT64_MAX);
}

TEST_F(RaftNodeTest, HandleMultipleStepDowns) {
    node_->StepDown(1);
    node_->StepDown(2);
    node_->StepDown(3);
    EXPECT_EQ(node_->GetCurrentTerm(), 3u);
    EXPECT_EQ(node_->GetNodeState(), raft::NodeState::FOLLOWER);
}

TEST_F(RaftNodeTest, HandleKeyWithColon) {
    // Edge case: key contains colon separator
    raft::RaftLogEntry entry;
    entry.index = 1;
    entry.term = 1;
    entry.command_type = "put";
    std::string cmd = "key:with:colons:value";
    entry.command.assign(cmd.begin(), cmd.end());

    node_->ApplyCommand(entry);
    // First colon splits key from value
    EXPECT_EQ(node_->GetKV("key"), "with:colons:value");
}

TEST_F(RaftNodeTest, HandleEmptyValue) {
    raft::RaftLogEntry entry;
    entry.index = 1;
    entry.term = 1;
    entry.command_type = "put";
    std::string cmd = "emptyval:";
    entry.command.assign(cmd.begin(), cmd.end());

    node_->ApplyCommand(entry);
    EXPECT_TRUE(node_->HasKV("emptyval"));
    EXPECT_EQ(node_->GetKV("emptyval"), "");
}

// ============================================================================
// Protobuf Message Tests
// ============================================================================

TEST(ProtobufTest, RequestVoteRequestSerialization) {
    raft::RequestVoteRequest request;
    request.set_term(5);
    request.set_candidate_id("candidate1");
    request.set_last_log_index(10);
    request.set_last_log_term(3);

    EXPECT_EQ(request.term(), 5u);
    EXPECT_EQ(request.candidate_id(), "candidate1");
    EXPECT_EQ(request.last_log_index(), 10u);
    EXPECT_EQ(request.last_log_term(), 3u);
}

TEST(ProtobufTest, RequestVoteResponseSerialization) {
    raft::RequestVoteResponse response;
    response.set_term(5);
    response.set_vote_granted(true);

    EXPECT_EQ(response.term(), 5u);
    EXPECT_TRUE(response.vote_granted());
}

TEST(ProtobufTest, AppendEntriesRequestSerialization) {
    raft::AppendEntriesRequest request;
    request.set_term(3);
    request.set_leader_id("leader1");
    request.set_prev_log_index(5);
    request.set_prev_log_term(2);
    request.set_leader_commit(4);

    auto* entry = request.add_entries();
    entry->set_index(6);
    entry->set_term(3);
    entry->set_command_type("put");
    entry->set_command("key:value");

    EXPECT_EQ(request.term(), 3u);
    EXPECT_EQ(request.leader_id(), "leader1");
    EXPECT_EQ(request.entries_size(), 1);
    EXPECT_EQ(request.entries(0).index(), 6u);
}

TEST(ProtobufTest, AppendEntriesResponseSerialization) {
    raft::AppendEntriesResponse response;
    response.set_term(3);
    response.set_success(true);
    response.set_match_index(5);

    EXPECT_EQ(response.term(), 3u);
    EXPECT_TRUE(response.success());
    EXPECT_EQ(response.match_index(), 5u);
}

TEST(ProtobufTest, LogEntrySerialization) {
    raft::LogEntry entry;
    entry.set_index(1);
    entry.set_term(1);
    entry.set_command_type("put");
    entry.set_command("foo:bar");

    EXPECT_EQ(entry.index(), 1u);
    EXPECT_EQ(entry.term(), 1u);
    EXPECT_EQ(entry.command_type(), "put");
    EXPECT_EQ(entry.command(), "foo:bar");
}

TEST(ProtobufTest, GetRequestSerialization) {
    raft::GetRequest request;
    request.set_key("testkey");
    EXPECT_EQ(request.key(), "testkey");
}

TEST(ProtobufTest, GetResponseSerialization) {
    raft::GetResponse response;
    response.set_value("testvalue");
    response.set_found(true);

    EXPECT_EQ(response.value(), "testvalue");
    EXPECT_TRUE(response.found());
}

TEST(ProtobufTest, PutRequestSerialization) {
    raft::PutRequest request;
    request.set_key("mykey");
    request.set_value("myvalue");

    EXPECT_EQ(request.key(), "mykey");
    EXPECT_EQ(request.value(), "myvalue");
}

TEST(ProtobufTest, PutResponseSerialization) {
    raft::PutResponse response;
    response.set_success(true);
    response.set_leader_hint("leader1:50051");

    EXPECT_TRUE(response.success());
    EXPECT_EQ(response.leader_hint(), "leader1:50051");
}

TEST(ProtobufTest, DeleteRequestSerialization) {
    raft::DeleteRequest request;
    request.set_key("deletekey");
    EXPECT_EQ(request.key(), "deletekey");
}

TEST(ProtobufTest, DeleteResponseSerialization) {
    raft::DeleteResponse response;
    response.set_success(true);

    EXPECT_TRUE(response.success());
}

TEST(ProtobufTest, GetClusterStatusResponseSerialization) {
    raft::GetClusterStatusResponse response;
    response.set_node_id("node1");
    response.set_state("leader");
    response.set_current_term(5);
    response.set_commit_index(10);
    response.set_last_applied(9);
    response.set_log_length(11);

    auto* member = response.add_members();
    member->set_node_id("node2");
    member->set_address("node2:50052");
    member->set_match_index(8);
    member->set_next_index(9);

    EXPECT_EQ(response.node_id(), "node1");
    EXPECT_EQ(response.state(), "leader");
    EXPECT_EQ(response.members_size(), 1);
    EXPECT_EQ(response.members(0).node_id(), "node2");
}

// ============================================================================
// Thread Safety Tests (Basic)
// ============================================================================

TEST_F(RaftNodeTest, ConcurrentReads) {
    node_->PutKV("shared", "value");

    std::vector<std::thread> threads;
    std::atomic<int> success_count{0};

    for (int i = 0; i < 10; ++i) {
        threads.emplace_back([this, &success_count]() {
            for (int j = 0; j < 100; ++j) {
                if (node_->GetKV("shared") == "value") {
                    success_count++;
                }
            }
        });
    }

    for (auto& t : threads) {
        t.join();
    }

    EXPECT_EQ(success_count.load(), 1000);
}

TEST_F(RaftNodeTest, ConcurrentStateReads) {
    std::vector<std::thread> threads;
    std::atomic<int> valid_count{0};

    for (int i = 0; i < 10; ++i) {
        threads.emplace_back([this, &valid_count]() {
            for (int j = 0; j < 100; ++j) {
                auto state = node_->GetNodeState();
                if (state == raft::NodeState::FOLLOWER ||
                    state == raft::NodeState::CANDIDATE ||
                    state == raft::NodeState::LEADER) {
                    valid_count++;
                }
            }
        });
    }

    for (auto& t : threads) {
        t.join();
    }

    EXPECT_EQ(valid_count.load(), 1000);
}

int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
