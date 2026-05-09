"""
Database connection and session management
"""
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from .config import settings


# Create database engine with connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=settings.DB_POOL_SIZE,  # Now 20
    max_overflow=settings.DB_MAX_OVERFLOW,  # Now 30
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=settings.DB_POOL_RECYCLE,  # Recycle after 1 hour
    pool_timeout=settings.DB_POOL_TIMEOUT,  # 30 second timeout
    echo=settings.DEBUG,
    connect_args={
        "connect_timeout": 10,  # PostgreSQL connection timeout
        "options": "-c statement_timeout=60000"  # 60 second query timeout
    }
)


# Enable PostGIS extension on connect
@event.listens_for(engine, "connect")
def enable_postgis(dbapi_conn, connection_record):
    """Enable PostGIS extensions when connecting to database"""
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis_raster;")
        dbapi_conn.commit()
    except Exception as e:
        print(f"PostGIS extension setup: {e}")
    finally:
        cursor.close()


# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base for models
Base = declarative_base()


# Dependency for FastAPI endpoints
def get_db():
    """
    Get database session for dependency injection
    Usage: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection():
    """Check if database connection is working"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False


def get_db_pool_status():
    """Get current connection pool status"""
    return {
        "pool_size": engine.pool.size(),
        "checked_out": engine.pool.checkedout(),
        "overflow": engine.pool.overflow(),
        "max_overflow": settings.DB_MAX_OVERFLOW,
    }
