"""
Test runner service for executing functional, performance, and chaos tests.
Orchestrates test execution and result collection.
"""

import asyncio
import subprocess
import json
import tempfile
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

from backend.models.test_result import TestType, TestStatus
from backend.services.ai_service import AIService
from backend.config import get_settings

settings = get_settings()


class TestRunner:
    """
    Service for running tests against deployed candidate solutions.
    Supports functional, performance, and chaos tests.
    """

    def __init__(self):
        """Initialize the test runner."""
        self.ai_service = AIService()
        self.test_dir = Path("/tmp/test_workspaces")
        self.test_dir.mkdir(exist_ok=True)

    async def run_all_tests(
        self,
        submission_id: int,
        endpoint_url: str,
        api_spec: Optional[Dict[str, Any]] = None,
        design_text: str = "",
        problem_description: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Run all test types against a deployment.

        Args:
            submission_id: Submission ID
            endpoint_url: Deployed service URL
            api_spec: API specification for test generation
            design_text: Design description
            problem_description: Problem description

        Returns:
            List of test results
        """
        results = []

        # Generate tests using AI
        test_specs = await self.ai_service.generate_tests(
            problem_description=problem_description,
            design_text=design_text,
            api_spec_input=api_spec,
            endpoint_url=endpoint_url,
        )

        # Run functional tests
        functional_results = await self._run_functional_tests(
            submission_id=submission_id,
            endpoint_url=endpoint_url,
            test_specs=test_specs.get("functional_tests", []),
        )
        results.extend(functional_results)

        # Run performance tests
        performance_results = await self._run_performance_tests(
            submission_id=submission_id,
            endpoint_url=endpoint_url,
            test_specs=test_specs.get("performance_tests", []),
        )
        results.extend(performance_results)

        # Run chaos tests
        chaos_results = await self._run_chaos_tests(
            submission_id=submission_id,
            endpoint_url=endpoint_url,
            test_specs=test_specs.get("chaos_tests", []),
        )
        results.extend(chaos_results)

        return results

    async def _run_functional_tests(
        self,
        submission_id: int,
        endpoint_url: str,
        test_specs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Run functional API tests.

        Args:
            submission_id: Submission ID
            endpoint_url: Service URL
            test_specs: Test specifications

        Returns:
            List of test results
        """
        results = []

        for spec in test_specs:
            test_name = spec.get("name", "Unnamed Test")
            start_time = datetime.utcnow()

            try:
                # Create test script
                test_script = self._generate_functional_test_script(
                    endpoint_url=endpoint_url,
                    spec=spec,
                )

                # Write and execute test
                workspace = self.test_dir / f"func_{submission_id}_{len(results)}"
                workspace.mkdir(exist_ok=True)

                test_file = workspace / "test_functional.py"
                test_file.write_text(test_script)

                # Run pytest
                proc = await asyncio.create_subprocess_exec(
                    "python", "-m", "pytest", str(test_file), "-v", "--tb=short",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=60,
                )

                duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                status = TestStatus.PASSED.value if proc.returncode == 0 else TestStatus.FAILED.value

                results.append({
                    "test_type": TestType.FUNCTIONAL.value,
                    "test_name": test_name,
                    "status": status,
                    "duration_ms": duration_ms,
                    "details": {
                        "stdout": stdout.decode()[:2000],
                        "stderr": stderr.decode()[:1000],
                        "spec": spec,
                    },
                })

            except asyncio.TimeoutError:
                results.append({
                    "test_type": TestType.FUNCTIONAL.value,
                    "test_name": test_name,
                    "status": TestStatus.ERROR.value,
                    "duration_ms": 60000,
                    "details": {"error": "Test timed out"},
                })
            except Exception as e:
                results.append({
                    "test_type": TestType.FUNCTIONAL.value,
                    "test_name": test_name,
                    "status": TestStatus.ERROR.value,
                    "duration_ms": 0,
                    "details": {"error": str(e)},
                })

        return results

    def _generate_functional_test_script(
        self,
        endpoint_url: str,
        spec: Dict[str, Any],
    ) -> str:
        """
        Generate a pytest script for a functional test.

        Args:
            endpoint_url: Service URL
            spec: Test specification

        Returns:
            Python test script
        """
        method = spec.get("method", "GET")
        path = spec.get("path", "/")
        expected_status = spec.get("expected_status", 200)
        body = spec.get("body", {})
        headers = spec.get("headers", {})

        return f'''
import requests
import pytest

def test_{spec.get("name", "api").replace(" ", "_").lower()}():
    """Test: {spec.get("description", "API test")}"""
    url = "{endpoint_url}{path}"
    headers = {json.dumps(headers)}

    response = requests.{method.lower()}(
        url,
        json={json.dumps(body) if body else "None"},
        headers=headers,
        timeout=30,
    )

    assert response.status_code == {expected_status}, f"Expected {expected_status}, got {{response.status_code}}"

    # Additional assertions from spec
    response_checks = {json.dumps(spec.get("response_checks", {}))}
    if response_checks:
        data = response.json()
        for key, expected in response_checks.items():
            assert key in data, f"Missing key: {{key}}"
'''

    async def _run_performance_tests(
        self,
        submission_id: int,
        endpoint_url: str,
        test_specs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Run performance/load tests using Locust.

        Args:
            submission_id: Submission ID
            endpoint_url: Service URL
            test_specs: Test specifications

        Returns:
            List of test results
        """
        results = []

        for spec in test_specs:
            test_name = spec.get("name", "Load Test")
            start_time = datetime.utcnow()

            try:
                # Create Locust file
                locust_script = self._generate_locust_script(
                    endpoint_url=endpoint_url,
                    spec=spec,
                )

                workspace = self.test_dir / f"perf_{submission_id}_{len(results)}"
                workspace.mkdir(exist_ok=True)

                locust_file = workspace / "locustfile.py"
                locust_file.write_text(locust_script)

                # Run Locust in headless mode
                users = spec.get("users", 10)
                spawn_rate = spec.get("spawn_rate", 5)
                run_time = spec.get("run_time", "30s")

                proc = await asyncio.create_subprocess_exec(
                    "locust",
                    "-f", str(locust_file),
                    "--headless",
                    "--host", endpoint_url,
                    "-u", str(users),
                    "-r", str(spawn_rate),
                    "-t", run_time,
                    "--csv", str(workspace / "results"),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=120,
                )

                duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

                # Parse results
                stats = self._parse_locust_stats(workspace / "results_stats.csv")

                # Determine pass/fail based on thresholds
                max_latency = spec.get("max_latency_ms", 1000)
                min_rps = spec.get("min_rps", 10)

                passed = (
                    stats.get("avg_response_time", float("inf")) < max_latency and
                    stats.get("requests_per_second", 0) >= min_rps and
                    stats.get("failure_rate", 100) < 5
                )

                results.append({
                    "test_type": TestType.PERFORMANCE.value,
                    "test_name": test_name,
                    "status": TestStatus.PASSED.value if passed else TestStatus.FAILED.value,
                    "duration_ms": duration_ms,
                    "details": {
                        "stats": stats,
                        "thresholds": {
                            "max_latency_ms": max_latency,
                            "min_rps": min_rps,
                        },
                    },
                })

            except asyncio.TimeoutError:
                results.append({
                    "test_type": TestType.PERFORMANCE.value,
                    "test_name": test_name,
                    "status": TestStatus.ERROR.value,
                    "duration_ms": 120000,
                    "details": {"error": "Performance test timed out"},
                })
            except Exception as e:
                results.append({
                    "test_type": TestType.PERFORMANCE.value,
                    "test_name": test_name,
                    "status": TestStatus.ERROR.value,
                    "duration_ms": 0,
                    "details": {"error": str(e)},
                })

        return results

    def _generate_locust_script(
        self,
        endpoint_url: str,
        spec: Dict[str, Any],
    ) -> str:
        """Generate a Locust load test script."""
        tasks = spec.get("tasks", [{"path": "/", "weight": 1}])

        task_methods = []
        for i, task in enumerate(tasks):
            method = task.get("method", "GET").lower()
            path = task.get("path", "/")
            weight = task.get("weight", 1)

            task_methods.append(f'''
    @task({weight})
    def task_{i}(self):
        self.client.{method}("{path}")
''')

        return f'''
from locust import HttpUser, task, between

class LoadTestUser(HttpUser):
    wait_time = between(1, 3)

{"".join(task_methods)}
'''

    def _parse_locust_stats(self, csv_path: Path) -> Dict[str, Any]:
        """Parse Locust CSV stats file."""
        try:
            import csv
            with open(csv_path) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if rows:
                    # Get aggregated stats
                    agg = rows[-1]  # Last row is usually aggregated
                    return {
                        "requests": int(agg.get("Request Count", 0)),
                        "failures": int(agg.get("Failure Count", 0)),
                        "avg_response_time": float(agg.get("Average Response Time", 0)),
                        "requests_per_second": float(agg.get("Requests/s", 0)),
                        "failure_rate": float(agg.get("Failure Count", 0)) / max(int(agg.get("Request Count", 1)), 1) * 100,
                    }
        except Exception:
            pass
        return {}

    async def _run_chaos_tests(
        self,
        submission_id: int,
        endpoint_url: str,
        test_specs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Run chaos engineering tests.

        Args:
            submission_id: Submission ID
            endpoint_url: Service URL
            test_specs: Test specifications

        Returns:
            List of test results
        """
        results = []

        for spec in test_specs:
            test_name = spec.get("name", "Chaos Test")
            scenario = spec.get("scenario", "service_failure")
            start_time = datetime.utcnow()

            try:
                # Create chaos experiment
                experiment = self._generate_chaos_experiment(
                    endpoint_url=endpoint_url,
                    spec=spec,
                )

                workspace = self.test_dir / f"chaos_{submission_id}_{len(results)}"
                workspace.mkdir(exist_ok=True)

                experiment_file = workspace / "experiment.json"
                experiment_file.write_text(json.dumps(experiment, indent=2))

                # Run chaos toolkit
                proc = await asyncio.create_subprocess_exec(
                    "chaos", "run", str(experiment_file),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=workspace,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=180,
                )

                duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                status = TestStatus.PASSED.value if proc.returncode == 0 else TestStatus.FAILED.value

                results.append({
                    "test_type": TestType.CHAOS.value,
                    "test_name": test_name,
                    "status": status,
                    "duration_ms": duration_ms,
                    "chaos_scenario": scenario,
                    "details": {
                        "stdout": stdout.decode()[:2000],
                        "stderr": stderr.decode()[:1000],
                        "experiment": experiment,
                    },
                })

            except asyncio.TimeoutError:
                results.append({
                    "test_type": TestType.CHAOS.value,
                    "test_name": test_name,
                    "status": TestStatus.ERROR.value,
                    "duration_ms": 180000,
                    "chaos_scenario": scenario,
                    "details": {"error": "Chaos test timed out"},
                })
            except Exception as e:
                results.append({
                    "test_type": TestType.CHAOS.value,
                    "test_name": test_name,
                    "status": TestStatus.ERROR.value,
                    "duration_ms": 0,
                    "chaos_scenario": scenario,
                    "details": {"error": str(e)},
                })

        return results

    def _generate_chaos_experiment(
        self,
        endpoint_url: str,
        spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a Chaos Toolkit experiment definition."""
        scenario = spec.get("scenario", "service_failure")

        # Base experiment structure
        experiment = {
            "version": "1.0.0",
            "title": spec.get("name", "Chaos Experiment"),
            "description": spec.get("description", "Test system resilience"),
            "steady-state-hypothesis": {
                "title": "Service is healthy",
                "probes": [
                    {
                        "type": "probe",
                        "name": "service-is-available",
                        "tolerance": True,
                        "provider": {
                            "type": "http",
                            "url": endpoint_url,
                            "timeout": 10,
                        },
                    }
                ],
            },
            "method": [],
            "rollbacks": [],
        }

        # Add scenario-specific actions
        if scenario == "service_failure":
            experiment["method"].append({
                "type": "action",
                "name": "simulate-service-failure",
                "provider": {
                    "type": "process",
                    "path": "sleep",
                    "arguments": "5",
                },
                "pauses": {"after": 5},
            })
        elif scenario == "network_latency":
            experiment["method"].append({
                "type": "action",
                "name": "introduce-latency",
                "provider": {
                    "type": "process",
                    "path": "sleep",
                    "arguments": "3",
                },
                "pauses": {"after": 3},
            })
        elif scenario == "zone_failure":
            experiment["method"].append({
                "type": "action",
                "name": "simulate-zone-failure",
                "provider": {
                    "type": "process",
                    "path": "sleep",
                    "arguments": "10",
                },
                "pauses": {"after": 10},
            })

        return experiment
