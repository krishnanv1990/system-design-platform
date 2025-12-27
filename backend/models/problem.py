"""
Problem model for system design challenges.

Supports multiple difficulty levels mapped to engineering levels:
- easy: L5 SWE (Senior Software Engineer)
- medium: L6 SWE (Staff Engineer)
- hard: L7 SWE (Principal Engineer)
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from backend.database import Base


# Difficulty level mapping to engineering levels
DIFFICULTY_LEVELS = {
    "easy": {
        "level": "L5",
        "title": "Senior Software Engineer",
        "description": "Focus on core functionality with basic scalability",
    },
    "medium": {
        "level": "L6",
        "title": "Staff Engineer",
        "description": "Production-ready design with high availability",
    },
    "hard": {
        "level": "L7",
        "title": "Principal Engineer",
        "description": "Global-scale architecture with advanced optimizations",
    },
}


class Problem(Base):
    """
    System design problem definition.

    Attributes:
        id: Primary key
        title: Problem title (e.g., "Design a URL Shortener")
        description: Full problem description with requirements
        difficulty: Difficulty level (easy, medium, hard) mapping to L5/L6/L7
        difficulty_requirements: Level-specific requirements for each difficulty
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

    # Level-specific requirements for easy (L5), medium (L6), hard (L7)
    # Structure: {"easy": {...}, "medium": {...}, "hard": {...}}
    difficulty_requirements = Column(JSONB, nullable=True)

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

    def get_requirements_for_difficulty(self, level: str = None) -> dict:
        """
        Get requirements for a specific difficulty level.

        Args:
            level: Difficulty level (easy/medium/hard). If None, uses problem's difficulty.

        Returns:
            Dict with requirements for the specified level
        """
        target_level = level or self.difficulty
        if self.difficulty_requirements and target_level in self.difficulty_requirements:
            return self.difficulty_requirements[target_level]
        return {}

    def __repr__(self) -> str:
        return f"<Problem(id={self.id}, title='{self.title}')>"
