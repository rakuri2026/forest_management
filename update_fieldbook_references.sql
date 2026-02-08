-- Update fieldbook references for existing data
WITH all_references AS (
    SELECT
        id,
        point_number,
        rasters.find_nearest_feature(longitude, latitude) as ref,
        LAG(rasters.find_nearest_feature(longitude, latitude)) OVER (ORDER BY point_number) as prev_ref
    FROM public.fieldbook
    WHERE calculation_id = 'd35dba3c-b039-434f-88b8-08accd318407'
    ORDER BY point_number
)
UPDATE public.fieldbook fb
SET reference = CASE
    WHEN ar.ref IS NOT NULL AND (ar.prev_ref IS NULL OR ar.ref != ar.prev_ref) THEN ar.ref
    ELSE NULL
END
FROM all_references ar
WHERE fb.id = ar.id;
