"""Ingestion pipeline for regulatory data sources.

Each module exposes:
    async def run(db, settings) -> IngestionLog

Orchestrated by scripts/seed_rag.py.
"""
