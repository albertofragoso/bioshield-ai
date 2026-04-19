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


async def _register(client, email: str = _EMAIL) -> None:
    await client.post(REGISTER_URL, json={"email": email, "password": _PASSWORD})


# ─────────────────────────────────────────────
# POST /biosync/upload
# ─────────────────────────────────────────────

async def test_upload_requires_auth(client):
    response = await client.post(UPLOAD_URL, json={"data": {"glucose": 95}})
    assert response.status_code == 401


async def test_upload_success(client, db_session):
    await _register(client)
    response = await client.post(UPLOAD_URL, json={"data": {"glucose": 95, "ldl": 120}})
    assert response.status_code == 201
    body = response.json()
    assert body["has_data"] is True
    assert "uploaded_at" in body and "expires_at" in body

    # Verify ciphertext persisted (not raw JSON)
    biomarker = db_session.scalar(select(Biomarker))
    assert biomarker is not None
    assert biomarker.encrypted_data is not None
    assert b"glucose" not in biomarker.encrypted_data
    assert len(biomarker.encryption_iv) == 12


async def test_upload_roundtrip_decrypts(client, db_session):
    await _register(client)
    payload = {"glucose": 95, "hba1c": 5.4, "notes": "fasting"}
    await client.post(UPLOAD_URL, json={"data": payload})

    biomarker = db_session.scalar(select(Biomarker))
    decrypted = decrypt_biomarker(
        biomarker.encrypted_data, biomarker.encryption_iv, TEST_SETTINGS.aes_key
    )
    assert decrypted == payload


async def test_upload_replaces_existing(client, db_session):
    await _register(client)
    await client.post(UPLOAD_URL, json={"data": {"glucose": 95}})
    await client.post(UPLOAD_URL, json={"data": {"glucose": 110}})

    biomarkers = db_session.scalars(select(Biomarker)).all()
    assert len(biomarkers) == 1
    decrypted = decrypt_biomarker(
        biomarkers[0].encrypted_data,
        biomarkers[0].encryption_iv,
        TEST_SETTINGS.aes_key,
    )
    assert decrypted == {"glucose": 110}


async def test_upload_empty_data_rejected(client):
    await _register(client)
    response = await client.post(UPLOAD_URL, json={"data": {}})
    assert response.status_code == 422


async def test_upload_sets_180d_expiry(client, db_session):
    await _register(client)
    before = datetime.now(UTC)
    await client.post(UPLOAD_URL, json={"data": {"glucose": 95}})
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
    await client.post(UPLOAD_URL, json={"data": {"glucose": 95}})
    response = await client.get(STATUS_URL)
    assert response.status_code == 200
    body = response.json()
    assert body["has_data"] is True


async def test_status_does_not_leak_decrypted_data(client):
    """GET /biosync/status must not echo back raw biomarker values."""
    await _register(client)
    await client.post(UPLOAD_URL, json={"data": {"glucose": 95, "secret_note": "xyz"}})
    response = await client.get(STATUS_URL)
    assert "glucose" not in response.text
    assert "secret_note" not in response.text
    assert "xyz" not in response.text


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
    await client.post(UPLOAD_URL, json={"data": {"glucose": 95}})
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
    await client.post(UPLOAD_URL, json={"data": {"glucose": 95}})

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
    await client.post(UPLOAD_URL, json={"data": {"glucose": 95}})

    removed = expire_biomarkers(db_session)
    assert removed == 0
    assert db_session.scalar(select(Biomarker)) is not None


# ─────────────────────────────────────────────
# Isolation: user A cannot see user B data
# ─────────────────────────────────────────────

async def test_user_isolation(client, db_session):
    await _register(client, email="alice@bioshield.ai")
    await client.post(UPLOAD_URL, json={"data": {"glucose": 150}})

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
