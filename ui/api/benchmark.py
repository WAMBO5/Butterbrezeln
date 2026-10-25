"""The challenge benchmark of a pipeline run: its submission.json against the organisers' reference.

Only challenge data counts: the reference is `expected.json` of the challenge case whose spec.md equals the run's
input (industrial-ai-hackathon/cases/), and regulation and page level come from the organisers' score_local.py.
The platform ranks by requirement-level F2 = 5PR / (4P + R); `requirement` here is the free one-to-one pairing by
(regulation, paragraph) of general-approach's tools/evalkit/score.py, an upper bound on that level. The country
layer of this UI is not in submission.json, so it never changes the score.
"""

from __future__ import annotations

import collections
import importlib.util
import json
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

from .config import CASES_DIR, TOOLS_DIR
from .models import Benchmark, BenchmarkLevel


@lru_cache(maxsize=1)
def _score_local() -> ModuleType:
    spec = importlib.util.spec_from_file_location("score_local", TOOLS_DIR / "score_local.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def f2(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 5 * precision * recall / (4 * precision + recall)


def _norm(text: str) -> str:
    return " ".join(text.split()).lower()


def reference_case(spec_text: str) -> Path | None:
    """The challenge case with a reference solution whose spec.md equals `spec_text`."""
    wanted = _norm(spec_text)
    for expected in sorted(CASES_DIR.glob("*/expected.json")):
        spec = expected.parent / "spec.md"
        if spec.is_file() and _norm(spec.read_text(encoding="utf-8")) == wanted:
            return expected.parent
    return None


def _level(name: str, stats: dict[str, Any]) -> BenchmarkLevel:
    p, r = stats["precision"], stats["recall"]
    return BenchmarkLevel(level=name, precision=p, recall=r, f2=f2(p, r), submitted=stats["n_submitted"],
                          expected=stats["n_expected"], matched=stats["n_matched"])


def score(submission: dict[str, Any], expected: dict[str, Any]) -> list[BenchmarkLevel]:
    local = _score_local()
    s = local.score(submission, expected)
    key = local._paragraph_key
    sub, exp = submission.get("requirements", []), expected.get("requirements", [])
    gold = collections.Counter((g["source"]["regulation"], key(g["source"].get("paragraph"))) for g in exp)
    ours = collections.Counter((r["source"]["regulation"], key(r["source"].get("paragraph"))) for r in sub)
    matched = sum(min(n, gold[k]) for k, n in ours.items())
    requirement = {"precision": matched / max(len(sub), 1), "recall": matched / max(len(exp), 1),
                   "n_submitted": len(sub), "n_expected": len(exp), "n_matched": matched}
    return [_level("regulation", s["regulation_level"]), _level("page", s["page_level"]),
            _level("requirement", requirement)]


def for_run(run_dir: Path, spec_text: str, state: dict[str, Any]) -> Benchmark | None:
    """The run's benchmark output; scored when the spec is a challenge case with a reference solution."""
    path = run_dir / "submission.json"
    if not path.is_file():
        return None
    submission = json.loads(path.read_text(encoding="utf-8"))
    case = reference_case(spec_text)
    levels = score(submission, json.loads((case / "expected.json").read_text(encoding="utf-8"))) if case else []
    problems = [str(p) for p in state.get("validation_problems") or []]
    return Benchmark(case_id=case.name if case else None, requirements=len(submission.get("requirements", [])),
                     valid=not problems, problems=problems, levels=levels)
