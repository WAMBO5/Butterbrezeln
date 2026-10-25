"""The challenge's own tools (`tools/validate.py`, `tools/score_local.py`), loaded from the package
so validation is exactly what the submission platform runs."""

from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType


@lru_cache(maxsize=None)
def load_tool(challenge_dir: Path, name: str) -> ModuleType:
    path = Path(challenge_dir) / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"challenge_{name}", path)
    if spec is None or spec.loader is None:
        raise FileNotFoundError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # validate.py defines dataclasses
    spec.loader.exec_module(module)
    return module
