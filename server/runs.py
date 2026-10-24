"""Run registry for the service: one background asyncio task per active run.

Everything else lives on disk under `data/runs/<run_id>/` (state, ledger, trace), so the server can
restart without losing a run, and events are streamed by tailing the run's `trace.jsonl`.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.compliance.oversight import HumanAction, OversightError
from app.config.settings import Settings
from app.pipeline.main import RunDeps, create_run, drive
from app.pipeline.oversight import resume_run
from app.pipeline.state import RunState

log = logging.getLogger(__name__)
FINISHED = ("done", "failed", "stopped")


class RunManager:
    def __init__(self, settings: Settings, deps: RunDeps):
        self.settings = settings
        self.deps = deps
        self.tasks: dict[str, asyncio.Task] = {}

    def run_dir(self, run_id: str) -> Path:
        path = (self.settings.runs_dir / run_id).resolve()
        if path.parent != self.settings.runs_dir.resolve():
            raise KeyError(run_id)
        return path

    def state(self, run_id: str) -> RunState:
        path = self.run_dir(run_id)
        if not (path / "state.json").exists():
            raise KeyError(run_id)
        return RunState.load(path)

    def list_runs(self) -> list[RunState]:
        if not self.settings.runs_dir.exists():
            return []
        states = []
        for d in self.settings.runs_dir.iterdir():
            if (d / "state.json").exists():
                try:
                    states.append(RunState.load(d))
                except Exception:  # a half-written run must not break the listing
                    log.exception("unreadable run state in %s", d)
        return sorted(states, key=lambda s: s.started_at, reverse=True)

    def _spawn(self, run_id: str, coro) -> None:
        async def guarded() -> None:
            try:
                await coro
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("run %s failed", run_id)

        self.tasks[run_id] = asyncio.create_task(guarded())

    def start(self, case_dir: Path, markets: list[str], mode: str) -> str:
        state = create_run(case_dir, markets=markets, mode=mode, settings=self.settings, run_dir=None, deps=self.deps)
        self._spawn(state.run_id, drive(state, self.deps))
        return state.run_id

    def save_upload(self, case_id: str, files: list[tuple[str, bytes]]) -> Path:
        safe = "".join(ch for ch in case_id if ch.isalnum() or ch in "-_") or "upload"
        target = self.settings.data_dir / "uploads" / f"{safe}-{uuid.uuid4().hex[:6]}"
        target.mkdir(parents=True)
        for name, data in files:
            (target / Path(name).name).write_bytes(data)
        return target

    def resume(self, run_id: str, checkpoint: str, actions: list[HumanAction]) -> None:
        state = self.state(run_id)
        if state.status != "awaiting_review" or state.checkpoint != checkpoint:
            raise OversightError(f"run is {state.status}, not waiting at {checkpoint}")
        self._spawn(run_id, resume_run(self.run_dir(run_id), checkpoint, actions, settings=self.settings,
                                       deps=self.deps))

    async def stop(self, run_id: str, reviewer: str, reason: str) -> None:
        state = self.state(run_id)
        if state.status in FINISHED:
            raise OversightError(f"run is already {state.status}")
        if state.status == "awaiting_review":
            action = HumanAction(checkpoint=state.checkpoint, reviewer=reviewer, action="stop", reason=reason,
                                 ts=datetime.now(timezone.utc).isoformat())
            self.resume(run_id, state.checkpoint, [action])
            return
        task = self.tasks.get(run_id)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        state = self.state(run_id)
        state.stopped = True
        state.human_actions.append({"checkpoint": state.checkpoint or "running", "reviewer": reviewer,
                                    "action": "stop", "reason": reason, "target_id": None, "payload": None,
                                    "ts": datetime.now(timezone.utc).isoformat()})
        state.save()
        self._spawn(run_id, drive(state, self.deps))

    def delete_upload(self, path: Path) -> None:
        shutil.rmtree(path, ignore_errors=True)
