"""Tests para ScanStateAccumulator — acumulador tipado de estado parcial del agente."""

import pytest

from app.agents.accumulator import ScanStateAccumulator
from app.schemas.models import ConflictSeverity, SemaphoreColor


# ---------------------------------------------------------------------------
# 1. Valores por defecto
# ---------------------------------------------------------------------------

def test_default_semaphore_is_gray():
    acc = ScanStateAccumulator()
    assert acc.semaphore == SemaphoreColor.GRAY


def test_default_product_name_is_none():
    acc = ScanStateAccumulator()
    assert acc.product_name is None


def test_default_extracted_ingredients_is_empty_list():
    acc = ScanStateAccumulator()
    assert acc.extracted_ingredients == []


def test_default_source_is_barcode():
    acc = ScanStateAccumulator()
    assert acc.source == "barcode"


# ---------------------------------------------------------------------------
# 2. apply() establece valores no-None para claves conocidas
# ---------------------------------------------------------------------------

def test_apply_sets_known_key():
    acc = ScanStateAccumulator()
    acc.apply({"product_name": "Oreo"})
    assert acc.product_name == "Oreo"


def test_apply_sets_semaphore():
    acc = ScanStateAccumulator()
    acc.apply({"semaphore": SemaphoreColor.RED})
    assert acc.semaphore == SemaphoreColor.RED


# ---------------------------------------------------------------------------
# 3. apply() NO sobreescribe cuando el valor del output es None
# ---------------------------------------------------------------------------

def test_apply_does_not_overwrite_with_none():
    acc = ScanStateAccumulator()
    acc.product_name = "Coca-Cola"
    acc.apply({"product_name": None})
    # El valor anterior debe conservarse
    assert acc.product_name == "Coca-Cola"


# ---------------------------------------------------------------------------
# 4. apply() ignora claves desconocidas sin lanzar excepción
# ---------------------------------------------------------------------------

def test_apply_ignores_unknown_keys():
    acc = ScanStateAccumulator()
    # No debe lanzar excepción con claves que no existen en el dataclass
    acc.apply({"nonexistent_field": "valor", "otra_clave": 42})


# ---------------------------------------------------------------------------
# 5. get() retorna el valor del atributo para claves conocidas
# ---------------------------------------------------------------------------

def test_get_returns_known_attribute():
    acc = ScanStateAccumulator()
    acc.product_name = "Pepsi"
    assert acc.get("product_name") == "Pepsi"


def test_get_returns_default_source():
    acc = ScanStateAccumulator()
    assert acc.get("source") == "barcode"


# ---------------------------------------------------------------------------
# 6. get() retorna el default proporcionado para claves desconocidas
# ---------------------------------------------------------------------------

def test_get_returns_default_for_unknown_key():
    acc = ScanStateAccumulator()
    assert acc.get("no_existe", "fallback") == "fallback"


def test_get_returns_none_default_for_unknown_key():
    acc = ScanStateAccumulator()
    assert acc.get("no_existe") is None


# ---------------------------------------------------------------------------
# 7. apply() con dict parcial solo toca las claves especificadas
# ---------------------------------------------------------------------------

def test_apply_partial_dict_leaves_other_fields_unchanged():
    acc = ScanStateAccumulator()
    acc.product_brand = "Nestlé"
    acc.semaphore = SemaphoreColor.YELLOW
    # Solo actualizamos product_name
    acc.apply({"product_name": "Kit Kat"})
    assert acc.product_name == "Kit Kat"
    # Campos no tocados deben permanecer intactos
    assert acc.product_brand == "Nestlé"
    assert acc.semaphore == SemaphoreColor.YELLOW
    assert acc.extracted_ingredients == []


# ---------------------------------------------------------------------------
# 8. Instanciar con source="photo" personalizado
# ---------------------------------------------------------------------------

def test_custom_source_photo():
    acc = ScanStateAccumulator(source="photo")
    assert acc.source == "photo"


# ---------------------------------------------------------------------------
# 9. apply() con dict vacío es no-op
# ---------------------------------------------------------------------------

def test_apply_empty_dict_is_noop():
    acc = ScanStateAccumulator()
    acc.product_name = "Milka"
    acc.apply({})
    assert acc.product_name == "Milka"


# ---------------------------------------------------------------------------
# 10. apply() con lista vacía sí sobreescribe ([] no es None)
# ---------------------------------------------------------------------------

def test_apply_empty_list_overwrites_existing():
    acc = ScanStateAccumulator()
    acc.extracted_ingredients = ["azúcar", "sal"]
    acc.apply({"extracted_ingredients": []})
    # [] es un update explícito válido, no debe ignorarse
    assert acc.extracted_ingredients == []


# ---------------------------------------------------------------------------
# 11. apply() reemplaza lista, no hace append
# ---------------------------------------------------------------------------

def test_apply_list_field_replaces_not_appends():
    acc = ScanStateAccumulator()
    acc.extracted_ingredients = ["a", "b"]
    acc.apply({"extracted_ingredients": ["c"]})
    assert acc.extracted_ingredients == ["c"]
