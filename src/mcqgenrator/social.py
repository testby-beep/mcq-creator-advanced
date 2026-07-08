import os
import random
import sqlite3
import string
from contextlib import contextmanager
from datetime import datetime, timezone

import pandas as pd

DB_PATH = "data/mcq_social.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS quiz_shares (
    code TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    tone TEXT NOT NULL,
    question_type TEXT NOT NULL,
    quiz_json TEXT NOT NULL,
    review TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leaderboard (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    player_name TEXT NOT NULL,
    score INTEGER NOT NULL,
    total INTEGER NOT NULL,
    seconds_taken REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS question_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT,
    subject TEXT,
    question_text TEXT NOT NULL,
    correct INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


@contextmanager
def _connect():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def _generate_code(length=6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choices(alphabet, k=length))


def create_share(subject: str, tone: str, question_type: str, quiz_json: str, review: str) -> str:
    init_db()
    code = _generate_code()
    with _connect() as conn:
        # extremely unlikely collision, but guard anyway
        while conn.execute("SELECT 1 FROM quiz_shares WHERE code = ?", (code,)).fetchone():
            code = _generate_code()
        conn.execute(
            "INSERT INTO quiz_shares (code, subject, tone, question_type, quiz_json, review, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (code, subject, tone, question_type, quiz_json, review, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    return code


def get_share(code: str):
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT code, subject, tone, question_type, quiz_json, review FROM quiz_shares WHERE code = ?",
            (code.strip().upper(),),
        ).fetchone()
        if row is None:
            return None
        cols = ["code", "subject", "tone", "question_type", "quiz_json", "review"]
        return dict(zip(cols, row))


def submit_score(code: str, player_name: str, score: int, total: int, seconds_taken: float = None):
    init_db()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO leaderboard (code, player_name, score, total, seconds_taken, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (code, player_name, score, total, seconds_taken, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()


def get_leaderboard(code: str) -> pd.DataFrame:
    init_db()
    with _connect() as conn:
        return pd.read_sql_query(
            "SELECT player_name, score, total, seconds_taken, created_at FROM leaderboard "
            "WHERE code = ? ORDER BY score DESC, seconds_taken ASC",
            conn,
            params=(code,),
        )


def log_attempt(question_text: str, correct: bool, subject: str = "", code: str = None):
    init_db()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO question_attempts (code, subject, question_text, correct, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (code, subject, question_text, int(correct), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()


def hardest_questions(limit: int = 10) -> pd.DataFrame:
    """Questions with the lowest correct-answer rate, across all attempts."""
    init_db()
    with _connect() as conn:
        df = pd.read_sql_query(
            "SELECT question_text, subject, COUNT(*) as attempts, "
            "SUM(correct) as correct_count "
            "FROM question_attempts GROUP BY question_text HAVING attempts >= 1",
            conn,
        )
    if df.empty:
        return df
    df["accuracy"] = (df["correct_count"] / df["attempts"] * 100).round(1)
    return df.sort_values(["accuracy", "attempts"], ascending=[True, False]).head(limit)
