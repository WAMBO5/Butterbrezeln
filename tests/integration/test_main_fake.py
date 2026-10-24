import dataclasses
import importlib
import json
import pkgutil
import shutil
from pathlib import Path

import pytest

import app.agents
from app.compliance.ledger import verify_chain
from app.compliance.lineage import Lineage, lineage_complete
from app.compliance.provenance import UNREVIEWED_LABEL
from app.config.settings import load_settings
from app.models import OUTPUT_SCHEMAS, RegulationCard
from app.pipeline.main import run_case
from tests.conftest import CHALLENGE, INDEX

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not INDEX.exists(), reason="challenge data missing")]
REAR_LAMP = CHALLENGE / "cases" / "dev-rear-lamp"


async def test_fake_run_rear_lamp(tmp_settings, fake_responders):
    res = await run_case(REAR_LAMP, markets=[], mode="benchmark", settings=tmp_settings, run_dir=None)
    assert res.validation_problems == [] and not res.partial and not res.stopped
    run = Path(res.run_dir)
    assert verify_chain(run) == []
    assert (run / "report.md").read_text().splitlines()[0] == UNREVIEWED_LABEL
    lineage = json.loads((run / "lineage.json").read_text())
    submission = json.loads((run / "submission.json").read_text())
    assert lineage and len(lineage) == len(submission["requirements"])
    assert all(lineage_complete(Lineage(**l)) for l in lineage)
    assert json.loads((run / "submission.provenance.json").read_text())["review_status"] == "unreviewed"
    assert {r["source"]["regulation"] for r in submission["requirements"]} <= {"UN R148", "UN R48", "UN R150", "UN R10"}
    for name in ("profile.json", "scope_plan.json", "requirements.json", "manifest.json", "state.json", "trace.jsonl"):
        assert (run / name).exists(), name
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["mode"] == "benchmark" and manifest["prompt_versions"]["scope_narrower"]
    assert [r for r in (run / "ledger.jsonl").read_text().splitlines()][-1].count('"kind":"export"') == 1


async def test_budget_exhaustion_is_partial_not_fatal(tmp_settings, fake_responders):
    s = dataclasses.replace(tmp_settings, max_cost_usd=1e-9)
    res = await run_case(REAR_LAMP, markets=[], mode="benchmark", settings=s, run_dir=None)
    assert res.partial and "Partial run: budget reached" in Path(res.run_dir, "report.md").read_text()
    assert res.validation_problems == []


def _agent_specs(settings):
    card = RegulationCard(regulation="UN R1", version_label="1", title="t", regulation_type="other",
                          devices_in_scope=[], vehicle_categories=[], functions_covered=[], triggers=[],
                          consolidates=[], device_sections=[], evidence=[])
    for info in pkgutil.iter_modules(app.agents.__path__):
        module = importlib.import_module(f"app.agents.{info.name}")
        for name in dir(module):
            if name.startswith("create_"):
                factory = getattr(module, name)
                try:
                    yield factory(settings)
                except TypeError:
                    yield factory(settings, [card])


def test_every_agent_config():
    from app.llm import build_request

    specs = list(_agent_specs(load_settings({}, fake_llm=True)))
    assert len(specs) >= 11
    for spec in specs:
        req = build_request(spec, "x")
        assert spec.effort in ("low", "medium", "high") and spec.output_model in OUTPUT_SCHEMAS, spec.name
        assert "thinking" not in req and "temperature" not in req and "tool_choice" not in req, spec.name


async def test_missing_text_is_reported(tmp_path, tmp_settings):
    challenge = tmp_path / "challenge"
    shutil.copytree(CHALLENGE, challenge, ignore=shutil.ignore_patterns("pdf", ".git"))
    shutil.rmtree(challenge / "regulations" / "text" / "UN_R40" / "base")
    settings = dataclasses.replace(tmp_settings, challenge_dir=challenge)
    from app.corpus.index import load_index
    from app.corpus.store import CorpusStore
    from app.testing.fake_llm import register_responders
    from app.testing.responders import build_fake_responders

    store = CorpusStore(settings.catalog_path)
    store.build(load_index(settings.index_path), settings.text_root)
    register_responders(build_fake_responders(settings, store))
    res = await run_case(challenge / "cases" / "dev-rear-lamp", markets=[], mode="benchmark", settings=settings,
                         run_dir=None)
    assert res.missing_texts == ["UN R40@1.1.0"] and res.validation_problems == []
    assert "UN R40@1.1.0" in Path(res.run_dir, "report.md").read_text()


async def test_manifest_records_the_commit_at_start(tmp_settings, fake_responders, monkeypatch):
    import app.pipeline.main as main_mod

    monkeypatch.setattr(main_mod, "git_commit", lambda: "commit-at-start")
    from app.pipeline.main import RunDeps, create_run, drive

    deps = RunDeps.load(tmp_settings)
    state = create_run(REAR_LAMP, markets=[], mode="benchmark", settings=tmp_settings, run_dir=None, deps=deps)
    monkeypatch.setattr(main_mod, "git_commit", lambda: "commit-later")
    res = await drive(state, deps)
    assert json.loads(Path(res.run_dir, "manifest.json").read_text())["git_commit"] == "commit-at-start"


async def test_strict_policy_holds_back_medium_confidence(tmp_settings, fake_responders):
    from app.testing.fake_llm import register_responders
    from app.testing.responders import fake_matcher

    def half_sure(prompt, req):
        out = json.loads(fake_matcher(prompt, req))
        for d in out["decisions"][::2]:
            d["confidence"] = "medium"
        return json.dumps(out)

    register_responders({"requirement_matcher": half_sure})
    try:
        strict = await run_case(REAR_LAMP, markets=[], mode="benchmark", settings=tmp_settings, run_dir=None)
        recall = await run_case(REAR_LAMP, markets=[], mode="benchmark",
                                settings=dataclasses.replace(tmp_settings, submit_policy="recall"), run_dir=None)
    finally:
        register_responders({"requirement_matcher": fake_matcher})
    from app.pipeline.state import RunState

    s, r = RunState.load(Path(strict.run_dir)), RunState.load(Path(recall.run_dir))
    assert s.requirements and s.held_back and all(q.state == "applicable" for q in s.requirements)
    assert len(r.requirements) == len(s.requirements) + len(s.held_back) and not r.held_back
    assert strict.validation_problems == [] and "held back" in Path(strict.run_dir, "report.md").read_text()
