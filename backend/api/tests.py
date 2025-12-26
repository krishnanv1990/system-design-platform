"""
Tests API routes.
Provides access to test results for submissions.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.submission import Submission
from backend.models.test_result import TestResult, TestType, TestStatus
from backend.models.user import User
from backend.schemas.test_result import TestResultResponse, TestSummaryResponse
from backend.auth.jwt_handler import get_current_user

router = APIRouter()


@router.get("/submission/{submission_id}", response_model=List[TestResultResponse])
async def get_submission_tests(
    submission_id: int,
    test_type: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all test results for a submission.

    Args:
        submission_id: Submission ID
        test_type: Optional filter by test type (functional, performance, chaos)
        db: Database session
        current_user: Authenticated user

    Returns:
        List of test results
    """
    # Verify submission belongs to user
    submission = db.query(Submission).filter(
        Submission.id == submission_id,
        Submission.user_id == current_user.id,
    ).first()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    query = db.query(TestResult).filter(TestResult.submission_id == submission_id)

    if test_type:
        query = query.filter(TestResult.test_type == test_type)

    results = query.order_by(TestResult.created_at).all()
    return results


@router.get("/submission/{submission_id}/summary", response_model=TestSummaryResponse)
async def get_test_summary(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a summary of all tests for a submission.

    Args:
        submission_id: Submission ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Test summary with counts and breakdown by type
    """
    # Verify submission belongs to user
    submission = db.query(Submission).filter(
        Submission.id == submission_id,
        Submission.user_id == current_user.id,
    ).first()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    # Get all test results
    results = db.query(TestResult).filter(
        TestResult.submission_id == submission_id
    ).all()

    # Categorize results
    functional_tests = [r for r in results if r.test_type == TestType.FUNCTIONAL.value]
    performance_tests = [r for r in results if r.test_type == TestType.PERFORMANCE.value]
    chaos_tests = [r for r in results if r.test_type == TestType.CHAOS.value]

    # Count statuses
    passed = sum(1 for r in results if r.status == TestStatus.PASSED.value)
    failed = sum(1 for r in results if r.status == TestStatus.FAILED.value)
    errors = sum(1 for r in results if r.status == TestStatus.ERROR.value)
    skipped = sum(1 for r in results if r.status == TestStatus.SKIPPED.value)

    # Determine overall status
    if errors > 0 or failed > 0:
        if passed > 0:
            overall_status = "partial"
        else:
            overall_status = "failed"
    elif passed > 0:
        overall_status = "passed"
    else:
        overall_status = "pending"

    return TestSummaryResponse(
        submission_id=submission_id,
        total_tests=len(results),
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        functional_tests=functional_tests,
        performance_tests=performance_tests,
        chaos_tests=chaos_tests,
        overall_status=overall_status,
    )


@router.get("/{test_id}", response_model=TestResultResponse)
async def get_test_result(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific test result by ID.

    Args:
        test_id: Test result ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Test result details
    """
    result = db.query(TestResult).filter(TestResult.id == test_id).first()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test result not found"
        )

    # Verify the test belongs to user's submission
    submission = db.query(Submission).filter(
        Submission.id == result.submission_id,
        Submission.user_id == current_user.id,
    ).first()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test result not found"
        )

    return result
