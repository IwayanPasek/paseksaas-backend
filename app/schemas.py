# app/schemas.py
# PasekSaaS — Pydantic Request/Response Schemas
# ──────────────────────────────────────────────────────
"""
Strict API contract definitions. These models are used for both
request validation and response serialization (OpenAPI docs).

IMPORTANT: Response field names MUST match what the React frontend expects.
See: react-app/src/hooks/useChat.js (lines 34-51)
     react-app/src/pages/storefront/components/ChatBubble.jsx (lines 22-34)
"""

import re
from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Incoming chat message from the storefront widget."""

    id_toko: int = Field(..., ge=1, description="Store ID (positive integer)")
    session_id: str = Field(..., min_length=5, max_length=100, description="Client session identifier")
    user_message: str = Field(..., min_length=1, max_length=500, description="User message text")

    @field_validator("user_message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        """Strip whitespace and remove dangerous control characters."""
        v = v.strip()
        v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)
        if not v:
            raise ValueError("Pesan tidak boleh kosong setelah sanitasi.")
        return v

    @field_validator("session_id")
    @classmethod
    def sanitize_session(cls, v: str) -> str:
        """Only allow alphanumeric, underscore, dash characters."""
        if not re.match(r"^[a-zA-Z0-9_\-]+$", v):
            raise ValueError("Format session_id tidak valid.")
        return v


class ProductCard(BaseModel):
    """Product card data sent to frontend for rendering in chat bubbles.
    
    Maps to: ChatBubble.jsx → msg.products[]
    Image path used by frontend: /assets/img/produk/{foto_produk}
    """

    id_produk: int
    nama_produk: str
    harga: float
    deskripsi: str | None = None
    foto_produk: str | None = None


class ChatResponse(BaseModel):
    """Response to the chat widget.
    
    CRITICAL: These field names are consumed by useChat.js:
      - data.reply       → AI response text
      - data.db_result   → Product cards array
      - data.toko        → Store name (for display)
      - data.gaya        → Language style
      - data.session_id  → Echo back session ID
    """

    reply: str
    db_result: list[ProductCard] = []
    toko: str
    gaya: str = "formal"
    session_id: str


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = "ok"
    service: str = "PasekSaaS AI Backend"
    version: str
    database: str
    redis: str
    deployment: str
    api_version: str
