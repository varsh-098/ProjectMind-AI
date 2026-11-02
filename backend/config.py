"""
backend/config.py
==================
Centralized configuration for ProjectMind AI.

WHY CENTRALIZED CONFIG?
Every part of the app needs settings — the LLM URL, the provider name, etc.
Instead of scattering os.getenv calls, we define ONE Settings class here.
It reads the .env file once at startup, validates values, applies defaults,
and makes them available throughout the app as `from backend.config import settings`.
"""

import os
from pathlib import Path


def _load_env_file() -> dict[str, str]:
    """Fallback reader for .env file when pydantic-settings is unavailable."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        env_path = Path(".env")

    env_map = {}
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_map[k.strip().lower()] = v.strip().strip("\"'")
        except Exception:
            pass
    return env_map


try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        """Application settings loaded from environment variables / .env file."""
        llm_provider: str = "nemotron"
        nemotron_base_url: str = "http://localhost:8080"
        nemotron_model: str = "nemotron"
        groq_api_key: str | None = None
        groq_model: str = "llama-3.3-70b-versatile"
        gemini_api_key: str | None = None
        gemini_model: str = "gemini-2.5-flash"
        llm_timeout: int = 120

        # Phase 22: Task-to-Model Specialization Tiers
        tier_fast_provider: str = "groq"
        tier_fast_model: str = "llama-3.3-70b-versatile"
        tier_balanced_provider: str = "gemini"
        tier_balanced_model: str = "gemini-2.5-flash"
        tier_complex_provider: str = "gemini"
        tier_complex_model: str = "gemini-2.5-pro"
        tier_local_provider: str = "nemotron"
        tier_local_model: str = "nemotron"

        # Phase 23: MongoDB Atlas Persistence
        mongodb_uri: str | None = None
        mongodb_db_name: str = "projectmind"

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )

    settings = Settings()

except ImportError:
    # Graceful fallback when pydantic-settings is not installed in the active environment
    class FallbackSettings:
        def __init__(self):
            env_map = _load_env_file()
            self.llm_provider = os.getenv("LLM_PROVIDER") or env_map.get("llm_provider", "nemotron")
            self.nemotron_base_url = os.getenv("NEMOTRON_BASE_URL") or env_map.get("nemotron_base_url", "http://localhost:8080")
            self.nemotron_model = os.getenv("NEMOTRON_MODEL") or env_map.get("nemotron_model", "nemotron")
            self.groq_api_key = os.getenv("GROQ_API_KEY") or env_map.get("groq_api_key")
            self.groq_model = os.getenv("GROQ_MODEL") or env_map.get("groq_model", "llama-3.3-70b-versatile")
            self.gemini_api_key = os.getenv("GEMINI_API_KEY") or env_map.get("gemini_api_key")
            self.gemini_model = os.getenv("GEMINI_MODEL") or env_map.get("gemini_model", "gemini-2.5-flash")
            self.llm_timeout = int(os.getenv("LLM_TIMEOUT") or env_map.get("llm_timeout", "120"))

            # Phase 22: Task-to-Model Specialization Tiers
            self.tier_fast_provider = os.getenv("TIER_FAST_PROVIDER") or env_map.get("tier_fast_provider", "groq")
            self.tier_fast_model = os.getenv("TIER_FAST_MODEL") or env_map.get("tier_fast_model", "llama-3.3-70b-versatile")
            self.tier_balanced_provider = os.getenv("TIER_BALANCED_PROVIDER") or env_map.get("tier_balanced_provider", "gemini")
            self.tier_balanced_model = os.getenv("TIER_BALANCED_MODEL") or env_map.get("tier_balanced_model", "gemini-2.5-flash")
            self.tier_complex_provider = os.getenv("TIER_COMPLEX_PROVIDER") or env_map.get("tier_complex_provider", "gemini")
            self.tier_complex_model = os.getenv("TIER_COMPLEX_MODEL") or env_map.get("tier_complex_model", "gemini-2.5-pro")
            self.tier_local_provider = os.getenv("TIER_LOCAL_PROVIDER") or env_map.get("tier_local_provider", "nemotron")
            self.tier_local_model = os.getenv("TIER_LOCAL_MODEL") or env_map.get("tier_local_model", "nemotron")

            # Phase 23: MongoDB Atlas Persistence
            self.mongodb_uri = os.getenv("MONGODB_URI") or env_map.get("mongodb_uri")
            self.mongodb_db_name = os.getenv("MONGODB_DB_NAME") or env_map.get("mongodb_db_name", "projectmind")

    settings = FallbackSettings()
