/**
 * Chandy-Lamport Snapshot Algorithm Implementation - C++ Template
 *
 * This template provides the basic structure for implementing the Chandy-Lamport
 * algorithm for capturing consistent global snapshots. You need to implement the TODO sections.
 *
 * Based on: "Distributed Snapshots: Determining Global States of Distributed Systems"
 * by K. Mani Chandy and Leslie Lamport (1985)
 *
 * Usage:
 *     ./server --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

#include <iostream>
#include <memory>
#include <string>
#include <vector>
#include <map>
#include <set>
#include <mutex>
#include <shared_mutex>
#include <chrono>
#include <thread>
#include <atomic>

#include <grpcpp/grpcpp.h>
#include "chandy_lamport.grpc.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;
using grpc::Channel;
using grpc::ClientContext;

namespace chandy_lamport {

// ============================================================================
// Data Structures
// ============================================================================

struct ChannelState {
    std::string from_process;
    std::string to_process;
    std::vector<ApplicationMessage> messages;
    std::atomic<bool> is_recording{false};
};

struct SnapshotState {
    std::string snapshot_id;
    std::string initiator_id;
    std::atomic<bool> local_state_recorded{false};
    uint64_t logical_clock = 0;
    std::map<std::string, int64_t> account_balances;
    std::map<std::string, std::string> kv_state;
    std::map<std::string, std::shared_ptr<ChannelState>> channel_states;
    std::set<std::string> markers_received;
    std::atomic<bool> recording_complete{false};
    uint64_t initiated_at = 0;
    uint64_t completed_at = 0;
};

// ============================================================================
// Chandy-Lamport Node Implementation
// ============================================================================

class ChandyLamportNode {
public:
    ChandyLamportNode(const std::string& node_id, int port, const std::vector<std::string>& peers)
        : node_id_(node_id), port_(port), peers_(peers), logical_clock_(0),
          snapshots_initiated_(0), snapshots_participated_(0) {

        // Initialize with default balance
        account_balances_[node_id + "_account"] = 1000;
    }

    void Initialize() {
        for (const auto& peer : peers_) {
            auto channel = grpc::CreateChannel(peer, grpc::InsecureChannelCredentials());
            peer_stubs_[peer] = SnapshotService::NewStub(channel);

            // Initialize incoming channel state
            std::string peer_id = peer.substr(0, peer.find(':'));
            auto cs = std::make_shared<ChannelState>();
            cs->from_process = peer_id;
            cs->to_process = node_id_;
            incoming_channels_[peer_id] = cs;
        }
        std::cout << "Node " << node_id_ << " initialized with " << peers_.size() << " peers" << std::endl;
    }

    uint64_t IncrementClock() {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        return ++logical_clock_;
    }

    void UpdateClock(uint64_t received_clock) {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        logical_clock_ = std::max(logical_clock_, received_clock) + 1;
    }

    // =========================================================================
    // Snapshot Initiation
    // =========================================================================

    /**
     * Initiate a new global snapshot.
     *
     * TODO: Implement snapshot initiation:
     * 1. Generate unique snapshot ID
     * 2. Record local state immediately
     * 3. Start recording on all incoming channels
     * 4. Send marker on all outgoing channels
     */
    InitiateSnapshotResponse InitiateSnapshot(const InitiateSnapshotRequest& request) {
        std::unique_lock<std::shared_mutex> lock(mutex_);

        std::string snapshot_id = request.snapshot_id().empty()
            ? GenerateUUID()
            : request.snapshot_id();

        // TODO: Implement snapshot initiation
        // - Record local state (account balances, kv_store, logical clock)
        // - Create SnapshotState
        // - Start recording on all incoming channels
        // - Send markers to all peers

        snapshots_initiated_++;

        InitiateSnapshotResponse response;
        response.set_success(true);
        response.set_snapshot_id(snapshot_id);
        response.set_initiated_at(GetCurrentTimeMs());
        return response;
    }

    // =========================================================================
    // Marker Handling
    // =========================================================================

    /**
     * Handle incoming marker message.
     *
     * TODO: Implement marker handling:
     * 1. If first marker for this snapshot:
     *    - Record local state
     *    - Mark sender's channel as empty
     *    - Start recording on other incoming channels
     *    - Send markers on all outgoing channels
     * 2. If not first marker:
     *    - Stop recording on sender's channel
     *    - Check if snapshot is complete
     */
    MarkerResponse ReceiveMarker(const MarkerMessage& request) {
        std::unique_lock<std::shared_mutex> lock(mutex_);

        std::string snapshot_id = request.snapshot_id();
        std::string sender_id = request.sender_id();

        UpdateClockInternal(request.logical_clock());

        bool first_marker = snapshots_.find(snapshot_id) == snapshots_.end();

        if (first_marker) {
            // TODO: Implement first marker handling
            snapshots_participated_++;
        } else {
            // TODO: Implement subsequent marker handling
        }

        MarkerResponse response;
        response.set_success(true);
        response.set_first_marker(first_marker);
        response.set_process_id(node_id_);
        return response;
    }

    // =========================================================================
    // Message Handling
    // =========================================================================

    SendMessageResponse SendMessage(const ApplicationMessage& request) {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        IncrementClockInternal();

        // TODO: Forward message to destination

        SendMessageResponse response;
        response.set_success(true);
        return response;
    }

    void RecordIncomingMessage(const std::string& sender_id, const ApplicationMessage& message) {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        for (auto& [id, snapshot] : snapshots_) {
            if (!snapshot->recording_complete) {
                std::string channel_key = sender_id + "->" + node_id_;
                auto it = snapshot->channel_states.find(channel_key);
                if (it != snapshot->channel_states.end() && it->second->is_recording) {
                    it->second->messages.push_back(message);
                }
            }
        }
    }

    // =========================================================================
    // Snapshot Retrieval
    // =========================================================================

    GetSnapshotResponse GetSnapshot(const GetSnapshotRequest& request) {
        std::shared_lock<std::shared_mutex> lock(mutex_);

        GetSnapshotResponse response;
        std::string snapshot_id = request.snapshot_id();

        auto it = snapshots_.find(snapshot_id);
        if (it != snapshots_.end()) {
            auto& snapshot = it->second;
            response.set_found(true);
            response.set_snapshot_id(snapshot_id);
            response.set_recording_complete(snapshot->recording_complete);

            auto* local_state = response.mutable_local_state();
            local_state->set_process_id(node_id_);
            local_state->set_logical_clock(snapshot->logical_clock);
            for (const auto& [k, v] : snapshot->account_balances) {
                (*local_state->mutable_account_balances())[k] = v;
            }
            for (const auto& [k, v] : snapshot->kv_state) {
                (*local_state->mutable_kv_state())[k] = v;
            }

            for (const auto& [key, cs] : snapshot->channel_states) {
                auto* channel_state = response.add_channel_states();
                channel_state->set_from_process(cs->from_process);
                channel_state->set_to_process(cs->to_process);
                for (const auto& msg : cs->messages) {
                    *channel_state->add_messages() = msg;
                }
            }
        } else {
            response.set_found(false);
        }

        return response;
    }

    GetGlobalSnapshotResponse GetGlobalSnapshot(const GetGlobalSnapshotRequest& request) {
        std::shared_lock<std::shared_mutex> lock(mutex_);

        GetGlobalSnapshotResponse response;
        std::string snapshot_id = request.snapshot_id();

        if (snapshots_.find(snapshot_id) == snapshots_.end()) {
            response.set_success(false);
            response.set_error("Snapshot not found");
            return response;
        }

        // TODO: Collect snapshots from all peers and combine
        response.set_success(false);
        response.set_error("Not implemented");
        return response;
    }

    // =========================================================================
    // Bank Service
    // =========================================================================

    GetBalanceResponse GetBalance(const GetBalanceRequest& request) {
        std::shared_lock<std::shared_mutex> lock(mutex_);
        GetBalanceResponse response;
        auto it = account_balances_.find(request.account_id());
        response.set_found(it != account_balances_.end());
        response.set_balance(it != account_balances_.end() ? it->second : 0);
        return response;
    }

    TransferResponse Transfer(const TransferRequest& request) {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        TransferResponse response;

        auto from_it = account_balances_.find(request.from_account());
        if (from_it == account_balances_.end()) {
            response.set_success(false);
            response.set_error("Source account not found");
            return response;
        }

        if (from_it->second < request.amount()) {
            response.set_success(false);
            response.set_error("Insufficient funds");
            return response;
        }

        from_it->second -= request.amount();
        account_balances_[request.to_account()] += request.amount();

        response.set_success(true);
        response.set_from_balance(from_it->second);
        response.set_to_balance(account_balances_[request.to_account()]);
        return response;
    }

    DepositResponse Deposit(const DepositRequest& request) {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        DepositResponse response;
        account_balances_[request.account_id()] += request.amount();
        response.set_success(true);
        response.set_new_balance(account_balances_[request.account_id()]);
        return response;
    }

    // =========================================================================
    // KeyValue Service
    // =========================================================================

    GetResponse Get(const GetRequest& request) {
        std::shared_lock<std::shared_mutex> lock(mutex_);
        GetResponse response;
        auto it = kv_store_.find(request.key());
        response.set_found(it != kv_store_.end());
        response.set_value(it != kv_store_.end() ? it->second : "");
        return response;
    }

    PutResponse Put(const PutRequest& request) {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        PutResponse response;
        kv_store_[request.key()] = request.value();
        response.set_success(true);
        return response;
    }

    DeleteResponse Delete(const DeleteRequest& request) {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        DeleteResponse response;
        kv_store_.erase(request.key());
        response.set_success(true);
        return response;
    }

    GetLeaderResponse GetLeader(const GetLeaderRequest& request) {
        GetLeaderResponse response;
        response.set_initiator_id(node_id_);
        response.set_is_initiator(true);
        return response;
    }

    GetClusterStatusResponse GetClusterStatus(const GetClusterStatusRequest& request) {
        std::shared_lock<std::shared_mutex> lock(mutex_);
        GetClusterStatusResponse response;
        response.set_node_id(node_id_);
        response.set_logical_clock(logical_clock_);
        response.set_is_recording(!current_snapshot_id_.empty());
        response.set_current_snapshot_id(current_snapshot_id_);
        response.set_snapshots_initiated(snapshots_initiated_);
        response.set_snapshots_participated(snapshots_participated_);

        for (const auto& peer : peers_) {
            auto* member = response.add_members();
            member->set_address(peer);
            member->set_is_healthy(true);
        }

        return response;
    }

private:
    uint64_t IncrementClockInternal() {
        return ++logical_clock_;
    }

    void UpdateClockInternal(uint64_t received_clock) {
        logical_clock_ = std::max(logical_clock_, received_clock) + 1;
    }

    std::string GenerateUUID() {
        static std::atomic<uint64_t> counter{0};
        return "snapshot-" + std::to_string(counter++) + "-" +
               std::to_string(GetCurrentTimeMs());
    }

    uint64_t GetCurrentTimeMs() {
        return std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()
        ).count();
    }

    std::string node_id_;
    int port_;
    std::vector<std::string> peers_;

    std::atomic<uint64_t> logical_clock_;
    std::map<std::string, std::shared_ptr<SnapshotState>> snapshots_;
    std::string current_snapshot_id_;

    std::map<std::string, std::shared_ptr<ChannelState>> incoming_channels_;
    std::map<std::string, int64_t> account_balances_;
    std::map<std::string, std::string> kv_store_;

    std::atomic<uint64_t> snapshots_initiated_;
    std::atomic<uint64_t> snapshots_participated_;

    mutable std::shared_mutex mutex_;
    std::map<std::string, std::unique_ptr<SnapshotService::Stub>> peer_stubs_;
};

// ============================================================================
// gRPC Service Implementations
// ============================================================================

class SnapshotServiceImpl final : public SnapshotService::Service {
public:
    explicit SnapshotServiceImpl(ChandyLamportNode* node) : node_(node) {}

    Status InitiateSnapshot(ServerContext* context, const InitiateSnapshotRequest* request,
                            InitiateSnapshotResponse* response) override {
        *response = node_->InitiateSnapshot(*request);
        return Status::OK;
    }

    Status ReceiveMarker(ServerContext* context, const MarkerMessage* request,
                         MarkerResponse* response) override {
        *response = node_->ReceiveMarker(*request);
        return Status::OK;
    }

    Status SendMessage(ServerContext* context, const ApplicationMessage* request,
                       SendMessageResponse* response) override {
        *response = node_->SendMessage(*request);
        return Status::OK;
    }

    Status GetSnapshot(ServerContext* context, const GetSnapshotRequest* request,
                       GetSnapshotResponse* response) override {
        *response = node_->GetSnapshot(*request);
        return Status::OK;
    }

    Status GetGlobalSnapshot(ServerContext* context, const GetGlobalSnapshotRequest* request,
                             GetGlobalSnapshotResponse* response) override {
        *response = node_->GetGlobalSnapshot(*request);
        return Status::OK;
    }

private:
    ChandyLamportNode* node_;
};

class BankServiceImpl final : public BankService::Service {
public:
    explicit BankServiceImpl(ChandyLamportNode* node) : node_(node) {}

    Status GetBalance(ServerContext* context, const GetBalanceRequest* request,
                      GetBalanceResponse* response) override {
        *response = node_->GetBalance(*request);
        return Status::OK;
    }

    Status Transfer(ServerContext* context, const TransferRequest* request,
                    TransferResponse* response) override {
        *response = node_->Transfer(*request);
        return Status::OK;
    }

    Status Deposit(ServerContext* context, const DepositRequest* request,
                   DepositResponse* response) override {
        *response = node_->Deposit(*request);
        return Status::OK;
    }

    Status Withdraw(ServerContext* context, const WithdrawRequest* request,
                    WithdrawResponse* response) override {
        response->set_success(false);
        response->set_error("Not implemented");
        return Status::OK;
    }

private:
    ChandyLamportNode* node_;
};

class KeyValueServiceImpl final : public KeyValueService::Service {
public:
    explicit KeyValueServiceImpl(ChandyLamportNode* node) : node_(node) {}

    Status Get(ServerContext* context, const GetRequest* request,
               GetResponse* response) override {
        *response = node_->Get(*request);
        return Status::OK;
    }

    Status Put(ServerContext* context, const PutRequest* request,
               PutResponse* response) override {
        *response = node_->Put(*request);
        return Status::OK;
    }

    Status Delete(ServerContext* context, const DeleteRequest* request,
                  DeleteResponse* response) override {
        *response = node_->Delete(*request);
        return Status::OK;
    }

    Status GetLeader(ServerContext* context, const GetLeaderRequest* request,
                     GetLeaderResponse* response) override {
        *response = node_->GetLeader(*request);
        return Status::OK;
    }

    Status GetClusterStatus(ServerContext* context, const GetClusterStatusRequest* request,
                            GetClusterStatusResponse* response) override {
        *response = node_->GetClusterStatus(*request);
        return Status::OK;
    }

private:
    ChandyLamportNode* node_;
};

} // namespace chandy_lamport

// ============================================================================
// Main Entry Point
// ============================================================================

int main(int argc, char** argv) {
    std::string node_id;
    int port = 50051;
    std::vector<std::string> peers;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--node-id" && i + 1 < argc) {
            node_id = argv[++i];
        } else if (arg == "--port" && i + 1 < argc) {
            port = std::stoi(argv[++i]);
        } else if (arg == "--peers" && i + 1 < argc) {
            std::string peers_str = argv[++i];
            size_t pos = 0;
            while ((pos = peers_str.find(',')) != std::string::npos) {
                peers.push_back(peers_str.substr(0, pos));
                peers_str.erase(0, pos + 1);
            }
            if (!peers_str.empty()) {
                peers.push_back(peers_str);
            }
        }
    }

    if (node_id.empty()) {
        std::cerr << "Usage: " << argv[0]
                  << " --node-id <id> --port <port> --peers <peer1:port1,peer2:port2>"
                  << std::endl;
        return 1;
    }

    chandy_lamport::ChandyLamportNode node(node_id, port, peers);
    node.Initialize();

    std::string server_address = "0.0.0.0:" + std::to_string(port);

    chandy_lamport::SnapshotServiceImpl snapshot_service(&node);
    chandy_lamport::BankServiceImpl bank_service(&node);
    chandy_lamport::KeyValueServiceImpl kv_service(&node);

    ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
    builder.RegisterService(&snapshot_service);
    builder.RegisterService(&bank_service);
    builder.RegisterService(&kv_service);

    std::unique_ptr<Server> server(builder.BuildAndStart());
    std::cout << "Chandy-Lamport node " << node_id << " listening on " << server_address << std::endl;

    server->Wait();
    return 0;
}
