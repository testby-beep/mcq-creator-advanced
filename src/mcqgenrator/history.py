import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import pandas as pd

DB_PATH = "data/mcq_history.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS quiz_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    subject TEXT NOT NULL,
    tone TEXT NOT NULL,
    question_type TEXT NOT NULL,
    num_questions INTEGER NOT NULL,
    provider TEXT,
    language TEXT,
    total_tokens INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_cost REAL,
    quiz_json TEXT NOT NULL,
    review TEXT
);
"""

_NEW_COLUMNS = {
    "provider": "TEXT",
    "language": "TEXT",
}


@contextmanager
def _connect():
    import os
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with _connect() as conn:
        conn.execute(_SCHEMA)
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(quiz_history)")}
        for col, coltype in _NEW_COLUMNS.items():
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE quiz_history ADD COLUMN {col} {coltype}")
        conn.commit()


def save_quiz_record(
    subject: str,
    tone: str,
    question_type: str,
    num_questions: int,
    quiz_json: str,
    review: str,
    total_tokens: int = None,
    prompt_tokens: int = None,
    completion_tokens: int = None,
    total_cost: float = None,
    provider: str = None,
    language: str = None,
) -> int:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO quiz_history
                (created_at, subject, tone, question_type, num_questions,
                 provider, language, total_tokens, prompt_tokens, completion_tokens,
                 total_cost, quiz_json, review)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                subject,
                tone,
                question_type,
                num_questions,
                provider,
                language,
                total_tokens,
                prompt_tokens,
                completion_tokens,
                total_cost,
                quiz_json,
                review,
            ),
        )
        conn.commit()
        return cur.lastrowid


def get_history_df() -> pd.DataFrame:
    init_db()
    with _connect() as conn:
        df = pd.read_sql_query(
            "SELECT id, created_at, subject, tone, question_type, num_questions, "
            "provider, language, total_tokens, prompt_tokens, completion_tokens, total_cost "
            "FROM quiz_history ORDER BY created_at DESC",
            conn,
        )
    return df


def get_record(record_id: int) -> dict:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM quiz_history WHERE id = ?", (record_id,)
        ).fetchone()
        if row is None:
            return None
        cols = [d[0] for d in conn.execute("SELECT * FROM quiz_history LIMIT 0").description]
        return dict(zip(cols, row))


def clear_history():
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM quiz_history")
        conn.commit()
