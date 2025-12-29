"""
Audit Log model for tracking user actions and usage costs.
Provides comprehensive logging for security, debugging, and billing.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Numeric, Index, JSON
from sqlalchemy.orm import relationship

from backend.database import Base


class ActionType(str, Enum):
    """Types of user actions that are audited."""
    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"

    # Problem actions
    VIEW_PROBLEM = "view_problem"
    LIST_PROBLEMS = "list_problems"

    # Submission actions
    CREATE_SUBMISSION = "create_submission"
    VIEW_SUBMISSION = "view_submission"
    LIST_SUBMISSIONS = "list_submissions"
    VALIDATE_SUBMISSION = "validate_submission"

    # Chat actions
    CHAT_MESSAGE = "chat_message"
    GENERATE_SUMMARY = "generate_summary"
    EVALUATE_DIAGRAM = "evaluate_diagram"

    # AI actions
    AI_VALIDATE_DESIGN = "ai_validate_design"
    AI_GENERATE_TERRAFORM = "ai_generate_terraform"
    AI_GENERATE_TESTS = "ai_generate_tests"
    AI_GENERATE_CODE = "ai_generate_code"
    AI_CHAT = "ai_chat"
    AI_DESIGN_SUMMARY = "ai_design_summary"

    # Deployment actions
    DEPLOY_START = "deploy_start"
    DEPLOY_COMPLETE = "deploy_complete"
    DEPLOY_FAILED = "deploy_failed"

    # Test actions
    RUN_TESTS = "run_tests"

    # User profile actions
    UPDATE_PROFILE = "update_profile"
    DELETE_ACCOUNT = "delete_account"
    EXPORT_DATA = "export_data"

    # Admin actions
    ADMIN_BAN_USER = "admin_ban_user"
    ADMIN_UNBAN_USER = "admin_unban_user"

    # Moderation actions
    MODERATION_FLAGGED = "moderation_flagged"
    MODERATION_BLOCKED = "moderation_blocked"


class CostCategory(str, Enum):
    """Categories for usage costs."""
    AI_INPUT_TOKENS = "ai_input_tokens"
    AI_OUTPUT_TOKENS = "ai_output_tokens"
    GCP_COMPUTE = "gcp_compute"
    GCP_STORAGE = "gcp_storage"
    GCP_NETWORK = "gcp_network"
    GCP_DATABASE = "gcp_database"


class AuditLog(Base):
    """
    Audit log for tracking all user actions.

    Attributes:
        id: Primary key
        user_id: User who performed the action (nullable for anonymous)
        action: Type of action performed
        resource_type: Type of resource affected (e.g., "submission", "problem")
        resource_id: ID of the affected resource
        details: Additional JSON details about the action
        ip_address: Client IP address
        user_agent: Client user agent string
        request_path: API endpoint path
        request_method: HTTP method
        response_status: HTTP response status code
        duration_ms: Request duration in milliseconds
        created_at: Timestamp of the action
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True, index=True)
    resource_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 max length
    user_agent = Column(String(512), nullable=True)
    request_path = Column(String(512), nullable=True)
    request_method = Column(String(10), nullable=True)
    response_status = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationship to user
    user = relationship("User", backref="audit_logs")

    # Indexes for common queries
    __table_args__ = (
        Index("ix_audit_logs_user_action", "user_id", "action"),
        Index("ix_audit_logs_created_at_action", "created_at", "action"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, user_id={self.user_id}, action='{self.action}')>"


class UsageCost(Base):
    """
    Usage cost tracking for billing and analytics.

    Attributes:
        id: Primary key
        user_id: User who incurred the cost
        audit_log_id: Related audit log entry
        category: Cost category (AI tokens, GCP resources, etc.)
        quantity: Quantity of the resource used
        unit: Unit of measurement (tokens, seconds, bytes, etc.)
        unit_cost_usd: Cost per unit in USD
        total_cost_usd: Total cost in USD
        details: Additional JSON details about the cost
        created_at: Timestamp of the cost
    """
    __tablename__ = "usage_costs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    audit_log_id = Column(Integer, ForeignKey("audit_logs.id"), nullable=True, index=True)
    category = Column(String(50), nullable=False, index=True)
    quantity = Column(Numeric(20, 6), nullable=False)
    unit = Column(String(20), nullable=False)
    unit_cost_usd = Column(Numeric(20, 10), nullable=False)
    total_cost_usd = Column(Numeric(20, 10), nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", backref="usage_costs")
    audit_log = relationship("AuditLog", backref="usage_costs")

    # Indexes for common queries
    __table_args__ = (
        Index("ix_usage_costs_user_category", "user_id", "category"),
        Index("ix_usage_costs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<UsageCost(id={self.id}, user_id={self.user_id}, category='{self.category}', total=${self.total_cost_usd})>"


# Cost rates for different services (in USD)
COST_RATES = {
    # Anthropic Claude API (Claude 3.5 Sonnet pricing)
    CostCategory.AI_INPUT_TOKENS: Decimal("0.000003"),  # $3 per million tokens
    CostCategory.AI_OUTPUT_TOKENS: Decimal("0.000015"),  # $15 per million tokens

    # GCP Cloud Run (approximate)
    CostCategory.GCP_COMPUTE: Decimal("0.00002400"),  # $0.0864 per vCPU-hour / 3600
    CostCategory.GCP_STORAGE: Decimal("0.00000003"),  # $0.026 per GB-month / 720 / 1000
    CostCategory.GCP_NETWORK: Decimal("0.00000012"),  # $0.12 per GB egress / 1000000
    CostCategory.GCP_DATABASE: Decimal("0.00010000"),  # $0.36 per hour / 3600
}
