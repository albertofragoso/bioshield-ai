"""Tests for the ingredient text parser."""

from scripts.utils.ingredient_parser import parse_ingredients


def test_simple_comma_list():
    assert parse_ingredients("Leche, Azúcar, Sal") == ["Leche", "Azúcar", "Sal"]


def test_sub_ingredients_extracted():
    result = parse_ingredients("Chocolate (Cacao (50%), Azúcar), Leche")
    assert "Chocolate" in result
    assert "Cacao" in result
    assert "Azúcar" in result
    assert "Leche" in result


def test_deduplication_preserves_order():
    result = parse_ingredients("Azúcar, Sal, Azúcar")
    assert result.count("Azúcar") == 1
    assert result.index("Azúcar") < result.index("Sal")


def test_strips_percentages():
    result = parse_ingredients("Harina (30%), Agua, Aceite (5%)")
    for item in result:
        assert "%" not in item


def test_e_numbers_extracted_as_ingredients():
    result = parse_ingredients("Lecitina de Soja (E322), Agua")
    assert "Lecitina de Soja" in result
    assert "E322" in result


def test_empty_string_returns_empty_list():
    assert parse_ingredients("") == []


def test_whitespace_only_returns_empty_list():
    assert parse_ingredients("   ") == []


def test_strips_asterisk_organic_markers():
    result = parse_ingredients("*Avena integral, Agua")
    assert "Avena integral" in result
    assert "*Avena integral" not in result


def test_deeply_nested_parentheses():
    result = parse_ingredients("Salsa (Tomate (60%), Sal, Aceite de Oliva (Acidez: 0.5%)), Agua")
    assert "Salsa" in result
    assert "Tomate" in result
    assert "Sal" in result
    assert "Aceite de Oliva" in result
    assert "Agua" in result
