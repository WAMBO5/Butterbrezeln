"""Data model shared by the API and the web UI (mirrored in web/src/types.ts)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SourceKind = Literal["spec", "un_regulation", "country_profile", "external", "dataset"]
FindingStatus = Literal["met", "open", "conflict"]
Effort = Literal["documentation", "testing", "design"]
VerdictStatus = Literal["green", "yellow", "red", "grey"]
Regime = Literal["unece_1958", "national", "not_covered"]
Decision = Literal["open", "accepted", "rejected"]
EventStatus = Literal["running", "ok", "fallback", "error"]


class Source(BaseModel):
    kind: SourceKind
    label: str
    title: str | None = None  # e.g. the regulation's title from regulations/index.json
    regulation: str | None = None
    version: str | None = None
    page: int | None = None
    paragraph: str | None = None
    pdf_url: str | None = None
    sha256: str | None = None
    spec_lines: list[int] | None = None  # [first, last], 1-based
    url: str | None = None
    href: str | None = None  # what the UI opens: local PDF with #page=N, remote PDF or web page
    in_certivity_corpus: bool = False


class LineageLink(BaseModel):
    """One link of the pipeline's chain for a requirement (lineage.json), resolved to our trace."""
    step: str  # part | fact | scope_decision | provision | obligation | match_decision
    ref: str
    summary: str
    trace_id: str | None = None
    spec_lines: list[int] | None = None  # where a fact's quote stands in the spec


class PipelineDetail(BaseModel):
    """What the certivity pipeline recorded for one requirement (requirements.json + lineage.json)."""
    state: str  # applicable | uncertain
    reason: str = ""
    evidence_status: str = ""  # evidence_needed | met
    test_case: str = ""
    parts: list[str] = Field(default_factory=list)
    lineage: list[LineageLink] = Field(default_factory=list)


class Requirement(BaseModel):
    id: str
    text: str
    source: Source
    trace_ids: list[str] = Field(default_factory=list)
    pipeline: PipelineDetail | None = None


class Finding(BaseModel):
    id: str
    requirement_id: str
    regulation: str
    status: FindingStatus
    effort: Effort | None = None  # only for conflict
    spec_lines: list[int] | None = None
    explanation: str
    suggestion: str | None = None  # concrete spec change, for conflict
    trace_ids: list[str] = Field(default_factory=list)


class SpecNote(BaseModel):
    id: str
    text: str
    spec_lines: list[int] | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)


class Suggestion(BaseModel):
    id: str
    country: str
    requirement_id: str | None = None
    deviation_id: str | None = None
    spec_section: str
    change: str
    reason: str
    effort: Effort
    sources: list[Source] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    decision: Decision = "open"


class CountryVerdict(BaseModel):
    iso3: str
    name: str
    status: VerdictStatus
    regime: Regime
    reasons: list[str] = Field(default_factory=list)
    blocking_finding_ids: list[str] = Field(default_factory=list)
    open_evidence_count: int = 0
    suggestions: list[Suggestion] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)


class TraceEvent(BaseModel):
    id: str
    run_id: str
    parent_id: str | None = None
    agent: str
    action: str
    ts_start: str
    ts_end: str | None = None
    status: EventStatus = "running"
    inputs_summary: str = ""
    outputs_summary: str = ""
    model: str | None = None
    prompt_sha256: str | None = None
    tokens: dict[str, int] | None = None
    sources: list[Source] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)


class Validation(BaseModel):
    ok: bool
    problems: list[str] = Field(default_factory=list)


class QAEntry(BaseModel):
    id: str
    country: str
    question: str
    answer: str
    suggestion_ids: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)


class ScopeExclusion(BaseModel):
    regulation: str
    reason: str


class LedgerCheck(BaseModel):
    records: int
    intact: bool
    problems: list[str] = Field(default_factory=list)
    head: str | None = None  # hash of the last record


class PipelineRunInfo(BaseModel):
    """The certivity pipeline run a result was read from (BACKEND_MODE=runs)."""
    run_id: str
    case_id: str
    path: str
    started_at: str | None = None
    finished_at: str | None = None
    git_commit: str | None = None
    cost_usd: float | None = None
    inherited_cost_usd: float | None = None  # a replay: what the reused steps of replay_of cost
    models: dict[str, str] = Field(default_factory=dict)  # agent -> model
    funnel: dict[str, int] = Field(default_factory=dict)  # state.json stage_counts
    product_type: str | None = None
    vehicle_categories: list[str] = Field(default_factory=list)
    parts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    open_issues: list[str] = Field(default_factory=list)  # checks the pipeline could not settle
    give_ups: list[str] = Field(default_factory=list)
    review_issues: int = 0  # findings of the output auditor
    excluded: list[ScopeExclusion] = Field(default_factory=list)
    score: dict | None = None  # dev cases only: against expected.json
    replay_of: str | None = None  # tools/replay_from_match.py reused this run's profile and scope plan
    ledger: LedgerCheck | None = None
    label: str | None = None  # submission.provenance.json, e.g. "Unreviewed AI draft — not for compliance use"


class PipelineJobStep(BaseModel):
    step: str
    label: str
    state: Literal["pending", "running", "done"] = "pending"


class PipelineJob(BaseModel):
    """A certivity pipeline run started from the UI on an uploaded spec."""
    id: str  # the run folder's name
    status: Literal["running", "done", "failed", "cancelled"]
    started_at: str
    spec_sha256: str
    fake_llm: bool = False
    steps: list[PipelineJobStep] = Field(default_factory=list)
    calls: int = 0
    cost_usd: float = 0.0
    error: str | None = None
    log_tail: list[str] = Field(default_factory=list)


class RunResult(BaseModel):
    run_id: str
    created_at: str
    status: Literal["running", "done", "error"] = "running"
    error: str | None = None
    spec_name: str
    spec_text: str
    countries: list[str]
    backend_mode: str
    llm_mode: str = "rules"
    has_image: bool = False
    pipeline: PipelineRunInfo | None = None
    requirements: list[Requirement] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    spec_notes: list[SpecNote] = Field(default_factory=list)
    verdicts: dict[str, CountryVerdict] = Field(default_factory=dict)
    validation: Validation | None = None
    qa: list[QAEntry] = Field(default_factory=list)


class AskRequest(BaseModel):
    question: str


class DecisionRequest(BaseModel):
    decision: Decision
    note: str | None = None
