# app/routers/chat.py
# PasekSaaS — Chat Endpoint
# ──────────────────────────────────────────────────────
"""
POST /api/chat    — Backward-compatible (MUST NOT break frontend)
POST /api/v1/chat — Versioned endpoint

Frontend integration:
  - Called by: react-app/src/hooks/useChat.js:34
  - Request:   { id_toko, session_id, user_message }
  - Response:  { reply, db_result, toko, gaya, session_id }
"""

import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings
from app.schemas import ChatRequest, ChatResponse
from app.redis import session_manager
from app.services.toko_service import get_toko_data, get_produk_list, log_chat_to_db
from app.services.chat_service import build_system_prompt, find_mentioned_products
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


async def _handle_chat(payload: ChatRequest, background_tasks: BackgroundTasks) -> ChatResponse:
    """
    Core chat handler logic shared between /api/chat and /api/v1/chat.
    Separated to avoid code duplication while maintaining backward compatibility.
    """
    settings = get_settings()

    logger.info(
        "[CHAT] id_toko=%d | session=%s...",
        payload.id_toko,
        payload.session_id[:10],
    )

    # 1. Fetch store data (cached)
    toko = await get_toko_data(payload.id_toko)
    if not toko:
        raise HTTPException(status_code=404, detail="Toko tidak ditemukan.")

    # 2. Fetch product list (cached)
    produk_list = await get_produk_list(payload.id_toko)

    # 3. Build system prompt
    system_prompt = build_system_prompt(toko, produk_list)

    # 4. Load session history from Redis
    history = await session_manager.get_history(payload.id_toko, payload.session_id)

    # 5. Construct messages for AI
    messages = [{"role": "system", "content": system_prompt}]
    messages += history
    messages.append({"role": "user", "content": payload.user_message})

    # 6. Call Azure OpenAI (with retry + timeout)
    try:
        reply = await ai_service.chat(messages)
    except Exception as e:
        logger.error(
            "Azure OpenAI Error (id_toko=%d): %s: %s",
            payload.id_toko,
            type(e).__name__,
            e,
        )
        raise HTTPException(
            status_code=503,
            detail="Layanan AI sedang tidak tersedia. Silakan coba lagi.",
        )

    # 7. Detect mentioned products for card UI
    db_result = find_mentioned_products(reply, produk_list)

    # 8. Update session history in Redis
    history.append({"role": "user", "content": payload.user_message})
    history.append({"role": "assistant", "content": reply})
    await session_manager.save_history(
        payload.id_toko,
        payload.session_id,
        history,
        max_messages=settings.MAX_HISTORY * 2,
    )

    # 9. Log chat to database (fire-and-forget background task)
    background_tasks.add_task(
        log_chat_to_db,
        payload.id_toko,
        payload.session_id,
        payload.user_message,
        reply,
    )

    # 10. Return response matching frontend contract
    return ChatResponse(
        reply=reply,
        db_result=db_result,
        toko=toko.get("nama_toko", ""),
        gaya=toko.get("ai_gaya_bahasa") or "formal",
        session_id=payload.session_id,
    )


@router.post("/api/chat", response_model=ChatResponse)
@limiter.limit("15/minute")
async def chat_endpoint(
    request: Request,
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
):
    """Backward-compatible chat endpoint (used by current frontend)."""
    return await _handle_chat(payload, background_tasks)


@router.post("/api/v1/chat", response_model=ChatResponse)
@limiter.limit("15/minute")
async def chat_endpoint_v1(
    request: Request,
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
):
    """Versioned chat endpoint for future API evolution."""
    return await _handle_chat(payload, background_tasks)
