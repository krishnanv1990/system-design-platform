/**
 * B+ Tree KV Store - Java Template
 *
 * This template provides the basic structure for implementing a distributed
 * key-value store using B+ Tree storage.
 *
 * Key concepts:
 * 1. B+ Tree - Balanced tree with all values in leaf nodes
 * 2. Pages - Fixed-size disk blocks for storage
 * 3. Buffer Pool - In-memory page cache
 * 4. WAL - Write-Ahead Logging for transactions
 *
 * Usage:
 *     java BPlusTreeKVServer --node-id node1 --port 50051 --data-dir ./data
 */

package com.sdp.kvstorebtree;

import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.stub.StreamObserver;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.logging.Logger;

public class BPlusTreeKVServer {
    private static final Logger logger = Logger.getLogger(BPlusTreeKVServer.class.getName());
    private static final int PAGE_SIZE = 4096;
    private static final int MAX_KEYS = 100;
    private static final int BUFFER_POOL_CAP = 1000;

    /**
     * B+ Tree Node.
     */
    public static class BPlusTreeNode {
        public int pageId;
        public boolean isLeaf;
        public List<String> keys = new ArrayList<>();
        public List<String> values = new ArrayList<>();  // Only for leaf nodes
        public List<Integer> children = new ArrayList<>();  // Only for internal nodes
        public int next = 0;  // Only for leaf nodes
        public boolean dirty = false;

        public BPlusTreeNode(int pageId, boolean isLeaf) {
            this.pageId = pageId;
            this.isLeaf = isLeaf;
            this.dirty = true;
        }
    }

    /**
     * Buffer Pool for page management.
     */
    public static class BufferPool {
        private final Map<Integer, BPlusTreeNode> pages = new ConcurrentHashMap<>();
        private final LinkedList<Integer> lruList = new LinkedList<>();
        private final int capacity;
        private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

        public BufferPool(int capacity) {
            this.capacity = capacity;
        }

        public BPlusTreeNode get(int pageId) {
            lock.readLock().lock();
            try {
                BPlusTreeNode node = pages.get(pageId);
                if (node != null) {
                    moveToFront(pageId);
                }
                return node;
            } finally {
                lock.readLock().unlock();
            }
        }

        public BPlusTreeNode put(BPlusTreeNode node) {
            lock.writeLock().lock();
            try {
                BPlusTreeNode evicted = null;
                if (pages.size() >= capacity) {
                    evicted = evict();
                }
                pages.put(node.pageId, node);
                lruList.addFirst(node.pageId);
                return evicted;
            } finally {
                lock.writeLock().unlock();
            }
        }

        private void moveToFront(int pageId) {
            lruList.remove(Integer.valueOf(pageId));
            lruList.addFirst(pageId);
        }

        private BPlusTreeNode evict() {
            if (lruList.isEmpty()) return null;

            // Find first clean page
            for (int i = lruList.size() - 1; i >= 0; i--) {
                int id = lruList.get(i);
                BPlusTreeNode node = pages.get(id);
                if (node != null && !node.dirty) {
                    lruList.remove(i);
                    return pages.remove(id);
                }
            }

            // Evict last dirty page
            int id = lruList.removeLast();
            return pages.remove(id);
        }

        public Collection<BPlusTreeNode> getAllPages() {
            return pages.values();
        }
    }

    /**
     * B+ Tree implementation.
     */
    public static class BPlusTree extends KVServiceGrpc.KVServiceImplBase {
        private final String nodeId;
        private final int port;
        private final Path dataDir;
        private int rootPageId = 0;
        private int nextPageId = 1;
        private final BufferPool bufferPool;
        private RandomAccessFile dataFile;
        private RandomAccessFile walFile;
        private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

        public BPlusTree(String nodeId, int port, String dataDir) {
            this.nodeId = nodeId;
            this.port = port;
            this.dataDir = Paths.get(dataDir);
            this.bufferPool = new BufferPool(BUFFER_POOL_CAP);
        }

        public void initialize() throws IOException {
            Files.createDirectories(dataDir);

            dataFile = new RandomAccessFile(dataDir.resolve("btree.dat").toFile(), "rw");
            walFile = new RandomAccessFile(dataDir.resolve("btree.wal").toFile(), "rw");

            if (dataFile.length() >= 8) {
                // Load metadata
                rootPageId = dataFile.readInt();
                nextPageId = dataFile.readInt();
            } else {
                // Create root
                BPlusTreeNode root = new BPlusTreeNode(0, true);
                bufferPool.put(root);
                writePage(root);
                saveMetadata();
            }

            logger.info("Node " + nodeId + " initialized");
        }

        private void saveMetadata() throws IOException {
            dataFile.seek(0);
            dataFile.writeInt(rootPageId);
            dataFile.writeInt(nextPageId);
        }

        private BPlusTreeNode readPage(int pageId) throws IOException {
            BPlusTreeNode node = bufferPool.get(pageId);
            if (node != null) {
                return node;
            }

            // Read from disk
            long offset = 8 + (long) pageId * PAGE_SIZE;
            if (dataFile.length() <= offset) {
                return null;
            }

            dataFile.seek(offset);
            byte[] data = new byte[PAGE_SIZE];
            dataFile.readFully(data);

            node = deserializePage(pageId, data);
            bufferPool.put(node);
            return node;
        }

        private void writePage(BPlusTreeNode node) throws IOException {
            byte[] data = serializePage(node);
            long offset = 8 + (long) node.pageId * PAGE_SIZE;
            dataFile.seek(offset);
            dataFile.write(data);
            node.dirty = false;
        }

        private byte[] serializePage(BPlusTreeNode node) throws IOException {
            ByteArrayOutputStream baos = new ByteArrayOutputStream(PAGE_SIZE);
            DataOutputStream dos = new DataOutputStream(baos);

            dos.writeByte(node.isLeaf ? 1 : 0);
            dos.writeInt(node.keys.size());
            dos.writeInt(node.next);

            for (String key : node.keys) {
                byte[] keyBytes = key.getBytes();
                dos.writeShort(keyBytes.length);
                dos.write(keyBytes);
            }

            if (node.isLeaf) {
                for (String value : node.values) {
                    byte[] valueBytes = value.getBytes();
                    dos.writeShort(valueBytes.length);
                    dos.write(valueBytes);
                }
            } else {
                for (int child : node.children) {
                    dos.writeInt(child);
                }
            }

            byte[] data = baos.toByteArray();
            byte[] result = new byte[PAGE_SIZE];
            System.arraycopy(data, 0, result, 0, Math.min(data.length, PAGE_SIZE));
            return result;
        }

        private BPlusTreeNode deserializePage(int pageId, byte[] data) throws IOException {
            DataInputStream dis = new DataInputStream(new ByteArrayInputStream(data));

            boolean isLeaf = dis.readByte() == 1;
            int numKeys = dis.readInt();
            int next = dis.readInt();

            BPlusTreeNode node = new BPlusTreeNode(pageId, isLeaf);
            node.next = next;
            node.dirty = false;

            for (int i = 0; i < numKeys; i++) {
                int keyLen = dis.readShort();
                byte[] keyBytes = new byte[keyLen];
                dis.readFully(keyBytes);
                node.keys.add(new String(keyBytes));
            }

            if (isLeaf) {
                for (int i = 0; i < numKeys; i++) {
                    int valueLen = dis.readShort();
                    byte[] valueBytes = new byte[valueLen];
                    dis.readFully(valueBytes);
                    node.values.add(new String(valueBytes));
                }
            } else {
                for (int i = 0; i <= numKeys; i++) {
                    node.children.add(dis.readInt());
                }
            }

            return node;
        }

        private int allocatePage() throws IOException {
            int pageId = nextPageId++;
            saveMetadata();
            return pageId;
        }

        private int findChildIndex(BPlusTreeNode node, String key) {
            int idx = Collections.binarySearch(node.keys, key);
            if (idx < 0) {
                idx = -(idx + 1);
            }
            return idx;
        }

        /**
         * Search for a key.
         */
        public String search(String key) throws IOException {
            lock.readLock().lock();
            try {
                BPlusTreeNode node = readPage(rootPageId);
                if (node == null) return null;

                while (!node.isLeaf) {
                    int childIdx = findChildIndex(node, key);
                    node = readPage(node.children.get(childIdx));
                    if (node == null) return null;
                }

                int idx = Collections.binarySearch(node.keys, key);
                if (idx >= 0) {
                    return node.values.get(idx);
                }
                return null;
            } finally {
                lock.readLock().unlock();
            }
        }

        /**
         * Insert a key-value pair.
         */
        public void insert(String key, String value) throws IOException {
            lock.writeLock().lock();
            try {
                writeWAL((byte) 0, key, value);

                BPlusTreeNode root = readPage(rootPageId);
                if (root == null) {
                    root = new BPlusTreeNode(0, true);
                    bufferPool.put(root);
                }

                if (root.keys.size() >= MAX_KEYS) {
                    BPlusTreeNode newRoot = new BPlusTreeNode(allocatePage(), false);
                    newRoot.children.add(rootPageId);
                    splitChild(newRoot, 0);
                    bufferPool.put(newRoot);
                    writePage(newRoot);
                    rootPageId = newRoot.pageId;
                    saveMetadata();
                }

                insertNonFull(rootPageId, key, value);
            } finally {
                lock.writeLock().unlock();
            }
        }

        private void insertNonFull(int pageId, String key, String value) throws IOException {
            BPlusTreeNode node = readPage(pageId);
            if (node == null) return;

            if (node.isLeaf) {
                int idx = Collections.binarySearch(node.keys, key);
                if (idx >= 0) {
                    node.values.set(idx, value);
                } else {
                    idx = -(idx + 1);
                    node.keys.add(idx, key);
                    node.values.add(idx, value);
                }
                node.dirty = true;
                writePage(node);
            } else {
                int childIdx = findChildIndex(node, key);
                BPlusTreeNode child = readPage(node.children.get(childIdx));

                if (child != null && child.keys.size() >= MAX_KEYS) {
                    splitChild(node, childIdx);
                    writePage(node);
                    if (key.compareTo(node.keys.get(childIdx)) > 0) {
                        childIdx++;
                    }
                }

                insertNonFull(node.children.get(childIdx), key, value);
            }
        }

        private void splitChild(BPlusTreeNode parent, int childIdx) throws IOException {
            BPlusTreeNode child = readPage(parent.children.get(childIdx));
            if (child == null) return;

            int mid = child.keys.size() / 2;
            BPlusTreeNode newNode = new BPlusTreeNode(allocatePage(), child.isLeaf);

            if (child.isLeaf) {
                for (int i = mid; i < child.keys.size(); i++) {
                    newNode.keys.add(child.keys.get(i));
                    newNode.values.add(child.values.get(i));
                }
                newNode.next = child.next;
                child.next = newNode.pageId;

                while (child.keys.size() > mid) {
                    child.keys.remove(child.keys.size() - 1);
                    child.values.remove(child.values.size() - 1);
                }

                parent.keys.add(childIdx, newNode.keys.get(0));
            } else {
                String promoteKey = child.keys.get(mid);

                for (int i = mid + 1; i < child.keys.size(); i++) {
                    newNode.keys.add(child.keys.get(i));
                }
                for (int i = mid + 1; i < child.children.size(); i++) {
                    newNode.children.add(child.children.get(i));
                }

                while (child.keys.size() > mid) {
                    child.keys.remove(child.keys.size() - 1);
                }
                while (child.children.size() > mid + 1) {
                    child.children.remove(child.children.size() - 1);
                }

                parent.keys.add(childIdx, promoteKey);
            }

            parent.children.add(childIdx + 1, newNode.pageId);
            bufferPool.put(newNode);
            writePage(child);
            writePage(newNode);
            parent.dirty = true;
        }

        /**
         * Delete a key.
         */
        public void delete(String key) throws IOException {
            lock.writeLock().lock();
            try {
                writeWAL((byte) 1, key, "");

                BPlusTreeNode node = readPage(rootPageId);
                while (node != null && !node.isLeaf) {
                    int childIdx = findChildIndex(node, key);
                    node = readPage(node.children.get(childIdx));
                }

                if (node != null) {
                    int idx = Collections.binarySearch(node.keys, key);
                    if (idx >= 0) {
                        node.keys.remove(idx);
                        node.values.remove(idx);
                        node.dirty = true;
                        writePage(node);
                    }
                }
            } finally {
                lock.writeLock().unlock();
            }
        }

        private void writeWAL(byte op, String key, String value) throws IOException {
            byte[] keyBytes = key.getBytes();
            byte[] valueBytes = value.getBytes();

            walFile.writeByte(op);
            walFile.writeInt(keyBytes.length);
            walFile.writeInt(valueBytes.length);
            walFile.write(keyBytes);
            walFile.write(valueBytes);
            walFile.getFD().sync();
        }

        public void flushBufferPool() throws IOException {
            lock.writeLock().lock();
            try {
                for (BPlusTreeNode node : bufferPool.getAllPages()) {
                    if (node.dirty) {
                        writePage(node);
                    }
                }
                dataFile.getFD().sync();
            } finally {
                lock.writeLock().unlock();
            }
        }

        // =========================================================================
        // KVService RPC Implementations
        // =========================================================================

        @Override
        public void put(KVStoreBTree.PutRequest request,
                       StreamObserver<KVStoreBTree.PutResponse> responseObserver) {
            try {
                insert(request.getKey(), request.getValue());
                responseObserver.onNext(KVStoreBTree.PutResponse.newBuilder()
                    .setSuccess(true)
                    .setStoredOn(nodeId)
                    .build());
            } catch (IOException e) {
                responseObserver.onNext(KVStoreBTree.PutResponse.newBuilder()
                    .setSuccess(false)
                    .setError(e.getMessage())
                    .build());
            }
            responseObserver.onCompleted();
        }

        @Override
        public void get(KVStoreBTree.GetRequest request,
                       StreamObserver<KVStoreBTree.GetResponse> responseObserver) {
            try {
                String value = search(request.getKey());
                responseObserver.onNext(KVStoreBTree.GetResponse.newBuilder()
                    .setValue(value != null ? value : "")
                    .setFound(value != null)
                    .setServedBy(nodeId)
                    .build());
            } catch (IOException e) {
                responseObserver.onNext(KVStoreBTree.GetResponse.newBuilder()
                    .setFound(false)
                    .setError(e.getMessage())
                    .build());
            }
            responseObserver.onCompleted();
        }

        @Override
        public void deleteKey(KVStoreBTree.DeleteRequest request,
                             StreamObserver<KVStoreBTree.DeleteResponse> responseObserver) {
            try {
                delete(request.getKey());
                responseObserver.onNext(KVStoreBTree.DeleteResponse.newBuilder()
                    .setSuccess(true)
                    .build());
            } catch (IOException e) {
                responseObserver.onNext(KVStoreBTree.DeleteResponse.newBuilder()
                    .setSuccess(false)
                    .setError(e.getMessage())
                    .build());
            }
            responseObserver.onCompleted();
        }

        public String getNodeId() { return nodeId; }
        public int getNextPageId() { return nextPageId; }
        public BufferPool getBufferPool() { return bufferPool; }
    }

    /**
     * StorageService implementation.
     */
    public static class StorageServiceImpl extends StorageServiceGrpc.StorageServiceImplBase {
        private final BPlusTree tree;

        public StorageServiceImpl(BPlusTree tree) {
            this.tree = tree;
        }

        @Override
        public void flushBuffer(KVStoreBTree.FlushRequest request,
                               StreamObserver<KVStoreBTree.FlushResponse> responseObserver) {
            try {
                tree.flushBufferPool();
                responseObserver.onNext(KVStoreBTree.FlushResponse.newBuilder()
                    .setSuccess(true)
                    .setPagesFlushed(tree.getBufferPool().getAllPages().size())
                    .build());
            } catch (IOException e) {
                responseObserver.onNext(KVStoreBTree.FlushResponse.newBuilder()
                    .setSuccess(false)
                    .setError(e.getMessage())
                    .build());
            }
            responseObserver.onCompleted();
        }

        @Override
        public void getStorageStats(KVStoreBTree.GetStorageStatsRequest request,
                                   StreamObserver<KVStoreBTree.GetStorageStatsResponse> responseObserver) {
            int dirtyPages = 0;
            for (BPlusTreeNode node : tree.getBufferPool().getAllPages()) {
                if (node.dirty) dirtyPages++;
            }

            responseObserver.onNext(KVStoreBTree.GetStorageStatsResponse.newBuilder()
                .setTotalPages(tree.getNextPageId())
                .setBufferPoolSize(tree.getBufferPool().getAllPages().size())
                .setDirtyPages(dirtyPages)
                .setNodeId(tree.getNodeId())
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
            System.err.println("Usage: java BPlusTreeKVServer --node-id <id> --port <port> --data-dir <path>");
            System.exit(1);
        }

        BPlusTree tree = new BPlusTree(nodeId, port, dataDir);
        tree.initialize();

        Server server = ServerBuilder.forPort(port)
                .addService(tree)
                .addService(new StorageServiceImpl(tree))
                .build()
                .start();

        logger.info("Starting B+ Tree KV Store node " + nodeId + " on port " + port);
        server.awaitTermination();
    }
}
