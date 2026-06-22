"""Health-check router: verifies PostgreSQL and Meilisearch connectivity."""

from __future__ import annotations

import logging

import anyio
from fastapi import APIRouter, Response, status

from database import DatabaseConnectionError, check_database_connection
from schemas import DependencyStatus, HealthResponse
from search_index import SearchIndexError, check_search_connection

logger = logging.getLogger("error_encyclopedia.health")

router = APIRouter(tags=["health"])


async def _check_database() -> DependencyStatus:
    """Probe PostgreSQL connectivity without raising."""
    try:
        await check_database_connection()
        return DependencyStatus(
            name="database", healthy=True, detail="PostgreSQL reachable."
        )
    except DatabaseConnectionError as exc:
        logger.warning("Health check: database unavailable: %s", exc)
        return DependencyStatus(name="database", healthy=False, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - health must never raise
        logger.exception("Health check: unexpected database error")
        return DependencyStatus(
            name="database", healthy=False, detail=f"Unexpected error: {exc}"
        )


async def _check_search() -> DependencyStatus:
    """Probe Meilisearch connectivity without raising (sync client off-thread)."""
    try:
        await anyio.to_thread.run_sync(check_search_connection)
        return DependencyStatus(
            name="search", healthy=True, detail="Meilisearch reachable."
        )
    except SearchIndexError as exc:
        logger.warning("Health check: search unavailable: %s", exc)
        return DependencyStatus(name="search", healthy=False, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - health must never raise
        logger.exception("Health check: unexpected search error")
        return DependencyStatus(
            name="search", healthy=False, detail=f"Unexpected error: {exc}"
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness/readiness probe for the API and its dependencies.",
)
async def health(response: Response) -> HealthResponse:
    """Return per-dependency status; HTTP 200 if all healthy, else 503."""
    db_status = await _check_database()
    search_status = await _check_search()
    dependencies = [db_status, search_status]

    all_healthy = all(dep.healthy for dep in dependencies)
    if not all_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="ok" if all_healthy else "degraded",
        dependencies=dependencies,
    )
