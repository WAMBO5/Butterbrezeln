"""Re-run matching, assembly and finalize on a finished run's profile, scope plan and obligations.

    uv run python tools/replay_from_match.py <source_run_dir> [--from-assemble]

Writes a new run folder under $CERTIVITY_DATA_DIR/runs/ (default data/runs/). Paid: matcher, reviewer and
output auditor calls only. Use it to change the model of the judgment tier without a new scope draw, e.g.
a Sonnet run followed by `ANTHROPIC_MODEL=claude-opus-5-5 uv run python tools/replay_from_match.py <run>`
(dev: Sonnet scope + Opus matching gave run 6, 74.7 %). `--from-assemble` keeps the matcher's decisions
and only redoes assembly and the output audit.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from app.config.settings import load_settings  # noqa: E402
from app.pipeline.main import RunDeps, _now, drive, new_run_id  # noqa: E402
from app.pipeline.state import RunState  # noqa: E402

src = RunState.load(Path(sys.argv[1]))
from_assemble = "--from-assemble" in sys.argv  # keep the matcher's decisions, redo assembly and the output audit
settings = load_settings()
deps = RunDeps.load(settings)
run_id = new_run_id(src.case_id)
state = src.model_copy(update={
    "run_id": run_id, "run_dir": str(settings.runs_dir / run_id), "status": "running",
    "step": "match" if from_assemble else "extract",
    "checkpoint": None, "started_at": _now(), "finished_at": None, "error": None,
    "decisions": src.decisions if from_assemble else [], "requirements": [], "lineage": [], "output_issues": [], "output_review": None,
    "give_ups": [g for g in src.give_ups if g.startswith(("product_profile", "scope_plan", "extraction"))],
    "score": None, "stage_counts": {}, "cost": {}, "partial": False, "validation_problems": [],
})
state.save()
print("replay of", src.run_id, "->", state.run_dir)
res = asyncio.run(drive(state, deps))
print("status:", res.status, "cost:", res.cost_usd, "submission:", res.submission_path)
print("score:", RunState.load(Path(res.run_dir)).score)
