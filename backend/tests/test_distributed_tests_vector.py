"""
Tests for the vector search test frameworks.

Tests the HNSW, IVF, and PQ test runners.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import grpc

from backend.services.distributed_tests_vector import (
    HNSWTestRunner,
    HNSWGrpcClientManager,
    IVFTestRunner,
    IVFGrpcClientManager,
    PQTestRunner,
    PQGrpcClientManager,
    TestType,
    TestStatus,
    TestResult,
)


class TestTestEnums:
    """Test the test type and status enums."""

    def test_test_type_values(self):
        """Test TestType enum values."""
        assert TestType.FUNCTIONAL.value == "functional"
        assert TestType.PERFORMANCE.value == "performance"
        assert TestType.CHAOS.value == "chaos"

    def test_test_status_values(self):
        """Test TestStatus enum values."""
        assert TestStatus.PENDING.value == "pending"
        assert TestStatus.RUNNING.value == "running"
        assert TestStatus.PASSED.value == "passed"
        assert TestStatus.FAILED.value == "failed"
        assert TestStatus.ERROR.value == "error"


class TestTestResult:
    """Test the TestResult dataclass."""

    def test_create_result(self):
        """Test creating a test result."""
        result = TestResult(
            test_name="Test Name",
            test_type=TestType.FUNCTIONAL,
            status=TestStatus.PASSED,
            duration_ms=100,
        )
        assert result.test_name == "Test Name"
        assert result.test_type == TestType.FUNCTIONAL
        assert result.status == TestStatus.PASSED
        assert result.duration_ms == 100
        assert result.details is None
        assert result.error_message is None
        assert result.chaos_scenario is None

    def test_create_result_with_details(self):
        """Test creating a test result with all fields."""
        result = TestResult(
            test_name="Test Name",
            test_type=TestType.CHAOS,
            status=TestStatus.FAILED,
            duration_ms=500,
            details={"key": "value"},
            error_message="Something went wrong",
            chaos_scenario="node_failure",
        )
        assert result.details == {"key": "value"}
        assert result.error_message == "Something went wrong"
        assert result.chaos_scenario == "node_failure"


# =============================================================================
# HNSW Test Runner Tests
# =============================================================================

class TestHNSWGrpcClientManager:
    """Test the HNSWGrpcClientManager singleton."""

    def test_singleton_pattern(self):
        """Test that HNSWGrpcClientManager is a singleton."""
        # Reset the singleton for testing
        HNSWGrpcClientManager._instance = None
        HNSWGrpcClientManager._stubs_compiled = False
        HNSWGrpcClientManager._proto_module_path = None
        HNSWGrpcClientManager._compilation_error = None

        with patch('backend.services.distributed_tests_vector.os.path.exists', return_value=False):
            manager1 = HNSWGrpcClientManager()
            manager2 = HNSWGrpcClientManager()

        assert manager1 is manager2

    @patch('backend.services.distributed_tests_vector.os.path.exists')
    def test_get_proto_path_not_found(self, mock_exists):
        """Test getting proto path when file doesn't exist."""
        mock_exists.return_value = False

        # Reset singleton
        HNSWGrpcClientManager._instance = None
        HNSWGrpcClientManager._stubs_compiled = False
        HNSWGrpcClientManager._proto_module_path = None
        HNSWGrpcClientManager._compilation_error = None

        manager = HNSWGrpcClientManager()
        proto_path = manager._get_proto_path()

        assert proto_path is None

    def test_is_ready_with_error(self):
        """Test is_ready when there's a compilation error."""
        HNSWGrpcClientManager._instance = None
        HNSWGrpcClientManager._stubs_compiled = False
        HNSWGrpcClientManager._compilation_error = "Test error"

        with patch('backend.services.distributed_tests_vector.os.path.exists', return_value=False):
            manager = HNSWGrpcClientManager()

        ready, error = manager.is_ready()
        assert ready is False
        assert error == "Test error"

        # Reset
        HNSWGrpcClientManager._compilation_error = None

    def test_create_channel_https(self):
        """Test creating a secure channel for HTTPS URLs."""
        HNSWGrpcClientManager._instance = None
        HNSWGrpcClientManager._stubs_compiled = False
        HNSWGrpcClientManager._compilation_error = None

        with patch('backend.services.distributed_tests_vector.os.path.exists', return_value=False):
            manager = HNSWGrpcClientManager()

        channel = manager._create_channel("https://example.run.app")
        assert channel is not None

    def test_create_channel_http(self):
        """Test creating an insecure channel for HTTP URLs."""
        HNSWGrpcClientManager._instance = None
        HNSWGrpcClientManager._stubs_compiled = False
        HNSWGrpcClientManager._compilation_error = None

        with patch('backend.services.distributed_tests_vector.os.path.exists', return_value=False):
            manager = HNSWGrpcClientManager()

        channel = manager._create_channel("http://localhost:50051")
        assert channel is not None

    def test_get_hnsw_stub_not_compiled(self):
        """Test getting stub when proto isn't compiled."""
        HNSWGrpcClientManager._instance = None
        HNSWGrpcClientManager._stubs_compiled = False
        HNSWGrpcClientManager._compilation_error = None

        with patch('backend.services.distributed_tests_vector.os.path.exists', return_value=False):
            manager = HNSWGrpcClientManager()

        stub, proto, error = manager.get_hnsw_stub("https://example.run.app")

        assert stub is None
        assert proto is None
        assert error is not None


class TestHNSWTestRunner:
    """Test the HNSWTestRunner class."""

    @pytest.fixture
    def mock_grpc_manager(self):
        """Create a mock HNSWGrpcClientManager that returns proper errors."""
        with patch.object(HNSWGrpcClientManager, '__new__') as mock_new:
            mock_manager = Mock()
            mock_manager.get_hnsw_stub.return_value = (None, None, "Proto not compiled")
            mock_manager.is_ready.return_value = (False, "Proto not compiled")
            mock_new.return_value = mock_manager
            yield mock_manager

    @pytest.fixture
    def runner(self, mock_grpc_manager):
        """Create a test runner with mock gRPC."""
        return HNSWTestRunner(
            cluster_urls=["https://hnsw-123-node1-xyz.run.app"],
            submission_id=123,
        )

    def test_initialization(self, runner):
        """Test runner initialization."""
        assert runner.cluster_size == 1
        assert runner.submission_id == 123
        assert len(runner.cluster_urls) == 1

    def test_generate_random_vector(self, runner):
        """Test random vector generation."""
        vector = runner._generate_random_vector(128)
        assert len(vector) == 128
        # Check it's roughly unit norm
        import math
        norm = math.sqrt(sum(x*x for x in vector))
        assert abs(norm - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_create_index_no_grpc(self, runner):
        """Test create index when gRPC isn't available."""
        result = await runner._test_create_index()

        assert result.test_name == "Create Index"
        assert result.test_type == TestType.FUNCTIONAL
        assert result.status == TestStatus.FAILED
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_run_functional_tests(self, runner):
        """Test running functional tests."""
        results = await runner.run_functional_tests()

        assert len(results) == 5
        for result in results:
            assert result.test_type == TestType.FUNCTIONAL

    @pytest.mark.asyncio
    async def test_run_performance_tests(self, runner):
        """Test running performance tests."""
        results = await runner.run_performance_tests()

        assert len(results) == 2
        for result in results:
            assert result.test_type == TestType.PERFORMANCE

    @pytest.mark.asyncio
    async def test_run_all_tests(self, runner):
        """Test running all tests."""
        results = await runner.run_all_tests()

        assert len(results) == 7  # 5 functional + 2 performance


# =============================================================================
# IVF Test Runner Tests
# =============================================================================

class TestIVFGrpcClientManager:
    """Test the IVFGrpcClientManager singleton."""

    def test_singleton_pattern(self):
        """Test that IVFGrpcClientManager is a singleton."""
        # Reset the singleton for testing
        IVFGrpcClientManager._instance = None
        IVFGrpcClientManager._stubs_compiled = False
        IVFGrpcClientManager._proto_module_path = None
        IVFGrpcClientManager._compilation_error = None

        with patch('backend.services.distributed_tests_vector.os.path.exists', return_value=False):
            manager1 = IVFGrpcClientManager()
            manager2 = IVFGrpcClientManager()

        assert manager1 is manager2

    def test_is_ready_with_error(self):
        """Test is_ready when there's a compilation error."""
        IVFGrpcClientManager._instance = None
        IVFGrpcClientManager._stubs_compiled = False
        IVFGrpcClientManager._compilation_error = "Test error"

        with patch('backend.services.distributed_tests_vector.os.path.exists', return_value=False):
            manager = IVFGrpcClientManager()

        ready, error = manager.is_ready()
        assert ready is False
        assert error == "Test error"

        # Reset
        IVFGrpcClientManager._compilation_error = None

    def test_get_ivf_stub_not_compiled(self):
        """Test getting stub when proto isn't compiled."""
        IVFGrpcClientManager._instance = None
        IVFGrpcClientManager._stubs_compiled = False
        IVFGrpcClientManager._compilation_error = None

        with patch('backend.services.distributed_tests_vector.os.path.exists', return_value=False):
            manager = IVFGrpcClientManager()

        stub, proto, error = manager.get_ivf_stub("https://example.run.app")

        assert stub is None
        assert proto is None
        assert error is not None


class TestIVFTestRunner:
    """Test the IVFTestRunner class."""

    @pytest.fixture
    def mock_grpc_manager(self):
        """Create a mock IVFGrpcClientManager that returns proper errors."""
        with patch.object(IVFGrpcClientManager, '__new__') as mock_new:
            mock_manager = Mock()
            mock_manager.get_ivf_stub.return_value = (None, None, "Proto not compiled")
            mock_manager.is_ready.return_value = (False, "Proto not compiled")
            mock_new.return_value = mock_manager
            yield mock_manager

    @pytest.fixture
    def runner(self, mock_grpc_manager):
        """Create a test runner with mock gRPC."""
        return IVFTestRunner(
            cluster_urls=["https://ivf-123-node1-xyz.run.app"],
            submission_id=123,
        )

    def test_initialization(self, runner):
        """Test runner initialization."""
        assert runner.cluster_size == 1
        assert runner.submission_id == 123
        assert len(runner.cluster_urls) == 1

    @pytest.mark.asyncio
    async def test_create_index_no_grpc(self, runner):
        """Test create index when gRPC isn't available."""
        result = await runner._test_create_index()

        assert result.test_name == "Create Index"
        assert result.test_type == TestType.FUNCTIONAL
        assert result.status == TestStatus.FAILED
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_run_functional_tests(self, runner):
        """Test running functional tests."""
        results = await runner.run_functional_tests()

        assert len(results) == 5
        for result in results:
            assert result.test_type == TestType.FUNCTIONAL

    @pytest.mark.asyncio
    async def test_run_performance_tests(self, runner):
        """Test running performance tests."""
        results = await runner.run_performance_tests()

        assert len(results) == 1
        for result in results:
            assert result.test_type == TestType.PERFORMANCE

    @pytest.mark.asyncio
    async def test_run_all_tests(self, runner):
        """Test running all tests."""
        results = await runner.run_all_tests()

        assert len(results) == 6  # 5 functional + 1 performance


# =============================================================================
# PQ Test Runner Tests
# =============================================================================

class TestPQGrpcClientManager:
    """Test the PQGrpcClientManager singleton."""

    def test_singleton_pattern(self):
        """Test that PQGrpcClientManager is a singleton."""
        # Reset the singleton for testing
        PQGrpcClientManager._instance = None
        PQGrpcClientManager._stubs_compiled = False
        PQGrpcClientManager._proto_module_path = None
        PQGrpcClientManager._compilation_error = None

        with patch('backend.services.distributed_tests_vector.os.path.exists', return_value=False):
            manager1 = PQGrpcClientManager()
            manager2 = PQGrpcClientManager()

        assert manager1 is manager2

    def test_is_ready_with_error(self):
        """Test is_ready when there's a compilation error."""
        PQGrpcClientManager._instance = None
        PQGrpcClientManager._stubs_compiled = False
        PQGrpcClientManager._compilation_error = "Test error"

        with patch('backend.services.distributed_tests_vector.os.path.exists', return_value=False):
            manager = PQGrpcClientManager()

        ready, error = manager.is_ready()
        assert ready is False
        assert error == "Test error"

        # Reset
        PQGrpcClientManager._compilation_error = None

    def test_get_pq_stub_not_compiled(self):
        """Test getting stub when proto isn't compiled."""
        PQGrpcClientManager._instance = None
        PQGrpcClientManager._stubs_compiled = False
        PQGrpcClientManager._compilation_error = None

        with patch('backend.services.distributed_tests_vector.os.path.exists', return_value=False):
            manager = PQGrpcClientManager()

        stub, proto, error = manager.get_pq_stub("https://example.run.app")

        assert stub is None
        assert proto is None
        assert error is not None


class TestPQTestRunner:
    """Test the PQTestRunner class."""

    @pytest.fixture
    def mock_grpc_manager(self):
        """Create a mock PQGrpcClientManager that returns proper errors."""
        with patch.object(PQGrpcClientManager, '__new__') as mock_new:
            mock_manager = Mock()
            mock_manager.get_pq_stub.return_value = (None, None, "Proto not compiled")
            mock_manager.is_ready.return_value = (False, "Proto not compiled")
            mock_new.return_value = mock_manager
            yield mock_manager

    @pytest.fixture
    def runner(self, mock_grpc_manager):
        """Create a test runner with mock gRPC."""
        return PQTestRunner(
            cluster_urls=["https://pq-123-node1-xyz.run.app"],
            submission_id=123,
        )

    def test_initialization(self, runner):
        """Test runner initialization."""
        assert runner.cluster_size == 1
        assert runner.submission_id == 123
        assert len(runner.cluster_urls) == 1

    @pytest.mark.asyncio
    async def test_create_index_no_grpc(self, runner):
        """Test create index when gRPC isn't available."""
        result = await runner._test_create_index()

        assert result.test_name == "Create Index"
        assert result.test_type == TestType.FUNCTIONAL
        assert result.status == TestStatus.FAILED
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_run_functional_tests(self, runner):
        """Test running functional tests."""
        results = await runner.run_functional_tests()

        assert len(results) == 5
        for result in results:
            assert result.test_type == TestType.FUNCTIONAL

    @pytest.mark.asyncio
    async def test_run_performance_tests(self, runner):
        """Test running performance tests."""
        results = await runner.run_performance_tests()

        assert len(results) == 2
        for result in results:
            assert result.test_type == TestType.PERFORMANCE

    @pytest.mark.asyncio
    async def test_run_all_tests(self, runner):
        """Test running all tests."""
        results = await runner.run_all_tests()

        assert len(results) == 7  # 5 functional + 2 performance


class TestVectorGeneration:
    """Test vector generation across all runners."""

    def test_hnsw_vector_dimensions(self):
        """Test HNSW runner generates correct dimension vectors."""
        with patch.object(HNSWGrpcClientManager, '__new__') as mock_new:
            mock_manager = Mock()
            mock_manager.get_hnsw_stub.return_value = (None, None, "Not compiled")
            mock_new.return_value = mock_manager

            runner = HNSWTestRunner(["http://localhost:50051"], 1)

            for dim in [64, 128, 256, 512]:
                vec = runner._generate_random_vector(dim)
                assert len(vec) == dim

    def test_ivf_vector_dimensions(self):
        """Test IVF runner generates correct dimension vectors."""
        with patch.object(IVFGrpcClientManager, '__new__') as mock_new:
            mock_manager = Mock()
            mock_manager.get_ivf_stub.return_value = (None, None, "Not compiled")
            mock_new.return_value = mock_manager

            runner = IVFTestRunner(["http://localhost:50051"], 1)

            for dim in [64, 128, 256, 512]:
                vec = runner._generate_random_vector(dim)
                assert len(vec) == dim

    def test_pq_vector_dimensions(self):
        """Test PQ runner generates correct dimension vectors."""
        with patch.object(PQGrpcClientManager, '__new__') as mock_new:
            mock_manager = Mock()
            mock_manager.get_pq_stub.return_value = (None, None, "Not compiled")
            mock_new.return_value = mock_manager

            runner = PQTestRunner(["http://localhost:50051"], 1)

            for dim in [64, 128, 256, 512]:
                vec = runner._generate_random_vector(dim)
                assert len(vec) == dim
