"""Market profiles: which corpus regulations a market applies, at which version and status.

The built-in profiles are illustrative samples with made-up names (design spec section 9.3). A
profile may give a `default` rule that applies to every regulation of the index it does not list.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.models import MarketProfile, MarketRule

BUILTIN_DIR = Path(__file__).with_name("profiles")


def _profile(data: dict, regulations: list[str]) -> MarketProfile:
    rules = [MarketRule(**{"source_ref": None, **r}) for r in data.get("rules") or []]
    listed = {r.regulation for r in rules}
    default = data.get("default")
    if default:
        rules += [MarketRule(regulation=reg, status=default["status"], version_role=default["version_role"],
                             source_ref=None) for reg in regulations if reg not in listed]
    return MarketProfile(market_id=data["market_id"], name=data["name"], illustrative=bool(data.get("illustrative")),
                         rules=sorted(rules, key=lambda r: r.regulation), outside_corpus=data.get("outside_corpus") or [])


def load_market_profiles(dirs: list[Path], regulations: list[str]) -> list[MarketProfile]:
    """Every `*.yaml` profile in `dirs` (later directories override earlier ones by market id)."""
    profiles: dict[str, MarketProfile] = {}
    for d in dirs:
        if not Path(d).exists():
            continue
        for path in sorted(Path(d).glob("*.yaml")):
            p = _profile(yaml.safe_load(path.read_text(encoding="utf-8")), regulations)
            profiles[p.market_id] = p
    return [profiles[k] for k in sorted(profiles)]
