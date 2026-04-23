"""Add performance indexes to forest_blocks table

Revision ID: 024_add_forest_blocks_indexes
Revises: b1028e3b11b0
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '024_add_forest_blocks_indexes'
down_revision = 'b1028e3b11b0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add indexes for common query patterns
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_forest_blocks_calculation 
        ON forest_blocks (calculation_id)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_forest_blocks_parent 
        ON forest_blocks (parent_block_id)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_forest_blocks_is_compartment 
        ON forest_blocks (is_compartment)
    """)
    
    # Spatial index for geometry queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_forest_blocks_geometry 
        ON forest_blocks USING GIST (geometry)
    """)
    
    # Composite index for common query pattern
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_forest_blocks_calc_compartment 
        ON forest_blocks (calculation_id, is_compartment)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_forest_blocks_calculation")
    op.execute("DROP INDEX IF EXISTS idx_forest_blocks_parent")
    op.execute("DROP INDEX IF EXISTS idx_forest_blocks_is_compartment")
    op.execute("DROP INDEX IF EXISTS idx_forest_blocks_geometry")
    op.execute("DROP INDEX IF EXISTS idx_forest_blocks_calc_compartment")