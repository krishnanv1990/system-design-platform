"""Add endpoint_url column to submissions

Revision ID: 003
Revises: 002
Create Date: 2025-12-26
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add endpoint_url column to submissions table
    op.add_column('submissions', sa.Column('endpoint_url', sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column('submissions', 'endpoint_url')
