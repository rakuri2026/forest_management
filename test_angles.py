"""Test angle classification logic"""

def classify_direction(azimuth_deg):
    if azimuth_deg >= 315 or azimuth_deg < 45:
        return 'North'
    elif azimuth_deg >= 45 and azimuth_deg < 135:
        return 'East'
    elif azimuth_deg >= 135 and azimuth_deg < 225:
        return 'South'
    elif azimuth_deg >= 225 and azimuth_deg < 315:
        return 'West'

# Test edge cases and boundary values
test_angles = [
    0,    # North (0 degrees)
    1,    # North
    44,   # North (just before 45)
    45,   # East (boundary)
    90,   # East (exactly east)
    134,  # East (just before 135)
    135,  # South (boundary)
    180,  # South (exactly south)
    224,  # South (just before 225)
    225,  # West (boundary)
    270,  # West (exactly west)
    314,  # West (just before 315)
    315,  # North (boundary)
    359,  # North (just before 360)
    360   # North (wraps to 0)
]

print("Angle Classification Test")
print("=" * 40)
for angle in test_angles:
    direction = classify_direction(angle % 360)
    print(f"{angle:3d} degrees = {direction:5s}")
