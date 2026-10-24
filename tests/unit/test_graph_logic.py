"""Graph logic that needs no API: fail-closed judging, reference resolution, number rules."""
import asyncio

from pipeline import llm
from pipeline.catalog.corpus import provisions
from pipeline.catalog.normalise import is_subsequence, number_sequence, numbers
from pipeline.graph import map as graph


def _r48(paragraph):
    return next(p for p in provisions("UN R48", "9.3.0") if p.paragraph == paragraph)


def test_failed_judge_batches_are_never_exported(monkeypatch, tmp_path):
    async def boom(*args, **kwargs):
        raise llm.LLMError("simulated failure")

    monkeypatch.setattr(llm, "structured", boom)
    pids = [_r48("6.10.4.1").provision_id, _r48("6.10.4.2").provision_id, _r48("6.10.4.3").provision_id]
    state = {"candidates": pids, "decisions": {}, "round": 1, "run_dir": str(tmp_path),
             "profile": {}, "functionalities": []}
    out = asyncio.run(graph.judge_node(state))
    assert {d["label"] for d in out["decisions"].values()} == {"unjudged"}
    assert set(out["decisions"]) == set(pids)  # nothing silently lost
    assert graph._FAILED["judge"] >= 1


def test_reference_to_another_regulation_is_not_resolved():
    p = _r48("6.5.8")
    by_label = {q.paragraph: q for q in provisions("UN R48", "9.3.0")}
    assert graph.resolve_reference(p, "6.2.2", " of UN Regulation No.", by_label) is None
    assert graph.resolve_reference(p, "6.2.2", " of this Regulation", by_label) is by_label["6.2.2"]
    assert graph.resolve_reference(p, "6.2.2", " above", by_label) is by_label["6.2.2"]
    # "paragraph 1.1. of Annex 3" resolves to the annex provision, never to a main-body paragraph 1.1
    r148 = {q.paragraph: q for q in provisions("UN R148", "1.6.0")}
    cite = next(q for q in provisions("UN R148", "1.6.0") if q.paragraph == "3.3.2.5.3")
    assert graph.resolve_reference(cite, "1.1", " of Annex 3", r148).paragraph == "Annex 3 1.1"
    assert graph.resolve_reference(cite, "1.1", " of Annex 99", r148) is None


def test_number_rules():
    assert numbers("3.00 mm") == numbers("3 mm") and numbers("0,50") == numbers("0.5")
    assert "375" not in numbers("375 mm") & numbers("not less than 350 mm", evidence=True)
    # a table row "1 102 min" must still support "1" and "102"
    assert {"1", "102"} <= numbers("1 102 min", evidence=True)
    assert numbers("1 102 min") == {"1102"} and numbers("1 102 min", join=False) == {"1", "102"}
    assert "60" in numbers("6.0\u2219101 cd", evidence=True)  # exponent flattened by PDF extraction


def test_quote_numbers_must_keep_their_order():
    assert is_subsequence(number_sequence("at least 30 and 5 degrees"), number_sequence("30 degrees, 15 and 5 degrees"))
    assert not is_subsequence(number_sequence("at least 5 and 30 degrees"), number_sequence("30 degrees and 5 degrees"))


def test_writer_splits_a_failing_batch_and_reports_what_it_loses(monkeypatch, tmp_path):
    import re

    from pipeline.models import DraftRequirement, DraftRequirements

    pids = [p.provision_id for p in provisions("UN R48", "9.3.0") if p.paragraph.startswith("6.10.4")][:4]
    always_fails = pids[1]

    async def structured(output_type, system, content, **kwargs):
        refs = re.findall(r'<provision ref="(P\d+)"', content)
        if len(refs) > 1:
            raise llm.TruncatedError("simulated overflow")  # a long batch overflows the reply
        if f'paragraph="{always_fails.split("|")[2]}"' in content:
            raise llm.LLMError("simulated refusal")  # one provision can never be written
        return DraftRequirements(requirements=[DraftRequirement(ref=refs[0], text="The lamp shall work.", quote="shall work")])

    monkeypatch.setattr(llm, "structured", structured)
    graph._FAILED.clear()
    state = {"decisions": {pid: {"label": "keep"} for pid in pids}, "xrefs": {}, "run_dir": str(tmp_path),
             "profile": {}, "functionalities": []}
    out = asyncio.run(graph.writer_node(state))
    assert len(out["drafts"]) == len(pids) - 1  # every provision but the one that always fails was written
    trace = (tmp_path / "trace.jsonl").read_text(encoding="utf-8")
    assert "writer_lost" in trace and always_fails in trace and graph._FAILED["writer"] >= 2


def test_triage_drop_returns_when_a_rewritten_query_hits_it_directly(monkeypatch, tmp_path):
    import re

    from pipeline.models import TriageGrade, TriageGrades

    pids = [p.provision_id for p in provisions("UN R48", "9.3.0") if p.paragraph.startswith("6.10.4")][:3]
    forced = pids[0]

    async def structured(output_type, system, content, **kwargs):
        refs = re.findall(r'<provision ref="(P\d+)"', content)
        return TriageGrades(grades=[TriageGrade(ref=r, relevant=False) for r in refs])

    monkeypatch.setattr(llm, "structured", structured)
    state = {"candidates": pids, "forced": [forced], "hits": {}, "seen": [], "triage_dropped": [forced, "X|1|old"],
             "round": 2, "run_dir": str(tmp_path), "profile": {}, "functionalities": []}
    out = asyncio.run(graph.triage_node(state))
    assert out["candidates"] == [forced]                          # skipped triage, goes straight to the judge
    assert set(out["triage_dropped"]) == {"X|1|old", *pids[1:]}   # the others stay dropped; the forced one is no longer


def test_an_api_outage_is_not_answered_with_more_requests(monkeypatch, tmp_path):
    """Splitting a batch is for content failures; during an outage it would only multiply the requests."""
    calls = []

    async def structured(output_type, system, content, **kwargs):
        calls.append(1)
        raise llm.APIUnavailableError("simulated outage")

    monkeypatch.setattr(llm, "structured", structured)
    pids = [p.provision_id for p in provisions("UN R48", "9.3.0") if p.paragraph.startswith("6.10.4")][:4]
    state = {"candidates": pids, "decisions": {}, "round": 1, "run_dir": str(tmp_path), "profile": {}, "functionalities": []}
    out = asyncio.run(graph.judge_node(state))
    assert {d["label"] for d in out["decisions"].values()} == {"unjudged"} and set(out["decisions"]) == set(pids)
    assert len(calls) == 1  # one batch, one request: no split, no retry storm
