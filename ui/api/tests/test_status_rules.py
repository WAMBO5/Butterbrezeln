from api.assess import _profile_fits, compute_status
from api.spec import parse_spec


def test_not_covered_is_grey_even_with_fixes():
    assert compute_status("not_covered", ["design"]) == "grey"


def test_no_fixes_is_green():
    assert compute_status("unece_1958", []) == "green"
    assert compute_status("national", []) == "green"


def test_doc_or_certification_fixes_are_yellow():
    assert compute_status("national", ["documentation"]) == "yellow"
    assert compute_status("unece_1958", ["testing", "documentation"]) == "yellow"


def test_any_design_fix_is_red():
    assert compute_status("national", ["documentation", "design"]) == "red"


def test_profile_only_fits_the_product_it_was_researched_for():
    covers = {"products": ["rear lamp"], "regulations": ["UN R148", "UN R150"]}
    lamp, bumper = parse_spec("spec.md", "# spec: Rear Lamp\n"), parse_spec("spec.md", "# spec: Bumper\n")
    assert _profile_fits(covers, lamp, ["UN R10", "UN R148"])
    assert not _profile_fits(covers, bumper, ["UN R148"])  # side lamps cite the same regulation
    assert not _profile_fits(covers, lamp, ["UN R10"])
    assert _profile_fits({}, bumper, [])
