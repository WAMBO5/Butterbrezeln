"""Qdrant collection `provisions`: dense bge-small + sparse BM25, hybrid query with reciprocal rank fusion."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from functools import lru_cache

from qdrant_client import QdrantClient, models

from pipeline import config
from pipeline.catalog.corpus import Version, base_versions, provisions
from pipeline.catalog.parse import Provision

COLLECTION = "provisions"
DENSE_MODEL = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL = "Qdrant/bm25"
EMBED_CHARS = 1500


@dataclass
class Hit:
    provision_id: str
    regulation: str
    version_label: str
    paragraph: str
    section: str
    score: float


@lru_cache(maxsize=1)
def client() -> QdrantClient:
    if config.QDRANT_URL:
        return QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY)
    config.QDRANT_PATH.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(config.QDRANT_PATH))


def close() -> None:
    """Close the local store explicitly so interpreter shutdown does not print a Qdrant __del__ error."""
    info = getattr(client, "cache_info", None)
    if info and info().currsize:
        client().close()
        client.cache_clear()


@lru_cache(maxsize=1)
def _dense():
    import os

    from fastembed import TextEmbedding
    # Half the logical cores: measured 3-5x faster than onnxruntime's default (all threads oversubscribe the hyperthreads).
    threads = int(os.environ.get("EMBED_THREADS") or max(1, (os.cpu_count() or 2) // 2))
    return TextEmbedding(DENSE_MODEL, threads=threads)


@lru_cache(maxsize=1)
def _sparse():
    from fastembed import SparseTextEmbedding
    return SparseTextEmbedding(SPARSE_MODEL)


def point_id(provision_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, provision_id))


def embed_text(p: Provision) -> str:
    return (" > ".join(p.heading_path) + "\n" + p.text)[:EMBED_CHARS]


def ensure_collection() -> None:
    c = client()
    if c.collection_exists(COLLECTION):
        return
    c.create_collection(
        COLLECTION,
        vectors_config={"dense": models.VectorParams(size=384, distance=models.Distance.COSINE)},
        sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
    )
    for field in ("regulation", "role", "version_label", "paragraph", "section", "function_ids"):
        try:
            c.create_payload_index(COLLECTION, field, models.PayloadSchemaType.KEYWORD)
        except Exception:  # local mode ignores payload indexes
            pass


def _version_filter(v: Version) -> models.Filter:
    return models.Filter(must=[models.FieldCondition(key="regulation", match=models.MatchValue(value=v.regulation)),
                               models.FieldCondition(key="version_label", match=models.MatchValue(value=v.version_label))])


def _expected_signature(v: Version) -> set[tuple]:
    return {(p.provision_id, p.paragraph, p.section, p.page)
            for p in provisions(v.regulation, v.version_label) if not p.rationale and p.text}


def _stored_signatures() -> dict[tuple[str, str], set[tuple]]:
    sig: dict[tuple[str, str], set[tuple]] = {}
    offset = None
    while True:
        points, offset = client().scroll(COLLECTION, limit=4096, offset=offset, with_vectors=False,
                                         with_payload=["provision_id", "regulation", "version_label", "paragraph", "section", "page"])
        for pt in points:
            pl = pt.payload
            sig.setdefault((pl["regulation"], pl["version_label"]), set()).add((pl["provision_id"], pl["paragraph"], pl["section"], pl["page"]))
        if offset is None:
            return sig


def indexed_versions() -> set[tuple[str, str]]:
    """Versions whose stored provisions (id, paragraph, section, page) equal what the parser produces now. A partial index,
    an index built by an older parser, or leftover points all fail this, not only a different point count."""
    if not client().collection_exists(COLLECTION):
        return set()
    stored = _stored_signatures()
    return {(v.regulation, v.version_label) for v in base_versions()
            if stored.get((v.regulation, v.version_label)) == _expected_signature(v)}


def missing_versions() -> list[str]:
    done = indexed_versions()
    return [f"{v.regulation} {v.version_label}" for v in base_versions() if (v.regulation, v.version_label) not in done]


def stored_vectors() -> dict[str, tuple[tuple, list[float]]]:
    """provision_id -> (BM25 signature, dense vector) of every stored point, so a re-index can reuse the dense vector of a
    provision whose text has not changed. The BM25 vector is cheap and deterministic: if it is identical, the embedded text
    is, and so is the dense vector."""
    out: dict[str, tuple[tuple, list[float]]] = {}
    if not client().collection_exists(COLLECTION):
        return out
    offset = None
    while True:
        points, offset = client().scroll(COLLECTION, limit=1024, offset=offset, with_vectors=True, with_payload=["provision_id"])
        for pt in points:
            sv = pt.vector["bm25"]
            out[pt.payload["provision_id"]] = (_sparse_signature(sv.indices, sv.values), list(pt.vector["dense"]))
        if offset is None:
            return out


def _sparse_signature(indices, values) -> tuple:
    """Order-independent: Qdrant keeps a sparse vector's indices sorted, fastembed emits them in token order."""
    return tuple(sorted((int(i), round(float(x), 5)) for i, x in zip(indices, values)))


def upsert_version(v: Version, batch: int = 128, reuse: dict | None = None) -> tuple[int, int]:
    """Replace a version's points. Returns (points written, dense vectors actually computed).

    Everything is computed first and the old points are deleted only then, so an interrupted run leaves the old version
    intact (and a changed one is caught by `indexed_versions`)."""
    ensure_collection()
    provs = [p for p in provisions(v.regulation, v.version_label) if not p.rationale and p.text]
    texts = [embed_text(p) for p in provs]
    sparse = list(_sparse().embed(texts))
    dense: list = [None] * len(provs)
    todo = []
    for i, (p, sp) in enumerate(zip(provs, sparse)):
        old = (reuse or {}).get(p.provision_id)
        if old is not None and old[0] == _sparse_signature(sp.indices, sp.values):
            dense[i] = old[1]
        else:
            todo.append(i)
    for j in range(0, len(todo), batch):
        idx = todo[j:j + batch]
        for i, vec in zip(idx, _dense().embed([texts[i] for i in idx])):
            dense[i] = vec.tolist() if hasattr(vec, "tolist") else list(vec)
    client().delete(COLLECTION, points_selector=models.FilterSelector(filter=_version_filter(v)))
    for i in range(0, len(provs), 256):
        chunk = range(i, min(i + 256, len(provs)))
        client().upsert(COLLECTION, points=[
            models.PointStruct(
                id=point_id(provs[k].provision_id),
                vector={"dense": dense[k], "bm25": models.SparseVector(indices=sparse[k].indices.tolist(), values=sparse[k].values.tolist())},
                payload={"provision_id": provs[k].provision_id, "regulation": provs[k].regulation, "role": provs[k].role,
                         "version_label": provs[k].version_label, "paragraph": provs[k].paragraph, "section": provs[k].section,
                         "page": provs[k].page, "page_span": [provs[k].page, provs[k].page_end],
                         "heading_path": provs[k].heading_path, "function_ids": []},
            ) for k in chunk])
    return len(provs), len(todo)


class _Memory:
    """All stored points in memory: a normalised dense matrix and a BM25 inverted index with Qdrant's IDF formula.
    Local-mode Qdrant evaluates filters point by point in Python (10+ s per query); this answers in milliseconds."""

    def __init__(self) -> None:
        import math

        import numpy as np

        self.payloads: list[dict] = []
        dense: list[list[float]] = []
        postings: dict[int, list[tuple[int, float]]] = {}
        offset = None
        while True:
            points, offset = client().scroll(COLLECTION, limit=2048, offset=offset, with_payload=True, with_vectors=True)
            for pt in points:
                row = len(self.payloads)
                self.payloads.append(pt.payload)
                dense.append(pt.vector["dense"])
                sv = pt.vector["bm25"]
                for i, val in zip(sv.indices, sv.values):
                    postings.setdefault(i, []).append((row, val))
            if offset is None:
                break
        m = np.asarray(dense, dtype=np.float32)
        self.dense = m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-9)
        n = len(self.payloads)
        self.postings = {t: (np.array([r for r, _ in rows]), np.array([v for _, v in rows], dtype=np.float32),
                             math.log(1 + (n - len(rows) + 0.5) / (len(rows) + 0.5))) for t, rows in postings.items()}
        self.regulation = np.array([p["regulation"] for p in self.payloads])
        self.role = np.array([p["role"] for p in self.payloads])

    def query(self, query: str, k: int, regulations: list[str] | None, role: str) -> list[Hit]:
        import numpy as np

        mask = self.role == role
        if regulations:
            mask &= np.isin(self.regulation, regulations)
        allowed = np.flatnonzero(mask)
        if not len(allowed):
            return []
        qd = np.asarray(_query_dense(query), dtype=np.float32)
        qd /= max(float(np.linalg.norm(qd)), 1e-9)
        dense_scores = self.dense[allowed] @ qd
        sparse = np.zeros(len(self.payloads), dtype=np.float32)
        for t, w in _query_sparse(query):
            if t in self.postings:
                rows, vals, idf = self.postings[t]
                sparse[rows] += w * vals * idf
        sparse_scores = sparse[allowed]
        depth = min(len(allowed), k * 2)
        fused: dict[int, float] = {}
        for scores in (dense_scores, sparse_scores):
            order = np.argsort(-scores)[:depth]
            for rank, j in enumerate(order):
                if scores[j] <= 0 and scores is sparse_scores:
                    break
                fused[int(allowed[j])] = fused.get(int(allowed[j]), 0.0) + 1.0 / (60 + rank + 1)
        best = sorted(fused.items(), key=lambda kv: -kv[1])[:k]
        return [Hit(self.payloads[r]["provision_id"], self.payloads[r]["regulation"], self.payloads[r]["version_label"],
                    self.payloads[r]["paragraph"], self.payloads[r]["section"], score) for r, score in best]


@lru_cache(maxsize=1)
def _memory() -> _Memory:
    return _Memory()


@lru_cache(maxsize=4096)
def _query_dense(query: str) -> tuple[float, ...]:
    return tuple(next(iter(_dense().query_embed(query))).tolist())


@lru_cache(maxsize=4096)
def _query_sparse(query: str) -> tuple[tuple[int, float], ...]:
    sp = next(iter(_sparse().query_embed(query)))
    return tuple(zip(sp.indices.tolist(), sp.values.tolist()))


def search(query: str, k: int = 40, regulations: list[str] | None = None, role: str = "base") -> list[Hit]:
    """Hybrid search (dense bge-small + BM25 with IDF, reciprocal rank fusion) over the stored provisions."""
    return _memory().query(query, k, regulations, role)
