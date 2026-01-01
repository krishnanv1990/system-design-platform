/*
Rendezvous Hashing (Highest Random Weight) Implementation in Go

Rendezvous hashing provides deterministic key-to-node mapping where each key
is assigned to the node with the highest computed weight. This approach offers
minimal disruption when nodes are added or removed.

Key concepts:
1. Weight function: Computes a pseudo-random weight for each (key, node) pair
2. Selection: Choose the node with maximum weight for each key
3. Replication: Use top-N nodes for replica placement

Your task: Implement the weight calculation and node selection algorithms.
*/

package main

import (
	"context"
	"crypto/md5"
	"crypto/tls"
	"encoding/binary"
	"fmt"
	"log"
	"net"
	"os"
	"sort"
	"sync"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/status"

	pb "rendezvous_hashing"
)

// RendezvousHashingNode implements the rendezvous hashing algorithm
type RendezvousHashingNode struct {
	pb.UnimplementedNodeRegistryServiceServer
	pb.UnimplementedRendezvousServiceServer
	pb.UnimplementedKeyValueServiceServer

	nodeID     string
	nodes      map[string]*pb.NodeInfo
	localStore map[string][]byte
	mu         sync.RWMutex
}

// NewRendezvousHashingNode creates a new rendezvous hashing node
func NewRendezvousHashingNode(nodeID string) *RendezvousHashingNode {
	return &RendezvousHashingNode{
		nodeID:     nodeID,
		nodes:      make(map[string]*pb.NodeInfo),
		localStore: make(map[string][]byte),
	}
}

// calculateWeight computes the weight for a key-node pair
//
// The weight should be deterministic and uniformly distributed.
// Common approach: hash(key + nodeID) converted to a float64.
//
// Args:
//
//	key: The key to calculate weight for
//	nodeID: The node identifier
//	capacityWeight: Multiplier for node capacity (default 1.0)
//
// Returns:
//
//	A floating point weight value
//
// TODO: Implement the weight calculation
func (n *RendezvousHashingNode) calculateWeight(key, nodeID string, capacityWeight float64) float64 {
	// TODO: Implement weight calculation
	// 1. Concatenate key and nodeID
	// 2. Hash the concatenated string (use MD5 or SHA256)
	// 3. Convert hash bytes to a floating point number in range [0, 1)
	// 4. Multiply by capacityWeight
	//
	// Hint: Use md5.Sum() and binary.BigEndian.Uint64() to convert bytes to uint64,
	// then divide by math.MaxUint64 to get a float in [0, 1)
	return 0.0
}

// getNodeForKey returns the node with the highest weight for a key
//
// TODO: Implement rendezvous hashing node selection
func (n *RendezvousHashingNode) getNodeForKey(key string) (string, float64) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	if len(n.nodes) == 0 {
		return "", 0.0
	}

	// TODO: Implement rendezvous hashing
	// 1. For each active node, calculate weight(key, nodeID)
	// 2. Return the node with the highest weight
	return "", 0.0
}

// getNodesForKey returns the top N nodes for a key (for replication)
//
// TODO: Implement multi-node selection
func (n *RendezvousHashingNode) getNodesForKey(key string, count int) []struct {
	nodeID string
	weight float64
} {
	n.mu.RLock()
	defer n.mu.RUnlock()

	if len(n.nodes) == 0 {
		return nil
	}

	// TODO: Implement top-N node selection
	// 1. Calculate weights for all active nodes
	// 2. Sort by weight descending
	// 3. Return top 'count' nodes
	return nil
}

// NodeRegistryService implementation

func (n *RendezvousHashingNode) AddNode(ctx context.Context, req *pb.AddNodeRequest) (*pb.AddNodeResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	capacityWeight := req.CapacityWeight
	if capacityWeight <= 0 {
		capacityWeight = 1.0
	}

	n.nodes[req.NodeId] = &pb.NodeInfo{
		NodeId:         req.NodeId,
		Address:        req.Address,
		Port:           req.Port,
		CapacityWeight: capacityWeight,
		IsActive:       true,
	}

	return &pb.AddNodeResponse{
		Success: true,
		Message: fmt.Sprintf("Node %s added successfully", req.NodeId),
	}, nil
}

func (n *RendezvousHashingNode) RemoveNode(ctx context.Context, req *pb.RemoveNodeRequest) (*pb.RemoveNodeResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	if _, exists := n.nodes[req.NodeId]; exists {
		delete(n.nodes, req.NodeId)
		return &pb.RemoveNodeResponse{
			Success: true,
			Message: fmt.Sprintf("Node %s removed", req.NodeId),
		}, nil
	}

	return &pb.RemoveNodeResponse{
		Success: false,
		Message: fmt.Sprintf("Node %s not found", req.NodeId),
	}, nil
}

func (n *RendezvousHashingNode) ListNodes(ctx context.Context, req *pb.ListNodesRequest) (*pb.ListNodesResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	nodes := make([]*pb.NodeInfo, 0, len(n.nodes))
	for _, node := range n.nodes {
		nodes = append(nodes, node)
	}

	return &pb.ListNodesResponse{Nodes: nodes}, nil
}

func (n *RendezvousHashingNode) GetNodeInfo(ctx context.Context, req *pb.GetNodeInfoRequest) (*pb.GetNodeInfoResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	if node, exists := n.nodes[req.NodeId]; exists {
		return &pb.GetNodeInfoResponse{Node: node, Found: true}, nil
	}

	return &pb.GetNodeInfoResponse{Found: false}, nil
}

// RendezvousService implementation

func (n *RendezvousHashingNode) GetNodeForKey(ctx context.Context, req *pb.GetNodeForKeyRequest) (*pb.GetNodeForKeyResponse, error) {
	nodeID, weight := n.getNodeForKey(req.Key)
	if nodeID == "" {
		return nil, status.Error(codes.NotFound, "No nodes available")
	}

	return &pb.GetNodeForKeyResponse{
		NodeId: nodeID,
		Weight: weight,
	}, nil
}

func (n *RendezvousHashingNode) GetNodesForKey(ctx context.Context, req *pb.GetNodesForKeyRequest) (*pb.GetNodesForKeyResponse, error) {
	nodes := n.getNodesForKey(req.Key, int(req.Count))

	result := make([]*pb.NodeWithWeight, len(nodes))
	for i, node := range nodes {
		result[i] = &pb.NodeWithWeight{
			NodeId: node.nodeID,
			Weight: node.weight,
		}
	}

	return &pb.GetNodesForKeyResponse{Nodes: result}, nil
}

func (n *RendezvousHashingNode) CalculateWeight(ctx context.Context, req *pb.CalculateWeightRequest) (*pb.CalculateWeightResponse, error) {
	n.mu.RLock()
	capacity := 1.0
	if node, exists := n.nodes[req.NodeId]; exists {
		capacity = node.CapacityWeight
	}
	n.mu.RUnlock()

	weight := n.calculateWeight(req.Key, req.NodeId, capacity)
	return &pb.CalculateWeightResponse{Weight: weight}, nil
}

// KeyValueService implementation

func (n *RendezvousHashingNode) Put(ctx context.Context, req *pb.PutRequest) (*pb.PutResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	n.localStore[req.Key] = req.Value
	return &pb.PutResponse{
		Success:       true,
		StoredOnNodes: []string{n.nodeID},
	}, nil
}

func (n *RendezvousHashingNode) Get(ctx context.Context, req *pb.GetRequest) (*pb.GetResponse, error) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	if value, exists := n.localStore[req.Key]; exists {
		return &pb.GetResponse{
			Found:        true,
			Value:        value,
			ServedByNode: n.nodeID,
		}, nil
	}

	return &pb.GetResponse{Found: false}, nil
}

func (n *RendezvousHashingNode) Delete(ctx context.Context, req *pb.DeleteRequest) (*pb.DeleteResponse, error) {
	n.mu.Lock()
	defer n.mu.Unlock()

	if _, exists := n.localStore[req.Key]; exists {
		delete(n.localStore, req.Key)
		return &pb.DeleteResponse{Success: true, DeletedFromNodes: 1}, nil
	}

	return &pb.DeleteResponse{Success: true, DeletedFromNodes: 0}, nil
}

func main() {
	nodeID := os.Getenv("NODE_ID")
	if nodeID == "" {
		nodeID = "node-0"
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "50051"
	}

	useTLS := os.Getenv("USE_TLS") == "true"

	lis, err := net.Listen("tcp", fmt.Sprintf(":%s", port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	var opts []grpc.ServerOption

	if useTLS {
		certPath := os.Getenv("TLS_CERT_PATH")
		if certPath == "" {
			certPath = "/certs/server.crt"
		}
		keyPath := os.Getenv("TLS_KEY_PATH")
		if keyPath == "" {
			keyPath = "/certs/server.key"
		}

		cert, err := tls.LoadX509KeyPair(certPath, keyPath)
		if err != nil {
			log.Fatalf("Failed to load TLS credentials: %v", err)
		}

		creds := credentials.NewTLS(&tls.Config{
			Certificates: []tls.Certificate{cert},
			ClientAuth:   tls.NoClientCert,
		})
		opts = append(opts, grpc.Creds(creds))
		log.Printf("Rendezvous Hashing node %s starting with TLS on port %s", nodeID, port)
	} else {
		log.Printf("Rendezvous Hashing node %s starting on port %s", nodeID, port)
	}

	server := grpc.NewServer(opts...)
	node := NewRendezvousHashingNode(nodeID)

	pb.RegisterNodeRegistryServiceServer(server, node)
	pb.RegisterRendezvousServiceServer(server, node)
	pb.RegisterKeyValueServiceServer(server, node)

	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
