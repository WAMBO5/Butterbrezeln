import json

import pytest

from app.corpus.index import load_index, regulation_dir, text_path
from app.corpus.parser import paragraph_key
from app.corpus.store import CorpusStore
from tests.conftest import GOLD, INDEX, TEXT_ROOT


def test_build_and_queries(tmp_path, mini_versions, mini_root):
    store = CorpusStore(tmp_path / "c.sqlite")
    stats = store.build(mini_versions, mini_root)
    assert stats.parsed == ["UN R999@1.0.0"] and stats.missing == ["UN R998@0.1.0"]
    assert store.build(mini_versions, mini_root).unchanged == ["UN R999@1.0.0"]
    assert {e.paragraph for e in store.toc("UN R999", "1.0.0", 1)} >= {"1", "2", "3", "5", "Annex 3"}
    assert store.search("trade name", 5, "base")[0].paragraph == "3.1"
    under = {p.paragraph for p in store.provisions_under(["UN R999@1.0.0#5"])}
    assert {"5", "5.1", "5.2", "5.3"} <= under and not any(l.startswith("Annex") for l in under)
    assert "UN R999@1.0.0#2.1" in store.get("UN R999@1.0.0#5.1").refs
    assert "version 1.0.0 | page" not in store.page_text("UN R999", "1.0.0", 2)


def test_find_and_versions(mini_store):
    assert mini_store.find("UN R999", "1.0.0", "Annex 3, Part 1, 1.2.").paragraph == "Annex 3 Part 1 1.2"
    assert mini_store.base_version("UN R999").version_label == "1.0.0"
    assert mini_store.get("nope") is None and mini_store.page_text("UN R999", "1.0.0", 99) is None


def test_search_ignores_short_words_and_quotes(mini_store):
    assert mini_store.search('a "of" OR ()', 5, "base") == []


def test_index_helpers():
    assert regulation_dir("UN R148") == "UN_R148" and regulation_dir("UN GTR 9") == "UN_GTR_9"
    assert text_path(TEXT_ROOT, "UN R148", "base") == TEXT_ROOT / "UN_R148/base/UN_R148_base.txt"


@pytest.mark.skipif(not INDEX.exists(), reason="challenge data missing")
def test_load_index():
    versions = load_index(INDEX)
    assert len({v.regulation for v in versions}) == 56
    assert {(v.role, v.version_label) for v in versions if v.regulation == "UN R10"} == {("base", "7.2.0"), ("latest", "7.3.0")}


@pytest.mark.skipif(not GOLD.exists(), reason="challenge data missing")
def test_golden_paragraphs_resolve(real_store):
    gold = json.loads(GOLD.read_text())["requirements"]
    unresolved = []
    for g in gold:
        s = g["source"]
        p = real_store.find(s["regulation"], s["version"], s["paragraph"])
        if not (p and p.page_start - 1 <= s["page"] <= p.page_end + 1):
            unresolved.append((s["regulation"], s["page"], s["paragraph"]))
    rate = 1 - len(unresolved) / len(gold)
    print(f"golden paragraphs resolved: {rate:.1%}; unresolved: {sorted(set(unresolved))}")
    assert rate >= 0.95
