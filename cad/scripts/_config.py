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


def parts(stem: str | None = None) -> dict[str, Any]:
    """The part registry (parts.yaml). With ``stem``, one part's record merged
    over the file ``defaults:`` (so revision/confidence fall through)."""
    doc = _doc("parts")
    if stem is None:
        return doc["parts"]
    if stem not in doc["parts"]:
        raise KeyError(f"part not in registry: {stem}")
    return {**doc.get("defaults", {}), **doc["parts"][stem]}


def placement(stem: str) -> dict[str, Any]:
    """Per-part ASSEMBLY-TIME placement metadata: ``cad/config/placement/<dashed
    name>.yaml``, today just the M6.8 ``mirror_plane`` symmetry declaration read by
    ``_transforms.mirror_placement``.

    Lives in its OWN per-part file family, deliberately OUTSIDE the ``parts/``
    registry (issue #156): a placement edit must force a FULL re-insert of only the
    assemblies that PLACE the part, so it is tokenised per-file into each containing
    assembly's recipe (``placement/*`` -> the referenced-part rows, see
    ``_buildgraph``/``dodo``). Keeping it out of ``parts/<name>.yaml`` means a
    placement edit does NOT rebuild the PART (placement is assembly-time only) and a
    custom-property edit does NOT force an assembly FULL. Returns ``{}`` for a part
    with no placement file -- the default bbox-``x`` mirror path in
    ``mirror_placement``."""
    path = CONFIG_DIR / "placement" / f"{stem}.yaml"
    if not path.exists():
        return {}
    return _load(path)


def flip_seeds(stem: str) -> list[str]:
    """The learned per-signature flip-polarity seeds for ONE assembly:
    ``cad/config/flip_seeds/<stem>.yaml`` (``seeds:`` list), consumed by
    ``_assembly.set_flip_seeds`` / ``_seed_flip``.

    Per-assembly (not one shared table in ``_assembly.py``) so re-learning one
    assembly's flip polarity re-keys only THAT assembly's recipe. Each build script
    reads it with its OWN stem as a LITERAL (``_config.flip_seeds("drive_train")``)
    so the token resolves to a single ``flip_seeds/<stem>.yaml`` file. Returns
    ``[]`` when the file is absent (seeds are an optimisation -- the ``_mate``
    readback guard still re-flips a miss, so a missing/misfiled seed costs an extra
    recovery, never wrong geometry)."""
    path = CONFIG_DIR / "flip_seeds" / f"{stem}.yaml"
    if not path.exists():
        return []
    return list(_load(path).get("seeds", []))


def materials() -> dict[str, Any]:
    return _doc("materials")


def palette(name: str) -> tuple[float, float, float]:
    return tuple(_doc("materials")["palette"][name])  # type: ignore[return-value]
