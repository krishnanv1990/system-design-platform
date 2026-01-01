// LSM Tree KV Store - Go Template
//
// This template provides the basic structure for implementing a distributed
// key-value store using Log-Structured Merge Tree (LSM Tree) storage.
//
// Key concepts:
// 1. MemTable - In-memory sorted structure for writes
// 2. WAL - Write-Ahead Log for durability
// 3. SSTable - Sorted String Table for persistent storage
// 4. Compaction - Merge SSTables across levels
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

	pb "github.com/sdp/kv_store_lsm"
)

const (
	MemTableMaxSize   = 4 * 1024 * 1024  // 4MB
	Level0MaxFiles    = 4
	LevelSizeMultiple = 10
)

// MemTableEntry represents a key-value pair in memory
type MemTableEntry struct {
	Key       string
	Value     string
	Timestamp uint64
	Deleted   bool
}

// MemTable is an in-memory sorted structure
type MemTable struct {
	entries map[string]*MemTableEntry
	size    uint64
	mu      sync.RWMutex
}

// NewMemTable creates a new MemTable
func NewMemTable() *MemTable {
	return &MemTable{
		entries: make(map[string]*MemTableEntry),
		size:    0,
	}
}

// Put adds or updates a key in the MemTable
func (m *MemTable) Put(key, value string, timestamp uint64) {
	m.mu.Lock()
	defer m.mu.Unlock()

	oldSize := uint64(0)
	if old, exists := m.entries[key]; exists {
		oldSize = uint64(len(old.Key) + len(old.Value))
	}

	m.entries[key] = &MemTableEntry{
		Key:       key,
		Value:     value,
		Timestamp: timestamp,
		Deleted:   false,
	}

	m.size = m.size - oldSize + uint64(len(key)+len(value))
}

// Get retrieves a value from the MemTable
func (m *MemTable) Get(key string) (*MemTableEntry, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	entry, exists := m.entries[key]
	return entry, exists
}

// Delete marks a key as deleted
func (m *MemTable) Delete(key string, timestamp uint64) {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.entries[key] = &MemTableEntry{
		Key:       key,
		Value:     "",
		Timestamp: timestamp,
		Deleted:   true,
	}
}

// GetSortedEntries returns all entries sorted by key
func (m *MemTable) GetSortedEntries() []*MemTableEntry {
	m.mu.RLock()
	defer m.mu.RUnlock()

	entries := make([]*MemTableEntry, 0, len(m.entries))
	for _, e := range m.entries {
		entries = append(entries, e)
	}

	sort.Slice(entries, func(i, j int) bool {
		return entries[i].Key < entries[j].Key
	})

	return entries
}

// SSTableInfo represents metadata about an SSTable
type SSTableInfo struct {
	ID        uint32
	Level     uint32
	Path      string
	MinKey    string
	MaxKey    string
	EntryCount uint64
	Size      uint64
}

// LSMTree implements the LSM Tree storage engine
type LSMTree struct {
	pb.UnimplementedKVServiceServer
	pb.UnimplementedStorageServiceServer
	pb.UnimplementedReplicationServiceServer

	nodeID      string
	port        int
	peers       []string
	dataDir     string
	memTable    *MemTable
	immutable   *MemTable
	sstables    map[uint32][]*SSTableInfo // level -> sstables
	nextSSID    uint32
	walFile     *os.File
	mu          sync.RWMutex
	peerClients map[string]pb.ReplicationServiceClient
}

// NewLSMTree creates a new LSM Tree store
func NewLSMTree(nodeID string, port int, peers []string, dataDir string) *LSMTree {
	return &LSMTree{
		nodeID:      nodeID,
		port:        port,
		peers:       peers,
		dataDir:     dataDir,
		memTable:    NewMemTable(),
		sstables:    make(map[uint32][]*SSTableInfo),
		nextSSID:    0,
		peerClients: make(map[string]pb.ReplicationServiceClient),
	}
}

// Initialize sets up the LSM Tree
func (l *LSMTree) Initialize() error {
	// Create directories
	if err := os.MkdirAll(l.dataDir, 0755); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Join(l.dataDir, "wal"), 0755); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Join(l.dataDir, "sst"), 0755); err != nil {
		return err
	}

	// Open WAL
	walPath := filepath.Join(l.dataDir, "wal", "wal.log")
	var err error
	l.walFile, err = os.OpenFile(walPath, os.O_RDWR|os.O_APPEND|os.O_CREATE, 0644)
	if err != nil {
		return err
	}

	// Recover from WAL
	if err := l.recoverFromWAL(); err != nil {
		log.Printf("Warning: WAL recovery failed: %v", err)
	}

	// Load SSTable metadata
	if err := l.loadSSTables(); err != nil {
		log.Printf("Warning: SSTable loading failed: %v", err)
	}

	// Connect to peers
	for _, peer := range l.peers {
		conn, err := grpc.Dial(peer, grpc.WithTransportCredentials(insecure.NewCredentials()))
		if err != nil {
			log.Printf("Warning: Failed to connect to peer %s: %v", peer, err)
			continue
		}
		l.peerClients[peer] = pb.NewReplicationServiceClient(conn)
	}

	log.Printf("Node %s initialized with peers: %v", l.nodeID, l.peers)
	return nil
}

func (l *LSMTree) recoverFromWAL() error {
	l.walFile.Seek(0, 0)

	for {
		header := make([]byte, 17) // 1 byte op + 8 bytes timestamp + 4 bytes key len + 4 bytes value len
		if _, err := io.ReadFull(l.walFile, header); err != nil {
			if err == io.EOF {
				break
			}
			return err
		}

		op := header[0]
		timestamp := binary.LittleEndian.Uint64(header[1:9])
		keyLen := binary.LittleEndian.Uint32(header[9:13])
		valueLen := binary.LittleEndian.Uint32(header[13:17])

		keyBytes := make([]byte, keyLen)
		if _, err := io.ReadFull(l.walFile, keyBytes); err != nil {
			return err
		}

		valueBytes := make([]byte, valueLen)
		if _, err := io.ReadFull(l.walFile, valueBytes); err != nil {
			return err
		}

		key := string(keyBytes)
		value := string(valueBytes)

		if op == 0 {
			l.memTable.Put(key, value, timestamp)
		} else {
			l.memTable.Delete(key, timestamp)
		}
	}

	return nil
}

func (l *LSMTree) loadSSTables() error {
	pattern := filepath.Join(l.dataDir, "sst", "*.sst")
	files, err := filepath.Glob(pattern)
	if err != nil {
		return err
	}

	for _, path := range files {
		var id, level uint32
		fmt.Sscanf(filepath.Base(path), "sst_%d_L%d.sst", &id, &level)

		// Read SSTable metadata
		info := &SSTableInfo{
			ID:    id,
			Level: level,
			Path:  path,
		}

		// Read min/max keys from file
		file, err := os.Open(path)
		if err != nil {
			continue
		}
		file.Close()

		if l.sstables[level] == nil {
			l.sstables[level] = make([]*SSTableInfo, 0)
		}
		l.sstables[level] = append(l.sstables[level], info)

		if id >= l.nextSSID {
			l.nextSSID = id + 1
		}
	}

	return nil
}

// writeToWAL writes an operation to the write-ahead log
func (l *LSMTree) writeToWAL(op byte, key, value string, timestamp uint64) error {
	header := make([]byte, 17)
	header[0] = op
	binary.LittleEndian.PutUint64(header[1:9], timestamp)
	binary.LittleEndian.PutUint32(header[9:13], uint32(len(key)))
	binary.LittleEndian.PutUint32(header[13:17], uint32(len(value)))

	if _, err := l.walFile.Write(header); err != nil {
		return err
	}
	if _, err := l.walFile.WriteString(key); err != nil {
		return err
	}
	if _, err := l.walFile.WriteString(value); err != nil {
		return err
	}

	return l.walFile.Sync()
}

// Put writes a key-value pair
//
// TODO: Implement put:
// 1. Write to WAL for durability
// 2. Write to MemTable
// 3. If MemTable is full, flush to SSTable
func (l *LSMTree) Put(key, value string) error {
	// TODO: Implement this method
	return nil
}

// Get retrieves a value by key
//
// TODO: Implement get:
// 1. Check MemTable first
// 2. Check immutable MemTable if exists
// 3. Check SSTables from L0 to Ln
func (l *LSMTree) Get(key string) (string, bool, error) {
	// TODO: Implement this method
	return "", false, nil
}

func (l *LSMTree) searchSSTable(info *SSTableInfo, key string) (string, bool, bool, error) {
	file, err := os.Open(info.Path)
	if err != nil {
		return "", false, false, err
	}
	defer file.Close()

	// Simple linear scan (in production, use bloom filter + index)
	for {
		header := make([]byte, 13)
		if _, err := io.ReadFull(file, header); err != nil {
			if err == io.EOF {
				break
			}
			return "", false, false, err
		}

		deleted := header[0] == 1
		keyLen := binary.LittleEndian.Uint32(header[1:5])
		valueLen := binary.LittleEndian.Uint32(header[5:9])

		keyBytes := make([]byte, keyLen)
		if _, err := io.ReadFull(file, keyBytes); err != nil {
			return "", false, false, err
		}

		valueBytes := make([]byte, valueLen)
		if _, err := io.ReadFull(file, valueBytes); err != nil {
			return "", false, false, err
		}

		if string(keyBytes) == key {
			return string(valueBytes), true, deleted, nil
		}
	}

	return "", false, false, nil
}

// Delete marks a key as deleted
func (l *LSMTree) Delete(key string) error {
	l.mu.Lock()
	defer l.mu.Unlock()

	timestamp := uint64(time.Now().UnixNano())

	// Write tombstone to WAL
	if err := l.writeToWAL(1, key, "", timestamp); err != nil {
		return err
	}

	// Write tombstone to MemTable
	l.memTable.Delete(key, timestamp)

	return nil
}

// flush writes MemTable to SSTable
//
// TODO: Implement flush:
// 1. Freeze current MemTable as immutable
// 2. Create new active MemTable
// 3. Write immutable MemTable to L0 SSTable
// 4. Clear WAL after successful write
func (l *LSMTree) flush() error {
	// TODO: Implement this method
	return nil
}

// compact merges SSTables at a level
//
// TODO: Implement compaction:
// 1. Select SSTables to compact
// 2. Merge-sort entries from all selected tables
// 3. Write to next level
// 4. Remove old SSTables
func (l *LSMTree) compact(level uint32) error {
	// TODO: Implement this method
	return nil
}

// =============================================================================
// KVService RPC Implementations
// =============================================================================

func (l *LSMTree) PutValue(ctx context.Context, req *pb.PutRequest) (*pb.PutResponse, error) {
	if err := l.Put(req.Key, req.Value); err != nil {
		return &pb.PutResponse{Success: false, Error: err.Error()}, nil
	}

	return &pb.PutResponse{
		Success:  true,
		StoredOn: l.nodeID,
	}, nil
}

func (l *LSMTree) GetValue(ctx context.Context, req *pb.GetRequest) (*pb.GetResponse, error) {
	value, found, err := l.Get(req.Key)
	if err != nil {
		return &pb.GetResponse{Found: false, Error: err.Error()}, nil
	}

	return &pb.GetResponse{
		Value:    value,
		Found:    found,
		ServedBy: l.nodeID,
	}, nil
}

func (l *LSMTree) DeleteValue(ctx context.Context, req *pb.DeleteRequest) (*pb.DeleteResponse, error) {
	if err := l.Delete(req.Key); err != nil {
		return &pb.DeleteResponse{Success: false, Error: err.Error()}, nil
	}

	return &pb.DeleteResponse{Success: true}, nil
}

// =============================================================================
// StorageService RPC Implementations
// =============================================================================

func (l *LSMTree) TriggerFlush(ctx context.Context, req *pb.FlushRequest) (*pb.FlushResponse, error) {
	if err := l.flush(); err != nil {
		return &pb.FlushResponse{Success: false, Error: err.Error()}, nil
	}

	return &pb.FlushResponse{Success: true}, nil
}

func (l *LSMTree) TriggerCompaction(ctx context.Context, req *pb.CompactionRequest) (*pb.CompactionResponse, error) {
	if err := l.compact(req.Level); err != nil {
		return &pb.CompactionResponse{Success: false, Error: err.Error()}, nil
	}

	return &pb.CompactionResponse{Success: true}, nil
}

func (l *LSMTree) GetStorageStats(ctx context.Context, req *pb.GetStorageStatsRequest) (*pb.GetStorageStatsResponse, error) {
	l.mu.RLock()
	defer l.mu.RUnlock()

	levelStats := make(map[uint32]*pb.LevelStats)
	for level, tables := range l.sstables {
		var totalSize uint64
		for _, t := range tables {
			totalSize += t.Size
		}
		levelStats[level] = &pb.LevelStats{
			SstableCount: uint32(len(tables)),
			TotalSize:    totalSize,
		}
	}

	return &pb.GetStorageStatsResponse{
		MemtableSize:   l.memTable.size,
		MemtableCount:  uint64(len(l.memTable.entries)),
		LevelStats:     levelStats,
		NodeId:         l.nodeID,
	}, nil
}

// =============================================================================
// ReplicationService RPC Implementations
// =============================================================================

func (l *LSMTree) Replicate(ctx context.Context, req *pb.ReplicateRequest) (*pb.ReplicateResponse, error) {
	for _, entry := range req.Entries {
		if entry.Deleted {
			l.Delete(entry.Key)
		} else {
			l.Put(entry.Key, entry.Value)
		}
	}

	return &pb.ReplicateResponse{
		Success: true,
		NodeId:  l.nodeID,
	}, nil
}

func (l *LSMTree) Heartbeat(ctx context.Context, req *pb.HeartbeatRequest) (*pb.HeartbeatResponse, error) {
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

	lsm := NewLSMTree(*nodeID, *port, peers, *dataDir)
	if err := lsm.Initialize(); err != nil {
		log.Fatalf("Failed to initialize LSM Tree: %v", err)
	}

	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	server := grpc.NewServer()
	pb.RegisterKVServiceServer(server, lsm)
	pb.RegisterStorageServiceServer(server, lsm)
	pb.RegisterReplicationServiceServer(server, lsm)

	log.Printf("Starting LSM Tree KV Store node %s on port %d", *nodeID, *port)

	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
