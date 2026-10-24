"""Run manifest: what ran, on which inputs, corpus, prompts and models, at what cost."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from pydantic import BaseModel

from app.compliance.redact import redact


class Manifest(BaseModel):
    run_id: str
    mode: str
    started_at: str
    finished_at: str | None
    git_commit: str | None
    settings: dict
    inputs: dict[str, str]
    corpus: dict
    prompt_versions: dict[str, str]
    models: dict[str, str]
    cost: dict
    review: dict | None


def prompt_version(instruction: str) -> str:
    return hashlib.sha256(instruction.encode("utf-8")).hexdigest()[:12]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def write_manifest(run_dir: Path, manifest: Manifest) -> Path:
    path = Path(run_dir) / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact(manifest), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_manifest(run_dir: Path) -> Manifest | None:
    path = Path(run_dir) / "manifest.json"
    return Manifest(**json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None
