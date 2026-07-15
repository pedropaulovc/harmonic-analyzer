"""Post-save integrity checks for parts that feed manufacturing drawings."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def require_saved_drawing_properties(adapter: Any, names: Sequence[str]) -> None:
    """Fail if a saved part lost any drawing-critical file property."""
    missing = [
        name for name in names
        if not str(adapter.currentModel.GetCustomInfoValue("", name) or "")
    ]
    if missing:
        raise RuntimeError(f"saved part drawing properties are missing: {missing}")
