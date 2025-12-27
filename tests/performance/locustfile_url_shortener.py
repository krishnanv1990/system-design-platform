"""
Performance tests for URL Shortener using Locust.
Simulates real-world workload patterns for a URL shortener service.

Real-world URL shortener characteristics:
- Read-heavy: 100:1 read/write ratio (most traffic is redirects)
- Bursty: Popular URLs can get viral traffic spikes
- Geographic distribution: Users from different regions
- Different user types: API users, web users, analytics users

Run with: locust -f locustfile_url_shortener.py --host=http://localhost:8000 -u 50 -r 5 -t 60s
"""

from locust import HttpUser, task, between, constant_pacing, events
import random
import string
import time


class URLShortenerReadUser(HttpUser):
    """
    Simulates typical end-users clicking on short links.
    This is the most common user type - represents 90% of traffic.
    """

    weight = 90  # 90% of simulated users
    wait_time = between(0.1, 1)  # Fast clicks, some pause

    # Shared pool of URLs across all users (simulates popular URLs)
    shared_urls = []

    def on_start(self):
        """Pre-create some URLs to click on."""
        # Create a few URLs for this user to click
        for _ in range(3):
            url = f"https://example.com/article/{random.randint(1, 1000000)}"
            try:
                response = self.client.post("/api/v1/urls",
                    json={"original_url": url},
                    timeout=10)
                if response.status_code in [200, 201]:
                    data = response.json()
                    short_code = data.get("short_code")
                    if short_code:
                        URLShortenerReadUser.shared_urls.append(short_code)
            except Exception:
                pass

    @task(100)
    def click_short_url(self):
        """
        Click on a short URL to get redirected.
        This is the primary operation - represents 95%+ of real traffic.
        """
        if not URLShortenerReadUser.shared_urls:
            return

        short_code = random.choice(URLShortenerReadUser.shared_urls)
        with self.client.get(f"/{short_code}",
            catch_response=True,
            allow_redirects=False,
            name="/[short_code] (redirect)") as response:

            if response.status_code in [200, 301, 302, 307, 308]:
                response.success()
            elif response.status_code == 404:
                # URL expired or deleted - still valid scenario
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(5)
    def get_url_info(self):
        """
        Get URL information (used by preview/unfurl services).
        """
        if not URLShortenerReadUser.shared_urls:
            return

        short_code = random.choice(URLShortenerReadUser.shared_urls)
        with self.client.get(f"/api/v1/urls/{short_code}",
            catch_response=True,
            name="/api/v1/urls/[code]") as response:

            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")


class URLShortenerWriteUser(HttpUser):
    """
    Simulates users creating short URLs.
    Represents about 8% of traffic (100:1 read/write ratio).
    """

    weight = 8  # 8% of simulated users
    wait_time = between(1, 5)  # Slower, more deliberate actions

    def on_start(self):
        """Initialize user session."""
        self.created_urls = []
        self.base_urls = [
            "https://www.google.com/search?q=",
            "https://www.github.com/user/repo/",
            "https://www.youtube.com/watch?v=",
            "https://www.medium.com/@author/",
            "https://docs.example.com/guide/",
            "https://api.service.com/v1/",
            "https://blog.company.com/post/",
            "https://shop.store.com/product/",
        ]

    @task(10)
    def create_short_url(self):
        """Create a new short URL."""
        base = random.choice(self.base_urls)
        url = f"{base}{random.randint(1, 10000000)}"

        with self.client.post("/api/v1/urls",
            json={"original_url": url},
            catch_response=True,
            name="/api/v1/urls (create)") as response:

            if response.status_code in [200, 201]:
                data = response.json()
                short_code = data.get("short_code")
                if short_code:
                    self.created_urls.append(short_code)
                    # Also add to shared pool for read users
                    URLShortenerReadUser.shared_urls.append(short_code)
                response.success()
            elif response.status_code in [400, 422]:
                # Validation error - still a valid test
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def create_with_expiry(self):
        """Create a URL with expiration."""
        url = f"https://temp.example.com/{random.randint(1, 1000000)}"

        with self.client.post("/api/v1/urls",
            json={
                "original_url": url,
                "expires_in_hours": random.choice([1, 24, 168])  # 1h, 1d, 1w
            },
            catch_response=True,
            name="/api/v1/urls (create with expiry)") as response:

            if response.status_code in [200, 201, 400, 422]:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def create_custom_url(self):
        """Create URL with custom short code."""
        custom_code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        url = f"https://custom.example.com/{random.randint(1, 1000000)}"

        with self.client.post("/api/v1/urls",
            json={
                "original_url": url,
                "custom_code": custom_code
            },
            catch_response=True,
            name="/api/v1/urls (custom code)") as response:

            if response.status_code in [200, 201, 409]:  # 409 = code already exists
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")


class URLShortenerAnalyticsUser(HttpUser):
    """
    Simulates analytics/monitoring users checking URL stats.
    Represents about 2% of traffic.
    """

    weight = 2  # 2% of simulated users
    wait_time = between(2, 10)  # Slower, periodic checks

    @task(5)
    def get_url_stats(self):
        """Get click statistics for a URL."""
        if not URLShortenerReadUser.shared_urls:
            return

        short_code = random.choice(URLShortenerReadUser.shared_urls)
        with self.client.get(f"/api/v1/urls/{short_code}/stats",
            catch_response=True,
            name="/api/v1/urls/[code]/stats") as response:

            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def health_check(self):
        """Check service health (monitoring system)."""
        with self.client.get("/health",
            catch_response=True) as response:

            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")


# Event hooks for custom metrics
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Log slow requests for analysis."""
    if response_time > 2000:  # > 2 seconds
        print(f"SLOW REQUEST: {name} took {response_time}ms")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Initialize shared state at test start."""
    URLShortenerReadUser.shared_urls = []
    print("Performance test started - simulating real-world URL shortener traffic")
    print("Traffic distribution: 90% reads, 8% writes, 2% analytics")
    print("Expected read:write ratio: ~100:1")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Report final statistics."""
    total_urls = len(URLShortenerReadUser.shared_urls)
    print(f"\nTest completed. Total URLs created: {total_urls}")
