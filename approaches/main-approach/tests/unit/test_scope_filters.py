import json

import pytest

from app.corpus.parser import paragraph_key
from app.matching.collect import collect_candidates, is_administrative
from app.models import PartSections, Provision, RegulationDecision, ScopePlan
from tests.conftest import GOLD


def prov(paragraph, text, path=()):
    return Provision(provision_id=f"R@1#{paragraph}", regulation="R", version_label="1", role="base", paragraph=paragraph,
                     heading_path=list(path), page_start=1, page_end=1, text=text, kind="requirement", refs=[])


def test_administrative_headings():
    assert is_administrative(prov("8.1", "The lamp shall be checked.", ["8 Conformity of production"]))
    assert is_administrative(prov("3.2", "Approval"))
    assert is_administrative(prov("Annex 5 1", "Samples shall be taken.", ["Annex 5 Minimum requirements for sampling by an inspector"]))
    assert not is_administrative(prov("3.3.1", "The lamp shall bear the trade name.", ["3 Administrative provisions", "3.3 Markings"]))
    long_sentence = "In the communication form the applicant shall state the category of the lamp and the voltage."
    assert not is_administrative(prov("5.2", long_sentence, ["5 General specifications"]))


def test_strict_scope_skips_uncertain_regulations(mini_store):
    def decision(state):
        return RegulationDecision(regulation="UN R999", version_label="1.0.0", state=state, path="device",
                                  part_ids=["p1"], sections=[PartSections(part_id="p1", section_ids=["UN R999@1.0.0#5"])],
                                  reason="r", evidence=[], consolidation_override=None)
    assert collect_candidates(mini_store, ScopePlan(decisions=[decision("applicable")], parts_without_regulation=[]),
                              states=("applicable",))
    assert not collect_candidates(mini_store, ScopePlan(decisions=[decision("uncertain")], parts_without_regulation=[]),
                                  states=("applicable",))


@pytest.mark.skipif(not GOLD.exists(), reason="challenge data missing")
def test_filter_keeps_almost_every_golden_paragraph(real_store):
    gold = json.loads(GOLD.read_text())["requirements"]
    lost = set()
    for g in gold:
        s = g["source"]
        p = real_store.find(s["regulation"], s["version"], s["paragraph"])
        if p is not None and is_administrative(p):
            lost.add((s["regulation"], paragraph_key(s["paragraph"])))
    assert len(lost) <= 2, lost
