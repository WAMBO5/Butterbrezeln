import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.compliance.oversight import (HumanAction, OversightError, export_status, open_items, sign_off,
                                      validate_actions)
from app.pipeline.main import run_case
from app.pipeline.oversight import resume_run
from app.pipeline.state import RunState
from app.testing.fake_llm import register_responders
from tests.conftest import CHALLENGE, INDEX

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not INDEX.exists(), reason="challenge data missing")]
REAR_LAMP = CHALLENGE / "cases" / "dev-rear-lamp"


def act(checkpoint, action="confirm", target=None, reason=None, payload=None):
    return HumanAction(checkpoint=checkpoint, reviewer="alex", action=action, target_id=target, reason=reason,
                       payload=payload, ts=datetime.now(timezone.utc).isoformat())


async def test_assisted_run_pauses_at_each_checkpoint(tmp_settings, fake_responders):
    res = await run_case(REAR_LAMP, markets=[], mode="assisted", settings=tmp_settings, run_dir=None)
    assert (res.status, res.checkpoint) == ("awaiting_review", "C1_profile")
    res = await resume_run(Path(res.run_dir), "C1_profile", [act("C1_profile")], settings=tmp_settings)
    assert res.checkpoint == "C2_scope"
    override = act("C2_scope", "override", "UN R10", "EMC applies to the LED driver",
                   {"state": "applicable"})
    res = await resume_run(Path(res.run_dir), "C2_scope", [override], settings=tmp_settings)
    assert res.checkpoint == "C3_requirements"
    res = await resume_run(Path(res.run_dir), "C3_requirements", [act("C3_requirements")], settings=tmp_settings)
    assert res.status == "done" and res.validation_problems == []
    run = Path(res.run_dir)
    assert export_status(run) == "unreviewed"
    sign_off(run, "alex", "Reviewed all requirements.")
    assert export_status(run) == "reviewed"
    provenance = json.loads((run / "submission.provenance.json").read_text())
    assert provenance["review_status"] == "reviewed" and provenance["label"] is None
    kinds = [json.loads(l)["kind"] for l in (run / "ledger.jsonl").read_text().splitlines()]
    assert kinds.count("human_action") == 4  # C1, C2, C3 and the C4 sign-off
    state = RunState.load(run)
    assert "UN R10" in state.pinned_decisions


async def test_override_without_reason_is_reasked(tmp_settings, fake_responders):
    res = await run_case(REAR_LAMP, markets=[], mode="assisted", settings=tmp_settings, run_dir=None)
    res = await resume_run(Path(res.run_dir), "C1_profile", [act("C1_profile", "override", "p1")],
                           settings=tmp_settings)
    assert res.checkpoint == "C1_profile" and RunState.load(Path(res.run_dir)).checkpoint_errors
    assert validate_actions([act("C1_profile", "edit", "p1", "  ")])


async def test_stop_at_scope_ends_the_run(tmp_settings, fake_responders):
    res = await run_case(REAR_LAMP, markets=[], mode="assisted", settings=tmp_settings, run_dir=None)
    res = await resume_run(Path(res.run_dir), "C1_profile", [act("C1_profile")], settings=tmp_settings)
    res = await resume_run(Path(res.run_dir), "C2_scope", [act("C2_scope", "stop", reason="wrong product")],
                           settings=tmp_settings)
    assert res.stopped and res.status == "stopped"
    assert "Stopped by reviewer" in Path(res.run_dir, "report.md").read_text()


async def test_signoff_refused_while_items_are_open(tmp_settings, fake_responders):
    from app.testing.responders import fake_matcher

    def uncertain_matcher(prompt, req):
        out = json.loads(fake_matcher(prompt, req))
        out["decisions"][0]["confidence"] = "medium"
        return json.dumps(out)

    register_responders({"requirement_matcher": uncertain_matcher})
    res = await run_case(REAR_LAMP, markets=[], mode="assisted", settings=tmp_settings, run_dir=None)
    for checkpoint in ("C1_profile", "C2_scope"):
        res = await resume_run(Path(res.run_dir), checkpoint, [act(checkpoint)], settings=tmp_settings)
    res = await resume_run(Path(res.run_dir), "C3_requirements", [act("C3_requirements")], settings=tmp_settings)
    run = Path(res.run_dir)
    state = RunState.load(run)
    assert open_items(state.requirements, state.give_ups, state.human_actions)
    with pytest.raises(OversightError):
        sign_off(run, "alex", "ok")
    register_responders({"requirement_matcher": fake_matcher})
