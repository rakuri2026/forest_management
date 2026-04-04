"""Create compartment_split_history table

Revision ID: b1028e3b11b0
Revises: 220a50e38095
Create Date: 2026-04-04 17:09:49.991930

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = 'b1028e3b11b0'
down_revision = '220a50e38095'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create compartment_split_history table
    op.create_table(
        'compartment_split_history',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('parent_block_id', UUID(as_uuid=True), nullable=False),
        sa.Column('calculation_id', UUID(as_uuid=True), nullable=False),

        # Split configuration
        sa.Column('split_method', sa.String(50), nullable=False),
        sa.Column('split_direction', sa.Float(), nullable=True),
        sa.Column('split_parameters', JSONB, nullable=True),
        sa.Column('number_of_compartments', sa.Integer(), nullable=False),

        # User and audit
        sa.Column('created_by', UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),

        # Metadata
        sa.Column('naming_pattern', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),

        schema='public'
    )

    # Add foreign key constraints
    op.create_foreign_key(
        'fk_compartment_split_history_parent_block',
        'compartment_split_history', 'forest_blocks',
        ['parent_block_id'], ['id'],
        source_schema='public', referent_schema='public',
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_compartment_split_history_calculation',
        'compartment_split_history', 'calculations',
        ['calculation_id'], ['id'],
        source_schema='public', referent_schema='public',
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_compartment_split_history_created_by',
        'compartment_split_history', 'users',
        ['created_by'], ['id'],
        source_schema='public', referent_schema='public',
        ondelete='SET NULL'
    )

    # Create indexes
    op.create_index(
        'idx_split_history_parent',
        'compartment_split_history',
        ['parent_block_id'],
        schema='public'
    )
    op.create_index(
        'idx_split_history_calc',
        'compartment_split_history',
        ['calculation_id'],
        schema='public'
    )
    op.create_index(
        'idx_split_history_created_by',
        'compartment_split_history',
        ['created_by'],
        schema='public'
    )
    op.create_index(
        'idx_split_history_created_at',
        'compartment_split_history',
        ['created_at'],
        schema='public'
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_split_history_created_at', table_name='compartment_split_history', schema='public')
    op.drop_index('idx_split_history_created_by', table_name='compartment_split_history', schema='public')
    op.drop_index('idx_split_history_calc', table_name='compartment_split_history', schema='public')
    op.drop_index('idx_split_history_parent', table_name='compartment_split_history', schema='public')

    # Drop foreign key constraints
    op.drop_constraint('fk_compartment_split_history_created_by', 'compartment_split_history', type_='foreignkey', schema='public')
    op.drop_constraint('fk_compartment_split_history_calculation', 'compartment_split_history', type_='foreignkey', schema='public')
    op.drop_constraint('fk_compartment_split_history_parent_block', 'compartment_split_history', type_='foreignkey', schema='public')

    # Drop table
    op.drop_table('compartment_split_history', schema='public')
