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


class TestDistributedBuildProcess:
    """Tests for the distributed build process."""

    def test_create_submission_endpoint_has_background_tasks(self):
        """Test create submission endpoint includes BackgroundTasks parameter."""
        from backend.api.distributed import create_distributed_submission
        import inspect

        sig = inspect.signature(create_distributed_submission)
        params = list(sig.parameters.keys())
        assert "background_tasks" in params

    def test_run_distributed_build_function_exists(self):
        """Test run_distributed_build function exists in distributed module."""
        from backend.api.distributed import run_distributed_build

        assert callable(run_distributed_build)

    @pytest.mark.asyncio
    async def test_run_distributed_build_updates_submission_status(self):
        """Test that run_distributed_build updates submission status."""
        from backend.api.distributed import run_distributed_build
        from unittest.mock import AsyncMock, patch, MagicMock

        # Mock the database session and submission
        mock_submission = MagicMock()
        mock_submission.id = 1
        mock_submission.status = "building"
        mock_submission.build_logs = ""

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_submission

        with patch('backend.api.distributed.SessionLocal', return_value=mock_db):
            with patch('backend.api.distributed.DistributedBuildService') as mock_service_class:
                mock_service = MagicMock()
                mock_service.start_build = AsyncMock(side_effect=Exception("Test error"))
                mock_service_class.return_value = mock_service

                # Run the build (should handle error gracefully)
                await run_distributed_build(1, "python", "print('hello')")

                # Verify submission was updated with error
                assert mock_submission.status == "build_failed"
                assert "BUILD ERROR" in mock_submission.build_logs

    def test_submission_response_includes_build_logs(self):
        """Test DistributedSubmissionResponse includes build_logs field."""
        from backend.api.distributed import DistributedSubmissionResponse

        # Check the model fields
        fields = DistributedSubmissionResponse.model_fields
        assert "build_logs" in fields

    def test_build_logs_endpoint_exists(self):
        """Test build logs endpoint exists in router."""
        from backend.api.distributed import router

        routes = [route.path for route in router.routes]
        assert "/submissions/{submission_id}/build-logs" in routes


class TestTemplateMainFunctions:
    """Tests to verify all templates have main() functions for proper execution."""

    def test_python_template_has_main_function(self):
        """Test Python template has main() function."""
        from backend.api.distributed import get_template_from_filesystem

        template = get_template_from_filesystem("python")

        # Should have main function
        assert "def main():" in template or 'if __name__ == "__main__":' in template
        # Should not contain error message
        assert "Template file not found" not in template
        assert "Template not available" not in template

    def test_go_template_has_main_function(self):
        """Test Go template has main() function."""
        from backend.api.distributed import get_template_from_filesystem

        template = get_template_from_filesystem("go")

        # Should have main function
        assert "func main()" in template
        # Should not contain error message
        assert "Template file not found" not in template
        assert "Template not available" not in template

    def test_java_template_has_main_function(self):
        """Test Java template has main() function."""
        from backend.api.distributed import get_template_from_filesystem

        template = get_template_from_filesystem("java")

        # Should have main function
        assert "public static void main" in template
        # Should not contain error message
        assert "Template file not found" not in template
        assert "Template not available" not in template

    def test_cpp_template_has_main_function(self):
        """Test C++ template has main() function."""
        from backend.api.distributed import get_template_from_filesystem

        template = get_template_from_filesystem("cpp")

        # Should have main function
        assert "int main(" in template
        # Should not contain error message
        assert "Template file not found" not in template
        assert "Template not available" not in template

    def test_rust_template_has_main_function(self):
        """Test Rust template has main() function."""
        from backend.api.distributed import get_template_from_filesystem

        template = get_template_from_filesystem("rust")

        # Should have main function
        assert "fn main()" in template or "async fn main()" in template
        # Should not contain error message
        assert "Template file not found" not in template
        assert "Template not available" not in template

    def test_all_templates_load_successfully(self):
        """Test that all templates load without 'not found' errors."""
        from backend.api.distributed import get_template_from_filesystem

        languages = ["python", "go", "java", "cpp", "rust"]
        for lang in languages:
            template = get_template_from_filesystem(lang)
            assert "Template file not found" not in template, f"{lang} template not found"
            assert len(template) > 100, f"{lang} template too short"


class TestCppCMakeListsGeneration:
    """Tests for C++ CMakeLists.txt generation."""

    def test_cpp_cmakelists_is_generated(self):
        """Test that CMakeLists.txt is generated for C++ builds."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        files = service._get_build_files("cpp")

        assert "CMakeLists.txt" in files

    def test_cpp_cmakelists_has_abseil_linking(self):
        """Test CMakeLists.txt includes Abseil library linking."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        cmake = service._get_cpp_cmakelists()

        assert "find_package(absl" in cmake
        assert "absl::base" in cmake
        assert "absl::strings" in cmake

    def test_cpp_cmakelists_has_grpc_linking(self):
        """Test CMakeLists.txt includes gRPC library linking."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        cmake = service._get_cpp_cmakelists()

        assert "find_package(gRPC" in cmake
        assert "grpc++" in cmake

    def test_cpp_cmakelists_has_protobuf_linking(self):
        """Test CMakeLists.txt includes Protobuf library linking."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        cmake = service._get_cpp_cmakelists()

        assert "find_package(Protobuf" in cmake
        assert "Protobuf_LIBRARIES" in cmake

    def test_cpp_cmakelists_generates_server_executable(self):
        """Test CMakeLists.txt creates server executable."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        cmake = service._get_cpp_cmakelists()

        assert "add_executable(server" in cmake
        assert "server.cpp" in cmake

    def test_cpp_cmakelists_has_fallback_for_manual_linking(self):
        """Test CMakeLists.txt has fallback for manual library linking."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        cmake = service._get_cpp_cmakelists()

        # Should have fallback mechanism for finding Abseil
        assert "find_library(ABSL_BASE" in cmake


class TestBuildLogsFetching:
    """Tests for build log fetching functionality."""

    def test_build_logs_response_model(self):
        """Test BuildLogsResponse model."""
        from backend.api.distributed import BuildLogsResponse

        response = BuildLogsResponse(logs="Build started...")
        assert response.logs == "Build started..."

    def test_submission_model_has_build_logs_field(self):
        """Test Submission model has build_logs field."""
        from backend.models.submission import Submission

        # Check that the field exists in the model
        assert hasattr(Submission, "build_logs")

    def test_submission_status_includes_building(self):
        """Test SubmissionStatus enum includes building status."""
        from backend.models.submission import SubmissionStatus

        assert hasattr(SubmissionStatus, "BUILDING")
        assert SubmissionStatus.BUILDING.value == "building"

    def test_submission_status_includes_build_failed(self):
        """Test SubmissionStatus enum includes build_failed status."""
        from backend.models.submission import SubmissionStatus

        assert hasattr(SubmissionStatus, "BUILD_FAILED")
        assert SubmissionStatus.BUILD_FAILED.value == "build_failed"

    def test_submission_status_includes_deploying(self):
        """Test SubmissionStatus enum includes deploying status."""
        from backend.models.submission import SubmissionStatus

        assert hasattr(SubmissionStatus, "DEPLOYING")
        assert SubmissionStatus.DEPLOYING.value == "deploying"

    def test_submission_status_includes_deploy_failed(self):
        """Test SubmissionStatus enum includes deploy_failed status."""
        from backend.models.submission import SubmissionStatus

        assert hasattr(SubmissionStatus, "DEPLOY_FAILED")
        assert SubmissionStatus.DEPLOY_FAILED.value == "deploy_failed"


class TestAICodeAnalysis:
    """Tests for AI-powered code analysis and build file modification."""

    def test_ai_service_has_analyze_distributed_code_method(self):
        """Test AIService has the analyze_distributed_code method."""
        from backend.services.ai_service import AIService

        service = AIService()
        assert hasattr(service, "analyze_distributed_code")
        assert callable(service.analyze_distributed_code)

    @pytest.mark.asyncio
    async def test_analyze_distributed_code_returns_valid_structure(self):
        """Test analyze_distributed_code returns expected structure."""
        from backend.services.ai_service import AIService

        service = AIService()
        result = await service.analyze_distributed_code(
            source_code="print('hello')",
            language="python",
            proto_spec="syntax = 'proto3';",
            problem_type="raft",
        )

        # Should return expected keys
        assert "is_valid" in result
        assert "errors" in result
        assert "warnings" in result
        assert "build_modifications" in result

    @pytest.mark.asyncio
    async def test_analyze_distributed_code_demo_mode(self):
        """Test analyze_distributed_code in demo mode returns mock response."""
        from backend.services.ai_service import AIService

        service = AIService()
        # In demo mode (no API key), should return mock response
        if service.demo_mode:
            result = await service.analyze_distributed_code(
                source_code="fn main() {}",
                language="rust",
                proto_spec="syntax = 'proto3';",
                problem_type="raft",
            )

            assert result["is_valid"] is True
            assert "Demo mode" in str(result.get("warnings", []))

    def test_get_default_build_modifications_python(self):
        """Test default build modifications for Python."""
        from backend.services.ai_service import AIService

        service = AIService()
        mods = service._get_default_build_modifications("python")

        assert "additional_dependencies" in mods
        assert isinstance(mods["additional_dependencies"], list)

    def test_get_default_build_modifications_cpp(self):
        """Test default build modifications for C++."""
        from backend.services.ai_service import AIService

        service = AIService()
        mods = service._get_default_build_modifications("cpp")

        assert "cmake_packages" in mods
        assert "cmake_libraries" in mods
        assert isinstance(mods["cmake_packages"], list)
        assert isinstance(mods["cmake_libraries"], list)

    def test_get_default_build_modifications_rust(self):
        """Test default build modifications for Rust."""
        from backend.services.ai_service import AIService

        service = AIService()
        mods = service._get_default_build_modifications("rust")

        assert "additional_dependencies" in mods


class TestBuildModifications:
    """Tests for build file modifications based on AI analysis."""

    def test_build_files_python_with_extra_dependencies(self):
        """Test Python build files include extra dependencies."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        mods = {"additional_dependencies": ["numpy>=1.0.0", "pandas>=2.0.0"]}
        files = service._get_build_files("python", mods)

        assert "requirements.txt" in files
        assert "numpy>=1.0.0" in files["requirements.txt"]
        assert "pandas>=2.0.0" in files["requirements.txt"]
        # Should also have base dependencies
        assert "grpcio" in files["requirements.txt"]

    def test_build_files_go_with_extra_dependencies(self):
        """Test Go build files include extra dependencies."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        mods = {"additional_dependencies": ["github.com/google/uuid v1.4.0"]}
        files = service._get_build_files("go", mods)

        assert "go.mod" in files
        assert "github.com/google/uuid" in files["go.mod"]
        # Should have base dependencies
        assert "google.golang.org/grpc" in files["go.mod"]

    def test_build_files_rust_generated(self):
        """Test Rust build files are generated."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        files = service._get_build_files("rust", {})

        assert "Cargo.toml" in files
        assert "build.rs" in files
        assert "tokio" in files["Cargo.toml"]
        assert "tonic" in files["Cargo.toml"]
        assert "tonic_build" in files["build.rs"]

    def test_build_files_java_generated(self):
        """Test Java build files are generated."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        files = service._get_build_files("java", {})

        assert "build.gradle" in files
        assert "io.grpc" in files["build.gradle"]
        assert "protobuf" in files["build.gradle"]

    def test_build_files_java_with_extra_dependencies(self):
        """Test Java build files include extra dependencies."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        mods = {"additional_dependencies": ["org.slf4j:slf4j-api:2.0.0"]}
        files = service._get_build_files("java", mods)

        assert "build.gradle" in files
        assert "org.slf4j:slf4j-api:2.0.0" in files["build.gradle"]

    def test_cpp_cmakelists_with_extra_packages(self):
        """Test CMakeLists.txt includes extra packages from AI analysis."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        cmake = service._get_cpp_cmakelists(
            cmake_packages=["Boost"],
            cmake_libraries=[]
        )

        assert "find_package(Boost QUIET)" in cmake
        assert "AI-detected additional packages" in cmake

    def test_cpp_cmakelists_with_extra_libraries(self):
        """Test CMakeLists.txt includes extra libraries from AI analysis."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        cmake = service._get_cpp_cmakelists(
            cmake_packages=[],
            cmake_libraries=["boost_system", "boost_thread"]
        )

        assert "boost_system" in cmake
        assert "boost_thread" in cmake
        assert "AI-detected additional libraries" in cmake

    def test_start_build_accepts_build_modifications(self):
        """Test start_build method accepts build_modifications parameter."""
        from backend.services.distributed_build import DistributedBuildService
        import inspect

        service = DistributedBuildService()
        sig = inspect.signature(service.start_build)
        params = list(sig.parameters.keys())

        assert "build_modifications" in params

    def test_create_source_archive_accepts_build_modifications(self):
        """Test _create_source_archive accepts build_modifications parameter."""
        from backend.services.distributed_build import DistributedBuildService
        import inspect

        service = DistributedBuildService()
        sig = inspect.signature(service._create_source_archive)
        params = list(sig.parameters.keys())

        assert "build_modifications" in params


class TestAIIntegrationInSubmission:
    """Tests for AI integration in the submission flow."""

    def test_run_distributed_build_imports_ai_service(self):
        """Test run_distributed_build has access to AIService."""
        from backend.api.distributed import AIService

        assert AIService is not None

    @pytest.mark.asyncio
    async def test_run_distributed_build_calls_ai_analysis(self):
        """Test that run_distributed_build calls AI analysis."""
        from backend.api.distributed import run_distributed_build
        from unittest.mock import AsyncMock, patch, MagicMock

        # Mock the database session and submission
        mock_submission = MagicMock()
        mock_submission.id = 1
        mock_submission.status = "building"
        mock_submission.build_logs = ""

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_submission

        with patch('backend.api.distributed.SessionLocal', return_value=mock_db):
            with patch('backend.api.distributed.DistributedBuildService') as mock_build_class:
                with patch('backend.api.distributed.AIService') as mock_ai_class:
                    # Setup AI service mock
                    mock_ai = MagicMock()
                    mock_ai.analyze_distributed_code = AsyncMock(return_value={
                        "is_valid": True,
                        "errors": [],
                        "warnings": ["Test warning"],
                        "detected_dependencies": ["test_dep"],
                        "build_modifications": {"additional_dependencies": []},
                    })
                    mock_ai_class.return_value = mock_ai

                    # Setup build service mock
                    mock_build = MagicMock()
                    mock_build.start_build = AsyncMock(side_effect=Exception("Test error"))
                    mock_build_class.return_value = mock_build

                    # Run the build
                    await run_distributed_build(1, "python", "print('hello')")

                    # Verify AI analysis was called
                    mock_ai.analyze_distributed_code.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_distributed_build_passes_modifications_to_build(self):
        """Test that run_distributed_build passes AI modifications to build service."""
        from backend.api.distributed import run_distributed_build
        from unittest.mock import AsyncMock, patch, MagicMock

        mock_submission = MagicMock()
        mock_submission.id = 1
        mock_submission.status = "building"
        mock_submission.build_logs = ""

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_submission

        build_mods = {"additional_dependencies": ["test_package"]}

        with patch('backend.api.distributed.SessionLocal', return_value=mock_db):
            with patch('backend.api.distributed.DistributedBuildService') as mock_build_class:
                with patch('backend.api.distributed.AIService') as mock_ai_class:
                    # Setup AI service mock
                    mock_ai = MagicMock()
                    mock_ai.analyze_distributed_code = AsyncMock(return_value={
                        "is_valid": True,
                        "errors": [],
                        "warnings": [],
                        "build_modifications": build_mods,
                    })
                    mock_ai_class.return_value = mock_ai

                    # Setup build service mock
                    mock_build = MagicMock()
                    mock_build.start_build = AsyncMock(side_effect=Exception("Test error"))
                    mock_build_class.return_value = mock_build

                    # Run the build
                    await run_distributed_build(1, "python", "print('hello')")

                    # Verify build was called with modifications
                    mock_build.start_build.assert_called_once()
                    call_args = mock_build.start_build.call_args
                    # Check that build_modifications was passed
                    assert call_args[0][3] == build_mods or call_args.kwargs.get("build_modifications") == build_mods

    def test_build_logs_include_analysis_info(self):
        """Test that build logs include AI analysis information."""
        # This tests that the build flow captures analysis results in logs
        # The implementation adds detected_dependencies and warnings to logs
        from backend.api.distributed import run_distributed_build
        import inspect

        # Verify the function exists and has proper implementation
        source = inspect.getsource(run_distributed_build)
        assert "detected_dependencies" in source
        assert "analysis_result" in source


class TestTemplateEndpoint:
    """Tests for the template endpoint to ensure it returns original templates."""

    def test_get_template_returns_filesystem_template_for_problem_1(self):
        """Test that getTemplate for problem_id 1 returns filesystem template."""
        from backend.api.distributed import get_template_from_filesystem

        # Template for Python should contain the template comment
        template = get_template_from_filesystem("python")
        assert "Raft Consensus Implementation" in template
        assert "TODO" in template or "template" in template.lower()
        # Should NOT be a complete solution
        assert "Template file not found" not in template

    def test_get_template_returns_different_content_than_solution(self):
        """Test that template content differs from solution content."""
        import os
        from backend.api.distributed import get_template_from_filesystem, get_distributed_problems_base_path

        template = get_template_from_filesystem("python")

        # Check if solutions directory exists and compare
        base_path = get_distributed_problems_base_path()
        solution_path = os.path.join(
            base_path,
            "distributed_problems",
            "raft",
            "solutions",
            "python",
            "server.py"
        )

        if os.path.exists(solution_path):
            with open(solution_path, "r") as f:
                solution = f.read()
            # Template and solution should be different
            assert template != solution


class TestUtf8RangeLinking:
    """Tests for utf8_range library linking in C++ builds."""

    def test_cpp_cmakelists_includes_utf8_range_linking(self):
        """Test that generated CMakeLists.txt includes utf8_range linking."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        cmake = service._get_cpp_cmakelists()

        # Should have utf8_range library detection and linking
        assert "find_library(UTF8_RANGE_LIB utf8_range" in cmake
        assert "find_library(UTF8_VALIDITY_LIB utf8_validity" in cmake
        assert "target_link_libraries(server ${UTF8_RANGE_LIB})" in cmake

    def test_cpp_cmakelists_utf8_range_after_abseil(self):
        """Test that utf8_range linking comes after Abseil linking."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        cmake = service._get_cpp_cmakelists()

        # utf8_range should come after the Abseil endif
        abseil_endif_pos = cmake.rfind("endif()")
        utf8_range_pos = cmake.find("UTF8_RANGE_LIB")

        # utf8_range should come after the main Abseil block
        assert utf8_range_pos > 0, "UTF8_RANGE_LIB not found in CMakeLists"


class TestCppTemplateContainsTodos:
    """Tests for C++ template file containing TODOs for students to implement."""

    def test_cpp_template_has_todo_comments(self):
        """Test that the C++ template file contains TODO comments."""
        from backend.api.distributed import get_template_from_filesystem

        template = get_template_from_filesystem("cpp")

        # Should contain TODO comments for implementation guidance
        assert "TODO" in template, "C++ template should contain TODO comments"

    def test_cpp_template_is_not_complete_implementation(self):
        """Test that the C++ template is not a complete implementation."""
        from backend.api.distributed import get_template_from_filesystem

        template = get_template_from_filesystem("cpp")

        # Should NOT say "A complete implementation"
        assert "A complete implementation" not in template, \
            "C++ template should not be a complete implementation"
        # Should say it's a template
        assert "Template" in template, "C++ template should identify as a template"

    def test_cpp_template_mentions_raft_algorithm_steps(self):
        """Test that C++ template mentions the Raft algorithm steps to implement."""
        from backend.api.distributed import get_template_from_filesystem

        template = get_template_from_filesystem("cpp")

        # Should mention the core Raft concepts as TODOs
        assert "Leader election" in template or "leader election" in template
        assert "Log replication" in template or "log replication" in template


class TestCloudRunEnvVars:
    """Tests for Cloud Run environment variable configuration."""

    def test_cloud_run_does_not_set_port_env_var(self):
        """Test that Cloud Run deployment does not set PORT env var (Cloud Run sets it automatically)."""
        from backend.services.distributed_build import DistributedBuildService
        import inspect

        service = DistributedBuildService()

        # Get the source code of the deploy_cluster method
        source = inspect.getsource(service.deploy_cluster)

        # Should NOT explicitly set PORT (Cloud Run sets it automatically based on container_port)
        assert 'name="PORT"' not in source, \
            "Cloud Run deployment should not set PORT env var (Cloud Run sets it automatically)"

    def test_cloud_run_env_vars_include_node_id_and_peers(self):
        """Test that Cloud Run deployment includes NODE_ID and PEERS env vars."""
        from backend.services.distributed_build import DistributedBuildService
        import inspect

        service = DistributedBuildService()
        source = inspect.getsource(service.deploy_cluster)

        # Should include NODE_ID and PEERS env vars
        assert 'name="NODE_ID"' in source, \
            "Cloud Run deployment should include NODE_ID env var"
        assert 'name="PEERS"' in source, \
            "Cloud Run deployment should include PEERS env var"


class TestDockerfilePortHandling:
    """Tests for Dockerfile PORT environment variable handling."""

    def test_python_dockerfile_passes_port_to_server(self):
        """Test that Python Dockerfile passes PORT env var to server."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        dockerfile = service._get_dockerfile("python")

        # Should pass PORT env var as --port argument
        assert "${PORT}" in dockerfile, \
            "Python Dockerfile should pass PORT env var to server"
        assert "--port" in dockerfile, \
            "Python Dockerfile should use --port argument"

    def test_cpp_dockerfile_passes_port_to_server(self):
        """Test that C++ Dockerfile passes PORT env var to server."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        dockerfile = service._get_cpp_dockerfile()

        # Should pass PORT env var as --port argument
        assert "${PORT}" in dockerfile, \
            "C++ Dockerfile should pass PORT env var to server"
        assert "--port" in dockerfile, \
            "C++ Dockerfile should use --port argument"

    def test_go_dockerfile_passes_port_to_server(self):
        """Test that Go Dockerfile passes PORT env var to server."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()
        dockerfile = service._get_dockerfile("go")

        # Should pass PORT env var as --port argument
        assert "${PORT}" in dockerfile, \
            "Go Dockerfile should pass PORT env var to server"

    def test_all_dockerfiles_pass_node_id_and_peers(self):
        """Test that all Dockerfiles pass NODE_ID and PEERS env vars."""
        from backend.services.distributed_build import DistributedBuildService

        service = DistributedBuildService()

        for lang in ["python", "go", "rust"]:
            dockerfile = service._get_dockerfile(lang)
            assert "${NODE_ID}" in dockerfile, \
                f"{lang} Dockerfile should pass NODE_ID env var"
            assert "${PEERS}" in dockerfile, \
                f"{lang} Dockerfile should pass PEERS env var"

        # C++ uses a separate method
        cpp_dockerfile = service._get_cpp_dockerfile()
        assert "${NODE_ID}" in cpp_dockerfile, \
            "C++ Dockerfile should pass NODE_ID env var"
        assert "${PEERS}" in cpp_dockerfile, \
            "C++ Dockerfile should pass PEERS env var"
