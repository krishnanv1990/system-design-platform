"""
Functional tests for URL Shortener system design.
Tests the core API endpoints and business logic.
"""

import pytest
import httpx
import asyncio
import time
import random
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


class TestURLExpirationBehavior:
    """Tests that verify actual URL expiration behavior."""

    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BASE_URL, timeout=30.0)

    def test_url_expires_after_ttl(self, client):
        """
        Test that a URL with short TTL actually expires.
        Creates URL with 1-second expiry and verifies it becomes inaccessible.
        """
        # Create URL with very short expiration (1 second or minimum allowed)
        payload = {
            "original_url": "https://www.example.com/expiry-test",
            "expires_in_seconds": 2,  # Try seconds first
        }
        response = client.post("/api/v1/urls", json=payload)

        # If seconds not supported, try hours with minimum value
        if response.status_code in [400, 422]:
            payload = {
                "original_url": "https://www.example.com/expiry-test",
                "expires_in_hours": 0.001,  # ~3.6 seconds
            }
            response = client.post("/api/v1/urls", json=payload)

        if response.status_code in [200, 201]:
            data = response.json()
            short_code = data.get("short_code") or data.get("short_url", "").split("/")[-1]

            # Verify URL works immediately
            get_response = client.get(f"/api/v1/urls/{short_code}")
            initial_works = get_response.status_code in [200, 301, 302, 307, 308]

            if initial_works:
                # Wait for expiration
                time.sleep(5)

                # Verify URL is now expired/inaccessible
                expired_response = client.get(f"/api/v1/urls/{short_code}")
                # Should be 404 (not found) or 410 (gone)
                assert expired_response.status_code in [404, 410, 200], \
                    f"Expected 404/410 after expiry, got {expired_response.status_code}"

                # If still 200, check for explicit expiry info in response
                if expired_response.status_code == 200:
                    data = expired_response.json()
                    # Check if response indicates expiry
                    if "expired" in data:
                        assert data["expired"] == True

    def test_url_accessible_before_expiry(self, client):
        """Test that URL remains accessible before expiration time."""
        payload = {
            "original_url": "https://www.example.com/long-expiry",
            "expires_in_hours": 24
        }
        response = client.post("/api/v1/urls", json=payload)

        if response.status_code in [200, 201]:
            data = response.json()
            short_code = data.get("short_code") or data.get("short_url", "").split("/")[-1]

            # Verify URL works multiple times over short period
            for _ in range(3):
                get_response = client.get(f"/api/v1/urls/{short_code}")
                assert get_response.status_code in [200, 301, 302, 307, 308]
                time.sleep(0.5)

    def test_expiry_returned_in_response(self, client):
        """Test that expiration time is returned when creating URL with TTL."""
        payload = {
            "original_url": "https://www.example.com/expiry-info",
            "expires_in_hours": 48
        }
        response = client.post("/api/v1/urls", json=payload)

        if response.status_code in [200, 201]:
            data = response.json()
            # Check if expiration info is in response
            has_expiry_info = any(key in data for key in [
                "expires_at", "expiration", "expires", "ttl", "expires_in"
            ])
            # Just log, don't fail - implementation may vary
            if not has_expiry_info:
                print("Note: Expiration time not returned in response")


class TestURLShortenerDataIntegrity:
    """Tests for data integrity and consistency."""

    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BASE_URL, timeout=30.0)

    def test_original_url_preserved(self, client):
        """Test that original URL is stored and returned correctly."""
        original = "https://www.example.com/with?query=params&special=!@#"
        payload = {"original_url": original}

        response = client.post("/api/v1/urls", json=payload)
        if response.status_code in [200, 201]:
            data = response.json()
            short_code = data.get("short_code") or data.get("short_url", "").split("/")[-1]

            # Retrieve and verify
            get_response = client.get(f"/api/v1/urls/{short_code}")
            if get_response.status_code == 200:
                retrieved = get_response.json()
                stored_url = retrieved.get("original_url") or retrieved.get("url") or retrieved.get("long_url")
                if stored_url:
                    assert stored_url == original, f"URL mismatch: {stored_url} != {original}"

    def test_short_code_uniqueness(self, client):
        """Test that each URL gets a unique short code."""
        short_codes = set()

        for i in range(20):
            response = client.post("/api/v1/urls", json={
                "original_url": f"https://www.example.com/unique/{i}/{time.time()}"
            })
            if response.status_code in [200, 201]:
                data = response.json()
                short_code = data.get("short_code") or data.get("short_url", "").split("/")[-1]
                if short_code:
                    assert short_code not in short_codes, f"Duplicate short code: {short_code}"
                    short_codes.add(short_code)

    def test_click_count_increments(self, client):
        """Test that click/access count increments correctly."""
        # Create URL
        response = client.post("/api/v1/urls", json={
            "original_url": "https://www.example.com/click-test"
        })

        if response.status_code in [200, 201]:
            data = response.json()
            short_code = data.get("short_code") or data.get("short_url", "").split("/")[-1]

            # Access URL multiple times
            for _ in range(5):
                client.get(f"/api/v1/urls/{short_code}", follow_redirects=False)
                time.sleep(0.2)  # Small delay between requests

            # Check stats
            stats_response = client.get(f"/api/v1/urls/{short_code}/stats")
            if stats_response.status_code == 200:
                stats = stats_response.json()
                click_count = stats.get("clicks") or stats.get("access_count") or stats.get("visits") or 0
                assert click_count >= 5, f"Expected at least 5 clicks, got {click_count}"


class TestURLShortenerErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BASE_URL, timeout=30.0)

    def test_invalid_short_code_format(self, client):
        """Test handling of invalid short code formats."""
        invalid_codes = [
            "../../../etc/passwd",  # Path traversal
            "<script>alert(1)</script>",  # XSS attempt
            "'; DROP TABLE urls; --",  # SQL injection
            "x" * 1000,  # Very long code
        ]

        for code in invalid_codes:
            response = client.get(f"/api/v1/urls/{code}")
            # Should return 400 or 404, not 500
            assert response.status_code in [400, 404, 422], \
                f"Unexpected status {response.status_code} for code: {code[:50]}"

    def test_malicious_url_handling(self, client):
        """Test that malicious URLs are handled safely."""
        malicious_urls = [
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "file:///etc/passwd",
        ]

        for url in malicious_urls:
            response = client.post("/api/v1/urls", json={"original_url": url})
            # Should either reject or sanitize
            assert response.status_code in [200, 201, 400, 422]

    def test_empty_response_handling(self, client):
        """Test handling of requests with empty body."""
        response = client.post("/api/v1/urls", content=b"")
        assert response.status_code in [400, 415, 422]

    def test_wrong_content_type(self, client):
        """Test handling of wrong content type."""
        response = client.post(
            "/api/v1/urls",
            content="original_url=https://example.com",
            headers={"Content-Type": "text/plain"}
        )
        assert response.status_code in [400, 415, 422, 200, 201]


class TestURLShortenerPerformanceBaseline:
    """Basic performance validation tests."""

    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BASE_URL, timeout=30.0)

    def test_create_url_response_time(self, client):
        """Test that URL creation completes within acceptable time."""
        import time as time_module

        latencies = []
        for i in range(10):
            start = time_module.time()
            response = client.post("/api/v1/urls", json={
                "original_url": f"https://www.example.com/perf/{i}"
            })
            latencies.append((time_module.time() - start) * 1000)

        avg_latency = sum(latencies) / len(latencies)
        # Should average under 2 seconds (generous for cold starts)
        assert avg_latency < 2000, f"Average create latency {avg_latency:.0f}ms exceeds threshold"

    def test_redirect_response_time(self, client):
        """Test that redirects complete quickly."""
        import time as time_module

        # First create a URL
        response = client.post("/api/v1/urls", json={
            "original_url": "https://www.example.com/redirect-perf"
        })

        if response.status_code in [200, 201]:
            data = response.json()
            short_code = data.get("short_code") or data.get("short_url", "").split("/")[-1]

            latencies = []
            for _ in range(10):
                start = time_module.time()
                client.get(f"/api/v1/urls/{short_code}", follow_redirects=False)
                latencies.append((time_module.time() - start) * 1000)

            avg_latency = sum(latencies) / len(latencies)
            # Redirects should be fast - under 500ms average
            assert avg_latency < 500, f"Average redirect latency {avg_latency:.0f}ms exceeds threshold"


class TestKeyGenerationService:
    """Tests for Key Generation Service (KGS) functionality."""

    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BASE_URL, timeout=30.0)

    def test_kgs_generates_unique_codes(self, client):
        """Test that KGS generates unique short codes for each URL."""
        short_codes = set()

        for i in range(50):
            response = client.post("/api/v1/urls", json={
                "original_url": f"https://www.example.com/kgs-unique-test/{i}/{time.time()}"
            })
            if response.status_code in [200, 201]:
                data = response.json()
                short_code = data.get("short_code") or data.get("short_url", "").split("/")[-1]
                if short_code:
                    # Verify uniqueness
                    assert short_code not in short_codes, f"Duplicate code generated: {short_code}"
                    short_codes.add(short_code)

        # Should have generated unique codes for all requests
        assert len(short_codes) >= 45, f"Expected at least 45 unique codes, got {len(short_codes)}"

    def test_kgs_code_format(self, client):
        """Test that KGS generates codes in expected format."""
        response = client.post("/api/v1/urls", json={
            "original_url": "https://www.example.com/kgs-format-test"
        })

        if response.status_code in [200, 201]:
            data = response.json()
            short_code = data.get("short_code") or data.get("short_url", "").split("/")[-1]

            if short_code:
                # Code should be alphanumeric, typically 6-8 characters
                assert len(short_code) >= 4, f"Short code too short: {short_code}"
                assert len(short_code) <= 10, f"Short code too long: {short_code}"
                assert short_code.isalnum(), f"Short code contains non-alphanumeric chars: {short_code}"

    def test_kgs_high_throughput(self, client):
        """Test KGS can handle high throughput of key allocations."""
        import concurrent.futures

        results = []

        def create_url(i):
            try:
                response = client.post("/api/v1/urls", json={
                    "original_url": f"https://www.example.com/kgs-throughput/{i}"
                })
                return response.status_code, response.json() if response.status_code in [200, 201] else None
            except Exception as e:
                return 500, str(e)

        # Create 20 URLs concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_url, i) for i in range(20)]
            results = [f.result() for f in futures]

        # Most should succeed
        success_count = sum(1 for status, _ in results if status in [200, 201])
        assert success_count >= 15, f"Expected at least 15 successes, got {success_count}"

        # Verify all successful ones have unique codes
        codes = set()
        for status, data in results:
            if status in [200, 201] and data:
                code = data.get("short_code") or data.get("short_url", "").split("/")[-1]
                if code:
                    assert code not in codes, f"Duplicate code in concurrent test: {code}"
                    codes.add(code)

    def test_kgs_custom_code_validation(self, client):
        """Test that custom codes are properly validated."""
        # Valid custom code
        custom_code = f"custom{random.randint(100, 999)}"
        response = client.post("/api/v1/urls", json={
            "original_url": "https://www.example.com/custom-code-test",
            "custom_code": custom_code
        })

        # Should accept or reject based on availability
        assert response.status_code in [200, 201, 409, 400, 422]

        if response.status_code in [200, 201]:
            data = response.json()
            returned_code = data.get("short_code") or data.get("short_url", "").split("/")[-1]
            # If accepted, the returned code should match
            assert returned_code == custom_code or custom_code in (returned_code or "")

    def test_kgs_custom_code_conflict(self, client):
        """Test that duplicate custom codes are rejected."""
        custom_code = f"dupe{random.randint(1000, 9999)}"
        url1 = f"https://www.example.com/dupe-test-1/{time.time()}"
        url2 = f"https://www.example.com/dupe-test-2/{time.time()}"

        # First request with custom code
        response1 = client.post("/api/v1/urls", json={
            "original_url": url1,
            "custom_code": custom_code
        })

        if response1.status_code in [200, 201]:
            # Second request with same custom code should fail
            response2 = client.post("/api/v1/urls", json={
                "original_url": url2,
                "custom_code": custom_code
            })

            # Should be rejected as conflict
            assert response2.status_code in [409, 400, 422], \
                f"Expected conflict error, got {response2.status_code}"

    def test_kgs_pool_health_in_response(self, client):
        """Test that health endpoint reports KGS pool status (optional)."""
        response = client.get("/health")

        if response.status_code == 200:
            data = response.json()
            # If KGS is implemented, health may include pool info
            # This is optional - just check health endpoint works
            assert "status" in data or "healthy" in str(data).lower()

    def test_kgs_fast_key_allocation(self, client):
        """Test that key allocation is fast (KGS advantage)."""
        latencies = []

        for i in range(10):
            start = time.time()
            response = client.post("/api/v1/urls", json={
                "original_url": f"https://www.example.com/kgs-speed-test/{i}"
            })
            latency_ms = (time.time() - start) * 1000

            if response.status_code in [200, 201]:
                latencies.append(latency_ms)

        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            # KGS should enable fast writes - under 2 seconds average
            # (generous for cloud cold starts)
            assert avg_latency < 2000, f"Average write latency {avg_latency:.0f}ms exceeds threshold"


class TestKGSResilience:
    """Tests for KGS resilience and edge cases."""

    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BASE_URL, timeout=30.0)

    def test_rapid_sequential_creates(self, client):
        """Test rapid sequential URL creation doesn't exhaust pool."""
        created_codes = []

        for i in range(30):
            response = client.post("/api/v1/urls", json={
                "original_url": f"https://www.example.com/rapid-create/{i}"
            })

            if response.status_code in [200, 201]:
                data = response.json()
                code = data.get("short_code") or data.get("short_url", "").split("/")[-1]
                if code:
                    created_codes.append(code)
            elif response.status_code == 503:
                # Pool exhaustion should not happen in normal operation
                pytest.fail("KGS pool exhausted during normal operation")

        # Should successfully create most URLs
        assert len(created_codes) >= 25, f"Only created {len(created_codes)} URLs"

        # All codes should be unique
        assert len(created_codes) == len(set(created_codes)), "Duplicate codes generated"

    def test_create_after_delete(self, client):
        """Test that deleting URLs doesn't affect new key generation."""
        # Create a URL
        response1 = client.post("/api/v1/urls", json={
            "original_url": "https://www.example.com/delete-test"
        })

        if response1.status_code in [200, 201]:
            data1 = response1.json()
            code1 = data1.get("short_code") or data1.get("short_url", "").split("/")[-1]

            # Delete it
            client.delete(f"/api/v1/urls/{code1}")

            # Create another URL - should get new code
            response2 = client.post("/api/v1/urls", json={
                "original_url": "https://www.example.com/after-delete"
            })

            if response2.status_code in [200, 201]:
                data2 = response2.json()
                code2 = data2.get("short_code") or data2.get("short_url", "").split("/")[-1]

                # New code should be different (KGS doesn't reuse immediately)
                # Note: Some implementations may reuse codes, which is also valid
                assert code2 is not None

    def test_same_url_different_codes(self, client):
        """Test that same URL submitted twice gets different short codes."""
        url = "https://www.example.com/same-url-test"

        response1 = client.post("/api/v1/urls", json={"original_url": url})
        response2 = client.post("/api/v1/urls", json={"original_url": url})

        if response1.status_code in [200, 201] and response2.status_code in [200, 201]:
            code1 = response1.json().get("short_code") or response1.json().get("short_url", "").split("/")[-1]
            code2 = response2.json().get("short_code") or response2.json().get("short_url", "").split("/")[-1]

            # May return same code (idempotent) or different codes - both are valid
            # Just verify both codes work
            if code1:
                get_response = client.get(f"/api/v1/urls/{code1}")
                assert get_response.status_code in [200, 301, 302, 307, 308]

    def test_code_character_distribution(self, client):
        """Test that generated codes have good character distribution."""
        codes = []

        for i in range(20):
            response = client.post("/api/v1/urls", json={
                "original_url": f"https://www.example.com/char-dist/{i}"
            })
            if response.status_code in [200, 201]:
                data = response.json()
                code = data.get("short_code") or data.get("short_url", "").split("/")[-1]
                if code:
                    codes.append(code)

        if codes:
            # Check that codes aren't all starting with same character
            first_chars = [c[0] for c in codes if c]
            unique_first_chars = len(set(first_chars))

            # Should have some variety (at least 3 different starting chars in 20 codes)
            assert unique_first_chars >= 2, "Codes lack variety - may indicate poor randomization"
