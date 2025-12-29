"""
User-related Pydantic schemas.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    """Schema for creating a new user (from OAuth)."""
    google_id: str
    email: EmailStr
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(BaseModel):
    """Schema for user response."""
    id: int
    email: str
    name: Optional[str]
    display_name: Optional[str] = None
    avatar_url: Optional[str]
    created_at: datetime
    # Optional fields for OAuth provider IDs
    google_id: Optional[str] = None
    facebook_id: Optional[str] = None
    linkedin_id: Optional[str] = None
    github_id: Optional[str] = None
    # Ban status (optional in some contexts)
    is_banned: Optional[bool] = None
    ban_reason: Optional[str] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
