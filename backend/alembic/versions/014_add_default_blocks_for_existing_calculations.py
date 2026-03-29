"""Add default blocks for existing PENDING calculations

Revision ID: 014
Revises: 012
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = '014'
down_revision = '012'
branch_labels = None
depends_on = None

def upgrade():
    """
    Create default single blocks for existing PENDING calculations
    that have no forest_blocks records.
    """

    connection = op.get_bind()

    # Find calculations without blocks
    result = connection.execute(text("""
        SELECT c.id, c.forest_name, c.boundary_geom
        FROM calculations c
        LEFT JOIN forest_blocks fb ON fb.calculation_id = c.id
        WHERE fb.id IS NULL
        AND c.status = 'PENDING'
        AND c.boundary_geom IS NOT NULL
    """))

    calculations = result.fetchall()

    print(f"Found {len(calculations)} calculations without blocks")

    for calc_id, forest_name, boundary_geom in calculations:
        # Create default block name
        block_name = f"{forest_name} - Block 1" if forest_name else "Block 1"

        print(f"Creating default block for calculation {calc_id}: {block_name}")

        # Create ForestBlock record
        connection.execute(text("""
            INSERT INTO forest_blocks (id, calculation_id, name, geometry, area_hectares, index, created_at)
            VALUES (
                gen_random_uuid(),
                :calc_id,
                :block_name,
                (SELECT boundary_geom FROM calculations WHERE id = :calc_id),
                (SELECT ST_Area(ST_Transform(boundary_geom, 32645)) / 10000
                 FROM calculations WHERE id = :calc_id),
                0,
                NOW()
            )
        """), {"calc_id": calc_id, "block_name": block_name})

        # Update result_data with block info
        connection.execute(text("""
            UPDATE calculations
            SET result_data = COALESCE(result_data, '{}'::jsonb) || jsonb_build_object(
                'blocks', jsonb_build_array(
                    jsonb_build_object(
                        'block_index', 0,
                        'block_name', :block_name,
                        'area_hectares', (SELECT ST_Area(ST_Transform(boundary_geom, 32645)) / 10000
                                          FROM calculations WHERE id = :calc_id),
                        'geometry', (SELECT ST_AsGeoJSON(boundary_geom)::jsonb
                                     FROM calculations WHERE id = :calc_id)
                    )
                ),
                'total_blocks', 1
            )
            WHERE id = :calc_id
        """), {"calc_id": calc_id, "block_name": block_name})

    print(f"Successfully created default blocks for {len(calculations)} calculations")

def downgrade():
    """Remove auto-created default blocks."""
    connection = op.get_bind()

    print("Removing auto-created default blocks...")

    # This is optional - only remove blocks that match the default naming pattern
    result = connection.execute(text("""
        DELETE FROM forest_blocks
        WHERE name LIKE '% - Block 1'
        AND index = 0
        RETURNING id
    """))

    deleted_count = len(result.fetchall())
    print(f"Removed {deleted_count} default blocks")
