# app/services/toko_service.py
# PasekSaaS — Toko (Store) Data Service
# ──────────────────────────────────────────────────────
"""
Handles all database operations related to toko (store) data.
Includes TTL caching to avoid redundant DB hits on every chat message.
"""

import json
import time
import logging
from typing import Any

import aiomysql

from app.database import db_manager

logger = logging.getLogger(__name__)

# ── Simple TTL cache ──────────────────────────────────
# Structure: { cache_key: (timestamp, data) }
_cache: dict[str, tuple[float, Any]] = {}
_cache_ttl: int = 300  # 5 minutes default, overridden from config


def set_cache_ttl(ttl_seconds: int) -> None:
    """Configure the cache TTL. Called once during startup."""
    global _cache_ttl
    _cache_ttl = ttl_seconds


def _get_cached(key: str) -> Any | None:
    """Return cached value if exists and not expired."""
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < _cache_ttl:
            return data
        del _cache[key]
    return None


def _set_cached(key: str, data: Any) -> None:
    """Store value in cache with current timestamp."""
    _cache[key] = (time.time(), data)


def invalidate_cache(id_toko: int | None = None) -> None:
    """Clear cache for a specific toko, or all if id_toko is None."""
    if id_toko is None:
        _cache.clear()
    else:
        keys_to_del = [k for k in _cache if k.endswith(f":{id_toko}")]
        for k in keys_to_del:
            del _cache[k]


# ── Database Queries ──────────────────────────────────

async def get_toko_data(id_toko: int) -> dict | None:
    """
    Fetch store data by ID. Results are cached for TOKO_CACHE_TTL_SECONDS.
    
    Returns:
        dict with keys: nama_toko, knowledge_base, ai_persona_prompt, ai_gaya_bahasa
        None if toko not found
    """
    cache_key = f"toko:{id_toko}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        async with db_manager.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT nama_toko, knowledge_base, ai_persona_prompt, ai_gaya_bahasa
                    FROM toko WHERE id_toko = %s LIMIT 1
                    """,
                    (id_toko,),
                )
                row = await cur.fetchone()

        if row:
            _set_cached(cache_key, row)
        return row

    except Exception as e:
        logger.error("DB Error get_toko_data (id_toko=%d): %s", id_toko, e)
        return None


async def get_produk_list(id_toko: int) -> list[dict]:
    """
    Fetch product list for a store. Results are cached.
    
    Returns:
        List of dicts with keys: id_produk, nama_produk, harga, deskripsi, foto_produk
    """
    cache_key = f"produk:{id_toko}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        async with db_manager.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT id_produk, nama_produk, harga, deskripsi, foto_produk
                    FROM produk WHERE id_toko = %s ORDER BY id_produk DESC LIMIT 30
                    """,
                    (id_toko,),
                )
                rows = await cur.fetchall()

        _set_cached(cache_key, rows)
        return rows

    except Exception as e:
        logger.error("DB Error get_produk_list (id_toko=%d): %s", id_toko, e)
        return []


async def log_chat_to_db(
    id_toko: int,
    session_id: str,
    user_query: str,
    ai_response: str,
) -> None:
    """
    Log a chat interaction to the database (fire-and-forget via BackgroundTask).
    Failures are logged but do not affect the user response.
    """
    try:
        async with db_manager.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO log_chat (id_toko, session_id, user_query, ai_response)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        id_toko,
                        session_id,
                        user_query,
                        json.dumps({"reply": ai_response}, ensure_ascii=False),
                    ),
                )
            await conn.commit()
    except Exception as e:
        logger.warning("Failed to log chat (id_toko=%d): %s", id_toko, e)
