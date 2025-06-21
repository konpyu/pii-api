"""Input validation for PII masking pipeline."""

from typing import Any, Dict

from ..config.settings import get_settings
from ..core.exceptions import ValidationError
from ..core.interfaces import Processor


class Validator(Processor):
    """Validates input text before processing."""

    def __init__(self) -> None:
        """Initialize validator with settings."""
        self.settings = get_settings()

    def process(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate input text.

        Args:
            text: Input text to validate
            context: Processing context

        Returns:
            Updated context with validation results

        Raises:
            ValidationError: If validation fails
        """
        # Check if text is None or not a string
        if text is None:
            raise ValidationError("text is required")

        if not isinstance(text, str):
            raise ValidationError("text must be a string")

        # Check text length
        text_bytes = text.encode("utf-8")
        if len(text_bytes) < self.settings.min_text_length:
            raise ValidationError(
                f"text is too short (minimum {self.settings.min_text_length} byte)"
            )

        if len(text_bytes) > self.settings.max_text_length:
            raise ValidationError(
                f"text is too long (maximum {self.settings.max_text_length} bytes)"
            )

        # Update context
        context["validated_text"] = text
        context["text_length"] = len(text_bytes)

        return context
