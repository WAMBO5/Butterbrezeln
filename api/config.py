"""Paths and environment switches for the API."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "industrial-ai-hackathon"
INDEX_PATH = PACKAGE / "regulations" / "index.json"
PDF_DIR = PACKAGE / "regulations" / "pdf"
CASES_DIR = PACKAGE / "cases"
TOOLS_DIR = PACKAGE / "tools"
DATA_DIR = ROOT / "data"
RUNS_DIR = Path(os.environ.get("RUNS_DIR", ROOT / "runs"))

# runs: requirements come from a finished run of the certivity pipeline whose input spec.md equals the
#       upload (read only: no pipeline run is started from here)
# mock: requirements come from a golden file in cases/*/expected.json (honestly labelled in the trace)
# engine: requirements come from feat/requirements-engine via ENGINE_ENTRYPOINT ("module:function")
BACKEND_MODE = os.environ.get("BACKEND_MODE", "runs")
ENGINE_ENTRYPOINT = os.environ.get("ENGINE_ENTRYPOINT", "")

# the pipeline checkouts and where their runs land: data/runs/<run_id>/ and, for the held-out samples of
# tools/sunday_runs.sh, ../sunday-data/<sample>/runs/<run_id>/; the held-out case and its runs came with
# the worktree on branch general
PIPELINE_ROOT = Path(os.environ.get("PIPELINE_ROOT", ROOT.parent / "Brezel" / "Butterbrezeln"))
PIPELINE_CHECKOUTS = [PIPELINE_ROOT, ROOT.parent / "Butterbrezeln-general"]
PIPELINE_RUN_DIRS = [Path(p) for p in os.environ.get("PIPELINE_RUN_DIRS", "").split(os.pathsep) if p] or [
    d for c in PIPELINE_CHECKOUTS for d in (c / "data" / "runs", c.parent / "sunday-data")]
PIPELINE_CASE_DIRS = [d for c in PIPELINE_CHECKOUTS for d in (c / "industrial-ai-hackathon" / "cases",
                                                              c / "tools" / "evalkit" / "mockcases")] + [CASES_DIR]
# run ids to show when several finished runs share a spec (e.g. the one whose submission was uploaded);
# otherwise the latest one
PIPELINE_RUN = [r.strip() for r in os.environ.get("PIPELINE_RUN", "").split(",") if r.strip()]

# auto: use LLM when credentials resolve, otherwise fall back to the rule set; off: rules only
LLM_MODE = os.environ.get("LLM_MODE", "auto")
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-opus-5-5")
