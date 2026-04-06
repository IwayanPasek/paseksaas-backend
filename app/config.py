# app/config.py
# PasekSaaS — Centralized Configuration with Validation
# ──────────────────────────────────────────────────────
"""
All environment variables are loaded and validated here using Pydantic BaseSettings.
Fails fast on missing critical variables instead of using hardcoded defaults.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import AliasChoices, Field


class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

    # ── Database ──────────────────────────────────────
    DB_HOST: str = Field(..., description="MySQL host")
    DB_USER: str = Field(..., description="MySQL user")
    DB_PASSWORD: str = Field(
        ...,
        validation_alias=AliasChoices("DB_PASSWORD", "DB_PASS"),
        description="MySQL password (accepts DB_PASSWORD or DB_PASS from .env)",
    )
    DB_NAME: str = Field(..., description="MySQL database name")
    DB_CHARSET: str = "utf8mb4"
    DB_POOL_MIN: int = Field(default=2, ge=1, le=20)
    DB_POOL_MAX: int = Field(default=10, ge=2, le=50)

    # ── Azure OpenAI ──────────────────────────────────
    AZURE_OPENAI_ENDPOINT: str = Field(..., description="Azure OpenAI endpoint URL")
    AZURE_OPENAI_API_KEY: str = Field(..., description="Azure OpenAI API key")
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4o-mini"

    # ── Redis ─────────────────────────────────────────
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    SESSION_TTL_SECONDS: int = Field(default=3600, ge=60, description="Session expiry in seconds")

    # ── CORS ──────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        "https://*.websitewayan.my.id",
        "http://*.websitewayan.my.id",
        "http://localhost:5173",
        "http://localhost:8000",
    ]

    # ── Rate Limiting ─────────────────────────────────
    RATE_LIMIT_CHAT: str = "15/minute"
    RATE_LIMIT_DEFAULT: str = "60/minute"

    # ── Chat Behaviour ────────────────────────────────
    MAX_HISTORY: int = Field(default=10, ge=2, le=50, description="Sliding window history per session")
    MAX_MSG_LEN: int = Field(default=500, ge=10, le=2000, description="Max user message length")
    AI_MAX_TOKENS: int = Field(default=800, ge=100, le=4000)
    AI_TEMPERATURE: float = Field(default=0.7, ge=0.0, le=2.0)
    AI_TIMEOUT_SECONDS: int = Field(default=30, ge=5, le=120)

    # ── Cache ─────────────────────────────────────────
    TOKO_CACHE_TTL_SECONDS: int = Field(default=300, ge=30, description="Toko data cache TTL (5 min)")

    # ── Site Config ───────────────────────────────────
    SITE_DOMAIN: str = Field(default="websitewayan.my.id", description="Main site domain")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Returns a cached singleton Settings instance.
    
    Call this instead of instantiating Settings() directly
    to avoid re-reading .env on every access.
    """
    return Settings()
