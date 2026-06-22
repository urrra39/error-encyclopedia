"""Meilisearch connection, index mapping, and document synchronization.

Responsibilities:

* Build a configured Meilisearch :class:`~meilisearch.Client` (with a request
  timeout so a hung search engine never blocks the API indefinitely).
* Declare the ``errors`` index *settings* (searchable / filterable / sortable
  attributes, ranking rules, typo tolerance, synonyms). Meilisearch stores
  documents schemalessly, so these settings are what drive search quality.
* Convert an :class:`~models.Error` ORM row into a strictly-typed
  :class:`MeiliErrorDocument` and push / remove it from the index.

Every network call is wrapped so Meilisearch outages or timeouts raise a single
:class:`SearchIndexError` instead of leaking driver-specific exceptions.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from meilisearch import Client
from meilisearch.errors import MeilisearchError
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from models import Error

logger = logging.getLogger("error_encyclopedia.search")

PRIMARY_KEY = "slug"


class SearchIndexError(RuntimeError):
    """Raised when Meilisearch is unreachable, times out, or rejects a request."""


class SearchSettings(BaseSettings):
    """Meilisearch configuration loaded from the environment / ``.env`` file."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    MEILISEARCH_URL: str = "http://localhost:7700"
    MEILISEARCH_API_KEY: str = ""
    MEILISEARCH_INDEX: str = "errors"
    # Per-request timeout (seconds) so a slow/hung engine fails fast.
    MEILISEARCH_TIMEOUT: int = 5


@lru_cache(maxsize=1)
def get_search_settings() -> SearchSettings:
    """Return a cached, validated ``SearchSettings`` singleton."""
    return SearchSettings()


search_settings = get_search_settings()


# Order matters: earlier searchable attributes are weighted more heavily.
INDEX_SETTINGS: dict[str, Any] = {
    "searchableAttributes": [
        "title",
        "plain_english_explanation",
        "root_causes",
        "fix_explanations",
        "code_snippets",
    ],
    "filterableAttributes": ["slug", "root_cause_count", "fix_count", "created_at"],
    "sortableAttributes": ["created_at", "fix_count", "root_cause_count"],
    "rankingRules": [
        "words",
        "typo",
        "proximity",
        "attribute",
        "sort",
        "exactness",
        "fix_count:desc",
    ],
    "distinctAttribute": "slug",
    "typoTolerance": {
        "enabled": True,
        # Error names are short (e.g. "CORS"); permit typos a little earlier
        # than the Meilisearch defaults so near-miss spellings still match.
        "minWordSizeForTypos": {"oneTypo": 4, "twoTypos": 8},
    },
    "synonyms": {
        "npm": ["node package manager"],
        "oom": ["out of memory", "outofmemoryerror"],
        "segfault": ["segmentation fault", "sigsegv"],
        "cors": ["cross origin resource sharing", "cross-origin"],
        "404": ["not found"],
        "500": ["internal server error"],
        "nullpointerexception": ["npe", "null pointer"],
    },
    "stopWords": ["a", "an", "the", "of", "to", "in", "on", "is"],
}


class MeiliErrorDocument(BaseModel):
    """The exact JSON document shape stored in the ``errors`` index."""

    slug: str = Field(..., description="Unique, URL-safe primary key.")
    title: str = Field(..., description="Human-readable error title.")
    plain_english_explanation: str = Field(..., description="Plain-English description.")
    root_causes: list[str] = Field(default_factory=list)
    fix_explanations: list[str] = Field(default_factory=list)
    code_snippets: list[str] = Field(default_factory=list)
    root_cause_count: int = Field(default=0, ge=0)
    fix_count: int = Field(default=0, ge=0)
    created_at: int = Field(..., description="Creation time as a Unix timestamp.")


@lru_cache(maxsize=1)
def get_client() -> Client:
    """Return a cached Meilisearch client configured with a request timeout."""
    return Client(
        url=search_settings.MEILISEARCH_URL,
        api_key=search_settings.MEILISEARCH_API_KEY or None,
        timeout=search_settings.MEILISEARCH_TIMEOUT,
    )


def build_document(error: Error) -> dict[str, Any]:
    """Flatten an ``Error`` (with loaded relationships) into an index document.

    The result is validated through :class:`MeiliErrorDocument` before being
    returned, guaranteeing the pushed payload always matches the declared shape.
    """
    code_snippets: list[str] = []
    fix_explanations: list[str] = []
    for fix in error.verified_fixes:
        fix_explanations.append(fix.explanation)
        code_snippets.append(fix.before_code_snippet)
        code_snippets.append(fix.after_code_snippet)

    root_cause_descriptions = [rc.description for rc in error.root_causes]

    document = MeiliErrorDocument(
        slug=error.slug,
        title=error.title,
        plain_english_explanation=error.plain_english_explanation,
        root_causes=root_cause_descriptions,
        fix_explanations=fix_explanations,
        code_snippets=code_snippets,
        root_cause_count=len(root_cause_descriptions),
        fix_count=len(error.verified_fixes),
        created_at=int(error.created_at.timestamp()),
    )
    return document.model_dump()


def ensure_index() -> None:
    """Create the ``errors`` index if missing and apply :data:`INDEX_SETTINGS`.

    Idempotent: safe to call on every application startup.
    """
    client = get_client()
    index_uid = search_settings.MEILISEARCH_INDEX
    try:
        try:
            client.get_index(index_uid)
        except MeilisearchError:
            # Index does not exist yet — create it with the slug primary key.
            client.create_index(index_uid, {"primaryKey": PRIMARY_KEY})
        client.index(index_uid).update_settings(INDEX_SETTINGS)
    except MeilisearchError as exc:
        logger.exception("Failed to ensure Meilisearch index %r", index_uid)
        raise SearchIndexError(
            f"Could not create or configure the '{index_uid}' index."
        ) from exc


def index_error(error: Error) -> None:
    """Add or update a single ``Error`` document in the search index."""
    client = get_client()
    index_uid = search_settings.MEILISEARCH_INDEX
    try:
        client.index(index_uid).add_documents([build_document(error)], primary_key=PRIMARY_KEY)
    except MeilisearchError as exc:
        logger.exception("Failed to index error %r", error.slug)
        raise SearchIndexError(f"Could not index error '{error.slug}'.") from exc


def index_errors(errors: list[Error]) -> None:
    """Bulk add/update many ``Error`` documents in a single request."""
    if not errors:
        return
    client = get_client()
    index_uid = search_settings.MEILISEARCH_INDEX
    documents = [build_document(error) for error in errors]
    try:
        client.index(index_uid).add_documents(documents, primary_key=PRIMARY_KEY)
    except MeilisearchError as exc:
        logger.exception("Failed to bulk-index %d errors", len(documents))
        raise SearchIndexError("Could not bulk-index error documents.") from exc


def delete_error(slug: str) -> None:
    """Remove a single document from the index by its slug."""
    client = get_client()
    index_uid = search_settings.MEILISEARCH_INDEX
    try:
        client.index(index_uid).delete_document(slug)
    except MeilisearchError as exc:
        logger.exception("Failed to delete error %r from index", slug)
        raise SearchIndexError(f"Could not delete error '{slug}' from the index.") from exc


def check_search_connection() -> bool:
    """Return ``True`` if Meilisearch reports a healthy status, else raise."""
    client = get_client()
    try:
        health = client.health()
        if health.get("status") != "available":
            raise SearchIndexError(f"Meilisearch is not available: {health!r}")
        return True
    except MeilisearchError as exc:
        logger.exception("Meilisearch health check failed")
        raise SearchIndexError("Could not reach Meilisearch.") from exc
