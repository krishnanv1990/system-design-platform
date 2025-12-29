"""
Audit Service for logging user actions and tracking usage costs.
Provides centralized logging for security, debugging, and billing.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from backend.models.audit_log import (
    AuditLog,
    UsageCost,
    ActionType,
    CostCategory,
    COST_RATES,
)

logger = logging.getLogger(__name__)


class AuditService:
    """
    Service for logging user actions and tracking usage costs.
    """

    def __init__(self, db: Session):
        """Initialize the audit service with a database session."""
        self.db = db

    def log_action(
        self,
        action: ActionType,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_path: Optional[str] = None,
        request_method: Optional[str] = None,
        response_status: Optional[int] = None,
        duration_ms: Optional[int] = None,
    ) -> AuditLog:
        """
        Log a user action to the audit log.

        Args:
            action: Type of action performed
            user_id: User who performed the action
            resource_type: Type of resource affected
            resource_id: ID of the affected resource
            details: Additional details about the action
            ip_address: Client IP address
            user_agent: Client user agent string
            request_path: API endpoint path
            request_method: HTTP method
            response_status: HTTP response status code
            duration_ms: Request duration in milliseconds

        Returns:
            Created AuditLog entry
        """
        try:
            audit_log = AuditLog(
                user_id=user_id,
                action=action.value if isinstance(action, ActionType) else action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
                request_path=request_path,
                request_method=request_method,
                response_status=response_status,
                duration_ms=duration_ms,
            )
            self.db.add(audit_log)
            self.db.commit()
            self.db.refresh(audit_log)

            logger.info(
                f"Audit log: user={user_id}, action={action}, "
                f"resource={resource_type}/{resource_id}"
            )
            return audit_log

        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
            self.db.rollback()
            raise

    def track_ai_usage(
        self,
        user_id: Optional[int],
        audit_log_id: Optional[int],
        input_tokens: int,
        output_tokens: int,
        model: str = "claude-sonnet-4",
        details: Optional[Dict[str, Any]] = None,
    ) -> List[UsageCost]:
        """
        Track AI API usage costs.

        Args:
            user_id: User who incurred the cost
            audit_log_id: Related audit log entry
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens generated
            model: AI model used
            details: Additional details

        Returns:
            List of created UsageCost entries
        """
        costs = []

        try:
            # Track input tokens
            if input_tokens > 0:
                input_cost = UsageCost(
                    user_id=user_id,
                    audit_log_id=audit_log_id,
                    category=CostCategory.AI_INPUT_TOKENS.value,
                    quantity=Decimal(input_tokens),
                    unit="tokens",
                    unit_cost_usd=COST_RATES[CostCategory.AI_INPUT_TOKENS],
                    total_cost_usd=COST_RATES[CostCategory.AI_INPUT_TOKENS] * input_tokens,
                    details={"model": model, **(details or {})},
                )
                self.db.add(input_cost)
                costs.append(input_cost)

            # Track output tokens
            if output_tokens > 0:
                output_cost = UsageCost(
                    user_id=user_id,
                    audit_log_id=audit_log_id,
                    category=CostCategory.AI_OUTPUT_TOKENS.value,
                    quantity=Decimal(output_tokens),
                    unit="tokens",
                    unit_cost_usd=COST_RATES[CostCategory.AI_OUTPUT_TOKENS],
                    total_cost_usd=COST_RATES[CostCategory.AI_OUTPUT_TOKENS] * output_tokens,
                    details={"model": model, **(details or {})},
                )
                self.db.add(output_cost)
                costs.append(output_cost)

            self.db.commit()
            for cost in costs:
                self.db.refresh(cost)

            total_cost = sum(c.total_cost_usd for c in costs)
            logger.info(
                f"AI usage tracked: user={user_id}, input={input_tokens}, "
                f"output={output_tokens}, total_cost=${total_cost:.6f}"
            )

            return costs

        except Exception as e:
            logger.error(f"Failed to track AI usage: {e}")
            self.db.rollback()
            raise

    def track_gcp_usage(
        self,
        user_id: Optional[int],
        audit_log_id: Optional[int],
        category: CostCategory,
        quantity: Decimal,
        unit: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> UsageCost:
        """
        Track GCP resource usage costs.

        Args:
            user_id: User who incurred the cost
            audit_log_id: Related audit log entry
            category: Cost category (GCP_COMPUTE, GCP_STORAGE, etc.)
            quantity: Quantity of the resource used
            unit: Unit of measurement
            details: Additional details

        Returns:
            Created UsageCost entry
        """
        try:
            unit_cost = COST_RATES.get(category, Decimal("0"))
            total_cost = unit_cost * quantity

            usage_cost = UsageCost(
                user_id=user_id,
                audit_log_id=audit_log_id,
                category=category.value,
                quantity=quantity,
                unit=unit,
                unit_cost_usd=unit_cost,
                total_cost_usd=total_cost,
                details=details,
            )
            self.db.add(usage_cost)
            self.db.commit()
            self.db.refresh(usage_cost)

            logger.info(
                f"GCP usage tracked: user={user_id}, category={category.value}, "
                f"quantity={quantity} {unit}, cost=${total_cost:.6f}"
            )

            return usage_cost

        except Exception as e:
            logger.error(f"Failed to track GCP usage: {e}")
            self.db.rollback()
            raise

    def get_user_costs(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get usage costs for a user within a date range.

        Args:
            user_id: User ID
            start_date: Start of date range (default: 30 days ago)
            end_date: End of date range (default: now)

        Returns:
            Dict with cost breakdown by category
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.utcnow()

        # Query costs grouped by category
        costs = (
            self.db.query(
                UsageCost.category,
                func.sum(UsageCost.quantity).label("total_quantity"),
                func.sum(UsageCost.total_cost_usd).label("total_cost"),
                func.count(UsageCost.id).label("count"),
            )
            .filter(
                and_(
                    UsageCost.user_id == user_id,
                    UsageCost.created_at >= start_date,
                    UsageCost.created_at <= end_date,
                )
            )
            .group_by(UsageCost.category)
            .all()
        )

        result = {
            "user_id": user_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "categories": {},
            "total_cost_usd": Decimal("0"),
        }

        for row in costs:
            result["categories"][row.category] = {
                "quantity": float(row.total_quantity),
                "cost_usd": float(row.total_cost),
                "count": row.count,
            }
            result["total_cost_usd"] += row.total_cost

        result["total_cost_usd"] = float(result["total_cost_usd"])

        return result

    def get_user_actions(
        self,
        user_id: int,
        action_filter: Optional[List[ActionType]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Get audit log entries for a user.

        Args:
            user_id: User ID
            action_filter: Filter to specific action types
            start_date: Start of date range
            end_date: End of date range
            limit: Maximum number of entries to return

        Returns:
            List of AuditLog entries
        """
        query = self.db.query(AuditLog).filter(AuditLog.user_id == user_id)

        if action_filter:
            action_values = [a.value for a in action_filter]
            query = query.filter(AuditLog.action.in_(action_values))

        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        return query.order_by(AuditLog.created_at.desc()).limit(limit).all()

    def get_action_summary(
        self,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get a summary of actions (optionally for a specific user).

        Args:
            user_id: Filter to specific user (optional)
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Dict with action counts and summary
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.utcnow()

        query = self.db.query(
            AuditLog.action,
            func.count(AuditLog.id).label("count"),
            func.avg(AuditLog.duration_ms).label("avg_duration_ms"),
        ).filter(
            and_(
                AuditLog.created_at >= start_date,
                AuditLog.created_at <= end_date,
            )
        )

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)

        actions = query.group_by(AuditLog.action).all()

        result = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "actions": {},
            "total_actions": 0,
        }

        for row in actions:
            result["actions"][row.action] = {
                "count": row.count,
                "avg_duration_ms": float(row.avg_duration_ms) if row.avg_duration_ms else None,
            }
            result["total_actions"] += row.count

        if user_id:
            result["user_id"] = user_id

        return result


def get_audit_service(db: Session) -> AuditService:
    """Factory function to create an AuditService instance."""
    return AuditService(db)
