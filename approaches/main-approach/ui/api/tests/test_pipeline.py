"""End-to-end run on the dev rear lamp with the mock backend, rules only, fixture country data."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from api.config import CASES_DIR

SPEC = (CASES_DIR / "dev-rear-lamp" / "spec.md").read_text(encoding="utf-8")

COUNTRIES = {
    "meta": {"sources": []},
    "countries": {
        "DEU": {"name_de": "Deutschland", "regime": "unece_1958", "applied_regulations": "all", "profile": None},
        "FRA": {"name_de": "Frankreich", "regime": "unece_1958", "applied_regulations": ["UN R10", "UN R48", "UN R148", "UN R150"], "profile": None},
        "JPN": {"name_de": "Japan", "regime": "unece_1958", "applied_regulations": ["UN R48", "UN R148", "UN R150"], "profile": None},
        "KOR": {"name_de": "Südkorea", "regime": "unece_1958", "applied_regulations": ["UN R48"], "profile": None},
        "CHN": {"name_de": "China", "regime": "national", "applied_regulations": [], "profile": "CHN"},
        "USA": {"name_de": "USA", "regime": "national", "applied_regulations": [], "profile": "USA"},
    },
}


def _profile(iso3, deviations):
    return {"iso3": iso3, "name_de": iso3, "summary_de": "Testprofil.", "accepts_un_approvals": False,
            "deviations": deviations}


CHN = _profile("CHN", [
    {"id": "CHN-01", "topic_de": "CCC", "effort": "pruefung_zertifizierung", "spec_section": "Zertifizierung",
     "suggestion_de": "CCC-Zertifizierung durchführen.", "check": {"type": "always"}, "source_url": "https://example.org/ccc"},
])
USA = _profile("USA", [
    {"id": "USA-01", "topic_de": "Seitenmarkierung", "effort": "design", "spec_section": "Function",
     "suggestion_de": "Seitenmarkierungsleuchte ergänzen.", "check": {"type": "spec_missing", "keywords": ["side marker"]},
     "source_url": "https://example.org/fmvss108"},
    {"id": "USA-02", "topic_de": "nie zutreffend", "effort": "design", "spec_section": "Function",
     "suggestion_de": "-", "check": {"type": "spec_contains", "keywords": ["xenon"]}},
])


@pytest.fixture()
def client(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "country_profiles").mkdir(parents=True)
    (data / "countries.json").write_text(json.dumps(COUNTRIES))
    (data / "country_profiles" / "CHN.json").write_text(json.dumps(CHN))
    (data / "country_profiles" / "USA.json").write_text(json.dumps(USA))
    monkeypatch.setattr("api.countries.DATA_DIR", data)

    from api import main
    from api.llm import LLM
    from api.runs import RunStore

    store = RunStore(tmp_path / "runs")
    store.llm = LLM(mode="off")
    monkeypatch.setattr(main, "store", store)
    return TestClient(main.app)


def _run(client, countries="DEU,FRA,JPN,CHN,USA,BRA"):
    response = client.post("/api/runs", files={"spec": ("spec.md", SPEC.encode())}, data={"countries": countries})
    assert response.status_code == 200, response.text
    run_id = response.json()["run_id"]
    for _ in range(200):
        result = client.get(f"/api/runs/{run_id}").json()
        if result["status"] != "running":
            return run_id, result
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_verdicts_follow_the_traffic_light_rule(client):
    _, result = _run(client)
    assert result["status"] == "done", result["error"]
    status = {iso: v["status"] for iso, v in result["verdicts"].items()}
    assert status == {"DEU": "green", "FRA": "green", "JPN": "yellow", "CHN": "yellow", "USA": "red", "BRA": "grey"}
    # UN R10 was researched (France lists it) and Japan does not apply it -> certification suggestion
    jpn = result["verdicts"]["JPN"]["suggestions"]
    assert len(jpn) == 1 and "UN R10" in jpn[0]["change"]
    usa = result["verdicts"]["USA"]["suggestions"]
    assert [s["deviation_id"] for s in usa] == ["USA-01"]
    assert usa[0]["sources"][0]["kind"] == "external"


def test_unresearched_regulation_is_not_a_gap(client, tmp_path):
    data = json.loads(json.dumps(COUNTRIES))
    del data["countries"]["FRA"]  # now no country lists UN R10: its application was never looked up
    (tmp_path / "data" / "countries.json").write_text(json.dumps(data))
    _, result = _run(client, "JPN")
    jpn = result["verdicts"]["JPN"]
    assert jpn["status"] == "green" and not jpn["suggestions"]
    assert any("UN R10" in r and "nicht geprüft" in r for r in jpn["reasons"])


def test_requirements_cite_pages_and_validate(client):
    _, result = _run(client)
    assert len(result["requirements"]) == 190
    assert result["validation"]["ok"], result["validation"]["problems"]
    for r in result["requirements"]:
        assert r["source"]["page"] and r["source"]["href"]


def test_every_trace_id_resolves(client):
    run_id, result = _run(client)
    events = {e["id"]: e for e in client.get(f"/api/runs/{run_id}/trace").json()}
    ids = [t for r in result["requirements"] for t in r["trace_ids"]]
    ids += [t for f in result["findings"] for t in f["trace_ids"]]
    for v in result["verdicts"].values():
        ids += v["trace_ids"] + [t for s in v["suggestions"] for t in s["trace_ids"]]
    assert ids and all(t in events for t in ids)
    assert all(e["status"] != "running" for e in events.values())
    # the requirement step cites the regulation it selected
    req_event = events[result["requirements"][0]["trace_ids"][0]]
    assert req_event["sources"][0]["kind"] == "un_regulation"


def test_ask_and_decide_are_logged(client):
    run_id, result = _run(client, "CHN")
    qa = client.post(f"/api/runs/{run_id}/countries/CHN/ask", json={"question": "Was muss sich für China ändern?"}).json()
    assert "CCC" in qa["answer"]
    sid = result["verdicts"]["CHN"]["suggestions"][0]["id"]
    decided = client.patch(f"/api/runs/{run_id}/suggestions/{sid}", json={"decision": "akzeptiert"}).json()
    assert decided["decision"] == "akzeptiert"
    agents = [e["agent"] for e in client.get(f"/api/runs/{run_id}/trace").json()]
    assert "qa_agent" in agents and "human_review" in agents


class ScriptedLLM:
    """Stands in for LLM in the country Q&A: returns one fixed answer."""
    available = True
    model = "scripted"
    disabled_reason = None

    def __init__(self, data):
        self.data = data

    def json(self, **_):
        return self.data, {"model": self.model, "prompt": "", "tokens": {"input": 0, "output": 0}}


def test_llm_is_off_unless_switched_on_with_a_model():
    from api.llm import LLM

    assert not LLM(mode="off", model="some-model").available
    assert not LLM(mode="on", model="").available


def test_qa_drops_uncited_suggestions_and_flags_uncited_answers(client):
    from api import main

    run_id, _ = _run(client, "CHN")
    suggestion = {"spec_section": "Zertifizierung", "change": "CCC-Prüfung beauftragen", "reason": "CCC",
                  "effort": "pruefung_zertifizierung", "requirement_id": "", "deviation_id": "CHN-01"}
    main.store.llm = ScriptedLLM({"answer": "CCC einplanen.", "cited_requirement_ids": [], "cited_deviation_ids": ["CHN-01"],
                                  "suggestions": [suggestion, {**suggestion, "change": "Ohne Beleg", "deviation_id": ""}]})
    qa = client.post(f"/api/runs/{run_id}/countries/CHN/ask", json={"question": "Was fehlt?"}).json()
    added = [s for s in client.get(f"/api/runs/{run_id}").json()["verdicts"]["CHN"]["suggestions"] if s["id"] in qa["suggestion_ids"]]
    assert [s["change"] for s in added] == ["CCC-Prüfung beauftragen"] and added[0]["sources"][0]["kind"] == "external"
    assert "Ohne Quellenangabe" not in qa["answer"]

    main.store.llm = ScriptedLLM({"answer": "Keine Ahnung.", "cited_requirement_ids": [], "cited_deviation_ids": [], "suggestions": []})
    qa = client.post(f"/api/runs/{run_id}/countries/CHN/ask", json={"question": "Und sonst?"}).json()
    assert "Ohne Quellenangabe" in qa["answer"] and not qa["sources"]
