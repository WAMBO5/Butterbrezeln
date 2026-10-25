from app.matching.scope_vote import majority, merge_plans
from app.models import PartSections, RegulationDecision, ScopePlan


def d(reg, state, sections=None, path="device"):
    sections = sections or {}
    kept = state != "not_applicable"
    return RegulationDecision(regulation=reg, version_label="1.0.0", state=state, path=path if kept else "none",
                              part_ids=list(sections) if kept else [],
                              sections=[PartSections(part_id=p, section_ids=ids) for p, ids in sections.items()],
                              reason=f"{reg} {state}", evidence=[], consolidation_override=None)


def test_majority():
    assert [majority(n) for n in (1, 2, 3, 5)] == [1, 2, 2, 3]


def test_two_of_three_keep_a_regulation_and_sections_are_the_union():
    plans = [
        ScopePlan(decisions=[d("A", "applicable", {"p1": ["A#5"]}), d("B", "uncertain", {"p1": ["B#3"]}),
                             d("C", "applicable", {"p2": ["C#1"]})], parts_without_regulation=[]),
        ScopePlan(decisions=[d("A", "applicable", {"p1": ["A#5", "A#6"], "p2": ["A#7"]}), d("B", "applicable", {"p1": ["B#3"]}),
                             d("C", "not_applicable")], parts_without_regulation=[]),
        ScopePlan(decisions=[d("A", "uncertain", {"p1": ["A#6"]}), d("B", "not_applicable"), d("C", "not_applicable")],
                  parts_without_regulation=["p3"]),
    ]
    merged, votes = merge_plans(plans)
    by_reg = {x.regulation: x for x in merged.decisions}
    assert by_reg["A"].state == "applicable" and by_reg["A"].part_ids == ["p1", "p2"]
    assert {s.part_id: s.section_ids for s in by_reg["A"].sections} == {"p1": ["A#5", "A#6"], "p2": ["A#7"]}
    assert by_reg["B"].state == "uncertain"  # kept by 2, applicable by only 1
    assert by_reg["C"].state == "not_applicable" and by_reg["C"].sections == []
    assert by_reg["C"].reason.startswith("kept by 1 of 3 scope samples only")
    assert votes["A"] == "3/3 kept, 2/3 applicable"
    assert merged.parts_without_regulation == ["p3"]


def test_a_single_plan_is_returned_unchanged():
    plan = ScopePlan(decisions=[d("A", "uncertain", {"p1": ["A#5"]})], parts_without_regulation=[])
    assert merge_plans([plan]) == (plan, {})
