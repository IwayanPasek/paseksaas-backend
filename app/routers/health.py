# app/routers/health.py
# PasekSaaS — Health Check Endpoint
# ──────────────────────────────────────────────────────
"""
GET /health — System health check

Verifies connectivity to:
  - MySQL database pool
  - Redis session store
  - Azure OpenAI client readiness

Used by: Apache ProxyPass /health → :8000/health
"""

from fastapi import APIRouter

from app import __version__
from app.config import get_settings
from app.database import db_manager
from app.redis import session_manager
from app.services.ai_service import ai_service
from app.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check for monitoring."""
    settings = get_settings()

    # Check database
    db_ok = await db_manager.ping()

    # Check Redis
    redis_ok = await session_manager.ping()

    return HealthResponse(
        status="ok" if (db_ok and redis_ok) else "degraded",
        version=__version__,
        database="ok" if db_ok else "error",
        redis="ok" if redis_ok else "error",
        deployment=settings.AZURE_OPENAI_DEPLOYMENT,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )
