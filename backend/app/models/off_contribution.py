"""Tabla de auditoría para contribuciones a Open Food Facts (flujo contributivo Fase 2).

Registra el consentimiento explícito del usuario (ODbL) y el resultado de cada envío
al API write de OFF. Permite audit trail sin modificar scan_history.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid4())


class OFFContribution(Base):
    __tablename__ = "off_contributions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    scan_history_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("scan_history.id", ondelete="SET NULL"), nullable=True
    )
    barcode: Mapped[str] = mapped_column(String(50), nullable=False)
    ingredients_text: Mapped[str] = mapped_column(Text, nullable=False)
    image_submitted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    off_response_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    off_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])  # type: ignore[name-defined]

    __table_args__ = (
        Index("idx_off_contrib_user", "user_id"),
        Index("idx_off_contrib_status", "status"),
    )
