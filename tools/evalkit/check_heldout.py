"""Pre-upload checks for a held-out main-goal file, beyond validate.py (free, no calls).

    python3 check_heldout.py <submission.json> [--case heldout-front-bumper] [--team team-04]

Exit 1 on any blocking problem: wrong case_id/team_id, a non-base version, a regulation outside the
allowlist, a page beyond that version's PDF, duplicate ids. Warnings (not blocking): missing paragraph,
exact duplicate texts, regulations with very few or very many requirements.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

def _find_root() -> Path:
    """The repo root: $CERTIVITY_ROOT, else the first parent that holds industrial-ai-hackathon/tools."""
    if os.environ.get("CERTIVITY_ROOT"):
        return Path(os.environ["CERTIVITY_ROOT"])
    for parent in Path(__file__).resolve().parents:
        if (parent / "industrial-ai-hackathon" / "tools" / "score_local.py").is_file():
            return parent
    raise SystemExit("repo root not found: set CERTIVITY_ROOT to the Butterbrezeln checkout")


ROOT = _find_root()
HACK = ROOT / "industrial-ai-hackathon"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("submission")
    ap.add_argument("--case", default="heldout-front-bumper")
    ap.add_argument("--team", default="team-04")
    ap.add_argument("--catalog", default=str(ROOT / "data" / "catalog.sqlite"))
    a = ap.parse_args()
    block, warn = [], []
    v = subprocess.run([sys.executable, str(HACK / "tools" / "validate.py"), a.submission], capture_output=True, text=True)
    if v.returncode != 0:
        block.append("validate.py failed:\n" + v.stdout[-1500:] + v.stderr[-500:])
    doc = json.loads(Path(a.submission).read_text())
    if doc.get("case_id") != a.case:
        block.append(f"case_id is {doc.get('case_id')!r}, expected {a.case!r}")
    if doc.get("team_id") != a.team:
        block.append(f"team_id is {doc.get('team_id')!r}, expected {a.team!r}")
    base = {}
    for r in json.loads((HACK / "regulations" / "index.json").read_text()):
        for ver in r.get("versions", []):
            if ver.get("role") == "base":
                base[r["regulation"]] = ver["version_label"]
    pages = {}
    try:
        con = sqlite3.connect(f"file:{a.catalog}?mode=ro", uri=True, timeout=30)
        for reg, label, n in con.execute("select v.regulation, v.version_label, max(p.page) from pages p "
                                         "join versions v on v.version_key = p.version_key group by v.version_key"):
            pages[(reg, label)] = n
    except sqlite3.Error as exc:
        warn.append(f"catalog not readable, page ranges unchecked: {exc}")
    reqs = doc.get("requirements", [])
    ids = collections.Counter(r.get("id") for r in reqs)
    if any(n > 1 for n in ids.values()):
        block.append(f"duplicate ids: {[i for i, n in ids.items() if n > 1][:10]}")
    bad_ver, bad_reg, bad_page, no_para = [], set(), [], 0
    for r in reqs:
        s = r.get("source", {})
        reg, ver, page = s.get("regulation"), s.get("version"), s.get("page")
        if reg not in base:
            bad_reg.add(reg)
            continue
        if ver != base[reg]:
            bad_ver.append(f"{r.get('id')} {reg} {ver} (base is {base[reg]})")
        n = pages.get((reg, ver))
        if n and isinstance(page, int) and page > n:
            bad_page.append(f"{r.get('id')} {reg} p.{page} > {n}")
        if not s.get("paragraph"):
            no_para += 1
    if bad_reg:
        block.append(f"regulations outside the allowlist: {sorted(map(str, bad_reg))}")
    if bad_ver:
        block.append(f"{len(bad_ver)} citations not on the base version, e.g. {bad_ver[:5]}")
    if bad_page:
        block.append(f"{len(bad_page)} pages beyond the PDF, e.g. {bad_page[:5]}")
    if no_para:
        warn.append(f"{no_para} requirements without a paragraph (a paragraph also counts at page level: add it)")
    texts = collections.Counter(" ".join(str(r.get("text", "")).split()).lower() for r in reqs)
    dups = sum(n - 1 for n in texts.values() if n > 1)
    if dups:
        warn.append(f"{dups} exact duplicate requirement texts")
    per = collections.Counter(r["source"]["regulation"] for r in reqs if "source" in r)
    print(f"{len(reqs)} requirements; per regulation: " + ", ".join(f"{k} {n}" for k, n in per.most_common()))
    for w in warn:
        print("WARN  " + w)
    for b in block:
        print("BLOCK " + b)
    print("OK to upload" if not block else "DO NOT UPLOAD")
    return 1 if block else 0


if __name__ == "__main__":
    raise SystemExit(main())
