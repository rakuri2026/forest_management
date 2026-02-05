"""
Minimal test server to verify species routes work
"""
import sys
sys.path.insert(0, 'backend')

from fastapi import FastAPI
from app.api.species import router as species_router

# Create simple test app
app = FastAPI(title="Species Test Server")

# Include species router
app.include_router(species_router)

@app.get("/")
def root():
    return {"message": "Species test server", "routes": len(app.routes)}

if __name__ == "__main__":
    import uvicorn
    print("Starting test server on http://localhost:8002")
    print("Try: http://localhost:8002/api/species/identify?q=sho")
    uvicorn.run(app, host="0.0.0.0", port=8002)
