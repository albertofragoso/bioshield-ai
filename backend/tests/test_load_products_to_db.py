"""Tests for the DB load script.

Uses in-memory SQLite — no file I/O, no network.
"""

import json

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.models import Product
from app.models.base import Base


@pytest.fixture()
def mem_db():
    """Fresh in-memory SQLite with full schema."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _write_input(tmp_path, products: list[dict]) -> object:
    path = tmp_path / "off_products.json"
    path.write_text(json.dumps(products))
    return path


def _run_load(mem_db, tmp_path, products):
    from unittest.mock import patch

    import scripts.load_products_to_db as loader

    path = _write_input(tmp_path, products)
    with (
        patch.object(loader, "INPUT_PATH", path),
        patch.object(loader, "SessionLocal", lambda: mem_db),
    ):
        loader.main()


_PRODUCT = {
    "barcode": "1234567890123",
    "name": "Avena Quaker",
    "brand": "Quaker",
    "category": "breakfast-cereals",
    "image_url": None,
    "ingredients_json": ["Avena integral", "Sal"],
    "ingredients_source": "off_dump_mx",
}


def test_inserts_new_product(mem_db, tmp_path):
    _run_load(mem_db, tmp_path, [_PRODUCT])
    result = mem_db.scalar(select(Product).where(Product.barcode == "1234567890123"))
    assert result is not None
    assert result.name == "Avena Quaker"
    assert result.ingredients_source == "off_dump_mx"
    assert result.ingredients_json == ["Avena integral", "Sal"]


def test_updates_existing_product(mem_db, tmp_path):
    mem_db.add(Product(barcode="1234567890123", name="Old Name", clean_score=0))
    mem_db.commit()

    updated = {**_PRODUCT, "name": "New Name"}
    _run_load(mem_db, tmp_path, [updated])

    result = mem_db.scalar(select(Product).where(Product.barcode == "1234567890123"))
    assert result.name == "New Name"


def test_idempotent_run(mem_db, tmp_path):
    _run_load(mem_db, tmp_path, [_PRODUCT])
    _run_load(mem_db, tmp_path, [_PRODUCT])

    count = mem_db.scalar(
        select(func.count()).select_from(Product).where(Product.barcode == "1234567890123")
    )
    assert count == 1


def test_missing_file_exits_cleanly(mem_db, tmp_path):
    from unittest.mock import patch

    import scripts.load_products_to_db as loader

    missing = tmp_path / "nonexistent.json"
    with (
        patch.object(loader, "INPUT_PATH", missing),
        patch.object(loader, "SessionLocal", lambda: mem_db),
    ):
        loader.main()  # should log error, not raise


def test_inserts_multiple_products(mem_db, tmp_path):
    products = [{**_PRODUCT, "barcode": f"BC{i}", "name": f"Product {i}"} for i in range(5)]
    _run_load(mem_db, tmp_path, products)

    count = mem_db.scalar(select(func.count()).select_from(Product))
    assert count == 5
