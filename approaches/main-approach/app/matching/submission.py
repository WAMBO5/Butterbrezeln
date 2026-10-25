"""The challenge submission: build, validate with `tools/validate.py`, score with `score_local.py`."""

from __future__ import annotations

import json
from pathlib import Path

from app.config.settings import Settings
from app.matching.challenge_tools import load_tool
from app.models import Requirement


def to_submission(reqs: list[Requirement], team_id: str, case_id: str) -> dict:
    out = []
    for r in reqs:
        item = {"id": r.id, "text": r.text,
                "source": {"regulation": r.source.regulation, "version": r.source.version, "page": r.source.page,
                           "paragraph": r.source.paragraph}}
        if r.test_case:
            item["test_case"] = r.test_case
        out.append(item)
    return {"team_id": team_id, "case_id": case_id, "requirements": out}


def validate_submission(data: dict, settings: Settings) -> list[str]:
    module = load_tool(settings.challenge_dir, "validate")
    return [str(p) for p in module.validate(data, index=module.load_index(settings.index_path))]


def score_submission(data: dict, expected_path: Path, settings: Settings) -> dict:
    module = load_tool(settings.challenge_dir, "score_local")
    return module.score(data, json.loads(Path(expected_path).read_text(encoding="utf-8")))
