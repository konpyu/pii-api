"""Japanese tokenization using SudachiPy."""

from typing import Any, Dict, List, NamedTuple

from sudachipy import Dictionary, SplitMode

from ..core.exceptions import ProcessingError
from ..core.interfaces import Processor


class Token(NamedTuple):
    """Represents a token from tokenization."""

    surface: str
    pos: List[str]
    start: int
    end: int


class JapaneseTokenizer(Processor):
    """Tokenizes Japanese text using SudachiPy."""

    def __init__(self, split_mode: str = "C") -> None:
        """
        Initialize Japanese tokenizer.

        Args:
            split_mode: Sudachi split mode ("A", "B", or "C").
                       A: Short unit, B: Middle unit, C: Long unit
        """
        try:
            self.dictionary = Dictionary()
            self.tokenizer = self.dictionary.create()

            # Set split mode
            mode_map = {
                "A": SplitMode.A,
                "B": SplitMode.B,
                "C": SplitMode.C,
            }
            self.split_mode = mode_map.get(split_mode.upper(), SplitMode.C)

        except Exception as e:
            raise ProcessingError(f"Failed to initialize tokenizer: {e}")

    def process(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tokenize Japanese text.

        Args:
            text: Input text to tokenize
            context: Processing context containing previous results

        Returns:
            Updated context with tokenization results
        """
        # Get text from context (could be masked by regex)
        input_text = context.get(
            "regex_masked_text", context.get("validated_text", text)
        )

        try:
            # Tokenize text
            morphemes = self.tokenizer.tokenize(input_text, self.split_mode)

            # Convert to Token objects
            tokens = []
            for morpheme in morphemes:
                token = Token(
                    surface=morpheme.surface(),
                    pos=morpheme.part_of_speech(),
                    start=morpheme.begin(),
                    end=morpheme.end(),
                )
                tokens.append(token)

            # Extract useful information for NER
            token_surfaces = [token.surface for token in tokens]
            token_positions = [(token.start, token.end) for token in tokens]

            # Update context
            context["tokens"] = tokens
            context["token_surfaces"] = token_surfaces
            context["token_positions"] = token_positions
            context["tokenized_text"] = input_text  # Keep track of what was tokenized

            return context

        except Exception as e:
            raise ProcessingError(f"Tokenization failed: {e}")
