"""
Submission orchestrator for managing the evaluation pipeline.
Coordinates validation, deployment, and testing of candidate solutions.
"""

import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models.problem import Problem
from backend.models.submission import Submission, SubmissionStatus
from backend.models.test_result import TestResult
from backend.services.validation_service import ValidationService
from backend.services.terraform_service import TerraformService
from backend.services.deployment_service import FastDeploymentService, DeploymentStrategy
from backend.services.warm_pool_service import WarmPoolService, ServiceType
from backend.services.test_runner import TestRunner
from backend.services.gcp_service import GCPService
from backend.services.cleanup_scheduler import cleanup_scheduler
from backend.services.audit_service import AuditService
from backend.models.audit_log import ActionType
from backend.config import get_settings

settings = get_settings()

# Deployment mode options:
# - "cloud_run" (Cloud Run deployment, 30-60 seconds) - DEFAULT
# - "warm_pool" (sub-second, pre-provisioned infrastructure + warm containers)
# - "terraform" (full infra, 10-15 minutes)
# Always deploy to real infrastructure, even in demo mode
DEPLOYMENT_MODE = "cloud_run"


class SubmissionOrchestrator:
    """
    Orchestrates the complete evaluation pipeline for submissions.
    Manages the flow from validation through deployment and testing.
    """

    @staticmethod
    def _update_progress(db: Session, submission: Submission, step: str, detail: str, progress_pct: int = 0):
        """Update submission with progress information."""
        from datetime import datetime
        submission.validation_feedback = submission.validation_feedback or {}
        if "progress" not in submission.validation_feedback:
            submission.validation_feedback["progress"] = []

        submission.validation_feedback["progress"].append({
            "step": step,
            "detail": detail,
            "progress_pct": progress_pct,
            "timestamp": datetime.utcnow().isoformat(),
        })
        submission.validation_feedback["current_step"] = step
        submission.validation_feedback["current_detail"] = detail
        # Force the JSONB column to be marked as modified
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(submission, "validation_feedback")
        db.commit()

    @staticmethod
    async def process_submission(submission_id: int) -> None:
        """
        Process a submission through the complete evaluation pipeline.

        Pipeline stages:
        1. Validation - Check design against requirements
        2. Terraform Generation - Generate infrastructure code
        3. Deployment - Deploy to GCP
        4. Testing - Run functional, performance, and chaos tests
        5. Cleanup - Clean up resources (optional)

        Args:
            submission_id: ID of the submission to process
        """
        db = SessionLocal()

        try:
            # Get submission
            submission = db.query(Submission).filter(Submission.id == submission_id).first()
            if not submission:
                return

            # Get problem
            problem = db.query(Problem).filter(Problem.id == submission.problem_id).first()
            if not problem:
                return

            # Stage 1: Validation
            await SubmissionOrchestrator._run_validation(db, submission, problem)
            if submission.status == SubmissionStatus.VALIDATION_FAILED.value:
                return

            # Stage 2 & 3: Generate and Deploy Infrastructure
            # Use cloud_run, warm pool, or legacy Terraform
            if DEPLOYMENT_MODE == "cloud_run":
                await SubmissionOrchestrator._cloud_run_deploy(db, submission, problem)
            elif DEPLOYMENT_MODE == "warm_pool":
                await SubmissionOrchestrator._warm_pool_deploy(db, submission, problem)
            elif DEPLOYMENT_MODE == "fast":
                await SubmissionOrchestrator._fast_deploy(db, submission, problem)
            else:
                await SubmissionOrchestrator._generate_infrastructure(db, submission, problem)
                if submission.status == SubmissionStatus.FAILED.value:
                    return
                await SubmissionOrchestrator._deploy_infrastructure(db, submission)

            if submission.status == SubmissionStatus.DEPLOY_FAILED.value:
                return

            # Stage 4: Testing
            await SubmissionOrchestrator._run_tests(db, submission, problem)

            # Stage 5: Complete
            submission.status = SubmissionStatus.COMPLETED.value
            db.commit()

        except Exception as e:
            submission.status = SubmissionStatus.FAILED.value
            submission.error_message = str(e)
            db.commit()
        finally:
            db.close()

    @staticmethod
    async def _run_validation(
        db: Session,
        submission: Submission,
        problem: Problem,
    ) -> None:
        """Run validation stage."""
        submission.status = SubmissionStatus.VALIDATING.value
        db.commit()

        SubmissionOrchestrator._update_progress(
            db, submission,
            "Validating Design",
            f"Claude AI is analyzing your system design for '{problem.title}'...",
            5
        )

        validation_service = ValidationService()
        result = await validation_service.validate_all(
            problem=problem,
            schema_input=submission.schema_input,
            api_spec_input=submission.api_spec_input,
            design_text=submission.design_text,
        )

        # Store validation feedback
        submission.validation_feedback = {
            "is_valid": result.is_valid,
            "errors": result.errors,
            "warnings": result.warnings,
            "suggestions": result.suggestions,
            "score": result.score,
        }

        if not result.is_valid:
            submission.status = SubmissionStatus.VALIDATION_FAILED.value
            submission.error_message = "; ".join(result.errors)
        else:
            # Continue to next stage
            submission.status = SubmissionStatus.GENERATING_INFRA.value

        db.commit()

    @staticmethod
    async def _cloud_run_deploy(
        db: Session,
        submission: Submission,
        problem: Problem,
    ) -> None:
        """
        Deploy to Google Cloud Run with real infrastructure.
        Creates a new Cloud Run service for each submission.
        Uses Google Cloud Python libraries for authentication.
        """
        import asyncio
        import json
        import tempfile
        import tarfile
        import io
        from pathlib import Path
        from google.cloud import storage
        from google.cloud.devtools import cloudbuild_v1
        from google.cloud import run_v2

        submission.status = SubmissionStatus.DEPLOYING.value
        db.commit()

        from backend.services.ai_service import AIService
        ai_service = AIService()

        project_id = settings.gcp_project_id
        region = settings.gcp_region or "us-central1"
        namespace = f"sub-{submission.id}"
        service_name = f"sdp-{namespace}"

        try:
            # Step 1: Generate API code using AI
            SubmissionOrchestrator._update_progress(
                db, submission,
                "Generating Code",
                f"Using Claude AI to generate FastAPI implementation from your design...",
                10
            )

            api_code = await ai_service.generate_api_code(
                problem_description=problem.description,
                design_text=submission.design_text or "",
                api_spec=submission.api_spec_input,
            )

            # Track AI usage cost
            try:
                input_tokens, output_tokens = ai_service.get_last_usage()
                if input_tokens > 0 or output_tokens > 0:
                    audit_service = AuditService(db)
                    audit_log = audit_service.log_action(
                        action=ActionType.AI_GENERATE_CODE,
                        user_id=submission.user_id,
                        resource_type="submission",
                        resource_id=submission.id,
                        details={"input_tokens": input_tokens, "output_tokens": output_tokens},
                    )
                    audit_service.track_ai_usage(
                        user_id=submission.user_id,
                        audit_log_id=audit_log.id,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        model=ai_service.model,
                    )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to track AI cost: {e}")

            SubmissionOrchestrator._update_progress(
                db, submission,
                "Code Generated",
                f"Generated {len(api_code)} characters of Python code. Preparing for deployment...",
                20
            )

            # Step 2: Create source tarball and upload to GCS
            workspace = Path(tempfile.mkdtemp(prefix=f"sdp_{submission.id}_"))

            # Write application files
            main_py = workspace / "main.py"
            main_py.write_text(api_code)

            requirements = workspace / "requirements.txt"
            # Minimal requirements - no database libraries to prevent import errors
            requirements.write_text("""fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.6.0
httpx==0.27.0
python-multipart==0.0.6
aiofiles==23.2.1
""")

            dockerfile = workspace / "Dockerfile"
            dockerfile.write_text("""FROM python:3.11-slim

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONFAULTHANDLER=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY startup_wrapper.py .

EXPOSE 8080
ENV PORT=8080

# Use startup wrapper for better error handling
CMD ["python", "startup_wrapper.py"]
""")

            # Create startup wrapper with error handling
            startup_wrapper = workspace / "startup_wrapper.py"
            startup_wrapper.write_text('''#!/usr/bin/env python3
"""
Startup wrapper for candidate applications.
Provides robust error handling, health checks, and graceful degradation.
"""

import sys
import os
import traceback
import signal
import resource
import logging
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Set memory limit (512MB)
MEMORY_LIMIT_MB = 512
try:
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_MB * 1024 * 1024, hard))
except Exception as e:
    logger.warning(f"Could not set memory limit: {e}")

# Timeout handler
def timeout_handler(signum, frame):
    logger.error("Request timeout - operation took too long")
    raise TimeoutError("Operation timed out")

# Register signal handlers
signal.signal(signal.SIGALRM, timeout_handler)

def create_fallback_app():
    """Create a minimal fallback app if main app fails to load."""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI(title="Fallback API")

    startup_error = os.environ.get("STARTUP_ERROR", "Unknown error")

    @app.get("/health")
    async def health():
        return {"status": "degraded", "error": "Main application failed to start"}

    @app.get("/")
    async def root():
        return {"status": "error", "message": startup_error}

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def catch_all(path: str):
        return JSONResponse(
            status_code=503,
            content={
                "error": "service_unavailable",
                "message": "Main application failed to start",
                "startup_error": startup_error
            }
        )

    return app

def validate_app(app: Any) -> bool:
    """Validate that the app has required endpoints."""
    try:
        routes = [route.path for route in app.routes]
        if "/health" not in routes:
            logger.warning("App missing /health endpoint - will add fallback")
            return False
        return True
    except Exception as e:
        logger.error(f"Error validating app: {e}")
        return False

def add_health_endpoint(app: Any) -> Any:
    """Add a health endpoint if missing."""
    try:
        @app.get("/health")
        async def health():
            return {"status": "healthy"}
        logger.info("Added missing /health endpoint")
    except Exception as e:
        logger.error(f"Failed to add health endpoint: {e}")
    return app

def main():
    """Main entry point with comprehensive error handling."""
    import uvicorn

    app = None

    try:
        logger.info("Starting application...")

        # Try to import the main application
        try:
            # First, validate the syntax
            with open("main.py", "r") as f:
                code = f.read()
            compile(code, "main.py", "exec")
            logger.info("Syntax validation passed")
        except SyntaxError as e:
            error_msg = f"Syntax error in main.py: {e}"
            logger.error(error_msg)
            os.environ["STARTUP_ERROR"] = error_msg
            app = create_fallback_app()

        if app is None:
            try:
                from main import app as main_app
                app = main_app
                logger.info("Main application imported successfully")

                # Validate and fix the app
                if not validate_app(app):
                    app = add_health_endpoint(app)

            except ImportError as e:
                error_msg = f"Import error: {e}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                os.environ["STARTUP_ERROR"] = error_msg
                app = create_fallback_app()
            except Exception as e:
                error_msg = f"Failed to load application: {e}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                os.environ["STARTUP_ERROR"] = error_msg
                app = create_fallback_app()

        # Start the server
        port = int(os.environ.get("PORT", 8080))
        logger.info(f"Starting server on port {port}")

        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info",
            access_log=True,
            timeout_keep_alive=30,
        )

    except MemoryError:
        logger.critical("Out of memory error!")
        sys.exit(137)
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        logger.critical(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
''')

            # Create tarball
            tar_buffer = io.BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar:
                for file_path in workspace.iterdir():
                    tar.add(file_path, arcname=file_path.name)
            tar_buffer.seek(0)

            # Upload to GCS
            SubmissionOrchestrator._update_progress(
                db, submission,
                "Uploading Source",
                f"Uploading application code to Google Cloud Storage...",
                25
            )

            storage_client = storage.Client(project=project_id)
            bucket_name = f"{project_id}_cloudbuild"
            bucket = storage_client.bucket(bucket_name)
            blob_name = f"source/submission_{submission.id}.tar.gz"
            blob = bucket.blob(blob_name)
            blob.upload_from_file(tar_buffer, content_type='application/gzip')

            # Step 3: Build container using Cloud Build API
            image_tag = f"us-central1-docker.pkg.dev/{project_id}/sdp-repo/candidate-{submission.id}:latest"

            SubmissionOrchestrator._update_progress(
                db, submission,
                "Building Container",
                f"Building Docker container image: candidate-{submission.id}. This may take 2-3 minutes...",
                30
            )

            build_client = cloudbuild_v1.CloudBuildClient()
            build = cloudbuild_v1.Build(
                source=cloudbuild_v1.Source(
                    storage_source=cloudbuild_v1.StorageSource(
                        bucket=bucket_name,
                        object_=blob_name,
                    )
                ),
                steps=[
                    cloudbuild_v1.BuildStep(
                        name="gcr.io/cloud-builders/docker",
                        args=["build", "-t", image_tag, "."],
                    ),
                ],
                images=[image_tag],
                timeout={"seconds": 300},
            )

            operation = build_client.create_build(project_id=project_id, build=build)

            # Wait for build to complete using the operation
            import time
            start_time = time.time()
            build_id = operation.metadata.build.id

            while True:
                if time.time() - start_time > 300:
                    raise Exception("Build timed out after 5 minutes")

                # Get build status
                build_result = build_client.get_build(project_id=project_id, id=build_id)

                if build_result.status in [
                    cloudbuild_v1.Build.Status.SUCCESS,
                    cloudbuild_v1.Build.Status.FAILURE,
                    cloudbuild_v1.Build.Status.INTERNAL_ERROR,
                    cloudbuild_v1.Build.Status.TIMEOUT,
                    cloudbuild_v1.Build.Status.CANCELLED,
                ]:
                    break

                await asyncio.sleep(10)

            if build_result.status != cloudbuild_v1.Build.Status.SUCCESS:
                raise Exception(f"Build failed with status: {build_result.status.name}")

            SubmissionOrchestrator._update_progress(
                db, submission,
                "Container Built",
                f"Docker image built successfully. Deploying to Cloud Run...",
                50
            )

            # Step 4: Deploy to Cloud Run using Run API
            run_client = run_v2.ServicesClient()
            parent = f"projects/{project_id}/locations/{region}"

            SubmissionOrchestrator._update_progress(
                db, submission,
                "Deploying to Cloud Run",
                f"Creating Cloud Run service: {service_name} in {region}...",
                55
            )

            service = run_v2.Service(
                ingress=run_v2.IngressTraffic.INGRESS_TRAFFIC_ALL,  # Allow public access
                template=run_v2.RevisionTemplate(
                    containers=[
                        run_v2.Container(
                            image=image_tag,
                            ports=[run_v2.ContainerPort(container_port=8080)],
                            resources=run_v2.ResourceRequirements(
                                limits={"memory": "512Mi", "cpu": "1"},
                            ),
                        )
                    ],
                    scaling=run_v2.RevisionScaling(
                        min_instance_count=0,
                        max_instance_count=2,
                    ),
                ),
            )

            # Check if service exists first
            service_path = f"{parent}/services/{service_name}"
            try:
                existing_service = run_client.get_service(name=service_path)
                # Service exists, update it
                service.name = service_path
                operation = run_client.update_service(service=service)
            except Exception:
                # Service doesn't exist, create new one (name must be empty)
                operation = run_client.create_service(
                    parent=parent,
                    service=service,
                    service_id=service_name,
                )

            # Wait for deployment
            result = operation.result(timeout=300)
            endpoint_url = result.uri

            SubmissionOrchestrator._update_progress(
                db, submission,
                "Service Deployed",
                f"Cloud Run service is live at: {endpoint_url}",
                65
            )

            # Make service publicly accessible using IAM API
            try:
                from google.iam.v1 import iam_policy_pb2
                from google.iam.v1 import policy_pb2

                # Get current policy
                get_request = iam_policy_pb2.GetIamPolicyRequest(resource=result.name)
                policy = run_client.get_iam_policy(request=get_request)

                # Add allUsers as invoker
                policy.bindings.append(
                    policy_pb2.Binding(
                        role="roles/run.invoker",
                        members=["allUsers"],
                    )
                )

                # Set the updated policy
                set_request = iam_policy_pb2.SetIamPolicyRequest(
                    resource=result.name,
                    policy=policy,
                )
                run_client.set_iam_policy(request=set_request)
            except Exception as iam_error:
                # Log but don't fail - service is deployed, just not public
                print(f"Warning: Could not set IAM policy: {iam_error}")

            # Store deployment info
            submission.deployment_id = service_name
            submission.namespace = namespace
            submission.endpoint_url = endpoint_url  # Store endpoint URL directly

            # Update validation_feedback - need to reassign to trigger SQLAlchemy change detection
            feedback = submission.validation_feedback or {}
            feedback["deployment"] = {
                "endpoint_url": endpoint_url,
                "service_name": service_name,
                "image": image_tag,
                "deployment_mode": "cloud_run",
            }
            feedback["generated_code"] = api_code[:2000]
            submission.validation_feedback = feedback  # Reassign to trigger change detection
            # Don't set status here - let _run_tests set it to TESTING
            db.commit()

            # Track GCP deployment costs
            try:
                from decimal import Decimal
                from backend.models.audit_log import CostCategory

                audit_service = AuditService(db)

                # Log deployment action
                deploy_log = audit_service.log_action(
                    action=ActionType.DEPLOY_COMPLETE,
                    user_id=submission.user_id,
                    resource_type="submission",
                    resource_id=submission.id,
                    details={
                        "service_name": service_name,
                        "endpoint_url": endpoint_url,
                        "deployment_mode": "cloud_run",
                        "memory": "512Mi",
                        "cpu": "1",
                    },
                )

                # Track Cloud Run compute cost (estimated 1 hour of usage)
                # Cloud Run: ~$0.024/vCPU-hour + ~$0.0025/GB-hour
                # 1 vCPU + 0.5GB for 1 hour = ~$0.02525
                compute_hours = Decimal("1.0")  # 1 hour deployment timeout
                audit_service.track_gcp_usage(
                    user_id=submission.user_id,
                    audit_log_id=deploy_log.id,
                    category=CostCategory.GCP_COMPUTE,
                    quantity=compute_hours,
                    unit="vCPU-hours",
                    details={"service_name": service_name, "memory": "512Mi", "cpu": "1"},
                )

                # Track storage cost for source upload (typically < 1MB)
                storage_mb = Decimal("1.0")  # Approximate source size
                audit_service.track_gcp_usage(
                    user_id=submission.user_id,
                    audit_log_id=deploy_log.id,
                    category=CostCategory.GCP_STORAGE,
                    quantity=storage_mb,
                    unit="MB",
                    details={"bucket": bucket_name, "blob": blob_name},
                )

            except Exception as cost_error:
                import logging
                logging.getLogger(__name__).error(f"Failed to track GCP costs: {cost_error}")

            # Register with cleanup scheduler (1 hour timeout)
            cleanup_scheduler.register_deployment(
                submission_id=submission.id,
                deployment_id=service_name,
                namespace=namespace,
                deployment_mode="cloud_run",
                endpoint_url=endpoint_url,
                timeout_minutes=60,
            )

        except Exception as e:
            submission.status = SubmissionStatus.DEPLOY_FAILED.value
            submission.error_message = f"Cloud Run deployment failed: {str(e)}"
            db.commit()

    @staticmethod
    async def _warm_pool_deploy(
        db: Session,
        submission: Submission,
        problem: Problem,
    ) -> None:
        """
        Fastest deployment using warm container pool with pre-provisioned infrastructure.
        Sub-second deployment for candidate API code.
        """
        submission.status = SubmissionStatus.DEPLOYING.value
        db.commit()

        warm_pool = WarmPoolService()

        # Determine required services from problem tags
        required_services = [ServiceType.POSTGRES]  # Default
        if problem.tags:
            if "cache" in problem.tags or "redis" in problem.tags:
                required_services.append(ServiceType.REDIS)
            if "nosql" in problem.tags or "cassandra" in problem.tags:
                required_services.append(ServiceType.CASSANDRA)
            if "messaging" in problem.tags or "kafka" in problem.tags:
                required_services.append(ServiceType.KAFKA)
            if "search" in problem.tags or "elasticsearch" in problem.tags:
                required_services.append(ServiceType.ELASTICSEARCH)

        # Generate candidate API code from their design
        from backend.services.ai_service import AIService
        ai_service = AIService()

        try:
            api_code = await ai_service.generate_api_code(
                problem_description=problem.description,
                design_text=submission.design_text or "",
                api_spec=submission.api_spec_input,
                required_services=[s.value for s in required_services],
            )

            # Track AI usage cost
            try:
                input_tokens, output_tokens = ai_service.get_last_usage()
                if input_tokens > 0 or output_tokens > 0:
                    audit_service = AuditService(db)
                    audit_log = audit_service.log_action(
                        action=ActionType.AI_GENERATE_CODE,
                        user_id=submission.user_id,
                        resource_type="submission",
                        resource_id=submission.id,
                        details={"input_tokens": input_tokens, "output_tokens": output_tokens, "mode": "warm_pool"},
                    )
                    audit_service.track_ai_usage(
                        user_id=submission.user_id,
                        audit_log_id=audit_log.id,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        model=ai_service.model,
                    )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to track AI cost: {e}")

            result = await warm_pool.deploy_candidate_api(
                submission_id=submission.id,
                api_code=api_code,
                required_services=required_services,
                api_spec=submission.api_spec_input,
            )

            if result["success"]:
                submission.deployment_id = result.get("container_id", f"warm-{submission.id}")
                submission.validation_feedback = submission.validation_feedback or {}
                submission.validation_feedback["deployment"] = {
                    "endpoint_url": result.get("endpoint_url"),
                    "deployment_time_seconds": result.get("deployment_time_seconds"),
                    "strategy": "warm_pool",
                    "services": result.get("services"),
                    "namespace": result.get("namespace"),
                }
                db.commit()

                # Track GCP deployment costs for warm pool
                try:
                    from decimal import Decimal
                    from backend.models.audit_log import CostCategory

                    audit_service = AuditService(db)

                    # Log deployment action
                    deploy_log = audit_service.log_action(
                        action=ActionType.DEPLOY_COMPLETE,
                        user_id=submission.user_id,
                        resource_type="submission",
                        resource_id=submission.id,
                        details={
                            "endpoint_url": result.get("endpoint_url"),
                            "deployment_mode": "warm_pool",
                            "deployment_time_seconds": result.get("deployment_time_seconds"),
                            "services": [s.value for s in required_services],
                        },
                    )

                    # Track compute cost (warm pool is more efficient)
                    compute_hours = Decimal("0.5")  # Estimated 30 min active usage
                    audit_service.track_gcp_usage(
                        user_id=submission.user_id,
                        audit_log_id=deploy_log.id,
                        category=CostCategory.GCP_COMPUTE,
                        quantity=compute_hours,
                        unit="vCPU-hours",
                        details={"deployment_mode": "warm_pool", "services": [s.value for s in required_services]},
                    )

                except Exception as cost_error:
                    import logging
                    logging.getLogger(__name__).error(f"Failed to track GCP costs: {cost_error}")

                # Register with cleanup scheduler (1 hour timeout)
                cleanup_scheduler.register_deployment(
                    submission_id=submission.id,
                    deployment_id=submission.deployment_id,
                    namespace=result.get("namespace", f"sub-{submission.id}"),
                    deployment_mode="warm_pool",
                    endpoint_url=result.get("endpoint_url", ""),
                    timeout_minutes=60,  # 1 hour timeout
                )
            else:
                raise Exception(result.get("error", "Warm pool deployment failed"))

        except Exception as e:
            submission.status = SubmissionStatus.DEPLOY_FAILED.value
            submission.error_message = f"Warm pool deployment failed: {str(e)}"
            db.commit()

    @staticmethod
    async def _fast_deploy(
        db: Session,
        submission: Submission,
        problem: Problem,
    ) -> None:
        """
        Fast deployment using Cloud Run (seconds instead of minutes).
        Uses pre-provisioned shared infrastructure with dynamic app deployment.
        """
        submission.status = SubmissionStatus.DEPLOYING.value
        db.commit()

        deployment_service = FastDeploymentService()

        # Determine problem type from tags or title
        problem_type = "url_shortener"  # Default
        if problem.tags:
            if "rate-limiting" in problem.tags or "rate limiter" in problem.title.lower():
                problem_type = "rate_limiter"
            elif "cache" in problem.tags or "cache" in problem.title.lower():
                problem_type = "cache"
            elif "notification" in problem.tags:
                problem_type = "notification"

        try:
            result = await deployment_service.deploy(
                submission_id=submission.id,
                design_text=submission.design_text or "",
                api_spec=submission.api_spec_input,
                problem_type=problem_type,
            )

            if result["success"]:
                submission.deployment_id = result.get("service_name", f"sub-{submission.id}")
                # Store deployment info for later reference
                submission.validation_feedback = submission.validation_feedback or {}
                submission.validation_feedback["deployment"] = {
                    "endpoint_url": result.get("endpoint_url"),
                    "deployment_time_seconds": result.get("deployment_time_seconds"),
                    "strategy": result.get("strategy"),
                    "resources": result.get("resources"),
                }
                db.commit()

                # Register with cleanup scheduler (1 hour timeout)
                cleanup_scheduler.register_deployment(
                    submission_id=submission.id,
                    deployment_id=submission.deployment_id,
                    namespace=submission.namespace or f"sub-{submission.id}",
                    deployment_mode="fast",
                    endpoint_url=result.get("endpoint_url", ""),
                    timeout_minutes=60,  # 1 hour timeout
                )
            else:
                raise Exception(result.get("error", "Deployment failed"))

        except Exception as e:
            submission.status = SubmissionStatus.DEPLOY_FAILED.value
            submission.error_message = f"Fast deployment failed: {str(e)}"
            db.commit()

    @staticmethod
    async def _generate_infrastructure(
        db: Session,
        submission: Submission,
        problem: Problem,
    ) -> None:
        """Generate Terraform code from design."""
        submission.status = SubmissionStatus.GENERATING_INFRA.value
        db.commit()

        terraform_service = TerraformService()

        try:
            terraform_code = await terraform_service.generate_terraform(
                problem_description=problem.description,
                design_text=submission.design_text or "",
                schema_input=submission.schema_input,
                api_spec_input=submission.api_spec_input,
                namespace=submission.namespace,
            )

            submission.generated_terraform = terraform_code
            db.commit()

        except Exception as e:
            submission.status = SubmissionStatus.FAILED.value
            submission.error_message = f"Failed to generate infrastructure: {str(e)}"
            db.commit()

    @staticmethod
    async def _deploy_infrastructure(
        db: Session,
        submission: Submission,
    ) -> None:
        """Deploy infrastructure to GCP using Terraform."""
        submission.status = SubmissionStatus.DEPLOYING.value
        db.commit()

        terraform_service = TerraformService()
        gcp_service = GCPService()

        # Check if GCP is configured
        if not gcp_service.is_configured():
            # Skip actual deployment in development
            submission.deployment_id = f"mock-deployment-{submission.id}"
            db.commit()
            return

        try:
            # Create workspace
            workspace = terraform_service.create_workspace(
                submission_id=submission.id,
                terraform_code=submission.generated_terraform,
            )

            # Initialize Terraform
            init_result = terraform_service.init_workspace(workspace)
            if not init_result["success"]:
                raise Exception(f"Terraform init failed: {init_result['stderr']}")

            # Plan
            plan_result = terraform_service.plan(workspace)
            if not plan_result["success"]:
                raise Exception(f"Terraform plan failed: {plan_result['stderr']}")

            # Apply
            apply_result = terraform_service.apply(workspace)
            if not apply_result["success"]:
                raise Exception(f"Terraform apply failed: {apply_result['stderr']}")

            # Get outputs
            outputs = terraform_service.get_outputs(workspace)
            submission.deployment_id = outputs.get("deployment_id", {}).get("value", str(submission.id))

            db.commit()

        except Exception as e:
            submission.status = SubmissionStatus.DEPLOY_FAILED.value
            submission.error_message = f"Deployment failed: {str(e)}"
            db.commit()

    @staticmethod
    async def _run_tests(
        db: Session,
        submission: Submission,
        problem: Problem,
    ) -> None:
        """Run all tests against deployed infrastructure."""
        submission.status = SubmissionStatus.TESTING.value
        db.commit()

        test_runner = TestRunner()

        # Get endpoint URL - prefer direct field, then validation_feedback, then construct from deployment_id
        deployment_info = submission.validation_feedback.get("deployment", {}) if submission.validation_feedback else {}
        endpoint_url = (
            submission.endpoint_url or
            deployment_info.get("endpoint_url") or
            f"https://{submission.deployment_id}-5i2gvcmu3q-uc.a.run.app"  # Fallback with correct format
        )

        SubmissionOrchestrator._update_progress(
            db, submission,
            "Starting Tests",
            f"Running tests against deployed service at {endpoint_url}...",
            70
        )

        # Determine test files being used
        problem_desc = problem.description.lower()
        if "url" in problem_desc and "shorten" in problem_desc:
            test_suite = "URL Shortener"
            tests_info = "test_url_shortener.py, locustfile_url_shortener.py, experiment_url_shortener.json"
        elif "file" in problem_desc and ("shar" in problem_desc or "dropbox" in problem_desc):
            test_suite = "File Sharing"
            tests_info = "test_file_sharing.py, locustfile_file_sharing.py, experiment_file_sharing.json"
        elif "chat" in problem_desc or "whatsapp" in problem_desc:
            test_suite = "Chat Application"
            tests_info = "test_chat_app.py, locustfile_chat.py, experiment_chat.json"
        else:
            test_suite = "Generic"
            tests_info = "test_url_shortener.py (default)"

        # Create progress callback
        def progress_callback(step: str, detail: str, pct: int):
            SubmissionOrchestrator._update_progress(db, submission, step, detail, pct)

        SubmissionOrchestrator._update_progress(
            db, submission,
            "Running Functional Tests",
            f"Executing {test_suite} functional tests using pytest. Testing API endpoints, data validation, and business logic...",
            75
        )

        try:
            results = await test_runner.run_all_tests(
                submission_id=submission.id,
                endpoint_url=endpoint_url,
                api_spec=submission.api_spec_input,
                design_text=submission.design_text or "",
                progress_callback=progress_callback,
                problem_description=problem.description,
            )

            # Store test results
            for result in results:
                test_result = TestResult(
                    submission_id=submission.id,
                    test_type=result["test_type"],
                    test_name=result["test_name"],
                    status=result["status"],
                    details=result.get("details"),
                    duration_ms=result.get("duration_ms"),
                    chaos_scenario=result.get("chaos_scenario"),
                )
                db.add(test_result)

            db.commit()

        except Exception as e:
            submission.error_message = f"Testing failed: {str(e)}"
            db.commit()

    @staticmethod
    async def cleanup_submission(submission_id: int) -> None:
        """
        Clean up resources for a submission.

        Args:
            submission_id: Submission ID
        """
        db = SessionLocal()

        try:
            submission = db.query(Submission).filter(Submission.id == submission_id).first()
            if not submission or not submission.namespace:
                return

            if DEPLOYMENT_MODE in ["cloud_run", "fast"]:
                # Clean up Cloud Run deployment
                deployment_service = FastDeploymentService()
                await deployment_service.cleanup(submission_id, submission.namespace)
            elif DEPLOYMENT_MODE == "warm_pool":
                # Clean up warm pool resources
                warm_pool = WarmPoolService()
                # warm_pool.cleanup(submission_id)
                pass
            else:
                # Clean up Terraform resources
                terraform_service = TerraformService()
                gcp_service = GCPService()

                workspace = terraform_service.workspace_dir / f"submission_{submission_id}"
                if workspace.exists():
                    terraform_service.destroy(workspace)
                    terraform_service.cleanup_workspace(workspace)

                if gcp_service.is_configured():
                    gcp_service.cleanup_namespace_resources(submission.namespace)

        finally:
            db.close()

    @staticmethod
    async def diagnose_deployment(submission_id: int) -> Dict[str, Any]:
        """
        Diagnose deployment issues by checking Cloud Run service status and logs.

        Args:
            submission_id: Submission ID to diagnose

        Returns:
            Diagnostic information including service status, recent logs, and identified issues
        """
        from google.cloud import logging as cloud_logging
        from google.cloud import run_v2
        import httpx

        db = SessionLocal()
        diagnosis = {
            "submission_id": submission_id,
            "service_status": None,
            "health_check": None,
            "recent_logs": [],
            "identified_issues": [],
            "recommendations": [],
        }

        try:
            submission = db.query(Submission).filter(Submission.id == submission_id).first()
            if not submission:
                diagnosis["identified_issues"].append("Submission not found")
                return diagnosis

            settings = get_settings()
            service_name = f"candidate-{submission.namespace}"

            # Check Cloud Run service status
            try:
                client = run_v2.ServicesClient()
                service_path = f"projects/{settings.gcp_project_id}/locations/{settings.gcp_region}/services/{service_name}"
                service = client.get_service(name=service_path)

                diagnosis["service_status"] = {
                    "name": service.name,
                    "uri": service.uri,
                    "latest_ready_revision": service.latest_ready_revision,
                    "conditions": [
                        {"type": c.type_, "status": c.state.name, "message": c.message}
                        for c in service.conditions
                    ],
                }

                # Check for unhealthy conditions
                for condition in service.conditions:
                    if condition.state.name != "CONDITION_SUCCEEDED":
                        diagnosis["identified_issues"].append(
                            f"Service condition '{condition.type_}' is {condition.state.name}: {condition.message}"
                        )
            except Exception as e:
                diagnosis["identified_issues"].append(f"Failed to get service status: {str(e)}")

            # Query Cloud Logging for recent errors
            try:
                logging_client = cloud_logging.Client(project=settings.gcp_project_id)

                # Query for errors in the last hour
                filter_str = f'''
                    resource.type="cloud_run_revision"
                    resource.labels.service_name="{service_name}"
                    severity>=ERROR
                    timestamp>="{(datetime.utcnow() - timedelta(hours=1)).isoformat()}Z"
                '''

                entries = list(logging_client.list_entries(filter_=filter_str, max_results=20))

                for entry in entries:
                    log_entry = {
                        "timestamp": str(entry.timestamp),
                        "severity": entry.severity,
                        "message": entry.payload if isinstance(entry.payload, str) else str(entry.payload),
                    }
                    diagnosis["recent_logs"].append(log_entry)

                    # Analyze error patterns
                    msg = log_entry["message"].lower()
                    if "modulenotfounderror" in msg or "importerror" in msg:
                        diagnosis["identified_issues"].append("Import error - missing dependency")
                        diagnosis["recommendations"].append("Check requirements.txt includes all needed packages")
                    elif "syntaxerror" in msg:
                        diagnosis["identified_issues"].append("Syntax error in generated code")
                        diagnosis["recommendations"].append("Review generated code for syntax issues")
                    elif "connection refused" in msg or "could not connect" in msg:
                        diagnosis["identified_issues"].append("Database/service connection error")
                        diagnosis["recommendations"].append("Ensure code uses in-memory storage, not external DB")
                    elif "memory" in msg or "oom" in msg:
                        diagnosis["identified_issues"].append("Out of memory error")
                        diagnosis["recommendations"].append("Increase Cloud Run memory limit")
                    elif "timeout" in msg:
                        diagnosis["identified_issues"].append("Request timeout")
                        diagnosis["recommendations"].append("Check for infinite loops or slow operations")

            except Exception as e:
                diagnosis["identified_issues"].append(f"Failed to query logs: {str(e)}")

            # Perform health check if service URL is available
            if submission.endpoint_url:
                diagnosis["health_check"] = await SubmissionOrchestrator.get_service_health(
                    submission_id, submission.endpoint_url
                )

        finally:
            db.close()

        return diagnosis

    @staticmethod
    async def get_service_health(submission_id: int, endpoint_url: str) -> Dict[str, Any]:
        """
        Perform health checks on the deployed service.

        Args:
            submission_id: Submission ID
            endpoint_url: Service endpoint URL

        Returns:
            Health check results
        """
        import httpx

        health_result = {
            "endpoint_url": endpoint_url,
            "health_endpoint": None,
            "root_endpoint": None,
            "latency_ms": None,
            "issues": [],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Check /health endpoint
            try:
                start = datetime.utcnow()
                response = await client.get(f"{endpoint_url}/health")
                latency = (datetime.utcnow() - start).total_seconds() * 1000

                health_result["health_endpoint"] = {
                    "status_code": response.status_code,
                    "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text[:500],
                    "latency_ms": round(latency, 2),
                }
                health_result["latency_ms"] = round(latency, 2)

                if response.status_code != 200:
                    health_result["issues"].append(f"/health returned {response.status_code}, expected 200")
                else:
                    try:
                        data = response.json()
                        if data.get("status") != "healthy":
                            health_result["issues"].append(f"/health status is '{data.get('status')}', expected 'healthy'")
                    except:
                        health_result["issues"].append("/health did not return valid JSON")

            except httpx.TimeoutException:
                health_result["health_endpoint"] = {"error": "Timeout after 30 seconds"}
                health_result["issues"].append("/health endpoint timed out - service may be unresponsive")
            except httpx.ConnectError as e:
                health_result["health_endpoint"] = {"error": f"Connection failed: {str(e)}"}
                health_result["issues"].append("Cannot connect to service - may not be running")
            except Exception as e:
                health_result["health_endpoint"] = {"error": str(e)}
                health_result["issues"].append(f"/health check failed: {str(e)}")

            # Check root endpoint
            try:
                response = await client.get(endpoint_url)
                health_result["root_endpoint"] = {
                    "status_code": response.status_code,
                    "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text[:500],
                }
            except Exception as e:
                health_result["root_endpoint"] = {"error": str(e)}

        return health_result
