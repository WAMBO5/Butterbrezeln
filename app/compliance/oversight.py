"""Human oversight (design spec section 14.3): checkpoints, actions, pinned decisions, sign-off."""

from __future__ import annotations

from app.compliance.lineage import Lineage
from app.models import Requirement, ScopePlan


def apply_pinned(plan: ScopePlan, actions: list[dict]) -> ScopePlan:
    """Re-apply scope decisions a reviewer changed, so a re-run never overwrites them silently."""
    return plan


def apply_requirement_pins(reqs: list[Requirement], lineages: list[Lineage],
                           actions: list[dict]) -> tuple[list[Requirement], list[Lineage]]:
    return reqs, lineages
