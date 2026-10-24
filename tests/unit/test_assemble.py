import json

import pytest

from app.compliance.provenance import UNREVIEWED_LABEL, provenance
from app.config.settings import load_settings
from app.matching.assemble import assemble
from app.matching.citations import check_citation
from app.matching.submission import score_submission, to_submission, validate_submission
from app.models import MatchDecision, Obligation, RegulationVersion
from tests.conftest import GOLD, INDEX

SETTINGS = load_settings({})


def ob(pid, n=1, quote="shall bear the trade name", text="The device shall bear the trade name."):
    return Obligation(obligation_id=f"{pid}/{n}", provision_id=pid, subject="s", condition=None, constraint="c",
                      quantities=[], text=text, quote=quote, kind="marking", extractor_version="x1", verified=True)


def dec(oid, part="p1", state="applicable", status="evidence_needed", test="look"):
    return MatchDecision(part_id=part, obligation_id=oid, state=state, reason="r", fact_refs=[],
                         evidence_status=status, test_case=test)


def test_dedup_merges_parts_and_worst_evidence(mini_store):
    o = ob("UN R999@1.0.0#3.1")
    reqs = assemble([dec(o.obligation_id, "p1", status="met"), dec(o.obligation_id, "p2", "uncertain", "not_met")],
                    {o.obligation_id: o}, mini_store, include_uncertain=True)
    assert len(reqs) == 1 and reqs[0].part_ids == ["p1", "p2"] and reqs[0].state == "applicable"
    assert reqs[0].evidence_status == "not_met" and reqs[0].test_case == "look"
    assert reqs[0].source.page == 1 and reqs[0].source.paragraph == "3.1" and reqs[0].source.version == "1.0.0"


def test_uncertain_policy_and_numbering(mini_store):
    a, b = ob("UN R999@1.0.0#3.1"), ob("UN R999@1.0.0#5.3", quote="The field shall be measured", text="t")
    obs = {a.obligation_id: a, b.obligation_id: b}
    decisions = [dec(b.obligation_id), dec(a.obligation_id, state="uncertain")]
    assert [r.id for r in assemble(decisions, obs, mini_store, include_uncertain=True)] == ["R-001", "R-002"]
    kept = assemble(decisions, obs, mini_store, include_uncertain=False)
    assert [r.obligation_ids for r in kept] == [[b.obligation_id]] and kept[0].id == "R-001"
    assert assemble([dec(a.obligation_id, state="not_applicable")], obs, mini_store, True) == []


def _versions():
    return [RegulationVersion(regulation="UN R999", title="t", role="base", version_label="1.0.0", status="",
                              file_name="", sha256=""),
            RegulationVersion(regulation="UN R999", title="t", role="latest", version_label="2.0.0", status="",
                              file_name="", sha256="")]


def test_citation_check(mini_store):
    o = ob("UN R999@1.0.0#3.1")
    [req] = assemble([dec(o.obligation_id)], {o.obligation_id: o}, mini_store, True)
    assert check_citation(mini_store, req, o, _versions()) == []
    wrong_page = req.model_copy(update={"source": req.source.model_copy(update={"page": 3})})
    assert "quote_not_on_page" in {i.type for i in check_citation(mini_store, wrong_page, o, _versions())}
    latest = req.model_copy(update={"source": req.source.model_copy(update={"version": "2.0.0"})})
    assert "not_base_version" in {i.type for i in check_citation(mini_store, latest, o, _versions())}
    gone = req.model_copy(update={"source": req.source.model_copy(update={"page": 99, "paragraph": "9.9"})})
    assert {"page_missing", "paragraph_missing"} <= {i.type for i in check_citation(mini_store, gone, o, _versions())}


def test_quote_page_is_cited(mini_store):
    o = ob("UN R999@1.0.0#5.1", quote="12 V 21 W", text="The lamp shall use 12 V 21 W.")
    [req] = assemble([dec(o.obligation_id)], {o.obligation_id: o}, mini_store, True)
    assert req.source.page == 3  # provision starts on page 2; the quote is on page 3


@pytest.mark.skipif(not INDEX.exists(), reason="challenge data missing")
def test_submission_validates(real_store):
    a = ob("UN R148@1.6.0#3.3.1", quote="x")
    b = ob("UN R148@1.6.0#4.1", quote="x")
    reqs = assemble([dec(a.obligation_id), dec(b.obligation_id)], {a.obligation_id: a, b.obligation_id: b},
                    real_store, True)
    data = to_submission(reqs, "team-x", "dev-rear-lamp")
    assert validate_submission(data, SETTINGS) == [] and set(data["requirements"][0]) == {"id", "text", "source", "test_case"}


@pytest.mark.skipif(not GOLD.exists(), reason="challenge data missing")
def test_score_against_itself():
    expected = json.loads(GOLD.read_text())
    assert score_submission(expected, GOLD, SETTINGS)["regulation_level"]["recall"] == 1.0


def test_provenance_label():
    p = provenance("run-1", "benchmark", {"a": "m"}, None)
    assert p["label"] == UNREVIEWED_LABEL and p["review_status"] == "unreviewed" and p["ai_generated"] is True
    assert provenance("run-1", "assisted", {}, {"reviewer": "x"})["label"] is None
