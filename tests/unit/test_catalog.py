"""Deterministic catalog code: parser gate, normalisation, supersession, section expansion."""
from pipeline.catalog.cards import cards, supersedes
from pipeline.catalog.corpus import provisions
from pipeline.catalog.gate import check
from pipeline.catalog.normalise import normalise, numbers, paragraph_key


def test_parser_gate_finds_every_gold_paragraph():
    assert check() == []


def test_paragraph_key_matches_score_local():
    assert paragraph_key("Annex 8 2.1") == paragraph_key("annex 8, 2.1.")
    assert paragraph_key("5.4.2.3") != paragraph_key("5.4.23")


def test_normalise_ligatures_and_superscripts():
    assert normalise("Speci\ufb01cations of 10\u00b2") == normalise("Specifications of 102")
    assert numbers("1,200 mm") == numbers("1 200 mm") == numbers("1200 mm") == {"1200"}


def test_supersession_reads_the_introduction():
    c = cards()
    assert set(c["UN R148"].supersedes) >= {"UN R6", "UN R7", "UN R23", "UN R38"}
    assert set(c["UN R150"].supersedes) >= {"UN R3", "UN R104"}
    assert c["UN R48"].supersedes == ()
    assert supersedes("no consolidation sentence here") == ()


def test_annex_part_labels_match_gold_style():
    labels = {p.paragraph for p in provisions("UN R150", "1.2.1")}
    assert {"Annex 6 Part 4 4.1", "Annex 4 Part 1 1.2"} <= labels


def test_section_expansion_pulls_whole_section():
    from pipeline.graph.map import _expand

    r48 = {p.paragraph: p for p in provisions("UN R48", "9.3.0")}
    out = _expand({r48["6.10.4.1"].provision_id})
    paras = {pid.split("|")[2] for pid in out}
    assert {"6.10.4.2", "6.10.5.1", "6.10.8"} <= paras
    assert not any(p.startswith("6.11") for p in paras)


def test_scope_text_says_what_the_regulation_applies_to():
    """Review finding: R6, R7, R19, R23, R38 and R123 got "1. Definitions" as their scope."""
    c = cards()
    for reg in ("UN R6", "UN R7", "UN R19", "UN R23", "UN R38", "UN R123", "UN R148", "UN R150", "UN R42", "UN R127", "UN R171"):
        scope = c[reg].scope
        assert "applies to" in scope.lower() or "apply to" in scope.lower(), (reg, scope[:120])
        assert "definitions" not in scope[:30].lower(), (reg, scope[:60])
    assert "retro-reflect" in c["UN R150"].scope.lower() and "light-signalling" in c["UN R148"].scope.lower()
    assert all(len(x.scope) > 40 for x in c.values())


def test_triage_rescue_is_local_to_the_neighbouring_paragraphs():
    from pipeline.graph.map import _rescue_key

    r48 = {p.paragraph: p for p in provisions("UN R48", "9.3.0")}
    assert _rescue_key(r48["6.10.4.1"]) == _rescue_key(r48["6.10.4.2"])      # same three-level parent
    assert _rescue_key(r48["6.10.4.1"]) != _rescue_key(r48["6.10.5.1"])      # same section 6.10, different parent
    annex = {p.paragraph: p for p in provisions("UN R150", "1.2.1")}
    assert _rescue_key(annex["Annex 6 Part 4 4.1"]) != _rescue_key(annex["Annex 6 Part 4 3"])
