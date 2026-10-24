import json

from app.compliance.ledger import Ledger, verify_chain
from app.compliance.manifest import Manifest, prompt_version, write_manifest
from app.compliance.redact import redact


def test_chain_detects_edit(tmp_path):
    led = Ledger(tmp_path)
    for i in range(3):
        led.append("note", "test", {"i": i}, None, {})
    assert verify_chain(tmp_path) == []
    lines = (tmp_path / "ledger.jsonl").read_text().splitlines()
    lines[1] = lines[1].replace('"actor":"test"', '"actor":"evil"')
    (tmp_path / "ledger.jsonl").write_text("\n".join(lines) + "\n")
    assert any("seq 2" in m for m in verify_chain(tmp_path))


def test_key_never_written(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-leak-777")
    Ledger(tmp_path).append("note", "t", {"api_key": "sk-leak-777", "x": "sk-leak-777"}, None, {})
    write_manifest(tmp_path, Manifest(run_id="r", mode="benchmark", started_at="a", finished_at=None, git_commit=None,
                                      settings={"note": "key sk-leak-777"}, inputs={}, corpus={}, prompt_versions={},
                                      models={}, cost={}, review=None))
    assert "sk-leak-777" not in "".join(p.read_text() for p in tmp_path.rglob("*") if p.is_file())


def test_two_ledger_objects_share_one_chain(tmp_path):
    Ledger(tmp_path).append("note", "a", {"n": 1}, None, {})
    rec = Ledger(tmp_path).append("note", "b", {"n": 2}, {"ok": True}, {"m": 1})
    assert rec.seq == 2 and verify_chain(tmp_path) == []
    assert json.loads((tmp_path / "calls" / "2.json").read_text()) == {"input": {"n": 2}, "output": {"ok": True}}
    assert [r.actor for r in Ledger(tmp_path).records()] == ["a", "b"]


def test_redact_drops_secret_keys():
    assert redact({"Authorization": "x", "nested": [{"secret_token": 1, "ok": 2}]}) == {"nested": [{"ok": 2}]}


def test_prompt_version_is_short_hash():
    assert len(prompt_version("abc")) == 12 and prompt_version("abc") != prompt_version("abd")
