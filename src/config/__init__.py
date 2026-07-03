"""Settings loading via pydantic-settings.

Reads from environment variables / .env (see .env.example at repo root).
Implements GEN-0017_Configuration_System. See settings.py for the Settings
model and get_settings() accessor.
"""

from src.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
