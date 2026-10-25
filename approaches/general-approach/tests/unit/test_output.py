from app.agents.output_auditor import build_output_audit_prompt
from app.agents.prompting import extract_payload
from app.compliance.lineage import build_lineage, lineage_complete
from app.gates.output_gate import OutputContext, output_gate
from app.matching.assemble import assemble
from app.matching.repair import apply_output_review
from app.models import (Fact, Issue, MatchDecision, Obligation, Part, PartSections, ProductProfile,
                        RegulationDecision, RegulationVersion, Review, ScopePlan)

PROFILE = ProductProfile(product_type="lamp", vehicle_categories=[], relations=[], unknowns=[], parts=[
    Part(part_id="p1", name="stop lamp", functions=[], properties=[], materials=[],
         facts=[Fact(fact_id="f1", key="colour", value="red", unit=None, source="spec", quote="red")])])
PLAN = ScopePlan(parts_without_regulation=[], decisions=[RegulationDecision(
    regulation="UN R999", version_label="1.0.0", state="applicable", path="device", part_ids=["p1"],
    sections=[PartSections(part_id="p1", section_ids=["UN R999@1.0.0#3"])], reason="device", evidence=[],
    consolidation_override=None)])
VERSIONS = [RegulationVersion(regulation="UN R999", title="t", role="base", version_label="1.0.0", status="",
                              file_name="", sha256="")]


def ob(pid="UN R999@1.0.0#3.1", quote="shall bear the trade name"):
    return Obligation(obligation_id=f"{pid}/1", provision_id=pid, subject="s", condition=None, constraint="c",
                      quantities=[], text="The device shall bear the trade name.", quote=quote, kind="marking",
                      extractor_version="x1", verified=True)


def dec(oid, facts=("f1",)):
    return MatchDecision(part_id="p1", obligation_id=oid, state="applicable", reason="r", fact_refs=list(facts),
                         evidence_status="evidence_needed", test_case="t")


def setup(mini_store, obligations, decisions):
    obs = {o.obligation_id: o for o in obligations}
    reqs = assemble(decisions, obs, mini_store, True)
    return reqs, OutputContext(store=mini_store, versions=VERSIONS, profile=PROFILE, plan=PLAN, obligations=obs,
                               decisions=decisions)


def test_complete_lineage_passes(mini_store):
    o = ob()
    reqs, ctx = setup(mini_store, [o], [dec(o.obligation_id)])
    kept, lineages, issues = output_gate(reqs, ctx)
    assert issues == [] and len(kept) == 1 and lineage_complete(lineages[0])
    assert {l.step for l in lineages[0].links} >= {"part", "fact", "scope_decision", "provision", "obligation",
                                                   "match_decision"}


def test_missing_match_decision_is_dropped(mini_store):
    o = ob()
    reqs, ctx = setup(mini_store, [o], [dec(o.obligation_id)])
    ctx.decisions = []
    kept, _, issues = output_gate(reqs, ctx)
    assert kept == [] and [i.type for i in issues] == ["lineage"]
    assert not lineage_complete(build_lineage(reqs[0], PROFILE, PLAN, ctx.obligations, [], []))


def test_bad_page_is_dropped(mini_store):
    o, bad = ob(), ob("UN R999@1.0.0#5.3", quote="this quote is nowhere")
    reqs, ctx = setup(mini_store, [o, bad], [dec(o.obligation_id), dec(bad.obligation_id)])
    kept, lineages, issues = output_gate(reqs, ctx)
    assert [r.obligation_ids for r in kept] == [[o.obligation_id]] and [i.type for i in issues] == ["citation"]
    assert kept[0].id == "R-001" and lineages[0].requirement_id == "R-001"


def _req(mini_store, n, paragraph="3.1"):
    o = ob()
    [r] = assemble([dec(o.obligation_id)], {o.obligation_id: o}, mini_store, True)
    return r.model_copy(update={"id": f"R-00{n}", "source": r.source.model_copy(update={"paragraph": paragraph}),
                                "obligation_ids": [f"UN R999@1.0.0#3.{n}/1"]})


def issue(type_, target, evidence=()):
    return Issue(type=type_, target_id=target, reason="r", evidence=list(evidence), proposed=None)


def test_repair_plan(mini_store):
    reqs = [_req(mini_store, 1), _req(mini_store, 2), _req(mini_store, 3), _req(mini_store, 4, "3.1.")]
    review = Review(verdict="retry", issues=[issue("duplicate", "R-001", ["R-002"]), issue("merged", "R-003"),
                                             issue("format", "R-004")])
    plan = apply_output_review(reqs, review)
    assert plan.dropped == ["R-002"] and plan.reextract == ["UN R999@1.0.0#3.3"]
    assert [r.id for r in plan.kept] == ["R-001", "R-004"] and plan.kept[1].source.paragraph == "3.1"


def test_same_wording_in_two_regulations_is_not_a_duplicate(mini_store):
    reqs = [_req(mini_store, 1), _req(mini_store, 2)]
    other = reqs[1].model_copy(update={"source": reqs[1].source.model_copy(update={"regulation": "UN R998"})})
    plan = apply_output_review([reqs[0], other], Review(verdict="retry", issues=[issue("duplicate", "R-001", ["R-002"])]))
    assert plan.dropped == [] and [r.id for r in plan.kept] == ["R-001", "R-002"]


def test_audit_prompt_lists_every_id(mini_store):
    reqs = [_req(mini_store, 1), _req(mini_store, 2)]
    assert extract_payload(build_output_audit_prompt(reqs))["requirement_ids"] == ["R-001", "R-002"]
