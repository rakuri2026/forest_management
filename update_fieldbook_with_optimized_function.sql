-- Update all fieldbook references using optimized function
-- This will take ~10-15 minutes for 295 points
WITH references_raw AS (
    SELECT
        id,
        point_number,
        rasters.find_nearest_feature(longitude, latitude) as ref
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

-- Show results
SELECT point_number, longitude, latitude, reference
FROM public.fieldbook
WHERE calculation_id = 'd35dba3c-b039-434f-88b8-08accd318407'
AND reference IS NOT NULL
ORDER BY point_number
LIMIT 20;
