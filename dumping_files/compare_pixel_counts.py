"""
Compare pixel counts between QGIS and our database
"""

# QGIS data from sundar.zip (user provided)
qgis_data = {
    "Panchpokhari pakho": {
        "zero_pixels": 370,
        "non_zero_pixels": 1683 - 370,  # Approximating total from percentage
        "percent_non_forest": 22
    },
    "Chaukune Bari": {
        "zero_pixels": 298,
        "non_zero_pixels": 972 - 298,
        "percent_non_forest": 31
    },
    "Tikaram pakho": {
        "zero_pixels": 313,
        "non_zero_pixels": 1448 - 313,
        "percent_non_forest": 22
    },
    "Dunetar": {
        "zero_pixels": 180,
        "non_zero_pixels": 1498 - 180,
        "percent_non_forest": 12
    },
    "Rame kholsa": {
        "zero_pixels": 310,
        "non_zero_pixels": 1830 - 310,
        "percent_non_forest": 17
    }
}

# Our database results
db_data = {
    "Panchpokhari pakho": {
        "percent_non_forest": 59.66
    },
    "Chaukune Bari": {
        "percent_non_forest": 70.93
    },
    "Tikaram pakho": {
        "percent_non_forest": 63.19
    },
    "Dunetar": {
        "zero_pixels": 1020,
        "total_pixels": 2115,
        "percent_non_forest": 48.14
    },
    "Rame kholsa": {
        "percent_non_forest": 57.83
    }
}

print("=" * 80)
print("COMPARISON: QGIS (sundar.zip) vs Our Database")
print("=" * 80)
print()

for block_name in qgis_data.keys():
    qgis = qgis_data[block_name]
    db = db_data[block_name]

    print(f"Block: {block_name}")
    print(f"  QGIS:     {qgis['percent_non_forest']}% non-forest ({qgis['zero_pixels']} pixels with 0m)")
    print(f"  Database: {db['percent_non_forest']}% non-forest")

    if block_name == "Dunetar":
        ratio = db['zero_pixels'] / qgis['zero_pixels']
        print(f"  Ratio:    {ratio:.1f}x more 0m pixels in database")

    difference = db['percent_non_forest'] - qgis['percent_non_forest']
    print(f"  Difference: +{difference:.1f} percentage points")
    print()

print("=" * 80)
print("CONCLUSION:")
print("=" * 80)
print()
print("The database shows 2-5x MORE non-forest (0m pixels) than QGIS for all blocks.")
print()
print("Possible causes:")
print("1. Different canopy raster files (database vs sundar.zip)")
print("2. Different block boundary polygons (larger in database)")
print("3. CRS/alignment issue between raster and vector")
print()
print("Next step: Compare the actual raster files and boundary shapefiles")
