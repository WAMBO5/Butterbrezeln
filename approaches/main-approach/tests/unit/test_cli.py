import pytest

from app.cli import build_parser, main
from tests.conftest import INDEX


def test_doctor_never_prints_the_key(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-cli-999")
    monkeypatch.setenv("CERTIVITY_DATA_DIR", str(tmp_path))
    code = main(["doctor"])
    out = capsys.readouterr().out
    assert "sk-test-cli-999" not in out and "API key: set" in out and code == 0
    assert "catalog: missing" in out and "cards: 0" in out


def test_doctor_without_key_fails(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("CERTIVITY_DATA_DIR", str(tmp_path))
    assert main(["doctor"]) == 1 and "API key: missing" in capsys.readouterr().out
    assert main(["--fake-llm", "doctor"]) == 0


def test_ping_flag_parses():
    args = build_parser().parse_args(["doctor", "--ping"])
    assert args.command == "doctor" and args.ping


@pytest.mark.integration
@pytest.mark.skipif(not INDEX.exists(), reason="challenge data missing")
def test_fake_bench(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CERTIVITY_DATA_DIR", str(tmp_path))
    assert main(["--fake-llm", "bench"]) == 0
    out = capsys.readouterr().out
    assert "regulation_level" in out and "validate.py: no problems" in out and "golden pages in sections" in out


def test_signoff_refuses_unfinished_run(tmp_path, capsys):
    from datetime import datetime, timezone

    from app.pipeline.state import RunState

    RunState(run_id="r", run_dir=str(tmp_path), case_dir=str(tmp_path), case_id="c", started_at=datetime.now(
        timezone.utc).isoformat(), status="awaiting_review").save()
    assert main(["signoff", str(tmp_path), "--reviewer", "alex"]) == 1
    assert "sign-off refused" in capsys.readouterr().err
