"""Legal pipeline: parse every base regulation and upsert provisions into Qdrant. Re-run when PDFs change.

    uv run python -m pipeline.legal            # index what is not indexed yet
    uv run python -m pipeline.legal --rebuild  # drop and rebuild the collection
"""

from __future__ import annotations

import argparse
import sys
import time

from pipeline.catalog.corpus import base_versions
from pipeline.catalog.gate import check
from pipeline.rag import store


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--force", action="store_true", help="index even if the parser gate fails")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    problems = check()
    print("parser gate:", "ok" if not problems else f"{len(problems)} problems")
    for p in problems:
        print("  ", p)
    if problems and not args.force:
        print("error: fix the parser (or pass --force) before indexing", file=sys.stderr)
        return 1

    if args.rebuild and store.client().collection_exists(store.COLLECTION):
        store.client().delete_collection(store.COLLECTION)
    done = store.indexed_versions()
    todo = [v for v in base_versions() if (v.regulation, v.version_label) not in done]
    print(f"{len(done)} versions indexed, {len(todo)} to index")
    reuse = store.stored_vectors() if todo else {}
    print(f"{len(reuse)} stored vectors available for reuse", flush=True)
    for v in todo:
        t0 = time.time()
        n, embedded = store.upsert_version(v, reuse=reuse)
        print(f"  {v.regulation} {v.version_label}: {n} provisions, {embedded} embedded, in {time.time() - t0:.0f}s", flush=True)
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
