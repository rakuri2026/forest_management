"""
Diagnose potential raster-vector alignment issues
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # Get Dunetar block geometry and analyze it in detail
    query = text("""
        WITH dunetar_geom AS (
            SELECT
                jsonb_array_elements(result_data->'blocks')->'geometry' as geom_json,
                jsonb_array_elements(result_data->'blocks')->>'block_name' as block_name
            FROM public.calculations
            WHERE forest_name = 'testForest'
        ),
        dunetar_polygon AS (
            SELECT
                ST_GeomFromGeoJSON(geom_json::text) as geom,
                block_name
            FROM dunetar_geom
            WHERE block_name = 'Dunetar'
        )
        SELECT
            block_name,
            ST_SRID(geom) as srid,
            ST_Area(geom::geography) / 10000 as area_hectares,
            ST_XMin(geom) as xmin,
            ST_YMin(geom) as ymin,
            ST_XMax(geom) as xmax,
            ST_YMax(geom) as ymax,
            ST_AsText(ST_Centroid(geom)) as centroid
        FROM dunetar_polygon
    """)

    result = db.execute(query).first()

    if result:
        print("=" * 80)
        print("Dunetar Block Geometry Details")
        print("=" * 80)
        print(f"Block Name: {result.block_name}")
        print(f"SRID: {result.srid}")
        print(f"Area: {result.area_hectares:.2f} hectares")
        print(f"Bounding Box:")
        print(f"  X: {result.xmin:.6f} to {result.xmax:.6f}")
        print(f"  Y: {result.ymin:.6f} to {result.ymax:.6f}")
        print(f"Centroid: {result.centroid}")
        print()

        # Now check how many raster tiles intersect this boundary
        query2 = text("""
            WITH dunetar_geom AS (
                SELECT
                    jsonb_array_elements(result_data->'blocks')->'geometry' as geom_json,
                    jsonb_array_elements(result_data->'blocks')->>'block_name' as block_name
                FROM public.calculations
                WHERE forest_name = 'testForest'
            ),
            dunetar_polygon AS (
                SELECT
                    ST_GeomFromGeoJSON(geom_json::text) as geom,
                    block_name
                FROM dunetar_geom
                WHERE block_name = 'Dunetar'
            )
            SELECT COUNT(*) as tile_count
            FROM rasters.canopy_height, dunetar_polygon
            WHERE ST_Intersects(rast, geom)
        """)

        result2 = db.execute(query2).first()
        print(f"Raster tiles intersecting this boundary: {result2.tile_count}")
        print()

        # Get the actual pixel values for ALL tiles
        query3 = text("""
            WITH dunetar_geom AS (
                SELECT
                    jsonb_array_elements(result_data->'blocks')->'geometry' as geom_json,
                    jsonb_array_elements(result_data->'blocks')->>'block_name' as block_name
                FROM public.calculations
                WHERE forest_name = 'testForest'
            ),
            dunetar_polygon AS (
                SELECT
                    ST_GeomFromGeoJSON(geom_json::text) as geom,
                    block_name
                FROM dunetar_geom
                WHERE block_name = 'Dunetar'
            ),
            all_tiles AS (
                SELECT
                    rid,
                    ST_Clip(rast, geom) as clipped_rast,
                    ST_XMin(ST_Envelope(rast)) as tile_xmin,
                    ST_YMin(ST_Envelope(rast)) as tile_ymin,
                    ST_XMax(ST_Envelope(rast)) as tile_xmax,
                    ST_YMax(ST_Envelope(rast)) as tile_ymax
                FROM rasters.canopy_height, dunetar_polygon
                WHERE ST_Intersects(rast, geom)
            )
            SELECT
                rid,
                tile_xmin,
                tile_ymin,
                tile_xmax,
                tile_ymax,
                (ST_SummaryStats(clipped_rast)).count as pixel_count,
                (ST_SummaryStats(clipped_rast)).sum as sum_values,
                (ST_SummaryStats(clipped_rast)).mean as mean_value,
                (ST_SummaryStats(clipped_rast)).min as min_value,
                (ST_SummaryStats(clipped_rast)).max as max_value
            FROM all_tiles
            ORDER BY rid
        """)

        results3 = db.execute(query3).fetchall()

        print(f"Raster Tiles Analysis ({len(results3)} tiles):")
        print("-" * 80)

        total_pixels = 0
        total_sum = 0

        for r in results3:
            total_pixels += r.pixel_count
            total_sum += r.sum_values

            print(f"Tile {r.rid}:")
            print(f"  BBox: X({r.tile_xmin:.6f} to {r.tile_xmax:.6f}), Y({r.tile_ymin:.6f} to {r.tile_ymax:.6f})")
            print(f"  Pixels: {r.pixel_count}, Mean: {r.mean_value:.1f}m, Min: {r.min_value:.1f}m, Max: {r.max_value:.1f}m")
            print()

        print("-" * 80)
        print(f"Total pixels: {total_pixels}")
        print(f"Overall mean: {(total_sum / total_pixels):.1f}m")
        print()

        print("Expected from QGIS analysis:")
        print("  ~1,500 total pixels")
        print("  180 pixels with 0m (12%)")
        print()
        print(f"Our analysis shows: {total_pixels} pixels")
        print(f"Difference: {total_pixels - 1500} pixels ({((total_pixels - 1500) / 1500 * 100):.1f}% more)")

finally:
    db.close()
