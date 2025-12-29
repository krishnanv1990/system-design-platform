"""Add user profile and ban fields

Revision ID: 004_add_user_profile_fields
Revises: 003_add_endpoint_url
Create Date: 2024-12-28

Adds the following columns to the users table:
- display_name: User-customizable display name
- is_banned: Whether the user is banned
- ban_reason: Reason for the ban
- banned_at: Timestamp when the user was banned
- is_admin: Whether the user has admin privileges
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_add_user_profile_fields'
down_revision = '003_add_endpoint_url'
branch_labels = None
depends_on = None


def upgrade():
    # Add display_name column
    op.add_column('users', sa.Column('display_name', sa.String(100), nullable=True))

    # Add ban-related columns
    op.add_column('users', sa.Column('is_banned', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('ban_reason', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('banned_at', sa.DateTime(), nullable=True))

    # Add admin column
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    op.drop_column('users', 'is_admin')
    op.drop_column('users', 'banned_at')
    op.drop_column('users', 'ban_reason')
    op.drop_column('users', 'is_banned')
    op.drop_column('users', 'display_name')
