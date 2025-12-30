/**
 * Integration Tests for Raft Consensus Implementation
 *
 * Tests cover:
 * - gRPC service initialization
 * - RequestVote RPC handling
 * - AppendEntries RPC handling
 * - KeyValue service operations
 * - Multi-node cluster simulation
 * - Leader election scenarios
 * - Log replication scenarios
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
#include <future>

#include <grpcpp/grpcpp.h>
#include <grpcpp/health_check_service_interface.h>
#include "raft.grpc.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;
using grpc::Channel;
using grpc::ClientContext;

// ============================================================================
// Mock RaftService for testing
// ============================================================================

class MockRaftService : public raft::RaftService::Service {
public:
    MockRaftService() : current_term_(0), voted_for_(""), vote_granted_(false) {}

    Status RequestVote(ServerContext* context,
                       const raft::RequestVoteRequest* request,
                       raft::RequestVoteResponse* response) override {
        (void)context;
        std::lock_guard<std::mutex> lock(mutex_);
        request_vote_calls_++;

        // Simple voting logic for testing
        if (request->term() > current_term_) {
            current_term_ = request->term();
            voted_for_ = "";
        }

        if (request->term() == current_term_ &&
            (voted_for_.empty() || voted_for_ == request->candidate_id())) {
            voted_for_ = request->candidate_id();
            response->set_vote_granted(true);
            vote_granted_ = true;
        } else {
            response->set_vote_granted(false);
        }

        response->set_term(current_term_);
        return Status::OK;
    }

    Status AppendEntries(ServerContext* context,
                         const raft::AppendEntriesRequest* request,
                         raft::AppendEntriesResponse* response) override {
        (void)context;
        std::lock_guard<std::mutex> lock(mutex_);
        append_entries_calls_++;

        if (request->term() > current_term_) {
            current_term_ = request->term();
            voted_for_ = "";
        }

        response->set_term(current_term_);

        if (request->term() < current_term_) {
            response->set_success(false);
            return Status::OK;
        }

        leader_id_ = request->leader_id();

        // Simple log matching for testing
        if (request->prev_log_index() > log_.size()) {
            response->set_success(false);
            return Status::OK;
        }

        // Accept entries
        for (int i = 0; i < request->entries_size(); ++i) {
            log_.push_back(request->entries(i));
        }

        if (request->leader_commit() > commit_index_) {
            commit_index_ = std::min(request->leader_commit(),
                                     static_cast<uint64_t>(log_.size()));
        }

        response->set_success(true);
        response->set_match_index(log_.size());
        return Status::OK;
    }

    Status InstallSnapshot(ServerContext* context,
                           const raft::InstallSnapshotRequest* request,
                           raft::InstallSnapshotResponse* response) override {
        (void)context;
        (void)request;
        std::lock_guard<std::mutex> lock(mutex_);
        install_snapshot_calls_++;
        response->set_term(current_term_);
        return Status::OK;
    }

    // Test accessors
    int GetRequestVoteCalls() const { return request_vote_calls_; }
    int GetAppendEntriesCalls() const { return append_entries_calls_; }
    int GetInstallSnapshotCalls() const { return install_snapshot_calls_; }
    uint64_t GetCurrentTerm() const { return current_term_; }
    std::string GetVotedFor() const { return voted_for_; }
    std::string GetLeaderId() const { return leader_id_; }
    size_t GetLogSize() const { return log_.size(); }
    uint64_t GetCommitIndex() const { return commit_index_; }

    void SetCurrentTerm(uint64_t term) { current_term_ = term; }
    void SetVotedFor(const std::string& id) { voted_for_ = id; }

private:
    std::mutex mutex_;
    uint64_t current_term_;
    std::string voted_for_;
    std::string leader_id_;
    std::vector<raft::LogEntry> log_;
    uint64_t commit_index_ = 0;
    bool vote_granted_;
    int request_vote_calls_ = 0;
    int append_entries_calls_ = 0;
    int install_snapshot_calls_ = 0;
};

// ============================================================================
// Mock KeyValueService for testing
// ============================================================================

class MockKeyValueService : public raft::KeyValueService::Service {
public:
    Status Get(ServerContext* context,
               const raft::GetRequest* request,
               raft::GetResponse* response) override {
        (void)context;
        std::lock_guard<std::mutex> lock(mutex_);
        auto it = kv_store_.find(request->key());
        if (it != kv_store_.end()) {
            response->set_value(it->second);
            response->set_found(true);
        } else {
            response->set_found(false);
        }
        return Status::OK;
    }

    Status Put(ServerContext* context,
               const raft::PutRequest* request,
               raft::PutResponse* response) override {
        (void)context;
        std::lock_guard<std::mutex> lock(mutex_);
        if (!is_leader_) {
            response->set_success(false);
            response->set_leader_hint(leader_hint_);
            return Status::OK;
        }
        kv_store_[request->key()] = request->value();
        response->set_success(true);
        return Status::OK;
    }

    Status Delete(ServerContext* context,
                  const raft::DeleteRequest* request,
                  raft::DeleteResponse* response) override {
        (void)context;
        std::lock_guard<std::mutex> lock(mutex_);
        if (!is_leader_) {
            response->set_success(false);
            response->set_leader_hint(leader_hint_);
            return Status::OK;
        }
        kv_store_.erase(request->key());
        response->set_success(true);
        return Status::OK;
    }

    Status GetLeader(ServerContext* context,
                     const raft::GetLeaderRequest* request,
                     raft::GetLeaderResponse* response) override {
        (void)context;
        (void)request;
        std::lock_guard<std::mutex> lock(mutex_);
        response->set_leader_id(leader_id_);
        response->set_is_leader(is_leader_);
        response->set_leader_address(leader_address_);
        return Status::OK;
    }

    Status GetClusterStatus(ServerContext* context,
                            const raft::GetClusterStatusRequest* request,
                            raft::GetClusterStatusResponse* response) override {
        (void)context;
        (void)request;
        std::lock_guard<std::mutex> lock(mutex_);
        response->set_node_id(node_id_);
        response->set_state(is_leader_ ? "leader" : "follower");
        response->set_current_term(current_term_);
        response->set_commit_index(commit_index_);
        response->set_last_applied(last_applied_);
        return Status::OK;
    }

    // Test configuration
    void SetIsLeader(bool is_leader) { is_leader_ = is_leader; }
    void SetLeaderHint(const std::string& hint) { leader_hint_ = hint; }
    void SetLeaderId(const std::string& id) { leader_id_ = id; }
    void SetLeaderAddress(const std::string& addr) { leader_address_ = addr; }
    void SetNodeId(const std::string& id) { node_id_ = id; }
    void SetCurrentTerm(uint64_t term) { current_term_ = term; }
    void SetCommitIndex(uint64_t idx) { commit_index_ = idx; }
    void SetLastApplied(uint64_t idx) { last_applied_ = idx; }

    // Direct KV access for testing
    void DirectPut(const std::string& key, const std::string& value) {
        std::lock_guard<std::mutex> lock(mutex_);
        kv_store_[key] = value;
    }

    std::string DirectGet(const std::string& key) {
        std::lock_guard<std::mutex> lock(mutex_);
        auto it = kv_store_.find(key);
        return it != kv_store_.end() ? it->second : "";
    }

private:
    std::mutex mutex_;
    std::map<std::string, std::string> kv_store_;
    bool is_leader_ = false;
    std::string leader_hint_;
    std::string leader_id_;
    std::string leader_address_;
    std::string node_id_;
    uint64_t current_term_ = 0;
    uint64_t commit_index_ = 0;
    uint64_t last_applied_ = 0;
};

// ============================================================================
// Test Fixtures
// ============================================================================

class RaftIntegrationTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Start mock service
        raft_service_ = std::make_unique<MockRaftService>();
        kv_service_ = std::make_unique<MockKeyValueService>();

        ServerBuilder builder;
        server_address_ = "localhost:0";  // Let OS pick port
        builder.AddListeningPort(server_address_, grpc::InsecureServerCredentials(), &port_);
        builder.RegisterService(raft_service_.get());
        builder.RegisterService(kv_service_.get());
        server_ = builder.BuildAndStart();

        // Update address with actual port
        server_address_ = "localhost:" + std::to_string(port_);

        // Create client stubs
        auto channel = grpc::CreateChannel(server_address_, grpc::InsecureChannelCredentials());
        raft_stub_ = raft::RaftService::NewStub(channel);
        kv_stub_ = raft::KeyValueService::NewStub(channel);
    }

    void TearDown() override {
        server_->Shutdown();
        server_.reset();
    }

    std::string server_address_;
    int port_;
    std::unique_ptr<Server> server_;
    std::unique_ptr<MockRaftService> raft_service_;
    std::unique_ptr<MockKeyValueService> kv_service_;
    std::unique_ptr<raft::RaftService::Stub> raft_stub_;
    std::unique_ptr<raft::KeyValueService::Stub> kv_stub_;
};

class MultiNodeTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Create 3 mock nodes
        for (int i = 0; i < 3; ++i) {
            auto raft_svc = std::make_unique<MockRaftService>();
            auto kv_svc = std::make_unique<MockKeyValueService>();

            ServerBuilder builder;
            int port;
            builder.AddListeningPort("localhost:0", grpc::InsecureServerCredentials(), &port);
            builder.RegisterService(raft_svc.get());
            builder.RegisterService(kv_svc.get());
            auto server = builder.BuildAndStart();

            std::string addr = "localhost:" + std::to_string(port);

            kv_svc->SetNodeId("node" + std::to_string(i));

            addresses_.push_back(addr);
            raft_services_.push_back(std::move(raft_svc));
            kv_services_.push_back(std::move(kv_svc));
            servers_.push_back(std::move(server));

            auto channel = grpc::CreateChannel(addr, grpc::InsecureChannelCredentials());
            raft_stubs_.push_back(raft::RaftService::NewStub(channel));
            kv_stubs_.push_back(raft::KeyValueService::NewStub(channel));
        }
    }

    void TearDown() override {
        for (auto& server : servers_) {
            server->Shutdown();
        }
    }

    std::vector<std::string> addresses_;
    std::vector<std::unique_ptr<MockRaftService>> raft_services_;
    std::vector<std::unique_ptr<MockKeyValueService>> kv_services_;
    std::vector<std::unique_ptr<Server>> servers_;
    std::vector<std::unique_ptr<raft::RaftService::Stub>> raft_stubs_;
    std::vector<std::unique_ptr<raft::KeyValueService::Stub>> kv_stubs_;
};

// ============================================================================
// RequestVote RPC Tests
// ============================================================================

TEST_F(RaftIntegrationTest, RequestVoteBasic) {
    raft::RequestVoteRequest request;
    request.set_term(1);
    request.set_candidate_id("candidate1");
    request.set_last_log_index(0);
    request.set_last_log_term(0);

    raft::RequestVoteResponse response;
    ClientContext context;

    Status status = raft_stub_->RequestVote(&context, request, &response);

    ASSERT_TRUE(status.ok());
    EXPECT_TRUE(response.vote_granted());
    EXPECT_EQ(response.term(), 1u);
}

TEST_F(RaftIntegrationTest, RequestVoteRejectLowerTerm) {
    // Set current term higher
    raft_service_->SetCurrentTerm(5);

    raft::RequestVoteRequest request;
    request.set_term(3);  // Lower than current
    request.set_candidate_id("candidate1");
    request.set_last_log_index(0);
    request.set_last_log_term(0);

    raft::RequestVoteResponse response;
    ClientContext context;

    Status status = raft_stub_->RequestVote(&context, request, &response);

    ASSERT_TRUE(status.ok());
    EXPECT_FALSE(response.vote_granted());
    EXPECT_EQ(response.term(), 5u);
}

TEST_F(RaftIntegrationTest, RequestVoteRejectAlreadyVoted) {
    // First vote
    {
        raft::RequestVoteRequest request;
        request.set_term(1);
        request.set_candidate_id("candidate1");
        raft::RequestVoteResponse response;
        ClientContext context;
        raft_stub_->RequestVote(&context, request, &response);
        EXPECT_TRUE(response.vote_granted());
    }

    // Second vote in same term - should be rejected
    {
        raft::RequestVoteRequest request;
        request.set_term(1);
        request.set_candidate_id("candidate2");
        raft::RequestVoteResponse response;
        ClientContext context;
        raft_stub_->RequestVote(&context, request, &response);
        EXPECT_FALSE(response.vote_granted());
    }
}

TEST_F(RaftIntegrationTest, RequestVoteCountCalls) {
    for (int i = 0; i < 5; ++i) {
        raft::RequestVoteRequest request;
        request.set_term(i + 1);
        request.set_candidate_id("candidate" + std::to_string(i));
        raft::RequestVoteResponse response;
        ClientContext context;
        raft_stub_->RequestVote(&context, request, &response);
    }

    EXPECT_EQ(raft_service_->GetRequestVoteCalls(), 5);
}

// ============================================================================
// AppendEntries RPC Tests
// ============================================================================

TEST_F(RaftIntegrationTest, AppendEntriesHeartbeat) {
    raft::AppendEntriesRequest request;
    request.set_term(1);
    request.set_leader_id("leader1");
    request.set_prev_log_index(0);
    request.set_prev_log_term(0);
    request.set_leader_commit(0);

    raft::AppendEntriesResponse response;
    ClientContext context;

    Status status = raft_stub_->AppendEntries(&context, request, &response);

    ASSERT_TRUE(status.ok());
    EXPECT_TRUE(response.success());
    EXPECT_EQ(response.term(), 1u);
}

TEST_F(RaftIntegrationTest, AppendEntriesWithLogEntry) {
    raft::AppendEntriesRequest request;
    request.set_term(1);
    request.set_leader_id("leader1");
    request.set_prev_log_index(0);
    request.set_prev_log_term(0);
    request.set_leader_commit(0);

    auto* entry = request.add_entries();
    entry->set_index(1);
    entry->set_term(1);
    entry->set_command_type("put");
    entry->set_command("key:value");

    raft::AppendEntriesResponse response;
    ClientContext context;

    Status status = raft_stub_->AppendEntries(&context, request, &response);

    ASSERT_TRUE(status.ok());
    EXPECT_TRUE(response.success());
    EXPECT_EQ(raft_service_->GetLogSize(), 1u);
}

TEST_F(RaftIntegrationTest, AppendEntriesRejectLowerTerm) {
    raft_service_->SetCurrentTerm(5);

    raft::AppendEntriesRequest request;
    request.set_term(3);  // Lower term
    request.set_leader_id("leader1");
    request.set_prev_log_index(0);
    request.set_prev_log_term(0);

    raft::AppendEntriesResponse response;
    ClientContext context;

    Status status = raft_stub_->AppendEntries(&context, request, &response);

    ASSERT_TRUE(status.ok());
    EXPECT_FALSE(response.success());
    EXPECT_EQ(response.term(), 5u);
}

TEST_F(RaftIntegrationTest, AppendEntriesMultipleEntries) {
    raft::AppendEntriesRequest request;
    request.set_term(1);
    request.set_leader_id("leader1");
    request.set_prev_log_index(0);
    request.set_prev_log_term(0);
    request.set_leader_commit(0);

    for (int i = 1; i <= 5; ++i) {
        auto* entry = request.add_entries();
        entry->set_index(i);
        entry->set_term(1);
        entry->set_command_type("put");
        entry->set_command("key" + std::to_string(i) + ":value" + std::to_string(i));
    }

    raft::AppendEntriesResponse response;
    ClientContext context;

    Status status = raft_stub_->AppendEntries(&context, request, &response);

    ASSERT_TRUE(status.ok());
    EXPECT_TRUE(response.success());
    EXPECT_EQ(raft_service_->GetLogSize(), 5u);
}

TEST_F(RaftIntegrationTest, AppendEntriesCountCalls) {
    for (int i = 0; i < 10; ++i) {
        raft::AppendEntriesRequest request;
        request.set_term(1);
        request.set_leader_id("leader1");
        raft::AppendEntriesResponse response;
        ClientContext context;
        raft_stub_->AppendEntries(&context, request, &response);
    }

    EXPECT_EQ(raft_service_->GetAppendEntriesCalls(), 10);
}

// ============================================================================
// KeyValue Service Tests
// ============================================================================

TEST_F(RaftIntegrationTest, GetNonExistentKey) {
    raft::GetRequest request;
    request.set_key("nonexistent");

    raft::GetResponse response;
    ClientContext context;

    Status status = kv_stub_->Get(&context, request, &response);

    ASSERT_TRUE(status.ok());
    EXPECT_FALSE(response.found());
}

TEST_F(RaftIntegrationTest, GetExistingKey) {
    kv_service_->DirectPut("testkey", "testvalue");

    raft::GetRequest request;
    request.set_key("testkey");

    raft::GetResponse response;
    ClientContext context;

    Status status = kv_stub_->Get(&context, request, &response);

    ASSERT_TRUE(status.ok());
    EXPECT_TRUE(response.found());
    EXPECT_EQ(response.value(), "testvalue");
}

TEST_F(RaftIntegrationTest, PutAsLeader) {
    kv_service_->SetIsLeader(true);

    raft::PutRequest request;
    request.set_key("newkey");
    request.set_value("newvalue");

    raft::PutResponse response;
    ClientContext context;

    Status status = kv_stub_->Put(&context, request, &response);

    ASSERT_TRUE(status.ok());
    EXPECT_TRUE(response.success());
    EXPECT_EQ(kv_service_->DirectGet("newkey"), "newvalue");
}

TEST_F(RaftIntegrationTest, PutAsFollower) {
    kv_service_->SetIsLeader(false);
    kv_service_->SetLeaderHint("leader:50051");

    raft::PutRequest request;
    request.set_key("newkey");
    request.set_value("newvalue");

    raft::PutResponse response;
    ClientContext context;

    Status status = kv_stub_->Put(&context, request, &response);

    ASSERT_TRUE(status.ok());
    EXPECT_FALSE(response.success());
    EXPECT_EQ(response.leader_hint(), "leader:50051");
}

TEST_F(RaftIntegrationTest, DeleteAsLeader) {
    kv_service_->SetIsLeader(true);
    kv_service_->DirectPut("deletekey", "value");

    raft::DeleteRequest request;
    request.set_key("deletekey");

    raft::DeleteResponse response;
    ClientContext context;

    Status status = kv_stub_->Delete(&context, request, &response);

    ASSERT_TRUE(status.ok());
    EXPECT_TRUE(response.success());
    EXPECT_EQ(kv_service_->DirectGet("deletekey"), "");
}

TEST_F(RaftIntegrationTest, DeleteAsFollower) {
    kv_service_->SetIsLeader(false);
    kv_service_->SetLeaderHint("leader:50051");

    raft::DeleteRequest request;
    request.set_key("somekey");

    raft::DeleteResponse response;
    ClientContext context;

    Status status = kv_stub_->Delete(&context, request, &response);

    ASSERT_TRUE(status.ok());
    EXPECT_FALSE(response.success());
    EXPECT_EQ(response.leader_hint(), "leader:50051");
}

TEST_F(RaftIntegrationTest, GetLeader) {
    kv_service_->SetIsLeader(true);
    kv_service_->SetLeaderId("self");
    kv_service_->SetLeaderAddress("localhost:50051");

    raft::GetLeaderRequest request;
    raft::GetLeaderResponse response;
    ClientContext context;

    Status status = kv_stub_->GetLeader(&context, request, &response);

    ASSERT_TRUE(status.ok());
    EXPECT_TRUE(response.is_leader());
    EXPECT_EQ(response.leader_id(), "self");
    EXPECT_EQ(response.leader_address(), "localhost:50051");
}

TEST_F(RaftIntegrationTest, GetClusterStatus) {
    kv_service_->SetNodeId("node1");
    kv_service_->SetIsLeader(true);
    kv_service_->SetCurrentTerm(5);
    kv_service_->SetCommitIndex(10);
    kv_service_->SetLastApplied(9);

    raft::GetClusterStatusRequest request;
    raft::GetClusterStatusResponse response;
    ClientContext context;

    Status status = kv_stub_->GetClusterStatus(&context, request, &response);

    ASSERT_TRUE(status.ok());
    EXPECT_EQ(response.node_id(), "node1");
    EXPECT_EQ(response.state(), "leader");
    EXPECT_EQ(response.current_term(), 5u);
    EXPECT_EQ(response.commit_index(), 10u);
    EXPECT_EQ(response.last_applied(), 9u);
}

// ============================================================================
// Multi-Node Tests
// ============================================================================

TEST_F(MultiNodeTest, AllNodesRespond) {
    for (size_t i = 0; i < 3; ++i) {
        raft::GetClusterStatusRequest request;
        raft::GetClusterStatusResponse response;
        ClientContext context;

        Status status = kv_stubs_[i]->GetClusterStatus(&context, request, &response);

        ASSERT_TRUE(status.ok());
        EXPECT_EQ(response.node_id(), "node" + std::to_string(i));
    }
}

TEST_F(MultiNodeTest, SimulateLeaderElection) {
    // Node 0 becomes candidate and requests votes
    raft::RequestVoteRequest request;
    request.set_term(1);
    request.set_candidate_id("node0");
    request.set_last_log_index(0);
    request.set_last_log_term(0);

    int votes = 1;  // Self vote
    for (size_t i = 1; i < 3; ++i) {
        raft::RequestVoteResponse response;
        ClientContext context;

        Status status = raft_stubs_[i]->RequestVote(&context, request, &response);
        ASSERT_TRUE(status.ok());
        if (response.vote_granted()) {
            votes++;
        }
    }

    // Should have majority (2 out of 3)
    EXPECT_GE(votes, 2);
}

TEST_F(MultiNodeTest, SimulateLogReplication) {
    // Set node 0 as leader
    kv_services_[0]->SetIsLeader(true);

    // Leader sends AppendEntries to followers
    raft::AppendEntriesRequest request;
    request.set_term(1);
    request.set_leader_id("node0");
    request.set_prev_log_index(0);
    request.set_prev_log_term(0);
    request.set_leader_commit(0);

    auto* entry = request.add_entries();
    entry->set_index(1);
    entry->set_term(1);
    entry->set_command_type("put");
    entry->set_command("key:value");

    int success_count = 0;
    for (size_t i = 1; i < 3; ++i) {
        raft::AppendEntriesResponse response;
        ClientContext context;

        Status status = raft_stubs_[i]->AppendEntries(&context, request, &response);
        ASSERT_TRUE(status.ok());
        if (response.success()) {
            success_count++;
        }
    }

    // Both followers should accept
    EXPECT_EQ(success_count, 2);
}

TEST_F(MultiNodeTest, SimulateHeartbeats) {
    // Leader sends heartbeats
    raft::AppendEntriesRequest request;
    request.set_term(1);
    request.set_leader_id("node0");
    request.set_prev_log_index(0);
    request.set_prev_log_term(0);
    request.set_leader_commit(0);
    // Empty entries = heartbeat

    for (int round = 0; round < 3; ++round) {
        for (size_t i = 1; i < 3; ++i) {
            raft::AppendEntriesResponse response;
            ClientContext context;

            Status status = raft_stubs_[i]->AppendEntries(&context, request, &response);
            ASSERT_TRUE(status.ok());
            EXPECT_TRUE(response.success());
        }
    }

    // Each follower should have received 3 heartbeats
    EXPECT_EQ(raft_services_[1]->GetAppendEntriesCalls(), 3);
    EXPECT_EQ(raft_services_[2]->GetAppendEntriesCalls(), 3);
}

// ============================================================================
// Concurrent Request Tests
// ============================================================================

TEST_F(RaftIntegrationTest, ConcurrentGetRequests) {
    kv_service_->DirectPut("concurrent", "value");

    std::vector<std::future<bool>> futures;
    for (int i = 0; i < 10; ++i) {
        futures.push_back(std::async(std::launch::async, [this]() {
            raft::GetRequest request;
            request.set_key("concurrent");
            raft::GetResponse response;
            ClientContext context;

            Status status = kv_stub_->Get(&context, request, &response);
            return status.ok() && response.found() && response.value() == "value";
        }));
    }

    for (auto& f : futures) {
        EXPECT_TRUE(f.get());
    }
}

TEST_F(RaftIntegrationTest, ConcurrentPutRequests) {
    kv_service_->SetIsLeader(true);

    std::vector<std::future<bool>> futures;
    for (int i = 0; i < 10; ++i) {
        futures.push_back(std::async(std::launch::async, [this, i]() {
            raft::PutRequest request;
            request.set_key("key" + std::to_string(i));
            request.set_value("value" + std::to_string(i));
            raft::PutResponse response;
            ClientContext context;

            Status status = kv_stub_->Put(&context, request, &response);
            return status.ok() && response.success();
        }));
    }

    for (auto& f : futures) {
        EXPECT_TRUE(f.get());
    }

    // Verify all keys were stored
    for (int i = 0; i < 10; ++i) {
        EXPECT_EQ(kv_service_->DirectGet("key" + std::to_string(i)),
                  "value" + std::to_string(i));
    }
}

TEST_F(RaftIntegrationTest, ConcurrentRequestVotes) {
    std::vector<std::future<bool>> futures;
    for (int i = 0; i < 10; ++i) {
        futures.push_back(std::async(std::launch::async, [this, i]() {
            raft::RequestVoteRequest request;
            request.set_term(i + 1);
            request.set_candidate_id("candidate" + std::to_string(i));
            raft::RequestVoteResponse response;
            ClientContext context;

            Status status = raft_stub_->RequestVote(&context, request, &response);
            return status.ok();
        }));
    }

    for (auto& f : futures) {
        EXPECT_TRUE(f.get());
    }

    EXPECT_EQ(raft_service_->GetRequestVoteCalls(), 10);
}

// ============================================================================
// Error Handling Tests
// ============================================================================

TEST_F(RaftIntegrationTest, HandleShutdownGracefully) {
    // This test verifies the server can be shut down cleanly
    server_->Shutdown();

    // Try to make a request - should fail
    raft::GetRequest request;
    request.set_key("test");
    raft::GetResponse response;
    ClientContext context;

    Status status = kv_stub_->Get(&context, request, &response);
    EXPECT_FALSE(status.ok());
}

TEST(ConnectionTest, HandleUnreachableServer) {
    // Try to connect to a non-existent server
    auto channel = grpc::CreateChannel("localhost:99999", grpc::InsecureChannelCredentials());
    auto stub = raft::RaftService::NewStub(channel);

    raft::RequestVoteRequest request;
    request.set_term(1);
    request.set_candidate_id("test");

    raft::RequestVoteResponse response;
    ClientContext context;
    context.set_deadline(std::chrono::system_clock::now() + std::chrono::milliseconds(100));

    Status status = stub->RequestVote(&context, request, &response);
    EXPECT_FALSE(status.ok());
}

// ============================================================================
// Timeout Tests
// ============================================================================

TEST_F(RaftIntegrationTest, RequestWithTimeout) {
    raft::GetRequest request;
    request.set_key("test");
    raft::GetResponse response;

    ClientContext context;
    context.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(1));

    Status status = kv_stub_->Get(&context, request, &response);
    EXPECT_TRUE(status.ok());
}

// ============================================================================
// Edge Case Tests
// ============================================================================

TEST_F(RaftIntegrationTest, EmptyKeyGet) {
    raft::GetRequest request;
    request.set_key("");  // Empty key

    raft::GetResponse response;
    ClientContext context;

    Status status = kv_stub_->Get(&context, request, &response);
    ASSERT_TRUE(status.ok());
    EXPECT_FALSE(response.found());
}

TEST_F(RaftIntegrationTest, LargeValuePut) {
    kv_service_->SetIsLeader(true);

    std::string large_value(10000, 'x');  // 10KB value

    raft::PutRequest request;
    request.set_key("largekey");
    request.set_value(large_value);

    raft::PutResponse response;
    ClientContext context;

    Status status = kv_stub_->Put(&context, request, &response);

    ASSERT_TRUE(status.ok());
    EXPECT_TRUE(response.success());
    EXPECT_EQ(kv_service_->DirectGet("largekey"), large_value);
}

TEST_F(RaftIntegrationTest, SpecialCharactersInKey) {
    kv_service_->SetIsLeader(true);

    raft::PutRequest request;
    request.set_key("special!@#$%^&*()key");
    request.set_value("value");

    raft::PutResponse response;
    ClientContext context;

    Status status = kv_stub_->Put(&context, request, &response);

    ASSERT_TRUE(status.ok());
    EXPECT_TRUE(response.success());
}

int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
