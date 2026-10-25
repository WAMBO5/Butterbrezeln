"""Citable sources: regulations/index.json, local PDFs, and the package's own validator."""

from __future__ import annotations

import importlib.util
import json
import sys
from functools import lru_cache
from typing import Any

from .config import INDEX_PATH, PDF_DIR, TOOLS_DIR
from .models import Requirement, Source, Validation


def slug(regulation: str) -> str:
    # same rule as tools/fetch_regulations.py
    return "_".join(regulation.replace("/", " ").split())


@lru_cache(maxsize=1)
def index() -> list[dict[str, Any]]:
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _by_regulation() -> dict[str, dict[str, Any]]:
    return {entry["regulation"]: entry for entry in index()}


def regulation_title(regulation: str) -> str:
    entry = _by_regulation().get(regulation)
    return entry["title"] if entry else regulation


def _version_file(regulation: str, version: str | None) -> tuple[str, dict[str, Any]] | None:
    entry = _by_regulation().get(regulation)
    if not entry:
        return None
    for v in entry.get("versions", []):
        if version is None or v.get("version_label") == version:
            files = v.get("files") or []
            if files:
                return v.get("role", "base"), files[0]
    return None


def un_source(regulation: str, version: str | None, page: int | None = None, paragraph: str | None = None) -> Source:
    label = regulation if version is None else f"{regulation} v{version}"
    if page:
        label += f", p. {page}"
    if paragraph:
        label += f", §{paragraph}"
    found = _version_file(regulation, version)
    pdf_url = sha = href = None
    if found:
        role, file = found
        pdf_url, sha = file.get("pdf_url"), file.get("sha256")
        local = PDF_DIR / slug(regulation) / role / file["name"]
        anchor = f"#page={page}" if page else ""
        if local.is_file():
            href = f"/api/sources/pdf/{slug(regulation)}/{role}/{file['name']}{anchor}"
        elif pdf_url:
            href = pdf_url + anchor
    return Source(
        kind="un_regulation", label=label, title=regulation_title(regulation), regulation=regulation, version=version, page=page,
        paragraph=paragraph, pdf_url=pdf_url, sha256=sha, href=href, in_certivity_corpus=True,
    )


def spec_source(spec_name: str, lines: list[int] | None) -> Source:
    label = spec_name
    if lines:
        label += f", line {lines[0]}" if lines[0] == lines[1] else f", lines {lines[0]}–{lines[1]}"
    return Source(kind="spec", label=label, spec_lines=lines, in_certivity_corpus=False)


@lru_cache(maxsize=1)
def _validator_module():
    spec = importlib.util.spec_from_file_location("certivity_validate", TOOLS_DIR / "validate.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module  # @dataclass looks the module up there
    spec.loader.exec_module(module)
    return module


def submission(requirements: list[Requirement], case_id: str, team_id: str = "butterbrezeln") -> dict[str, Any]:
    """The requirements in the platform's main-goal format (schemas/submission_main.schema.json)."""
    out = []
    for r in requirements:
        src = {"regulation": r.source.regulation, "version": r.source.version, "page": r.source.page}
        if r.source.paragraph:
            src["paragraph"] = r.source.paragraph
        out.append({"id": r.id, "text": r.text, "source": src})
    return {"team_id": team_id, "case_id": case_id, "requirements": out}


def validate_requirements(requirements: list[Requirement], case_id: str) -> Validation:
    module = _validator_module()
    problems = module.validate(submission(requirements, case_id), "main", index=index())
    return Validation(ok=not problems, problems=[str(p) for p in problems])
