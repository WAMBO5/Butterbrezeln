"""Deterministic responders for `--fake-llm` runs. They read the prompt payload, never golden data."""

from __future__ import annotations

import json

from app.agents.prompting import extract_payload
from app.testing.fake_llm import FakeRequest

PASS = json.dumps({"verdict": "pass", "issues": []})


def fake_pass_review(prompt: str, req: FakeRequest) -> str:
    return PASS


def fake_profiler(prompt: str, req: FakeRequest) -> str:
    p = extract_payload(prompt)
    evidence = p.get("scope_ids") or []
    return json.dumps({
        "regulation": p["regulation"], "version_label": p["version_label"], "title": p["title"] or p["regulation"],
        "regulation_type": "device", "devices_in_scope": [p["title"] or "device"], "vehicle_categories": [],
        "functions_covered": [], "triggers": [], "consolidates": [], "device_sections": [], "evidence": evidence[:1],
    })
