// Consistent Hashing Implementation - Go Template
//
// This template provides the basic structure for implementing a
// consistent hash ring for distributed key-value storage.
//
// Key concepts:
// 1. Hash Ring - Keys and nodes are mapped to a circular hash space
// 2. Virtual Nodes - Each physical node has multiple positions on the ring
// 3. Lookup - Find the first node clockwise from the key's hash position
// 4. Rebalancing - When nodes join/leave, only nearby keys need to move
//
// Usage:
//     go run server.go --node-id node1 --port 50051 --peers node2:50052,node3:50053

package main

import (
	"context"
	"crypto/md5"
	"encoding/binary"
	"flag"
	"fmt"
	"log"
	"net"
	"sort"
	"strings"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"

	pb "github.com/sdp/chash"
)

const (
	DefaultVirtualNodes     = 150
	DefaultReplicationFactor = 3
)

// VirtualNode represents a virtual node on the hash ring
type VirtualNode struct {
	NodeID    string
	VirtualID uint32
	HashValue uint64
}

// NodeInfo contains information about a physical node
type NodeInfo struct {
	NodeID        string
	Address       string
	VirtualNodes  uint32
	KeysCount     uint64
	IsHealthy     bool
	LastHeartbeat uint64
}

// HashRingState holds the state of the consistent hash ring
type HashRingState struct {
	Nodes             map[string]*NodeInfo
	VNodes            []VirtualNode
	ReplicationFactor uint32
	VNodesPerNode     uint32
}

// ConsistentHashRing implements the consistent hashing algorithm
type ConsistentHashRing struct {
	pb.UnimplementedHashRingServiceServer
	pb.UnimplementedKeyValueServiceServer
	pb.UnimplementedNodeServiceServer

	nodeID      string
	port        int
	peers       []string
	state       HashRingState
	mu          sync.RWMutex
	kvStore     map[string]string
	peerClients map[string]pb.NodeServiceClient
}

// NewConsistentHashRing creates a new hash ring node
func NewConsistentHashRing(nodeID string, port int, peers []string) *ConsistentHashRing {
	return &ConsistentHashRing{
		nodeID: nodeID,
		port:   port,
		peers:  peers,
		state: HashRingState{
			Nodes:             make(map[string]*NodeInfo),
			VNodes:            make([]VirtualNode, 0),
			ReplicationFactor: DefaultReplicationFactor,
			VNodesPerNode:     DefaultVirtualNodes,
		},
		kvStore:     make(map[string]string),
		peerClients: make(map[string]pb.NodeServiceClient),
	}
}

// Initialize sets up connections to peer nodes
func (r *ConsistentHashRing) Initialize() error {
	for _, peer := range r.peers {
		var conn *grpc.ClientConn
		var err error

		// Cloud Run URLs require TLS credentials
		if strings.Contains(peer, ".run.app") {
			creds := credentials.NewClientTLSFromCert(nil, "")
			conn, err = grpc.Dial(peer, grpc.WithTransportCredentials(creds))
			log.Printf("Using TLS for peer: %s", peer)
		} else {
			conn, err = grpc.Dial(peer, grpc.WithTransportCredentials(insecure.NewCredentials()))
			log.Printf("Using insecure channel for peer: %s", peer)
		}

		if err != nil {
			log.Printf("Warning: Failed to connect to peer %s: %v", peer, err)
			continue
		}
		r.peerClients[peer] = pb.NewNodeServiceClient(conn)
	}

	// Add self to the ring
	selfAddr := fmt.Sprintf("localhost:%d", r.port)
	r.AddNodeInternal(r.nodeID, selfAddr, DefaultVirtualNodes)

	log.Printf("Node %s initialized with peers: %v", r.nodeID, r.peers)
	return nil
}

// Hash computes the hash value for a key
//
// TODO: Implement consistent hashing function:
// - Use a good hash function (MD5, SHA-1, etc.)
// - Return a value in the ring's hash space
// - Must be deterministic (same key always hashes to same position)
func (r *ConsistentHashRing) Hash(key string) uint64 {
	h := md5.Sum([]byte(key))
	return binary.BigEndian.Uint64(h[:8])
}

func (r *ConsistentHashRing) getVNodeHash(nodeID string, virtualID uint32) uint64 {
	key := fmt.Sprintf("%s:%d", nodeID, virtualID)
	return r.Hash(key)
}

// AddNodeInternal adds a node to the hash ring
//
// TODO: Implement node addition:
// 1. Create virtual nodes for this physical node
// 2. Insert virtual nodes into the ring (maintain sorted order)
// 3. Return list of added virtual nodes
func (r *ConsistentHashRing) AddNodeInternal(nodeID, address string, numVNodes uint32) []VirtualNode {
	r.mu.Lock()
	defer r.mu.Unlock()

	// Check if node already exists
	if _, exists := r.state.Nodes[nodeID]; exists {
		return nil
	}

	// Create node info
	r.state.Nodes[nodeID] = &NodeInfo{
		NodeID:       nodeID,
		Address:      address,
		VirtualNodes: numVNodes,
		IsHealthy:    true,
	}

	// Create virtual nodes
	addedVNodes := make([]VirtualNode, 0, numVNodes)
	for i := uint32(0); i < numVNodes; i++ {
		vnode := VirtualNode{
			NodeID:    nodeID,
			VirtualID: i,
			HashValue: r.getVNodeHash(nodeID, i),
		}
		addedVNodes = append(addedVNodes, vnode)
		r.state.VNodes = append(r.state.VNodes, vnode)
	}

	// Sort virtual nodes by hash value
	sort.Slice(r.state.VNodes, func(i, j int) bool {
		return r.state.VNodes[i].HashValue < r.state.VNodes[j].HashValue
	})

	log.Printf("Added node %s with %d virtual nodes", nodeID, numVNodes)
	return addedVNodes
}

// RemoveNodeInternal removes a node from the hash ring
//
// TODO: Implement node removal:
// 1. Remove all virtual nodes for this physical node
// 2. Update the ring structure
// 3. Return True if successful
func (r *ConsistentHashRing) RemoveNodeInternal(nodeID string) bool {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.state.Nodes[nodeID]; !exists {
		return false
	}

	// Remove virtual nodes
	newVNodes := make([]VirtualNode, 0, len(r.state.VNodes))
	for _, vnode := range r.state.VNodes {
		if vnode.NodeID != nodeID {
			newVNodes = append(newVNodes, vnode)
		}
	}
	r.state.VNodes = newVNodes
	delete(r.state.Nodes, nodeID)

	log.Printf("Removed node %s", nodeID)
	return true
}

// GetNodeForKey returns the node responsible for a key
//
// TODO: Implement key lookup:
// 1. Hash the key to find its position on the ring
// 2. Find the first node clockwise from that position
// 3. Handle wrap-around (if key hash > max vnode hash, use first node)
func (r *ConsistentHashRing) GetNodeForKey(key string) *NodeInfo {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if len(r.state.VNodes) == 0 {
		return nil
	}

	keyHash := r.Hash(key)

	// Binary search to find first vnode with hash >= keyHash
	idx := sort.Search(len(r.state.VNodes), func(i int) bool {
		return r.state.VNodes[i].HashValue >= keyHash
	})

	// Wrap around if necessary
	if idx >= len(r.state.VNodes) {
		idx = 0
	}

	vnode := r.state.VNodes[idx]
	return r.state.Nodes[vnode.NodeID]
}

// GetNodesForKey returns multiple nodes for a key (for replication)
//
// TODO: Implement multi-node lookup:
// 1. Find the primary node for the key
// 2. Walk clockwise to find additional unique physical nodes
// 3. Return up to 'count' unique physical nodes
func (r *ConsistentHashRing) GetNodesForKey(key string, count int) []*NodeInfo {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if len(r.state.VNodes) == 0 {
		return nil
	}

	keyHash := r.Hash(key)
	idx := sort.Search(len(r.state.VNodes), func(i int) bool {
		return r.state.VNodes[i].HashValue >= keyHash
	})

	result := make([]*NodeInfo, 0, count)
	seenNodes := make(map[string]bool)

	ringSize := len(r.state.VNodes)
	for i := 0; i < ringSize && len(result) < count; i++ {
		vnode := r.state.VNodes[(idx+i)%ringSize]
		if !seenNodes[vnode.NodeID] {
			seenNodes[vnode.NodeID] = true
			if node, exists := r.state.Nodes[vnode.NodeID]; exists {
				result = append(result, node)
			}
		}
	}

	return result
}

// =============================================================================
// HashRingService RPC Implementations
// =============================================================================

func (r *ConsistentHashRing) AddNode(ctx context.Context, req *pb.AddNodeRequest) (*pb.AddNodeResponse, error) {
	numVNodes := req.VirtualNodes
	if numVNodes == 0 {
		numVNodes = DefaultVirtualNodes
	}
	vnodes := r.AddNodeInternal(req.NodeId, req.Address, numVNodes)

	pbVNodes := make([]*pb.VirtualNode, len(vnodes))
	for i, v := range vnodes {
		pbVNodes[i] = &pb.VirtualNode{
			NodeId:    v.NodeID,
			VirtualId: v.VirtualID,
			HashValue: v.HashValue,
		}
	}

	return &pb.AddNodeResponse{
		Success:     true,
		AddedVnodes: pbVNodes,
	}, nil
}

func (r *ConsistentHashRing) RemoveNode(ctx context.Context, req *pb.RemoveNodeRequest) (*pb.RemoveNodeResponse, error) {
	success := r.RemoveNodeInternal(req.NodeId)
	errMsg := ""
	if !success {
		errMsg = "Node not found"
	}
	return &pb.RemoveNodeResponse{
		Success: success,
		Error:   errMsg,
	}, nil
}

func (r *ConsistentHashRing) GetNode(ctx context.Context, req *pb.GetNodeRequest) (*pb.GetNodeResponse, error) {
	node := r.GetNodeForKey(req.Key)
	if node == nil {
		return &pb.GetNodeResponse{}, nil
	}
	return &pb.GetNodeResponse{
		NodeId:      node.NodeID,
		NodeAddress: node.Address,
		KeyHash:     r.Hash(req.Key),
	}, nil
}

func (r *ConsistentHashRing) GetNodes(ctx context.Context, req *pb.GetNodesRequest) (*pb.GetNodesResponse, error) {
	count := int(req.Count)
	if count == 0 {
		count = 3
	}
	nodes := r.GetNodesForKey(req.Key, count)

	pbNodes := make([]*pb.NodeInfo, len(nodes))
	for i, n := range nodes {
		pbNodes[i] = &pb.NodeInfo{
			NodeId:       n.NodeID,
			Address:      n.Address,
			VirtualNodes: n.VirtualNodes,
			KeysCount:    n.KeysCount,
			IsHealthy:    n.IsHealthy,
		}
	}

	return &pb.GetNodesResponse{
		Nodes:   pbNodes,
		KeyHash: r.Hash(req.Key),
	}, nil
}

func (r *ConsistentHashRing) GetRingState(ctx context.Context, req *pb.GetRingStateRequest) (*pb.GetRingStateResponse, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	pbNodes := make([]*pb.NodeInfo, 0, len(r.state.Nodes))
	var totalKeys uint64
	for _, n := range r.state.Nodes {
		pbNodes = append(pbNodes, &pb.NodeInfo{
			NodeId:       n.NodeID,
			Address:      n.Address,
			VirtualNodes: n.VirtualNodes,
			KeysCount:    n.KeysCount,
			IsHealthy:    n.IsHealthy,
		})
		totalKeys += n.KeysCount
	}

	pbVNodes := make([]*pb.VirtualNode, len(r.state.VNodes))
	for i, v := range r.state.VNodes {
		pbVNodes[i] = &pb.VirtualNode{
			NodeId:    v.NodeID,
			VirtualId: v.VirtualID,
			HashValue: v.HashValue,
		}
	}

	return &pb.GetRingStateResponse{
		Nodes:             pbNodes,
		Vnodes:            pbVNodes,
		TotalKeys:         totalKeys,
		ReplicationFactor: r.state.ReplicationFactor,
	}, nil
}

func (r *ConsistentHashRing) Rebalance(ctx context.Context, req *pb.RebalanceRequest) (*pb.RebalanceResponse, error) {
	// TODO: Implement rebalancing logic
	return &pb.RebalanceResponse{
		Success:   true,
		KeysMoved: 0,
	}, nil
}

// =============================================================================
// KeyValueService RPC Implementations
// =============================================================================

func (r *ConsistentHashRing) Get(ctx context.Context, req *pb.GetRequest) (*pb.GetResponse, error) {
	r.mu.RLock()
	value, found := r.kvStore[req.Key]
	r.mu.RUnlock()

	return &pb.GetResponse{
		Value:    value,
		Found:    found,
		ServedBy: r.nodeID,
	}, nil
}

func (r *ConsistentHashRing) Put(ctx context.Context, req *pb.PutRequest) (*pb.PutResponse, error) {
	r.mu.Lock()
	r.kvStore[req.Key] = req.Value
	r.state.Nodes[r.nodeID].KeysCount = uint64(len(r.kvStore))
	r.mu.Unlock()

	return &pb.PutResponse{
		Success:  true,
		StoredOn: r.nodeID,
	}, nil
}

func (r *ConsistentHashRing) Delete(ctx context.Context, req *pb.DeleteRequest) (*pb.DeleteResponse, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.kvStore[req.Key]; exists {
		delete(r.kvStore, req.Key)
		r.state.Nodes[r.nodeID].KeysCount = uint64(len(r.kvStore))
		return &pb.DeleteResponse{Success: true}, nil
	}
	return &pb.DeleteResponse{
		Success: false,
		Error:   "Key not found",
	}, nil
}

func (r *ConsistentHashRing) GetLeader(ctx context.Context, req *pb.GetLeaderRequest) (*pb.GetLeaderResponse, error) {
	return &pb.GetLeaderResponse{
		NodeId:        r.nodeID,
		NodeAddress:   fmt.Sprintf("localhost:%d", r.port),
		IsCoordinator: true,
	}, nil
}

func (r *ConsistentHashRing) GetClusterStatus(ctx context.Context, req *pb.GetClusterStatusRequest) (*pb.GetClusterStatusResponse, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	pbNodes := make([]*pb.NodeInfo, 0, len(r.state.Nodes))
	var totalKeys uint64
	var healthyNodes uint32
	for _, n := range r.state.Nodes {
		pbNodes = append(pbNodes, &pb.NodeInfo{
			NodeId:       n.NodeID,
			Address:      n.Address,
			VirtualNodes: n.VirtualNodes,
			KeysCount:    n.KeysCount,
			IsHealthy:    n.IsHealthy,
		})
		totalKeys += n.KeysCount
		if n.IsHealthy {
			healthyNodes++
		}
	}

	return &pb.GetClusterStatusResponse{
		NodeId:              r.nodeID,
		NodeAddress:         fmt.Sprintf("localhost:%d", r.port),
		IsCoordinator:       true,
		TotalNodes:          uint32(len(r.state.Nodes)),
		HealthyNodes:        healthyNodes,
		TotalKeys:           totalKeys,
		ReplicationFactor:   r.state.ReplicationFactor,
		VirtualNodesPerNode: r.state.VNodesPerNode,
		Members:             pbNodes,
	}, nil
}

// =============================================================================
// NodeService RPC Implementations
// =============================================================================

func (r *ConsistentHashRing) TransferKeys(ctx context.Context, req *pb.TransferKeysRequest) (*pb.TransferKeysResponse, error) {
	r.mu.Lock()
	for _, kv := range req.Keys {
		r.kvStore[kv.Key] = kv.Value
	}
	r.state.Nodes[r.nodeID].KeysCount = uint64(len(r.kvStore))
	r.mu.Unlock()

	return &pb.TransferKeysResponse{
		Success:      true,
		KeysReceived: uint64(len(req.Keys)),
	}, nil
}

func (r *ConsistentHashRing) Heartbeat(ctx context.Context, req *pb.HeartbeatRequest) (*pb.HeartbeatResponse, error) {
	return &pb.HeartbeatResponse{
		Acknowledged: true,
		Timestamp:    uint64(time.Now().UnixMilli()),
	}, nil
}

func (r *ConsistentHashRing) GetLocalKeys(ctx context.Context, req *pb.GetLocalKeysRequest) (*pb.GetLocalKeysResponse, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	keys := make([]*pb.KeyValuePair, 0, len(r.kvStore))
	for k, v := range r.kvStore {
		keys = append(keys, &pb.KeyValuePair{
			Key:   k,
			Value: v,
			Hash:  r.Hash(k),
		})
	}

	return &pb.GetLocalKeysResponse{
		Keys:       keys,
		TotalCount: uint64(len(keys)),
	}, nil
}

func (r *ConsistentHashRing) StoreLocal(ctx context.Context, req *pb.StoreLocalRequest) (*pb.StoreLocalResponse, error) {
	r.mu.Lock()
	r.kvStore[req.Key] = req.Value
	r.state.Nodes[r.nodeID].KeysCount = uint64(len(r.kvStore))
	r.mu.Unlock()

	return &pb.StoreLocalResponse{Success: true}, nil
}

func (r *ConsistentHashRing) DeleteLocal(ctx context.Context, req *pb.DeleteLocalRequest) (*pb.DeleteLocalResponse, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.kvStore[req.Key]; exists {
		delete(r.kvStore, req.Key)
		r.state.Nodes[r.nodeID].KeysCount = uint64(len(r.kvStore))
		return &pb.DeleteLocalResponse{Success: true}, nil
	}
	return &pb.DeleteLocalResponse{
		Success: false,
		Error:   "Key not found",
	}, nil
}

// =============================================================================
// Main Entry Point
// =============================================================================

func main() {
	nodeID := flag.String("node-id", "", "Unique node identifier")
	port := flag.Int("port", 50051, "Port to listen on")
	peersStr := flag.String("peers", "", "Comma-separated list of peer addresses")
	flag.Parse()

	if *nodeID == "" {
		log.Fatal("--node-id is required")
	}
	if *peersStr == "" {
		log.Fatal("--peers is required")
	}

	peers := strings.Split(*peersStr, ",")
	for i, p := range peers {
		peers[i] = strings.TrimSpace(p)
	}

	ring := NewConsistentHashRing(*nodeID, *port, peers)
	if err := ring.Initialize(); err != nil {
		log.Fatalf("Failed to initialize node: %v", err)
	}

	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	server := grpc.NewServer()
	pb.RegisterHashRingServiceServer(server, ring)
	pb.RegisterKeyValueServiceServer(server, ring)
	pb.RegisterNodeServiceServer(server, ring)

	log.Printf("Starting Consistent Hashing node %s on port %d", *nodeID, *port)

	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
