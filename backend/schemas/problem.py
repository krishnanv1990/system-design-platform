"""
Problem-related Pydantic schemas.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class ProblemCreate(BaseModel):
    """Schema for creating a new problem."""
    title: str
    description: str
    difficulty: str = "medium"
    expected_schema: Optional[Dict[str, Any]] = None
    expected_api_spec: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None
    hints: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class ProblemUpdate(BaseModel):
    """Schema for updating a problem."""
    title: Optional[str] = None
    description: Optional[str] = None
    difficulty: Optional[str] = None
    expected_schema: Optional[Dict[str, Any]] = None
    expected_api_spec: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None
    hints: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class ProblemResponse(BaseModel):
    """Schema for problem response."""
    id: int
    title: str
    description: str
    difficulty: str
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
    tags: Optional[List[str]]
    created_at: datetime

    class Config:
        from_attributes = True
