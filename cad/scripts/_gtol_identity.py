"""Stable datum keys and model annotation names shared by PMI and surface finishes.

Separate from GD&T symbols so naming a finish does not fold frame vocabulary edits.
"""

from __future__ import annotations

_PMI_NAME_PREFIX = "HARMONIC_PMI_"


def datum_key(letter: str) -> str:
    """Return the stable spec key for a datum feature symbol."""
    return f"datum:{letter}"


def pmi_annotation_name(key: str) -> str:
    """Return the unique model-annotation name persisted for ``key``."""
    return f"{_PMI_NAME_PREFIX}{key.replace(':', '_')}"
