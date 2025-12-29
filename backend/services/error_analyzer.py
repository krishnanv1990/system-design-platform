"""
AI-powered error analysis service.
Uses Claude to analyze test failures and categorize root causes.
"""

import json
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

import anthropic

from backend.config import get_settings
from backend.prompts.analyze_error import ERROR_ANALYSIS_PROMPT, ERROR_ANALYSIS_USER_TEMPLATE
from backend.models.test_result import ErrorCategory, AnalysisStatus

settings = get_settings()


class ErrorAnalyzer:
    """
    Service for analyzing test failures using Claude AI.
    Categorizes failures as user_solution, platform, or deployment issues.
    """

    def __init__(self):
        """Initialize the Anthropic client."""
        has_valid_api_key = settings.anthropic_api_key and settings.anthropic_api_key != "demo-key"
        self.demo_mode = not has_valid_api_key
        if has_valid_api_key:
            self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        else:
            self.client = None
        self.model = "claude-sonnet-4-20250514"
        self._last_input_tokens = 0
        self._last_output_tokens = 0

    def get_last_usage(self) -> tuple[int, int]:
        """Get the input and output tokens from the last API call."""
        return self._last_input_tokens, self._last_output_tokens

    async def analyze_failure(
        self,
        test_type: str,
        test_name: str,
        status: str,
        error_output: str,
        problem_description: str,
        design_text: str,
        api_spec: Optional[Dict[str, Any]] = None,
        endpoint_url: str = "",
    ) -> Dict[str, Any]:
        """
        Analyze a test failure using Claude AI.

        Args:
            test_type: Type of test (functional, performance, chaos)
            test_name: Name of the test
            status: Test status (failed, error)
            error_output: The error message/output from the test
            problem_description: The problem being solved
            design_text: Candidate's design description
            api_spec: API specification (optional)
            endpoint_url: Deployed endpoint URL

        Returns:
            Analysis result with category, explanation, and suggestions
        """
        # Return mock analysis in demo mode
        if self.demo_mode:
            return self._get_demo_analysis(test_type, status, error_output)

        # Build the context for Claude
        user_message = ERROR_ANALYSIS_USER_TEMPLATE.format(
            test_type=test_type,
            test_name=test_name,
            status=status,
            error_output=error_output[:3000],  # Truncate long errors
            problem_description=problem_description,
            design_text=design_text or "No design description provided",
            api_spec=json.dumps(api_spec, indent=2) if api_spec else "No API spec provided",
            endpoint_url=endpoint_url or "Not available",
        )

        try:
            # Call Claude for analysis
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=ERROR_ANALYSIS_PROMPT,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )

            # Track token usage
            self._last_input_tokens = message.usage.input_tokens
            self._last_output_tokens = message.usage.output_tokens

            response_text = message.content[0].text

            # Parse the JSON response
            # Handle potential markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            result = json.loads(response_text.strip())

            # Validate and normalize the category
            category = result.get("category", "unknown")
            if category not in [e.value for e in ErrorCategory]:
                category = ErrorCategory.UNKNOWN.value

            return {
                "category": category,
                "confidence": float(result.get("confidence", 0.5)),
                "explanation": result.get("explanation", "Analysis could not determine the cause."),
                "suggestions": result.get("suggestions", []),
                "technical_details": result.get("technical_details", {}),
                "analyzed_at": datetime.utcnow().isoformat(),
                "status": AnalysisStatus.COMPLETED.value,
            }

        except json.JSONDecodeError as e:
            return {
                "category": ErrorCategory.UNKNOWN.value,
                "confidence": 0.3,
                "explanation": "Error analysis encountered a parsing issue.",
                "suggestions": ["Review the test output manually"],
                "technical_details": {"parse_error": str(e)},
                "analyzed_at": datetime.utcnow().isoformat(),
                "status": AnalysisStatus.FAILED.value,
            }
        except Exception as e:
            return {
                "category": ErrorCategory.UNKNOWN.value,
                "confidence": 0.0,
                "explanation": f"Error analysis failed: {str(e)}",
                "suggestions": ["Check test logs for more details"],
                "technical_details": {"error": str(e)},
                "analyzed_at": datetime.utcnow().isoformat(),
                "status": AnalysisStatus.FAILED.value,
            }

    def _get_demo_analysis(
        self,
        test_type: str,
        status: str,
        error_output: str,
    ) -> Dict[str, Any]:
        """
        Generate demo analysis based on error patterns.
        Used when Claude API is not available.
        """
        error_lower = error_output.lower()

        # Pattern matching for common errors
        if "connection refused" in error_lower or "connection reset" in error_lower:
            return {
                "category": ErrorCategory.DEPLOYMENT.value,
                "confidence": 0.9,
                "explanation": "The service could not be reached. This is likely a deployment or infrastructure issue, not a problem with your solution.",
                "suggestions": [
                    "Check the deployment status in the GCP console",
                    "Verify the Cloud Run service is running",
                    "Review deployment logs for startup errors"
                ],
                "technical_details": {
                    "error_type": "ConnectionError",
                    "affected_component": "Network/Deployment"
                },
                "analyzed_at": datetime.utcnow().isoformat(),
                "status": AnalysisStatus.COMPLETED.value,
                "demo_mode": True,
            }

        if "timeout" in error_lower:
            return {
                "category": ErrorCategory.DEPLOYMENT.value,
                "confidence": 0.8,
                "explanation": "The request timed out. This could be due to service startup time or resource constraints.",
                "suggestions": [
                    "Check if the service is handling requests correctly",
                    "Review Cloud Run logs for slow startup",
                    "Consider if the endpoint requires more resources"
                ],
                "technical_details": {
                    "error_type": "TimeoutError",
                    "affected_component": "Service Performance"
                },
                "analyzed_at": datetime.utcnow().isoformat(),
                "status": AnalysisStatus.COMPLETED.value,
                "demo_mode": True,
            }

        if "assert" in error_lower or "expected" in error_lower:
            return {
                "category": ErrorCategory.USER_SOLUTION.value,
                "confidence": 0.85,
                "explanation": "The test assertion failed because the API response didn't match the expected format or values.",
                "suggestions": [
                    "Review the API specification and ensure your response format matches",
                    "Check that all required fields are included in responses",
                    "Verify data types match the expected schema"
                ],
                "technical_details": {
                    "error_type": "AssertionError",
                    "affected_component": "API Response"
                },
                "analyzed_at": datetime.utcnow().isoformat(),
                "status": AnalysisStatus.COMPLETED.value,
                "demo_mode": True,
            }

        if "404" in error_output or "not found" in error_lower:
            return {
                "category": ErrorCategory.USER_SOLUTION.value,
                "confidence": 0.9,
                "explanation": "The requested endpoint was not found. Your API is missing a required route.",
                "suggestions": [
                    "Check that all required endpoints are implemented",
                    "Verify the URL path matches the API specification",
                    "Ensure routes are correctly registered"
                ],
                "technical_details": {
                    "error_type": "NotFoundError",
                    "affected_component": "API Routes"
                },
                "analyzed_at": datetime.utcnow().isoformat(),
                "status": AnalysisStatus.COMPLETED.value,
                "demo_mode": True,
            }

        if "500" in error_output or "internal server error" in error_lower:
            return {
                "category": ErrorCategory.USER_SOLUTION.value,
                "confidence": 0.75,
                "explanation": "The server returned an internal error. There's likely an unhandled exception in your code.",
                "suggestions": [
                    "Check for null pointer or undefined value errors",
                    "Add proper error handling to your endpoints",
                    "Review the server logs for the stack trace"
                ],
                "technical_details": {
                    "error_type": "InternalServerError",
                    "affected_component": "API Implementation"
                },
                "analyzed_at": datetime.utcnow().isoformat(),
                "status": AnalysisStatus.COMPLETED.value,
                "demo_mode": True,
            }

        if "400" in error_output or "422" in error_output or "validation" in error_lower:
            return {
                "category": ErrorCategory.USER_SOLUTION.value,
                "confidence": 0.85,
                "explanation": "The request was rejected due to validation errors. Your API's input validation may be too strict or incorrect.",
                "suggestions": [
                    "Review your input validation logic",
                    "Ensure you accept the request format specified in the API spec",
                    "Check that required fields are properly validated"
                ],
                "technical_details": {
                    "error_type": "ValidationError",
                    "affected_component": "Input Validation"
                },
                "analyzed_at": datetime.utcnow().isoformat(),
                "status": AnalysisStatus.COMPLETED.value,
                "demo_mode": True,
            }

        # Performance test specific
        if test_type == "performance":
            return {
                "category": ErrorCategory.USER_SOLUTION.value,
                "confidence": 0.7,
                "explanation": "The performance test failed to meet the required thresholds. Your implementation may need optimization.",
                "suggestions": [
                    "Review response time requirements",
                    "Consider adding caching for frequently accessed data",
                    "Optimize database queries if applicable"
                ],
                "technical_details": {
                    "error_type": "PerformanceFailure",
                    "affected_component": "API Performance"
                },
                "analyzed_at": datetime.utcnow().isoformat(),
                "status": AnalysisStatus.COMPLETED.value,
                "demo_mode": True,
            }

        # Chaos test specific
        if test_type == "chaos":
            return {
                "category": ErrorCategory.USER_SOLUTION.value,
                "confidence": 0.7,
                "explanation": "The system did not handle the failure scenario gracefully. Consider improving resilience.",
                "suggestions": [
                    "Implement retry logic with exponential backoff",
                    "Add circuit breaker patterns",
                    "Consider graceful degradation strategies"
                ],
                "technical_details": {
                    "error_type": "ResilienceFailure",
                    "affected_component": "Fault Tolerance"
                },
                "analyzed_at": datetime.utcnow().isoformat(),
                "status": AnalysisStatus.COMPLETED.value,
                "demo_mode": True,
            }

        # Default unknown
        return {
            "category": ErrorCategory.UNKNOWN.value,
            "confidence": 0.5,
            "explanation": "The test failed for an unclear reason. Please review the error details.",
            "suggestions": [
                "Review the full error output above",
                "Check your API implementation against the specification",
                "Verify your service is running correctly"
            ],
            "technical_details": {
                "error_type": "Unknown",
                "affected_component": "Unknown"
            },
            "analyzed_at": datetime.utcnow().isoformat(),
            "status": AnalysisStatus.COMPLETED.value,
            "demo_mode": True,
        }


# Singleton instance
error_analyzer = ErrorAnalyzer()
