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


@pytest.mark.skipif(not SUBGOAL.exists(), reason="challenge data missing")
def test_load_subgoal_links_requirements(tmp_settings):
    inp = load_subgoal(SUBGOAL, tmp_settings)
    assert inp.case_id == "subgoal-dev" and len(inp.requirements_old) == 94
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
