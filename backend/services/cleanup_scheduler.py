"""
Cleanup Scheduler Service

Manages automatic teardown of deployed candidate resources:
- Tracks deployment timestamps
- Schedules cleanup after configurable timeout (default: 1 hour)
- Supports manual teardown
- Recycles warm pool containers
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dataclasses import dataclass, field
import logging

from backend.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Default timeout: 1 hour
DEFAULT_TIMEOUT_MINUTES = 60


@dataclass
class DeploymentRecord:
    """Tracks a deployed submission for cleanup."""
    submission_id: int
    deployment_id: str
    deployed_at: datetime
    timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES
    scheduled_cleanup_at: datetime = field(init=False)
    namespace: str = ""
    deployment_mode: str = "warm_pool"  # warm_pool, fast, terraform
    endpoint_url: str = ""
    is_cleaned_up: bool = False
    cleanup_task: Optional[asyncio.Task] = None

    def __post_init__(self):
        self.scheduled_cleanup_at = self.deployed_at + timedelta(minutes=self.timeout_minutes)


class CleanupScheduler:
    """
    Schedules and manages cleanup of deployed resources.

    Features:
    - Automatic cleanup after timeout (default 1 hour)
    - Manual teardown support
    - Warm pool container recycling
    - Cleanup status tracking
    """

    _instance = None

    def __new__(cls):
        """Singleton pattern for global scheduler access."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.deployments: Dict[int, DeploymentRecord] = {}
        self.timeout_minutes = DEFAULT_TIMEOUT_MINUTES
        self._cleanup_callbacks = []
        logger.info(f"CleanupScheduler initialized with {self.timeout_minutes} minute timeout")

    def register_deployment(
        self,
        submission_id: int,
        deployment_id: str,
        namespace: str,
        deployment_mode: str = "warm_pool",
        endpoint_url: str = "",
        timeout_minutes: Optional[int] = None,
    ) -> DeploymentRecord:
        """
        Register a new deployment for scheduled cleanup.

        Args:
            submission_id: The submission ID
            deployment_id: The deployment/container ID
            namespace: Deployment namespace
            deployment_mode: warm_pool, fast, or terraform
            endpoint_url: The deployed endpoint URL
            timeout_minutes: Custom timeout (defaults to 60 minutes)

        Returns:
            DeploymentRecord for tracking
        """
        timeout = timeout_minutes or self.timeout_minutes

        record = DeploymentRecord(
            submission_id=submission_id,
            deployment_id=deployment_id,
            deployed_at=datetime.utcnow(),
            timeout_minutes=timeout,
            namespace=namespace,
            deployment_mode=deployment_mode,
            endpoint_url=endpoint_url,
        )

        self.deployments[submission_id] = record

        # Schedule automatic cleanup
        record.cleanup_task = asyncio.create_task(
            self._scheduled_cleanup(submission_id, timeout)
        )

        logger.info(
            f"Registered deployment for submission {submission_id}, "
            f"scheduled cleanup at {record.scheduled_cleanup_at}"
        )

        return record

    async def _scheduled_cleanup(self, submission_id: int, timeout_minutes: int):
        """Background task that waits and then triggers cleanup."""
        try:
            await asyncio.sleep(timeout_minutes * 60)
            await self.cleanup_deployment(submission_id, reason="timeout")
        except asyncio.CancelledError:
            logger.info(f"Cleanup task cancelled for submission {submission_id}")

    async def cleanup_deployment(
        self,
        submission_id: int,
        reason: str = "manual",
    ) -> Dict:
        """
        Clean up a deployment (manual or automatic).

        Args:
            submission_id: The submission to clean up
            reason: "manual" or "timeout"

        Returns:
            Cleanup result
        """
        record = self.deployments.get(submission_id)
        if not record:
            return {
                "success": False,
                "error": f"No deployment found for submission {submission_id}",
            }

        if record.is_cleaned_up:
            return {
                "success": True,
                "message": "Already cleaned up",
                "submission_id": submission_id,
            }

        logger.info(f"Cleaning up deployment for submission {submission_id} (reason: {reason})")

        try:
            # Cancel the scheduled cleanup task if this is manual
            if reason == "manual" and record.cleanup_task:
                record.cleanup_task.cancel()

            # Perform cleanup based on deployment mode
            if record.deployment_mode == "warm_pool":
                result = await self._cleanup_warm_pool(record)
            elif record.deployment_mode == "fast":
                result = await self._cleanup_cloud_run(record)
            else:
                result = await self._cleanup_terraform(record)

            record.is_cleaned_up = True

            # Update database
            await self._update_submission_status(submission_id, "cleaned_up")

            return {
                "success": True,
                "submission_id": submission_id,
                "deployment_id": record.deployment_id,
                "reason": reason,
                "cleaned_at": datetime.utcnow().isoformat(),
                "details": result,
            }

        except Exception as e:
            logger.error(f"Cleanup failed for submission {submission_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "submission_id": submission_id,
            }

    async def _cleanup_warm_pool(self, record: DeploymentRecord) -> Dict:
        """Recycle a warm pool container."""
        from backend.services.warm_pool_service import WarmPoolService

        warm_pool = WarmPoolService()
        await warm_pool.cleanup_submission(record.submission_id)

        return {
            "mode": "warm_pool",
            "action": "recycled",
            "container_id": record.deployment_id,
        }

    async def _cleanup_cloud_run(self, record: DeploymentRecord) -> Dict:
        """Delete Cloud Run service."""
        from backend.services.deployment_service import FastDeploymentService

        deployment_service = FastDeploymentService()
        await deployment_service.cleanup(record.submission_id, record.namespace)

        return {
            "mode": "cloud_run",
            "action": "deleted",
            "service_name": record.deployment_id,
        }

    async def _cleanup_terraform(self, record: DeploymentRecord) -> Dict:
        """Destroy Terraform resources."""
        from backend.services.orchestrator import SubmissionOrchestrator

        await SubmissionOrchestrator.cleanup_submission(record.submission_id)

        return {
            "mode": "terraform",
            "action": "destroyed",
            "namespace": record.namespace,
        }

    async def _update_submission_status(self, submission_id: int, status: str):
        """Update submission status in database."""
        from backend.database import SessionLocal
        from backend.models.submission import Submission

        db = SessionLocal()
        try:
            submission = db.query(Submission).filter(Submission.id == submission_id).first()
            if submission:
                if not submission.validation_feedback:
                    submission.validation_feedback = {}
                submission.validation_feedback["cleanup"] = {
                    "status": status,
                    "cleaned_at": datetime.utcnow().isoformat(),
                }
                db.commit()
        finally:
            db.close()

    def get_deployment_status(self, submission_id: int) -> Optional[Dict]:
        """Get status of a deployment."""
        record = self.deployments.get(submission_id)
        if not record:
            return None

        now = datetime.utcnow()
        time_remaining = (record.scheduled_cleanup_at - now).total_seconds()

        return {
            "submission_id": submission_id,
            "deployment_id": record.deployment_id,
            "namespace": record.namespace,
            "deployment_mode": record.deployment_mode,
            "endpoint_url": record.endpoint_url,
            "deployed_at": record.deployed_at.isoformat(),
            "scheduled_cleanup_at": record.scheduled_cleanup_at.isoformat(),
            "time_remaining_seconds": max(0, time_remaining),
            "time_remaining_minutes": max(0, time_remaining / 60),
            "is_cleaned_up": record.is_cleaned_up,
        }

    def get_all_active_deployments(self) -> List[Dict]:
        """Get all active (not cleaned up) deployments."""
        return [
            self.get_deployment_status(sid)
            for sid, record in self.deployments.items()
            if not record.is_cleaned_up
        ]

    def extend_timeout(self, submission_id: int, additional_minutes: int = 30) -> Dict:
        """Extend the cleanup timeout for a deployment."""
        record = self.deployments.get(submission_id)
        if not record:
            return {"success": False, "error": "Deployment not found"}

        if record.is_cleaned_up:
            return {"success": False, "error": "Deployment already cleaned up"}

        # Cancel existing task
        if record.cleanup_task:
            record.cleanup_task.cancel()

        # Update timeout
        record.timeout_minutes += additional_minutes
        record.scheduled_cleanup_at = record.deployed_at + timedelta(minutes=record.timeout_minutes)

        # Schedule new cleanup
        remaining = (record.scheduled_cleanup_at - datetime.utcnow()).total_seconds() / 60
        record.cleanup_task = asyncio.create_task(
            self._scheduled_cleanup(submission_id, remaining)
        )

        return {
            "success": True,
            "submission_id": submission_id,
            "new_scheduled_cleanup_at": record.scheduled_cleanup_at.isoformat(),
            "time_remaining_minutes": remaining,
        }


# Global scheduler instance
cleanup_scheduler = CleanupScheduler()
