"""Finished runs of the certivity pipeline (the team's requirements engine), read only.

`uv run certivity run <case>` writes one folder per run: manifest.json (input hashes, models, cost),
submission.json, requirements.json, lineage.json (per requirement: part -> fact -> scope decision ->
provision -> obligation -> match decision), scope_plan.json, profile.json, trace.jsonl, state.json
and the hash-chained ledger.jsonl. An uploaded spec is matched to a run by the sha256 the manifest
records for spec.md. Nothing is started from here: a spec without a finished run is an error.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import PIPELINE_CASE_DIRS, PIPELINE_CHECKOUTS, PIPELINE_RUN, PIPELINE_RUN_DIRS
from .models import (Finding, LedgerCheck, LineageLink, PipelineDetail, PipelineRunInfo, Requirement,
                     ScopeExclusion, SpecNote)
from .sources import regulation_title, un_source
from .spec import ParsedSpec
from .trace import TraceRecorder

STEP_ORDER = ["load_case", "analyze", "scope", "collect", "extract", "match", "assemble", "markets", "finalize"]

# per pipeline step: the agent that leads it and what it does, in plain words
STEPS: dict[str, tuple[str, str]] = {
    "load_case": ("pipeline", "Fall und Eingaben geladen"),
    "analyze": ("product_analyst", "Produkt zerlegt: Bauteile, Funktionen, Materialien"),
    "scope": ("scope_narrower", "Vorschriften eingegrenzt"),
    "collect": ("pipeline", "Fundstellen in den Vorschriften gesammelt"),
    "extract": ("obligation_extractor", "Pflichten wörtlich aus den Vorschriften zitiert"),
    "match": ("requirement_matcher", "Pflichten mit den Bauteilen abgeglichen"),
    "assemble": ("output_auditor", "Anforderungen zusammengestellt und geprüft"),
    "markets": ("pipeline", "Märkte geprüft"),
    "finalize": ("pipeline", "Abgabe geschrieben (submission.json, lineage.json)"),
}
AGENT_TASKS: dict[str, str] = {
    "product_analyst": "Produktanalyse",
    "profile_verifier": "Gegenprüfung des Produktprofils",
    "scope_narrower": "Eingrenzung der Vorschriften",
    "recall_auditor": "Gegenprüfung auf übersehene Vorschriften",
    "obligation_extractor": "Pflichten zitieren",
    "requirement_matcher": "Abgleich Pflicht ↔ Bauteil",
    "match_reviewer": "Gegenprüfung des Abgleichs",
    "output_auditor": "Schlussprüfung der Anforderungen",
}
SCOPE_STATE = {"applicable": "anwendbar", "uncertain": "unsicher", "not_applicable": "nicht anwendbar"}


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(text: str) -> str:
    return " ".join(text.split()).lower()


@dataclass(frozen=True)
class RunRef:
    dir: Path
    run_id: str
    case_id: str
    started_at: str
    finished: bool
    spec_sha256: str | None


def runs() -> list[RunRef]:
    """Every pipeline run folder under PIPELINE_RUN_DIRS, oldest first."""
    found: dict[str, RunRef] = {}
    for root in PIPELINE_RUN_DIRS:
        for manifest in [*root.glob("*/manifest.json"), *root.glob("*/runs/*/manifest.json")]:
            try:
                data = _json(manifest)
            except (OSError, ValueError):
                continue  # still being written
            folder = manifest.parent
            run_id = data.get("run_id") or folder.name
            found[run_id] = RunRef(
                dir=folder, run_id=run_id, case_id=run_id.split("Z-", 1)[-1], started_at=data.get("started_at") or "",
                finished=bool(data.get("finished_at")) and all((folder / f).is_file() for f in ("submission.json", "lineage.json")),
                spec_sha256=(data.get("inputs") or {}).get("spec.md"),
            )
    return sorted(found.values(), key=lambda r: r.started_at)


def case_dirs() -> dict[str, Path]:
    """Case id -> folder with spec.md (and the drawing), from the pipeline checkout and our package."""
    found: dict[str, Path] = {}
    for root in PIPELINE_CASE_DIRS:
        for spec in sorted(root.glob("*/spec.md")):
            found.setdefault(spec.parent.name, spec.parent)
    return found


def cases_with_runs() -> dict[str, Path]:
    done = {r.case_id for r in runs() if r.finished}
    return {case: folder for case, folder in case_dirs().items() if case in done}


def match(spec_text: str) -> RunRef | None:
    """The finished run whose input spec.md equals the upload: a pinned one (PIPELINE_RUN), else the latest."""
    sha = hashlib.sha256(spec_text.encode("utf-8")).hexdigest()
    wanted = _norm(spec_text)
    same_case = {case for case, folder in case_dirs().items() if _norm((folder / "spec.md").read_text(encoding="utf-8")) == wanted}
    hits = [r for r in runs() if r.finished and (r.spec_sha256 == sha or r.case_id in same_case)]
    pinned = [r for r in hits if r.run_id in PIPELINE_RUN]
    return (pinned or hits)[-1] if hits else None


def _trace(folder: Path) -> list[dict[str, Any]]:
    path = folder / "trace.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _predecessor(ref: RunRef, own_steps: set[str]) -> RunRef | None:
    """For a replay (tools/replay_from_match.py): the earlier full run whose profile and scope plan it reused."""
    plan = ref.dir / "scope_plan.json"
    if "analyze" in own_steps or not plan.is_file():
        return None
    content = plan.read_bytes()
    for other in reversed(runs()):
        theirs = other.dir / "scope_plan.json"
        if (other.case_id == ref.case_id and other.started_at < ref.started_at and theirs.is_file()
                and theirs.read_bytes() == content and any(e.get("step") == "analyze" for e in _trace(other.dir))):
            return other
    return None


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def verify_ledger(folder: Path) -> LedgerCheck | None:
    """Recomputes the ledger's hash chain, by the rule of the pipeline's app/compliance/ledger.py."""
    path = folder / "ledger.jsonl"
    if not path.is_file():
        return None
    problems: list[str] = []
    prev, n = "0" * 64, 0
    for n, line in enumerate((l for l in path.read_text(encoding="utf-8").splitlines() if l), start=1):
        try:
            record = json.loads(line)
        except ValueError:
            problems.append(f"Eintrag {n}: kein gültiges JSON")
            continue
        body = {k: v for k, v in record.items() if k != "hash"}
        if record.get("seq") != n or record.get("prev_hash") != prev:
            problems.append(f"Eintrag {n}: Verkettung unterbrochen")
        if hashlib.sha256((str(record.get("prev_hash")) + _canonical(body)).encode("utf-8")).hexdigest() != record.get("hash"):
            problems.append(f"Eintrag {n}: Inhalt passt nicht zum Hash")
        prev = record.get("hash", "")
    return LedgerCheck(records=n, intact=not problems, problems=problems[:5], head=prev if n else None)


def _steps(events: list[dict[str, Any]]) -> OrderedDict[str, dict[str, Any]]:
    """step -> {start, end, agents: {agent: totals}}, in the order the steps ran."""
    steps: OrderedDict[str, dict[str, Any]] = OrderedDict()
    current: dict[str, Any] | None = None
    for e in events:
        kind = e.get("event")
        if kind == "step_start":
            current = steps.setdefault(e["step"], {"start": e["ts"], "end": None, "agents": OrderedDict()})
        elif kind == "step_end" and e.get("step") in steps:
            steps[e["step"]]["end"] = e["ts"]
        elif kind in ("agent_start", "agent_end", "agent_error") and current is not None:
            a = current["agents"].setdefault(e["agent"], {"start": e["ts"], "end": e["ts"], "calls": 0, "errors": 0,
                                                          "input": 0, "output": 0, "cost": 0.0, "model": None})
            a["end"] = max(a["end"], e["ts"])
            a["model"] = e.get("model") or a["model"]
            if kind != "agent_start":
                a["calls"] += 1
                a["errors"] += kind == "agent_error"
                usage = e.get("usage") or {}
                a["input"] += usage.get("input", 0)
                a["output"] += usage.get("output", 0)
                a["cost"] += e.get("cost_usd") or 0.0
    return steps


def _money(usd: float) -> str:
    return f"{usd:.2f} $".replace(".", ",")


def _n(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def _agent_output(a: dict[str, Any]) -> str:
    parts = [_n(a["calls"] - a["errors"], "Antwort", "Antworten")]
    if a["errors"]:
        parts.append(f"{a['errors']} ohne lesbare Antwort")
    parts.append(f"{a['input'] + a['output']:,} Tokens".replace(",", "."))
    if a["cost"]:
        parts.append(_money(a["cost"]))
    return " · ".join(parts)


def _step_output(name: str, state: dict[str, Any], profile: dict[str, Any], manifest: dict[str, Any],
                 agents: dict[str, Any]) -> str:
    c = state.get("stage_counts") or {}
    errors = sum(a["errors"] for a in agents.values())
    if name == "load_case":
        return ", ".join(manifest.get("inputs") or {}) or "spec.md"
    if name == "analyze":
        facts = sum(len(p.get("facts") or []) for p in profile.get("parts") or [])
        loop = state.get("profile_loop") or {}
        check = "alles geklärt" if loop.get("resolved") else f"{len(loop.get('open_issues') or [])} Punkte ungeklärt"
        return (f"{len(profile.get('parts') or [])} Bauteile, {facts} Fakten aus der Beschreibung, "
                f"{len(profile.get('unknowns') or [])} offene Punkte · Gegenprüfung in {loop.get('attempts', '?')} Runden: {check}")
    if name == "scope":
        return (f"{c.get('kept_regulations', '?')} von {c.get('regulations', '?')} Vorschriften behalten, "
                f"{c.get('sections', '?')} Abschnitte ausgewählt")
    if name == "collect":
        return f"{c.get('candidate_provisions', '?')} Fundstellen als Kandidaten"
    if name == "extract":
        return f"{c.get('obligations', '?')} Pflichten zitiert" + (f" · {errors} Aufrufe ohne lesbare Antwort" if errors else "")
    if name == "match":
        return (f"{c.get('decisions', '?')} Einzelentscheidungen: {c.get('applicable_decisions', '?')} anwendbar, "
                f"{c.get('uncertain_decisions', '?')} unsicher")
    if name == "assemble":
        issues = len((state.get("output_review") or {}).get("issues") or [])
        return f"{c.get('requirements', '?')} Anforderungen · Schlussprüfung: {issues} Hinweise"
    return ""


def _fact_lines(spec: ParsedSpec, fact: dict[str, Any] | None, summary: str) -> list[int] | None:
    """[line, line] where a fact's quote stands in the spec, if it came from the spec."""
    quote = (fact or {}).get("quote") if (fact or {}).get("source", "spec") == "spec" else None
    if not quote:
        found = re.search(r"\(spec: (.+)\)$", summary)
        quote = found.group(1) if found else None
    if not quote:
        return None
    wanted = _norm(quote)[:60]
    for i, line in enumerate(spec.lines, start=1):
        if wanted and wanted in _norm(line):
            return [i, i]
    return None


def _display_path(folder: Path) -> str:
    for checkout in PIPELINE_CHECKOUTS:
        try:
            return str(folder.relative_to(checkout.parent))
        except ValueError:
            continue
    return str(folder)


@dataclass
class Imported:
    requirements: list[Requirement]
    findings: list[Finding]
    notes: list[SpecNote]
    info: PipelineRunInfo


def import_run(ref: RunRef, spec: ParsedSpec, trace: TraceRecorder, parent: str) -> Imported:
    """Logs the run's steps into our trace (original times) and converts its output to our model."""
    folder = ref.dir
    manifest, state = _json(folder / "manifest.json"), _json(folder / "state.json")
    profile = _json(folder / "profile.json") if (folder / "profile.json").is_file() else {}
    plan = _json(folder / "scope_plan.json") if (folder / "scope_plan.json").is_file() else {}
    provenance = _json(folder / "submission.provenance.json") if (folder / "submission.provenance.json").is_file() else {}
    details = {r["id"]: r for r in _json(folder / "requirements.json")}
    lineage = {x["requirement_id"]: x.get("links") or [] for x in _json(folder / "lineage.json")}
    submitted = _json(folder / "submission.json")["requirements"]

    own = _steps(_trace(folder))
    source = _predecessor(ref, set(own))
    first_own = min((STEP_ORDER.index(s) for s in own if s in STEP_ORDER), default=0)
    earlier = OrderedDict((k, v) for k, v in (_steps(_trace(source.dir)) if source else {}).items()
                          if k in STEP_ORDER and STEP_ORDER.index(k) < first_own)

    ids: dict[str, str] = {}  # "step", "step:agent" and "agent" -> our event id
    times: dict[str, tuple[str, str | None]] = {}
    models: dict[str, str] = {}
    inherited = 0.0  # cost of the steps a replay reused

    def log_steps(steps: OrderedDict[str, dict[str, Any]], origin: RunRef) -> None:
        for name, step in steps.items():
            if name == "markets" and not state.get("markets"):
                continue  # no markets were asked for; our country step does that
            lead, action = STEPS.get(name, ("pipeline", name))
            agents = step["agents"]
            cost = sum(a["cost"] for a in agents.values())
            if origin is not ref:
                nonlocal inherited
                inherited += cost
            tags = {"pipeline_run": origin.run_id, "pipeline_step": name}
            if cost:
                tags["cost_usd"] = f"{cost:.4f}"
            event = trace.replay(
                lead, action, ts_start=step["start"], ts_end=step["end"], parent=parent,
                inputs_summary="" if origin is ref else f"übernommen aus Lauf {origin.run_id}: dieser Lauf hat ab dem Abgleich neu gerechnet",
                outputs_summary=_step_output(name, state, profile, manifest, agents),
                model=", ".join(sorted({a["model"] for a in agents.values() if a["model"]})) or None,
                tokens={"input": sum(a["input"] for a in agents.values()), "output": sum(a["output"] for a in agents.values())} if agents else None,
                tags=tags,
            )
            ids[name], times[name] = event.id, (step["start"], step["end"])
            for agent, a in agents.items():
                child = trace.replay(
                    agent, f"{AGENT_TASKS.get(agent, agent)} · {_n(a['calls'], 'Aufruf', 'Aufrufe')}", ts_start=a["start"], ts_end=a["end"],
                    parent=event.id, outputs_summary=_agent_output(a), model=a["model"],
                    tokens={"input": a["input"], "output": a["output"]},
                    tags={**tags, "cost_usd": f"{a['cost']:.4f}", "calls": str(a["calls"]), "errors": str(a["errors"])},
                )
                ids.setdefault(f"{name}:{agent}", child.id)
                ids.setdefault(agent, child.id)
                if a["model"]:
                    models.setdefault(agent, a["model"])

    if source:
        log_steps(earlier, source)
    log_steps(own, ref)

    # one step per regulation that yields requirements, so every requirement links to why it was kept
    decisions = {d["regulation"]: d for d in plan.get("decisions") or []}
    parts = {p["part_id"]: p for p in profile.get("parts") or []}
    groups: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for item in submitted:
        groups.setdefault(item["source"]["regulation"], []).append(item)
    start, end = times.get("scope", (manifest.get("started_at") or "", None))
    decided = end or start  # the decisions are what the scope step put out
    scope_model = models.get("scope_narrower") or (manifest.get("models") or {}).get("scope_narrower")
    reg_ids: dict[str, str] = {}
    for regulation, group in groups.items():
        d = decisions.get(regulation) or {}
        pages = sorted({g["source"]["page"] for g in group if g["source"].get("page")})
        span = f", Seiten {pages[0]}–{pages[-1]}" if pages else ""
        event = trace.replay(
            "scope_narrower", f"Vorschrift ausgewählt: {regulation} – {regulation_title(regulation)}",
            ts_start=decided, ts_end=decided, parent=ids.get("scope", parent),
            inputs_summary="Bauteile: " + (", ".join(parts[p]["name"] for p in d.get("part_ids") or [] if p in parts) or "–"),
            outputs_summary=f"{SCOPE_STATE.get(d.get('state'), d.get('state', '?'))} ({d.get('path', '?')}): {d.get('reason', '')} "
                            f"→ {len(group)} Anforderungen{span}",
            model=scope_model, sources=[un_source(regulation, group[0]["source"].get("version"))],
            tags={"regulation": regulation, "scope_state": d.get("state", "?"), "pipeline_run": ref.run_id},
        )
        reg_ids[regulation] = event.id
    excluded = [d for d in plan.get("decisions") or [] if d.get("state") == "not_applicable"]
    if excluded:
        trace.replay("scope_narrower", f"{len(excluded)} Vorschriften ausgeschlossen", ts_start=decided, ts_end=decided,
                     parent=ids.get("scope", parent), outputs_summary=", ".join(d["regulation"] for d in excluded),
                     model=scope_model, tags={"pipeline_run": ref.run_id, "excluded": str(len(excluded))})

    facts = {f["fact_id"]: f for p in profile.get("parts") or [] for f in p.get("facts") or []}
    by_link = {
        "part": ids.get("analyze:product_analyst") or ids.get("analyze"),
        "fact": ids.get("analyze:product_analyst") or ids.get("analyze"),
        "provision": ids.get("collect"),
        "obligation": ids.get("extract:obligation_extractor") or ids.get("obligation_extractor") or ids.get("extract"),
        "match_decision": ids.get("match:requirement_matcher") or ids.get("requirement_matcher") or ids.get("match"),
    }
    requirements: list[Requirement] = []
    findings: list[Finding] = []
    for item in submitted:
        rid, src = item["id"], item["source"]
        regulation = src["regulation"]
        detail = details.get(rid) or {}
        links = [
            LineageLink(
                step=link.get("step", ""), ref=link.get("ref", ""), summary=link.get("summary", ""),
                trace_id=reg_ids.get(regulation) if link.get("step") == "scope_decision" else by_link.get(link.get("step", "")),
                spec_lines=_fact_lines(spec, facts.get(link.get("ref", "")), link.get("summary", "")) if link.get("step") == "fact" else None,
            )
            for link in lineage.get(rid, [])
        ]
        test_case = detail.get("test_case") or item.get("test_case") or ""
        requirements.append(Requirement(
            id=rid, text=item["text"], source=un_source(regulation, src.get("version"), src.get("page"), src.get("paragraph")),
            trace_ids=[reg_ids[regulation]],
            pipeline=PipelineDetail(
                state=detail.get("state", "applicable"), reason=detail.get("reason", ""),
                evidence_status=detail.get("evidence_status", ""), test_case=test_case,
                parts=[parts[p]["name"] for p in detail.get("part_ids") or [] if p in parts], lineage=links,
            ),
        ))
        met = detail.get("evidence_status") == "met"
        findings.append(Finding(
            id=f"fd-{rid}", requirement_id=rid, regulation=regulation, status="erfuellt" if met else "offen",
            spec_lines=next((link.spec_lines for link in links if link.spec_lines), None),
            explanation=(detail.get("reason") if met else test_case or detail.get("reason")) or "Im Rahmen der Typprüfung nachzuweisen.",
            trace_ids=[by_link["match_decision"] or reg_ids[regulation]],
        ))

    notes = [SpecNote(id=f"note-{n}", text=f"Ihre Beschreibung lässt offen: {unknown}",
                      trace_ids=[by_link["part"]] if by_link["part"] else [])
             for n, unknown in enumerate(profile.get("unknowns") or [], start=1)]

    if source:
        for agent, model in (_json(source.dir / "manifest.json").get("models") or {}).items():
            models.setdefault(agent, model)
    for agent, model in (manifest.get("models") or {}).items():
        models[agent] = model
    loops = [state.get("profile_loop") or {}, state.get("scope_loop") or {}]
    info = PipelineRunInfo(
        run_id=ref.run_id, case_id=state.get("case_id") or ref.case_id, path=_display_path(folder),
        started_at=manifest.get("started_at"), finished_at=manifest.get("finished_at"), git_commit=manifest.get("git_commit"),
        cost_usd=(manifest.get("cost") or {}).get("spent_usd"), inherited_cost_usd=round(inherited, 4) if source else None,
        models=models,
        funnel={k: v for k, v in (state.get("stage_counts") or {}).items() if isinstance(v, int)},
        product_type=profile.get("product_type"), vehicle_categories=[str(c) for c in profile.get("vehicle_categories") or []],
        parts=[p.get("name") or p.get("part_id", "") for p in profile.get("parts") or []],
        unknowns=list(profile.get("unknowns") or []),
        open_issues=[i.get("reason", "") for loop in loops for i in loop.get("open_issues") or []],
        give_ups=list(state.get("give_ups") or []),
        review_issues=len((state.get("output_review") or {}).get("issues") or []),
        excluded=[ScopeExclusion(regulation=d["regulation"], reason=d.get("reason", "")) for d in excluded],
        score=state.get("score"), replay_of=source.run_id if source else None, ledger=verify_ledger(folder),
        label=provenance.get("label"),
    )
    return Imported(requirements, findings, notes, info)
