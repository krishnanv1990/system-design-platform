"""set_admin_user_krishnanv

Revision ID: 99e39b0bff72
Revises: 005
Create Date: 2025-12-29 13:04:03.300906

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '99e39b0bff72'
down_revision: Union[str, Sequence[str], None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - set admin user."""
    # Set krishnanv2005@gmail.com as admin
    op.execute(
        """
        UPDATE users
        SET is_admin = TRUE
        WHERE email = 'krishnanv2005@gmail.com'
        """
    )


def downgrade() -> None:
    """Downgrade schema - remove admin status."""
    op.execute(
        """
        UPDATE users
        SET is_admin = FALSE
        WHERE email = 'krishnanv2005@gmail.com'
        """
    )
