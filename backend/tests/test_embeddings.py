"""Tests para app/services/embeddings.py — ruta local BGE-M3.

SentenceTransformer se mockea para evitar descarga de ~500MB en CI.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.config import Settings


def _local_settings(**overrides) -> Settings:
    base = dict(
        debug=True,
        database_url="sqlite:///:memory:",
        jwt_secret="test-jwt-secret-not-for-production",
        aes_key="test-aes-key-32-bytes-xxxxxxxxxx",
        gemini_api_key="test-key",
        chroma_persist_directory="",
        allowed_origins=["http://testserver"],
        use_local_embeddings=True,
        bge_model_name="BAAI/bge-m3",
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture(autouse=True)
def reset_bge_singleton():
    """Resetea el singleton _bge_model entre tests para aislar efectos de carga."""
    import app.services.embeddings as emb

    original = emb._bge_model
    emb._bge_model = None
    yield
    emb._bge_model = original


def _make_mock_model(dim: int = 1024) -> MagicMock:
    mock = MagicMock()
    mock.encode.return_value = np.zeros(dim, dtype=float)
    return mock


# ─────────────────────────────────────────────
# _embed_local_bge
# ─────────────────────────────────────────────


def test_embed_local_bge_returns_list_of_floats():
    settings = _local_settings()
    mock_model = _make_mock_model()

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        from app.services.embeddings import _embed_local_bge

        result = _embed_local_bge("sodium benzoate preservative", settings)

    assert isinstance(result, list)
    assert len(result) == 1024
    assert all(isinstance(x, float) for x in result)


def test_embed_local_bge_singleton_does_not_reload_model():
    """Segunda llamada reutiliza el singleton; SentenceTransformer se instancia una sola vez."""
    settings = _local_settings()
    mock_model = _make_mock_model()

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model) as mock_cls:
        from app.services.embeddings import _embed_local_bge

        _embed_local_bge("first call", settings)
        _embed_local_bge("second call", settings)

    assert mock_cls.call_count == 1


def test_embed_local_bge_propagates_load_error():
    """OSError al cargar el modelo se propaga sin silenciarse."""
    settings = _local_settings()

    with patch("sentence_transformers.SentenceTransformer", side_effect=OSError("model not found")):
        from app.services.embeddings import _embed_local_bge

        with pytest.raises(OSError, match="model not found"):
            _embed_local_bge("test", settings)


# ─────────────────────────────────────────────
# embed_text — ruta local
# ─────────────────────────────────────────────


async def test_embed_text_local_path_returns_vector():
    settings = _local_settings()
    mock_model = _make_mock_model()

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        from app.services import embeddings as emb

        result = await emb.embed_text("trans fat hydrogenated", settings)

    assert isinstance(result, list)
    assert len(result) == 1024


async def test_embed_text_raises_on_empty_string():
    settings = _local_settings()
    from app.services.embeddings import embed_text

    with pytest.raises(ValueError, match="empty"):
        await embed_text("   ", settings)
