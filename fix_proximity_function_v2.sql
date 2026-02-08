CREATE OR REPLACE FUNCTION rasters.analyze_nearby_features(p_geom_wkt text)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_geom GEOMETRY;
    v_centroid GEOMETRY;
    v_result JSONB;
    v_north_features TEXT[];
    v_east_features TEXT[];
    v_south_features TEXT[];
    v_west_features TEXT[];
    v_feature_record RECORD;
    v_azimuth DOUBLE PRECISION;
    v_distance_m DOUBLE PRECISION;
    v_direction TEXT;
    v_formatted TEXT;
BEGIN
    -- Convert WKT to geometry (assume SRID 4326)
    v_geom := ST_Force2D(ST_GeomFromText(p_geom_wkt, 4326));
    v_centroid := ST_Centroid(v_geom);

    -- Initialize arrays
    v_north_features := ARRAY[]::TEXT[];
    v_east_features := ARRAY[]::TEXT[];
    v_south_features := ARRAY[]::TEXT[];
    v_west_features := ARRAY[]::TEXT[];

    -- UNION ALL features from all tables with distance and azimuth
    -- Then keep only closest instance of each feature per direction
    FOR v_feature_record IN
        WITH all_features_raw AS (
            -- River lines
            SELECT
                COALESCE(river_name, features) as name,
                ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645)) as distance_m,
                degrees(ST_Azimuth(v_centroid, ST_ClosestPoint(geom, v_centroid))) as azimuth
            FROM river.river_line
            WHERE ST_DWithin(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645), 100)
                AND (river_name IS NOT NULL OR features IS NOT NULL)

            UNION ALL

            -- Ridges
            SELECT
                ridge_name as name,
                ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645)) as distance_m,
                degrees(ST_Azimuth(v_centroid, ST_ClosestPoint(geom, v_centroid))) as azimuth
            FROM river.ridge
            WHERE ST_DWithin(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645), 100)
                AND ridge_name IS NOT NULL

            UNION ALL

            -- Roads
            SELECT
                COALESCE(name, name_en, highway) as name,
                ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645)) as distance_m,
                degrees(ST_Azimuth(v_centroid, ST_ClosestPoint(geom, v_centroid))) as azimuth
            FROM infrastructure.road
            WHERE ST_DWithin(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645), 100)
                AND (name IS NOT NULL OR name_en IS NOT NULL OR highway IS NOT NULL)

            UNION ALL

            -- POI
            SELECT
                COALESCE(name, name_en, amenity, shop, tourism) as name,
                ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645)) as distance_m,
                degrees(ST_Azimuth(v_centroid, ST_ClosestPoint(geom, v_centroid))) as azimuth
            FROM infrastructure.poi
            WHERE ST_DWithin(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645), 100)
                AND (name IS NOT NULL OR name_en IS NOT NULL OR amenity IS NOT NULL OR shop IS NOT NULL OR tourism IS NOT NULL)

            UNION ALL

            -- Health facilities
            SELECT
                COALESCE(hf_type, vdc_name1) as name,
                ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645)) as distance_m,
                degrees(ST_Azimuth(v_centroid, ST_ClosestPoint(geom, v_centroid))) as azimuth
            FROM infrastructure.health_facilities
            WHERE ST_DWithin(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645), 100)
                AND (hf_type IS NOT NULL OR vdc_name1 IS NOT NULL)

            UNION ALL

            -- Education facilities
            SELECT
                COALESCE(name, name_en, amenity) as name,
                ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645)) as distance_m,
                degrees(ST_Azimuth(v_centroid, ST_ClosestPoint(geom, v_centroid))) as azimuth
            FROM infrastructure.education_facilities
            WHERE ST_DWithin(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645), 100)
                AND (name IS NOT NULL OR name_en IS NOT NULL OR amenity IS NOT NULL)

            UNION ALL

            -- Settlements
            SELECT
                vil_name as name,
                ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(shape, 32645)) as distance_m,
                degrees(ST_Azimuth(v_centroid, ST_ClosestPoint(shape, v_centroid))) as azimuth
            FROM admin.settlement
            WHERE ST_DWithin(ST_Transform(v_geom, 32645), ST_Transform(shape, 32645), 100)
                AND vil_name IS NOT NULL

            UNION ALL

            -- Forest boundaries
            SELECT
                COALESCE(description, "boundary of") as name,
                ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645)) as distance_m,
                degrees(ST_Azimuth(v_centroid, ST_ClosestPoint(geom, v_centroid))) as azimuth
            FROM admin."esa_forest_Boundary"
            WHERE ST_DWithin(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645), 100)
                AND (description IS NOT NULL OR "boundary of" IS NOT NULL)
        ),
        -- Keep only the closest instance of each unique feature
        unique_features AS (
            SELECT DISTINCT ON (name)
                name, distance_m, azimuth
            FROM all_features_raw
            WHERE name IS NOT NULL AND name != ''
            ORDER BY name, distance_m
        )
        SELECT name, distance_m, azimuth
        FROM unique_features
        ORDER BY distance_m
        LIMIT 50  -- Limit to 50 nearest unique features
    LOOP
        v_azimuth := v_feature_record.azimuth;
        v_distance_m := v_feature_record.distance_m;

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

        -- Format as: "Feature Name: DIR(azimuth°) distance"
        v_formatted := v_feature_record.name || ': ' || v_direction || '(' || ROUND(v_azimuth)::TEXT || '°) ' || ROUND(v_distance_m)::TEXT || 'm';

        -- Assign to quadrant arrays (N/E/S/W for broad grouping)
        IF v_azimuth >= 315 OR v_azimuth < 45 THEN
            v_north_features := array_append(v_north_features, v_formatted);
        ELSIF v_azimuth >= 45 AND v_azimuth < 135 THEN
            v_east_features := array_append(v_east_features, v_formatted);
        ELSIF v_azimuth >= 135 AND v_azimuth < 225 THEN
            v_south_features := array_append(v_south_features, v_formatted);
        ELSIF v_azimuth >= 225 AND v_azimuth < 315 THEN
            v_west_features := array_append(v_west_features, v_formatted);
        END IF;
    END LOOP;

    -- Build result JSONB with comma-separated strings
    v_result := jsonb_build_object(
        'features_north', CASE
            WHEN array_length(v_north_features, 1) > 0 THEN
                array_to_string(v_north_features, ', ')
            ELSE NULL
        END,
        'features_east', CASE
            WHEN array_length(v_east_features, 1) > 0 THEN
                array_to_string(v_east_features, ', ')
            ELSE NULL
        END,
        'features_south', CASE
            WHEN array_length(v_south_features, 1) > 0 THEN
                array_to_string(v_south_features, ', ')
            ELSE NULL
        END,
        'features_west', CASE
            WHEN array_length(v_west_features, 1) > 0 THEN
                array_to_string(v_west_features, ', ')
            ELSE NULL
        END
    );

    RETURN v_result;

EXCEPTION
    WHEN OTHERS THEN
        -- Return empty result on any error
        RETURN jsonb_build_object(
            'features_north', NULL,
            'features_east', NULL,
            'features_south', NULL,
            'features_west', NULL,
            'error', SQLERRM
        );
END;
$function$;
