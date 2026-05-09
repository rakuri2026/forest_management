"""Merge all migration heads

Revision ID: 4c5dc19e96e5
Revises: 009_add_subarea_to_fieldbook, 013, 016, 016_create_operational_plans_table, 024_add_forest_blocks_indexes, 6be2029e7da1, 90daf66d2ae9
Create Date: 2026-05-09 17:54:30.440979

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4c5dc19e96e5'
down_revision = ('009_add_subarea_to_fieldbook', '013', '016', '016_create_operational_plans_table', '024_add_forest_blocks_indexes', '6be2029e7da1', '90daf66d2ae9')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
