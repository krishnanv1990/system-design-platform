"""
User profile API endpoints.
Allows users to view and update their profile, and contact support.
Admin endpoints for managing user bans.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.auth.jwt_handler import get_current_user

router = APIRouter()


# ============ Request/Response Schemas ============

class ProfileResponse(BaseModel):
    """User profile response."""
    id: int
    email: str
    name: Optional[str]
    display_name: Optional[str]
    avatar_url: Optional[str]
    is_banned: bool
    ban_reason: Optional[str]
    banned_at: Optional[datetime]
    created_at: datetime
    linked_providers: List[str]

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    """Request to update user profile."""
    display_name: Optional[str] = None


class ContactSupportRequest(BaseModel):
    """Request to contact support."""
    subject: str
    message: str
    contact_email: Optional[EmailStr] = None


class ContactSupportResponse(BaseModel):
    """Response from contact support."""
    success: bool
    message: str
    ticket_id: Optional[str] = None


class AdminUnbanRequest(BaseModel):
    """Admin request to unban a user."""
    user_id: int
    reason: Optional[str] = None


class AdminUserResponse(BaseModel):
    """Admin view of user."""
    id: int
    email: str
    name: Optional[str]
    display_name: Optional[str]
    is_banned: bool
    ban_reason: Optional[str]
    banned_at: Optional[datetime]
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============ User Profile Endpoints ============

@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Get the current user's profile.

    Returns:
        User profile information
    """
    return ProfileResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        display_name=current_user.display_name,
        avatar_url=current_user.avatar_url,
        is_banned=current_user.is_banned,
        ban_reason=current_user.ban_reason,
        banned_at=current_user.banned_at,
        created_at=current_user.created_at,
        linked_providers=current_user.get_oauth_providers(),
    )


@router.put("/profile", response_model=ProfileResponse)
async def update_profile(
    request: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update the current user's profile.

    Args:
        request: Profile update data
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated user profile
    """
    # Check if user is banned
    if current_user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is suspended. Please contact support."
        )

    # Validate display name
    if request.display_name is not None:
        display_name = request.display_name.strip()
        if len(display_name) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Display name must be 100 characters or less"
            )
        if len(display_name) < 1:
            display_name = None  # Clear display name if empty
        current_user.display_name = display_name

    db.commit()
    db.refresh(current_user)

    return ProfileResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        display_name=current_user.display_name,
        avatar_url=current_user.avatar_url,
        is_banned=current_user.is_banned,
        ban_reason=current_user.ban_reason,
        banned_at=current_user.banned_at,
        created_at=current_user.created_at,
        linked_providers=current_user.get_oauth_providers(),
    )


@router.post("/contact-support", response_model=ContactSupportResponse)
async def contact_support(
    request: ContactSupportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit a support request.

    In production, this would:
    - Create a ticket in a support system (Zendesk, Freshdesk, etc.)
    - Send an email notification to support team
    - Log the request for tracking

    Args:
        request: Support request data
        current_user: Authenticated user

    Returns:
        Confirmation with ticket ID
    """
    import uuid

    # Generate a ticket ID
    ticket_id = f"SDP-{uuid.uuid4().hex[:8].upper()}"

    # Log the support request (in production, integrate with support system)
    print(f"Support request from {current_user.email}:")
    print(f"  Ticket ID: {ticket_id}")
    print(f"  Subject: {request.subject}")
    print(f"  Message: {request.message[:200]}...")
    if request.contact_email:
        print(f"  Contact email: {request.contact_email}")

    # In production, you would:
    # 1. Create ticket in support system
    # 2. Send confirmation email to user
    # 3. Notify support team

    return ContactSupportResponse(
        success=True,
        message="Your support request has been submitted. We'll respond within 24-48 hours.",
        ticket_id=ticket_id,
    )


# ============ Admin Endpoints ============

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin privileges."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


@router.get("/admin/users", response_model=List[AdminUserResponse])
async def list_users(
    banned_only: bool = False,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    List all users (admin only).

    Args:
        banned_only: If True, only return banned users
        db: Database session
        admin_user: Admin user making the request

    Returns:
        List of users
    """
    query = db.query(User)
    if banned_only:
        query = query.filter(User.is_banned.is_(True))

    users = query.order_by(User.created_at.desc()).all()

    return [
        AdminUserResponse(
            id=u.id,
            email=u.email,
            name=u.name,
            display_name=u.display_name,
            is_banned=u.is_banned,
            ban_reason=u.ban_reason,
            banned_at=u.banned_at,
            is_admin=u.is_admin,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.post("/admin/unban", response_model=AdminUserResponse)
async def unban_user(
    request: AdminUnbanRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Unban a user (admin only).

    Args:
        request: Unban request with user ID
        db: Database session
        admin_user: Admin user making the request

    Returns:
        Updated user information
    """
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not banned"
        )

    # Log the unban action
    print(f"Admin {admin_user.email} unbanning user {user.email}")
    print(f"  Previous ban reason: {user.ban_reason}")
    print(f"  Unban reason: {request.reason or 'No reason provided'}")

    # Unban the user
    user.is_banned = False
    user.ban_reason = None
    user.banned_at = None
    db.commit()
    db.refresh(user)

    return AdminUserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        display_name=user.display_name,
        is_banned=user.is_banned,
        ban_reason=user.ban_reason,
        banned_at=user.banned_at,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )


@router.post("/admin/ban")
async def ban_user(
    user_id: int,
    reason: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Ban a user (admin only).

    Args:
        user_id: User ID to ban
        reason: Ban reason
        db: Database session
        admin_user: Admin user making the request

    Returns:
        Updated user information
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot ban admin users"
        )

    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already banned"
        )

    # Log the ban action
    print(f"Admin {admin_user.email} banning user {user.email}")
    print(f"  Reason: {reason}")

    # Ban the user
    user.is_banned = True
    user.ban_reason = reason
    user.banned_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    return AdminUserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        display_name=user.display_name,
        is_banned=user.is_banned,
        ban_reason=user.ban_reason,
        banned_at=user.banned_at,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )
