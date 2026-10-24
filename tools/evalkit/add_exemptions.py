"""Add "deemed to comply" exemption provisions that a submission leaves out (code only, no model calls).

    uv run python add_exemptions.py out.json submission.json [--catalog data/catalog.sqlite]

A provision whose text says "deemed to comply" and whose top-level chapter the submission already cites
(same regulation, same first paragraph number, outside annexes) is added verbatim, cited to its base
version, page and paragraph. On dev this added 4 requirements, 2 of which the experts list.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
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
sys.path.insert(0, str(ROOT / "industrial-ai-hackathon" / "tools"))
from score_local import _paragraph_key  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("submission")
    ap.add_argument("--catalog", default=str(ROOT / "data" / "catalog.sqlite"))
    a = ap.parse_args()
    doc = json.loads(Path(a.submission).read_text())
    reqs = [dict(r) for r in doc["requirements"]]
    cited = {(r["source"]["regulation"], _paragraph_key(r["source"].get("paragraph"))) for r in reqs}
    chapters = {(reg, str(p).split(".")[0]) for reg, p in cited if p and not str(p).startswith("annex")}
    versions = {r["source"]["regulation"]: r["source"]["version"] for r in reqs}
    con = sqlite3.connect(f"file:{a.catalog}?mode=ro", uri=True, timeout=30)
    added = []
    for reg, label in versions.items():
        for para, page, text in con.execute("select paragraph, page_start, text from provisions "
                                            "where regulation = ? and version_label = ? and role = 'base'", (reg, label)):
            k = (reg, _paragraph_key(para))
            if k in cited or str(para).lower().startswith("annex") or (reg, str(k[1]).split(".")[0]) not in chapters:
                continue
            body = " ".join((text or "").split())
            if not re.search(r"deemed to comply", body, re.I) or len(body) > 1500:
                continue
            added.append({"id": "", "text": body, "source": {"regulation": reg, "version": label, "page": page,
                                                             "paragraph": para}})
    out = reqs + added
    for n, r in enumerate(out, start=1):
        r["id"] = f"R-{n:04d}"
    Path(a.out).write_text(json.dumps({**doc, "requirements": out}, indent=1, ensure_ascii=False))
    print(f"{a.out}: {len(out)} requirements (+{len(added)} exemptions: "
          + ", ".join(f"{r['source']['regulation']} {r['source']['paragraph']}" for r in added) + ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
