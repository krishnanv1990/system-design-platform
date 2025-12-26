"""
Submissions API routes.
Handles solution submissions and their lifecycle.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.problem import Problem
from backend.models.submission import Submission, SubmissionStatus
from backend.models.user import User
from backend.schemas.submission import (
    SubmissionCreate,
    SubmissionResponse,
    SubmissionDetailResponse,
    ValidationRequest,
    ValidationResponse,
)
from backend.auth.jwt_handler import get_current_user
from backend.services.validation_service import ValidationService
from backend.services.orchestrator import SubmissionOrchestrator

router = APIRouter()


@router.post("", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    submission_data: SubmissionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new submission and start the evaluation pipeline.

    Args:
        submission_data: Submission data (schema, API spec, design)
        background_tasks: FastAPI background tasks
        db: Database session
        current_user: Authenticated user

    Returns:
        Created submission with initial status
    """
    # Verify problem exists
    problem = db.query(Problem).filter(Problem.id == submission_data.problem_id).first()
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Problem not found"
        )

    # Generate unique namespace for this submission
    namespace = f"candidate-{current_user.id}-sub-{submission_data.problem_id}"

    # Create submission
    submission = Submission(
        problem_id=submission_data.problem_id,
        user_id=current_user.id,
        schema_input=submission_data.schema_input,
        api_spec_input=submission_data.api_spec_input,
        design_text=submission_data.design_text,
        namespace=namespace,
        status=SubmissionStatus.PENDING.value,
    )

    db.add(submission)
    db.commit()
    db.refresh(submission)

    # Start the evaluation pipeline in background
    background_tasks.add_task(
        SubmissionOrchestrator.process_submission,
        submission.id,
    )

    return submission


@router.get("", response_model=List[SubmissionResponse])
async def list_submissions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    problem_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List submissions for the current user.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        problem_id: Optional filter by problem
        db: Database session
        current_user: Authenticated user

    Returns:
        List of user's submissions
    """
    query = db.query(Submission).filter(Submission.user_id == current_user.id)

    if problem_id:
        query = query.filter(Submission.problem_id == problem_id)

    submissions = query.order_by(Submission.created_at.desc()).offset(skip).limit(limit).all()
    return submissions


@router.get("/{submission_id}", response_model=SubmissionDetailResponse)
async def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information about a specific submission.

    Args:
        submission_id: Submission ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Detailed submission information
    """
    submission = db.query(Submission).filter(
        Submission.id == submission_id,
        Submission.user_id == current_user.id,
    ).first()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    return submission


@router.post("/validate", response_model=ValidationResponse)
async def validate_submission(
    validation_data: ValidationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Validate a submission without creating it.
    Useful for getting feedback before final submission.

    Args:
        validation_data: Data to validate
        db: Database session
        current_user: Authenticated user

    Returns:
        Validation results with feedback
    """
    # Get problem for validation context
    problem = db.query(Problem).filter(Problem.id == validation_data.problem_id).first()
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Problem not found"
        )

    # Run validation
    validation_service = ValidationService()
    result = await validation_service.validate_all(
        problem=problem,
        schema_input=validation_data.schema_input,
        api_spec_input=validation_data.api_spec_input,
        design_text=validation_data.design_text,
    )

    return result


@router.delete("/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a submission (only allowed for pending submissions).

    Args:
        submission_id: Submission ID
        db: Database session
        current_user: Authenticated user
    """
    submission = db.query(Submission).filter(
        Submission.id == submission_id,
        Submission.user_id == current_user.id,
    ).first()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    # Only allow deletion of pending submissions
    if submission.status != SubmissionStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete submission that is already being processed"
        )

    db.delete(submission)
    db.commit()
