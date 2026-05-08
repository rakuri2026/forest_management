"""Add compartment fields to forest_blocks

Revision ID: 220a50e38095
Revises: 014
Create Date: 2026-04-04 17:08:51.911534

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '220a50e38095'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add compartment fields to forest_blocks table
    op.add_column(
        'forest_blocks',
        sa.Column('is_compartment', sa.Boolean(), nullable=False, server_default='false'),
        schema='public'
    )
    op.add_column(
        'forest_blocks',
        sa.Column('parent_block_id', UUID(as_uuid=True), nullable=True),
        schema='public'
    )
    op.add_column(
        'forest_blocks',
        sa.Column('compartment_code', sa.String(50), nullable=True),
        schema='public'
    )
    op.add_column(
        'forest_blocks',
        sa.Column('area_sqm', sa.Float(), nullable=True),
        schema='public'
    )

    # Add foreign key constraint for parent_block_id
    op.create_foreign_key(
        'fk_forest_blocks_parent_block_id',
        'forest_blocks', 'forest_blocks',
        ['parent_block_id'], ['id'],
        source_schema='public', referent_schema='public',
        ondelete='CASCADE'
    )

    # Create indexes for performance
    op.create_index(
        'idx_forest_blocks_parent',
        'forest_blocks',
        ['parent_block_id'],
        schema='public'
    )
    op.create_index(
        'idx_forest_blocks_is_compartment',
        'forest_blocks',
        ['is_compartment'],
        schema='public'
    )
    op.create_index(
        'idx_forest_blocks_compartment_code',
        'forest_blocks',
        ['compartment_code'],
        schema='public'
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_forest_blocks_compartment_code', table_name='forest_blocks', schema='public')
    op.drop_index('idx_forest_blocks_is_compartment', table_name='forest_blocks', schema='public')
    op.drop_index('idx_forest_blocks_parent', table_name='forest_blocks', schema='public')

    # Drop foreign key constraint
    op.drop_constraint('fk_forest_blocks_parent_block_id', 'forest_blocks', type_='foreignkey', schema='public')

    # Drop columns
    op.drop_column('forest_blocks', 'area_sqm', schema='public')
    op.drop_column('forest_blocks', 'compartment_code', schema='public')
    op.drop_column('forest_blocks', 'parent_block_id', schema='public')
    op.drop_column('forest_blocks', 'is_compartment', schema='public')
