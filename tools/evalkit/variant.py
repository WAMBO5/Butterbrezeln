"""Build an upload variant from one or more main-goal submissions, without model calls.

    python3 variant.py out.json a.json [b.json ...] [--drop-reg "UN R26,UN R94"] [--only-reg ...]
                       [--drop-annex] [--case ID] [--team ID] [--dedup 0.82]

- Union of the inputs in the order given: a requirement of a later file is dropped when an earlier one
  has the same regulation and paragraph key and similar text (token Jaccard >= --dedup), or the same text.
- --drop-reg / --only-reg: leave regulations out, or keep only these.
- --new-paragraphs-only: later inputs only fill paragraphs the earlier ones do not cover.
- --drop-annex: leave out requirements whose paragraph starts with "Annex".
- Ids are renumbered R-0001...; extra fields (state, reason, ...) are kept.
Then run validate.py / check_heldout.py on the output.
"""
from __future__ import annotations

import argparse
import json
import os
import re
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


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+(?:[.,][0-9]+)?", text.lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--drop-reg", default="")
    ap.add_argument("--only-reg", default="")
    ap.add_argument("--drop-annex", action="store_true")
    ap.add_argument("--case")
    ap.add_argument("--team")
    ap.add_argument("--dedup", type=float, default=0.82)
    ap.add_argument("--new-paragraphs-only", action="store_true",
                    help="from the 2nd input on, add only requirements whose (regulation, paragraph) no earlier input has")
    a = ap.parse_args()
    drop = {s.strip() for s in a.drop_reg.split(",") if s.strip()}
    only = {s.strip() for s in a.only_reg.split(",") if s.strip()}
    docs = [json.loads(Path(p).read_text()) for p in a.inputs]
    kept: list[dict] = []
    seen: dict[tuple, list[set[str]]] = {}
    texts: set[str] = set()
    stats = []
    for i, (path, doc) in enumerate(zip(a.inputs, docs)):
        added = 0
        earlier = set(seen)
        for r in doc["requirements"]:
            s = r["source"]
            if s["regulation"] in drop or (only and s["regulation"] not in only):
                continue
            if a.drop_annex and str(s.get("paragraph", "")).strip().lower().startswith("annex"):
                continue
            norm = " ".join(r["text"].split()).lower()
            key = (s["regulation"], _paragraph_key(s.get("paragraph")) or f"p{s['page']}")
            tk = tokens(r["text"])
            if a.new_paragraphs_only and i > 0 and key in earlier:
                continue
            if norm in texts or any(jaccard(tk, other) >= a.dedup for other in seen.get(key, [])):
                continue
            texts.add(norm)
            seen.setdefault(key, []).append(tk)
            kept.append(dict(r))
            added += 1
        stats.append(f"{Path(path).name}: +{added}/{len(doc['requirements'])}")
    for n, r in enumerate(kept, start=1):
        r["id"] = f"R-{n:04d}"
    out = {"team_id": a.team or docs[0]["team_id"], "case_id": a.case or docs[0]["case_id"], "requirements": kept}
    Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"{a.out}: {len(kept)} requirements ({'; '.join(stats)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
