-- OPTIMIZED VERSION: Filter within 100m FIRST, then UNION, then find nearest
-- This uses spatial indexes effectively and only processes nearby features
CREATE OR REPLACE FUNCTION rasters.find_nearest_feature(p_lon double precision, p_lat double precision)
 RETURNS text
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_point GEOMETRY;
    v_point_utm GEOMETRY;
    v_nearest_feature TEXT;
    v_distance_m DOUBLE PRECISION;
    v_azimuth DOUBLE PRECISION;
    v_direction TEXT;
BEGIN
    -- Create point geometry (WGS84)
    v_point := ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326);

    -- Transform to UTM for distance calculations
    v_point_utm := ST_Transform(v_point, 32645);

    -- STRATEGY: Filter within 100m FIRST using ST_DWithin (uses spatial indexes!)
    -- Then UNION the filtered results, then find nearest
    WITH nearby_features AS (
        -- Rivers within 100m
        SELECT
            COALESCE(river_name, features) as name,
            ST_Distance(v_point_utm, ST_Transform(geom, 32645)) as distance_m,
            degrees(ST_Azimuth(v_point, ST_ClosestPoint(geom, v_point))) as azimuth
        FROM river.river_line
        WHERE (river_name IS NOT NULL OR features IS NOT NULL)
          AND ST_DWithin(ST_Transform(geom, 32645), v_point_utm, 100)

        UNION ALL

        -- Roads within 100m
        SELECT
            COALESCE(name, name_en, highway) as name,
            ST_Distance(v_point_utm, ST_Transform(geom, 32645)) as distance_m,
            degrees(ST_Azimuth(v_point, ST_ClosestPoint(geom, v_point))) as azimuth
        FROM infrastructure.road
        WHERE (name IS NOT NULL OR name_en IS NOT NULL OR highway IS NOT NULL)
          AND ST_DWithin(ST_Transform(geom, 32645), v_point_utm, 100)

        UNION ALL

        -- Settlements within 100m
        SELECT
            vil_name as name,
            ST_Distance(v_point_utm, ST_Transform(shape, 32645)) as distance_m,
            degrees(ST_Azimuth(v_point, ST_ClosestPoint(shape, v_point))) as azimuth
        FROM admin.settlement
        WHERE vil_name IS NOT NULL
          AND ST_DWithin(ST_Transform(shape, 32645), v_point_utm, 100)

        UNION ALL

        -- POI within 100m
        SELECT
            COALESCE(name, name_en, amenity) as name,
            ST_Distance(v_point_utm, ST_Transform(geom, 32645)) as distance_m,
            degrees(ST_Azimuth(v_point, ST_ClosestPoint(geom, v_point))) as azimuth
        FROM infrastructure.poi
        WHERE (name IS NOT NULL OR name_en IS NOT NULL OR amenity IS NOT NULL)
          AND ST_DWithin(ST_Transform(geom, 32645), v_point_utm, 100)
    )
    SELECT name, distance_m, azimuth
    INTO v_nearest_feature, v_distance_m, v_azimuth
    FROM nearby_features
    WHERE name IS NOT NULL AND name != ''
    ORDER BY distance_m
    LIMIT 1;

    -- If no feature found within 100m, return null
    IF v_nearest_feature IS NULL THEN
        RETURN NULL;
    END IF;

    -- Determine 8-direction compass bearing
    IF v_azimuth >= 337.5 OR v_azimuth < 22.5 THEN
        v_direction := 'N';
    ELSIF v_azimuth >= 22.5 AND v_azimuth < 67.5 THEN
        v_direction := 'NE';
    ELSIF v_azimuth >= 67.5 AND v_azimuth < 112.5 THEN
        v_direction := 'E';
    ELSIF v_azimuth >= 112.5 AND v_azimuth < 157.5 THEN
        v_direction := 'SE';
    ELSIF v_azimuth >= 157.5 AND v_azimuth < 202.5 THEN
        v_direction := 'S';
    ELSIF v_azimuth >= 202.5 AND v_azimuth < 247.5 THEN
        v_direction := 'SW';
    ELSIF v_azimuth >= 247.5 AND v_azimuth < 292.5 THEN
        v_direction := 'W';
    ELSIF v_azimuth >= 292.5 AND v_azimuth < 337.5 THEN
        v_direction := 'NW';
    END IF;

    -- Format as: "Feature: DIR(azimuth°) distance"
    RETURN v_nearest_feature || ': ' || v_direction || '(' || ROUND(v_azimuth)::TEXT || '°) ' || ROUND(v_distance_m)::TEXT || 'm';

EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$function$;
