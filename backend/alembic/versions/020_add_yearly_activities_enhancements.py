"""Add year_numbers array, requires_map, block/sub-area to year_details, and spatial_data table

Revision ID: 020_add_yearly_activities_enhancements
Revises: 019_add_year_number_to_proposed_activities
Create Date: 2026-04-10

Changes:
1. Add requires_map column to potential_activities
2. Remove year_number from proposed_yearly_activities
3. Add year_numbers array to proposed_yearly_activities
4. Add block_id and sub_area_id to activity_year_details
5. Create activity_spatial_data table for map geometries
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '020_add_yearly_activities_enhancements'
down_revision = '019_add_year_number_to_proposed_activities'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add requires_map to potential_activities
    op.add_column(
        'potential_activities',
        sa.Column('requires_map', sa.Boolean(), nullable=False, server_default='false'),
        schema='public'
    )
    
    # Set requires_map for specific serial numbers (59 activities)
    serial_numbers = [
        '1', '2', '4', '5', '6', '7', '8', '9', '10', '11', '12', '15', '18',
        '20', '21', '22', '23', '24', '25', '26', '27', '28',
        '30', '31', '32', '33', '34', '35', '36',
        '52', '54', '58', '59', '60', '61', '62',
        '82', '83', '84', '85', '86', '87', '88', '89', '90', '91', '92',
        '94', '95', '96', '97', '98', '99', '100', '101',
        '125', '126', '127', '128', '131'
    ]
    
    op.execute(
        f"UPDATE public.potential_activities SET requires_map = true WHERE sn IN ({','.join(repr(sn) for sn in serial_numbers)})"
    )
    
    # Step 2: Add block_id and sub_area_id to activity_year_details
    op.add_column(
        'activity_year_details',
        sa.Column('block_id', UUID(as_uuid=True), nullable=True),
        schema='public'
    )
    op.add_column(
        'activity_year_details',
        sa.Column('sub_area_id', UUID(as_uuid=True), nullable=True),
        schema='public'
    )
    
    # Add foreign key constraints
    op.create_foreign_key(
        'fk_year_detail_block',
        'activity_year_details', 'forest_blocks',
        ['block_id'], ['id'],
        source_schema='public', referent_schema='public',
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_year_detail_sub_area',
        'activity_year_details', 'forest_sub_areas',
        ['sub_area_id'], ['id'],
        source_schema='public', referent_schema='public',
        ondelete='SET NULL'
    )
    
    # Step 3: Create year_numbers array in proposed_yearly_activities
    # First, migrate existing year_number data to year_numbers array
    op.execute("""
        ALTER TABLE public.proposed_yearly_activities 
        ADD COLUMN IF NOT EXISTS year_numbers INTEGER[]
    """)
    
    # Migrate existing data: if year_number is set, convert to array
    op.execute("""
        UPDATE public.proposed_yearly_activities 
        SET year_numbers = ARRAY[year_number] 
        WHERE year_number IS NOT NULL AND year_numbers IS NULL
    """)
    
    # Set default for new records (all years 1-10)
    op.execute("""
        UPDATE public.proposed_yearly_activities 
        SET year_numbers = ARRAY[1,2,3,4,5,6,7,8,9,10] 
        WHERE year_numbers IS NULL
    """)
    
    # Remove the old year_number column (after migration)
    op.drop_column(
        'proposed_yearly_activities',
        'year_number',
        schema='public'
    )
    
    # Step 4: Create activity_spatial_data table
    op.create_table(
        'activity_spatial_data',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        sa.Column('proposed_activity_id', UUID(as_uuid=True), sa.ForeignKey('public.proposed_yearly_activities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('year_detail_id', UUID(as_uuid=True), sa.ForeignKey('public.activity_year_details.id', ondelete='CASCADE'), nullable=True),
        sa.Column('geometry', sa.Text(), nullable=False),  # GeoJSON as text
        sa.Column('geometry_type', sa.String(20), nullable=False),  # Point, LineString, Polygon
        sa.Column('spatial_source', sa.String(50), nullable=False),  # block, sub_area, user_group, drawn
        sa.Column('source_entity_id', UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        schema='public'
    )
    
    # Create spatial index on geometry (as text for now, can be converted to GIST later)
    op.create_index(
        'idx_activity_spatial_geometry',
        'activity_spatial_data',
        ['geometry'],
        unique=False,
        schema='public',
        postgresql_using='gin',
        postgresql_ops={'geometry': 'gist'}
    )


def downgrade() -> None:
    # Drop spatial data table
    op.drop_index('idx_activity_spatial_geometry', table_name='activity_spatial_data', schema='public')
    op.drop_table('activity_spatial_data', schema='public')
    
    # Re-add year_number column
    op.add_column(
        'proposed_yearly_activities',
        sa.Column('year_number', sa.Integer(), nullable=True),
        schema='public'
    )
    
    # Migrate back: if year_numbers has single value, convert to year_number
    op.execute("""
        UPDATE public.proposed_yearly_activities 
        SET year_number = year_numbers[1] 
        WHERE array_length(year_numbers, 1) = 1
    """)
    
    # Drop year_numbers column
    op.drop_column(
        'proposed_yearly_activities',
        'year_numbers',
        schema='public'
    )
    
    # Remove foreign keys and columns from activity_year_details
    op.drop_constraint('fk_year_detail_sub_area', 'activity_year_details', schema='public')
    op.drop_constraint('fk_year_detail_block', 'activity_year_details', schema='public')
    op.drop_column('activity_year_details', 'sub_area_id', schema='public')
    op.drop_column('activity_year_details', 'block_id', schema='public')
    
    # Remove requires_map column
    op.drop_column('potential_activities', 'requires_map', schema='public')
