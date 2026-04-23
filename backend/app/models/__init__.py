"""SQLAlchemy ORM models for BioShield AI.

Compatible with SQLite (dev) and PostgreSQL (prod).
UUID fields use String(36); JSONB uses JSON; BYTEA uses LargeBinary.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.off_contribution import OFFContribution


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid4())


def _expires_at() -> datetime:
    return datetime.now(UTC) + timedelta(days=180)


# ─────────────────────────────────────────────
# users
# ─────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    biomarkers: Mapped[list["Biomarker"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    scan_history: Mapped[list["ScanHistory"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")


# ─────────────────────────────────────────────
# refresh_tokens
# ─────────────────────────────────────────────

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    family_id: Mapped[str] = mapped_column(String(36), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    __table_args__ = (
        Index("idx_refresh_tokens_user", "user_id"),
        Index("idx_refresh_tokens_family", "family_id"),
        Index("idx_refresh_tokens_hash", "token_hash", unique=True),
    )


# ─────────────────────────────────────────────
# products  (new — normalizes scan_history.product_barcode)
# ─────────────────────────────────────────────

class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    barcode: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    brand: Mapped[str | None] = mapped_column(String(255))
    image_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    scans: Mapped[list["ScanHistory"]] = relationship(back_populates="product")

    __table_args__ = (
        Index("idx_products_barcode", "barcode"),
    )


# ─────────────────────────────────────────────
# biomarkers
# ─────────────────────────────────────────────

class Biomarker(Base):
    __tablename__ = "biomarkers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    encrypted_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encryption_iv: Mapped[bytes] = mapped_column(LargeBinary(16), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_expires_at, nullable=False)

    user: Mapped["User"] = relationship(back_populates="biomarkers")

    __table_args__ = (
        Index("idx_biomarkers_user", "user_id"),
    )


# ─────────────────────────────────────────────
# scan_history
# ─────────────────────────────────────────────

class ScanHistory(Base):
    __tablename__ = "scan_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_barcode: Mapped[str] = mapped_column(String(50), ForeignKey("products.barcode"), nullable=False)
    ingredient_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ingredients.id"))
    semaphore_result: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    conflict_severity: Mapped[str | None] = mapped_column(String(10))
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped["User"] = relationship(back_populates="scan_history")
    product: Mapped["Product"] = relationship(back_populates="scans")
    ingredient: Mapped["Ingredient | None"] = relationship(back_populates="scans")

    __table_args__ = (
        CheckConstraint("confidence_score >= 0.0 AND confidence_score <= 1.0", name="ck_scan_confidence"),
        Index("idx_scan_history_user", "user_id"),
        Index("idx_scan_history_barcode", "product_barcode"),
    )


# ─────────────────────────────────────────────
# data_sources
# ─────────────────────────────────────────────

class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    region: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[str | None] = mapped_column(String(50))
    source_checksum: Mapped[str | None] = mapped_column(String(71))
    license: Mapped[str | None] = mapped_column(String(50))
    format: Mapped[str | None] = mapped_column(String(20))
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    regulatory_statuses: Mapped[list["RegulatoryStatus"]] = relationship(back_populates="source")
    ingestion_logs: Mapped[list["IngestionLog"]] = relationship(back_populates="source", cascade="all, delete-orphan")


# ─────────────────────────────────────────────
# ingredients
# ─────────────────────────────────────────────

class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cas_number: Mapped[str | None] = mapped_column(String(20), unique=True)
    e_number: Mapped[str | None] = mapped_column(String(10))
    synonyms: Mapped[list] = mapped_column(JSON, default=list)
    entity_id: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    regulatory_statuses: Mapped[list["RegulatoryStatus"]] = relationship(back_populates="ingredient", cascade="all, delete-orphan")
    conflicts: Mapped[list["Conflict"]] = relationship(back_populates="ingredient", cascade="all, delete-orphan")
    scans: Mapped[list["ScanHistory"]] = relationship(back_populates="ingredient")

    __table_args__ = (
        Index("idx_ingredients_cas", "cas_number"),
        Index("idx_ingredients_e_number", "e_number"),
        Index("idx_ingredients_entity_id", "entity_id"),
    )


# ─────────────────────────────────────────────
# regulatory_status
# ─────────────────────────────────────────────

class RegulatoryStatus(Base):
    __tablename__ = "regulatory_status"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ingredient_id: Mapped[str] = mapped_column(String(36), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    usage_limits: Mapped[str | None] = mapped_column(String(255))
    hazard_note: Mapped[str | None] = mapped_column(Text)
    data_version: Mapped[str | None] = mapped_column(String(50))
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    ingredient: Mapped["Ingredient"] = relationship(back_populates="regulatory_statuses")
    source: Mapped["DataSource"] = relationship(back_populates="regulatory_statuses")

    __table_args__ = (
        UniqueConstraint("ingredient_id", "source_id", name="uq_reg_status_ingredient_source"),
        Index("idx_reg_status_ingredient", "ingredient_id"),
        Index("idx_reg_status_source", "source_id"),
    )


# ─────────────────────────────────────────────
# conflicts
# ─────────────────────────────────────────────

class Conflict(Base):
    __tablename__ = "conflicts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ingredient_id: Mapped[str] = mapped_column(String(36), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)
    conflict_type: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)

    ingredient: Mapped["Ingredient"] = relationship(back_populates="conflicts")

    __table_args__ = (
        Index("idx_conflicts_ingredient", "ingredient_id"),
        Index("idx_conflicts_unresolved", "resolved"),
    )


# ─────────────────────────────────────────────
# ingestion_log
# ─────────────────────────────────────────────

class IngestionLog(Base):
    __tablename__ = "ingestion_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    ingestion_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(71), nullable=False)
    data_version: Mapped[str] = mapped_column(String(50), nullable=False)
    records_processed: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source: Mapped["DataSource"] = relationship(back_populates="ingestion_logs")

    __table_args__ = (
        Index("idx_ingestion_source", "source_id"),
    )


__all__ = [
    "Base",
    "Biomarker",
    "Conflict",
    "DataSource",
    "Ingredient",
    "IngestionLog",
    "OFFContribution",
    "Product",
    "RefreshToken",
    "RegulatoryStatus",
    "ScanHistory",
    "User",
]
