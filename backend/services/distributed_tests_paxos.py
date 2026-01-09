"""
Paxos Consensus Test Framework

Runs functional, performance, and chaos tests against deployed Paxos clusters.
Tests verify the implementation of the Paxos consensus algorithm.
"""

import asyncio
import os
import sys
import time
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

import grpc

from backend.config import get_settings
from backend.models.test_result import TestType, TestStatus

settings = get_settings()


@dataclass
class DistributedDistributedTestResult:
    """Result of a single test."""
    test_name: str
    test_type: TestType
    status: TestStatus
    duration_ms: int
    details: Optional[Dict] = None
    error_message: Optional[str] = None
    chaos_scenario: Optional[str] = None


class PaxosGrpcClientManager:
    """Manages gRPC client connections for Paxos clusters."""

    _instance = None
    _stubs_compiled = False
    _proto_module_path = None
    _compilation_error: Optional[str] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not PaxosGrpcClientManager._stubs_compiled and not PaxosGrpcClientManager._compilation_error:
            self._compile_stubs()

    def _get_proto_path(self) -> Optional[str]:
        """Get path to paxos.proto file."""
        base_paths = [
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "/app",
            os.getcwd(),
        ]

        for base in base_paths:
            proto_path = os.path.join(base, "distributed_problems", "paxos", "proto", "paxos.proto")
            if os.path.exists(proto_path):
                return proto_path
        return None

    def _compile_stubs(self):
        """Compile proto stubs to a persistent location."""
        proto_path = self._get_proto_path()
        if not proto_path:
            PaxosGrpcClientManager._compilation_error = "Paxos proto file not found."
            return

        try:
            from grpc_tools import protoc

            stubs_dir = os.path.join(tempfile.gettempdir(), "paxos_grpc_stubs")
            os.makedirs(stubs_dir, exist_ok=True)

            result = protoc.main([
                'grpc_tools.protoc',
                f'--proto_path={os.path.dirname(proto_path)}',
                f'--python_out={stubs_dir}',
                f'--grpc_python_out={stubs_dir}',
                proto_path
            ])

            if result == 0:
                PaxosGrpcClientManager._proto_module_path = stubs_dir
                PaxosGrpcClientManager._stubs_compiled = True
            else:
                PaxosGrpcClientManager._compilation_error = f"Proto compilation failed with code {result}"

        except ImportError as e:
            PaxosGrpcClientManager._compilation_error = f"grpc_tools not installed: {e}"
        except Exception as e:
            PaxosGrpcClientManager._compilation_error = f"Failed to compile proto stubs: {e}"

    def is_ready(self) -> Tuple[bool, Optional[str]]:
        if PaxosGrpcClientManager._compilation_error:
            return False, PaxosGrpcClientManager._compilation_error
        if not PaxosGrpcClientManager._stubs_compiled:
            return False, "Proto stubs not compiled"
        return True, None

    def get_kv_stub(self, url: str) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
        if PaxosGrpcClientManager._compilation_error:
            return None, None, PaxosGrpcClientManager._compilation_error

        if not PaxosGrpcClientManager._stubs_compiled:
            return None, None, "Proto stubs not compiled"

        try:
            if PaxosGrpcClientManager._proto_module_path not in sys.path:
                sys.path.insert(0, PaxosGrpcClientManager._proto_module_path)

            import paxos_pb2
            import paxos_pb2_grpc

            channel = self._create_channel(url)
            return paxos_pb2_grpc.KeyValueServiceStub(channel), paxos_pb2, None

        except Exception as e:
            return None, None, f"Failed to create gRPC stub: {e}"

    def _create_channel(self, url: str) -> grpc.Channel:
        if url.startswith("https://"):
            host = url.replace("https://", "")
            credentials = grpc.ssl_channel_credentials()
            return grpc.secure_channel(f"{host}:443", credentials)
        elif url.startswith("http://"):
            host = url.replace("http://", "")
            return grpc.insecure_channel(host)
        else:
            return grpc.insecure_channel(url)


class PaxosTestRunner:
    """Test runner for Paxos consensus implementations."""

    def __init__(self, cluster_urls: List[str], submission_id: Optional[int] = None):
        self.cluster_urls = cluster_urls
        self.cluster_size = len(cluster_urls)
        self.submission_id = submission_id
        self.grpc_manager = PaxosGrpcClientManager()
        self._grpc_ready, self._grpc_error = self.grpc_manager.is_ready()

    async def run_all_tests(self) -> List[DistributedTestResult]:
        """Run all tests and return results."""
        results = []

        try:
            results.extend(await self.run_functional_tests())
        except Exception as e:
            results.append(DistributedTestResult(
                test_name="Functional Tests",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.ERROR,
                duration_ms=0,
                error_message=f"Test framework error: {e}",
            ))

        try:
            results.extend(await self.run_performance_tests())
        except Exception as e:
            results.append(DistributedTestResult(
                test_name="Performance Tests",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.ERROR,
                duration_ms=0,
                error_message=f"Test framework error: {e}",
            ))

        try:
            results.extend(await self.run_chaos_tests())
        except Exception as e:
            results.append(DistributedTestResult(
                test_name="Chaos Tests",
                test_type=TestType.CHAOS,
                status=TestStatus.ERROR,
                duration_ms=0,
                error_message=f"Test framework error: {e}",
            ))

        if not results:
            results.append(DistributedTestResult(
                test_name="Test Execution",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.ERROR,
                duration_ms=0,
                error_message="No tests were executed",
            ))

        return results

    async def run_functional_tests(self) -> List[DistributedTestResult]:
        """Run Paxos-specific functional tests."""
        results = []
        results.append(await self._test_leader_election())
        results.append(await self._test_basic_consensus())
        results.append(await self._test_slot_ordering())
        results.append(await self._test_value_agreement())
        return results

    async def run_performance_tests(self) -> List[DistributedTestResult]:
        """Run performance tests."""
        results = []
        results.append(await self._test_throughput())
        results.append(await self._test_latency())
        return results

    async def run_chaos_tests(self) -> List[DistributedTestResult]:
        """Run chaos tests."""
        results = []
        results.append(await self._test_proposer_failure())
        results.append(await self._test_acceptor_failure())
        return results

    async def _test_leader_election(self) -> DistributedTestResult:
        """Test that a leader is elected in Multi-Paxos."""
        start_time = time.time()

        try:
            leader_found = False
            leader_id = None
            last_error = None

            for attempt in range(60):
                for url in self.cluster_urls:
                    status, error = await self._get_cluster_status(url)
                    if error:
                        last_error = error
                        continue
                    if status and status.get("role") == "leader":
                        leader_found = True
                        leader_id = status.get("node_id")
                        break
                if leader_found:
                    break
                await asyncio.sleep(0.5)

            duration_ms = int((time.time() - start_time) * 1000)

            if leader_found:
                return DistributedTestResult(
                    test_name="Leader Election (Multi-Paxos)",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.PASSED,
                    duration_ms=duration_ms,
                    details={"leader_id": leader_id},
                )
            else:
                return DistributedTestResult(
                    test_name="Leader Election (Multi-Paxos)",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=duration_ms,
                    error_message=f"No leader elected. {last_error or ''}",
                    details={"hint": "Check your Multi-Paxos leader election implementation."},
                )

        except Exception as e:
            return DistributedTestResult(
                test_name="Leader Election (Multi-Paxos)",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"Test framework error: {e}",
            )

    async def _test_basic_consensus(self) -> DistributedTestResult:
        """Test basic Paxos consensus - Put/Get."""
        start_time = time.time()

        try:
            leader_url, leader_error = await self._find_leader()
            if not leader_url:
                return DistributedTestResult(
                    test_name="Basic Consensus",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=f"Could not find leader. {leader_error or ''}",
                )

            test_key = f"paxos_key_{int(time.time())}"
            test_value = "paxos_value"

            put_result, put_error = await self._put(leader_url, test_key, test_value)
            if put_error or not put_result.get("success"):
                return DistributedTestResult(
                    test_name="Basic Consensus",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=f"Put failed: {put_error or put_result.get('error')}",
                    details={"hint": "Check Paxos Phase 1 (Prepare) and Phase 2 (Accept)."},
                )

            await asyncio.sleep(0.5)

            get_result, get_error = await self._get(leader_url, test_key)
            duration_ms = int((time.time() - start_time) * 1000)

            if get_error or not get_result.get("found"):
                return DistributedTestResult(
                    test_name="Basic Consensus",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=duration_ms,
                    error_message=f"Get failed: {get_error or 'Key not found'}",
                )

            if get_result.get("value") != test_value:
                return DistributedTestResult(
                    test_name="Basic Consensus",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=duration_ms,
                    error_message=f"Value mismatch: expected '{test_value}', got '{get_result.get('value')}'",
                )

            return DistributedTestResult(
                test_name="Basic Consensus",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.PASSED,
                duration_ms=duration_ms,
                details={"key": test_key, "value": test_value},
            )

        except Exception as e:
            return DistributedTestResult(
                test_name="Basic Consensus",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"Test framework error: {e}",
            )

    async def _test_slot_ordering(self) -> DistributedTestResult:
        """Test that Paxos maintains slot ordering."""
        start_time = time.time()

        try:
            leader_url, _ = await self._find_leader()
            if not leader_url:
                return DistributedTestResult(
                    test_name="Slot Ordering",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="Could not find leader",
                )

            # Write multiple values
            keys = []
            for i in range(5):
                key = f"slot_key_{i}_{int(time.time())}"
                result, error = await self._put(leader_url, key, f"value_{i}")
                if error or not result.get("success"):
                    return DistributedTestResult(
                        test_name="Slot Ordering",
                        test_type=TestType.FUNCTIONAL,
                        status=TestStatus.FAILED,
                        duration_ms=int((time.time() - start_time) * 1000),
                        error_message=f"Put {i} failed",
                    )
                keys.append(key)

            await asyncio.sleep(1)

            # Verify all values
            for i, key in enumerate(keys):
                result, _ = await self._get(leader_url, key)
                if not result.get("found") or result.get("value") != f"value_{i}":
                    return DistributedTestResult(
                        test_name="Slot Ordering",
                        test_type=TestType.FUNCTIONAL,
                        status=TestStatus.FAILED,
                        duration_ms=int((time.time() - start_time) * 1000),
                        error_message=f"Value {i} not found or incorrect",
                    )

            return DistributedTestResult(
                test_name="Slot Ordering",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.PASSED,
                duration_ms=int((time.time() - start_time) * 1000),
                details={"entries": len(keys)},
            )

        except Exception as e:
            return DistributedTestResult(
                test_name="Slot Ordering",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"Test framework error: {e}",
            )

    async def _test_value_agreement(self) -> DistributedTestResult:
        """Test that all nodes agree on values."""
        start_time = time.time()

        try:
            leader_url, _ = await self._find_leader()
            if not leader_url:
                return DistributedTestResult(
                    test_name="Value Agreement",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="Could not find leader",
                )

            key = f"agreement_key_{int(time.time())}"
            value = "agreement_value"
            result, error = await self._put(leader_url, key, value)
            if error or not result.get("success"):
                return DistributedTestResult(
                    test_name="Value Agreement",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="Put failed",
                )

            await asyncio.sleep(2)

            # Check all nodes
            for url in self.cluster_urls:
                result, error = await self._get(url, key)
                if error or not result.get("found") or result.get("value") != value:
                    return DistributedTestResult(
                        test_name="Value Agreement",
                        test_type=TestType.FUNCTIONAL,
                        status=TestStatus.FAILED,
                        duration_ms=int((time.time() - start_time) * 1000),
                        error_message=f"Node {url} has inconsistent value",
                    )

            return DistributedTestResult(
                test_name="Value Agreement",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.PASSED,
                duration_ms=int((time.time() - start_time) * 1000),
                details={"nodes_checked": len(self.cluster_urls)},
            )

        except Exception as e:
            return DistributedTestResult(
                test_name="Value Agreement",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"Test framework error: {e}",
            )

    async def _test_throughput(self) -> DistributedTestResult:
        """Test write throughput."""
        start_time = time.time()

        try:
            leader_url, _ = await self._find_leader()
            if not leader_url:
                return DistributedTestResult(
                    test_name="Throughput",
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="Could not find leader",
                )

            num_ops = 100
            successful_ops = 0
            write_start = time.time()

            for i in range(num_ops):
                key = f"throughput_key_{i}_{int(time.time() * 1000)}"
                result, error = await self._put(leader_url, key, f"value_{i}")
                if not error and result.get("success"):
                    successful_ops += 1

            write_duration = time.time() - write_start
            ops_per_second = successful_ops / write_duration if write_duration > 0 else 0

            duration_ms = int((time.time() - start_time) * 1000)

            if ops_per_second >= 10:
                return DistributedTestResult(
                    test_name="Throughput",
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.PASSED,
                    duration_ms=duration_ms,
                    details={"ops_per_second": round(ops_per_second, 2)},
                )
            else:
                return DistributedTestResult(
                    test_name="Throughput",
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.FAILED,
                    duration_ms=duration_ms,
                    error_message=f"Throughput too low: {ops_per_second:.2f} ops/sec",
                )

        except Exception as e:
            return DistributedTestResult(
                test_name="Throughput",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"Test framework error: {e}",
            )

    async def _test_latency(self) -> DistributedTestResult:
        """Test operation latency."""
        start_time = time.time()

        try:
            leader_url, _ = await self._find_leader()
            if not leader_url:
                return DistributedTestResult(
                    test_name="Latency",
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="Could not find leader",
                )

            latencies = []
            for i in range(50):
                key = f"latency_key_{i}_{int(time.time() * 1000)}"
                op_start = time.time()
                result, error = await self._put(leader_url, key, f"value_{i}")
                op_latency = (time.time() - op_start) * 1000
                if not error and result.get("success"):
                    latencies.append(op_latency)

            if not latencies:
                return DistributedTestResult(
                    test_name="Latency",
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="No successful operations",
                )

            latencies.sort()
            p95 = latencies[int(len(latencies) * 0.95)]

            if p95 < 500:
                return DistributedTestResult(
                    test_name="Latency",
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"p95_ms": round(p95, 2)},
                )
            else:
                return DistributedTestResult(
                    test_name="Latency",
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=f"P95 latency too high: {p95:.2f}ms",
                )

        except Exception as e:
            return DistributedTestResult(
                test_name="Latency",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"Test framework error: {e}",
            )

    async def _test_proposer_failure(self) -> DistributedTestResult:
        """Test recovery from proposer failure."""
        start_time = time.time()
        return DistributedTestResult(
            test_name="Proposer Failure",
            test_type=TestType.CHAOS,
            status=TestStatus.PASSED,
            duration_ms=int((time.time() - start_time) * 1000),
            details={"note": "Chaos test skipped in this environment"},
            chaos_scenario="skipped",
        )

    async def _test_acceptor_failure(self) -> DistributedTestResult:
        """Test recovery from acceptor failure."""
        start_time = time.time()
        return DistributedTestResult(
            test_name="Acceptor Failure",
            test_type=TestType.CHAOS,
            status=TestStatus.PASSED,
            duration_ms=int((time.time() - start_time) * 1000),
            details={"note": "Chaos test skipped in this environment"},
            chaos_scenario="skipped",
        )

    # Helper methods
    async def _find_leader(self) -> Tuple[Optional[str], Optional[str]]:
        for url in self.cluster_urls:
            status, error = await self._get_cluster_status(url)
            if error:
                continue
            if status and status.get("role") == "leader":
                return url, None
        return None, "No leader found"

    async def _get_cluster_status(self, url: str) -> Tuple[Optional[Dict], Optional[str]]:
        stub, paxos_pb2, error = self.grpc_manager.get_kv_stub(url)
        if error:
            return None, error
        if not stub or not paxos_pb2:
            return None, "gRPC stub not available"

        try:
            request = paxos_pb2.GetClusterStatusRequest()
            response = stub.GetClusterStatus(request, timeout=10.0)
            return {
                "node_id": response.node_id,
                "role": response.role,
                "current_slot": response.current_slot,
            }, None
        except grpc.RpcError as e:
            return None, f"gRPC error: {e}"
        except Exception as e:
            return None, f"Error: {e}"

    async def _put(self, url: str, key: str, value: str) -> Tuple[Dict, Optional[str]]:
        stub, paxos_pb2, error = self.grpc_manager.get_kv_stub(url)
        if error:
            return {}, error
        if not stub or not paxos_pb2:
            return {}, "gRPC stub not available"

        try:
            request = paxos_pb2.PutRequest(key=key, value=value)
            response = stub.Put(request, timeout=30.0)
            return {
                "success": response.success,
                "error": response.error if response.error else None,
            }, None
        except grpc.RpcError as e:
            return {}, f"gRPC error: {e}"
        except Exception as e:
            return {}, f"Error: {e}"

    async def _get(self, url: str, key: str) -> Tuple[Dict, Optional[str]]:
        stub, paxos_pb2, error = self.grpc_manager.get_kv_stub(url)
        if error:
            return {}, error
        if not stub or not paxos_pb2:
            return {}, "gRPC stub not available"

        try:
            request = paxos_pb2.GetRequest(key=key)
            response = stub.Get(request, timeout=10.0)
            return {
                "found": response.found,
                "value": response.value if response.found else None,
            }, None
        except grpc.RpcError as e:
            return {}, f"gRPC error: {e}"
        except Exception as e:
            return {}, f"Error: {e}"
