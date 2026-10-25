"""Starts the certivity pipeline on an uploaded spec (BACKEND_MODE=runs) and reports its progress.

The upload becomes a case folder `data/uploads/upload-<sha8>/` in the pipeline checkout, and
`./certivity <approach> run <case> --out <run dir>` runs as a subprocess there. Progress is read from the run's own
trace.jsonl and state.json, so a job also survives a reload of this API. Once the run has written
submission.json and lineage.json, `pipeline_runs.match` finds it by the spec's sha256 like any other run.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import LAUNCH_RUNS_DIR, PIPELINE_APPROACH, PIPELINE_CMD, PIPELINE_FAKE_LLM, PIPELINE_ROOT
from .models import PipelineJob, PipelineJobStep
from .pipeline_runs import STEP_ORDER, STEPS

UPLOADS_DIR = PIPELINE_ROOT / "data" / "uploads"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


class JobError(RuntimeError):
    """A reason the run cannot start; its message is shown as is."""


@dataclass
class Job:
    id: str
    run_dir: Path
    case_dir: Path
    log: Path
    spec_sha256: str
    started_at: str
    fake_llm: bool
    process: subprocess.Popen | None = None  # None: started before this API (re)loaded
    cancelled: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def launch_problem() -> str | None:
    """Why no run can be started from here, or None."""
    if PIPELINE_CMD:
        return None
    if not (PIPELINE_ROOT / "certivity").is_file() or not (PIPELINE_ROOT / "approaches" / PIPELINE_APPROACH).is_dir():
        return (f"No pipeline to start in {PIPELINE_ROOT}: it needs the ./certivity launcher and "
                f"approaches/{PIPELINE_APPROACH}. Set PIPELINE_ROOT or PIPELINE_APPROACH to match.")
    return None


def _command(case_dir: Path, run_dir: Path) -> list[str]:
    base = shlex.split(PIPELINE_CMD, posix=os.name != "nt") if PIPELINE_CMD else [str(PIPELINE_ROOT / "certivity"), PIPELINE_APPROACH]
    return [*base, *(["--fake-llm"] if PIPELINE_FAKE_LLM else []), "run", str(case_dir), "--out", str(run_dir)]


def _write_case(spec: bytes, image: bytes | None, image_name: str | None, sha: str) -> Path:
    case_dir = UPLOADS_DIR / f"upload-{sha[:8]}"
    case_dir.mkdir(parents=True, exist_ok=True)
    for old in case_dir.iterdir():  # the pipeline reads every *.md and every drawing in the folder
        if old.is_file() and (old.suffix.lower() == ".md" or old.suffix.lower() in IMAGE_SUFFIXES):
            old.unlink()
    (case_dir / "spec.md").write_bytes(spec)  # bytes as uploaded: the manifest's hash must match
    if image:
        suffix = Path(image_name or "").suffix.lower()
        (case_dir / f"drawing{suffix if suffix in IMAGE_SUFFIXES else '.png'}").write_bytes(image)
    return case_dir


def start(spec: bytes, image: bytes | None = None, image_name: str | None = None) -> PipelineJob:
    problem = launch_problem()
    if problem:
        raise JobError(problem)
    sha = hashlib.sha256(spec).hexdigest()
    with _lock:
        running = [j for j in _jobs.values() if status(j).status == "running"]
        same = next((j for j in running if j.spec_sha256 == sha), None)
        if same:
            return status(same)
        if running:
            raise JobError(f"Pipeline run {running[0].id} is still in progress; start this one when it has finished.")
        case_dir = _write_case(spec, image, image_name, sha)
        now = datetime.now(timezone.utc)
        run_id = f"{now:%Y%m%dT%H%M%S%f}Z-{case_dir.name}"
        run_dir = LAUNCH_RUNS_DIR / run_id
        run_dir.parent.mkdir(parents=True, exist_ok=True)
        log = case_dir / f"{run_id}.log"
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        with log.open("wb") as out:
            process = subprocess.Popen(_command(case_dir, run_dir), cwd=PIPELINE_ROOT, env=env, stdout=out,
                                       stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        job = Job(id=run_id, run_dir=run_dir, case_dir=case_dir, log=log, spec_sha256=sha,
                  started_at=now.isoformat(), fake_llm=PIPELINE_FAKE_LLM, process=process)
        _jobs[run_id] = job
    return status(job)


def get(job_id: str) -> Job | None:
    """A job of this API, or one it started before a reload (found by its run folder)."""
    with _lock:
        if job_id in _jobs:
            return _jobs[job_id]
        run_dir = (LAUNCH_RUNS_DIR / job_id).resolve()
        if run_dir.parent != LAUNCH_RUNS_DIR.resolve() or not (run_dir / "state.json").is_file():
            return None
        state = _read_json(run_dir / "state.json") or {}
        case_dir = Path(state.get("case_dir") or "")
        if UPLOADS_DIR.resolve() not in case_dir.resolve().parents or not (case_dir / "spec.md").is_file():
            return None  # only runs started from here
        job = Job(id=job_id, run_dir=run_dir, case_dir=case_dir, log=case_dir / f"{job_id}.log",
                  spec_sha256=hashlib.sha256((case_dir / "spec.md").read_bytes()).hexdigest(),
                  started_at=state.get("started_at") or "", fake_llm=False)
        _jobs[job_id] = job
        return job


def cancel(job: Job) -> PipelineJob:
    with job.lock:
        if job.process is not None and job.process.poll() is None:
            job.process.terminate()
            job.cancelled = True
    return status(job)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None  # missing or still being written


def _events(run_dir: Path) -> list[dict[str, Any]]:
    try:
        lines = (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except ValueError:
            continue  # the line being written
    return events


def _log_tail(path: Path, n: int = 12) -> list[str]:
    try:
        return [l for l in path.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()][-n:]
    except OSError:
        return []


def status(job: Job) -> PipelineJob:
    events = _events(job.run_dir)
    started = {e["step"] for e in events if e.get("event") == "step_start"}
    ended = {e["step"] for e in events if e.get("event") == "step_end"}
    order = STEP_ORDER + sorted(started - set(STEP_ORDER))
    steps = [PipelineJobStep(step=s, label=STEPS.get(s, ("", s))[1],
                             state="done" if s in ended else "running" if s in started else "pending") for s in order]
    finished = all((job.run_dir / f).is_file() for f in ("submission.json", "lineage.json")) and bool(
        (_read_json(job.run_dir / "manifest.json") or {}).get("finished_at"))
    exit_code = job.process.poll() if job.process is not None else None
    error = None
    if job.cancelled:
        state = "cancelled"
    elif finished:
        state = "done"
    elif job.process is not None:
        state = "running" if exit_code is None else "failed"
    else:  # started before a reload: only the run's own state tells
        pipeline_state = (_read_json(job.run_dir / "state.json") or {}).get("status")
        state = "failed" if pipeline_state in ("failed", "stopped") else "running"
    if state == "done":  # finished_at is written before the last step_end; steps that never ran are left out
        steps = [s.model_copy(update={"state": "done"}) for s in steps if s.state != "pending"]
    if state == "failed":
        error = (f"The pipeline stopped (exit code {exit_code}) without writing a submission."
                 if exit_code is not None else "The pipeline stopped without writing a submission.")
    calls = [e for e in events if e.get("event") in ("agent_end", "agent_error")]
    return PipelineJob(
        id=job.id, status=state, started_at=job.started_at, spec_sha256=job.spec_sha256, fake_llm=job.fake_llm,
        steps=steps, calls=len(calls), cost_usd=round(sum(e.get("cost_usd") or 0.0 for e in calls), 4), error=error,
        log_tail=_log_tail(job.log) if state in ("failed", "cancelled") else [],
    )
