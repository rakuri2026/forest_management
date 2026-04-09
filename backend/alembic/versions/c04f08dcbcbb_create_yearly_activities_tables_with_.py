"""Create yearly activities tables with spatial support

Revision ID: c04f08dcbcbb
Revises: 6be2029e7da1
Create Date: 2026-04-05 18:28:16.363133

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = 'c04f08dcbcbb'
down_revision = '6be2029e7da1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update existing potential_activities table
    # Add UUID column (for new records, existing records keep integer ID)
    op.add_column(
        'potential_activities',
        sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=True),
        schema='public'
    )

    # Add missing columns to potential_activities
    op.add_column(
        'potential_activities',
        sa.Column('description', sa.Text(), nullable=True),
        schema='public'
    )
    op.add_column(
        'potential_activities',
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        schema='public'
    )
    op.add_column(
        'potential_activities',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        schema='public'
    )
    op.add_column(
        'potential_activities',
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        schema='public'
    )
    op.add_column(
        'potential_activities',
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        schema='public'
    )

    # Add index for is_default (already exists as varchar, keep as is for now)
    op.create_index(
        'idx_potential_activities_default',
        'potential_activities',
        ['is_default'],
        schema='public'
    )

    # Create proposed_yearly_activities table
    op.create_table(
        'proposed_yearly_activities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('calculation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('public.calculations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('potential_activity_id', sa.Integer(), sa.ForeignKey('public.potential_activities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('block_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('public.forest_blocks.id', ondelete='SET NULL'), nullable=True),
        sa.Column('sub_area_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('public.forest_sub_areas.id', ondelete='SET NULL'), nullable=True),
        sa.Column('default_quantity', sa.Numeric(10, 2), nullable=False),
        sa.Column('default_yearly_budget', sa.Numeric(12, 2), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='proposed'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.CheckConstraint(
            '(sub_area_id IS NULL) OR (sub_area_id IS NOT NULL AND block_id IS NOT NULL)',
            name='check_sub_area_has_block'
        ),
        schema='public'
    )

    # Create indexes for proposed_yearly_activities
    op.create_index(
        'idx_proposed_activities_calculation',
        'proposed_yearly_activities',
        ['calculation_id'],
        schema='public'
    )
    op.create_index(
        'idx_proposed_activities_block',
        'proposed_yearly_activities',
        ['block_id'],
        schema='public'
    )
    op.create_index(
        'idx_proposed_activities_sub_area',
        'proposed_yearly_activities',
        ['sub_area_id'],
        schema='public'
    )
    op.create_index(
        'idx_proposed_activities_status',
        'proposed_yearly_activities',
        ['status'],
        schema='public'
    )

    # Create activity_year_details table
    op.create_table(
        'activity_year_details',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('proposed_activity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('public.proposed_yearly_activities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('year_number', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Numeric(10, 2), nullable=True),
        sa.Column('yearly_budget', sa.Numeric(12, 2), nullable=True),
        sa.Column('target_completion_month', sa.String(20), nullable=True),
        sa.Column('actual_quantity', sa.Numeric(10, 2), nullable=True),
        sa.Column('actual_budget', sa.Numeric(12, 2), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='planned'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.CheckConstraint(
            'year_number >= 1 AND year_number <= 10',
            name='check_year_number'
        ),
        sa.UniqueConstraint('proposed_activity_id', 'year_number', name='unique_activity_year'),
        schema='public'
    )

    # Create indexes for activity_year_details
    op.create_index(
        'idx_activity_year_proposed',
        'activity_year_details',
        ['proposed_activity_id'],
        schema='public'
    )
    op.create_index(
        'idx_activity_year_number',
        'activity_year_details',
        ['year_number'],
        schema='public'
    )
    op.create_index(
        'idx_activity_year_status',
        'activity_year_details',
        ['status'],
        schema='public'
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('idx_activity_year_status', table_name='activity_year_details', schema='public')
    op.drop_index('idx_activity_year_number', table_name='activity_year_details', schema='public')
    op.drop_index('idx_activity_year_proposed', table_name='activity_year_details', schema='public')
    op.drop_table('activity_year_details', schema='public')

    op.drop_index('idx_proposed_activities_status', table_name='proposed_yearly_activities', schema='public')
    op.drop_index('idx_proposed_activities_sub_area', table_name='proposed_yearly_activities', schema='public')
    op.drop_index('idx_proposed_activities_block', table_name='proposed_yearly_activities', schema='public')
    op.drop_index('idx_proposed_activities_calculation', table_name='proposed_yearly_activities', schema='public')
    op.drop_table('proposed_yearly_activities', schema='public')

    # Remove added columns from potential_activities
    op.drop_index('idx_potential_activities_default', table_name='potential_activities', schema='public')
    op.drop_column('potential_activities', 'updated_at', schema='public')
    op.drop_column('potential_activities', 'created_at', schema='public')
    op.drop_column('potential_activities', 'is_active', schema='public')
    op.drop_column('potential_activities', 'display_order', schema='public')
    op.drop_column('potential_activities', 'description', schema='public')
    op.drop_column('potential_activities', 'uuid', schema='public')
