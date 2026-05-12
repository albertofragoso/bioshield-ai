"""Verify security headers are present on all responses."""


async def test_security_headers_on_health(client):
    response = await client.get("/health")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("x-xss-protection") == "0"


async def test_hsts_absent_in_debug_mode(client):
    # TEST_SETTINGS has debug=True — HSTS must NOT be set in dev
    response = await client.get("/health")
    assert "strict-transport-security" not in response.headers


async def test_security_headers_on_401(client):
    response = await client.get("/biosync/status")
    assert response.status_code == 401
    assert response.headers.get("x-content-type-options") == "nosniff"
