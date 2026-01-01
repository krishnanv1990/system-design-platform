/**
 * Consistent Hashing Implementation - C++ Template
 *
 * This template provides the basic structure for implementing a
 * consistent hash ring for distributed key-value storage.
 *
 * Key concepts:
 * 1. Hash Ring - Keys and nodes are mapped to a circular hash space
 * 2. Virtual Nodes - Each physical node has multiple positions on the ring
 * 3. Lookup - Find the first node clockwise from the key's hash position
 * 4. Rebalancing - When nodes join/leave, only nearby keys need to move
 *
 * Usage:
 *     ./server --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <shared_mutex>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include <grpcpp/grpcpp.h>
#include "consistent_hashing.grpc.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;
using grpc::Channel;
using grpc::ClientContext;
using grpc::InsecureChannelCredentials;
using grpc::SslCredentials;
using grpc::SslCredentialsOptions;

namespace chash = consistent_hashing;

constexpr int DEFAULT_VIRTUAL_NODES = 150;
constexpr int DEFAULT_REPLICATION_FACTOR = 3;

// Virtual node on the hash ring
struct VirtualNode {
    std::string node_id;
    uint32_t virtual_id;
    uint64_t hash_value;

    bool operator<(const VirtualNode& other) const {
        return hash_value < other.hash_value;
    }
};

// Physical node info
struct NodeInfo {
    std::string node_id;
    std::string address;
    uint32_t virtual_nodes;
    uint64_t keys_count;
    bool is_healthy;
    uint64_t last_heartbeat;
};

// Hash ring state
struct HashRingState {
    std::unordered_map<std::string, std::shared_ptr<NodeInfo>> nodes;
    std::vector<VirtualNode> vnodes;
    uint32_t replication_factor = DEFAULT_REPLICATION_FACTOR;
    uint32_t vnodes_per_node = DEFAULT_VIRTUAL_NODES;
};

class ConsistentHashRing final : public chash::HashRingService::Service,
                                  public chash::KeyValueService::Service,
                                  public chash::NodeService::Service {
public:
    ConsistentHashRing(const std::string& node_id, int port, const std::vector<std::string>& peers)
        : node_id_(node_id), port_(port), peers_(peers) {}

    void Initialize() {
        for (const auto& peer : peers_) {
            std::shared_ptr<Channel> channel;

            // Cloud Run URLs require SSL
            if (peer.find(".run.app:443") != std::string::npos ||
                peer.find(".run.app") != std::string::npos) {
                SslCredentialsOptions ssl_opts;
                auto creds = SslCredentials(ssl_opts);
                channel = grpc::CreateChannel(peer, creds);
                std::cout << "Using SSL for peer: " << peer << std::endl;
            } else {
                channel = grpc::CreateChannel(peer, InsecureChannelCredentials());
                std::cout << "Using insecure channel for peer: " << peer << std::endl;
            }
            peer_stubs_[peer] = chash::NodeService::NewStub(channel);
        }

        // Add self to the ring
        std::string self_addr = "localhost:" + std::to_string(port_);
        AddNodeInternal(node_id_, self_addr, DEFAULT_VIRTUAL_NODES);
        std::cout << "Node " << node_id_ << " initialized with " << peers_.size() << " peers" << std::endl;
    }

    /**
     * Hash a key to a position on the ring.
     *
     * TODO: Implement consistent hashing function:
     * - Use a good hash function (MD5, SHA-1, etc.)
     * - Return a value in the ring's hash space
     * - Must be deterministic (same key always hashes to same position)
     */
    uint64_t Hash(const std::string& key) const {
        // Simple FNV-1a hash
        uint64_t hash = 14695981039346656037ULL;
        for (char c : key) {
            hash ^= static_cast<uint64_t>(c);
            hash *= 1099511628211ULL;
        }
        return hash;
    }

    uint64_t GetVNodeHash(const std::string& node_id, uint32_t virtual_id) const {
        return Hash(node_id + ":" + std::to_string(virtual_id));
    }

    /**
     * Add a node to the hash ring.
     *
     * TODO: Implement node addition:
     * 1. Create virtual nodes for this physical node
     * 2. Insert virtual nodes into the ring (maintain sorted order)
     * 3. Return list of added virtual nodes
     */
    std::vector<VirtualNode> AddNodeInternal(const std::string& node_id,
                                              const std::string& address,
                                              uint32_t num_vnodes) {
        std::unique_lock<std::shared_mutex> lock(mutex_);

        // Check if node already exists
        if (state_.nodes.find(node_id) != state_.nodes.end()) {
            return {};
        }

        // Create node info
        auto node_info = std::make_shared<NodeInfo>();
        node_info->node_id = node_id;
        node_info->address = address;
        node_info->virtual_nodes = num_vnodes;
        node_info->keys_count = 0;
        node_info->is_healthy = true;
        node_info->last_heartbeat = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();
        state_.nodes[node_id] = node_info;

        // Create virtual nodes
        std::vector<VirtualNode> added_vnodes;
        for (uint32_t i = 0; i < num_vnodes; ++i) {
            VirtualNode vnode;
            vnode.node_id = node_id;
            vnode.virtual_id = i;
            vnode.hash_value = GetVNodeHash(node_id, i);
            added_vnodes.push_back(vnode);
            state_.vnodes.push_back(vnode);
        }

        // Sort virtual nodes by hash value
        std::sort(state_.vnodes.begin(), state_.vnodes.end());

        std::cout << "Added node " << node_id << " with " << num_vnodes << " virtual nodes" << std::endl;
        return added_vnodes;
    }

    /**
     * Remove a node from the hash ring.
     *
     * TODO: Implement node removal:
     * 1. Remove all virtual nodes for this physical node
     * 2. Update the ring structure
     * 3. Return true if successful
     */
    bool RemoveNodeInternal(const std::string& node_id) {
        std::unique_lock<std::shared_mutex> lock(mutex_);

        if (state_.nodes.find(node_id) == state_.nodes.end()) {
            return false;
        }

        // Remove virtual nodes
        state_.vnodes.erase(
            std::remove_if(state_.vnodes.begin(), state_.vnodes.end(),
                [&node_id](const VirtualNode& v) { return v.node_id == node_id; }),
            state_.vnodes.end());

        state_.nodes.erase(node_id);
        std::cout << "Removed node " << node_id << std::endl;
        return true;
    }

    /**
     * Get the node responsible for a key.
     *
     * TODO: Implement key lookup:
     * 1. Hash the key to find its position on the ring
     * 2. Find the first node clockwise from that position
     * 3. Handle wrap-around (if key hash > max vnode hash, use first node)
     */
    std::shared_ptr<NodeInfo> GetNodeForKey(const std::string& key) {
        std::shared_lock<std::shared_mutex> lock(mutex_);

        if (state_.vnodes.empty()) {
            return nullptr;
        }

        uint64_t key_hash = Hash(key);

        // Binary search for first vnode with hash >= key_hash
        auto it = std::lower_bound(state_.vnodes.begin(), state_.vnodes.end(),
            VirtualNode{"", 0, key_hash},
            [](const VirtualNode& a, const VirtualNode& b) {
                return a.hash_value < b.hash_value;
            });

        // Wrap around if necessary
        if (it == state_.vnodes.end()) {
            it = state_.vnodes.begin();
        }

        auto node_it = state_.nodes.find(it->node_id);
        if (node_it != state_.nodes.end()) {
            return node_it->second;
        }
        return nullptr;
    }

    /**
     * Get multiple nodes for a key (for replication).
     *
     * TODO: Implement multi-node lookup:
     * 1. Find the primary node for the key
     * 2. Walk clockwise to find additional unique physical nodes
     * 3. Return up to 'count' unique physical nodes
     */
    std::vector<std::shared_ptr<NodeInfo>> GetNodesForKey(const std::string& key, int count) {
        std::shared_lock<std::shared_mutex> lock(mutex_);

        if (state_.vnodes.empty()) {
            return {};
        }

        uint64_t key_hash = Hash(key);
        auto it = std::lower_bound(state_.vnodes.begin(), state_.vnodes.end(),
            VirtualNode{"", 0, key_hash},
            [](const VirtualNode& a, const VirtualNode& b) {
                return a.hash_value < b.hash_value;
            });

        size_t start_idx = it == state_.vnodes.end() ? 0 : std::distance(state_.vnodes.begin(), it);

        std::vector<std::shared_ptr<NodeInfo>> result;
        std::unordered_set<std::string> seen_nodes;

        for (size_t i = 0; i < state_.vnodes.size() && result.size() < static_cast<size_t>(count); ++i) {
            const auto& vnode = state_.vnodes[(start_idx + i) % state_.vnodes.size()];
            if (seen_nodes.find(vnode.node_id) == seen_nodes.end()) {
                seen_nodes.insert(vnode.node_id);
                auto node_it = state_.nodes.find(vnode.node_id);
                if (node_it != state_.nodes.end()) {
                    result.push_back(node_it->second);
                }
            }
        }

        return result;
    }

    // =========================================================================
    // HashRingService RPC Implementations
    // =========================================================================

    Status AddNode(ServerContext* context, const chash::AddNodeRequest* request,
                   chash::AddNodeResponse* response) override {
        uint32_t num_vnodes = request->virtual_nodes();
        if (num_vnodes == 0) num_vnodes = DEFAULT_VIRTUAL_NODES;

        auto vnodes = AddNodeInternal(request->node_id(), request->address(), num_vnodes);

        response->set_success(true);
        for (const auto& v : vnodes) {
            auto* pb_vnode = response->add_added_vnodes();
            pb_vnode->set_node_id(v.node_id);
            pb_vnode->set_virtual_id(v.virtual_id);
            pb_vnode->set_hash_value(v.hash_value);
        }

        return Status::OK;
    }

    Status RemoveNode(ServerContext* context, const chash::RemoveNodeRequest* request,
                      chash::RemoveNodeResponse* response) override {
        bool success = RemoveNodeInternal(request->node_id());
        response->set_success(success);
        if (!success) {
            response->set_error("Node not found");
        }
        return Status::OK;
    }

    Status GetNode(ServerContext* context, const chash::GetNodeRequest* request,
                   chash::GetNodeResponse* response) override {
        auto node = GetNodeForKey(request->key());
        if (node) {
            response->set_node_id(node->node_id);
            response->set_node_address(node->address);
            response->set_key_hash(Hash(request->key()));
        }
        return Status::OK;
    }

    Status GetNodes(ServerContext* context, const chash::GetNodesRequest* request,
                    chash::GetNodesResponse* response) override {
        int count = request->count();
        if (count == 0) count = 3;

        auto nodes = GetNodesForKey(request->key(), count);
        for (const auto& n : nodes) {
            auto* pb_node = response->add_nodes();
            pb_node->set_node_id(n->node_id);
            pb_node->set_address(n->address);
            pb_node->set_virtual_nodes(n->virtual_nodes);
            pb_node->set_keys_count(n->keys_count);
            pb_node->set_is_healthy(n->is_healthy);
        }
        response->set_key_hash(Hash(request->key()));

        return Status::OK;
    }

    Status GetRingState(ServerContext* context, const chash::GetRingStateRequest* request,
                        chash::GetRingStateResponse* response) override {
        std::shared_lock<std::shared_mutex> lock(mutex_);

        uint64_t total_keys = 0;
        for (const auto& [id, node] : state_.nodes) {
            auto* pb_node = response->add_nodes();
            pb_node->set_node_id(node->node_id);
            pb_node->set_address(node->address);
            pb_node->set_virtual_nodes(node->virtual_nodes);
            pb_node->set_keys_count(node->keys_count);
            pb_node->set_is_healthy(node->is_healthy);
            total_keys += node->keys_count;
        }

        for (const auto& v : state_.vnodes) {
            auto* pb_vnode = response->add_vnodes();
            pb_vnode->set_node_id(v.node_id);
            pb_vnode->set_virtual_id(v.virtual_id);
            pb_vnode->set_hash_value(v.hash_value);
        }

        response->set_total_keys(total_keys);
        response->set_replication_factor(state_.replication_factor);

        return Status::OK;
    }

    Status Rebalance(ServerContext* context, const chash::RebalanceRequest* request,
                     chash::RebalanceResponse* response) override {
        // TODO: Implement rebalancing logic
        response->set_success(true);
        response->set_keys_moved(0);
        return Status::OK;
    }

    // =========================================================================
    // KeyValueService RPC Implementations
    // =========================================================================

    Status Get(ServerContext* context, const chash::GetRequest* request,
               chash::GetResponse* response) override {
        std::shared_lock<std::shared_mutex> lock(mutex_);
        auto it = kv_store_.find(request->key());
        if (it != kv_store_.end()) {
            response->set_value(it->second);
            response->set_found(true);
        } else {
            response->set_found(false);
        }
        response->set_served_by(node_id_);
        return Status::OK;
    }

    Status Put(ServerContext* context, const chash::PutRequest* request,
               chash::PutResponse* response) override {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        kv_store_[request->key()] = request->value();
        if (state_.nodes.find(node_id_) != state_.nodes.end()) {
            state_.nodes[node_id_]->keys_count = kv_store_.size();
        }
        response->set_success(true);
        response->set_stored_on(node_id_);
        return Status::OK;
    }

    Status Delete(ServerContext* context, const chash::DeleteRequest* request,
                  chash::DeleteResponse* response) override {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        if (kv_store_.erase(request->key()) > 0) {
            if (state_.nodes.find(node_id_) != state_.nodes.end()) {
                state_.nodes[node_id_]->keys_count = kv_store_.size();
            }
            response->set_success(true);
        } else {
            response->set_success(false);
            response->set_error("Key not found");
        }
        return Status::OK;
    }

    Status GetLeader(ServerContext* context, const chash::GetLeaderRequest* request,
                     chash::GetLeaderResponse* response) override {
        response->set_node_id(node_id_);
        response->set_node_address("localhost:" + std::to_string(port_));
        response->set_is_coordinator(true);
        return Status::OK;
    }

    Status GetClusterStatus(ServerContext* context, const chash::GetClusterStatusRequest* request,
                            chash::GetClusterStatusResponse* response) override {
        std::shared_lock<std::shared_mutex> lock(mutex_);

        response->set_node_id(node_id_);
        response->set_node_address("localhost:" + std::to_string(port_));
        response->set_is_coordinator(true);
        response->set_total_nodes(state_.nodes.size());

        uint64_t total_keys = 0;
        uint32_t healthy_nodes = 0;
        for (const auto& [id, node] : state_.nodes) {
            auto* pb_node = response->add_members();
            pb_node->set_node_id(node->node_id);
            pb_node->set_address(node->address);
            pb_node->set_virtual_nodes(node->virtual_nodes);
            pb_node->set_keys_count(node->keys_count);
            pb_node->set_is_healthy(node->is_healthy);
            total_keys += node->keys_count;
            if (node->is_healthy) ++healthy_nodes;
        }

        response->set_healthy_nodes(healthy_nodes);
        response->set_total_keys(total_keys);
        response->set_replication_factor(state_.replication_factor);
        response->set_virtual_nodes_per_node(state_.vnodes_per_node);

        return Status::OK;
    }

    // =========================================================================
    // NodeService RPC Implementations
    // =========================================================================

    Status TransferKeys(ServerContext* context, const chash::TransferKeysRequest* request,
                        chash::TransferKeysResponse* response) override {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        for (const auto& kv : request->keys()) {
            kv_store_[kv.key()] = kv.value();
        }
        if (state_.nodes.find(node_id_) != state_.nodes.end()) {
            state_.nodes[node_id_]->keys_count = kv_store_.size();
        }
        response->set_success(true);
        response->set_keys_received(request->keys_size());
        return Status::OK;
    }

    Status Heartbeat(ServerContext* context, const chash::HeartbeatRequest* request,
                     chash::HeartbeatResponse* response) override {
        response->set_acknowledged(true);
        response->set_timestamp(std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count());
        return Status::OK;
    }

    Status GetLocalKeys(ServerContext* context, const chash::GetLocalKeysRequest* request,
                        chash::GetLocalKeysResponse* response) override {
        std::shared_lock<std::shared_mutex> lock(mutex_);
        for (const auto& [k, v] : kv_store_) {
            auto* kv = response->add_keys();
            kv->set_key(k);
            kv->set_value(v);
            kv->set_hash(Hash(k));
        }
        response->set_total_count(kv_store_.size());
        return Status::OK;
    }

    Status StoreLocal(ServerContext* context, const chash::StoreLocalRequest* request,
                      chash::StoreLocalResponse* response) override {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        kv_store_[request->key()] = request->value();
        if (state_.nodes.find(node_id_) != state_.nodes.end()) {
            state_.nodes[node_id_]->keys_count = kv_store_.size();
        }
        response->set_success(true);
        return Status::OK;
    }

    Status DeleteLocal(ServerContext* context, const chash::DeleteLocalRequest* request,
                       chash::DeleteLocalResponse* response) override {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        if (kv_store_.erase(request->key()) > 0) {
            if (state_.nodes.find(node_id_) != state_.nodes.end()) {
                state_.nodes[node_id_]->keys_count = kv_store_.size();
            }
            response->set_success(true);
        } else {
            response->set_success(false);
            response->set_error("Key not found");
        }
        return Status::OK;
    }

private:
    std::string node_id_;
    int port_;
    std::vector<std::string> peers_;
    HashRingState state_;
    std::unordered_map<std::string, std::string> kv_store_;
    mutable std::shared_mutex mutex_;
    std::unordered_map<std::string, std::unique_ptr<chash::NodeService::Stub>> peer_stubs_;
};

// =============================================================================
// Main Entry Point
// =============================================================================

int main(int argc, char* argv[]) {
    std::string node_id;
    int port = 50051;
    std::string peers_str;

    for (int i = 1; i < argc; ++i) {
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
        std::cerr << "Usage: " << argv[0] << " --node-id <id> --port <port> --peers <peer1:port1,peer2:port2>" << std::endl;
        return 1;
    }

    // Parse peers
    std::vector<std::string> peers;
    std::stringstream ss(peers_str);
    std::string peer;
    while (std::getline(ss, peer, ',')) {
        // Trim whitespace
        peer.erase(0, peer.find_first_not_of(" \t"));
        peer.erase(peer.find_last_not_of(" \t") + 1);
        if (!peer.empty()) {
            peers.push_back(peer);
        }
    }

    ConsistentHashRing ring(node_id, port, peers);
    ring.Initialize();

    std::string server_address = "0.0.0.0:" + std::to_string(port);
    ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
    builder.RegisterService(static_cast<chash::HashRingService::Service*>(&ring));
    builder.RegisterService(static_cast<chash::KeyValueService::Service*>(&ring));
    builder.RegisterService(static_cast<chash::NodeService::Service*>(&ring));

    std::unique_ptr<Server> server(builder.BuildAndStart());
    std::cout << "Starting Consistent Hashing node " << node_id << " on " << server_address << std::endl;

    server->Wait();
    return 0;
}
