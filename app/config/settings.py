"""Run settings, read once from the environment (and `.env`).

The API key is never stored: only whether it is present. The Anthropic SDK reads it from the
environment itself.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_PRICES = Path(__file__).with_name("prices.yaml")


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _str(env: Mapping[str, str], key: str) -> str | None:
    value = env.get(key)
    return value.strip() or None if value is not None else None


@dataclass(frozen=True)
class Settings:
    model_judgment: str | None
    model_fast: str | None
    model_review: str | None
    api_key_present: bool
    team_id: str
    max_cost_usd: float
    max_retries: int
    concurrency: int
    include_uncertain: bool
    retention_days: int
    data_dir: Path
    challenge_dir: Path
    prices_path: Path
    fake_llm: bool
    cost_mode: str = "full"  # "reduced": match_reviewer only on disputed batches, matcher at low effort

    @property
    def catalog_path(self) -> Path:
        return self.data_dir / "catalog.sqlite"

    @property
    def cards_dir(self) -> Path:
        return self.data_dir / "cards"

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def markets_dir(self) -> Path:
        return self.data_dir / "markets"

    @property
    def obligations_path(self) -> Path:
        return self.data_dir / "obligations.sqlite"

    @property
    def index_path(self) -> Path:
        return self.challenge_dir / "regulations" / "index.json"

    @property
    def text_root(self) -> Path:
        return self.challenge_dir / "regulations" / "text"

    @property
    def cases_dir(self) -> Path:
        return self.challenge_dir / "cases"


def load_settings(env: Mapping[str, str] | None = None, *, fake_llm: bool = False) -> Settings:
    """Settings from `env`, or from `.env` plus `os.environ` when `env` is None."""
    if env is None:
        from dotenv import load_dotenv

        load_dotenv(override=False)
        env = os.environ
    judgment = _str(env, "ANTHROPIC_MODEL")
    return Settings(
        model_judgment=judgment,
        model_fast=_str(env, "ANTHROPIC_MODEL_FAST"),
        model_review=_str(env, "ANTHROPIC_MODEL_REVIEW") or judgment,
        api_key_present=bool(env.get("ANTHROPIC_API_KEY")),
        team_id=_str(env, "CERTIVITY_TEAM_ID") or "certivity-dev",
        max_cost_usd=float(env.get("CERTIVITY_MAX_COST_USD") or 5),
        max_retries=int(env.get("CERTIVITY_MAX_RETRIES") or 2),
        concurrency=int(env.get("CERTIVITY_CONCURRENCY") or 6),
        include_uncertain=_bool(env.get("CERTIVITY_INCLUDE_UNCERTAIN"), True),
        retention_days=int(env.get("CERTIVITY_RETENTION_DAYS") or 183),
        data_dir=Path(env.get("CERTIVITY_DATA_DIR") or "data"),
        challenge_dir=Path(env.get("CERTIVITY_CHALLENGE_DIR") or "industrial-ai-hackathon"),
        prices_path=Path(env.get("CERTIVITY_PRICES") or _DEFAULT_PRICES),
        fake_llm=fake_llm,
        cost_mode=(_str(env, "CERTIVITY_COST_MODE") or "full").lower(),
    )
