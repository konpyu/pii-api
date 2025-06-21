"""Regex-based PII detection and masking."""

import re
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Pattern

import yaml

from ..config.constants import MaskToken
from ..config.settings import get_settings
from ..core.exceptions import ProcessingError
from ..core.interfaces import Entity, Processor


class RegexPattern(NamedTuple):
    """Represents a regex pattern for PII detection."""

    name: str
    pattern: Pattern[str]
    description: str = ""


class RegexProcessor(Processor):
    """Performs regex-based PII detection and masking."""

    def __init__(self, patterns_file: str | None = None) -> None:
        """
        Initialize regex processor.

        Args:
            patterns_file: Path to YAML file containing regex patterns.
                          If None, uses default from settings.
        """
        self.settings = get_settings()
        if patterns_file:
            self.patterns_file = patterns_file
            # For test files that don't exist, raise error early
            test_path = Path(patterns_file)
            if not test_path.exists() and test_path.is_absolute():
                raise ProcessingError(f"Regex patterns file not found: {patterns_file}")
        else:
            self.patterns_file = self.settings.regex_patterns_file
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> List[RegexPattern]:
        """Load regex patterns from YAML file."""
        patterns_path = Path(self.patterns_file)

        # Try relative to project root first
        if not patterns_path.is_absolute():
            project_root = Path(__file__).parent.parent.parent.parent
            patterns_path = project_root / patterns_path

        if not patterns_path.exists():
            # Try relative to config directory
            patterns_path = (
                Path(__file__).parent.parent / "config" / "regex_patterns.yaml"
            )

        if not patterns_path.exists():
            raise ProcessingError(
                f"Regex patterns file not found: {self.patterns_file}"
            )

        try:
            with open(patterns_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            raise ProcessingError(f"Failed to load regex patterns: {e}")

        patterns = []
        for pattern_config in data.get("patterns", []):
            try:
                compiled = re.compile(pattern_config["regex"])
                patterns.append(
                    RegexPattern(
                        name=pattern_config["name"],
                        pattern=compiled,
                        description=pattern_config.get("description", ""),
                    )
                )
            except re.error as e:
                raise ProcessingError(
                    f"Invalid regex pattern '{pattern_config['name']}': {e}"
                )

        return patterns

    def process(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply regex patterns to detect and mask PII.

        Args:
            text: Input text to process
            context: Processing context containing previous results

        Returns:
            Updated context with regex matches and masked text
        """
        # Get text from context if already validated
        validated_text = context.get("validated_text", text)

        # Track all matches
        regex_matches: List[Entity] = []
        regex_match_types: List[str] = []

        # Collect all matches first
        all_matches = []
        for regex_pattern in self.patterns:
            for match in regex_pattern.pattern.finditer(validated_text):
                all_matches.append((match, regex_pattern))

        # Sort matches by start position (to handle overlapping matches)
        all_matches.sort(key=lambda x: x[0].start())

        # Apply replacements from right to left to preserve positions
        masked_text = validated_text
        for match, regex_pattern in reversed(all_matches):
            # Create entity for the match
            entity = Entity(
                text=match.group(),
                label=regex_pattern.name.upper(),
                start=match.start(),
                end=match.end(),
            )
            regex_matches.append(entity)
            regex_match_types.append(regex_pattern.name)

            # Replace with mask token
            mask_token = MaskToken.DEFAULT
            masked_text = (
                masked_text[: match.start()] + mask_token + masked_text[match.end() :]
            )

        # Reverse regex_matches to maintain original order
        regex_matches.reverse()

        # Update context
        context["regex_matches"] = regex_matches
        context["regex_match_types"] = list(set(regex_match_types))
        context["regex_masked_text"] = masked_text

        return context
