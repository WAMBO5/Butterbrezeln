"""Paths and environment switches for the API."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent  # ui/
REPO = ROOT.parent
# one .env at the repository root for the whole product (see .env.example): the API key and models for real runs
# and the UI settings below. The approaches find the same file on their own; the environment wins over it
load_dotenv(REPO / ".env", override=False)
PACKAGE = REPO / "industrial-ai-hackathon"
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

# the pipeline: the approaches under approaches/ write each run to data/<approach>/runs/<run_id>/ (see ./certivity
# in the repository root), so every approach's finished runs show up here, as do the held-out samples of
# general-approach's tools/sunday_runs.sh in data/<approach>/sunday/<sample>/runs/. Runs on the scripted demo model
# never go to data/: they live in DEMO_DIR, with their own data folder, and are labelled as demo runs
PIPELINE_ROOT = Path(os.environ.get("PIPELINE_ROOT", REPO))
PIPELINE_CHECKOUTS = [PIPELINE_ROOT]
DEMO_DIR = RUNS_DIR / "pipeline-demo"
DEMO_RUNS_DIR = DEMO_DIR / "runs"
PIPELINE_RUN_DIRS = [Path(p) for p in os.environ.get("PIPELINE_RUN_DIRS", "").split(os.pathsep) if p] or [
    *sorted([*(PIPELINE_ROOT / "data").glob("*/runs"), *(PIPELINE_ROOT / "data").glob("*/sunday")]), DEMO_RUNS_DIR]
PIPELINE_CASE_DIRS = [PIPELINE_ROOT / "industrial-ai-hackathon" / "cases",
                      *sorted((PIPELINE_ROOT / "approaches").glob("*/tools/evalkit/mockcases")),
                      CASES_DIR, REPO / "testdata" / "fake-cases"]
# run ids to show when several finished runs share a spec (e.g. the one whose submission was uploaded);
# otherwise the latest real run
PIPELINE_RUN = [r.strip() for r in os.environ.get("PIPELINE_RUN", "").split(",") if r.strip()]

# Runs started from the UI go through the ./certivity launcher of one approach (general-approach holds the best
# dev score) and land in data/<approach>/runs/. A real run is paid: it stops at PIPELINE_MAX_COST_USD (a full
# dev run costs about $6.50). PIPELINE_FAKE_LLM=1 allows only the free scripted demo model, e.g. for a public demo
PIPELINE_APPROACH = os.environ.get("PIPELINE_APPROACH", "general-approach")
LAUNCH_RUNS_DIR = PIPELINE_ROOT / "data" / PIPELINE_APPROACH / "runs"
PIPELINE_CMD = os.environ.get("PIPELINE_CMD", "")
PIPELINE_FAKE_LLM = os.environ.get("PIPELINE_FAKE_LLM", "").lower() in ("1", "true", "yes")
PIPELINE_MAX_COST_USD = float(os.environ.get("PIPELINE_MAX_COST_USD") or 12)

# off (default): rule set only, no paid calls; on: use LLM for the spec check and country questions when
# credentials resolve, falling back to the rule set on any error. The model comes from the environment, as
# in the pipeline (AGENTS.md rule 3)
LLM_MODE = os.environ.get("LLM_MODE", "off")
LLM_MODEL = os.environ.get("LLM_MODEL") or os.environ.get("ANTHROPIC_MODEL", "")
