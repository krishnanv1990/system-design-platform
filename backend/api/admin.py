"""
Admin API endpoints for platform management.
Provides access to warm pool status, cleanup management, and other administrative functions.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from backend.services.warm_pool_service import WarmPoolService
from backend.services.cleanup_scheduler import cleanup_scheduler

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
async def get_all_deployments():
    """
    Get all active deployments with their cleanup schedules.

    Returns:
        List of all active deployments with time remaining
    """
    return {
        "deployments": cleanup_scheduler.get_all_active_deployments(),
        "default_timeout_minutes": cleanup_scheduler.timeout_minutes,
    }


@router.get("/deployments/{submission_id}")
async def get_deployment_status(submission_id: int):
    """
    Get the status of a specific deployment.

    Returns:
        Deployment details including time until cleanup
    """
    status = cleanup_scheduler.get_deployment_status(submission_id)
    if not status:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return status


@router.post("/deployments/{submission_id}/teardown")
async def teardown_deployment(submission_id: int):
    """
    Manually tear down a deployment immediately.

    This will:
    - For warm_pool: Recycle the container back to the pool
    - For fast: Delete the Cloud Run service
    - For terraform: Destroy all Terraform resources
    """
    result = await cleanup_scheduler.cleanup_deployment(submission_id, reason="manual")

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Teardown failed"))

    return result


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
async def cleanup_all_deployments():
    """
    Tear down all active deployments.
    Use with caution!
    """
    results = []
    for deployment in cleanup_scheduler.get_all_active_deployments():
        result = await cleanup_scheduler.cleanup_deployment(
            deployment["submission_id"],
            reason="manual_bulk"
        )
        results.append(result)

    return {
        "cleaned_up": len([r for r in results if r.get("success")]),
        "failed": len([r for r in results if not r.get("success")]),
        "results": results,
    }
