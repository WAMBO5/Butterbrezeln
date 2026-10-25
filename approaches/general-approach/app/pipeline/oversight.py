"""Resume an assisted run at its checkpoint with the reviewer's actions (design spec 14.3)."""

from __future__ import annotations

from pathlib import Path

from app.compliance.ledger import Ledger
from app.compliance.oversight import (HumanAction, OversightError, apply_profile_actions,
                                      apply_requirement_pins, apply_scope_actions, validate_actions)
from app.config.settings import Settings, load_settings
from app.pipeline.main import RunDeps, RunResult, drive, result_of
from app.pipeline.state import RunState


async def resume_run(run_dir: Path, checkpoint: str, actions: list[HumanAction], *, settings: Settings | None = None,
                     deps: RunDeps | None = None, listeners: list | None = None) -> RunResult:
    state = RunState.load(Path(run_dir))
    if state.status != "awaiting_review" or state.checkpoint != checkpoint:
        raise OversightError(f"run is {state.status} at checkpoint {state.checkpoint}, not waiting at {checkpoint}")
    errors = validate_actions(actions)
    if errors:  # re-ask: the run stays at its checkpoint with the errors
        state.checkpoint_errors = errors
        state.save()
        return result_of(state)
    settings = settings or load_settings()
    deps = deps or RunDeps.load(settings)
    ledger = Ledger(Path(run_dir))
    by_id = {r.id: r for r in state.requirements}
    for a in actions:
        record = a.model_dump()
        if checkpoint == "C3_requirements" and a.target_id in by_id:
            record["payload"] = {**(a.payload or {}), "obligation_ids": by_id[a.target_id].obligation_ids}
        ledger.append("human_action", a.reviewer, record, None, {"checkpoint": checkpoint, "action": a.action})
        state.human_actions.append(record)
    state.checkpoint_errors = []
    if any(a.action == "stop" for a in actions):
        state.stopped = True
    elif checkpoint == "C1_profile":
        state.profile = apply_profile_actions(state.profile, state.human_actions)
    elif checkpoint == "C2_scope":
        state.plan = apply_scope_actions(state.plan, state.human_actions, state.profile, deps.store)
        changed = [a.target_id for a in actions if a.action in ("edit", "override") and a.target_id]
        state.pinned_decisions = sorted(set(state.pinned_decisions) | set(changed))
    elif checkpoint == "C3_requirements":
        state.requirements, state.lineage = apply_requirement_pins(state.requirements, state.lineage,
                                                                   state.human_actions)
    state.save()
    return await drive(state, deps, listeners)
