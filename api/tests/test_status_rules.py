from api.assess import compute_status


def test_not_covered_is_grey_even_with_fixes():
    assert compute_status("not_covered", ["design"]) == "grey"


def test_no_fixes_is_green():
    assert compute_status("unece_1958", []) == "green"
    assert compute_status("national", []) == "green"


def test_doc_or_certification_fixes_are_yellow():
    assert compute_status("national", ["doku_kennzeichnung"]) == "yellow"
    assert compute_status("unece_1958", ["pruefung_zertifizierung", "doku_kennzeichnung"]) == "yellow"


def test_any_design_fix_is_red():
    assert compute_status("national", ["doku_kennzeichnung", "design"]) == "red"
