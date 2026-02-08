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

    -- Find nearest features in each direction (NO DISTANCE LIMIT)
    -- Get top 3 nearest per direction for variety
    FOR v_feature_record IN
        WITH all_features_raw AS (
            -- River lines
            (SELECT
                COALESCE(river_name, features) as name,
                ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645)) as distance_m,
                degrees(ST_Azimuth(v_centroid, ST_ClosestPoint(geom, v_centroid))) as azimuth
            FROM river.river_line
            WHERE (river_name IS NOT NULL OR features IS NOT NULL)
            ORDER BY ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645))
            LIMIT 20)

            UNION ALL

            -- Ridges
            (SELECT
                ridge_name as name,
                ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645)) as distance_m,
                degrees(ST_Azimuth(v_centroid, ST_ClosestPoint(geom, v_centroid))) as azimuth
            FROM river.ridge
            WHERE ridge_name IS NOT NULL
            ORDER BY ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645))
            LIMIT 10)

            UNION ALL

            -- Roads
            (SELECT
                COALESCE(name, name_en, highway) as name,
                ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645)) as distance_m,
                degrees(ST_Azimuth(v_centroid, ST_ClosestPoint(geom, v_centroid))) as azimuth
            FROM infrastructure.road
            WHERE (name IS NOT NULL OR name_en IS NOT NULL OR highway IS NOT NULL)
            ORDER BY ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645))
            LIMIT 20)

            UNION ALL

            -- POI
            (SELECT
                COALESCE(name, name_en, amenity, shop, tourism) as name,
                ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645)) as distance_m,
                degrees(ST_Azimuth(v_centroid, ST_ClosestPoint(geom, v_centroid))) as azimuth
            FROM infrastructure.poi
            WHERE (name IS NOT NULL OR name_en IS NOT NULL OR amenity IS NOT NULL OR shop IS NOT NULL OR tourism IS NOT NULL)
            ORDER BY ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645))
            LIMIT 15)

            UNION ALL

            -- Health facilities
            (SELECT
                COALESCE(hf_type, vdc_name1) as name,
                ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645)) as distance_m,
                degrees(ST_Azimuth(v_centroid, ST_ClosestPoint(geom, v_centroid))) as azimuth
            FROM infrastructure.health_facilities
            WHERE (hf_type IS NOT NULL OR vdc_name1 IS NOT NULL)
            ORDER BY ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645))
            LIMIT 10)

            UNION ALL

            -- Education facilities
            (SELECT
                COALESCE(name, name_en, amenity) as name,
                ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645)) as distance_m,
                degrees(ST_Azimuth(v_centroid, ST_ClosestPoint(geom, v_centroid))) as azimuth
            FROM infrastructure.education_facilities
            WHERE (name IS NOT NULL OR name_en IS NOT NULL OR amenity IS NOT NULL)
            ORDER BY ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(geom, 32645))
            LIMIT 10)

            UNION ALL

            -- Settlements
            (SELECT
                vil_name as name,
                ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(shape, 32645)) as distance_m,
                degrees(ST_Azimuth(v_centroid, ST_ClosestPoint(shape, v_centroid))) as azimuth
            FROM admin.settlement
            WHERE vil_name IS NOT NULL
            ORDER BY ST_Distance(ST_Transform(v_geom, 32645), ST_Transform(shape, 32645))
            LIMIT 15)
        ),
        -- Keep only the closest instance of each unique feature
        unique_features AS (
            SELECT DISTINCT ON (name)
                name, distance_m, azimuth
            FROM all_features_raw
            WHERE name IS NOT NULL AND name != ''
            ORDER BY name, distance_m
        ),
        -- Assign to direction quadrants and rank by distance within each
        features_with_quadrant AS (
            SELECT
                name, distance_m, azimuth,
                CASE
                    WHEN azimuth >= 315 OR azimuth < 45 THEN 'N'
                    WHEN azimuth >= 45 AND azimuth < 135 THEN 'E'
                    WHEN azimuth >= 135 AND azimuth < 225 THEN 'S'
                    WHEN azimuth >= 225 AND azimuth < 315 THEN 'W'
                END as quadrant,
                ROW_NUMBER() OVER (
                    PARTITION BY CASE
                        WHEN azimuth >= 315 OR azimuth < 45 THEN 'N'
                        WHEN azimuth >= 45 AND azimuth < 135 THEN 'E'
                        WHEN azimuth >= 135 AND azimuth < 225 THEN 'S'
                        WHEN azimuth >= 225 AND azimuth < 315 THEN 'W'
                    END
                    ORDER BY distance_m
                ) as rank_in_quadrant
            FROM unique_features
        )
        -- Take top 3 nearest features per quadrant
        SELECT name, distance_m, azimuth, quadrant
        FROM features_with_quadrant
        WHERE rank_in_quadrant <= 3
        ORDER BY quadrant, distance_m
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

        -- Assign to quadrant arrays
        IF v_feature_record.quadrant = 'N' THEN
            v_north_features := array_append(v_north_features, v_formatted);
        ELSIF v_feature_record.quadrant = 'E' THEN
            v_east_features := array_append(v_east_features, v_formatted);
        ELSIF v_feature_record.quadrant = 'S' THEN
            v_south_features := array_append(v_south_features, v_formatted);
        ELSIF v_feature_record.quadrant = 'W' THEN
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
