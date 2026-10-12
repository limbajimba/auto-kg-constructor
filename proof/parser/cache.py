"""SHA-256 based parse cache with automatic invalidation.

Cache entries are JSON files keyed by input file hash. If the PDF
changes (new edition, re-download), the hash changes and all old
cache entries are bypassed — no stale data is ever served.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from proof.log import get_logger

log = get_logger("proof.parser.cache")

T = TypeVar("T", bound=BaseModel)


class ParseCache:
    """Cache parsed results, keyed by input file hash."""

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._hash_memo: dict[str, str] = {}

    def file_hash(self, path: Path) -> str:
        """Compute or return memoized SHA-256 of a file."""
        key = str(path)
        if key not in self._hash_memo:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            self._hash_memo[key] = h.hexdigest()
        return self._hash_memo[key]

    def _cache_path(self, cache_key: str) -> Path:
        """Convert a cache key to a filesystem path."""
        safe_key = cache_key.replace(":", "_").replace("/", "_")
        return self._cache_dir / f"{safe_key}.json"

    def load(self, cache_key: str, model_cls: type[T]) -> T | None:
        """Load a cached result, or None if miss."""
        path = self._cache_path(cache_key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            result = model_cls.model_validate(data)
            log.info("Cache hit: %s", cache_key)
            return result
        except Exception as exc:
            log.warning("Cache read failed for %s: %s", cache_key, exc)
            return None

    def save(self, cache_key: str, model: BaseModel) -> None:
        """Save a result to cache (atomic write via tempfile + rename)."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._cache_path(cache_key)
        fd, tmp = tempfile.mkstemp(dir=self._cache_dir, suffix=".tmp")
        try:
            with open(fd, "w") as f:
                f.write(model.model_dump_json(indent=2))
            Path(tmp).replace(path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        log.info("Cache saved: %s", cache_key)

    def load_raw(self, cache_key: str) -> dict | None:
        """Load a cached raw JSON dict, or None if miss."""
        path = self._cache_path(cache_key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            log.info("Cache hit: %s", cache_key)
            return data
        except Exception as exc:
            log.warning("Cache read failed for %s: %s", cache_key, exc)
            return None

    def save_raw(self, cache_key: str, data: dict) -> None:
        """Save a raw JSON dict to cache (atomic write via tempfile + rename)."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._cache_path(cache_key)
        fd, tmp = tempfile.mkstemp(dir=self._cache_dir, suffix=".tmp")
        try:
            with open(fd, "w") as f:
                f.write(json.dumps(data, indent=2, ensure_ascii=False))
            Path(tmp).replace(path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        log.info("Cache saved: %s", cache_key)
