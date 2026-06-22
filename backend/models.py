"""SQLAlchemy ORM models for the Error Encyclopedia core domain.

Relationships (one-to-many in both cases)::

    Error (1) ──< (N) RootCause
    Error (1) ──< (N) VerifiedFix

Deletes cascade at the ORM level (``cascade="all, delete-orphan"``) and at the
database level (``ondelete="CASCADE"`` + ``passive_deletes=True``), so removing
an ``Error`` always removes its dependent rows — whether the delete is issued
through the ORM or directly in SQL.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Error(Base):
    """A single software error indexed by the encyclopedia.

    ``slug`` is the canonical, URL-safe identifier used for SEO routes such as
    ``/error/modulenotfounderror``. It is unique and indexed for fast lookups.
    """

    __tablename__ = "errors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    plain_english_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    root_causes: Mapped[list["RootCause"]] = relationship(
        back_populates="error",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RootCause.id",
        lazy="selectin",
    )
    verified_fixes: Mapped[list["VerifiedFix"]] = relationship(
        back_populates="error",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="VerifiedFix.id",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_errors_created_at", "created_at"),)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Error id={self.id} slug={self.slug!r}>"


class RootCause(Base):
    """A common root cause for a given :class:`Error` (many per error)."""

    __tablename__ = "root_causes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    error_id: Mapped[int] = mapped_column(
        ForeignKey("errors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)

    error: Mapped["Error"] = relationship(back_populates="root_causes")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<RootCause id={self.id} error_id={self.error_id}>"


class VerifiedFix(Base):
    """A verified fix for an :class:`Error`, with before/after code (many per error)."""

    __tablename__ = "verified_fixes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    error_id: Mapped[int] = mapped_column(
        ForeignKey("errors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    before_code_snippet: Mapped[str] = mapped_column(Text, nullable=False)
    after_code_snippet: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    error: Mapped["Error"] = relationship(back_populates="verified_fixes")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<VerifiedFix id={self.id} error_id={self.error_id}>"
