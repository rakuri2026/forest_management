import sys
sys.path.insert(0, 'backend')

from app.main import app

print("All registered routes:")
print("=" * 60)
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        methods = ', '.join(route.methods) if route.methods else 'N/A'
        print(f"{methods:10} {route.path}")
    elif hasattr(route, 'path'):
        print(f"{'MOUNT':10} {route.path}")

print("\n" + "=" * 60)
print(f"Total routes: {len(app.routes)}")

# Check specifically for species routes
species_routes = [r for r in app.routes if hasattr(r, 'path') and '/species' in r.path]
print(f"\nSpecies routes found: {len(species_routes)}")
for route in species_routes:
    if hasattr(route, 'methods'):
        methods = ', '.join(route.methods) if route.methods else 'N/A'
        print(f"  {methods:10} {route.path}")
