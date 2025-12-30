"""
Admin API endpoints for platform management.
Provides access to warm pool status, cleanup management, and other administrative functions.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List

from backend.database import get_db
from backend.models.submission import Submission
from backend.models.user import User
from backend.services.warm_pool_service import WarmPoolService
from backend.services.cleanup_scheduler import cleanup_scheduler
from backend.api.user import require_admin
from backend.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/warm-pool/status")
async def get_warm_pool_status():
    """
    Get the current status of the warm container pool.

    Returns:
        Pool status including container counts and details
    """
    warm_pool = WarmPoolService()
    return warm_pool.get_pool_status()


@router.get("/deployment-mode")
async def get_deployment_mode():
    """
    Get the current deployment mode.

    Returns:
        Current deployment mode and available options
    """
    from backend.services.orchestrator import DEPLOYMENT_MODE

    return {
        "current_mode": DEPLOYMENT_MODE,
        "available_modes": {
            "warm_pool": {
                "description": "Pre-provisioned infrastructure + warm containers",
                "deployment_time": "< 1 second",
            },
            "fast": {
                "description": "Cloud Run dynamic deployment",
                "deployment_time": "10-30 seconds",
            },
            "terraform": {
                "description": "Full Terraform infrastructure deployment",
                "deployment_time": "10-15 minutes",
            },
        },
    }


@router.get("/infrastructure/status")
async def get_infrastructure_status():
    """
    Get the status of pre-provisioned infrastructure services.

    Returns:
        Status of all infrastructure services (Postgres, Cassandra, Kafka, etc.)
    """
    warm_pool = WarmPoolService()

    services = {}
    for service_type, service in warm_pool.infrastructure.items():
        services[service_type.value] = {
            "host": service.host,
            "port": service.port,
            "status": "available",  # In production, would do health checks
        }

    return {
        "services": services,
        "total_services": len(services),
    }


# ============ Deployment & Cleanup Management ============

@router.get("/deployments")
async def get_all_deployments(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Get all active deployments from the database.

    Returns:
        List of all active deployments with their details
    """
    # Query database for active deployments (submissions with deployment_id)
    active_statuses = ["deploying", "testing", "completed", "deploy_failed"]
    submissions = db.query(Submission).filter(
        Submission.deployment_id.isnot(None),
        Submission.status.in_(active_statuses),
    ).order_by(Submission.created_at.desc()).all()

    deployments = []
    for submission in submissions:
        user = submission.user
        deployments.append({
            "submission_id": submission.id,
            "user_email": user.email if user else "unknown",
            "deployment_id": submission.deployment_id,
            "endpoint_url": submission.endpoint_url,
            "status": submission.status,
            "created_at": submission.created_at.isoformat(),
            "deployment_mode": "distributed" if hasattr(submission, 'language') else "warm_pool",
        })

    return {
        "deployments": deployments,
        "total_count": len(deployments),
        "default_timeout_minutes": cleanup_scheduler.timeout_minutes,
    }


@router.get("/deployments/{submission_id}")
async def get_deployment_status(
    submission_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Get the status of a specific deployment.

    Returns:
        Deployment details from database
    """
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission or not submission.deployment_id:
        raise HTTPException(status_code=404, detail="Deployment not found")

    user = submission.user
    return {
        "submission_id": submission.id,
        "user_email": user.email if user else "unknown",
        "deployment_id": submission.deployment_id,
        "endpoint_url": submission.endpoint_url,
        "status": submission.status,
        "created_at": submission.created_at.isoformat(),
    }


@router.post("/deployments/{submission_id}/teardown")
async def teardown_deployment(
    submission_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Manually tear down a deployment immediately.

    This will delete the Cloud Run service and update the database.
    """
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if not submission.deployment_id:
        raise HTTPException(status_code=400, detail="No deployment to teardown")

    result = await _delete_cloud_run_service(submission, db)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Teardown failed"))

    return result


async def _delete_cloud_run_service(submission: Submission, db: Session) -> dict:
    """
    Delete a Cloud Run service for a submission.
    """
    from google.cloud import run_v2
    import logging

    logger = logging.getLogger(__name__)
    service_name = submission.deployment_id
    project_id = settings.gcp_project_id
    region = settings.gcp_region or "us-central1"

    try:
        # Delete the Cloud Run service
        client = run_v2.ServicesClient()
        name = f"projects/{project_id}/locations/{region}/services/{service_name}"

        logger.info(f"Deleting Cloud Run service: {name}")

        try:
            operation = client.delete_service(name=name)
            # Wait for deletion to complete (with timeout)
            operation.result(timeout=60)
            logger.info(f"Successfully deleted service: {service_name}")
        except Exception as e:
            # Service might not exist or already deleted
            logger.warning(f"Could not delete service {service_name}: {e}")

        # Update submission status
        submission.status = "cleaned_up"
        submission.deployment_id = None
        submission.endpoint_url = None
        if not submission.validation_feedback:
            submission.validation_feedback = {}
        submission.validation_feedback["cleanup"] = {
            "status": "cleaned_up",
            "cleaned_at": datetime.utcnow().isoformat(),
            "cleaned_by": "admin",
        }
        db.commit()

        return {
            "success": True,
            "submission_id": submission.id,
            "service_name": service_name,
            "message": f"Deleted Cloud Run service: {service_name}",
        }

    except Exception as e:
        logger.error(f"Failed to delete service {service_name}: {e}")
        return {
            "success": False,
            "submission_id": submission.id,
            "error": str(e),
        }


@router.post("/deployments/{submission_id}/extend")
async def extend_deployment_timeout(submission_id: int, additional_minutes: int = 30):
    """
    Extend the cleanup timeout for a deployment.

    Args:
        submission_id: The submission ID
        additional_minutes: Minutes to add to the timeout (default: 30)
    """
    result = cleanup_scheduler.extend_timeout(submission_id, additional_minutes)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Extension failed"))

    return result


@router.post("/deployments/cleanup-all")
async def cleanup_all_deployments(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Tear down all active deployments.
    Use with caution!
    """
    # Query database for active deployments
    active_statuses = ["deploying", "testing", "completed", "deploy_failed"]
    submissions = db.query(Submission).filter(
        Submission.deployment_id.isnot(None),
        Submission.status.in_(active_statuses),
    ).all()

    results = []
    for submission in submissions:
        result = await _delete_cloud_run_service(submission, db)
        results.append(result)

    return {
        "cleaned_up": len([r for r in results if r.get("success")]),
        "failed": len([r for r in results if not r.get("success")]),
        "results": results,
    }
