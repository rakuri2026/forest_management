"""Merge migration heads

Revision ID: 50214feab44e
Revises: 009_add_subarea_to_fieldbook, 013, 015
Create Date: 2026-04-03 09:07:45.546205

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '50214feab44e'
down_revision = ('009_add_subarea_to_fieldbook', '013', '015')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
