import json
from pathlib import Path

import pytest

from app.agents.prompting import extract_payload
from app.agents.synergy_advisor import build_synergy_prompt
from app.gates.advice_gate import SynergyInput, advice_claims, advice_gate
from app.markets.math import core_and_extras, fix_ranking, market_sets, verdicts
from app.models import Action, MarketProfile, MarketRule, Requirement, ShipPlan, Source
from tests.conftest import CHALLENGE, INDEX


def req(rid, reg, status="evidence_needed", text="The lamp shall emit 4 cd at least."):
    return Requirement(id=rid, text=text, source=Source(regulation=reg, version="1", page=1, paragraph="1"),
                       part_ids=["p1"], obligation_ids=[f"{rid}/o"], state="applicable", reason="r",
                       evidence_status=status, test_case=None)


def market(mid, rules):
    return MarketProfile(market_id=mid, name=mid, illustrative=True, outside_corpus=[],
                         rules=[MarketRule(regulation=r, status=s, version_role="base", source_ref=None) for r, s in rules])


@pytest.fixture
def inp(mini_store):
    reqs = [req("R-1", "UN R148"), req("R-2", "UN R150")]
    profiles = [market("x", [("UN R148", "mandatory"), ("UN R150", "mandatory")]), market("y", [("UN R148", "mandatory")])]
    sets = market_sets(reqs, profiles, mini_store)
    vs = verdicts(sets, profiles, reqs)
    return SynergyInput(sets=sets, core_extras=core_and_extras(sets), verdicts=vs, fix_ranking=fix_ranking(vs),
                        top_requirements=reqs, profile_summary={"product_type": "lamp"}, profiles=profiles)


def plan(unlocked, rationale="Measure the intensity once for both."):
    return ShipPlan(envelope_summary="s", synergies=[], caveats=[], actions=[
        Action(title="Photometry test", kind="test_evidence", requirement_ids=["R-1"], markets_unlocked=unlocked,
               rationale=rationale)])


def test_gate_accepts_code_computed_unlocks(inp):
    assert advice_gate(inp, plan(["y"])) == []


def test_gate_catches_wrong_unlocks_and_invented_numbers(inp):
    assert [i.type for i in advice_gate(inp, plan(["x", "y"]))] == ["markets_unlocked"]
    assert [i.type for i in advice_gate(inp, plan(["y"], "Saves 30 percent."))] == ["invented_number"]
    assert [i.type for i in advice_gate(inp, plan(["y"], "Reach 4 cd."))] == []
    bad_id = ShipPlan(envelope_summary="s", synergies=[], caveats=[], actions=[
        Action(title="t", kind="design_change", requirement_ids=["R-9"], markets_unlocked=[], rationale="r")])
    assert [i.type for i in advice_gate(inp, bad_id)] == ["unknown_id"]


def test_claims_and_prompt(inp):
    claims = advice_claims(inp, plan(["y"]))
    assert len(claims) == 1 and "4 cd" in claims[0].cited_text
    payload = extract_payload(build_synergy_prompt(inp, []))
    assert payload["top_requirement_ids"] == ["R-1", "R-2"] and {v["market_id"] for v in payload["verdicts"]} == {"x", "y"}


@pytest.mark.integration
@pytest.mark.skipif(not INDEX.exists(), reason="challenge data missing")
async def test_run_with_markets_writes_ship_plan(tmp_settings, fake_responders):
    from app.pipeline.main import run_case

    res = await run_case(CHALLENGE / "cases" / "dev-rear-lamp", markets=["market_a", "market_b", "market_c"],
                         mode="benchmark", settings=tmp_settings, run_dir=None)
    run = Path(res.run_dir)
    ship = json.loads((run / "ship_plan.json").read_text())
    markets = json.loads((run / "markets.json").read_text())
    assert ship["actions"] and {v["market_id"]: v["verdict"] for v in markets["verdicts"]}["market_c"] == "not_covered"
    assert "Market C (illustrative)" in (run / "report.md").read_text()
