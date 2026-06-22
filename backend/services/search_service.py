"""Search orchestration on top of the synchronous Meilisearch client.

The official ``meilisearch`` client is synchronous, so every network call is
dispatched onto a worker thread via :func:`anyio.to_thread.run_sync` to keep the
async event loop responsive. Meilisearch outages/timeouts surface from
``search_index`` as :class:`SearchIndexError`; this layer re-raises them as
:class:`SearchUnavailable` so the router can cleanly map them to HTTP 503.
"""

from __future__ import annotations

import logging
from typing import Any

import anyio
from meilisearch.errors import MeilisearchError

from models import Error
from schemas import (
    AutocompleteSuggestion,
    ErrorSummary,
    SearchResponse,
    SearchResultItem,
)
from search_index import (
    SearchIndexError,
    get_client,
    search_settings,
)

logger = logging.getLogger("error_encyclopedia.search_service")

# Defensive bounds so a malicious/buggy client cannot request an unbounded page.
_MAX_LIMIT = 50
_DEFAULT_LIMIT = 20


class SearchUnavailable(RuntimeError):
    """Raised when the search backend cannot serve a request (maps to HTTP 503)."""


def _clamp_limit(limit: int, default: int = _DEFAULT_LIMIT) -> int:
    """Clamp a requested limit into the ``[1, _MAX_LIMIT]`` range."""
    if limit <= 0:
        return default
    return min(limit, _MAX_LIMIT)


def _run_raw_search(query: str, limit: int, attributes: list[str]) -> dict[str, Any]:
    """Execute a blocking Meilisearch query (called inside a worker thread).

    Wraps the synchronous client and normalizes engine errors into
    :class:`SearchIndexError` so the async caller has a single exception type.
    """
    client = get_client()
    index_uid = search_settings.MEILISEARCH_INDEX
    try:
        return client.index(index_uid).search(
            query,
            {"limit": limit, "attributesToRetrieve": attributes},
        )
    except MeilisearchError as exc:
        logger.exception("Meilisearch query failed for %r", query)
        raise SearchIndexError("Meilisearch query failed.") from exc


def _hit_to_result(hit: dict[str, Any]) -> SearchResultItem:
    """Convert a raw Meilisearch hit dict into a typed :class:`SearchResultItem`."""
    return SearchResultItem(
        slug=str(hit.get("slug", "")),
        title=str(hit.get("title", "")),
        plain_english_explanation=str(hit.get("plain_english_explanation", "")),
        root_cause_count=int(hit.get("root_cause_count", 0) or 0),
        fix_count=int(hit.get("fix_count", 0) or 0),
    )


async def search_errors(query: str, limit: int = _DEFAULT_LIMIT) -> SearchResponse:
    """Full-text search for errors.

    An empty/whitespace query short-circuits to an empty result set *before*
    touching Meilisearch, so the endpoint stays a 200 even when the search
    engine is down. Zero hits return cleanly as an empty list.
    """
    normalized = query.strip()
    if not normalized:
        return SearchResponse(query="", total=0, hits=[], processing_time_ms=0)

    bounded_limit = _clamp_limit(limit)
    attributes = [
        "slug",
        "title",
        "plain_english_explanation",
        "root_cause_count",
        "fix_count",
    ]
    try:
        raw = await anyio.to_thread.run_sync(
            _run_raw_search, normalized, bounded_limit, attributes
        )
    except SearchIndexError as exc:
        raise SearchUnavailable(str(exc)) from exc

    raw_hits = raw.get("hits") or []
    hits = [_hit_to_result(hit) for hit in raw_hits]
    return SearchResponse(
        query=normalized,
        total=len(hits),
        hits=hits,
        processing_time_ms=int(raw.get("processingTimeMs", 0) or 0),
    )


async def autocomplete_errors(
    query: str, limit: int = _DEFAULT_LIMIT
) -> list[AutocompleteSuggestion]:
    """Lightweight typeahead suggestions (slug + title only).

    Returns an empty list for an empty query without touching Meilisearch.
    """
    normalized = query.strip()
    if not normalized:
        return []

    bounded_limit = _clamp_limit(limit, default=min(_DEFAULT_LIMIT, 10))
    attributes = ["slug", "title"]
    try:
        raw = await anyio.to_thread.run_sync(
            _run_raw_search, normalized, bounded_limit, attributes
        )
    except SearchIndexError as exc:
        raise SearchUnavailable(str(exc)) from exc

    raw_hits = raw.get("hits") or []
    return [
        AutocompleteSuggestion(
            slug=str(hit.get("slug", "")), title=str(hit.get("title", ""))
        )
        for hit in raw_hits
        if hit.get("slug")
    ]


async def related_errors(error: Error, limit: int = 5) -> list[ErrorSummary]:
    """Find errors related to ``error`` by searching its title.

    The error's own slug is excluded from the results. Returns an empty list
    (never raises) so detail-page rendering degrades gracefully when the search
    backend is unavailable — related errors are a non-critical enrichment.
    """
    title = (error.title or "").strip()
    if not title:
        return []

    bounded_limit = _clamp_limit(limit, default=min(_DEFAULT_LIMIT, 10))
    # Over-fetch by one so excluding the error itself still yields ``limit`` rows.
    attributes = ["slug", "title", "plain_english_explanation"]
    try:
        raw = await anyio.to_thread.run_sync(
            _run_raw_search, title, bounded_limit + 1, attributes
        )
    except SearchIndexError:
        logger.warning(
            "Search backend unavailable while fetching related errors for %r; "
            "returning none.",
            error.slug,
        )
        return []

    raw_hits = raw.get("hits") or []
    related: list[ErrorSummary] = []
    for hit in raw_hits:
        slug = str(hit.get("slug", ""))
        if not slug or slug == error.slug:
            continue
        related.append(
            ErrorSummary(
                slug=slug,
                title=str(hit.get("title", "")),
                plain_english_explanation=str(
                    hit.get("plain_english_explanation", "")
                ),
            )
        )
        if len(related) >= bounded_limit:
            break
    return related
