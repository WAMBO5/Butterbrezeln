"""Pydantic schemas for every hand-off between nodes and for every structured LLM output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# --- product -----------------------------------------------------------------------------------------------

class Attribute(BaseModel):
    name: str
    value: str
    source: Literal["spec", "image"]


class Component(BaseModel):
    id: str = Field(description="short snake_case id, unique in the product; the root is 'assembly'")
    name: str
    parent_id: str = Field(description="id of the parent component, '' for the root assembly")
    attributes: list[Attribute]
    unknowns: list[str] = Field(description="facts an engineer would need that the spec and image do not state")
    conflicts: list[str] = Field(description="places where spec and image disagree; keep both versions")


class ProductProfile(BaseModel):
    product_name: str
    product_type: str
    vehicle_categories: list[str] = Field(description="only categories the spec states, e.g. ['M1']; [] if not stated")
    context_facts: list[str] = Field(description="stated facts about use and mounting, e.g. 'mounted at the rear of the vehicle'")
    components: list[Component]


class Functionality(BaseModel):
    id: str = Field(description="an id from the taxonomy list, or 'unmapped'")
    statement: str = Field(description="what it does, in the vocabulary of UN Regulations")
    component_ids: list[str]
    queries: list[str] = Field(description="3-5 search queries: label, regulatory paraphrase, one 'shall' sentence")


class FunctionalityList(BaseModel):
    functionalities: list[Functionality]


class QueryRewrite(BaseModel):
    functionality_id: str
    queries: list[str]


class QueryRewrites(BaseModel):
    rewrites: list[QueryRewrite]


# --- regulations and provisions ----------------------------------------------------------------------------

class RegulationDecision(BaseModel):
    regulation: str
    decision: Literal["applicable", "not_applicable", "uncertain"]
    reason: str


class RouteDecisions(BaseModel):
    decisions: list[RegulationDecision]


class TriageGrade(BaseModel):
    ref: str
    relevant: bool


class TriageGrades(BaseModel):
    grades: list[TriageGrade]


class JudgeDecision(BaseModel):
    ref: str
    label: Literal["keep", "reject", "uncertain"]
    reason: str = Field(description="one short sentence tied to product facts and the provision's scope")
    functionality_ids: list[str] = Field(description="functionality ids this provision constrains; [] for reject")


class JudgeDecisions(BaseModel):
    decisions: list[JudgeDecision]


class DraftRequirement(BaseModel):
    ref: str = Field(description="ref of the provision the obligation comes from")
    text: str = Field(description="one engineering obligation, self-contained, conditions and numbers kept")
    quote: str = Field(description="verbatim span of the cited provision (or its attached reference) that states it")


class DraftRequirements(BaseModel):
    requirements: list[DraftRequirement]
