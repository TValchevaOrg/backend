"""Application settings, sourced from the environment.

Database settings deliberately reuse the transform pipeline's ``FOODIE_DB_*``
variable names (see ``transform/foodie_transform/config.py``) so one set of
credentials drives both the writer and this reader. API-server settings use a
``FOODIE_API_*`` namespace. Values are read from the process environment, with a
``.env`` / ``.env.local`` file as a fallback for local development.

Settings are loaded once and cached (:func:`get_settings`); inject them through
FastAPI's dependency system rather than importing a module-level singleton, so
tests can override them.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _quote(value: str) -> str:
    """Escape a value for a libpq ``keyword=value`` connection string.

    Mirrors the quoting in the transform pipeline's config so an assembled
    connection string behaves identically on both sides.
    """
    if value == "" or any(c.isspace() for c in value) or "'" in value or "\\" in value:
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"
    return value


class Settings(BaseSettings):
    """Typed view over the environment. See ``.env.example`` for the contract."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Database (shared FOODIE_DB_* contract with the transform pipeline) -- #
    db_dsn: str = Field(default="", alias="FOODIE_DB_DSN")
    db_host: str = Field(default="localhost", alias="FOODIE_DB_HOST")
    db_port: int = Field(default=5432, alias="FOODIE_DB_PORT")
    db_name: str = Field(default="foodie", alias="FOODIE_DB_NAME")
    db_user: str = Field(default="foodie", alias="FOODIE_DB_USER")
    db_password: str = Field(default="", alias="FOODIE_DB_PASSWORD")
    db_sslmode: str = Field(default="prefer", alias="FOODIE_DB_SSLMODE")

    # --- API server --------------------------------------------------------- #
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="FOODIE_API_CORS_ORIGINS",
    )
    log_level: str = Field(default="INFO", alias="FOODIE_API_LOG_LEVEL")
    pool_min_size: int = Field(default=1, alias="FOODIE_API_POOL_MIN_SIZE")
    pool_max_size: int = Field(default=10, alias="FOODIE_API_POOL_MAX_SIZE")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def conninfo(self) -> str:
        """A libpq connection string: the DSN verbatim, or assembled from parts."""
        if self.db_dsn:
            return self.db_dsn
        parts = {
            "host": self.db_host,
            "port": self.db_port,
            "dbname": self.db_name,
            "user": self.db_user,
            "password": self.db_password,
            "sslmode": self.db_sslmode,
        }
        return " ".join(
            f"{key}={_quote(str(value))}"
            for key, value in parts.items()
            if value is not None and value != ""
        )

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list (``"*"`` allows all; blank disables CORS)."""
        raw = self.cors_origins.strip()
        if not raw:
            return []
        return [origin.strip() for origin in raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance (read from the environment once)."""
    return Settings()
