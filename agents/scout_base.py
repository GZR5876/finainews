"""
Shared scout agent loop.
Each category scout inherits ScoutConfig and calls run_scout().
"""
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import anthropic

from tools.history import check_history, save_candidate

SCOUT_MODEL = "claude-sonnet-4-6"
MAX_ITERATIONS = 40  # safety ceiling for tool-use turns


@dataclass
class ScoutConfig:
    category: str
    label: str
    sources: list[str]
    search_queries: list[str]
    materiality_criteria: str
    max_atoms: int = 7
    min_score: int = 6


SYSTEM_PROMPT_TEMPLATE = """\
You are an AI news scout for a weekly intelligence briefing.
Your sole audience is the CFO of a major global port operator — \
a senior executive who needs strategic signal, not noise.

Your category this week: **{label}**

## Materiality bar
{materiality_criteria}

## Your task
Search and fetch the news sources below, identify the {max_atoms} most \
material stories from the PAST 7 DAYS, and save each as a candidate atom.

For each atom you save, provide:
- headline: ≤12 words, active voice, data-anchored where possible
- what: 2 sentences — what happened
- so_what: 2 sentences — why a port-operator CFO should care
- score: 1–10 (10 = must-read for this audience)

## Rules
- Only include stories published or significantly updated in the last 7 days.
- Minimum score: {min_score}/10. Do not save below that threshold.
- Before saving, call check_history to avoid repeating stories from the past 6 weeks.
- Save at most {max_atoms} atoms; stop after that limit is reached.
- Do not hallucinate URLs. Only save URLs you have actually fetched or seen.
- Be concise and data-driven. Avoid marketing language.

## Sources to search and fetch
{sources_list}

## Search queries to try
{queries_list}

Start by fetching the sources and running the search queries, then save the best atoms.
When you have saved your atoms (or exhausted good material), stop — output nothing else.
"""


def _build_tool_definitions() -> list[dict]:
    return [
        {
            "name": "check_history",
            "description": (
                "Check whether a URL has already been covered in a recent newsletter. "
                "Returns {seen: bool, headline?, week?}."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The article URL to check."}
                },
                "required": ["url"],
            },
        },
        {
            "name": "save_candidate",
            "description": "Save a news atom to the candidate pool for human review.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "url":      {"type": "string"},
                    "headline": {"type": "string", "description": "≤12 words, active voice."},
                    "what":     {"type": "string", "description": "2 sentences: what happened."},
                    "so_what":  {"type": "string", "description": "2 sentences: why the CFO cares."},
                    "score":    {"type": "number", "description": "1–10 relevance score."},
                },
                "required": ["url", "headline", "what", "so_what", "score"],
            },
        },
    ]


def _dispatch_tool(name: str, inputs: dict, category: str, week_label: str) -> Any:
    if name == "check_history":
        return check_history(inputs["url"])
    if name == "save_candidate":
        return save_candidate(
            url=inputs["url"],
            category=category,
            headline=inputs["headline"],
            what=inputs["what"],
            so_what=inputs["so_what"],
            score=inputs["score"],
            week_label=week_label,
        )
    return {"error": f"Unknown tool: {name}"}


async def run_scout(config: ScoutConfig, week_label: str) -> list[dict]:
    """
    Run the scout agent loop for one category.
    Returns the list of saved candidate dicts.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    system = SYSTEM_PROMPT_TEMPLATE.format(
        label=config.label,
        materiality_criteria=config.materiality_criteria,
        max_atoms=config.max_atoms,
        min_score=config.min_score,
        sources_list="\n".join(f"- {s}" for s in config.sources),
        queries_list="\n".join(f"- {q}" for q in config.search_queries),
    )

    messages: list[dict] = [
        {"role": "user", "content": "Begin your news scouting for this week."}
    ]

    custom_tools = _build_tool_definitions()
    builtin_tools = [
        {"type": "web_search_20250305", "name": "web_search"},
    ]
    all_tools = builtin_tools + custom_tools

    saved: list[dict] = []

    for _ in range(MAX_ITERATIONS):
        response = client.beta.messages.create(
            model=SCOUT_MODEL,
            max_tokens=4096,
            system=system,
            messages=messages,
            tools=all_tools,
            betas=["web-search-2025-03-05"],
        )

        # Append assistant turn
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason != "tool_use":
            break

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name in ("web_search",):
                # Built-in tools: result injected by the API — skip local dispatch
                continue
            result = _dispatch_tool(block.name, block.input, config.category, week_label)
            if block.name == "save_candidate" and result.get("saved"):
                saved.append(block.input | {"item_id": result["item_id"]})
                if len(saved) >= config.max_atoms:
                    # Signal the agent to stop
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result | {"note": "Max atoms reached. Stop saving."}),
                    })
                    messages.append({"role": "user", "content": tool_results})
                    return saved
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    return saved
