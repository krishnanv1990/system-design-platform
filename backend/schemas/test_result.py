"""
Test result-related Pydantic schemas.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

from backend.schemas.error_analysis import ErrorAnalysisResponse


class TestResultResponse(BaseModel):
    """Schema for individual test result."""
    id: int
    submission_id: int
    test_type: str
    test_name: str
    status: str
    details: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None
    chaos_scenario: Optional[str] = None
    created_at: datetime

    # Error analysis fields
    error_category: Optional[str] = None
    error_analysis: Optional[Dict[str, Any]] = None
    ai_analysis_status: Optional[str] = None

    class Config:
        from_attributes = True


class TestSummaryResponse(BaseModel):
    """Schema for test summary across all test types."""
    submission_id: int
    total_tests: int
    passed: int
    failed: int
    errors: int
    skipped: int

    # Breakdown by test type
    functional_tests: List[TestResultResponse]
    performance_tests: List[TestResultResponse]
    chaos_tests: List[TestResultResponse]

    # Overall status
    overall_status: str  # passed, failed, partial

    # Error analysis summary
    issues_by_category: Dict[str, int] = {
        "user_solution": 0,
        "platform": 0,
        "deployment": 0,
        "unknown": 0
    }
    has_platform_issues: bool = False  # True if any failures are platform/deployment related
