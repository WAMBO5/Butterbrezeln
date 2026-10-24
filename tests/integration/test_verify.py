import json
from pathlib import Path

import pytest

from app.cli import main
from app.compliance.replay import replay
from app.eval.funnel import funnel_metrics
from app.pipeline.main import run_case
from app.testing.fake_llm import register_responders
from tests.conftest import CHALLENGE, GOLD, INDEX

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not INDEX.exists(), reason="challenge data missing")]
REAR_LAMP = CHALLENGE / "cases" / "dev-rear-lamp"


@pytest.fixture
async def fake_run(tmp_settings, fake_responders):
    res = await run_case(REAR_LAMP, markets=[], mode="benchmark", settings=tmp_settings, run_dir=None)
    return Path(res.run_dir)


async def test_replay_reproduces_and_detects_edits(fake_run, tmp_settings, fake_responders):
    assert replay(fake_run, fake_responders, tmp_settings) == []
    path = fake_run / "submission.json"
    data = json.loads(path.read_text())
    data["requirements"][0]["text"] = "The lamp shall be edited by hand."
    path.write_text(json.dumps(data))
    problems = replay(fake_run, fake_responders, tmp_settings)
    assert problems and any("submission.json" in p for p in problems)


async def test_funnel_values_in_range(fake_run, fake_responders):
    report = funnel_metrics(fake_run, GOLD, fake_responders)
    assert 0 <= report.golden_pages_in_sections <= 1 and 0 <= report.candidate_coverage <= 1
    assert report.scope_regulations_kept == "4/4" and report.final_score["regulation_level"]["recall"] == 1.0


def test_score_with_fake_judge(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CERTIVITY_DATA_DIR", str(tmp_path))
    assert main(["--fake-llm", "run", str(REAR_LAMP)]) == 0
    [run_dir] = list((tmp_path / "runs").iterdir())
    ours = [r["id"] for r in json.loads((run_dir / "submission.json").read_text())["requirements"]
            if r["source"]["regulation"] == "UN R150"]
    gold = [r["id"] for r in json.loads(GOLD.read_text())["requirements"] if r["source"]["regulation"] == "UN R150"]
    pairs = list(zip(ours[:3], gold[:3]))

    def judge(prompt, req):
        from app.agents.prompting import extract_payload
        payload = extract_payload(prompt)
        found = [{"ours": o, "golden": g} for o, g in pairs if o in payload["ours"] and g in payload["golden"]]
        return json.dumps({"pairs": found + found[:1]})  # a repeated pair must not count twice

    register_responders({"requirement_judge": judge})
    assert main(["--fake-llm", "score", str(run_dir), "--judge"]) == 0
    assert "matched: 3" in capsys.readouterr().out
