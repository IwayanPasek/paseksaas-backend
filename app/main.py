# app/main.py
# PasekSaaS — FastAPI Application Factory
# ──────────────────────────────────────────────────────
"""
Central application assembly point. Handles:
  - Lifespan (startup/shutdown) for DB, Redis, AI client
  - CORS middleware with subdomain wildcard support
  - Rate limiter integration
  - Router mounting

IMPORTANT: CORS uses regex pattern to allow all subdomains of the
configured domain (*.websitewayan.my.id) as required for multi-tenant SaaS.
"""

import re
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app import __version__
from app.config import get_settings
from app.database import db_manager
from app.redis import session_manager
from app.services.ai_service import ai_service
from app.services.toko_service import set_cache_ttl
from app.routers import chat, health

# ── Logging ───────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all services on startup, clean up on shutdown."""
    settings = get_settings()

    logger.info("🚀 Starting PasekSaaS AI Backend v%s", __version__)

    # 1. MySQL async pool
    await db_manager.connect(
        host=settings.DB_HOST,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        db=settings.DB_NAME,
        charset=settings.DB_CHARSET,
        minsize=settings.DB_POOL_MIN,
        maxsize=settings.DB_POOL_MAX,
    )

    # 2. Redis session store
    await session_manager.connect(
        redis_url=settings.REDIS_URL,
        ttl_seconds=settings.SESSION_TTL_SECONDS,
    )

    # 3. Azure OpenAI client
    ai_service.initialize(
        endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        deployment=settings.AZURE_OPENAI_DEPLOYMENT,
        max_tokens=settings.AI_MAX_TOKENS,
        temperature=settings.AI_TEMPERATURE,
        timeout=settings.AI_TIMEOUT_SECONDS,
    )

    # 4. Configure cache TTL
    set_cache_ttl(settings.TOKO_CACHE_TTL_SECONDS)

    logger.info("✅ All services initialized.")

    yield

    # Shutdown
    logger.info("🔴 Shutting down...")
    await db_manager.disconnect()
    await session_manager.disconnect()
    logger.info("🔴 Shutdown complete.")


# ── App Factory ───────────────────────────────────────
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title="PasekSaaS AI Backend",
        version=__version__,
        lifespan=lifespan,
    )

    # ── CORS Middleware ──────────────────────────────
    # Build regex pattern for subdomain wildcard matching
    # Allows: https://anything.websitewayan.my.id
    escaped_domain = re.escape(settings.SITE_DOMAIN)
    origin_regex = rf"https?://([a-zA-Z0-9\-]+\.)?{escaped_domain}"

    application.add_middleware(
        CORSMiddleware,
        allow_origin_regex=origin_regex,
        allow_origins=[
            "http://localhost:5173",    # Vite dev
            "http://localhost:8000",    # Local API
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8000",
        ],
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["Content-Type"],
        allow_credentials=True,
    )

    # ── Rate Limiter ────────────────────────────────
    # Slowapi requires limiter on app.state
    application.state.limiter = chat.limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── Routers ─────────────────────────────────────
    application.include_router(chat.router)
    application.include_router(health.router)

    return application


# Create the app instance (imported by uvicorn)
app = create_app()
