"""
backend/config.py
==================
Centralized configuration for ProjectMind AI.

WHY CENTRALIZED CONFIG?
Every part of the app needs settings — the LLM URL, the provider name, etc.
If you scatter os.getenv("...") calls throughout the codebase, you get:
  - No validation (typos in env var names silently return None)
  - No defaults documented anywhere
  - No single place to see what the app is configured to do

Instead, we define ONE Settings class here. It reads the .env file once
at startup, validates the values, applies defaults, and makes them available
throughout the app as `from backend.config import settings`.

HOW IT WORKS:
pydantic-settings reads environment variables (and optionally a .env file)
and maps them to typed Python attributes on your class.

Example: if your .env has LLM_PROVIDER=nemotron, then settings.llm_provider == "nemotron".
If the variable is missing, pydantic uses the default you specify.
If you declare it as required (no default), pydantic raises a clear error at startup.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables / .env file.

    Pydantic automatically reads environment variables whose names match
    the attribute names (case-insensitive).
    """

    # -------------------------------------------------------
    # LLM Provider
    # -------------------------------------------------------
    # Which LLM backend to use. The factory (llm/factory.py) reads
    # this and returns the correct provider object.
    # Default: "nemotron" (local llama-server)
    llm_provider: str = "nemotron"

    # -------------------------------------------------------
    # Nemotron (local llama-server) settings
    # -------------------------------------------------------
    # llama-server listens on this URL. Default port is 8080.
    nemotron_base_url: str = "http://localhost:8080"

    # The model name to pass in API requests.
    # llama-server accepts any string here if you didn't set --alias.
    # You can also set it to "default" if your server ignores the model field.
    nemotron_model: str = "nemotron"

    # -------------------------------------------------------
    # Groq (cloud API) settings
    # -------------------------------------------------------
    # API key from https://console.groq.com/keys
    # Default: None — only required when LLM_PROVIDER=groq
    groq_api_key: str | None = None

    # Which model to use on Groq.
    # Popular options: llama-3.3-70b-versatile, mixtral-8x7b-32768, gemma2-9b-it
    groq_model: str = "llama-3.3-70b-versatile"

    # Timeout in seconds for LLM requests.
    # Local models (Nemotron) need more time. Cloud (Groq) is usually fast.
    llm_timeout: int = 120

    # Pydantic v2 uses a dict for config, not a nested class.
    # SettingsConfigDict is specific to pydantic-settings and supports env_file.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# -------------------------------------------------------
# Singleton instance
# -------------------------------------------------------
# Imported everywhere as: from backend.config import settings
# Created once at module load time. Reads .env immediately.
settings = Settings()
