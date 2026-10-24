"""Combine two independently built main-goal submissions by agreement (no model calls, no golden data).

    python3 ensemble.py out.json primary.json secondary.json [--case ID] [--team ID]

1. Agreement: keep a primary requirement only when the secondary also cites its regulation and paragraph.
2. Fill: add secondary requirements for paragraphs the primary does not cite, but only inside a
   section (regulation + first two levels of the paragraph number, or the same annex paragraph) that
   the primary already covers.
Both rules use only the two inputs, so they apply unchanged to the held-out case.
On dev (primary = pipeline run 3, secondary = lane v7) the judge-pair estimate was F2 0.759,
against 0.738 for run 3 alone.
"""
from __future__ import annotations

import argparse
import json
import os
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


sys.path.insert(0, str(_find_root() / "industrial-ai-hackathon" / "tools"))
from score_local import _paragraph_key  # noqa: E402


def key(r: dict) -> tuple:
    s = r["source"]
    return s["regulation"], _paragraph_key(s.get("paragraph")) or f"p{s['page']}"


def section(k: tuple) -> tuple:
    return k[0], ".".join(str(k[1]).split(".")[:2])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("primary")
    ap.add_argument("secondary")
    ap.add_argument("--case")
    ap.add_argument("--team")
    a = ap.parse_args()
    p_doc, s_doc = json.loads(Path(a.primary).read_text()), json.loads(Path(a.secondary).read_text())
    P, S = p_doc["requirements"], s_doc["requirements"]
    p_keys, s_keys = {key(r) for r in P}, {key(r) for r in S}
    p_sections = {section(k) for k in p_keys}
    agreed = [r for r in P if key(r) in s_keys]
    fill = [r for r in S if key(r) not in p_keys and section(key(r)) in p_sections]
    out = [dict(r) for r in agreed + fill]
    out.sort(key=lambda r: (r["source"]["regulation"], r["source"]["page"], str(r["source"].get("paragraph"))))
    for n, r in enumerate(out, start=1):
        r["id"] = f"R-{n:04d}"
    doc = {"team_id": a.team or p_doc["team_id"], "case_id": a.case or p_doc["case_id"], "requirements": out}
    Path(a.out).write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    print(f"{a.out}: {len(out)} requirements = {len(agreed)} agreed of {len(P)} primary "
          f"+ {len(fill)} filled from {len(S)} secondary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
