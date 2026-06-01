"""Tests for schema hardening — H5, H2, M1, M3.

RED phase: all tests should FAIL before fixes are applied.
"""

import pytest
from pydantic import ValidationError

from app.schemas.models import (
    AnalyticsEventIn,
    LoginRequest,
    OFFContributeRequest,
    PhotoScanRequest,
    RegisterRequest,
)

# ─────────────────────────────────────────────
# H5 — password / email length bounds
# ─────────────────────────────────────────────


def test_register_password_max_length():
    """RegisterRequest rejects passwords longer than 128 chars."""
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@b.com", password="x" * 129)


def test_login_password_max_length():
    """LoginRequest rejects passwords longer than 128 chars."""
    with pytest.raises(ValidationError):
        LoginRequest(email="a@b.com", password="x" * 129)


def test_login_password_min_length():
    """LoginRequest rejects passwords shorter than 8 chars."""
    with pytest.raises(ValidationError):
        LoginRequest(email="a@b.com", password="short")


def test_email_max_length():
    """RegisterRequest rejects emails longer than 254 chars."""
    long_local = "a" * 245
    with pytest.raises(ValidationError):
        RegisterRequest(email=f"{long_local}@b.com", password="valid123")


# ─────────────────────────────────────────────
# H2 — analytics payload DoS guards
# ─────────────────────────────────────────────


def test_analytics_payload_oversized():
    """AnalyticsEventIn rejects payloads whose JSON exceeds 4096 bytes."""
    with pytest.raises(ValidationError):
        AnalyticsEventIn(
            event_type="alt_button_shown",
            payload={"k": "x" * 5000},
        )


def test_analytics_payload_too_many_keys():
    """AnalyticsEventIn rejects payloads with more than 20 keys."""
    with pytest.raises(ValidationError):
        AnalyticsEventIn(
            event_type="alt_button_shown",
            payload={str(i): i for i in range(21)},
        )


def test_analytics_payload_invalid_type():
    """AnalyticsEventIn rejects payloads whose values are not str | int | float | bool."""
    with pytest.raises(ValidationError):
        AnalyticsEventIn(
            event_type="alt_button_shown",
            payload={"bad_key": ["list", "value"]},
        )


# ─────────────────────────────────────────────
# M3 — barcode format
# ─────────────────────────────────────────────


def test_off_barcode_invalid_pattern():
    """OFFContributeRequest rejects non-numeric barcodes."""
    with pytest.raises(ValidationError):
        OFFContributeRequest(
            barcode="ABC123",
            ingredients=["agua"],
            consent=True,
        )


def test_off_barcode_too_short():
    """OFFContributeRequest rejects barcodes shorter than 8 digits."""
    with pytest.raises(ValidationError):
        OFFContributeRequest(
            barcode="123",
            ingredients=["agua"],
            consent=True,
        )


def test_off_barcode_valid():
    """OFFContributeRequest accepts a valid 8-digit numeric barcode."""
    req = OFFContributeRequest(
        barcode="12345678",
        ingredients=["agua"],
        consent=True,
    )
    assert req.barcode == "12345678"


# ─────────────────────────────────────────────
# M1 — input size bounds
# ─────────────────────────────────────────────


def test_image_base64_too_large():
    """PhotoScanRequest rejects image_base64 strings exceeding 5 MB."""
    with pytest.raises(ValidationError):
        PhotoScanRequest(image_base64="A" * 5_242_881)
