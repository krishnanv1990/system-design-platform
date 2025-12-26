"""
GCP service for cloud resource management.
Provides direct API access for resource queries and management.
"""

import os
from typing import Optional, Dict, Any, List
from google.cloud import storage
from google.cloud import resourcemanager_v3
from google.auth import default as google_default
from google.auth.exceptions import DefaultCredentialsError

from backend.config import get_settings

settings = get_settings()


class GCPService:
    """
    Service for interacting with Google Cloud Platform.
    Handles resource management and status queries.
    """

    def __init__(self):
        """Initialize GCP clients."""
        self._credentials = None
        self._storage_client = None
        self._resource_manager_client = None

    @property
    def credentials(self):
        """Lazy load GCP credentials."""
        if self._credentials is None:
            try:
                # Try to load from file if path specified
                if settings.gcp_credentials_path and os.path.exists(settings.gcp_credentials_path):
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.gcp_credentials_path

                self._credentials, _ = google_default()
            except DefaultCredentialsError:
                # Return None if no credentials available (for development)
                pass
        return self._credentials

    @property
    def storage_client(self):
        """Lazy load Storage client."""
        if self._storage_client is None and self.credentials:
            self._storage_client = storage.Client(
                project=settings.gcp_project_id,
                credentials=self.credentials,
            )
        return self._storage_client

    def is_configured(self) -> bool:
        """
        Check if GCP is properly configured.

        Returns:
            True if GCP credentials are available
        """
        return self.credentials is not None

    def get_project_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the configured GCP project.

        Returns:
            Project information or None if not available
        """
        if not self.is_configured():
            return None

        try:
            client = resourcemanager_v3.ProjectsClient(credentials=self.credentials)
            project = client.get_project(name=f"projects/{settings.gcp_project_id}")
            return {
                "name": project.name,
                "project_id": project.project_id,
                "display_name": project.display_name,
                "state": str(project.state),
            }
        except Exception as e:
            return {"error": str(e)}

    def list_buckets(self, prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List storage buckets, optionally filtered by prefix.

        Args:
            prefix: Optional prefix to filter bucket names

        Returns:
            List of bucket information
        """
        if not self.storage_client:
            return []

        buckets = []
        for bucket in self.storage_client.list_buckets():
            if prefix and not bucket.name.startswith(prefix):
                continue
            buckets.append({
                "name": bucket.name,
                "location": bucket.location,
                "storage_class": bucket.storage_class,
                "created": bucket.time_created.isoformat() if bucket.time_created else None,
            })
        return buckets

    def create_bucket(
        self,
        name: str,
        location: str = None,
    ) -> Dict[str, Any]:
        """
        Create a new storage bucket.

        Args:
            name: Bucket name
            location: Bucket location (defaults to project region)

        Returns:
            Created bucket information or error
        """
        if not self.storage_client:
            return {"error": "GCP not configured"}

        try:
            bucket = self.storage_client.create_bucket(
                name,
                location=location or settings.gcp_region,
            )
            return {
                "name": bucket.name,
                "location": bucket.location,
                "created": True,
            }
        except Exception as e:
            return {"error": str(e)}

    def delete_bucket(self, name: str, force: bool = False) -> Dict[str, Any]:
        """
        Delete a storage bucket.

        Args:
            name: Bucket name
            force: If True, delete all objects first

        Returns:
            Deletion result
        """
        if not self.storage_client:
            return {"error": "GCP not configured"}

        try:
            bucket = self.storage_client.bucket(name)

            if force:
                # Delete all objects first
                blobs = list(bucket.list_blobs())
                for blob in blobs:
                    blob.delete()

            bucket.delete()
            return {"deleted": True}
        except Exception as e:
            return {"error": str(e)}

    def get_resource_labels(self, namespace: str) -> Dict[str, str]:
        """
        Generate standard labels for resources in a namespace.

        Args:
            namespace: Resource namespace

        Returns:
            Dictionary of labels
        """
        return {
            "managed-by": "system-design-platform",
            "namespace": namespace,
            "environment": "candidate-test",
        }

    def cleanup_namespace_resources(self, namespace: str) -> Dict[str, Any]:
        """
        Clean up all resources in a namespace.
        This is a placeholder - actual implementation would query and delete
        all resources with the namespace label.

        Args:
            namespace: Namespace to clean up

        Returns:
            Cleanup result
        """
        results = {
            "namespace": namespace,
            "buckets_deleted": 0,
            "errors": [],
        }

        # Clean up storage buckets
        if self.storage_client:
            for bucket in self.storage_client.list_buckets():
                if bucket.labels.get("namespace") == namespace:
                    try:
                        self.delete_bucket(bucket.name, force=True)
                        results["buckets_deleted"] += 1
                    except Exception as e:
                        results["errors"].append(f"Failed to delete bucket {bucket.name}: {e}")

        # TODO: Add cleanup for other resource types:
        # - Cloud Run services
        # - Cloud SQL instances
        # - Pub/Sub topics
        # - etc.

        return results
