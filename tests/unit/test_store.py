"""Hybrid store on a throwaway in-memory Qdrant: upsert, completeness check, vector reuse, filtered hybrid search."""
import pytest
from qdrant_client import QdrantClient

from pipeline.catalog.corpus import base_versions
from pipeline.rag import store


@pytest.fixture()
def memory_store(monkeypatch):
    c = QdrantClient(":memory:")
    monkeypatch.setattr(store, "client", lambda: c)
    store._memory.cache_clear()
    yield c
    store._memory.cache_clear()


@pytest.fixture(scope="module")
def r42_vectors():
    """UN R42 embedded once for the whole module (the slow part); later tests reuse the vectors."""
    mp = pytest.MonkeyPatch()
    c = QdrantClient(":memory:")
    mp.setattr(store, "client", lambda: c)
    v = next(x for x in base_versions() if x.regulation == "UN R42")
    store.upsert_version(v)
    vectors = store.stored_vectors()
    mp.undo()
    return v, vectors


def test_upsert_search_and_completeness(memory_store, r42_vectors):
    v, vectors = r42_vectors
    n, embedded = store.upsert_version(v, reuse=vectors)
    assert n > 50 and embedded == 0  # every vector reused: nothing was embedded
    assert (v.regulation, v.version_label) in store.indexed_versions()

    hits = store.search("front and rear protective devices pendulum impact test", k=10)
    assert hits and all(h.regulation == "UN R42" for h in hits)
    assert hits == sorted(hits, key=lambda h: -h.score)
    assert store.search("anything", k=5, regulations=["UN R148"]) == []

    store.upsert_version(v, reuse=vectors)  # idempotent: a re-run replaces, never duplicates
    assert memory_store.count(store.COLLECTION, exact=True).count == n


def test_a_stale_payload_makes_a_version_count_as_not_indexed(memory_store, r42_vectors):
    """Same point count, but a section the current parser would not produce: the old count-only check missed this."""
    v, vectors = r42_vectors
    store.upsert_version(v, reuse=vectors)
    assert (v.regulation, v.version_label) in store.indexed_versions()
    some_point = memory_store.scroll(store.COLLECTION, limit=1)[0][0].id
    memory_store.set_payload(store.COLLECTION, payload={"section": "stale"}, points=[some_point])
    assert (v.regulation, v.version_label) not in store.indexed_versions()
    store.upsert_version(v, reuse=vectors)  # a re-index replaces the version and the check passes again
    assert (v.regulation, v.version_label) in store.indexed_versions()


def test_only_provisions_whose_text_changed_are_embedded_again(memory_store, r42_vectors, monkeypatch):
    v, vectors = r42_vectors
    changed = next(iter(vectors))
    real = store.embed_text
    monkeypatch.setattr(store, "embed_text", lambda p: real(p) + " changed wording" if p.provision_id == changed else real(p))
    n, embedded = store.upsert_version(v, reuse=vectors)
    assert embedded == 1 and n > 50  # one provision re-embedded, every other vector reused
    stored = store.stored_vectors()
    assert stored[changed][1] != vectors[changed][1]          # the changed provision got a new dense vector
    other = next(pid for pid in vectors if pid != changed)
    assert stored[other][1] == vectors[other][1]              # an unchanged one kept exactly its old vector
