"""Data contracts between every step (design spec section 8).

Field names are binding. Models used as an agent output have no default values, so every field
is required in the structured-output schema the SDK sends.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TEXT_LIMIT = 2000

ProvisionKind = Literal[
    "scope", "definition", "administrative", "requirement", "test_procedure", "conformity", "transitional", "form", "other"
]
DecisionState = Literal["applicable", "uncertain", "not_applicable"]
# The only grounds on which the matcher may exclude an obligation from a part (spec silence is not one).
ExclusionReason = Literal["other_function", "other_class", "other_vehicle", "shown_absent", "presence_only",
                          "alternative_method"]
EvidenceStatus = Literal["met", "not_met", "evidence_needed"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


# --- Regulation side (product-agnostic) -------------------------------------------------------


class Quantity(_Model):
    value: str
    unit: str | None
    comparator: str | None


class Source(_Model):
    regulation: str
    version: str
    page: int
    paragraph: str | None


class SourceRef(_Model):
    document_id: str
    quote: str


class RegulationVersion(_Model):
    regulation: str
    title: str
    role: Literal["base", "latest"]
    version_label: str
    status: str
    file_name: str
    sha256: str


class TocEntry(_Model):
    provision_id: str
    paragraph: str
    heading: str
    page: int
    kind: ProvisionKind
    depth: int


class SearchHit(_Model):
    provision_id: str
    regulation: str
    version_label: str
    paragraph: str
    page: int
    snippet: str
    rank: float


class Provision(_Model):
    provision_id: str
    regulation: str
    version_label: str
    role: Literal["base", "latest"]
    paragraph: str
    heading_path: list[str]
    page_start: int
    page_end: int
    text: str
    kind: ProvisionKind
    refs: list[str]


class DeviceSections(_Model):
    device: str
    section_ids: list[str]


class RegulationCard(_Model):
    regulation: str
    version_label: str
    title: str
    regulation_type: Literal["device", "installation", "vehicle_system", "cross_cutting", "other"]
    devices_in_scope: list[str]
    vehicle_categories: list[str]
    functions_covered: list[str]
    triggers: list[str]
    consolidates: list[str]
    device_sections: list[DeviceSections]
    evidence: list[str]


ObligationKind = Literal["design", "performance", "marking", "test", "documentation", "conformity"]
# What an obligation is, independent of any product: an outcome the product must achieve, a condition
# that defines or measures an outcome, a design rule, a permission; or text that is no product
# requirement at all (how a laboratory runs a test, the approval procedure).
ObligationRole = Literal["outcome", "outcome_condition", "design_rule", "permission", "procedure", "administrative"]


class ExtractedObligation(_Model):
    subject: str
    condition: str | None
    constraint: str
    quantities: list[Quantity]
    text: str = Field(max_length=TEXT_LIMIT)
    quote: str
    kind: ObligationKind
    role: ObligationRole


class Obligation(ExtractedObligation):
    obligation_id: str
    provision_id: str
    extractor_version: str
    verified: bool
    role: ObligationRole = "outcome_condition"  # obligations cached before roles existed count as kept


class ProvisionObligations(_Model):
    provision_id: str
    obligations: list[ExtractedObligation]
    no_obligation_reason: str | None


class ExtractionOutput(_Model):
    items: list[ProvisionObligations]


# --- Product side (regulation-agnostic) -------------------------------------------------------


class Fact(_Model):
    fact_id: str
    key: str
    value: str
    unit: str | None
    source: Literal["spec", "drawing"]
    quote: str


class Part(_Model):
    part_id: str
    name: str
    functions: list[str]
    properties: list[str]
    materials: list[str]
    facts: list[Fact]


class ProductProfile(_Model):
    product_type: str
    vehicle_categories: list[str]
    parts: list[Part]
    relations: list[str]
    unknowns: list[str]


class CaseInput(_Model):
    case_id: str
    spec_text: str | None
    image_paths: list[Path]


# --- Narrowing and matching -------------------------------------------------------------------


class PartSections(_Model):
    part_id: str
    section_ids: list[str]


class RegulationDecision(_Model):
    regulation: str
    version_label: str
    state: DecisionState
    path: Literal["device", "installation", "cross_cutting", "none"]
    part_ids: list[str]
    sections: list[PartSections]
    reason: str
    evidence: list[str]
    consolidation_override: str | None


class ScopePlan(_Model):
    decisions: list[RegulationDecision]
    parts_without_regulation: list[str]


class MatchDecision(_Model):
    part_id: str
    obligation_id: str
    state: DecisionState
    reason: str
    fact_refs: list[str]
    evidence_status: EvidenceStatus
    test_case: str


class MatchBatch(_Model):
    decisions: list[MatchDecision]


class GroupDecision(_Model):
    """The matcher's decision on one obligation for a group of parts that share a section: the
    parts it binds (state applies to them); the group's other parts are not bound by it."""
    obligation_id: str
    state: DecisionState
    part_ids: list[str]
    exclusion: ExclusionReason | None
    reason: str
    fact_refs: list[str]
    evidence_status: EvidenceStatus
    test_case: str


class GroupMatchBatch(_Model):
    decisions: list[GroupDecision]


class Requirement(_Model):
    id: str
    text: str = Field(max_length=TEXT_LIMIT)
    source: Source
    part_ids: list[str]
    obligation_ids: list[str]
    state: Literal["applicable", "uncertain"]
    reason: str
    evidence_status: EvidenceStatus
    test_case: str | None


# --- Verification -----------------------------------------------------------------------------


class Issue(_Model):
    type: str
    target_id: str
    reason: str
    evidence: list[str]
    proposed: str | None


class Review(_Model):
    verdict: Literal["pass", "retry"]
    issues: list[Issue]


class Claim(_Model):
    claim_id: str
    text: str
    cited_text: str


# --- Markets ----------------------------------------------------------------------------------


class MarketRule(_Model):
    regulation: str
    status: Literal["mandatory", "accepted", "not_applied"]
    version_role: Literal["base", "latest"]
    source_ref: SourceRef | None


class MarketProfile(_Model):
    market_id: str
    name: str
    illustrative: bool
    rules: list[MarketRule]
    outside_corpus: list[SourceRef]


class MarketVerdict(_Model):
    market_id: str
    verdict: Literal["ready", "evidence_needed", "blocked", "not_covered"]
    blocking: list[str]
    missing_evidence: list[str]
    extras: list[str]


class Action(_Model):
    title: str
    kind: Literal["design_change", "test_evidence", "documentation"]
    requirement_ids: list[str]
    markets_unlocked: list[str]
    rationale: str


class ShipPlan(_Model):
    envelope_summary: str
    actions: list[Action]
    synergies: list[str]
    caveats: list[str]


# --- Sub-goal ---------------------------------------------------------------------------------


class SubgoalSource(_Model):
    page: int
    paragraph: str | None


class SubgoalChange(_Model):
    requirement_id: str | None
    change: Literal["modified", "removed", "added"]
    new_text: str | None
    reason: str
    source: SubgoalSource


class ChangeOutput(_Model):
    changes: list[SubgoalChange]


OUTPUT_SCHEMAS: tuple[type[BaseModel], ...] = (
    RegulationCard,
    ExtractionOutput,
    ProductProfile,
    ScopePlan,
    MatchBatch,
    GroupMatchBatch,
    Review,
    MarketProfile,
    ShipPlan,
    ChangeOutput,
)
