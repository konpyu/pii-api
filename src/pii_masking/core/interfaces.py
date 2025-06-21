"""Abstract base classes and data models for PII masking pipeline."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Entity:
    """Represents a detected PII entity."""

    text: str
    label: str
    start: int
    end: int
    confidence: float = 1.0


@dataclass
class MaskingResult:
    """Result of PII masking operation."""

    masked_text: str
    entities: List[Entity] = field(default_factory=list)
    risk_score: float = 0.0
    cached: bool = False


class Processor(ABC):
    """Base class for all pipeline processors."""

    @abstractmethod
    def process(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process text and return updated context.

        Args:
            text: Input text to process
            context: Processing context containing intermediate results

        Returns:
            Updated context dictionary
        """
        pass


class CacheProvider(ABC):
    """Abstract cache interface."""

    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        """
        Retrieve value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        pass

    @abstractmethod
    def set(self, key: str, value: str, ttl: int = 3600) -> None:
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
        """
        pass
