# Regeneration Data Implementation

Date: February 19, 2026
Status: IMPLEMENTED

## Overview
Added regeneration data (1-10 cm DBH) to tree distribution model export.

## Regeneration Categories

1. Unestablished Regeneration (1-4 cm DBH)
   - Count per plot: 2-5 species
   - DBH range: 1.0 - 4.0 cm
   - Height: NULL
   - Tree class: NULL

2. Established Regeneration/Sapling (4-10 cm DBH)
   - Count per plot: 1-4 species
   - DBH range: 4.0 - 10.0 cm
   - Height: NULL
   - Tree class: NULL

## Implementation

New function: generate_regeneration_entries()
Location: backend/app/services/tree_distribution.py (lines 555-644)

Generates regeneration entries for each sample plot with:
- Random DBH within specified ranges
- Weighted species selection
- Random placement within plot buffer
- NULL height_m and tree_class

## Statistics Enhanced

Before: Only mature tree count
After: Separated statistics
- mature_trees: DBH >= 10cm
- regeneration_total: DBH < 10cm
- regeneration_unestablished: 1-4cm
- regeneration_established: 4-10cm

## How to Test

1. Restart backend
2. Generate tree model
3. Open GPKG in QGIS
4. Filter: dbh_cm < 10 to see regeneration
5. Check height_m and tree_class are NULL for regeneration

