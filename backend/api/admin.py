"""
Admin API endpoints for platform management.
Provides access to warm pool status and other administrative functions.
"""

from fastapi import APIRouter, Depends, HTTPException

from backend.services.warm_pool_service import WarmPoolService

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
