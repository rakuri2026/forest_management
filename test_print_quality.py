"""
Test script to verify map print quality.

Analyzes the generated maps for:
- Actual DPI
- Image dimensions vs expected A5 size
- Color depth
- File size efficiency
"""

from PIL import Image
import os

def test_print_quality(image_path):
    """Analyze a map image for print quality."""
    if not os.path.exists(image_path):
        print(f"[FAIL] File not found: {image_path}")
        return

    print(f"\nAnalyzing: {os.path.basename(image_path)}")
    print("-" * 60)

    # Open image
    img = Image.open(image_path)

    # Get dimensions
    width, height = img.size
    print(f"Dimensions: {width} x {height} pixels")

    # Get DPI
    dpi = img.info.get('dpi', (96, 96))
    print(f"DPI: {dpi[0]} x {dpi[1]}")

    # Calculate physical size at given DPI
    width_inches = width / dpi[0]
    height_inches = height / dpi[1]
    width_mm = width_inches * 25.4
    height_mm = height_inches * 25.4

    print(f"Physical size at {dpi[0]} DPI:")
    print(f"  {width_inches:.2f} x {height_inches:.2f} inches")
    print(f"  {width_mm:.1f} x {height_mm:.1f} mm")

    # Compare to A5
    if width_mm < height_mm:  # Portrait
        expected = "148 x 210 mm (A5 Portrait)"
        match = abs(width_mm - 148) < 10 and abs(height_mm - 210) < 10
    else:  # Landscape
        expected = "210 x 148 mm (A5 Landscape)"
        match = abs(width_mm - 210) < 10 and abs(height_mm - 148) < 10

    print(f"Expected: {expected}")
    print(f"Match: {'[OK]' if match else '[WARN]'}")

    # Color mode
    print(f"Color mode: {img.mode}")

    # File size
    file_size = os.path.getsize(image_path)
    print(f"File size: {file_size / 1024:.1f} KB")

    # Print recommendations
    print("\nPrint Recommendations:")
    if dpi[0] >= 300:
        print("  [OK] DPI sufficient for professional printing")
    elif dpi[0] >= 150:
        print("  [WARN] DPI acceptable for desktop printing")
    else:
        print("  [FAIL] DPI too low for quality printing")

    if file_size < 500 * 1024:
        print("  [OK] File size efficient for web and print")
    else:
        print("  [WARN] File size large (may slow loading)")

if __name__ == '__main__':
    print("="*60)
    print("Boundary Map Print Quality Test")
    print("="*60)

    # Test both maps
    test_print_quality('testData/boundary_map_3723abf4-14f6-421f-bbad-eb850519e5d1.png')
    test_print_quality('testData/boundary_map_3723abf4-14f6-421f-bbad-eb850519e5d1_landscape.png')

    print("\n" + "="*60)
    print("Test Complete")
    print("="*60)
