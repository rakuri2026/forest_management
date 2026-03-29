"""add_forest_blocks_and_sub_areas_tables

Revision ID: 013
Revises: 012
Create Date: 2026-03-26 11:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid


revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create forest_blocks and forest_sub_areas tables"""
    
    op.execute("""
        CREATE TABLE public.forest_blocks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            calculation_id UUID NOT NULL REFERENCES public.calculations(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            geometry geometry(GEOMETRY, 4326) NOT NULL,
            area_hectares DOUBLE PRECISION NOT NULL CHECK (area_hectares > 0),
            "index" INTEGER NOT NULL CHECK ("index" >= 0),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        )
    """)
    
    op.execute("""
        CREATE TABLE public.forest_sub_areas (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            calculation_id UUID NOT NULL REFERENCES public.calculations(id) ON DELETE CASCADE,
            block_id UUID REFERENCES public.forest_blocks(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            category VARCHAR(50) NOT NULL CHECK (category IN ('protected', 'plantation', 'pro-poor', 'religious', 'biodiversity', 'tourist', 'office', 'private_land')),
            geometry geometry(GEOMETRY, 4326) NOT NULL,
            area_hectares DOUBLE PRECISION NOT NULL CHECK (area_hectares > 0),
            is_excluded BOOLEAN DEFAULT FALSE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        )
    """)
    
    op.execute("CREATE INDEX idx_forest_blocks_calculation_id ON public.forest_blocks(calculation_id)")
    op.execute("CREATE INDEX idx_forest_blocks_geometry ON public.forest_blocks USING GIST(geometry)")
    op.execute("CREATE INDEX idx_forest_sub_areas_calculation_id ON public.forest_sub_areas(calculation_id)")
    op.execute("CREATE INDEX idx_forest_sub_areas_block_id ON public.forest_sub_areas(block_id)")
    op.execute("CREATE INDEX idx_forest_sub_areas_geometry ON public.forest_sub_areas USING GIST(geometry)")


def downgrade() -> None:
    """Drop forest_blocks and forest_sub_areas tables"""
    
    op.execute("DROP INDEX IF EXISTS idx_forest_sub_areas_geometry")
    op.execute("DROP INDEX IF EXISTS idx_forest_sub_areas_block_id")
    op.execute("DROP INDEX IF EXISTS idx_forest_sub_areas_calculation_id")
    op.execute("DROP INDEX IF EXISTS idx_forest_blocks_geometry")
    op.execute("DROP INDEX IF EXISTS idx_forest_blocks_calculation_id")
    op.execute("DROP TABLE IF EXISTS public.forest_sub_areas")
    op.execute("DROP TABLE IF EXISTS public.forest_blocks")