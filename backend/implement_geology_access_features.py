"""
Add geology analysis, access calculation, and nearby features to analysis.py
This adds three major features:
A. Geology class percentages
B. Access (distance and direction to district headquarters)
C. Nearby features within 100m (by direction: N, E, S, W)
"""

# Read the analysis.py file
with open('app/services/analysis.py', 'r', encoding='utf-8') as f:
    content = f.read()

# ====================
# PART 1: Add geology analysis function
# ====================

geology_function = '''

def analyze_geology_geometry(geometry_wkt: str, db: Session) -> Dict[str, Any]:
    """
    Analyze geology classes that intersect with the geometry
    Returns percentage coverage for each geology class

    Args:
        geometry_wkt: WKT string of geometry
        db: Database session

    Returns:
        Dict with geology_percentages: {class_name: percentage}
    """
    geology_query = text("""
        WITH input_geom AS (
            SELECT ST_GeomFromText(:wkt, 4326) as geom
        ),
        total_area AS (
            SELECT ST_Area(ST_Transform(geom, 32645)) as area
            FROM input_geom
        ),
        geology_intersections AS (
            SELECT
                g."geology class" as geology_class,
                ST_Area(
                    ST_Transform(
                        ST_Intersection(g.geom, i.geom),
                        32645
                    )
                ) as intersection_area
            FROM geology.geology g, input_geom i
            WHERE ST_Intersects(g.geom, i.geom)
            AND g."geology class" IS NOT NULL
            AND g."geology class" != 'No Data'
        )
        SELECT
            geology_class,
            (intersection_area / (SELECT area FROM total_area)) * 100 as percentage
        FROM geology_intersections
        WHERE intersection_area > 0
        ORDER BY percentage DESC
    """)

    try:
        result = db.execute(geology_query, {"wkt": geometry_wkt})
        geology_data = {}

        for row in result:
            if row.geology_class and row.percentage:
                geology_data[row.geology_class] = round(float(row.percentage), 2)

        return {
            "geology_percentages": geology_data if geology_data else None
        }
    except Exception as e:
        print(f"Geology analysis error: {e}")
        return {"geology_percentages": None}


def calculate_access_info(geometry_wkt: str, db: Session) -> Dict[str, Any]:
    """
    Calculate access information: distance and direction to nearest district headquarters

    Args:
        geometry_wkt: WKT string of geometry
        db: Database session

    Returns:
        Dict with access_info: "Location Direction (degrees°) distance km"
    """
    access_query = text("""
        WITH input_geom AS (
            SELECT
                ST_GeomFromText(:wkt, 4326) as geom,
                ST_Centroid(ST_GeomFromText(:wkt, 4326)) as centroid
        ),
        nearest_hq AS (
            SELECT
                dh."head quarter" as name,
                ST_Distance(
                    ST_Transform(i.centroid, 32645),
                    ST_Transform(dh.geom, 32645)
                ) / 1000.0 as distance_km,
                degrees(
                    ST_Azimuth(
                        i.centroid,
                        dh.geom
                    )
                ) as azimuth_degrees
            FROM admin."district Headquarter" dh, input_geom i
            WHERE dh."head quarter" IS NOT NULL
            ORDER BY ST_Distance(i.centroid, dh.geom)
            LIMIT 1
        )
        SELECT
            name,
            distance_km,
            azimuth_degrees,
            CASE
                WHEN azimuth_degrees >= 337.5 OR azimuth_degrees < 22.5 THEN 'North'
                WHEN azimuth_degrees >= 22.5 AND azimuth_degrees < 67.5 THEN 'Northeast'
                WHEN azimuth_degrees >= 67.5 AND azimuth_degrees < 112.5 THEN 'East'
                WHEN azimuth_degrees >= 112.5 AND azimuth_degrees < 157.5 THEN 'Southeast'
                WHEN azimuth_degrees >= 157.5 AND azimuth_degrees < 202.5 THEN 'South'
                WHEN azimuth_degrees >= 202.5 AND azimuth_degrees < 247.5 THEN 'Southwest'
                WHEN azimuth_degrees >= 247.5 AND azimuth_degrees < 292.5 THEN 'West'
                ELSE 'Northwest'
            END as direction
        FROM nearest_hq
    """)

    try:
        result = db.execute(access_query, {"wkt": geometry_wkt}).first()

        if result and result.name:
            access_str = f"{result.name} {result.direction} ({int(result.azimuth_degrees)}°) {result.distance_km:.1f} km"
            return {"access_info": access_str}
        else:
            return {"access_info": None}
    except Exception as e:
        print(f"Access calculation error: {e}")
        return {"access_info": None}


def analyze_nearby_features(geometry_wkt: str, db: Session) -> Dict[str, Any]:
    """
    Find natural and infrastructure features within 100m of boundary
    Reports features by direction: North, East, South, West

    Args:
        geometry_wkt: WKT string of geometry
        db: Database session

    Returns:
        Dict with features_north, features_east, features_south, features_west
    """

    # Define feature tables and their name columns
    feature_tables = [
        ('river.river_line', ['river_name', 'features']),
        ('river.ridge', ['ridge_name']),
        ('infrastructure.road', ['name', 'name_en', 'highway']),
        ('infrastructure.poi', ['name', 'name_en', 'amenity', 'shop', 'tourism']),
        ('infrastructure.health_facilities', ['hf_type', 'vdc_name1']),
        ('infrastructure.education_facilities', ['name', 'name_en', 'amenity']),
        ('buildings.building', ['Building']),  # Generic name
        ('admin.settlement', ['vil_name']),
        ('admin."esa_forest_Boundary"', ['description', '"boundary of"']),
    ]

    directions = {
        'north': (315, 45),      # 315° to 45°
        'east': (45, 135),       # 45° to 135°
        'south': (135, 225),     # 135° to 225°
        'west': (225, 315)       # 225° to 315° (wraps to 360/0)
    }

    result_features = {}

    for direction_name, (start_angle, end_angle) in directions.items():
        features_list = []

        # Build query for this direction
        for table_name, name_columns in feature_tables:
            # Build COALESCE for name columns
            name_coalesce = "COALESCE(" + ", ".join([f"f.{col}" if '"' not in col else f'f.{col}' for col in name_columns]) + ")"

            # Handle angle wrapping for North (315-45)
            if direction_name == 'north':
                angle_condition = f"(azimuth_deg >= {start_angle} OR azimuth_deg < {end_angle})"
            else:
                angle_condition = f"(azimuth_deg >= {start_angle} AND azimuth_deg < {end_angle})"

            direction_query = text(f"""
                WITH input_geom AS (
                    SELECT ST_GeomFromText(:wkt, 4326) as geom
                ),
                nearby AS (
                    SELECT
                        {name_coalesce} as feature_name,
                        ST_Distance(ST_Transform(i.geom, 32645), ST_Transform(f.geom, 32645)) as distance_m,
                        degrees(ST_Azimuth(ST_Centroid(i.geom), ST_ClosestPoint(f.geom, ST_Centroid(i.geom)))) as azimuth_deg
                    FROM {table_name} f, input_geom i
                    WHERE ST_DWithin(ST_Transform(i.geom, 32645), ST_Transform(f.geom, 32645), 100)
                )
                SELECT DISTINCT feature_name
                FROM nearby
                WHERE feature_name IS NOT NULL
                AND feature_name != ''
                AND {angle_condition}
                LIMIT 10
            """)

            try:
                result = db.execute(direction_query, {"wkt": geometry_wkt})
                for row in result:
                    if row.feature_name and row.feature_name.strip():
                        features_list.append(row.feature_name.strip())
            except Exception as e:
                # Skip tables that might have issues
                continue

        # Store comma-separated list or None
        result_features[f"features_{direction_name}"] = ", ".join(features_list) if features_list else None

    return result_features
'''

# Find where to insert these functions - before analyze_admin_boundaries
insert_marker = 'async def analyze_admin_boundaries(calculation_id: UUID, db: Session) -> Dict[str, Any]:'
insert_pos = content.find(insert_marker)

if insert_pos == -1:
    print("ERROR: Could not find insertion point")
    exit(1)

content = content[:insert_pos] + geology_function + '\n\n' + content[insert_pos:]
print("SUCCESS: Added geology, access, and nearby features functions")

# ====================
# PART 2: Add calls to these functions in analyze_block_geometry
# ====================

# Find the location detection call in analyze_block_geometry
location_marker = '''    # 15. Administrative Location (Province, District, Municipality, Ward, Watershed)
    location_results = get_administrative_location(block_wkt, db)
    block_results.update(location_results)'''

location_pos = content.find(location_marker)

if location_pos == -1:
    print("ERROR: Could not find location detection in analyze_block_geometry")
    exit(1)

# Add after location detection
additional_analysis = '''

    # 16. Geology Analysis
    geology_results = analyze_geology_geometry(block_wkt, db)
    block_results.update(geology_results)

    # 17. Access Information
    access_results = calculate_access_info(block_wkt, db)
    block_results.update(access_results)

    # 18. Nearby Features (within 100m, by direction)
    nearby_results = analyze_nearby_features(block_wkt, db)
    block_results.update(nearby_results)'''

insert_after = location_pos + len(location_marker)
content = content[:insert_after] + additional_analysis + content[insert_after:]
print("SUCCESS: Added block-level geology, access, and nearby features analysis")

# ====================
# PART 3: Add calls for whole forest analysis
# ====================

# Find the whole forest location detection
whole_location_marker = '''    # 3b. Get administrative location for whole forest
    whole_geom_query = text("""
        SELECT ST_AsText(boundary_geom) as wkt
        FROM public.calculations
        WHERE id = :calc_id
    """)
    whole_geom = db.execute(whole_geom_query, {"calc_id": str(calculation_id)}).first()
    if whole_geom:
        whole_location = get_administrative_location(whole_geom.wkt, db)
        # Prefix keys with "whole_" to distinguish from block-level data
        results["whole_province"] = whole_location.get("province")
        results["whole_district"] = whole_location.get("district")
        results["whole_municipality"] = whole_location.get("municipality")
        results["whole_ward"] = whole_location.get("ward")
        results["whole_watershed"] = whole_location.get("watershed")
        results["whole_major_river_basin"] = whole_location.get("major_river_basin")'''

whole_location_pos = content.find(whole_location_marker)

if whole_location_pos == -1:
    print("ERROR: Could not find whole forest location detection")
    exit(1)

# Add after whole forest location
whole_additional = '''

    # 3c. Geology analysis for whole forest
    if whole_geom:
        whole_geology = analyze_geology_geometry(whole_geom.wkt, db)
        results["whole_geology_percentages"] = whole_geology.get("geology_percentages")

    # 3d. Access information for whole forest
    if whole_geom:
        whole_access = calculate_access_info(whole_geom.wkt, db)
        results["whole_access_info"] = whole_access.get("access_info")

    # 3e. Nearby features for whole forest
    if whole_geom:
        whole_features = analyze_nearby_features(whole_geom.wkt, db)
        results["whole_features_north"] = whole_features.get("features_north")
        results["whole_features_east"] = whole_features.get("features_east")
        results["whole_features_south"] = whole_features.get("features_south")
        results["whole_features_west"] = whole_features.get("features_west")'''

insert_after_whole = whole_location_pos + len(whole_location_marker)
content = content[:insert_after_whole] + whole_additional + content[insert_after_whole:]
print("SUCCESS: Added whole forest geology, access, and nearby features analysis")

# Write the updated file
with open('app/services/analysis.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n" + "="*60)
print("IMPLEMENTATION COMPLETE!")
print("="*60)
print("\nAdded features:")
print("  A. Geology Analysis - percentage coverage by geology class")
print("  B. Access Info - distance and direction to district headquarters")
print("  C. Nearby Features - features within 100m by direction (N/E/S/W)")
print("\nAll features added to:")
print("  - Block-level analysis")
print("  - Whole forest analysis")
print("\nNext steps:")
print("  1. Restart the backend server")
print("  2. Update TypeScript types")
print("  3. Add UI rows in CalculationDetail.tsx")
