-- Check the most recent upload and its feature data
SELECT
    forest_name,
    status,
    created_at,
    result_data->'blocks'->0->'block_name' as block1_name,
    result_data->'blocks'->0->'features_north' as block1_north,
    result_data->'blocks'->0->'features_east' as block1_east,
    result_data->'blocks'->0->'features_south' as block1_south,
    result_data->'blocks'->0->'features_west' as block1_west
FROM public.calculations
ORDER BY created_at DESC
LIMIT 1;
