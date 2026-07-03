"""Configuration System (GEN-0017).

Loads runtime configuration from environment variables / .env, per the
approved stack decision and .env.example at repo root. This is the only
module permitted to read os.environ directly — everything else receives
config through the Settings object, injected by the Kernel at boot.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated runtime configuration.

    Field names intentionally mirror the keys in .env.example.
    """

    model_config = SettingsConfigDict(
        env_prefix="GENESIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["development", "production"] = "development"

    # Database
    database_url: str = "sqlite+aiosqlite:///./genesis.db"

    # Vector memory (Qdrant)
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Cache / event transport (Redis)
    redis_url: str = "redis://localhost:6379/0"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Kernel Scheduler defaults (GEN: KERNEL_ARCHITECTURE_PROPOSAL.md §3b)
    scheduler_max_concurrent_tasks: int = 10
    scheduler_default_task_timeout_seconds: float = 300.0
    scheduler_default_max_retries: int = 3
    scheduler_retry_backoff_base_seconds: float = 1.0

    # Kernel dispatch (KERNEL_ARCHITECTURE_PROPOSAL.md §5)
    kernel_dispatch_timeout_seconds: float = 30.0

    # Boot (KERNEL_ARCHITECTURE_PROPOSAL.md §6)
    boot_health_check_timeout_seconds: float = 10.0
    shutdown_grace_period_seconds: float = 15.0


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings singleton.

    Cached so repeated calls don't re-read the environment; tests that need
    a fresh Settings instance should call get_settings.cache_clear() first.
    """
    return Settings()
