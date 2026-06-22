"""Async repository functions for the Error Encyclopedia core domain.

Every function takes an :class:`~sqlalchemy.ext.asyncio.AsyncSession` and uses
fully asynchronous SQLAlchemy access. Slug generation is deterministic and
collision-safe: a title is normalized to a URL-safe base slug and, if that slug
already exists, a numeric suffix is appended until a free slug is found.
"""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Error, RootCause, VerifiedFix
from schemas import ErrorCreate

# Characters kept verbatim are [a-z0-9]; everything else collapses to a hyphen.
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_MAX_SLUG_LENGTH = 255


def slugify(value: str) -> str:
    """Normalize an arbitrary string into a lowercase, hyphenated slug.

    Strips non-alphanumeric characters, collapses runs of separators into a
    single hyphen, and trims leading/trailing hyphens. Falls back to ``"error"``
    when the input has no usable characters.
    """
    lowered = value.strip().lower()
    slug = _NON_ALNUM.sub("-", lowered).strip("-")
    slug = slug[:_MAX_SLUG_LENGTH].strip("-")
    return slug or "error"


async def slug_exists(session: AsyncSession, slug: str) -> bool:
    """Return ``True`` if an error with the given slug already exists."""
    result = await session.execute(
        select(func.count()).select_from(Error).where(Error.slug == slug)
    )
    return (result.scalar_one() or 0) > 0


async def _unique_slug(session: AsyncSession, base_slug: str) -> str:
    """Return ``base_slug`` or the first ``base_slug-N`` variant that is free."""
    if not await slug_exists(session, base_slug):
        return base_slug
    suffix = 2
    while True:
        # Reserve room for the numeric suffix within the column length budget.
        candidate_base = base_slug[: _MAX_SLUG_LENGTH - len(f"-{suffix}")]
        candidate = f"{candidate_base.rstrip('-')}-{suffix}"
        if not await slug_exists(session, candidate):
            return candidate
        suffix += 1


async def get_error_by_slug(session: AsyncSession, slug: str) -> Error | None:
    """Return the error matching ``slug`` (relationships eager-loaded), or ``None``.

    ``root_causes`` and ``verified_fixes`` use ``lazy="selectin"`` on the model,
    so a plain ``select`` already eager-loads them in a follow-up query.
    """
    result = await session.execute(select(Error).where(Error.slug == slug))
    return result.scalar_one_or_none()


async def list_errors(
    session: AsyncSession, limit: int = 50, offset: int = 0
) -> list[Error]:
    """Return a page of errors ordered by most-recently-created first."""
    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)
    result = await session.execute(
        select(Error)
        .order_by(Error.created_at.desc(), Error.id.desc())
        .limit(safe_limit)
        .offset(safe_offset)
    )
    return list(result.scalars().all())


async def create_error(session: AsyncSession, payload: ErrorCreate) -> Error:
    """Create an error with its root causes and verified fixes.

    The slug is taken from ``payload.slug`` when provided (normalized) or derived
    from the title, and is always made unique. The new ``Error`` is flushed and
    refreshed so the caller receives a fully-populated object (id, created_at,
    and eager-loaded relationships) without committing — the request-scoped
    ``get_db`` dependency owns the commit.
    """
    base_slug = slugify(payload.slug) if payload.slug else slugify(payload.title)
    slug = await _unique_slug(session, base_slug)

    error = Error(
        slug=slug,
        title=payload.title,
        plain_english_explanation=payload.plain_english_explanation,
        root_causes=[
            RootCause(description=rc.description) for rc in payload.root_causes
        ],
        verified_fixes=[
            VerifiedFix(
                before_code_snippet=fix.before_code_snippet,
                after_code_snippet=fix.after_code_snippet,
                explanation=fix.explanation,
            )
            for fix in payload.verified_fixes
        ],
    )
    session.add(error)
    await session.flush()
    # Re-load through the ORM so created_at (server default) and the selectin
    # relationships are populated on the returned instance.
    await session.refresh(error)
    return error
