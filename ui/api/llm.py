"""Optional LLM calls with JSON-schema output. Callers fall back to rules on LLMError."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from .config import LLM_MODE, LLM_MODEL


class LLMError(Exception):
    """This call failed; the caller should use its rule-based fallback."""


def _credentials_configured() -> bool:
    # the SDK also resolves `ant auth login` profiles stored under ~/.config/anthropic
    env = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE", "ANTHROPIC_IDENTITY_TOKEN_FILE")
    return any(os.environ.get(name) for name in env) or (Path.home() / ".config" / "anthropic").is_dir()


class LLM:
    def __init__(self, mode: str = LLM_MODE, model: str = LLM_MODEL):
        self.mode = mode
        self.model = model
        self.disabled_reason: str | None = None
        if mode not in ("on", "auto"):  # "auto" is the old name of "on"
            self.disabled_reason = "LLM_MODE=off (Standard; LLM_MODE=on schaltet LLM ein)"
        elif not model:
            self.disabled_reason = "Kein Modell gesetzt (ANTHROPIC_MODEL oder LLM_MODEL)"
        elif not _credentials_configured():
            self.disabled_reason = "Keine LLM-Zugangsdaten (ANTHROPIC_API_KEY setzen oder `ant auth login`)"
        self._client = None
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self.disabled_reason is None

    def _get_client(self):
        with self._lock:
            if self._client is None:
                try:
                    import anthropic
                except ImportError:
                    self.disabled_reason = "Paket 'anthropic' nicht installiert"
                    raise LLMError(self.disabled_reason)
                self._client = anthropic.Anthropic()
            return self._client

    def json(self, *, system: str, user: str, schema: dict[str, Any], effort: str = "low",
             max_tokens: int = 16000) -> tuple[Any, dict[str, Any]]:
        """Returns (parsed JSON, meta with model, prompt and token usage). Raises LLMError."""
        if not self.available:
            raise LLMError(self.disabled_reason or "LLM nicht verfügbar")
        import anthropic

        client = self._get_client()
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            self.disabled_reason = f"Keine gültigen LLM-Zugangsdaten ({exc.__class__.__name__})"
            raise LLMError(self.disabled_reason) from exc
        except TypeError as exc:  # raised when no credential source resolves at all
            self.disabled_reason = f"Keine LLM-Zugangsdaten gefunden ({exc})"
            raise LLMError(self.disabled_reason) from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("Rate-Limit erreicht") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"API-Fehler {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Keine Verbindung zur LLM API") from exc

        if response.stop_reason == "refusal":
            raise LLMError("Anfrage vom Modell abgelehnt")
        if response.stop_reason == "max_tokens":
            raise LLMError("Antwort abgeschnitten (max_tokens)")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise LLMError("Keine Textantwort")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("Ungültiges JSON in der Antwort") from exc
        usage = response.usage
        meta = {
            "model": response.model,
            "prompt": system + "\n\n" + user,
            "tokens": {"input": usage.input_tokens, "output": usage.output_tokens},
            "request_id": getattr(response, "_request_id", None),
        }
        return data, meta
