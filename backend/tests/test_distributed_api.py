"""
Tests for the distributed consensus API endpoints.

These are unit tests that don't require a database connection.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestDistributedBuildService:
    """Tests for the distributed build service."""

    def test_get_cloudbuild_config_python(self):
        """Test generating Cloud Build config for Python."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        config = service.get_cloudbuild_config("python", 123)

        assert "steps" in config
        assert "images" in config
        assert len(config["steps"]) >= 2

    def test_get_cloudbuild_config_go(self):
        """Test generating Cloud Build config for Go."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        config = service.get_cloudbuild_config("go", 123)

        assert "steps" in config
        assert "golang" in str(config["steps"])

    def test_get_cloudbuild_config_java(self):
        """Test generating Cloud Build config for Java."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        config = service.get_cloudbuild_config("java", 123)

        assert "steps" in config
        assert "gradle" in str(config["steps"])

    def test_get_cloudbuild_config_cpp(self):
        """Test generating Cloud Build config for C++."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        config = service.get_cloudbuild_config("cpp", 123)

        assert "steps" in config
        assert "cmake" in str(config["steps"])

    def test_get_cloudbuild_config_rust(self):
        """Test generating Cloud Build config for Rust."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        config = service.get_cloudbuild_config("rust", 123)

        assert "steps" in config
        assert "cargo" in str(config["steps"])

    def test_get_source_filename(self):
        """Test getting source filename for each language."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()

        assert service._get_source_filename("python") == "server.py"
        assert service._get_source_filename("go") == "server.go"
        assert service._get_source_filename("java") == "RaftServer.java"
        assert service._get_source_filename("cpp") == "server.cpp"
        assert service._get_source_filename("rust") == "src/main.rs"

    def test_get_dockerfile_python(self):
        """Test getting Dockerfile for Python."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        dockerfile = service._get_dockerfile("python")

        assert "python" in dockerfile.lower()
        assert "pip install" in dockerfile

    def test_get_dockerfile_go(self):
        """Test getting Dockerfile for Go."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        dockerfile = service._get_dockerfile("go")

        assert "golang" in dockerfile.lower()
        assert "go build" in dockerfile

    def test_get_build_files_python(self):
        """Test getting build files for Python."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        files = service._get_build_files("python")

        assert "requirements.txt" in files
        assert "grpcio" in files["requirements.txt"]

    def test_get_build_files_go(self):
        """Test getting build files for Go."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        files = service._get_build_files("go")

        assert "go.mod" in files
        assert "grpc" in files["go.mod"].lower()


class TestDistributedTestRunner:
    """Tests for the distributed test runner."""

    def test_test_result_dataclass(self):
        """Test the TestResult dataclass."""
        from backend.services.distributed_tests import TestResult, TestType, TestStatus

        result = TestResult(
            test_name="Test",
            test_type=TestType.FUNCTIONAL,
            status=TestStatus.PASSED,
            duration_ms=100,
            details={"key": "value"},
        )

        assert result.test_name == "Test"
        assert result.test_type == TestType.FUNCTIONAL
        assert result.status == TestStatus.PASSED
        assert result.duration_ms == 100
        assert result.details == {"key": "value"}

    @pytest.mark.asyncio
    async def test_run_all_tests(self):
        """Test running all tests."""
        from backend.services.distributed_tests import DistributedTestRunner

        runner = DistributedTestRunner(["http://node1:50051", "http://node2:50051", "http://node3:50051"])
        results = await runner.run_all_tests()

        # Should have multiple test results
        assert len(results) > 0

        # Should have functional, performance, and chaos tests
        test_types = {r.test_type.value for r in results}
        assert "functional" in test_types
        assert "performance" in test_types
        assert "chaos" in test_types

    def test_test_type_enum(self):
        """Test TestType enum values."""
        from backend.services.distributed_tests import TestType

        assert TestType.FUNCTIONAL.value == "functional"
        assert TestType.PERFORMANCE.value == "performance"
        assert TestType.CHAOS.value == "chaos"

    def test_test_status_enum(self):
        """Test TestStatus enum values."""
        from backend.services.distributed_tests import TestStatus

        assert TestStatus.PENDING.value == "pending"
        assert TestStatus.RUNNING.value == "running"
        assert TestStatus.PASSED.value == "passed"
        assert TestStatus.FAILED.value == "failed"
        assert TestStatus.ERROR.value == "error"


class TestDistributedAPIHelpers:
    """Tests for distributed API helper functions."""

    def test_get_template_from_filesystem_python(self):
        """Test loading Python template from filesystem."""
        from backend.api.distributed import get_template_from_filesystem

        template = get_template_from_filesystem("python")

        # Template should contain Python code
        assert "class RaftNode" in template or "def " in template

    def test_get_template_from_filesystem_go(self):
        """Test loading Go template from filesystem."""
        from backend.api.distributed import get_template_from_filesystem

        template = get_template_from_filesystem("go")

        # Template should contain Go code
        assert "package main" in template or "func " in template

    def test_get_template_from_filesystem_java(self):
        """Test loading Java template from filesystem."""
        from backend.api.distributed import get_template_from_filesystem

        template = get_template_from_filesystem("java")

        # Template should contain Java code
        assert "class" in template

    def test_get_template_from_filesystem_cpp(self):
        """Test loading C++ template from filesystem."""
        from backend.api.distributed import get_template_from_filesystem

        template = get_template_from_filesystem("cpp")

        # Template should contain C++ code
        assert "class" in template or "#include" in template

    def test_get_template_from_filesystem_rust(self):
        """Test loading Rust template from filesystem."""
        from backend.api.distributed import get_template_from_filesystem

        template = get_template_from_filesystem("rust")

        # Template should contain Rust code
        assert "fn " in template or "pub " in template

    def test_get_proto_from_filesystem(self):
        """Test loading proto file from filesystem."""
        from backend.api.distributed import get_proto_from_filesystem

        proto = get_proto_from_filesystem()

        # Proto should contain service definitions
        assert "service" in proto or "message" in proto

    def test_get_build_command(self):
        """Test getting build commands for each language."""
        from backend.api.distributed import get_build_command

        assert "pip" in get_build_command("python")
        assert "go" in get_build_command("go")
        assert "gradle" in get_build_command("java")
        assert "cmake" in get_build_command("cpp")
        assert "cargo" in get_build_command("rust")

    def test_get_run_command(self):
        """Test getting run commands for each language."""
        from backend.api.distributed import get_run_command

        assert "python" in get_run_command("python")
        assert "./server" in get_run_command("go")
        assert "java" in get_run_command("java")
        assert "./build/server" in get_run_command("cpp") or "./server" in get_run_command("cpp")
        assert "release" in get_run_command("rust")
