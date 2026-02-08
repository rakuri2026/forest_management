"""
Main FastAPI application
Community Forest Management System
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time

from .core.config import settings
from .core.database import check_db_connection, Base, engine
from .api import auth_router, forests_router, inventory_router, species_router
from .api import fieldbook, sampling, fieldbook_list, sampling_list, biodiversity

# Debug: Print router info
print(f"DEBUG: Species router loaded with prefix: {species_router.prefix}")
print(f"DEBUG: Species router has {len(species_router.routes)} routes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events
    Startup and shutdown logic
    """
    # Startup
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"Debug mode: {settings.DEBUG}")

    # Check database connection
    if check_db_connection():
        print("Database connection successful")
    else:
        print("Database connection failed")

    # Note: We don't create tables here as they already exist in cf_db
    # Only the forest_managers table needs to be created via migration

    yield

    # Shutdown
    print("Shutting down application...")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API for Community Forest Management and Analysis",
    lifespan=lifespan
)


# Add CORS middleware
# Allow requests from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,  # Allow credentials (cookies, auth headers)
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],  # Expose all headers
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time to response headers"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions"""
    if settings.DEBUG:
        # In debug mode, show full error
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "type": type(exc).__name__,
                "path": str(request.url)
            }
        )
    else:
        # In production, hide error details
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )


# Include routers
app.include_router(
    auth_router,
    prefix="/api/auth",
    tags=["Authentication"]
)

app.include_router(
    forests_router,
    prefix="/api/forests",
    tags=["Forest Management"]
)

app.include_router(
    inventory_router,
    prefix="/api/inventory",
    tags=["Tree Inventory"]
)

print(f"DEBUG: Including species router...")
app.include_router(
    species_router,
    prefix="/api/species",
    tags=["Species"]
)
print(f"DEBUG: Species router included. Total app routes: {len(app.routes)}")

# Include fieldbook and sampling routers
app.include_router(
    fieldbook.router,
    prefix="/api/calculations",
    tags=["Fieldbook"]
)

app.include_router(
    sampling.router,
    prefix="/api",
    tags=["Sampling"]
)

# Include list routers
app.include_router(
    fieldbook_list.router,
    prefix="/api",
    tags=["Fieldbook Lists"]
)

app.include_router(
    sampling_list.router,
    prefix="/api",
    tags=["Sampling Lists"]
)

# Include biodiversity router
app.include_router(
    biodiversity.router,
    prefix="/api",
    tags=["Biodiversity"]
)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint - API information"""
    import datetime
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "reloaded_at": str(datetime.datetime.now()),
        "endpoints": {
            "auth": "/api/auth",
            "forests": "/api/forests",
            "inventory": "/api/inventory",
            "species": "/api/species",
            "fieldbook": "/api/calculations/{id}/fieldbook",
            "sampling": "/api/calculations/{id}/sampling"
        }
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    db_status = check_db_connection()

    return {
        "status": "healthy" if db_status else "unhealthy",
        "database": "connected" if db_status else "disconnected",
        "version": settings.APP_VERSION
    }


# Test endpoint to verify routes
@app.get("/test-species")
async def test_species():
    """Test endpoint to check if species routes are loaded"""
    species_routes = []
    for route in app.routes:
        if hasattr(route, 'path') and '/species' in route.path:
            species_routes.append({
                "path": route.path,
                "methods": list(route.methods) if hasattr(route, 'methods') else []
            })

    return {
        "species_routes_found": len(species_routes),
        "routes": species_routes,
        "total_routes": len(app.routes)
    }


# Database info endpoint
@app.get("/api/db-info")
async def database_info():
    """Database connection information (debug only)"""
    if not settings.DEBUG:
        return {"detail": "Only available in debug mode"}

    from .core.database import get_db_pool_status

    return {
        "connected": check_db_connection(),
        "pool_status": get_db_pool_status(),
        "database_url": settings.DATABASE_URL.split("@")[-1]  # Hide credentials
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
