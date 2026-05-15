---
name: weekly-ai-news
description: Generates the weekly AI news executive summary for a port-operator
  CFO. Use when the user asks to "run the weekly AI scan", "draft this week's AI
  newsletter", "find this week's AI news", or starts the weekly briefing workflow.
---

# Weekly AI News -- Procedure

## Setup
- Determine the current ISO week: YYYY-WNN (e.g. 2025-W20).
- Create the issue directory: data/issues/{week}/ if it does not exist.
- Run `python scripts/setup_db.py` to ensure data/history.db exists.
- Read references/audience.md and references/voice.md before writing anything.

## Phase 1: Scout (sequential, one category at a time)

**Start with a digest sweep** before diving into individual sources. Search the
following weekly AI digests for items published in the last 7 days:
- The Rundown AI (therundown.ai)
- TLDR AI (tldr.tech/ai)
- Superhuman AI newsletter (superhuman.ai)
- Ben's Bites (bensbites.com)
- Air Street Press (press.airstreet.com)

Pull any finance-relevant or port-relevant items from the digests into the
candidate pool before proceeding to per-category source searches.

Then work through the four categories in the order below. For each category:

1. Read the corresponding source file (references/sources_{category}.md).
2. Use WebSearch + WebFetch to find items published in the last 7 days.
3. For each candidate item, run: `python scripts/check_history.py --url "{url}"` -- skip any that return `SEEN`.
4. Score each surviving item on three dimensions (1-10 each):
   - **Relevance** to a CFO of a global port operator (apply +1 materiality bonus for finance items per audience.md)
   - **Novelty** -- genuinely new development, not a restatement of old news
   - **Materiality** -- near-term financial or operational impact
5. Drop any item where Relevance < 7 or total score < 21.
6. Keep top 5-8 items per category. Record each as:
   ```
   id: {category}_{NNN}
   headline: ...
   what: (2 sentences -- what happened)
   so_what: (1 sentence -- why a port CFO cares)
   source_url: ...
   scores: { relevance: N, novelty: N, materiality: N, total: N }
   ```

Categories (in scout order -- but finance goes first in the output):
- `finance`    -- references/sources_finance.md   (target 3+ items, 50% of total)
- `agents`     -- references/sources_agents.md
- `physical`   -- references/sources_physical.md
- `foundation` -- references/sources_foundation.md

Also check Anthropic's finance-specific resources:
- https://www.anthropic.com/news/finance-agents (and related Anthropic finance pages)
These pages carry heavier weight -- any named finance agent deployment from
Anthropic should be scored at full value regardless of recency within the last 30 days.

## Phase 2: Candidate review (human checkpoint)

After all categories are scouted:
1. Render the candidates to data/issues/{week}/candidates.html using the template
   `templates/candidates.html.j2` -- pass the full list of scored items.
2. Print a summary table to the terminal: id | category | headline | scores.
3. **STOP.** Tell the user:
   > "Phase 1 complete -- {N} candidates in data/issues/{week}/candidates.html.
   > Review and edit data/issues/{week}/selections.json to choose items and add
   > comments, then tell me to continue."
4. Wait for the user to say "continue" or equivalent before proceeding.

## Phase 3: Polish (human checkpoint)

1. Read data/issues/{week}/selections.json.
2. For each selected item, write a newsletter entry in the voice defined in
   references/voice.md. Hard rules for every item:
   - **Headline**: "Company/who did what" format -- subject + verb + object, max 10
     words, no qualifiers. Write it as a plain text title above the body sentences.
   - **No em dashes** anywhere. Use a comma, colon, or recast the sentence.
   - **Three sentences maximum:**
     1. Bold impact lead -- one sentence stating the operational or financial consequence.
     2. One short context sentence covering the key facts (who, what, scale/evidence).
     3. One action/implication sentence for the CFO's team.
   - **Source URL on its own line** after the three sentences, prefixed with `Source:`.
   - Total target: ~60 words per item, not 120.
3. Assemble into data/issues/{week}/draft.md using the section order from audience.md:
   ```
   ## 1. AI in Finance
   ## 2. AI Agents & Applications
   ## 3. Physical AI
   ## 4. Foundation Models
   ```
   Omit any section with no selected items. Separate items within a section
   with a single blank line. Separate sections with `---`.
4. Optionally include a "Tip of the Week" box at the end: one practical how-to
   tip for using AI in a finance or port operations context, with a source link
   (YouTube video or article). Source from references/sources_tips.md.
5. **STOP.** Tell the user:
   > "Draft ready at data/issues/{week}/draft.md. Edit freely, then tell me to
   > render when ready."
6. Wait for the user to say "render" or equivalent before proceeding.

## Phase 4: Render & archive

1. Run `python scripts/render.py --week {week}` -- produces newsletter.html and
   newsletter.pdf in data/issues/{week}/.
2. The script also inserts all rendered items into data/history.db to prevent
   future duplicates.
3. Report the output paths to the user.
