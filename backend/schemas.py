"""Pydantic v2 request/response models for the Error Encyclopedia API.

These schemas form the public contract of the HTTP API. Read models that are
populated directly from SQLAlchemy ORM rows enable ``from_attributes`` so they
can be validated straight off an ``Error``/``RootCause``/``VerifiedFix`` object.
Write models (``*Create``) describe the ingestion payloads.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Read models (populated from ORM rows)
# ---------------------------------------------------------------------------


class RootCauseRead(BaseModel):
    """A single root cause as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Database identifier.")
    description: str = Field(..., description="Plain-text description of the cause.")


class VerifiedFixRead(BaseModel):
    """A single verified fix (before/after code + explanation)."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Database identifier.")
    before_code_snippet: str = Field(..., description="Code that triggers the error.")
    after_code_snippet: str = Field(..., description="Corrected code.")
    explanation: str = Field(..., description="Why the fix works.")


class ErrorSummary(BaseModel):
    """Lightweight error representation used in lists and related-error blocks."""

    model_config = ConfigDict(from_attributes=True)

    slug: str = Field(..., description="Unique, URL-safe identifier.")
    title: str = Field(..., description="Human-readable error title.")
    plain_english_explanation: str = Field(
        ..., description="Plain-English description of the error."
    )


class ErrorDetail(BaseModel):
    """Full error detail including root causes, verified fixes, and related errors."""

    model_config = ConfigDict(from_attributes=True)

    slug: str = Field(..., description="Unique, URL-safe identifier.")
    title: str = Field(..., description="Human-readable error title.")
    plain_english_explanation: str = Field(
        ..., description="Plain-English description of the error."
    )
    created_at: datetime = Field(..., description="When the error was first indexed.")
    root_causes: list[RootCauseRead] = Field(
        default_factory=list, description="Common root causes for this error."
    )
    verified_fixes: list[VerifiedFixRead] = Field(
        default_factory=list, description="Verified fixes with before/after code."
    )
    related: list[ErrorSummary] = Field(
        default_factory=list, description="Other errors related to this one."
    )


# ---------------------------------------------------------------------------
# Search models
# ---------------------------------------------------------------------------


class SearchResultItem(BaseModel):
    """A single hit returned by the search endpoint."""

    slug: str = Field(..., description="Unique, URL-safe identifier.")
    title: str = Field(..., description="Human-readable error title.")
    plain_english_explanation: str = Field(
        ..., description="Plain-English description of the error."
    )
    root_cause_count: int = Field(
        default=0, ge=0, description="Number of catalogued root causes."
    )
    fix_count: int = Field(default=0, ge=0, description="Number of verified fixes.")


class SearchResponse(BaseModel):
    """The envelope returned by the search endpoint."""

    query: str = Field(..., description="The query string that was searched.")
    total: int = Field(..., ge=0, description="Number of hits returned.")
    hits: list[SearchResultItem] = Field(
        default_factory=list, description="Matching error documents."
    )
    processing_time_ms: int = Field(
        default=0, ge=0, description="Search engine processing time in milliseconds."
    )


class AutocompleteSuggestion(BaseModel):
    """A lightweight typeahead suggestion (slug + title only)."""

    slug: str = Field(..., description="Unique, URL-safe identifier.")
    title: str = Field(..., description="Human-readable error title.")


class AutocompleteResponse(BaseModel):
    """The envelope returned by the autocomplete endpoint."""

    query: str = Field(..., description="The query string that was searched.")
    suggestions: list[AutocompleteSuggestion] = Field(
        default_factory=list, description="Ordered typeahead suggestions."
    )


# ---------------------------------------------------------------------------
# Write models (ingestion payloads)
# ---------------------------------------------------------------------------


class RootCauseCreate(BaseModel):
    """Payload for a single root cause when creating an error."""

    description: str = Field(
        ..., min_length=1, max_length=10_000, description="Description of the cause."
    )


class VerifiedFixCreate(BaseModel):
    """Payload for a single verified fix when creating an error."""

    before_code_snippet: str = Field(
        ..., min_length=1, max_length=50_000, description="Code that triggers the error."
    )
    after_code_snippet: str = Field(
        ..., min_length=1, max_length=50_000, description="Corrected code."
    )
    explanation: str = Field(
        ..., min_length=1, max_length=10_000, description="Why the fix works."
    )


class ErrorCreate(BaseModel):
    """Payload for creating an error with its root causes and verified fixes."""

    title: str = Field(
        ..., min_length=1, max_length=512, description="Human-readable error title."
    )
    plain_english_explanation: str = Field(
        ..., min_length=1, description="Plain-English description of the error."
    )
    slug: str | None = Field(
        default=None,
        max_length=255,
        description="Optional explicit slug; generated from the title if omitted.",
    )
    root_causes: list[RootCauseCreate] = Field(
        default_factory=list, description="Common root causes for this error."
    )
    verified_fixes: list[VerifiedFixCreate] = Field(
        default_factory=list, description="Verified fixes with before/after code."
    )


# ---------------------------------------------------------------------------
# Operational models
# ---------------------------------------------------------------------------


class DependencyStatus(BaseModel):
    """Health status of a single downstream dependency."""

    name: str = Field(..., description="Dependency name (e.g. 'database').")
    healthy: bool = Field(..., description="Whether the dependency is reachable.")
    detail: str = Field(..., description="Human-readable status detail.")


class HealthResponse(BaseModel):
    """Aggregate health-check response."""

    status: str = Field(..., description="Overall status: 'ok' or 'degraded'.")
    dependencies: list[DependencyStatus] = Field(
        default_factory=list, description="Per-dependency health details."
    )
