"""Obligation cache: extracted obligations per provision, keyed by the provision's normalised text
and the extractor version, so a changed text or prompt re-extracts only what changed."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path

from app.corpus.parser import normalize
from app.models import Obligation, Provision, ProvisionObligations

EXTRACTOR_VERSION = "x1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS obligations (
    provision_id TEXT, text_hash TEXT, extractor_version TEXT, obligations TEXT, reason TEXT,
    PRIMARY KEY (provision_id, text_hash, extractor_version));
CREATE TABLE IF NOT EXISTS verified (obligation_id TEXT PRIMARY KEY);
"""


def _text_hash(p: Provision) -> str:
    return hashlib.sha256(normalize(p.text).encode("utf-8")).hexdigest()


class ObligationCache:
    def __init__(self, db_path: Path):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._db.executescript(SCHEMA)

    def _key(self, p: Provision) -> tuple[str, str, str]:
        return p.provision_id, _text_hash(p), EXTRACTOR_VERSION

    def get(self, p: Provision) -> list[Obligation] | None:
        """The cached obligations ([] = none in this provision), or None on a cache miss."""
        with self._lock:
            row = self._db.execute(
                "SELECT obligations FROM obligations WHERE provision_id=? AND text_hash=? AND extractor_version=?",
                self._key(p)).fetchone()
            if row is None:
                return None
            verified = {r[0] for r in self._db.execute(
                "SELECT obligation_id FROM verified WHERE obligation_id LIKE ?", (p.provision_id + "/%",))}
        return [Obligation(**{**o, "verified": o["obligation_id"] in verified}) for o in json.loads(row[0])]

    def put(self, p: Provision, item: ProvisionObligations) -> list[Obligation]:
        obligations = [
            Obligation(**o.model_dump(), obligation_id=f"{p.provision_id}/{n}", provision_id=p.provision_id,
                       extractor_version=EXTRACTOR_VERSION, verified=False)
            for n, o in enumerate(item.obligations, start=1)
        ]
        with self._lock, self._db:
            self._db.execute("DELETE FROM obligations WHERE provision_id=?", (p.provision_id,))
            self._db.execute("DELETE FROM verified WHERE obligation_id LIKE ?", (p.provision_id + "/%",))
            self._db.execute("INSERT INTO obligations VALUES (?,?,?,?,?)",
                             (*self._key(p), json.dumps([o.model_dump() for o in obligations]),
                              item.no_obligation_reason))
        return obligations

    def mark_verified(self, ids: list[str]) -> None:
        with self._lock, self._db:
            self._db.executemany("INSERT OR IGNORE INTO verified VALUES (?)", [(i,) for i in ids])

    def unverified(self, ids: list[str]) -> list[str]:
        with self._lock:
            done = {r[0] for r in self._db.execute(
                f"SELECT obligation_id FROM verified WHERE obligation_id IN ({','.join('?' * len(ids))})", ids)} \
                if ids else set()
        return [i for i in ids if i not in done]

    def count(self) -> int:
        with self._lock:
            rows = self._db.execute("SELECT obligations FROM obligations").fetchall()
        return sum(len(json.loads(r[0])) for r in rows)
