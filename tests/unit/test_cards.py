from app.agents.regulation_profiler import build_profiler_prompt
from app.corpus.cards import CardPayload, CardStore
from app.gates.card_gate import card_claims, card_gate
from app.models import DeviceSections, RegulationCard


def card(**kw):
    data = dict(regulation="UN R999", version_label="1.0.0", title="Rear lamps", regulation_type="device",
                devices_in_scope=["rear lamp", "stop lamp"], vehicle_categories=["M", "N"],
                functions_covered=["rear position signalling"], triggers=["contains LEDs"], consolidates=["UN R7"],
                device_sections=[DeviceSections(device="rear lamp", section_ids=["UN R999@1.0.0#5"])],
                evidence=["UN R999@1.0.0#1", "UN R999@1.0.0#Introduction"])
    data.update(kw)
    return RegulationCard(**data)


def payload(store):
    return CardPayload(store=store, version=store.base_version("UN R999"))


def test_prompt_has_own_scope_only(mini_store):
    prompt = build_profiler_prompt(payload(mini_store), [])
    assert "This Regulation applies to rear lamps" in prompt and "UN R999@1.0.0#5.1" in prompt
    assert "version 1.0.0 | page" not in prompt and "UN R998" not in prompt


def test_gate_accepts_valid_card(mini_store):
    assert card_gate(payload(mini_store), card()) == []


def test_gate_flags_unknown_ids_and_mismatches(mini_store):
    issues = card_gate(payload(mini_store), card(evidence=["UN R999@1.0.0#42"], version_label="2.0.0",
                                                 devices_in_scope=[], title=""))
    types = {i.type for i in issues}
    assert {"unknown_id", "mismatch", "missing_field"} <= types


def test_claims_one_per_entry(mini_store):
    claims = card_claims(payload(mini_store), card())
    assert len(claims) == 2 + 1 + 1 and all(c.cited_text for c in claims)
    assert all(len(c.cited_text) <= 4000 for c in claims)


def test_card_store_round_trip(tmp_path):
    store = CardStore(tmp_path)
    store.save(card())
    assert store.load("UN R999", "1.0.0") == card() and store.load("UN R1", "1") is None
