"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-12-26

This migration captures the existing schema. Since tables may already exist
from Base.metadata.create_all(), we use IF NOT EXISTS to handle both fresh
installs and migrations from existing databases.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            name VARCHAR(255),
            picture VARCHAR(500),
            google_id VARCHAR(255) UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_id ON users(id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON users(email)")

    # Create problems table
    op.execute("""
        CREATE TABLE IF NOT EXISTS problems (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            difficulty VARCHAR(50) DEFAULT 'medium',
            tags JSONB,
            hints JSONB,
            expected_api_spec JSONB,
            expected_schema JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_problems_id ON problems(id)")

    # Create submissions table
    op.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            problem_id INTEGER NOT NULL REFERENCES problems(id),
            schema_input JSONB,
            api_spec_input JSONB,
            design_text TEXT,
            status VARCHAR(50) DEFAULT 'pending',
            validation_feedback JSONB,
            generated_terraform TEXT,
            deployment_id VARCHAR(255),
            namespace VARCHAR(255),
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_submissions_id ON submissions(id)")

    # Create test_results table
    op.execute("""
        CREATE TABLE IF NOT EXISTS test_results (
            id SERIAL PRIMARY KEY,
            submission_id INTEGER NOT NULL REFERENCES submissions(id),
            test_type VARCHAR(50) NOT NULL,
            test_name VARCHAR(255) NOT NULL,
            status VARCHAR(50) DEFAULT 'pending',
            details JSONB,
            duration_ms INTEGER,
            chaos_scenario VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_test_results_id ON test_results(id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS test_results CASCADE")
    op.execute("DROP TABLE IF EXISTS submissions CASCADE")
    op.execute("DROP TABLE IF EXISTS problems CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
