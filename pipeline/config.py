"""Configuration from the environment. Model ids are plain Anthropic ids (no LiteLLM prefix)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _path(name: str, default: str) -> Path:
    p = Path(os.environ.get(name) or default)
    return p if p.is_absolute() else ROOT / p


def _model(name: str, default: str) -> str:
    return (os.environ.get(name) or default).removeprefix("anthropic/")


HACKATHON_DIR = _path("HACKATHON_DIR", "industrial-ai-hackathon")
QDRANT_PATH = _path("QDRANT_PATH", "data/qdrant")
QDRANT_URL = os.environ.get("QDRANT_URL") or None
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY") or None
CACHE_DIR = _path("LLM_CACHE_DIR", "data/llm_cache")
RUNS_DIR = ROOT / "runs"
OUT_DIR = ROOT / "out"
TEAM_ID = os.environ.get("TEAM_ID") or "team-04"  # Certivity platform team id; override with the TEAM_ID env var

MODEL = _model("ANTHROPIC_MODEL", "claude-opus-5-5")
MODEL_FAST = _model("ANTHROPIC_MODEL_FAST", "claude-haiku-5-5")
MAX_CONCURRENCY = int(os.environ.get("LLM_MAX_CONCURRENCY") or 8)

INDEX_JSON = HACKATHON_DIR / "regulations" / "index.json"
TEXT_DIR = HACKATHON_DIR / "regulations" / "text"
PDF_DIR = HACKATHON_DIR / "regulations" / "pdf"
