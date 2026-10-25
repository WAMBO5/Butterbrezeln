import pytest
from pydantic import ValidationError

from app.models import OUTPUT_SCHEMAS, MatchDecision, Requirement, Source


def test_requirement_text_limit():
    with pytest.raises(ValidationError):
        Requirement(id="R-001", text="x" * 2001, source=Source(regulation="UN R48", version="9.3.0", page=1, paragraph=None),
                    part_ids=[], obligation_ids=[], state="applicable", reason="r", evidence_status="met", test_case=None)


def test_state_literal():
    with pytest.raises(ValidationError):
        MatchDecision(part_id="p1", obligation_id="o", state="maybe", reason="", fact_refs=[], evidence_status="met", test_case="")


def test_every_output_schema_renders_json_schema():
    assert all(m.model_json_schema()["type"] == "object" for m in OUTPUT_SCHEMAS)


def test_output_schemas_accepted_by_structured_output_transform():
    # the SDK turns each model into the strict schema it sends; it must not raise
    from anthropic.lib._parse._transform import transform_schema

    for model in OUTPUT_SCHEMAS:
        assert transform_schema(model)["additionalProperties"] is False
