"""Run store and the analysis pipeline: spec -> requirements -> validation -> findings -> verdicts."""

from __future__ import annotations

import threading
import uuid
from pathlib import Path

from .assess import assess_country, assess_spec
from .backend_client import BackendError, make_backend
from .config import BACKEND_MODE, RUNS_DIR
from .countries import country_name
from .llm import LLM
from .models import RunResult, Source, TraceEvent
from .sources import spec_source, validate_requirements
from .spec import ParsedSpec, parse_spec
from .trace import TraceRecorder, now_iso


class RunState:
    def __init__(self, result: RunResult, directory: Path):
        self.result = result
        self.dir = directory
        self.lock = threading.RLock()
        self.events: dict[str, TraceEvent] = {}  # latest state per event id, in start order
        self.stream: list[TraceEvent] = []  # every emission, for SSE
        self.trace = TraceRecorder(result.run_id, directory / "trace.jsonl", self._on_event)

    def _on_event(self, event: TraceEvent) -> None:
        with self.lock:
            self.events[event.id] = event
            self.stream.append(event)

    @property
    def spec(self) -> ParsedSpec:
        return parse_spec(self.result.spec_name, self.result.spec_text)

    def save(self) -> None:
        with self.lock:
            (self.dir / "result.json").write_text(self.result.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, directory: Path) -> "RunState":
        state = cls(RunResult.model_validate_json((directory / "result.json").read_text(encoding="utf-8")), directory)
        trace_file = directory / "trace.jsonl"
        if trace_file.is_file():
            for line in trace_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    event = TraceEvent.model_validate_json(line)
                    state.events[event.id] = event
                    state.stream.append(event)
        return state


class RunStore:
    def __init__(self, root: Path = RUNS_DIR):
        self.root = root
        self.runs: dict[str, RunState] = {}
        self.llm = LLM()
        self._lock = threading.Lock()

    def get(self, run_id: str) -> RunState | None:
        with self._lock:
            if run_id in self.runs:
                return self.runs[run_id]
            directory = self.root / run_id
            if run_id.isalnum() and (directory / "result.json").is_file():
                self.runs[run_id] = RunState.load(directory)
                return self.runs[run_id]
        return None

    def start(self, spec_name: str, spec_text: str, image: bytes | None, countries: list[str]) -> RunState:
        run_id = uuid.uuid4().hex[:12]
        directory = self.root / run_id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "spec.md").write_text(spec_text, encoding="utf-8")
        if image:
            (directory / "image.png").write_bytes(image)
        result = RunResult(run_id=run_id, created_at=now_iso(), spec_name=spec_name, spec_text=spec_text,
                           countries=countries, backend_mode=BACKEND_MODE, has_image=bool(image))
        state = RunState(result, directory)
        with self._lock:
            self.runs[run_id] = state
        state.save()
        threading.Thread(target=self._execute, args=(state, image), daemon=True).start()
        return state

    def _execute(self, state: RunState, image: bytes | None) -> None:
        result, trace = state.result, state.trace
        try:
            names = ", ".join(country_name(c) for c in result.countries)
            with trace.step("orchestrator", "Analysis", inputs_summary=f"{result.spec_name} · Countries: {names}") as root:
                with trace.step("spec_parser", "Read spec", parent=root.id) as step:
                    spec = parse_spec(result.spec_name, result.spec_text)
                    step.add_source(spec_source(spec.name, [1, len(spec.lines)]))
                    step.output(f"\"{spec.title}\" · {len(spec.lines)} lines · Sections: "
                                + ", ".join(s.title for s in spec.sections))

                backend = make_backend()
                with trace.step("requirements_engine", "Derive requirements", parent=root.id,
                                inputs_summary=f"Backend: {backend.name}") as step:
                    extraction = backend.extract_requirements(result.spec_text, image, trace, step.id)
                    requirements, case_id, pipeline = extraction.requirements, extraction.case_id, extraction.pipeline
                    regs = sorted({r.source.regulation for r in requirements})
                    step.output(f"{len(requirements)} requirements from {len(regs)} regulations: {', '.join(regs)}"
                                + (f" · pipeline run {pipeline.run_id}" if pipeline else ""))
                    if pipeline:
                        step.add_source(Source(kind="dataset", label=pipeline.path, title=f"Pipeline run {pipeline.run_id}",
                                               in_certivity_corpus=False))
                with state.lock:
                    result.requirements, result.pipeline = requirements, pipeline
                state.save()

                with trace.step("validator", "Check citations (tools/validate.py)", parent=root.id,
                                inputs_summary="Platform validator against regulations/index.json") as step:
                    validation = validate_requirements(requirements, case_id)
                    step.add_source(Source(kind="dataset", label="regulations/index.json", in_certivity_corpus=True))
                    step.output("valid" if validation.ok else f"{len(validation.problems)} problems")
                    if not validation.ok:
                        step.fallback("Validation failed")
                with state.lock:
                    result.validation = validation

                if extraction.findings is not None:  # the pipeline matched every requirement to the parts itself
                    with trace.step("spec_assessor", "Check spec against requirements", parent=root.id,
                                    inputs_summary="Matching decisions of the pipeline run (requirement_matcher, match_reviewer)",
                                    tags={"source": "pipeline"}) as step:
                        findings, notes, mode = extraction.findings, extraction.notes, "pipeline"
                        uncertain = sum(r.pipeline is not None and r.pipeline.state == "uncertain" for r in requirements)
                        met = sum(f.status == "met" for f in findings)
                        step.output(f"{len(findings) - met} pieces of evidence needed, {uncertain} of them with uncertain applicability · "
                                    f"{met} met · {len(notes)} open points in the description")
                else:
                    with trace.step("spec_assessor", "Check spec against requirements", parent=root.id,
                                    inputs_summary=f"LLM: {self.llm.model}" if self.llm.available else "Rule set") as step:
                        findings, notes, mode = assess_spec(spec, requirements, self.llm, trace, step.id)
                        step.output(f"{len(findings)} findings · {len(notes)} spec notes · mode: {mode}")
                with state.lock:
                    result.findings, result.spec_notes, result.llm_mode = findings, notes, mode
                state.save()

                with trace.step("country_assessor", "Assess countries", parent=root.id,
                                inputs_summary=f"{len(result.countries)} countries · traffic-light rule compute_status()") as step:
                    for iso3 in result.countries:
                        verdict = assess_country(iso3, spec, requirements, findings, trace, step.id)
                        with state.lock:
                            result.verdicts[iso3] = verdict
                    counts = {c: sum(v.status == c for v in result.verdicts.values()) for c in ("green", "yellow", "red", "grey")}
                    step.output(f"green {counts['green']} · yellow {counts['yellow']} · red {counts['red']} · grey {counts['grey']}")
                root.output("done")
            with state.lock:
                result.status = "done"
        except Exception as exc:  # the run must end in a visible state, never hang
            with state.lock:
                result.status = "error"
                result.error = str(exc) if isinstance(exc, BackendError) else f"{exc.__class__.__name__}: {exc}"
        state.save()
