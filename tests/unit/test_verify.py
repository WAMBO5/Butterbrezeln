"""Verifier fails closed; export passes the organizer's validate.py."""
import json

from pipeline.catalog.corpus import provisions
from pipeline.verify.checks import submission, validate, verify


def _prov(reg, ver, para):
    return next(p for p in provisions(reg, ver) if p.paragraph == para)


def test_verifier_keeps_supported_row_and_finds_page():
    p = _prov("UN R48", "9.3.0", "6.10.4.2")
    d = {"provision_id": p.provision_id, "text": "The rear position lamps shall be not less than 350 mm nor more than 1,500 mm above the ground.",
         "quote": "not less than 350 mm nor more than 1,500 mm"}
    rows, drops, _ = verify([d], {p.provision_id: p}, {})
    assert len(rows) == 1 and rows[0].page == 50 and rows[0].paragraph == "6.10.4.2"


def test_verifier_drops_number_not_in_evidence():
    p = _prov("UN R48", "9.3.0", "6.10.4.2")
    d = {"provision_id": p.provision_id, "text": "The lamp shall be at least 375 mm above the ground.", "quote": "not less than 350 mm"}
    rows, drops, _ = verify([d], {p.provision_id: p}, {})
    assert not rows and drops["number not in evidence"] == 1


def test_verifier_drops_latest_version_and_bad_quote():
    from pipeline.catalog.corpus import versions

    latest = next(v for v in versions() if v.regulation == "UN R48" and v.role == "latest")
    lp = _prov("UN R48", latest.version_label, "6.10.4.2")
    good_quote = {"provision_id": lp.provision_id, "text": "The rear position lamps shall be not less than 350 mm above the ground.",
                  "quote": "not less than 350 mm"}
    rows, drops, _ = verify([good_quote], {lp.provision_id: lp}, {})
    assert not rows and drops["not a base version in index.json"] == 1

    p = _prov("UN R48", "9.3.0", "6.10.4.2")
    bad = {"provision_id": p.provision_id, "text": "The lamp shall glow.", "quote": "this sentence is not in the regulation at all"}
    rows, drops, _ = verify([bad], {p.provision_id: p}, {})
    assert not rows and drops["quote not in cited text"] == 1


def test_export_passes_validate(tmp_path):
    p = _prov("UN R48", "9.3.0", "6.10.4.2")
    d = {"provision_id": p.provision_id, "text": "The rear position lamps shall be not less than 350 mm above the ground.",
         "quote": "not less than 350 mm"}
    rows, _, _ = verify([d], {p.provision_id: p}, {})
    path = tmp_path / "s.json"
    path.write_text(json.dumps(submission(rows, "dev-rear-lamp", "team-00")), encoding="utf-8")
    assert validate(path) == []


# --- verifier paths -------------------------------------------------------------------------------------------

def _one(p, text, quote):
    rows, drops, _ = verify([{"provision_id": p.provision_id, "text": text, "quote": quote}], {p.provision_id: p}, {})
    return rows, drops


def _height():
    return _prov("UN R48", "9.3.0", "6.10.4.2")


def test_ellipsis_quote_is_matched_fragment_by_fragment_in_order():
    p = _height()
    text = "The rear position lamps shall be not less than 350 mm above the ground, 2,100 mm if the optional lamps are not installed."
    rows, _ = _one(p, text, "not less than 350 mm nor more than ... if the optional lamps are not installed")
    assert len(rows) == 1
    rows, drops = _one(p, text, "if the optional lamps are not installed ... not less than 350 mm nor more than")  # wrong order
    assert not rows and drops["quote not in cited text"] == 1


def test_fuzzy_quote_tolerates_a_typo_but_never_a_changed_number():
    p = _height()
    text = "The rear position lamps shall be not less than 350 mm and not more than 1,500 mm above the ground."
    rows, _ = _one(p, text, "not less than 350 mm nor more tan 1,500 mm")
    assert len(rows) == 1 and rows[0].quote_match == "fuzzy"
    rows, drops = _one(p, text, "not less than 360 mm nor more than 1,500 mm")
    assert not rows and drops["quote not in cited text"] == 1


def test_generic_short_quote_and_invented_obligation_are_dropped():
    p = _height()
    rows, drops = _one(p, "The rear position lamps shall be mounted.", "shall be")
    assert not rows and drops["quote too short"] == 1
    rows, drops = _one(p, "The lamp shall flash twice and emit blue light continuously.", "not less than 350 mm nor more than 1,500 mm")
    assert not rows and drops["text not supported by the cited text"] == 1


def test_identifiers_and_powers_of_ten_are_not_mistaken_for_invented_numbers():
    p = _height()
    quote = "not less than 350 mm nor more than 1,500 mm"
    for text in ("For M1 vehicles the rear position lamps shall be not less than 350 mm above the ground.",
                 "Under UN R48 the rear position lamps shall be not more than 1.5 x 10^3 mm above the ground.",
                 "The rear position lamps shall be not more than 1.5 \u00d7 10\u00b3 mm above the ground."):
        rows, drops = _one(p, text, quote)
        assert len(rows) == 1, (text, dict(drops))


def test_multi_page_provision_is_cited_at_its_first_page_like_the_gold_file():
    p = next(q for q in provisions("UN R10", "7.2.0") if q.paragraph == "6.7.1")
    assert p.page_end > p.page
    last = next(line for line in reversed(p.lines) if len(line) > 30)
    rows, _ = _one(p, last, last)
    assert len(rows) == 1 and rows[0].page == p.page


def test_duplicate_text_under_one_label_is_exported_once():
    p = _height()
    d = {"provision_id": p.provision_id, "text": "The rear position lamps shall be not less than 350 mm above the ground.",
         "quote": "not less than 350 mm nor more than 1,500 mm"}
    rows, drops, _ = verify([d, dict(d)], {p.provision_id: p}, {})
    assert len(rows) == 1 and drops["duplicate"] == 1
