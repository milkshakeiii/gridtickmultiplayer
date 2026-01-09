"""
Configuration management for Grid Backend.
Uses pydantic-settings for environment variable parsing.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/gridbackend",
        description="PostgreSQL connection URL with asyncpg driver"
    )

    # Security
    secret_key: str = Field(
        default="change-me-in-production-use-a-real-secret-key",
        description="Secret key for JWT token signing"
    )
    algorithm: str = Field(
        default="HS256",
        description="Algorithm for JWT token signing"
    )

    # Session
    session_timeout_seconds: int = Field(
        default=0,
        description="Session timeout in seconds. 0 means no expiration"
    )

    # Password
    min_password_length: int = Field(
        default=8,
        description="Minimum password length for registration"
    )

    # Debug
    debug_mode: bool = Field(
        default=False,
        description="Enable debug endpoints and features"
    )
    debug_user: str = Field(
        default="",
        description="Username that automatically gets debug access (for development)"
    )

    # Tick Engine
    tick_rate_ms: int = Field(
        default=1000,
        description="Tick rate in milliseconds"
    )

    # Game Logic Module
    game_module: str = Field(
        default="grid_backend.game_modules.example",
        description="Python module path for game logic"
    )

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Database pooling
    db_pool_size: int = Field(
        default=5,
        description="Database connection pool size"
    )
    db_max_overflow: int = Field(
        default=10,
        description="Maximum database connections above pool size"
    )

    # Persistence
    entity_save_interval_seconds: int = Field(
        default=30,
        description="Interval for periodic entity state persistence"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Use dependency injection in FastAPI routes.
    """
    return Settings()
