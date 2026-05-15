#!/usr/bin/env python3
"""
Render the polished draft into newsletter.html (and optionally newsletter.pdf),
then archive the published items into data/history.db.

Usage:
    python scripts/render.py --week 2025-W20

Requires: jinja2, markdown, weasyprint (optional — PDF skipped if not installed)
"""
import argparse
import json
import sqlite3
from datetime import datetime, date
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    raise SystemExit("Missing dependency: pip install jinja2")

try:
    import markdown as md_lib
except ImportError:
    raise SystemExit("Missing dependency: pip install markdown")

ROOT = Path(__file__).parent.parent
TEMPLATES = ROOT / "templates"
DATA = ROOT / "data"
DB_PATH = DATA / "history.db"

SECTION_MAP = {
    "foundation": "1. Foundation Models",
    "physical":   "2. Physical AI",
    "finance":    "3. AI in Finance",
    "agents":     "4. AI Agents & Applications",
}


def load_selections(week: str) -> list[dict]:
    path = DATA / "issues" / week / "selections.json"
    if not path.exists():
        raise SystemExit(f"selections.json not found at {path}")
    return json.loads(path.read_text())


def load_candidates(week: str) -> dict[str, dict]:
    path = DATA / "issues" / week / "candidates.json"
    if not path.exists():
        raise SystemExit(f"candidates.json not found at {path}")
    items = json.loads(path.read_text())
    return {item["id"]: item for item in items}


def load_draft(week: str) -> str:
    path = DATA / "issues" / week / "draft.md"
    if not path.exists():
        raise SystemExit(f"draft.md not found at {path}")
    return path.read_text()


def parse_draft_sections(draft_md: str, selections: list[dict], candidates: dict) -> list[dict]:
    """
    Split draft.md on section headers and map body text back to selected items.
    Returns a list of section dicts ready for the Jinja2 template.
    """
    import re

    # Build a lookup: category -> ordered list of selected ids
    cat_order = list(SECTION_MAP.keys())
    selected_by_cat: dict[str, list[dict]] = {c: [] for c in cat_order}
    for sel in selections:
        item_id = sel["id"]
        category = item_id.rsplit("_", 1)[0]
        candidate = candidates.get(item_id, {})
        selected_by_cat.setdefault(category, []).append({
            "id": item_id,
            "headline": candidate.get("headline", item_id),
            "source_url": candidate.get("source_url", ""),
            "user_comment": sel.get("user_comment"),
        })

    # Split draft on ## headers
    blocks = re.split(r"^(##\s+.+)$", draft_md, flags=re.MULTILINE)
    # blocks: ['preamble', '## 1. Foundation Models', 'body...', '## 2. ...', ...]
    section_bodies: dict[str, str] = {}
    for i in range(1, len(blocks) - 1, 2):
        header = blocks[i]
        body = blocks[i + 1].strip() if i + 1 < len(blocks) else ""
        for cat, label in SECTION_MAP.items():
            if label.lower() in header.lower():
                section_bodies[cat] = body
                break

    sections = []
    for cat in cat_order:
        sel_items = selected_by_cat.get(cat, [])
        if not sel_items:
            continue
        body_md = section_bodies.get(cat, "")
        # Split body into per-item blocks by blank lines between paragraphs
        # We trust the draft has one block per item in order
        paras = [p.strip() for p in re.split(r"\n{2,}", body_md) if p.strip()]
        rendered_items = []
        for idx, meta in enumerate(sel_items):
            body_text = paras[idx] if idx < len(paras) else ""
            rendered_items.append({
                "headline": meta["headline"],
                "body_html": md_lib.markdown(body_text),
                "source_url": meta["source_url"],
            })
        sections.append({"label": SECTION_MAP[cat], "items": rendered_items})

    return sections


def archive_to_db(week: str, selections: list[dict], candidates: dict):
    if not DB_PATH.exists():
        return
    con = sqlite3.connect(DB_PATH)
    for sel in selections:
        item_id = sel["id"]
        candidate = candidates.get(item_id, {})
        category = item_id.rsplit("_", 1)[0]
        try:
            con.execute(
                "INSERT OR IGNORE INTO issues (id, week, category, headline, source_url) "
                "VALUES (?, ?, ?, ?, ?)",
                (item_id, week, category,
                 candidate.get("headline", ""), candidate.get("source_url", "")),
            )
        except sqlite3.Error:
            pass
    con.commit()
    con.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", required=True, help="ISO week string, e.g. 2025-W20")
    args = parser.parse_args()
    week = args.week

    issue_dir = DATA / "issues" / week
    issue_dir.mkdir(parents=True, exist_ok=True)

    selections = load_selections(week)
    candidates = load_candidates(week)
    draft_md   = load_draft(week)
    sections   = parse_draft_sections(draft_md, selections, candidates)

    issue_date = date.today().strftime("%d %B %Y")

    env = Environment(loader=FileSystemLoader(str(TEMPLATES)))
    tmpl = env.get_template("newsletter.html.j2")
    html = tmpl.render(week=week, issue_date=issue_date, sections=sections,
                       generated_at=datetime.now().isoformat(timespec="minutes"))

    html_path = issue_dir / "newsletter.html"
    html_path.write_text(html)
    print(f"HTML: {html_path}")

    # Optional PDF via WeasyPrint
    try:
        from weasyprint import HTML as WP_HTML
        pdf_path = issue_dir / "newsletter.pdf"
        WP_HTML(string=html, base_url=str(issue_dir)).write_pdf(str(pdf_path))
        print(f"PDF : {pdf_path}")
    except ImportError:
        print("PDF skipped (weasyprint not installed; run: pip install weasyprint)")

    archive_to_db(week, selections, candidates)
    print("Archived to history.db")


if __name__ == "__main__":
    main()
