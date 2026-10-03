"""Prove every configuration of a multi-configuration part carries its material.

``apply_material`` sets the ACTIVE configuration's material only
(``IPartDoc::SetMaterialPropertyName2``), so a configuration split before it
could carry no material, and an assembly placing that configuration would take
the part's mass from the wrong density.  Shared by the parts that save an
INSTALLED configuration beside their manufactured default (MHA-DT-030, MHA-DT-032).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import _telemetry
from _common import _early_bound


def require_material_in_every_configuration(
    adapter: Any, part_name: str, material: str, configurations: Sequence[str]
) -> None:
    """Read each configuration's material back; raise unless all are ``material``.

    Every configuration is logged before any raise, so a failing leaf still
    shows what each one reads.
    """
    part = _early_bound(adapter.currentModel, "IPartDoc")
    readings: dict[str, str] = {}
    for name in configurations:
        # Early-bound: the retval, then the [out] database.
        read, database = part.GetMaterialPropertyName2(name)
        readings[name] = str(read or "")
        _telemetry.info(f"material in {name}: {read!r} (database {database!r})")
    wrong = {name: got for name, got in readings.items() if got != material}
    if wrong:
        raise RuntimeError(
            f"{part_name}: configurations {wrong} do not carry {material!r}"
        )
    _telemetry.success(f"{material} in every configuration {list(readings)}")
