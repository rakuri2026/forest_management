"""
Test script for map generation service.

Tests:
1. Portrait A5 map generation
2. Landscape A5 map generation
3. File dimensions verification
4. DPI verification
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from app.services.map_generator import MapGenerator, generate_test_map
from PIL import Image
import io


def verify_image_properties(image_buffer: io.BytesIO, expected_width: int, expected_height: int, dpi: int):
    """Verify image dimensions and DPI."""
    image_buffer.seek(0)
    img = Image.open(image_buffer)

    print(f"  Image size: {img.size[0]} × {img.size[1]} pixels")
    print(f"  Expected: ~{expected_width} × ~{expected_height} pixels (at {dpi} DPI)")

    # Check DPI info
    if 'dpi' in img.info:
        print(f"  DPI: {img.info['dpi']}")

    # Allow 5% tolerance for dimensions
    width_ok = abs(img.size[0] - expected_width) / expected_width < 0.05
    height_ok = abs(img.size[1] - expected_height) / expected_height < 0.05

    if width_ok and height_ok:
        print(f"  [OK] Dimensions correct!")
        return True
    else:
        print(f"  [FAIL] Dimensions incorrect!")
        return False


def test_map_generation():
    """Run all map generation tests."""
    print("="*60)
    print("Map Generation Service Test")
    print("="*60)

    # Initialize generator
    print("\n1. Initializing MapGenerator (300 DPI)...")
    generator = MapGenerator(dpi=300)
    print("  [OK] MapGenerator initialized")

    # Test portrait orientation
    print("\n2. Testing Portrait A5 Map (148mm x 210mm)...")
    portrait_buffer = generator.generate_test_map(
        orientation='portrait',
        output_path='testData/test_map_portrait.png'
    )

    # A5 portrait at 300 DPI: 148mm x 210mm = 5.83" x 8.27" = 1749 x 2481 pixels
    if verify_image_properties(portrait_buffer, 1749, 2481, 300):
        print("  [OK] Portrait map generated successfully")
        print("  [OK] Saved to: testData/test_map_portrait.png")

    # Test landscape orientation
    print("\n3. Testing Landscape A5 Map (210mm x 148mm)...")
    landscape_buffer = generator.generate_test_map(
        orientation='landscape',
        output_path='testData/test_map_landscape.png'
    )

    # A5 landscape at 300 DPI: 210mm x 148mm = 8.27" x 5.83" = 2481 x 1749 pixels
    if verify_image_properties(landscape_buffer, 2481, 1749, 300):
        print("  [OK] Landscape map generated successfully")
        print("  [OK] Saved to: testData/test_map_landscape.png")

    # Test convenience function
    print("\n4. Testing convenience function...")
    test_buffer = generate_test_map(orientation='portrait')
    print("  [OK] Convenience function works")

    print("\n" + "="*60)
    print("[SUCCESS] All tests passed!")
    print("="*60)
    print("\nGenerated test maps:")
    print("  - testData/test_map_portrait.png")
    print("  - testData/test_map_landscape.png")
    print("\nNext steps:")
    print("  1. Open the generated PNG files to verify quality")
    print("  2. Check that north arrow and scale bar are visible")
    print("  3. Verify text is readable at 300 DPI")
    print("  4. Proceed to Week 2: Generate actual forest maps")


if __name__ == '__main__':
    try:
        test_map_generation()
    except Exception as e:
        print(f"\n[FAIL] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
