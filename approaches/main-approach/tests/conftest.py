import shutil
from pathlib import Path

import pytest

from app.models import RegulationVersion

CHALLENGE = Path("industrial-ai-hackathon")
INDEX = CHALLENGE / "regulations" / "index.json"
TEXT_ROOT = CHALLENGE / "regulations" / "text"
GOLD = CHALLENGE / "cases" / "dev-rear-lamp" / "expected.json"
MINI = Path("tests/fixtures/mini_regulation.txt")


def _version(regulation: str, label: str, title: str = "t") -> RegulationVersion:
    return RegulationVersion(regulation=regulation, title=title, role="base", version_label=label,
                             status="enforced", file_name=f"{regulation.replace(' ', '_')}_base.pdf", sha256="x")


@pytest.fixture
def mini_versions() -> list[RegulationVersion]:
    return [_version("UN R999", "1.0.0", "Rear lamps"), _version("UN R998", "0.1.0", "Missing text")]


@pytest.fixture
def mini_root(tmp_path: Path) -> Path:
    root = tmp_path / "text"
    target = root / "UN_R999" / "base" / "UN_R999_base.txt"
    target.parent.mkdir(parents=True)
    shutil.copy(MINI, target)
    return root


@pytest.fixture
def mini_store(tmp_path, mini_versions, mini_root):
    from app.corpus.store import CorpusStore

    store = CorpusStore(tmp_path / "mini.sqlite")
    store.build(mini_versions, mini_root)
    return store


@pytest.fixture(scope="session")
def real_store(tmp_path_factory):
    if not INDEX.exists():
        pytest.skip("challenge data missing")
    from app.corpus.index import load_index
    from app.corpus.store import CorpusStore

    store = CorpusStore(tmp_path_factory.mktemp("corpus") / "catalog.sqlite")
    store.build(load_index(INDEX), TEXT_ROOT)
    return store


@pytest.fixture
def tmp_settings(tmp_path):
    """Fake-model settings with a tmp data dir and a price for the fake model."""
    from app.config.settings import load_settings

    prices = tmp_path / "prices.yaml"
    prices.write_text("fake: {input: 1, output: 1, cache_read: null}\n")
    return load_settings({"CERTIVITY_DATA_DIR": str(tmp_path / "data"), "CERTIVITY_PRICES": str(prices),
                          "CERTIVITY_TEAM_ID": "team-test"}, fake_llm=True)


@pytest.fixture
def fake_responders(tmp_settings):
    from app.corpus.store import CorpusStore
    from app.corpus.index import load_index
    from app.testing.fake_llm import register_responders
    from app.testing.responders import build_fake_responders

    store = CorpusStore(tmp_settings.catalog_path)
    store.build(load_index(tmp_settings.index_path), tmp_settings.text_root)
    register_responders(build_fake_responders(tmp_settings, store))
    return store
