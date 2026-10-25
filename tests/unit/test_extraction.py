import json

import pytest

from app.agents.obligation_extractor import build_extraction_prompt
from app.agents.prompting import extract_payload
from app.corpus import obligations as ob
from app.corpus.obligations import ObligationCache
from app.gates.extraction_gate import extraction_gate
from app.matching.extraction import ExtractionBatch, make_extraction_batches
from app.models import ExtractedObligation, ExtractionOutput, Provision, ProvisionObligations


def prov(pid="UN R1@1#5.1", text="The ﬁeld shall be measured. The lamp shall be red.", kind="requirement"):
    return Provision(provision_id=pid, regulation="UN R1", version_label="1", role="base", paragraph=pid.split("#")[1],
                     heading_path=[], page_start=1, page_end=1, text=text, kind=kind, refs=[])


def obligation(quote="The field shall be measured", text="The field shall be measured."):
    return ExtractedObligation(subject="field", condition=None, constraint="measured", quantities=[], text=text,
                               quote=quote, kind="test", role="outcome_condition")


def out(*items):
    return ExtractionOutput(items=list(items))


def item(pid="UN R1@1#5.1", obs=None, reason=None):
    return ProvisionObligations(provision_id=pid, obligations=[obligation()] if obs is None else obs,
                                no_obligation_reason=reason)


BATCH = ExtractionBatch(section_id="UN R1@1#5", provisions=[prov()], definitions=[])


def test_gate_passes_ligature_quote():
    assert extraction_gate(BATCH, out(item())) == []


def test_gate_quote_not_in_source():
    issues = extraction_gate(BATCH, out(item(obs=[obligation(quote="The lamp shall be blue")])))
    assert [i.type for i in issues] == ["quote_not_found"]


def test_gate_merged_obligation():
    merged = obligation(text="It shall be red, it shall be bright and it shall be on.")
    assert [i.type for i in extraction_gate(BATCH, out(item(obs=[merged])))] == ["merged"]


def test_gate_missing_and_unknown_items():
    types = {i.type for i in extraction_gate(BATCH, out(item(pid="UN R1@1#9")))}
    assert types == {"unknown_id", "missing_item"}


def test_gate_empty_item():
    assert [i.type for i in extraction_gate(BATCH, out(item(obs=[])))] == ["empty_item"]


def test_cache_round_trip_and_invalidation(tmp_path, monkeypatch):
    cache = ObligationCache(tmp_path / "o.sqlite")
    p = prov()
    assert cache.get(p) is None
    stored = cache.put(p, item())
    assert [o.obligation_id for o in stored] == ["UN R1@1#5.1/1"] and cache.get(p) == stored
    assert cache.unverified(["UN R1@1#5.1/1"]) == ["UN R1@1#5.1/1"]
    cache.mark_verified(["UN R1@1#5.1/1"])
    assert cache.unverified(["UN R1@1#5.1/1"]) == [] and cache.get(p)[0].verified
    assert cache.get(prov(text="Changed text shall apply.")) is None
    monkeypatch.setattr(ob, "EXTRACTOR_VERSION", ob.EXTRACTOR_VERSION + "-next")
    assert cache.get(p) is None


def test_cache_remembers_no_obligation(tmp_path):
    cache = ObligationCache(tmp_path / "o.sqlite")
    cache.put(prov(), item(obs=[], reason="heading only"))
    assert cache.get(prov()) == []


def test_batches_limit_and_kinds(real_store):
    provisions = real_store.provisions("UN R148", "1.6.0")
    batches = make_extraction_batches(provisions, real_store, 15)
    kinds = {p.kind for b in batches for p in b.provisions}
    assert all(len(b.provisions) <= 15 for b in batches) and "form" not in kinds and "definition" not in kinds
    assert all(len({p.paragraph.split(".")[0].split(" ")[0] for p in b.provisions}) == 1 for b in batches
               if not b.section_id.split("#")[1].startswith("Annex"))


def test_prompt_payload_has_no_product(mini_store):
    batch = make_extraction_batches(mini_store.provisions("UN R999", "1.0.0"), mini_store, 15)[0]
    payload = extract_payload(build_extraction_prompt(batch, []))
    assert "product" not in payload and payload["provision_ids"] == [p.provision_id for p in batch.provisions]


async def test_extract_verified_salvages_good_items_and_reextracts_flagged(tmp_path):
    from app.config.settings import load_settings
    from app.models import Issue, Review
    from app.pipeline.extraction import extract_verified

    settings = load_settings({"CERTIVITY_MAX_RETRIES": "0"}, fake_llm=True)
    p1, p2 = prov("UN R1@1#5.1"), prov("UN R1@1#5.2", text="The lamp shall be red.")
    batch = ExtractionBatch(section_id="UN R1@1#5", provisions=[p1, p2], definitions=[])
    good2 = obligation(quote="The lamp shall be red.", text="The lamp shall be red.")
    calls = []

    async def call(spec, prompt):
        calls.append(spec.name)
        if spec.name == "extraction_verifier":
            return Review(verdict="retry", issues=[Issue(type="missing", target_id="UN R1@1#5.1", reason="r",
                                                         evidence=[], proposed=None)])
        if calls.count("obligation_extractor") == 1:  # p1 has a bad quote, p2 is fine
            return out(item("UN R1@1#5.1", obs=[obligation(quote="not in source")]), item("UN R1@1#5.2", obs=[good2]))
        return out(item("UN R1@1#5.1"))

    cache = ObligationCache(tmp_path / "o.sqlite")
    first = await extract_verified(batch, cache, settings, call, None, verify=False)
    assert [o.provision_id for o in first] == ["UN R1@1#5.2"] and cache.get(p1) is None
    second = await extract_verified(batch, cache, settings, call, None, verify=True)
    assert {o.provision_id for o in second} == {"UN R1@1#5.1", "UN R1@1#5.2"}
    assert calls == ["obligation_extractor", "obligation_extractor", "extraction_verifier", "obligation_extractor"]
    assert cache.unverified([o.obligation_id for o in second]) == []


async def test_a_batch_without_output_is_retried_in_halves(tmp_path):
    from app.config.settings import load_settings
    from app.llm import AgentOutputError
    from app.pipeline.extraction import extract_verified

    settings = load_settings({"CERTIVITY_MAX_RETRIES": "0"}, fake_llm=True)
    provisions = [prov(f"UN R1@1#5.{n}", text="The lamp shall be red.") for n in (1, 2, 3)]
    batch = ExtractionBatch(section_id="UN R1@1#5", provisions=provisions, definitions=[])
    sizes = []

    async def call(spec, prompt):
        ids = extract_payload(prompt)["provision_ids"]
        sizes.append(len(ids))
        if len(ids) > 1:  # too long for one output
            raise AgentOutputError(spec.name, "output truncated at max_tokens=21000")
        return out(item(ids[0], obs=[obligation(quote="The lamp shall be red.", text="The lamp shall be red.")]))

    cache = ObligationCache(tmp_path / "o.sqlite")
    got = await extract_verified(batch, cache, settings, call, None, verify=False)
    assert {o.provision_id for o in got} == {p.provision_id for p in provisions}
    assert sizes == [3, 2, 1, 1, 1]
