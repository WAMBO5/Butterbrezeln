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


def test_prompts_name_no_regulation_paragraph_or_count_target():
    """Agent instructions stay general: no regulation numbers, paragraph numbers or target counts that
    would tune them to the worked example."""
    import re

    pattern = re.compile(r"\bUN R\s?\d|\bR\s?\d{1,3}\b|Regulation No\.? ?\d|paragraph \d|§\s?\d|\b\d{2,} requirements")
    offenders = {m.__name__: pattern.findall(m.INSTRUCTION) for m in iter_agent_modules() if pattern.search(m.INSTRUCTION)}
    assert offenders == {}
