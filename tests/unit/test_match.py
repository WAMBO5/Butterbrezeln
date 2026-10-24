from app.agents.prompting import extract_payload
from app.agents.requirement_matcher import build_match_prompt
from app.gates.match_gate import match_gate
from app.matching.collect import collect_candidates
from app.matching.match import MatchInput, make_match_batches, resolve
from app.models import (Fact, GroupDecision, GroupMatchBatch, Issue, Obligation, Part, PartSections, ProductProfile,
                        RegulationCard, RegulationDecision, ScopePlan)
from app.pipeline.loop import Attempt, LoopResult


def part(pid, value):
    return Part(part_id=pid, name=f"{pid} name", functions=["f"], properties=[], materials=[],
                facts=[Fact(fact_id=f"{pid}-f1", key="colour", value=value, unit=None, source="spec", quote=value)])


PROFILE = ProductProfile(product_type="rear lamp", vehicle_categories=["M1"], relations=[], unknowns=[],
                         parts=[part("p1", "red-ruby"), part("p2", "amber-topaz"), part("p3", "green-jade")])
CARD = RegulationCard(regulation="UN R999", version_label="1.0.0", title="Rear lamps", regulation_type="device",
                      devices_in_scope=[], vehicle_categories=[], functions_covered=[], triggers=[], consolidates=[],
                      device_sections=[], evidence=[])


def ob(n, pid="UN R999@1.0.0#5.1"):
    return Obligation(obligation_id=f"{pid}/{n}", provision_id=pid, subject="lamp", condition=None, constraint="c",
                      quantities=[], text=f"The lamp shall do {n}.", quote="q", kind="design", extractor_version="x1",
                      verified=False)


def plan(sections=("UN R999@1.0.0#5",), parts=("p1", "p2")):
    return ScopePlan(decisions=[RegulationDecision(
        regulation="UN R999", version_label="1.0.0", state="applicable", path="device", part_ids=list(parts),
        sections=[PartSections(part_id=p, section_ids=list(sections)) for p in parts], reason="r", evidence=[],
        consolidation_override=None)], parts_without_regulation=["p3"])


def batch(obligations=None):
    return MatchInput(parts=PROFILE.parts[:2], product_summary={"product_type": "rear lamp", "vehicle_categories": ["M1"],
                      "other_parts": ["p3 name"]}, card=CARD, heading_path=["5 Specifications"],
                      obligations=obligations or [ob(1), ob(2)], definitions=[])


def decision(oid, state="applicable", parts=("p1", "p2"), facts=(), status="evidence_needed"):
    return GroupDecision(obligation_id=oid, state=state, part_ids=list(parts), reason="matcher says so",
                         fact_refs=list(facts), evidence_status=status, test_case="t")


def test_collect_adds_referenced_provision_once(mini_store):
    cands = collect_candidates(mini_store, plan(sections=("UN R999@1.0.0#5", "UN R999@1.0.0#5.1"), parts=("p1",)))
    ids = [p.provision_id for c in cands for p in c.provisions]
    assert ids.count("UN R999@1.0.0#5.1") == 1
    assert "UN R999@1.0.0#Annex 3 Part 1 1.2" not in ids  # a reference to a whole annex does not pull it in
    assert all(c.part_id == "p1" for c in cands)
    with_annex = collect_candidates(mini_store, plan(sections=("UN R999@1.0.0#5", "UN R999@1.0.0#Annex 3"), parts=("p1",)))
    ids = [p.provision_id for c in with_annex for p in c.provisions]
    assert ids.count("UN R999@1.0.0#Annex 3 Part 1 1.2") == 1


def test_parts_sharing_a_section_are_matched_together(mini_store):
    cands = collect_candidates(mini_store, plan())
    obligations = {p.provision_id: [ob(n, p.provision_id) for n in range(1, 31)] for c in cands for p in c.provisions}
    batches = make_match_batches(cands, obligations, PROFILE, [CARD], mini_store, 40)
    assert batches and all([p.part_id for p in b.parts] == ["p1", "p2"] for b in batches)
    assert all(len(b.obligations) <= 40 for b in batches)
    assert sum(len(b.obligations) for b in batches) == sum(len(v) for v in obligations.values())


def test_prompt_has_only_the_groups_facts():
    prompt = build_match_prompt(batch(), [])
    assert "red-ruby" in prompt and "amber-topaz" in prompt and "green-jade" not in prompt
    payload = extract_payload(prompt)
    assert payload["obligation_ids"] == ["UN R999@1.0.0#5.1/1", "UN R999@1.0.0#5.1/2"]
    assert payload["part_ids"] == ["p1", "p2"]


def test_gate_cases():
    ok = GroupMatchBatch(decisions=[decision(ob(1).obligation_id), decision(ob(2).obligation_id, "not_applicable", ())])
    assert match_gate(batch(), ok) == []
    bad = GroupMatchBatch(decisions=[
        decision(ob(1).obligation_id), decision(ob(1).obligation_id), decision("UN R999@1.0.0#9/1"),
        decision(ob(2).obligation_id, status="not_met"), decision(ob(2).obligation_id, facts=["p3-f1"]),
        decision(ob(2).obligation_id, parts=("p3",)), decision(ob(2).obligation_id, parts=())])
    types = {i.type for i in match_gate(batch(), bad)}
    assert {"duplicate_decision", "unknown_id", "not_met_without_fact", "unknown_fact", "unknown_part",
            "no_parts"} <= types
    assert {i.type for i in match_gate(batch(), GroupMatchBatch(decisions=[decision(ob(1).obligation_id)]))} == {"missing_decision"}


def test_resolve_expands_to_one_decision_per_part():
    out = GroupMatchBatch(decisions=[decision(ob(1).obligation_id, parts=("p1",)),
                                     decision(ob(2).obligation_id, "not_applicable", ())])
    decided = resolve(batch(), LoopResult(output=out, resolved=True, attempts=[Attempt(1)], open_issues=[]))
    states = {(d.part_id, d.obligation_id): d.state for d in decided}
    assert states == {("p1", ob(1).obligation_id): "applicable", ("p2", ob(1).obligation_id): "not_applicable",
                      ("p1", ob(2).obligation_id): "not_applicable", ("p2", ob(2).obligation_id): "not_applicable"}


def test_disagreement_becomes_uncertain_with_both_reasons():
    out = GroupMatchBatch(decisions=[decision(ob(1).obligation_id, "not_applicable", ()), decision(ob(2).obligation_id)])
    issue = Issue(type="silent_spec", target_id=ob(1).obligation_id, reason="spec is only silent", evidence=[],
                  proposed="uncertain")
    result = LoopResult(output=out, resolved=False, attempts=[Attempt(1)], open_issues=[issue])
    decided = {(d.part_id, d.obligation_id): d for d in resolve(batch(), result)}
    first = decided[("p1", ob(1).obligation_id)]
    assert first.state == "uncertain" and first.reason == "matcher says so | reviewer: spec is only silent"
    assert decided[("p2", ob(1).obligation_id)].state == "uncertain"
    assert decided[("p1", ob(2).obligation_id)].state == "applicable"


def test_missing_output_makes_every_obligation_uncertain():
    result = LoopResult(output=None, resolved=False, attempts=[Attempt(1)], open_issues=[])
    decided = resolve(batch(), result)
    assert len(decided) == 4 and {d.state for d in decided} == {"uncertain"} and decided[0].reason == "no decision"


def test_reduced_cost_mode_reviews_only_disputed_batches():
    from app.config.settings import load_settings
    from app.pipeline.main import verify_extraction
    from app.pipeline.match import match_loop

    reduced = load_settings({"CERTIVITY_COST_MODE": "reduced"}, fake_llm=True)
    loop = match_loop(reduced)
    assert loop.producer.effort == "medium" and loop.producer.tools == ()
    all_applicable = GroupMatchBatch(decisions=[decision(ob(1).obligation_id), decision(ob(2).obligation_id)])
    disputed = GroupMatchBatch(decisions=[decision(ob(1).obligation_id, "not_applicable", ()),
                                          decision(ob(2).obligation_id)])
    assert not loop.needs_review(batch(), all_applicable) and loop.needs_review(batch(), disputed)
    full = match_loop(load_settings({}, fake_llm=True))
    assert full.needs_review is None and full.producer.effort == "medium" and len(full.producer.tools) == 1
    assert not verify_extraction(reduced) and verify_extraction(load_settings({}, fake_llm=True))
