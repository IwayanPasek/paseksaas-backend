# app/schemas.py
# PasekSaaS — Pydantic Request/Response Schemas
# ──────────────────────────────────────────────────────
from pydantic import BaseModel, Field, field_validator, AliasChoices
from typing import List, Optional, Any
import re

class ChatRequest(BaseModel):
    """Incoming chat message from the storefront widget."""
    store_id: int = Field(..., validation_alias=AliasChoices("store_id", "id_toko"), ge=1, description="Store ID (positive integer)")
    session_id: str = Field(..., min_length=5, max_length=100, description="Client session identifier")
    user_message: str = Field(..., min_length=1, max_length=500, description="User message text")

    @field_validator("user_message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        v = v.strip()
        v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)
        if not v:
            raise ValueError("Message cannot be empty after sanitation.")
        return v

    @field_validator("session_id")
    @classmethod
    def sanitize_session(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_\-]+$", v):
            raise ValueError("Invalid session_id format.")
        return v

class ProductItem(BaseModel):
    """Product summary for chat responses (Matches frontend contract)."""
    id: int = Field(..., validation_alias=AliasChoices("id", "id_produk"))
    name: str = Field(..., validation_alias=AliasChoices("name", "nama_produk"))
    price: int = Field(..., validation_alias=AliasChoices("price", "harga"))
    description: Optional[str] = Field(None, validation_alias=AliasChoices("description", "deskripsi"))
    image: Optional[str] = Field(None, validation_alias=AliasChoices("image", "foto_produk"))
    categoryId: Optional[int] = Field(None, validation_alias=AliasChoices("categoryId", "id_kategori"))

class ChatResponse(BaseModel):
    """Response to the chat widget."""
    reply: str
    products: List[ProductItem] = []
    store_name: str
    tone: str = "formal"
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
