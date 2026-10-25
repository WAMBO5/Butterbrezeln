"""Text for PDFs that have none yet (a held-out drop): the same page-marked format as the
challenge's own text files, so the parser and citations work unchanged."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.config.settings import Settings
from app.corpus.index import load_index, regulation_dir, text_path


def _pypdf_pages(path: Path) -> list[str]:
    from pypdf import PdfReader

    return [page.extract_text() or "" for page in PdfReader(str(path)).pages]


def extract_pdf_text(pdf_path: Path, header: str, page_texts: Callable[[Path], list[str]] | None = None) -> str:
    """`=== PDF page N ===`, the header line (`{page}` / `{pages}` filled in), then the page text."""
    pages = (page_texts or _pypdf_pages)(Path(pdf_path))
    out = []
    for n, text in enumerate(pages, start=1):
        out.append(f"=== PDF page {n} ===\n{header.format(page=n, pages=len(pages))}\n{text.strip()}\n")
    return "\n".join(out)


def extract_missing_texts(settings: Settings) -> list[str]:
    """Write text files for downloaded PDFs that have none: regulation versions and sub-goal pairs."""
    written: list[str] = []
    pdf_root = settings.challenge_dir / "regulations" / "pdf"
    for v in load_index(settings.index_path):
        target = text_path(settings.text_root, v.regulation, v.role)
        pdf = pdf_root / regulation_dir(v.regulation) / v.role / v.file_name
        if target.exists() or not pdf.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(extract_pdf_text(pdf, f"{v.regulation}, version {v.version_label} | page {{page}} of {{pages}}"),
                          encoding="utf-8")
        written.append(f"{v.regulation}@{v.version_label}")
    for case in sorted((settings.challenge_dir / "subgoal").glob("*")):
        for which in ("old", "new"):
            pdf = case / f"{which}.pdf"
            target = settings.text_root / "subgoal" / case.name / f"{which}.txt"
            if pdf.exists() and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(extract_pdf_text(pdf, f"sub-goal {case.name} {which} | page {{page}} of {{pages}}"),
                                  encoding="utf-8")
                written.append(f"subgoal/{case.name}/{which}")
    return written
