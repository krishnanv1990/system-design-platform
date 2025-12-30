"""
Submission model for candidate solutions.

Supports two types of submissions:
1. System Design: Schema, API spec, and design canvas
2. Distributed Consensus: Source code in a specific language
"""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from backend.database import Base


class SubmissionStatus(str, Enum):
    """Status of a submission through the evaluation pipeline."""
    PENDING = "pending"
    VALIDATING = "validating"
    VALIDATION_FAILED = "validation_failed"
    GENERATING_INFRA = "generating_infra"
    BUILDING = "building"  # For distributed consensus: compiling code
    BUILD_FAILED = "build_failed"
    DEPLOYING = "deploying"
    DEPLOY_FAILED = "deploy_failed"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"


class SubmissionType(str, Enum):
    """Type of submission."""
    SYSTEM_DESIGN = "system_design"
    DISTRIBUTED_CONSENSUS = "distributed_consensus"


class Submission(Base):
    """
    Candidate's solution submission.

    Supports two submission types:
    1. System Design: Schema, API spec, design canvas
    2. Distributed Consensus: Source code implementation

    Attributes:
        id: Primary key
        problem_id: Reference to the problem being solved
        user_id: Reference to the submitting user
        submission_type: Type of submission (system_design or distributed_consensus)

        # System Design fields:
        schema_input: Candidate's database schema design
        api_spec_input: Candidate's API specification
        design_text: Free-form design description

        # Distributed Consensus fields:
        language: Selected programming language
        source_code: Candidate's implementation code
        build_logs: Compilation output and logs
        cluster_node_urls: URLs for each cluster node

        # Common fields:
        generated_terraform: Terraform code generated from design
        deployment_id: GCP resource identifier for deployed solution
        status: Current status in the evaluation pipeline
        error_message: Error details if submission failed
        created_at: Submission timestamp
    """
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    submission_type = Column(String(50), default=SubmissionType.SYSTEM_DESIGN.value)

    # System Design solution inputs
    schema_input = Column(JSONB, nullable=True)
    api_spec_input = Column(JSONB, nullable=True)
    design_text = Column(Text, nullable=True)

    # Distributed Consensus solution inputs
    language = Column(String(20), nullable=True)  # python, go, java, cpp, rust
    source_code = Column(Text, nullable=True)  # The implementation code
    build_logs = Column(Text, nullable=True)  # Compilation output
    build_artifact_url = Column(String(512), nullable=True)  # GCS URL of built artifact
    cluster_node_urls = Column(JSONB, nullable=True)  # ["http://node1:8080", "http://node2:8080", ...]

    # Generated infrastructure code
    generated_terraform = Column(Text, nullable=True)

    # Deployment tracking
    deployment_id = Column(String(255), nullable=True)
    namespace = Column(String(255), nullable=True)  # Candidate isolation namespace
    endpoint_url = Column(String(512), nullable=True)  # Deployed service URL (or leader URL for clusters)

    # Status and errors
    status = Column(String(50), default=SubmissionStatus.PENDING.value)
    error_message = Column(Text, nullable=True)

    # AI validation feedback
    validation_feedback = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    problem = relationship("Problem", back_populates="submissions")
    user = relationship("User", back_populates="submissions")
    test_results = relationship("TestResult", back_populates="submission")

    def __repr__(self) -> str:
        return f"<Submission(id={self.id}, status='{self.status}')>"
