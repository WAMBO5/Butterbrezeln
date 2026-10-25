from pathlib import Path

import pytest

from app.markets.delta import align_provisions, align_versions
from app.markets.math import core_and_extras, fix_ranking, market_sets, markets_unlocked, verdicts
from app.markets.profiles import BUILTIN_DIR, load_market_profiles
from app.models import MarketProfile, MarketRule, Provision, Requirement, Source, SourceRef
from tests.conftest import INDEX

REGS = ["UN R10", "UN R48", "UN R148", "UN R150"]


def req(rid, reg, status="evidence_needed", page=1, paragraph="1"):
    return Requirement(id=rid, text=f"{rid} text", source=Source(regulation=reg, version="1", page=page, paragraph=paragraph),
                       part_ids=["p1"], obligation_ids=[f"{rid}/o"], state="applicable", reason="r",
                       evidence_status=status, test_case=None)


def market(mid, rules, outside=()):
    return MarketProfile(market_id=mid, name=mid, illustrative=True, outside_corpus=list(outside),
                         rules=[MarketRule(regulation=r, status=s, version_role="base", source_ref=None) for r, s in rules])


REQS = [req("R-1", "UN R148", "met"), req("R-2", "UN R148", "not_met"), req("R-3", "UN R150"), req("R-4", "UN R10", "met")]
X = market("x", [("UN R148", "mandatory"), ("UN R150", "mandatory"), ("UN R10", "mandatory")])
Y = market("y", [("UN R148", "mandatory"), ("UN R150", "not_applied"), ("UN R10", "mandatory")])
Z = market("z", [("UN R148", "mandatory"), ("UN R10", "accepted")],
           outside=[SourceRef(document_id="note", quote="national rule")])


def test_builtin_profiles():
    profiles = {p.market_id: p for p in load_market_profiles([BUILTIN_DIR], REGS)}
    assert set(profiles) == {"market_a", "market_b", "market_c"} and all(p.illustrative for p in profiles.values())
    assert profiles["market_a"].name == "Market A (illustrative)"
    roles = {r.regulation: r.version_role for r in profiles["market_b"].rules}
    assert roles["UN R10"] == roles["UN R48"] == "latest" and roles["UN R148"] == "base"
    c = {r.regulation: r.status for r in profiles["market_c"].rules}
    assert c["UN R150"] == "not_applied" and profiles["market_c"].outside_corpus[0].document_id == "sample-note"


def test_core_and_extras(mini_store):
    sets = market_sets(REQS, [X, Y], mini_store)
    ce = core_and_extras(sets)
    assert ce.core == ["R-1", "R-2", "R-4"] and ce.extras == {"x": ["R-3"], "y": []} and ce.envelope == ["R-1", "R-2", "R-3", "R-4"]


def test_verdict_order_and_not_covered(mini_store):
    sets = market_sets(REQS, [X, Y, Z], mini_store)
    v = {m.market_id: m for m in verdicts(sets, [X, Y, Z], REQS)}
    assert v["x"].verdict == "blocked" and v["x"].blocking == ["R-2"] and v["x"].missing_evidence == ["R-3"]
    assert v["z"].verdict == "not_covered"
    fixed = [r.model_copy(update={"evidence_status": "met"}) if r.id == "R-2" else r for r in REQS]
    v2 = {m.market_id: m for m in verdicts(market_sets(fixed, [X, Y], mini_store), [X, Y], fixed)}
    assert v2["x"].verdict == "evidence_needed" and v2["y"].verdict == "ready"


def test_fix_ranking_and_unlocks(mini_store):
    sets = market_sets(REQS, [X, Y], mini_store)
    v = verdicts(sets, [X, Y], REQS)
    ranking = fix_ranking(v)
    assert [(f.requirement_id, sorted(f.markets_held_back)) for f in ranking] == [("R-2", ["x", "y"]), ("R-3", ["x"])]
    assert markets_unlocked(["R-2"], v) == ["y"] and markets_unlocked(["R-2", "R-3"], v) == ["x", "y"]


def p(paragraph, text):
    return Provision(provision_id=f"R@1#{paragraph}", regulation="R", version_label="1", role="base", paragraph=paragraph,
                     heading_path=[], page_start=1, page_end=1, text=text, kind="requirement", refs=[])


def test_align_provisions():
    old = [p("1", "Same text."), p("2", "The lamp shall be red."), p("3", "Removed entirely, nothing similar."),
           p("4", "The lens shall be made of glass and shall be clear.")]
    new = [p("1", "Same  text."), p("2", "The lamp shall be amber."), p("5", "The lens shall be made of glass and shall be clear!"),
           p("6", "A totally new requirement about software updates.")]
    changes = {(c.paragraph, c.status) for c in align_provisions(old, new)}
    assert ("1", "unchanged") in changes and ("2", "modified") in changes and ("3", "removed") in changes
    assert ("6", "added") in changes and any(s == "modified" and par == "4" for par, s in changes)


@pytest.mark.skipif(not INDEX.exists(), reason="challenge data missing")
def test_align_r10_versions(real_store):
    changes = align_versions(real_store, "UN R10", "7.2.0", "7.3.0")
    statuses = [c.status for c in changes]
    assert statuses.count("modified") >= 1 and statuses.count("unchanged") > 100
