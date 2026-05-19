"""Tests for load_all_products — multi-source merge with priority-by-barcode."""
import json
from pathlib import Path
from unittest.mock import MagicMock


def _write_json(path: Path, data: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _make_product(
    barcode="1234567890123",
    name="Test Product",
    brand="Brand",
    category="snacks",
    ingredients_source="off_dump_mx",
) -> dict:
    return {
        "barcode": barcode,
        "name": name,
        "brand": brand,
        "category": category,
        "image_url": None,
        "ingredients_json": ["ingredient one", "ingredient two"],
        "ingredients_source": ingredients_source,
    }


def test_inserts_product_from_single_source(tmp_path):
    """Producto nuevo se inserta correctamente."""
    from scripts.load_all_products import _load_sources

    source = tmp_path / "off_mx_products.json"
    _write_json(source, [_make_product(barcode="AAA")])

    db_mock = MagicMock()
    db_mock.scalar.return_value = None  # barcode no existe

    ins, sk = _load_sources([source], db_mock)
    assert ins == 1
    assert sk == 0
    db_mock.add.assert_called_once()


def test_skips_existing_barcode(tmp_path):
    """Si el barcode ya existe en DB, se hace skip (no update)."""
    from scripts.load_all_products import _load_sources

    source = tmp_path / "usda_products.json"
    _write_json(source, [_make_product(barcode="BBB")])

    db_mock = MagicMock()
    db_mock.scalar.return_value = MagicMock()  # barcode ya existe

    ins, sk = _load_sources([source], db_mock)
    assert ins == 0
    assert sk == 1
    db_mock.add.assert_not_called()


def test_priority_preserved_across_sources(tmp_path):
    """MX product no se sobreescribe cuando USDA tiene el mismo barcode."""
    from scripts.load_all_products import _load_sources

    mx = tmp_path / "off_mx_products.json"
    usda = tmp_path / "usda_products.json"
    _write_json(mx, [_make_product(barcode="SHARED", name="MX Version", ingredients_source="off_dump_mx")])
    _write_json(usda, [_make_product(barcode="SHARED", name="USDA Version", ingredients_source="usda_branded")])

    inserted_names: list[str] = []

    def mock_add(obj):
        inserted_names.append(obj.name)

    # Simula que tras insertar MX, USDA lo encuentra como existente
    call_count = {"n": 0}
    def mock_scalar(stmt):
        call_count["n"] += 1
        # Primera llamada (MX): barcode no existe → insert
        # Segunda llamada (USDA): barcode ya existe → skip
        return None if call_count["n"] == 1 else MagicMock()

    db_mock = MagicMock()
    db_mock.scalar.side_effect = mock_scalar
    db_mock.add.side_effect = mock_add

    ins, sk = _load_sources([mx, usda], db_mock)
    assert ins == 1
    assert sk == 1
    assert inserted_names == ["MX Version"]


def test_missing_source_file_is_skipped(tmp_path):
    """Un archivo JSON inexistente se omite sin error."""
    from scripts.load_all_products import _load_sources

    existing = tmp_path / "off_mx_products.json"
    missing = tmp_path / "off_global_products.json"
    _write_json(existing, [_make_product()])

    db_mock = MagicMock()
    db_mock.scalar.return_value = None

    ins, sk = _load_sources([existing, missing], db_mock)
    assert ins == 1


def test_inserts_products_from_multiple_sources(tmp_path):
    """Productos de 3 fuentes distintas se insertan todos si no hay duplicados."""
    from scripts.load_all_products import _load_sources

    mx = tmp_path / "off_mx_products.json"
    glo = tmp_path / "off_global_products.json"
    usda = tmp_path / "usda_products.json"
    _write_json(mx, [_make_product(barcode="111", ingredients_source="off_dump_mx")])
    _write_json(glo, [_make_product(barcode="222", ingredients_source="off_global")])
    _write_json(usda, [_make_product(barcode="333", ingredients_source="usda_branded")])

    db_mock = MagicMock()
    db_mock.scalar.return_value = None

    ins, sk = _load_sources([mx, glo, usda], db_mock)
    assert ins == 3
    assert sk == 0
