"""
cache.py - a tiny disk cache for decision packets.

Why this exists:
  Each analysis makes several Gemini calls, and the free tier has a small
  per-day cap (429 RESOURCE_EXHAUSTED). Caching lets you analyze a customer once
  and then replay the exact decision packet for free - in the UI or the CLI -
  without spending quota. That keeps a live demo reliable even after you've hit
  the daily limit.

Storage:
  One JSON file per (customer, k) under data/cache/, mirroring the plain-JSON,
  easy-to-inspect approach used by memory.py. Delete a file (or the whole
  folder) to invalidate. data/cache/ is gitignored - it's generated, per-run.

Note:
  A replayed packet is frozen as of when it was computed (including the memory
  hits it recalled at that time). That's expected for a replay; turn the cache
  off, or Clear cache, to force a fresh run.
"""
import json

from config import DATA_DIR

CACHE_DIR = DATA_DIR / "cache"


def _key_path(customer_id: str, k: int):
    """Path to the cache file for one (customer_id, k) pair."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{customer_id}__k{k}.json"


def has(customer_id: str, k: int) -> bool:
    """True if a cached packet exists for (customer_id, k)."""
    return _key_path(customer_id, k).exists()


def load(customer_id: str, k: int):
    """Return the cached packet for (customer_id, k), or None on miss/corruption."""
    path = _key_path(customer_id, k)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None  # corrupt/unreadable -> treat as a miss and run fresh


def save(customer_id: str, k: int, packet: dict) -> dict:
    """Persist a decision packet for (customer_id, k). Best-effort: a cache write
    must never break the pipeline, so failures are swallowed."""
    path = _key_path(customer_id, k)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(packet, f, indent=2)
    except (TypeError, ValueError, OSError):
        pass
    return packet


def clear(customer_id: str = None) -> int:
    """Delete cached packets. With no argument, clears the whole cache; with a
    customer_id, clears only that customer's packets. Returns how many were removed."""
    if not CACHE_DIR.exists():
        return 0
    removed = 0
    for path in CACHE_DIR.glob("*.json"):
        if customer_id is None or path.name.startswith(f"{customer_id}__"):
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    return removed