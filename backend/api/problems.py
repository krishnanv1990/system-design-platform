"""
Problems API routes.
CRUD operations for system design problems.

Supports difficulty levels mapped to engineering levels:
- easy: L5 SWE (Senior Software Engineer)
- medium: L6 SWE (Staff Engineer)
- hard: L7 SWE (Principal Engineer)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.problem import Problem, DIFFICULTY_LEVELS
from backend.models.user import User
from backend.schemas.problem import (
    ProblemCreate,
    ProblemUpdate,
    ProblemResponse,
    ProblemListResponse,
    DifficultyLevelInfo,
)
from backend.auth.jwt_handler import get_current_user, get_current_user_optional

router = APIRouter()


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin privileges for problem management."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to manage problems"
        )
    return current_user


def get_difficulty_info(difficulty: str) -> Optional[DifficultyLevelInfo]:
    """
    Get difficulty level info for a given difficulty.

    Args:
        difficulty: Difficulty level (easy/medium/hard)

    Returns:
        DifficultyLevelInfo with level, title, and description
    """
    if difficulty in DIFFICULTY_LEVELS:
        level_data = DIFFICULTY_LEVELS[difficulty]
        return DifficultyLevelInfo(
            level=level_data["level"],
            title=level_data["title"],
            description=level_data["description"],
        )
    return None


def problem_to_response(problem: Problem) -> dict:
    """
    Convert a Problem model to a response dict with difficulty info.

    Args:
        problem: Problem model instance

    Returns:
        Dict ready for ProblemResponse serialization
    """
    return {
        "id": problem.id,
        "title": problem.title,
        "description": problem.description,
        "difficulty": problem.difficulty,
        "difficulty_requirements": problem.difficulty_requirements,
        "difficulty_info": get_difficulty_info(problem.difficulty),
        "expected_schema": problem.expected_schema,
        "expected_api_spec": problem.expected_api_spec,
        "hints": problem.hints,
        "tags": problem.tags,
        "created_at": problem.created_at,
    }


def problem_to_list_response(problem: Problem) -> dict:
    """
    Convert a Problem model to a list response dict with difficulty info.

    Args:
        problem: Problem model instance

    Returns:
        Dict ready for ProblemListResponse serialization
    """
    return {
        "id": problem.id,
        "title": problem.title,
        "description": problem.description,
        "difficulty": problem.difficulty,
        "difficulty_info": get_difficulty_info(problem.difficulty),
        "tags": problem.tags,
        "created_at": problem.created_at,
    }


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
        difficulty: Filter by difficulty level (easy/medium/hard)
        tag: Filter by tag
        db: Database session

    Returns:
        List of problems with difficulty level info (L5/L6/L7)
    """
    query = db.query(Problem)

    if difficulty:
        query = query.filter(Problem.difficulty == difficulty)

    if tag:
        # Filter problems that contain the specified tag
        query = query.filter(Problem.tags.contains([tag]))

    problems = query.offset(skip).limit(limit).all()

    # Add difficulty level info to each problem
    return [problem_to_list_response(p) for p in problems]


@router.get("/{problem_id}", response_model=ProblemResponse)
async def get_problem(
    problem_id: int,
    selected_difficulty: Optional[str] = Query(
        None,
        description="Override difficulty level (easy/medium/hard)"
    ),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Get a specific problem by ID.

    Args:
        problem_id: Problem ID
        selected_difficulty: Optional difficulty level override
        db: Database session
        current_user: Optional authenticated user

    Returns:
        Problem details with difficulty level info (L5/L6/L7)
    """
    problem = db.query(Problem).filter(Problem.id == problem_id).first()

    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Problem not found"
        )

    response = problem_to_response(problem)

    # If a specific difficulty is selected, use that for difficulty_info
    if selected_difficulty and selected_difficulty in DIFFICULTY_LEVELS:
        response["difficulty_info"] = get_difficulty_info(selected_difficulty)

    return response


@router.post("", response_model=ProblemResponse, status_code=status.HTTP_201_CREATED)
async def create_problem(
    problem_data: ProblemCreate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Create a new problem (admin only).

    Args:
        problem_data: Problem creation data
        db: Database session
        admin_user: Authenticated admin user

    Returns:
        Created problem with difficulty level info
    """

    # Convert difficulty_requirements to dict if provided
    difficulty_reqs = None
    if problem_data.difficulty_requirements:
        difficulty_reqs = {
            k: v.model_dump() if hasattr(v, 'model_dump') else v
            for k, v in problem_data.difficulty_requirements.items()
        }

    problem = Problem(
        title=problem_data.title,
        description=problem_data.description,
        difficulty=problem_data.difficulty,
        difficulty_requirements=difficulty_reqs,
        expected_schema=problem_data.expected_schema,
        expected_api_spec=problem_data.expected_api_spec,
        validation_rules=problem_data.validation_rules,
        hints=problem_data.hints,
        tags=problem_data.tags or [],
    )

    db.add(problem)
    db.commit()
    db.refresh(problem)

    return problem_to_response(problem)


@router.put("/{problem_id}", response_model=ProblemResponse)
async def update_problem(
    problem_id: int,
    problem_data: ProblemUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Update an existing problem (admin only).

    Args:
        problem_id: Problem ID
        problem_data: Problem update data
        db: Database session
        admin_user: Authenticated admin user

    Returns:
        Updated problem with difficulty level info
    """

    problem = db.query(Problem).filter(Problem.id == problem_id).first()

    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Problem not found"
        )

    # Update only provided fields
    update_data = problem_data.model_dump(exclude_unset=True)

    # Handle difficulty_requirements conversion
    if "difficulty_requirements" in update_data and update_data["difficulty_requirements"]:
        update_data["difficulty_requirements"] = {
            k: v.model_dump() if hasattr(v, 'model_dump') else v
            for k, v in update_data["difficulty_requirements"].items()
        }

    for field, value in update_data.items():
        setattr(problem, field, value)

    db.commit()
    db.refresh(problem)

    return problem_to_response(problem)


@router.delete("/{problem_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_problem(
    problem_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Delete a problem (admin only).

    Args:
        problem_id: Problem ID
        db: Database session
        admin_user: Authenticated admin user
    """

    problem = db.query(Problem).filter(Problem.id == problem_id).first()

    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Problem not found"
        )

    db.delete(problem)
    db.commit()
