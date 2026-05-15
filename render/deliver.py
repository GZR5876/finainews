"""
Render the final newsletter and deliver via Resend.
"""
import json
import os
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).parent
DATA_DIR = Path(__file__).parent.parent / "data"


def _render_html(markdown_text: str, week_label: str) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    tmpl = env.get_template("newsletter.html.j2")
    body_html = markdown.markdown(
        markdown_text, extensions=["extra", "nl2br", "sane_lists"]
    )
    return tmpl.render(week_label=week_label, body_html=body_html)


def render_to_file(markdown_text: str, week_label: str) -> Path:
    html = _render_html(markdown_text, week_label)
    out = DATA_DIR / f"newsletter_{week_label.replace(' ', '_')}.html"
    out.write_text(html)
    print(f"Newsletter rendered → {out}")
    return out


def send_email(markdown_text: str, week_label: str) -> None:
    try:
        import resend
    except ImportError:
        print("resend not installed — skipping email delivery.")
        return

    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print("RESEND_API_KEY not set — skipping email delivery.")
        return

    resend.api_key = api_key
    html = _render_html(markdown_text, week_label)

    params = {
        "from": os.environ["RESEND_FROM"],
        "to": [os.environ["RESEND_TO"]],
        "subject": f"AI Weekly Intelligence · {week_label}",
        "html": html,
    }
    r = resend.Emails.send(params)
    print(f"Email sent: {r}")
