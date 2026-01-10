"""
Test runner service for executing functional, performance, and chaos tests.
Orchestrates test execution and result collection against deployed services.
"""

import asyncio
import subprocess
import json
import tempfile
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import re

from backend.models.test_result import TestType, TestStatus, AnalysisStatus
from backend.services.ai_service import AIService
from backend.services.error_analyzer import error_analyzer
from backend.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Path to test files - use environment variable or fallback to relative path
TESTS_DIR = Path(os.getenv("TESTS_DIR", str(Path(__file__).parent.parent.parent / "tests")))


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
        self.tests_dir = TESTS_DIR

    async def run_all_tests(
        self,
        submission_id: int,
        endpoint_url: str,
        api_spec: Optional[Dict[str, Any]] = None,
        design_text: str = "",
        problem_description: str = "",
        progress_callback: Optional[callable] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run all test types against a deployment.

        Args:
            submission_id: Submission ID
            endpoint_url: Deployed service URL
            api_spec: API specification for test generation
            design_text: Design description
            problem_description: Problem description
            progress_callback: Optional callback(step, detail, pct) for progress updates

        Returns:
            List of test results with error analysis for failures
        """
        results = []

        # Determine which test file to run based on problem description
        test_file = self._get_test_file_for_problem(problem_description)
        locust_file = self._get_locust_file_for_problem(problem_description)
        chaos_file = self._get_chaos_file_for_problem(problem_description)

        # Get test file names for logging
        test_file_name = test_file.name if test_file else "none"
        locust_file_name = locust_file.name if locust_file else "none"
        chaos_file_name = chaos_file.name if chaos_file else "none"

        # Run functional tests using pytest
        if progress_callback:
            progress_callback(
                "Running Functional Tests",
                f"Executing pytest with {test_file_name}: Testing health endpoints, CRUD operations, error handling...",
                75
            )

        functional_results = await self._run_pytest_tests(
            submission_id=submission_id,
            endpoint_url=endpoint_url,
            test_file=test_file,
        )
        results.extend(functional_results)

        passed_count = sum(1 for r in functional_results if r.get("status") == "passed")
        total_count = len(functional_results)

        # Run performance tests using Locust
        if progress_callback:
            progress_callback(
                "Running Performance Tests",
                f"Functional: {passed_count}/{total_count} passed. Now running Locust load test with {locust_file_name}: 10 users, 30 seconds...",
                85
            )

        performance_results = await self._run_locust_tests(
            submission_id=submission_id,
            endpoint_url=endpoint_url,
            locust_file=locust_file,
        )
        results.extend(performance_results)

        perf_status = performance_results[0].get("status", "unknown") if performance_results else "skipped"

        # Run chaos tests using Chaos Toolkit
        if progress_callback:
            progress_callback(
                "Running Chaos Tests",
                f"Performance: {perf_status}. Now running chaos engineering tests with {chaos_file_name}: Testing resilience under failures...",
                92
            )

        chaos_results = await self._run_chaos_toolkit_tests(
            submission_id=submission_id,
            endpoint_url=endpoint_url,
            chaos_file=chaos_file,
        )
        results.extend(chaos_results)

        # Analyze failed tests
        failed_results = [r for r in results if r.get("status") in ["failed", "error"]]
        if failed_results and progress_callback:
            progress_callback(
                "Analyzing Failures",
                f"AI is analyzing {len(failed_results)} failed test(s) to identify root causes...",
                96
            )

        # Add error analysis to failed tests
        for result in results:
            if result.get("status") in ["failed", "error"]:
                await self._add_error_analysis(
                    result=result,
                    problem_description=problem_description,
                    design_text=design_text,
                    api_spec=api_spec,
                    endpoint_url=endpoint_url,
                )
            else:
                # Mark passed/skipped tests as analysis skipped
                result["ai_analysis_status"] = AnalysisStatus.SKIPPED.value

        if progress_callback:
            total_tests = len(results)
            passed_tests = sum(1 for r in results if r.get("status") == "passed")
            progress_callback(
                "Tests Complete",
                f"All tests finished: {passed_tests}/{total_tests} passed",
                100
            )

        return results

    async def _add_error_analysis(
        self,
        result: Dict[str, Any],
        problem_description: str,
        design_text: str,
        api_spec: Optional[Dict[str, Any]],
        endpoint_url: str,
    ) -> None:
        """
        Add AI-powered error analysis to a failed test result.
        Modifies the result dict in place.
        """
        try:
            # Get error output from details
            details = result.get("details", {})
            error_output = ""
            if isinstance(details, dict):
                error_output = details.get("error", "")
                if not error_output:
                    error_output = details.get("stderr", "")
                if not error_output:
                    error_output = details.get("stdout", "")
            elif isinstance(details, str):
                error_output = details

            # Analyze the failure
            analysis = await error_analyzer.analyze_failure(
                test_type=result.get("test_type", "unknown"),
                test_name=result.get("test_name", "unknown"),
                status=result.get("status", "failed"),
                error_output=str(error_output),
                problem_description=problem_description,
                design_text=design_text,
                api_spec=api_spec,
                endpoint_url=endpoint_url,
            )

            # Add analysis to result
            result["error_category"] = analysis.get("category")
            result["error_analysis"] = analysis
            result["ai_analysis_status"] = analysis.get("status", AnalysisStatus.COMPLETED.value)

        except Exception as e:
            # If analysis fails, mark it but don't fail the whole test
            result["ai_analysis_status"] = AnalysisStatus.FAILED.value
            result["error_analysis"] = {
                "error": str(e),
                "status": AnalysisStatus.FAILED.value,
            }

    def _get_test_file_for_problem(self, problem_description: str) -> Optional[Path]:
        """Get the appropriate test file based on problem type."""
        desc_lower = problem_description.lower()
        functional_dir = self.tests_dir / "functional"

        if "url" in desc_lower and "shorten" in desc_lower:
            return functional_dir / "test_url_shortener.py"
        elif "file" in desc_lower and ("shar" in desc_lower or "dropbox" in desc_lower):
            return functional_dir / "test_file_sharing.py"
        elif "chat" in desc_lower or "whatsapp" in desc_lower or "messag" in desc_lower:
            return functional_dir / "test_chat_app.py"
        else:
            # Return generic test or first available
            return functional_dir / "test_url_shortener.py"

    def _get_locust_file_for_problem(self, problem_description: str) -> Optional[Path]:
        """Get the appropriate Locust file based on problem type."""
        desc_lower = problem_description.lower()
        perf_dir = self.tests_dir / "performance"

        if "url" in desc_lower and "shorten" in desc_lower:
            return perf_dir / "locustfile_url_shortener.py"
        elif "file" in desc_lower and ("shar" in desc_lower or "dropbox" in desc_lower):
            return perf_dir / "locustfile_file_sharing.py"
        elif "chat" in desc_lower or "whatsapp" in desc_lower or "messag" in desc_lower:
            return perf_dir / "locustfile_chat.py"
        else:
            return perf_dir / "locustfile_url_shortener.py"

    def _get_chaos_file_for_problem(self, problem_description: str) -> Optional[Path]:
        """Get the appropriate chaos experiment file based on problem type."""
        desc_lower = problem_description.lower()
        chaos_dir = self.tests_dir / "chaos"

        if "url" in desc_lower and "shorten" in desc_lower:
            return chaos_dir / "experiment_url_shortener.json"
        elif "file" in desc_lower and ("shar" in desc_lower or "dropbox" in desc_lower):
            return chaos_dir / "experiment_file_sharing.json"
        elif "chat" in desc_lower or "whatsapp" in desc_lower or "messag" in desc_lower:
            return chaos_dir / "experiment_chat.json"
        else:
            return chaos_dir / "experiment_url_shortener.json"

    async def _run_pytest_tests(
        self,
        submission_id: int,
        endpoint_url: str,
        test_file: Optional[Path],
    ) -> List[Dict[str, Any]]:
        """Run pytest tests against the deployed service."""
        results = []
        start_time = datetime.utcnow()

        if not test_file or not test_file.exists():
            warning_msg = f"Functional test file not found: {test_file}"
            logger.warning(warning_msg)
            return [{
                "test_type": TestType.FUNCTIONAL.value,
                "test_name": "pytest_suite",
                "status": TestStatus.SKIPPED.value,
                "duration_ms": 0,
                "details": {"error": "No test file found", "warning": warning_msg},
            }]

        try:
            # Run pytest with JSON output
            env = os.environ.copy()
            env["TEST_TARGET_URL"] = endpoint_url

            proc = await asyncio.create_subprocess_exec(
                "python", "-m", "pytest", str(test_file),
                "-v", "--tb=short", "-x", "--timeout=60",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=300,  # 5 minute timeout for all tests
            )

            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            output = stdout.decode()

            # Parse pytest output to extract individual test results
            test_results = self._parse_pytest_output(output)

            if test_results:
                for test_name, passed in test_results.items():
                    results.append({
                        "test_type": TestType.FUNCTIONAL.value,
                        "test_name": test_name,
                        "status": TestStatus.PASSED.value if passed else TestStatus.FAILED.value,
                        "duration_ms": duration_ms // len(test_results),
                        "details": {"output": output[:500]},
                    })
            else:
                # No individual tests parsed, report overall
                results.append({
                    "test_type": TestType.FUNCTIONAL.value,
                    "test_name": "pytest_suite",
                    "status": TestStatus.PASSED.value if proc.returncode == 0 else TestStatus.FAILED.value,
                    "duration_ms": duration_ms,
                    "details": {
                        "stdout": output[:2000],
                        "stderr": stderr.decode()[:1000],
                        "return_code": proc.returncode,
                    },
                })

        except asyncio.TimeoutError:
            results.append({
                "test_type": TestType.FUNCTIONAL.value,
                "test_name": "pytest_suite",
                "status": TestStatus.ERROR.value,
                "duration_ms": 300000,
                "details": {"error": "Tests timed out after 5 minutes"},
            })
        except Exception as e:
            results.append({
                "test_type": TestType.FUNCTIONAL.value,
                "test_name": "pytest_suite",
                "status": TestStatus.ERROR.value,
                "duration_ms": 0,
                "details": {"error": str(e)},
            })

        return results

    def _parse_pytest_output(self, output: str) -> Dict[str, bool]:
        """Parse pytest verbose output to extract test results."""
        results = {}
        # Match lines like "test_health_endpoint PASSED" or "test_create_short_url FAILED"
        pattern = r"(test_\w+)\s+(PASSED|FAILED|ERROR|SKIPPED)"
        matches = re.findall(pattern, output)
        for test_name, status in matches:
            results[test_name] = status == "PASSED"
        return results

    async def _run_locust_tests(
        self,
        submission_id: int,
        endpoint_url: str,
        locust_file: Optional[Path],
    ) -> List[Dict[str, Any]]:
        """Run Locust performance tests."""
        results = []
        start_time = datetime.utcnow()

        if not locust_file or not locust_file.exists():
            warning_msg = f"Locust performance test file not found: {locust_file}"
            logger.warning(warning_msg)
            return [{
                "test_type": TestType.PERFORMANCE.value,
                "test_name": "load_test",
                "status": TestStatus.SKIPPED.value,
                "duration_ms": 0,
                "details": {"error": "No Locust file found", "warning": warning_msg},
            }]

        # Check if locust command is available
        import shutil
        locust_cmd = shutil.which("locust")
        if not locust_cmd:
            return [{
                "test_type": TestType.PERFORMANCE.value,
                "test_name": "load_test",
                "status": TestStatus.SKIPPED.value,
                "duration_ms": 0,
                "details": {"error": "Locust command not found in PATH"},
            }]

        try:
            workspace = self.test_dir / f"perf_{submission_id}"
            workspace.mkdir(exist_ok=True)

            proc = await asyncio.create_subprocess_exec(
                locust_cmd,
                "-f", str(locust_file),
                "--headless",
                "--host", endpoint_url,
                "-u", "10",  # 10 users
                "-r", "2",   # spawn rate
                "-t", "30s", # run time
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

            # Determine pass/fail with lenient thresholds for candidate solutions
            # Cloud Run cold starts can cause high initial latency
            # Candidate solutions may have implementation gaps
            max_latency_ms = 5000  # 5 seconds - allows for cold starts and slow implementations
            max_error_rate = 50    # 50% - focus on whether core functionality works at all

            passed = (
                stats.get("avg_response_time", float("inf")) < max_latency_ms and
                stats.get("failure_rate", 100) < max_error_rate
            )

            results.append({
                "test_type": TestType.PERFORMANCE.value,
                "test_name": "load_test_10_users",
                "status": TestStatus.PASSED.value if passed else TestStatus.FAILED.value,
                "duration_ms": duration_ms,
                "details": {
                    "stats": stats,
                    "thresholds": {"max_latency_ms": max_latency_ms, "max_error_rate": max_error_rate},
                },
            })

        except asyncio.TimeoutError:
            results.append({
                "test_type": TestType.PERFORMANCE.value,
                "test_name": "load_test",
                "status": TestStatus.ERROR.value,
                "duration_ms": 120000,
                "details": {"error": "Load test timed out"},
            })
        except Exception as e:
            results.append({
                "test_type": TestType.PERFORMANCE.value,
                "test_name": "load_test",
                "status": TestStatus.ERROR.value,
                "duration_ms": 0,
                "details": {"error": str(e)},
            })

        return results

    async def _run_chaos_toolkit_tests(
        self,
        submission_id: int,
        endpoint_url: str,
        chaos_file: Optional[Path],
    ) -> List[Dict[str, Any]]:
        """Run Chaos Toolkit experiments."""
        results = []
        start_time = datetime.utcnow()

        if not chaos_file or not chaos_file.exists():
            warning_msg = f"Chaos experiment file not found: {chaos_file}"
            logger.warning(warning_msg)
            return [{
                "test_type": TestType.CHAOS.value,
                "test_name": "chaos_experiment",
                "status": TestStatus.SKIPPED.value,
                "duration_ms": 0,
                "chaos_scenario": "none",
                "details": {"error": "No chaos experiment file found", "warning": warning_msg},
            }]

        try:
            workspace = self.test_dir / f"chaos_{submission_id}"
            workspace.mkdir(exist_ok=True)

            # Read and modify experiment to use the endpoint URL
            with open(chaos_file) as f:
                experiment = json.load(f)

            # Replace placeholders in the experiment
            experiment_str = json.dumps(experiment)
            experiment_str = experiment_str.replace("${TARGET_URL}", endpoint_url)
            experiment_str = experiment_str.replace("${TEST_TOKEN}", "test-token")
            modified_experiment = json.loads(experiment_str)

            # Write modified experiment
            modified_file = workspace / "experiment.json"
            with open(modified_file, "w") as f:
                json.dump(modified_experiment, f, indent=2)

            # Run chaos toolkit using python -m chaostoolkit.cli
            # The 'chaos' CLI entry point may not be installed, so we use the module directly
            proc = await asyncio.create_subprocess_exec(
                "python", "-m", "chaostoolkit.cli", "run", str(modified_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workspace),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=300,
            )

            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            results.append({
                "test_type": TestType.CHAOS.value,
                "test_name": experiment.get("title", "chaos_experiment"),
                "status": TestStatus.PASSED.value if proc.returncode == 0 else TestStatus.FAILED.value,
                "duration_ms": duration_ms,
                "chaos_scenario": "resilience_test",
                "details": {
                    "stdout": stdout.decode()[:2000],
                    "stderr": stderr.decode()[:1000],
                },
            })

        except asyncio.TimeoutError:
            results.append({
                "test_type": TestType.CHAOS.value,
                "test_name": "chaos_experiment",
                "status": TestStatus.ERROR.value,
                "duration_ms": 300000,
                "chaos_scenario": "timeout",
                "details": {"error": "Chaos experiment timed out"},
            })
        except Exception as e:
            results.append({
                "test_type": TestType.CHAOS.value,
                "test_name": "chaos_experiment",
                "status": TestStatus.ERROR.value,
                "duration_ms": 0,
                "chaos_scenario": "error",
                "details": {"error": str(e)},
            })

        return results

    # Legacy methods kept for compatibility
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
