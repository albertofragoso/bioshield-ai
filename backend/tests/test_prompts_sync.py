"""Ensures backend/app/agents/prompts.py mirrors docs/prompts.md verbatim.

If this test fails: edit both files to match — they are tied source-of-truth.
"""

import re
from pathlib import Path

from app.agents.prompts import (
    EXTRACTOR_PROMPT,
    OCR_CORRECTION_PROMPT,
    RECONCILER_PROMPT,
)

_DOCS_PROMPTS = (
    Path(__file__).resolve().parents[2] / "docs" / "prompts.md"
)


def _extract_fenced_block(markdown: str, after_heading: str) -> str:
    """Return the first fenced code block after the given ## heading."""
    # Split on the heading, take what's after
    parts = markdown.split(f"## {after_heading}", 1)
    if len(parts) < 2:
        raise AssertionError(f"Heading '## {after_heading}' not found")
    tail = parts[1]
    match = re.search(r"```\n(.*?)\n```", tail, re.DOTALL)
    if not match:
        raise AssertionError(f"No fenced block under '## {after_heading}'")
    return match.group(1)


def test_extractor_prompt_matches_docs():
    md = _DOCS_PROMPTS.read_text(encoding="utf-8")
    assert _extract_fenced_block(md, "EXTRACTOR_PROMPT") == EXTRACTOR_PROMPT


def test_reconciler_prompt_matches_docs():
    md = _DOCS_PROMPTS.read_text(encoding="utf-8")
    assert _extract_fenced_block(md, "RECONCILER_PROMPT") == RECONCILER_PROMPT


def test_ocr_correction_prompt_matches_docs():
    md = _DOCS_PROMPTS.read_text(encoding="utf-8")
    assert _extract_fenced_block(md, "OCR_CORRECTION_PROMPT") == OCR_CORRECTION_PROMPT
