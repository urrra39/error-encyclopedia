"""Search router: full-text search and lightweight autocomplete."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from schemas import AutocompleteResponse, SearchResponse
from services import autocomplete_errors, search_errors
from services.search_service import SearchUnavailable

router = APIRouter(prefix="/api", tags=["search"])


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Full-text search across the error encyclopedia.",
)
async def search(
    q: str = Query(default="", description="Search query string."),
    limit: int = Query(default=20, ge=1, le=50, description="Maximum hits to return."),
) -> SearchResponse:
    """Search for errors. An empty/whitespace query returns an empty 200 result.

    A 503 is returned when the search backend is unavailable for a real query.
    """
    try:
        return await search_errors(q, limit=limit)
    except SearchUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is temporarily unavailable. Please try again shortly.",
        ) from exc


@router.get(
    "/autocomplete",
    response_model=AutocompleteResponse,
    summary="Lightweight typeahead suggestions for the search box.",
)
async def autocomplete(
    q: str = Query(default="", description="Partial query string."),
    limit: int = Query(
        default=10, ge=1, le=50, description="Maximum suggestions to return."
    ),
) -> AutocompleteResponse:
    """Return slug/title suggestions for real-time typeahead.

    An empty/whitespace query returns an empty 200 result. A 503 is returned
    when the search backend is unavailable for a real query.
    """
    normalized = q.strip()
    try:
        suggestions = await autocomplete_errors(q, limit=limit)
    except SearchUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autocomplete is temporarily unavailable. Please try again shortly.",
        ) from exc
    return AutocompleteResponse(query=normalized, suggestions=suggestions)
