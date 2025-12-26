"""
Test result-related Pydantic schemas.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class TestResultResponse(BaseModel):
    """Schema for individual test result."""
    id: int
    submission_id: int
    test_type: str
    test_name: str
    status: str
    details: Optional[Dict[str, Any]]
    duration_ms: Optional[int]
    chaos_scenario: Optional[str]
    created_at: datetime

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
