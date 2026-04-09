"""Add inventory_grid_cells table for persistent grid cell storage

Revision ID: 018
Revises: 017_add_grid_metadata
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa

revision = '018_add_grid_cells'
down_revision = '017_add_grid_metadata'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'inventory_grid_cells',
        sa.Column('id', sa.UUID(), nullable=False, primary_key=True),
        sa.Column('inventory_calculation_id', sa.UUID(), nullable=False, index=True),
        sa.Column('cell_id', sa.Integer(), nullable=False),
        sa.Column('geom', sa.Geometry('POLYGON', srid=4326), nullable=False),
        sa.UniqueConstraint('inventory_calculation_id', 'cell_id', name='uq_inventory_grid_cells')
    )

def downgrade():
    op.drop_table('inventory_grid_cells')
