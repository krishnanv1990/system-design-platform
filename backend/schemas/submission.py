"""
Submission-related Pydantic schemas.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class SubmissionCreate(BaseModel):
    """Schema for creating a new submission."""
    problem_id: int
    schema_input: Optional[Dict[str, Any]] = None
    api_spec_input: Optional[Dict[str, Any]] = None
    design_text: Optional[str] = None
    validation_feedback: Optional[Dict[str, Any]] = None  # Pre-validated results from frontend


class SubmissionResponse(BaseModel):
    """Schema for basic submission response."""
    id: int
    problem_id: int
    user_id: int
    status: str
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SubmissionDetailResponse(BaseModel):
    """Schema for detailed submission response."""
    id: int
    problem_id: int
    user_id: int
    schema_input: Optional[Dict[str, Any]]
    api_spec_input: Optional[Dict[str, Any]]
    design_text: Optional[str]
    generated_terraform: Optional[str]
    deployment_id: Optional[str]
    namespace: Optional[str]
    status: str
    error_message: Optional[str]
    validation_feedback: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ValidationRequest(BaseModel):
    """Schema for validation request."""
    problem_id: int
    schema_input: Optional[Dict[str, Any]] = None
    api_spec_input: Optional[Dict[str, Any]] = None
    design_text: Optional[str] = None


class ValidationResponse(BaseModel):
    """Schema for validation response."""
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    suggestions: List[str] = []
    score: Optional[float] = None  # 0-100 score if applicable
