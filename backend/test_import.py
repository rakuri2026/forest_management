"""Test if species router can be imported from backend directory"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

print(f"Python path: {sys.path}")
print()

try:
    from app.api.species import router as species_router
    print("SUCCESS: Species router imported")
    print(f"  Prefix: {species_router.prefix}")
    print(f"  Routes: {len(species_router.routes)}")
    print()

    for route in species_router.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            print(f"  {route.path} - {route.methods}")

except Exception as e:
    print("FAILED: Could not import species router")
    print(f"  Error: {e}")
    import traceback
    traceback.print_exc()
