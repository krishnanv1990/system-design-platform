"""
Problem model for system design challenges and distributed systems problems.

Supports multiple difficulty levels mapped to engineering levels:
- easy: L5 SWE (Senior Software Engineer)
- medium: L6 SWE (Staff Engineer)
- hard: L7 SWE (Principal Engineer)

Problem types:
- system_design: Traditional system design problems (schema, API, architecture)
- distributed_consensus: Distributed consensus algorithm implementations (Raft, Paxos)
"""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship

from backend.database import Base


class ProblemType(str, Enum):
    """Type of problem."""
    SYSTEM_DESIGN = "system_design"
    DISTRIBUTED_CONSENSUS = "distributed_consensus"


class SupportedLanguage(str, Enum):
    """Supported programming languages for distributed systems problems."""
    PYTHON = "python"
    GO = "go"
    JAVA = "java"
    CPP = "cpp"
    RUST = "rust"


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
    Problem definition for system design and distributed consensus problems.

    Attributes:
        id: Primary key
        title: Problem title (e.g., "Design a URL Shortener" or "Implement Raft Consensus")
        description: Full problem description with requirements
        problem_type: Type of problem (system_design or distributed_consensus)
        difficulty: Difficulty level (easy, medium, hard) mapping to L5/L6/L7
        difficulty_requirements: Level-specific requirements for each difficulty
        expected_schema: JSON schema that valid solutions should match (system_design only)
        expected_api_spec: Expected API specification (system_design only)
        validation_rules: Custom validation rules for this problem
        hints: Optional hints for candidates

        # Distributed consensus specific fields:
        grpc_proto: gRPC proto file content (distributed_consensus only)
        supported_languages: List of supported languages (distributed_consensus only)
        cluster_size: Number of nodes for the cluster (3 or 5)
        language_templates: Code templates for each language
        test_scenarios: Test scenarios for distributed system testing

        created_at: Problem creation timestamp
    """
    __tablename__ = "problems"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    problem_type = Column(String(50), default=ProblemType.SYSTEM_DESIGN.value)
    difficulty = Column(String(50), default="medium")

    # Level-specific requirements for easy (L5), medium (L6), hard (L7)
    # Structure: {"easy": {...}, "medium": {...}, "hard": {...}}
    difficulty_requirements = Column(JSONB, nullable=True)

    # Expected solution structure (for validation) - system_design problems
    expected_schema = Column(JSONB, nullable=True)
    expected_api_spec = Column(JSONB, nullable=True)
    validation_rules = Column(JSONB, nullable=True)

    # Distributed consensus specific fields
    grpc_proto = Column(Text, nullable=True)  # Proto file content
    supported_languages = Column(JSONB, nullable=True)  # ["python", "go", "java", "cpp", "rust"]
    cluster_size = Column(Integer, nullable=True)  # 3 or 5 nodes
    language_templates = Column(JSONB, nullable=True)  # {"python": "...", "go": "...", ...}
    test_scenarios = Column(JSONB, nullable=True)  # Distributed system test scenarios

    # Additional metadata
    hints = Column(JSONB, nullable=True)
    tags = Column(JSONB, default=list)  # e.g., ["distributed-systems", "consensus"]

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
