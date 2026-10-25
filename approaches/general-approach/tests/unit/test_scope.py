import random

from app.agents.prompting import extract_payload
from app.agents.recall_auditor import build_audit_prompt
from app.agents.scope_narrower import build_scope_prompt, create_scope_narrower, render_cards
from app.config.settings import load_settings
from app.gates.scope_gate import ScopeContext, scope_gate
from app.matching.safety_net import safety_net, safety_queries
from app.models import (DeviceSections, Fact, Part, PartSections, ProductProfile, RegulationCard, RegulationDecision,
                        RegulationVersion, ScopePlan)


def version(reg, label="1.0.0"):
    return RegulationVersion(regulation=reg, title=reg, role="base", version_label=label, status="", file_name="",
                             sha256="")


def card(reg, consolidates=(), label="1.0.0"):
    return RegulationCard(regulation=reg, version_label=label, title=f"{reg} title", regulation_type="device",
                          devices_in_scope=["rear lamp"], vehicle_categories=[], functions_covered=[], triggers=[],
                          consolidates=list(consolidates), device_sections=[], evidence=[])


PROFILE = ProductProfile(product_type="rear lamp", vehicle_categories=["M1"], unknowns=[], relations=[], parts=[
    Part(part_id="p1", name="stop lamp", functions=["braking indication"], properties=["emits red light"],
         materials=["PMMA"], facts=[Fact(fact_id="f1", key="k", value="v", unit=None, source="spec", quote="q")]),
    Part(part_id="p2", name="trade name marking", functions=[], properties=[], materials=[], facts=[]),
])


def decision(reg, state="applicable", parts=("p1",), sections=("UN R999@1.0.0#5",), label="1.0.0", override=None):
    return RegulationDecision(regulation=reg, version_label=label, state=state, path="device", part_ids=list(parts),
                              sections=[PartSections(part_id=p, section_ids=list(sections)) for p in parts]
                              if state != "not_applicable" else [], reason="r", evidence=[],
                              consolidation_override=override)


def ctx(store, cards=None):
    versions = [version("UN R999"), version("UN R998", "0.1.0")]
    return ScopeContext(profile=PROFILE, versions=versions, cards=cards or [card("UN R999"), card("UN R998", label="0.1.0")],
                        store=store)


def plan(*decisions, without=("p2",)):
    return ScopePlan(decisions=list(decisions), parts_without_regulation=list(without))


def types(issues):
    return sorted(i.type for i in issues)


def test_valid_plan_passes(mini_store):
    good = plan(decision("UN R999"), decision("UN R998", "not_applicable", parts=(), label="0.1.0"))
    assert scope_gate(ctx(mini_store), good) == []


def test_every_regulation_decided_once(mini_store):
    assert types(scope_gate(ctx(mini_store), plan(decision("UN R999")))) == ["missing_decision"]
    dup = plan(decision("UN R999"), decision("UN R999"), decision("UN R998", "not_applicable", (), label="0.1.0"))
    assert types(scope_gate(ctx(mini_store), dup)) == ["duplicate_decision"]


def test_version_must_be_base(mini_store):
    p = plan(decision("UN R999", label="2.0.0"), decision("UN R998", "not_applicable", (), label="0.1.0"))
    assert "wrong_version" in types(scope_gate(ctx(mini_store), p))


def test_ids_must_exist(mini_store):
    p = plan(decision("UN R999", parts=("p9",), sections=("UN R998@0.1.0#5",)),
             decision("UN R998", "not_applicable", (), label="0.1.0"), without=("p1", "p2"))
    assert {"unknown_part", "unknown_section"} <= set(types(scope_gate(ctx(mini_store), p)))


def test_consolidated_regulation_needs_override(mini_store):
    cards = [card("UN R999", consolidates=["UN R998"]), card("UN R998", label="0.1.0")]
    kept_both = plan(decision("UN R999"), decision("UN R998", sections=("UN R999@1.0.0#5",), label="0.1.0"))
    issues = scope_gate(ctx(mini_store, cards), kept_both)
    assert "consolidated" in types(issues)
    ok = plan(decision("UN R999"), decision("UN R998", sections=("UN R999@1.0.0#5",), label="0.1.0", override="needed"))
    assert "consolidated" not in types(scope_gate(ctx(mini_store, cards), ok))


def test_every_part_covered(mini_store):
    p = plan(decision("UN R999"), decision("UN R998", "not_applicable", (), label="0.1.0"), without=())
    assert types(scope_gate(ctx(mini_store), p)) == ["uncovered_part"]


def test_kept_decisions_need_sections(mini_store):
    p = plan(decision("UN R999", sections=()), decision("UN R998", "not_applicable", (), label="0.1.0"))
    assert types(scope_gate(ctx(mini_store), p)) == ["missing_sections"]


def test_render_cards_is_stable():
    cards = [card(f"UN R{n}") for n in (3, 148, 10, 48)]
    shuffled = cards[:]
    random.Random(1).shuffle(shuffled)
    assert render_cards(cards) == render_cards(shuffled) and render_cards(cards).count("\n") == 3


def test_safety_net_marks_excluded_top_hit(mini_store):
    excluded = plan(decision("UN R999", "not_applicable", ()), decision("UN R998", "not_applicable", (), label="0.1.0"),
                    without=("p1", "p2"))
    hits = safety_net(mini_store, PROFILE, excluded, 5)
    assert any(h.regulation == "UN R999" and h.excluded and h.best_rank == 1 for h in hits)
    assert len(safety_queries(PROFILE)) == len(set(safety_queries(PROFILE)))


def test_audit_prompt_lists_only_excluded_cards(mini_store):
    p = plan(decision("UN R999"), decision("UN R998", "not_applicable", (), label="0.1.0"))
    prompt = build_audit_prompt(ctx(mini_store), p, [])
    excluded_section = prompt.split("# Cards of excluded regulations")[1].split("\n# ")[0]
    assert "UN R998 title" in excluded_section and "UN R999 title" not in excluded_section


def test_narrower_spec_has_cards_and_tools():
    spec = create_scope_narrower(load_settings({}, fake_llm=True), [card("UN R999")])
    assert "UN R999 title" in spec.instruction and spec.tool_call_limit == 15 and len(spec.tools) == 3
    assert spec.effort == "high"


def test_scope_prompt_payload():
    payload = extract_payload(build_scope_prompt(PROFILE, []))
    assert payload["part_ids"] == ["p1", "p2"] and payload["feedback"] == []
