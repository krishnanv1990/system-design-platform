// Log-Structured KV Store with Compaction - Go Template
//
// This template provides the basic structure for implementing a distributed
// key-value store using append-only log storage with compaction (Bitcask-style).
//
// Key concepts:
// 1. Append-Only Log - All writes are appended to log file
// 2. In-Memory Index - KeyDir maps keys to file positions
// 3. Compaction - Merge and remove stale entries
// 4. Crash Recovery - Rebuild index from log on startup
//
// Usage:
//     go run server.go --node-id node1 --port 50051 --peers node2:50052,node3:50053

package main

import (
	"context"
	"encoding/binary"
	"flag"
	"fmt"
	"hash/crc32"
	"io"
	"log"
	"net"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	pb "github.com/sdp/kv_store_log"
)

const (
	MaxSegmentSize = 64 * 1024 * 1024 // 64MB
	TombstoneValue = "__TOMBSTONE__"
)

// KeyDirEntry points to a value in the log
type KeyDirEntry struct {
	SegmentID uint32
	Offset    uint64
	Size      uint32
	Timestamp uint64
}

// LogEntry represents a single log record
type LogEntry struct {
	CRC       uint32
	Timestamp uint64
	KeySize   uint32
	ValueSize uint32
	Key       string
	Value     string
}

// Segment represents a log segment file
type Segment struct {
	ID       uint32
	File     *os.File
	Path     string
	Size     uint64
	mu       sync.Mutex
}

// LogStructuredStore implements the log-structured storage engine
type LogStructuredStore struct {
	pb.UnimplementedKVServiceServer
	pb.UnimplementedStorageServiceServer
	pb.UnimplementedReplicationServiceServer

	nodeID         string
	port           int
	peers          []string
	dataDir        string
	keyDir         map[string]*KeyDirEntry
	activeSegment  *Segment
	segments       map[uint32]*Segment
	mu             sync.RWMutex
	peerClients    map[string]pb.ReplicationServiceClient
}

// NewLogStructuredStore creates a new log-structured store
func NewLogStructuredStore(nodeID string, port int, peers []string, dataDir string) *LogStructuredStore {
	return &LogStructuredStore{
		nodeID:      nodeID,
		port:        port,
		peers:       peers,
		dataDir:     dataDir,
		keyDir:      make(map[string]*KeyDirEntry),
		segments:    make(map[uint32]*Segment),
		peerClients: make(map[string]pb.ReplicationServiceClient),
	}
}

// Initialize sets up the store and recovers from existing logs
func (s *LogStructuredStore) Initialize() error {
	// Create data directory if not exists
	if err := os.MkdirAll(s.dataDir, 0755); err != nil {
		return err
	}

	// Recover from existing segments
	if err := s.recover(); err != nil {
		return err
	}

	// Create new active segment if none exists
	if s.activeSegment == nil {
		if err := s.createNewSegment(); err != nil {
			return err
		}
	}

	// Connect to peers
	for _, peer := range s.peers {
		conn, err := grpc.Dial(peer, grpc.WithTransportCredentials(insecure.NewCredentials()))
		if err != nil {
			log.Printf("Warning: Failed to connect to peer %s: %v", peer, err)
			continue
		}
		s.peerClients[peer] = pb.NewReplicationServiceClient(conn)
	}

	log.Printf("Node %s initialized with peers: %v", s.nodeID, s.peers)
	return nil
}

// recover rebuilds the keyDir from existing log segments
//
// TODO: Implement recovery:
// 1. Scan data directory for segment files
// 2. Read each segment and rebuild keyDir
// 3. Handle tombstones (deleted keys)
func (s *LogStructuredStore) recover() error {
	files, err := filepath.Glob(filepath.Join(s.dataDir, "segment_*.log"))
	if err != nil {
		return err
	}

	for _, path := range files {
		var segmentID uint32
		fmt.Sscanf(filepath.Base(path), "segment_%d.log", &segmentID)

		segment, err := s.openSegment(segmentID, path)
		if err != nil {
			log.Printf("Warning: Failed to open segment %d: %v", segmentID, err)
			continue
		}

		// Read all entries and rebuild keyDir
		if err := s.rebuildFromSegment(segment); err != nil {
			log.Printf("Warning: Failed to rebuild from segment %d: %v", segmentID, err)
		}

		s.segments[segmentID] = segment
		s.activeSegment = segment
	}

	return nil
}

func (s *LogStructuredStore) openSegment(id uint32, path string) (*Segment, error) {
	file, err := os.OpenFile(path, os.O_RDWR|os.O_APPEND|os.O_CREATE, 0644)
	if err != nil {
		return nil, err
	}

	stat, err := file.Stat()
	if err != nil {
		return nil, err
	}

	return &Segment{
		ID:   id,
		File: file,
		Path: path,
		Size: uint64(stat.Size()),
	}, nil
}

func (s *LogStructuredStore) rebuildFromSegment(segment *Segment) error {
	segment.File.Seek(0, 0)

	for {
		offset, _ := segment.File.Seek(0, 1)

		entry, err := s.readEntry(segment.File)
		if err == io.EOF {
			break
		}
		if err != nil {
			return err
		}

		if entry.Value == TombstoneValue {
			delete(s.keyDir, entry.Key)
		} else {
			s.keyDir[entry.Key] = &KeyDirEntry{
				SegmentID: segment.ID,
				Offset:    uint64(offset),
				Size:      entry.KeySize + entry.ValueSize + 20, // header size
				Timestamp: entry.Timestamp,
			}
		}
	}

	return nil
}

func (s *LogStructuredStore) readEntry(file *os.File) (*LogEntry, error) {
	header := make([]byte, 20)
	if _, err := io.ReadFull(file, header); err != nil {
		return nil, err
	}

	entry := &LogEntry{
		CRC:       binary.LittleEndian.Uint32(header[0:4]),
		Timestamp: binary.LittleEndian.Uint64(header[4:12]),
		KeySize:   binary.LittleEndian.Uint32(header[12:16]),
		ValueSize: binary.LittleEndian.Uint32(header[16:20]),
	}

	keyBytes := make([]byte, entry.KeySize)
	if _, err := io.ReadFull(file, keyBytes); err != nil {
		return nil, err
	}
	entry.Key = string(keyBytes)

	valueBytes := make([]byte, entry.ValueSize)
	if _, err := io.ReadFull(file, valueBytes); err != nil {
		return nil, err
	}
	entry.Value = string(valueBytes)

	return entry, nil
}

func (s *LogStructuredStore) createNewSegment() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	segmentID := uint32(len(s.segments))
	path := filepath.Join(s.dataDir, fmt.Sprintf("segment_%06d.log", segmentID))

	file, err := os.OpenFile(path, os.O_RDWR|os.O_APPEND|os.O_CREATE, 0644)
	if err != nil {
		return err
	}

	segment := &Segment{
		ID:   segmentID,
		File: file,
		Path: path,
		Size: 0,
	}

	s.segments[segmentID] = segment
	s.activeSegment = segment

	return nil
}

// Append writes a key-value pair to the log
//
// TODO: Implement append:
// 1. Create log entry with CRC, timestamp, key, value
// 2. Write to active segment
// 3. Update keyDir with new position
// 4. Rotate segment if needed
func (s *LogStructuredStore) Append(key, value string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	entry := &LogEntry{
		Timestamp: uint64(time.Now().UnixNano()),
		KeySize:   uint32(len(key)),
		ValueSize: uint32(len(value)),
		Key:       key,
		Value:     value,
	}

	// Calculate CRC
	data := make([]byte, 16+len(key)+len(value))
	binary.LittleEndian.PutUint64(data[0:8], entry.Timestamp)
	binary.LittleEndian.PutUint32(data[8:12], entry.KeySize)
	binary.LittleEndian.PutUint32(data[12:16], entry.ValueSize)
	copy(data[16:], key)
	copy(data[16+len(key):], value)
	entry.CRC = crc32.ChecksumIEEE(data)

	// Write entry
	s.activeSegment.mu.Lock()
	offset := s.activeSegment.Size

	header := make([]byte, 20)
	binary.LittleEndian.PutUint32(header[0:4], entry.CRC)
	binary.LittleEndian.PutUint64(header[4:12], entry.Timestamp)
	binary.LittleEndian.PutUint32(header[12:16], entry.KeySize)
	binary.LittleEndian.PutUint32(header[16:20], entry.ValueSize)

	if _, err := s.activeSegment.File.Write(header); err != nil {
		s.activeSegment.mu.Unlock()
		return err
	}
	if _, err := s.activeSegment.File.WriteString(key); err != nil {
		s.activeSegment.mu.Unlock()
		return err
	}
	if _, err := s.activeSegment.File.WriteString(value); err != nil {
		s.activeSegment.mu.Unlock()
		return err
	}

	entrySize := uint64(20 + len(key) + len(value))
	s.activeSegment.Size += entrySize
	s.activeSegment.mu.Unlock()

	// Update keyDir
	s.keyDir[key] = &KeyDirEntry{
		SegmentID: s.activeSegment.ID,
		Offset:    offset,
		Size:      uint32(entrySize),
		Timestamp: entry.Timestamp,
	}

	// Rotate if needed
	if s.activeSegment.Size >= MaxSegmentSize {
		s.createNewSegment()
	}

	return nil
}

// Get retrieves a value by key
//
// TODO: Implement get:
// 1. Lookup key in keyDir
// 2. Seek to position in segment file
// 3. Read and return value
func (s *LogStructuredStore) Get(key string) (string, bool, error) {
	s.mu.RLock()
	entry, exists := s.keyDir[key]
	if !exists {
		s.mu.RUnlock()
		return "", false, nil
	}

	segment, ok := s.segments[entry.SegmentID]
	s.mu.RUnlock()

	if !ok {
		return "", false, fmt.Errorf("segment not found")
	}

	segment.mu.Lock()
	defer segment.mu.Unlock()

	segment.File.Seek(int64(entry.Offset), 0)
	logEntry, err := s.readEntry(segment.File)
	if err != nil {
		return "", false, err
	}

	if logEntry.Value == TombstoneValue {
		return "", false, nil
	}

	return logEntry.Value, true, nil
}

// Delete marks a key as deleted with a tombstone
func (s *LogStructuredStore) Delete(key string) error {
	return s.Append(key, TombstoneValue)
}

// Compact merges segments and removes stale entries
//
// TODO: Implement compaction:
// 1. Create new compacted segment
// 2. Write only latest value for each key
// 3. Skip tombstones
// 4. Update keyDir to point to new segment
// 5. Delete old segments
func (s *LogStructuredStore) Compact() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	// Create new compacted segment
	segmentID := uint32(len(s.segments))
	path := filepath.Join(s.dataDir, fmt.Sprintf("segment_%06d.log", segmentID))

	file, err := os.OpenFile(path, os.O_RDWR|os.O_APPEND|os.O_CREATE, 0644)
	if err != nil {
		return err
	}

	newSegment := &Segment{
		ID:   segmentID,
		File: file,
		Path: path,
		Size: 0,
	}

	// Write all live keys
	newKeyDir := make(map[string]*KeyDirEntry)
	for key, entry := range s.keyDir {
		segment := s.segments[entry.SegmentID]

		segment.File.Seek(int64(entry.Offset), 0)
		logEntry, err := s.readEntry(segment.File)
		if err != nil {
			continue
		}

		if logEntry.Value == TombstoneValue {
			continue
		}

		// Write to new segment
		offset := newSegment.Size

		header := make([]byte, 20)
		binary.LittleEndian.PutUint32(header[0:4], logEntry.CRC)
		binary.LittleEndian.PutUint64(header[4:12], logEntry.Timestamp)
		binary.LittleEndian.PutUint32(header[12:16], logEntry.KeySize)
		binary.LittleEndian.PutUint32(header[16:20], logEntry.ValueSize)

		newSegment.File.Write(header)
		newSegment.File.WriteString(logEntry.Key)
		newSegment.File.WriteString(logEntry.Value)

		entrySize := uint64(20 + len(logEntry.Key) + len(logEntry.Value))
		newSegment.Size += entrySize

		newKeyDir[key] = &KeyDirEntry{
			SegmentID: segmentID,
			Offset:    offset,
			Size:      uint32(entrySize),
			Timestamp: logEntry.Timestamp,
		}
	}

	// Update state
	s.keyDir = newKeyDir
	s.segments[segmentID] = newSegment
	s.activeSegment = newSegment

	return nil
}

// =============================================================================
// KVService RPC Implementations
// =============================================================================

func (s *LogStructuredStore) Put(ctx context.Context, req *pb.PutRequest) (*pb.PutResponse, error) {
	if err := s.Append(req.Key, req.Value); err != nil {
		return &pb.PutResponse{Success: false, Error: err.Error()}, nil
	}

	return &pb.PutResponse{
		Success:  true,
		StoredOn: s.nodeID,
	}, nil
}

func (s *LogStructuredStore) GetValue(ctx context.Context, req *pb.GetRequest) (*pb.GetResponse, error) {
	value, found, err := s.Get(req.Key)
	if err != nil {
		return &pb.GetResponse{Found: false, Error: err.Error()}, nil
	}

	return &pb.GetResponse{
		Value:    value,
		Found:    found,
		ServedBy: s.nodeID,
	}, nil
}

func (s *LogStructuredStore) DeleteKey(ctx context.Context, req *pb.DeleteRequest) (*pb.DeleteResponse, error) {
	if err := s.Delete(req.Key); err != nil {
		return &pb.DeleteResponse{Success: false, Error: err.Error()}, nil
	}

	return &pb.DeleteResponse{Success: true}, nil
}

// =============================================================================
// StorageService RPC Implementations
// =============================================================================

func (s *LogStructuredStore) TriggerCompaction(ctx context.Context, req *pb.CompactionRequest) (*pb.CompactionResponse, error) {
	if err := s.Compact(); err != nil {
		return &pb.CompactionResponse{Success: false, Error: err.Error()}, nil
	}

	return &pb.CompactionResponse{
		Success:      true,
		KeysRetained: uint64(len(s.keyDir)),
	}, nil
}

func (s *LogStructuredStore) GetStorageStats(ctx context.Context, req *pb.GetStorageStatsRequest) (*pb.GetStorageStatsResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	var totalSize uint64
	for _, segment := range s.segments {
		totalSize += segment.Size
	}

	return &pb.GetStorageStatsResponse{
		TotalKeys:     uint64(len(s.keyDir)),
		TotalSegments: uint32(len(s.segments)),
		TotalSize:     totalSize,
		NodeId:        s.nodeID,
	}, nil
}

// =============================================================================
// ReplicationService RPC Implementations
// =============================================================================

func (s *LogStructuredStore) Replicate(ctx context.Context, req *pb.ReplicateRequest) (*pb.ReplicateResponse, error) {
	for _, entry := range req.Entries {
		if entry.IsTombstone {
			s.Delete(entry.Key)
		} else {
			s.Append(entry.Key, entry.Value)
		}
	}

	return &pb.ReplicateResponse{
		Success:          true,
		NodeId:           s.nodeID,
		EntriesProcessed: uint64(len(req.Entries)),
	}, nil
}

func (s *LogStructuredStore) Heartbeat(ctx context.Context, req *pb.HeartbeatRequest) (*pb.HeartbeatResponse, error) {
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

	store := NewLogStructuredStore(*nodeID, *port, peers, *dataDir)
	if err := store.Initialize(); err != nil {
		log.Fatalf("Failed to initialize store: %v", err)
	}

	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	server := grpc.NewServer()
	pb.RegisterKVServiceServer(server, store)
	pb.RegisterStorageServiceServer(server, store)
	pb.RegisterReplicationServiceServer(server, store)

	log.Printf("Starting Log-Structured KV Store node %s on port %d", *nodeID, *port)

	if err := server.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
