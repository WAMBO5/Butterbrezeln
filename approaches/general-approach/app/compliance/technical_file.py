"""Regenerate the measured parts of the AI Act documents (`certivity technical-file`).

Only the text between `<!-- name:start -->` and `<!-- name:end -->` markers is rewritten; everything
else in the documents is edited by hand.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from app.compliance.ledger import Ledger
from app.compliance.manifest import read_manifest
from app.compliance.redact import redact
from app.config.settings import Settings
from app.pipeline.state import RunState

DOCS_DIR = Path("docs/ai-act")


def replace_block(text: str, name: str, body: str) -> str:
    pattern = re.compile(rf"(<!-- {name}:start -->\n).*?(\n<!-- {name}:end -->)", re.S)
    return pattern.sub(lambda m: m.group(1) + body + m.group(2), text)


def _metrics(run_dir: Path, settings: Settings) -> str:
    from app.eval.funnel import funnel_metrics
    from app.pipeline.main import RunDeps

    state = RunState.load(run_dir)
    lines = [f"Latest bench run `{state.run_id}` ({state.mode} mode, {state.finished_at or state.started_at}).", ""]
    if state.score:
        lines += ["| level | precision | recall | F1 |", "|---|---|---|---|"]
        lines += [f"| {k.replace('_', ' ')} | {v['precision']:.3f} | {v['recall']:.3f} | {v['f1']:.3f} |"
                  for k, v in state.score.items()]
    expected = Path(state.case_dir) / "expected.json"
    if expected.exists():
        f = funnel_metrics(run_dir, expected, RunDeps.load(settings).store, settings)
        lines += ["", f"- Golden regulations kept by the scope plan: {f.scope_regulations_kept}.",
                  f"- Golden pages inside the chosen sections: {f.golden_pages_in_sections:.1%}.",
                  f"- Golden requirements with a similar extracted obligation: {f.candidate_coverage:.1%}."]
    c = state.stage_counts
    lines += [f"- Requirements: {c.get('requirements', len(state.requirements))} "
              f"({c.get('applicable_decisions', 0)} applicable and {c.get('uncertain_decisions', 0)} uncertain part decisions).",
              f"- Cost: ${float((state.cost or {}).get('spent_usd', 0)):.2f}"
              f"{' (partial run: the budget was reached)' if state.partial else ''}.",
              f"- Validation with `tools/validate.py`: {'no problems' if not state.validation_problems else state.validation_problems}."]
    return "\n".join(lines)


def _models(run_dir: Path) -> str:
    manifest = read_manifest(run_dir)
    if manifest is None:
        return "No manifest for the latest bench run."
    lines = [f"From the manifest of `{manifest.run_id}` (git commit {manifest.git_commit or 'unknown'}).", "",
             "| agent | model | prompt version |", "|---|---|---|"]
    lines += [f"| {agent} | {model} | {manifest.prompt_versions.get(agent, '')} |"
              for agent, model in sorted(manifest.models.items())]
    return "\n".join(lines)


def _oversight(runs_dir: Path) -> str:
    counts: Counter[tuple[str, str]] = Counter()
    signed = runs = 0
    for run in sorted(runs_dir.glob("*")) if runs_dir.exists() else []:
        if not (run / "ledger.jsonl").exists():
            continue
        runs += 1
        signed += (run / "signoff.json").exists()
        for r in Ledger(run).records():
            if r.kind == "human_action":
                counts[(str(r.meta.get("checkpoint")), str(r.meta.get("action", "signoff")))] += 1
    if not counts:
        return f"No human actions in {runs} runs yet."
    lines = [f"{runs} runs, {signed} signed off.", "", "| checkpoint | action | count |", "|---|---|---|"]
    lines += [f"| {cp} | {action} | {n} |" for (cp, action), n in sorted(counts.items())]
    return "\n".join(lines)


def update_technical_file(settings: Settings, bench_runs: list[Path], docs_dir: Path = DOCS_DIR) -> list[Path]:
    runs = [r for r in bench_runs if (Path(r) / "state.json").exists()]
    if not runs:
        return []
    latest = max(runs, key=lambda r: RunState.load(Path(r)).started_at)
    blocks = {"metrics": _metrics(Path(latest), settings), "models": _models(Path(latest)),
              "oversight": _oversight(settings.runs_dir)}
    blocks = {k: str(redact(v)) for k, v in blocks.items()}
    written = []
    for path in sorted(Path(docs_dir).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        new = text
        for name, body in blocks.items():
            new = replace_block(new, name, body)
        if new != text:
            path.write_text(new, encoding="utf-8")
            written.append(path)
    return written


def bench_runs(settings: Settings) -> list[Path]:
    """Finished benchmark runs of the worked example."""
    out = []
    for run in settings.runs_dir.glob("*") if settings.runs_dir.exists() else []:
        try:
            state = RunState.load(run)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if state.case_id == "dev-rear-lamp" and state.mode == "benchmark" and state.status == "done":
            out.append(run)
    return out
