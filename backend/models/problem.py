"""
Problem model for system design challenges.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from backend.database import Base


class Problem(Base):
    """
    System design problem definition.

    Attributes:
        id: Primary key
        title: Problem title (e.g., "Design a URL Shortener")
        description: Full problem description with requirements
        difficulty: Difficulty level (easy, medium, hard)
        expected_schema: JSON schema that valid solutions should match
        expected_api_spec: Expected API specification (OpenAPI-like format)
        validation_rules: Custom validation rules for this problem
        hints: Optional hints for candidates
        created_at: Problem creation timestamp
    """
    __tablename__ = "problems"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    difficulty = Column(String(50), default="medium")

    # Expected solution structure (for validation)
    expected_schema = Column(JSONB, nullable=True)
    expected_api_spec = Column(JSONB, nullable=True)
    validation_rules = Column(JSONB, nullable=True)

    # Additional metadata
    hints = Column(JSONB, nullable=True)
    tags = Column(JSONB, default=list)  # e.g., ["distributed-systems", "caching"]

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to submissions
    submissions = relationship("Submission", back_populates="problem")

    def __repr__(self) -> str:
        return f"<Problem(id={self.id}, title='{self.title}')>"
