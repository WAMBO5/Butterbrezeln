import time
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.matching.submission import validate_submission
from server.main import create_app
from tests.conftest import CHALLENGE, INDEX

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not INDEX.exists(), reason="challenge data missing")]
REAR_LAMP = str(CHALLENGE / "cases" / "dev-rear-lamp")


@pytest.fixture
def client(tmp_settings):
    with TestClient(create_app(tmp_settings)) as c:
        yield c


def wait(client, run_id, until=("done", "failed", "stopped", "awaiting_review"), timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/runs/{run_id}").json()
        if body["status"] in until:
            return body
        time.sleep(0.2)
    raise AssertionError(f"run {run_id} did not finish: {body['status']}")


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_benchmark_run_end_to_end(client, tmp_settings):
    run_id = client.post("/runs", json={"case_dir": REAR_LAMP, "markets": [], "mode": "benchmark"}).json()["run_id"]
    body = wait(client, run_id)
    assert body["status"] == "done" and body["requirements"] and body["label"]
    assert set(body["quotes"]) == {r["id"] for r in body["requirements"]}
    submission = client.get(f"/runs/{run_id}/submission.json").json()
    assert validate_submission(submission, tmp_settings) == []
    rid = body["requirements"][0]["id"]
    lineage = client.get(f"/runs/{run_id}/requirements/{rid}/lineage").json()
    assert {"part", "provision", "match_decision"} <= {l["step"] for l in lineage["links"]}
    assert client.get(f"/runs/{run_id}/manifest").json()["mode"] == "benchmark"
    assert client.get(f"/runs/{run_id}/provenance.json").json()["review_status"] == "unreviewed"
    assert client.get(f"/runs/{run_id}/ledger").json()[-1]["kind"] == "export"
    events = client.get(f"/runs/{run_id}/events")
    assert events.headers["content-type"].startswith("text/event-stream") and "data: " in events.text
    assert any(r["run_id"] == run_id for r in client.get("/runs").json())


def test_sources(client):
    page = client.get("/pages/UN R148/1.6.0/6").json()
    assert page["text"] and not page["text"].startswith("UN R148, version")
    prov = client.get("/provisions/" + quote("UN R148@1.6.0#3.1", safe="")).json()
    assert prov["paragraph"] == "3.1" and prov["page_start"] >= 1
    assert client.get("/pages/UN R148/1.6.0/999").status_code == 404


def test_assisted_checkpoints_and_signoff(client):
    run_id = client.post("/runs", json={"case_dir": REAR_LAMP, "markets": [], "mode": "assisted"}).json()["run_id"]
    body = wait(client, run_id)
    assert body["status"] == "awaiting_review"
    cp = client.get(f"/runs/{run_id}/checkpoints").json()
    assert cp["checkpoint"] == "C1_profile" and cp["profile"]
    assert client.post(f"/runs/{run_id}/signoff", json={"reviewer": "alex", "statement": "ok"}).status_code == 409
    bad = client.post(f"/runs/{run_id}/checkpoints/C1_profile",
                      json={"reviewer": "alex", "actions": [{"action": "override", "target_id": "p1"}]})
    assert bad.status_code == 422
    ok = client.post(f"/runs/{run_id}/checkpoints/C1_profile", json={"reviewer": "alex", "actions": [{"action": "confirm"}]})
    assert ok.status_code == 202
    assert wait(client, run_id)["checkpoint"] == "C2_scope"
    assert client.post(f"/runs/{run_id}/stop", json={"reviewer": "alex", "reason": "demo"}).status_code == 202
    assert wait(client, run_id)["status"] == "stopped"


def test_bad_case_is_rejected(client, tmp_path):
    assert client.post("/runs", json={"case_dir": str(tmp_path), "markets": [], "mode": "benchmark"}).status_code == 400


def test_upload_creates_a_run(client):
    files = [("files", ("spec.md", b"# spec: Side marker\n\n## Main Parts\n\n- Amber lamp\n", "text/markdown"))]
    run_id = client.post("/runs/upload", data={"case_id": "upload-test", "mode": "benchmark"}, files=files).json()["run_id"]
    assert wait(client, run_id)["status"] == "done"


def test_markets_endpoints(client):
    markets = client.get("/markets").json()
    assert {m["market_id"] for m in markets} >= {"market_a", "market_b", "market_c"} and all(m["illustrative"] for m in markets)
    run_id = client.post("/runs", json={"case_dir": REAR_LAMP, "markets": [], "mode": "benchmark"}).json()["run_id"]
    assert wait(client, run_id)["markets_result"] is None
    assert client.post(f"/runs/{run_id}/markets", json={"markets": ["market_a", "market_c"]}).status_code == 202
    deadline = time.time() + 30
    while time.time() < deadline and client.get(f"/runs/{run_id}").json()["markets_result"] is None:
        time.sleep(0.2)
    result = client.get(f"/runs/{run_id}").json()["markets_result"]
    assert {v["market_id"]: v["verdict"] for v in result["markets"]["verdicts"]}["market_c"] == "not_covered"
