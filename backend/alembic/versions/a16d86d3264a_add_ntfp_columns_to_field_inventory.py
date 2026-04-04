"""Add NTFP columns to field inventory

Revision ID: a16d86d3264a
Revises: 50214feab44e
Create Date: 2026-04-03 09:09:57.112469

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a16d86d3264a'
down_revision = '50214feab44e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add NTFP columns to field_inventory_sample_plots
    op.add_column('field_inventory_sample_plots',
        sa.Column('firewood_kg_per_100sqm_per_year', sa.Numeric(precision=15, scale=6), nullable=True),
        schema='public'
    )
    op.add_column('field_inventory_sample_plots',
        sa.Column('grass_kg_per_100sqm_per_year', sa.Numeric(precision=15, scale=6), nullable=True),
        schema='public'
    )
    op.add_column('field_inventory_sample_plots',
        sa.Column('bedding_material_kg_per_100sqm_per_year', sa.Numeric(precision=15, scale=6), nullable=True),
        schema='public'
    )
    op.add_column('field_inventory_sample_plots',
        sa.Column('ntfp_kg_per_100sqm_per_year', sa.Numeric(precision=15, scale=6), nullable=True),
        schema='public'
    )

    # Add NTFP aggregate columns to field_inventory_block_summary
    op.add_column('field_inventory_block_summary',
        sa.Column('firewood_kg_per_ha', sa.Numeric(precision=15, scale=6), nullable=True),
        schema='public'
    )
    op.add_column('field_inventory_block_summary',
        sa.Column('grass_kg_per_ha', sa.Numeric(precision=15, scale=6), nullable=True),
        schema='public'
    )
    op.add_column('field_inventory_block_summary',
        sa.Column('bedding_material_kg_per_ha', sa.Numeric(precision=15, scale=6), nullable=True),
        schema='public'
    )
    op.add_column('field_inventory_block_summary',
        sa.Column('ntfp_kg_per_ha', sa.Numeric(precision=15, scale=6), nullable=True),
        schema='public'
    )


def downgrade() -> None:
    # Remove NTFP columns from field_inventory_block_summary
    op.drop_column('field_inventory_block_summary', 'ntfp_kg_per_ha', schema='public')
    op.drop_column('field_inventory_block_summary', 'bedding_material_kg_per_ha', schema='public')
    op.drop_column('field_inventory_block_summary', 'grass_kg_per_ha', schema='public')
    op.drop_column('field_inventory_block_summary', 'firewood_kg_per_ha', schema='public')

    # Remove NTFP columns from field_inventory_sample_plots
    op.drop_column('field_inventory_sample_plots', 'ntfp_kg_per_100sqm_per_year', schema='public')
    op.drop_column('field_inventory_sample_plots', 'bedding_material_kg_per_100sqm_per_year', schema='public')
    op.drop_column('field_inventory_sample_plots', 'grass_kg_per_100sqm_per_year', schema='public')
    op.drop_column('field_inventory_sample_plots', 'firewood_kg_per_100sqm_per_year', schema='public')
