"""
Problems API routes.
CRUD operations for system design problems.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.problem import Problem
from backend.models.user import User
from backend.schemas.problem import (
    ProblemCreate,
    ProblemUpdate,
    ProblemResponse,
    ProblemListResponse,
)
from backend.auth.jwt_handler import get_current_user, get_current_user_optional

router = APIRouter()


@router.get("", response_model=List[ProblemListResponse])
async def list_problems(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    difficulty: Optional[str] = None,
    tag: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    List all problems with optional filtering.

    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        difficulty: Filter by difficulty level
        tag: Filter by tag
        db: Database session

    Returns:
        List of problems (without validation rules for security)
    """
    query = db.query(Problem)

    if difficulty:
        query = query.filter(Problem.difficulty == difficulty)

    if tag:
        # Filter problems that contain the specified tag
        query = query.filter(Problem.tags.contains([tag]))

    problems = query.offset(skip).limit(limit).all()
    return problems


@router.get("/{problem_id}", response_model=ProblemResponse)
async def get_problem(
    problem_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Get a specific problem by ID.

    Args:
        problem_id: Problem ID
        db: Database session
        current_user: Optional authenticated user

    Returns:
        Problem details (includes hints if authenticated)
    """
    problem = db.query(Problem).filter(Problem.id == problem_id).first()

    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Problem not found"
        )

    return problem


@router.post("", response_model=ProblemResponse, status_code=status.HTTP_201_CREATED)
async def create_problem(
    problem_data: ProblemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new problem (admin only in production).

    Args:
        problem_data: Problem creation data
        db: Database session
        current_user: Authenticated user

    Returns:
        Created problem
    """
    # TODO: Add admin role check in production

    problem = Problem(
        title=problem_data.title,
        description=problem_data.description,
        difficulty=problem_data.difficulty,
        expected_schema=problem_data.expected_schema,
        expected_api_spec=problem_data.expected_api_spec,
        validation_rules=problem_data.validation_rules,
        hints=problem_data.hints,
        tags=problem_data.tags or [],
    )

    db.add(problem)
    db.commit()
    db.refresh(problem)

    return problem


@router.put("/{problem_id}", response_model=ProblemResponse)
async def update_problem(
    problem_id: int,
    problem_data: ProblemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update an existing problem (admin only in production).

    Args:
        problem_id: Problem ID
        problem_data: Problem update data
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated problem
    """
    # TODO: Add admin role check in production

    problem = db.query(Problem).filter(Problem.id == problem_id).first()

    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Problem not found"
        )

    # Update only provided fields
    update_data = problem_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(problem, field, value)

    db.commit()
    db.refresh(problem)

    return problem


@router.delete("/{problem_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_problem(
    problem_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a problem (admin only in production).

    Args:
        problem_id: Problem ID
        db: Database session
        current_user: Authenticated user
    """
    # TODO: Add admin role check in production

    problem = db.query(Problem).filter(Problem.id == problem_id).first()

    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Problem not found"
        )

    db.delete(problem)
    db.commit()
