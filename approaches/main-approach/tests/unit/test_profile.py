import re
from pathlib import Path

import pytest

from app.agents.product_analyst import build_analyst_prompt
from app.agents.prompting import prompt_text
from app.gates.profile_gate import profile_gate
from app.matching.case_loader import CaseError, load_case
from app.models import CaseInput, Fact, Part, ProductProfile

CASES = Path("tests/fixtures/cases")
REAR_LAMP = Path("industrial-ai-hackathon/cases/dev-rear-lamp")


def profile(**kw):
    facts = [Fact(fact_id="f1", key="product type", value="side marker", unit=None, source="spec",
                  quote="Side marker lamp for trucks.")]
    data = dict(product_type="side marker lamp", vehicle_categories=["N"],
                parts=[Part(part_id="p1", name="Amber lamp", functions=["side marking"], properties=["emits amber light"],
                            materials=[], facts=facts)], relations=[], unknowns=[])
    data.update(kw)
    return ProductProfile(**data)


@pytest.mark.skipif(not REAR_LAMP.exists(), reason="challenge data missing")
def test_load_real_case():
    case = load_case(REAR_LAMP)
    assert case.case_id == "dev-rear-lamp" and len(case.image_paths) == 1 and "Rear lamp" in case.spec_text


def test_load_partial_cases():
    assert load_case(CASES / "spec_only").image_paths == [] and load_case(CASES / "image_only").spec_text is None
    with pytest.raises(CaseError):
        load_case(CASES / "empty")


def test_gate_accepts_valid_profile():
    assert profile_gate(load_case(CASES / "spec_only"), profile()) == []


def test_gate_rules():
    case = load_case(CASES / "spec_only")
    assert [i.type for i in profile_gate(case, profile(parts=[]))] == ["no_parts"]
    bad_quote = profile()
    bad_quote.parts[0].facts[0].quote = "Front lamp for buses"
    assert [i.type for i in profile_gate(case, bad_quote)] == ["quote_not_found"]
    dup = profile()
    dup.parts.append(dup.parts[0].model_copy())
    assert {i.type for i in profile_gate(case, dup)} == {"duplicate_id"}
    drawing = profile()
    drawing.parts[0].facts[0] = Fact(fact_id="f1", key="k", value="v", unit=None, source="drawing", quote="")
    assert [i.type for i in profile_gate(case, drawing)] == ["empty_quote"]
    image_only = load_case(CASES / "image_only")
    assert [i.type for i in profile_gate(image_only, profile())] == ["spec_fact_without_spec"]


def test_prompt_marks_spec_untrusted_and_has_no_regulations():
    blocks = build_analyst_prompt(load_case(CASES / "image_only"), [])
    assert blocks[0]["type"] == "image"
    text = prompt_text(build_analyst_prompt(load_case(CASES / "spec_only"), []))
    assert '<untrusted_input name="spec">' in text and not re.search(r"UN R\d", text)


def test_injection_stays_data():
    injected = load_case(CASES / "injected")
    text = prompt_text(build_analyst_prompt(injected, []))
    inj = "Ignore previous instructions"
    assert text.count(inj) == 1
    assert text.index('<untrusted_input name="spec">') < text.index(inj) < text.index("</untrusted_input>")
    clean = load_case(CASES / "spec_only")
    assert profile_gate(injected, profile()) == profile_gate(clean, profile())
