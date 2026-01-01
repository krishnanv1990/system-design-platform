/**
 * Log-Structured KV Store with Compaction - Java Template
 *
 * This template provides the basic structure for implementing a distributed
 * key-value store using append-only log storage with compaction (Bitcask-style).
 *
 * Key concepts:
 * 1. Append-Only Log - All writes are appended to log file
 * 2. In-Memory Index - KeyDir maps keys to file positions
 * 3. Compaction - Merge and remove stale entries
 * 4. Crash Recovery - Rebuild index from log on startup
 *
 * Usage:
 *     java LogStructuredKVServer --node-id node1 --port 50051 --data-dir ./data
 */

package com.sdp.kvstorelog;

import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.stub.StreamObserver;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.logging.Logger;
import java.util.zip.CRC32;

public class LogStructuredKVServer {
    private static final Logger logger = Logger.getLogger(LogStructuredKVServer.class.getName());
    private static final int MAX_SEGMENT_SIZE = 64 * 1024 * 1024; // 64MB
    private static final String TOMBSTONE = "__TOMBSTONE__";

    /**
     * KeyDirEntry points to a value in the log.
     */
    public static class KeyDirEntry {
        public final int segmentId;
        public final long offset;
        public final int size;
        public final long timestamp;

        public KeyDirEntry(int segmentId, long offset, int size, long timestamp) {
            this.segmentId = segmentId;
            this.offset = offset;
            this.size = size;
            this.timestamp = timestamp;
        }
    }

    /**
     * Segment represents a log segment file.
     */
    public static class Segment {
        public final int id;
        public final Path path;
        public RandomAccessFile file;
        public long size;
        public final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

        public Segment(int id, Path path) throws IOException {
            this.id = id;
            this.path = path;
            this.file = new RandomAccessFile(path.toFile(), "rw");
            this.size = file.length();
        }

        public void close() throws IOException {
            file.close();
        }
    }

    /**
     * LogStructuredStore implements the log-structured storage engine.
     */
    public static class LogStructuredStore extends KVServiceGrpc.KVServiceImplBase {
        private final String nodeId;
        private final int port;
        private final Path dataDir;
        private final Map<String, KeyDirEntry> keyDir = new ConcurrentHashMap<>();
        private final Map<Integer, Segment> segments = new ConcurrentHashMap<>();
        private Segment activeSegment;
        private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

        public LogStructuredStore(String nodeId, int port, String dataDir) {
            this.nodeId = nodeId;
            this.port = port;
            this.dataDir = Paths.get(dataDir);
        }

        public void initialize() throws IOException {
            Files.createDirectories(dataDir);
            recover();

            if (activeSegment == null) {
                createNewSegment();
            }

            logger.info("Node " + nodeId + " initialized with data dir: " + dataDir);
        }

        /**
         * Recover from existing log segments.
         * TODO: Rebuild keyDir from log files
         */
        private void recover() throws IOException {
            try (DirectoryStream<Path> stream = Files.newDirectoryStream(dataDir, "segment_*.log")) {
                List<Path> files = new ArrayList<>();
                stream.forEach(files::add);
                Collections.sort(files);

                for (Path path : files) {
                    String filename = path.getFileName().toString();
                    int segmentId = Integer.parseInt(filename.replace("segment_", "").replace(".log", ""));

                    Segment segment = new Segment(segmentId, path);
                    segments.put(segmentId, segment);
                    rebuildFromSegment(segment);
                    activeSegment = segment;
                }
            }
        }

        private void rebuildFromSegment(Segment segment) throws IOException {
            segment.file.seek(0);
            while (segment.file.getFilePointer() < segment.size) {
                long offset = segment.file.getFilePointer();

                try {
                    // Read header: crc(4) + timestamp(8) + keySize(4) + valueSize(4) = 20 bytes
                    int crc = segment.file.readInt();
                    long timestamp = segment.file.readLong();
                    int keySize = segment.file.readInt();
                    int valueSize = segment.file.readInt();

                    byte[] keyBytes = new byte[keySize];
                    segment.file.readFully(keyBytes);
                    String key = new String(keyBytes);

                    byte[] valueBytes = new byte[valueSize];
                    segment.file.readFully(valueBytes);
                    String value = new String(valueBytes);

                    int entrySize = 20 + keySize + valueSize;

                    if (TOMBSTONE.equals(value)) {
                        keyDir.remove(key);
                    } else {
                        keyDir.put(key, new KeyDirEntry(segment.id, offset, entrySize, timestamp));
                    }
                } catch (EOFException e) {
                    break;
                }
            }
        }

        private void createNewSegment() throws IOException {
            lock.writeLock().lock();
            try {
                int segmentId = segments.size();
                Path path = dataDir.resolve(String.format("segment_%06d.log", segmentId));
                Segment segment = new Segment(segmentId, path);
                segments.put(segmentId, segment);
                activeSegment = segment;
            } finally {
                lock.writeLock().unlock();
            }
        }

        /**
         * Append a key-value pair to the log.
         * TODO: Create entry, write to segment, update keyDir
         */
        public void append(String key, String value) throws IOException {
            lock.writeLock().lock();
            try {
                long timestamp = System.nanoTime();
                byte[] keyBytes = key.getBytes();
                byte[] valueBytes = value.getBytes();

                // Calculate CRC
                CRC32 crc = new CRC32();
                ByteBuffer headerBuf = ByteBuffer.allocate(16);
                headerBuf.putLong(timestamp);
                headerBuf.putInt(keyBytes.length);
                headerBuf.putInt(valueBytes.length);
                crc.update(headerBuf.array());
                crc.update(keyBytes);
                crc.update(valueBytes);

                activeSegment.lock.writeLock().lock();
                try {
                    long offset = activeSegment.size;

                    // Write entry
                    activeSegment.file.writeInt((int) crc.getValue());
                    activeSegment.file.writeLong(timestamp);
                    activeSegment.file.writeInt(keyBytes.length);
                    activeSegment.file.writeInt(valueBytes.length);
                    activeSegment.file.write(keyBytes);
                    activeSegment.file.write(valueBytes);

                    int entrySize = 20 + keyBytes.length + valueBytes.length;
                    activeSegment.size += entrySize;

                    // Update keyDir
                    if (!TOMBSTONE.equals(value)) {
                        keyDir.put(key, new KeyDirEntry(activeSegment.id, offset, entrySize, timestamp));
                    } else {
                        keyDir.remove(key);
                    }

                    // Rotate if needed
                    if (activeSegment.size >= MAX_SEGMENT_SIZE) {
                        createNewSegment();
                    }
                } finally {
                    activeSegment.lock.writeLock().unlock();
                }
            } finally {
                lock.writeLock().unlock();
            }
        }

        /**
         * Get a value by key.
         * TODO: Lookup in keyDir, seek to position, read value
         */
        public String get(String key) throws IOException {
            KeyDirEntry entry = keyDir.get(key);
            if (entry == null) {
                return null;
            }

            Segment segment = segments.get(entry.segmentId);
            if (segment == null) {
                return null;
            }

            segment.lock.readLock().lock();
            try {
                segment.file.seek(entry.offset);

                // Skip header
                segment.file.readInt(); // crc
                segment.file.readLong(); // timestamp
                int keySize = segment.file.readInt();
                int valueSize = segment.file.readInt();

                // Skip key
                segment.file.skipBytes(keySize);

                // Read value
                byte[] valueBytes = new byte[valueSize];
                segment.file.readFully(valueBytes);
                String value = new String(valueBytes);

                if (TOMBSTONE.equals(value)) {
                    return null;
                }
                return value;
            } finally {
                segment.lock.readLock().unlock();
            }
        }

        /**
         * Delete a key.
         */
        public void delete(String key) throws IOException {
            append(key, TOMBSTONE);
        }

        /**
         * Compact segments.
         * TODO: Create new segment with only live keys
         */
        public void compact() throws IOException {
            lock.writeLock().lock();
            try {
                int newSegmentId = segments.size();
                Path newPath = dataDir.resolve(String.format("segment_%06d.log", newSegmentId));
                Segment newSegment = new Segment(newSegmentId, newPath);

                Map<String, KeyDirEntry> newKeyDir = new HashMap<>();

                for (Map.Entry<String, KeyDirEntry> entry : keyDir.entrySet()) {
                    String key = entry.getKey();
                    String value = get(key);

                    if (value != null) {
                        long timestamp = System.nanoTime();
                        byte[] keyBytes = key.getBytes();
                        byte[] valueBytes = value.getBytes();

                        CRC32 crc = new CRC32();
                        ByteBuffer headerBuf = ByteBuffer.allocate(16);
                        headerBuf.putLong(timestamp);
                        headerBuf.putInt(keyBytes.length);
                        headerBuf.putInt(valueBytes.length);
                        crc.update(headerBuf.array());
                        crc.update(keyBytes);
                        crc.update(valueBytes);

                        long offset = newSegment.size;

                        newSegment.file.writeInt((int) crc.getValue());
                        newSegment.file.writeLong(timestamp);
                        newSegment.file.writeInt(keyBytes.length);
                        newSegment.file.writeInt(valueBytes.length);
                        newSegment.file.write(keyBytes);
                        newSegment.file.write(valueBytes);

                        int entrySize = 20 + keyBytes.length + valueBytes.length;
                        newSegment.size += entrySize;

                        newKeyDir.put(key, new KeyDirEntry(newSegmentId, offset, entrySize, timestamp));
                    }
                }

                keyDir.clear();
                keyDir.putAll(newKeyDir);
                segments.put(newSegmentId, newSegment);
                activeSegment = newSegment;

            } finally {
                lock.writeLock().unlock();
            }
        }

        // =========================================================================
        // KVService RPC Implementations
        // =========================================================================

        @Override
        public void put(KVStoreLog.PutRequest request,
                       StreamObserver<KVStoreLog.PutResponse> responseObserver) {
            try {
                append(request.getKey(), request.getValue());
                responseObserver.onNext(KVStoreLog.PutResponse.newBuilder()
                    .setSuccess(true)
                    .setStoredOn(nodeId)
                    .build());
            } catch (IOException e) {
                responseObserver.onNext(KVStoreLog.PutResponse.newBuilder()
                    .setSuccess(false)
                    .setError(e.getMessage())
                    .build());
            }
            responseObserver.onCompleted();
        }

        @Override
        public void getValue(KVStoreLog.GetRequest request,
                            StreamObserver<KVStoreLog.GetResponse> responseObserver) {
            try {
                String value = get(request.getKey());
                responseObserver.onNext(KVStoreLog.GetResponse.newBuilder()
                    .setValue(value != null ? value : "")
                    .setFound(value != null)
                    .setServedBy(nodeId)
                    .build());
            } catch (IOException e) {
                responseObserver.onNext(KVStoreLog.GetResponse.newBuilder()
                    .setFound(false)
                    .setError(e.getMessage())
                    .build());
            }
            responseObserver.onCompleted();
        }

        @Override
        public void deleteKey(KVStoreLog.DeleteRequest request,
                             StreamObserver<KVStoreLog.DeleteResponse> responseObserver) {
            try {
                delete(request.getKey());
                responseObserver.onNext(KVStoreLog.DeleteResponse.newBuilder()
                    .setSuccess(true)
                    .build());
            } catch (IOException e) {
                responseObserver.onNext(KVStoreLog.DeleteResponse.newBuilder()
                    .setSuccess(false)
                    .setError(e.getMessage())
                    .build());
            }
            responseObserver.onCompleted();
        }

        public String getNodeId() { return nodeId; }
        public int getKeyCount() { return keyDir.size(); }
        public int getSegmentCount() { return segments.size(); }
    }

    /**
     * StorageService implementation.
     */
    public static class StorageServiceImpl extends StorageServiceGrpc.StorageServiceImplBase {
        private final LogStructuredStore store;

        public StorageServiceImpl(LogStructuredStore store) {
            this.store = store;
        }

        @Override
        public void triggerCompaction(KVStoreLog.CompactionRequest request,
                                     StreamObserver<KVStoreLog.CompactionResponse> responseObserver) {
            try {
                store.compact();
                responseObserver.onNext(KVStoreLog.CompactionResponse.newBuilder()
                    .setSuccess(true)
                    .setKeysRetained(store.getKeyCount())
                    .build());
            } catch (IOException e) {
                responseObserver.onNext(KVStoreLog.CompactionResponse.newBuilder()
                    .setSuccess(false)
                    .setError(e.getMessage())
                    .build());
            }
            responseObserver.onCompleted();
        }

        @Override
        public void getStorageStats(KVStoreLog.GetStorageStatsRequest request,
                                   StreamObserver<KVStoreLog.GetStorageStatsResponse> responseObserver) {
            responseObserver.onNext(KVStoreLog.GetStorageStatsResponse.newBuilder()
                .setTotalKeys(store.getKeyCount())
                .setTotalSegments(store.getSegmentCount())
                .setNodeId(store.getNodeId())
                .build());
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
            System.err.println("Usage: java LogStructuredKVServer --node-id <id> --port <port> --data-dir <path>");
            System.exit(1);
        }

        LogStructuredStore store = new LogStructuredStore(nodeId, port, dataDir);
        store.initialize();

        Server server = ServerBuilder.forPort(port)
                .addService(store)
                .addService(new StorageServiceImpl(store))
                .build()
                .start();

        logger.info("Starting Log-Structured KV Store node " + nodeId + " on port " + port);
        server.awaitTermination();
    }
}
