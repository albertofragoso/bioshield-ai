from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient

from app.main import app
from app.models.base import get_db


@pytest.mark.asyncio
async def test_health_returns_db_status(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert "app" in body


@pytest.mark.asyncio
async def test_health_no_auth_required(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_returns_degraded_on_db_failure(client: AsyncClient):
    def broken_db():
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("DB connection failed")
        yield mock_db

    app.dependency_overrides[get_db] = broken_db
    try:
        response = await client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["db"] == "error"
    finally:
        app.dependency_overrides.pop(get_db, None)
