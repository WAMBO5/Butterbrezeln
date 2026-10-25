"""Load any challenge case folder: `*.md` is the spec, `*.png` / `*.jpg` are drawings."""

from __future__ import annotations

from pathlib import Path

from app.models import CaseInput

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


class CaseError(Exception):
    pass


def load_case(case_dir: Path) -> CaseInput:
    case_dir = Path(case_dir)
    if not case_dir.is_dir():
        raise CaseError(f"case folder not found: {case_dir}")
    specs = sorted(p for p in case_dir.iterdir() if p.suffix.lower() == ".md" and p.is_file())
    images = sorted(p for p in case_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES and p.is_file())
    spec_text = "\n\n".join(p.read_text(encoding="utf-8").strip() for p in specs) or None
    if spec_text is None and not images:
        raise CaseError(f"{case_dir} has neither a spec (*.md) nor a drawing (*.png, *.jpg)")
    return CaseInput(case_id=case_dir.name, spec_text=spec_text, image_paths=images)
