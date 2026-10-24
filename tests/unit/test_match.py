from app.agents.prompting import extract_payload
from app.agents.requirement_matcher import build_match_prompt
from app.gates.match_gate import match_gate
from app.matching.collect import collect_candidates
from app.matching.match import MatchInput, make_match_batches, resolve
from app.models import (Fact, Issue, MatchBatch, MatchDecision, Obligation, Part, PartSections, ProductProfile,
                        RegulationCard, RegulationDecision, Review, ScopePlan)
from app.pipeline.loop import Attempt, LoopResult


def part(pid, value):
    return Part(part_id=pid, name=f"{pid} name", functions=["f"], properties=[], materials=[],
                facts=[Fact(fact_id=f"{pid}-f1", key="colour", value=value, unit=None, source="spec", quote=value)])


PROFILE = ProductProfile(product_type="rear lamp", vehicle_categories=["M1"], parts=[part("p1", "red-ruby"),
                         part("p2", "amber-topaz")], relations=[], unknowns=[])
CARD = RegulationCard(regulation="UN R999", version_label="1.0.0", title="Rear lamps", regulation_type="device",
                      devices_in_scope=[], vehicle_categories=[], functions_covered=[], triggers=[], consolidates=[],
                      device_sections=[], evidence=[])


def ob(n, pid="UN R999@1.0.0#5.1"):
    return Obligation(obligation_id=f"{pid}/{n}", provision_id=pid, subject="lamp", condition=None, constraint="c",
                      quantities=[], text=f"The lamp shall do {n}.", quote="q", kind="design", extractor_version="x1",
                      verified=False)


def plan(sections=("UN R999@1.0.0#5",)):
    return ScopePlan(decisions=[RegulationDecision(
        regulation="UN R999", version_label="1.0.0", state="applicable", path="device", part_ids=["p1"],
        sections=[PartSections(part_id="p1", section_ids=list(sections))], reason="r", evidence=[],
        consolidation_override=None)], parts_without_regulation=["p2"])


def batch(obligations=None):
    return MatchInput(part=PROFILE.parts[0], product_summary={"product_type": "rear lamp", "vehicle_categories": ["M1"],
                      "other_parts": ["p2 name"]}, card=CARD, heading_path=["5 Specifications"],
                      obligations=obligations or [ob(1), ob(2)], definitions=[])


def decision(oid, state="applicable", facts=(), status="evidence_needed", part_id="p1"):
    return MatchDecision(part_id=part_id, obligation_id=oid, state=state, reason="matcher says so",
                         fact_refs=list(facts), evidence_status=status, test_case="t")


def test_collect_adds_referenced_provision_once(mini_store):
    cands = collect_candidates(mini_store, plan(sections=("UN R999@1.0.0#5", "UN R999@1.0.0#5.1")))
    ids = [p.provision_id for c in cands for p in c.provisions]
    assert ids.count("UN R999@1.0.0#5.1") == 1
    assert "UN R999@1.0.0#Annex 3 Part 1 1.2" in ids and ids.count("UN R999@1.0.0#Annex 3 Part 1 1.2") == 1
    assert all(c.part_id == "p1" for c in cands)


def test_batches_respect_limit(mini_store):
    cands = collect_candidates(mini_store, plan())
    obligations = {c.provisions[0].provision_id: [ob(n, c.provisions[0].provision_id) for n in range(1, 91)]
                   for c in cands}
    batches = make_match_batches(cands, obligations, PROFILE, [CARD], mini_store, 40)
    assert batches and all(len(b.obligations) <= 40 for b in batches)
    assert sum(len(b.obligations) for b in batches) == sum(len(v) for v in obligations.values())


def test_prompt_has_only_this_parts_facts():
    prompt = build_match_prompt(batch(), [])
    assert "red-ruby" in prompt and "amber-topaz" not in prompt
    assert extract_payload(prompt)["obligation_ids"] == ["UN R999@1.0.0#5.1/1", "UN R999@1.0.0#5.1/2"]


def test_gate_cases():
    ok = MatchBatch(decisions=[decision(ob(1).obligation_id), decision(ob(2).obligation_id)])
    assert match_gate(batch(), ok) == []
    bad = MatchBatch(decisions=[decision(ob(1).obligation_id), decision(ob(1).obligation_id),
                                decision("UN R999@1.0.0#9/1"), decision(ob(2).obligation_id, status="not_met"),
                                decision(ob(2).obligation_id, facts=["p2-f1"])])
    types = {i.type for i in match_gate(batch(), bad)}
    assert {"duplicate_decision", "unknown_id", "not_met_without_fact", "unknown_fact"} <= types
    assert {i.type for i in match_gate(batch(), MatchBatch(decisions=[decision(ob(1).obligation_id)]))} == {"missing_decision"}


def test_disagreement_becomes_uncertain_with_both_reasons():
    out = MatchBatch(decisions=[decision(ob(1).obligation_id, "not_applicable"), decision(ob(2).obligation_id)])
    issue = Issue(type="silent_spec", target_id=ob(1).obligation_id, reason="spec is only silent", evidence=[],
                  proposed="uncertain")
    result = LoopResult(output=out, resolved=False, attempts=[Attempt(1)], open_issues=[issue])
    decided = {d.obligation_id: d for d in resolve(batch(), result)}
    assert decided[ob(1).obligation_id].state == "uncertain"
    assert decided[ob(1).obligation_id].reason == "matcher says so | reviewer: spec is only silent"
    assert decided[ob(2).obligation_id].state == "applicable"


def test_missing_output_makes_every_obligation_uncertain():
    result = LoopResult(output=None, resolved=False, attempts=[Attempt(1)], open_issues=[])
    decided = resolve(batch(), result)
    assert [d.state for d in decided] == ["uncertain", "uncertain"] and decided[0].reason == "no decision"
