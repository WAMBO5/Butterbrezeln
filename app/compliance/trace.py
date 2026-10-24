"""Run trace: every LLM event as a redacted JSON line, passed on to listeners (UI, SSE)."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from app.compliance.redact import redact


class Trace:
    def __init__(self, path: Path, listeners: list[Callable[[dict], None]] | None = None):
        self.path = Path(path)
        self.listeners = list(listeners or [])
        self._lock = threading.Lock()

    def __call__(self, event: dict) -> None:
        record = redact({"ts": datetime.now(timezone.utc).isoformat(), **event})
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        for listener in self.listeners:
            listener(record)
