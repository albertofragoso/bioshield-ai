import pytest
from app.schemas.models import ConflictSeverity, RegulatoryStatus
from app.core.priorities import worst_severity, worst_status


class TestWorstStatus:
    def test_banned_beats_all(self):
        result = worst_status([
            RegulatoryStatus.APPROVED,
            RegulatoryStatus.RESTRICTED,
            RegulatoryStatus.BANNED,
        ])
        assert result == RegulatoryStatus.BANNED

    def test_restricted_beats_approved_and_under_review(self):
        result = worst_status([RegulatoryStatus.APPROVED, RegulatoryStatus.UNDER_REVIEW, RegulatoryStatus.RESTRICTED])
        assert result == RegulatoryStatus.RESTRICTED

    def test_single_item(self):
        assert worst_status([RegulatoryStatus.APPROVED]) == RegulatoryStatus.APPROVED

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            worst_status([])


class TestWorstSeverity:
    def test_high_beats_all(self):
        result = worst_severity([ConflictSeverity.LOW, ConflictSeverity.MEDIUM, ConflictSeverity.HIGH])
        assert result == ConflictSeverity.HIGH

    def test_medium_beats_low(self):
        assert worst_severity([ConflictSeverity.LOW, ConflictSeverity.MEDIUM]) == ConflictSeverity.MEDIUM

    def test_single_item(self):
        assert worst_severity([ConflictSeverity.LOW]) == ConflictSeverity.LOW

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            worst_severity([])
