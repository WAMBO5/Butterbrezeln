from pathlib import Path

import pytest

from api import countries as country_data
from api.assess import _matching_groups, _profile_fits, assess_country, compute_status
from api.models import Requirement, Source
from api.spec import parse_spec
from api.trace import TraceRecorder


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


# --- country profiles with more than one researched product (CHN, USA: rear lamp and front bumper) ----

CASES = Path(__file__).resolve().parents[3] / "industrial-ai-hackathon" / "cases"


def test_covers_may_list_several_products():
    covers = [{"id": "rear_lamp", "products": ["rear lamp"], "regulations": ["UN R148"]},
              {"id": "front_bumper", "products": ["bumper"], "regulations": ["UN R48"]}]
    lamp, bumper = parse_spec("s", "# spec: Rear Lamp\n"), parse_spec("s", "# spec: Bumper\n")
    assert [g["id"] for g in _matching_groups(covers, lamp, ["UN R148"])] == ["rear_lamp"]
    assert [g["id"] for g in _matching_groups(covers, bumper, ["UN R148", "UN R48"])] == ["front_bumper"]
    assert not _matching_groups(covers, bumper, ["UN R148"])  # R148 alone is the lamp group's regulation
    assert _profile_fits(covers, bumper, ["UN R48"]) and not _profile_fits(covers, bumper, [])


def _verdict(iso3: str, case: str, cited: list[str], tmp_path):
    spec = parse_spec("spec.md", (CASES / case / "spec.md").read_text(encoding="utf-8"))
    reqs = [Requirement(id=f"r{i}", text="x", source=Source(kind="un_regulation", label=r, regulation=r))
            for i, r in enumerate(cited)]
    trace = TraceRecorder("t", tmp_path / "trace.jsonl", lambda e: None)
    return assess_country(iso3, spec, reqs, [], trace, "root")


@pytest.mark.parametrize("iso3", ["CHN", "USA"])
def test_bumper_gets_bumper_items_and_no_lamp_only_ones(iso3, tmp_path):
    verdict = _verdict(iso3, "heldout-front-bumper", ["UN R10", "UN R48", "UN R148"], tmp_path)
    assert verdict.regime == "national"
    ids = {s.deviation_id for s in verdict.suggestions}
    lamp_ids = {d["id"] for d in country_data.profile(iso3)["deviations"] if d.get("applies_to") == ["rear_lamp"]}
    assert ids and not ids & lamp_ids
    assert {s.effort for s in verdict.suggestions} <= {"documentation", "testing"}  # the map names no design gap
    assert all("source not verified" in s.reason for s in verdict.suggestions)  # the map is not reverified
    assert verdict.status == "yellow"


@pytest.mark.parametrize("iso3", ["CHN", "USA"])
def test_rear_lamp_keeps_its_items_and_gets_no_bumper_ones(iso3, tmp_path):
    verdict = _verdict(iso3, "dev-rear-lamp", ["UN R10", "UN R48", "UN R148", "UN R150"], tmp_path)
    ids = {s.deviation_id for s in verdict.suggestions}
    bumper_ids = {d["id"] for d in country_data.profile(iso3)["deviations"] if d.get("applies_to") == ["front_bumper"]}
    assert f"{iso3}-01" in ids and not ids & bumper_ids
    assert verdict.regime == "national"


@pytest.mark.parametrize("iso3", ["CHN", "USA"])
def test_profile_data_is_consistent(iso3):
    profile = country_data.profile(iso3)
    groups = {g["id"] for g in profile["covers"]}
    assert groups == {"rear_lamp", "front_bumper"}
    ids = [d["id"] for d in profile["deviations"]]
    assert len(ids) == len(set(ids))
    for dev in profile["deviations"]:
        assert dev.get("applies_to") and set(dev["applies_to"]) <= groups, dev["id"]
        assert dev["effort"] in ("documentation", "testing", "design")
