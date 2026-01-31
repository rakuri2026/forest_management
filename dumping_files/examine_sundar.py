"""
Extract and examine sundar.zip
"""
import zipfile
import os

zip_path = "D:/forest_management/testData/sundar.zip"
extract_path = "D:/forest_management/testData/sundar_extracted"

# Extract
os.makedirs(extract_path, exist_ok=True)

with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall(extract_path)
    print("Extracted files:")
    for name in zip_ref.namelist():
        print(f"  {name}")

print()
print("Directory structure:")
for root, dirs, files in os.walk(extract_path):
    level = root.replace(extract_path, '').count(os.sep)
    indent = ' ' * 2 * level
    print(f"{indent}{os.path.basename(root)}/")
    subindent = ' ' * 2 * (level + 1)
    for file in files:
        print(f"{subindent}{file}")
