"""
Editor agent: single Opus call.
Takes the human-selected shortlist and emits a polished markdown newsletter.
"""
import json
import os
from datetime import datetime

import anthropic

EDITOR_MODEL = "claude-opus-4-7"

VOICE_SPEC = """\
- Audience: CFO of a global port operator. Assume board-level financial literacy, \
  operational context, and zero tolerance for filler.
- Tone: executive advisory — direct, data-anchored, no hedging, no hype.
- Lead with the so-what (implication), not the event.
- Each item: ~120 words. One punchy headline (≤12 words). \
  Two-sentence "What happened" block. Two-sentence "Why it matters" block. \
  One-sentence "Watch for" forward look. Source link at the end.
- Section order: Foundation Models → Physical AI → AI in Finance → AI Agents & Apps.
- Opening: 3-sentence executive summary of the week's dominant theme.
- Close: one "signal vs. noise" paragraph — what to act on now vs. monitor.
- No bullet points inside items — flowing prose only.
- No marketing language, no "revolutionary", no "game-changing".
"""

SYSTEM_PROMPT = f"""\
You are a senior technology editor writing a weekly AI intelligence briefing \
for a C-suite audience in the global port and logistics sector.

Voice and format specification:
{VOICE_SPEC}

You will receive a JSON list of selected news atoms. \
Produce the complete newsletter in Markdown. \
Do not add any commentary outside the newsletter itself.
"""


def run_editor(selected_items: list[dict], week_label: str) -> str:
    """
    Generate the newsletter draft from selected items.
    Returns markdown string.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Group by category for the prompt
    by_cat: dict[str, list[dict]] = {}
    for item in selected_items:
        by_cat.setdefault(item["category"], []).append(item)

    user_content = (
        f"Week of {week_label}\n\n"
        f"Selected news atoms:\n```json\n{json.dumps(selected_items, indent=2)}\n```\n\n"
        "Write the newsletter now."
    )

    response = client.messages.create(
        model=EDITOR_MODEL,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    return response.content[0].text
