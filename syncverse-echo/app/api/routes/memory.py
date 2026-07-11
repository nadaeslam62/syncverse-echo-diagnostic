import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logging_config import get_logger
from app.models.memory import Memory
from app.schemas.memory import MemoryCreate, MemoryOut
from app.services.memory_service import MemoryService
from app.services.vector_store_service import get_vector_store_service

logger = get_logger(__name__)
router = APIRouter(tags=["Memory"])


@router.post("/memory", response_model=MemoryOut, status_code=201, summary="Manually record a memory")
def create_memory(payload: MemoryCreate, db: Session = Depends(get_db)) -> MemoryOut:
    """Record a memory. Currently the only ingestion endpoint - the
    SyncVerse backend has not yet been integrated with Echo, so this is
    presently exercised by manual entry, imports, and testing rather than
    live platform events. AutoMemoryCollector
    (app/services/auto_memory_collector.py) has the domain-shaped helpers
    for that future integration but is intentionally not wired to any
    route yet, since the actual event shapes should be driven by what the
    backend integration needs, not guessed at here."""
    try:
        service = MemoryService(db)
        memory = service.create_memory(payload)
        return MemoryOut.model_validate(memory)
    except Exception as exc:
        logger.exception("Failed to create memory for project=%s", payload.project_id)
        raise HTTPException(status_code=500, detail="Failed to record memory.") from exc


@router.get(
    "/memory/diagnostics/{project_id}",
    summary="Ingestion diagnostics for a project - use this once the backend integration is live",
)
def memory_diagnostics(project_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """Ground truth for a given project, useful once the backend starts
    calling Echo:

      - postgres_row_count: 0 is expected right now, pre-integration.
        Once the backend is wired up, if this stays 0 after it should be
        sending data, check the backend is calling the right URL/prefix,
        sending this exact project_id, and Echo's logs for
        "Request validation failed" around the expected call time.
      - chroma_vector_count: should track postgres_row_count. A gap means
        rows are saved but embedding is failing (check logs for
        "Failed to embed memory").
      - database_backend: if this flags ephemeral risk and
        postgres_row_count unexpectedly drops after previously working,
        the container likely restarted and HF Spaces persistent storage
        isn't enabled - SQLite and Chroma both live under /data, which is
        wiped on restart unless persistent storage is turned on.
    """
    row_count = db.execute(
        select(func.count()).select_from(Memory).where(Memory.project_id == project_id)
    ).scalar_one()

    try:
        vector_count = get_vector_store_service().count(project_id)
        vector_status = "ok"
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Vector store count failed for project=%s: %s", project_id, exc)
        vector_count = None
        vector_status = f"error: {exc}"

    return {
        "project_id": str(project_id),
        "postgres_row_count": row_count,
        "chroma_vector_count": vector_count,
        "chroma_status": vector_status,
        "database_backend": (
            "sqlite (ephemeral risk - persists only if HF Spaces persistent "
            "storage is enabled; wiped on restart otherwise)"
            if settings.using_sqlite_fallback
            else "postgresql"
        ),
    }
