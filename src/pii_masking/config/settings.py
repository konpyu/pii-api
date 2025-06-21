"""Application settings using pydantic-settings."""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

from .constants import DEFAULT_CACHE_TTL, DEFAULT_MAX_TEXT_LENGTH, DEFAULT_MODEL_PATH


class Settings(BaseSettings):
    """Application configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API Configuration
    max_text_length: int = DEFAULT_MAX_TEXT_LENGTH
    min_text_length: int = 1

    # Model Configuration
    model_path: str = DEFAULT_MODEL_PATH
    omp_num_threads: int = 1
    ort_intra_op_threads: int = 4

    # Cache Configuration
    cache_enabled: bool = True
    cache_ttl: int = DEFAULT_CACHE_TTL

    # Performance
    request_timeout: int = 120  # milliseconds

    # Regex patterns file
    regex_patterns_file: str = "config/regex_patterns.yaml"

    # NER Configuration
    ner_confidence_threshold: float = 0.5

    # Risk scoring weights
    risk_base_score: float = 0.2
    risk_person_single: float = 0.4
    risk_person_multiple: float = 0.7
    risk_regex_increment: float = 0.1

    # Logging
    log_level: str = "INFO"

    @property
    def model_env_vars(self) -> dict[str, str]:
        """Environment variables for ONNX Runtime."""
        return {
            "OMP_NUM_THREADS": str(self.omp_num_threads),
            "ORT_INTRA_OP_NUM_THREADS": str(self.ort_intra_op_threads),
        }


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get cached settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
