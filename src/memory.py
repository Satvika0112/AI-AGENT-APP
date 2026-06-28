"""
memory.py - the platform's shared memory (the 'learning loop').

Every time a human accepts / edits / rejects a recommendation, we write a
record here. Before recommending, the Planner asks memory for SIMILAR past
cases, so the system gradually learns from real decisions instead of starting
from scratch every time.

Storage is a plain JSON file (data/memory.json) - easy to read, inspect, and
demo. You could later swap this for a vector DB without changing the Planner.
"""
import json
from datetime import datetime, timezone

from config import DATA_DIR

MEMORY_FILE = DATA_DIR / "memory.json"


def _load() -> list:
    """Read all past records. Returns [] if the file doesn't exist yet."""
    if not MEMORY_FILE.exists():
        return []
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []  # corrupt/empty file -> start fresh rather than crash


def _save(records: list) -> None:
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)


def remember(
    customer_id: str,
    situation_type: str,
    action_id: str,
    action_label: str,
    decision: str,          # 'accepted' | 'edited' | 'rejected'
    signals: list = None,
    note: str = "",
) -> dict:
    """Save one human decision to memory and return the record."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "customer_id": customer_id,
        "situation_type": situation_type,
        "action_id": action_id,
        "action_label": action_label,
        "decision": decision,
        "signals": signals or [],
        "note": note,
    }
    records = _load()
    records.append(record)
    _save(records)
    return record


def recall_similar(situation_type: str, signals: list = None, limit: int = 5) -> list:
    """Find past decisions that resemble the current situation.

    Similarity is deliberately simple and explainable:
      +3 points if the situation_type matches (e.g. both 'churn_risk')
      +1 point for each shared signal keyword
    We return the highest-scoring past records, best first.
    """
    signals = set(s.lower() for s in (signals or []))
    scored = []
    for r in _load():
        score = 0
        if r.get("situation_type") == situation_type:
            score += 3
        past_signals = set(s.lower() for s in r.get("signals", []))
        score += len(signals & past_signals)
        if score > 0:
            scored.append((score, r))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [r for _, r in scored[:limit]]


def all_records() -> list:
    """Return the full decision history (newest last) - handy for the UI."""
    return _load()