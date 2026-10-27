"""`RunState`: everything a run has decided so far, saved after every step (ENGINEERING.md, Run state).

A run can stop at a checkpoint (assisted mode), be resumed later from this file, and the server
keeps nothing in memory that is not in it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.compliance.lineage import Lineage
from app.models import Issue, MatchDecision, Obligation, ProductProfile, Requirement, ScopePlan

RunStatus = Literal["running", "awaiting_review", "done", "stopped", "failed"]
STATE_FILE = "state.json"


class RunState(BaseModel):
    run_id: str
    run_dir: str
    case_dir: str
    case_id: str
    markets: list[str] = Field(default_factory=list)
    mode: Literal["benchmark", "assisted"] = "benchmark"
    status: RunStatus = "running"
    step: str | None = None
    checkpoint: str | None = None
    checkpoint_errors: list[str] = Field(default_factory=list)
    started_at: str
    finished_at: str | None = None
    git_commit: str | None = None
    parent_run: str | None = None  # set when this run reuses an earlier run's profile and scope
    error: str | None = None

    profile: ProductProfile | None = None
    profile_loop: dict | None = None
    plan: ScopePlan | None = None
    scope_loop: dict | None = None
    safety_hits: list[dict] = Field(default_factory=list)
    pinned_decisions: list[str] = Field(default_factory=list)
    candidates: list[dict] = Field(default_factory=list)
    obligations: dict[str, Obligation] = Field(default_factory=dict)
    decisions: list[MatchDecision] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    held_back: list[Requirement] = Field(default_factory=list)  # uncertain, not in the submission
    lineage: list[Lineage] = Field(default_factory=list)
    output_issues: list[Issue] = Field(default_factory=list)
    output_review: dict | None = None
    give_ups: list[str] = Field(default_factory=list)
    human_actions: list[dict] = Field(default_factory=list)
    markets_result: dict | None = None

    partial: bool = False
    stopped: bool = False
    missing_texts: list[str] = Field(default_factory=list)
    validation_problems: list[str] = Field(default_factory=list)
    score: dict | None = None
    stage_counts: dict = Field(default_factory=dict)
    cost: dict = Field(default_factory=dict)

    def save(self) -> Path:
        path = Path(self.run_dir) / STATE_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(self.model_dump_json(indent=1), encoding="utf-8")
        tmp.replace(path)
        return path

    @classmethod
    def load(cls, run_dir: Path) -> RunState:
        return cls(**json.loads((Path(run_dir) / STATE_FILE).read_text(encoding="utf-8")))
