"""Score a main-goal submission on the dev case the way the platform ranks it (F2 at three levels).

    python3 score.py <submission.json> [--judge] [--label NAME] [--expected expected.json]

- validate.py must pass (exit 2 otherwise)
- regulation and page level from the organisers' score_local.py, plus F2
- req(para): free one-to-one pairing by (regulation, paragraph key), an upper bound on the requirement level
- --judge: requirement level by meaning, through the Anthropic API (paid; model from ANTHROPIC_MODEL_JUDGE,
  ANTHROPIC_MODEL_MATCH or ANTHROPIC_MODEL), per regulation, one-to-one enforced in code
- --label: append one row to the scoreboard (data/scoreboard.md)

The expected text is only ever used here, for scoring; it never reaches a generating prompt.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel

def _find_root() -> Path:
    """The repo root: $CERTIVITY_ROOT, else the first parent that holds industrial-ai-hackathon/tools."""
    if os.environ.get("CERTIVITY_ROOT"):
        return Path(os.environ["CERTIVITY_ROOT"])
    for parent in Path(__file__).resolve().parents:
        if (parent / "industrial-ai-hackathon" / "tools" / "score_local.py").is_file():
            return parent
    raise SystemExit("repo root not found: set CERTIVITY_ROOT to the Butterbrezeln checkout")


ROOT = _find_root()
HACK = ROOT / "industrial-ai-hackathon"
sys.path.insert(0, str(HACK / "tools"))
from score_local import _paragraph_key, score  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = HERE / "judge_cache"
SCOREBOARD = ROOT / "data" / "scoreboard.md"

JUDGE_SYSTEM = """\
You compare two lists of engineering requirements derived from the same UN Regulation: OURS and EXPECTED.
Pair one of ours with one expected requirement only when both state the same engineering obligation: the
same scope (what it applies to), the same condition, and the same constraint (value, limit or property).
Wording may differ; a requirement that states the obligation with slightly more or less context still pairs.
Each id may be used at most once. Leave out requirements without a counterpart. Be strict about different
values, different subjects or different directions.
"""
JUDGE_STRICT_SYSTEM = """\
You compare two lists of engineering requirements derived from the same UN Regulation: OURS and EXPECTED.
Pair one of ours with one expected requirement only when both state exactly the same engineering obligation:
the same scope (what it applies to), the same condition, and the same constraint (value, limit, property).
Do not pair when ours merges several obligations of which the expected states one, when ours adds or drops a
condition, exception or value, when the subject differs, or when ours only refers to the obligation in general
terms. Wording may differ. Each id may be used at most once. Leave out requirements without an exact counterpart.
"""
JUDGE_SCHEMA = {"type": "object", "properties": {"pairs": {"type": "array", "items": {"type": "object", "properties": {
    "ours": {"type": "string"}, "expected": {"type": "string"}}, "required": ["ours", "expected"],
    "additionalProperties": False}}}, "required": ["pairs"], "additionalProperties": False}


def f2(p: float, r: float) -> float:
    return 0.0 if p + r == 0 else 5 * p * r / (4 * p + r)


def lines(reqs: list[dict]) -> str:
    return "\n".join(f"[{r['id']}] (§{r['source'].get('paragraph')}, p.{r['source']['page']}) {r['text']}" for r in reqs)


class _Pair(BaseModel):
    ours: str
    expected: str


class _Pairs(BaseModel):
    pairs: list[_Pair]


async def judge_json(system: str, prompt: str, schema: dict, tag: str, model: str | None = None,
                     effort: str = "medium", timeout: int = 1800) -> dict:
    """One structured judge call through the Anthropic SDK (ANTHROPIC_API_KEY), cached on disk by its inputs.

    The model is ANTHROPIC_MODEL_JUDGE, else ANTHROPIC_MODEL_MATCH, else ANTHROPIC_MODEL."""
    from anthropic import AsyncAnthropic

    model = model or next((os.environ[k] for k in ("ANTHROPIC_MODEL_JUDGE", "ANTHROPIC_MODEL_MATCH", "ANTHROPIC_MODEL")
                           if os.environ.get(k)), "")
    if not model:
        raise RuntimeError("set ANTHROPIC_MODEL (or ANTHROPIC_MODEL_JUDGE) for --judge")
    key = hashlib.sha256("\x1f".join([system, prompt, json.dumps(schema, sort_keys=True), model, effort]).encode()).hexdigest()[:24]
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())["out"]
    client = AsyncAnthropic(max_retries=4, timeout=float(timeout))
    message = await client.messages.parse(
        model=model, max_tokens=16000,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": effort}, output_format=_Pairs)
    if message.parsed_output is None:
        raise RuntimeError(f"judge failed [{tag}]: no structured output ({message.stop_reason})")
    out = message.parsed_output.model_dump()
    path.write_text(json.dumps({"tag": tag, "out": out}))
    return out


async def judge(sub: list[dict], exp: list[dict], system: str = JUDGE_SYSTEM) -> tuple[int, dict, list]:
    regs = sorted({r["source"]["regulation"] for r in sub} & {g["source"]["regulation"] for g in exp})
    jobs = []
    for reg in regs:
        o = [r for r in sub if r["source"]["regulation"] == reg]
        g = [x for x in exp if x["source"]["regulation"] == reg]
        prompt = f"<ours>\n{lines(o)}\n</ours>\n\n<expected>\n{lines(g)}\n</expected>\n\nPair requirements that state the same obligation."
        jobs.append((reg, o, g, judge_json(system, prompt, JUDGE_SCHEMA, tag=f"judge:{reg}")))
    outs = await asyncio.gather(*[j[3] for j in jobs])
    matched, per, pairs = 0, {}, []
    for (reg, o, g, _), out in zip(jobs, outs):
        oi, gi, uo, ug = {r["id"] for r in o}, {x["id"] for x in g}, set(), set()
        for p in out["pairs"]:
            if p["ours"] in oi and p["expected"] in gi and p["ours"] not in uo and p["expected"] not in ug:
                uo.add(p["ours"]); ug.add(p["expected"]); pairs.append((p["ours"], p["expected"]))
        per[reg] = (len(o), len(g), len(uo))
        matched += len(uo)
    return matched, per, pairs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("submission")
    ap.add_argument("--expected", default=str(HACK / "cases" / "dev-rear-lamp" / "expected.json"))
    ap.add_argument("--judge", action="store_true")
    ap.add_argument("--strict", action="store_true", help="stricter judge, calibrated against the platform")
    ap.add_argument("--label")
    a = ap.parse_args()
    v = subprocess.run([sys.executable, str(HACK / "tools" / "validate.py"), a.submission], capture_output=True, text=True)
    if v.returncode != 0 and "jsonschema" in (v.stdout + v.stderr) and "No module" in (v.stdout + v.stderr):
        print("validate.py could not run: jsonschema is not installed for this python; use `uv run python score.py ...`")
        return 2
    if v.returncode != 0:
        print("VALIDATION FAILED\n" + v.stdout[-2000:] + v.stderr[-1000:])
        return 2
    sub_doc, exp_doc = json.loads(Path(a.submission).read_text()), json.loads(Path(a.expected).read_text())
    sub, exp = sub_doc["requirements"], exp_doc["requirements"]
    s = score(sub_doc, exp_doc)
    gold = collections.Counter((g["source"]["regulation"], _paragraph_key(g["source"].get("paragraph"))) for g in exp)
    ours = collections.Counter((r["source"]["regulation"], _paragraph_key(r["source"].get("paragraph"))) for r in sub)
    pm = sum(min(n, gold[k]) for k, n in ours.items())
    rows = {}
    print(f"{'level':<12}{'P':>7}{'R':>7}{'F2':>7}   n_sub / n_gold / matched")
    for name, label in (("regulation_level", "regulation"), ("page_level", "page")):
        x = s[name]
        rows[label] = (x["precision"], x["recall"], f2(x["precision"], x["recall"]))
        print(f"{label:<12}{x['precision']:>7.3f}{x['recall']:>7.3f}{rows[label][2]:>7.3f}   {x['n_submitted']} / {x['n_expected']} / {x['n_matched']}")
    pp, pr = pm / max(len(sub), 1), pm / max(len(exp), 1)
    rows["req(para)"] = (pp, pr, f2(pp, pr))
    print(f"{'req(para)':<12}{pp:>7.3f}{pr:>7.3f}{f2(pp, pr):>7.3f}   {len(sub)} / {len(exp)} / {pm}   (upper-bound proxy)")
    per = collections.defaultdict(lambda: [0, 0, 0])
    for k, n in ours.items():
        per[k[0]][0] += n; per[k[0]][2] += min(n, gold.get(k, 0))
    for k, n in gold.items():
        per[k[0]][1] += n
    print("per regulation (ours / gold / para-matched): " + "; ".join(
        f"{r} {a_}/{b}/{c}" for r, (a_, b, c) in sorted(per.items(), key=lambda kv: -kv[1][1])))
    missed = {k: n - min(n, ours.get(k, 0)) for k, n in gold.items() if n - min(n, ours.get(k, 0))}
    print(f"gold paragraphs missed ({sum(missed.values())} reqs): " + ", ".join(
        f"{r.split()[-1]}§{p}" for r, p in sorted(missed)))
    if a.judge:
        m, jper, pairs = asyncio.run(judge(sub, exp, JUDGE_STRICT_SYSTEM if a.strict else JUDGE_SYSTEM))
        jp, jr = m / max(len(sub), 1), m / max(len(exp), 1)
        rows["req(judge)"] = (jp, jr, f2(jp, jr))
        print(f"{'req(strict)' if a.strict else 'req(judge)':<12}{jp:>7.3f}{jr:>7.3f}{f2(jp, jr):>7.3f}   {len(sub)} / {len(exp)} / {m}")
        print("  " + "; ".join(f"{r} {x}/{y}/{z}" for r, (x, y, z) in jper.items()))
        out_dir = HERE / "pairs"  # never next to the submission: other lanes' folders are not ours to write
        out_dir.mkdir(exist_ok=True)
        tag = hashlib.sha256(str(Path(a.submission).resolve()).encode()).hexdigest()[:8]
        (out_dir / f"{Path(a.submission).stem}.{tag}.{'strict' if a.strict else 'judge'}_pairs.json").write_text(json.dumps(pairs, indent=0))
    if a.label:
        SCOREBOARD.parent.mkdir(parents=True, exist_ok=True)
        if not SCOREBOARD.exists():
            SCOREBOARD.write_text("# Dev-case scoreboard (rear lamp)\n\nF2 = 5PR/(4P+R), the ranking metric. "
                                  "req(judge): LLM judge, one-to-one; req(para): free paragraph-pairing upper bound.\n\n"
                                  "| when | label | n | reg F2 | page F2 (P/R) | req(para) F2 (P/R) | req(judge) F2 (P/R) | file |\n"
                                  "|---|---|---|---|---|---|---|---|\n")
        def cell(k):
            if k not in rows:
                return "–"
            p_, r_, f_ = rows[k]
            return f"{f_:.3f} ({p_:.2f}/{r_:.2f})"
        row = (f"| {datetime.datetime.now():%a %H:%M} | {a.label} | {len(sub)} | {rows['regulation'][2]:.3f} | "
               f"{cell('page')} | {cell('req(para)')} | {cell('req(judge)')} | `{a.submission}` |")
        lines = SCOREBOARD.read_text().rstrip("\n").split("\n")
        # the judge table is the first table; later sections (platform scores) stay below it
        end = next((n for n, l in enumerate(lines) if l.startswith("## ")), len(lines))
        while end > 0 and lines[end - 1] == "":
            end -= 1
        lines.insert(end, row)
        SCOREBOARD.write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
