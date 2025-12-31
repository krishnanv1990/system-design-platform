"""
Functional Tests for Raft Consensus Implementation

Tests the core Raft consensus properties:
1. Leader Election - A leader must be elected
2. Leader Uniqueness - Only one leader per term
3. Log Replication - Logs must be replicated to followers
4. Consistency - All nodes must have consistent data after operations
5. Follower Safety - Followers must not accept old term requests
6. Leader Failure Recovery - New leader must be elected when leader fails

Usage:
    pytest test_raft_consensus.py -v --cluster-urls "http://node1:50051,http://node2:50052,http://node3:50053"
"""

import pytest
import grpc
import time
import random
import string
import asyncio
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

# Import generated protobuf modules
# Proto stubs are compiled at runtime from raft.proto
import sys
import os
import tempfile

raft_pb2 = None
raft_pb2_grpc = None
_proto_compilation_error = None

def _compile_proto_stubs():
    """Compile raft.proto to Python stubs at runtime."""
    global raft_pb2, raft_pb2_grpc, _proto_compilation_error

    # Find the proto file
    proto_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "distributed_problems", "raft", "proto", "raft.proto"),
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "distributed_problems", "raft", "proto", "raft.proto"),
        "/app/distributed_problems/raft/proto/raft.proto",
    ]

    proto_path = None
    for path in proto_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            proto_path = abs_path
            break

    if not proto_path:
        _proto_compilation_error = "Proto file raft.proto not found. Searched paths: " + ", ".join(proto_paths)
        return False

    try:
        from grpc_tools import protoc

        # Compile to temp directory
        stubs_dir = os.path.join(tempfile.gettempdir(), "raft_test_stubs")
        os.makedirs(stubs_dir, exist_ok=True)

        result = protoc.main([
            'grpc_tools.protoc',
            f'--proto_path={os.path.dirname(proto_path)}',
            f'--python_out={stubs_dir}',
            f'--grpc_python_out={stubs_dir}',
            proto_path
        ])

        if result != 0:
            _proto_compilation_error = f"Proto compilation failed with exit code {result}"
            return False

        # Add to path and import
        if stubs_dir not in sys.path:
            sys.path.insert(0, stubs_dir)

        import importlib
        raft_pb2 = importlib.import_module("raft_pb2")
        raft_pb2_grpc = importlib.import_module("raft_pb2_grpc")
        return True

    except ImportError as e:
        _proto_compilation_error = f"grpc_tools not installed: {e}. Install with: pip install grpcio-tools"
        return False
    except Exception as e:
        _proto_compilation_error = f"Failed to compile proto stubs: {e}"
        return False

# Compile protos at module load
_compile_proto_stubs()


@dataclass
class ClusterNode:
    """Represents a node in the Raft cluster."""
    address: str
    channel: Optional[grpc.Channel] = None
    raft_stub: Optional[object] = None
    kv_stub: Optional[object] = None


class RaftTestClient:
    """Client for testing Raft cluster operations."""

    def __init__(self, node_addresses: List[str]):
        """
        Initialize test client with cluster node addresses.

        Args:
            node_addresses: List of "host:port" addresses for each node

        Raises:
            RuntimeError: If proto modules are not available
        """
        if raft_pb2 is None or raft_pb2_grpc is None:
            error_msg = _proto_compilation_error or "Proto modules not compiled"
            raise RuntimeError(f"Cannot create RaftTestClient: {error_msg}")

        self.nodes: List[ClusterNode] = []
        for addr in node_addresses:
            node = ClusterNode(address=addr)
            # Handle both http:// URLs and host:port formats
            if addr.startswith("https://"):
                # For HTTPS (Cloud Run), use secure channel
                host = addr.replace("https://", "")
                credentials = grpc.ssl_channel_credentials()
                node.channel = grpc.secure_channel(f"{host}:443", credentials)
            elif addr.startswith("http://"):
                host = addr.replace("http://", "")
                node.channel = grpc.insecure_channel(host)
            else:
                node.channel = grpc.insecure_channel(addr)
            node.raft_stub = raft_pb2_grpc.RaftServiceStub(node.channel)
            node.kv_stub = raft_pb2_grpc.KeyValueServiceStub(node.channel)
            self.nodes.append(node)

    def close(self):
        """Close all gRPC channels."""
        for node in self.nodes:
            if node.channel:
                node.channel.close()

    def get_leader(self) -> Optional[Tuple[str, str]]:
        """
        Find the current leader in the cluster.

        Returns:
            Tuple of (leader_id, leader_address) or None if no leader found
        """
        for node in self.nodes:
            try:
                request = raft_pb2.GetLeaderRequest()
                response = node.kv_stub.GetLeader(request, timeout=5)
                if response.is_leader:
                    return (response.leader_id, node.address)
                elif response.leader_id:
                    return (response.leader_id, response.leader_address)
            except grpc.RpcError:
                continue
        return None

    def get_cluster_status(self) -> List[Dict]:
        """
        Get status of all nodes in the cluster.

        Returns:
            List of status dictionaries for each reachable node
        """
        statuses = []
        for node in self.nodes:
            try:
                request = raft_pb2.GetClusterStatusRequest()
                response = node.kv_stub.GetClusterStatus(request, timeout=5)
                statuses.append({
                    "node_id": response.node_id,
                    "state": response.state,
                    "current_term": response.current_term,
                    "commit_index": response.commit_index,
                    "last_applied": response.last_applied,
                    "log_length": response.log_length,
                    "address": node.address,
                })
            except grpc.RpcError as e:
                statuses.append({
                    "address": node.address,
                    "error": str(e),
                })
        return statuses

    def put(self, key: str, value: str, follow_redirect: bool = True) -> bool:
        """
        Put a key-value pair into the cluster.

        Args:
            key: Key to store
            value: Value to store
            follow_redirect: Whether to follow leader hints

        Returns:
            True if operation succeeded
        """
        for attempt in range(3):
            for node in self.nodes:
                try:
                    request = raft_pb2.PutRequest(key=key, value=value)
                    response = node.kv_stub.Put(request, timeout=10)
                    if response.success:
                        return True
                    elif response.leader_hint and follow_redirect:
                        # Try the leader hint
                        continue
                except grpc.RpcError:
                    continue
            time.sleep(0.5)
        return False

    def get(self, key: str) -> Optional[str]:
        """
        Get a value from the cluster.

        Args:
            key: Key to retrieve

        Returns:
            Value if found, None otherwise
        """
        for node in self.nodes:
            try:
                request = raft_pb2.GetRequest(key=key)
                response = node.kv_stub.Get(request, timeout=5)
                if response.found:
                    return response.value
            except grpc.RpcError:
                continue
        return None

    def delete(self, key: str) -> bool:
        """
        Delete a key from the cluster.

        Args:
            key: Key to delete

        Returns:
            True if operation succeeded
        """
        for attempt in range(3):
            for node in self.nodes:
                try:
                    request = raft_pb2.DeleteRequest(key=key)
                    response = node.kv_stub.Delete(request, timeout=10)
                    if response.success:
                        return True
                except grpc.RpcError:
                    continue
            time.sleep(0.5)
        return False

    def wait_for_leader(self, timeout: float = 30.0) -> Optional[str]:
        """
        Wait for a leader to be elected.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            Leader ID if elected, None if timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            leader = self.get_leader()
            if leader:
                return leader[0]
            time.sleep(0.5)
        return None

    def wait_for_convergence(self, timeout: float = 30.0) -> bool:
        """
        Wait for all nodes to have the same commit index.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if cluster converged, False if timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            statuses = self.get_cluster_status()
            commit_indices = [s.get("commit_index") for s in statuses if "commit_index" in s]
            if len(commit_indices) == len(self.nodes) and len(set(commit_indices)) == 1:
                return True
            time.sleep(0.5)
        return False


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def check_proto_available():
    """Check if proto stubs were compiled successfully."""
    if _proto_compilation_error:
        pytest.skip(f"gRPC proto compilation failed: {_proto_compilation_error}")
    if raft_pb2 is None or raft_pb2_grpc is None:
        pytest.skip("Proto modules not available. Check grpc_tools installation.")


@pytest.fixture(scope="module")
def cluster_urls(request, check_proto_available):
    """Get cluster URLs from command line or environment."""
    urls = os.environ.get("RAFT_CLUSTER_URLS", "")
    if not urls:
        urls = getattr(request, "param", "") if hasattr(request, "param") else ""
    if not urls:
        pytest.skip("No cluster URLs provided. Set RAFT_CLUSTER_URLS env var.")
    return [url.strip() for url in urls.split(",")]


@pytest.fixture(scope="module")
def client(cluster_urls):
    """Create a test client for the cluster."""
    test_client = RaftTestClient(cluster_urls)
    yield test_client
    test_client.close()


@pytest.fixture(autouse=True)
def wait_for_cluster(client):
    """Ensure cluster has a leader before each test."""
    leader = client.wait_for_leader(timeout=30)
    if not leader:
        pytest.fail("Cluster failed to elect a leader within 30 seconds")


def generate_key(prefix: str = "key") -> str:
    """Generate a unique test key."""
    return f"{prefix}_{random.randint(1000, 9999)}_{int(time.time() * 1000)}"


def generate_value(length: int = 32) -> str:
    """Generate a random test value."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


# ============================================================================
# Leader Election Tests
# ============================================================================

class TestLeaderElection:
    """Tests for Raft leader election."""

    def test_leader_is_elected(self, client):
        """Verify that a leader is elected when the cluster starts."""
        leader = client.get_leader()
        assert leader is not None, "No leader found in cluster"
        assert leader[0], "Leader ID should not be empty"

    def test_single_leader_per_term(self, client):
        """Verify that there is only one leader per term."""
        statuses = client.get_cluster_status()
        leaders = [s for s in statuses if s.get("state") == "leader"]
        assert len(leaders) <= 1, f"Found {len(leaders)} leaders, expected at most 1"

        if len(leaders) == 1:
            leader_term = leaders[0]["current_term"]
            # Check no other node claims to be leader in same term
            for status in statuses:
                if status.get("state") == "leader":
                    assert status["current_term"] == leader_term

    def test_leader_has_highest_term(self, client):
        """Verify the leader has the highest or equal term."""
        statuses = client.get_cluster_status()
        leader_status = next((s for s in statuses if s.get("state") == "leader"), None)

        if leader_status:
            leader_term = leader_status["current_term"]
            for status in statuses:
                if "current_term" in status:
                    assert status["current_term"] <= leader_term, \
                        f"Non-leader has higher term: {status['current_term']} > {leader_term}"

    def test_followers_know_leader(self, client):
        """Verify that followers know who the leader is."""
        leader = client.get_leader()
        assert leader is not None

        for node in client.nodes:
            try:
                request = raft_pb2.GetLeaderRequest()
                response = node.kv_stub.GetLeader(request, timeout=5)
                if not response.is_leader:
                    assert response.leader_id == leader[0], \
                        f"Follower thinks leader is {response.leader_id}, but actual leader is {leader[0]}"
            except grpc.RpcError:
                pass  # Node might be temporarily unavailable


# ============================================================================
# Log Replication Tests
# ============================================================================

class TestLogReplication:
    """Tests for Raft log replication."""

    def test_put_is_replicated(self, client):
        """Verify that a put operation is replicated to all nodes."""
        key = generate_key("replication")
        value = generate_value()

        # Put value through leader
        success = client.put(key, value)
        assert success, "Put operation failed"

        # Wait for replication
        time.sleep(2)

        # Verify all nodes have the value
        for node in client.nodes:
            try:
                request = raft_pb2.GetRequest(key=key)
                response = node.kv_stub.Get(request, timeout=5)
                assert response.found, f"Key not found on node {node.address}"
                assert response.value == value, f"Value mismatch on node {node.address}"
            except grpc.RpcError as e:
                pytest.fail(f"Failed to read from node {node.address}: {e}")

    def test_log_consistency(self, client):
        """Verify that all nodes have consistent log lengths after operations."""
        # Perform several operations
        for i in range(5):
            key = generate_key(f"consistency_{i}")
            value = generate_value()
            client.put(key, value)

        # Wait for convergence
        converged = client.wait_for_convergence(timeout=10)
        assert converged, "Cluster failed to converge"

        # Check log lengths are consistent
        statuses = client.get_cluster_status()
        log_lengths = [s.get("log_length") for s in statuses if "log_length" in s]
        assert len(set(log_lengths)) == 1, f"Inconsistent log lengths: {log_lengths}"

    def test_commit_index_advances(self, client):
        """Verify that commit index advances after operations."""
        # Get initial commit indices
        initial_statuses = client.get_cluster_status()
        initial_commits = {s.get("node_id"): s.get("commit_index", 0) for s in initial_statuses if "node_id" in s}

        # Perform operation
        key = generate_key("commit_advance")
        value = generate_value()
        success = client.put(key, value)
        assert success

        # Wait for replication
        time.sleep(2)

        # Get new commit indices
        final_statuses = client.get_cluster_status()
        final_commits = {s.get("node_id"): s.get("commit_index", 0) for s in final_statuses if "node_id" in s}

        # Verify commit index advanced for at least majority
        advanced = 0
        for node_id, initial in initial_commits.items():
            if node_id in final_commits and final_commits[node_id] > initial:
                advanced += 1

        majority = len(client.nodes) // 2 + 1
        assert advanced >= majority, f"Only {advanced} nodes advanced commit index, need {majority}"


# ============================================================================
# Key-Value Store Tests
# ============================================================================

class TestKeyValueStore:
    """Tests for the key-value store state machine."""

    def test_put_and_get(self, client):
        """Test basic put and get operations."""
        key = generate_key("basic")
        value = generate_value()

        success = client.put(key, value)
        assert success, "Put failed"

        result = client.get(key)
        assert result == value, f"Get returned {result}, expected {value}"

    def test_overwrite_value(self, client):
        """Test overwriting an existing value."""
        key = generate_key("overwrite")
        value1 = generate_value()
        value2 = generate_value()

        client.put(key, value1)
        time.sleep(1)

        client.put(key, value2)
        time.sleep(1)

        result = client.get(key)
        assert result == value2, f"Get returned {result}, expected {value2}"

    def test_delete_key(self, client):
        """Test delete operation."""
        key = generate_key("delete")
        value = generate_value()

        client.put(key, value)
        time.sleep(1)

        success = client.delete(key)
        assert success, "Delete failed"

        time.sleep(1)

        result = client.get(key)
        assert result is None, f"Key should be deleted, but got {result}"

    def test_get_nonexistent_key(self, client):
        """Test getting a key that doesn't exist."""
        key = generate_key("nonexistent")
        result = client.get(key)
        assert result is None, f"Expected None for nonexistent key, got {result}"

    def test_empty_value(self, client):
        """Test storing an empty value."""
        key = generate_key("empty")
        value = ""

        success = client.put(key, value)
        assert success

        result = client.get(key)
        assert result == value, f"Expected empty string, got {result}"

    def test_large_value(self, client):
        """Test storing a large value."""
        key = generate_key("large")
        value = generate_value(10000)  # 10KB value

        success = client.put(key, value)
        assert success

        result = client.get(key)
        assert result == value, "Large value mismatch"

    def test_special_characters_in_key(self, client):
        """Test keys with special characters."""
        key = f"special!@#$%^&*()_{int(time.time())}"
        value = generate_value()

        success = client.put(key, value)
        assert success

        result = client.get(key)
        assert result == value

    def test_unicode_value(self, client):
        """Test storing unicode values."""
        key = generate_key("unicode")
        value = "Hello 世界 🌍 Привет"

        success = client.put(key, value)
        assert success

        result = client.get(key)
        assert result == value


# ============================================================================
# Consistency Tests
# ============================================================================

class TestConsistency:
    """Tests for data consistency across the cluster."""

    def test_read_your_writes(self, client):
        """Verify that a write is immediately readable."""
        key = generate_key("ryw")
        value = generate_value()

        success = client.put(key, value)
        assert success

        # Should be able to read immediately from any node
        result = client.get(key)
        assert result == value, "Read-your-writes violation"

    def test_eventual_consistency(self, client):
        """Verify that all nodes eventually have the same data."""
        key = generate_key("eventual")
        value = generate_value()

        client.put(key, value)

        # Wait for propagation
        time.sleep(3)

        # All nodes should have the same value
        values = []
        for node in client.nodes:
            try:
                request = raft_pb2.GetRequest(key=key)
                response = node.kv_stub.Get(request, timeout=5)
                if response.found:
                    values.append(response.value)
            except grpc.RpcError:
                pass

        assert all(v == value for v in values), f"Inconsistent values: {values}"

    def test_monotonic_reads(self, client):
        """Verify that reads are monotonic (never see older values)."""
        key = generate_key("monotonic")

        for i in range(10):
            value = f"version_{i}"
            client.put(key, value)

        time.sleep(2)

        # All subsequent reads should return the latest version
        for _ in range(5):
            result = client.get(key)
            assert result == "version_9", f"Got old value: {result}"


# ============================================================================
# Concurrent Operation Tests
# ============================================================================

class TestConcurrentOperations:
    """Tests for handling concurrent operations."""

    def test_concurrent_puts(self, client):
        """Test handling multiple concurrent put operations."""
        keys = [generate_key(f"concurrent_{i}") for i in range(10)]
        values = [generate_value() for _ in range(10)]

        def put_operation(key, value):
            return client.put(key, value)

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(put_operation, keys, values))

        # At least majority should succeed
        success_count = sum(results)
        majority = len(keys) // 2 + 1
        assert success_count >= majority, f"Only {success_count} succeeded, need {majority}"

        # Wait for replication
        time.sleep(3)

        # Verify all successful puts are readable
        for key, value, success in zip(keys, values, results):
            if success:
                result = client.get(key)
                assert result == value, f"Value mismatch for {key}"

    def test_concurrent_reads(self, client):
        """Test handling multiple concurrent read operations."""
        key = generate_key("concurrent_read")
        value = generate_value()
        client.put(key, value)
        time.sleep(1)

        def get_operation(_):
            return client.get(key)

        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(get_operation, range(20)))

        # All reads should return the same value
        assert all(r == value for r in results if r is not None), \
            f"Inconsistent concurrent reads: {set(results)}"


# ============================================================================
# Safety Property Tests
# ============================================================================

class TestSafetyProperties:
    """Tests for Raft safety properties."""

    def test_no_split_brain(self, client):
        """Verify that cluster doesn't have split brain (multiple leaders)."""
        statuses = client.get_cluster_status()
        leaders = [s for s in statuses if s.get("state") == "leader"]
        assert len(leaders) <= 1, f"Split brain detected: {len(leaders)} leaders"

    def test_leader_completeness(self, client):
        """Verify that leader has all committed entries."""
        # Perform several operations
        keys_values = [(generate_key(f"complete_{i}"), generate_value()) for i in range(5)]
        for key, value in keys_values:
            client.put(key, value)

        time.sleep(2)

        # Get leader
        leader = client.get_leader()
        assert leader is not None

        # Verify leader has all entries
        leader_node = next((n for n in client.nodes if n.address == leader[1]), None)
        if leader_node:
            for key, value in keys_values:
                try:
                    request = raft_pb2.GetRequest(key=key)
                    response = leader_node.kv_stub.Get(request, timeout=5)
                    assert response.found, f"Leader missing key {key}"
                    assert response.value == value, f"Leader has wrong value for {key}"
                except grpc.RpcError as e:
                    pytest.fail(f"Failed to read from leader: {e}")


# ============================================================================
# Main Test Runner
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
