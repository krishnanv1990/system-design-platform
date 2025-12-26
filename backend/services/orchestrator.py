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
from backend.config import get_settings

settings = get_settings()

# Deployment mode options:
# - "warm_pool" (sub-second, pre-provisioned infrastructure + warm containers)
# - "fast" (Cloud Run, 10-30 seconds)
# - "terraform" (full infra, 10-15 minutes)
DEPLOYMENT_MODE = "warm_pool"


class SubmissionOrchestrator:
    """
    Orchestrates the complete evaluation pipeline for submissions.
    Manages the flow from validation through deployment and testing.
    """

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
            # Use warm pool (fastest), fast deployment, or legacy Terraform
            if DEPLOYMENT_MODE == "warm_pool":
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

        # Construct endpoint URL (would come from Terraform outputs in production)
        endpoint_url = f"https://{submission.namespace}.{settings.gcp_region}.run.app"

        try:
            results = await test_runner.run_all_tests(
                submission_id=submission.id,
                endpoint_url=endpoint_url,
                api_spec=submission.api_spec_input,
                design_text=submission.design_text or "",
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

            if DEPLOYMENT_MODE == "fast":
                # Clean up Cloud Run deployment
                deployment_service = FastDeploymentService()
                await deployment_service.cleanup(submission_id, submission.namespace)
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
