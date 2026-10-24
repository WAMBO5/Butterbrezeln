"""Parser gate: every gold paragraph of the worked example must be a parsed provision on its base version."""

from __future__ import annotations

import json
import sys

from pipeline import config
from pipeline.catalog.corpus import provisions
from pipeline.catalog.normalise import paragraph_key


def check(expected_path=None) -> list[str]:
    path = expected_path or config.HACKATHON_DIR / "cases" / "dev-rear-lamp" / "expected.json"
    gold = json.loads(path.read_text(encoding="utf-8"))["requirements"]
    missing = []
    for r in gold:
        s = r["source"]
        want = paragraph_key(s.get("paragraph"))
        # "5.1.4.4.1. Table 3" cites the paragraph that holds the table
        want = (want or "").split(" table ")[0]
        have = {paragraph_key(p.paragraph): p for p in provisions(s["regulation"], s["version"])}
        prov = have.get(want)
        if prov is None:
            missing.append(f"{s['regulation']} {s['version']} {s.get('paragraph')} (p{s['page']}): not parsed")
        elif not (prov.page - 1 <= s["page"] <= prov.page_end + 1):
            missing.append(f"{s['regulation']} {s.get('paragraph')}: gold page {s['page']}, parsed {prov.page}-{prov.page_end}")
    return sorted(set(missing))


if __name__ == "__main__":
    problems = check()
    print("\n".join(problems) or "parser gate: all gold paragraphs found")
    sys.exit(1 if problems else 0)
