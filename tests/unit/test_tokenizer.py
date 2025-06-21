"""Tests for Japanese tokenizer."""

from typing import Any, Dict

from pii_masking.processors.tokenizer import JapaneseTokenizer, Token


class TestJapaneseTokenizer:
    """Test JapaneseTokenizer class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.tokenizer = JapaneseTokenizer()

    def test_tokenizer_initialization(self) -> None:
        """Test tokenizer can be initialized."""
        tokenizer = JapaneseTokenizer()
        assert tokenizer.dictionary is not None
        assert tokenizer.tokenizer is not None

    def test_split_modes(self) -> None:
        """Test different split modes."""
        # Test all split modes initialize correctly
        for mode in ["A", "B", "C"]:
            tokenizer = JapaneseTokenizer(split_mode=mode)
            assert tokenizer.split_mode is not None

    def test_process_simple_text(self) -> None:
        """Test tokenization of simple Japanese text."""
        text = "田中さんは東京に住んでいます。"
        context: Dict[str, Any] = {"validated_text": text}
        result = self.tokenizer.process(text, context)

        assert "tokens" in result
        assert "token_surfaces" in result
        assert "token_positions" in result
        assert len(result["tokens"]) > 0

        # Check token structure
        first_token = result["tokens"][0]
        assert isinstance(first_token, Token)
        assert hasattr(first_token, "surface")
        assert hasattr(first_token, "pos")
        assert hasattr(first_token, "start")
        assert hasattr(first_token, "end")

    def test_process_with_masked_text(self) -> None:
        """Test tokenization with pre-masked text."""
        text = "元のテキスト"
        masked_text = "電話番号は<MASK>です。"
        context: Dict[str, Any] = {
            "validated_text": text,
            "regex_masked_text": masked_text,
        }
        result = self.tokenizer.process(text, context)

        # Should use masked text, not original
        assert result["tokenized_text"] == masked_text
        # SudachiPy might split <MASK> into separate tokens
        surfaces = result["token_surfaces"]
        # Check if <MASK> appears as single token or split tokens
        assert "<MASK>" in surfaces or (
            "MASK" in surfaces and "<" in surfaces and ">" in surfaces
        )

    def test_token_positions(self) -> None:
        """Test that token positions are correct."""
        text = "私は日本人です"
        context: Dict[str, Any] = {"validated_text": text}
        result = self.tokenizer.process(text, context)

        tokens = result["tokens"]
        positions = result["token_positions"]

        # Verify positions match token boundaries
        for i, token in enumerate(tokens):
            assert positions[i] == (token.start, token.end)
            # Verify surface text matches position
            assert text[token.start : token.end] == token.surface

    def test_empty_text(self) -> None:
        """Test tokenization of empty text."""
        text = ""
        context: Dict[str, Any] = {"validated_text": text}
        result = self.tokenizer.process(text, context)

        assert result["tokens"] == []
        assert result["token_surfaces"] == []
        assert result["token_positions"] == []

    def test_english_text(self) -> None:
        """Test tokenization of English text."""
        text = "Hello World"
        context: Dict[str, Any] = {"validated_text": text}
        result = self.tokenizer.process(text, context)

        # Should still tokenize English
        assert len(result["tokens"]) > 0
        assert "Hello" in result["token_surfaces"]

    def test_mixed_text(self) -> None:
        """Test tokenization of mixed Japanese and English."""
        text = "私はPythonを使います"
        context: Dict[str, Any] = {"validated_text": text}
        result = self.tokenizer.process(text, context)

        surfaces = result["token_surfaces"]
        assert "私" in surfaces
        assert "Python" in surfaces or "python" in surfaces.lower()

    def test_punctuation_handling(self) -> None:
        """Test handling of punctuation."""
        text = "こんにちは！元気ですか？"
        context: Dict[str, Any] = {"validated_text": text}
        result = self.tokenizer.process(text, context)

        # Punctuation should be tokenized
        surfaces = result["token_surfaces"]
        assert "！" in surfaces or "!" in surfaces
        assert "？" in surfaces or "?" in surfaces
