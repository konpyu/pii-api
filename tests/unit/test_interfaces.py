"""Tests for core interfaces."""

from pii_masking import Entity, MaskingResult


class TestEntity:
    """Test Entity dataclass."""

    def test_entity_creation(self) -> None:
        """Test creating an Entity."""
        entity = Entity(text="田中", label="PERSON", start=0, end=2, confidence=0.95)
        assert entity.text == "田中"
        assert entity.label == "PERSON"
        assert entity.start == 0
        assert entity.end == 2
        assert entity.confidence == 0.95

    def test_entity_default_confidence(self) -> None:
        """Test Entity with default confidence."""
        entity = Entity(text="東京", label="LOCATION", start=5, end=7)
        assert entity.confidence == 1.0


class TestMaskingResult:
    """Test MaskingResult dataclass."""

    def test_masking_result_creation(self) -> None:
        """Test creating a MaskingResult."""
        entities = [
            Entity("田中", "PERSON", 0, 2),
            Entity("090-1234-5678", "PHONE", 5, 18),
        ]
        result = MaskingResult(
            masked_text="<MASK>さん<MASK>です",
            entities=entities,
            risk_score=0.7,
            cached=False,
        )
        assert result.masked_text == "<MASK>さん<MASK>です"
        assert len(result.entities) == 2
        assert result.risk_score == 0.7
        assert result.cached is False

    def test_masking_result_defaults(self) -> None:
        """Test MaskingResult with default values."""
        result = MaskingResult(masked_text="テスト")
        assert result.masked_text == "テスト"
        assert result.entities == []
        assert result.risk_score == 0.0
        assert result.cached is False
