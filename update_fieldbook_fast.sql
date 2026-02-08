-- Step 1: Create fast function
CREATE OR REPLACE FUNCTION rasters.find_nearest_road(p_lon double precision, p_lat double precision)
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
    v_point := ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326);

    SELECT
        COALESCE(name, name_en, highway),
        ST_Distance(ST_Transform(v_point, 32645), ST_Transform(geom, 32645)),
        degrees(ST_Azimuth(v_point, ST_ClosestPoint(geom, v_point)))
    INTO v_nearest_feature, v_distance_m, v_azimuth
    FROM infrastructure.road
    WHERE (name IS NOT NULL OR name_en IS NOT NULL OR highway IS NOT NULL)
    ORDER BY ST_Distance(ST_Transform(v_point, 32645), ST_Transform(geom, 32645))
    LIMIT 1;

    IF v_nearest_feature IS NULL THEN
        RETURN NULL;
    END IF;

    IF v_azimuth >= 337.5 OR v_azimuth < 22.5 THEN v_direction := 'N';
    ELSIF v_azimuth >= 22.5 AND v_azimuth < 67.5 THEN v_direction := 'NE';
    ELSIF v_azimuth >= 67.5 AND v_azimuth < 112.5 THEN v_direction := 'E';
    ELSIF v_azimuth >= 112.5 AND v_azimuth < 157.5 THEN v_direction := 'SE';
    ELSIF v_azimuth >= 157.5 AND v_azimuth < 202.5 THEN v_direction := 'S';
    ELSIF v_azimuth >= 202.5 AND v_azimuth < 247.5 THEN v_direction := 'SW';
    ELSIF v_azimuth >= 247.5 AND v_azimuth < 292.5 THEN v_direction := 'W';
    ELSIF v_azimuth >= 292.5 AND v_azimuth < 337.5 THEN v_direction := 'NW';
    END IF;

    RETURN v_nearest_feature || ': ' || v_direction || '(' || ROUND(v_azimuth)::TEXT || '°) ' || ROUND(v_distance_m)::TEXT || 'm';
EXCEPTION
    WHEN OTHERS THEN RETURN NULL;
END;
$function$;

-- Step 2: Update fieldbook using fast function
WITH references_raw AS (
    SELECT
        id,
        point_number,
        rasters.find_nearest_road(longitude, latitude) as ref
    FROM public.fieldbook
    WHERE calculation_id = 'd35dba3c-b039-434f-88b8-08accd318407'
    ORDER BY point_number
),
references_with_lag AS (
    SELECT
        id,
        ref,
        LAG(ref) OVER (ORDER BY point_number) as prev_ref
    FROM references_raw
)
UPDATE public.fieldbook fb
SET reference = CASE
    WHEN rwl.ref IS NOT NULL AND (rwl.prev_ref IS NULL OR rwl.ref != rwl.prev_ref) THEN rwl.ref
    ELSE NULL
END
FROM references_with_lag rwl
WHERE fb.id = rwl.id;
