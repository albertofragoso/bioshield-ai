"""Tests del endpoint público /waitlist.

Cubre: signup exitoso, idempotencia (email duplicado → 409),
consent requerido (→ 422), email inválido (→ 422),
conteo GET /waitlist/count, consent_text almacenado.
"""

from sqlalchemy import text

VALID_PAYLOAD = {
    "email": "waitlist@test.com",
    "name": "Test User",
    "source": "linkedin",
    "signup_intent": "salud_personal",
    "consent": True,
    "turnstile_token": "dev-bypass",
}


async def test_signup_returns_201(client):
    """Signup exitoso devuelve 201 con position y total >= 1."""
    resp = await client.post("/waitlist", json=VALID_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert "position" in body
    assert "total" in body
    assert body["total"] >= 1


async def test_signup_idempotent_uppercase_email(client, db_session):
    """Mismo email en uppercase → 409 en el segundo intento.

    La migración crea el índice UNIQUE funcional vía op.execute() (LOWER(email)),
    que Base.metadata.create_all() no ejecuta. Este test recrea ese índice en la
    sesión de test antes de verificar idempotencia.
    """
    # Recrear el índice UNIQUE funcional que existe en producción vía Alembic
    db_session.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS waitlist_signups_email_lower_test_idx "
            "ON waitlist_signups (LOWER(email))"
        )
    )
    db_session.flush()

    email = "idempotent@test.com"
    resp1 = await client.post("/waitlist", json={**VALID_PAYLOAD, "email": email})
    assert resp1.status_code == 201

    # Segundo intento con uppercase — normaliza a lowercase, colisiona con el UNIQUE
    resp2 = await client.post("/waitlist", json={**VALID_PAYLOAD, "email": email.upper()})
    assert resp2.status_code == 409
    assert resp2.json()["detail"]["error"] == "already_registered"


async def test_signup_requires_consent(client):
    """consent: false → 422."""
    payload = {**VALID_PAYLOAD, "email": "noconsent@test.com", "consent": False}
    resp = await client.post("/waitlist", json=payload)
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "consent_required"


async def test_signup_rejects_invalid_email(client):
    """Email inválido → 422 de Pydantic."""
    payload = {**VALID_PAYLOAD, "email": "not-an-email"}
    resp = await client.post("/waitlist", json=payload)
    assert resp.status_code == 422


async def test_count_endpoint(client):
    """GET /waitlist/count devuelve total como int >= 0."""
    await client.post("/waitlist", json={**VALID_PAYLOAD, "email": "count@test.com"})
    resp = await client.get("/waitlist/count")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["total"], int)
    assert body["total"] >= 1


async def test_signup_stores_consent_text(client, db_session):
    """El consent_text almacenado contiene referencia a LFPDPPP."""
    email = "consentcheck@test.com"
    await client.post("/waitlist", json={**VALID_PAYLOAD, "email": email})
    row = db_session.execute(
        text("SELECT consent_text FROM waitlist_signups WHERE email = :email"),
        {"email": email},
    ).fetchone()
    assert row is not None
    assert "LFPDPPP" in row[0]
