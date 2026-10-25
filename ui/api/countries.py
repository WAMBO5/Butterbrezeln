"""Country data: data/countries.json (UNECE 1958 membership) and data/country_profiles/<ISO3>.json."""

from __future__ import annotations

import json
from typing import Any

from .config import DATA_DIR

EU27 = ["AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC", "HUN", "IRL",
        "ITA", "LVA", "LTU", "LUX", "MLT", "NLD", "POL", "PRT", "ROU", "SVK", "SVN", "ESP", "SWE"]
TOP_MARKETS = ["DEU", "FRA", "USA", "CHN", "JPN", "KOR", "IND", "BRA"]


def countries_data() -> dict[str, Any]:
    # read on every call: the files are small and may be curated while the server runs
    path = DATA_DIR / "countries.json"
    if not path.is_file():
        return {"meta": {}, "countries": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def country(iso3: str) -> dict[str, Any] | None:
    return countries_data().get("countries", {}).get(iso3)


def profile(iso3: str) -> dict[str, Any] | None:
    path = DATA_DIR / "country_profiles" / f"{iso3}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def researched_regulations() -> set[str]:
    """Regulations whose application per country was actually looked up. A cited regulation outside
    this set is 'not checked', not 'not applied'."""
    data = countries_data()
    researched = set(data.get("meta", {}).get("checked_regulations", []))
    for entry in data.get("countries", {}).values():
        if isinstance(entry.get("applied_regulations"), list):
            researched.update(entry["applied_regulations"])
    return researched


def country_name(iso3: str) -> str:
    entry = country(iso3)
    return (entry or {}).get("name") or iso3


def listing() -> dict[str, Any]:
    data = countries_data()
    entries = data.get("countries", {})
    items = [
        {"iso3": iso, "name": e.get("name", iso), "regime": e.get("regime", "not_covered"),
         "has_profile": bool(e.get("profile"))}
        for iso, e in sorted(entries.items(), key=lambda kv: kv[1].get("name", kv[0]))
    ]
    presets = {
        "EU-27": EU27,
        "UNECE 1958": [i["iso3"] for i in items if i["regime"] == "unece_1958"],
        "Top markets": TOP_MARKETS,
    }
    return {"countries": items, "presets": presets, "meta": data.get("meta", {})}
