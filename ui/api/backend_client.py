"""Adapters to the requirements backend: finished pipeline runs, a direct call, or a mock.

All return Requirement objects whose source cites regulation, version, page and paragraph, and
all log one trace step per selected regulation so every requirement links back to the step that
produced it.
"""

from __future__ import annotations

import importlib
import json
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Protocol

from . import pipeline_runs
from .config import BACKEND_MODE, CASES_DIR, ENGINE_ENTRYPOINT
from .models import Finding, PipelineRunInfo, Requirement, Source, SpecNote
from .sources import regulation_title, un_source
from .spec import parse_spec
from .trace import TraceRecorder


class BackendError(RuntimeError):
    """A failure the engineer can act on; its message is shown as is."""


NO_RUN = ("There is no finished pipeline run for this product description yet. Start one in the pipeline repo "
          "with `uv run certivity run <case folder>`; the result will then appear here.")


@dataclass
class Extraction:
    requirements: list[Requirement]
    case_id: str
    pipeline: PipelineRunInfo | None = None
    findings: list[Finding] | None = None  # set when the backend already matched the spec against them
    notes: list[SpecNote] = field(default_factory=list)


class BackendClient(Protocol):
    name: str

    def extract_requirements(self, spec_md: str, image: bytes | None, trace: TraceRecorder, parent: str) -> Extraction: ...


def _norm(text: str) -> str:
    return " ".join(text.split()).lower()


def _to_requirements(items: list[dict[str, Any]], trace: TraceRecorder, parent: str, agent: str,
                     how: str) -> list[Requirement]:
    """Groups submission-format requirements by regulation and logs one step per regulation."""
    groups: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for item in items:
        groups.setdefault(item["source"]["regulation"], []).append(item)
    out: list[Requirement] = []
    for regulation, group in groups.items():
        version = group[0]["source"].get("version")
        pages = sorted({g["source"].get("page") for g in group if g["source"].get("page")})
        with trace.step(agent, f"Regulation selected: {regulation} – {regulation_title(regulation)}",
                        parent=parent, inputs_summary=how,
                        tags={"regulation": regulation}) as step:
            step.add_source(un_source(regulation, version))
            for item in group:
                src = item["source"]
                out.append(Requirement(
                    id=item["id"], text=item["text"],
                    source=un_source(regulation, src.get("version"), src.get("page"), src.get("paragraph")),
                    trace_ids=[step.id],
                ))
            step.output(f"{len(group)} requirements from {regulation} v{version}, pages {pages[0]}–{pages[-1]}"
                        if pages else f"{len(group)} requirements from {regulation}")
    return out


class PipelineRunsBackend:
    """Shows the finished certivity pipeline run whose input spec.md equals the upload (read only)."""

    name = "runs"

    def extract_requirements(self, spec_md, image, trace, parent):
        ref = pipeline_runs.match(spec_md)
        if ref is None:
            raise BackendError(NO_RUN)
        imported = pipeline_runs.import_run(ref, parse_spec("spec.md", spec_md), trace, parent)
        return Extraction(imported.requirements, imported.info.case_id, imported.info, imported.findings, imported.notes)


class MockBackend:
    """Replays a golden answer (cases/<case>/expected.json) for a spec that matches the case's spec.md."""

    name = "mock"

    def extract_requirements(self, spec_md, image, trace, parent):
        wanted = _norm(spec_md)
        case = next((p for p in sorted(CASES_DIR.iterdir()) if (p / "expected.json").is_file() and (p / "spec.md").is_file()
                     and _norm((p / "spec.md").read_text(encoding="utf-8")) == wanted), None)
        if case is None:
            raise BackendError("Demo mode: there is no reference answer for this product description.")
        expected = json.loads((case / "expected.json").read_text(encoding="utf-8"))
        how = f"MOCK: golden file {case.name}/expected.json (spec matches exactly)"
        trace.record("requirements_engine", "Backend mode", parent=parent, outputs_summary=how,
                     sources=[Source(kind="dataset", label=f"{case.name}/expected.json", in_certivity_corpus=True)])
        requirements = _to_requirements(expected["requirements"], trace, parent, "requirements_engine (mock)", how)
        return Extraction(requirements, expected.get("case_id", case.name))


class RequirementsEngineClient:
    """Calls the real backend through ENGINE_ENTRYPOINT='package.module:function'.

    Assumed contract until the branch is read: function(spec_md: str, image: bytes | None) returns a
    main-goal submission dict ({"case_id", "requirements": [{id, text, source{regulation, version,
    page, paragraph}}]}) or just the requirements list.
    """

    name = "engine"

    def __init__(self, entrypoint: str = ENGINE_ENTRYPOINT):
        if ":" not in entrypoint:
            raise RuntimeError("BACKEND_MODE=engine needs ENGINE_ENTRYPOINT='module:function'")
        module, func = entrypoint.split(":", 1)
        self._fn = getattr(importlib.import_module(module), func)
        self.entrypoint = entrypoint

    def extract_requirements(self, spec_md, image, trace, parent):
        with trace.step("requirements_engine", "Call backend", parent=parent,
                        inputs_summary=f"{self.entrypoint}(spec.md, image={'yes' if image else 'no'})") as step:
            result = self._fn(spec_md, image)
            items = result["requirements"] if isinstance(result, dict) else result
            step.output(f"{len(items)} requirements received")
        case_id = result.get("case_id", "upload") if isinstance(result, dict) else "upload"
        return Extraction(_to_requirements(items, trace, step.id, "requirements_engine",
                                           f"Output of {self.entrypoint}"), case_id)


def make_backend(mode: str = BACKEND_MODE) -> BackendClient:
    if mode == "engine":
        return RequirementsEngineClient()
    return MockBackend() if mode == "mock" else PipelineRunsBackend()
