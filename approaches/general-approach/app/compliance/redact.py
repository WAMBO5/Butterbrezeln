"""Remove secrets from anything written to disk (ledger, manifest, trace, reports)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

SECRET_KEY_RE = re.compile(r"(?i)api[_-]?key|authorization|secret")
REDACTED = "[REDACTED]"


def jsonable(obj: Any) -> Any:
    """Plain JSON data from models, paths and containers."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


def redact(obj: Any) -> Any:
    """`obj` as JSON data without secret-named keys and without the API key value anywhere."""
    key = os.environ.get("ANTHROPIC_API_KEY") or None

    def walk(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items() if not SECRET_KEY_RE.search(str(k))}
        if isinstance(value, list):
            return [walk(v) for v in value]
        if isinstance(value, str) and key and key in value:
            return value.replace(key, REDACTED)
        return value

    return walk(jsonable(obj))
