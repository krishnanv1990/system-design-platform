"""
GCP Assets API routes.
Provides access to deployed GCP resources for submissions.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from backend.database import get_db
from backend.models.submission import Submission
from backend.models.user import User
from backend.auth.jwt_handler import get_current_user
from backend.config import get_settings

settings = get_settings()

router = APIRouter()


class GCPAssetSummary(BaseModel):
    """Summary of GCP assets for a submission."""
    submission_id: int
    user_email: str
    status: str
    created_at: datetime

    # Cloud Run service details
    service_name: Optional[str] = None
    endpoint_url: Optional[str] = None
    region: str = "us-central1"

    # Container image
    container_image: Optional[str] = None

    # Resource links
    console_links: dict = {}

    # Generated code (if available)
    generated_code: Optional[str] = None

    class Config:
        from_attributes = True


class AdminAssetsSummary(BaseModel):
    """Summary of all GCP assets across all candidates."""
    total_submissions: int
    active_deployments: int
    total_cost_estimate: str
    assets: List[GCPAssetSummary]


def _build_console_links(project_id: str, region: str, service_name: str, submission_id: int) -> dict:
    """Build GCP Console links for a deployment."""
    return {
        "cloud_run_service": f"https://console.cloud.google.com/run/detail/{region}/{service_name}/metrics?project={project_id}",
        "cloud_run_logs": f"https://console.cloud.google.com/run/detail/{region}/{service_name}/logs?project={project_id}",
        "cloud_run_revisions": f"https://console.cloud.google.com/run/detail/{region}/{service_name}/revisions?project={project_id}",
        "cloud_build_history": f"https://console.cloud.google.com/cloud-build/builds?project={project_id}",
        "container_registry": f"https://console.cloud.google.com/artifacts/docker/{project_id}/{region}/sdp-repo?project={project_id}",
        "cloud_storage_source": f"https://console.cloud.google.com/storage/browser/{project_id}_cloudbuild/source?project={project_id}",
    }


def _get_asset_summary(submission: Submission, user_email: str) -> GCPAssetSummary:
    """Build GCP asset summary for a submission."""
    project_id = settings.gcp_project_id
    region = settings.gcp_region or "us-central1"

    service_name = submission.deployment_id
    endpoint_url = submission.endpoint_url

    # Get deployment info from validation_feedback
    validation_feedback = submission.validation_feedback or {}
    deployment_info = validation_feedback.get("deployment", {})

    if not endpoint_url:
        endpoint_url = deployment_info.get("endpoint_url")

    container_image = deployment_info.get("image")
    if not container_image and service_name:
        container_image = f"us-central1-docker.pkg.dev/{project_id}/sdp-repo/candidate-{submission.id}:latest"

    # Get generated code if available
    generated_code = deployment_info.get("generated_code") or validation_feedback.get("generated_code")

    # Build console links
    console_links = {}
    if service_name:
        console_links = _build_console_links(project_id, region, service_name, submission.id)

    return GCPAssetSummary(
        submission_id=submission.id,
        user_email=user_email,
        status=submission.status,
        created_at=submission.created_at,
        service_name=service_name,
        endpoint_url=endpoint_url,
        region=region,
        container_image=container_image,
        console_links=console_links,
        generated_code=generated_code,
    )


@router.get("/submission/{submission_id}", response_model=GCPAssetSummary)
async def get_submission_assets(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get GCP assets for a specific submission.
    Candidates can only view their own submissions.

    Returns Cloud Run service details, console links, and generated code.
    """
    # Verify submission belongs to user
    submission = db.query(Submission).filter(
        Submission.id == submission_id,
        Submission.user_id == current_user.id,
    ).first()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    return _get_asset_summary(submission, current_user.email)


@router.get("/submission/{submission_id}/code")
async def get_submission_code(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the full generated code for a submission.
    Fetches from GCS if available.
    """
    from google.cloud import storage

    # Verify submission belongs to user
    submission = db.query(Submission).filter(
        Submission.id == submission_id,
        Submission.user_id == current_user.id,
    ).first()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    # Try to get code from GCS
    try:
        project_id = settings.gcp_project_id
        storage_client = storage.Client(project=project_id)
        bucket_name = f"{project_id}_cloudbuild"
        bucket = storage_client.bucket(bucket_name)

        # Try to download the source tarball and extract main.py
        blob_name = f"source/submission_{submission.id}.tar.gz"
        blob = bucket.blob(blob_name)

        if blob.exists():
            import tarfile
            import io

            tar_bytes = blob.download_as_bytes()
            tar_buffer = io.BytesIO(tar_bytes)

            with tarfile.open(fileobj=tar_buffer, mode='r:gz') as tar:
                for member in tar.getmembers():
                    if member.name == "main.py":
                        f = tar.extractfile(member)
                        if f:
                            return {
                                "submission_id": submission_id,
                                "filename": "main.py",
                                "code": f.read().decode('utf-8'),
                                "source": "gcs",
                            }

        # Fallback to validation_feedback
        validation_feedback = submission.validation_feedback or {}
        code = validation_feedback.get("generated_code")
        if code:
            return {
                "submission_id": submission_id,
                "filename": "main.py",
                "code": code,
                "source": "validation_feedback",
                "truncated": True,
            }

        return {
            "submission_id": submission_id,
            "code": None,
            "error": "Code not available",
        }

    except Exception as e:
        # Fallback to validation_feedback
        validation_feedback = submission.validation_feedback or {}
        code = validation_feedback.get("generated_code")

        return {
            "submission_id": submission_id,
            "filename": "main.py",
            "code": code,
            "source": "validation_feedback",
            "truncated": True if code else False,
            "gcs_error": str(e),
        }


@router.get("/admin/all", response_model=AdminAssetsSummary)
async def get_all_assets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Admin endpoint: Get all GCP assets across all candidates.
    Only accessible by admin users.
    """
    # Check if user is admin using the is_admin field on the User model
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    # Get all submissions with deployments
    submissions = db.query(Submission).filter(
        Submission.deployment_id.isnot(None)
    ).order_by(Submission.created_at.desc()).all()

    # Build summaries
    assets = []
    active_count = 0

    for submission in submissions:
        # Get user email
        user = submission.user
        user_email = user.email if user else "unknown"

        summary = _get_asset_summary(submission, user_email)
        assets.append(summary)

        if submission.status in ["deploying", "testing", "completed"]:
            active_count += 1

    # Estimate cost (rough estimate based on Cloud Run pricing)
    # Free tier: 2 million requests, 360,000 GB-seconds of memory, 180,000 vCPU-seconds
    # Beyond free tier: ~$0.00002400 per vCPU-second, $0.00000250 per GB-second
    estimated_cost = f"${active_count * 0.50:.2f}/hour (estimate based on {active_count} active deployments)"

    return AdminAssetsSummary(
        total_submissions=len(submissions),
        active_deployments=active_count,
        total_cost_estimate=estimated_cost,
        assets=assets,
    )


@router.get("/admin/cleanup-candidates")
async def get_cleanup_candidates(
    hours_old: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Admin endpoint: Get list of deployments that are candidates for cleanup.
    Returns deployments older than specified hours.
    """
    from datetime import timedelta

    # Check if user is admin using the is_admin field on the User model
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    cutoff_time = datetime.utcnow() - timedelta(hours=hours_old)

    # Get old deployments
    old_submissions = db.query(Submission).filter(
        Submission.deployment_id.isnot(None),
        Submission.created_at < cutoff_time,
    ).order_by(Submission.created_at).all()

    cleanup_candidates = []
    for submission in old_submissions:
        user = submission.user
        cleanup_candidates.append({
            "submission_id": submission.id,
            "user_email": user.email if user else "unknown",
            "service_name": submission.deployment_id,
            "created_at": submission.created_at.isoformat(),
            "age_hours": (datetime.utcnow() - submission.created_at).total_seconds() / 3600,
            "status": submission.status,
        })

    return {
        "cutoff_hours": hours_old,
        "total_candidates": len(cleanup_candidates),
        "candidates": cleanup_candidates,
    }
