"""Assembly-time config accessors — deliberately SEPARATE from _config.py.

``_config.py`` is imported by ``_common``, so it sits in EVERY part's recipe
closure: adding an accessor there re-keys all ~100 parts (a one-time whole-fleet
rebuild). These accessors are read ONLY on the assembly path -- ``placement`` by
``_transforms.mirror_placement`` (assembly-only) and ``flip_seeds`` by the
``build_<stem>_assembly.py`` scripts -- and NEVER by a part. Keeping them here,
in a module no part imports (``_common`` does not import it), keeps every part off
their churn: a placement/flip-seed edit re-keys only the assemblies that read it.

``_buildgraph`` recognises ``_config_asm.<accessor>`` calls exactly like
``_config.<accessor>`` (same family-token machinery), so the per-file config deps
are tracked identically.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def placement(stem: str) -> dict[str, Any]:
    """Per-part ASSEMBLY-TIME placement metadata: ``cad/config/placement/<dashed
    name>.yaml``, today just the M6.8 ``mirror_plane`` symmetry declaration read by
    ``_transforms.mirror_placement`` (issue #156).

    Its own per-part file family, OUTSIDE the ``parts/`` registry: a placement edit
    forces a FULL re-insert of only the assemblies that PLACE the part (tokenised
    per-file into each containing assembly's recipe via ``placement/*`` ->
    referenced-part rows), and never rebuilds the PART (placement is assembly-time).
    Returns ``{}`` for a part with no placement file -- the default bbox-``x``
    mirror path in ``mirror_placement``."""
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
    reads it with its OWN stem as a LITERAL. Returns ``[]`` when the file is absent
    (seeds are an optimisation -- the ``_mate`` readback guard still re-flips a miss,
    so a missing/misfiled seed costs an extra recovery, never wrong geometry)."""
    path = CONFIG_DIR / "flip_seeds" / f"{stem}.yaml"
    if not path.exists():
        return []
    return list(_load(path).get("seeds", []))
