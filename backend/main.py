"""FastAPI application entrypoint for the Error Encyclopedia API.

Wires together the database, search index, and HTTP routers. Startup performs a
best-effort schema initialization and search-index bootstrap (failures are logged
but never crash the app, so the service can boot and report unhealthy via
``/health`` even when a dependency is temporarily down). All domain exceptions
are mapped to clean HTTP responses — tracebacks never reach clients.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import DatabaseConnectionError, dispose_engine, init_db
from routers import errors, health, search
from search_index import SearchIndexError, ensure_index
from services.search_service import SearchUnavailable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("error_encyclopedia.main")

API_TITLE = "Error Encyclopedia API"
API_VERSION = "1.0.0"
API_DESCRIPTION = (
    "Search and browse a curated encyclopedia of software errors, their root "
    "causes, and verified fixes."
)

# The Next.js frontend runs on localhost:3000 during development.
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: bootstrap dependencies on startup, clean up on exit."""
    logger.info("Starting %s v%s", API_TITLE, API_VERSION)

    try:
        await init_db()
        logger.info("Database schema initialized.")
    except DatabaseConnectionError as exc:
        logger.error("Database initialization failed at startup: %s", exc)
    except Exception:  # noqa: BLE001 - startup must not crash the process
        logger.exception("Unexpected error during database initialization.")

    try:
        await anyio.to_thread.run_sync(ensure_index)
        logger.info("Search index ensured.")
    except SearchIndexError as exc:
        logger.error("Search index bootstrap failed at startup: %s", exc)
    except Exception:  # noqa: BLE001 - startup must not crash the process
        logger.exception("Unexpected error during search index bootstrap.")

    try:
        yield
    finally:
        try:
            await dispose_engine()
            logger.info("Database engine disposed.")
        except Exception:  # noqa: BLE001 - shutdown must be best-effort
            logger.exception("Error while disposing the database engine.")


app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Exception handlers — translate domain errors into clean HTTP responses.
# ---------------------------------------------------------------------------


@app.exception_handler(DatabaseConnectionError)
async def handle_database_error(
    request: Request, exc: DatabaseConnectionError
) -> JSONResponse:
    """Map database connectivity failures to HTTP 503."""
    logger.error("Database error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "The database is temporarily unavailable. Please try again shortly."
        },
    )


@app.exception_handler(SearchIndexError)
async def handle_search_index_error(
    request: Request, exc: SearchIndexError
) -> JSONResponse:
    """Map search-index failures to HTTP 503."""
    logger.error("Search error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "Search is temporarily unavailable. Please try again shortly."
        },
    )


@app.exception_handler(SearchUnavailable)
async def handle_search_unavailable(
    request: Request, exc: SearchUnavailable
) -> JSONResponse:
    """Map search-service unavailability to HTTP 503."""
    logger.error(
        "Search unavailable on %s %s: %s", request.method, request.url.path, exc
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "Search is temporarily unavailable. Please try again shortly."
        },
    )


@app.exception_handler(OSError)
async def handle_connection_error(request: Request, exc: OSError) -> JSONResponse:
    """Map low-level connection failures (e.g. asyncpg raising a bare ``OSError``
    when PostgreSQL is unreachable) to HTTP 503 instead of a generic 500.

    SQLAlchemy/asyncpg surface connection-refused failures as ``OSError`` rather
    than ``SQLAlchemyError`` during the connect phase, so they bypass ``get_db``'s
    ``SQLAlchemyError`` translation and would otherwise leak through as a 500.
    """
    logger.error(
        "Connection error on %s %s: %s", request.method, request.url.path, exc
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "A required backend service is temporarily unavailable. "
            "Please try again shortly."
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler: log the traceback, return a generic 500 to the client."""
    logger.exception(
        "Unhandled error on %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected internal error occurred."},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(health.router)
app.include_router(search.router)
app.include_router(errors.router)


@app.get("/", tags=["meta"], summary="Service metadata.")
async def root() -> dict[str, str]:
    """Return basic service metadata and links to interactive docs."""
    return {
        "service": API_TITLE,
        "version": API_VERSION,
        "docs": "/docs",
        "health": "/health",
    }
