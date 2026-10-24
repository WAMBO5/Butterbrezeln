"""The one place that calls LLM.

Structured output into a Pydantic model, prompt caching on the stable system prefix, effort instead of sampling
parameters (the 5.5 models reject a non-default temperature), server-side refusal fallback on Opus/Sonnet, bounded
concurrency, and a disk cache keyed by the full request so a re-run is free and reproducible.

The request is what `messages.parse` would send (the schema goes into `output_config.format`), but we call `create` and
validate ourselves so that `stop_reason` is checked first: a refusal and a truncated reply are different failures.

Failures come in two kinds. A content failure (refusal, truncated or malformed reply, a request the API rejects) fails the
same way if the same request is sent again, so callers split the batch (`LLMError.splittable`). A transient failure (429,
529, 5xx, timeout) is waited out here, the same request again, after the SDK's own short backoff; only if it outlasts all
of that does it surface as `APIUnavailableError`, which callers must not answer by sending more requests.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from typing import TypeVar

import anthropic
from anthropic.lib._parse._transform import to_json_output_format
from pydantic import BaseModel, ValidationError

from pipeline import config

T = TypeVar("T", bound=BaseModel)

_client: anthropic.AsyncAnthropic | None = None
_sem: asyncio.Semaphore | None = None
FALLBACK_BETA = "server-side-fallback-2026-07-01"
REQUEST_TIMEOUT = anthropic.Timeout(600.0, connect=10.0)
TRANSIENT_WAITS = (30, 60, 120, 240)  # seconds we wait, on top of the SDK's retries, before giving up on a transient failure
TRANSIENT_STATUS = {408, 409, 429}


class LLMError(RuntimeError):
    """A call that failed in a way a caller can degrade around."""
    splittable = True  # sending the same request again fails the same way; a smaller batch is a different request


class TruncatedError(LLMError):
    """The reply hit max_tokens."""


class APIUnavailableError(LLMError):
    """429/529/5xx/timeouts that outlasted the SDK's retries and our own waits. More requests would only add load."""
    splittable = False


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(max_retries=3)  # short SDK backoff; long waits are ours (TRANSIENT_WAITS)
    return _client


def _get_sem() -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(config.MAX_CONCURRENCY)
    return _sem


def _key(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _read_cache(path, output_type: type[T]) -> T | None:
    try:
        return output_type.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError):  # missing, or corrupt because a run was killed mid-write: a cache miss
        return None


def _write_atomic(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


async def _post(kwargs: dict, model: str, name: str):
    """One request, waiting out transient failures. The wait is outside the semaphore so it does not block other calls."""
    error: Exception | None = None
    for wait in (*TRANSIENT_WAITS, None):
        async with _get_sem():
            try:
                if "haiku" in model:  # no server-side refusal fallback for Haiku
                    return await _get_client().messages.create(**kwargs)
                return await _get_client().beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **kwargs)
            except (anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.NotFoundError):
                raise  # a wrong key or model id fails every call: stop the run instead of degrading it
            except anthropic.APIStatusError as exc:
                if exc.status_code not in TRANSIENT_STATUS and exc.status_code < 500:
                    raise LLMError(f"{name}: request rejected ({exc.status_code}): {exc.message}") from exc
                error = exc
            except anthropic.APIConnectionError as exc:  # includes timeouts
                error = exc
        if wait is None:
            break
        await asyncio.sleep(wait)
    raise APIUnavailableError(f"{name}: API unavailable after retries: {type(error).__name__}: {error}") from error


async def structured(output_type: type[T], system: str, content: str | list, *, model: str | None = None,
                     effort: str = "medium", max_tokens: int = 32000, label: str = "") -> T:
    """One LLM call that returns a validated `output_type`. `system` is cached; put varying input in `content`."""
    model = model or config.MODEL
    name = label or output_type.__name__
    payload = {"model": model, "system": system, "content": content, "effort": effort,
               "schema": output_type.model_json_schema(), "max_tokens": max_tokens}
    path = config.CACHE_DIR / f"{_key(payload)}.json"
    cached = _read_cache(path, output_type)
    if cached is not None:
        return cached
    truncated_marker = path.with_suffix(".truncated")
    if truncated_marker.is_file():  # this exact request already ran into max_tokens (billed); do not pay for it again
        raise TruncatedError(f"{name}: reply hit max_tokens={max_tokens} on an earlier run")

    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": content}],
        output_config={"effort": effort, "format": to_json_output_format(output_type)},
        # Explicit timeout: without it the SDK refuses non-streaming calls it estimates at over 10 minutes.
        timeout=REQUEST_TIMEOUT,
    )
    response = await _post(kwargs, model, name)

    if response.stop_reason == "refusal":
        raise LLMError(f"{name}: refused ({getattr(response, 'stop_details', None)})")
    if response.stop_reason == "max_tokens":
        _write_atomic(truncated_marker, "max_tokens")
        raise TruncatedError(f"{name}: reply hit max_tokens={max_tokens}")
    text = "".join(block.text for block in response.content if block.type == "text")
    try:
        parsed = output_type.model_validate_json(text)
    except ValidationError as exc:
        raise LLMError(f"{name}: reply did not match {output_type.__name__}: {exc.errors()[:2]}") from exc
    _write_atomic(path, parsed.model_dump_json())
    return parsed


def image_block(png_bytes: bytes, media_type: str = "image/png") -> dict:
    import base64
    return {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                        "data": base64.standard_b64encode(png_bytes).decode("ascii")}}
