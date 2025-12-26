"""
Pydantic schemas for error analysis.
Used for API request/response validation.
"""

from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class ErrorCategoryEnum(str, Enum):
    """Categories for test failure root causes."""
    USER_SOLUTION = "user_solution"
    PLATFORM = "platform"
    DEPLOYMENT = "deployment"
    UNKNOWN = "unknown"


class AnalysisStatusEnum(str, Enum):
    """Status of AI error analysis."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TechnicalDetails(BaseModel):
    """Technical details about the error."""
    error_type: Optional[str] = None
    affected_component: Optional[str] = None


class ErrorAnalysisResponse(BaseModel):
    """Response model for error analysis results."""
    category: ErrorCategoryEnum = Field(
        description="Root cause category of the failure"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence level of the analysis (0-1)"
    )
    explanation: str = Field(
        description="Human-readable explanation of what went wrong"
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Actionable suggestions for fixing the issue"
    )
    technical_details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Technical details about the error"
    )
    analyzed_at: Optional[str] = Field(
        default=None,
        description="Timestamp when the analysis was performed"
    )
    status: AnalysisStatusEnum = Field(
        default=AnalysisStatusEnum.PENDING,
        description="Status of the analysis"
    )
    demo_mode: Optional[bool] = Field(
        default=None,
        description="Whether this was a demo/mock analysis"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "category": "user_solution",
                "confidence": 0.85,
                "explanation": "The API response didn't match the expected format.",
                "suggestions": [
                    "Review the API specification",
                    "Check that all required fields are included"
                ],
                "technical_details": {
                    "error_type": "AssertionError",
                    "affected_component": "API Response"
                },
                "analyzed_at": "2025-12-26T10:00:00",
                "status": "completed"
            }
        }
