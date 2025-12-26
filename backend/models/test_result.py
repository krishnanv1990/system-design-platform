"""
Test result model for storing evaluation outcomes.
"""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from backend.database import Base


class TestType(str, Enum):
    """Types of tests run against candidate solutions."""
    FUNCTIONAL = "functional"
    PERFORMANCE = "performance"
    CHAOS = "chaos"


class TestStatus(str, Enum):
    """Test execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class TestResult(Base):
    """
    Individual test result for a submission.

    Attributes:
        id: Primary key
        submission_id: Reference to the parent submission
        test_type: Category of test (functional, performance, chaos)
        test_name: Human-readable test name
        status: Test outcome
        details: Detailed test output and metrics
        duration_ms: Test execution time in milliseconds
        created_at: Test execution timestamp
    """
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False)

    test_type = Column(String(50), nullable=False)
    test_name = Column(String(255), nullable=False)
    status = Column(String(50), default=TestStatus.PENDING.value)

    # Detailed results and metrics
    details = Column(JSONB, nullable=True)

    # Performance metrics
    duration_ms = Column(Integer, nullable=True)

    # For chaos tests: what failure was simulated
    chaos_scenario = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    submission = relationship("Submission", back_populates="test_results")

    def __repr__(self) -> str:
        return f"<TestResult(id={self.id}, test_name='{self.test_name}', status='{self.status}')>"
