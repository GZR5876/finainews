#!/usr/bin/env python3
"""Create data/history.db and its schema if they don't already exist."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "history.db"


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS issues (
            id          TEXT PRIMARY KEY,   -- e.g. finance_001
            week        TEXT NOT NULL,      -- e.g. 2025-W20
            category    TEXT NOT NULL,
            headline    TEXT NOT NULL,
            source_url  TEXT NOT NULL,
            inserted_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_issues_url  ON issues(source_url);
        CREATE INDEX IF NOT EXISTS idx_issues_week ON issues(week);
    """)
    con.commit()
    con.close()
    print(f"DB ready: {DB_PATH}")


if __name__ == "__main__":
    main()
