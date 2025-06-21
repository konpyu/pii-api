"""Main masking pipeline orchestrator."""

from typing import Any, Dict, List, Optional

from ..cache.cache_key import generate_cache_key
from ..cache.memory_cache import InMemoryCache, MaskingResultCache
from ..config.constants import MaskToken
from ..config.settings import get_settings
from ..processors.ner import NERProcessor
from ..processors.regex import RegexProcessor
from ..processors.risk_scorer import RiskScorer
from ..processors.tokenizer import JapaneseTokenizer
from ..processors.validator import Validator
from .interfaces import CacheProvider, Entity, MaskingResult


class MaskingPipeline:
    """Main orchestrator for PII masking pipeline."""

    def __init__(
        self,
        validator: Optional[Validator] = None,
        cache: Optional[CacheProvider] = None,
        regex_processor: Optional[RegexProcessor] = None,
        tokenizer: Optional[JapaneseTokenizer] = None,
        ner_processor: Optional[NERProcessor] = None,
        risk_scorer: Optional[RiskScorer] = None,
    ) -> None:
        """
        Initialize masking pipeline with processors.

        Args:
            validator: Input validator (creates default if None)
            cache: Cache provider (creates InMemoryCache if None)
            regex_processor: Regex processor (creates default if None)
            tokenizer: Japanese tokenizer (creates default if None)
            ner_processor: NER processor (creates mock if None)
            risk_scorer: Risk scorer (creates default if None)
        """
        self.settings = get_settings()

        # Initialize components with defaults if not provided
        self.validator = validator or Validator()
        self.cache = cache or InMemoryCache()
        self.result_cache = MaskingResultCache(self.cache)
        self.regex_processor = regex_processor or RegexProcessor()
        self.tokenizer = tokenizer or JapaneseTokenizer()
        self.ner_processor = ner_processor or NERProcessor(use_mock=True)
        self.risk_scorer = risk_scorer or RiskScorer()

    def mask_text(self, text: str) -> MaskingResult:
        """
        Execute full masking pipeline.

        Args:
            text: Input text to mask

        Returns:
            MaskingResult with masked text and metadata

        Raises:
            ValidationError: If input validation fails
            ProcessingError: If processing fails
        """
        # Step 1: Check cache
        if self.settings.cache_enabled:
            cache_key = generate_cache_key(text, prefix="mask")
            cached_result = self.result_cache.get_result(cache_key)
            if cached_result is not None:
                return cached_result

        # Step 2: Validate input
        context: Dict[str, Any] = {}
        context = self.validator.process(text, context)

        # Step 3: Apply regex masking
        context = self.regex_processor.process(text, context)

        # Step 4: Tokenize
        context = self.tokenizer.process(text, context)

        # Step 5: Apply NER
        context = self.ner_processor.process(text, context)

        # Step 6: Apply final masking
        masked_text = self._apply_final_masking(text, context)

        # Step 7: Calculate risk score
        context = self.risk_scorer.process(text, context)

        # Step 8: Create result
        all_entities = self._merge_entities(
            context.get("regex_matches", []), context.get("ner_entities", [])
        )

        result = MaskingResult(
            masked_text=masked_text,
            entities=all_entities,
            risk_score=context.get("risk_score", 0.0),
            cached=False,
        )

        # Step 9: Cache result
        if self.settings.cache_enabled:
            try:
                self.result_cache.set_result(
                    cache_key, result, ttl=self.settings.cache_ttl
                )
            except Exception:
                # Cache failures should not break the pipeline
                pass

        return result

    def _apply_final_masking(self, original_text: str, context: Dict[str, Any]) -> str:
        """
        Apply final masking based on all detected entities.

        Args:
            original_text: Original input text
            context: Processing context with detected entities

        Returns:
            Fully masked text
        """
        # Start with regex-masked text if available
        masked_text: str = context.get("regex_masked_text", original_text)

        # Get NER entities
        ner_entities = context.get("ner_entities", [])

        # Apply NER masking (from right to left to preserve positions)
        for entity in sorted(ner_entities, key=lambda e: e.start, reverse=True):
            # Check if this position was already masked by regex
            if self._is_already_masked(masked_text, entity.start, entity.end):
                continue

            # Apply mask
            mask_token = MaskToken.DEFAULT.value
            masked_text = (
                masked_text[: entity.start] + mask_token + masked_text[entity.end :]
            )

        return masked_text

    def _is_already_masked(self, text: str, start: int, end: int) -> bool:
        """
        Check if a position is already masked.

        Args:
            text: Text to check
            start: Start position
            end: End position

        Returns:
            True if position contains mask token
        """
        if start >= len(text) or end > len(text):
            return True

        segment = text[start:end]
        return MaskToken.DEFAULT in segment

    def _merge_entities(
        self, regex_entities: List[Entity], ner_entities: List[Entity]
    ) -> List[Entity]:
        """
        Merge and deduplicate entities from different sources.

        Args:
            regex_entities: Entities from regex matching
            ner_entities: Entities from NER

        Returns:
            Merged list of entities
        """
        all_entities = []

        # Add regex entities
        all_entities.extend(regex_entities)

        # Add NER entities that don't overlap with regex
        for ner_entity in ner_entities:
            overlaps = False
            for regex_entity in regex_entities:
                if (
                    ner_entity.start >= regex_entity.start
                    and ner_entity.end <= regex_entity.end
                ):
                    overlaps = True
                    break
            if not overlaps:
                all_entities.append(ner_entity)

        # Sort by position
        all_entities.sort(key=lambda e: e.start)

        return all_entities
