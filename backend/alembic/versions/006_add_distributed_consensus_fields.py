"""add_distributed_consensus_fields

Revision ID: 006
Revises: 99e39b0bff72
Create Date: 2025-12-29

Adds support for distributed consensus problems:
- Problem type field to distinguish system_design from distributed_consensus
- gRPC proto, language templates, cluster configuration for problems
- Language, source code, build artifacts for submissions
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, Sequence[str], None] = '99e39b0bff72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add distributed consensus fields to problems and submissions tables."""

    # Add new columns to problems table
    op.add_column('problems', sa.Column('problem_type', sa.String(50), nullable=False, server_default='system_design'))
    op.add_column('problems', sa.Column('grpc_proto', sa.Text(), nullable=True))
    op.add_column('problems', sa.Column('supported_languages', postgresql.JSONB(), nullable=True))
    op.add_column('problems', sa.Column('cluster_size', sa.Integer(), nullable=True))
    op.add_column('problems', sa.Column('language_templates', postgresql.JSONB(), nullable=True))
    op.add_column('problems', sa.Column('test_scenarios', postgresql.JSONB(), nullable=True))

    # Add new columns to submissions table
    op.add_column('submissions', sa.Column('submission_type', sa.String(50), nullable=False, server_default='system_design'))
    op.add_column('submissions', sa.Column('language', sa.String(20), nullable=True))
    op.add_column('submissions', sa.Column('source_code', sa.Text(), nullable=True))
    op.add_column('submissions', sa.Column('build_logs', sa.Text(), nullable=True))
    op.add_column('submissions', sa.Column('build_artifact_url', sa.String(512), nullable=True))
    op.add_column('submissions', sa.Column('cluster_node_urls', postgresql.JSONB(), nullable=True))

    # Create index on problem_type for efficient filtering
    op.create_index('ix_problems_problem_type', 'problems', ['problem_type'])
    op.create_index('ix_submissions_submission_type', 'submissions', ['submission_type'])


def downgrade() -> None:
    """Remove distributed consensus fields."""

    # Drop indexes
    op.drop_index('ix_submissions_submission_type', table_name='submissions')
    op.drop_index('ix_problems_problem_type', table_name='problems')

    # Remove columns from submissions table
    op.drop_column('submissions', 'cluster_node_urls')
    op.drop_column('submissions', 'build_artifact_url')
    op.drop_column('submissions', 'build_logs')
    op.drop_column('submissions', 'source_code')
    op.drop_column('submissions', 'language')
    op.drop_column('submissions', 'submission_type')

    # Remove columns from problems table
    op.drop_column('problems', 'test_scenarios')
    op.drop_column('problems', 'language_templates')
    op.drop_column('problems', 'cluster_size')
    op.drop_column('problems', 'supported_languages')
    op.drop_column('problems', 'grpc_proto')
    op.drop_column('problems', 'problem_type')
