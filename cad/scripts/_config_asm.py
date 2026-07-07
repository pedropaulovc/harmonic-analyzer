"""Assembly-time config accessors — deliberately SEPARATE from _config.py.

``_config.py`` is imported by ``_common``, so it sits in EVERY part's recipe
closure: adding an accessor there re-keys all ~100 parts (a one-time whole-fleet
rebuild). This accessor is read ONLY on the assembly path -- ``placement`` by
``_transforms.mirror_placement`` (assembly-only) -- and NEVER by a part. Keeping it
here, in a module no part imports (``_common`` does not import it), keeps every part
off its churn: a placement edit re-keys only the assemblies that read it.

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
