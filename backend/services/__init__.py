"""Service-layer package: search orchestration and related business logic."""

from services.search_service import (
    SearchUnavailable,
    autocomplete_errors,
    related_errors,
    search_errors,
)

__all__ = [
    "SearchUnavailable",
    "autocomplete_errors",
    "related_errors",
    "search_errors",
]
