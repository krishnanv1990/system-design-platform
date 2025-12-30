"""
Raft Consensus Performance Tests.

This test simulates realistic load patterns for a Raft-based distributed system:
- Write operations (through leader)
- Read operations (can be served by any node for eventual consistency)
- Cluster health checks
- Leader election stress testing

Run distributed mode:
  Master: locust -f locustfile_raft.py --master --host=http://raft-leader:50051
  Worker: locust -f locustfile_raft.py --worker --master-host=<master-ip>
"""

from locust import HttpUser, task, between, events, LoadTestShape
from locust.runners import MasterRunner, WorkerRunner
import random
import string
import time
import os
import json
import grpc
from datetime import datetime
from typing import List, Optional
from concurrent import futures

# Try to import generated protobuf files
try:
    import raft_pb2
    import raft_pb2_grpc
    import kv_pb2
    import kv_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False


# Configuration from environment
TARGET_RPS = int(os.getenv("TARGET_RPS", "10000"))
CLUSTER_SIZE = int(os.getenv("CLUSTER_SIZE", "5"))
CONCURRENT_USERS = int(os.getenv("CONCURRENT_USERS", "1000"))

# Raft cluster endpoints
RAFT_NODES = os.getenv("RAFT_NODES", "localhost:50051,localhost:50052,localhost:50053").split(",")


class RaftGrpcClient:
    """gRPC client for Raft cluster operations."""

    def __init__(self, nodes: List[str]):
        self.nodes = nodes
        self.channels = {}
        self.stubs = {}
        self.kv_stubs = {}
        self.leader_id: Optional[str] = None

        for node in nodes:
            try:
                channel = grpc.insecure_channel(node)
                self.channels[node] = channel
                if GRPC_AVAILABLE:
                    self.stubs[node] = raft_pb2_grpc.RaftServiceStub(channel)
                    self.kv_stubs[node] = kv_pb2_grpc.KeyValueServiceStub(channel)
            except Exception as e:
                print(f"Failed to connect to {node}: {e}")

    def find_leader(self) -> Optional[str]:
        """Find the current leader in the cluster."""
        for node, stub in self.stubs.items():
            try:
                if GRPC_AVAILABLE:
                    request = raft_pb2.GetLeaderRequest()
                    response = stub.GetLeader(request, timeout=5)
                    if response.is_leader:
                        self.leader_id = node
                        return node
                    elif response.leader_id:
                        self.leader_id = response.leader_id
                        return response.leader_id
            except Exception:
                continue
        return None

    def put(self, key: str, value: str) -> tuple:
        """Put a key-value pair (must go through leader)."""
        start_time = time.time()
        leader = self.leader_id or self.find_leader()

        if not leader or leader not in self.kv_stubs:
            return (None, (time.time() - start_time) * 1000, "no_leader")

        try:
            if GRPC_AVAILABLE:
                request = kv_pb2.PutRequest(key=key, value=value)
                response = self.kv_stubs[leader].Put(request, timeout=10)
                elapsed = (time.time() - start_time) * 1000
                if response.success:
                    return (response, elapsed, None)
                else:
                    # Leader might have changed
                    self.leader_id = None
                    return (None, elapsed, "not_leader")
        except grpc.RpcError as e:
            elapsed = (time.time() - start_time) * 1000
            self.leader_id = None
            return (None, elapsed, str(e.code()))
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return (None, elapsed, str(e))

        return (None, (time.time() - start_time) * 1000, "grpc_unavailable")

    def get(self, key: str) -> tuple:
        """Get a value by key (can be served by any node)."""
        start_time = time.time()

        # Try any node for reads (eventual consistency)
        node = random.choice(list(self.kv_stubs.keys())) if self.kv_stubs else None

        if not node:
            return (None, (time.time() - start_time) * 1000, "no_nodes")

        try:
            if GRPC_AVAILABLE:
                request = kv_pb2.GetRequest(key=key)
                response = self.kv_stubs[node].Get(request, timeout=5)
                elapsed = (time.time() - start_time) * 1000
                return (response, elapsed, None)
        except grpc.RpcError as e:
            elapsed = (time.time() - start_time) * 1000
            return (None, elapsed, str(e.code()))
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return (None, elapsed, str(e))

        return (None, (time.time() - start_time) * 1000, "grpc_unavailable")

    def delete(self, key: str) -> tuple:
        """Delete a key (must go through leader)."""
        start_time = time.time()
        leader = self.leader_id or self.find_leader()

        if not leader or leader not in self.kv_stubs:
            return (None, (time.time() - start_time) * 1000, "no_leader")

        try:
            if GRPC_AVAILABLE:
                request = kv_pb2.DeleteRequest(key=key)
                response = self.kv_stubs[leader].Delete(request, timeout=10)
                elapsed = (time.time() - start_time) * 1000
                if response.success:
                    return (response, elapsed, None)
                else:
                    self.leader_id = None
                    return (None, elapsed, "not_leader")
        except grpc.RpcError as e:
            elapsed = (time.time() - start_time) * 1000
            self.leader_id = None
            return (None, elapsed, str(e.code()))
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return (None, elapsed, str(e))

        return (None, (time.time() - start_time) * 1000, "grpc_unavailable")

    def get_cluster_status(self) -> dict:
        """Get status of all nodes in the cluster."""
        status = {}
        for node, stub in self.stubs.items():
            try:
                if GRPC_AVAILABLE:
                    request = raft_pb2.GetClusterStatusRequest()
                    response = stub.GetClusterStatus(request, timeout=5)
                    status[node] = {
                        "state": response.state,
                        "term": response.current_term,
                        "commit_index": response.commit_index,
                        "last_log_index": response.last_log_index,
                    }
            except Exception as e:
                status[node] = {"error": str(e)}
        return status


class RaftConsensusUser(HttpUser):
    """
    Simulates realistic user behavior for Raft-based key-value store.

    Traffic patterns:
    - 70% reads (get operations)
    - 25% writes (put operations)
    - 5% deletes
    """

    wait_time = between(0.1, 0.5)
    abstract = True  # Don't instantiate directly

    client: RaftGrpcClient = None
    created_keys: List[str] = []

    def on_start(self):
        """Initialize gRPC client."""
        if RaftConsensusUser.client is None:
            RaftConsensusUser.client = RaftGrpcClient(RAFT_NODES)
        self.created_keys = []

    def _generate_random_key(self) -> str:
        """Generate a random key."""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))

    def _generate_random_value(self) -> str:
        """Generate a random value."""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(10, 100)))

    def _record_result(self, name: str, response_time: float, error: Optional[str]):
        """Record the result to Locust stats."""
        if error:
            events.request.fire(
                request_type="grpc",
                name=name,
                response_time=response_time,
                response_length=0,
                response=None,
                context={},
                exception=Exception(error),
            )
        else:
            events.request.fire(
                request_type="grpc",
                name=name,
                response_time=response_time,
                response_length=0,
                response=None,
                context={},
                exception=None,
            )

    @task(70)
    def get_key(self):
        """Read operation - 70% of traffic."""
        if not self.created_keys:
            # Read a random key (might not exist)
            key = self._generate_random_key()
        else:
            key = random.choice(self.created_keys)

        response, elapsed, error = self.client.get(key)
        self._record_result("GET /kv/{key}", elapsed, error)

    @task(25)
    def put_key(self):
        """Write operation - 25% of traffic."""
        key = self._generate_random_key()
        value = self._generate_random_value()

        response, elapsed, error = self.client.put(key, value)

        if not error:
            self.created_keys.append(key)
            # Keep list manageable
            if len(self.created_keys) > 100:
                self.created_keys.pop(0)

        self._record_result("PUT /kv/{key}", elapsed, error)

    @task(5)
    def delete_key(self):
        """Delete operation - 5% of traffic."""
        if not self.created_keys:
            return

        key = self.created_keys.pop(random.randint(0, len(self.created_keys) - 1))
        response, elapsed, error = self.client.delete(key)
        self._record_result("DELETE /kv/{key}", elapsed, error)


class RaftHttpUser(HttpUser):
    """
    HTTP-based Raft client for when gRPC is not available.
    Uses REST API endpoints that proxy to gRPC.
    """

    wait_time = between(0.1, 0.5)
    created_keys: List[str] = []

    def on_start(self):
        """Initialize user session."""
        self.created_keys = []
        self.leader_url = None

    def _generate_random_key(self) -> str:
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))

    def _generate_random_value(self) -> str:
        return ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(10, 100)))

    def _find_leader(self):
        """Find leader through HTTP health endpoint."""
        try:
            with self.client.get("/api/v1/raft/leader", catch_response=True) as response:
                if response.status_code == 200:
                    data = response.json()
                    self.leader_url = data.get("leader_url")
                    response.success()
                    return True
        except Exception:
            pass
        return False

    @task(70)
    def get_key(self):
        """Read operation - 70% of traffic."""
        if not self.created_keys:
            key = self._generate_random_key()
        else:
            key = random.choice(self.created_keys)

        with self.client.get(
            f"/api/v1/raft/kv/{key}",
            catch_response=True,
            name="/api/v1/raft/kv/{key}"
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            elif response.status_code == 503:
                # Service unavailable - might be during election
                response.success()
            else:
                response.failure(f"Unexpected: {response.status_code}")

    @task(25)
    def put_key(self):
        """Write operation - 25% of traffic."""
        key = self._generate_random_key()
        value = self._generate_random_value()

        with self.client.post(
            "/api/v1/raft/kv",
            json={"key": key, "value": value},
            catch_response=True,
            name="POST /api/v1/raft/kv"
        ) as response:
            if response.status_code in [200, 201]:
                self.created_keys.append(key)
                if len(self.created_keys) > 100:
                    self.created_keys.pop(0)
                response.success()
            elif response.status_code in [503, 307]:
                # Service unavailable or redirect to leader
                response.success()
            else:
                response.failure(f"Unexpected: {response.status_code}")

    @task(5)
    def delete_key(self):
        """Delete operation - 5% of traffic."""
        if not self.created_keys:
            return

        key = self.created_keys.pop(random.randint(0, len(self.created_keys) - 1))

        with self.client.delete(
            f"/api/v1/raft/kv/{key}",
            catch_response=True,
            name="DELETE /api/v1/raft/kv/{key}"
        ) as response:
            if response.status_code in [200, 204, 404]:
                response.success()
            elif response.status_code == 503:
                response.success()
            else:
                response.failure(f"Unexpected: {response.status_code}")


class LeaderElectionStressUser(HttpUser):
    """
    Stress tests leader election by sending requests during instability.
    """

    wait_time = between(0.01, 0.1)  # Very fast
    weight = 1  # Lower weight than normal users

    def on_start(self):
        self.created_keys = []

    @task(80)
    def write_during_instability(self):
        """Test writes during potential leader changes."""
        key = ''.join(random.choices(string.ascii_lowercase, k=10))
        value = f"stress_test_{time.time()}"

        with self.client.post(
            "/api/v1/raft/kv",
            json={"key": key, "value": value},
            catch_response=True,
            name="POST /api/v1/raft/kv [stress]"
        ) as response:
            # Accept various responses during instability
            if response.status_code in [200, 201, 307, 408, 503, 504]:
                response.success()
            else:
                response.failure(f"Unexpected: {response.status_code}")

    @task(20)
    def check_cluster_health(self):
        """Check cluster health during stress."""
        with self.client.get(
            "/api/v1/raft/status",
            catch_response=True,
            name="GET /api/v1/raft/status"
        ) as response:
            if response.status_code in [200, 503]:
                response.success()
            else:
                response.failure(f"Unexpected: {response.status_code}")


class RaftLoadShape(LoadTestShape):
    """
    Custom load shape for Raft testing.

    Stages:
    1. Warm-up: Gradual increase
    2. Normal: Steady state
    3. Leader election stress: Sudden spike to test leader election
    4. Recovery: Back to normal
    5. Peak: Maximum load
    6. Cool-down: Gradual decrease
    """

    stages = [
        {"duration": 30, "users": CONCURRENT_USERS // 10, "spawn_rate": 50},    # Warm-up
        {"duration": 120, "users": CONCURRENT_USERS // 2, "spawn_rate": 100},   # Normal
        {"duration": 60, "users": CONCURRENT_USERS, "spawn_rate": 500},         # Spike
        {"duration": 60, "users": CONCURRENT_USERS // 2, "spawn_rate": 100},    # Recovery
        {"duration": 180, "users": CONCURRENT_USERS, "spawn_rate": 200},        # Peak
        {"duration": 30, "users": CONCURRENT_USERS // 10, "spawn_rate": 50},    # Cool-down
    ]

    def tick(self):
        run_time = self.get_run_time()

        cumulative_time = 0
        for stage in self.stages:
            cumulative_time += stage["duration"]
            if run_time < cumulative_time:
                return (stage["users"], stage["spawn_rate"])

        return None


# Event handlers

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Initialize test environment."""
    if isinstance(environment.runner, MasterRunner):
        print(f"Master node starting - Target: {TARGET_RPS} RPS")
        print(f"Cluster size: {CLUSTER_SIZE} nodes")
        print(f"Raft nodes: {RAFT_NODES}")
    elif isinstance(environment.runner, WorkerRunner):
        print("Worker node connecting to master")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Initialize cluster connection."""
    print(f"Starting Raft performance test against {RAFT_NODES}")

    # Try to find leader
    client = RaftGrpcClient(RAFT_NODES)
    leader = client.find_leader()
    if leader:
        print(f"Found leader: {leader}")
    else:
        print("Warning: Could not find leader - cluster may be initializing")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Save test results."""
    if isinstance(environment.runner, MasterRunner):
        stats = environment.runner.stats

        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "test_type": "raft_consensus",
            "cluster_size": CLUSTER_SIZE,
            "total_requests": stats.total.num_requests,
            "total_failures": stats.total.num_failures,
            "avg_response_time": stats.total.avg_response_time,
            "median_response_time": stats.total.median_response_time,
            "p95_response_time": stats.total.get_response_time_percentile(0.95),
            "p99_response_time": stats.total.get_response_time_percentile(0.99),
            "requests_per_second": stats.total.current_rps,
            "failures_per_second": stats.total.current_fail_per_sec,
        }

        output_file = f"raft_load_test_results_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\nRaft Performance Test Results saved to {output_file}")
        print(f"Total Requests: {results['total_requests']:,}")
        print(f"Total Failures: {results['total_failures']:,}")
        print(f"Avg Response Time: {results['avg_response_time']:.2f}ms")
        print(f"P99 Response Time: {results['p99_response_time']:.2f}ms")
        print(f"RPS: {results['requests_per_second']:.2f}")
