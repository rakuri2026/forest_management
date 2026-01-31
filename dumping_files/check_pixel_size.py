"""
Check canopy raster pixel size
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')
from app.core.database import SessionLocal
from sqlalchemy import text
import math

db = SessionLocal()
try:
    # Get raster metadata for tiles that intersect Dunetar
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
            rid,
            ST_ScaleX(rast) as scale_x,
            ST_ScaleY(rast) as scale_y,
            ST_Width(rast) as width,
            ST_Height(rast) as height,
            ST_PixelWidth(rast) as pixel_width,
            ST_PixelHeight(rast) as pixel_height,
            ST_XMin(ST_Envelope(rast)) as xmin,
            ST_YMin(ST_Envelope(rast)) as ymin,
            ST_XMax(ST_Envelope(rast)) as xmax,
            ST_YMax(ST_Envelope(rast)) as ymax
        FROM rasters.canopy_height, dunetar_polygon
        WHERE ST_Intersects(rast, geom)
        ORDER BY rid
    """)

    results = db.execute(query).fetchall()

    print("=" * 80)
    print("Canopy Raster Pixel Size for Dunetar-Intersecting Tiles")
    print("=" * 80)

    for r in results:
        print(f"\nTile {r.rid}:")
        print(f"  Dimensions: {r.width} x {r.height} pixels")
        print(f"  Scale X (degrees): {r.scale_x}")
        print(f"  Scale Y (degrees): {r.scale_y}")
        print(f"  Pixel Width: {r.pixel_width}")
        print(f"  Pixel Height: {r.pixel_height}")
        print(f"  Tile BBox: X({r.xmin:.6f} to {r.xmax:.6f}), Y({r.ymin:.6f} to {r.ymax:.6f})")

        # Calculate real-world pixel size in meters (approximately at this latitude)
        # At latitude 27°, 1 degree ≈ 111 km longitude, 111 km latitude
        lat = 27.438
        pixel_width_m = abs(r.scale_x) * 111000 * math.cos(math.radians(lat))
        pixel_height_m = abs(r.scale_y) * 111000

        print(f"  Pixel size in meters: ~{pixel_width_m:.1f}m x {pixel_height_m:.1f}m")
        print(f"  Pixel area: ~{pixel_width_m * pixel_height_m:.1f} m²")

    # Calculate expected pixel count for Dunetar block
    dunetar_area_m2 = 101.53 * 10000  # 101.53 hectares
    pixel_area_m2 = pixel_width_m * pixel_height_m

    expected_pixels = dunetar_area_m2 / pixel_area_m2

    print()
    print("=" * 80)
    print("Expected Pixel Count Calculation")
    print("=" * 80)
    print(f"Dunetar area: 101.53 hectares = {dunetar_area_m2:.0f} m²")
    print(f"Pixel area: ~{pixel_area_m2:.1f} m²")
    print(f"Expected pixels: ~{expected_pixels:.0f}")
    print()
    print(f"Actual pixels (PostGIS): 2,119")
    print(f"Actual pixels (QGIS): ~1,500")
    print()

    # Calculate what pixel size would give 1,500 pixels
    qgis_pixel_area = dunetar_area_m2 / 1500
    qgis_pixel_size = math.sqrt(qgis_pixel_area)

    print(f"For QGIS to get 1,500 pixels, pixel size would be: ~{qgis_pixel_size:.1f}m x {qgis_pixel_size:.1f}m")
    print(f"PostGIS pixel size is: ~{pixel_width_m:.1f}m x {pixel_height_m:.1f}m")
    print()

    ratio = pixel_width_m / qgis_pixel_size
    print(f"Ratio: PostGIS pixels are {ratio:.2f}x smaller than QGIS expects")

finally:
    db.close()
