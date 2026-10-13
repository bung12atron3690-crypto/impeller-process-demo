"""Bounded, expiring, process-local geometry metadata; no uploaded files retained."""
from collections import OrderedDict
from threading import Lock
from time import monotonic
from uuid import uuid4

from .schemas import Analysis

TTL_SECONDS = 1800
MAX_ENTRIES = 32
_cache = OrderedDict()
_lock = Lock()


def save(analysis: Analysis) -> str:
    key = uuid4().hex
    analysis.analysis_id = key
    compact = analysis.model_copy(update={"preview": None}, deep=True)
    with _lock:
        now = monotonic()
        for old in [k for k, (created, _) in _cache.items() if now - created > TTL_SECONDS]:
            del _cache[old]
        _cache[key] = (now, compact)
        while len(_cache) > MAX_ENTRIES:
            _cache.popitem(last=False)
    return key


def get(key: str) -> Analysis | None:
    with _lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        if monotonic() - entry[0] > TTL_SECONDS:
            del _cache[key]
            return None
        return entry[1].model_copy(deep=True)
