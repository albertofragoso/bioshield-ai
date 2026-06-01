"""S5 — PHI Isolation tests (H1, M4).

Red phase: these tests fail until _biomarkers_to_flags and _decode_base64_safe
are added to app.services.gemini.
"""

import base64
import json

import pytest
from fastapi import HTTPException

# ── _biomarkers_to_flags ──────────────────────────────────────────────────────


def test_flags_ldl_elevated():
    from app.services.gemini import _biomarkers_to_flags

    flags = _biomarkers_to_flags({"ldl": 200})
    assert flags == {"ldl_elevated": True}


def test_flags_glucose_normal():
    from app.services.gemini import _biomarkers_to_flags

    flags = _biomarkers_to_flags({"glucose": 90})
    assert flags == {"glucose_normal": True}


def test_flags_hdl_low():
    from app.services.gemini import _biomarkers_to_flags

    flags = _biomarkers_to_flags({"hdl": 30})
    assert flags == {"hdl_low": True}


def test_flags_no_numeric_values():
    from app.services.gemini import _biomarkers_to_flags

    flags = _biomarkers_to_flags({"ldl": 200, "glucose": 90})
    assert all(isinstance(v, bool) for v in flags.values())


def test_no_numeric_in_reconciler_prompt_payload():
    """Flags JSON must not contain raw biomarker values."""
    from app.services.gemini import _biomarkers_to_flags

    biomarkers = {"ldl": 200, "glucose": 95}
    flags_json = json.dumps(_biomarkers_to_flags(biomarkers))
    assert "200" not in flags_json
    assert "95" not in flags_json


def test_unknown_biomarker_flagged_as_present():
    from app.services.gemini import _biomarkers_to_flags

    flags = _biomarkers_to_flags({"mystery_marker": 42.5})
    assert flags == {"mystery_marker_present": True}


# ── _decode_base64_safe ───────────────────────────────────────────────────────


def test_pdf_decoder_valid():
    from app.services.gemini import _decode_base64_safe

    data = base64.b64encode(b"hello pdf").decode()
    assert _decode_base64_safe(data, max_bytes=1024) == b"hello pdf"


def test_pdf_decoder_rejects_oversized():
    from app.services.gemini import _decode_base64_safe

    oversized = base64.b64encode(b"x" * (21 * 1024 * 1024)).decode()
    with pytest.raises(HTTPException) as exc_info:
        _decode_base64_safe(oversized, max_bytes=20 * 1024 * 1024)
    assert exc_info.value.status_code == 413


def test_pdf_decoder_rejects_invalid_base64():
    from app.services.gemini import _decode_base64_safe

    with pytest.raises(HTTPException) as exc_info:
        _decode_base64_safe("not-valid!!!!", max_bytes=1024 * 1024)
    assert exc_info.value.status_code == 400
