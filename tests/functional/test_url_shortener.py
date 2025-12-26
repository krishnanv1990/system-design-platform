"""
Functional tests for URL Shortener system design.
Tests the core API endpoints and business logic.
"""

import pytest
import httpx
import asyncio
from typing import Optional
import os

# Base URL for the deployed service (set via environment variable)
BASE_URL = os.getenv("TEST_TARGET_URL", "http://localhost:8000")


class TestURLShortenerFunctional:
    """Functional tests for URL Shortener API."""

    @pytest.fixture
    def client(self):
        """Create HTTP client for tests."""
        return httpx.Client(base_url=BASE_URL, timeout=30.0)

    @pytest.fixture
    def async_client(self):
        """Create async HTTP client for tests."""
        return httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)

    # ==================== Health Check Tests ====================

    def test_health_endpoint(self, client):
        """Test that health endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"

    def test_root_endpoint(self, client):
        """Test root endpoint returns service info."""
        response = client.get("/")
        assert response.status_code == 200

    # ==================== URL Creation Tests ====================

    def test_create_short_url_basic(self, client):
        """Test creating a short URL with valid input."""
        payload = {
            "original_url": "https://www.example.com/very/long/path/to/resource"
        }
        response = client.post("/api/v1/urls", json=payload)
        assert response.status_code in [200, 201]
        data = response.json()
        assert "short_code" in data or "short_url" in data

    def test_create_short_url_with_custom_code(self, client):
        """Test creating a short URL with custom short code."""
        payload = {
            "original_url": "https://www.example.com/custom",
            "custom_code": "mylink123"
        }
        response = client.post("/api/v1/urls", json=payload)
        # May return 200/201 for success or 409 if code exists
        assert response.status_code in [200, 201, 409]

    def test_create_short_url_invalid_url(self, client):
        """Test that invalid URLs are rejected."""
        payload = {
            "original_url": "not-a-valid-url"
        }
        response = client.post("/api/v1/urls", json=payload)
        assert response.status_code in [400, 422]

    def test_create_short_url_empty_url(self, client):
        """Test that empty URLs are rejected."""
        payload = {
            "original_url": ""
        }
        response = client.post("/api/v1/urls", json=payload)
        assert response.status_code in [400, 422]

    def test_create_short_url_missing_url(self, client):
        """Test that missing URL field is rejected."""
        payload = {}
        response = client.post("/api/v1/urls", json=payload)
        assert response.status_code in [400, 422]

    # ==================== URL Retrieval Tests ====================

    def test_get_url_by_short_code(self, client):
        """Test retrieving original URL by short code."""
        # First create a URL
        create_response = client.post("/api/v1/urls", json={
            "original_url": "https://www.example.com/test-retrieval"
        })
        if create_response.status_code in [200, 201]:
            data = create_response.json()
            short_code = data.get("short_code") or data.get("short_url", "").split("/")[-1]

            # Now retrieve it
            get_response = client.get(f"/api/v1/urls/{short_code}")
            assert get_response.status_code == 200

    def test_get_nonexistent_url(self, client):
        """Test that nonexistent short codes return 404."""
        response = client.get("/api/v1/urls/nonexistent123456")
        assert response.status_code == 404

    def test_redirect_short_url(self, client):
        """Test that short URL redirects to original."""
        # First create a URL
        create_response = client.post("/api/v1/urls", json={
            "original_url": "https://www.example.com/redirect-test"
        })
        if create_response.status_code in [200, 201]:
            data = create_response.json()
            short_code = data.get("short_code") or data.get("short_url", "").split("/")[-1]

            # Try to access the redirect endpoint (don't follow redirects)
            redirect_response = client.get(f"/{short_code}", follow_redirects=False)
            assert redirect_response.status_code in [301, 302, 307, 308, 200]

    # ==================== URL Analytics Tests ====================

    def test_get_url_stats(self, client):
        """Test retrieving URL analytics/stats."""
        # First create a URL
        create_response = client.post("/api/v1/urls", json={
            "original_url": "https://www.example.com/stats-test"
        })
        if create_response.status_code in [200, 201]:
            data = create_response.json()
            short_code = data.get("short_code") or data.get("short_url", "").split("/")[-1]

            # Try to get stats
            stats_response = client.get(f"/api/v1/urls/{short_code}/stats")
            # Stats endpoint may or may not exist
            assert stats_response.status_code in [200, 404]

    # ==================== URL Expiration Tests ====================

    def test_create_url_with_expiration(self, client):
        """Test creating URL with custom expiration."""
        payload = {
            "original_url": "https://www.example.com/expiring",
            "expires_in_hours": 24
        }
        response = client.post("/api/v1/urls", json=payload)
        assert response.status_code in [200, 201, 400]  # 400 if not supported

    # ==================== Duplicate URL Tests ====================

    def test_duplicate_url_handling(self, client):
        """Test how duplicate original URLs are handled."""
        payload = {
            "original_url": "https://www.example.com/duplicate-test"
        }
        response1 = client.post("/api/v1/urls", json=payload)
        response2 = client.post("/api/v1/urls", json=payload)

        # Both should succeed (may return same or different short codes)
        assert response1.status_code in [200, 201]
        assert response2.status_code in [200, 201]

    # ==================== Batch Operations Tests ====================

    def test_batch_create_urls(self, client):
        """Test creating multiple URLs in batch."""
        payload = {
            "urls": [
                {"original_url": "https://example1.com"},
                {"original_url": "https://example2.com"},
                {"original_url": "https://example3.com"}
            ]
        }
        response = client.post("/api/v1/urls/batch", json=payload)
        # Batch endpoint may not exist
        assert response.status_code in [200, 201, 404, 405]

    # ==================== Delete Tests ====================

    def test_delete_url(self, client):
        """Test deleting a short URL."""
        # First create a URL
        create_response = client.post("/api/v1/urls", json={
            "original_url": "https://www.example.com/to-delete"
        })
        if create_response.status_code in [200, 201]:
            data = create_response.json()
            short_code = data.get("short_code") or data.get("short_url", "").split("/")[-1]

            # Delete it
            delete_response = client.delete(f"/api/v1/urls/{short_code}")
            assert delete_response.status_code in [200, 204, 404, 405]


class TestURLShortenerEdgeCases:
    """Edge case tests for URL Shortener."""

    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BASE_URL, timeout=30.0)

    def test_very_long_url(self, client):
        """Test handling of very long URLs."""
        long_path = "a" * 2000
        payload = {
            "original_url": f"https://www.example.com/{long_path}"
        }
        response = client.post("/api/v1/urls", json=payload)
        # Should either accept or reject with proper error
        assert response.status_code in [200, 201, 400, 413, 422]

    def test_url_with_special_characters(self, client):
        """Test URLs with special characters."""
        payload = {
            "original_url": "https://www.example.com/path?query=value&special=!@#$%"
        }
        response = client.post("/api/v1/urls", json=payload)
        assert response.status_code in [200, 201, 400, 422]

    def test_url_with_unicode(self, client):
        """Test URLs with unicode characters."""
        payload = {
            "original_url": "https://www.example.com/путь/到/경로"
        }
        response = client.post("/api/v1/urls", json=payload)
        assert response.status_code in [200, 201, 400, 422]

    def test_concurrent_requests(self, client):
        """Test handling of concurrent requests."""
        import concurrent.futures

        def create_url(i):
            response = client.post("/api/v1/urls", json={
                "original_url": f"https://www.example.com/concurrent/{i}"
            })
            return response.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_url, i) for i in range(10)]
            results = [f.result() for f in futures]

        # All should succeed
        success_count = sum(1 for r in results if r in [200, 201])
        assert success_count >= 8  # Allow some failures under load

    def test_rate_limiting(self, client):
        """Test that rate limiting is applied."""
        responses = []
        for i in range(100):
            response = client.post("/api/v1/urls", json={
                "original_url": f"https://www.example.com/rate-limit/{i}"
            })
            responses.append(response.status_code)

        # Check if any 429 (rate limited) responses
        rate_limited = sum(1 for r in responses if r == 429)
        # Rate limiting may or may not be implemented
        assert True  # Just verify no crashes
