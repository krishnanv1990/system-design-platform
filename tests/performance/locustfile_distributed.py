"""
Distributed Performance Tests for URL Shortener at Scale.

This test simulates real-world load patterns for a URL shortener serving:
- 1 million concurrent users
- 1 billion total URLs
- Peak traffic patterns

Run distributed mode:
  Master: locust -f locustfile_distributed.py --master --host=http://target:8000
  Worker: locust -f locustfile_distributed.py --worker --master-host=<master-ip>

Or use Kubernetes:
  kubectl apply -f locust-deployment.yaml
"""

from locust import HttpUser, task, between, events, LoadTestShape
from locust.runners import MasterRunner, WorkerRunner
import random
import string
import time
import os
import json
from datetime import datetime
from typing import List


# Configuration from environment
TARGET_RPS = int(os.getenv("TARGET_RPS", "100000"))  # Requests per second target
TOTAL_URLS = int(os.getenv("TOTAL_URLS", "1000000000"))  # 1 billion
CONCURRENT_USERS = int(os.getenv("CONCURRENT_USERS", "1000000"))  # 1 million

# Realistic URL distribution (Zipf-like)
POPULAR_URL_PERCENTAGE = 0.001  # 0.1% of URLs get 80% of traffic
POPULAR_URL_ACCESS_RATIO = 0.80

# Pre-populated short codes for read tests (in real scenario, load from file/DB)
PRELOADED_CODES: List[str] = []


class URLShortenerScaleUser(HttpUser):
    """
    Simulates realistic user behavior at scale.

    Traffic patterns:
    - 80% reads (accessing short URLs)
    - 15% creates (new URL shortening)
    - 5% analytics (checking stats)
    """

    wait_time = between(0.1, 0.5)  # Fast users for high RPS

    # Track created URLs per user for realistic access patterns
    created_urls: List[str] = []

    def on_start(self):
        """Initialize user session."""
        self.created_urls = []
        self.test_domains = [
            "https://www.google.com/search",
            "https://www.amazon.com/dp",
            "https://www.github.com/repo",
            "https://www.medium.com/article",
            "https://www.youtube.com/watch",
            "https://www.twitter.com/status",
            "https://www.linkedin.com/post",
            "https://www.reddit.com/r",
            "https://www.stackoverflow.com/q",
            "https://www.wikipedia.org/wiki",
        ]

    def _generate_random_url(self) -> str:
        """Generate a realistic random URL."""
        domain = random.choice(self.test_domains)
        path = ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))
        query = f"?id={random.randint(1, 10000000)}&ref={random.randint(1, 1000)}"
        return f"{domain}/{path}{query}"

    @task(80)
    def access_short_url(self):
        """
        Access/redirect a short URL - highest frequency task (80%).

        Simulates the read-heavy nature of URL shorteners where
        most traffic is redirect requests.
        """
        short_code = None

        # Decide whether to access popular URL or random URL
        if PRELOADED_CODES and random.random() < POPULAR_URL_ACCESS_RATIO:
            # Access from preloaded popular URLs (Zipf distribution)
            idx = min(int(random.paretovariate(1.16)), len(PRELOADED_CODES) - 1)
            short_code = PRELOADED_CODES[idx]
        elif self.created_urls:
            short_code = random.choice(self.created_urls)

        if short_code:
            with self.client.get(
                f"/api/v1/urls/{short_code}",
                catch_response=True,
                allow_redirects=False,
                name="/api/v1/urls/[short_code]"
            ) as response:
                if response.status_code in [200, 301, 302, 307, 308]:
                    response.success()
                elif response.status_code == 404:
                    # URL might have expired
                    if short_code in self.created_urls:
                        self.created_urls.remove(short_code)
                    response.success()
                else:
                    response.failure(f"Unexpected: {response.status_code}")

    @task(15)
    def create_short_url(self):
        """
        Create a new short URL (15% of traffic).

        Represents users actively shortening URLs.
        """
        url = self._generate_random_url()

        with self.client.post(
            "/api/v1/urls",
            json={"original_url": url},
            catch_response=True,
            name="POST /api/v1/urls"
        ) as response:
            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                    short_code = data.get("short_code") or data.get("id")
                    if short_code:
                        self.created_urls.append(short_code)
                        # Keep list manageable
                        if len(self.created_urls) > 100:
                            self.created_urls.pop(0)
                    response.success()
                except Exception:
                    response.success()  # Still succeeded
            elif response.status_code == 429:
                response.success()  # Rate limited is expected under load
            else:
                response.failure(f"Unexpected: {response.status_code}")

    @task(5)
    def get_url_stats(self):
        """
        Get URL analytics (5% of traffic).

        Represents users checking their URL performance.
        """
        if not self.created_urls:
            return

        short_code = random.choice(self.created_urls)

        with self.client.get(
            f"/api/v1/urls/{short_code}/stats",
            catch_response=True,
            name="/api/v1/urls/[short_code]/stats"
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Unexpected: {response.status_code}")


class URLShortenerBurstUser(HttpUser):
    """
    Simulates burst traffic patterns.

    Represents viral content scenarios where a single URL
    gets millions of requests in a short time.
    """

    wait_time = between(0.01, 0.1)  # Very fast
    weight = 1  # Lower weight than normal users

    def on_start(self):
        self.viral_codes = os.getenv("VIRAL_CODES", "").split(",")

    @task
    def access_viral_url(self):
        """Hammer a viral URL."""
        if not self.viral_codes or not self.viral_codes[0]:
            return

        short_code = random.choice(self.viral_codes)

        with self.client.get(
            f"/api/v1/urls/{short_code}",
            catch_response=True,
            allow_redirects=False,
            name="/api/v1/urls/[viral]"
        ) as response:
            if response.status_code in [200, 301, 302, 307, 308, 404, 429]:
                response.success()
            else:
                response.failure(f"Unexpected: {response.status_code}")


class StagesLoadShape(LoadTestShape):
    """
    Custom load shape simulating real-world traffic patterns.

    Stages:
    1. Warm-up: Gradually increase to 10% load
    2. Normal: Sustain 50% load
    3. Peak: Spike to 100% load (simulating peak hours)
    4. Sustained Peak: Hold peak for testing
    5. Cool-down: Gradually decrease
    """

    stages = [
        # (duration_seconds, users, spawn_rate)
        {"duration": 60, "users": CONCURRENT_USERS // 10, "spawn_rate": 1000},      # Warm-up
        {"duration": 300, "users": CONCURRENT_USERS // 2, "spawn_rate": 5000},      # Normal load
        {"duration": 120, "users": CONCURRENT_USERS, "spawn_rate": 10000},          # Ramp to peak
        {"duration": 600, "users": CONCURRENT_USERS, "spawn_rate": 10000},          # Sustained peak
        {"duration": 120, "users": CONCURRENT_USERS // 2, "spawn_rate": 5000},      # Cool down
        {"duration": 60, "users": CONCURRENT_USERS // 10, "spawn_rate": 1000},      # End
    ]

    def tick(self):
        run_time = self.get_run_time()

        cumulative_time = 0
        for stage in self.stages:
            cumulative_time += stage["duration"]
            if run_time < cumulative_time:
                return (stage["users"], stage["spawn_rate"])

        return None  # Stop the test


# Event handlers for distributed testing

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Initialize test environment."""
    if isinstance(environment.runner, MasterRunner):
        print(f"Master node starting - Target: {TARGET_RPS} RPS")
        print(f"Concurrent users: {CONCURRENT_USERS:,}")
        print(f"Simulating {TOTAL_URLS:,} total URLs")
    elif isinstance(environment.runner, WorkerRunner):
        print(f"Worker node connecting to master")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Load preloaded codes for read tests."""
    global PRELOADED_CODES

    codes_file = os.getenv("PRELOADED_CODES_FILE", "")
    if codes_file and os.path.exists(codes_file):
        with open(codes_file, 'r') as f:
            PRELOADED_CODES = [line.strip() for line in f if line.strip()]
        print(f"Loaded {len(PRELOADED_CODES):,} preloaded short codes")
    else:
        print("No preloaded codes file - will only test with dynamically created URLs")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Save test results."""
    if isinstance(environment.runner, MasterRunner):
        stats = environment.runner.stats

        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_requests": stats.total.num_requests,
            "total_failures": stats.total.num_failures,
            "avg_response_time": stats.total.avg_response_time,
            "median_response_time": stats.total.median_response_time,
            "p95_response_time": stats.total.get_response_time_percentile(0.95),
            "p99_response_time": stats.total.get_response_time_percentile(0.99),
            "requests_per_second": stats.total.current_rps,
            "failures_per_second": stats.total.current_fail_per_sec,
        }

        output_file = f"load_test_results_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\nTest Results saved to {output_file}")
        print(f"Total Requests: {results['total_requests']:,}")
        print(f"Total Failures: {results['total_failures']:,}")
        print(f"Avg Response Time: {results['avg_response_time']:.2f}ms")
        print(f"P99 Response Time: {results['p99_response_time']:.2f}ms")
        print(f"RPS: {results['requests_per_second']:.2f}")


# Custom metrics collection

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Collect custom metrics for each request."""
    # This hook can be used to send metrics to Prometheus, Datadog, etc.
    pass
