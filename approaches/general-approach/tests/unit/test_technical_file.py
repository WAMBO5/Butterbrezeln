import shutil
from pathlib import Path

import pytest

from app.compliance.technical_file import replace_block, update_technical_file
from app.pipeline.main import run_case
from tests.conftest import CHALLENGE, INDEX

DOCS = Path("docs/ai-act")


def test_replace_block_keeps_the_rest():
    text = "head\n<!-- metrics:start -->\nold\n<!-- metrics:end -->\ntail\n"
    assert replace_block(text, "metrics", "new") == "head\n<!-- metrics:start -->\nnew\n<!-- metrics:end -->\ntail\n"
    assert replace_block("no markers", "metrics", "new") == "no markers"


@pytest.mark.integration
@pytest.mark.skipif(not INDEX.exists(), reason="challenge data missing")
async def test_update_rewrites_only_marked_blocks(tmp_path, tmp_settings, fake_responders, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-techfile-321")
    res = await run_case(CHALLENGE / "cases" / "dev-rear-lamp", markets=[], mode="benchmark", settings=tmp_settings,
                         run_dir=None)
    docs = tmp_path / "docs"
    shutil.copytree(DOCS, docs)
    before = {p.name: p.read_text() for p in docs.glob("*.md")}
    written = update_technical_file(tmp_settings, [Path(res.run_dir)], docs_dir=docs)
    assert {p.name for p in written} == {"technical-file.md", "instructions-for-use.md"}
    for p in docs.glob("*.md"):
        after = p.read_text()
        assert "sk-techfile-321" not in after
        for marker in ("metrics", "models", "oversight"):
            after = replace_block(after, marker, "X")
            before[p.name] = replace_block(before[p.name], marker, "X")
        assert after == before[p.name], p.name
    tech = (docs / "technical-file.md").read_text()
    assert "page level" in tech and "fake/scope_narrower" in tech and res.run_dir.split("/")[-1] in tech
