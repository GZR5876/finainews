import yaml
from pathlib import Path
from agents.scout_base import ScoutConfig, run_scout

_cfg = yaml.safe_load((Path(__file__).parent.parent / "sources" / "physical_ai.yaml").read_text())

CONFIG = ScoutConfig(
    category=_cfg["category"],
    label=_cfg["label"],
    sources=_cfg["sources"],
    search_queries=_cfg["search_queries"],
    materiality_criteria=_cfg["materiality_criteria"],
    max_atoms=_cfg["max_atoms"],
    min_score=_cfg["min_score"],
)


async def scout(week_label: str) -> list[dict]:
    return await run_scout(CONFIG, week_label)
