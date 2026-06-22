"""Errors router: detail lookup, paginated listing, and ingestion."""

from __future__ import annotations

import logging

import anyio
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from crud import create_error, get_error_by_slug, list_errors
from database import get_db
from schemas import (
    ErrorCreate,
    ErrorDetail,
    ErrorSummary,
    RootCauseRead,
    VerifiedFixRead,
)
from search_index import SearchIndexError
from search_index import index_error as index_error_sync
from services import related_errors

logger = logging.getLogger("error_encyclopedia.errors")

router = APIRouter(prefix="/api/errors", tags=["errors"])


@router.get(
    "",
    response_model=list[ErrorSummary],
    summary="List errors (most recent first).",
)
async def list_errors_endpoint(
    limit: int = Query(default=50, ge=1, le=200, description="Page size."),
    offset: int = Query(default=0, ge=0, description="Number of rows to skip."),
    session: AsyncSession = Depends(get_db),
) -> list[ErrorSummary]:
    """Return a page of error summaries ordered by creation time descending."""
    errors = await list_errors(session, limit=limit, offset=offset)
    return [ErrorSummary.model_validate(error) for error in errors]


@router.get(
    "/{slug}",
    response_model=ErrorDetail,
    summary="Fetch a single error with its root causes, fixes, and related errors.",
)
async def get_error_endpoint(
    slug: str,
    session: AsyncSession = Depends(get_db),
) -> ErrorDetail:
    """Return full error detail. Responds with 404 for an unknown slug."""
    error = await get_error_by_slug(session, slug)
    if error is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No error found for slug '{slug}'.",
        )

    related = await related_errors(error, limit=5)
    return ErrorDetail(
        slug=error.slug,
        title=error.title,
        plain_english_explanation=error.plain_english_explanation,
        created_at=error.created_at,
        root_causes=[RootCauseRead.model_validate(rc) for rc in error.root_causes],
        verified_fixes=[
            VerifiedFixRead.model_validate(fix) for fix in error.verified_fixes
        ],
        related=related,
    )


@router.post(
    "",
    response_model=ErrorDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new error and index it for search.",
)
async def create_error_endpoint(
    payload: ErrorCreate,
    session: AsyncSession = Depends(get_db),
) -> ErrorDetail:
    """Persist an error with its children, then best-effort index it.

    If Meilisearch indexing fails, the database row is still created (the request
    succeeds) and a warning is logged — search consistency is reconciled later by
    a re-index rather than failing user-facing writes.
    """
    error = await create_error(session, payload)

    # Best-effort search indexing: never fail the write on a search outage.
    try:
        await anyio.to_thread.run_sync(index_error_sync, error)
    except SearchIndexError as exc:
        logger.warning(
            "Created error %r but failed to index it for search: %s",
            error.slug,
            exc,
        )
    except Exception as exc:  # noqa: BLE001 - indexing is non-critical
        logger.exception(
            "Created error %r but hit an unexpected indexing error: %s",
            error.slug,
            exc,
        )

    return ErrorDetail(
        slug=error.slug,
        title=error.title,
        plain_english_explanation=error.plain_english_explanation,
        created_at=error.created_at,
        root_causes=[RootCauseRead.model_validate(rc) for rc in error.root_causes],
        verified_fixes=[
            VerifiedFixRead.model_validate(fix) for fix in error.verified_fixes
        ],
        related=[],
    )
