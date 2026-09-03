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
import re
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


_RELEASE_VERSION_RE = re.compile(r"^v([1-9]\d*)$")


def _load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@functools.lru_cache(maxsize=None)
def _doc(name: str) -> dict[str, Any]:
    """One config doc as a dict. ``machine`` and ``parts`` are now SPLIT across a
    directory of per-subsystem / per-part files (so a single value edit invalidates
    only the parts that read that one file -- see dodo.py); they are re-aggregated
    here into the exact same shape callers always saw, so every accessor, the
    verify audit and provenance are unchanged. Other docs are a single file."""
    split_dir = CONFIG_DIR / name
    if split_dir.is_dir():
        if name == "machine":
            # machine/_base.yaml (units) + one file per subsystem dict.
            agg: dict[str, Any] = dict(_load(split_dir / "_base.yaml"))
            for p in sorted(split_dir.glob("*.yaml")):
                if p.name != "_base.yaml":
                    agg.update(_load(p))
            return agg
        if name == "parts":
            # parts/_defaults.yaml (defaults:) + one file per registry entry.
            defaults = _load(split_dir / "_defaults.yaml")
            entries: dict[str, Any] = {}
            for p in sorted(split_dir.glob("*.yaml")):
                if p.name != "_defaults.yaml":
                    entries.update(_load(p))
            return {**defaults, "parts": entries}
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"config file missing: {path}")
    return _load(path)


def release_revision() -> str:
    """Return the next compact release revision stamped into CAD metadata."""
    value = str(_doc("release")["next_revision"]).strip()
    if not _RELEASE_VERSION_RE.fullmatch(value):
        raise ValueError(f"invalid next_revision in release.yaml: {value!r}")
    return value


def channels() -> list[dict[str, Any]]:
    """The 20 channel rows, ordered by build-loop index (j)."""
    rows = _doc("channels")["channels"]
    return sorted(rows, key=lambda r: r["index"])


def active_count() -> int:
    """How many channels the build PHYSICALLY instantiates (machine.yaml).

    A BUILD-SPEED KNOB: drop it below 20 to cut build/refresh time during
    debugging iterations (each channel adds a cylinder gear + cam-follower to
    drive-train and a rocker/amplitude-bar/top-lever/spring to channel); set
    it back to 20 — the full machine, the default — for validation and
    release. Caps the per-channel mechanism to the FIRST ``active_count``
    channels; the 20 cone gears and all 20 channels.yaml rows (gear law,
    ratios, synthesis truth model) are ALWAYS kept. See the
    channels.active_count note in machine/channels.yaml.
    """
    return int(machine("channels", "active_count"))


def active_channels() -> list[dict[str, Any]]:
    """The first ``active_count`` channel rows — the physically-built channels."""
    return channels()[: active_count()]


def cone_teeth(index: int) -> int:
    """Cone-gear tooth count for 0-based channel ``index``."""
    return channels()[index]["cone_teeth"]


def amplitudes() -> list[float]:
    """The a_j coefficient vector, indexed by channel (amplitude-bar stations)."""
    return [ch["amplitude_mm"] for ch in channels()]


def poses() -> dict[str, Any]:
    """Saved assembly overrides from poses.yaml: ``parallel`` drives every bar
    to a common target amplitude, while ``sinusoid`` retains the Default
    per-channel amplitudes and turns the cam train."""
    return _doc("poses")


def assembly_configuration_roles() -> dict[str, str]:
    """Assembly configuration names in their presentation order."""
    saved = poses()
    return {
        "default": "Default",
        "parallel": str(saved["parallel"]["configuration"]),
        "sinusoid": str(saved["sinusoid"]["configuration"]),
    }


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


def title_block(kind: str) -> dict[str, Any]:
    """A title-block general tolerance row from title_block.yaml.

    ``title_block('linear_2pl')`` -> ``{value_in, display}``;
    ``title_block('angular')``    -> ``{value_deg, display}``.
    """
    return _doc("title_block")[kind]


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


def parts(stem: str | None = None) -> dict[str, Any]:
    """The part registry (parts.yaml). With ``stem``, one part's record merged
    over the file ``defaults:`` (so revision/confidence fall through)."""
    doc = _doc("parts")
    if stem is None:
        return doc["parts"]
    if stem not in doc["parts"]:
        raise KeyError(f"part not in registry: {stem}")
    return {**doc.get("defaults", {}), **doc["parts"][stem]}


def materials() -> dict[str, Any]:
    return _doc("materials")


def palette(name: str) -> tuple[float, float, float]:
    return tuple(_doc("materials")["palette"][name])  # type: ignore[return-value]
