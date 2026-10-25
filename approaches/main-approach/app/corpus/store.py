"""The parsed corpus in SQLite with an FTS5 index (design spec section 7).

Built once from `regulations/text`, keyed by each text file's sha256, so a re-build only parses
files that changed.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path

from app.corpus.index import text_path, version_key
from app.corpus.parser import iter_pages, paragraph_key, parse_regulation
from app.models import Provision, RegulationVersion, SearchHit, TocEntry

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (version_key TEXT PRIMARY KEY, sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS versions (
    version_key TEXT PRIMARY KEY, regulation TEXT, version_label TEXT, role TEXT, title TEXT,
    status TEXT, file_name TEXT, sha256 TEXT);
CREATE TABLE IF NOT EXISTS provisions (
    provision_id TEXT PRIMARY KEY, version_key TEXT, regulation TEXT, version_label TEXT, role TEXT,
    paragraph TEXT, pkey TEXT, heading_path TEXT, page_start INTEGER, page_end INTEGER, text TEXT,
    kind TEXT, refs TEXT, seq INTEGER);
CREATE INDEX IF NOT EXISTS provisions_version ON provisions (version_key, seq);
CREATE INDEX IF NOT EXISTS provisions_pkey ON provisions (version_key, pkey);
CREATE TABLE IF NOT EXISTS pages (version_key TEXT, page INTEGER, text TEXT, PRIMARY KEY (version_key, page));
CREATE VIRTUAL TABLE IF NOT EXISTS provisions_fts USING fts5(provision_id UNINDEXED, heading, text);
"""

_WORD_RE = re.compile(r"[^\W_]{3,}", re.UNICODE)


@dataclass
class BuildStats:
    parsed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def _depth(paragraph: str) -> int:
    """1 plus the dots of the numeric part; annex, part and appendix headings are depth 1."""
    parts = paragraph.split("~")[0].split(" ")
    last = parts[-1]
    if not re.fullmatch(r"\d+(?:\.\d+)*", last) or (len(parts) >= 2 and parts[-2] in ("Annex", "Part", "Appendix")):
        return 1
    return 1 + last.count(".")


def _heading(text: str) -> str:
    return text.split("\n", 1)[0][:120]


class CorpusStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._db.executescript(SCHEMA)

    # --- build ---------------------------------------------------------------------------------

    def build(self, versions: list[RegulationVersion], text_root: Path) -> BuildStats:
        stats = BuildStats()
        with self._lock, self._db:
            for v in versions:
                key = version_key(v.regulation, v.version_label)
                self._db.execute(
                    "INSERT OR REPLACE INTO versions VALUES (?,?,?,?,?,?,?,?)",
                    (key, v.regulation, v.version_label, v.role, v.title, v.status, v.file_name, v.sha256),
                )
                path = text_path(text_root, v.regulation, v.role)
                if not path.exists():
                    stats.missing.append(key)
                    continue
                raw = path.read_text(encoding="utf-8")
                digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                row = self._db.execute("SELECT sha256 FROM files WHERE version_key=?", (key,)).fetchone()
                if row and row["sha256"] == digest:
                    stats.unchanged.append(key)
                    continue
                self._replace_version(key, v, raw)
                self._db.execute("INSERT OR REPLACE INTO files VALUES (?,?)", (key, digest))
                stats.parsed.append(key)
        return stats

    def _replace_version(self, key: str, v: RegulationVersion, raw: str) -> None:
        old = [r["provision_id"] for r in self._db.execute("SELECT provision_id FROM provisions WHERE version_key=?", (key,))]
        self._db.executemany("DELETE FROM provisions_fts WHERE provision_id=?", [(p,) for p in old])
        self._db.execute("DELETE FROM provisions WHERE version_key=?", (key,))
        self._db.execute("DELETE FROM pages WHERE version_key=?", (key,))
        provisions = parse_regulation(raw, v.regulation, v.version_label, v.role)
        by_key = {paragraph_key(p.paragraph): p.provision_id for p in provisions}
        for seq, p in enumerate(provisions):
            refs = [self._resolve(ref, by_key) for ref in p.refs]
            self._db.execute(
                "INSERT INTO provisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (p.provision_id, key, p.regulation, p.version_label, p.role, p.paragraph, paragraph_key(p.paragraph),
                 json.dumps(p.heading_path), p.page_start, p.page_end, p.text, p.kind,
                 json.dumps(list(dict.fromkeys(refs))), seq),
            )
            self._db.execute("INSERT INTO provisions_fts VALUES (?,?,?)", (p.provision_id, _heading(p.text), p.text))
        self._db.executemany(
            "INSERT OR REPLACE INTO pages VALUES (?,?,?)", [(key, n, text) for n, text in iter_pages(raw)]
        )

    @staticmethod
    def _resolve(ref: str, by_key: dict[str | None, str]) -> str:
        kind, _, value = ref.partition(":")
        if kind == "para":
            return by_key.get(paragraph_key(value), ref)
        if kind == "annex":
            return by_key.get(paragraph_key(f"Annex {value}"), ref)
        return ref

    # --- queries -------------------------------------------------------------------------------

    def _rows(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    @staticmethod
    def _provision(row: sqlite3.Row) -> Provision:
        return Provision(
            provision_id=row["provision_id"], regulation=row["regulation"], version_label=row["version_label"],
            role=row["role"], paragraph=row["paragraph"], heading_path=json.loads(row["heading_path"]),
            page_start=row["page_start"], page_end=row["page_end"], text=row["text"], kind=row["kind"],
            refs=json.loads(row["refs"]),
        )

    def versions(self) -> list[RegulationVersion]:
        rows = self._rows("SELECT * FROM versions ORDER BY regulation, role")
        return [RegulationVersion(regulation=r["regulation"], title=r["title"], role=r["role"],
                                  version_label=r["version_label"], status=r["status"], file_name=r["file_name"],
                                  sha256=r["sha256"]) for r in rows]

    def has_text(self, regulation: str, version_label: str) -> bool:
        return bool(self._rows("SELECT 1 FROM files WHERE version_key=?", (version_key(regulation, version_label),)))

    def base_version(self, regulation: str) -> RegulationVersion | None:
        return next((v for v in self.versions() if v.regulation == regulation and v.role == "base"), None)

    def get(self, provision_id: str) -> Provision | None:
        rows = self._rows("SELECT * FROM provisions WHERE provision_id=?", (provision_id,))
        return self._provision(rows[0]) if rows else None

    def find(self, regulation: str, version_label: str, paragraph: str) -> Provision | None:
        rows = self._rows(
            "SELECT * FROM provisions WHERE version_key=? AND pkey=? ORDER BY seq LIMIT 1",
            (version_key(regulation, version_label), paragraph_key(paragraph)),
        )
        return self._provision(rows[0]) if rows else None

    def provisions(self, regulation: str, version_label: str) -> list[Provision]:
        rows = self._rows("SELECT * FROM provisions WHERE version_key=? ORDER BY seq",
                          (version_key(regulation, version_label),))
        return [self._provision(r) for r in rows]

    def toc(self, regulation: str, version_label: str, depth: int) -> list[TocEntry]:
        return [
            TocEntry(provision_id=p.provision_id, paragraph=p.paragraph, heading=_heading(p.text), page=p.page_start,
                     kind=p.kind, depth=_depth(p.paragraph))
            for p in self.provisions(regulation, version_label)
            if p.paragraph != "Introduction" and _depth(p.paragraph) <= depth
        ]

    def search(self, query: str, limit: int, role: str) -> list[SearchHit]:
        words = list(dict.fromkeys(w.casefold() for w in _WORD_RE.findall(query)))
        if not words:
            return []
        match = " OR ".join(f'"{w}"' for w in words)
        rows = self._rows(
            "SELECT p.*, bm25(provisions_fts) AS rank FROM provisions_fts f JOIN provisions p "
            "ON p.provision_id = f.provision_id WHERE provisions_fts MATCH ? AND p.role = ? AND p.kind != 'form' "
            "ORDER BY rank LIMIT ?",
            (match, role, limit),
        )
        return [
            SearchHit(provision_id=r["provision_id"], regulation=r["regulation"], version_label=r["version_label"],
                      paragraph=r["paragraph"], page=r["page_start"], snippet=" ".join(r["text"].split())[:300],
                      rank=float(r["rank"]))
            for r in rows
        ]

    def provisions_under(self, section_ids: list[str]) -> list[Provision]:
        out: dict[str, Provision] = {}
        for sid in section_ids:
            root = self.get(sid)
            if root is None:
                continue
            for p in self.provisions(root.regulation, root.version_label):
                if p.paragraph == root.paragraph or p.paragraph.startswith(root.paragraph + ".") or \
                        p.paragraph.startswith(root.paragraph + " "):
                    out.setdefault(p.provision_id, p)
        return list(out.values())

    def page_text(self, regulation: str, version_label: str, page: int) -> str | None:
        rows = self._rows("SELECT text FROM pages WHERE version_key=? AND page=?",
                          (version_key(regulation, version_label), page))
        return rows[0]["text"] if rows else None

    def page_count(self, regulation: str, version_label: str) -> int:
        rows = self._rows("SELECT MAX(page) AS n FROM pages WHERE version_key=?", (version_key(regulation, version_label),))
        return int(rows[0]["n"] or 0)
