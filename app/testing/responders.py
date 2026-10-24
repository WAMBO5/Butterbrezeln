"""Deterministic responders for `--fake-llm` runs. They read the prompt payload, never golden data."""

from __future__ import annotations

import json
import re

from app.agents.prompting import extract_payload
from app.config.settings import Settings
from app.corpus.parser import normalize
from app.corpus.store import CorpusStore
from app.testing.fake_llm import FakeRequest, Responder

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


# --- full fake run ----------------------------------------------------------------------------

FAKE_APPLICABLE = ("UN R148", "UN R48", "UN R150", "UN R10")
_SPEC_RE = re.compile(r'<untrusted_input name="spec">\n(.*?)\n</untrusted_input>', re.S)
_SHALL_RE = re.compile(r"[^.;:]*\b(?:shall|must)\b[^.;]*[.;]?", re.I)


def _section_after(spec: str, heading: str) -> list[str]:
    lines = spec.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower() == f"## {heading}".lower():
            out = []
            for nxt in lines[i + 1:]:
                if nxt.startswith("## "):
                    break
                if nxt.strip():
                    out.append(nxt.strip())
            return out
    return []


def fake_analyst(prompt: str, req: FakeRequest) -> str:
    m = _SPEC_RE.search(prompt)
    spec = m.group(1) if m else ""
    product = (_section_after(spec, "Product Type") or ["product"])[0]
    category = (_section_after(spec, "Vehicle Category") or [""])[0]
    bullets = [b[2:].strip() for b in _section_after(spec, "Main Parts") if b.startswith("- ")]
    electronics = ["contains electronics"] if "LED" in spec or "PCB" in spec else []
    parts = []
    for n, name in enumerate(bullets or [product], start=1):
        source, quote = ("spec", name) if spec else ("drawing", "drawing label")
        parts.append({"part_id": f"p{n}", "name": name, "functions": [name], "properties": electronics,
                      "materials": [], "facts": [{"fact_id": f"f{n}", "key": "part", "value": name, "unit": None,
                                                  "source": source, "quote": quote}]})
    return json.dumps({"product_type": product, "vehicle_categories": [category.split(" ")[0]] if category else [],
                       "parts": parts, "relations": [], "unknowns": []})


def _top_requirement_sections(store: CorpusStore, regulation: str, version_label: str) -> list[str]:
    provisions = store.provisions(regulation, version_label)
    tops = [p for p in provisions if p.paragraph.isdigit()]
    out = []
    for top in tops:
        if any(p.kind == "requirement" and p.paragraph.startswith(top.paragraph + ".") for p in provisions):
            out.append(top.provision_id)
        if len(out) == 2:
            break
    return out


def make_fake_narrower(store: CorpusStore) -> Responder:
    def respond(prompt: str, req: FakeRequest) -> str:
        part_ids = extract_payload(prompt)["part_ids"]
        decisions = []
        for v in sorted((v for v in store.versions() if v.role == "base"), key=lambda v: v.regulation):
            sections = _top_requirement_sections(store, v.regulation, v.version_label) \
                if v.regulation in FAKE_APPLICABLE else []
            if sections:
                decisions.append({"regulation": v.regulation, "version_label": v.version_label, "state": "applicable",
                                  "path": "device", "part_ids": part_ids,
                                  "sections": [{"part_id": p, "section_ids": sections} for p in part_ids],
                                  "reason": "fake: listed as applicable", "evidence": [],
                                  "consolidation_override": None})
            else:
                decisions.append({"regulation": v.regulation, "version_label": v.version_label,
                                  "state": "not_applicable", "path": "none", "part_ids": [], "sections": [],
                                  "reason": "fake: not listed", "evidence": [], "consolidation_override": None})
        covered = bool([d for d in decisions if d["state"] == "applicable"])
        return json.dumps({"decisions": decisions, "parts_without_regulation": [] if covered else part_ids})
    return respond


def make_fake_extractor(store: CorpusStore) -> Responder:
    def respond(prompt: str, req: FakeRequest) -> str:
        items = []
        for pid in extract_payload(prompt)["provision_ids"]:
            p = store.get(pid)
            m = _SHALL_RE.search(p.text) if p else None
            if m and m.group(0).strip():
                quote = m.group(0).strip()
                items.append({"provision_id": pid, "no_obligation_reason": None, "obligations": [{
                    "subject": "the device", "condition": None, "constraint": "as stated", "quantities": [],
                    "text": normalize(quote)[:2000], "quote": quote, "kind": "design"}]})
            else:
                items.append({"provision_id": pid, "obligations": [], "no_obligation_reason": "fake: no shall clause"})
        return json.dumps({"items": items})
    return respond


def fake_matcher(prompt: str, req: FakeRequest) -> str:
    payload = extract_payload(prompt)
    return json.dumps({"decisions": [
        {"obligation_id": oid, "state": "applicable", "part_ids": payload["part_ids"], "reason": "fake: applies",
         "fact_refs": [], "evidence_status": "evidence_needed", "test_case": "Inspect and test per the paragraph."}
        for oid in payload["obligation_ids"]]})


def fake_synergy(prompt: str, req: FakeRequest) -> str:
    payload = extract_payload(prompt)
    open_markets = [v for v in payload["verdicts"] if v["verdict"] in ("blocked", "evidence_needed")]
    if not open_markets:
        return json.dumps({"envelope_summary": "fake: every market is ready.", "actions": [], "synergies": [],
                           "caveats": ["fake plan"]})
    ids = sorted(set(open_markets[0]["blocking"]) | set(open_markets[0]["missing_evidence"]))
    unlocked = sorted(v["market_id"] for v in open_markets
                      if set(v["blocking"]) | set(v["missing_evidence"]) <= set(ids))
    return json.dumps({"envelope_summary": "fake: prove the shared requirements once.", "synergies": [],
                       "caveats": ["Illustrative market data."],
                       "actions": [{"title": "Produce the evidence for the shared requirements", "kind": "test_evidence",
                                    "requirement_ids": ids, "markets_unlocked": unlocked,
                                    "rationale": "One test campaign covers every market that asks for them."}]})


_SOURCE_RE = re.compile(r'<untrusted_input name="source ([^" ]+)[^"]*">\n(.*?)\n</untrusted_input>', re.S)


def fake_onboarding(prompt: str, req: FakeRequest) -> str:
    payload = extract_payload(prompt)
    rules, outside, sample = [], [], False
    for doc_id, text in _SOURCE_RE.findall(prompt):
        sample = sample or text.lstrip().startswith("ILLUSTRATIVE SAMPLE")
        for sentence in (line.strip() for line in text.splitlines() if line.strip()):
            m = re.search(r"Regulation No\. (\d+)", sentence)
            if m:
                rules.append({"regulation": f"UN R{m.group(1)}", "status": "accepted" if "accepts" in sentence else "mandatory",
                              "version_role": "latest" if "latest" in sentence else "base",
                              "source_ref": {"document_id": doc_id, "quote": sentence.strip()}})
            elif "outside" in sentence:
                outside.append({"document_id": doc_id, "quote": sentence.strip()})
    return json.dumps({"market_id": "x", "name": payload["market_name"], "illustrative": sample, "rules": rules,
                       "outside_corpus": outside})


def build_fake_responders(settings: Settings, store: CorpusStore) -> dict[str, Responder]:
    """Scripted outputs for a whole offline run. They read the prompt payload only."""
    return {
        "regulation_profiler": fake_profiler,
        "grounding_verifier": fake_pass_review,
        "product_analyst": fake_analyst,
        "profile_verifier": fake_pass_review,
        "scope_narrower": make_fake_narrower(store),
        "recall_auditor": fake_pass_review,
        "obligation_extractor": make_fake_extractor(store),
        "extraction_verifier": fake_pass_review,
        "requirement_matcher": fake_matcher,
        "match_reviewer": fake_pass_review,
        "output_auditor": fake_pass_review,
        "synergy_advisor": fake_synergy,
        "market_onboarding": fake_onboarding,
    }
