"""Regulation cards on disk: one JSON file per regulation version (git-ignored `data/cards/`)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.corpus.index import regulation_dir
from app.corpus.store import CorpusStore
from app.models import RegulationCard, RegulationVersion


@dataclass
class CardPayload:
    store: CorpusStore
    version: RegulationVersion


class CardStore:
    def __init__(self, directory: Path):
        self.dir = Path(directory)

    def _path(self, regulation: str, version_label: str) -> Path:
        return self.dir / f"{regulation_dir(regulation)}@{version_label}.json"

    def save(self, card: RegulationCard) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self._path(card.regulation, card.version_label)
        path.write_text(card.model_dump_json(indent=1), encoding="utf-8")
        return path

    def load(self, regulation: str, version_label: str) -> RegulationCard | None:
        path = self._path(regulation, version_label)
        if not path.exists():
            return None
        return RegulationCard(**json.loads(path.read_text(encoding="utf-8")))

    def base_cards(self, versions: list[RegulationVersion]) -> list[RegulationCard]:
        cards = [self.load(v.regulation, v.version_label) for v in versions if v.role == "base"]
        return [c for c in cards if c is not None]
