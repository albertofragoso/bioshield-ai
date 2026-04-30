"""Tests for /biosync endpoints + TTL maintenance job."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import Biomarker, User
from app.services.crypto import decrypt_biomarker
from app.services.maintenance import expire_biomarkers
from tests.conftest import TEST_SETTINGS

REGISTER_URL = "/auth/register"
UPLOAD_URL = "/biosync/upload"
STATUS_URL = "/biosync/status"
DELETE_URL = "/biosync/data"

_EMAIL = "biosync@bioshield.ai"
_PASSWORD = "securepassword123"


def _biomarker(
    name: str = "glucose",
    raw_name: str = "Glucosa en ayuno",
    value: float = 95.0,
    unit: str = "mg/dL",
    classification: str = "normal",
) -> dict:
    return {
        "name": name,
        "raw_name": raw_name,
        "value": value,
        "unit": unit,
        "unit_normalized": True,
        "reference_range_low": 70.0,
        "reference_range_high": 99.0,
        "reference_source": "canonical",
        "classification": classification,
    }


def _upload_body(biomarkers: list[dict] | None = None) -> dict:
    return {
        "biomarkers": biomarkers if biomarkers is not None else [_biomarker()],
        "lab_name": None,
        "test_date": None,
    }


async def _register(client, email: str = _EMAIL) -> None:
    await client.post(REGISTER_URL, json={"email": email, "password": _PASSWORD})


# ─────────────────────────────────────────────
# POST /biosync/upload
# ─────────────────────────────────────────────


async def test_upload_requires_auth(client):
    response = await client.post(UPLOAD_URL, json=_upload_body())
    assert response.status_code == 401


async def test_upload_success(client, db_session):
    await _register(client)
    body = _upload_body(
        [
            _biomarker("glucose", value=95),
            _biomarker("ldl", "Colesterol LDL", 120, classification="high"),
        ]
    )
    response = await client.post(UPLOAD_URL, json=body)
    assert response.status_code == 201
    resp_body = response.json()
    assert resp_body["has_data"] is True
    assert "uploaded_at" in resp_body and "expires_at" in resp_body

    # Verify ciphertext persisted (not raw JSON)
    biomarker = db_session.scalar(select(Biomarker))
    assert biomarker is not None
    assert biomarker.encrypted_data is not None
    assert b"glucose" not in biomarker.encrypted_data
    assert len(biomarker.encryption_iv) == 12


async def test_upload_roundtrip_decrypts(client, db_session):
    await _register(client)
    bm_glucose = _biomarker("glucose", "Glucosa en ayuno", 95.0)
    bm_ldl = _biomarker("ldl", "Colesterol LDL", 110.0, classification="high")
    body = _upload_body([bm_glucose, bm_ldl])
    await client.post(UPLOAD_URL, json=body)

    biomarker = db_session.scalar(select(Biomarker))
    decrypted = decrypt_biomarker(
        biomarker.encrypted_data, biomarker.encryption_iv, TEST_SETTINGS.aes_key
    )
    # The decrypted payload mirrors the BiomarkerUploadRequest dict
    assert "biomarkers" in decrypted
    assert len(decrypted["biomarkers"]) == 2
    names = {b["name"] for b in decrypted["biomarkers"]}
    assert names == {"glucose", "ldl"}


async def test_upload_replaces_existing(client, db_session):
    await _register(client)
    await client.post(UPLOAD_URL, json=_upload_body([_biomarker("glucose", value=95)]))
    await client.post(
        UPLOAD_URL, json=_upload_body([_biomarker("glucose", value=110, classification="high")])
    )

    biomarkers = db_session.scalars(select(Biomarker)).all()
    assert len(biomarkers) == 1
    decrypted = decrypt_biomarker(
        biomarkers[0].encrypted_data,
        biomarkers[0].encryption_iv,
        TEST_SETTINGS.aes_key,
    )
    assert decrypted["biomarkers"][0]["value"] == 110.0


async def test_upload_empty_biomarkers_rejected(client):
    await _register(client)
    response = await client.post(UPLOAD_URL, json=_upload_body([]))
    assert response.status_code == 422


async def test_upload_sets_180d_expiry(client, db_session):
    await _register(client)
    before = datetime.now(UTC)
    await client.post(UPLOAD_URL, json=_upload_body())
    after = datetime.now(UTC)

    biomarker = db_session.scalar(select(Biomarker))
    # SQLite strips tzinfo on round-trip; re-attach UTC for comparison
    uploaded = biomarker.uploaded_at.replace(tzinfo=UTC)
    expires = biomarker.expires_at.replace(tzinfo=UTC)
    delta = expires - uploaded
    assert timedelta(days=180) - timedelta(seconds=2) <= delta <= timedelta(days=180)
    assert before <= uploaded <= after


# ─────────────────────────────────────────────
# GET /biosync/status
# ─────────────────────────────────────────────


async def test_status_requires_auth(client):
    response = await client.get(STATUS_URL)
    assert response.status_code == 401


async def test_status_404_when_no_data(client):
    await _register(client)
    response = await client.get(STATUS_URL)
    assert response.status_code == 404


async def test_status_after_upload(client):
    await _register(client)
    await client.post(UPLOAD_URL, json=_upload_body())
    response = await client.get(STATUS_URL)
    assert response.status_code == 200
    body = response.json()
    assert body["has_data"] is True


async def test_status_does_not_leak_decrypted_data(client):
    """GET /biosync/status must not echo back raw biomarker values."""
    await _register(client)
    await client.post(UPLOAD_URL, json=_upload_body([_biomarker("glucose", value=95)]))
    response = await client.get(STATUS_URL)
    body = response.json()
    assert set(body.keys()) == {"id", "uploaded_at", "expires_at", "has_data"}
    assert "glucose" not in response.text
    assert "value" not in response.text


# ─────────────────────────────────────────────
# DELETE /biosync/data
# ─────────────────────────────────────────────


async def test_delete_requires_auth(client):
    response = await client.delete(DELETE_URL)
    assert response.status_code == 401


async def test_delete_404_when_no_data(client):
    await _register(client)
    response = await client.delete(DELETE_URL)
    assert response.status_code == 404


async def test_delete_removes_data(client, db_session):
    await _register(client)
    await client.post(UPLOAD_URL, json=_upload_body())
    response = await client.delete(DELETE_URL)
    assert response.status_code == 204

    status_response = await client.get(STATUS_URL)
    assert status_response.status_code == 404
    assert db_session.scalar(select(Biomarker)) is None


# ─────────────────────────────────────────────
# TTL maintenance job
# ─────────────────────────────────────────────


async def test_expire_biomarkers_removes_past_due(client, db_session):
    await _register(client)
    await client.post(UPLOAD_URL, json=_upload_body())

    biomarker = db_session.scalar(select(Biomarker))
    assert biomarker is not None

    # Force expiration into the past
    biomarker.expires_at = datetime.now(UTC) - timedelta(days=1)
    db_session.commit()

    removed = expire_biomarkers(db_session)
    assert removed == 1
    assert db_session.scalar(select(Biomarker)) is None


async def test_expire_biomarkers_keeps_active(client, db_session):
    await _register(client)
    await client.post(UPLOAD_URL, json=_upload_body())

    removed = expire_biomarkers(db_session)
    assert removed == 0
    assert db_session.scalar(select(Biomarker)) is not None


# ─────────────────────────────────────────────
# Isolation: user A cannot see user B data
# ─────────────────────────────────────────────


async def test_user_isolation(client, db_session):
    await _register(client, email="alice@bioshield.ai")
    await client.post(
        UPLOAD_URL, json=_upload_body([_biomarker("glucose", value=150, classification="high")])
    )

    # Log out (delete client cookies) and register bob
    client.cookies.clear()
    await _register(client, email="bob@bioshield.ai")

    # Bob must not see Alice's biomarker
    response = await client.get(STATUS_URL)
    assert response.status_code == 404

    # DB still has exactly one row (Alice's)
    biomarkers = db_session.scalars(select(Biomarker)).all()
    assert len(biomarkers) == 1

    alice = db_session.scalar(select(User).where(User.email == "alice@bioshield.ai"))
    assert biomarkers[0].user_id == alice.id
