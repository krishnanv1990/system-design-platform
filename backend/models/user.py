"""
User model for authentication and profile management.
Supports multiple OAuth providers (Google, Facebook, LinkedIn, GitHub).
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.orm import relationship

from backend.database import Base


class User(Base):
    """
    User model representing authenticated users.

    Supports authentication via multiple OAuth providers. Users are uniquely
    identified by their email address, but may link multiple OAuth accounts.

    Attributes:
        id: Primary key
        email: User's email address (unique, required)
        name: Display name from OAuth provider
        display_name: User-customizable display name
        avatar_url: Profile picture URL from OAuth provider
        google_id: Unique Google OAuth identifier (optional)
        facebook_id: Unique Facebook OAuth identifier (optional)
        linkedin_id: Unique LinkedIn OAuth identifier (optional)
        github_id: Unique GitHub OAuth identifier (optional)
        is_banned: Whether user is banned from using the platform
        ban_reason: Reason for the ban
        banned_at: Timestamp when user was banned
        is_admin: Whether user has admin privileges
        created_at: Account creation timestamp
    """
    __tablename__ = "users"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # User profile (email is the primary unique identifier)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    display_name = Column(String(100), nullable=True)  # User-customizable display name
    avatar_url = Column(String(512), nullable=True)

    # OAuth provider identifiers (nullable - user may have any combination)
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    facebook_id = Column(String(255), unique=True, nullable=True, index=True)
    linkedin_id = Column(String(255), unique=True, nullable=True, index=True)
    github_id = Column(String(255), unique=True, nullable=True, index=True)

    # Ban status
    is_banned = Column(Boolean, default=False, nullable=False)
    ban_reason = Column(Text, nullable=True)
    banned_at = Column(DateTime, nullable=True)

    # Admin status
    is_admin = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to submissions
    submissions = relationship("Submission", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"

    def get_oauth_providers(self) -> list[str]:
        """
        Get list of linked OAuth providers for this user.

        Returns:
            List of provider names that are linked to this account
        """
        providers = []
        if self.google_id:
            providers.append("google")
        if self.facebook_id:
            providers.append("facebook")
        if self.linkedin_id:
            providers.append("linkedin")
        if self.github_id:
            providers.append("github")
        return providers

    def get_display_name(self) -> str:
        """
        Get the user's display name, falling back to name or email.

        Returns:
            Display name to show in the UI
        """
        if self.display_name:
            return self.display_name
        if self.name:
            return self.name
        # Fall back to email prefix
        return self.email.split("@")[0]
