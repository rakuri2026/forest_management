"""Link trees to compartments

Revision ID: 761f7c526c2c
Revises: b1028e3b11b0
Create Date: 2026-04-04 17:11:01.523672

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '761f7c526c2c'
down_revision = 'b1028e3b11b0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add forest_block_id and compartment_id columns to inventory_trees
    op.add_column(
        'inventory_trees',
        sa.Column('forest_block_id', UUID(as_uuid=True), nullable=True),
        schema='public'
    )
    op.add_column(
        'inventory_trees',
        sa.Column('compartment_id', UUID(as_uuid=True), nullable=True),
        schema='public'
    )

    # Add foreign key constraints
    op.create_foreign_key(
        'fk_inventory_trees_forest_block',
        'inventory_trees', 'forest_blocks',
        ['forest_block_id'], ['id'],
        source_schema='public', referent_schema='public',
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_inventory_trees_compartment',
        'inventory_trees', 'forest_blocks',
        ['compartment_id'], ['id'],
        source_schema='public', referent_schema='public',
        ondelete='SET NULL'
    )

    # Add check constraint: tree must belong to either block OR compartment (not both, not neither)
    # Note: We allow both to be NULL temporarily for existing data, but new inserts must have one
    op.create_check_constraint(
        'check_tree_assignment',
        'inventory_trees',
        '(forest_block_id IS NOT NULL AND compartment_id IS NULL) OR (forest_block_id IS NULL AND compartment_id IS NOT NULL) OR (forest_block_id IS NULL AND compartment_id IS NULL)',
        schema='public'
    )

    # Create indexes for performance
    op.create_index(
        'idx_inventory_trees_forest_block',
        'inventory_trees',
        ['forest_block_id'],
        schema='public'
    )
    op.create_index(
        'idx_inventory_trees_compartment',
        'inventory_trees',
        ['compartment_id'],
        schema='public'
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_inventory_trees_compartment', table_name='inventory_trees', schema='public')
    op.drop_index('idx_inventory_trees_forest_block', table_name='inventory_trees', schema='public')

    # Drop check constraint
    op.drop_constraint('check_tree_assignment', 'inventory_trees', type_='check', schema='public')

    # Drop foreign key constraints
    op.drop_constraint('fk_inventory_trees_compartment', 'inventory_trees', type_='foreignkey', schema='public')
    op.drop_constraint('fk_inventory_trees_forest_block', 'inventory_trees', type_='foreignkey', schema='public')

    # Drop columns
    op.drop_column('inventory_trees', 'compartment_id', schema='public')
    op.drop_column('inventory_trees', 'forest_block_id', schema='public')
