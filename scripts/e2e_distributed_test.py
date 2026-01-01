#!/usr/bin/env python3
"""
E2E Test Script for Distributed Consensus Problems

This script tests the full submission pipeline for all distributed problems
across all supported languages. It:
1. Gets the template code for each problem/language combination
2. Submits the template code
3. Polls until build/test completion
4. Reports results

Usage:
    python scripts/e2e_distributed_test.py [--backend-url URL] [--problem-id ID] [--language LANG]

Examples:
    # Test all problems and languages
    python scripts/e2e_distributed_test.py

    # Test specific problem
    python scripts/e2e_distributed_test.py --problem-id 1

    # Test specific language
    python scripts/e2e_distributed_test.py --language python

    # Test against production
    python scripts/e2e_distributed_test.py --backend-url https://sdp-backend-875426505110.us-central1.run.app
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import aiohttp

# Problem configurations
PROBLEMS = {
    1: "Raft Consensus",
    2: "Paxos Consensus",
    3: "Two-Phase Commit",
    4: "Chandy-Lamport Snapshot",
    5: "Consistent Hashing",
    6: "Rendezvous Hashing",
}

LANGUAGES = ["python", "go", "java", "cpp", "rust"]

# Status constants
TERMINAL_STATUSES = ["COMPLETED", "FAILED", "BUILD_FAILED", "DEPLOY_FAILED"]
SUCCESS_STATUSES = ["COMPLETED"]


@dataclass
class TestResult:
    """Result of a single E2E test."""
    problem_id: int
    problem_name: str
    language: str
    submission_id: Optional[int]
    status: str
    duration_seconds: float
    build_passed: bool
    deploy_passed: bool
    tests_passed: int
    tests_failed: int
    tests_error: int
    error_message: Optional[str]


class DistributedE2ETest:
    """E2E test runner for distributed problems."""

    def __init__(self, backend_url: str, timeout_seconds: int = 900):
        self.backend_url = backend_url.rstrip('/')
        self.timeout_seconds = timeout_seconds
        self.results: List[TestResult] = []

    async def get_template(
        self, session: aiohttp.ClientSession, problem_id: int, language: str
    ) -> str:
        """Get the template code for a problem/language."""
        url = f"{self.backend_url}/api/distributed/problems/{problem_id}/template/{language}"
        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Failed to get template: {resp.status}")
            data = await resp.json()
            return data.get("template", "")

    async def submit_code(
        self, session: aiohttp.ClientSession, problem_id: int, language: str, source_code: str
    ) -> int:
        """Submit code and return submission ID."""
        url = f"{self.backend_url}/api/distributed/submissions"
        payload = {
            "problem_id": problem_id,
            "language": language,
            "source_code": source_code,
        }
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Failed to submit: {resp.status} - {text}")
            data = await resp.json()
            return data["id"]

    async def get_submission_status(
        self, session: aiohttp.ClientSession, submission_id: int
    ) -> dict:
        """Get current submission status."""
        url = f"{self.backend_url}/api/distributed/submissions/{submission_id}"
        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Failed to get status: {resp.status}")
            return await resp.json()

    async def get_test_results(
        self, session: aiohttp.ClientSession, submission_id: int
    ) -> List[dict]:
        """Get test results for a submission."""
        url = f"{self.backend_url}/api/distributed/submissions/{submission_id}/tests"
        async with session.get(url) as resp:
            if resp.status != 200:
                return []
            return await resp.json()

    async def wait_for_completion(
        self, session: aiohttp.ClientSession, submission_id: int
    ) -> Tuple[str, Optional[str]]:
        """Poll until submission reaches terminal status."""
        start_time = time.time()
        last_status = ""

        while time.time() - start_time < self.timeout_seconds:
            status_data = await self.get_submission_status(session, submission_id)
            current_status = status_data.get("status", "UNKNOWN")

            if current_status != last_status:
                elapsed = int(time.time() - start_time)
                print(f"    [{elapsed}s] Status: {current_status}")
                last_status = current_status

            if current_status.upper() in TERMINAL_STATUSES:
                return current_status, status_data.get("error_message")

            await asyncio.sleep(10)  # Poll every 10 seconds

        return "TIMEOUT", f"Exceeded {self.timeout_seconds}s timeout"

    async def run_single_test(
        self, session: aiohttp.ClientSession, problem_id: int, language: str
    ) -> TestResult:
        """Run a single E2E test for a problem/language combination."""
        problem_name = PROBLEMS.get(problem_id, f"Problem {problem_id}")
        print(f"\n{'='*60}")
        print(f"Testing {problem_name} [{language}]")
        print(f"{'='*60}")

        start_time = time.time()

        try:
            # Get template
            print("  Getting template...")
            template = await self.get_template(session, problem_id, language)
            if not template or template.startswith("//") and "not found" in template.lower():
                raise Exception(f"Template not available: {template[:100]}")
            print(f"  Template size: {len(template)} bytes")

            # Submit
            print("  Submitting code...")
            submission_id = await self.submit_code(session, problem_id, language, template)
            print(f"  Submission ID: {submission_id}")

            # Wait for completion
            print("  Waiting for build and tests...")
            final_status, error_message = await self.wait_for_completion(session, submission_id)

            # Get test results
            test_results = await self.get_test_results(session, submission_id)
            tests_passed = sum(1 for t in test_results if t.get("status") == "passed")
            tests_failed = sum(1 for t in test_results if t.get("status") == "failed")
            tests_error = sum(1 for t in test_results if t.get("status") == "error")

            duration = time.time() - start_time

            # Determine pass/fail
            build_passed = final_status.upper() not in ["BUILD_FAILED"]
            deploy_passed = final_status.upper() not in ["BUILD_FAILED", "DEPLOY_FAILED"]

            result = TestResult(
                problem_id=problem_id,
                problem_name=problem_name,
                language=language,
                submission_id=submission_id,
                status=final_status,
                duration_seconds=duration,
                build_passed=build_passed,
                deploy_passed=deploy_passed,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                tests_error=tests_error,
                error_message=error_message,
            )

            # Print summary
            status_icon = "✓" if final_status.upper() in SUCCESS_STATUSES and tests_failed == 0 else "✗"
            print(f"\n  {status_icon} Result: {final_status}")
            print(f"    Duration: {duration:.1f}s")
            print(f"    Build: {'✓' if build_passed else '✗'}")
            print(f"    Deploy: {'✓' if deploy_passed else '✗'}")
            print(f"    Tests: {tests_passed} passed, {tests_failed} failed, {tests_error} error")
            if error_message:
                print(f"    Error: {error_message[:200]}")

            return result

        except Exception as e:
            duration = time.time() - start_time
            print(f"\n  ✗ Error: {e}")
            return TestResult(
                problem_id=problem_id,
                problem_name=problem_name,
                language=language,
                submission_id=None,
                status="ERROR",
                duration_seconds=duration,
                build_passed=False,
                deploy_passed=False,
                tests_passed=0,
                tests_failed=0,
                tests_error=0,
                error_message=str(e),
            )

    async def run_all_tests(
        self,
        problem_ids: Optional[List[int]] = None,
        languages: Optional[List[str]] = None,
    ) -> List[TestResult]:
        """Run E2E tests for specified problems and languages."""
        if problem_ids is None:
            problem_ids = list(PROBLEMS.keys())
        if languages is None:
            languages = LANGUAGES

        print(f"\n{'#'*60}")
        print(f"# Distributed E2E Test Suite")
        print(f"# Backend: {self.backend_url}")
        print(f"# Problems: {problem_ids}")
        print(f"# Languages: {languages}")
        print(f"# Total tests: {len(problem_ids) * len(languages)}")
        print(f"{'#'*60}")

        async with aiohttp.ClientSession() as session:
            for problem_id in problem_ids:
                for language in languages:
                    result = await self.run_single_test(session, problem_id, language)
                    self.results.append(result)

        return self.results

    def print_summary(self):
        """Print test summary."""
        print(f"\n{'='*60}")
        print("TEST SUMMARY")
        print(f"{'='*60}")

        total = len(self.results)
        passed = sum(1 for r in self.results if r.status.upper() in SUCCESS_STATUSES and r.tests_failed == 0)
        failed = total - passed

        print(f"\nTotal: {total}, Passed: {passed}, Failed: {failed}")
        print(f"\nDetailed Results:")
        print("-" * 60)

        for result in self.results:
            status_icon = "✓" if result.status.upper() in SUCCESS_STATUSES and result.tests_failed == 0 else "✗"
            print(
                f"  {status_icon} {result.problem_name} [{result.language}]: "
                f"{result.status} ({result.duration_seconds:.1f}s)"
            )
            if result.tests_passed + result.tests_failed + result.tests_error > 0:
                print(
                    f"      Tests: {result.tests_passed} passed, "
                    f"{result.tests_failed} failed, {result.tests_error} error"
                )
            if result.error_message:
                print(f"      Error: {result.error_message[:100]}")

        print(f"\n{'='*60}")
        print(f"OVERALL: {'PASSED' if failed == 0 else 'FAILED'}")
        print(f"{'='*60}")

        return failed == 0

    def save_results(self, output_file: str):
        """Save results to JSON file."""
        data = {
            "backend_url": self.backend_url,
            "total_tests": len(self.results),
            "passed": sum(1 for r in self.results if r.status.upper() in SUCCESS_STATUSES and r.tests_failed == 0),
            "results": [
                {
                    "problem_id": r.problem_id,
                    "problem_name": r.problem_name,
                    "language": r.language,
                    "submission_id": r.submission_id,
                    "status": r.status,
                    "duration_seconds": r.duration_seconds,
                    "build_passed": r.build_passed,
                    "deploy_passed": r.deploy_passed,
                    "tests_passed": r.tests_passed,
                    "tests_failed": r.tests_failed,
                    "tests_error": r.tests_error,
                    "error_message": r.error_message,
                }
                for r in self.results
            ],
        }
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\nResults saved to: {output_file}")


async def main():
    parser = argparse.ArgumentParser(description="E2E tests for distributed problems")
    parser.add_argument(
        "--backend-url",
        default="https://sdp-backend-875426505110.us-central1.run.app",
        help="Backend API URL",
    )
    parser.add_argument(
        "--problem-id",
        type=int,
        help="Test specific problem ID (1-6)",
    )
    parser.add_argument(
        "--language",
        help="Test specific language",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Timeout in seconds per test (default: 900)",
    )
    parser.add_argument(
        "--output",
        default="e2e_results.json",
        help="Output file for results",
    )
    args = parser.parse_args()

    # Parse problem IDs
    problem_ids = [args.problem_id] if args.problem_id else None
    languages = [args.language] if args.language else None

    # Run tests
    tester = DistributedE2ETest(args.backend_url, args.timeout)
    await tester.run_all_tests(problem_ids, languages)

    # Print summary and save results
    success = tester.print_summary()
    tester.save_results(args.output)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
