"""Runs the UI reads and starts: real before demo, failed runs skipped, demo runs isolated, the benchmark score."""

import hashlib
import json
from pathlib import Path

import pytest

from api import benchmark, pipeline_jobs, pipeline_runs
from api.config import CASES_DIR

SPEC = "# spec: Test lamp\n\n## Function\n\n- Stop lamp\n"


def _run(root: Path, run_id: str, *, fake: bool = False, status: str = "done", requirements: list | None = None) -> Path:
    folder = root / run_id
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps({
        "run_id": run_id, "started_at": run_id[:15], "finished_at": "x",
        "inputs": {"spec.md": hashlib.sha256(SPEC.encode()).hexdigest()}, "settings": {"fake_llm": fake}}))
    (folder / "state.json").write_text(json.dumps({"status": status}))
    (folder / "submission.json").write_text(json.dumps({"requirements": requirements or []}))
    (folder / "lineage.json").write_text("[]")
    return folder


def test_a_real_run_wins_over_a_later_demo_run_and_failed_runs_are_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_runs, "PIPELINE_RUN_DIRS", [tmp_path])
    _run(tmp_path, "20261025T080000Z-case")
    _run(tmp_path, "20261025T090000Z-case", fake=True)
    _run(tmp_path, "20261025T100000Z-case", status="failed")
    assert pipeline_runs.match(SPEC).run_id == "20261025T080000Z-case"
    assert pipeline_runs.match(SPEC, prefer="20261025T090000Z-case").run_id == "20261025T090000Z-case"
    assert pipeline_runs.match(SPEC, prefer="20261025T100000Z-case").run_id == "20261025T080000Z-case"  # failed


def test_the_run_just_started_is_found_by_its_folder_name(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_runs, "PIPELINE_RUN_DIRS", [tmp_path])
    _run(tmp_path, "20261025T080000Z-case")
    folder = _run(tmp_path, "20261025T090000Z-job", fake=True)  # the folder is the job id; the pipeline names its run
    manifest = json.loads((folder / "manifest.json").read_text())
    (folder / "manifest.json").write_text(json.dumps({**manifest, "run_id": "20261025T090001Z-case"}))
    assert pipeline_runs.match(SPEC, prefer="20261025T090000Z-job").dir == folder
    assert pipeline_runs.find("20261025T090000Z-job").dir == folder


def test_a_demo_run_is_used_when_there_is_no_real_one(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_runs, "PIPELINE_RUN_DIRS", [tmp_path])
    _run(tmp_path, "20261025T090000Z-case", fake=True)
    ref = pipeline_runs.match(SPEC)
    assert ref.run_id == "20261025T090000Z-case" and ref.fake


def test_benchmark_scores_only_against_the_challenge_reference(tmp_path):
    case = CASES_DIR / "dev-rear-lamp"
    if not (case / "expected.json").exists():
        pytest.skip("challenge case not present (see industrial-ai-hackathon/README.md)")
    expected = json.loads((case / "expected.json").read_text(encoding="utf-8"))
    folder = tmp_path / "run"
    folder.mkdir()
    (folder / "submission.json").write_text(json.dumps(expected))
    b = benchmark.for_run(folder, (case / "spec.md").read_text(encoding="utf-8"), {})
    assert b.case_id == "dev-rear-lamp" and b.valid
    assert [lv.level for lv in b.levels] == ["regulation", "page", "requirement"]
    assert all(abs(lv.f2 - 1) < 1e-9 for lv in b.levels)
    other = benchmark.for_run(folder, SPEC, {"validation_problems": ["bad page"]})
    assert other.case_id is None and not other.levels and not other.valid


def test_f2_weighs_recall_four_times():
    assert abs(benchmark.f2(0.5, 1.0) - 5 * 0.5 / (4 * 0.5 + 1)) < 1e-9
    assert benchmark.f2(0, 0) == 0


def test_demo_runs_get_their_own_extraction_cache_and_real_runs_a_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_jobs, "DEMO_DIR", tmp_path / "demo")
    root = tmp_path / "repo"
    (root / "data" / "shared" / "cards").mkdir(parents=True)
    (root / "data" / pipeline_jobs.PIPELINE_APPROACH).mkdir(parents=True)
    (root / "data" / pipeline_jobs.PIPELINE_APPROACH / "catalog.sqlite").write_text("")
    (root / "data" / "shared" / "obligations.sqlite").write_text("")
    monkeypatch.setattr(pipeline_jobs, "PIPELINE_ROOT", root)

    demo = pipeline_jobs._env(True)
    data = Path(demo["CERTIVITY_DATA_DIR"])
    assert data.is_relative_to(tmp_path / "demo")
    assert (data / "catalog.sqlite").is_symlink() and (data / "cards").is_symlink()
    assert not (data / "obligations.sqlite").exists()  # created by the run itself, never the shared file
    assert "--fake-llm" in pipeline_jobs._command(Path("c"), Path("r"), True)

    real = pipeline_jobs._env(False)
    assert real.get("CERTIVITY_DATA_DIR") != demo["CERTIVITY_DATA_DIR"]
    assert float(real["CERTIVITY_MAX_COST_USD"]) == pipeline_jobs.PIPELINE_MAX_COST_USD
    assert "--fake-llm" not in pipeline_jobs._command(Path("c"), Path("r"), False)


def test_real_mode_needs_key_and_models_and_never_shows_the_key(monkeypatch):
    monkeypatch.setattr(pipeline_jobs, "PIPELINE_FAKE_LLM", False)
    monkeypatch.setattr(pipeline_jobs, "launch_problem", lambda: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert "ANTHROPIC_API_KEY" in pipeline_jobs.real_problem()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-secret")
    monkeypatch.delenv("ANTHROPIC_MODEL_FAST", raising=False)
    problem = pipeline_jobs.real_problem()
    assert "ANTHROPIC_MODEL_FAST" in problem and "sk-test-secret" not in problem
    monkeypatch.setattr(pipeline_jobs, "PIPELINE_FAKE_LLM", True)
    assert "demo" in pipeline_jobs.real_problem()


def test_a_real_run_is_refused_in_code_when_real_mode_is_not_ready(monkeypatch):
    monkeypatch.setattr(pipeline_jobs, "real_problem", lambda: "No API key")
    monkeypatch.setattr(pipeline_jobs, "launch_problem", lambda: None)
    started = []
    monkeypatch.setattr(pipeline_jobs.subprocess, "Popen", lambda *a, **k: started.append(a))
    try:
        pipeline_jobs.start(SPEC.encode(), demo=False)
        raise AssertionError("a real run started without an API key")
    except pipeline_jobs.JobError as exc:
        assert "No API key" in str(exc)
    assert not started


def test_the_api_refuses_real_mode_without_a_key(monkeypatch):
    from fastapi.testclient import TestClient

    from api import main
    monkeypatch.setattr(pipeline_jobs, "real_problem", lambda: "No API key: set ANTHROPIC_API_KEY in .env")
    client = TestClient(main.app)
    r = client.post("/api/runs", files={"spec": ("spec.md", SPEC)}, data={"countries": "DEU", "real": "true"})
    assert r.status_code == 409 and "ANTHROPIC_API_KEY" in r.json()["detail"]
    assert client.get("/api/health").json()["real"] == {"available": False, "reason": "No API key: set ANTHROPIC_API_KEY in .env",
                                                          "model": main.store.llm_real.model}


def test_lookup_names_the_analysis_that_would_be_reused(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from api import main
    monkeypatch.setattr(pipeline_runs, "PIPELINE_RUN_DIRS", [tmp_path])
    monkeypatch.setattr(main, "BACKEND_MODE", "runs")
    client = TestClient(main.app)
    assert client.post("/api/pipeline/lookup", files={"spec": ("spec.md", SPEC)}).json() == {"run": None}
    _run(tmp_path, "20261025T080000Z-case")
    found = client.post("/api/pipeline/lookup", files={"spec": ("spec.md", SPEC)}).json()["run"]
    assert found["run_id"] == "20261025T080000Z-case" and found["fake_llm"] is False


def test_a_result_is_fresh_only_when_its_pipeline_run_was_started_for_it(tmp_path):
    from api.runs import RunStore
    store = RunStore(tmp_path)
    assert store.start("spec.md", SPEC, None, ["DEU"], pipeline_run="job-1").result.pipeline_fresh
    assert not store.start("spec.md", SPEC, None, ["DEU"]).result.pipeline_fresh
