/*
 * Rendezvous Hashing (Highest Random Weight) Implementation in C++
 *
 * Rendezvous hashing (also called HRW - Highest Random Weight) is a distributed
 * hashing algorithm that maps keys to nodes by computing a weight for each
 * key-node pair and selecting the node with maximum weight.
 *
 * Advantages over consistent hashing:
 * - Simpler implementation (no ring structure or virtual nodes)
 * - Equal distribution without configuration
 * - Easy to extend for weighted nodes
 *
 * Your task: Implement the weight calculation and node selection algorithms.
 */

#include <grpcpp/grpcpp.h>
#include <grpcpp/security/server_credentials.h>

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <mutex>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

// OpenSSL for MD5 hashing
#include <openssl/md5.h>

#include "rendezvous_hashing.grpc.pb.h"
#include "rendezvous_hashing.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;
using grpc::StatusCode;

using namespace rendezvous_hashing;

class RendezvousHashingNode final : public NodeRegistryService::Service,
                                     public RendezvousService::Service,
                                     public KeyValueService::Service {
public:
    explicit RendezvousHashingNode(const std::string& node_id)
        : node_id_(node_id) {}

    /**
     * Calculate the weight for a key-node pair.
     *
     * The weight should be deterministic and uniformly distributed.
     * Common approach: hash(key + node_id) converted to a double.
     *
     * @param key The key to calculate weight for
     * @param node_id The node identifier
     * @param capacity_weight Multiplier for node capacity (default 1.0)
     * @return A floating point weight value
     *
     * TODO: Implement the weight calculation
     * Hint: Use MD5 to hash key + node_id, convert first 8 bytes to uint64_t,
     *       normalize to [0, 1), multiply by capacity_weight
     */
    double calculateWeight(const std::string& key, const std::string& node_id,
                          double capacity_weight = 1.0) {
        // TODO: Implement weight calculation
        // 1. Concatenate key and node_id
        // 2. Hash the concatenated string using MD5
        // 3. Convert hash bytes to a double in range [0, 1)
        // 4. Multiply by capacity_weight
        return 0.0;
    }

    /**
     * Get the node with the highest weight for a given key.
     *
     * @param key The key to look up
     * @param out_weight Output parameter for the weight
     * @return Node ID with highest weight, or empty string if no nodes
     *
     * TODO: Implement rendezvous hashing node selection
     */
    std::string getNodeForKey(const std::string& key, double& out_weight) {
        std::lock_guard<std::mutex> lock(mutex_);

        if (nodes_.empty()) {
            out_weight = 0.0;
            return "";
        }

        // TODO: Implement rendezvous hashing
        // 1. For each active node, calculate weight(key, node_id)
        // 2. Return the node with the highest weight
        out_weight = 0.0;
        return "";
    }

    /**
     * Get the top N nodes for a key (useful for replication).
     *
     * @param key The key to look up
     * @param count Number of nodes to return
     * @return Vector of (node_id, weight) pairs, sorted by weight descending
     *
     * TODO: Implement multi-node selection
     */
    std::vector<std::pair<std::string, double>> getNodesForKey(
            const std::string& key, int count) {
        std::lock_guard<std::mutex> lock(mutex_);

        if (nodes_.empty()) {
            return {};
        }

        // TODO: Implement top-N node selection
        // 1. Calculate weights for all active nodes
        // 2. Sort by weight descending
        // 3. Return top 'count' nodes
        return {};
    }

    // NodeRegistryService implementation
    Status AddNode(ServerContext* context, const AddNodeRequest* request,
                   AddNodeResponse* response) override {
        std::lock_guard<std::mutex> lock(mutex_);

        NodeInfo node_info;
        node_info.set_node_id(request->node_id());
        node_info.set_address(request->address());
        node_info.set_port(request->port());
        node_info.set_capacity_weight(
            request->capacity_weight() > 0 ? request->capacity_weight() : 1.0);
        node_info.set_is_active(true);

        nodes_[request->node_id()] = node_info;

        response->set_success(true);
        response->set_message("Node " + request->node_id() + " added successfully");
        return Status::OK;
    }

    Status RemoveNode(ServerContext* context, const RemoveNodeRequest* request,
                      RemoveNodeResponse* response) override {
        std::lock_guard<std::mutex> lock(mutex_);

        auto it = nodes_.find(request->node_id());
        if (it != nodes_.end()) {
            nodes_.erase(it);
            response->set_success(true);
            response->set_message("Node " + request->node_id() + " removed");
        } else {
            response->set_success(false);
            response->set_message("Node " + request->node_id() + " not found");
        }
        return Status::OK;
    }

    Status ListNodes(ServerContext* context, const ListNodesRequest* request,
                     ListNodesResponse* response) override {
        std::lock_guard<std::mutex> lock(mutex_);

        for (const auto& [id, node] : nodes_) {
            *response->add_nodes() = node;
        }
        return Status::OK;
    }

    Status GetNodeInfo(ServerContext* context, const GetNodeInfoRequest* request,
                       GetNodeInfoResponse* response) override {
        std::lock_guard<std::mutex> lock(mutex_);

        auto it = nodes_.find(request->node_id());
        if (it != nodes_.end()) {
            *response->mutable_node() = it->second;
            response->set_found(true);
        } else {
            response->set_found(false);
        }
        return Status::OK;
    }

    // RendezvousService implementation
    Status GetNodeForKey(ServerContext* context,
                         const GetNodeForKeyRequest* request,
                         GetNodeForKeyResponse* response) override {
        double weight;
        std::string node_id = getNodeForKey(request->key(), weight);

        if (node_id.empty()) {
            return Status(StatusCode::NOT_FOUND, "No nodes available");
        }

        response->set_node_id(node_id);
        response->set_weight(weight);
        return Status::OK;
    }

    Status GetNodesForKey(ServerContext* context,
                          const GetNodesForKeyRequest* request,
                          GetNodesForKeyResponse* response) override {
        auto nodes = getNodesForKey(request->key(), request->count());

        for (const auto& [id, weight] : nodes) {
            auto* node = response->add_nodes();
            node->set_node_id(id);
            node->set_weight(weight);
        }
        return Status::OK;
    }

    Status CalculateWeight(ServerContext* context,
                           const CalculateWeightRequest* request,
                           CalculateWeightResponse* response) override {
        double capacity = 1.0;
        {
            std::lock_guard<std::mutex> lock(mutex_);
            auto it = nodes_.find(request->node_id());
            if (it != nodes_.end()) {
                capacity = it->second.capacity_weight();
            }
        }

        double weight = calculateWeight(request->key(), request->node_id(), capacity);
        response->set_weight(weight);
        return Status::OK;
    }

    // KeyValueService implementation
    Status Put(ServerContext* context, const PutRequest* request,
               PutResponse* response) override {
        std::lock_guard<std::mutex> lock(mutex_);

        local_store_[request->key()] = request->value();
        response->set_success(true);
        response->add_stored_on_nodes(node_id_);
        return Status::OK;
    }

    Status Get(ServerContext* context, const GetRequest* request,
               GetResponse* response) override {
        std::lock_guard<std::mutex> lock(mutex_);

        auto it = local_store_.find(request->key());
        if (it != local_store_.end()) {
            response->set_found(true);
            response->set_value(it->second);
            response->set_served_by_node(node_id_);
        } else {
            response->set_found(false);
        }
        return Status::OK;
    }

    Status Delete(ServerContext* context, const DeleteRequest* request,
                  DeleteResponse* response) override {
        std::lock_guard<std::mutex> lock(mutex_);

        auto it = local_store_.find(request->key());
        if (it != local_store_.end()) {
            local_store_.erase(it);
            response->set_success(true);
            response->set_deleted_from_nodes(1);
        } else {
            response->set_success(true);
            response->set_deleted_from_nodes(0);
        }
        return Status::OK;
    }

private:
    std::string node_id_;
    std::unordered_map<std::string, NodeInfo> nodes_;
    std::unordered_map<std::string, std::string> local_store_;
    std::mutex mutex_;
};

std::string readFile(const std::string& path) {
    std::ifstream file(path);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open file: " + path);
    }
    std::stringstream buffer;
    buffer << file.rdbuf();
    return buffer.str();
}

int main() {
    std::string node_id = "node-0";
    if (const char* env_node_id = std::getenv("NODE_ID")) {
        node_id = env_node_id;
    }

    std::string port = "50051";
    if (const char* env_port = std::getenv("PORT")) {
        port = env_port;
    }

    bool use_tls = false;
    if (const char* env_tls = std::getenv("USE_TLS")) {
        use_tls = std::string(env_tls) == "true";
    }

    std::string server_address = "0.0.0.0:" + port;

    RendezvousHashingNode service(node_id);

    ServerBuilder builder;

    if (use_tls) {
        std::string cert_path = "/certs/server.crt";
        std::string key_path = "/certs/server.key";

        if (const char* env_cert = std::getenv("TLS_CERT_PATH")) {
            cert_path = env_cert;
        }
        if (const char* env_key = std::getenv("TLS_KEY_PATH")) {
            key_path = env_key;
        }

        std::string server_cert = readFile(cert_path);
        std::string server_key = readFile(key_path);

        grpc::SslServerCredentialsOptions ssl_opts;
        ssl_opts.pem_key_cert_pairs.push_back({server_key, server_cert});

        builder.AddListeningPort(server_address,
                                 grpc::SslServerCredentials(ssl_opts));
        std::cout << "Rendezvous Hashing node " << node_id
                  << " starting with TLS on port " << port << std::endl;
    } else {
        builder.AddListeningPort(server_address,
                                 grpc::InsecureServerCredentials());
        std::cout << "Rendezvous Hashing node " << node_id
                  << " starting on port " << port << std::endl;
    }

    builder.RegisterService(static_cast<NodeRegistryService::Service*>(&service));
    builder.RegisterService(static_cast<RendezvousService::Service*>(&service));
    builder.RegisterService(static_cast<KeyValueService::Service*>(&service));

    std::unique_ptr<Server> server(builder.BuildAndStart());
    server->Wait();

    return 0;
}
