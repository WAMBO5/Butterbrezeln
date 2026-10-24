"""Regulation index, page-marked text (extracted with PyMuPDF when missing), and parsed provisions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pipeline import config
from pipeline.catalog.parse import Provision, parse_text


@dataclass(frozen=True)
class Version:
    regulation: str
    title: str
    role: str
    version_label: str
    folder: str  # "UN_R148"

    @property
    def text_path(self) -> Path:
        return config.TEXT_DIR / self.folder / self.role / f"{self.folder}_{self.role}.txt"

    @property
    def pdf_path(self) -> Path:
        return config.PDF_DIR / self.folder / self.role / f"{self.folder}_{self.role}.pdf"


@lru_cache(maxsize=1)
def versions() -> tuple[Version, ...]:
    out = []
    for reg in json.loads(config.INDEX_JSON.read_text(encoding="utf-8")):
        for v in reg["versions"]:
            folder = Path(v["files"][0]["name"]).stem.rsplit("_", 1)[0]
            out.append(Version(reg["regulation"], reg.get("title", ""), v["role"], v["version_label"], folder))
    return tuple(out)


def base_versions() -> list[Version]:
    return [v for v in versions() if v.role == "base"]


def find_version(regulation: str, version_label: str) -> Version | None:
    return next((v for v in versions() if v.regulation == regulation and v.version_label == version_label), None)


def extract_pdf(pdf: Path, regulation: str, version_label: str) -> str:
    """Write the organizer's page-marker format: '=== PDF page N ===' then the 'version | page X of Y' header."""
    import pymupdf

    parts = []
    with pymupdf.open(pdf) as doc:
        for i, page in enumerate(doc, start=1):
            body = page.get_text("text")
            if not body.strip():
                try:
                    body = page.get_textpage_ocr().extractText()
                except Exception:  # OCR needs Tesseract; leave the page empty rather than fail the corpus
                    body = ""
            parts.append(f"=== PDF page {i} ===\n{regulation}, version {version_label} | page {i} of {doc.page_count}\n{body.strip()}\n")
    return "\n".join(parts)


def page_text(v: Version) -> str:
    if not v.text_path.is_file():
        if not v.pdf_path.is_file():
            raise FileNotFoundError(f"{v.regulation} {v.version_label}: neither {v.text_path} nor {v.pdf_path} exists")
        v.text_path.parent.mkdir(parents=True, exist_ok=True)
        v.text_path.write_text(extract_pdf(v.pdf_path, v.regulation, v.version_label), encoding="utf-8")
    return v.text_path.read_text(encoding="utf-8")


def page_count(v: Version) -> int:
    marks = re.findall(r"^=== PDF page (\d+) ===$", page_text(v), re.M)
    return max(map(int, marks)) if marks else 0


def read_page(v: Version, page: int) -> str:
    text = page_text(v)
    m = re.search(rf"^=== PDF page {page} ===$(.*?)(?=^=== PDF page \d+ ===$|\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


@lru_cache(maxsize=128)
def provisions(regulation: str, version_label: str) -> tuple[Provision, ...]:
    v = find_version(regulation, version_label)
    if v is None:
        raise KeyError(f"{regulation} {version_label} is not in index.json")
    return tuple(parse_text(page_text(v), v.regulation, v.role, v.version_label))
