# app/redis.py
# PasekSaaS — Redis Session Manager
# ──────────────────────────────────────────────────────
"""
Manages chat session history in Redis with automatic TTL expiry.
Replaces the in-memory dict that leaked memory and was lost on restart.

Each session key stores a JSON-serialized list of message dicts:
  [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
"""

import json
import logging

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class SessionManager:
    """Redis-backed chat session store with TTL."""

    def __init__(self):
        self._redis: aioredis.Redis | None = None
        self._ttl: int = 3600  # Default 1 hour

    async def connect(self, redis_url: str, ttl_seconds: int = 3600) -> None:
        """Connect to Redis. Called once during app startup."""
        self._ttl = ttl_seconds
        self._redis = aioredis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )
        # Verify connection
        await self._redis.ping()
        logger.info("✅ Redis session store ready (TTL=%ds)", ttl_seconds)

    async def disconnect(self) -> None:
        """Close Redis connection. Called on app shutdown."""
        if self._redis:
            await self._redis.close()
            logger.info("🔴 Redis connection closed.")

    def _key(self, id_toko: int, session_id: str) -> str:
        """Build the Redis key for a session."""
        return f"chat_session:{id_toko}:{session_id}"

    async def get_history(self, id_toko: int, session_id: str) -> list[dict]:
        """Retrieve chat history for a session.
        
        Returns:
            List of message dicts [{"role": "...", "content": "..."}]
        """
        if not self._redis:
            return []

        try:
            key = self._key(id_toko, session_id)
            raw = await self._redis.get(key)
            if raw:
                return json.loads(raw)
            return []
        except Exception as e:
            logger.warning("Redis get_history error: %s", e)
            return []

    async def save_history(
        self,
        id_toko: int,
        session_id: str,
        messages: list[dict],
        max_messages: int = 20,
    ) -> None:
        """Save chat history with TTL and sliding window truncation.
        
        Args:
            id_toko: Store ID
            session_id: Client session ID
            messages: Full message list
            max_messages: Max messages to keep (pairs × 2)
        """
        if not self._redis:
            return

        try:
            key = self._key(id_toko, session_id)
            # Truncate to last N messages (sliding window)
            trimmed = messages[-max_messages:]
            await self._redis.setex(
                key,
                self._ttl,
                json.dumps(trimmed, ensure_ascii=False),
            )
        except Exception as e:
            logger.warning("Redis save_history error: %s", e)

    async def ping(self) -> bool:
        """Check if Redis is reachable."""
        if not self._redis:
            return False
        try:
            return await self._redis.ping()
        except Exception:
            return False


# Global singleton — initialized in lifespan
session_manager = SessionManager()
