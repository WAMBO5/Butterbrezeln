"""The challenge's regulation allowlist (`regulations/index.json`) and text file locations."""

from __future__ import annotations

import json
from pathlib import Path

from app.models import RegulationVersion


def regulation_dir(regulation: str) -> str:
    """`"UN R148"` → `"UN_R148"`, `"UN GTR 9"` → `"UN_GTR_9"`."""
    return regulation.replace(" ", "_")


def load_index(index_path: Path) -> list[RegulationVersion]:
    """Every version of every regulation in the index, base and latest."""
    entries = json.loads(Path(index_path).read_text(encoding="utf-8"))
    versions: list[RegulationVersion] = []
    for entry in entries:
        for v in entry.get("versions", []):
            files = v.get("files") or [{}]
            versions.append(
                RegulationVersion(
                    regulation=entry["regulation"],
                    title=entry.get("title", ""),
                    role=v["role"],
                    version_label=v["version_label"],
                    status=v.get("status", ""),
                    file_name=files[0].get("name", ""),
                    sha256=files[0].get("sha256", ""),
                )
            )
    return versions


def text_path(text_root: Path, regulation: str, role: str) -> Path:
    """`text_root/UN_R148/base/UN_R148_base.txt`."""
    d = regulation_dir(regulation)
    return Path(text_root) / d / role / f"{d}_{role}.txt"


def version_key(regulation: str, version_label: str) -> str:
    return f"{regulation}@{version_label}"
