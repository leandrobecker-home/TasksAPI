"""Application settings loaded from environment variables (RT10).

Every setting is read from the process environment, optionally backed by a
local ``.env`` file. Variables use the ``TASKS_`` prefix, e.g. ``TASKS_PORT``.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Runtime configuration. Invalid values make the application fail on startup."""

    model_config = SettingsConfigDict(
        env_prefix="TASKS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="sqlite:///./tasks.db",
        min_length=1,
        description="SQLAlchemy URL of the database.",
    )
    log_level: LogLevel = Field(default="INFO", description="Minimum log level.")
    host: str = Field(default="127.0.0.1", min_length=1, description="Bind address.")
    port: int = Field(default=8000, ge=1, le=65535, description="Listening port.")

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        """Accept the level in any letter case, e.g. ``info``."""
        return value.upper() if isinstance(value, str) else value


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, built once on first use."""
    return Settings()
