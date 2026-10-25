from pathlib import Path

from app.config.settings import load_settings


def test_defaults():
    s = load_settings({"ANTHROPIC_MODEL": "m-judge"})
    assert (s.max_cost_usd, s.max_retries, s.concurrency, s.include_uncertain, s.retention_days) == (5.0, 2, 6, True, 183)
    assert s.model_review == "m-judge" and s.model_fast is None
    assert s.index_path == Path("industrial-ai-hackathon/regulations/index.json")
    assert s.catalog_path == Path("data/catalog.sqlite")


def test_key_is_never_stored():
    s = load_settings({"ANTHROPIC_API_KEY": "sk-secret-123"})
    assert s.api_key_present and "sk-secret-123" not in repr(s)
