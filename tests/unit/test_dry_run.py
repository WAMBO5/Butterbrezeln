"""The whole product graph on dev-rear-lamp with a fake model: wiring, state keys, files, verifier, export, validate.py.

Costs nothing (no API call). Needs the full local index; skipped until `python -m pipeline.legal` has finished.
"""
import asyncio
import json
import re

import pytest

from pipeline import config, llm
from pipeline.models import (Component, DraftRequirement, DraftRequirements, Functionality, FunctionalityList,
                             JudgeDecision, JudgeDecisions, ProductProfile, QueryRewrites, RegulationDecision,
                             RouteDecisions, TriageGrade, TriageGrades)


def _index_ready() -> bool:
    try:
        from pipeline.rag import store
        return not store.missing_versions()
    except Exception:  # locked by a running indexer, or no store yet
        return False


BLOCK = re.compile(r'<provision ref="(P\d+)"[^>]*>\nheading: [^\n]*\n(.*?)\n</provision>', re.S)
APPLICABLE = {"UN R10", "UN R48", "UN R148", "UN R150", "UN R7", "UN R3"}  # R7 and R3 must be dropped as superseded


def _fake_llm():
    state = {"judge_calls": 0}

    async def structured(output_type, system, content, **kwargs):
        if output_type is ProductProfile:
            return ProductProfile(product_name="Rear lamp", product_type="rear lamp", vehicle_categories=["M1"],
                                  context_facts=["mounted at the rear of the vehicle"],
                                  components=[Component(id="assembly", name="Rear lamp", parent_id="", attributes=[],
                                                        unknowns=[], conflicts=[])])
        if output_type is FunctionalityList:
            qs = lambda name, extra: [name, f"{name} {extra}", f"The {name} shall comply with the requirements"]
            return FunctionalityList(functionalities=[
                Functionality(id="rear_position_lamp", statement="rear position lamp", component_ids=["assembly"],
                              queries=qs("rear position lamp", "luminous intensity colour red geometric visibility")),
                Functionality(id="stop_lamp", statement="stop lamp", component_ids=["assembly"], queries=qs("stop lamp", "braking")),
                Functionality(id="rear_retro_reflector", statement="retro-reflector", component_ids=["assembly"],
                              queries=qs("rear retro-reflector", "coefficient of luminous intensity")),
                Functionality(id="emc", statement="electronics", component_ids=["assembly"],
                              queries=qs("electromagnetic compatibility", "electrical electronic sub-assembly immunity emission"))])
        if output_type is RouteDecisions:
            entries = json.loads(content.split("Regulations to decide:\n")[1])
            return RouteDecisions(decisions=[RegulationDecision(
                regulation=e["regulation"], decision="applicable" if e["regulation"] in APPLICABLE else "not_applicable",
                reason="fake") for e in entries])
        if output_type is TriageGrades:
            return TriageGrades(grades=[TriageGrade(ref=r, relevant=True) for r, _ in BLOCK.findall(content)])
        if output_type is JudgeDecisions:
            blocks = BLOCK.findall(content)
            state["judge_calls"] += 1
            if state["judge_calls"] == 1 and len(blocks) > 1:
                blocks = blocks[:-1]  # the model skips one ref: the graph must ask for it again
            return JudgeDecisions(decisions=[JudgeDecision(
                ref=r, label="keep" if " shall " in f" {t} " else "reject", reason="fake",
                functionality_ids=["rear_position_lamp"]) for r, t in blocks])
        if output_type is DraftRequirements:
            out = []
            for ref, text in BLOCK.findall(content):
                first = text.split("\n")[0]
                if " shall " in f" {first} " and len(first) > 30:
                    out.append(DraftRequirement(ref=ref, text=first[:300], quote=first[:300]))
                    if not state.get("bad_added"):  # once: one draft per failure mode the verifier must catch
                        state["bad_added"] = True
                        out.append(DraftRequirement(ref=ref, text=first[:300], quote=first[:300]))  # duplicate
                        out.append(DraftRequirement(ref=ref, text=first[:300] + " The limit is 987654 mm.", quote=first[:300]))
                        out.append(DraftRequirement(ref=ref, text=first[:300], quote="this sentence is not in the regulation at all"))
            return DraftRequirements(requirements=out)
        if output_type is QueryRewrites:
            return QueryRewrites(rewrites=[])
        raise AssertionError(f"unexpected output type {output_type}")

    return structured


def test_graph_end_to_end_with_fake_llm(monkeypatch, tmp_path):
    if not _index_ready():  # checked when the test runs, not at collection, so the store is not opened needlessly
        pytest.skip("needs the full local index and an unlocked store: uv run python -m pipeline.legal")
    from pipeline import run as run_module
    from pipeline.graph import map as graph

    monkeypatch.setattr(llm, "structured", _fake_llm())
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    graph._FAILED.clear()

    result = asyncio.run(run_module.run_case("cases/dev-rear-lamp"))
    run_dir = tmp_path / "dev-rear-lamp"
    run = next(run_dir.iterdir())

    assert result["validation_problems"] == []
    assert result["requirements"] > 20
    sub = json.loads((run / "submission.json").read_text(encoding="utf-8"))
    cited = {r["source"]["regulation"] for r in sub["requirements"]}
    assert sub["team_id"] == config.TEAM_ID and cited <= APPLICABLE - {"UN R7", "UN R3"}
    route = {r["regulation"]: r for r in json.loads((run / "route.json").read_text(encoding="utf-8"))}
    for old, successor in (("UN R7", "UN R148"), ("UN R3", "UN R150")):  # named in the Introduction of R148 / R150
        assert route[old]["decision"] == "not_applicable" and successor in route[old]["reason"] and route[old]["superseded"]
    for reason in ("duplicate", "number not in evidence", "quote not in cited text"):
        assert result["drops"].get(reason, 0) >= 1, (reason, result["drops"])
    for name in ("components.json", "functionalities.json", "route.json", "decisions.jsonl", "retrieval_grades.jsonl",
                 "trace.jsonl", "submission.json", "score.json"):
        assert (run / name).is_file(), name
    assert result["score"]["regulation_level"]["recall"] == 1.0
    assert not graph._FAILED
