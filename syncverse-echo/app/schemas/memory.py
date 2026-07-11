from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.memory import MemoryType
from app.schemas.common import ORMModel


class MemoryCreate(BaseModel):
    """Incoming payload for POST /memory.

    Deliberately left strict/snake_case for now, NOT case-tolerant. This
    is diagnostic-first: main.py logs the raw body + validation errors of
    any request that fails validation, so if the backend's real requests
    are being rejected for a casing reason, that will show up verbatim in
    server logs. Once that's confirmed (or ruled out) against a real
    request, either add case-tolerant aliasing here or fix the actual
    root cause - don't do both at once, since a permissive schema would
    silently absorb the exact mismatch we're trying to observe.
    """

    project_id: UUID
    team_name: Optional[str] = None
    memory_type: MemoryType
    title: str = Field(..., max_length=500)
    content: str
    author: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryOut(ORMModel):
    id: UUID
    project_id: UUID
    team_name: Optional[str] = None
    memory_type: MemoryType
    title: str
    content: str
    author: Optional[str] = None
    created_at: datetime


class MemorySearchResult(BaseModel):
    memory: MemoryOut
    relevance_score: float
