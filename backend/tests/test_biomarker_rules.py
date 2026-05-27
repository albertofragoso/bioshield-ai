"""Tests for the biomarker_rules module and the updated alternatives helpers."""

import pytest

from app.services.biomarker_rules import (
    BIOMARKER_RULES,
    BiomarkerRule,
    DecryptedBiomarker,
    excludes_for,
    keywords_for,
    parse_biomarker_payload,
)


class TestKeywordsFor:
    def test_ldl_returns_nonempty_with_trans_fat_and_hydrogenated(self):
        kws = keywords_for("ldl")
        assert len(kws) > 0
        assert "trans fat" in kws
        assert "hydrogenated" in kws

    def test_hba1c_returns_nonempty(self):
        """HBA1C keywords exist — proves the biomarker is now reachable from alternatives."""
        kws = keywords_for("hba1c")
        assert len(kws) > 0

    def test_unknown_biomarker_returns_empty_tuple(self):
        assert keywords_for("unknown_biomarker") == ()


class TestExcludesFor:
    def test_sodium_excludes_contains_sodium_bicarbonate(self):
        excs = excludes_for("sodium")
        assert len(excs) > 0
        assert "sodium bicarbonate" in excs

    def test_unknown_biomarker_returns_empty_tuple(self):
        assert excludes_for("unknown_biomarker") == ()


class TestBiomarkerRules:
    def test_nonempty_and_all_instances(self):
        assert len(BIOMARKER_RULES) > 0
        for rule in BIOMARKER_RULES:
            assert isinstance(rule, BiomarkerRule)


class TestBiomarkerConflicts:
    """Integration tests via the public-ish helper in alternatives."""

    def setup_method(self):
        from app.services.alternatives import _biomarker_conflicts

        self._fn = _biomarker_conflicts

    def test_trans_fat_flags_ldl(self):
        result = self._fn(["trans fat"], ["ldl"])
        assert len(result) > 0

    def test_water_does_not_flag_ldl(self):
        result = self._fn(["water"], ["ldl"])
        assert result == []

    def test_fructose_flags_hba1c(self):
        """Proves HBA1C now works — was missing from the old _BIOMARKER_FLAG_KEYWORDS."""
        result = self._fn(["fructose"], ["hba1c"])
        assert len(result) > 0

    def test_excluded_ingredient_does_not_flag_ldl(self):
        # "hydrogenated" keyword matches LDL but "petroleum" exclude fires — should not flag
        result = self._fn(["hydrogenated petroleum resin"], ["ldl"])
        assert result == []

    def test_excluded_ingredient_does_not_flag_sodium(self):
        # "sodium" keyword matches but "sodium bicarbonate" exclude fires — should not flag
        result = self._fn(["sodium bicarbonate"], ["sodium"])
        assert result == []


class TestParseBiomarkerPayload:
    def test_raises_on_legacy_flatdict(self):
        """Legacy {"ldl": 130} format must raise ValueError, not return None."""
        with pytest.raises(ValueError, match="Unrecognized biomarker payload shape"):
            parse_biomarker_payload({"ldl": 130, "glucose": 95})

    def test_raises_on_missing_biomarkers_key(self):
        with pytest.raises(ValueError, match="Unrecognized biomarker payload shape"):
            parse_biomarker_payload({"unexpected": "shape"})

    def test_returns_typed_list_on_valid_payload(self):
        result = parse_biomarker_payload({
            "biomarkers": [
                {"name": "ldl", "classification": "high", "value": 145.0, "unit": "mg/dL"},
                {"name": "glucose", "classification": "normal", "value": 95.0, "unit": "mg/dL"},
            ]
        })
        assert len(result) == 2
        assert result[0].name == "ldl"
        assert result[0].classification == "high"
        assert result[0].value == 145.0
        assert isinstance(result[0], DecryptedBiomarker)
