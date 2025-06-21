"""Tests for regex processor."""

from typing import Any, Dict

import pytest

from pii_masking.core.exceptions import ProcessingError
from pii_masking.processors.regex import RegexProcessor


class TestRegexProcessor:
    """Test RegexProcessor class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.processor = RegexProcessor()

    def test_load_patterns(self) -> None:
        """Test loading regex patterns from YAML file."""
        patterns = self.processor.patterns
        assert len(patterns) > 0

        # Check some expected patterns
        pattern_names = [p.name for p in patterns]
        assert "phone_number" in pattern_names
        assert "postal_code" in pattern_names
        assert "email" in pattern_names

    def test_process_phone_number(self) -> None:
        """Test detection of phone numbers."""
        text = "連絡先は03-1234-5678です。"
        context: Dict[str, Any] = {"validated_text": text}
        result = self.processor.process(text, context)

        assert result["regex_masked_text"] == "連絡先は<MASK>です。"
        assert len(result["regex_matches"]) == 1
        assert result["regex_matches"][0].text == "03-1234-5678"
        assert result["regex_matches"][0].label == "PHONE_NUMBER"

    def test_process_postal_code(self) -> None:
        """Test detection of postal codes."""
        text = "郵便番号は150-0002です。"
        context: Dict[str, Any] = {"validated_text": text}
        result = self.processor.process(text, context)

        assert result["regex_masked_text"] == "郵便番号は<MASK>です。"
        assert len(result["regex_matches"]) == 1
        assert result["regex_matches"][0].text == "150-0002"
        assert result["regex_matches"][0].label == "POSTAL_CODE"

    def test_process_email(self) -> None:
        """Test detection of email addresses."""
        text = "メールアドレスはtest@example.comです。"
        context: Dict[str, Any] = {"validated_text": text}
        result = self.processor.process(text, context)

        assert result["regex_masked_text"] == "メールアドレスは<MASK>です。"
        assert len(result["regex_matches"]) == 1
        assert result["regex_matches"][0].text == "test@example.com"
        assert result["regex_matches"][0].label == "EMAIL"

    def test_process_multiple_pii(self) -> None:
        """Test detection of multiple PII types."""
        text = "電話は03-1234-5678、郵便番号は150-0002です。"
        context: Dict[str, Any] = {"validated_text": text}
        result = self.processor.process(text, context)

        assert result["regex_masked_text"] == "電話は<MASK>、郵便番号は<MASK>です。"
        assert len(result["regex_matches"]) == 2

        # Check match types
        assert "phone_number" in result["regex_match_types"]
        assert "postal_code" in result["regex_match_types"]

    def test_process_mynumber(self) -> None:
        """Test detection of My Number."""
        text = "マイナンバーは123456789012です。"
        context: Dict[str, Any] = {"validated_text": text}
        result = self.processor.process(text, context)

        assert result["regex_masked_text"] == "マイナンバーは<MASK>です。"
        assert len(result["regex_matches"]) == 1
        assert result["regex_matches"][0].text == "123456789012"

    def test_process_no_pii(self) -> None:
        """Test processing text with no PII."""
        text = "これは個人情報を含まないテキストです。"
        context: Dict[str, Any] = {"validated_text": text}
        result = self.processor.process(text, context)

        assert result["regex_masked_text"] == text
        assert len(result["regex_matches"]) == 0
        assert len(result["regex_match_types"]) == 0

    def test_process_credit_card(self) -> None:
        """Test detection of credit card numbers."""
        text = "カード番号: 1234 5678 9012 3456"
        context: Dict[str, Any] = {"validated_text": text}
        result = self.processor.process(text, context)

        assert result["regex_masked_text"] == "カード番号: <MASK>"
        assert len(result["regex_matches"]) == 1

    def test_invalid_patterns_file(self) -> None:
        """Test handling of invalid patterns file."""
        with pytest.raises(ProcessingError, match="not found"):
            RegexProcessor("/absolute/path/to/nonexistent.yaml")
