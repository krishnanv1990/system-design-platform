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
from backend.api.user import require_admin

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
    admin_user: User = Depends(require_admin),
):
    """
    Admin endpoint: Get all GCP assets across all candidates.
    Only accessible by admin users (requires is_admin flag AND email in whitelist).
    """

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
    admin_user: User = Depends(require_admin),
):
    """
    Admin endpoint: Get list of deployments that are candidates for cleanup.
    Returns deployments older than specified hours.
    Only accessible by admin users (requires is_admin flag AND email in whitelist).
    """
    from datetime import timedelta

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


class DistributedSubmissionAsset(BaseModel):
    """Asset info for a distributed submission."""
    submission_id: int
    problem_id: int
    language: str
    status: str
    created_at: datetime
    cluster_node_urls: List[str]
    build_artifact_url: Optional[str] = None
    console_links: dict = {}


class UserGCPResources(BaseModel):
    """Summary of a user's GCP resources."""
    user_id: int
    user_email: str
    active_cloud_run_services: int
    total_cluster_nodes: int
    distributed_submissions: List[DistributedSubmissionAsset]


def _get_distributed_submission_asset(submission: Submission, project_id: str, region: str) -> DistributedSubmissionAsset:
    """Build asset info for a distributed submission."""
    cluster_urls = submission.cluster_node_urls or []

    console_links = {}
    if cluster_urls:
        # Extract service names from Cloud Run URLs
        service_names = []
        for url in cluster_urls:
            # URL format: https://service-name-xxx.region.run.app
            if "run.app" in url:
                parts = url.replace("https://", "").split(".")
                if parts:
                    service_name = parts[0]
                    # Remove the random suffix to get base name
                    service_names.append(service_name)

        console_links = {
            "cloud_run_services": f"https://console.cloud.google.com/run?project={project_id}",
            "cloud_build_history": f"https://console.cloud.google.com/cloud-build/builds?project={project_id}",
            "artifact_registry": f"https://console.cloud.google.com/artifacts/docker/{project_id}/{region}/sdp-repo?project={project_id}",
        }

    return DistributedSubmissionAsset(
        submission_id=submission.id,
        problem_id=submission.problem_id,
        language=submission.language or "unknown",
        status=submission.status,
        created_at=submission.created_at,
        cluster_node_urls=cluster_urls,
        build_artifact_url=submission.build_artifact_url,
        console_links=console_links,
    )


@router.get("/user/gcp-resources", response_model=UserGCPResources)
async def get_user_gcp_resources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the current user's GCP resources.
    Shows active Cloud Run services and cluster deployments.
    """
    project_id = settings.gcp_project_id
    region = settings.gcp_region or "us-central1"

    # Get all distributed submissions with active clusters
    submissions = db.query(Submission).filter(
        Submission.user_id == current_user.id,
        Submission.submission_type == "distributed_consensus",
    ).order_by(Submission.created_at.desc()).all()

    distributed_assets = []
    total_nodes = 0
    active_services = 0

    for submission in submissions:
        asset = _get_distributed_submission_asset(submission, project_id, region)
        distributed_assets.append(asset)

        if submission.cluster_node_urls:
            total_nodes += len(submission.cluster_node_urls)
            active_services += len(submission.cluster_node_urls)

    return UserGCPResources(
        user_id=current_user.id,
        user_email=current_user.email,
        active_cloud_run_services=active_services,
        total_cluster_nodes=total_nodes,
        distributed_submissions=distributed_assets,
    )


class AdminGCPResources(BaseModel):
    """Admin view of all GCP resources."""
    total_users: int
    total_active_services: int
    total_cluster_nodes: int
    resources_by_user: List[UserGCPResources]


@router.get("/admin/gcp-resources", response_model=AdminGCPResources)
async def get_admin_gcp_resources(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Admin endpoint: Get all GCP resources across all users.
    Shows active Cloud Run services and cluster deployments.
    """
    project_id = settings.gcp_project_id
    region = settings.gcp_region or "us-central1"

    # Get all distributed submissions with active clusters
    submissions = db.query(Submission).filter(
        Submission.submission_type == "distributed_consensus",
    ).order_by(Submission.created_at.desc()).all()

    # Group by user
    users_data: dict = {}
    for submission in submissions:
        user_id = submission.user_id
        if user_id not in users_data:
            user = submission.user
            users_data[user_id] = {
                "user_id": user_id,
                "user_email": user.email if user else "unknown",
                "distributed_submissions": [],
                "active_services": 0,
                "total_nodes": 0,
            }

        asset = _get_distributed_submission_asset(submission, project_id, region)
        users_data[user_id]["distributed_submissions"].append(asset)

        if submission.cluster_node_urls:
            users_data[user_id]["total_nodes"] += len(submission.cluster_node_urls)
            users_data[user_id]["active_services"] += len(submission.cluster_node_urls)

    # Build response
    resources_by_user = []
    total_services = 0
    total_nodes = 0

    for data in users_data.values():
        resources_by_user.append(UserGCPResources(
            user_id=data["user_id"],
            user_email=data["user_email"],
            active_cloud_run_services=data["active_services"],
            total_cluster_nodes=data["total_nodes"],
            distributed_submissions=data["distributed_submissions"],
        ))
        total_services += data["active_services"]
        total_nodes += data["total_nodes"]

    return AdminGCPResources(
        total_users=len(users_data),
        total_active_services=total_services,
        total_cluster_nodes=total_nodes,
        resources_by_user=resources_by_user,
    )


class StorageInfo(BaseModel):
    """Storage information for container images."""
    total_size_bytes: int
    total_size_formatted: str
    images: List[dict]
    artifact_registry_url: str


def _format_bytes(size_bytes: int) -> str:
    """Format bytes to human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


@router.get("/storage", response_model=StorageInfo)
async def get_storage_info(
    current_user: User = Depends(get_current_user),
):
    """
    Get storage footprint for container images in Artifact Registry.
    Shows total size and individual image sizes.
    """
    from google.cloud import artifactregistry_v1

    project_id = settings.gcp_project_id
    region = settings.gcp_region or "us-central1"

    images = []
    total_size = 0

    try:
        client = artifactregistry_v1.ArtifactRegistryClient()

        # List all docker images in the repository
        parent = f"projects/{project_id}/locations/{region}/repositories/sdp-repo"

        # List docker images
        request = artifactregistry_v1.ListDockerImagesRequest(parent=parent)

        for image in client.list_docker_images(request=request):
            size = image.image_size_bytes or 0
            total_size += size

            # Extract image name from URI
            # Format: us-central1-docker.pkg.dev/project/repo/image@sha256:...
            name = image.uri.split("/")[-1].split("@")[0] if "/" in image.uri else image.uri

            images.append({
                "name": name,
                "uri": image.uri,
                "size_bytes": size,
                "size_formatted": _format_bytes(size),
                "upload_time": image.upload_time.isoformat() if image.upload_time else None,
                "media_type": image.media_type,
            })

    except Exception as e:
        # Return empty if Artifact Registry is not accessible
        print(f"Error fetching storage info: {e}")

    artifact_registry_url = f"https://console.cloud.google.com/artifacts/docker/{project_id}/{region}/sdp-repo?project={project_id}"

    return StorageInfo(
        total_size_bytes=total_size,
        total_size_formatted=_format_bytes(total_size),
        images=images,
        artifact_registry_url=artifact_registry_url,
    )


@router.get("/admin/storage", response_model=StorageInfo)
async def get_admin_storage_info(
    admin_user: User = Depends(require_admin),
):
    """
    Admin endpoint: Get storage footprint for all container images.
    """
    from google.cloud import artifactregistry_v1

    project_id = settings.gcp_project_id
    region = settings.gcp_region or "us-central1"

    images = []
    total_size = 0

    try:
        client = artifactregistry_v1.ArtifactRegistryClient()

        # List all docker images in the repository
        parent = f"projects/{project_id}/locations/{region}/repositories/sdp-repo"

        request = artifactregistry_v1.ListDockerImagesRequest(parent=parent)

        for image in client.list_docker_images(request=request):
            size = image.image_size_bytes or 0
            total_size += size

            name = image.uri.split("/")[-1].split("@")[0] if "/" in image.uri else image.uri

            images.append({
                "name": name,
                "uri": image.uri,
                "size_bytes": size,
                "size_formatted": _format_bytes(size),
                "upload_time": image.upload_time.isoformat() if image.upload_time else None,
                "media_type": image.media_type,
                "tags": list(image.tags) if image.tags else [],
            })

    except Exception as e:
        print(f"Error fetching admin storage info: {e}")

    artifact_registry_url = f"https://console.cloud.google.com/artifacts/docker/{project_id}/{region}/sdp-repo?project={project_id}"

    return StorageInfo(
        total_size_bytes=total_size,
        total_size_formatted=_format_bytes(total_size),
        images=images,
        artifact_registry_url=artifact_registry_url,
    )
