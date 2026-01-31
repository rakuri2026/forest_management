"""
Calculate what raster resolution QGIS must be using
"""
import math

# User's QGIS data
qgis_data = {
    "Panchpokhari pakho": {
        "area_ha": 134.12,
        "total_pixels": 370 + 1313,  # 0m + non-zero
        "zero_pixels": 370
    },
    "Chaukune Bari": {
        "area_ha": 69.64,
        "total_pixels": 298 + 674,
        "zero_pixels": 298
    },
    "Tikaram pakho": {
        "area_ha": 90.24,
        "total_pixels": 313 + 1135,
        "zero_pixels": 313
    },
    "Dunetar": {
        "area_ha": 101.54,
        "total_pixels": 180 + 1318,
        "zero_pixels": 180
    },
    "Rame kholsa": {
        "area_ha": 122.58,
        "total_pixels": 310 + 1520,
        "zero_pixels": 310
    }
}

print("=" * 80)
print("Calculating QGIS Raster Resolution")
print("=" * 80)
print()

resolutions = []

for block_name, data in qgis_data.items():
    area_m2 = data['area_ha'] * 10000
    total_pixels = data['total_pixels']

    pixel_area_m2 = area_m2 / total_pixels
    pixel_size_m = math.sqrt(pixel_area_m2)

    resolutions.append(pixel_size_m)

    print(f"{block_name}:")
    print(f"  Area: {data['area_ha']:.2f} ha = {area_m2:.0f} m²")
    print(f"  Total pixels: {total_pixels}")
    print(f"  Pixel area: {pixel_area_m2:.1f} m²")
    print(f"  Pixel size: {pixel_size_m:.1f}m x {pixel_size_m:.1f}m")
    print()

avg_resolution = sum(resolutions) / len(resolutions)

print("=" * 80)
print(f"Average QGIS pixel resolution: {avg_resolution:.1f}m")
print("=" * 80)
print()

# Compare with PostGIS
postgis_pixel_size = 26.5 * 29.9  # area in m²
postgis_resolution = math.sqrt(postgis_pixel_size)

print(f"PostGIS pixel resolution: ~26.5m x 29.9m (geometric mean: {postgis_resolution:.1f}m)")
print()

ratio = avg_resolution / postgis_resolution
print(f"Ratio: QGIS pixels are {ratio:.2f}x larger than PostGIS")
print()

if ratio > 1.05:
    print("CONCLUSION: QGIS is using a COARSER/RESAMPLED raster!")
    print(f"QGIS raster appears to be resampled to ~{avg_resolution:.0f}m resolution")
    print(f"PostGIS raster is at native ~{postgis_resolution:.0f}m resolution")
elif ratio < 0.95:
    print("CONCLUSION: PostGIS is using a COARSER/RESAMPLED raster!")
else:
    print("CONCLUSION: Both use similar resolution - discrepancy must be elsewhere")
