import inspect

from app.tools import corpus_tools as ct
from app.tools.limits import ToolCallLimiter


def test_table_of_contents(mini_store):
    ct.bind_store(mini_store)
    out = ct.get_table_of_contents("UN R999", 9)
    assert out["status"] == "ok" and out["version_label"] == "1.0.0"
    assert {"provision_id", "paragraph", "heading", "page", "kind"} <= set(out["entries"][0])
    assert any(e["paragraph"] == "5.1" for e in out["entries"])  # depth clamped to 4, still includes depth 2


def test_unknown_regulation(mini_store):
    ct.bind_store(mini_store)
    assert ct.get_table_of_contents("UN R1", 2) == {"status": "error", "message": "unknown regulation: UN R1"}


def test_search_and_read(mini_store):
    ct.bind_store(mini_store)
    hits = ct.search_corpus("trade name")["hits"]
    assert hits[0]["provision_id"] == "UN R999@1.0.0#3.1" and len(hits[0]["snippet"]) <= 300
    read = ct.read_provision("UN R999@1.0.0#5.1")
    assert read["status"] == "ok" and read["page_start"] == 2 and read["truncated"] is False
    assert ct.read_provision("UN R999@1.0.0#77")["status"] == "error"


def test_tools_have_docstrings_and_hints():
    for fn in (ct.get_table_of_contents, ct.search_corpus, ct.read_provision):
        assert "Args:" in fn.__doc__
        assert all(p.annotation is not inspect.Parameter.empty for p in inspect.signature(fn).parameters.values())


def test_limiter_blocks_after_max():
    limiter = ToolCallLimiter("scope_narrower", 15)
    assert [limiter.check() for _ in range(15)] == [None] * 15
    assert limiter.check() == {"status": "error", "message": "Tool budget exhausted; answer with what you have."}


def test_limiter_wrap_keeps_signature(mini_store):
    ct.bind_store(mini_store)
    wrapped = ToolCallLimiter("x", 1).wrap(ct.read_provision)
    assert inspect.signature(wrapped) == inspect.signature(ct.read_provision) and wrapped.__doc__ == ct.read_provision.__doc__
    assert wrapped("UN R999@1.0.0#5.1")["status"] == "ok" and wrapped("UN R999@1.0.0#5.1")["status"] == "error"
