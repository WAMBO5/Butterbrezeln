"""Machine-readable provenance for every export (AI Act Art. 50)."""

from __future__ import annotations

UNREVIEWED_LABEL = "Unreviewed AI draft — not for compliance use"


def provenance(run_id: str, mode: str, models: dict[str, str], review: dict | None) -> dict:
    return {
        "generator": "certivity-requirements-engine",
        "ai_generated": True,
        "run_id": run_id,
        "mode": mode,
        "models": models,
        "review_status": "reviewed" if review else "unreviewed",
        "label": None if review else UNREVIEWED_LABEL,
    }
