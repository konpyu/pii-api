"""Risk scoring for PII masking results."""

from typing import Any, Dict, List

from ..config.constants import EntityType
from ..config.settings import get_settings
from ..core.interfaces import Entity, Processor


class RiskScorer(Processor):
    """Calculates risk score based on detected PII entities."""

    def __init__(self) -> None:
        """Initialize risk scorer with settings."""
        self.settings = get_settings()

    def compute_risk_score(
        self,
        regex_entities: List[Entity],
        ner_entities: List[Entity],
        regex_match_types: List[str],
    ) -> float:
        """
        Compute risk score based on detected entities.

        Args:
            regex_entities: Entities detected by regex
            ner_entities: Entities detected by NER
            regex_match_types: Types of regex matches found

        Returns:
            Risk score between 0.0 and 1.0
        """
        # Start with base score
        score = self.settings.risk_base_score

        # Count person entities
        person_count = sum(
            1 for entity in ner_entities if entity.label == EntityType.PERSON
        )

        # Add score based on person count
        if person_count == 1:
            score += self.settings.risk_person_single
        elif person_count >= 2:
            score += self.settings.risk_person_multiple

        # Add score for each unique regex match type
        unique_regex_types = len(set(regex_match_types))
        score += unique_regex_types * self.settings.risk_regex_increment

        # Cap at 1.0
        return min(1.0, score)

    def _calculate_entity_diversity(self, entities: List[Entity]) -> float:
        """
        Calculate diversity score based on entity types.

        Args:
            entities: List of entities

        Returns:
            Diversity score between 0.0 and 1.0
        """
        if not entities:
            return 0.0

        # Count unique entity types
        entity_types = set(entity.label for entity in entities)
        unique_types = len(entity_types)

        # More diverse entity types = higher risk
        diversity_score = min(1.0, unique_types * 0.2)
        return diversity_score

    def _calculate_density_score(self, text_length: int, entity_count: int) -> float:
        """
        Calculate density score based on entity density in text.

        Args:
            text_length: Length of text in bytes
            entity_count: Number of entities found

        Returns:
            Density score between 0.0 and 1.0
        """
        if text_length == 0:
            return 0.0

        # Calculate entities per 100 characters
        density = (entity_count / text_length) * 100

        # Higher density = higher risk
        # Assume 1 entity per 20 chars is very high density
        density_score = min(1.0, density * 0.2)
        return density_score

    def process(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate risk score for the processed text.

        Args:
            text: Input text (not used directly)
            context: Processing context containing detected entities

        Returns:
            Updated context with risk score
        """
        # Get entities from context
        regex_entities = context.get("regex_matches", [])
        ner_entities = context.get("ner_entities", [])
        regex_match_types = context.get("regex_match_types", [])

        # Calculate main risk score
        risk_score = self.compute_risk_score(
            regex_entities, ner_entities, regex_match_types
        )

        # Calculate additional metrics
        all_entities = regex_entities + ner_entities
        entity_count = len(all_entities)

        # Get text length from context
        text_length = context.get("text_length", 0)

        # Calculate supplementary scores
        diversity_score = self._calculate_entity_diversity(all_entities)
        density_score = self._calculate_density_score(text_length, entity_count)

        # Update context
        context["risk_score"] = risk_score
        context["risk_metrics"] = {
            "entity_count": entity_count,
            "diversity_score": diversity_score,
            "density_score": density_score,
            "person_count": sum(
                1 for e in ner_entities if e.label == EntityType.PERSON
            ),
            "regex_type_count": len(regex_match_types),
        }

        return context
