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
from backend.services.test_runner import TestRunner
from backend.services.gcp_service import GCPService
from backend.config import get_settings

settings = get_settings()


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

            # Stage 2: Terraform Generation
            await SubmissionOrchestrator._generate_infrastructure(db, submission, problem)
            if submission.status == SubmissionStatus.FAILED.value:
                return

            # Stage 3: Deployment
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

            terraform_service = TerraformService()
            gcp_service = GCPService()

            # Destroy Terraform resources
            workspace = terraform_service.workspace_dir / f"submission_{submission_id}"
            if workspace.exists():
                terraform_service.destroy(workspace)
                terraform_service.cleanup_workspace(workspace)

            # Clean up any remaining GCP resources
            if gcp_service.is_configured():
                gcp_service.cleanup_namespace_resources(submission.namespace)

        finally:
            db.close()
