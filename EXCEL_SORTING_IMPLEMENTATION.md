# Excel Export Complete Enhancement Implementation

## Status: COMPLETED

Successfully implemented 5 major enhancements for Tree Model Excel exports.

---

## Implementation Details

### File Modified
`backend/app/services/tree_distribution.py` - Function: `export_to_excel()` (lines 825-1052)

### New Features
1. **Multi-level sorting** (sample plot → species importance → alphabetical)
2. **Serial number (SN) columns** for each category (resets per sample plot)
3. **Column repositioning** (longitude/latitude after sample_plot_number)
4. **Empty row removal** (clean, no visual gaps)
5. **DBH/Height rounding** (0 decimal places - whole numbers only)

### Sorting Order

The Excel export now sorts rows in the following priority order:

1. **Sample Plot Number (Numeric)**
   - Sorted numerically: 1, 2, 3, 4, 5... 10, 11, 12
   - NOT alphabetically: ~~1, 10, 11, 2, 3~~
   - Missing/invalid values sorted last (999999)

2. **Species Importance (Ecological Role)**
   - Dominant species (priority 1)
   - Co-dominant species (priority 2)
   - Associate species (priority 3)
   - Occasional species (priority 4)
   - Rare species (priority 5)

3. **Species Name (Alphabetical A-Z)**
   - Sorted alphabetically by scientific name
   - Works across all size classes (regen/sapling/pole/tree)

### Serial Number Columns

Four new columns added to help count and understand each category:

- **regen_sn**: Serial number for regeneration (1, 2, 3... resets per plot)
- **sapling_sn**: Serial number for saplings (1, 2, 3... resets per plot)
- **pole_sn**: Serial number for poles (1, 2, 3... resets per plot)
- **tree_sn**: Serial number for trees (1, 2, 3... resets per plot)

**Example:**
```
Plot | regen_sn | regen_species     | tree_sn | tree_species
-----+----------+-------------------+---------+-----------------
1    | 1        | Shorea robusta    |         |
1    | 2        | Alnus nepalensis  |         |
1    |          |                   | 1       | Pinus roxburghii
1    |          |                   | 2       | Quercus sp.
2    | 1        | Shorea robusta    |         |  <- SN resets for plot 2
2    |          |                   | 1       | Alnus nepalensis <- SN resets
```

---

## How It Works

### Step 1: Capture Species Role
```python
species_role = tree.get('species_role', 'associate')
record['species_role'] = species_role  # Temporary column for sorting
```

### Step 2: Convert Sample Plot to Numeric
```python
df['sample_plot_number_numeric'] = pd.to_numeric(df['sample_plot_number'], errors='coerce').fillna(999999)
```

### Step 3: Map Role to Priority
```python
role_priority = {
    'dominant': 1,
    'co-dominant': 2,
    'associate': 3,
    'occasional': 4,
    'rare': 5
}
df['role_priority'] = df['species_role'].map(role_priority).fillna(3)
```

### Step 4: Extract Species Name for Sorting
```python
df['species_for_sorting'] = (
    df['tree_species_scientific'].fillna('') +
    df['pole_species_scientific'].fillna('') +
    df['sapling_species_scientific'].fillna('') +
    df['regen_species_scientific'].fillna('')
)
```

### Step 5: Sort by All Criteria
```python
df = df.sort_values(
    by=['sample_plot_number_numeric', 'role_priority', 'species_for_sorting'],
    ascending=[True, True, True]
)
```

### Step 6: Clean Up and Reassign FID
```python
# Remove temporary sorting columns (not shown in final Excel)
df = df.drop(columns=['sample_plot_number_numeric', 'role_priority', 'species_for_sorting', 'species_role'])

# Reassign FID sequentially after sorting
df['fid'] = range(1, len(df) + 1)
```

### Step 7: Generate Serial Numbers per Category
```python
# Initialize SN columns
df['regen_sn'] = None
df['sapling_sn'] = None
df['pole_sn'] = None
df['tree_sn'] = None

# Calculate serial numbers per plot per category
for plot_num in df['sample_plot_number'].unique():
    plot_mask = df['sample_plot_number'] == plot_num

    # Regeneration SN (reset per plot)
    regen_mask = plot_mask & df['regen_species_scientific'].notna()
    if regen_mask.any():
        df.loc[regen_mask, 'regen_sn'] = range(1, regen_mask.sum() + 1)

    # Sapling SN (reset per plot)
    sapling_mask = plot_mask & df['sapling_species_scientific'].notna()
    if sapling_mask.any():
        df.loc[sapling_mask, 'sapling_sn'] = range(1, sapling_mask.sum() + 1)

    # Pole SN (reset per plot)
    pole_mask = plot_mask & df['pole_species_scientific'].notna()
    if pole_mask.any():
        df.loc[pole_mask, 'pole_sn'] = range(1, pole_mask.sum() + 1)

    # Tree SN (reset per plot)
    tree_mask = plot_mask & df['tree_species_scientific'].notna()
    if tree_mask.any():
        df.loc[tree_mask, 'tree_sn'] = range(1, tree_mask.sum() + 1)
```

---

## Example Output

### Before Sorting & SN:
```
FID | Plot | tree_species         | Role
----+------+----------------------+------------
1   | 10   | Quercus sp.         | Associate
2   | 2    | Shorea robusta      | Dominant
3   | 1    | Pinus roxburghii    | Rare
4   | 2    | Alnus nepalensis    | Co-dominant
5   | 1    | Shorea robusta      | Dominant
```

### After Sorting & SN Assignment:
```
FID | Plot | tree_sn | tree_species         | Role
----+------+---------+----------------------+------------
1   | 1    | 1       | Shorea robusta      | Dominant        ← Plot 1, Dominant, A-Z
2   | 1    | 2       | Pinus roxburghii    | Rare            ← Plot 1, Rare, A-Z
3   | 2    | 1       | Shorea robusta      | Dominant        ← Plot 2, tree_sn resets to 1
4   | 2    | 2       | Alnus nepalensis    | Co-dominant     ← Plot 2, Co-dominant
5   | 10   | 1       | Quercus sp.         | Associate       ← Plot 10, tree_sn resets
```

**Complete Column Structure (22 columns total):**
```
1. fid
2. block_name
3. sample_plot_number
4. longitude                   ← Moved here for easy reference
5. latitude                    ← Moved here for easy reference
6. regen_sn                    ← NEW
7. regen_species_scientific
8. regen_dbh
9. regen_count
10. sapling_sn                  ← NEW
11. sapling_species_scientific
12. sapling_dbh_cm
13. sapling_count
14. pole_sn                     ← NEW
15. pole_species_scientific
16. pole_dbh_cm
17. pole_height_m
18. pole_class
19. tree_sn                     ← NEW
20. tree_species_scientific
21. tree_dbh_cm
22. tree_height_m
23. tree_class
```

---

## Testing

### Prerequisites
1. Backend server running on port 8001
2. Login with demo@forest.com / Demo1234
3. Existing calculation with species data

### Test Steps

1. **Generate Tree Model**
   ```
   - Go to Calculation Detail page
   - Click "Tree Model" tab
   - Click "Generate Tree Model"
   - Wait for completion (~5-10 minutes)
   ```

2. **Download Excel File**
   ```
   - Click "Download Excel" button
   - Open the .xlsx file
   ```

3. **Verify Sorting & SN Columns**
   - Check sample_plot_number: 1, 2, 3... 10, 11, 12 (NOT 1, 10, 11, 2)
   - Within each plot, dominant species appear first
   - Within each role, species are alphabetical
   - FID is sequential (1, 2, 3...)
   - **Check SN columns**: regen_sn, sapling_sn, pole_sn, tree_sn
   - Verify SN resets to 1 for each new sample plot

### Expected Result
All rows properly sorted with:
- Numeric plot sorting
- Dominant → Co-dominant → Associate → Rare ordering
- Alphabetical species names
- No species_role column visible (removed before export)
- **4 SN columns present**: Reset to 1 for each new sample plot
- Total 22 columns (was 18, now +4 SN columns)

---

## Notes

- **Hidden Columns**: The `species_role` column is used internally for sorting but is NOT included in the final Excel export
- **FID Reset**: After sorting and empty row removal, FID is reassigned sequentially (1, 2, 3...) so it matches the final data
- **Null Handling**: Missing sample plot numbers are sorted last (assigned 999999)
- **Multi-Size Support**: Species names are extracted from tree/pole/sapling/regen columns automatically
- **Performance**: Sorting and SN generation done in-memory using pandas, very fast even for large datasets
- **SN Columns**: Each category (regen/sapling/pole/tree) has its own serial number that resets to 1 for each new sample plot
- **Excel Columns**: 22 columns total (added 4 SN columns)
- **Column Order**: Longitude/latitude placed after sample_plot_number for easy coordinate reference
- **Empty Row Removal**: Rows with no species data (all regen/sapling/pole/tree columns empty) are automatically removed to eliminate visual gaps
- **DBH/Height Rounding**: All diameter and height measurements rounded to 0 decimal places (12.2→12, 12.8→13, 15.5→16) for field simplicity

---

## Validation

File: `backend/app/services/tree_distribution.py`

Key sections:
- Line 862: Species role extraction
- Line 873: Temporary sorting column added
- Lines 927-963: Complete sorting logic
- Line 963: FID reassignment after sort
- Lines 965-994: Serial number (SN) generation per category per plot
- Lines 996-1022: Column order (longitude/latitude after sample_plot_number)
- Lines 1024-1035: Empty row removal and final FID reassignment
- Lines 1037-1052: DBH and height rounding to 0 decimal places

---

## Rollback Instructions

If you need to revert this change:

1. Remove lines 862, 873, and 927-1022 from tree_distribution.py
2. The export will return to original unsorted order without SN columns
3. No database changes required (sorting and SN are export-only features)

---

**Date Implemented:** February 23, 2026
**Features Added:**
- Multi-level sorting (sample plot → species importance → alphabetical)
- Serial number (SN) columns per category (4 new columns)

**Modified By:** Claude Code
**Status:** Production Ready
