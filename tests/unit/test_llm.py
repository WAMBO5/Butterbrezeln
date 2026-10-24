"""pipeline/llm.py with a fake client: error mapping, caching, and no repeat payment for a truncated request."""
import asyncio
from types import SimpleNamespace

import pytest

from pipeline import config, llm
from pipeline.models import TriageGrades


class _Messages:
    def __init__(self, response):
        self.response, self.calls = response, 0

    async def create(self, **kwargs):
        self.calls += 1
        assert kwargs["output_config"]["format"]["type"] == "json_schema" and kwargs["timeout"] == llm.REQUEST_TIMEOUT
        return self.response


def _client(monkeypatch, tmp_path, stop_reason="end_turn", text=""):
    response = SimpleNamespace(stop_reason=stop_reason, stop_details=None,
                               content=[SimpleNamespace(type="text", text=text)] if text else [])
    messages = _Messages(response)
    monkeypatch.setattr(llm, "_get_client", lambda: SimpleNamespace(messages=messages, beta=SimpleNamespace(messages=messages)))
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    return messages


def _call():
    return asyncio.run(llm.structured(TriageGrades, "system", "content", label="t"))


def test_valid_reply_is_parsed_and_cached(monkeypatch, tmp_path):
    messages = _client(monkeypatch, tmp_path, text='{"grades": [{"ref": "P0", "relevant": true}]}')
    assert _call().grades[0].ref == "P0" and _call().grades[0].relevant
    assert messages.calls == 1  # the second call came from the disk cache


def test_refusal_truncation_and_bad_json_are_different_failures(monkeypatch, tmp_path):
    _client(monkeypatch, tmp_path, stop_reason="refusal")
    with pytest.raises(llm.LLMError, match="refused") as refused:
        _call()
    assert not isinstance(refused.value, llm.TruncatedError)
    _client(monkeypatch, tmp_path / "b", text="not json")
    with pytest.raises(llm.LLMError, match="did not match"):
        _call()


def test_truncated_request_is_never_paid_for_twice(monkeypatch, tmp_path):
    messages = _client(monkeypatch, tmp_path, stop_reason="max_tokens", text='{"grades": [')
    with pytest.raises(llm.TruncatedError):
        _call()
    with pytest.raises(llm.TruncatedError, match="earlier run"):
        _call()
    assert messages.calls == 1


# --- transient failures and the cache --------------------------------------------------------------------------

def _status_error(cls, status):
    import httpx2

    response = httpx2.Response(status, request=httpx2.Request("POST", "http://test"))
    return cls("simulated", response=response, body=None)


class _Flaky:
    """Raises the given errors in order, then returns a valid reply."""

    def __init__(self, errors):
        self.errors, self.calls = list(errors), 0

    async def create(self, **kwargs):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return SimpleNamespace(stop_reason="end_turn", stop_details=None,
                               content=[SimpleNamespace(type="text", text='{"grades": []}')])


def _flaky(monkeypatch, tmp_path, errors):
    import anthropic

    flaky = _Flaky(errors)
    monkeypatch.setattr(llm, "_get_client", lambda: SimpleNamespace(messages=flaky, beta=SimpleNamespace(messages=flaky)))
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "TRANSIENT_WAITS", (0, 0))  # no real sleeping in tests
    return flaky, anthropic


def test_transient_api_errors_are_waited_out_with_the_same_request(monkeypatch, tmp_path):
    import anthropic

    flaky, _ = _flaky(monkeypatch, tmp_path, [])
    flaky.errors = [_status_error(anthropic.RateLimitError, 429), _status_error(anthropic.InternalServerError, 529)]
    assert _call().grades == []
    assert flaky.calls == 3  # two transient failures, then the same request succeeded


def test_a_transient_outage_that_never_ends_is_not_splittable(monkeypatch, tmp_path):
    import anthropic

    flaky, _ = _flaky(monkeypatch, tmp_path, [])
    flaky.errors = [_status_error(anthropic.RateLimitError, 429)] * 10
    with pytest.raises(llm.APIUnavailableError) as err:
        _call()
    assert err.value.splittable is False and flaky.calls == 3  # first try + one per wait, then it gives up


def test_a_rejected_request_is_a_content_failure_and_a_wrong_key_stops_the_run(monkeypatch, tmp_path):
    import anthropic

    flaky, _ = _flaky(monkeypatch, tmp_path, [])
    flaky.errors = [_status_error(anthropic.BadRequestError, 400)]
    with pytest.raises(llm.LLMError) as err:
        _call()
    assert err.value.splittable and flaky.calls == 1  # not retried: the same request would be rejected again
    flaky.errors = [_status_error(anthropic.AuthenticationError, 401)]
    with pytest.raises(anthropic.AuthenticationError):
        _call()


def test_a_corrupt_cache_file_is_a_cache_miss_not_a_crash(monkeypatch, tmp_path):
    messages = _client(monkeypatch, tmp_path, text='{"grades": [{"ref": "P0", "relevant": true}]}')
    _call()
    (cache_file,) = tmp_path.glob("*.json")
    cache_file.write_text('{"grades": [{"ref": "P0", "rele', encoding="utf-8")  # a run killed mid-write
    assert _call().grades[0].ref == "P0" and messages.calls == 2
    assert not list(tmp_path.glob("*.tmp"))  # writes are atomic: no stray temp file
