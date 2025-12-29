"""Add audit log and usage cost tables

Revision ID: 005
Revises: 004
Create Date: 2024-12-29

Adds the following tables:
- audit_logs: Tracks all user actions for security and debugging
- usage_costs: Tracks usage costs for billing and analytics
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('action', sa.String(50), nullable=False, index=True),
        sa.Column('resource_type', sa.String(50), nullable=True, index=True),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(512), nullable=True),
        sa.Column('request_path', sa.String(512), nullable=True),
        sa.Column('request_method', sa.String(10), nullable=True),
        sa.Column('response_status', sa.Integer(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )

    # Create composite indexes for audit_logs
    op.create_index('ix_audit_logs_user_action', 'audit_logs', ['user_id', 'action'])
    op.create_index('ix_audit_logs_created_at_action', 'audit_logs', ['created_at', 'action'])
    op.create_index('ix_audit_logs_resource', 'audit_logs', ['resource_type', 'resource_id'])

    # Create usage_costs table
    op.create_table(
        'usage_costs',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('audit_log_id', sa.Integer(), sa.ForeignKey('audit_logs.id'), nullable=True, index=True),
        sa.Column('category', sa.String(50), nullable=False, index=True),
        sa.Column('quantity', sa.Numeric(20, 6), nullable=False),
        sa.Column('unit', sa.String(20), nullable=False),
        sa.Column('unit_cost_usd', sa.Numeric(20, 10), nullable=False),
        sa.Column('total_cost_usd', sa.Numeric(20, 10), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )

    # Create composite indexes for usage_costs
    op.create_index('ix_usage_costs_user_category', 'usage_costs', ['user_id', 'category'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_usage_costs_user_category', table_name='usage_costs')
    op.drop_index('ix_audit_logs_resource', table_name='audit_logs')
    op.drop_index('ix_audit_logs_created_at_action', table_name='audit_logs')
    op.drop_index('ix_audit_logs_user_action', table_name='audit_logs')

    # Drop tables
    op.drop_table('usage_costs')
    op.drop_table('audit_logs')
