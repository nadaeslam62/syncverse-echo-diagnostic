from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import settings
from app.core.database import get_db
from app.schemas.common import HealthResponse
from app.services.vector_store_service import get_vector_store_service

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Service health check")
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unavailable"

    vector_status = "ok"
    try:
        get_vector_store_service()
    except Exception:
        vector_status = "unavailable"

    persistence_warning = None
    if settings.using_sqlite_fallback:
        persistence_warning = (
            "DATABASE_URL is not set - running on SQLite + local ChromaDB "
            "under /data. This directory only survives a restart if HF "
            "Spaces persistent storage is enabled for this Space; "
            "otherwise every redeploy/sleep/restart silently wipes all "
            "stored memories, which shows up later as an empty /timeline "
            "with no error anywhere. Set DATABASE_URL to a managed "
            "Postgres instance for production."
        )

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        app_name=settings.APP_NAME,
        version=__version__,
        database=db_status,
        database_backend="sqlite" if settings.using_sqlite_fallback else "postgresql",
        persistence_warning=persistence_warning,
        vector_store=vector_status,
        llm_configured=settings.has_llm_credentials,
    )
