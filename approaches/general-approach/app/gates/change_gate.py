"""Code gate for `change_analyst` output: the challenge's own validator with `requirements_old`."""

from __future__ import annotations

from typing import Any

from app.matching.challenge_tools import load_tool
from app.models import ChangeOutput, Issue


def _issue(type_: str, target: str, reason: str) -> Issue:
    return Issue(type=type_, target_id=target, reason=reason, evidence=[], proposed=None)


def change_gate(inp: Any, out: ChangeOutput) -> list[Issue]:
    validate = load_tool(inp.challenge_dir, "validate")
    data = {"team_id": "gate", "case_id": inp.case_id, "changes": [c.model_dump() for c in out.changes]}
    issues = [_issue("validation", p.path, p.message)
              for p in validate.validate(data, kind="subgoal", requirements_old=inp.requirements_old)]
    for n, c in enumerate(out.changes):
        if c.change == "added" and c.requirement_id is not None:
            issues.append(_issue("added_with_id", f"$.changes[{n}]", "an added requirement has requirement_id null"))
        if c.change in ("modified", "added") and not (c.new_text or "").strip():
            issues.append(_issue("missing_text", f"$.changes[{n}]", f"a {c.change} change needs new_text"))
    return issues
