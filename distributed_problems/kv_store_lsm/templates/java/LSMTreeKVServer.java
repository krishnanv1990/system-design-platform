/**
 * LSM Tree KV Store - Java Template
 *
 * This template provides the basic structure for implementing a distributed
 * key-value store using Log-Structured Merge Tree (LSM Tree) storage.
 *
 * Key concepts:
 * 1. MemTable - In-memory sorted structure for writes
 * 2. WAL - Write-Ahead Log for durability
 * 3. SSTable - Sorted String Table for persistent storage
 * 4. Compaction - Merge SSTables across levels
 *
 * Usage:
 *     java LSMTreeKVServer --node-id node1 --port 50051 --data-dir ./data
 */

package com.sdp.kvstorelsmtree;

import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.stub.StreamObserver;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.ConcurrentSkipListMap;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.logging.Logger;

public class LSMTreeKVServer {
    private static final Logger logger = Logger.getLogger(LSMTreeKVServer.class.getName());
    private static final int MEMTABLE_MAX_SIZE = 4 * 1024 * 1024; // 4MB
    private static final int LEVEL0_MAX_FILES = 4;

    /**
     * MemTableEntry represents a key-value pair in memory.
     */
    public static class MemTableEntry {
        public final String key;
        public final String value;
        public final long timestamp;
        public final boolean deleted;

        public MemTableEntry(String key, String value, long timestamp, boolean deleted) {
            this.key = key;
            this.value = value;
            this.timestamp = timestamp;
            this.deleted = deleted;
        }
    }

    /**
     * SSTableInfo represents metadata about an SSTable.
     */
    public static class SSTableInfo {
        public final int id;
        public final int level;
        public final Path path;
        public String minKey;
        public String maxKey;
        public long entryCount;
        public long size;

        public SSTableInfo(int id, int level, Path path) {
            this.id = id;
            this.level = level;
            this.path = path;
        }
    }

    /**
     * LSMTree implements the LSM Tree storage engine.
     */
    public static class LSMTree extends KVServiceGrpc.KVServiceImplBase {
        private final String nodeId;
        private final int port;
        private final Path dataDir;
        private ConcurrentSkipListMap<String, MemTableEntry> memTable = new ConcurrentSkipListMap<>();
        private ConcurrentSkipListMap<String, MemTableEntry> immutableMemTable;
        private final Map<Integer, List<SSTableInfo>> sstables = new HashMap<>();
        private int nextSSTableId = 0;
        private long memTableSize = 0;
        private RandomAccessFile walFile;
        private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

        public LSMTree(String nodeId, int port, String dataDir) {
            this.nodeId = nodeId;
            this.port = port;
            this.dataDir = Paths.get(dataDir);
        }

        public void initialize() throws IOException {
            Files.createDirectories(dataDir);
            Files.createDirectories(dataDir.resolve("wal"));
            Files.createDirectories(dataDir.resolve("sst"));

            // Open WAL
            Path walPath = dataDir.resolve("wal").resolve("wal.log");
            walFile = new RandomAccessFile(walPath.toFile(), "rw");

            // Recover from WAL
            recoverFromWAL();

            // Load SSTable metadata
            loadSSTables();

            logger.info("Node " + nodeId + " initialized");
        }

        private void recoverFromWAL() throws IOException {
            walFile.seek(0);
            while (walFile.getFilePointer() < walFile.length()) {
                try {
                    byte op = walFile.readByte();
                    long timestamp = walFile.readLong();
                    int keyLen = walFile.readInt();
                    int valueLen = walFile.readInt();

                    byte[] keyBytes = new byte[keyLen];
                    walFile.readFully(keyBytes);
                    byte[] valueBytes = new byte[valueLen];
                    walFile.readFully(valueBytes);

                    String key = new String(keyBytes);
                    String value = new String(valueBytes);

                    if (op == 0) {
                        memTable.put(key, new MemTableEntry(key, value, timestamp, false));
                    } else {
                        memTable.put(key, new MemTableEntry(key, "", timestamp, true));
                    }
                } catch (EOFException e) {
                    break;
                }
            }
        }

        private void loadSSTables() throws IOException {
            try (DirectoryStream<Path> stream = Files.newDirectoryStream(dataDir.resolve("sst"), "*.sst")) {
                for (Path path : stream) {
                    String filename = path.getFileName().toString();
                    // Parse sst_000001_L0.sst
                    String[] parts = filename.replace(".sst", "").split("_");
                    int id = Integer.parseInt(parts[1]);
                    int level = Integer.parseInt(parts[2].replace("L", ""));

                    SSTableInfo info = new SSTableInfo(id, level, path);
                    sstables.computeIfAbsent(level, k -> new ArrayList<>()).add(info);

                    if (id >= nextSSTableId) {
                        nextSSTableId = id + 1;
                    }
                }
            }
        }

        private void writeToWAL(byte op, String key, String value, long timestamp) throws IOException {
            byte[] keyBytes = key.getBytes();
            byte[] valueBytes = value.getBytes();

            walFile.writeByte(op);
            walFile.writeLong(timestamp);
            walFile.writeInt(keyBytes.length);
            walFile.writeInt(valueBytes.length);
            walFile.write(keyBytes);
            walFile.write(valueBytes);
            walFile.getFD().sync();
        }

        /**
         * Put a key-value pair.
         * TODO: Write to WAL, then MemTable, flush if needed
         */
        public void put(String key, String value) throws IOException {
            lock.writeLock().lock();
            try {
                long timestamp = System.nanoTime();
                writeToWAL((byte) 0, key, value, timestamp);

                memTable.put(key, new MemTableEntry(key, value, timestamp, false));
                memTableSize += key.length() + value.length();

                if (memTableSize >= MEMTABLE_MAX_SIZE) {
                    flush();
                }
            } finally {
                lock.writeLock().unlock();
            }
        }

        /**
         * Get a value by key.
         * TODO: Check MemTable, immutable, then SSTables
         */
        public String get(String key) throws IOException {
            lock.readLock().lock();
            try {
                // Check MemTable
                MemTableEntry entry = memTable.get(key);
                if (entry != null) {
                    return entry.deleted ? null : entry.value;
                }

                // Check immutable MemTable
                if (immutableMemTable != null) {
                    entry = immutableMemTable.get(key);
                    if (entry != null) {
                        return entry.deleted ? null : entry.value;
                    }
                }

                // Check SSTables (L0 first, then other levels)
                for (int level = 0; level <= 5; level++) {
                    List<SSTableInfo> tables = sstables.getOrDefault(level, Collections.emptyList());
                    for (int i = tables.size() - 1; i >= 0; i--) {
                        SSTableInfo info = tables.get(i);
                        String value = searchSSTable(info, key);
                        if (value != null) {
                            return "__DELETED__".equals(value) ? null : value;
                        }
                    }
                }

                return null;
            } finally {
                lock.readLock().unlock();
            }
        }

        private String searchSSTable(SSTableInfo info, String key) throws IOException {
            try (RandomAccessFile file = new RandomAccessFile(info.path.toFile(), "r")) {
                while (file.getFilePointer() < file.length()) {
                    byte deleted = file.readByte();
                    int keyLen = file.readInt();
                    int valueLen = file.readInt();
                    file.readInt(); // timestamp (truncated)

                    byte[] keyBytes = new byte[keyLen];
                    file.readFully(keyBytes);
                    byte[] valueBytes = new byte[valueLen];
                    file.readFully(valueBytes);

                    String entryKey = new String(keyBytes);
                    if (entryKey.equals(key)) {
                        return deleted == 1 ? "__DELETED__" : new String(valueBytes);
                    }
                }
            }
            return null;
        }

        /**
         * Delete a key.
         */
        public void delete(String key) throws IOException {
            lock.writeLock().lock();
            try {
                long timestamp = System.nanoTime();
                writeToWAL((byte) 1, key, "", timestamp);
                memTable.put(key, new MemTableEntry(key, "", timestamp, true));
            } finally {
                lock.writeLock().unlock();
            }
        }

        /**
         * Flush MemTable to SSTable.
         * TODO: Write sorted entries to SSTable file
         */
        public void flush() throws IOException {
            if (memTable.isEmpty()) {
                return;
            }

            // Make current MemTable immutable
            immutableMemTable = memTable;
            memTable = new ConcurrentSkipListMap<>();
            memTableSize = 0;

            // Write SSTable
            int ssId = nextSSTableId++;
            Path path = dataDir.resolve("sst").resolve(String.format("sst_%06d_L0.sst", ssId));

            try (RandomAccessFile file = new RandomAccessFile(path.toFile(), "rw")) {
                String minKey = null, maxKey = null;
                long entryCount = 0;

                for (MemTableEntry entry : immutableMemTable.values()) {
                    if (minKey == null) minKey = entry.key;
                    maxKey = entry.key;

                    byte[] keyBytes = entry.key.getBytes();
                    byte[] valueBytes = entry.value.getBytes();

                    file.writeByte(entry.deleted ? 1 : 0);
                    file.writeInt(keyBytes.length);
                    file.writeInt(valueBytes.length);
                    file.writeInt((int) entry.timestamp);
                    file.write(keyBytes);
                    file.write(valueBytes);
                    entryCount++;
                }

                SSTableInfo info = new SSTableInfo(ssId, 0, path);
                info.minKey = minKey;
                info.maxKey = maxKey;
                info.entryCount = entryCount;
                info.size = file.length();

                sstables.computeIfAbsent(0, k -> new ArrayList<>()).add(info);
            }

            immutableMemTable = null;

            // Clear WAL
            walFile.setLength(0);

            // Check if compaction needed
            List<SSTableInfo> l0Tables = sstables.getOrDefault(0, Collections.emptyList());
            if (l0Tables.size() >= LEVEL0_MAX_FILES) {
                compact(0);
            }
        }

        /**
         * Compact SSTables at a level.
         */
        public void compact(int level) throws IOException {
            List<SSTableInfo> tables = sstables.getOrDefault(level, Collections.emptyList());
            if (tables.size() < 2) {
                return;
            }

            // Read and merge all entries
            Map<String, MemTableEntry> allEntries = new TreeMap<>();
            for (SSTableInfo table : tables) {
                try (RandomAccessFile file = new RandomAccessFile(table.path.toFile(), "r")) {
                    while (file.getFilePointer() < file.length()) {
                        byte deleted = file.readByte();
                        int keyLen = file.readInt();
                        int valueLen = file.readInt();
                        int timestamp = file.readInt();

                        byte[] keyBytes = new byte[keyLen];
                        file.readFully(keyBytes);
                        byte[] valueBytes = new byte[valueLen];
                        file.readFully(valueBytes);

                        String key = new String(keyBytes);
                        String value = new String(valueBytes);

                        MemTableEntry existing = allEntries.get(key);
                        if (existing == null || timestamp > existing.timestamp) {
                            allEntries.put(key, new MemTableEntry(key, value, timestamp, deleted == 1));
                        }
                    }
                }
            }

            // Write new SSTable at next level
            int ssId = nextSSTableId++;
            int nextLevel = level + 1;
            Path path = dataDir.resolve("sst").resolve(String.format("sst_%06d_L%d.sst", ssId, nextLevel));

            try (RandomAccessFile file = new RandomAccessFile(path.toFile(), "rw")) {
                String minKey = null, maxKey = null;
                long entryCount = 0;

                for (MemTableEntry entry : allEntries.values()) {
                    if (entry.deleted) continue;

                    if (minKey == null) minKey = entry.key;
                    maxKey = entry.key;

                    byte[] keyBytes = entry.key.getBytes();
                    byte[] valueBytes = entry.value.getBytes();

                    file.writeByte(0);
                    file.writeInt(keyBytes.length);
                    file.writeInt(valueBytes.length);
                    file.writeInt((int) entry.timestamp);
                    file.write(keyBytes);
                    file.write(valueBytes);
                    entryCount++;
                }

                SSTableInfo info = new SSTableInfo(ssId, nextLevel, path);
                info.minKey = minKey;
                info.maxKey = maxKey;
                info.entryCount = entryCount;
                info.size = file.length();

                sstables.computeIfAbsent(nextLevel, k -> new ArrayList<>()).add(info);
            }

            // Remove old SSTables
            for (SSTableInfo table : tables) {
                Files.deleteIfExists(table.path);
            }
            sstables.put(level, new ArrayList<>());
        }

        // =========================================================================
        // KVService RPC Implementations
        // =========================================================================

        @Override
        public void putValue(KVStoreLSM.PutRequest request,
                            StreamObserver<KVStoreLSM.PutResponse> responseObserver) {
            try {
                put(request.getKey(), request.getValue());
                responseObserver.onNext(KVStoreLSM.PutResponse.newBuilder()
                    .setSuccess(true)
                    .setStoredOn(nodeId)
                    .build());
            } catch (IOException e) {
                responseObserver.onNext(KVStoreLSM.PutResponse.newBuilder()
                    .setSuccess(false)
                    .setError(e.getMessage())
                    .build());
            }
            responseObserver.onCompleted();
        }

        @Override
        public void getValue(KVStoreLSM.GetRequest request,
                            StreamObserver<KVStoreLSM.GetResponse> responseObserver) {
            try {
                String value = get(request.getKey());
                responseObserver.onNext(KVStoreLSM.GetResponse.newBuilder()
                    .setValue(value != null ? value : "")
                    .setFound(value != null)
                    .setServedBy(nodeId)
                    .build());
            } catch (IOException e) {
                responseObserver.onNext(KVStoreLSM.GetResponse.newBuilder()
                    .setFound(false)
                    .setError(e.getMessage())
                    .build());
            }
            responseObserver.onCompleted();
        }

        @Override
        public void deleteValue(KVStoreLSM.DeleteRequest request,
                               StreamObserver<KVStoreLSM.DeleteResponse> responseObserver) {
            try {
                delete(request.getKey());
                responseObserver.onNext(KVStoreLSM.DeleteResponse.newBuilder()
                    .setSuccess(true)
                    .build());
            } catch (IOException e) {
                responseObserver.onNext(KVStoreLSM.DeleteResponse.newBuilder()
                    .setSuccess(false)
                    .setError(e.getMessage())
                    .build());
            }
            responseObserver.onCompleted();
        }

        public String getNodeId() { return nodeId; }
        public long getMemTableSize() { return memTableSize; }
        public int getMemTableCount() { return memTable.size(); }
        public Map<Integer, List<SSTableInfo>> getSSTables() { return sstables; }
    }

    /**
     * StorageService implementation.
     */
    public static class StorageServiceImpl extends StorageServiceGrpc.StorageServiceImplBase {
        private final LSMTree lsm;

        public StorageServiceImpl(LSMTree lsm) {
            this.lsm = lsm;
        }

        @Override
        public void triggerFlush(KVStoreLSM.FlushRequest request,
                                StreamObserver<KVStoreLSM.FlushResponse> responseObserver) {
            try {
                lsm.flush();
                responseObserver.onNext(KVStoreLSM.FlushResponse.newBuilder()
                    .setSuccess(true)
                    .build());
            } catch (IOException e) {
                responseObserver.onNext(KVStoreLSM.FlushResponse.newBuilder()
                    .setSuccess(false)
                    .setError(e.getMessage())
                    .build());
            }
            responseObserver.onCompleted();
        }

        @Override
        public void triggerCompaction(KVStoreLSM.CompactionRequest request,
                                     StreamObserver<KVStoreLSM.CompactionResponse> responseObserver) {
            try {
                lsm.compact((int) request.getLevel());
                responseObserver.onNext(KVStoreLSM.CompactionResponse.newBuilder()
                    .setSuccess(true)
                    .build());
            } catch (IOException e) {
                responseObserver.onNext(KVStoreLSM.CompactionResponse.newBuilder()
                    .setSuccess(false)
                    .setError(e.getMessage())
                    .build());
            }
            responseObserver.onCompleted();
        }

        @Override
        public void getStorageStats(KVStoreLSM.GetStorageStatsRequest request,
                                   StreamObserver<KVStoreLSM.GetStorageStatsResponse> responseObserver) {
            KVStoreLSM.GetStorageStatsResponse.Builder response = KVStoreLSM.GetStorageStatsResponse.newBuilder()
                .setMemtableSize(lsm.getMemTableSize())
                .setMemtableCount(lsm.getMemTableCount())
                .setNodeId(lsm.getNodeId());

            for (Map.Entry<Integer, List<SSTableInfo>> entry : lsm.getSSTables().entrySet()) {
                long totalSize = entry.getValue().stream().mapToLong(s -> s.size).sum();
                response.putLevelStats(entry.getKey(), KVStoreLSM.LevelStats.newBuilder()
                    .setSstableCount(entry.getValue().size())
                    .setTotalSize(totalSize)
                    .build());
            }

            responseObserver.onNext(response.build());
            responseObserver.onCompleted();
        }
    }

    // =============================================================================
    // Main Entry Point
    // =============================================================================

    public static void main(String[] args) throws IOException, InterruptedException {
        String nodeId = null;
        int port = 50051;
        String dataDir = "./data";

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--node-id":
                    nodeId = args[++i];
                    break;
                case "--port":
                    port = Integer.parseInt(args[++i]);
                    break;
                case "--data-dir":
                    dataDir = args[++i];
                    break;
            }
        }

        if (nodeId == null) {
            System.err.println("Usage: java LSMTreeKVServer --node-id <id> --port <port> --data-dir <path>");
            System.exit(1);
        }

        LSMTree lsm = new LSMTree(nodeId, port, dataDir);
        lsm.initialize();

        Server server = ServerBuilder.forPort(port)
                .addService(lsm)
                .addService(new StorageServiceImpl(lsm))
                .build()
                .start();

        logger.info("Starting LSM Tree KV Store node " + nodeId + " on port " + port);
        server.awaitTermination();
    }
}
