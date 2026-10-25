"""Sub-goal (design spec section 9.4): `version_delta` (code) → `change_analyst` loop →
`validate.py --requirements-old` → `changes.json`."""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

from app.agents.change_analyst import build_change_prompt, create_change_analyst
from app.agents.grounding_verifier import build_grounding_prompt, create_grounding_verifier
from app.compliance.ledger import Ledger
from app.config.settings import Settings
from app.corpus.parser import normalize, paragraph_key, parse_regulation
from app.corpus.pdf_text import extract_pdf_text
from app.gates.change_gate import change_gate
from app.llm import LLM, Budget, load_prices
from app.markets.delta import align_provisions
from app.matching.challenge_tools import load_tool
from app.models import ChangeOutput, Claim, SubgoalChange
from app.pipeline.calls import AgentCall, bind_call, gather_limited
from app.pipeline.loop import LoopSpec, run_verified

BATCH = 20
HEADER_RE = re.compile(r"^(UN .+?), version (\S+) \| page \d+ of \d+$", re.M)


@dataclass
class SubgoalInput:
    case_id: str
    old_text: str
    new_text: str
    requirements_old: list[dict]
    pairs: list[dict] = field(default_factory=list)
    challenge_dir: Path = Path("industrial-ai-hackathon")


def describe_change(old: str, new: str) -> str:
    """The word-level edit from `old` to `new`, as "'x' became 'y'; 'z' was added"."""
    a, b = normalize(old).split(), normalize(new).split()
    parts = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "replace":
            parts.append(f"'{' '.join(a[i1:i2])}' became '{' '.join(b[j1:j2])}'")
        elif op == "insert":
            parts.append(f"'{' '.join(b[j1:j2])}' was added")
        elif op == "delete":
            parts.append(f"'{' '.join(a[i1:i2])}' was removed")
    return "; ".join(parts)


def _text(subgoal_dir: Path, settings: Settings, which: str) -> str:
    path = settings.text_root / "subgoal" / subgoal_dir.name / f"{which}.txt"
    if not path.exists():
        pdf = subgoal_dir / f"{which}.pdf"
        if not pdf.exists():
            raise FileNotFoundError(f"neither {path} nor {pdf} exists; run tools/fetch_regulations.py")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(extract_pdf_text(pdf, f"sub-goal {subgoal_dir.name} {which} | page {{page}} of {{pages}}"),
                        encoding="utf-8")
    return path.read_text(encoding="utf-8")


def _identity(text: str, fallback: str) -> tuple[str, str]:
    m = HEADER_RE.search(text)
    return (m.group(1), m.group(2)) if m else ("UN R?", fallback)


def load_subgoal(subgoal_dir: Path, settings: Settings) -> SubgoalInput:
    subgoal_dir = Path(subgoal_dir)
    old_text, new_text = _text(subgoal_dir, settings, "old"), _text(subgoal_dir, settings, "new")
    reqs = json.loads((subgoal_dir / "requirements_old.json").read_text(encoding="utf-8"))
    reqs = reqs["requirements"] if isinstance(reqs, dict) else reqs
    reg, old_label = _identity(old_text, "old")
    _, new_label = _identity(new_text, "new")
    old = [p for p in parse_regulation(old_text, reg, old_label, "base") if p.paragraph != "Introduction"]
    new = [p for p in parse_regulation(new_text, reg, new_label, "latest") if p.paragraph != "Introduction"]
    by_paragraph: dict[str | None, list[dict]] = {}
    for r in reqs:
        by_paragraph.setdefault(paragraph_key((r.get("source") or {}).get("paragraph")), []).append(r)
    pairs = []
    for c in align_provisions(old, new):
        if c.status == "unchanged":
            continue
        linked = by_paragraph.get(paragraph_key(c.old.paragraph), []) if c.old else []
        pairs.append({
            "paragraph": c.paragraph, "status": c.status,
            "old_paragraph": c.old.paragraph if c.old else None, "new_paragraph": c.new.paragraph if c.new else None,
            "old_page": c.old.page_start if c.old else None, "new_page": c.new.page_start if c.new else None,
            "edit": describe_change(c.old.text, c.new.text) if c.old and c.new else None,
            "old_text": " ".join(c.old.text.split())[:3000] if c.old else None,
            "new_text": " ".join(c.new.text.split())[:3000] if c.new else None,
            "linked": [{"id": r["id"], "text": r["text"]} for r in linked],
        })
    return SubgoalInput(case_id=f"subgoal-{subgoal_dir.name}", old_text=old_text, new_text=new_text,
                        requirements_old=reqs, pairs=pairs, challenge_dir=settings.challenge_dir)


def change_claims(inp: SubgoalInput, out: ChangeOutput) -> list[Claim]:
    by_para = {paragraph_key(p["new_paragraph"] or p["old_paragraph"]): p for p in inp.pairs}
    claims = []
    for n, c in enumerate(out.changes):
        pair = by_para.get(paragraph_key(c.source.paragraph), {})
        cited = f"edit: {pair.get('edit')}\nold: {pair.get('old_text')}\nnew: {pair.get('new_text')}"
        claims.append(Claim(claim_id=f"change:{n}", text=c.reason, cited_text=cited[:4000]))
    return claims


async def analyse_changes(inp: SubgoalInput, settings: Settings, call: AgentCall,
                          ledger: Ledger | None) -> list[SubgoalChange]:
    batches = [replace(inp, pairs=inp.pairs[i:i + BATCH]) for i in range(0, len(inp.pairs), BATCH)]
    loop = LoopSpec(name="subgoal_changes", producer=create_change_analyst(settings), output_schema=ChangeOutput,
                    build_prompt=lambda b, fb: build_change_prompt(b.pairs, b.case_id, fb), gate=change_gate,
                    verifier=create_grounding_verifier(settings),
                    build_review_prompt=lambda b, out: build_grounding_prompt(change_claims(b, out)),
                    max_retries=settings.max_retries)
    results = await gather_limited([run_verified(loop, b, call, ledger) for b in batches], settings.concurrency)
    changes: list[SubgoalChange] = []
    seen: set[str] = set()
    for res in results:
        for c in (res.output.changes if res.output else []):
            if c.requirement_id is not None:
                if c.requirement_id in seen:
                    continue
                seen.add(c.requirement_id)
            changes.append(c)
    return changes


async def run_subgoal(subgoal_dir: Path, settings: Settings, llm: LLM | None = None) -> Path:
    inp = load_subgoal(Path(subgoal_dir), settings)
    out_dir = settings.data_dir / "subgoal" / Path(subgoal_dir).name
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(out_dir)
    llm = llm or LLM(settings, budget=Budget(settings.max_cost_usd, load_prices(settings.prices_path)))
    changes = await analyse_changes(inp, settings, bind_call(llm, ledger), ledger)
    data = {"team_id": settings.team_id, "case_id": inp.case_id, "changes": [c.model_dump() for c in changes]}
    validate = load_tool(settings.challenge_dir, "validate")
    problems = [str(p) for p in validate.validate(data, requirements_old=inp.requirements_old)]
    path = out_dir / "changes.json"
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    (out_dir / "validation.json").write_text(json.dumps({"problems": problems}, indent=1), encoding="utf-8")
    ledger.append("export", "orchestrator", None, data, {"changes": len(changes), "validation_problems": len(problems)})
    return path
