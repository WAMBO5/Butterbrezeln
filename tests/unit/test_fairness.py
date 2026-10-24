import importlib
import json
import pkgutil
from pathlib import Path

import pytest

import app.agents
from app.corpus.parser import normalize
from tests.conftest import GOLD

EXAMPLES = Path("app/agents/examples/extraction_examples.json")


def iter_agent_modules():
    for info in pkgutil.iter_modules(app.agents.__path__):
        module = importlib.import_module(f"app.agents.{info.name}")
        if hasattr(module, "INSTRUCTION"):
            yield module


@pytest.mark.skipif(not GOLD.exists(), reason="challenge data missing")
def test_no_golden_text_in_prompts():
    gold = [normalize(r["text"])[:60] for r in json.load(open(GOLD))["requirements"]]
    corpus = " ".join(normalize(m.INSTRUCTION) for m in iter_agent_modules()) + normalize(EXAMPLES.read_text())
    assert not [g for g in gold if g in corpus]


def test_agent_modules_found():
    assert len(list(iter_agent_modules())) >= 2
