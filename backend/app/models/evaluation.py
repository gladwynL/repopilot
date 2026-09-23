import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EvaluationRunRecord(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(50))
    review_config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    total_cases: Mapped[int]
    passed_cases: Mapped[int]
    failed_cases: Mapped[int]
    errored_cases: Mapped[int]
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB)

    cases: Mapped[list["EvaluationCaseResultRecord"]] = relationship(
        back_populates="run",
        order_by="EvaluationCaseResultRecord.position",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class EvaluationCaseResultRecord(Base):
    __tablename__ = "evaluation_case_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    case_id: Mapped[str] = mapped_column(String(100))
    passed: Mapped[bool]
    error: Mapped[str | None] = mapped_column(Text)
    """Sanitized RepoPilot error message; never raw provider output."""
    latency_ms: Mapped[int | None]
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)
    """Case description, per-condition results, and the structured review (if any)."""

    run: Mapped[EvaluationRunRecord] = relationship(back_populates="cases")

    __table_args__ = (
        UniqueConstraint("run_id", "position", name="uq_evaluation_case_results_run_position"),
    )
