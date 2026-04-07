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

async def get_toko_data(store_id: int) -> dict | None:
    """
    Fetch store data by ID. Results are cached.
    
    Returns:
        dict with keys: store_name, knowledge_base, ai_persona, ai_tone
    """
    cache_key = f"toko:{store_id}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        async with db_manager.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT 
                        nama_toko AS store_name, 
                        knowledge_base, 
                        ai_persona_prompt AS ai_persona, 
                        ai_gaya_bahasa AS ai_tone
                    FROM toko WHERE id_toko = %s LIMIT 1
                    """,
                    (store_id,),
                )
                row = await cur.fetchone()

        if row:
            _set_cached(cache_key, row)
        return row

    except Exception as e:
        logger.error("DB Error get_toko_data (store_id=%d): %s", store_id, e)
        return None


async def get_produk_list(store_id: int) -> list[dict]:
    """
    Fetch product list for a store. Results are cached.
    """
    cache_key = f"produk:{store_id}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        async with db_manager.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT 
                        id_produk, 
                        nama_produk, 
                        harga, 
                        deskripsi, 
                        foto_produk
                    FROM produk WHERE id_toko = %s ORDER BY id_produk DESC LIMIT 30
                    """,
                    (store_id,),
                )
                rows = await cur.fetchall()

        _set_cached(cache_key, rows)
        return rows

    except Exception as e:
        logger.error("DB Error get_produk_list (store_id=%d): %s", store_id, e)
        return []


async def log_chat_to_db(
    store_id: int,
    session_id: str,
    user_query: str,
    ai_response: str,
) -> None:
    """
    Log a chat interaction to the database.
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
                        store_id,
                        session_id,
                        user_query,
                        json.dumps({"reply": ai_response}, ensure_ascii=False),
                    ),
                )
            await conn.commit()
    except Exception as e:
        logger.warning("Failed to log chat (store_id=%d): %s", store_id, e)
