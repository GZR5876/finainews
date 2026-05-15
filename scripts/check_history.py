#!/usr/bin/env python3
"""
Check whether a URL has already been published in a previous issue.

Usage:
    python scripts/check_history.py --url "https://example.com/article"

Exits 0 and prints SEEN if the URL is in history, NEW otherwise.
"""
import argparse
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "history.db"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    args = parser.parse_args()

    if not DB_PATH.exists():
        print("NEW")
        return

    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT week FROM issues WHERE source_url = ? LIMIT 1", (args.url,)
    ).fetchone()
    con.close()

    if row:
        print(f"SEEN (first published {row[0]})")
    else:
        print("NEW")


if __name__ == "__main__":
    main()
