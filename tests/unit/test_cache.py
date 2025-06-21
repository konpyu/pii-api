"""Tests for cache implementations."""

import json
import time

import pytest

from pii_masking.cache.cache_key import generate_cache_key, is_valid_cache_key
from pii_masking.cache.memory_cache import InMemoryCache, MaskingResultCache
from pii_masking.core.exceptions import CacheError
from pii_masking.core.interfaces import MaskingResult


class TestInMemoryCache:
    """Test InMemoryCache class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.cache = InMemoryCache()

    def test_set_and_get(self) -> None:
        """Test basic set and get operations."""
        self.cache.set("key1", "value1")
        assert self.cache.get("key1") == "value1"

    def test_get_nonexistent(self) -> None:
        """Test getting non-existent key."""
        assert self.cache.get("nonexistent") is None

    def test_ttl_expiration(self) -> None:
        """Test TTL expiration."""
        # Set with 0.1 second TTL
        self.cache.set("key1", "value1", ttl=0.1)
        assert self.cache.get("key1") == "value1"

        # Wait for expiration
        time.sleep(0.2)
        assert self.cache.get("key1") is None

    def test_clear_expired(self) -> None:
        """Test clearing expired entries."""
        self.cache.set("key1", "value1", ttl=0.1)
        self.cache.set("key2", "value2", ttl=10)

        # Wait for first key to expire
        time.sleep(0.2)

        removed = self.cache.clear_expired()
        assert removed == 1
        assert self.cache.size() == 1
        assert self.cache.get("key2") == "value2"

    def test_clear_all(self) -> None:
        """Test clearing all entries."""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        assert self.cache.size() == 2

        self.cache.clear()
        assert self.cache.size() == 0
        assert self.cache.get("key1") is None

    def test_access_count(self) -> None:
        """Test access counting."""
        self.cache.set("key1", "value1")

        # Access multiple times
        for _ in range(3):
            self.cache.get("key1")

        stats = self.cache.get_stats()
        assert stats["total_hits"] == 3
        assert stats["hit_distribution"]["key1"] == 3

    def test_overwrite_value(self) -> None:
        """Test overwriting existing value."""
        self.cache.set("key1", "value1")
        self.cache.set("key1", "value2")
        assert self.cache.get("key1") == "value2"


class TestMaskingResultCache:
    """Test MaskingResultCache class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.base_cache = InMemoryCache()
        self.cache = MaskingResultCache(self.base_cache)

    def test_set_and_get_result(self) -> None:
        """Test caching MaskingResult."""
        result = MaskingResult(
            masked_text="<MASK>さんです",
            entities=[],  # Entities not cached
            risk_score=0.7,
            cached=False,
        )

        self.cache.set_result("key1", result)
        cached = self.cache.get_result("key1")

        assert cached is not None
        assert cached.masked_text == result.masked_text
        assert cached.risk_score == result.risk_score
        assert cached.cached is True  # Should be marked as cached

    def test_get_nonexistent_result(self) -> None:
        """Test getting non-existent result."""
        assert self.cache.get_result("nonexistent") is None

    def test_invalid_cached_data(self) -> None:
        """Test handling of invalid cached data."""
        # Manually set invalid JSON
        self.base_cache.set("key1", "invalid json")

        with pytest.raises(CacheError, match="Failed to deserialize"):
            self.cache.get_result("key1")

    def test_incomplete_cached_data(self) -> None:
        """Test handling of incomplete cached data."""
        # Set incomplete data
        self.base_cache.set("key1", json.dumps({"risk_score": 0.5}))

        with pytest.raises(CacheError, match="Failed to deserialize"):
            self.cache.get_result("key1")


class TestCacheKey:
    """Test cache key generation."""

    def test_generate_cache_key(self) -> None:
        """Test cache key generation."""
        key = generate_cache_key("test text")
        assert len(key) == 64  # SHA-256 hex length
        assert all(c in "0123456789abcdef" for c in key)

    def test_generate_cache_key_with_prefix(self) -> None:
        """Test cache key generation with prefix."""
        key = generate_cache_key("test text", prefix="mask")
        assert key.startswith("mask:")
        assert len(key) == 69  # "mask:" + 64 hex chars

    def test_cache_key_deterministic(self) -> None:
        """Test that same input produces same key."""
        text = "田中さんの電話番号"
        key1 = generate_cache_key(text)
        key2 = generate_cache_key(text)
        assert key1 == key2

    def test_cache_key_different_inputs(self) -> None:
        """Test that different inputs produce different keys."""
        key1 = generate_cache_key("text1")
        key2 = generate_cache_key("text2")
        assert key1 != key2

    def test_is_valid_cache_key(self) -> None:
        """Test cache key validation."""
        # Valid keys
        valid_key = generate_cache_key("test")
        assert is_valid_cache_key(valid_key)

        valid_key_with_prefix = generate_cache_key("test", prefix="mask")
        assert is_valid_cache_key(valid_key_with_prefix)

        # Invalid keys
        assert not is_valid_cache_key("too short")
        assert not is_valid_cache_key("not_hex_" + "0" * 56)
        assert not is_valid_cache_key(":no_prefix")
        assert not is_valid_cache_key("0" * 63)  # Wrong length
