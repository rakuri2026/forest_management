"""
Script to add administrative location detection to analysis.py
Adds spatial intersection with province, district, municipality, ward, and watershed
"""

# Read the file
with open('backend/app/services/analysis.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find where to insert the new function (after analyze_soil_geometry but before analyze_admin_boundaries)
# We'll add it right after the soil function definitions

new_function = '''

def get_administrative_location(geometry_wkt: str, db: Session) -> Dict[str, Any]:
    """
    Get administrative location by intersecting geometry centroid with admin boundaries

    Args:
        geometry_wkt: WKT string of geometry
        db: Database session

    Returns:
        Dict with: province, district, municipality, ward, watershed, major_river_basin
    """
    location = {}

    # Query for province
    province_query = text("""
        SELECT p.province
        FROM admin.province p
        WHERE ST_Intersects(
            p.shape,
            ST_Centroid(ST_GeomFromText(:wkt, 4326))
        )
        LIMIT 1
    """)
    province_result = db.execute(province_query, {"wkt": geometry_wkt}).first()
    location["province"] = province_result.province if province_result else None

    # Query for municipality (includes district)
    municipality_query = text("""
        SELECT m.district, m.gapa_napa as municipality
        FROM admin.municipality m
        WHERE ST_Intersects(
            m.geom,
            ST_Centroid(ST_GeomFromText(:wkt, 4326))
        )
        LIMIT 1
    """)
    municipality_result = db.execute(municipality_query, {"wkt": geometry_wkt}).first()
    if municipality_result:
        location["district"] = municipality_result.district
        location["municipality"] = municipality_result.municipality
    else:
        location["district"] = None
        location["municipality"] = None

    # Query for ward
    ward_query = text("""
        SELECT w.ward
        FROM admin.ward w
        WHERE ST_Intersects(
            w.geom,
            ST_Centroid(ST_GeomFromText(:wkt, 4326))
        )
        LIMIT 1
    """)
    ward_result = db.execute(ward_query, {"wkt": geometry_wkt}).first()
    location["ward"] = str(ward_result.ward) if ward_result else None

    # Query for watershed
    watershed_query = text("""
        SELECT w."watershed name" as watershed_name, w."major river basin" as major_river_basin
        FROM admin."watershed_Nepal" w
        WHERE ST_Intersects(
            w.geom,
            ST_Centroid(ST_GeomFromText(:wkt, 4326))
        )
        LIMIT 1
    """)
    watershed_result = db.execute(watershed_query, {"wkt": geometry_wkt}).first()
    if watershed_result:
        location["watershed"] = watershed_result.watershed_name
        location["major_river_basin"] = watershed_result.major_river_basin
    else:
        location["watershed"] = None
        location["major_river_basin"] = None

    return location
'''

# Insert the new function before analyze_admin_boundaries
# Find the position to insert
insert_marker = 'async def analyze_admin_boundaries(calculation_id: UUID, db: Session) -> Dict[str, Any]:'
insert_pos = content.find(insert_marker)

if insert_pos != -1:
    # Insert before analyze_admin_boundaries
    content = content[:insert_pos] + new_function + '\n\n' + content[insert_pos:]
    print("SUCCESS: Added get_administrative_location function")
else:
    print("ERROR: Could not find insertion point")
    exit(1)

# Now add the call to get_administrative_location in analyze_block_geometry
# Find the soil analysis call
soil_marker = '    # 14. Soil Texture\n    soil_results = analyze_soil_geometry(block_wkt, db)\n    block_results.update(soil_results)'
soil_pos = content.find(soil_marker)

if soil_pos != -1:
    # Add location detection after soil
    location_code = '''

    # 15. Administrative Location (Province, District, Municipality, Ward, Watershed)
    location_results = get_administrative_location(block_wkt, db)
    block_results.update(location_results)'''

    # Find the end of the soil block
    insert_after = soil_pos + len(soil_marker)
    content = content[:insert_after] + location_code + content[insert_after:]
    print("SUCCESS: Added location detection to analyze_block_geometry")
else:
    print("ERROR: Could not find soil analysis in analyze_block_geometry")
    exit(1)

# Now add whole forest location detection in analyze_forest_boundary
# Find where vector_results are updated
vector_marker = '    # 3. Vector analysis\n    vector_results = await analyze_vectors(calculation_id, db)\n    results.update(vector_results)'
vector_pos = content.find(vector_marker)

if vector_pos != -1:
    # Add whole forest location after vector analysis
    whole_location_code = '''

    # 3b. Get administrative location for whole forest
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

    insert_after = vector_pos + len(vector_marker)
    content = content[:insert_after] + whole_location_code + content[insert_after:]
    print("SUCCESS: Added whole forest location detection to analyze_forest_boundary")
else:
    print("ERROR: Could not find vector analysis in analyze_forest_boundary")
    exit(1)

# Write the updated content
with open('backend/app/services/analysis.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\nSUCCESS: Successfully added administrative location detection!")
print("\nAdded features:")
print("  - get_administrative_location() function")
print("  - Per-block location detection (province, district, municipality, ward, watershed)")
print("  - Whole forest location detection (with 'whole_' prefix)")
print("  - Uses ST_Centroid + ST_Intersects for spatial queries")
