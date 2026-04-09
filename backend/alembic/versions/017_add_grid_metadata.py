"""Add grid metadata columns to inventory_calculations

Revision ID: 017_add_grid_metadata
Revises: 016_add_pole_count
Create Date: 2026-04-08

"""
from alembic import op
import sqlalchemy as sa

revision = '017_add_grid_metadata'
down_revision = ('016_add_pole_count', 'c04f08dcbcbb')
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('inventory_calculations', 
        sa.Column('grid_origin_x', sa.Float(), nullable=True))
    op.add_column('inventory_calculations', 
        sa.Column('grid_origin_y', sa.Float(), nullable=True))
    op.add_column('inventory_calculations', 
        sa.Column('grid_num_cols', sa.Integer(), nullable=True))
    op.add_column('inventory_calculations', 
        sa.Column('grid_num_rows', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('inventory_calculations', 'grid_num_rows')
    op.drop_column('inventory_calculations', 'grid_num_cols')
    op.drop_column('inventory_calculations', 'grid_origin_y')
    op.drop_column('inventory_calculations', 'grid_origin_x')