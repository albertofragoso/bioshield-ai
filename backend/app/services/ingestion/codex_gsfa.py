"""Codex Alimentarius GSFA scraping.

The GSFA (General Standard for Food Additives) is published as a relational
HTML database at gsfaonline.fao.org. Rate-limited to 1 req / 2 s.
For MVP we accept pre-downloaded HTML / curated records to avoid flakiness.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Iterable

import httpx
from selectolax.parser import HTMLParser
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

SOURCE_NAME = "Codex_GSFA"
BASE_URL = "https://www.fao.org/gsfaonline/additives/results.html"
REQUEST_DELAY_SECONDS = 2.0


def parse_additives_page(html: str) -> list[IngestionRecord]:
    """Extract additive rows from a GSFA results HTML page.

    Expected columns: INS Number, Additive Name, Functional Class, Year Adopted.
    """
    tree = HTMLParser(html)
    records: list[IngestionRecord] = []
    for row in tree.css("table tr"):
        cells = [c.text(strip=True) for c in row.css("td")]
        if len(cells) < 2:
            continue
        ins = cells[0]
        name = cells[1]
        if not name or not ins.isdigit():
            continue
        records.append(
            IngestionRecord(
                canonical_name=name,
                e_number=f"E{ins}" if ins else None,
                status="APPROVED",
                usage_limits=cells[2] if len(cells) > 2 else None,
            )
        )
    return records


async def fetch_pages(client: httpx.AsyncClient, urls: list[str]) -> list[str]:
    """Fetch multiple GSFA pages with polite rate limiting."""
    pages: list[str] = []
    for url in urls:
        response = await client.get(url)
        response.raise_for_status()
        pages.append(response.text)
        await asyncio.sleep(REQUEST_DELAY_SECONDS)
    return pages


async def run(
    db: Session,
    settings: Settings,
    records: Iterable[IngestionRecord] | None = None,
    html_pages: list[str] | None = None,
) -> IngestionLog:
    if records is None:
        if not html_pages:
            async with httpx.AsyncClient(timeout=30) as client:
                html_pages = await fetch_pages(client, [BASE_URL])
        records = []
        for html in html_pages:
            records.extend(parse_additives_page(html))

    records_list = list(records)
    raw = "\n".join(html_pages or []).encode() if html_pages else str(len(records_list)).encode()

    source = get_or_create_source(
        db,
        name=SOURCE_NAME,
        region="GLOBAL",
        version="GSFA_latest",
        source_checksum=checksum(raw),
        license_="IGO",
        format_="HTML",
    )
    log = start_log(db, source, checksum(raw))

    for rec in records_list:
        ing = upsert_ingredient(db, rec)
        upsert_regulatory_status(db, ing, source, rec)
        await index_record(ing, rec, SOURCE_NAME, settings)

    finish_log(log, records_processed=len(records_list), status="SUCCESS")
    db.commit()
    logger.info("Codex GSFA ingested: %d records", len(records_list))
    return log
