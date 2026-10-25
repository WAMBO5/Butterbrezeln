import json
from pathlib import Path

import pytest

from app.corpus.pdf_text import extract_pdf_text
from app.gates.change_gate import change_gate
from app.models import ChangeOutput, SubgoalChange, SubgoalSource
from app.pipeline.subgoal import SubgoalInput, describe_change, load_subgoal, run_subgoal
from tests.conftest import CHALLENGE

SUBGOAL = CHALLENGE / "subgoal" / "dev"


def test_extract_pdf_text_writes_markers_and_headers(tmp_path):
    text = extract_pdf_text(tmp_path / "x.pdf", "UN R1, version 1.0.0 | page {page} of {pages}",
                            page_texts=lambda path: ["a", "b"])
    assert text.count("=== PDF page") == 2 and "UN R1, version 1.0.0 | page 2 of 2" in text
    from app.corpus.parser import iter_pages
    assert iter_pages(text) == [(1, "a"), (2, "b")]


def test_gate_rejects_unknown_requirement():
    inp = SubgoalInput(case_id="subgoal-x", old_text="", new_text="", requirements_old=[{"id": "R-001", "text": "t"}],
                       pairs=[])
    bad = ChangeOutput(changes=[SubgoalChange(requirement_id="R-999", change="modified", new_text="n", reason="r",
                                              source=SubgoalSource(page=1, paragraph="1"))])
    assert change_gate(inp, bad)
    ok = ChangeOutput(changes=[SubgoalChange(requirement_id="R-001", change="modified", new_text="n", reason="r",
                                             source=SubgoalSource(page=1, paragraph="1"))])
    assert change_gate(inp, ok) == []
    added_with_id = ChangeOutput(changes=[SubgoalChange(requirement_id="R-001", change="added", new_text="n",
                                                        reason="r", source=SubgoalSource(page=1, paragraph="1"))])
    assert "added_with_id" in {i.type for i in change_gate(inp, added_with_id)}


def test_describe_change_names_the_edit():
    assert describe_change("The lamp shall be red.", "The lamp shall be amber.") == "'red.' became 'amber.'"


def test_link_requirements_by_page_introduction_and_words():
    from app.corpus.parser import parse_regulation
    from app.pipeline.subgoal import link_requirements

    text = ("=== PDF page 1 ===\nIntroduction\n1. Driver assistance systems support the driver.\n"
            "2. The system shall aim to prevent misuse.\n"
            "=== PDF page 2 ===\n1. Scope\n1.1. This Regulation applies to vehicles.\n"
            "2. Modification of the vehicle type\n2.1. Every modification shall be notified.\n"
            "=== PDF page 3 ===\nAnnex 1\nThe manufacturer shall declare the capability of the system.\n")
    old = parse_regulation(text, "UN R1", "1.0.0", "base")
    reqs = [{"id": "R-001", "text": "The system shall aim to prevent misuse.", "source": {"page": 1, "paragraph": "2"}},
            {"id": "R-002", "text": "Every modification shall be notified.", "source": {"page": 2, "paragraph": "2.1"}},
            {"id": "R-003", "text": "The manufacturer shall declare the capability.", "source": {"page": 3, "paragraph": "tb:6784"}}]
    linked = {label: [r["id"] for r in rs] for label, rs in link_requirements(reqs, old).items()}
    assert linked == {"Introduction 2": ["R-001"], "2.1": ["R-002"], "Annex 1": ["R-003"]}


def test_split_provisions_stay_in_one_batch_in_paragraph_order():
    from app.pipeline.subgoal import _batches, _label_order

    labels = ["6.5.2", "5.10", "6.4", "Annex 2 1.1", "6.5", "5.9", "6.5.1"]
    pairs = sorted(({"new_paragraph": label, "old_paragraph": None} for label in labels),
                   key=lambda p: _label_order(p["new_paragraph"]))
    assert [p["new_paragraph"] for p in pairs] == ["5.9", "5.10", "6.4", "6.5", "6.5.1", "6.5.2", "Annex 2 1.1"]
    assert [[p["new_paragraph"] for p in b] for b in _batches(pairs, 4)] == [
        ["5.9", "5.10", "6.4", "6.5", "6.5.1", "6.5.2"], ["Annex 2 1.1"]]


def test_claims_cite_the_linked_pair_and_the_source_pair_with_their_labels():
    from app.pipeline.subgoal import change_claims

    split = {"paragraph": "6.5", "status": "modified", "old_paragraph": "6.5", "new_paragraph": "6.5", "old_page": 8,
             "new_page": 10, "edit": "...", "old_text": "The offset shall be at most 0.2 m.", "new_text": "Offset",
             "linked": [{"id": "R-084", "text": "The offset shall be at most 0.2 m."}]}
    part = {"paragraph": "6.5.2", "status": "added", "old_paragraph": None, "new_paragraph": "6.5.2", "old_page": None,
            "new_page": 10, "edit": None, "old_text": None, "new_text": "The offset shall be at most the vehicle width.",
            "linked": []}
    inp = SubgoalInput(case_id="subgoal-x", old_text="", new_text="", requirements_old=[], pairs=[split, part],
                       regulation="UN R175", versions=("0.1.0", "1.0.0"))
    out = ChangeOutput(changes=[SubgoalChange(requirement_id="R-084", change="modified", new_text="n",
                                              reason="Paragraph 6.5.2 (formerly 6.5) ...",
                                              source=SubgoalSource(page=10, paragraph="6.5.2"))])
    cited = change_claims(inp, out)[0].cited_text
    assert "UN R175, modified: paragraph 6.5 (page 8) of version 0.1.0 -> paragraph 6.5 (page 10) of version 1.0.0" in cited
    assert "-> paragraph 6.5.2 (page 10) of version 1.0.0" in cited and "the vehicle width" in cited


@pytest.mark.skipif(not SUBGOAL.exists(), reason="challenge data missing")
def test_load_subgoal_links_requirements(tmp_settings):
    inp = load_subgoal(SUBGOAL, tmp_settings)
    assert inp.case_id == "subgoal-dev" and len(inp.requirements_old) == 94
    assert inp.regulation == "UN R175" and inp.versions == ("0.1.0", "1.0.0")
    statuses = {p["status"] for p in inp.pairs}
    assert {"modified", "added"} <= statuses and any(p["linked"] for p in inp.pairs if p["status"] == "modified")


@pytest.mark.integration
@pytest.mark.skipif(not SUBGOAL.exists(), reason="challenge data missing")
async def test_fake_subgoal_validates(tmp_settings, fake_responders):
    from app.matching.challenge_tools import load_tool

    out = await run_subgoal(SUBGOAL, tmp_settings)
    data = json.loads(Path(out).read_text())
    assert data["case_id"] == "subgoal-dev" and data["changes"]
    validate = load_tool(tmp_settings.challenge_dir, "validate")
    old = validate.load_requirements_old(SUBGOAL / "requirements_old.json")
    assert validate.validate(data, requirements_old=old) == []
