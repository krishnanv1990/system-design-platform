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
    created_at: str

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
    created_at: str

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
    created_at: str

    class Config:
        from_attributes = True


class BuildLogsResponse(BaseModel):
    """Response for build logs."""
    logs: str


# ============================================================================
# Background Build Task
# ============================================================================

async def run_distributed_build(submission_id: int, language: str, source_code: str):
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

        # Update status to building
        submission.status = SubmissionStatus.BUILDING.value
        submission.build_logs = "Analyzing code and preparing build...\n"
        db.commit()

        try:
            # Load the proto spec
            proto_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "distributed_problems",
                "raft",
                "proto",
                "raft.proto"
            )
            proto_spec = ""
            if os.path.exists(proto_path):
                with open(proto_path, "r") as f:
                    proto_spec = f.read()

            # Analyze code using Claude AI for spec validation and dependency detection
            logger.info(f"Analyzing code for submission {submission_id}, language: {language}")
            analysis_result = await ai_service.analyze_distributed_code(
                source_code=source_code,
                language=language,
                proto_spec=proto_spec,
                problem_type="raft",
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
            logger.info(f"Starting build for submission {submission_id}, language: {language}")
            build_id = await build_service.start_build(
                submission_id, language, source_code, build_modifications
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
                        test_runner = DistributedTestRunner(cluster_urls)

                        try:
                            test_results = await test_runner.run_all_tests()

                            # Log test results
                            passed = sum(1 for r in test_results if r.status.value == "passed")
                            failed = sum(1 for r in test_results if r.status.value == "failed")
                            errors = sum(1 for r in test_results if r.status.value == "error")

                            submission.build_logs += f"\n{'=' * 50}\nTEST RESULTS\n{'=' * 50}\n"
                            submission.build_logs += f"Passed: {passed}, Failed: {failed}, Errors: {errors}\n\n"

                            # Import TestResult model
                            from backend.models.test_result import TestResult as TestResultModel

                            for result in test_results:
                                status_icon = "✓" if result.status.value == "passed" else "✗" if result.status.value == "failed" else "!"
                                submission.build_logs += f"{status_icon} [{result.test_type.value}] {result.test_name}: {result.status.value} ({result.duration_ms}ms)\n"
                                if result.error_message:
                                    submission.build_logs += f"   Error: {result.error_message}\n"
                                if result.details:
                                    submission.build_logs += f"   Details: {result.details}\n"

                                # Create TestResult database record
                                test_result_record = TestResultModel(
                                    submission_id=submission_id,
                                    test_type=result.test_type.value,
                                    test_name=result.test_name,
                                    status=result.status.value,
                                    duration_ms=result.duration_ms,
                                    details=result.details if result.details else {},
                                    chaos_scenario=getattr(result, 'chaos_scenario', None),
                                )
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


def get_template_from_filesystem(language: str) -> str:
    """Load template from the distributed_problems directory."""
    # Map language to directory/file
    file_map = {
        "python": "python/server.py",
        "go": "go/server.go",
        "java": "java/RaftServer.java",
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
        "raft",
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


def get_proto_from_filesystem() -> str:
    """Load the Raft proto file from filesystem."""
    base_path = get_distributed_problems_base_path()
    proto_path = os.path.join(base_path, "distributed_problems", "raft", "proto", "raft.proto")

    try:
        with open(proto_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        # Include debug info for troubleshooting
        debug_info = f"base_path={base_path}, cwd={os.getcwd()}"
        return f"// Proto file not found: {proto_path} ({debug_info})"
    except PermissionError:
        return f"// Proto file permission denied: {proto_path}"


# ============================================================================
# Problems Endpoints
# ============================================================================

@router.get("/problems", response_model=List[DistributedProblemListResponse])
async def list_distributed_problems(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all distributed consensus problems.

    Returns:
        List of distributed consensus problems
    """
    problems = db.query(Problem).filter(
        Problem.problem_type == ProblemType.DISTRIBUTED_CONSENSUS.value
    ).all()

    # If no problems in DB, return a default Raft problem
    if not problems:
        return [{
            "id": 1,
            "title": "Implement Raft Consensus",
            "description": "Implement the Raft consensus algorithm. Your implementation should handle leader election, log replication, and safety properties as defined in the Raft paper.",
            "difficulty": "hard",
            "problem_type": "distributed_consensus",
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "cluster_size": 3,
            "tags": ["distributed-systems", "consensus", "raft"],
            "created_at": "2025-01-01T00:00:00Z",
        }]

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
    # For the default Raft problem (id=1), return from filesystem
    if problem_id == 1:
        proto = get_proto_from_filesystem()
        test_scenarios = [
            {"name": "Leader Election", "description": "Verify that a leader is elected when the cluster starts", "test_type": "functional"},
            {"name": "Leader Failure", "description": "Verify that a new leader is elected when the current leader fails", "test_type": "functional"},
            {"name": "Log Replication", "description": "Verify that log entries are replicated to all followers", "test_type": "functional"},
            {"name": "Consistency", "description": "Verify that all nodes have consistent logs after operations", "test_type": "functional"},
            {"name": "Network Partition", "description": "Verify correct behavior during network partitions", "test_type": "chaos"},
            {"name": "Node Restart", "description": "Verify that nodes rejoin the cluster correctly after restart", "test_type": "chaos"},
            {"name": "High Throughput", "description": "Test cluster performance under high write load", "test_type": "performance"},
            {"name": "Latency", "description": "Measure request latency under normal conditions", "test_type": "performance"},
        ]

        templates = {}
        for lang in ["python", "go", "java", "cpp", "rust"]:
            templates[lang] = {
                "language": lang,
                "template": get_template_from_filesystem(lang),
                "build_command": get_build_command(lang),
                "run_command": get_run_command(lang),
            }

        return {
            "id": 1,
            "title": "Implement Raft Consensus",
            "description": "Implement the Raft consensus algorithm. Your implementation should handle leader election, log replication, and safety properties as defined in the Raft paper.\n\nKey features to implement:\n1. Leader Election - Use randomized timeouts to elect a leader\n2. Log Replication - Replicate commands from leader to followers\n3. Safety - Ensure only nodes with complete logs can become leader\n4. Heartbeats - Maintain leadership with periodic AppendEntries RPCs\n\nRefer to the gRPC proto file for the required service interfaces.",
            "difficulty": "hard",
            "problem_type": "distributed_consensus",
            "grpc_proto": proto,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "cluster_size": 3,
            "language_templates": templates,
            "test_scenarios": test_scenarios,
            "hints": [
                "Start by implementing the election timeout - when it fires, transition to candidate state",
                "Use randomized timeouts to prevent split votes",
                "The leader sends empty AppendEntries as heartbeats to maintain authority",
                "Remember to reset the election timer when receiving valid AppendEntries",
                "Log matching: if two entries have the same index and term, they are identical",
            ],
            "tags": ["distributed-systems", "consensus", "raft"],
            "created_at": "2025-01-01T00:00:00Z",
        }

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

    # For the default Raft problem, load from filesystem
    if problem_id == 1:
        template = get_template_from_filesystem(language)
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
