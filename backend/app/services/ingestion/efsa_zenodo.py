"""EFSA OpenFoodTox ingestion via Zenodo API.

OpenFoodTox is the canonical source for EFSA hazard assessments (NOAEL,
genotoxicity, carcinogenicity). The Zenodo record ID is parameterized via
settings.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Iterable

import httpx
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import IngestionLog
from app.services.ingestion.common import (
    IngestionRecord,
    checksum,
    finish_log,
    get_or_create_source,
    index_record,
    start_log,
    upsert_ingredient,
    upsert_regulatory_status,
)

logger = logging.getLogger(__name__)

SOURCE_NAME = "EFSA_OpenFoodTox"
ZENODO_RECORD_URL = "https://zenodo.org/api/records/8120114"  # current OpenFoodTox release


def parse_records(payload: dict) -> list[IngestionRecord]:
    """Translate OpenFoodTox JSON rows into canonical IngestionRecords.

    The exact schema depends on the Zenodo dataset version; parser looks for
    common fields: name, cas, e_number, conclusion, noael.
    """
    records: list[IngestionRecord] = []
    items = payload.get("data") or payload.get("records") or []
    for row in items:
        name = (row.get("name") or row.get("substance") or "").strip()
        if not name:
            continue
        cas = (row.get("cas") or row.get("cas_number") or "").strip() or None
        e_num = (row.get("e_number") or "").strip() or None
        status = row.get("conclusion") or row.get("status") or "UNDER REVIEW"
        hazard = row.get("hazard") or row.get("notes") or None
        evaluated = row.get("evaluated_at")

        evaluated_dt: datetime | None = None
        if evaluated:
            try:
                evaluated_dt = datetime.fromisoformat(evaluated).replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass

        records.append(
            IngestionRecord(
                canonical_name=name,
                cas_number=cas,
                e_number=e_num,
                status=str(status).upper(),
                hazard_note=hazard,
                evaluated_at=evaluated_dt,
            )
        )
    return records


async def fetch_live(client: httpx.AsyncClient, url: str = ZENODO_RECORD_URL) -> dict:
    response = await client.get(url)
    response.raise_for_status()
    return response.json()


async def run(
    db: Session,
    settings: Settings,
    records: Iterable[IngestionRecord] | None = None,
    payload: dict | None = None,
) -> IngestionLog:
    if records is None:
        if payload is None:
            async with httpx.AsyncClient(timeout=60) as client:
                payload = await fetch_live(client)
        records = parse_records(payload)

    records_list = list(records)
    raw = json.dumps(payload).encode() if payload else str(len(records_list)).encode()

    source = get_or_create_source(
        db,
        name=SOURCE_NAME,
        region="EU",
        version="OpenFoodTox_latest",
        source_checksum=checksum(raw),
        license_="CC BY 4.0",
        format_="JSON",
    )
    log = start_log(db, source, checksum(raw))

    for rec in records_list:
        ing = upsert_ingredient(db, rec)
        upsert_regulatory_status(db, ing, source, rec)
        await index_record(ing, rec, SOURCE_NAME, settings)

    finish_log(log, records_processed=len(records_list), status="SUCCESS")
    db.commit()
    logger.info("EFSA OpenFoodTox ingested: %d records", len(records_list))
    return log
