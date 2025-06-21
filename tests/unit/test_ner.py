"""Tests for NER processor."""

from typing import Any, Dict

import pytest

from pii_masking.config.constants import EntityType
from pii_masking.core.exceptions import ModelLoadError, ProcessingError
from pii_masking.processors.ner import NERProcessor


class TestNERProcessor:
    """Test NERProcessor class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        # Use mock NER for testing
        self.processor = NERProcessor(use_mock=True)

    def test_processor_initialization(self) -> None:
        """Test NER processor initialization."""
        processor = NERProcessor(use_mock=True)
        assert processor.use_mock is True
        assert processor.session is None

    def test_mock_ner_inference(self) -> None:
        """Test mock NER inference."""
        tokens = ["田中", "さん", "は", "東京", "に", "住んで", "います"]
        predictions = self.processor._mock_ner_inference(tokens)

        assert len(predictions) == 2  # 田中 and 東京
        assert predictions[0]["text"] == "田中"
        assert predictions[0]["label"] == EntityType.PERSON
        assert predictions[1]["text"] == "東京"
        assert predictions[1]["label"] == EntityType.LOCATION

    def test_process_with_person_names(self) -> None:
        """Test NER detection of person names."""
        context: Dict[str, Any] = {
            "token_surfaces": ["佐藤", "さん", "が", "来ました"],
            "token_positions": [(0, 2), (2, 4), (4, 5), (5, 9)],
        }
        result = self.processor.process("", context)

        assert "ner_entities" in result
        assert len(result["ner_entities"]) == 1
        assert result["ner_entities"][0].text == "佐藤"
        assert result["ner_entities"][0].label == EntityType.PERSON
        assert result["ner_entities"][0].start == 0
        assert result["ner_entities"][0].end == 2

    def test_process_with_locations(self) -> None:
        """Test NER detection of locations."""
        context: Dict[str, Any] = {
            "token_surfaces": ["私", "は", "大阪", "から", "京都", "へ", "行く"],
            "token_positions": [
                (0, 1),
                (1, 2),
                (2, 4),
                (4, 6),
                (6, 8),
                (8, 9),
                (9, 11),
            ],
        }
        result = self.processor.process("", context)

        entities = result["ner_entities"]
        assert len(entities) == 2
        assert entities[0].text == "大阪"
        assert entities[0].label == EntityType.LOCATION
        assert entities[1].text == "京都"
        assert entities[1].label == EntityType.LOCATION

    def test_process_with_organizations(self) -> None:
        """Test NER detection of organizations."""
        context: Dict[str, Any] = {
            "token_surfaces": ["トヨタ", "と", "ソニー", "の", "株価"],
            "token_positions": [(0, 3), (3, 4), (4, 7), (7, 8), (8, 10)],
        }
        result = self.processor.process("", context)

        entities = result["ner_entities"]
        assert len(entities) == 2
        assert entities[0].label == EntityType.ORGANIZATION
        assert entities[1].label == EntityType.ORGANIZATION

    def test_process_without_tokens(self) -> None:
        """Test process fails without tokenization."""
        context: Dict[str, Any] = {}
        with pytest.raises(ProcessingError, match="Tokenization required"):
            self.processor.process("test", context)

    def test_process_with_masked_tokens(self) -> None:
        """Test NER with masked tokens."""
        context: Dict[str, Any] = {
            "token_surfaces": ["<MASK>", "さん", "は", "東京", "に", "います"],
            "token_positions": [(0, 6), (6, 8), (8, 9), (9, 11), (11, 12), (12, 15)],
        }
        result = self.processor.process("", context)

        # Should only detect 東京, not <MASK>
        entities = result["ner_entities"]
        assert len(entities) == 1
        assert entities[0].text == "東京"

    def test_process_no_entities(self) -> None:
        """Test NER with text containing no entities."""
        context: Dict[str, Any] = {
            "token_surfaces": ["今日", "は", "いい", "天気", "です"],
            "token_positions": [(0, 2), (2, 3), (3, 5), (5, 7), (7, 9)],
        }
        result = self.processor.process("", context)

        assert result["ner_entities"] == []
        assert result["ner_performed"] is True

    def test_model_loading_error(self) -> None:
        """Test model loading error handling."""
        with pytest.raises(ModelLoadError, match="Model file not found"):
            NERProcessor(model_path="/nonexistent/model.onnx", use_mock=False)

    def test_multiple_same_entities(self) -> None:
        """Test handling of multiple occurrences of same entity."""
        context: Dict[str, Any] = {
            "token_surfaces": ["田中", "と", "田中", "が", "話す"],
            "token_positions": [(0, 2), (2, 3), (3, 5), (5, 6), (6, 8)],
        }
        result = self.processor.process("", context)

        entities = result["ner_entities"]
        assert len(entities) == 2
        assert all(e.text == "田中" for e in entities)
        assert entities[0].start != entities[1].start
