import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

CACHE_DB_PATH = "data/mcq_cache.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS quiz_cache (
    cache_key TEXT PRIMARY KEY,
    quiz_json TEXT NOT NULL,
    review TEXT,
    created_at TEXT NOT NULL,
    hits INTEGER NOT NULL DEFAULT 0
);
"""


@contextmanager
def _connect():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(CACHE_DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _init():
    with _connect() as conn:
        conn.execute(_SCHEMA)
        conn.commit()


def make_key(**kwargs) -> str:
    """Deterministic cache key from every input that affects the generated quiz."""
    payload = json.dumps(kwargs, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get(cache_key: str):
    _init()
    with _connect() as conn:
        row = conn.execute(
            "SELECT quiz_json, review FROM quiz_cache WHERE cache_key = ?", (cache_key,)
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE quiz_cache SET hits = hits + 1 WHERE cache_key = ?", (cache_key,)
        )
        conn.commit()
        return {"quiz": row[0], "review": row[1]}


def set(cache_key: str, quiz_json: str, review: str):
    _init()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO quiz_cache (cache_key, quiz_json, review, created_at, hits)
            VALUES (?, ?, ?, ?, 0)
            ON CONFLICT(cache_key) DO UPDATE SET quiz_json=excluded.quiz_json, review=excluded.review
            """,
            (cache_key, quiz_json, review, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()


def stats():
    _init()
    with _connect() as conn:
        total, hits = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(hits), 0) FROM quiz_cache"
        ).fetchone()
        return {"entries": total, "cache_hits_served": hits}


def clear():
    _init()
    with _connect() as conn:
        conn.execute("DELETE FROM quiz_cache")
        conn.commit()
