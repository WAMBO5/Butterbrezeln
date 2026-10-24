"""Functionality taxonomy and demo markets."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_DIR = Path(__file__).parent


@lru_cache(maxsize=1)
def functions() -> dict[str, str]:
    data = yaml.safe_load((_DIR / "functions.yaml").read_text(encoding="utf-8"))
    return {k: v for group in data.values() for k, v in group.items()}


@lru_cache(maxsize=1)
def markets() -> dict:
    return yaml.safe_load((_DIR / "markets.yaml").read_text(encoding="utf-8"))
