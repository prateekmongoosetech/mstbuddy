"""
Logs every chat interaction to SQLite for analysis and future training.
Stored at /app/data/conversations.db inside the container (mount as volume).
"""

import sqlite3
import json
import time
from pathlib import Path

DB_PATH = Path("/app/data/conversations.db")


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT    NOT NULL,
                timestamp   REAL    NOT NULL,
                question    TEXT    NOT NULL,
                answer      TEXT    NOT NULL,
                strategy    TEXT,
                sources     TEXT,   -- JSON array
                model       TEXT,
                latency_ms  INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id);
            CREATE INDEX IF NOT EXISTS idx_timestamp ON conversations(timestamp);

            CREATE TABLE IF NOT EXISTS questions_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                question    TEXT    NOT NULL UNIQUE,
                asked_count INTEGER DEFAULT 1,
                first_seen  REAL,
                last_seen   REAL
            );
        """)


def log_conversation(
    session_id: str,
    question: str,
    answer: str,
    strategy: str | None = None,
    sources: list | None = None,
    model: str | None = None,
    latency_ms: int | None = None,
) -> None:
    now = time.time()
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO conversations
               (session_id, timestamp, question, answer, strategy, sources, model, latency_ms)
               VALUES (?,?,?,?,?,?,?,?)""",
            (session_id, now, question, answer, strategy,
             json.dumps(sources or []), model, latency_ms),
        )

        # Upsert into questions_log for frequency tracking
        conn.execute(
            """INSERT INTO questions_log (question, asked_count, first_seen, last_seen)
               VALUES (?, 1, ?, ?)
               ON CONFLICT(question) DO UPDATE SET
                   asked_count = asked_count + 1,
                   last_seen   = excluded.last_seen""",
            (question.strip().lower(), now, now),
        )


def get_stats() -> dict:
    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        unique_sessions = conn.execute(
            "SELECT COUNT(DISTINCT session_id) FROM conversations"
        ).fetchone()[0]
        top_questions = conn.execute(
            """SELECT question, asked_count FROM questions_log
               ORDER BY asked_count DESC LIMIT 20"""
        ).fetchall()
        return {
            "total_conversations": total,
            "unique_sessions": unique_sessions,
            "top_questions": [dict(r) for r in top_questions],
        }


def export_training_jsonl(limit: int = 5000) -> list[dict]:
    """Export conversations as instruction-following pairs for fine-tuning."""
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT question, answer, strategy FROM conversations
               WHERE length(answer) > 50
               ORDER BY timestamp DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [
        {
            "messages": [
                {"role": "user", "content": r["question"]},
                {"role": "assistant", "content": r["answer"]},
            ]
        }
        for r in rows
    ]
