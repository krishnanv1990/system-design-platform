"""
Vector Search Test Framework

Runs functional, performance, and chaos tests against deployed vector search clusters.
Tests verify the implementation of HNSW, IVF, and Product Quantization algorithms.
"""

import asyncio
import os
import sys
import time
import tempfile
import random
import math
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


# =============================================================================
# HNSW Test Runner
# =============================================================================

class HNSWGrpcClientManager:
    """Manages gRPC client connections for HNSW clusters."""

    _instance = None
    _stubs_compiled = False
    _proto_module_path = None
    _compilation_error: Optional[str] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not HNSWGrpcClientManager._stubs_compiled and not HNSWGrpcClientManager._compilation_error:
            self._compile_stubs()

    def _get_proto_path(self) -> Optional[str]:
        """Get path to hnsw.proto file."""
        base_paths = [
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "/app",
            os.getcwd(),
        ]

        for base in base_paths:
            proto_path = os.path.join(base, "distributed_problems", "hnsw", "proto", "hnsw.proto")
            if os.path.exists(proto_path):
                return proto_path
        return None

    def _compile_stubs(self):
        """Compile proto stubs to a persistent location."""
        proto_path = self._get_proto_path()
        if not proto_path:
            HNSWGrpcClientManager._compilation_error = "HNSW proto file not found."
            return

        try:
            from grpc_tools import protoc

            stubs_dir = os.path.join(tempfile.gettempdir(), "hnsw_grpc_stubs")
            os.makedirs(stubs_dir, exist_ok=True)

            result = protoc.main([
                'grpc_tools.protoc',
                f'--proto_path={os.path.dirname(proto_path)}',
                f'--python_out={stubs_dir}',
                f'--grpc_python_out={stubs_dir}',
                proto_path
            ])

            if result != 0:
                HNSWGrpcClientManager._compilation_error = f"Proto compilation failed with code {result}"
                return

            if stubs_dir not in sys.path:
                sys.path.insert(0, stubs_dir)

            HNSWGrpcClientManager._proto_module_path = stubs_dir
            HNSWGrpcClientManager._stubs_compiled = True

        except Exception as e:
            HNSWGrpcClientManager._compilation_error = f"Failed to compile HNSW proto: {str(e)}"

    def is_ready(self) -> Tuple[bool, Optional[str]]:
        """Check if the gRPC client is ready."""
        if HNSWGrpcClientManager._compilation_error:
            return False, HNSWGrpcClientManager._compilation_error
        return HNSWGrpcClientManager._stubs_compiled, None

    def _create_channel(self, url: str) -> grpc.Channel:
        """Create a gRPC channel for the given URL."""
        if url.startswith("https://"):
            host = url.replace("https://", "").split("/")[0]
            credentials = grpc.ssl_channel_credentials()
            return grpc.secure_channel(f"{host}:443", credentials)
        elif url.startswith("http://"):
            host = url.replace("http://", "").split("/")[0]
            return grpc.insecure_channel(host)
        else:
            return grpc.insecure_channel(url)

    def get_hnsw_stub(self, url: str) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
        """Get HNSW stub and proto module."""
        if not HNSWGrpcClientManager._stubs_compiled:
            return None, None, HNSWGrpcClientManager._compilation_error or "Stubs not compiled"

        try:
            import hnsw_pb2
            import hnsw_pb2_grpc

            channel = self._create_channel(url)
            stub = hnsw_pb2_grpc.HNSWServiceStub(channel)
            return stub, hnsw_pb2, None

        except Exception as e:
            return None, None, f"Failed to create HNSW stub: {str(e)}"


class HNSWTestRunner:
    """Test runner for HNSW implementations."""

    def __init__(self, cluster_urls: List[str], submission_id: int):
        self.cluster_urls = cluster_urls
        self.cluster_size = len(cluster_urls)
        self.submission_id = submission_id
        self.grpc_manager = HNSWGrpcClientManager()

    async def run_all_tests(self) -> List[DistributedTestResult]:
        """Run all tests."""
        results = []
        results.extend(await self.run_functional_tests())
        results.extend(await self.run_performance_tests())
        return results

    async def run_functional_tests(self) -> List[DistributedTestResult]:
        """Run functional tests."""
        tests = [
            self._test_create_index,
            self._test_insert_vector,
            self._test_search,
            self._test_delete_vector,
            self._test_batch_insert,
        ]
        results = []
        for test in tests:
            try:
                result = await test()
                results.append(result)
            except Exception as e:
                results.append(DistributedTestResult(
                    test_name=test.__name__.replace("_test_", "").replace("_", " ").title(),
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.ERROR,
                    duration_ms=0,
                    error_message=f"Test framework error: {str(e)}"
                ))
        return results

    async def run_performance_tests(self) -> List[DistributedTestResult]:
        """Run performance tests."""
        tests = [
            self._test_search_throughput,
            self._test_search_latency,
        ]
        results = []
        for test in tests:
            try:
                result = await test()
                results.append(result)
            except Exception as e:
                results.append(DistributedTestResult(
                    test_name=test.__name__.replace("_test_", "").replace("_", " ").title(),
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.ERROR,
                    duration_ms=0,
                    error_message=f"Test framework error: {str(e)}"
                ))
        return results

    def _generate_random_vector(self, dimension: int = 128) -> List[float]:
        """Generate a random unit vector."""
        vec = [random.gauss(0, 1) for _ in range(dimension)]
        norm = math.sqrt(sum(x*x for x in vec))
        return [x / norm for x in vec]

    async def _test_create_index(self) -> DistributedTestResult:
        """Test creating an HNSW index."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_hnsw_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Create Index",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error,
                details={"hint": "Ensure the HNSW service is running and proto is compiled"}
            )

        try:
            request = proto.CreateIndexRequest(
                dimension=128,
                m=16,
                ef_construction=200,
                distance_type="euclidean"
            )
            response = stub.CreateIndex(request, timeout=10)

            if response.success:
                return DistributedTestResult(
                    test_name="Create Index",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"index_id": response.index_id}
                )
            else:
                return DistributedTestResult(
                    test_name="Create Index",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=response.error
                )
        except grpc.RpcError as e:
            return DistributedTestResult(
                test_name="Create Index",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"gRPC error: {e.details() if hasattr(e, 'details') else str(e)}"
            )

    async def _test_insert_vector(self) -> DistributedTestResult:
        """Test inserting a vector."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_hnsw_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Insert Vector",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error
            )

        try:
            vector = self._generate_random_vector()
            request = proto.InsertRequest(
                id="test_vector_1",
                vector=vector,
                metadata={"type": "test"}
            )
            response = stub.Insert(request, timeout=10)

            if response.success:
                return DistributedTestResult(
                    test_name="Insert Vector",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"level": response.level}
                )
            else:
                return DistributedTestResult(
                    test_name="Insert Vector",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=response.error
                )
        except grpc.RpcError as e:
            return DistributedTestResult(
                test_name="Insert Vector",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"gRPC error: {str(e)}"
            )

    async def _test_search(self) -> DistributedTestResult:
        """Test searching for nearest neighbors."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_hnsw_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Search",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error
            )

        try:
            query = self._generate_random_vector()
            request = proto.SearchRequest(
                query_vector=query,
                k=10,
                ef_search=50
            )
            response = stub.Search(request, timeout=10)

            return DistributedTestResult(
                test_name="Search",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.PASSED,
                duration_ms=int((time.time() - start_time) * 1000),
                details={
                    "results_count": len(response.results),
                    "search_time_us": response.search_time_us,
                    "nodes_visited": response.nodes_visited
                }
            )
        except grpc.RpcError as e:
            return DistributedTestResult(
                test_name="Search",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"gRPC error: {str(e)}"
            )

    async def _test_delete_vector(self) -> DistributedTestResult:
        """Test deleting a vector."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_hnsw_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Delete Vector",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error
            )

        try:
            request = proto.DeleteRequest(id="test_vector_1")
            response = stub.Delete(request, timeout=10)

            return DistributedTestResult(
                test_name="Delete Vector",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.PASSED if response.success else TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                details={"found": response.found},
                error_message=response.error if not response.success else None
            )
        except grpc.RpcError as e:
            return DistributedTestResult(
                test_name="Delete Vector",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"gRPC error: {str(e)}"
            )

    async def _test_batch_insert(self) -> DistributedTestResult:
        """Test batch inserting vectors."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_hnsw_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Batch Insert",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error
            )

        try:
            vectors = []
            for i in range(100):
                vector = proto.Vector(
                    id=f"batch_vector_{i}",
                    values=self._generate_random_vector(),
                    metadata={"batch": "test"}
                )
                vectors.append(vector)

            request = proto.BatchInsertRequest(vectors=vectors)
            response = stub.BatchInsert(request, timeout=30)

            if response.success:
                return DistributedTestResult(
                    test_name="Batch Insert",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"inserted_count": response.inserted_count}
                )
            else:
                return DistributedTestResult(
                    test_name="Batch Insert",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=response.error
                )
        except grpc.RpcError as e:
            return DistributedTestResult(
                test_name="Batch Insert",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"gRPC error: {str(e)}"
            )

    async def _test_search_throughput(self) -> DistributedTestResult:
        """Test search throughput."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_hnsw_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Search Throughput",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error
            )

        try:
            num_queries = 100
            successful_queries = 0

            for _ in range(num_queries):
                query = self._generate_random_vector()
                request = proto.SearchRequest(query_vector=query, k=10, ef_search=50)
                try:
                    stub.Search(request, timeout=5)
                    successful_queries += 1
                except:
                    pass

            duration_s = time.time() - start_time
            qps = successful_queries / duration_s

            return DistributedTestResult(
                test_name="Search Throughput",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.PASSED,
                duration_ms=int(duration_s * 1000),
                details={
                    "queries_per_second": round(qps, 2),
                    "total_queries": num_queries,
                    "successful_queries": successful_queries
                }
            )
        except Exception as e:
            return DistributedTestResult(
                test_name="Search Throughput",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=str(e)
            )

    async def _test_search_latency(self) -> DistributedTestResult:
        """Test search latency percentiles."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_hnsw_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Search Latency",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error
            )

        try:
            latencies = []
            for _ in range(50):
                query = self._generate_random_vector()
                request = proto.SearchRequest(query_vector=query, k=10, ef_search=50)
                query_start = time.time()
                try:
                    stub.Search(request, timeout=5)
                    latencies.append((time.time() - query_start) * 1000)
                except:
                    pass

            if latencies:
                latencies.sort()
                p50 = latencies[len(latencies) // 2]
                p95 = latencies[int(len(latencies) * 0.95)]
                p99 = latencies[int(len(latencies) * 0.99)]

                return DistributedTestResult(
                    test_name="Search Latency",
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={
                        "p50_ms": round(p50, 2),
                        "p95_ms": round(p95, 2),
                        "p99_ms": round(p99, 2),
                        "sample_size": len(latencies)
                    }
                )
            else:
                return DistributedTestResult(
                    test_name="Search Latency",
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message="No successful queries"
                )
        except Exception as e:
            return DistributedTestResult(
                test_name="Search Latency",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=str(e)
            )


# =============================================================================
# IVF Test Runner
# =============================================================================

class IVFGrpcClientManager:
    """Manages gRPC client connections for IVF clusters."""

    _instance = None
    _stubs_compiled = False
    _proto_module_path = None
    _compilation_error: Optional[str] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not IVFGrpcClientManager._stubs_compiled and not IVFGrpcClientManager._compilation_error:
            self._compile_stubs()

    def _get_proto_path(self) -> Optional[str]:
        """Get path to inverted_file_index.proto file."""
        base_paths = [
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "/app",
            os.getcwd(),
        ]

        for base in base_paths:
            proto_path = os.path.join(base, "distributed_problems", "inverted_file_index", "proto", "inverted_file_index.proto")
            if os.path.exists(proto_path):
                return proto_path
        return None

    def _compile_stubs(self):
        """Compile proto stubs to a persistent location."""
        proto_path = self._get_proto_path()
        if not proto_path:
            IVFGrpcClientManager._compilation_error = "IVF proto file not found."
            return

        try:
            from grpc_tools import protoc

            stubs_dir = os.path.join(tempfile.gettempdir(), "ivf_grpc_stubs")
            os.makedirs(stubs_dir, exist_ok=True)

            result = protoc.main([
                'grpc_tools.protoc',
                f'--proto_path={os.path.dirname(proto_path)}',
                f'--python_out={stubs_dir}',
                f'--grpc_python_out={stubs_dir}',
                proto_path
            ])

            if result != 0:
                IVFGrpcClientManager._compilation_error = f"Proto compilation failed with code {result}"
                return

            if stubs_dir not in sys.path:
                sys.path.insert(0, stubs_dir)

            IVFGrpcClientManager._proto_module_path = stubs_dir
            IVFGrpcClientManager._stubs_compiled = True

        except Exception as e:
            IVFGrpcClientManager._compilation_error = f"Failed to compile IVF proto: {str(e)}"

    def is_ready(self) -> Tuple[bool, Optional[str]]:
        """Check if the gRPC client is ready."""
        if IVFGrpcClientManager._compilation_error:
            return False, IVFGrpcClientManager._compilation_error
        return IVFGrpcClientManager._stubs_compiled, None

    def _create_channel(self, url: str) -> grpc.Channel:
        """Create a gRPC channel for the given URL."""
        if url.startswith("https://"):
            host = url.replace("https://", "").split("/")[0]
            credentials = grpc.ssl_channel_credentials()
            return grpc.secure_channel(f"{host}:443", credentials)
        elif url.startswith("http://"):
            host = url.replace("http://", "").split("/")[0]
            return grpc.insecure_channel(host)
        else:
            return grpc.insecure_channel(url)

    def get_ivf_stub(self, url: str) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
        """Get IVF stub and proto module."""
        if not IVFGrpcClientManager._stubs_compiled:
            return None, None, IVFGrpcClientManager._compilation_error or "Stubs not compiled"

        try:
            import inverted_file_index_pb2
            import inverted_file_index_pb2_grpc

            channel = self._create_channel(url)
            stub = inverted_file_index_pb2_grpc.IVFServiceStub(channel)
            return stub, inverted_file_index_pb2, None

        except Exception as e:
            return None, None, f"Failed to create IVF stub: {str(e)}"


class IVFTestRunner:
    """Test runner for IVF implementations."""

    def __init__(self, cluster_urls: List[str], submission_id: int):
        self.cluster_urls = cluster_urls
        self.cluster_size = len(cluster_urls)
        self.submission_id = submission_id
        self.grpc_manager = IVFGrpcClientManager()

    async def run_all_tests(self) -> List[DistributedTestResult]:
        """Run all tests."""
        results = []
        results.extend(await self.run_functional_tests())
        results.extend(await self.run_performance_tests())
        return results

    async def run_functional_tests(self) -> List[DistributedTestResult]:
        """Run functional tests."""
        tests = [
            self._test_create_index,
            self._test_train,
            self._test_add_vector,
            self._test_search,
            self._test_batch_add,
        ]
        results = []
        for test in tests:
            try:
                result = await test()
                results.append(result)
            except Exception as e:
                results.append(DistributedTestResult(
                    test_name=test.__name__.replace("_test_", "").replace("_", " ").title(),
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.ERROR,
                    duration_ms=0,
                    error_message=f"Test framework error: {str(e)}"
                ))
        return results

    async def run_performance_tests(self) -> List[DistributedTestResult]:
        """Run performance tests."""
        tests = [
            self._test_search_throughput,
        ]
        results = []
        for test in tests:
            try:
                result = await test()
                results.append(result)
            except Exception as e:
                results.append(DistributedTestResult(
                    test_name=test.__name__.replace("_test_", "").replace("_", " ").title(),
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.ERROR,
                    duration_ms=0,
                    error_message=f"Test framework error: {str(e)}"
                ))
        return results

    def _generate_random_vector(self, dimension: int = 128) -> List[float]:
        """Generate a random unit vector."""
        vec = [random.gauss(0, 1) for _ in range(dimension)]
        norm = math.sqrt(sum(x*x for x in vec))
        return [x / norm for x in vec]

    async def _test_create_index(self) -> DistributedTestResult:
        """Test creating an IVF index."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_ivf_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Create Index",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error,
                details={"hint": "Ensure the IVF service is running and proto is compiled"}
            )

        try:
            request = proto.CreateIndexRequest(
                dimension=128,
                n_clusters=10,
                distance_type="euclidean"
            )
            response = stub.CreateIndex(request, timeout=10)

            if response.success:
                return DistributedTestResult(
                    test_name="Create Index",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"index_id": response.index_id}
                )
            else:
                return DistributedTestResult(
                    test_name="Create Index",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=response.error
                )
        except grpc.RpcError as e:
            return DistributedTestResult(
                test_name="Create Index",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"gRPC error: {str(e)}"
            )

    async def _test_train(self) -> DistributedTestResult:
        """Test training the index with k-means."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_ivf_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Train Index",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error
            )

        try:
            # Generate training vectors
            training_vectors = []
            for i in range(100):
                vector = proto.Vector(
                    id=f"train_{i}",
                    values=self._generate_random_vector()
                )
                training_vectors.append(vector)

            request = proto.TrainRequest(
                training_vectors=training_vectors,
                n_iterations=10
            )
            response = stub.Train(request, timeout=30)

            if response.success:
                return DistributedTestResult(
                    test_name="Train Index",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"n_clusters": response.n_clusters, "inertia": response.inertia}
                )
            else:
                return DistributedTestResult(
                    test_name="Train Index",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=response.error
                )
        except grpc.RpcError as e:
            return DistributedTestResult(
                test_name="Train Index",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"gRPC error: {str(e)}"
            )

    async def _test_add_vector(self) -> DistributedTestResult:
        """Test adding a vector."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_ivf_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Add Vector",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error
            )

        try:
            vector = self._generate_random_vector()
            request = proto.AddRequest(
                id="test_vector_1",
                vector=vector,
                metadata={"type": "test"}
            )
            response = stub.Add(request, timeout=10)

            if response.success:
                return DistributedTestResult(
                    test_name="Add Vector",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"assigned_cluster": response.assigned_cluster}
                )
            else:
                return DistributedTestResult(
                    test_name="Add Vector",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=response.error
                )
        except grpc.RpcError as e:
            return DistributedTestResult(
                test_name="Add Vector",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"gRPC error: {str(e)}"
            )

    async def _test_search(self) -> DistributedTestResult:
        """Test searching for nearest neighbors."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_ivf_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Search",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error
            )

        try:
            query = self._generate_random_vector()
            request = proto.SearchRequest(
                query_vector=query,
                k=10,
                n_probe=3
            )
            response = stub.Search(request, timeout=10)

            return DistributedTestResult(
                test_name="Search",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.PASSED,
                duration_ms=int((time.time() - start_time) * 1000),
                details={
                    "results_count": len(response.results),
                    "search_time_us": response.search_time_us,
                    "clusters_searched": list(response.clusters_searched)
                }
            )
        except grpc.RpcError as e:
            return DistributedTestResult(
                test_name="Search",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"gRPC error: {str(e)}"
            )

    async def _test_batch_add(self) -> DistributedTestResult:
        """Test batch adding vectors."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_ivf_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Batch Add",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error
            )

        try:
            vectors = []
            for i in range(100):
                vector = proto.Vector(
                    id=f"batch_vector_{i}",
                    values=self._generate_random_vector(),
                    metadata={"batch": "test"}
                )
                vectors.append(vector)

            request = proto.BatchAddRequest(vectors=vectors)
            response = stub.BatchAdd(request, timeout=30)

            if response.success:
                return DistributedTestResult(
                    test_name="Batch Add",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"added_count": response.added_count}
                )
            else:
                return DistributedTestResult(
                    test_name="Batch Add",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=response.error
                )
        except grpc.RpcError as e:
            return DistributedTestResult(
                test_name="Batch Add",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"gRPC error: {str(e)}"
            )

    async def _test_search_throughput(self) -> DistributedTestResult:
        """Test search throughput."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_ivf_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Search Throughput",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error
            )

        try:
            num_queries = 100
            successful_queries = 0

            for _ in range(num_queries):
                query = self._generate_random_vector()
                request = proto.SearchRequest(query_vector=query, k=10, n_probe=3)
                try:
                    stub.Search(request, timeout=5)
                    successful_queries += 1
                except:
                    pass

            duration_s = time.time() - start_time
            qps = successful_queries / duration_s

            return DistributedTestResult(
                test_name="Search Throughput",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.PASSED,
                duration_ms=int(duration_s * 1000),
                details={
                    "queries_per_second": round(qps, 2),
                    "total_queries": num_queries,
                    "successful_queries": successful_queries
                }
            )
        except Exception as e:
            return DistributedTestResult(
                test_name="Search Throughput",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=str(e)
            )


# =============================================================================
# PQ Test Runner
# =============================================================================

class PQGrpcClientManager:
    """Manages gRPC client connections for PQ clusters."""

    _instance = None
    _stubs_compiled = False
    _proto_module_path = None
    _compilation_error: Optional[str] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not PQGrpcClientManager._stubs_compiled and not PQGrpcClientManager._compilation_error:
            self._compile_stubs()

    def _get_proto_path(self) -> Optional[str]:
        """Get path to product_quantization.proto file."""
        base_paths = [
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "/app",
            os.getcwd(),
        ]

        for base in base_paths:
            proto_path = os.path.join(base, "distributed_problems", "product_quantization", "proto", "product_quantization.proto")
            if os.path.exists(proto_path):
                return proto_path
        return None

    def _compile_stubs(self):
        """Compile proto stubs to a persistent location."""
        proto_path = self._get_proto_path()
        if not proto_path:
            PQGrpcClientManager._compilation_error = "PQ proto file not found."
            return

        try:
            from grpc_tools import protoc

            stubs_dir = os.path.join(tempfile.gettempdir(), "pq_grpc_stubs")
            os.makedirs(stubs_dir, exist_ok=True)

            result = protoc.main([
                'grpc_tools.protoc',
                f'--proto_path={os.path.dirname(proto_path)}',
                f'--python_out={stubs_dir}',
                f'--grpc_python_out={stubs_dir}',
                proto_path
            ])

            if result != 0:
                PQGrpcClientManager._compilation_error = f"Proto compilation failed with code {result}"
                return

            if stubs_dir not in sys.path:
                sys.path.insert(0, stubs_dir)

            PQGrpcClientManager._proto_module_path = stubs_dir
            PQGrpcClientManager._stubs_compiled = True

        except Exception as e:
            PQGrpcClientManager._compilation_error = f"Failed to compile PQ proto: {str(e)}"

    def is_ready(self) -> Tuple[bool, Optional[str]]:
        """Check if the gRPC client is ready."""
        if PQGrpcClientManager._compilation_error:
            return False, PQGrpcClientManager._compilation_error
        return PQGrpcClientManager._stubs_compiled, None

    def _create_channel(self, url: str) -> grpc.Channel:
        """Create a gRPC channel for the given URL."""
        if url.startswith("https://"):
            host = url.replace("https://", "").split("/")[0]
            credentials = grpc.ssl_channel_credentials()
            return grpc.secure_channel(f"{host}:443", credentials)
        elif url.startswith("http://"):
            host = url.replace("http://", "").split("/")[0]
            return grpc.insecure_channel(host)
        else:
            return grpc.insecure_channel(url)

    def get_pq_stub(self, url: str) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
        """Get PQ stub and proto module."""
        if not PQGrpcClientManager._stubs_compiled:
            return None, None, PQGrpcClientManager._compilation_error or "Stubs not compiled"

        try:
            import product_quantization_pb2
            import product_quantization_pb2_grpc

            channel = self._create_channel(url)
            stub = product_quantization_pb2_grpc.PQServiceStub(channel)
            return stub, product_quantization_pb2, None

        except Exception as e:
            return None, None, f"Failed to create PQ stub: {str(e)}"


class PQTestRunner:
    """Test runner for Product Quantization implementations."""

    def __init__(self, cluster_urls: List[str], submission_id: int):
        self.cluster_urls = cluster_urls
        self.cluster_size = len(cluster_urls)
        self.submission_id = submission_id
        self.grpc_manager = PQGrpcClientManager()

    async def run_all_tests(self) -> List[DistributedTestResult]:
        """Run all tests."""
        results = []
        results.extend(await self.run_functional_tests())
        results.extend(await self.run_performance_tests())
        return results

    async def run_functional_tests(self) -> List[DistributedTestResult]:
        """Run functional tests."""
        tests = [
            self._test_create_index,
            self._test_train,
            self._test_encode_decode,
            self._test_add_vector,
            self._test_search,
        ]
        results = []
        for test in tests:
            try:
                result = await test()
                results.append(result)
            except Exception as e:
                results.append(DistributedTestResult(
                    test_name=test.__name__.replace("_test_", "").replace("_", " ").title(),
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.ERROR,
                    duration_ms=0,
                    error_message=f"Test framework error: {str(e)}"
                ))
        return results

    async def run_performance_tests(self) -> List[DistributedTestResult]:
        """Run performance tests."""
        tests = [
            self._test_compression_ratio,
            self._test_search_throughput,
        ]
        results = []
        for test in tests:
            try:
                result = await test()
                results.append(result)
            except Exception as e:
                results.append(DistributedTestResult(
                    test_name=test.__name__.replace("_test_", "").replace("_", " ").title(),
                    test_type=TestType.PERFORMANCE,
                    status=TestStatus.ERROR,
                    duration_ms=0,
                    error_message=f"Test framework error: {str(e)}"
                ))
        return results

    def _generate_random_vector(self, dimension: int = 128) -> List[float]:
        """Generate a random unit vector."""
        vec = [random.gauss(0, 1) for _ in range(dimension)]
        norm = math.sqrt(sum(x*x for x in vec))
        return [x / norm for x in vec]

    async def _test_create_index(self) -> DistributedTestResult:
        """Test creating a PQ index."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_pq_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Create Index",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error,
                details={"hint": "Ensure the PQ service is running and proto is compiled"}
            )

        try:
            request = proto.CreateIndexRequest(
                dimension=128,
                m=8,
                ks=256,
                distance_type="euclidean"
            )
            response = stub.CreateIndex(request, timeout=10)

            if response.success:
                return DistributedTestResult(
                    test_name="Create Index",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"index_id": response.index_id, "dsub": response.dsub}
                )
            else:
                return DistributedTestResult(
                    test_name="Create Index",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=response.error
                )
        except grpc.RpcError as e:
            return DistributedTestResult(
                test_name="Create Index",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"gRPC error: {str(e)}"
            )

    async def _test_train(self) -> DistributedTestResult:
        """Test training the quantizer."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_pq_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Train Quantizer",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error
            )

        try:
            # Generate training vectors
            training_vectors = []
            for i in range(256):
                vector = proto.Vector(
                    id=f"train_{i}",
                    values=self._generate_random_vector()
                )
                training_vectors.append(vector)

            request = proto.TrainRequest(
                training_vectors=training_vectors,
                n_iterations=10
            )
            response = stub.Train(request, timeout=60)

            if response.success:
                return DistributedTestResult(
                    test_name="Train Quantizer",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"total_error": response.total_error}
                )
            else:
                return DistributedTestResult(
                    test_name="Train Quantizer",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=response.error
                )
        except grpc.RpcError as e:
            return DistributedTestResult(
                test_name="Train Quantizer",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"gRPC error: {str(e)}"
            )

    async def _test_encode_decode(self) -> DistributedTestResult:
        """Test encoding and decoding vectors."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_pq_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Encode/Decode",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error
            )

        try:
            original = self._generate_random_vector()

            # Encode
            encode_request = proto.EncodeRequest(vector=original)
            encode_response = stub.Encode(encode_request, timeout=10)

            if not encode_response.success:
                return DistributedTestResult(
                    test_name="Encode/Decode",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=f"Encode failed: {encode_response.error}"
                )

            # Decode
            decode_request = proto.DecodeRequest(codes=list(encode_response.codes))
            decode_response = stub.Decode(decode_request, timeout=10)

            if not decode_response.success:
                return DistributedTestResult(
                    test_name="Encode/Decode",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=f"Decode failed: {decode_response.error}"
                )

            # Calculate reconstruction error
            reconstructed = list(decode_response.vector)
            error_sum = sum((a - b) ** 2 for a, b in zip(original, reconstructed))
            rmse = math.sqrt(error_sum / len(original))

            return DistributedTestResult(
                test_name="Encode/Decode",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.PASSED,
                duration_ms=int((time.time() - start_time) * 1000),
                details={
                    "codes_length": len(encode_response.codes),
                    "reconstruction_rmse": round(rmse, 4)
                }
            )
        except grpc.RpcError as e:
            return DistributedTestResult(
                test_name="Encode/Decode",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"gRPC error: {str(e)}"
            )

    async def _test_add_vector(self) -> DistributedTestResult:
        """Test adding a vector."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_pq_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Add Vector",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error
            )

        try:
            vector = self._generate_random_vector()
            request = proto.AddRequest(
                id="test_vector_1",
                vector=vector,
                metadata={"type": "test"}
            )
            response = stub.Add(request, timeout=10)

            if response.success:
                return DistributedTestResult(
                    test_name="Add Vector",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.PASSED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    details={"codes_length": len(response.codes)}
                )
            else:
                return DistributedTestResult(
                    test_name="Add Vector",
                    test_type=TestType.FUNCTIONAL,
                    status=TestStatus.FAILED,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error_message=response.error
                )
        except grpc.RpcError as e:
            return DistributedTestResult(
                test_name="Add Vector",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"gRPC error: {str(e)}"
            )

    async def _test_search(self) -> DistributedTestResult:
        """Test searching for nearest neighbors."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_pq_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Search",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error
            )

        try:
            query = self._generate_random_vector()
            request = proto.SearchRequest(
                query_vector=query,
                k=10,
                rerank=True,
                rerank_k=100
            )
            response = stub.Search(request, timeout=10)

            return DistributedTestResult(
                test_name="Search",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.PASSED,
                duration_ms=int((time.time() - start_time) * 1000),
                details={
                    "results_count": len(response.results),
                    "search_time_us": response.search_time_us,
                    "used_reranking": response.used_reranking
                }
            )
        except grpc.RpcError as e:
            return DistributedTestResult(
                test_name="Search",
                test_type=TestType.FUNCTIONAL,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"gRPC error: {str(e)}"
            )

    async def _test_compression_ratio(self) -> DistributedTestResult:
        """Test the compression ratio achieved by PQ."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_pq_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Compression Ratio",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error
            )

        try:
            request = proto.GetStatsRequest()
            response = stub.GetStats(request, timeout=10)

            stats = response.stats
            return DistributedTestResult(
                test_name="Compression Ratio",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.PASSED,
                duration_ms=int((time.time() - start_time) * 1000),
                details={
                    "compression_ratio": stats.compression_ratio,
                    "dimension": stats.dimension,
                    "m": stats.m,
                    "ks": stats.ks,
                    "memory_usage_mb": stats.memory_usage_mb
                }
            )
        except grpc.RpcError as e:
            return DistributedTestResult(
                test_name="Compression Ratio",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=f"gRPC error: {str(e)}"
            )

    async def _test_search_throughput(self) -> DistributedTestResult:
        """Test search throughput."""
        start_time = time.time()

        stub, proto, error = self.grpc_manager.get_pq_stub(self.cluster_urls[0])
        if error:
            return DistributedTestResult(
                test_name="Search Throughput",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.FAILED,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error
            )

        try:
            num_queries = 100
            successful_queries = 0

            for _ in range(num_queries):
                query = self._generate_random_vector()
                request = proto.SearchRequest(query_vector=query, k=10)
                try:
                    stub.Search(request, timeout=5)
                    successful_queries += 1
                except:
                    pass

            duration_s = time.time() - start_time
            qps = successful_queries / duration_s

            return DistributedTestResult(
                test_name="Search Throughput",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.PASSED,
                duration_ms=int(duration_s * 1000),
                details={
                    "queries_per_second": round(qps, 2),
                    "total_queries": num_queries,
                    "successful_queries": successful_queries
                }
            )
        except Exception as e:
            return DistributedTestResult(
                test_name="Search Throughput",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.ERROR,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=str(e)
            )
