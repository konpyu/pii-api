"""Named Entity Recognition using ONNX models."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import onnxruntime as ort

from ..config.constants import EntityType
from ..config.settings import get_settings
from ..core.exceptions import ModelLoadError, ProcessingError
from ..core.interfaces import Entity, Processor


class NERProcessor(Processor):
    """Performs Named Entity Recognition using ONNX models."""

    # Mock gazetteer for testing (replace with actual NER model in production)
    MOCK_PERSON_NAMES: Set[str] = {
        "佐藤",
        "鈴木",
        "高橋",
        "田中",
        "山田",
        "渡辺",
        "伊藤",
        "中村",
    }
    MOCK_LOCATIONS: Set[str] = {"東京", "大阪", "京都", "北海道", "沖縄", "福岡"}
    MOCK_ORGANIZATIONS: Set[str] = {"トヨタ", "ソニー", "任天堂", "東京大学", "NHK"}

    def __init__(self, model_path: Optional[str] = None, use_mock: bool = True) -> None:
        """
        Initialize NER processor.

        Args:
            model_path: Path to ONNX model file. If None, uses default from settings.
            use_mock: If True, use mock NER instead of ONNX model (for testing).
        """
        self.settings = get_settings()
        self.use_mock = use_mock
        self.session: Optional[ort.InferenceSession] = None

        if not use_mock:
            # Load ONNX model
            model_file = model_path or self.settings.model_path
            self._load_model(model_file)

    def _load_model(self, model_path: str) -> None:
        """Load ONNX model file."""
        model_file = Path(model_path)

        # Check if path is absolute
        if not model_file.is_absolute():
            # Try relative to project root
            project_root = Path(__file__).parent.parent.parent.parent
            model_file = project_root / model_path

        if not model_file.exists():
            # Try relative to models directory
            model_file = Path(__file__).parent.parent / "models" / Path(model_path).name

        if not model_file.exists():
            raise ModelLoadError(f"Model file not found: {model_path}")

        try:
            # Set environment variables for ONNX Runtime
            for key, value in self.settings.model_env_vars.items():
                os.environ[key] = value

            # Create inference session
            self.session = ort.InferenceSession(
                str(model_file),
                providers=["CPUExecutionProvider"],
            )

        except Exception as e:
            raise ModelLoadError(f"Failed to load ONNX model: {e}")

    def _run_ner_inference(self, tokens: List[str]) -> List[Dict[str, Any]]:
        """
        Run NER inference on tokenized text.

        Args:
            tokens: List of token strings

        Returns:
            List of NER predictions
        """
        if self.use_mock:
            return self._mock_ner_inference(tokens)

        if self.session is None:
            raise ProcessingError("Model not loaded")

        # TODO: Implement actual ONNX inference
        # This would involve:
        # 1. Convert tokens to model input format
        # 2. Run inference
        # 3. Post-process outputs to extract entities
        raise NotImplementedError("ONNX inference not yet implemented")

    def _mock_ner_inference(self, tokens: List[str]) -> List[Dict[str, Any]]:
        """Mock NER inference using gazetteers."""
        entities = []

        for i, token in enumerate(tokens):
            entity_type = None

            if token in self.MOCK_PERSON_NAMES:
                entity_type = EntityType.PERSON
            elif token in self.MOCK_LOCATIONS:
                entity_type = EntityType.LOCATION
            elif token in self.MOCK_ORGANIZATIONS:
                entity_type = EntityType.ORGANIZATION

            if entity_type:
                entities.append(
                    {
                        "token_index": i,
                        "text": token,
                        "label": entity_type,
                        "confidence": 0.9,  # Mock confidence
                    }
                )

        return entities

    def process(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply NER to detect entities.

        Args:
            text: Input text (not used directly, uses tokens from context)
            context: Processing context containing tokenization results

        Returns:
            Updated context with NER entities
        """
        # Get tokens from context
        if "token_surfaces" not in context:
            raise ProcessingError("Tokenization required before NER")

        tokens = context["token_surfaces"]
        token_positions = context.get("token_positions", [])

        # Run NER inference
        try:
            ner_predictions = self._run_ner_inference(tokens)
        except Exception as e:
            raise ProcessingError(f"NER inference failed: {e}")

        # Convert predictions to Entity objects
        ner_entities: List[Entity] = []
        for pred in ner_predictions:
            token_idx = pred["token_index"]

            # Get position from original text
            if token_idx < len(token_positions):
                start, end = token_positions[token_idx]
            else:
                # Fallback if positions not available
                start = 0
                end = len(pred["text"])

            entity = Entity(
                text=pred["text"],
                label=pred["label"],
                start=start,
                end=end,
                confidence=pred.get("confidence", 1.0),
            )
            ner_entities.append(entity)

        # Update context
        context["ner_entities"] = ner_entities
        context["ner_performed"] = True

        return context
