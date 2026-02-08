-- Simplified FAST version: Only query roads table (most common reference)
CREATE OR REPLACE FUNCTION rasters.find_nearest_feature_fast(p_lon double precision, p_lat double precision)
 RETURNS text
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_point GEOMETRY;
    v_nearest_feature TEXT;
    v_distance_m DOUBLE PRECISION;
    v_azimuth DOUBLE PRECISION;
    v_direction TEXT;
BEGIN
    -- Create point geometry
    v_point := ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326);

    -- Find nearest road feature ONLY (for speed)
    SELECT
        COALESCE(name, name_en, highway) as name,
        ST_Distance(ST_Transform(v_point, 32645), ST_Transform(geom, 32645)) as distance_m,
        degrees(ST_Azimuth(v_point, ST_ClosestPoint(geom, v_point))) as azimuth
    INTO v_nearest_feature, v_distance_m, v_azimuth
    FROM infrastructure.road
    WHERE (name IS NOT NULL OR name_en IS NOT NULL OR highway IS NOT NULL)
    ORDER BY ST_Distance(ST_Transform(v_point, 32645), ST_Transform(geom, 32645))
    LIMIT 1;

    -- If no road found, return null
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
