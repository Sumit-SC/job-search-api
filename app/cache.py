"""
In-memory TTL cache for /jobspy and /rssjobs responses.
Reduces repeated scraping for the same params; single process only.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

logger = __import__("logging").getLogger(__name__)

# TTL seconds
JOBSPY_CACHE_TTL = 15 * 60   # 15 min
RSSJOBS_CACHE_TTL = 10 * 60  # 10 min
MAX_CACHE_ENTRIES = 100


def _make_key(prefix: str, params: Dict[str, Any]) -> str:
    """Stable cache key from param dict (order-independent for same set)."""
    normalized = json.dumps({k: v for k, v in sorted(params.items()) if v is not None}, sort_keys=True)
    return prefix + ":" + hashlib.sha256(normalized.encode()).hexdigest()[:32]


class TTLCache:
    """In-memory cache with TTL and max size (FIFO eviction)."""

    def __init__(self, ttl_seconds: int, max_entries: int = MAX_CACHE_ENTRIES):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._store: OrderedDict[str, Tuple[Any, float]] = OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        now = time.monotonic()
        if key not in self._store:
            return None
        val, expires = self._store[key]
        if now >= expires:
            del self._store[key]
            return None
        self._store.move_to_end(key)  # mark recently used
        return val

    def set(self, key: str, value: Any) -> None:
        now = time.monotonic()
        while len(self._store) >= self.max_entries and self._store:
            self._store.popitem(last=False)
        self._store[key] = (value, now + self.ttl)
        self._store.move_to_end(key)


_jobspy_cache: Optional[TTLCache] = None
_rssjobs_cache: Optional[TTLCache] = None


def get_jobspy_cache() -> TTLCache:
    global _jobspy_cache
    if _jobspy_cache is None:
        _jobspy_cache = TTLCache(ttl_seconds=JOBSPY_CACHE_TTL)
    return _jobspy_cache


def get_rssjobs_cache() -> TTLCache:
    global _rssjobs_cache
    if _rssjobs_cache is None:
        _rssjobs_cache = TTLCache(ttl_seconds=RSSJOBS_CACHE_TTL)
    return _rssjobs_cache


def jobspy_cache_key(
    q: Optional[str],
    location: Optional[str],
    days: int,
    limit: int,
    sites: Optional[str],
    preset: Optional[str],
    country: str,
    is_remote: bool,
) -> str:
    return _make_key(
        "jobspy",
        {
            "q": (q or "").strip().lower(),
            "location": (location or "").strip().lower(),
            "days": days,
            "limit": limit,
            "sites": (sites or "").strip().lower(),
            "preset": (preset or "").strip().lower(),
            "country": (country or "usa").strip().lower(),
            "is_remote": is_remote,
        },
    )


def rssjobs_cache_key(keywords: str, location: str, limit: int) -> str:
    return _make_key(
        "rssjobs",
        {
            "keywords": (keywords or "").strip().lower(),
            "location": (location or "").strip().lower(),
            "limit": limit,
        },
    )
