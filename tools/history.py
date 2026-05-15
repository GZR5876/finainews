"""
SQLite-backed tools shared across all scout agents.
Three tables: items, selections, issues.
"""
import hashlib
import json
import sqlite3
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "news.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url         TEXT NOT NULL,
            url_hash    TEXT NOT NULL UNIQUE,
            category    TEXT NOT NULL,
            headline    TEXT,
            what        TEXT,
            so_what     TEXT,
            scout_score REAL,
            surfaced_at TEXT NOT NULL,
            week_label  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS selections (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id     INTEGER NOT NULL REFERENCES items(id),
            selected    INTEGER NOT NULL DEFAULT 0,
            week_label  TEXT NOT NULL,
            selected_at TEXT
        );

        CREATE TABLE IF NOT EXISTS issues (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            week_label  TEXT NOT NULL UNIQUE,
            markdown    TEXT,
            html        TEXT,
            created_at  TEXT NOT NULL
        );
        """)


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().encode()).hexdigest()[:16]


def check_history(url: str, weeks: int = 6) -> dict:
    """Return whether this URL has been surfaced in the past `weeks` weeks."""
    h = _url_hash(url)
    cutoff = (datetime.utcnow() - timedelta(weeks=weeks)).isoformat()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT headline, surfaced_at, week_label FROM items "
            "WHERE url_hash = ? AND surfaced_at >= ?",
            (h, cutoff),
        ).fetchone()
    if row:
        return {"seen": True, "headline": row["headline"], "week": row["week_label"]}
    return {"seen": False}


def save_candidate(
    url: str,
    category: str,
    headline: str,
    what: str,
    so_what: str,
    score: float,
    week_label: str,
) -> dict:
    """Persist a candidate news atom. Returns the item id."""
    h = _url_hash(url)
    now = datetime.utcnow().isoformat()
    try:
        with _get_conn() as conn:
            cur = conn.execute(
                """INSERT OR IGNORE INTO items
                   (url, url_hash, category, headline, what, so_what,
                    scout_score, surfaced_at, week_label)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (url, h, category, headline, what, so_what, score, now, week_label),
            )
            item_id = cur.lastrowid
        return {"saved": True, "item_id": item_id}
    except Exception as e:
        return {"saved": False, "error": str(e)}


def get_candidates(week_label: str) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM items WHERE week_label = ? ORDER BY scout_score DESC",
            (week_label,),
        ).fetchall()
    return [dict(r) for r in rows]


def save_selections(selections: dict[int, bool], week_label: str) -> None:
    """selections: {item_id: True/False}"""
    now = datetime.utcnow().isoformat()
    with _get_conn() as conn:
        for item_id, selected in selections.items():
            conn.execute(
                """INSERT OR REPLACE INTO selections
                   (item_id, selected, week_label, selected_at)
                   VALUES (?,?,?,?)""",
                (item_id, 1 if selected else 0, week_label, now if selected else None),
            )


def get_selected_items(week_label: str) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT i.* FROM items i
               JOIN selections s ON s.item_id = i.id
               WHERE s.selected = 1 AND s.week_label = ?
               ORDER BY i.category, i.scout_score DESC""",
            (week_label,),
        ).fetchall()
    return [dict(r) for r in rows]


def save_issue(week_label: str, markdown: str, html: str) -> None:
    now = datetime.utcnow().isoformat()
    with _get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO issues (week_label, markdown, html, created_at)
               VALUES (?,?,?,?)""",
            (week_label, markdown, html, now),
        )
