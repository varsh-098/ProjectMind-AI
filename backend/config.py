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


VALID_SAMESITE_VALUES = {"lax", "strict", "none"}


def validate_security_config(cookie_samesite: str, cookie_secure: bool, cors_allowed_origins: str) -> None:
    """
    Validate cookie and CORS settings for security compliance.

    Raises:
        ValueError: If SameSite is invalid, if SameSite=None is used without Secure=True,
                    or if wildcard CORS origin '*' is configured with credentials.
    """
    samesite_clean = (cookie_samesite or "").strip().lower()
    if samesite_clean not in VALID_SAMESITE_VALUES:
        raise ValueError(
            f"Invalid cookie_samesite value '{cookie_samesite}'. Must be one of: {sorted(VALID_SAMESITE_VALUES)}."
        )

    if samesite_clean == "none" and not cookie_secure:
        raise ValueError(
            "Invalid configuration: cookie_samesite='none' requires cookie_secure=True. "
            "Modern browsers reject SameSite=None cookies unless Secure is enabled."
        )

    if cors_allowed_origins:
        origins = [o.strip() for o in cors_allowed_origins.split(",") if o.strip()]
        if "*" in origins:
            raise ValueError(
                "Invalid configuration: Wildcard CORS origin '*' is prohibited when credentials/cookies are enabled."
            )


try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import model_validator

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
        mongodb_database: str = "projectmind"
        mongodb_db_name: str | None = None  # legacy backward-compatible alias

        # Auth & Security Configuration
        cookie_secure: bool = False
        cookie_samesite: str = "lax"
        session_expiry_days: int = 7
        cors_allowed_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"

        @model_validator(mode="after")
        def validate_security(self):
            validate_security_config(
                cookie_samesite=self.cookie_samesite,
                cookie_secure=self.cookie_secure,
                cors_allowed_origins=self.cors_allowed_origins,
            )
            return self

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
            self.mongodb_database = (
                os.getenv("MONGODB_DATABASE")
                or os.getenv("MONGODB_DB_NAME")
                or env_map.get("mongodb_database")
                or env_map.get("mongodb_db_name")
                or "projectmind"
            )
            self.mongodb_db_name = self.mongodb_database  # legacy backward-compatible alias

            # Auth & Security Configuration
            self.cookie_secure = (
                (os.getenv("COOKIE_SECURE") or env_map.get("cookie_secure", "false")).lower() in ("true", "1", "yes")
            )
            self.cookie_samesite = (os.getenv("COOKIE_SAMESITE") or env_map.get("cookie_samesite", "lax")).strip().lower()
            self.session_expiry_days = int(
                os.getenv("SESSION_EXPIRY_DAYS") or env_map.get("session_expiry_days", "7")
            )
            self.cors_allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS") or env_map.get(
                "cors_allowed_origins",
                "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
            )

            validate_security_config(
                cookie_samesite=self.cookie_samesite,
                cookie_secure=self.cookie_secure,
                cors_allowed_origins=self.cors_allowed_origins,
            )

    settings = FallbackSettings()
