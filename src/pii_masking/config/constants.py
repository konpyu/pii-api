"""Constants and enums for PII masking pipeline."""

from enum import Enum


class EntityType(str, Enum):
    """Types of entities that can be detected."""

    PERSON = "PERSON"
    LOCATION = "LOCATION"
    ORGANIZATION = "ORGANIZATION"
    DATE = "DATE"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    POSTAL_CODE = "POSTAL_CODE"
    MYNUMBER = "MYNUMBER"
    CREDIT_CARD = "CREDIT_CARD"
    BANK_ACCOUNT = "BANK_ACCOUNT"


class MaskToken(str, Enum):
    """Token used for masking."""

    DEFAULT = "<MASK>"
    PERSON = "<PERSON>"
    PHONE = "<PHONE>"
    EMAIL = "<EMAIL>"


# Default values
DEFAULT_MAX_TEXT_LENGTH = 1024
DEFAULT_CACHE_TTL = 86400  # 24 hours
DEFAULT_MODEL_PATH = "models/distilbert-jp-int8.onnx"
