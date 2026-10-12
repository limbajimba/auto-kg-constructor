"""Tests for the parse cache."""

from __future__ import annotations

from proof.parser.cache import ParseCache
from proof.parser.models import DocumentMetadata, DocumentOutline


def _make_outline() -> DocumentOutline:
    return DocumentOutline(
        metadata=DocumentMetadata(
            title="Test Doc",
            subtitle=None,
            version="v1",
            effective_date=None,
            issuing_body="Test Org",
            total_pages=10,
            document_type="standard",
        ),
        entries=[],
    )


def test_cache_miss_returns_none(tmp_path):
    cache = ParseCache(tmp_path)
    result = cache.load("nonexistent", DocumentOutline)
    assert result is None


def test_cache_roundtrip(tmp_path):
    cache = ParseCache(tmp_path)
    outline = _make_outline()
    cache.save("test_key", outline)
    loaded = cache.load("test_key", DocumentOutline)
    assert loaded is not None
    assert loaded.metadata.title == "Test Doc"


def test_different_keys_are_independent(tmp_path):
    cache = ParseCache(tmp_path)
    outline = _make_outline()
    cache.save("key_a", outline)
    assert cache.load("key_b", DocumentOutline) is None
    assert cache.load("key_a", DocumentOutline) is not None


def test_file_hash_is_deterministic(tmp_path):
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"fake pdf content")

    cache = ParseCache(tmp_path / "cache")
    hash1 = cache.file_hash(test_file)
    hash2 = cache.file_hash(test_file)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex length
