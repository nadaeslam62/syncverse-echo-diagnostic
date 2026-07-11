"""SyncVerse Echo - FastAPI application entrypoint.

Echo is mounted as an integrated feature of the SyncVerse backend (prefix
`/echo` by default) rather than a standalone service, so it can be included
directly into the main SyncVerse app if desired:

    from app.main import app as echo_app
    main_app.mount("/echo-service", echo_app)

or by simply including `app.api.routes.*` routers into an existing FastAPI
instance.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import echo, health, memory, summary, timeline
from app.core.config import settings
from app.core.database import init_db
from app.core.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s (env=%s)", settings.APP_NAME, __version__, settings.APP_ENV)
    db_kind = "SQLite (fallback)" if settings.using_sqlite_fallback else "PostgreSQL"
    logger.info("Database: %s", db_kind)
    init_db()
    if not settings.has_llm_credentials:
        logger.warning(
            "GOOGLE_API_KEY is not set. Echo will boot, but chat responses "
            "and embeddings will use degraded local fallbacks until it is "
            "configured."
        )
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title="SyncVerse Echo",
    description=(
        "Echo - the AI teammate and living memory of every SyncVerse "
        "project. Not a chatbot: an integrated intelligence layer that "
        "remembers project decisions, coordinates teams, advises on "
        "technical choices, and writes documentation."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def log_validation_errors(request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI's default behaviour for a bad request body is to return a
    422 with zero server-side log line. Once an external caller (e.g. the
    SyncVerse backend, once integrated) starts sending requests here, a
    schema mismatch would otherwise be indistinguishable from "nothing
    called us" - both just show up as an empty /timeline later. Log the
    raw body and the validation errors for every failed request so any
    future caller-side DTO/casing mismatch is visible in Echo's own logs
    the moment it happens, not just as an opaque 422 to the caller.
    """
    try:
        raw_body = await request.body()
        body_preview = raw_body.decode("utf-8", errors="replace")[:2000]
    except Exception:  # pragma: no cover - defensive
        body_preview = "<unable to read body>"

    logger.error(
        "Request validation failed: %s %s errors=%s body=%s",
        request.method, request.url.path, exc.errors(), body_preview,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


app.include_router(health.router, prefix=settings.API_PREFIX)
app.include_router(echo.router, prefix=settings.API_PREFIX)
app.include_router(memory.router, prefix=settings.API_PREFIX)
app.include_router(timeline.router, prefix=settings.API_PREFIX)
app.include_router(summary.router, prefix=settings.API_PREFIX)


@app.get("/", include_in_schema=False)
def root():
    return {
        "service": settings.APP_NAME,
        "version": __version__,
        "docs": "/docs",
        "chat_endpoint": f"{settings.API_PREFIX}/chat",
    }
