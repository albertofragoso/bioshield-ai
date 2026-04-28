"""Shared helpers for ingestion modules."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import (
    DataSource,
    IngestionLog,
    Ingredient,
    RegulatoryStatus,
)
from app.services.embeddings import embed_text
from app.services.rag import build_embedding_template, get_collection, upsert_record

logger = logging.getLogger(__name__)


@dataclass
class IngestionRecord:
    """Canonical in-memory form before persisting to DB + Chroma."""

    canonical_name: str
    cas_number: str | None = None
    e_number: str | None = None
    synonyms: list[str] = field(default_factory=list)
    status: str = "APPROVED"
    usage_limits: str | None = None
    hazard_note: str | None = None
    evaluated_at: datetime | None = None

    @property
    def entity_id(self) -> str:
        if self.cas_number:
            return f"CAS:{self.cas_number}"
        if self.e_number:
            return f"E:{self.e_number}"
        return f"NAME:{self.canonical_name.lower().replace(' ', '_')}"


def checksum(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def get_or_create_source(
    db: Session,
    name: str,
    region: str,
    version: str,
    source_checksum: str,
    license_: str,
    format_: str,
) -> DataSource:
    source = db.scalar(select(DataSource).where(DataSource.name == name))
    if not source:
        source = DataSource(
            name=name,
            region=region,
            version=version,
            source_checksum=source_checksum,
            license=license_,
            format=format_,
            last_ingested_at=datetime.now(UTC),
        )
        db.add(source)
        db.flush()
    else:
        source.version = version
        source.source_checksum = source_checksum
        source.last_ingested_at = datetime.now(UTC)
    return source


def upsert_ingredient(db: Session, record: IngestionRecord) -> Ingredient:
    """Upsert ingredient by (CAS, E-number, or canonical name)."""
    ing: Ingredient | None = None
    if record.cas_number:
        ing = db.scalar(select(Ingredient).where(Ingredient.cas_number == record.cas_number))
    if ing is None and record.e_number:
        ing = db.scalar(select(Ingredient).where(Ingredient.e_number == record.e_number))
    if ing is None:
        ing = db.scalar(
            select(Ingredient).where(Ingredient.canonical_name == record.canonical_name)
        )

    if ing is None:
        ing = Ingredient(
            canonical_name=record.canonical_name,
            cas_number=record.cas_number,
            e_number=record.e_number,
            synonyms=record.synonyms,
            entity_id=record.entity_id,
        )
        db.add(ing)
        db.flush()
    else:
        ing.canonical_name = record.canonical_name
        ing.e_number = record.e_number or ing.e_number
        merged = set(ing.synonyms or []) | set(record.synonyms or [])
        ing.synonyms = sorted(merged)
        ing.entity_id = ing.entity_id or record.entity_id
    return ing


def upsert_regulatory_status(
    db: Session, ingredient: Ingredient, source: DataSource, record: IngestionRecord
) -> RegulatoryStatus:
    existing = db.scalar(
        select(RegulatoryStatus).where(
            RegulatoryStatus.ingredient_id == ingredient.id,
            RegulatoryStatus.source_id == source.id,
        )
    )
    if existing:
        existing.status = record.status
        existing.usage_limits = record.usage_limits
        existing.hazard_note = record.hazard_note
        existing.data_version = source.version
        existing.evaluated_at = record.evaluated_at
        return existing

    status = RegulatoryStatus(
        ingredient_id=ingredient.id,
        source_id=source.id,
        status=record.status,
        usage_limits=record.usage_limits,
        hazard_note=record.hazard_note,
        data_version=source.version,
        evaluated_at=record.evaluated_at,
    )
    db.add(status)
    db.flush()
    return status


async def index_record(
    ingredient: Ingredient, record: IngestionRecord, source_name: str, settings: Settings
) -> None:
    """Upsert embedding + metadata into ChromaDB.

    Embedding failures (quota exhaustion, API outage) are non-fatal: the SQL
    upsert already persisted the record, so BM25 retrieval still works. Chroma
    will be back-filled on the next successful seed run.
    """
    template = build_embedding_template(
        entity_id=ingredient.entity_id or record.entity_id,
        canonical_name=ingredient.canonical_name,
        hazard_note=record.hazard_note,
        usage_limits=record.usage_limits,
    )
    # Skip embedding in tests (no API key AND local model disabled).
    # When use_local_embeddings=True, no Gemini key is needed — allow through.
    if not settings.use_local_embeddings and (
        not settings.gemini_api_key or settings.gemini_api_key == "test-key"
    ):
        return
    try:
        embedding = await embed_text(template, settings)
    except (RuntimeError, Exception) as exc:
        logger.warning(
            "Chroma indexing skipped for %s (%s): %s — BM25 still available",
            ingredient.canonical_name,
            source_name,
            exc,
        )
        return
    collection = get_collection(settings)
    metadata: dict[str, Any] = {
        "entity_id": ingredient.entity_id or record.entity_id,
        "canonical_name": ingredient.canonical_name,
        "cas_number": record.cas_number or "",
        "e_number": record.e_number or "",
        "source": source_name,
        "status": record.status,
    }
    upsert_record(
        collection=collection,
        entity_id=ingredient.entity_id or record.entity_id,
        template_text=template,
        embedding=embedding,
        metadata=metadata,
    )


def start_log(db: Session, source: DataSource, source_checksum: str) -> IngestionLog:
    log = IngestionLog(
        source_id=source.id,
        ingestion_id=f"ingest_{source.name}_{datetime.now(UTC).timestamp():.0f}",
        source_checksum=source_checksum,
        data_version=source.version or "unknown",
        status="RUNNING",
        started_at=datetime.now(UTC),
    )
    db.add(log)
    db.flush()
    return log


def finish_log(log: IngestionLog, records_processed: int, status: str = "SUCCESS") -> None:
    log.records_processed = records_processed
    log.status = status
    log.completed_at = datetime.now(UTC)
