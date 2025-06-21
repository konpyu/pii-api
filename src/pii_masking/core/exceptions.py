"""Custom exceptions for PII masking pipeline."""


class PIIMaskingError(Exception):
    """Base exception for all PII masking errors."""

    pass


class ValidationError(PIIMaskingError):
    """Raised when input validation fails."""

    pass


class ProcessingError(PIIMaskingError):
    """Raised when processing fails."""

    pass


class ModelLoadError(PIIMaskingError):
    """Raised when model loading fails."""

    pass


class CacheError(PIIMaskingError):
    """Raised when cache operations fail."""

    pass
