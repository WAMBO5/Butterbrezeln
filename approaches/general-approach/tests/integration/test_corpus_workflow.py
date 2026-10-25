import json
import shutil
from pathlib import Path

import pytest

from app.compliance.ledger import verify_chain
from app.config.settings import load_settings
from app.corpus.cards import CardStore
from app.pipeline.corpus import build_corpus
from app.testing.fake_llm import register_responders
from app.testing.responders import fake_pass_review, fake_profiler

pytestmark = pytest.mark.integration
MINI = Path("tests/fixtures/mini_regulation.txt")


def mini_challenge(root: Path) -> Path:
    index = []
    for reg in ("UN R999", "UN R998"):
        d = reg.replace(" ", "_")
        target = root / "regulations" / "text" / d / "base" / f"{d}_base.txt"
        target.parent.mkdir(parents=True)
        target.write_text(MINI.read_text().replace("UN R999", reg))
        index.append({"regulation": reg, "title": f"{reg} lamps", "versions": [
            {"role": "base", "version_label": "1.0.0", "status": "enforced",
             "files": [{"name": f"{d}_base.pdf", "sha256": "x"}]}]})
    (root / "regulations" / "index.json").write_text(json.dumps(index))
    return root


async def test_build_corpus_writes_cards(tmp_path):
    settings = load_settings({"CERTIVITY_DATA_DIR": str(tmp_path / "data"),
                              "CERTIVITY_CHALLENGE_DIR": str(mini_challenge(tmp_path / "ch"))}, fake_llm=True)
    register_responders({"regulation_profiler": fake_profiler, "grounding_verifier": fake_pass_review})
    report = await build_corpus(settings, cards=True, prefill=False, force=False, extract_missing=False)
    assert sorted(report.cards_written) == ["UN R998@1.0.0", "UN R999@1.0.0"] and report.cards_failed == []
    cards = CardStore(settings.cards_dir)
    assert cards.load("UN R999", "1.0.0").regulation == "UN R999"
    run_dirs = list((settings.data_dir / "corpus_runs").iterdir())
    assert len(run_dirs) == 1 and verify_chain(run_dirs[0]) == []
    again = await build_corpus(settings, cards=True, prefill=False, force=False, extract_missing=False)
    assert again.cards_written == [] and again.stats.unchanged == ["UN R998@1.0.0", "UN R999@1.0.0"]
