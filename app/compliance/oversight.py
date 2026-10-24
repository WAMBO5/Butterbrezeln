"""Human oversight (design spec section 14.3): checkpoint actions, pinned decisions, sign-off.

Assisted mode pauses at C1 (profile), C2 (scope plan) and C3 (requirements). A reviewer confirms,
edits, overrides (with a reason) or stops. Decisions a human changed are pinned: re-applied on any
re-run. Output counts as reviewed only after a named sign-off (C4), refused while items are open.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.compliance.ledger import Ledger
from app.compliance.lineage import Lineage, LineageLink
from app.compliance.manifest import read_manifest, write_manifest
from app.corpus.store import CorpusStore
from app.models import Part, PartSections, ProductProfile, RegulationDecision, Requirement, ScopePlan

CHECKPOINTS = ("C1_profile", "C2_scope", "C3_requirements")
CHANGES = ("edit", "override")


class HumanAction(BaseModel):
    checkpoint: str
    reviewer: str
    action: Literal["confirm", "edit", "override", "stop"]
    target_id: str | None = None
    reason: str | None = None
    payload: dict | None = None
    ts: str


class SignOff(BaseModel):
    reviewer: str
    ts: str
    statement: str


class OversightError(Exception):
    pass


def validate_actions(actions: list[HumanAction]) -> list[str]:
    errors = []
    for n, a in enumerate(actions, start=1):
        if a.checkpoint not in CHECKPOINTS:
            errors.append(f"action {n}: unknown checkpoint {a.checkpoint}")
        if a.action in CHANGES and not (a.reason or "").strip():
            errors.append(f"action {n}: an {a.action} needs a reason")
        if a.action in CHANGES and not a.target_id:
            errors.append(f"action {n}: an {a.action} needs a target_id")
        if not a.reviewer.strip():
            errors.append(f"action {n}: name the reviewer")
    return errors


def _actions(actions: list, checkpoint: str) -> list[dict]:
    out = [a.model_dump() if isinstance(a, HumanAction) else a for a in actions]
    return [a for a in out if a.get("checkpoint") == checkpoint]


def apply_profile_actions(profile: ProductProfile, actions: list) -> ProductProfile:
    for a in _actions(actions, "C1_profile"):
        payload = a.get("payload") or {}
        if a["action"] not in CHANGES:
            continue
        if "profile" in payload:
            profile = ProductProfile(**payload["profile"])
        elif "part" in payload:
            part = payload["part"]
            others = [p for p in profile.parts if p.part_id != part["part_id"]]
            profile = profile.model_copy(update={"parts": others + [Part(**part)]})
        elif payload.get("remove_part"):
            profile = profile.model_copy(update={"parts": [p for p in profile.parts if p.part_id != a["target_id"]]})
    return profile


def _default_sections(store: CorpusStore | None, regulation: str, version_label: str) -> list[str]:
    if store is None:
        return []
    skip = {"form", "transitional", "administrative", "scope", "definition"}
    return [e.provision_id for e in store.toc(regulation, version_label, 1)
            if e.kind not in skip and not e.paragraph.startswith("Annex")]


def apply_scope_actions(plan: ScopePlan, actions: list, profile: ProductProfile | None = None,
                        store: CorpusStore | None = None) -> ScopePlan:
    decisions = {d.regulation: d for d in plan.decisions}
    for a in _actions(actions, "C2_scope"):
        if a["action"] not in CHANGES or not a.get("target_id"):
            continue
        payload = a.get("payload") or {}
        reg = a["target_id"]
        current = decisions.get(reg)
        state = payload.get("state", current.state if current else "applicable")
        version = payload.get("version_label") or (current.version_label if current else "")
        part_ids = payload.get("part_ids") or (current.part_ids if current and current.part_ids else
                                               [p.part_id for p in profile.parts] if profile else [])
        if "sections" in payload:
            sections = [PartSections(**s) for s in payload["sections"]]
        elif current and current.sections:
            sections = current.sections
        else:
            ids = _default_sections(store, reg, version)
            sections = [PartSections(part_id=p, section_ids=ids) for p in part_ids] if state != "not_applicable" else []
        decisions[reg] = RegulationDecision(
            regulation=reg, version_label=version, state=state,
            path=payload.get("path", current.path if current else "device"),
            part_ids=part_ids if state != "not_applicable" else [],
            sections=sections if state != "not_applicable" else [],
            reason=f"reviewer {a['reviewer']}: {a.get('reason')}", evidence=current.evidence if current else [],
            consolidation_override=a.get("reason") if state != "not_applicable" else None)
    return plan.model_copy(update={"decisions": [decisions[k] for k in sorted(decisions)]})


def apply_pinned(plan: ScopePlan, actions: list) -> ScopePlan:
    """Re-apply scope decisions a reviewer changed, so a re-run never overwrites them silently."""
    return apply_scope_actions(plan, actions) if _actions(actions, "C2_scope") else plan


def _targets(a: dict) -> set[str]:
    payload = a.get("payload") or {}
    return {t for t in [a.get("target_id"), *payload.get("obligation_ids", [])] if t}


def apply_requirement_actions(reqs: list[Requirement], actions: list) -> list[Requirement]:
    out = []
    for r in reqs:
        keep = True
        for a in _actions(actions, "C3_requirements"):
            if a["action"] not in CHANGES or not (_targets(a) & {r.id, *r.obligation_ids}):
                continue
            payload = a.get("payload") or {}
            if payload.get("state") == "not_applicable":
                keep = False
            elif payload.get("state") in ("applicable", "uncertain"):
                r = r.model_copy(update={"state": payload["state"], "reason": f"reviewer {a['reviewer']}: {a.get('reason')}"})
            if payload.get("text"):
                r = r.model_copy(update={"text": str(payload["text"])[:2000]})
        if keep:
            out.append(r)
    return out


def apply_requirement_pins(reqs: list[Requirement], lineages: list[Lineage],
                           actions: list) -> tuple[list[Requirement], list[Lineage]]:
    """C3 actions applied to requirements (matched by obligation id), then numbered again."""
    c3 = _actions(actions, "C3_requirements")
    if not c3:
        return reqs, lineages
    by_id = {l.requirement_id: l for l in lineages}
    kept = apply_requirement_actions(reqs, actions)
    out_reqs, out_lineages = [], []
    for n, r in enumerate(kept, start=1):
        lin = by_id.get(r.id, Lineage(requirement_id=r.id, links=[]))
        links = list(lin.links) + [
            LineageLink(step="human_action", ref=f"{a['checkpoint']}:{a['action']}",
                        summary=f"{a['reviewer']}: {a.get('reason') or ''}")
            for a in c3 if _targets(a) & {r.id, *r.obligation_ids}]
        new_id = f"R-{n:03d}"
        out_reqs.append(r.model_copy(update={"id": new_id}))
        out_lineages.append(Lineage(requirement_id=new_id, links=links))
    return out_reqs, out_lineages


def open_items(reqs: list[Requirement], give_ups: list[str], actions: list | None = None) -> list[str]:
    """Uncertain requirements, verifier disagreements and give-ups that no C3 action decided."""
    acted: set[str] = set()
    for a in _actions(actions or [], "C3_requirements"):
        acted |= _targets(a)
    items = []
    for r in reqs:
        if acted & {r.id, *r.obligation_ids}:
            continue
        if "| reviewer:" in r.reason:
            items.append(f"{r.id}: verifier disagreement — {r.reason[:120]}")
        elif r.state == "uncertain":
            items.append(f"{r.id}: uncertain — {r.reason[:120]}")
    items += [f"G-{n}: {g[:160]}" for n, g in enumerate(give_ups, start=1) if f"G-{n}" not in acted]
    return items


def export_status(run_dir: Path) -> Literal["reviewed", "unreviewed"]:
    return "reviewed" if (Path(run_dir) / "signoff.json").exists() else "unreviewed"


def sign_off(run_dir: Path, reviewer: str, statement: str) -> SignOff:
    from app.compliance.provenance import provenance
    from app.pipeline.state import RunState

    run_dir = Path(run_dir)
    state = RunState.load(run_dir)
    if state.status != "done":
        raise OversightError(f"the run is {state.status}; only a finished run can be signed off")
    if not reviewer.strip():
        raise OversightError("name the reviewer")
    items = open_items(state.requirements, state.give_ups, state.human_actions)
    if items:
        raise OversightError(f"{len(items)} open items need a decision first: " + "; ".join(items[:5]))
    signoff = SignOff(reviewer=reviewer, ts=datetime.now(timezone.utc).isoformat(), statement=statement)
    (run_dir / "signoff.json").write_text(signoff.model_dump_json(indent=1), encoding="utf-8")
    Ledger(run_dir).append("human_action", reviewer, {"checkpoint": "C4_signoff", "action": "signoff",
                                                      "statement": statement}, None, {"checkpoint": "C4_signoff"})
    sidecar = run_dir / "submission.provenance.json"
    models = json.loads(sidecar.read_text(encoding="utf-8")).get("models", {}) if sidecar.exists() else {}
    sidecar.write_text(json.dumps(provenance(state.run_id, state.mode, models, signoff.model_dump()), indent=1),
                       encoding="utf-8")
    manifest = read_manifest(run_dir)
    if manifest is not None:
        write_manifest(run_dir, manifest.model_copy(update={"review": signoff.model_dump()}))
    return signoff
