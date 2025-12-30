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

    def test_cpp_uses_prebuilt_base_image(self):
        """Test that C++ build uses prebuilt base image for faster builds."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        config = service.get_cloudbuild_config("cpp", 123)

        # Should use prebuilt base image
        steps_str = str(config["steps"])
        assert "raft-cpp-base" in steps_str
        assert "latest" in steps_str

    def test_cpp_build_has_reduced_timeout(self):
        """Test that C++ build timeout is reduced due to prebuilt dependencies."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        config = service.get_cloudbuild_config("cpp", 123)

        # With prebuilt deps, timeout should be 300s or less (not 900s)
        assert config["timeout"] == "300s"

    def test_cpp_dockerfile_uses_base_image_libraries(self):
        """Test that C++ Dockerfile copies libraries from prebuilt base image."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        dockerfile = service._get_dockerfile("cpp")

        # Should reference the base image for libraries
        assert "raft-cpp-base" in dockerfile
        assert "/usr/local/lib" in dockerfile
        assert "ldconfig" in dockerfile

    def test_cpp_dockerfile_includes_project_id(self):
        """Test that C++ Dockerfile correctly includes project ID."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        dockerfile = service._get_dockerfile("cpp")

        # Should include the project ID from settings
        assert service.project_id in dockerfile

    def test_cpp_build_copies_pregenerated_proto_files(self):
        """Test that C++ build copies pre-generated proto files from base image."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        config = service.get_cloudbuild_config("cpp", 123)

        # Should copy generated proto files
        steps_str = str(config["steps"])
        assert "cp -r /app/generated" in steps_str or "generated" in steps_str


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


class TestDistributedPathResolution:
    """Tests for distributed problems path resolution."""

    def test_get_distributed_problems_base_path_default(self):
        """Test that base path is resolved correctly."""
        from backend.api.distributed import get_distributed_problems_base_path

        base_path = get_distributed_problems_base_path()

        # Should return a valid path string
        assert isinstance(base_path, str)
        assert len(base_path) > 0

    def test_get_distributed_problems_base_path_with_env_var(self, monkeypatch):
        """Test that APP_BASE_PATH environment variable is used."""
        from backend.api.distributed import get_distributed_problems_base_path

        monkeypatch.setenv("APP_BASE_PATH", "/custom/path")
        base_path = get_distributed_problems_base_path()

        assert base_path == "/custom/path"

    def test_get_distributed_problems_base_path_finds_files(self):
        """Test that the resolved path contains the expected files."""
        import os
        from backend.api.distributed import get_distributed_problems_base_path

        base_path = get_distributed_problems_base_path()
        proto_path = os.path.join(
            base_path,
            "distributed_problems",
            "raft",
            "proto",
            "raft.proto"
        )

        # The file should exist at the resolved path
        assert os.path.exists(proto_path), f"Proto file not found at {proto_path}"

    def test_template_file_exists_at_resolved_path(self):
        """Test that template files exist at the resolved path."""
        import os
        from backend.api.distributed import get_distributed_problems_base_path

        base_path = get_distributed_problems_base_path()
        python_template = os.path.join(
            base_path,
            "distributed_problems",
            "raft",
            "templates",
            "python",
            "server.py"
        )

        # The Python template should exist
        assert os.path.exists(python_template), f"Python template not found at {python_template}"


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


class TestSecurityAnalysis:
    """Tests for security analysis features in build configs."""

    def test_security_analysis_type_enum(self):
        """Test SecurityAnalysisType enum values."""
        from backend.services.distributed_build import SecurityAnalysisType

        assert SecurityAnalysisType.MEMORY_CORRUPTION.value == "memory_corruption"
        assert SecurityAnalysisType.BUFFER_OVERFLOW.value == "buffer_overflow"
        assert SecurityAnalysisType.RACE_CONDITION.value == "race_condition"
        assert SecurityAnalysisType.UNDEFINED_BEHAVIOR.value == "undefined_behavior"
        assert SecurityAnalysisType.CONCURRENCY.value == "concurrency"

    def test_security_finding_dataclass(self):
        """Test SecurityFinding dataclass."""
        from backend.services.distributed_build import SecurityFinding, SecurityAnalysisType

        finding = SecurityFinding(
            finding_type=SecurityAnalysisType.RACE_CONDITION,
            severity="high",
            message="Potential race condition detected",
            file="server.cpp",
            line=42,
            details={"variable": "counter"}
        )

        assert finding.finding_type == SecurityAnalysisType.RACE_CONDITION
        assert finding.severity == "high"
        assert finding.message == "Potential race condition detected"
        assert finding.file == "server.cpp"
        assert finding.line == 42

    def test_python_build_includes_bandit_security_analysis(self):
        """Test Python build includes Bandit security scanner."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        config = service.get_cloudbuild_config("python", 123)

        steps_str = str(config["steps"])
        assert "bandit" in steps_str
        assert "security_analysis.log" in steps_str

    def test_python_build_includes_safety_dependency_check(self):
        """Test Python build includes Safety for vulnerable dependencies."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        config = service.get_cloudbuild_config("python", 123)

        steps_str = str(config["steps"])
        assert "safety check" in steps_str

    def test_go_build_includes_race_detector(self):
        """Test Go build includes race detector."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        config = service.get_cloudbuild_config("go", 123)

        steps_str = str(config["steps"])
        assert "-race" in steps_str
        assert "go vet" in steps_str

    def test_go_build_includes_static_analysis(self):
        """Test Go build includes go vet static analysis."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        config = service.get_cloudbuild_config("go", 123)

        steps_str = str(config["steps"])
        assert "go vet" in steps_str

    def test_java_build_includes_spotbugs(self):
        """Test Java build includes SpotBugs analysis."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        config = service.get_cloudbuild_config("java", 123)

        steps_str = str(config["steps"])
        assert "spotbugs" in steps_str.lower()

    def test_cpp_build_includes_address_sanitizer(self):
        """Test C++ build includes AddressSanitizer for memory analysis."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        config = service.get_cloudbuild_config("cpp", 123)

        steps_str = str(config["steps"])
        assert "fsanitize=address" in steps_str
        assert "AddressSanitizer" in steps_str

    def test_cpp_build_includes_thread_sanitizer(self):
        """Test C++ build includes ThreadSanitizer for race detection."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        config = service.get_cloudbuild_config("cpp", 123)

        steps_str = str(config["steps"])
        assert "fsanitize=thread" in steps_str
        assert "ThreadSanitizer" in steps_str

    def test_rust_build_includes_clippy(self):
        """Test Rust build includes Clippy linter."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        config = service.get_cloudbuild_config("rust", 123)

        steps_str = str(config["steps"])
        assert "clippy" in steps_str

    def test_rust_build_includes_cargo_audit(self):
        """Test Rust build includes cargo audit for vulnerable dependencies."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        config = service.get_cloudbuild_config("rust", 123)

        steps_str = str(config["steps"])
        assert "cargo audit" in steps_str


class TestAdminDeploymentManagement:
    """Tests for admin deployment management endpoints."""

    def test_admin_router_has_teardown_endpoint(self):
        """Test admin router has teardown deployment endpoint."""
        from backend.api.admin import router

        routes = [route.path for route in router.routes]
        assert "/admin/deployments/{submission_id}/teardown" in routes

    def test_admin_router_has_cleanup_all_endpoint(self):
        """Test admin router has cleanup all deployments endpoint."""
        from backend.api.admin import router

        routes = [route.path for route in router.routes]
        assert "/admin/deployments/cleanup-all" in routes

    def test_admin_router_has_extend_endpoint(self):
        """Test admin router has extend deployment timeout endpoint."""
        from backend.api.admin import router

        routes = [route.path for route in router.routes]
        assert "/admin/deployments/{submission_id}/extend" in routes

    def test_admin_router_has_list_deployments_endpoint(self):
        """Test admin router has list deployments endpoint."""
        from backend.api.admin import router

        routes = [route.path for route in router.routes]
        assert "/admin/deployments" in routes
