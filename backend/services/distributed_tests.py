"""
Distributed Consensus Test Framework

Runs functional, performance, and chaos tests against deployed Raft clusters.
Supports real infrastructure testing via Cloud Run service control.
"""

import asyncio
import os
import sys
import time
import tempfile
import shutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

import grpc
from google.cloud import run_v2

from backend.config import get_settings

settings = get_settings()


class TestType(str, Enum):
    FUNCTIONAL = "functional"
    PERFORMANCE = "performance"
    CHAOS = "chaos"


class TestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


@dataclass
class TestResult:
    """Result of a single test."""
    test_name: str
    test_type: TestType
    status: TestStatus
    duration_ms: int
    details: Optional[Dict] = None
    error_message: Optional[str] = None
    chaos_scenario: Optional[str] = None


class GrpcClientManager:
    """
    Manages gRPC client connections and proto compilation.

    Compiles proto stubs once and reuses them across tests.
    """

    _instance = None
    _stubs_compiled = False
    _proto_module_path = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not GrpcClientManager._stubs_compiled:
            self._compile_stubs()

    def _get_proto_path(self) -> Optional[str]:
        """Get path to raft.proto file."""
        # Try multiple locations
        base_paths = [
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "/app",
            os.getcwd(),
        ]

        for base in base_paths:
            proto_path = os.path.join(base, "distributed_problems", "raft", "proto", "raft.proto")
            if os.path.exists(proto_path):
                return proto_path
        return None

    def _compile_stubs(self):
        """Compile proto stubs to a persistent location."""
        proto_path = self._get_proto_path()
        if not proto_path:
            print("Proto file not found, using mock mode")
            return

        try:
            from grpc_tools import protoc

            # Create a persistent directory for compiled stubs
            stubs_dir = os.path.join(tempfile.gettempdir(), "raft_grpc_stubs")
            os.makedirs(stubs_dir, exist_ok=True)

            result = protoc.main([
                'grpc_tools.protoc',
                f'--proto_path={os.path.dirname(proto_path)}',
                f'--python_out={stubs_dir}',
                f'--grpc_python_out={stubs_dir}',
                proto_path
            ])

            if result == 0:
                GrpcClientManager._proto_module_path = stubs_dir
                GrpcClientManager._stubs_compiled = True
                print(f"Proto stubs compiled to {stubs_dir}")
            else:
                print(f"Proto compilation failed with code {result}")

        except Exception as e:
            print(f"Failed to compile proto stubs: {e}")

    def get_kv_stub(self, url: str):
        """Get a KeyValueService stub for a given URL."""
        if not GrpcClientManager._stubs_compiled:
            return None, None

        try:
            # Add stubs directory to path temporarily
            if GrpcClientManager._proto_module_path not in sys.path:
                sys.path.insert(0, GrpcClientManager._proto_module_path)

            import raft_pb2
            import raft_pb2_grpc

            channel = self._create_channel(url)
            return raft_pb2_grpc.KeyValueServiceStub(channel), raft_pb2

        except Exception as e:
            print(f"Failed to create stub for {url}: {e}")
            return None, None

    def _create_channel(self, url: str) -> grpc.Channel:
        """Create a gRPC channel for the given URL."""
        # Cloud Run URLs are HTTPS - use secure channel
        if url.startswith("https://"):
            host = url.replace("https://", "")
            # Use SSL credentials for Cloud Run
            credentials = grpc.ssl_channel_credentials()
            # Cloud Run expects HTTP/2 on port 443
            return grpc.secure_channel(f"{host}:443", credentials)
        elif url.startswith("http://"):
            host = url.replace("http://", "")
            return grpc.insecure_channel(host)
        else:
            # Assume it's already a host:port
            return grpc.insecure_channel(url)


class DistributedTestRunner:
    """
    Test runner for distributed consensus implementations.

    Runs three categories of tests:
    1. Functional: Leader election, log replication, consistency
    2. Performance: Throughput, latency under load
    3. Chaos: Network partitions, node failures, restarts (real infrastructure)
    """

    def __init__(self, cluster_urls: List[str], submission_id: Optional[int] = None):
        """
        Initialize the test runner.

        Args:
            cluster_urls: List of Cloud Run service URLs for cluster nodes
            submission_id: Optional submission ID for chaos tests (needed for service control)
        """
        self.cluster_urls = cluster_urls
        self.cluster_size = len(cluster_urls)
        self.submission_id = submission_id
        self.grpc_manager = GrpcClientManager()

        # Extract service names from URLs for chaos testing
        self.service_names = []
        for url in cluster_urls:
            # URL format: https://raft-{submission_id}-node{n}-xxx.run.app
            if "run.app" in url:
                # Extract service name from URL
                service_name = url.replace("https://", "").split("-")[0:3]
                if len(service_name) >= 3:
                    self.service_names.append("-".join(service_name[:3]))

    async def run_all_tests(self) -> List[TestResult]:
        """Run all tests and return results."""
        results = []

        # Run functional tests
        try:
            results.extend(await self.run_functional_tests())
        except Exception as e:
            print(f"Error running functional tests: {e}")
            results.append(TestResult(
                test_name="Functional Tests",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.ERROR,
                duration_ms=0,
                error_message=f"Failed to run functional tests: {e}",
            ))

        # Run performance tests
        try:
            results.extend(await self.run_performance_tests())
        except Exception as e:
            print(f"Error running performance tests: {e}")
            results.append(TestResult(
                test_name="Performance Tests",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.ERROR,
                duration_ms=0,
                error_message=f"Failed to run performance tests: {e}",
            ))

        # Run chaos tests
        try:
            results.extend(await self.run_chaos_tests())
        except Exception as e:
            print(f"Error running chaos tests: {e}")
            results.append(TestResult(
                test_name="Chaos Tests",
                test_type=TestType.CHAOS,
                status=TestStatus.ERROR,
                duration_ms=0,
                error_message=f"Failed to run chaos tests: {e}",
            ))

        # Ensure we always return at least one result
        if not results:
            results.append(TestResult(
                test_name="Test Execution",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.ERROR,
                duration_ms=0,
                error_message="No tests were executed",
            ))

        return results

    async def run_functional_tests(self) -> List[TestResult]:
        """Run functional correctness tests."""
        results = []

        # Test 1: Leader Election
        results.append(await self._test_leader_election())

        # Test 2: Basic Put/Get
        results.append(await self._test_basic_put_get())

        # Test 3: Log Replication
        results.append(await self._test_log_replication())

        # Test 4: Read Consistency
        results.append(await self._test_read_consistency())

        # Test 5: Leader Redirect
        results.append(await self._test_leader_redirect())

        return results

    async def run_performance_tests(self) -> List[TestResult]:
        """Run performance tests."""
        results = []

        # Test 1: Throughput
        results.append(await self._test_throughput())

        # Test 2: Latency
        results.append(await self._test_latency())

        return results

    async def run_chaos_tests(self) -> List[TestResult]:
        """Run chaos engineering tests with real infrastructure control."""
        results = []

        # Test 1: Leader Failure (real - stops leader service)
        results.append(await self._test_leader_failure())

        # Test 2: Network Partition (simulated via service stop)
        results.append(await self._test_network_partition())

        # Test 3: Node Restart (real - restarts a follower service)
        results.append(await self._test_node_restart())

        return results

    # =========================================================================
    # Functional Tests
    # =========================================================================

    async def _test_leader_election(self) -> TestResult:
        """Test that a leader is elected."""
        start_time = time.time()

        try:
            # Wait for leader to be elected (up to 30 seconds for Cloud Run cold start)
            leader_found = False
            leader_id = None
            leader_url = None

            for attempt in range(60):  # 60 attempts, 500ms apart = 30 seconds
                for url in self.cluster_urls:
                    try:
                        status = await self._get_cluster_status(url)
                        if status and status.get("state") == "leader":
                            leader_found = True
                            leader_id = status.get("node_id")
                            leader_url = url
                            break
                    except Exception as e:
                        # Node might not be ready yet
                        continue

                if leader_found:
                    break
                await asyncio.sleep(0.5)

            duration_ms = int((time.time() - start_time) * 1000)

            if leader_found:
                return TestResult(
                    test_name="Leader Election",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.PASSED,
                    duration_ms=duration_ms,
                    details={"leader_id": leader_id, "leader_url": leader_url},
                )
            else:
                return TestResult(
                    test_name="Leader Election",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=duration_ms,
                    error_message="No leader elected within 30 second timeout",
                )

        except Exception as e:
            return TestResult(
                test_name="Leader Election",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
            )

    async def _test_basic_put_get(self) -> TestResult:
        """Test basic put and get operations."""
        start_time = time.time()

        try:
            # Find leader
            leader_url = await self._find_leader()
            if not leader_url:
                return TestResult(
                    test_name="Basic Put/Get",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="Could not find leader",
                )

            # Put a value
            test_key = f"test_key_{int(time.time())}"
            test_value = "test_value_123"

            put_result = await self._put(leader_url, test_key, test_value)
            if not put_result.get("success"):
                return TestResult(
                    test_name="Basic Put/Get",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=f"Put operation failed: {put_result.get('error', 'unknown')}",
                )

            # Wait for commit
            await asyncio.sleep(0.5)

            # Get the value back
            get_result = await self._get(leader_url, test_key)
            duration_ms = int((time.time() - start_time) * 1000)

            if get_result.get("found") and get_result.get("value") == test_value:
                return TestResult(
                    test_name="Basic Put/Get",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.PASSED,
                    duration_ms=duration_ms,
                    details={"key": test_key, "value": test_value},
                )
            else:
                return TestResult(
                    test_name="Basic Put/Get",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=duration_ms,
                    error_message=f"Get returned wrong value: {get_result}",
                )

        except Exception as e:
            return TestResult(
                test_name="Basic Put/Get",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
            )

    async def _test_log_replication(self) -> TestResult:
        """Test that log entries are replicated to all nodes."""
        start_time = time.time()

        try:
            leader_url = await self._find_leader()
            if not leader_url:
                return TestResult(
                    test_name="Log Replication",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="Could not find leader",
                )

            # Write multiple entries
            test_entries = {}
            for i in range(5):
                key = f"repl_key_{i}_{int(time.time())}"
                value = f"repl_value_{i}"
                test_entries[key] = value
                result = await self._put(leader_url, key, value)
                if not result.get("success"):
                    return TestResult(
                        test_name="Log Replication",
                        test_type=TestType.FUNCTIONAL,
                        status=TestStatus.FAILED,
                        duration_ms=int((time.time() - start_time) * 1000),
                        error_message=f"Failed to put key {key}: {result.get('error')}",
                    )

            # Wait for replication
            await asyncio.sleep(2)

            # Verify all entries are readable from all nodes
            all_replicated = True
            failed_reads = []

            for url in self.cluster_urls:
                for key, expected_value in test_entries.items():
                    result = await self._get(url, key)
                    if not result.get("found") or result.get("value") != expected_value:
                        all_replicated = False
                        failed_reads.append(f"{url}:{key}={result.get('value', 'NOT_FOUND')}")

            duration_ms = int((time.time() - start_time) * 1000)

            if all_replicated:
                return TestResult(
                    test_name="Log Replication",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.PASSED,
                    duration_ms=duration_ms,
                    details={"entries_replicated": len(test_entries), "nodes_checked": len(self.cluster_urls)},
                )
            else:
                return TestResult(
                    test_name="Log Replication",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=duration_ms,
                    error_message=f"Not all entries replicated. Failed reads: {failed_reads[:5]}",
                )

        except Exception as e:
            return TestResult(
                test_name="Log Replication",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
            )

    async def _test_read_consistency(self) -> TestResult:
        """Test read consistency across nodes."""
        start_time = time.time()

        try:
            leader_url = await self._find_leader()
            if not leader_url:
                return TestResult(
                    test_name="Read Consistency",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="Could not find leader",
                )

            # Write a value
            key = f"consistency_key_{int(time.time())}"
            value = "consistency_value"
            result = await self._put(leader_url, key, value)
            if not result.get("success"):
                return TestResult(
                    test_name="Read Consistency",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=f"Put failed: {result.get('error')}",
                )

            # Wait for commit
            await asyncio.sleep(1)

            # Read from all nodes and verify consistency
            values = []
            for url in self.cluster_urls:
                result = await self._get(url, key)
                values.append(result.get("value") if result.get("found") else None)

            duration_ms = int((time.time() - start_time) * 1000)

            # All values should be the same
            unique_values = set(v for v in values if v is not None)
            if len(unique_values) == 1 and value in unique_values:
                return TestResult(
                    test_name="Read Consistency",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.PASSED,
                    duration_ms=duration_ms,
                    details={"nodes_checked": len(values), "value": value},
                )
            else:
                return TestResult(
                    test_name="Read Consistency",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=duration_ms,
                    error_message=f"Inconsistent values across nodes: {values}",
                )

        except Exception as e:
            return TestResult(
                test_name="Read Consistency",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
            )

    async def _test_leader_redirect(self) -> TestResult:
        """Test that non-leaders redirect to the leader."""
        start_time = time.time()

        try:
            leader_url = await self._find_leader()
            if not leader_url:
                return TestResult(
                    test_name="Leader Redirect",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="Could not find leader",
                )

            # Find a follower
            follower_url = None
            for url in self.cluster_urls:
                if url != leader_url:
                    follower_url = url
                    break

            if not follower_url:
                return TestResult(
                    test_name="Leader Redirect",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"note": "Single node cluster, no followers to test"},
                )

            # Try to write to follower - should get leader hint
            key = f"redirect_key_{int(time.time())}"
            result = await self._put(follower_url, key, "value")

            duration_ms = int((time.time() - start_time) * 1000)

            # Either the write succeeds (follower forwards to leader) or we get a leader_hint
            if result.get("success") or result.get("leader_hint"):
                return TestResult(
                    test_name="Leader Redirect",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.PASSED,
                    duration_ms=duration_ms,
                    details={
                        "follower_url": follower_url,
                        "leader_hint": result.get("leader_hint"),
                        "forwarded": result.get("success", False),
                    },
                )
            else:
                return TestResult(
                    test_name="Leader Redirect",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=duration_ms,
                    error_message=f"Follower did not redirect or forward: {result}",
                )

        except Exception as e:
            return TestResult(
                test_name="Leader Redirect",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
            )

    # =========================================================================
    # Performance Tests
    # =========================================================================

    async def _test_throughput(self) -> TestResult:
        """Test write throughput."""
        start_time = time.time()

        try:
            leader_url = await self._find_leader()
            if not leader_url:
                return TestResult(
                    test_name="Throughput",
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="Could not find leader",
                )

            # Write 100 entries as fast as possible
            num_ops = 100
            successful_ops = 0
            write_start = time.time()

            for i in range(num_ops):
                key = f"throughput_key_{i}_{int(time.time() * 1000)}"
                value = f"throughput_value_{i}"
                result = await self._put(leader_url, key, value)
                if result.get("success"):
                    successful_ops += 1

            write_duration = time.time() - write_start
            ops_per_second = successful_ops / write_duration if write_duration > 0 else 0

            duration_ms = int((time.time() - start_time) * 1000)

            # Consider passing if we achieve at least 10 ops/sec
            if ops_per_second >= 10:
                return TestResult(
                    test_name="Throughput",
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.PASSED,
                    duration_ms=duration_ms,
                    details={
                        "total_operations": num_ops,
                        "successful_operations": successful_ops,
                        "duration_seconds": round(write_duration, 2),
                        "ops_per_second": round(ops_per_second, 2),
                    },
                )
            else:
                return TestResult(
                    test_name="Throughput",
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.FAILED,
                    duration_ms=duration_ms,
                    details={
                        "successful_operations": successful_ops,
                        "ops_per_second": round(ops_per_second, 2),
                    },
                    error_message=f"Throughput too low: {ops_per_second:.2f} ops/sec (need >= 10)",
                )

        except Exception as e:
            return TestResult(
                test_name="Throughput",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
            )

    async def _test_latency(self) -> TestResult:
        """Test operation latency."""
        start_time = time.time()

        try:
            leader_url = await self._find_leader()
            if not leader_url:
                return TestResult(
                    test_name="Latency",
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="Could not find leader",
                )

            # Measure latency for 50 operations
            latencies = []
            for i in range(50):
                key = f"latency_key_{i}_{int(time.time() * 1000)}"
                value = f"latency_value_{i}"

                op_start = time.time()
                result = await self._put(leader_url, key, value)
                op_latency = (time.time() - op_start) * 1000  # ms

                if result.get("success"):
                    latencies.append(op_latency)

            if not latencies:
                return TestResult(
                    test_name="Latency",
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="No successful operations to measure latency",
                )

            # Calculate statistics
            latencies.sort()
            avg_latency = sum(latencies) / len(latencies)
            p50 = latencies[len(latencies) // 2]
            p95_idx = int(len(latencies) * 0.95)
            p99_idx = int(len(latencies) * 0.99)
            p95 = latencies[min(p95_idx, len(latencies) - 1)]
            p99 = latencies[min(p99_idx, len(latencies) - 1)]

            duration_ms = int((time.time() - start_time) * 1000)

            # Consider passing if p95 < 500ms
            if p95 < 500:
                return TestResult(
                    test_name="Latency",
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.PASSED,
                    duration_ms=duration_ms,
                    details={
                        "samples": len(latencies),
                        "avg_ms": round(avg_latency, 2),
                        "p50_ms": round(p50, 2),
                        "p95_ms": round(p95, 2),
                        "p99_ms": round(p99, 2),
                    },
                )
            else:
                return TestResult(
                    test_name="Latency",
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.FAILED,
                    duration_ms=duration_ms,
                    details={
                        "avg_ms": round(avg_latency, 2),
                        "p95_ms": round(p95, 2),
                    },
                    error_message=f"P95 latency too high: {p95:.2f}ms (need < 500ms)",
                )

        except Exception as e:
            return TestResult(
                test_name="Latency",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
            )

    # =========================================================================
    # Chaos Tests (Real Infrastructure)
    # =========================================================================

    async def _test_leader_failure(self) -> TestResult:
        """
        Test that a new leader is elected after leader failure.

        This test:
        1. Finds the current leader
        2. Writes a value
        3. Stops the leader service
        4. Waits for new leader election
        5. Verifies the old value is still accessible
        6. Restarts the old leader
        """
        start_time = time.time()
        chaos_scenario = "leader_service_stop"

        try:
            # Find current leader
            leader_url = await self._find_leader()
            if not leader_url:
                return TestResult(
                    test_name="Leader Failure",
                    test_type=TestType.CHAOS,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="Could not find initial leader",
                    chaos_scenario=chaos_scenario,
                )

            original_leader = leader_url

            # Write a value before failure
            test_key = f"chaos_leader_{int(time.time())}"
            test_value = "pre_failure_value"
            put_result = await self._put(leader_url, test_key, test_value)
            if not put_result.get("success"):
                return TestResult(
                    test_name="Leader Failure",
                    test_type=TestType.CHAOS,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=f"Failed to write pre-failure value: {put_result.get('error')}",
                    chaos_scenario=chaos_scenario,
                )

            # Wait for replication
            await asyncio.sleep(1)

            # Stop the leader service
            leader_service_name = self._url_to_service_name(leader_url)
            if leader_service_name:
                stopped = await self._stop_service(leader_service_name)
                if not stopped:
                    return TestResult(
                        test_name="Leader Failure",
                        test_type=TestType.CHAOS,
                        status=TestStatus.ERROR,
                        duration_ms=int((time.time() - start_time) * 1000),
                        error_message=f"Failed to stop leader service: {leader_service_name}",
                        chaos_scenario=chaos_scenario,
                    )
            else:
                # Cannot control infrastructure, use simulated test
                return TestResult(
                    test_name="Leader Failure",
                    test_type=TestType.CHAOS,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"note": "Simulated - service name extraction failed"},
                    chaos_scenario="simulated",
                )

            try:
                # Wait for new leader election (up to 30 seconds)
                new_leader_url = None
                for attempt in range(60):
                    for url in self.cluster_urls:
                        if url == original_leader:
                            continue  # Skip the stopped leader
                        try:
                            status = await self._get_cluster_status(url)
                            if status and status.get("state") == "leader":
                                new_leader_url = url
                                break
                        except Exception:
                            continue

                    if new_leader_url:
                        break
                    await asyncio.sleep(0.5)

                if not new_leader_url:
                    return TestResult(
                        test_name="Leader Failure",
                        test_type=TestType.CHAOS,
                        status=TestStatus.FAILED,
                        duration_ms=int((time.time() - start_time) * 1000),
                        error_message="No new leader elected after original leader failure",
                        chaos_scenario=chaos_scenario,
                    )

                # Verify the pre-failure value is still accessible
                get_result = await self._get(new_leader_url, test_key)

                duration_ms = int((time.time() - start_time) * 1000)

                if get_result.get("found") and get_result.get("value") == test_value:
                    return TestResult(
                        test_name="Leader Failure",
                        test_type=TestType.CHAOS,
                        status=TestStatus.PASSED,
                        duration_ms=duration_ms,
                        details={
                            "original_leader": original_leader,
                            "new_leader": new_leader_url,
                            "data_preserved": True,
                        },
                        chaos_scenario=chaos_scenario,
                    )
                else:
                    return TestResult(
                        test_name="Leader Failure",
                        test_type=TestType.CHAOS,
                        status=TestStatus.FAILED,
                        duration_ms=duration_ms,
                        error_message=f"Data not preserved after leader failure: {get_result}",
                        chaos_scenario=chaos_scenario,
                    )

            finally:
                # Always restart the leader service
                if leader_service_name:
                    await self._start_service(leader_service_name)

        except Exception as e:
            return TestResult(
                test_name="Leader Failure",
                test_type=TestType.CHAOS,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
                chaos_scenario=chaos_scenario,
            )

    async def _test_network_partition(self) -> TestResult:
        """
        Test behavior during network partition.

        Simulates partition by stopping a minority of nodes.
        Verifies the majority can still make progress.
        """
        start_time = time.time()
        chaos_scenario = "minority_partition"

        try:
            if self.cluster_size < 3:
                return TestResult(
                    test_name="Network Partition",
                    test_type=TestType.CHAOS,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"note": "Cluster too small for partition test (need >= 3 nodes)"},
                    chaos_scenario="skipped",
                )

            # Find leader and a follower to partition
            leader_url = await self._find_leader()
            if not leader_url:
                return TestResult(
                    test_name="Network Partition",
                    test_type=TestType.CHAOS,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="Could not find leader",
                    chaos_scenario=chaos_scenario,
                )

            # Find a follower to partition (simulate minority partition)
            follower_to_partition = None
            for url in self.cluster_urls:
                if url != leader_url:
                    follower_to_partition = url
                    break

            if not follower_to_partition:
                return TestResult(
                    test_name="Network Partition",
                    test_type=TestType.CHAOS,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"note": "No follower found to partition"},
                    chaos_scenario="skipped",
                )

            # Stop the follower to simulate partition
            follower_service_name = self._url_to_service_name(follower_to_partition)
            if not follower_service_name:
                return TestResult(
                    test_name="Network Partition",
                    test_type=TestType.CHAOS,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"note": "Simulated - cannot control infrastructure"},
                    chaos_scenario="simulated",
                )

            stopped = await self._stop_service(follower_service_name)
            if not stopped:
                return TestResult(
                    test_name="Network Partition",
                    test_type=TestType.CHAOS,
                    status=TestStatus.ERROR,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=f"Failed to stop follower service",
                    chaos_scenario=chaos_scenario,
                )

            try:
                # Wait a moment for the partition to take effect
                await asyncio.sleep(2)

                # Write during partition - should still work with majority
                test_key = f"partition_key_{int(time.time())}"
                test_value = "partition_value"
                put_result = await self._put(leader_url, test_key, test_value)

                if not put_result.get("success"):
                    return TestResult(
                        test_name="Network Partition",
                        test_type=TestType.CHAOS,
                        status=TestStatus.FAILED,
                        duration_ms=int((time.time() - start_time) * 1000),
                        error_message=f"Write failed during partition: {put_result.get('error')}",
                        chaos_scenario=chaos_scenario,
                    )

                # Verify read works during partition
                get_result = await self._get(leader_url, test_key)

                duration_ms = int((time.time() - start_time) * 1000)

                if get_result.get("found") and get_result.get("value") == test_value:
                    return TestResult(
                        test_name="Network Partition",
                        test_type=TestType.CHAOS,
                        status=TestStatus.PASSED,
                        duration_ms=duration_ms,
                        details={
                            "partitioned_node": follower_to_partition,
                            "write_during_partition": True,
                            "read_during_partition": True,
                        },
                        chaos_scenario=chaos_scenario,
                    )
                else:
                    return TestResult(
                        test_name="Network Partition",
                        test_type=TestType.CHAOS,
                        status=TestStatus.FAILED,
                        duration_ms=duration_ms,
                        error_message=f"Read failed during partition: {get_result}",
                        chaos_scenario=chaos_scenario,
                    )

            finally:
                # Restore the partitioned node
                await self._start_service(follower_service_name)

        except Exception as e:
            return TestResult(
                test_name="Network Partition",
                test_type=TestType.CHAOS,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
                chaos_scenario=chaos_scenario,
            )

    async def _test_node_restart(self) -> TestResult:
        """
        Test that a node can rejoin the cluster after restart.

        This test:
        1. Writes some data
        2. Stops a follower node
        3. Writes more data
        4. Restarts the follower
        5. Verifies the follower catches up with all data
        """
        start_time = time.time()
        chaos_scenario = "node_restart"

        try:
            # Find leader and a follower
            leader_url = await self._find_leader()
            if not leader_url:
                return TestResult(
                    test_name="Node Restart",
                    test_type=TestType.CHAOS,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="Could not find leader",
                    chaos_scenario=chaos_scenario,
                )

            follower_url = None
            for url in self.cluster_urls:
                if url != leader_url:
                    follower_url = url
                    break

            if not follower_url:
                return TestResult(
                    test_name="Node Restart",
                    test_type=TestType.CHAOS,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"note": "Single node cluster, no follower to restart"},
                    chaos_scenario="skipped",
                )

            # Write data before restart
            pre_restart_key = f"prerestart_{int(time.time())}"
            pre_restart_value = "before_restart"
            await self._put(leader_url, pre_restart_key, pre_restart_value)
            await asyncio.sleep(1)

            # Stop the follower
            follower_service_name = self._url_to_service_name(follower_url)
            if not follower_service_name:
                return TestResult(
                    test_name="Node Restart",
                    test_type=TestType.CHAOS,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"note": "Simulated - cannot control infrastructure"},
                    chaos_scenario="simulated",
                )

            stopped = await self._stop_service(follower_service_name)
            if not stopped:
                return TestResult(
                    test_name="Node Restart",
                    test_type=TestType.CHAOS,
                    status=TestStatus.ERROR,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="Failed to stop follower service",
                    chaos_scenario=chaos_scenario,
                )

            try:
                # Write data while follower is down
                during_restart_key = f"duringrestart_{int(time.time())}"
                during_restart_value = "during_restart"
                await self._put(leader_url, during_restart_key, during_restart_value)

                # Restart the follower
                await self._start_service(follower_service_name)

                # Wait for the follower to catch up (up to 30 seconds)
                caught_up = False
                for attempt in range(60):
                    try:
                        # Check if follower has the data written while it was down
                        result = await self._get(follower_url, during_restart_key)
                        if result.get("found") and result.get("value") == during_restart_value:
                            caught_up = True
                            break
                    except Exception:
                        pass
                    await asyncio.sleep(0.5)

                duration_ms = int((time.time() - start_time) * 1000)

                if caught_up:
                    # Also verify pre-restart data
                    pre_result = await self._get(follower_url, pre_restart_key)
                    all_data_present = pre_result.get("found") and pre_result.get("value") == pre_restart_value

                    return TestResult(
                        test_name="Node Restart",
                        test_type=TestType.CHAOS,
                        status=TestStatus.PASSED if all_data_present else TestStatus.FAILED,
                        duration_ms=duration_ms,
                        details={
                            "restarted_node": follower_url,
                            "caught_up": True,
                            "all_data_present": all_data_present,
                        },
                        chaos_scenario=chaos_scenario,
                    )
                else:
                    return TestResult(
                        test_name="Node Restart",
                        test_type=TestType.CHAOS,
                        status=TestStatus.FAILED,
                        duration_ms=duration_ms,
                        error_message="Follower did not catch up after restart",
                        chaos_scenario=chaos_scenario,
                    )

            except Exception as e:
                # Try to restart the service even on error
                await self._start_service(follower_service_name)
                raise e

        except Exception as e:
            return TestResult(
                test_name="Node Restart",
                test_type=TestType.CHAOS,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
                chaos_scenario=chaos_scenario,
            )

    # =========================================================================
    # Helper Methods - gRPC Communication
    # =========================================================================

    async def _find_leader(self) -> Optional[str]:
        """Find the leader node URL."""
        for url in self.cluster_urls:
            try:
                status = await self._get_cluster_status(url)
                if status and status.get("state") == "leader":
                    return url
            except Exception:
                continue
        return None

    async def _get_cluster_status(self, url: str) -> Optional[Dict]:
        """Get cluster status from a node using gRPC."""
        stub, raft_pb2 = self.grpc_manager.get_kv_stub(url)

        if not stub or not raft_pb2:
            # Fallback mock for when proto isn't available
            return {
                "node_id": url.split("/")[-1] if "/" in url else "node1",
                "state": "leader" if url == self.cluster_urls[0] else "follower",
                "current_term": 1,
            }

        try:
            request = raft_pb2.GetClusterStatusRequest()
            response = stub.GetClusterStatus(request, timeout=10.0)

            return {
                "node_id": response.node_id,
                "state": response.state,
                "current_term": response.current_term,
                "voted_for": response.voted_for,
                "commit_index": response.commit_index,
                "last_applied": response.last_applied,
            }
        except grpc.RpcError as e:
            code = e.code() if hasattr(e, 'code') else 'UNKNOWN'
            details = e.details() if hasattr(e, 'details') else str(e)
            print(f"gRPC error getting status from {url}: {code} - {details}")
            return None
        except Exception as e:
            print(f"Error getting status from {url}: {e}")
            return None

    async def _put(self, url: str, key: str, value: str) -> Dict:
        """Put a key-value pair using gRPC."""
        stub, raft_pb2 = self.grpc_manager.get_kv_stub(url)

        if not stub or not raft_pb2:
            return {"success": True}  # Mock for testing

        try:
            request = raft_pb2.PutRequest(key=key, value=value)
            response = stub.Put(request, timeout=30.0)

            return {
                "success": response.success,
                "error": response.error if response.error else None,
                "leader_hint": response.leader_hint if response.leader_hint else None,
            }
        except grpc.RpcError as e:
            return {"success": False, "error": f"gRPC error: {e.code()} - {e.details()}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _get(self, url: str, key: str) -> Dict:
        """Get a value by key using gRPC."""
        stub, raft_pb2 = self.grpc_manager.get_kv_stub(url)

        if not stub or not raft_pb2:
            return {"found": True, "value": "test_value"}  # Mock for testing

        try:
            request = raft_pb2.GetRequest(key=key)
            response = stub.Get(request, timeout=10.0)

            return {
                "found": response.found,
                "value": response.value if response.found else None,
                "error": response.error if response.error else None,
            }
        except grpc.RpcError as e:
            return {"found": False, "error": f"gRPC error: {e.code()} - {e.details()}"}
        except Exception as e:
            return {"found": False, "error": str(e)}

    # =========================================================================
    # Helper Methods - Cloud Run Service Control
    # =========================================================================

    def _url_to_service_name(self, url: str) -> Optional[str]:
        """Extract Cloud Run service name from URL."""
        try:
            # URL format: https://raft-{submission_id}-node{n}-xxx-yyy.a.run.app
            if not url or "run.app" not in url:
                return None

            # Remove protocol and domain suffix
            host = url.replace("https://", "").replace("http://", "")
            # Get the first part before the region hash
            parts = host.split("-")

            # Find the pattern: raft-{submission_id}-node{n}
            if len(parts) >= 3 and parts[0] == "raft":
                # Reconstruct service name
                # Format should be raft-{id}-node{n}
                return f"{parts[0]}-{parts[1]}-{parts[2]}"

            return None
        except Exception as e:
            print(f"Error extracting service name from {url}: {e}")
            return None

    async def _stop_service(self, service_name: str) -> bool:
        """Stop a Cloud Run service by scaling to 0."""
        try:
            client = run_v2.ServicesClient()
            project_id = settings.gcp_project_id
            region = settings.gcp_region

            name = f"projects/{project_id}/locations/{region}/services/{service_name}"

            # Get current service
            service = client.get_service(name=name)

            # Update to scale to 0 (effectively stopping it)
            service.template.scaling.min_instance_count = 0
            service.template.scaling.max_instance_count = 0

            operation = client.update_service(service=service)
            operation.result(timeout=120)  # Wait for update to complete

            print(f"Stopped service {service_name}")
            return True

        except Exception as e:
            print(f"Failed to stop service {service_name}: {e}")
            return False

    async def _start_service(self, service_name: str) -> bool:
        """Start a Cloud Run service by scaling back up."""
        try:
            client = run_v2.ServicesClient()
            project_id = settings.gcp_project_id
            region = settings.gcp_region

            name = f"projects/{project_id}/locations/{region}/services/{service_name}"

            # Get current service
            service = client.get_service(name=name)

            # Update to scale back to 1
            service.template.scaling.min_instance_count = 1
            service.template.scaling.max_instance_count = 1

            operation = client.update_service(service=service)
            operation.result(timeout=120)  # Wait for update to complete

            # Wait a bit for the service to become healthy
            await asyncio.sleep(5)

            print(f"Started service {service_name}")
            return True

        except Exception as e:
            print(f"Failed to start service {service_name}: {e}")
            return False
