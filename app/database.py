# app/database.py
# PasekSaaS — Async MySQL Connection Pool (aiomysql)
# ──────────────────────────────────────────────────────
"""
Async database layer using aiomysql. Replaces the synchronous
mysql.connector that was blocking the FastAPI event loop.

Usage:
    async with db_manager.connection() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT ...", (param,))
            row = await cur.fetchone()
"""

import logging
from contextlib import asynccontextmanager

import aiomysql

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages an async MySQL connection pool lifecycle."""

    def __init__(self):
        self._pool: aiomysql.Pool | None = None

    async def connect(
        self,
        host: str,
        user: str,
        password: str,
        db: str,
        charset: str = "utf8mb4",
        minsize: int = 2,
        maxsize: int = 10,
    ) -> None:
        """Create the connection pool. Called once during app startup."""
        self._pool = await aiomysql.create_pool(
            host=host,
            user=user,
            password=password,
            db=db,
            charset=charset,
            minsize=minsize,
            maxsize=maxsize,
            autocommit=False,
            echo=False,
            pool_recycle=3600,  # Recycle connections every hour
        )
        logger.info("✅ Async MySQL pool ready (min=%d, max=%d)", minsize, maxsize)

    async def disconnect(self) -> None:
        """Close all connections in the pool. Called on app shutdown."""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            logger.info("🔴 MySQL pool closed.")

    @asynccontextmanager
    async def connection(self):
        """Async context manager that yields a connection and auto-releases it.
        
        Usage:
            async with db_manager.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(...)
        """
        if not self._pool:
            raise RuntimeError("Database pool not initialized. Call connect() first.")

        conn = await self._pool.acquire()
        try:
            yield conn
        finally:
            self._pool.release(conn)

    async def ping(self) -> bool:
        """Check if the database is reachable."""
        try:
            async with self.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
            return True
        except Exception as e:
            logger.warning("DB ping failed: %s", e)
            return False


# Global singleton — initialized in lifespan
db_manager = DatabaseManager()
