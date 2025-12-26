"""Add error analysis columns

Revision ID: 002
Revises: 001
Create Date: 2025-12-26

Adds columns for AI-powered error analysis:
- error_category: Root cause category (user_solution, platform, deployment)
- error_analysis: Detailed AI analysis (JSONB)
- ai_analysis_status: Status of the analysis process
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add error_category column
    op.execute("""
        ALTER TABLE test_results
        ADD COLUMN IF NOT EXISTS error_category VARCHAR(50)
    """)

    # Add error_analysis JSONB column
    op.execute("""
        ALTER TABLE test_results
        ADD COLUMN IF NOT EXISTS error_analysis JSONB
    """)

    # Add ai_analysis_status column with default value
    op.execute("""
        ALTER TABLE test_results
        ADD COLUMN IF NOT EXISTS ai_analysis_status VARCHAR(20) DEFAULT 'pending'
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE test_results DROP COLUMN IF EXISTS ai_analysis_status")
    op.execute("ALTER TABLE test_results DROP COLUMN IF EXISTS error_analysis")
    op.execute("ALTER TABLE test_results DROP COLUMN IF EXISTS error_category")
