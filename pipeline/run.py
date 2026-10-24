"""Product run: spec and exploded view in, validated submission.json out. Calls LLM (paid).

    uv run --env-file .env python -m pipeline.run --case cases/dev-rear-lamp
    uv run --env-file .env python -m pipeline.run --case cases/heldout-front-bumper --no-export-uncertain
    uv run python -m pipeline.run --promote runs/dev-rear-lamp/<timestamp>   # copy to out/ after validate.py passes
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

from pipeline import config


def _case_dir(case: str) -> Path:
    p = Path(case)
    for cand in (p, config.HACKATHON_DIR / p, config.HACKATHON_DIR / "cases" / p):
        if (cand / "spec.md").is_file() or any(cand.glob("exploded_view.*")):
            return cand.resolve()
    raise SystemExit(f"error: no spec.md or exploded_view.* under {case}")


def promote(run_dir: Path) -> int:
    from pipeline.verify.checks import validate

    src = run_dir / "submission.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    if not config.TEAM_ID or data.get("team_id") != config.TEAM_ID:
        print("error: set TEAM_ID and re-run the case so submission.json carries it", file=sys.stderr)
        return 1
    problems = validate(src)
    if problems:
        print("error: validate.py failed:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    config.OUT_DIR.mkdir(exist_ok=True)
    dst = config.OUT_DIR / f"{data['case_id']}.json"
    shutil.copyfile(src, dst)
    print(f"promoted {src} -> {dst}")
    return 0


def preflight() -> None:
    """Fail before any paid call when the vector store is locked, missing or only partly indexed."""
    from pipeline.rag import store

    try:
        missing = store.missing_versions()
    except RuntimeError as exc:  # local Qdrant folder locked by another process (e.g. pipeline.legal still running)
        raise SystemExit(f"error: cannot open the Qdrant store ({exc}); wait for pipeline.legal to finish") from exc
    if missing:
        raise SystemExit(f"error: {len(missing)} base versions are not fully indexed, run `uv run python -m pipeline.legal`:\n  "
                         + "\n  ".join(missing))


async def run_case(case: str, export_uncertain: bool = True) -> dict:
    from pipeline.graph import map as graph

    case_dir = _case_dir(case)
    preflight()
    graph._FAILED.clear()  # per-run counters (the API process runs many)
    run_dir = config.RUNS_DIR / case_dir.name / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"run {run_dir} | model {config.MODEL} | fast model {config.MODEL_FAST}", flush=True)
    state = await graph.build_graph().ainvoke(
        {"case_id": case_dir.name, "case_dir": str(case_dir), "run_dir": str(run_dir), "export_uncertain": export_uncertain},
        {"recursion_limit": 60})
    return {"run_dir": str(run_dir), **state["result"]}


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", help="case folder, e.g. cases/dev-rear-lamp")
    ap.add_argument("--no-export-uncertain", action="store_true", help="withhold judge 'uncertain' rows from the export")
    ap.add_argument("--promote", metavar="RUN_DIR", help="copy RUN_DIR/submission.json to out/ after validation")
    args = ap.parse_args(argv)
    if args.promote:
        return promote(Path(args.promote))
    if not args.case:
        ap.error("--case or --promote is required")
    try:
        result = asyncio.run(run_case(args.case, export_uncertain=not args.no_export_uncertain))
    finally:
        from pipeline.rag import store
        store.close()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result["requirements"]:
        print("warning: the run produced no requirements; see trace.jsonl", file=sys.stderr)
        return 1
    return 0 if not result["validation_problems"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
