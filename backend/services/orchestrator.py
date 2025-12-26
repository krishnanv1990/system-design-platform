"""
Submission orchestrator for managing the evaluation pipeline.
Coordinates validation, deployment, and testing of candidate solutions.
"""

import asyncio
from typing import Optional
from datetime import datetime

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
            requirements.write_text("""fastapi==0.109.0
uvicorn[standard]==0.27.0
asyncpg==0.29.0
pydantic==2.6.0
httpx==0.27.0
""")

            dockerfile = workspace / "Dockerfile"
            dockerfile.write_text("""FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
EXPOSE 8080
ENV PORT=8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
""")

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

            database_url = f"postgresql://postgres:sdp-demo-2024@/candidate_{submission.id}?host=/cloudsql/{project_id}:{region}:sdp-db"

            SubmissionOrchestrator._update_progress(
                db, submission,
                "Deploying to Cloud Run",
                f"Creating Cloud Run service: {service_name} in {region}...",
                55
            )

            service = run_v2.Service(
                template=run_v2.RevisionTemplate(
                    containers=[
                        run_v2.Container(
                            image=image_tag,
                            ports=[run_v2.ContainerPort(container_port=8080)],
                            env=[
                                run_v2.EnvVar(name="DATABASE_URL", value=database_url),
                            ],
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

            try:
                # Try to update existing service
                service.name = f"{parent}/services/{service_name}"
                operation = run_client.update_service(service=service)
            except Exception:
                # Create new service
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

            # Make service publicly accessible
            from google.iam.v1 import policy_pb2, iam_policy_pb2
            policy = run_client.get_iam_policy(resource=result.name)
            policy.bindings.append(
                policy_pb2.Binding(
                    role="roles/run.invoker",
                    members=["allUsers"],
                )
            )
            run_client.set_iam_policy(resource=result.name, policy=policy)

            # Store deployment info
            submission.deployment_id = service_name
            submission.namespace = namespace
            submission.validation_feedback = submission.validation_feedback or {}
            submission.validation_feedback["deployment"] = {
                "endpoint_url": endpoint_url,
                "service_name": service_name,
                "image": image_tag,
                "deployment_mode": "cloud_run",
            }
            submission.validation_feedback["generated_code"] = api_code[:2000]
            submission.status = SubmissionStatus.DEPLOYED.value
            db.commit()

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

        # Get endpoint URL from deployment info
        deployment_info = submission.validation_feedback.get("deployment", {}) if submission.validation_feedback else {}
        endpoint_url = deployment_info.get("endpoint_url", f"https://{submission.deployment_id}-{settings.gcp_project_id}.{settings.gcp_region}.run.app")

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
