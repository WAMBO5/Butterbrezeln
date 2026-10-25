"""Code gate for regulation cards, and the claims `grounding_verifier` checks."""

from __future__ import annotations

from app.corpus.cards import CardPayload
from app.models import Claim, Issue, RegulationCard

CITED_LIMIT = 4000


def _issue(type_: str, target: str, reason: str) -> Issue:
    return Issue(type=type_, target_id=target, reason=reason, evidence=[], proposed=None)


def card_gate(payload: CardPayload, card: RegulationCard) -> list[Issue]:
    v = payload.version
    issues: list[Issue] = []
    if card.regulation != v.regulation or card.version_label != v.version_label:
        issues.append(_issue("mismatch", "card", f"card must be for {v.regulation} version {v.version_label}"))
    if not card.title.strip():
        issues.append(_issue("missing_field", "title", "title is empty"))
    if card.regulation_type == "device" and not card.devices_in_scope:
        issues.append(_issue("missing_field", "devices_in_scope", "a device regulation needs devices_in_scope"))
    ids = list(card.evidence) + [sid for ds in card.device_sections for sid in ds.section_ids]
    for pid in dict.fromkeys(ids):
        p = payload.store.get(pid)
        if p is None or p.regulation != v.regulation or p.version_label != v.version_label:
            issues.append(_issue("unknown_id", pid, f"{pid} is not a provision id of {v.regulation} {v.version_label}"))
    return issues


def card_claims(payload: CardPayload, card: RegulationCard) -> list[Claim]:
    parts = []
    for pid in card.evidence:
        p = payload.store.get(pid)
        if p is not None:
            parts.append(f"[{pid}] {p.text}")
    cited = "\n\n".join(parts)[:CITED_LIMIT]
    claims = [Claim(claim_id=f"device:{n}", text=f"{card.regulation} applies to the device type: {d}", cited_text=cited)
              for n, d in enumerate(card.devices_in_scope)]
    claims += [Claim(claim_id=f"consolidates:{n}", text=f"{card.regulation} combines or replaces {r}", cited_text=cited)
               for n, r in enumerate(card.consolidates)]
    claims += [Claim(claim_id=f"trigger:{n}", text=f"{card.regulation} applies to products with the property: {t}",
                     cited_text=cited) for n, t in enumerate(card.triggers)]
    return claims
