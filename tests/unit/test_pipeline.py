"""Tests for main masking pipeline."""

import pytest

from pii_masking.config.constants import EntityType
from pii_masking.core.exceptions import ValidationError
from pii_masking.core.interfaces import Entity
from pii_masking.core.pipeline import MaskingPipeline


class TestMaskingPipeline:
    """Test MaskingPipeline class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.pipeline = MaskingPipeline()

    def test_pipeline_initialization(self) -> None:
        """Test pipeline initialization with defaults."""
        pipeline = MaskingPipeline()
        assert pipeline.validator is not None
        assert pipeline.cache is not None
        assert pipeline.regex_processor is not None
        assert pipeline.tokenizer is not None
        assert pipeline.ner_processor is not None
        assert pipeline.risk_scorer is not None

    def test_mask_simple_text(self) -> None:
        """Test masking simple text with no PII."""
        text = "これは個人情報を含まないテキストです。"
        result = self.pipeline.mask_text(text)

        assert result.masked_text == text  # No changes
        assert result.entities == []
        assert result.risk_score == 0.2  # Base score only
        assert result.cached is False

    def test_mask_phone_number(self) -> None:
        """Test masking phone number."""
        text = "連絡先は03-1234-5678です。"
        result = self.pipeline.mask_text(text)

        assert result.masked_text == "連絡先は<MASK>です。"
        assert len(result.entities) == 1
        assert result.entities[0].label == "PHONE_NUMBER"
        assert result.risk_score > 0.2

    def test_mask_person_name(self) -> None:
        """Test masking person name."""
        text = "田中さんに会いました。"
        result = self.pipeline.mask_text(text)

        assert result.masked_text == "<MASK>さんに会いました。"
        assert len(result.entities) == 1
        assert result.entities[0].label == EntityType.PERSON
        assert abs(result.risk_score - 0.6) < 0.001  # Base + Person

    def test_mask_multiple_pii(self) -> None:
        """Test masking multiple PII types."""
        text = "田中さんの電話番号は03-1234-5678です。"
        result = self.pipeline.mask_text(text)

        assert "<MASK>" in result.masked_text
        assert result.masked_text.count("<MASK>") == 2
        assert len(result.entities) == 2
        assert result.risk_score > 0.6

    def test_mask_with_location(self) -> None:
        """Test masking with location."""
        text = "東京に住んでいます。"
        result = self.pipeline.mask_text(text)

        assert result.masked_text == "<MASK>に住んでいます。"
        assert len(result.entities) == 1
        assert result.entities[0].label == EntityType.LOCATION

    def test_validation_error(self) -> None:
        """Test validation error handling."""
        with pytest.raises(ValidationError):
            self.pipeline.mask_text("")

        with pytest.raises(ValidationError):
            self.pipeline.mask_text("あ" * 500)  # Too long

    def test_cache_functionality(self) -> None:
        """Test caching functionality."""
        text = "佐藤さんです。"

        # First call - not cached
        result1 = self.pipeline.mask_text(text)
        assert result1.cached is False

        # Second call - should be cached
        result2 = self.pipeline.mask_text(text)
        assert result2.cached is True
        assert result2.masked_text == result1.masked_text
        assert result2.risk_score == result1.risk_score

    def test_entity_merging(self) -> None:
        """Test entity merging from different sources."""
        # Test internal method
        regex_entities = [
            Entity("03-1234-5678", "PHONE", 10, 22),
        ]
        ner_entities = [
            Entity("田中", "PERSON", 0, 2),
            Entity("1234", "NUMBER", 13, 17),  # Overlaps with phone
        ]

        merged = self.pipeline._merge_entities(regex_entities, ner_entities)

        # Should have 2 entities (田中 and phone, not the overlapping number)
        assert len(merged) == 2
        assert merged[0].text == "田中"
        assert merged[1].text == "03-1234-5678"

    def test_already_masked_check(self) -> None:
        """Test checking if text is already masked."""
        assert self.pipeline._is_already_masked("text<MASK>text", 4, 10)
        assert not self.pipeline._is_already_masked("normal text", 0, 6)

    def test_disable_cache(self) -> None:
        """Test with cache disabled."""
        # Create pipeline with cache disabled
        pipeline = MaskingPipeline()
        pipeline.settings.cache_enabled = False

        text = "田中さんです。"
        result1 = self.pipeline.mask_text(text)
        result2 = self.pipeline.mask_text(text)

        # Both should not be cached
        assert result1.cached is False
        assert result2.cached is False

    def test_complex_japanese_text(self) -> None:
        """Test with complex Japanese text."""
        text = "株式会社トヨタの田中様より、090-1234-5678にご連絡ください。"
        result = self.pipeline.mask_text(text)

        # Should mask company, person, and phone
        assert result.masked_text.count("<MASK>") >= 3
        assert result.risk_score > 0.7

    def test_email_masking(self) -> None:
        """Test email masking."""
        text = "メールはtest@example.comまで。"
        result = self.pipeline.mask_text(text)

        assert result.masked_text == "メールは<MASK>まで。"
        assert len(result.entities) == 1
        assert result.entities[0].label == "EMAIL"
