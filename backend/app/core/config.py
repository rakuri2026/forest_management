"""
Application configuration settings
"""
from pydantic_settings import BaseSettings
from pydantic import validator
from typing import List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database
    DATABASE_URL: str = "postgresql://postgres:admin123@localhost:5432/cf_db"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # JWT Authentication
    SECRET_KEY: str = "cf-forest-management-secret-key-2026-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # File Upload
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: str = ".shp,.kml,.geojson,.json,.gpkg,.zip"
    UPLOAD_DIR: str = "./uploads"
    EXPORT_DIR: str = "./exports"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # Application
    APP_NAME: str = "Community Forest Management System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    @validator("ALLOWED_EXTENSIONS")
    def parse_extensions(cls, v):
        """Convert comma-separated string to list"""
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(",")]
        return v

    @validator("CORS_ORIGINS")
    def parse_cors_origins(cls, v):
        """Convert comma-separated string to list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()

# Ensure upload and export directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.EXPORT_DIR, exist_ok=True)
