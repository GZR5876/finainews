"""
Weekly AI news orchestrator.
Entry point: python orchestrator.py [--week YYYY-Www] [--skip-gate1] [--skip-gate2] [--no-email]
"""
import asyncio
import json
import os
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

import click
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

load_dotenv()

from tools.history import (
    init_db,
    get_candidates,
    save_selections,
    get_selected_items,
    save_issue,
)
from agents import foundation, physical_ai, finance, agents_apps
from agents.editor import run_editor
from render.deliver import render_to_file, send_email

DATA_DIR = Path(__file__).parent / "data"
TEMPLATES_DIR = Path(__file__).parent / "gates" / "templates"


def _week_label() -> str:
    now = datetime.utcnow()
    return now.strftime("%Y-W%V")          # e.g. "2025-W20"


def _week_display(label: str) -> str:
    # "2025-W20" → "Week of 12 May 2025"
    try:
        dt = datetime.strptime(label + "-1", "%Y-W%W-%w")
        return dt.strftime("Week of %-d %B %Y")
    except Exception:
        return label


async def _run_scouts(week_label: str) -> dict[str, list]:
    print("⟳  Running 4 scouts in parallel…")
    results = await asyncio.gather(
        foundation.scout(week_label),
        physical_ai.scout(week_label),
        finance.scout(week_label),
        agents_apps.scout(week_label),
        return_exceptions=True,
    )
    scouts = ["foundation", "physical_ai", "finance", "agents_apps"]
    out = {}
    for name, res in zip(scouts, results):
        if isinstance(res, Exception):
            print(f"  ✗ {name} scout failed: {res}")
            out[name] = []
        else:
            print(f"  ✓ {name}: {len(res)} candidates")
            out[name] = res
    return out


CATEGORY_META = {
    "foundation_models": "Foundation Models",
    "physical_ai":       "Physical AI & Robotics",
    "finance_ai":        "AI in Finance",
    "agents_apps":       "AI Agents & Apps",
}


def _render_candidates_html(candidates: list[dict], week_label: str) -> Path:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    tmpl = env.get_template("candidates.html.j2")

    cats_seen = []
    cat_keys = []
    for item in candidates:
        if item["category"] not in cat_keys:
            cat_keys.append(item["category"])
            cats_seen.append({
                "key": item["category"],
                "label": CATEGORY_META.get(item["category"], item["category"]),
            })

    items_enriched = [
        {**item, "label": CATEGORY_META.get(item["category"], item["category"])}
        for item in candidates
    ]

    html = tmpl.render(
        week_label=_week_display(week_label),
        total=len(candidates),
        categories=cats_seen,
        items=items_enriched,
        items_json=json.dumps(items_enriched),
    )
    out = DATA_DIR / "candidates.html"
    out.write_text(html)
    return out


def _gate1_local(candidates: list[dict], week_label: str) -> dict[int, bool]:
    """Serve candidates.html, wait for human to submit selections."""
    html_path = _render_candidates_html(candidates, week_label)
    host = os.getenv("GATE1_HOST", "127.0.0.1")
    port = int(os.getenv("GATE1_PORT", "8765"))

    print(f"\n🌐  Gate 1 ready at http://{host}:{port}")
    print(f"    (or open {html_path} directly and POST manually)")
    webbrowser.open(f"http://{host}:{port}")

    from gates.gate1_server import wait_for_selections
    return wait_for_selections(host, port)


def _gate1_ci(candidates: list[dict], week_label: str) -> dict[int, bool]:
    """
    CI mode: auto-select the top 3 per category by score.
    Used when GATE1_CI=1 (e.g., in GitHub Actions).
    """
    print("⚙  CI mode: auto-selecting top 3 per category.")
    by_cat: dict[str, list] = {}
    for item in candidates:
        by_cat.setdefault(item["category"], []).append(item)

    selected: dict[int, bool] = {}
    for item in candidates:
        selected[item["id"]] = False
    for cat_items in by_cat.values():
        top = sorted(cat_items, key=lambda x: x["scout_score"], reverse=True)[:3]
        for item in top:
            selected[item["id"]] = True
    return selected


def _gate2(draft_path: Path) -> str:
    """Wait for the human to edit draft.md, then return its contents."""
    print(f"\n📝  Gate 2: edit {draft_path} then press Enter to continue…")
    try:
        input()
    except EOFError:
        # non-interactive (CI) — just read it as-is
        pass
    return draft_path.read_text()


@click.command()
@click.option("--week", default=None, help="Week label e.g. 2025-W20 (default: current)")
@click.option("--skip-gate1", is_flag=True, help="Auto-select top 3 per category (CI mode)")
@click.option("--skip-gate2", is_flag=True, help="Skip human editing of draft.md")
@click.option("--no-email", is_flag=True, help="Render HTML but don't send email")
def main(week: str | None, skip_gate1: bool, skip_gate2: bool, no_email: bool):
    week_label = week or _week_label()
    ci_mode = skip_gate1 or os.getenv("GATE1_CI") == "1"

    print(f"\n{'='*60}")
    print(f"  AI Weekly News — {_week_display(week_label)}")
    print(f"{'='*60}\n")

    # Init
    DATA_DIR.mkdir(exist_ok=True)
    init_db()

    # Step 1: Run scouts
    asyncio.run(_run_scouts(week_label))

    # Step 2: Load candidates from DB
    candidates = get_candidates(week_label)
    if not candidates:
        print("No candidates found. Exiting.")
        sys.exit(0)
    print(f"\n📋  {len(candidates)} total candidates surfaced.\n")

    # Step 3: Gate 1
    if ci_mode:
        selections = _gate1_ci(candidates, week_label)
    else:
        selections = _gate1_local(candidates, week_label)

    save_selections(selections, week_label)
    selected = get_selected_items(week_label)
    print(f"\n✓  {len(selected)} items selected for the newsletter.\n")

    if not selected:
        print("No items selected. Exiting.")
        sys.exit(0)

    # Step 4: Editor agent
    print("✍  Running editor (Opus)…")
    draft_md = run_editor(selected, _week_display(week_label))
    draft_path = DATA_DIR / f"draft_{week_label}.md"
    draft_path.write_text(draft_md)
    print(f"   Draft written → {draft_path}\n")

    # Step 5: Gate 2
    if not skip_gate2 and not os.getenv("GATE2_CI"):
        final_md = _gate2(draft_path)
    else:
        final_md = draft_md

    # Step 6: Render + archive
    html_path = render_to_file(final_md, _week_display(week_label))
    save_issue(week_label, final_md, html_path.read_text())

    # Step 7: Deliver
    if not no_email:
        send_email(final_md, _week_display(week_label))

    print(f"\n✅  Done. Newsletter for {_week_display(week_label)} complete.")
    print(f"    HTML: {html_path}")
    print(f"    Draft: {draft_path}")


if __name__ == "__main__":
    main()
