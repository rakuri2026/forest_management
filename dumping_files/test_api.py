import requests

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0ODUyNDczZS02Y2I5LTQ0MjItOTFiOS1hYThkNTlkMzllODMiLCJlbWFpbCI6Im5ld3VzZXJAZXhhbXBsZS5jb20iLCJleHAiOjE3NjkzNTY5ODAsInR5cGUiOiJhY2Nlc3MifQ.qJdOkhOKAOaAkmbrJf0suThuJJzqhzYYWrsDWxMorp0"

response = requests.get(
    "http://localhost:8004/api/forests/calculations/e771aa41-7bcf-48d8-b1ec-d1a06e17df41",
    headers={"Authorization": f"Bearer {TOKEN}"}
)

data = response.json()
result_data = data.get('result_data', {})

print("API Response Status:", response.status_code)
print("Has result_data:", result_data is not None)
print("result_data type:", type(result_data))
print("\nTop-level keys in result_data:")
if result_data:
    for key in list(result_data.keys())[:15]:
        value = result_data.get(key)
        if isinstance(value, (dict, list)):
            print(f"  {key}: {type(value).__name__}")
        else:
            print(f"  {key}: {value}")
else:
    print("  EMPTY or None!")

print("\nChecking specific fields:")
print(f"  slope_dominant_class: {result_data.get('slope_dominant_class')}")
print(f"  aspect_dominant: {result_data.get('aspect_dominant')}")
print(f"  forest_type_dominant: {result_data.get('forest_type_dominant')}")
print(f"  landcover_dominant: {result_data.get('landcover_dominant')}")
