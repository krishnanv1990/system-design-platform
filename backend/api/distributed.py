"""
Distributed Consensus Problems API routes.

Provides endpoints for:
- Listing distributed consensus problems (Raft, Paxos, etc.)
- Getting problem details with gRPC proto and language templates
- Saving/loading user code
- Creating and managing distributed submissions
"""

import os
import asyncio
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from google.cloud.devtools import cloudbuild_v1

from backend.database import get_db, SessionLocal
from backend.models.problem import Problem, ProblemType, SupportedLanguage
from backend.models.submission import Submission, SubmissionStatus, SubmissionType
from backend.models.user import User
from backend.auth.jwt_handler import get_current_user
from backend.services.distributed_build import DistributedBuildService
from backend.services.ai_service import AIService
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


# ============================================================================
# Pydantic Schemas
# ============================================================================

class LanguageTemplate(BaseModel):
    """Code template for a language."""
    language: str
    template: str
    build_command: str
    run_command: str


class TestScenario(BaseModel):
    """Test scenario for distributed system testing."""
    name: str
    description: str
    test_type: str  # functional, performance, chaos
    parameters: Optional[dict] = None


class DistributedProblemListResponse(BaseModel):
    """List response for distributed problems."""
    id: int
    title: str
    description: str
    difficulty: str
    problem_type: str
    supported_languages: List[str]
    cluster_size: int
    tags: Optional[List[str]] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class DistributedProblemResponse(BaseModel):
    """Full response for a distributed problem."""
    id: int
    title: str
    description: str
    difficulty: str
    problem_type: str
    grpc_proto: str
    supported_languages: List[str]
    cluster_size: int
    language_templates: dict
    test_scenarios: List[TestScenario]
    hints: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class TemplateResponse(BaseModel):
    """Response for template code."""
    template: str


class SavedCodeResponse(BaseModel):
    """Response for saved code."""
    code: str


class SaveCodeRequest(BaseModel):
    """Request to save code."""
    language: str
    code: str


class DistributedSubmissionCreate(BaseModel):
    """Create a distributed submission."""
    problem_id: int
    language: str
    source_code: str


class DistributedSubmissionResponse(BaseModel):
    """Response for a distributed submission."""
    id: int
    problem_id: int
    user_id: int
    submission_type: str
    language: str
    source_code: str
    status: str
    build_logs: Optional[str] = None
    build_artifact_url: Optional[str] = None
    cluster_node_urls: Optional[List[str]] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class BuildLogsResponse(BaseModel):
    """Response for build logs."""
    logs: str


# ============================================================================
# Background Build Task
# ============================================================================

async def run_distributed_build(submission_id: int, language: str, source_code: str, problem_id: int):
    """
    Background task to run the distributed build process.

    This function:
    1. Analyzes the code using Claude AI for spec validation and dependency detection
    2. Starts the Cloud Build job with AI-modified build files
    3. Monitors build progress and streams logs
    4. Updates submission status and stores logs in database
    5. Deploys the cluster on successful build
    """
    db = SessionLocal()
    try:
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        if not submission:
            logger.error(f"Submission {submission_id} not found")
            return

        build_service = DistributedBuildService()
        ai_service = AIService()
        project_id = settings.gcp_project_id

        # Get problem type from problem_id
        problem_type = get_problem_type_from_id(problem_id)
        config = PROBLEM_TYPE_CONFIG.get(problem_type, PROBLEM_TYPE_CONFIG["raft"])

        # Update status to building
        submission.status = SubmissionStatus.BUILDING.value
        submission.build_logs = f"Analyzing code and preparing build for {problem_type}...\n"
        db.commit()

        try:
            # Load the proto spec based on problem type
            proto_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "distributed_problems",
                config["directory"],
                "proto",
                config["proto_file"]
            )
            proto_spec = ""
            if os.path.exists(proto_path):
                with open(proto_path, "r") as f:
                    proto_spec = f.read()

            # Analyze code using Claude AI for spec validation and dependency detection
            logger.info(f"Analyzing code for submission {submission_id}, language: {language}, problem_type: {problem_type}")
            analysis_result = await ai_service.analyze_distributed_code(
                source_code=source_code,
                language=language,
                proto_spec=proto_spec,
                problem_type=problem_type,
            )

            # Log analysis results
            build_modifications = analysis_result.get("build_modifications", {})
            if analysis_result.get("errors"):
                submission.build_logs += f"Spec validation warnings: {', '.join(analysis_result['errors'])}\n"
            if analysis_result.get("warnings"):
                submission.build_logs += f"Analysis notes: {', '.join(analysis_result['warnings'])}\n"
            if analysis_result.get("detected_dependencies"):
                submission.build_logs += f"Detected dependencies: {', '.join(analysis_result['detected_dependencies'])}\n"

            submission.build_logs += "\nStarting build process...\n"
            db.commit()

            # Start the Cloud Build with AI-generated build modifications
            logger.info(f"Starting build for submission {submission_id}, language: {language}, problem_type: {problem_type}")
            build_id = await build_service.start_build(
                submission_id, language, source_code, build_modifications, problem_type
            )

            submission.build_logs = f"Build started. Build ID: {build_id}\n"
            db.commit()

            # Monitor build progress
            build_client = cloudbuild_v1.CloudBuildClient()
            logs_buffer = [f"Build ID: {build_id}\n", "=" * 50 + "\n"]

            import time
            start_time = time.time()
            last_log_fetch = 0

            while True:
                # Timeout after 10 minutes
                if time.time() - start_time > 600:
                    submission.status = SubmissionStatus.BUILD_FAILED.value
                    submission.build_logs = "".join(logs_buffer) + "\n\nBuild timed out after 10 minutes."
                    submission.error_message = "Build timed out"
                    db.commit()
                    return

                # Get build status
                build_result = build_client.get_build(project_id=project_id, id=build_id)

                # Fetch logs periodically (every 5 seconds)
                if time.time() - last_log_fetch > 5:
                    try:
                        from google.cloud import storage
                        # logs_bucket is like "gs://xxx.cloudbuild-logs.googleusercontent.com"
                        logs_bucket = build_result.logs_bucket
                        if logs_bucket:
                            bucket_name = logs_bucket.replace("gs://", "")
                            blob_name = f"log-{build_id}.txt"

                            storage_client = storage.Client(project=project_id)
                            bucket = storage_client.bucket(bucket_name)
                            blob = bucket.blob(blob_name)

                            if blob.exists():
                                log_content = blob.download_as_text()
                                logs_buffer = [f"Build ID: {build_id}\n", "=" * 50 + "\n", log_content]

                                # Update logs in database
                                submission.build_logs = "".join(logs_buffer)
                                db.commit()
                    except Exception as log_err:
                        logger.debug(f"Could not fetch logs: {log_err}")

                    last_log_fetch = time.time()

                # Check if build completed
                if build_result.status == cloudbuild_v1.Build.Status.SUCCESS:
                    logger.info(f"Build {build_id} succeeded")

                    # Final log fetch - use logs_bucket
                    try:
                        from google.cloud import storage
                        logs_bucket = build_result.logs_bucket
                        if logs_bucket:
                            bucket_name = logs_bucket.replace("gs://", "")
                            blob_name = f"log-{build_id}.txt"

                            storage_client = storage.Client(project=project_id)
                            bucket = storage_client.bucket(bucket_name)
                            blob = bucket.blob(blob_name)

                            if blob.exists():
                                logs_buffer = [f"Build ID: {build_id}\n", "=" * 50 + "\n", blob.download_as_text()]
                    except Exception as e:
                        logger.debug(f"Final log fetch failed: {e}")

                    logs_buffer.append("\n\n" + "=" * 50 + "\nBUILD SUCCESSFUL\n" + "=" * 50)
                    submission.build_logs = "".join(logs_buffer)
                    submission.status = SubmissionStatus.DEPLOYING.value

                    # Get the image name from build
                    if build_result.images:
                        submission.build_artifact_url = build_result.images[0]

                    db.commit()

                    # Deploy the cluster
                    try:
                        submission.build_logs += "\n\nDeploying cluster...\n"
                        db.commit()

                        image_name = f"gcr.io/{project_id}/raft-{submission_id}-{language}"
                        cluster_urls = await build_service.deploy_cluster(submission_id, image_name)

                        submission.cluster_node_urls = cluster_urls
                        submission.status = SubmissionStatus.TESTING.value
                        submission.build_logs += f"Cluster deployed successfully!\nNodes: {cluster_urls}\n"
                        submission.build_logs += "\nRunning tests against cluster...\n"
                        db.commit()

                        # Run tests against the cluster
                        from backend.services.distributed_tests import DistributedTestRunner
                        from backend.models.test_result import TestResult as TestResultModel, AnalysisStatus, ErrorCategory
                        from backend.services.error_analyzer import error_analyzer

                        test_runner = DistributedTestRunner(cluster_urls, submission_id=submission_id)

                        try:
                            test_results = await test_runner.run_all_tests()

                            # Log test results
                            passed = sum(1 for r in test_results if r.status.value == "passed")
                            failed = sum(1 for r in test_results if r.status.value == "failed")
                            errors = sum(1 for r in test_results if r.status.value == "error")

                            submission.build_logs += f"\n{'=' * 50}\nTEST RESULTS\n{'=' * 50}\n"
                            submission.build_logs += f"Passed: {passed}, Failed: {failed}, Errors: {errors}\n\n"

                            for result in test_results:
                                status_icon = "✓" if result.status.value == "passed" else "✗" if result.status.value == "failed" else "!"
                                submission.build_logs += f"{status_icon} [{result.test_type.value}] {result.test_name}: {result.status.value} ({result.duration_ms}ms)\n"
                                if result.error_message:
                                    submission.build_logs += f"   Error: {result.error_message}\n"
                                if result.details:
                                    # Truncate details for logs
                                    details_str = str(result.details)
                                    if len(details_str) > 200:
                                        details_str = details_str[:200] + "..."
                                    submission.build_logs += f"   Details: {details_str}\n"

                                # Build comprehensive details dict including error_message
                                details_dict = result.details.copy() if result.details else {}
                                if result.error_message:
                                    details_dict["error"] = result.error_message
                                    details_dict["error_message"] = result.error_message

                                # Create TestResult database record
                                test_result_record = TestResultModel(
                                    submission_id=submission_id,
                                    test_type=result.test_type.value,
                                    test_name=result.test_name,
                                    status=result.status.value,
                                    duration_ms=result.duration_ms,
                                    details=details_dict,
                                    chaos_scenario=getattr(result, 'chaos_scenario', None),
                                )

                                # Add error analysis for failed/error tests
                                if result.status.value in ["failed", "error"]:
                                    try:
                                        analysis = await error_analyzer.analyze_failure(
                                            test_type=result.test_type.value,
                                            test_name=result.test_name,
                                            status=result.status.value,
                                            error_output=result.error_message or str(result.details),
                                            problem_description="Raft distributed consensus implementation",
                                            design_text="",
                                            api_spec=None,
                                            endpoint_url=cluster_urls[0] if cluster_urls else "",
                                        )
                                        test_result_record.error_category = analysis.get("category", ErrorCategory.UNKNOWN.value)
                                        test_result_record.error_analysis = analysis
                                        test_result_record.ai_analysis_status = AnalysisStatus.COMPLETED.value
                                    except Exception as analysis_err:
                                        logger.warning(f"Error analysis failed for {result.test_name}: {analysis_err}")
                                        test_result_record.error_category = ErrorCategory.UNKNOWN.value
                                        test_result_record.ai_analysis_status = AnalysisStatus.FAILED.value
                                        test_result_record.error_analysis = {"error": str(analysis_err)}
                                else:
                                    test_result_record.ai_analysis_status = AnalysisStatus.SKIPPED.value

                                db.add(test_result_record)

                            # Determine final status based on test results
                            if failed == 0 and errors == 0:
                                submission.status = SubmissionStatus.COMPLETED.value
                                submission.build_logs += "\n✓ All tests passed! Submission completed successfully."
                            else:
                                submission.status = SubmissionStatus.COMPLETED.value  # Still completed, but with failures
                                submission.build_logs += f"\n✗ Tests completed with {failed} failures and {errors} errors."

                            # Schedule auto-teardown after 1 hour
                            submission.build_logs += "\n\nNote: Cluster will be automatically torn down in 1 hour. Use 'Tear Down' button to remove it earlier."

                        except Exception as test_err:
                            logger.error(f"Test execution failed: {test_err}")
                            submission.status = SubmissionStatus.COMPLETED.value
                            submission.build_logs += f"\n\nTest execution error: {test_err}"

                            # Create an error test result so the UI shows something
                            from backend.models.test_result import TestResult as TestResultModel
                            error_result = TestResultModel(
                                submission_id=submission_id,
                                test_type="functional",
                                test_name="Test Execution",
                                status="error",
                                duration_ms=0,
                                details={"error": str(test_err)},
                            )
                            db.add(error_result)

                        db.commit()

                        # Schedule auto-teardown after 1 hour (3600 seconds)
                        asyncio.create_task(schedule_auto_teardown(submission_id))

                    except Exception as deploy_err:
                        logger.error(f"Deployment failed: {deploy_err}")
                        submission.status = SubmissionStatus.DEPLOY_FAILED.value
                        submission.error_message = str(deploy_err)
                        submission.build_logs += f"\n\nDEPLOYMENT FAILED: {deploy_err}"
                        db.commit()

                    return

                elif build_result.status in [
                    cloudbuild_v1.Build.Status.FAILURE,
                    cloudbuild_v1.Build.Status.INTERNAL_ERROR,
                    cloudbuild_v1.Build.Status.TIMEOUT,
                    cloudbuild_v1.Build.Status.CANCELLED,
                ]:
                    logger.error(f"Build {build_id} failed with status: {build_result.status.name}")

                    # Final log fetch - use logs_bucket, not log_url
                    log_content = ""
                    try:
                        from google.cloud import storage
                        # logs_bucket is like "gs://xxx.cloudbuild-logs.googleusercontent.com"
                        logs_bucket = build_result.logs_bucket
                        if logs_bucket:
                            # Remove gs:// prefix if present
                            bucket_name = logs_bucket.replace("gs://", "")
                            blob_name = f"log-{build_id}.txt"

                            storage_client = storage.Client(project=project_id)
                            bucket = storage_client.bucket(bucket_name)
                            blob = bucket.blob(blob_name)

                            if blob.exists():
                                log_content = blob.download_as_text()
                                logger.info(f"Fetched {len(log_content)} bytes of build logs")
                    except Exception as e:
                        logger.warning(f"Final log fetch failed: {e}")

                    # Build detailed error message from build result
                    error_details = []
                    if hasattr(build_result, 'failure_info') and build_result.failure_info:
                        if build_result.failure_info.detail:
                            error_details.append(f"Failure: {build_result.failure_info.detail}")

                    # Get step-level errors
                    for i, step in enumerate(build_result.steps):
                        if step.status == cloudbuild_v1.Build.Status.FAILURE:
                            error_details.append(f"Step {i} ({step.name}) failed with exit code {step.exit_code}")

                    # Construct final logs
                    logs_buffer = [f"Build ID: {build_id}\n", "=" * 50 + "\n"]
                    if log_content:
                        logs_buffer.append(log_content)
                    if error_details:
                        logs_buffer.append("\n\n" + "=" * 50 + "\nERROR DETAILS:\n")
                        logs_buffer.extend([f"  - {e}\n" for e in error_details])
                    logs_buffer.append("\n" + "=" * 50 + f"\nBUILD FAILED: {build_result.status.name}\n" + "=" * 50)

                    submission.status = SubmissionStatus.BUILD_FAILED.value
                    submission.build_logs = "".join(logs_buffer)
                    submission.error_message = f"Build failed: {build_result.status.name}"
                    if error_details:
                        submission.error_message += f" - {error_details[0]}"
                    db.commit()
                    return

                # Wait before polling again
                await asyncio.sleep(5)

        except Exception as build_err:
            logger.error(f"Build process failed: {build_err}")
            submission.status = SubmissionStatus.BUILD_FAILED.value
            submission.error_message = str(build_err)
            submission.build_logs = (submission.build_logs or "") + f"\n\nBUILD ERROR: {build_err}"
            db.commit()

    except Exception as e:
        logger.error(f"Background build task failed: {e}")
    finally:
        db.close()


# ============================================================================
# Problem Type Configuration
# ============================================================================

PROBLEM_TYPE_CONFIG = {
    "raft": {
        "directory": "raft",
        "proto_file": "raft.proto",
        "java_class": "RaftServer",
        "test_runner": "backend.services.distributed_tests.DistributedTestRunner",
    },
    "paxos": {
        "directory": "paxos",
        "proto_file": "paxos.proto",
        "java_class": "PaxosServer",
        "test_runner": "backend.services.distributed_tests_paxos.PaxosTestRunner",
    },
    "two_phase_commit": {
        "directory": "two_phase_commit",
        "proto_file": "two_phase_commit.proto",
        "java_class": "TwoPhaseCommitServer",
        "test_runner": "backend.services.distributed_tests_2pc.TwoPhaseCommitTestRunner",
    },
    "chandy_lamport": {
        "directory": "chandy_lamport",
        "proto_file": "chandy_lamport.proto",
        "java_class": "ChandyLamportServer",
        "test_runner": "backend.services.distributed_tests_chandy_lamport.ChandyLamportTestRunner",
    },
    "consistent_hashing": {
        "directory": "consistent_hashing",
        "proto_file": "consistent_hashing.proto",
        "java_class": "ConsistentHashingServer",
        "test_runner": "backend.services.distributed_tests_consistent_hashing.ConsistentHashingTestRunner",
    },
    "rendezvous_hashing": {
        "directory": "rendezvous_hashing",
        "proto_file": "rendezvous_hashing.proto",
        "java_class": "RendezvousHashingServer",
        "test_runner": "backend.services.distributed_tests_rendezvous_hashing.RendezvousHashingTestRunner",
    },
}

# Default problem IDs for filesystem-based problems
DEFAULT_PROBLEM_IDS = {
    1: "raft",
    2: "paxos",
    3: "two_phase_commit",
    4: "chandy_lamport",
    5: "consistent_hashing",
    6: "rendezvous_hashing",
}


# ============================================================================
# Helper Functions
# ============================================================================

def get_distributed_problems_base_path() -> str:
    """
    Get the base path for distributed problems files.

    Tries multiple strategies:
    1. APP_BASE_PATH environment variable (for Docker containers)
    2. Relative path calculation from this file
    3. Current working directory
    """
    # Strategy 1: Environment variable (most reliable for containers)
    env_base = os.environ.get("APP_BASE_PATH")
    if env_base:
        return env_base

    # Strategy 2: Relative path from this file
    # This works when running from source: backend/api/distributed.py -> project root
    file_based_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Strategy 3: Check /app (Docker standard location)
    docker_path = "/app"

    # Check which path has the distributed_problems directory
    for base_path in [file_based_path, docker_path, os.getcwd()]:
        check_path = os.path.join(base_path, "distributed_problems", "raft", "proto", "raft.proto")
        if os.path.exists(check_path):
            return base_path

    # Default to file-based path (original behavior)
    return file_based_path


def get_template_from_filesystem(language: str, problem_type: str = "raft") -> str:
    """Load template from the distributed_problems directory."""
    config = PROBLEM_TYPE_CONFIG.get(problem_type, PROBLEM_TYPE_CONFIG["raft"])

    # Map language to directory/file - use problem-specific Java class name
    java_class = config["java_class"]
    file_map = {
        "python": "python/server.py",
        "go": "go/server.go",
        "java": f"java/{java_class}.java",
        "cpp": "cpp/server.cpp",
        "rust": "rust/src/main.rs",
    }

    if language not in file_map:
        return f"// Template not available for {language}"

    # Construct path relative to project root
    base_path = get_distributed_problems_base_path()
    template_path = os.path.join(
        base_path,
        "distributed_problems",
        config["directory"],
        "templates",
        file_map[language]
    )

    try:
        with open(template_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        # Include debug info for troubleshooting
        debug_info = f"base_path={base_path}, cwd={os.getcwd()}"
        return f"// Template file not found: {template_path} ({debug_info})"
    except PermissionError:
        return f"// Template file permission denied: {template_path}"


def get_proto_from_filesystem(problem_type: str = "raft") -> str:
    """Load the proto file from filesystem for the given problem type."""
    config = PROBLEM_TYPE_CONFIG.get(problem_type, PROBLEM_TYPE_CONFIG["raft"])
    base_path = get_distributed_problems_base_path()
    proto_path = os.path.join(
        base_path, "distributed_problems", config["directory"], "proto", config["proto_file"]
    )

    try:
        with open(proto_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        # Include debug info for troubleshooting
        debug_info = f"base_path={base_path}, cwd={os.getcwd()}"
        return f"// Proto file not found: {proto_path} ({debug_info})"
    except PermissionError:
        return f"// Proto file permission denied: {proto_path}"


def get_problem_type_from_id(problem_id: int) -> str:
    """Get problem type from problem ID."""
    return DEFAULT_PROBLEM_IDS.get(problem_id, "raft")


# ============================================================================
# Problems Endpoints
# ============================================================================

@router.get("/problems", response_model=List[DistributedProblemListResponse])
async def list_distributed_problems(
    db: Session = Depends(get_db),
):
    """
    List all distributed consensus problems.

    Returns:
        List of distributed consensus problems
    """
    problems = db.query(Problem).filter(
        Problem.problem_type == ProblemType.DISTRIBUTED_CONSENSUS.value
    ).all()

    # If no problems in DB, return default problems
    if not problems:
        return [
            {
                "id": 1,
                "title": "Implement Raft Consensus",
                "description": "Implement the Raft consensus algorithm. Your implementation should handle leader election, log replication, and safety properties as defined in the Raft paper.",
                "difficulty": "hard",
                "problem_type": "distributed_consensus",
                "supported_languages": ["python", "go", "java", "cpp", "rust"],
                "cluster_size": 3,
                "tags": ["distributed-systems", "consensus", "raft"],
                "created_at": "2025-01-01T00:00:00Z",
            },
            {
                "id": 2,
                "title": "Implement Paxos Consensus",
                "description": "Implement the Multi-Paxos consensus algorithm. Your implementation should handle proposer, acceptor, and learner roles as defined in 'Paxos Made Simple'.",
                "difficulty": "hard",
                "problem_type": "distributed_consensus",
                "supported_languages": ["python", "go", "java", "cpp", "rust"],
                "cluster_size": 3,
                "tags": ["distributed-systems", "consensus", "paxos"],
                "created_at": "2025-01-01T00:00:00Z",
            },
            {
                "id": 3,
                "title": "Implement Two-Phase Commit",
                "description": "Implement the Two-Phase Commit (2PC) protocol for distributed transactions. Your implementation should handle coordinator and participant roles.",
                "difficulty": "medium",
                "problem_type": "distributed_consensus",
                "supported_languages": ["python", "go", "java", "cpp", "rust"],
                "cluster_size": 3,
                "tags": ["distributed-systems", "transactions", "2pc"],
                "created_at": "2025-01-01T00:00:00Z",
            },
            {
                "id": 4,
                "title": "Implement Chandy-Lamport Snapshot",
                "description": "Implement the Chandy-Lamport algorithm for capturing consistent global snapshots in distributed systems.",
                "difficulty": "medium",
                "problem_type": "distributed_consensus",
                "supported_languages": ["python", "go", "java", "cpp", "rust"],
                "cluster_size": 3,
                "tags": ["distributed-systems", "snapshots", "chandy-lamport"],
                "created_at": "2025-01-01T00:00:00Z",
            },
            {
                "id": 5,
                "title": "Implement Consistent Hashing",
                "description": "Implement a consistent hash ring for distributing keys across a cluster of nodes.",
                "difficulty": "medium",
                "problem_type": "distributed_consensus",
                "supported_languages": ["python", "go", "java", "cpp", "rust"],
                "cluster_size": 3,
                "tags": ["distributed-systems", "hashing", "consistent-hashing"],
                "created_at": "2025-01-01T00:00:00Z",
            },
            {
                "id": 6,
                "title": "Implement Rendezvous Hashing",
                "description": "Implement rendezvous (highest random weight) hashing for distributed key-to-node mapping.",
                "difficulty": "medium",
                "problem_type": "distributed_consensus",
                "supported_languages": ["python", "go", "java", "cpp", "rust"],
                "cluster_size": 3,
                "tags": ["distributed-systems", "hashing", "rendezvous-hashing"],
                "created_at": "2025-01-01T00:00:00Z",
            },
        ]

    return [
        {
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "difficulty": p.difficulty,
            "problem_type": p.problem_type,
            "supported_languages": p.supported_languages or ["python", "go", "java", "cpp", "rust"],
            "cluster_size": p.cluster_size or 3,
            "tags": p.tags,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in problems
    ]


@router.get("/problems/{problem_id}", response_model=DistributedProblemResponse)
async def get_distributed_problem(
    problem_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific distributed problem by ID.

    Args:
        problem_id: Problem ID

    Returns:
        Full problem details with gRPC proto and language templates
    """
    # Default problems (1-4) are loaded from filesystem
    if problem_id in DEFAULT_PROBLEM_IDS:
        problem_type = DEFAULT_PROBLEM_IDS[problem_id]
        return _get_default_problem(problem_id, problem_type)

    # Check database for other problems
    problem = db.query(Problem).filter(
        Problem.id == problem_id,
        Problem.problem_type == ProblemType.DISTRIBUTED_CONSENSUS.value
    ).first()

    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Problem not found"
        )

    return {
        "id": problem.id,
        "title": problem.title,
        "description": problem.description,
        "difficulty": problem.difficulty,
        "problem_type": problem.problem_type,
        "grpc_proto": problem.grpc_proto or "",
        "supported_languages": problem.supported_languages or ["python", "go"],
        "cluster_size": problem.cluster_size or 3,
        "language_templates": problem.language_templates or {},
        "test_scenarios": problem.test_scenarios or [],
        "hints": problem.hints,
        "tags": problem.tags,
        "created_at": problem.created_at.isoformat() if problem.created_at else None,
    }


def get_build_command(language: str) -> str:
    """Get the build command for a language."""
    commands = {
        "python": "pip install -r requirements.txt && python -m grpc_tools.protoc -I../proto --python_out=. --grpc_python_out=. ../proto/raft.proto",
        "go": "go mod download && protoc --go_out=. --go-grpc_out=. ../proto/raft.proto && go build -o server .",
        "java": "./gradlew build",
        "cpp": "mkdir -p build && cd build && cmake .. && make",
        "rust": "cargo build --release",
    }
    return commands.get(language, "echo 'Unknown language'")


def get_run_command(language: str) -> str:
    """Get the run command for a language."""
    commands = {
        "python": "python server.py --node-id $NODE_ID --port $PORT --peers $PEERS",
        "go": "./server --node-id $NODE_ID --port $PORT --peers $PEERS",
        "java": "java -jar build/libs/raft-server.jar --node-id $NODE_ID --port $PORT --peers $PEERS",
        "cpp": "./build/server --node-id $NODE_ID --port $PORT --peers $PEERS",
        "rust": "./target/release/server --node-id $NODE_ID --port $PORT --peers $PEERS",
    }
    return commands.get(language, "echo 'Unknown language'")


def _get_default_problem(problem_id: int, problem_type: str) -> dict:
    """Get a default problem configuration from filesystem."""
    proto = get_proto_from_filesystem(problem_type)

    templates = {}
    for lang in ["python", "go", "java", "cpp", "rust"]:
        templates[lang] = {
            "language": lang,
            "template": get_template_from_filesystem(lang, problem_type),
            "build_command": get_build_command(lang),
            "run_command": get_run_command(lang),
        }

    # Problem-specific configurations
    problems_config = {
        "raft": {
            "id": 1,
            "title": "Implement Raft Consensus",
            "description": "Implement the Raft consensus algorithm. Your implementation should handle leader election, log replication, and safety properties as defined in the Raft paper.\n\nKey features to implement:\n1. Leader Election - Use randomized timeouts to elect a leader\n2. Log Replication - Replicate commands from leader to followers\n3. Safety - Ensure only nodes with complete logs can become leader\n4. Heartbeats - Maintain leadership with periodic AppendEntries RPCs\n\nRefer to the gRPC proto file for the required service interfaces.",
            "difficulty": "hard",
            "test_scenarios": [
                {"name": "Leader Election", "description": "Verify that a leader is elected when the cluster starts", "test_type": "functional"},
                {"name": "Leader Failure", "description": "Verify that a new leader is elected when the current leader fails", "test_type": "functional"},
                {"name": "Log Replication", "description": "Verify that log entries are replicated to all followers", "test_type": "functional"},
                {"name": "Consistency", "description": "Verify that all nodes have consistent logs after operations", "test_type": "functional"},
                {"name": "Network Partition", "description": "Verify correct behavior during network partitions", "test_type": "chaos"},
                {"name": "Node Restart", "description": "Verify that nodes rejoin the cluster correctly after restart", "test_type": "chaos"},
                {"name": "High Throughput", "description": "Test cluster performance under high write load", "test_type": "performance"},
                {"name": "Latency", "description": "Measure request latency under normal conditions", "test_type": "performance"},
            ],
            "hints": [
                "Start by implementing the election timeout - when it fires, transition to candidate state",
                "Use randomized timeouts to prevent split votes",
                "The leader sends empty AppendEntries as heartbeats to maintain authority",
                "Remember to reset the election timer when receiving valid AppendEntries",
                "Log matching: if two entries have the same index and term, they are identical",
            ],
            "tags": ["distributed-systems", "consensus", "raft"],
        },
        "paxos": {
            "id": 2,
            "title": "Implement Paxos Consensus",
            "description": "Implement the Multi-Paxos consensus algorithm as described in 'Paxos Made Simple' by Leslie Lamport.\n\nKey features to implement:\n1. Phase 1 (Prepare) - Proposer sends prepare requests to acceptors\n2. Phase 2 (Accept) - If majority promises, proposer sends accept requests\n3. Learning - Learners discover chosen values\n4. Multi-Paxos - Leader election to skip Phase 1 for consecutive slots\n\nRefer to the gRPC proto file for the required service interfaces.",
            "difficulty": "hard",
            "test_scenarios": [
                {"name": "Leader Election", "description": "Verify Multi-Paxos leader election works correctly", "test_type": "functional"},
                {"name": "Basic Consensus", "description": "Verify that a single value can be agreed upon", "test_type": "functional"},
                {"name": "Slot Ordering", "description": "Verify that values are committed in slot order", "test_type": "functional"},
                {"name": "Value Agreement", "description": "Verify all nodes agree on the same values", "test_type": "functional"},
                {"name": "Proposer Failure", "description": "Verify recovery from proposer failure", "test_type": "chaos"},
                {"name": "Acceptor Failure", "description": "Verify recovery from acceptor failure", "test_type": "chaos"},
                {"name": "Throughput", "description": "Test consensus throughput under load", "test_type": "performance"},
                {"name": "Latency", "description": "Measure consensus latency", "test_type": "performance"},
            ],
            "hints": [
                "Proposal numbers must be unique and totally ordered",
                "Use (round, proposer_id) pairs for total ordering",
                "An acceptor can promise to ignore lower-numbered proposals",
                "The proposer must use the highest-numbered accepted value",
                "Multi-Paxos allows skipping Phase 1 when the leader is stable",
            ],
            "tags": ["distributed-systems", "consensus", "paxos"],
        },
        "two_phase_commit": {
            "id": 3,
            "title": "Implement Two-Phase Commit",
            "description": "Implement the Two-Phase Commit (2PC) protocol for distributed transactions.\n\nKey features to implement:\n1. Begin Transaction - Coordinator starts a new transaction\n2. Phase 1 (Prepare) - Coordinator asks participants to vote\n3. Phase 2 (Commit/Abort) - Based on votes, commit or abort\n4. Participant Recovery - Handle participant failures gracefully\n\nRefer to the gRPC proto file for the required service interfaces.",
            "difficulty": "medium",
            "test_scenarios": [
                {"name": "Coordinator Detection", "description": "Verify coordinator is correctly identified", "test_type": "functional"},
                {"name": "Transaction Commit", "description": "Verify successful transaction commit", "test_type": "functional"},
                {"name": "Transaction Abort", "description": "Verify transaction abort on participant vote no", "test_type": "functional"},
                {"name": "Atomicity", "description": "Verify transactions are atomic across participants", "test_type": "functional"},
                {"name": "Coordinator Failure", "description": "Test behavior when coordinator fails", "test_type": "chaos"},
                {"name": "Participant Failure", "description": "Test behavior when participant fails", "test_type": "chaos"},
                {"name": "Transaction Throughput", "description": "Measure transaction throughput", "test_type": "performance"},
                {"name": "Transaction Latency", "description": "Measure transaction latency", "test_type": "performance"},
            ],
            "hints": [
                "The coordinator must log its decision before sending Phase 2 messages",
                "Participants must write their vote to stable storage before responding",
                "If any participant votes ABORT, the transaction must abort",
                "A prepared participant must wait for the coordinator's decision",
                "Consider implementing timeouts for blocking scenarios",
            ],
            "tags": ["distributed-systems", "transactions", "2pc"],
        },
        "chandy_lamport": {
            "id": 4,
            "title": "Implement Chandy-Lamport Snapshot",
            "description": "Implement the Chandy-Lamport algorithm for capturing consistent global snapshots in distributed systems.\n\nKey features to implement:\n1. Snapshot Initiation - Any process can initiate a snapshot\n2. Marker Propagation - Send markers on all outgoing channels\n3. State Recording - Record local state and channel state\n4. Global Snapshot Assembly - Combine local snapshots into global view\n\nRefer to the gRPC proto file for the required service interfaces.",
            "difficulty": "medium",
            "test_scenarios": [
                {"name": "Cluster Connectivity", "description": "Verify all nodes can communicate", "test_type": "functional"},
                {"name": "Snapshot Initiation", "description": "Verify snapshot can be initiated from any node", "test_type": "functional"},
                {"name": "Marker Propagation", "description": "Verify markers reach all nodes", "test_type": "functional"},
                {"name": "State Consistency", "description": "Verify snapshot captures consistent state", "test_type": "functional"},
                {"name": "Channel Recording", "description": "Verify in-transit messages are recorded", "test_type": "functional"},
                {"name": "Node Failure", "description": "Test behavior during node failure", "test_type": "chaos"},
                {"name": "Snapshot Latency", "description": "Measure snapshot completion time", "test_type": "performance"},
                {"name": "Concurrent Operations", "description": "Test snapshot during concurrent operations", "test_type": "performance"},
            ],
            "hints": [
                "On first marker receipt, immediately record local state",
                "Start recording messages on channels where marker hasn't arrived",
                "Stop recording a channel when its marker arrives",
                "The global snapshot is the union of all local snapshots",
                "Use Lamport clocks to help reason about ordering",
            ],
            "tags": ["distributed-systems", "snapshots", "chandy-lamport"],
        },
        "consistent_hashing": {
            "id": 5,
            "title": "Implement Consistent Hashing",
            "description": "Implement a consistent hash ring for distributing keys across a cluster of nodes.\n\nKey features to implement:\n1. Hash Ring - Map keys and nodes to positions on a circular hash space\n2. Virtual Nodes - Create multiple positions per physical node for better distribution\n3. Key Lookup - Find the responsible node by walking clockwise from key position\n4. Rebalancing - Minimize key movement when nodes join or leave\n\nRefer to the gRPC proto file for the required service interfaces.",
            "difficulty": "medium",
            "test_scenarios": [
                {"name": "Cluster Connectivity", "description": "Verify all nodes can communicate", "test_type": "functional"},
                {"name": "Key Distribution", "description": "Verify keys are distributed evenly across nodes", "test_type": "functional"},
                {"name": "Node Lookup", "description": "Verify correct node is returned for each key", "test_type": "functional"},
                {"name": "Virtual Nodes", "description": "Verify virtual nodes improve distribution", "test_type": "functional"},
                {"name": "Node Addition", "description": "Verify minimal key movement when adding nodes", "test_type": "functional"},
                {"name": "Node Removal", "description": "Verify minimal key movement when removing nodes", "test_type": "functional"},
                {"name": "Node Failure", "description": "Test behavior during node failure", "test_type": "chaos"},
                {"name": "Lookup Latency", "description": "Measure key lookup latency", "test_type": "performance"},
            ],
            "hints": [
                "Use a consistent hash function like MD5 or SHA-1 for deterministic positioning",
                "More virtual nodes (100-200) gives better distribution but uses more memory",
                "Binary search on sorted virtual nodes enables O(log n) lookups",
                "When a node joins, only keys between it and its predecessor need to move",
                "Replicate keys to the next N physical nodes for fault tolerance",
            ],
            "tags": ["distributed-systems", "hashing", "consistent-hashing"],
        },
        "rendezvous_hashing": {
            "id": 6,
            "title": "Implement Rendezvous Hashing",
            "description": "Implement rendezvous (highest random weight) hashing for distributed key-to-node mapping.\n\nKey features to implement:\n1. Weight Calculation - Hash each (key, node) pair to compute weights\n2. Node Selection - Choose the node with highest weight for each key\n3. Deterministic Mapping - Same key always maps to same node given same cluster\n4. Minimal Disruption - Only keys from failed/added nodes need remapping\n\nRefer to the gRPC proto file for the required service interfaces.",
            "difficulty": "medium",
            "test_scenarios": [
                {"name": "Cluster Connectivity", "description": "Verify all nodes can communicate", "test_type": "functional"},
                {"name": "Key Distribution", "description": "Verify keys are distributed evenly", "test_type": "functional"},
                {"name": "Deterministic Mapping", "description": "Verify same key maps to same node", "test_type": "functional"},
                {"name": "Weight Calculation", "description": "Verify correct weight ordering", "test_type": "functional"},
                {"name": "Node Addition", "description": "Verify minimal disruption when adding nodes", "test_type": "functional"},
                {"name": "Node Removal", "description": "Verify only affected keys are remapped", "test_type": "functional"},
                {"name": "Node Failure", "description": "Test behavior during node failure", "test_type": "chaos"},
                {"name": "Lookup Latency", "description": "Measure key lookup latency", "test_type": "performance"},
            ],
            "hints": [
                "Hash the concatenation of key and node ID to get the weight",
                "The node with highest weight for a key is selected",
                "Unlike consistent hashing, no virtual nodes are needed",
                "Each lookup requires computing weights for all nodes (O(n))",
                "Consider caching weights for frequently accessed keys",
            ],
            "tags": ["distributed-systems", "hashing", "rendezvous-hashing"],
        },
    }

    config = problems_config.get(problem_type, problems_config["raft"])

    return {
        "id": config["id"],
        "title": config["title"],
        "description": config["description"],
        "difficulty": config["difficulty"],
        "problem_type": "distributed_consensus",
        "grpc_proto": proto,
        "supported_languages": ["python", "go", "java", "cpp", "rust"],
        "cluster_size": 3,
        "language_templates": templates,
        "test_scenarios": config["test_scenarios"],
        "hints": config["hints"],
        "tags": config["tags"],
        "created_at": "2025-01-01T00:00:00Z",
    }


@router.get("/problems/{problem_id}/template/{language}", response_model=TemplateResponse)
async def get_language_template(
    problem_id: int,
    language: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the template code for a specific language.

    Args:
        problem_id: Problem ID
        language: Programming language

    Returns:
        Template code for the specified language
    """
    if language not in [lang.value for lang in SupportedLanguage]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported language: {language}"
        )

    # For default problems (1-6), load from filesystem
    if problem_id in DEFAULT_PROBLEM_IDS:
        problem_type = DEFAULT_PROBLEM_IDS[problem_id]
        template = get_template_from_filesystem(language, problem_type)
        return {"template": template}

    # Check database for other problems
    problem = db.query(Problem).filter(
        Problem.id == problem_id,
        Problem.problem_type == ProblemType.DISTRIBUTED_CONSENSUS.value
    ).first()

    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Problem not found"
        )

    templates = problem.language_templates or {}
    if language not in templates:
        return {"template": f"// Template not available for {language}"}

    return {"template": templates[language].get("template", "")}


@router.get("/problems/{problem_id}/saved-code/{language}", response_model=SavedCodeResponse)
async def get_saved_code(
    problem_id: int,
    language: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get saved code for a problem/language combination.

    This looks for the most recent submission by the user for this problem/language.
    """
    submission = db.query(Submission).filter(
        Submission.problem_id == problem_id,
        Submission.user_id == current_user.id,
        Submission.submission_type == SubmissionType.DISTRIBUTED_CONSENSUS.value,
        Submission.language == language,
    ).order_by(Submission.created_at.desc()).first()

    if not submission or not submission.source_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No saved code found"
        )

    return {"code": submission.source_code}


@router.post("/problems/{problem_id}/save-code")
async def save_code(
    problem_id: int,
    request: SaveCodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Save code for a problem (auto-save functionality).

    Creates a draft submission with pending status.
    """
    # Look for existing draft
    submission = db.query(Submission).filter(
        Submission.problem_id == problem_id,
        Submission.user_id == current_user.id,
        Submission.submission_type == SubmissionType.DISTRIBUTED_CONSENSUS.value,
        Submission.language == request.language,
        Submission.status == SubmissionStatus.PENDING.value,
    ).order_by(Submission.created_at.desc()).first()

    if submission:
        # Update existing draft
        submission.source_code = request.code
    else:
        # Create new draft
        submission = Submission(
            problem_id=problem_id,
            user_id=current_user.id,
            submission_type=SubmissionType.DISTRIBUTED_CONSENSUS.value,
            language=request.language,
            source_code=request.code,
            status=SubmissionStatus.PENDING.value,
        )
        db.add(submission)

    db.commit()
    return {"message": "Code saved successfully"}


# ============================================================================
# Submissions Endpoints
# ============================================================================

@router.post("/submissions", response_model=DistributedSubmissionResponse)
async def create_distributed_submission(
    data: DistributedSubmissionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit code for compilation and testing.

    This will:
    1. Create a submission record
    2. Queue the build process as a background task
    3. Return the submission ID for status polling
    """
    if data.language not in [lang.value for lang in SupportedLanguage]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported language: {data.language}"
        )

    # Create submission
    submission = Submission(
        problem_id=data.problem_id,
        user_id=current_user.id,
        submission_type=SubmissionType.DISTRIBUTED_CONSENSUS.value,
        language=data.language,
        source_code=data.source_code,
        status=SubmissionStatus.BUILDING.value,
        build_logs="Queuing build job...\n",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # Start the build process in the background
    # Using asyncio.create_task because BackgroundTasks doesn't support async functions well
    asyncio.create_task(run_distributed_build(
        submission_id=submission.id,
        language=data.language,
        source_code=data.source_code,
        problem_id=data.problem_id,
    ))

    logger.info(f"Created submission {submission.id} and queued build for {data.language}")

    return {
        "id": submission.id,
        "problem_id": submission.problem_id,
        "user_id": submission.user_id,
        "submission_type": submission.submission_type,
        "language": submission.language,
        "source_code": submission.source_code,
        "status": submission.status,
        "build_logs": submission.build_logs,
        "build_artifact_url": submission.build_artifact_url,
        "cluster_node_urls": submission.cluster_node_urls,
        "error_message": submission.error_message,
        "created_at": submission.created_at.isoformat(),
    }


@router.get("/submissions", response_model=List[DistributedSubmissionResponse])
async def list_distributed_submissions(
    problem_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List user's distributed submissions.

    Args:
        problem_id: Optional filter by problem ID
    """
    query = db.query(Submission).filter(
        Submission.user_id == current_user.id,
        Submission.submission_type == SubmissionType.DISTRIBUTED_CONSENSUS.value,
    )

    if problem_id:
        query = query.filter(Submission.problem_id == problem_id)

    submissions = query.order_by(Submission.created_at.desc()).limit(50).all()

    return [
        {
            "id": s.id,
            "problem_id": s.problem_id,
            "user_id": s.user_id,
            "submission_type": s.submission_type,
            "language": s.language,
            "source_code": s.source_code,
            "status": s.status,
            "build_logs": s.build_logs,
            "build_artifact_url": s.build_artifact_url,
            "cluster_node_urls": s.cluster_node_urls,
            "error_message": s.error_message,
            "created_at": s.created_at.isoformat(),
        }
        for s in submissions
    ]


@router.get("/submissions/{submission_id}", response_model=DistributedSubmissionResponse)
async def get_distributed_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific distributed submission.

    Args:
        submission_id: Submission ID
    """
    submission = db.query(Submission).filter(
        Submission.id == submission_id,
        Submission.user_id == current_user.id,
        Submission.submission_type == SubmissionType.DISTRIBUTED_CONSENSUS.value,
    ).first()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    return {
        "id": submission.id,
        "problem_id": submission.problem_id,
        "user_id": submission.user_id,
        "submission_type": submission.submission_type,
        "language": submission.language,
        "source_code": submission.source_code,
        "status": submission.status,
        "build_logs": submission.build_logs,
        "build_artifact_url": submission.build_artifact_url,
        "cluster_node_urls": submission.cluster_node_urls,
        "error_message": submission.error_message,
        "created_at": submission.created_at.isoformat(),
    }


@router.get("/submissions/{submission_id}/build-logs", response_model=BuildLogsResponse)
async def get_build_logs(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get build logs for a submission.

    Args:
        submission_id: Submission ID
    """
    submission = db.query(Submission).filter(
        Submission.id == submission_id,
        Submission.user_id == current_user.id,
    ).first()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    return {"logs": submission.build_logs or "No build logs available yet."}


@router.get("/submissions/{submission_id}/tests")
async def get_submission_tests(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get test results for a distributed submission.

    Args:
        submission_id: Submission ID
    """
    from backend.models.test_result import TestResult

    submission = db.query(Submission).filter(
        Submission.id == submission_id,
        Submission.user_id == current_user.id,
    ).first()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    tests = db.query(TestResult).filter(
        TestResult.submission_id == submission_id
    ).all()

    return [
        {
            "id": t.id,
            "submission_id": t.submission_id,
            "test_type": t.test_type,
            "test_name": t.test_name,
            "status": t.status,
            "details": t.details,
            "duration_ms": t.duration_ms,
            "chaos_scenario": t.chaos_scenario,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tests
    ]


@router.post("/submissions/{submission_id}/teardown")
async def teardown_cluster(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Tear down the deployed cluster for a submission.

    This will delete all Cloud Run services associated with the submission.
    """
    submission = db.query(Submission).filter(
        Submission.id == submission_id,
        Submission.user_id == current_user.id,
    ).first()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    if not submission.cluster_node_urls or len(submission.cluster_node_urls) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No cluster deployed for this submission"
        )

    try:
        build_service = DistributedBuildService()
        await build_service.cleanup_cluster(submission_id)

        # Update submission to indicate cluster is torn down
        submission.cluster_node_urls = []
        submission.build_logs += "\n\nCluster torn down successfully."
        db.commit()

        logger.info(f"Cluster torn down for submission {submission_id}")
        return {"message": "Cluster torn down successfully"}

    except Exception as e:
        logger.error(f"Failed to tear down cluster for submission {submission_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to tear down cluster: {str(e)}"
        )


# Auto-teardown background task
async def schedule_auto_teardown(submission_id: int, delay_seconds: int = 3600):
    """
    Schedule automatic teardown of a cluster after a delay.

    Args:
        submission_id: Submission ID
        delay_seconds: Delay before teardown (default: 1 hour)
    """
    await asyncio.sleep(delay_seconds)

    db = SessionLocal()
    try:
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        if submission and submission.cluster_node_urls and len(submission.cluster_node_urls) > 0:
            logger.info(f"Auto-tearing down cluster for submission {submission_id}")
            build_service = DistributedBuildService()
            await build_service.cleanup_cluster(submission_id)

            submission.cluster_node_urls = []
            submission.build_logs += "\n\nCluster auto-torn down after 1 hour."
            db.commit()
            logger.info(f"Auto-teardown completed for submission {submission_id}")
    except Exception as e:
        logger.error(f"Auto-teardown failed for submission {submission_id}: {e}")
    finally:
        db.close()
