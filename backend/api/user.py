"""
User profile API endpoints.
Allows users to view and update their profile, and contact support.
Admin endpoints for managing user bans.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.models.audit_log import AuditLog, UsageCost
from backend.services.audit_service import AuditService
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


class UsageCostItem(BaseModel):
    """Single usage cost item."""
    id: int
    category: str
    quantity: float
    unit: str
    unit_cost_usd: float
    total_cost_usd: float
    details: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class UsageCostSummary(BaseModel):
    """Summary of usage costs by category."""
    category: str
    total_quantity: float
    unit: str
    total_cost_usd: float


class UsageCostResponse(BaseModel):
    """Response with user's usage costs."""
    total_cost_usd: float
    start_date: datetime
    end_date: datetime
    by_category: List[UsageCostSummary]
    recent_items: List[UsageCostItem]


class AuditLogItem(BaseModel):
    """Single audit log item."""
    id: int
    action: str
    resource_type: Optional[str]
    resource_id: Optional[int]
    details: Optional[Dict[str, Any]]
    request_path: Optional[str]
    request_method: Optional[str]
    response_status: Optional[int]
    duration_ms: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    """Response with user's audit logs."""
    total_count: int
    items: List[AuditLogItem]


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


# ============ Usage Cost Endpoints ============

@router.get("/usage", response_model=UsageCostResponse)
async def get_usage_costs(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the current user's usage costs.

    Returns a summary of costs by category and recent cost items.

    Args:
        days: Number of days to look back (1-365, default 30)
        db: Database session
        current_user: Authenticated user

    Returns:
        UsageCostResponse with cost breakdown
    """
    audit_service = AuditService(db)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get cost summary
    cost_data = audit_service.get_user_costs(
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
    )

    # Get recent cost items (last 50)
    recent_costs = (
        db.query(UsageCost)
        .filter(UsageCost.user_id == current_user.id)
        .filter(UsageCost.created_at >= start_date)
        .order_by(UsageCost.created_at.desc())
        .limit(50)
        .all()
    )

    # Convert categories dict to by_category list
    categories = cost_data.get("categories", {})
    by_category = [
        UsageCostSummary(
            category=cat_name,
            total_quantity=float(cat_data["quantity"]),
            unit="tokens" if "tokens" in cat_name else "units",
            total_cost_usd=float(cat_data["cost_usd"]),
        )
        for cat_name, cat_data in categories.items()
    ]

    return UsageCostResponse(
        total_cost_usd=float(cost_data.get("total_cost_usd", 0)),
        start_date=start_date,
        end_date=end_date,
        by_category=by_category,
        recent_items=[
            UsageCostItem(
                id=cost.id,
                category=cost.category,
                quantity=float(cost.quantity),
                unit=cost.unit,
                unit_cost_usd=float(cost.unit_cost_usd),
                total_cost_usd=float(cost.total_cost_usd),
                details=cost.details,
                created_at=cost.created_at,
            )
            for cost in recent_costs
        ],
    )


@router.get("/activity", response_model=AuditLogResponse)
async def get_activity_log(
    days: int = Query(default=7, ge=1, le=90, description="Number of days to look back"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of items to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the current user's activity log.

    Returns recent actions performed by the user.

    Args:
        days: Number of days to look back (1-90, default 7)
        limit: Maximum number of items to return (1-100, default 50)
        db: Database session
        current_user: Authenticated user

    Returns:
        AuditLogResponse with activity items
    """
    start_date = datetime.utcnow() - timedelta(days=days)

    # Get total count
    total_count = (
        db.query(AuditLog)
        .filter(AuditLog.user_id == current_user.id)
        .filter(AuditLog.created_at >= start_date)
        .count()
    )

    # Get recent items
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.user_id == current_user.id)
        .filter(AuditLog.created_at >= start_date)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )

    return AuditLogResponse(
        total_count=total_count,
        items=[
            AuditLogItem(
                id=log.id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                details=log.details,
                request_path=log.request_path,
                request_method=log.request_method,
                response_status=log.response_status,
                duration_ms=log.duration_ms,
                created_at=log.created_at,
            )
            for log in logs
        ],
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
