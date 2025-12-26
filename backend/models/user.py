"""
User model for authentication and profile management.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship

from backend.database import Base


class User(Base):
    """
    User model representing authenticated users.

    Attributes:
        id: Primary key
        google_id: Unique Google OAuth identifier
        email: User's email address (unique)
        name: Display name
        avatar_url: Profile picture URL from Google
        created_at: Account creation timestamp
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    google_id = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    avatar_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to submissions
    submissions = relationship("Submission", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"
