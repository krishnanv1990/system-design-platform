"""
SQLAlchemy ORM models for the system design platform.
"""

from backend.models.user import User
from backend.models.problem import Problem
from backend.models.submission import Submission
from backend.models.test_result import TestResult

__all__ = ["User", "Problem", "Submission", "TestResult"]
