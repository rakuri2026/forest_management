"""Add pole_count to inventory_calculations

Revision ID: 016_add_pole_count
Revises: 015
Create Date: 2026-04-07

"""
from alembic import op
import sqlalchemy as sa

revision = '016_add_pole_count'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('inventory_calculations', 
        sa.Column('pole_count', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('inventory_calculations', 'pole_count')
