"""Tests for input validator."""

from typing import Any, Dict

import pytest

from pii_masking.core.exceptions import ValidationError
from pii_masking.processors.validator import Validator


class TestValidator:
    """Test Validator class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.validator = Validator()

    def test_valid_text(self) -> None:
        """Test validation of valid text."""
        text = "これは有効なテキストです。"
        context: Dict[str, Any] = {}
        result = self.validator.process(text, context)

        assert result["validated_text"] == text
        assert result["text_length"] == len(text.encode("utf-8"))

    def test_empty_text(self) -> None:
        """Test validation fails for empty text."""
        with pytest.raises(ValidationError, match="too short"):
            self.validator.process("", {})

    def test_none_text(self) -> None:
        """Test validation fails for None text."""
        with pytest.raises(ValidationError, match="text is required"):
            self.validator.process(None, {})  # type: ignore

    def test_non_string_text(self) -> None:
        """Test validation fails for non-string text."""
        with pytest.raises(ValidationError, match="must be a string"):
            self.validator.process(123, {})  # type: ignore

    def test_text_too_long(self) -> None:
        """Test validation fails for text exceeding max length."""
        # Create text longer than 1024 bytes
        long_text = "あ" * 500  # Each Japanese character is ~3 bytes
        with pytest.raises(ValidationError, match="too long"):
            self.validator.process(long_text, {})

    def test_text_length_boundary(self) -> None:
        """Test text at exactly max length passes."""
        # Create text exactly 1024 bytes
        # ASCII characters are 1 byte each
        text = "a" * 1024
        context: Dict[str, Any] = {}
        result = self.validator.process(text, context)

        assert result["validated_text"] == text
        assert result["text_length"] == 1024

    def test_unicode_text(self) -> None:
        """Test validation with various Unicode characters."""
        text = "田中さんの電話番号は03-1234-5678です。😊"
        context: Dict[str, Any] = {}
        result = self.validator.process(text, context)

        assert result["validated_text"] == text
        assert "text_length" in result
