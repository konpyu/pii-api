"""Tests for risk scorer."""

from typing import Any, Dict

from pii_masking.config.constants import EntityType
from pii_masking.core.interfaces import Entity
from pii_masking.processors.risk_scorer import RiskScorer


class TestRiskScorer:
    """Test RiskScorer class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.scorer = RiskScorer()

    def test_scorer_initialization(self) -> None:
        """Test risk scorer initialization."""
        scorer = RiskScorer()
        assert scorer.settings is not None

    def test_compute_risk_score_no_entities(self) -> None:
        """Test risk score with no entities."""
        score = self.scorer.compute_risk_score([], [], [])
        assert score == 0.2  # Base score only

    def test_compute_risk_score_single_person(self) -> None:
        """Test risk score with single person."""
        ner_entities = [
            Entity("田中", EntityType.PERSON, 0, 2),
        ]
        score = self.scorer.compute_risk_score([], ner_entities, [])
        assert abs(score - 0.6) < 0.001  # Base 0.2 + Single person 0.4

    def test_compute_risk_score_multiple_persons(self) -> None:
        """Test risk score with multiple persons."""
        ner_entities = [
            Entity("田中", EntityType.PERSON, 0, 2),
            Entity("佐藤", EntityType.PERSON, 10, 12),
        ]
        score = self.scorer.compute_risk_score([], ner_entities, [])
        assert abs(score - 0.9) < 0.001  # Base 0.2 + Multiple persons 0.7

    def test_compute_risk_score_with_regex(self) -> None:
        """Test risk score with regex matches."""
        regex_entities = [
            Entity("03-1234-5678", "PHONE_NUMBER", 5, 17),
        ]
        regex_types = ["phone_number"]
        score = self.scorer.compute_risk_score(regex_entities, [], regex_types)
        assert abs(score - 0.3) < 0.001  # Base 0.2 + 1 regex type * 0.1

    def test_compute_risk_score_combined(self) -> None:
        """Test risk score with both NER and regex entities."""
        ner_entities = [Entity("田中", EntityType.PERSON, 0, 2)]
        regex_entities = [
            Entity("03-1234-5678", "PHONE_NUMBER", 5, 17),
            Entity("150-0002", "POSTAL_CODE", 20, 28),
        ]
        regex_types = ["phone_number", "postal_code"]
        score = self.scorer.compute_risk_score(
            regex_entities, ner_entities, regex_types
        )
        assert score == 0.8  # Base 0.2 + Person 0.4 + 2 regex types * 0.1

    def test_compute_risk_score_max_cap(self) -> None:
        """Test risk score is capped at 1.0."""
        ner_entities = [
            Entity("田中", EntityType.PERSON, 0, 2),
            Entity("佐藤", EntityType.PERSON, 10, 12),
            Entity("鈴木", EntityType.PERSON, 20, 22),
        ]
        regex_entities = [
            Entity("03-1234-5678", "PHONE_NUMBER", 5, 17),
            Entity("150-0002", "POSTAL_CODE", 20, 28),
            Entity("test@example.com", "EMAIL", 30, 46),
        ]
        regex_types = ["phone_number", "postal_code", "email", "credit_card"]
        score = self.scorer.compute_risk_score(
            regex_entities, ner_entities, regex_types
        )
        assert score == 1.0  # Should be capped

    def test_calculate_entity_diversity(self) -> None:
        """Test entity diversity calculation."""
        entities = [
            Entity("田中", EntityType.PERSON, 0, 2),
            Entity("東京", EntityType.LOCATION, 5, 7),
            Entity("トヨタ", EntityType.ORGANIZATION, 10, 13),
        ]
        diversity = self.scorer._calculate_entity_diversity(entities)
        assert abs(diversity - 0.6) < 0.001  # 3 types * 0.2

    def test_calculate_density_score(self) -> None:
        """Test density score calculation."""
        # 2 entities in 100 bytes
        density = self.scorer._calculate_density_score(100, 2)
        assert density == 0.4  # (2/100)*100*0.2

        # Edge case: no text
        density = self.scorer._calculate_density_score(0, 5)
        assert density == 0.0

    def test_process_full_context(self) -> None:
        """Test full processing with context."""
        context: Dict[str, Any] = {
            "text_length": 50,
            "regex_matches": [
                Entity("03-1234-5678", "PHONE_NUMBER", 5, 17),
            ],
            "regex_match_types": ["phone_number"],
            "ner_entities": [
                Entity("田中", EntityType.PERSON, 0, 2),
                Entity("東京", EntityType.LOCATION, 20, 22),
            ],
        }

        result = self.scorer.process("", context)

        assert "risk_score" in result
        assert (
            abs(result["risk_score"] - 0.7) < 0.001
        )  # Base 0.2 + Person 0.4 + Regex 0.1

        assert "risk_metrics" in result
        metrics = result["risk_metrics"]
        assert metrics["entity_count"] == 3
        assert metrics["person_count"] == 1
        assert metrics["regex_type_count"] == 1
        assert metrics["diversity_score"] > 0
        assert metrics["density_score"] > 0

    def test_process_empty_context(self) -> None:
        """Test processing with empty context."""
        context: Dict[str, Any] = {}
        result = self.scorer.process("", context)

        assert result["risk_score"] == 0.2  # Base score
        assert result["risk_metrics"]["entity_count"] == 0
