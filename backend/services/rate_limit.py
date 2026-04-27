"""
Lightweight rate limiter.
- Uses Redis when REDIS_URL is set (production).
- Falls back to in-process dict (dev / single-instance).

Usage:
    from services.rate_limit import check_or_raise
    check_or_raise('login', identifier=ip, limit=10, window_sec=60)
"""
from __future__ import annotations
import os, time, threading, logging
from typing import Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)

_REDIS_URL = os.environ.get('REDIS_URL', '').strip()
_redis = None
_lock = threading.Lock()
_mem: dict[str, list[float]] = {}                       # key -> [timestamps]

if _REDIS_URL:
    try:
        import redis as _r
        _redis = _r.from_url(_REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        _redis.ping()
        logger.info(f"[rate_limit] Redis connected: {_REDIS_URL}")
    except Exception as e:                              # noqa: BLE001
        logger.warning(f"[rate_limit] Redis unavailable ({e}); using in-memory fallback")
        _redis = None


def _redis_check(bucket: str, identifier: str, limit: int, window_sec: int) -> tuple[bool, int]:
    """Returns (allowed, remaining_after_increment)."""
    key = f"rl:{bucket}:{identifier}"
    try:
        # INCR + EXPIRE on first set
        pipe = _redis.pipeline()
        pipe.incr(key, 1)
        pipe.expire(key, window_sec, nx=True)           # only set TTL on first incr
        count, _ = pipe.execute()
        return (count <= limit, max(0, limit - count))
    except Exception as e:                              # noqa: BLE001
        logger.warning(f"[rate_limit] redis op failed ({e}); falling back in-memory")
        return _mem_check(bucket, identifier, limit, window_sec)


def _mem_check(bucket: str, identifier: str, limit: int, window_sec: int) -> tuple[bool, int]:
    key = f"{bucket}:{identifier}"
    now = time.time()
    cutoff = now - window_sec
    with _lock:
        bucket_list = _mem.get(key, [])
        bucket_list = [t for t in bucket_list if t > cutoff]
        if len(bucket_list) >= limit:
            _mem[key] = bucket_list
            return False, 0
        bucket_list.append(now)
        _mem[key] = bucket_list
        # housekeeping: trim if dict gets large
        if len(_mem) > 5000:
            for k in list(_mem.keys())[:1000]:
                _mem.pop(k, None)
        return True, max(0, limit - len(bucket_list))


def check(bucket: str, identifier: str, limit: int, window_sec: int) -> tuple[bool, int]:
    """Check + increment. Returns (allowed, remaining)."""
    if not identifier:
        return True, limit
    if _redis is not None:
        return _redis_check(bucket, identifier, limit, window_sec)
    return _mem_check(bucket, identifier, limit, window_sec)


def check_or_raise(bucket: str, identifier: str, limit: int, window_sec: int,
                   detail: Optional[str] = None):
    allowed, _ = check(bucket, identifier, limit, window_sec)
    if not allowed:
        msg = detail or f"Too many requests. Try again in {window_sec}s."
        raise HTTPException(status_code=429, detail=msg)


def is_redis_active() -> bool:
    return _redis is not None
