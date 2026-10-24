"""Product pipeline: component agent and functionality agent."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline import llm, prompts
from pipeline.models import FunctionalityList, ProductProfile, QueryRewrites
from pipeline.taxonomy import functions


def load_case(case_dir: Path) -> tuple[str, bytes | None, str]:
    spec = next((p for p in (case_dir / "spec.md", case_dir / "spec.txt") if p.is_file()), None)
    image = next((p for p in sorted(case_dir.glob("exploded_view.*")) if p.suffix.lower() in {".png", ".jpg", ".jpeg"}), None)
    media = "image/png" if image is None or image.suffix.lower() == ".png" else "image/jpeg"
    return (spec.read_text(encoding="utf-8") if spec else ""), (image.read_bytes() if image else None), media


async def component_agent(spec: str, image: bytes | None, media_type: str = "image/png") -> ProductProfile:
    content: list = []
    if image:
        content.append(llm.image_block(image, media_type))
    content.append({"type": "text", "text": f"Specification:\n\n{spec or '(no specification text given)'}\n\n"
                                            + ("The image above is the exploded view of the product." if image else "No drawing given.")})
    return await llm.structured(ProductProfile, prompts.COMPONENTS, content, effort="medium", label="component agent")


def _taxonomy_text() -> str:
    return "\n".join(f"- {k}: {v}" for k, v in functions().items())


async def functionality_agent(profile: ProductProfile) -> FunctionalityList:
    system = prompts.FUNCTIONALITIES.format(taxonomy=_taxonomy_text())
    out = await llm.structured(FunctionalityList, system, "Product profile:\n" + profile.model_dump_json(indent=1),
                               effort="medium", label="functionality agent")
    valid = set(functions())
    for f in out.functionalities:
        if f.id not in valid:
            f.id = "unmapped"
    return out


async def rewrite_queries(gaps: list[dict], context: list[dict]) -> QueryRewrites:
    """Coverage loop: new queries for functionalities without a kept provision, from on-topic vocabulary only."""
    content = ("Functionalities without an applicable provision:\n" + json.dumps(gaps, indent=1, ensure_ascii=False)
               + "\n\nOn-topic provision headings and texts seen so far:\n" + json.dumps(context, indent=1, ensure_ascii=False))
    return await llm.structured(QueryRewrites, prompts.REWRITE, content, effort="low", label="query rewrite")
