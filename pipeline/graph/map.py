"""Product run as one LangGraph graph.

components -> functionalities -> connect -> applicability -> retrieve (+ section expansion) -> triage -> judge
  -> coverage (back to retrieve with rewritten queries, max 3 rounds) -> cross-references -> writer -> verify/export
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from pipeline import config, llm, prompts
from pipeline.catalog.cards import cards
from pipeline.catalog.corpus import provisions
from pipeline.catalog.parse import Provision
from pipeline.graph import product
from pipeline.models import (DraftRequirements, JudgeDecisions, ProductProfile, QueryRewrites, RouteDecisions,
                             TriageGrades)
from pipeline.rag import store

MAX_ROUNDS = 3
CONNECT_K = 200
PROVISION_K = 40
SECTION_CAP = 80
TRIAGE_BATCH = 40
JUDGE_BATCH = 20
WRITER_BATCH = 8


class RunState(TypedDict, total=False):
    case_id: str
    case_dir: str
    run_dir: str
    export_uncertain: bool
    profile: dict
    functionalities: list[dict]
    queries: dict[str, list[str]]        # functionality id -> queries for the current round
    round: int
    route: list[dict]
    regulations: list[str]               # applicable or uncertain after supersession
    candidates: list[str]                # provision ids waiting for triage and judging
    hits: dict[str, list[str]]           # provision id -> queries that hit it
    seen: list[str]                      # provision ids already judged or triaged out
    triage_dropped: list[str]            # provision ids triage dropped (can return if a later query hits them directly)
    forced: list[str]                    # this round: previously dropped, now hit directly -> straight to the judge
    decisions: dict[str, dict]           # provision id -> judge decision
    xrefs: dict[str, str]
    drafts: list[dict]
    result: dict


# --- helpers ---------------------------------------------------------------------------------------------

def provision(pid: str) -> Provision:
    reg, ver, _ = pid.split("|", 2)
    return _by_id(reg, ver)[pid]


_ID_CACHE: dict[tuple[str, str], dict[str, Provision]] = {}


def _by_id(reg: str, ver: str) -> dict[str, Provision]:
    if (reg, ver) not in _ID_CACHE:
        _ID_CACHE[(reg, ver)] = {p.provision_id: p for p in provisions(reg, ver)}
    return _ID_CACHE[(reg, ver)]


def _log(state: RunState, stage: str, **data: Any) -> None:
    with open(Path(state["run_dir"]) / "trace.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": round(time.time(), 2), "stage": stage, **data}, ensure_ascii=False) + "\n")
    print(f"[{stage}] " + ", ".join(f"{k}={v}" for k, v in data.items() if not isinstance(v, (list, dict))), flush=True)


def _write(state: RunState, name: str, data: Any) -> None:
    path = Path(state["run_dir"]) / name
    if name.endswith(".jsonl"):
        path.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in data), encoding="utf-8")
    else:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _block(ref: str, p: Provision, limit: int) -> str:
    head = " > ".join(p.heading_path)
    text = p.text if len(p.text) <= limit else p.text[:limit] + " [...]"
    return f"<provision ref=\"{ref}\" regulation=\"{p.regulation}\" version=\"{p.version_label}\" paragraph=\"{p.paragraph}\">\nheading: {head}\n{text}\n</provision>"


def _profile_text(state: RunState) -> str:
    return ("Product profile:\n" + json.dumps(state["profile"], ensure_ascii=False)
            + "\n\nFunctionalities:\n" + json.dumps([{k: f[k] for k in ("id", "statement", "component_ids")}
                                                     for f in state["functionalities"]], ensure_ascii=False))


_FAILED: Counter = Counter()


async def _safe(state: RunState, stage: str, coro, default):
    """One failed LLM batch degrades the run instead of aborting it; the failure is traced and counted."""
    try:
        return await coro
    except llm.LLMError as exc:
        _log(state, "batch_failed", batch_stage=stage, error=str(exc)[:500])
        _FAILED[stage] += 1
        return default


# --- nodes -----------------------------------------------------------------------------------------------

async def components_node(state: RunState) -> RunState:
    spec, image, media = product.load_case(Path(state["case_dir"]))
    profile = await product.component_agent(spec, image, media)
    _write(state, "components.json", profile.model_dump())
    _log(state, "components", components=len(profile.components))
    return {"profile": profile.model_dump()}


async def functionalities_node(state: RunState) -> RunState:
    out = await product.functionality_agent(ProductProfile.model_validate(state["profile"]))
    funcs = [f.model_dump() for f in out.functionalities]
    _write(state, "functionalities.json", funcs)
    queries: dict[str, list[str]] = defaultdict(list)
    for f in funcs:
        queries[f["id"] if f["id"] != "unmapped" else f"unmapped:{f['statement'][:40]}"] += f["queries"]
    _log(state, "functionalities", functionalities=len(funcs), queries=sum(map(len, queries.values())))
    return {"functionalities": funcs, "queries": dict(queries), "round": 1, "seen": [], "decisions": {}, "hits": {}}


async def connect_and_route_node(state: RunState) -> RunState:
    """Global hybrid search: every regulation with a hit is connected; the applicability agent decides on each."""
    per_reg: dict[str, dict[str, float]] = defaultdict(dict)  # regulation -> provision id -> best score over all queries
    for qs in state["queries"].values():
        for q in qs:
            for h in store.search(q, k=CONNECT_K):
                per_reg[h.regulation][h.provision_id] = max(h.score, per_reg[h.regulation].get(h.provision_id, 0.0))
    all_cards = cards()
    entries = []
    for reg, hits in sorted(per_reg.items()):
        top = sorted(hits, key=hits.get, reverse=True)[:5]
        card = all_cards[reg]
        entries.append({"regulation": reg, "title": card.title, "version": card.version_label,
                        "scope": card.scope[:2000], "hits": len(hits),
                        "top_provisions": [{"paragraph": provision(p).paragraph, "text": provision(p).text[:400]} for p in top]})
    system = prompts.APPLICABILITY
    batches = [entries[i:i + 10] for i in range(0, len(entries), 10)]
    results = await asyncio.gather(*[_safe(state, "applicability", llm.structured(
        RouteDecisions, system, _profile_text(state) + "\n\nRegulations to decide:\n" + json.dumps(b, ensure_ascii=False),
        effort="medium", label="applicability"), RouteDecisions(decisions=[])) for b in batches])
    decided = {d.regulation: d.model_dump() for r in results for d in r.decisions}
    route = []
    for e in entries:
        d = decided.get(e["regulation"]) or {"regulation": e["regulation"], "decision": "uncertain", "reason": "no decision returned"}
        route.append({**d, "hits": e["hits"], "title": e["title"]})
    # Supersession: a predecessor named in a kept consolidated regulation's Introduction is dropped.
    kept = {r["regulation"] for r in route if r["decision"] in ("applicable", "uncertain")}
    for r in route:
        succ = [s for s in kept if r["regulation"] in all_cards[s].supersedes]
        if succ and r["decision"] != "not_applicable":
            r.update(decision="not_applicable", reason=f"superseded by {', '.join(sorted(succ))} (Introduction)", superseded=True)
    regs = sorted(r["regulation"] for r in route if r["decision"] in ("applicable", "uncertain"))
    _write(state, "route.json", route)
    _log(state, "route", connected=len(route), applicable=len(regs), regulations=regs)
    return {"route": route, "regulations": regs}


def _expand(pids: set[str]) -> set[str]:
    out = set(pids)
    by_section: dict[tuple[str, str, str], list[Provision]] = defaultdict(list)
    for pid in pids:
        p = provision(pid)
        by_section[(p.regulation, p.version_label, p.section)].append(p)
    for (reg, ver, section), hit_provs in by_section.items():
        members = [p for p in provisions(reg, ver) if p.section == section and not p.rationale and p.text]
        if len(members) <= SECTION_CAP:
            out.update(p.provision_id for p in members)
        else:  # large section: neighbours of each hit only
            idx = {p.provision_id: i for i, p in enumerate(members)}
            for h in hit_provs:
                i = idx.get(h.provision_id, 0)
                out.update(p.provision_id for p in members[max(0, i - 4): i + 5])
    return out


async def retrieve_node(state: RunState) -> RunState:
    regs, hits = state.get("regulations") or [], {k: list(v) for k, v in state.get("hits", {}).items()}
    found: set[str] = set()
    for fid, qs in state["queries"].items():
        for q in qs:
            for reg in regs:
                for h in store.search(q, k=PROVISION_K, regulations=[reg]):
                    found.add(h.provision_id)
                    hits.setdefault(h.provision_id, []).append(fid)
    expanded = _expand(found)
    forced = sorted(found & set(state.get("triage_dropped", [])))  # a rewritten query hits them directly: skip triage
    new = sorted((expanded - set(state.get("seen", []))) | set(forced))
    _log(state, "retrieve", round=state["round"], hits=len(found), expanded=len(expanded), new=len(new), forced=len(forced))
    return {"candidates": new, "hits": hits, "forced": forced}


def _rescue_key(p: Provision) -> tuple[str, str, str]:
    if p.paragraph.startswith("Annex"):
        return (p.regulation, p.section, ".".join(p.number.split(".")[:2]))  # two levels: one hit must not rescue a whole annex item
    return (p.regulation, "", ".".join(p.number.split(".")[:3]))


async def triage_node(state: RunState) -> RunState:
    forced = set(state.get("forced", []))
    cands = [c for c in state["candidates"] if c not in forced]
    batches = [cands[i:i + TRIAGE_BATCH] for i in range(0, len(cands), TRIAGE_BATCH)]

    async def grade(batch: list[str]) -> dict[str, bool]:
        refs = {f"P{i}": pid for i, pid in enumerate(batch)}
        content = "\n\n".join(_block(r, provision(pid), 700) for r, pid in refs.items())
        out = await _safe(state, "triage", llm.structured(
            TriageGrades, prompts.TRIAGE + "\n\n" + _profile_text(state), content,
            model=config.MODEL_FAST, effort="low", label="triage"), TriageGrades(grades=[]))
        got = {refs[g.ref]: g.relevant for g in out.grades if g.ref in refs}
        return {pid: got.get(pid, True) for pid in batch}

    grades: dict[str, bool] = {}
    for g in await asyncio.gather(*[grade(b) for b in batches]):
        grades.update(g)
    # A provision Haiku marked irrelevant is rescued only if it sits right next to a relevant direct hit (same three-level
    # parent, or the same item of the same annex part): whole sections would keep almost everything.
    relevant_keys = {_rescue_key(provision(p)) for p, ok in grades.items() if ok and p in state["hits"]}
    keep = [p for p, ok in grades.items() if ok or _rescue_key(provision(p)) in relevant_keys]
    dropped = (set(state.get("triage_dropped", [])) - forced) | (set(grades) - set(keep))
    keep += sorted(forced)
    with open(Path(state["run_dir"]) / "retrieval_grades.jsonl", "a", encoding="utf-8") as f:
        for p, ok in grades.items():
            f.write(json.dumps({"provision_id": p, "relevant": ok, "round": state["round"]}) + "\n")
    _log(state, "triage", graded=len(grades), kept=len(keep), forced=len(forced))
    return {"candidates": keep, "seen": sorted(set(state.get("seen", [])) | set(grades) | forced),
            "triage_dropped": sorted(dropped)}


async def judge_node(state: RunState) -> RunState:
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for pid in state["candidates"]:
        p = provision(pid)
        groups[(p.regulation, p.section)].append(pid)
    batches = []
    for pids in groups.values():
        pids.sort(key=lambda x: (provision(x).page, x))
        batches += [pids[i:i + JUDGE_BATCH] for i in range(0, len(pids), JUDGE_BATCH)]
    system = prompts.JUDGE + "\n\n" + _profile_text(state)

    def unjudged(pids: list[str], reason: str) -> list[dict]:
        # Fail closed: a provision no model judged is recorded, never exported (the writer only takes keep/uncertain).
        return [{"ref": "", "label": "unjudged", "reason": reason, "functionality_ids": [], "provision_id": pid,
                 "round": state["round"]} for pid in pids]

    async def judge(batch: list[str], attempt: int = 0) -> list[dict]:
        refs = {f"P{i}": pid for i, pid in enumerate(batch)}
        content = "\n\n".join(_block(r, provision(pid), 2500) for r, pid in refs.items())
        try:
            out = await llm.structured(JudgeDecisions, system, content, effort="medium", label="judge")
        except llm.LLMError as exc:
            _log(state, "batch_failed", batch_stage="judge", error=str(exc)[:500], size=len(batch))
            _FAILED["judge"] += 1
            if exc.splittable and len(batch) > 1 and attempt < 2:  # a smaller batch is a different request; the same one fails the same way
                half = len(batch) // 2
                first, second = await asyncio.gather(judge(batch[:half], attempt + 1), judge(batch[half:], attempt + 1))
                return first + second
            return unjudged(batch, f"judge call failed: {str(exc)[:120]}")
        res, answered = [], set()
        for d in out.decisions:
            if d.ref in refs and d.ref not in answered:
                answered.add(d.ref)
                res.append({**d.model_dump(), "provision_id": refs[d.ref], "round": state["round"]})
        missing = [pid for r, pid in refs.items() if r not in answered]
        if missing and attempt == 0:
            res += await judge(missing, attempt=1)  # the call worked but skipped refs: ask once for just those
        elif missing:
            res += unjudged(missing, "no decision returned by the judge")
        return res

    decisions = dict(state.get("decisions", {}))
    for res in await asyncio.gather(*[judge(b) for b in batches]):
        for d in res:
            decisions[d["provision_id"]] = d
    labels = Counter(d["label"] for d in decisions.values())
    with open(Path(state["run_dir"]) / "decisions.jsonl", "a", encoding="utf-8") as f:
        for b in batches:
            for pid in b:
                if pid in decisions:
                    f.write(json.dumps(decisions[pid], ensure_ascii=False) + "\n")
    _log(state, "judge", round=state["round"], batches=len(batches), **labels)
    return {"decisions": decisions}


async def coverage_node(state: RunState) -> RunState:
    covered = {fid for d in state["decisions"].values() if d["label"] == "keep" for fid in d["functionality_ids"]}
    gaps = [f for f in state["functionalities"] if f["id"] != "unmapped" and f["id"] not in covered]
    nothing_to_search = not state.get("regulations") or not state.get("candidates")
    if not gaps or state["round"] >= MAX_ROUNDS or nothing_to_search:
        _log(state, "coverage", round=state["round"], gaps=[f["id"] for f in gaps], stop=True)
        return {"queries": {}}
    on_topic = sorted((kv for kv in state["decisions"].items() if kv[1]["label"] != "reject"),
                      key=lambda kv: kv[1]["label"] != "keep")[:60]
    context = [{"paragraph": provision(pid).paragraph, "heading": " > ".join(provision(pid).heading_path),
                "text": provision(pid).text[:200]} for pid, _ in on_topic]
    rw = await _safe(state, "rewrite", product.rewrite_queries([{k: f[k] for k in ("id", "statement")} for f in gaps], context),
                     QueryRewrites(rewrites=[]))
    queries = {r.functionality_id: r.queries for r in rw.rewrites if r.queries}
    _log(state, "coverage", round=state["round"], gaps=[f["id"] for f in gaps], rewritten=len(queries))
    return {"queries": queries, "round": state["round"] + 1}


def _after_coverage(state: RunState) -> str:
    return "retrieve" if state.get("queries") else "xrefs"


REF = re.compile(r"paragraphs? ((?:\d+\.)+\d*\.?)((?:\s+[\w.]+){0,8})", re.I)


OTHER_DOCUMENT = re.compile(r"\bregulations?\s+no\b|\bgtr\b|\bdirective\b|\biso\b|\bcispr\b|\bsae\b")


def resolve_reference(p: Provision, number: str, tail: str, by_label: dict[str, Provision]) -> Provision | None:
    """The provision "paragraph <number> <tail>" in p's text points to, or None when it points elsewhere.

    "paragraph 6.2.2. of UN Regulation No. 7" points into another document and is not resolved. "paragraph 1.1. of
    Annex 3" resolves to the one provision labelled "Annex 3 ... 1.1" if that is unambiguous; inside an annex a bare
    "paragraph 3.1." means that annex."""
    tail = tail.lower()
    if "this regulation" not in tail and OTHER_DOCUMENT.search(tail):
        return None
    annex = re.search(r"annex\s+(\d+[a-z]?)", tail)
    if annex and "this annex" not in tail:  # "paragraph 1.1. of Annex 3": resolved only when the label is unambiguous
        wanted = f"Annex {annex.group(1).upper()} "
        found = [q for label, q in by_label.items() if label.startswith(wanted) and label.endswith(" " + number)]
        return found[0] if len(found) == 1 else None
    if p.paragraph.startswith("Annex") and "this regulation" not in tail:
        return by_label.get(f"{p.section} {number}")
    return by_label.get(number)


async def xrefs_node(state: RunState) -> RunState:
    """Attach the paragraphs a kept provision refers to (same version), deterministically."""
    xrefs: dict[str, str] = {}
    for pid, d in state["decisions"].items():
        if d["label"] not in ("keep", "uncertain"):
            continue
        p = provision(pid)
        by_label: dict[str, Provision] = {}
        for q in provisions(p.regulation, p.version_label):
            if not q.rationale:
                by_label.setdefault(q.paragraph, q)  # a duplicate label keeps the first provision
        parts = []
        for m, tail in REF.findall(p.text):
            target = resolve_reference(p, m.rstrip("."), tail, by_label)
            if target and target.provision_id != pid and len(parts) < 4:
                parts.append(f"[paragraph {target.paragraph}] {target.text[:1200]}")
        if parts:
            xrefs[pid] = "\n".join(parts)
    _log(state, "xrefs", attached=len(xrefs))
    return {"xrefs": xrefs}


async def writer_node(state: RunState) -> RunState:
    labels = {"keep", "uncertain"} if state.get("export_uncertain", True) else {"keep"}
    kept = [pid for pid, d in state["decisions"].items() if d["label"] in labels]
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for pid in kept:
        groups[(provision(pid).regulation, provision(pid).section)].append(pid)
    batches = []
    for pids in groups.values():
        pids.sort(key=lambda x: (provision(x).page, x))
        batches += [pids[i:i + WRITER_BATCH] for i in range(0, len(pids), WRITER_BATCH)]
    system = prompts.WRITER + "\n\n" + _profile_text(state)

    lost: list[str] = []

    async def write(batch: list[str], attempt: int = 0) -> list[dict]:
        refs = {f"P{i}": pid for i, pid in enumerate(batch)}
        blocks = []
        for r, pid in refs.items():
            b = _block(r, provision(pid), 8000)
            if pid in state["xrefs"]:
                b += f"\n<attached_reference for=\"{r}\">\n{state['xrefs'][pid]}\n</attached_reference>"
            blocks.append(b)
        try:
            out = await llm.structured(DraftRequirements, system, "\n\n".join(blocks), effort="medium", label="writer")
        except llm.LLMError as exc:
            _log(state, "batch_failed", batch_stage="writer", error=str(exc)[:500], size=len(batch))
            _FAILED["writer"] += 1
            if exc.splittable and len(batch) > 1 and attempt < 3:  # a long table can overflow the reply; a smaller batch is a different request
                half = len(batch) // 2
                first, second = await asyncio.gather(write(batch[:half], attempt + 1), write(batch[half:], attempt + 1))
                return first + second
            lost.extend(batch)
            return []
        return [{**d.model_dump(), "provision_id": refs[d.ref]} for d in out.requirements if d.ref in refs]

    drafts = [d for res in await asyncio.gather(*[write(b) for b in batches]) for d in res]
    if lost:  # visible, never silent: these kept provisions produced no requirement
        _log(state, "writer_lost", count=len(lost), provision_ids=lost)
    _log(state, "writer", provisions=len(kept), batches=len(batches), drafts=len(drafts), lost=len(lost))
    return {"drafts": drafts}


async def export_node(state: RunState) -> RunState:
    from pipeline.verify.checks import score, submission, validate, verify

    provs = {d["provision_id"]: provision(d["provision_id"]) for d in state["drafts"]}
    rows, drops, dropped = verify(state["drafts"], provs, state["xrefs"])
    order = {r: i for i, r in enumerate(sorted({r.regulation for r in rows}))}
    rows.sort(key=lambda r: (order[r.regulation], r.page, r.paragraph))
    team = config.TEAM_ID
    sub = submission(rows, state["case_id"], team)
    run_dir = Path(state["run_dir"])
    _write(state, "submission.json", sub)
    _write(state, "requirements_trace.jsonl", [r.__dict__ for r in rows])
    _write(state, "verifier_drops.jsonl", dropped)
    problems = validate(run_dir / "submission.json")
    expected = Path(state["case_dir"]) / "expected.json"
    sc = score(run_dir / "submission.json", expected)
    if sc is not None:
        _write(state, "score.json", sc)
    result = {"requirements": len(rows), "drops": dict(drops), "validation_problems": problems,
              "failed_batches": dict(_FAILED),
              "fuzzy_quotes": sum(r.quote_match == "fuzzy" for r in rows), "score": sc, "team_id": team}
    _log(state, "export", requirements=len(rows), valid=not problems, drops=dict(drops))
    return {"result": result}


def build_graph():
    g = StateGraph(RunState)
    for name, fn in [("components", components_node), ("functionalities", functionalities_node),
                     ("route", connect_and_route_node), ("retrieve", retrieve_node), ("triage", triage_node),
                     ("judge", judge_node), ("coverage", coverage_node), ("xrefs", xrefs_node),
                     ("writer", writer_node), ("export", export_node)]:
        g.add_node(name, fn)
    g.add_edge(START, "components")
    g.add_edge("components", "functionalities")
    g.add_edge("functionalities", "route")
    g.add_edge("route", "retrieve")
    g.add_edge("retrieve", "triage")
    g.add_edge("triage", "judge")
    g.add_edge("judge", "coverage")
    g.add_conditional_edges("coverage", _after_coverage, {"retrieve": "retrieve", "xrefs": "xrefs"})
    g.add_edge("xrefs", "writer")
    g.add_edge("writer", "export")
    g.add_edge("export", END)
    return g.compile()
