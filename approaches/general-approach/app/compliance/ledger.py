"""Append-only, hash-chained decision ledger of a run (design spec section 14.4).

`ledger.jsonl` holds one record per event with the hashes of its input and output; the full
content goes to `calls/<seq>.json`. Changing any record breaks the chain.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from app.compliance.redact import redact

GENESIS = "0" * 64
LedgerKind = Literal["agent_call", "gate", "review", "loop_result", "human_action", "export", "note"]

_LOCKS: dict[Path, threading.Lock] = {}
_HEADS: dict[Path, tuple[int, str]] = {}
_GUARD = threading.Lock()


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class LedgerRecord(BaseModel):
    seq: int
    ts: str
    kind: LedgerKind
    actor: str
    input_hash: str | None
    output_hash: str | None
    meta: dict
    prev_hash: str
    hash: str


def _record_hash(record: dict) -> str:
    body = {k: v for k, v in record.items() if k != "hash"}
    return sha256(record["prev_hash"] + canonical(body))


class Ledger:
    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        self.path = (self.run_dir / "ledger.jsonl").resolve()
        with _GUARD:
            self._lock = _LOCKS.setdefault(self.path, threading.Lock())

    def _head(self) -> tuple[int, str]:
        if self.path not in _HEADS:
            records = self.records()
            _HEADS[self.path] = (records[-1].seq, records[-1].hash) if records else (0, GENESIS)
        return _HEADS[self.path]

    def append(self, kind: LedgerKind, actor: str, input_obj: Any, output_obj: Any, meta: dict) -> LedgerRecord:
        clean_in, clean_out = redact(input_obj), redact(output_obj)
        with self._lock:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            seq, prev = self._head()
            seq += 1
            record = {
                "seq": seq,
                "ts": datetime.now(timezone.utc).isoformat(),
                "kind": kind,
                "actor": actor,
                "input_hash": None if input_obj is None else sha256(canonical(clean_in)),
                "output_hash": None if output_obj is None else sha256(canonical(clean_out)),
                "meta": redact(meta),
                "prev_hash": prev,
            }
            record["hash"] = _record_hash(record)
            calls = self.run_dir / "calls"
            calls.mkdir(exist_ok=True)
            (calls / f"{seq}.json").write_text(canonical({"input": clean_in, "output": clean_out}), encoding="utf-8")
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(canonical(record) + "\n")
            _HEADS[self.path] = (seq, record["hash"])
            return LedgerRecord(**record)

    def records(self) -> list[LedgerRecord]:
        if not self.path.exists():
            return []
        return [LedgerRecord(**json.loads(line)) for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    def call(self, seq: int) -> dict:
        return json.loads((self.run_dir / "calls" / f"{seq}.json").read_text(encoding="utf-8"))


def verify_chain(run_dir: Path) -> list[str]:
    """[] when the chain is intact; otherwise one message per bad record."""
    path = Path(run_dir) / "ledger.jsonl"
    if not path.exists():
        return ["ledger.jsonl missing"]
    problems: list[str] = []
    prev = GENESIS
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            problems.append(f"seq {n}: not valid JSON")
            continue
        if record.get("seq") != n:
            problems.append(f"seq {n}: sequence number is {record.get('seq')}")
        if record.get("prev_hash") != prev:
            problems.append(f"seq {n}: prev_hash does not match the previous record")
        if _record_hash(record) != record.get("hash"):
            problems.append(f"seq {n}: hash does not match the record content")
        prev = record.get("hash", "")
    return problems
