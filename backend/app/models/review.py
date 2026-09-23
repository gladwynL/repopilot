import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

SEVERITIES_SQL = "'low', 'medium', 'high', 'critical'"


class ReviewRecord(Base):
    """A completed review. Rows are immutable except for ``is_current``."""

    __tablename__ = "reviews"
    # Fetch created_at via RETURNING on insert instead of a follow-up SELECT.
    __mapper_args__: ClassVar[dict[str, Any]] = {"eager_defaults": True}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cache_key: Mapped[str] = mapped_column(String(64))
    is_current: Mapped[bool]
    """True for the one review per ``cache_key`` that cache lookups return."""

    owner: Mapped[str] = mapped_column(String(100))
    repo: Mapped[str] = mapped_column(String(100))
    pull_number: Mapped[int]
    head_sha: Mapped[str] = mapped_column(String(64))

    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(50))
    review_config: Mapped[dict[str, Any]] = mapped_column(JSONB)

    summary: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str | None] = mapped_column(String(16))
    finding_count: Mapped[int]
    reviewed_files: Mapped[list[str]] = mapped_column(JSONB)
    truncated_files: Mapped[list[str]] = mapped_column(JSONB)
    skipped_files: Mapped[list[dict[str, str]]] = mapped_column(JSONB)
    limitations: Mapped[list[str]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    findings: Mapped[list["ReviewFindingRecord"]] = relationship(
        back_populates="review",
        order_by="ReviewFindingRecord.position",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    test_suggestions: Mapped[list["ReviewTestSuggestionRecord"]] = relationship(
        back_populates="review",
        order_by="ReviewTestSuggestionRecord.position",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(f"risk_level IN ({SEVERITIES_SQL})", name="risk_level"),
        CheckConstraint("pull_number > 0", name="pull_number_positive"),
        # At most one reusable review per identity, enforced by the database.
        Index(
            "uq_reviews_current_cache_key",
            "cache_key",
            unique=True,
            postgresql_where=text("is_current"),
        ),
        # History filtered by repository/PR (case-insensitive), newest first.
        Index(
            "ix_reviews_repo_pull_created",
            func.lower(text("owner")),
            func.lower(text("repo")),
            "pull_number",
            text("created_at DESC"),
        ),
        Index("ix_reviews_created_at", text("created_at DESC")),
    )


class ReviewFindingRecord(Base):
    __tablename__ = "review_findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    category: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float]
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[str] = mapped_column(Text)
    file: Mapped[str | None] = mapped_column(Text)
    line_start: Mapped[int | None]
    line_end: Mapped[int | None]

    review: Mapped[ReviewRecord] = relationship(back_populates="findings")

    __table_args__ = (
        UniqueConstraint("review_id", "position", name="uq_review_findings_review_position"),
        CheckConstraint(f"severity IN ({SEVERITIES_SQL})", name="severity"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
    )


class ReviewTestSuggestionRecord(Base):
    __tablename__ = "review_test_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    description: Mapped[str] = mapped_column(Text)
    file: Mapped[str | None] = mapped_column(Text)

    review: Mapped[ReviewRecord] = relationship(back_populates="test_suggestions")

    __table_args__ = (
        UniqueConstraint(
            "review_id", "position", name="uq_review_test_suggestions_review_position"
        ),
    )
