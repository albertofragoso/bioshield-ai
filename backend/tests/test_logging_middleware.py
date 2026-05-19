from app.core.context import REQUEST_ID_VAR


def test_request_id_var_default_is_none():
    assert REQUEST_ID_VAR.get() is None


def test_request_id_var_set_and_get():
    token = REQUEST_ID_VAR.set("abc-123")
    assert REQUEST_ID_VAR.get() == "abc-123"
    REQUEST_ID_VAR.reset(token)
    assert REQUEST_ID_VAR.get() is None


from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_response_has_request_id_header():
    response = client.get("/health")
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) == 36  # uuid4


def test_request_id_is_unique_per_request():
    r1 = client.get("/health")
    r2 = client.get("/health")
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]
