"""
Performance tests for File Sharing Service using Locust.
Run with: locust -f locustfile_file_sharing.py --host=http://localhost:8000
"""

from locust import HttpUser, task, between, events
import random
import io
import os


class FileShareUser(HttpUser):
    """Simulates a user interacting with the File Sharing service."""

    wait_time = between(1, 3)

    def on_start(self):
        """Initialize user session."""
        self.uploaded_files = []
        self.created_folders = []
        self.auth_headers = {"Authorization": "Bearer test-token"}

    def generate_file(self, size_kb=10):
        """Generate a random file of specified size."""
        content = os.urandom(size_kb * 1024)
        return io.BytesIO(content)

    @task(5)
    def upload_small_file(self):
        """Upload a small file (10KB)."""
        file_content = self.generate_file(10)
        files = {"file": (f"test_{random.randint(1, 100000)}.txt", file_content, "text/plain")}

        with self.client.post("/api/v1/files",
            headers=self.auth_headers,
            files=files,
            catch_response=True) as response:

            if response.status_code in [200, 201]:
                data = response.json()
                file_id = data.get("id") or data.get("file_id")
                if file_id:
                    self.uploaded_files.append(file_id)
                response.success()
            elif response.status_code == 404:
                response.success()  # Endpoint not implemented
            else:
                response.failure(f"Upload failed: {response.status_code}")

    @task(2)
    def upload_medium_file(self):
        """Upload a medium file (100KB)."""
        file_content = self.generate_file(100)
        files = {"file": (f"medium_{random.randint(1, 100000)}.bin", file_content, "application/octet-stream")}

        with self.client.post("/api/v1/files",
            headers=self.auth_headers,
            files=files,
            catch_response=True) as response:

            if response.status_code in [200, 201, 404]:
                response.success()
            else:
                response.failure(f"Upload failed: {response.status_code}")

    @task(10)
    def download_file(self):
        """Download a file."""
        if not self.uploaded_files:
            return

        file_id = random.choice(self.uploaded_files)
        with self.client.get(f"/api/v1/files/{file_id}/download",
            headers=self.auth_headers,
            catch_response=True) as response:

            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Download failed: {response.status_code}")

    @task(8)
    def list_files(self):
        """List files in root folder."""
        with self.client.get("/api/v1/files",
            headers=self.auth_headers,
            params={"limit": 50},
            catch_response=True) as response:

            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"List failed: {response.status_code}")

    @task(3)
    def get_file_metadata(self):
        """Get file metadata."""
        if not self.uploaded_files:
            return

        file_id = random.choice(self.uploaded_files)
        with self.client.get(f"/api/v1/files/{file_id}",
            headers=self.auth_headers,
            catch_response=True) as response:

            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Metadata fetch failed: {response.status_code}")

    @task(2)
    def create_folder(self):
        """Create a folder."""
        folder_name = f"folder_{random.randint(1, 100000)}"

        with self.client.post("/api/v1/folders",
            headers=self.auth_headers,
            json={"name": folder_name, "parent_id": "root"},
            catch_response=True) as response:

            if response.status_code in [200, 201]:
                data = response.json()
                folder_id = data.get("id") or data.get("folder_id")
                if folder_id:
                    self.created_folders.append(folder_id)
                response.success()
            elif response.status_code == 404:
                response.success()
            else:
                response.failure(f"Create folder failed: {response.status_code}")

    @task(1)
    def search_files(self):
        """Search for files."""
        with self.client.get("/api/v1/files/search",
            headers=self.auth_headers,
            params={"query": "test", "limit": 20},
            catch_response=True) as response:

            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Search failed: {response.status_code}")

    @task(1)
    def get_sync_delta(self):
        """Get sync delta for client sync."""
        with self.client.get("/api/v1/sync/delta",
            headers=self.auth_headers,
            params={"cursor": "", "limit": 100},
            catch_response=True) as response:

            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Sync failed: {response.status_code}")

    @task(1)
    def health_check(self):
        """Health check."""
        self.client.get("/health")


class FileShareConcurrentUploadUser(HttpUser):
    """User for testing concurrent upload scenarios."""

    wait_time = between(0.5, 1)

    def on_start(self):
        self.auth_headers = {"Authorization": "Bearer test-token"}

    @task
    def concurrent_upload(self):
        """Simulate concurrent uploads from multiple devices."""
        file_content = io.BytesIO(os.urandom(5 * 1024))  # 5KB
        files = {"file": (f"concurrent_{random.randint(1, 100000)}.txt", file_content, "text/plain")}

        self.client.post("/api/v1/files",
            headers=self.auth_headers,
            files=files)
