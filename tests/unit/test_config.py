"""Tests for configuration management."""

import os
from unittest.mock import patch

from pii_masking.config.constants import EntityType, MaskToken
from pii_masking.config.settings import Settings, get_settings


class TestConstants:
    """Test constants and enums."""

    def test_entity_types(self) -> None:
        """Test EntityType enum values."""
        assert EntityType.PERSON == "PERSON"
        assert EntityType.PHONE == "PHONE"
        assert EntityType.EMAIL == "EMAIL"

    def test_mask_tokens(self) -> None:
        """Test MaskToken enum values."""
        assert MaskToken.DEFAULT == "<MASK>"
        assert MaskToken.PERSON == "<PERSON>"


class TestSettings:
    """Test Settings class."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        settings = Settings()
        assert settings.max_text_length == 1024
        assert settings.cache_enabled is True
        assert settings.cache_ttl == 86400
        assert settings.omp_num_threads == 1

    def test_env_override(self) -> None:
        """Test settings can be overridden by environment variables."""
        with patch.dict(
            os.environ, {"MAX_TEXT_LENGTH": "2048", "CACHE_ENABLED": "false"}
        ):
            settings = Settings()
            assert settings.max_text_length == 2048
            assert settings.cache_enabled is False

    def test_model_env_vars(self) -> None:
        """Test model environment variables property."""
        settings = Settings()
        env_vars = settings.model_env_vars
        assert env_vars["OMP_NUM_THREADS"] == "1"
        assert env_vars["ORT_INTRA_OP_NUM_THREADS"] == "4"

    def test_get_settings_singleton(self) -> None:
        """Test get_settings returns the same instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2
