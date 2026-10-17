"""Application configuration for Falsify API server."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.falsify.config import EngineConfig


class AppConfig(BaseSettings):
    """Central configuration for FastAPI application and environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server settings
    app_name: str = Field(default="Falsify API", description="API Service Name")
    app_version: str = Field(default="1.0.0", description="API Service Version")
    debug: bool = Field(default=False, description="Debug mode")
    host: str = Field(default="0.0.0.0", description="Bind host")
    port: int = Field(default=8000, description="Bind port")

    # Database settings
    database_url: str = Field(
        default="sqlite:///./falsify.db",
        description="SQLAlchemy database connection URL",
    )

    # Static file serving (SPA frontend)
    static_dir: str | None = Field(
        default=None,
        description="Path to compiled frontend static files directory (e.g. frontend/dist).",
    )

    # Security & operational limits
    api_key: str | None = Field(
        default=None,
        description="Optional master API key to protect verification endpoints.",
    )
    max_request_size_bytes: int = Field(
        default=1_048_576,
        description="Maximum request payload size in bytes (default 1MB).",
    )
    rate_limit_per_minute: int = Field(
        default=0,
        description="Max requests per minute per IP. 0 disables rate limiting.",
    )
    auto_create_tables: bool = Field(
        default=False,
        description="Whether to run Base.metadata.create_all() on startup. False in production to ensure Alembic controls the schema.",
    )

    # CORS settings
    cors_origins: Any = Field(
        default=["*"],
        description="Allowed CORS origins as list or comma-separated string.",
    )

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {v}")
        return v

    @field_validator("max_request_size_bytes")
    @classmethod
    def validate_max_request_size(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"max_request_size_bytes must be positive, got {v}")
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            # Handle comma-separated string or single origin
            stripped = value.strip()
            if not stripped:
                return ["*"]
            if stripped.startswith("[") and stripped.endswith("]"):
                # JSON list format
                import json
                try:
                    return json.loads(stripped)
                except Exception:
                    pass
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        return ["*"]

    def build_engine_config(self, **overrides) -> EngineConfig:
        """Construct an EngineConfig using environment defaults and overrides."""
        return EngineConfig.from_env(**overrides)


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    """Return cached AppConfig singleton."""
    return AppConfig()
