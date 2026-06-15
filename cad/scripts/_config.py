"""Config loader — the YAML files in ``cad/config/`` are the source of truth.

Build scripts import from here instead of hardcoding parametrics, fits and
materials. Derived geometry (centre distances, cam grids, incline trig) is still
computed in the build scripts from these inputs — only the genuinely tabular
data lives in YAML.

    from _config import channels, machine, fit, cone_teeth
    DP = machine("gear_train", "diametral_pitch")
    for ch in channels():
        teeth = ch["cone_teeth"]
    backlash = fit("gear_mesh", "rack_backlash_mm")
"""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@functools.lru_cache(maxsize=None)
def _doc(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"config file missing: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def channels() -> list[dict[str, Any]]:
    """The 20 channel rows, ordered by build-loop index (j)."""
    rows = _doc("channels")["channels"]
    return sorted(rows, key=lambda r: r["index"])


def cone_teeth(index: int) -> int:
    """Cone-gear tooth count for 0-based channel ``index``."""
    return channels()[index]["cone_teeth"]


def amplitudes() -> list[float]:
    """The a_j coefficient vector, indexed by channel (amplitude-bar stations)."""
    return [ch["amplitude_mm"] for ch in channels()]


def machine(*keys: str) -> Any:
    """Walk machine.yaml, e.g. ``machine('gear_train', 'diametral_pitch')``."""
    node: Any = _doc("machine")
    for key in keys:
        node = node[key]
    return node


def fit(group: str, *keys: str) -> Any:
    """A fit value from tolerances.yaml ``fits:``, e.g. ``fit('gear_mesh', 'rack_backlash_mm')``."""
    node: Any = _doc("tolerances")["fits"][group]
    for key in keys:
        node = node[key]
    return node


def provenance(doc: str, *keys: str) -> dict[str, Any]:
    """The ``source``/``confidence``/``notes`` triple for a config node.

    Provenance is preserved INLINE in the YAML (rather than regenerated into
    DIMENSIONS.md, which stays the curated narrative). This reads it back so the
    Part D custom-property writer can stamp ``Source``/``Confidence``/``Notes``
    onto the parts. ``doc`` is the file stem; ``keys`` walk into it (empty = the
    file's top-level provenance, as on channels.yaml).

        provenance("machine", "cone_incline")   # -> {source, confidence, notes}
        provenance("channels")                  # -> file-level triple
    """
    node: Any = _doc(doc)
    for key in keys:
        node = node[key]
    return {k: node[k] for k in ("source", "confidence", "notes") if k in node}


def materials() -> dict[str, Any]:
    return _doc("materials")


def palette(name: str) -> tuple[float, float, float]:
    return tuple(_doc("materials")["palette"][name])  # type: ignore[return-value]
