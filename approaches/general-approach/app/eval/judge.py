"""Requirement-level estimate with an LLM judge (paid; design spec section 12).

It lives outside `app/agents` because its prompts contain the expected (golden) text at run time;
it is used only to score a finished run, never to produce one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from app.agents.factory import AgentSpec, make_agent
from app.agents.prompting import render_prompt
from app.config.settings import Settings
from app.pipeline.calls import AgentCall, gather_limited

INSTRUCTION = """\
You compare two lists of engineering requirements from the same UN Regulation: ours and the expected
ones. Pair a requirement of ours with an expected requirement only when both state the same
engineering obligation: the same scope (what it applies to), the same condition, and the same
constraint (value, limit or property). Wording may differ. Use each id at most once. Leave out
requirements without a counterpart.
"""


class JudgePair(BaseModel):
    ours: str
    golden: str


class JudgePairs(BaseModel):
    pairs: list[JudgePair]


@dataclass
class JudgeReport:
    matched: int
    precision: float
    recall: float
    pairs: list[tuple[str, str]] = field(default_factory=list)


def create_requirement_judge(settings: Settings) -> AgentSpec:
    return make_agent(name="requirement_judge", description="Pairs our requirements with expected ones",
                      instruction=INSTRUCTION, output_schema=JudgePairs, tier="judgment", effort="low",
                      settings=settings, max_tokens=32000)


def _lines(reqs: list[dict]) -> str:
    return "\n".join(f"[{r['id']}] (§{r['source'].get('paragraph')}, p.{r['source']['page']}) {r['text']}" for r in reqs)


async def judge_requirements(run_dir: Path, expected_path: Path, settings: Settings, call: AgentCall) -> JudgeReport:
    ours = json.loads((Path(run_dir) / "submission.json").read_text(encoding="utf-8"))["requirements"]
    gold = json.loads(Path(expected_path).read_text(encoding="utf-8"))["requirements"]
    spec = create_requirement_judge(settings)
    regs = sorted({r["source"]["regulation"] for r in ours} & {g["source"]["regulation"] for g in gold})
    groups = [([r for r in ours if r["source"]["regulation"] == reg], [g for g in gold if g["source"]["regulation"] == reg])
              for reg in regs]
    prompts = [render_prompt(task="Pair requirements that state the same obligation.",
                             context=[("Our requirements", _lines(o)), ("Expected requirements", _lines(g))],
                             untrusted=[], payload={"ours": [r["id"] for r in o], "golden": [r["id"] for r in g]})
               for o, g in groups]
    outputs = await gather_limited([call(spec, p) for p in prompts], settings.concurrency)
    accepted: list[tuple[str, str]] = []
    used_ours: set[str] = set()
    used_gold: set[str] = set()
    for (o, g), out in zip(groups, outputs):
        ours_ids, gold_ids = {r["id"] for r in o}, {r["id"] for r in g}
        for pair in out.pairs:  # one-to-one, enforced in code
            if pair.ours in ours_ids and pair.golden in gold_ids and pair.ours not in used_ours \
                    and pair.golden not in used_gold:
                used_ours.add(pair.ours)
                used_gold.add(pair.golden)
                accepted.append((pair.ours, pair.golden))
    n = len(accepted)
    return JudgeReport(matched=n, precision=n / len(ours) if ours else 0.0, recall=n / len(gold) if gold else 0.0,
                       pairs=accepted)
