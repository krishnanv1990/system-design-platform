"""
Problem-related Pydantic schemas.

Supports difficulty levels mapped to engineering levels:
- easy: L5 SWE (Senior Software Engineer)
- medium: L6 SWE (Staff Engineer)
- hard: L7 SWE (Principal Engineer)
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


# Valid difficulty levels
DifficultyLevel = Literal["easy", "medium", "hard"]


class DifficultyLevelInfo(BaseModel):
    """Information about a difficulty level."""
    level: str = Field(description="Engineering level (L5/L6/L7)")
    title: str = Field(description="Level title (e.g., 'Senior Software Engineer')")
    description: str = Field(description="Brief description of expectations")


class DifficultyRequirements(BaseModel):
    """Requirements specific to a difficulty level."""
    focus_areas: List[str] = Field(
        default_factory=list,
        description="Key areas to focus on at this level"
    )
    expected_components: List[str] = Field(
        default_factory=list,
        description="Components expected in the design"
    )
    evaluation_criteria: List[str] = Field(
        default_factory=list,
        description="Criteria used to evaluate the design"
    )
    scale_requirements: Optional[str] = Field(
        default=None,
        description="Scale/performance requirements"
    )
    additional_considerations: Optional[List[str]] = Field(
        default=None,
        description="Additional points to consider"
    )


class ProblemCreate(BaseModel):
    """Schema for creating a new problem."""
    title: str
    description: str
    difficulty: DifficultyLevel = "medium"
    difficulty_requirements: Optional[Dict[str, DifficultyRequirements]] = None
    expected_schema: Optional[Dict[str, Any]] = None
    expected_api_spec: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None
    hints: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class ProblemUpdate(BaseModel):
    """Schema for updating a problem."""
    title: Optional[str] = None
    description: Optional[str] = None
    difficulty: Optional[DifficultyLevel] = None
    difficulty_requirements: Optional[Dict[str, DifficultyRequirements]] = None
    expected_schema: Optional[Dict[str, Any]] = None
    expected_api_spec: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None
    hints: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class ProblemResponse(BaseModel):
    """Schema for problem response with full details."""
    id: int
    title: str
    description: str
    difficulty: str
    difficulty_requirements: Optional[Dict[str, Any]] = None
    difficulty_info: Optional[DifficultyLevelInfo] = None
    expected_schema: Optional[Dict[str, Any]]
    expected_api_spec: Optional[Dict[str, Any]]
    hints: Optional[List[str]]
    tags: Optional[List[str]]
    created_at: datetime

    class Config:
        from_attributes = True


class ProblemListResponse(BaseModel):
    """Schema for problem list response (without validation rules)."""
    id: int
    title: str
    description: str
    difficulty: str
    difficulty_info: Optional[DifficultyLevelInfo] = None
    tags: Optional[List[str]]
    created_at: datetime

    class Config:
        from_attributes = True
