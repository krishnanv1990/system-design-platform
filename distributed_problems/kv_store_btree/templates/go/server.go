// B+ Tree KV Store - Go Template
//
// This template provides the basic structure for implementing a distributed
// key-value store using B+ Tree storage.
//
// Key concepts:
// 1. B+ Tree - Balanced tree with all values in leaf nodes
// 2. Pages - Fixed-size disk blocks for storage
// 3. Buffer Pool - In-memory page cache
// 4. WAL - Write-Ahead Logging for transactions
//
// Usage:
//     go run server.go --node-id node1 --port 50051 --peers node2:50052,node3:50053

package main

import (
	"context"
	"encoding/binary"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	pb "github.com/sdp/kv_store_btree"
)

const (
	PageSize      = 4096
	MaxKeys       = 100  // Max keys per node
	MinKeys       = MaxKeys / 2
	BufferPoolCap = 1000
)

// BPlusTreeNode represents a node in the B+ tree
type BPlusTreeNode struct {
	PageID   uint32
	IsLeaf   bool
	Keys     []string
	Values   []string   // Only for leaf nodes
	Children []uint32   // Only for internal nodes
	Next     uint32     // Only for leaf nodes - sibling pointer
	Dirty    bool
}

// NewLeafNode creates a new leaf node
func NewLeafNode(pageID uint32) *BPlusTreeNode {
	return &BPlusTreeNode{
		PageID:   pageID,
		IsLeaf:   true,
		Keys:     make([]string, 0, MaxKeys),
		Values:   make([]string, 0, MaxKeys),
		Children: nil,
		Next:     0,
		Dirty:    true,
	}
}

// NewInternalNode creates a new internal node
func NewInternalNode(pageID uint32) *BPlusTreeNode {
	return &BPlusTreeNode{
		PageID:   pageID,
		IsLeaf:   false,
		Keys:     make([]string, 0, MaxKeys),
		Values:   nil,
		Children: make([]uint32, 0, MaxKeys+1),
		Next:     0,
		Dirty:    true,
	}
}

// BufferPool manages in-memory pages
type BufferPool struct {
	pages    map[uint32]*BPlusTreeNode
	lruList  []uint32
	capacity int
	mu       sync.RWMutex
}

// NewBufferPool creates a new buffer pool
func NewBufferPool(capacity int) *BufferPool {
	return &BufferPool{
		pages:    make(map[uint32]*BPlusTreeNode),
		lruList:  make([]uint32, 0, capacity),
		capacity: capacity,
	}
}

// Get retrieves a page from the buffer pool
func (bp *BufferPool) Get(pageID uint32) (*BPlusTreeNode, bool) {
	bp.mu.Lock()
	defer bp.mu.Unlock()

	node, exists := bp.pages[pageID]
	if exists {
		// Move to front of LRU list
		bp.moveToFront(pageID)
	}
	return node, exists
}

// Put adds a page to the buffer pool
func (bp *BufferPool) Put(node *BPlusTreeNode) *BPlusTreeNode {
	bp.mu.Lock()
	defer bp.mu.Unlock()

	var evicted *BPlusTreeNode

	// Evict if at capacity
	if len(bp.pages) >= bp.capacity {
		evicted = bp.evict()
	}

	bp.pages[node.PageID] = node
	bp.lruList = append(bp.lruList, node.PageID)

	return evicted
}

func (bp *BufferPool) moveToFront(pageID uint32) {
	for i, id := range bp.lruList {
		if id == pageID {
			bp.lruList = append(bp.lruList[:i], bp.lruList[i+1:]...)
			bp.lruList = append(bp.lruList, pageID)
			break
		}
	}
}

func (bp *BufferPool) evict() *BPlusTreeNode {
	if len(bp.lruList) == 0 {
		return nil
	}

	// Find first clean page to evict
	for i, id := range bp.lruList {
		if node, exists := bp.pages[id]; exists && !node.Dirty {
			bp.lruList = append(bp.lruList[:i], bp.lruList[i+1:]...)
			delete(bp.pages, id)
			return node
		}
	}

	// Evict first dirty page
	id := bp.lruList[0]
	bp.lruList = bp.lruList[1:]
	node := bp.pages[id]
	delete(bp.pages, id)
	return node
}

// BPlusTree implements the B+ Tree storage engine
type BPlusTree struct {
	pb.UnimplementedKVServiceServer
	pb.UnimplementedStorageServiceServer
	pb.UnimplementedReplicationServiceServer

	nodeID      string
	port        int
	peers       []string
	dataDir     string
	rootPageID  uint32
	nextPageID  uint32
	bufferPool  *BufferPool
	dataFile    *os.File
	walFile     *os.File
	mu          sync.RWMutex
	peerClients map[string]pb.ReplicationServiceClient
}

// NewBPlusTree creates a new B+ Tree store
func NewBPlusTree(nodeID string, port int, peers []string, dataDir string) *BPlusTree {
	return &BPlusTree{
		nodeID:      nodeID,
		port:        port,
		peers:       peers,
		dataDir:     dataDir,
		rootPageID:  0,
		nextPageID:  1,
		bufferPool:  NewBufferPool(BufferPoolCap),
		peerClients: make(map[string]pb.ReplicationServiceClient),
	}
}

// Initialize sets up the B+ Tree
func (t *BPlusTree) Initialize() error {
	// Create directories
	if err := os.MkdirAll(t.dataDir, 0755); err != nil {
		return err
	}

	// Open data file
	dataPath := filepath.Join(t.dataDir, "btree.dat")
	var err error
	t.dataFile, err = os.OpenFile(dataPath, os.O_RDWR|os.O_CREATE, 0644)
	if err != nil {
		return err
	}

	// Open WAL
	walPath := filepath.Join(t.dataDir, "btree.wal")
	t.walFile, err = os.OpenFile(walPath, os.O_RDWR|os.O_APPEND|os.O_CREATE, 0644)
	if err != nil {
		return err
	}

	// Load or create root
	if err := t.loadMetadata(); err != nil {
		// Create new root
		root := NewLeafNode(0)
		t.bufferPool.Put(root)
		t.rootPageID = 0
		t.nextPageID = 1
		t.writePage(root)
	}

	// Connect to peers
	for _, peer := range t.peers {
		conn, err := grpc.Dial(peer, grpc.WithTransportCredentials(insecure.NewCredentials()))
		if err != nil {
			log.Printf("Warning: Failed to connect to peer %s: %v", peer, err)
			continue
		}
		t.peerClients[peer] = pb.NewReplicationServiceClient(conn)
	}

	log.Printf("Node %s initialized with peers: %v", t.nodeID, t.peers)
	return nil
}

func (t *BPlusTree) loadMetadata() error {
	// Read metadata from first bytes of data file
	header := make([]byte, 8)
	if _, err := t.dataFile.ReadAt(header, 0); err != nil {
		return err
	}

	t.rootPageID = binary.LittleEndian.Uint32(header[0:4])
	t.nextPageID = binary.LittleEndian.Uint32(header[4:8])

	return nil
}

func (t *BPlusTree) saveMetadata() error {
	header := make([]byte, 8)
	binary.LittleEndian.PutUint32(header[0:4], t.rootPageID)
	binary.LittleEndian.PutUint32(header[4:8], t.nextPageID)

	_, err := t.dataFile.WriteAt(header, 0)
	return err
}

// readPage reads a page from disk
func (t *BPlusTree) readPage(pageID uint32) (*BPlusTreeNode, error) {
	// Check buffer pool first
	if node, found := t.bufferPool.Get(pageID); found {
		return node, nil
	}

	// Read from disk
	offset := int64(8 + pageID*PageSize)
	data := make([]byte, PageSize)
	if _, err := t.dataFile.ReadAt(data, offset); err != nil {
		return nil, err
	}

	// Deserialize
	node := t.deserializePage(pageID, data)
	t.bufferPool.Put(node)

	return node, nil
}

// writePage writes a page to disk
func (t *BPlusTree) writePage(node *BPlusTreeNode) error {
	data := t.serializePage(node)
	offset := int64(8 + node.PageID*PageSize)

	if _, err := t.dataFile.WriteAt(data, offset); err != nil {
		return err
	}

	node.Dirty = false
	return nil
}

func (t *BPlusTree) serializePage(node *BPlusTreeNode) []byte {
	data := make([]byte, PageSize)

	// Header: isLeaf(1) + numKeys(4) + next(4) = 9 bytes
	if node.IsLeaf {
		data[0] = 1
	}
	binary.LittleEndian.PutUint32(data[1:5], uint32(len(node.Keys)))
	binary.LittleEndian.PutUint32(data[5:9], node.Next)

	offset := 9

	// Write keys
	for _, key := range node.Keys {
		keyLen := len(key)
		binary.LittleEndian.PutUint16(data[offset:offset+2], uint16(keyLen))
		offset += 2
		copy(data[offset:], key)
		offset += keyLen
	}

	// Write values (for leaf) or children (for internal)
	if node.IsLeaf {
		for _, value := range node.Values {
			valLen := len(value)
			binary.LittleEndian.PutUint16(data[offset:offset+2], uint16(valLen))
			offset += 2
			copy(data[offset:], value)
			offset += valLen
		}
	} else {
		for _, child := range node.Children {
			binary.LittleEndian.PutUint32(data[offset:offset+4], child)
			offset += 4
		}
	}

	return data
}

func (t *BPlusTree) deserializePage(pageID uint32, data []byte) *BPlusTreeNode {
	isLeaf := data[0] == 1
	numKeys := binary.LittleEndian.Uint32(data[1:5])
	next := binary.LittleEndian.Uint32(data[5:9])

	var node *BPlusTreeNode
	if isLeaf {
		node = NewLeafNode(pageID)
	} else {
		node = NewInternalNode(pageID)
	}
	node.Next = next
	node.Dirty = false

	offset := 9

	// Read keys
	for i := uint32(0); i < numKeys; i++ {
		keyLen := binary.LittleEndian.Uint16(data[offset : offset+2])
		offset += 2
		node.Keys = append(node.Keys, string(data[offset:offset+int(keyLen)]))
		offset += int(keyLen)
	}

	// Read values or children
	if isLeaf {
		for i := uint32(0); i < numKeys; i++ {
			valLen := binary.LittleEndian.Uint16(data[offset : offset+2])
			offset += 2
			node.Values = append(node.Values, string(data[offset:offset+int(valLen)]))
			offset += int(valLen)
		}
	} else {
		for i := uint32(0); i <= numKeys; i++ {
			child := binary.LittleEndian.Uint32(data[offset : offset+4])
			offset += 4
			node.Children = append(node.Children, child)
		}
	}

	return node
}

// allocatePage allocates a new page
func (t *BPlusTree) allocatePage() uint32 {
	pageID := t.nextPageID
	t.nextPageID++
	t.saveMetadata()
	return pageID
}

// Search finds a key in the B+ tree
//
// TODO: Implement search:
// 1. Start at root
// 2. If internal node, find child to follow
// 3. If leaf node, search for key
func (t *BPlusTree) Search(key string) (string, bool, error) {
	t.mu.RLock()
	defer t.mu.RUnlock()

	node, err := t.readPage(t.rootPageID)
	if err != nil {
		return "", false, err
	}

	// Traverse to leaf
	for !node.IsLeaf {
		childIdx := t.findChildIndex(node, key)
		node, err = t.readPage(node.Children[childIdx])
		if err != nil {
			return "", false, err
		}
	}

	// Search in leaf
	idx := sort.SearchStrings(node.Keys, key)
	if idx < len(node.Keys) && node.Keys[idx] == key {
		return node.Values[idx], true, nil
	}

	return "", false, nil
}

func (t *BPlusTree) findChildIndex(node *BPlusTreeNode, key string) int {
	idx := sort.SearchStrings(node.Keys, key)
	return idx
}

// Insert adds a key-value pair to the B+ tree
//
// TODO: Implement insert:
// 1. Find the correct leaf node
// 2. Insert key-value in sorted order
// 3. If node overflows, split and propagate up
func (t *BPlusTree) Insert(key, value string) error {
	t.mu.Lock()
	defer t.mu.Unlock()

	// Write to WAL first
	if err := t.writeWAL(0, key, value); err != nil {
		return err
	}

	root, err := t.readPage(t.rootPageID)
	if err != nil {
		return err
	}

	// If root needs splitting
	if len(root.Keys) >= MaxKeys {
		newRoot := NewInternalNode(t.allocatePage())
		newRoot.Children = append(newRoot.Children, t.rootPageID)

		t.splitChild(newRoot, 0)

		t.bufferPool.Put(newRoot)
		t.writePage(newRoot)
		t.rootPageID = newRoot.PageID
		t.saveMetadata()
	}

	return t.insertNonFull(t.rootPageID, key, value)
}

func (t *BPlusTree) insertNonFull(pageID uint32, key, value string) error {
	node, err := t.readPage(pageID)
	if err != nil {
		return err
	}

	if node.IsLeaf {
		// Insert into leaf
		idx := sort.SearchStrings(node.Keys, key)

		// Check for update
		if idx < len(node.Keys) && node.Keys[idx] == key {
			node.Values[idx] = value
		} else {
			// Insert new key-value
			node.Keys = append(node.Keys, "")
			node.Values = append(node.Values, "")
			copy(node.Keys[idx+1:], node.Keys[idx:])
			copy(node.Values[idx+1:], node.Values[idx:])
			node.Keys[idx] = key
			node.Values[idx] = value
		}

		node.Dirty = true
		return t.writePage(node)
	}

	// Find child
	childIdx := t.findChildIndex(node, key)
	child, err := t.readPage(node.Children[childIdx])
	if err != nil {
		return err
	}

	// Split child if full
	if len(child.Keys) >= MaxKeys {
		t.splitChild(node, childIdx)
		t.writePage(node)

		// Determine which child to follow after split
		if key > node.Keys[childIdx] {
			childIdx++
		}
	}

	return t.insertNonFull(node.Children[childIdx], key, value)
}

func (t *BPlusTree) splitChild(parent *BPlusTreeNode, childIdx int) error {
	child, err := t.readPage(parent.Children[childIdx])
	if err != nil {
		return err
	}

	mid := len(child.Keys) / 2
	var newNode *BPlusTreeNode

	if child.IsLeaf {
		newNode = NewLeafNode(t.allocatePage())
		newNode.Keys = append(newNode.Keys, child.Keys[mid:]...)
		newNode.Values = append(newNode.Values, child.Values[mid:]...)
		newNode.Next = child.Next
		child.Next = newNode.PageID

		child.Keys = child.Keys[:mid]
		child.Values = child.Values[:mid]

		// Promote first key of new node
		parent.Keys = append(parent.Keys, "")
		copy(parent.Keys[childIdx+1:], parent.Keys[childIdx:])
		parent.Keys[childIdx] = newNode.Keys[0]
	} else {
		newNode = NewInternalNode(t.allocatePage())
		promoteKey := child.Keys[mid]

		newNode.Keys = append(newNode.Keys, child.Keys[mid+1:]...)
		newNode.Children = append(newNode.Children, child.Children[mid+1:]...)

		child.Keys = child.Keys[:mid]
		child.Children = child.Children[:mid+1]

		parent.Keys = append(parent.Keys, "")
		copy(parent.Keys[childIdx+1:], parent.Keys[childIdx:])
		parent.Keys[childIdx] = promoteKey
	}

	parent.Children = append(parent.Children, 0)
	copy(parent.Children[childIdx+2:], parent.Children[childIdx+1:])
	parent.Children[childIdx+1] = newNode.PageID

	t.bufferPool.Put(newNode)
	t.writePage(child)
	t.writePage(newNode)
	parent.Dirty = true

	return nil
}

// Delete removes a key from the B+ tree
func (t *BPlusTree) Delete(key string) error {
	t.mu.Lock()
	defer t.mu.Unlock()

	// Write to WAL first
	if err := t.writeWAL(1, key, ""); err != nil {
		return err
	}

	// Find and delete from leaf
	node, err := t.readPage(t.rootPageID)
	if err != nil {
		return err
	}

	// Traverse to leaf
	for !node.IsLeaf {
		childIdx := t.findChildIndex(node, key)
		node, err = t.readPage(node.Children[childIdx])
		if err != nil {
			return err
		}
	}

	// Delete from leaf
	idx := sort.SearchStrings(node.Keys, key)
	if idx < len(node.Keys) && node.Keys[idx] == key {
		node.Keys = append(node.Keys[:idx], node.Keys[idx+1:]...)
		node.Values = append(node.Values[:idx], node.Values[idx+1:]...)
		node.Dirty = true
		return t.writePage(node)
	}

	return nil
}

// Scan returns all key-value pairs in a range
func (t *BPlusTree) Scan(startKey, endKey string) ([]string, []string, error) {
	t.mu.RLock()
	defer t.mu.RUnlock()

	// Find starting leaf
	node, err := t.readPage(t.rootPageID)
	if err != nil {
		return nil, nil, err
	}

	for !node.IsLeaf {
		childIdx := t.findChildIndex(node, startKey)
		node, err = t.readPage(node.Children[childIdx])
		if err != nil {
			return nil, nil, err
		}
	}

	// Collect results
	keys := make([]string, 0)
	values := make([]string, 0)

	for {
		for i, key := range node.Keys {
			if key >= startKey && key <= endKey {
				keys = append(keys, key)
				values = append(values, node.Values[i])
			} else if key > endKey {
				return keys, values, nil
			}
		}

		if node.Next == 0 {
			break
		}

		node, err = t.readPage(node.Next)
		if err != nil {
			return nil, nil, err
		}
	}

	return keys, values, nil
}

func (t *BPlusTree) writeWAL(op byte, key, value string) error {
	header := make([]byte, 9)
	header[0] = op
	binary.LittleEndian.PutUint32(header[1:5], uint32(len(key)))
	binary.LittleEndian.PutUint32(header[5:9], uint32(len(value)))

	if _, err := t.walFile.Write(header); err != nil {
		return err
	}
	if _, err := t.walFile.WriteString(key); err != nil {
		return err
	}
	if _, err := t.walFile.WriteString(value); err != nil {
		return err
	}

	return t.walFile.Sync()
}

// FlushBufferPool writes all dirty pages to disk
func (t *BPlusTree) FlushBufferPool() error {
	t.mu.Lock()
	defer t.mu.Unlock()

	t.bufferPool.mu.Lock()
	defer t.bufferPool.mu.Unlock()

	for _, node := range t.bufferPool.pages {
		if node.Dirty {
			if err := t.writePage(node); err != nil {
				return err
			}
		}
	}

	return t.dataFile.Sync()
}

// =============================================================================
// KVService RPC Implementations
// =============================================================================

func (t *BPlusTree) Put(ctx context.Context, req *pb.PutRequest) (*pb.PutResponse, error) {
	if err := t.Insert(req.Key, req.Value); err != nil {
		return &pb.PutResponse{Success: false, Error: err.Error()}, nil
	}

	return &pb.PutResponse{
		Success:  true,
		StoredOn: t.nodeID,
	}, nil
}

func (t *BPlusTree) Get(ctx context.Context, req *pb.GetRequest) (*pb.GetResponse, error) {
	value, found, err := t.Search(req.Key)
	if err != nil {
		return &pb.GetResponse{Found: false, Error: err.Error()}, nil
	}

	return &pb.GetResponse{
		Value:    value,
		Found:    found,
		ServedBy: t.nodeID,
	}, nil
}

func (t *BPlusTree) DeleteKey(ctx context.Context, req *pb.DeleteRequest) (*pb.DeleteResponse, error) {
	if err := t.Delete(req.Key); err != nil {
		return &pb.DeleteResponse{Success: false, Error: err.Error()}, nil
	}

	return &pb.DeleteResponse{Success: true}, nil
}

func (t *BPlusTree) ScanRange(ctx context.Context, req *pb.ScanRequest) (*pb.ScanResponse, error) {
	keys, values, err := t.Scan(req.StartKey, req.EndKey)
	if err != nil {
		return &pb.ScanResponse{Error: err.Error()}, nil
	}

	pairs := make([]*pb.KeyValuePair, len(keys))
	for i := range keys {
		pairs[i] = &pb.KeyValuePair{
			Key:   keys[i],
			Value: values[i],
		}
	}

	return &pb.ScanResponse{
		Pairs: pairs,
		Count: uint64(len(pairs)),
	}, nil
}

// =============================================================================
// StorageService RPC Implementations
// =============================================================================

func (t *BPlusTree) FlushBuffer(ctx context.Context, req *pb.FlushRequest) (*pb.FlushResponse, error) {
	if err := t.FlushBufferPool(); err != nil {
		return &pb.FlushResponse{Success: false, Error: err.Error()}, nil
	}

	return &pb.FlushResponse{
		Success:      true,
		PagesFlushed: uint32(len(t.bufferPool.pages)),
	}, nil
}

func (t *BPlusTree) GetStorageStats(ctx context.Context, req *pb.GetStorageStatsRequest) (*pb.GetStorageStatsResponse, error) {
	t.mu.RLock()
	defer t.mu.RUnlock()

	t.bufferPool.mu.RLock()
	defer t.bufferPool.mu.RUnlock()

	dirtyPages := uint32(0)
	for _, node := range t.bufferPool.pages {
		if node.Dirty {
			dirtyPages++
		}
	}

	return &pb.GetStorageStatsResponse{
		TotalPages:      t.nextPageID,
		BufferPoolSize:  uint32(len(t.bufferPool.pages)),
		DirtyPages:      dirtyPages,
		NodeId:          t.nodeID,
	}, nil
}

// =============================================================================
// ReplicationService RPC Implementations
// =============================================================================

func (t *BPlusTree) Replicate(ctx context.Context, req *pb.ReplicateRequest) (*pb.ReplicateResponse, error) {
	for _, entry := range req.Entries {
		if entry.Deleted {
			t.Delete(entry.Key)
		} else {
			t.Insert(entry.Key, entry.Value)
		}
	}

	return &pb.ReplicateResponse{
		Success: true,
		NodeId:  t.nodeID,
	}, nil
}

func (t *BPlusTree) Heartbeat(ctx context.Context, req *pb.HeartbeatRequest) (*pb.HeartbeatResponse, error) {
	return &pb.HeartbeatResponse{
		Acknowledged: true,
		Timestamp:    uint64(time.Now().UnixMilli()),
	}, nil
}

// =============================================================================
// Main Entry Point
// =============================================================================

func main() {
	nodeID := flag.String("node-id", "", "Unique node identifier")
	port := flag.Int("port", 50051, "Port to listen on")
	peersStr := flag.String("peers", "", "Comma-separated list of peer addresses")
	dataDir := flag.String("data-dir", "./data", "Data directory path")
	flag.Parse()

	if *nodeID == "" {
		log.Fatal("--node-id is required")
	}

	var peers []string
	if *peersStr != "" {
		peers = strings.Split(*peersStr, ",")
		for i, p := range peers {
			peers[i] = strings.TrimSpace(p)
		}
	}

	tree := NewBPlusTree(*nodeID, *port, peers, *dataDir)
	if err := tree.Initialize(); err != nil {
		log.Fatalf("Failed to initialize B+ Tree: %v", err)
	}

	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	server := grpc.NewServer()
	pb.RegisterKVServiceServer(server, tree)
	pb.RegisterStorageServiceServer(server, tree)
	pb.RegisterReplicationServiceServer(server, tree)

	log.Printf("Starting B+ Tree KV Store node %s on port %d", *nodeID, *port)

	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
