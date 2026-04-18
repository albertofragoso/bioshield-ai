"""FDA EAFUS ingestion: parse the FDA 'Everything Added to Food' Excel workbook.

Live URL varies over time; callers may inject `raw_bytes` with a pre-downloaded
.xlsx to keep ingestion deterministic. The parser expects columns:
    'CAS Reg No. (or other ID)', 'Substance', 'Document Number', etc.

For MVP without live download, `scripts/seed_rag.py` uses the curated
fixture at `backend/data/seed/additives.json`.
"""

from __future__ import annotations

import io
import logging
from typing import Iterable

import httpx
from openpyxl import load_workbook
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

SOURCE_NAME = "FDA_EAFUS"
DEFAULT_URL = "https://www.cfsanappsexternal.fda.gov/scripts/fdcc/eafus.xlsx"  # subject to change


def parse_workbook(raw_bytes: bytes) -> list[IngestionRecord]:
    workbook = load_workbook(filename=io.BytesIO(raw_bytes), read_only=True, data_only=True)
    sheet = workbook.active

    headers: list[str] = []
    records: list[IngestionRecord] = []
    for i, row in enumerate(sheet.iter_rows(values_only=True)):
        if i == 0:
            headers = [str(h or "").strip() for h in row]
            continue
        if not row:
            continue
        row_dict = {headers[j]: row[j] for j in range(min(len(headers), len(row)))}
        substance = (row_dict.get("Substance") or row_dict.get("Name") or "").strip()
        cas = (row_dict.get("CAS Reg No. (or other ID)") or row_dict.get("CAS") or "").strip()
        if not substance:
            continue
        records.append(
            IngestionRecord(
                canonical_name=substance,
                cas_number=cas if cas and "-" in cas else None,
                status="APPROVED",  # EAFUS = approved for use in food
                hazard_note=None,
            )
        )
    return records


async def fetch_live_bytes(client: httpx.AsyncClient, url: str = DEFAULT_URL) -> bytes:
    response = await client.get(url)
    response.raise_for_status()
    return response.content


async def run(
    db: Session,
    settings: Settings,
    records: Iterable[IngestionRecord] | None = None,
    raw_bytes: bytes | None = None,
) -> IngestionLog:
    """Ingest FDA EAFUS records into SQL + Chroma.

    - If `records` is provided, use them directly (test path).
    - Else if `raw_bytes` is provided, parse the workbook.
    - Else fetch the live URL (may 404 depending on FDA's schedule).
    """
    if records is None:
        if raw_bytes is None:
            async with httpx.AsyncClient(timeout=60) as client:
                raw_bytes = await fetch_live_bytes(client)
        records = parse_workbook(raw_bytes)

    records_list = list(records)
    source_bytes = raw_bytes or str(len(records_list)).encode()
    source = get_or_create_source(
        db,
        name=SOURCE_NAME,
        region="US",
        version="EAFUS_latest",
        source_checksum=checksum(source_bytes),
        license_="Public Domain",
        format_="XLSX",
    )
    log = start_log(db, source, checksum(source_bytes))

    for rec in records_list:
        ing = upsert_ingredient(db, rec)
        upsert_regulatory_status(db, ing, source, rec)
        await index_record(ing, rec, SOURCE_NAME, settings)

    finish_log(log, records_processed=len(records_list), status="SUCCESS")
    db.commit()
    logger.info("FDA EAFUS ingested: %d records", len(records_list))
    return log
