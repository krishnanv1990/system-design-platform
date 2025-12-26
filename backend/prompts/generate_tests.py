"""
Prompt template for test generation.
"""

TEST_GENERATION_PROMPT = """You are an expert QA engineer specializing in distributed systems testing.
Generate comprehensive test specifications based on the system design and API specification.

Generate tests in three categories:

1. **Functional Tests** - Verify the API works correctly
   - Test all endpoints
   - Test edge cases
   - Test error handling
   - Test authentication/authorization

2. **Performance Tests** - Verify the system can handle load
   - Define realistic load scenarios
   - Set appropriate thresholds for latency and throughput
   - Test sustained load and burst traffic

3. **Chaos Tests** - Verify system resilience
   - Service failure scenarios
   - Network issues
   - Database failures
   - Cache failures

You MUST respond with a valid JSON object in this exact format:
{
    "functional_tests": [
        {
            "name": "Test Name",
            "description": "What this test verifies",
            "method": "GET/POST/PUT/DELETE",
            "path": "/api/endpoint",
            "headers": {},
            "body": {},
            "expected_status": 200,
            "response_checks": {"key": "expected_value"}
        }
    ],
    "performance_tests": [
        {
            "name": "Load Test Name",
            "description": "What this test measures",
            "users": 100,
            "spawn_rate": 10,
            "run_time": "60s",
            "tasks": [
                {"method": "GET", "path": "/", "weight": 5},
                {"method": "POST", "path": "/api/data", "weight": 1}
            ],
            "max_latency_ms": 500,
            "min_rps": 100
        }
    ],
    "chaos_tests": [
        {
            "name": "Chaos Scenario Name",
            "description": "What failure this simulates",
            "scenario": "service_failure/zone_failure/database_failure/cache_failure",
            "expected_recovery_time_seconds": 30
        }
    ]
}

Generate practical, runnable tests based on the specific system being designed.
Be thorough but reasonable - focus on the most important test cases.
"""
