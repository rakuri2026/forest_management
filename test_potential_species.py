"""
Test potential tree species analysis
"""
import sys
sys.path.insert(0, 'backend')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.services.analysis import analyze_potential_tree_species

# Database connection
DATABASE_URL = "postgresql://postgres:admin123@localhost:5432/cf_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print("=" * 70)
print("Testing Potential Tree Species Analysis")
print("=" * 70)

# Test with Shorea robusta forest type
test_forest_types = {
    "Shorea robusta": 60.5,
    "Pinus roxburghii": 30.2,
    "Alnus": 9.3
}

print(f"\nTest Forest Type Distribution:")
for ft, pct in test_forest_types.items():
    print(f"  {ft}: {pct}%")

print("\n" + "=" * 70)
print("POTENTIAL TREE SPECIES")
print("=" * 70)

result = analyze_potential_tree_species(test_forest_types, db)

if result['species_count'] > 0:
    print(f"\nFound {result['species_count']} potential species:")
    print("-" * 70)

    for i, species in enumerate(result['potential_species'][:15], 1):  # Show top 15
        print(f"\n{i}. {species['scientific_name']} ({species['local_name']})")
        print(f"   Role: {species['role']} (Rank {species['availability_rank']})")
        print(f"   Economic Value: {species['economic_value']}")
        print(f"   Found in: {', '.join(species['forest_types'])}")
else:
    print("\nNo species found (may need to check forest_species_association table)")

print("\n" + "=" * 70)
print("Test Complete!")
print("=" * 70)

db.close()
