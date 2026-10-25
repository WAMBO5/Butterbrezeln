"""Records every agent step of a run (EU AI Act Art. 12-style logging).

Each step becomes a TraceEvent: emitted once when it starts (status "running") and again when it
ends, and appended to runs/<run_id>/trace.jsonl in its final state. Output objects (requirements,
findings, verdicts, suggestions) carry the ids of the steps that produced them.
"""

from __future__ import annotations

import hashlib
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

from .models import Source, TraceEvent


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Step:
    """Handle for a running step; mutate it inside the `with` block."""

    def __init__(self, event: TraceEvent):
        self.event = event

    @property
    def id(self) -> str:
        return self.event.id

    def add_source(self, source: Source) -> None:
        self.event.sources.append(source)

    def set_llm(self, model: str, prompt: str, tokens: dict[str, int] | None) -> None:
        self.event.model = model
        self.event.prompt_sha256 = sha256_text(prompt)
        self.event.tokens = tokens

    def output(self, summary: str) -> None:
        self.event.outputs_summary = summary

    def fallback(self, reason: str) -> None:
        self.event.status = "fallback"
        self.event.tags["fallback_reason"] = reason


class TraceRecorder:
    def __init__(self, run_id: str, path: Path, on_event: Callable[[TraceEvent], None]):
        self.run_id = run_id
        self.path = path
        self.on_event = on_event
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def _new(self, agent: str, action: str, parent: str | None, inputs_summary: str, tags: dict[str, str] | None) -> TraceEvent:
        return TraceEvent(
            id=f"ev-{uuid.uuid4().hex[:10]}",
            run_id=self.run_id,
            parent_id=parent,
            agent=agent,
            action=action,
            ts_start=now_iso(),
            inputs_summary=inputs_summary,
            tags=dict(tags or {}),
        )

    def _finish(self, event: TraceEvent) -> None:
        event.ts_end = event.ts_end or now_iso()
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(event.model_dump_json() + "\n")
        self.on_event(event.model_copy(deep=True))

    @contextmanager
    def step(self, agent: str, action: str, *, parent: str | None = None, inputs_summary: str = "",
             tags: dict[str, str] | None = None) -> Iterator[Step]:
        event = self._new(agent, action, parent, inputs_summary, tags)
        self.on_event(event.model_copy(deep=True))
        handle = Step(event)
        try:
            yield handle
        except Exception as exc:
            event.status = "error"
            event.outputs_summary = event.outputs_summary or f"Error: {exc}"
            self._finish(event)
            raise
        if event.status == "running":
            event.status = "ok"
        self._finish(event)

    def record(self, agent: str, action: str, *, parent: str | None = None, inputs_summary: str = "",
               outputs_summary: str = "", sources: list[Source] | None = None,
               tags: dict[str, str] | None = None) -> TraceEvent:
        """An instantaneous step, e.g. a human decision."""
        event = self._new(agent, action, parent, inputs_summary, tags)
        event.outputs_summary = outputs_summary
        event.sources = list(sources or [])
        event.status = "ok"
        event.ts_end = event.ts_start
        self._finish(event)
        return event

    def replay(self, agent: str, action: str, *, ts_start: str, ts_end: str | None, parent: str | None = None,
               inputs_summary: str = "", outputs_summary: str = "", model: str | None = None,
               tokens: dict[str, int] | None = None, sources: list[Source] | None = None,
               tags: dict[str, str] | None = None) -> TraceEvent:
        """A finished step that ran elsewhere (a pipeline run), logged with its original times."""
        event = self._new(agent, action, parent, inputs_summary, tags)
        event.ts_start, event.ts_end = ts_start, ts_end or ts_start
        event.outputs_summary, event.model, event.tokens = outputs_summary, model, tokens
        event.sources = list(sources or [])
        event.status = "ok"
        self._finish(event)
        return event
