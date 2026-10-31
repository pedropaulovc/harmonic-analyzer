"""The ``drawing_unit`` a package declares (issue #290 transition switch).

A part's ``cad/config/parts/<stem>.yaml`` row or an assembly's
``cad/config/assemblies/<stem>.yaml`` contract may declare ``drawing_unit: in``
or ``drawing_unit: mm``; a package that declares nothing prints millimetres.
The TOL_* stamps, the model's document units and the sheet's document units
all follow that one value.  At cutover inches become the default and only
metric-only supplier packages keep ``mm``.

Pure data: no config reads, no SolidWorks.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

DrawingUnit = Literal["mm", "in"]


def drawing_unit(owner: str, row: Mapping[str, Any] | None) -> DrawingUnit:
    """``row``'s declared unit, ``"mm"`` when it declares none (or there is no
    row); any value other than ``"mm"``/``"in"`` raises."""
    value = "mm" if row is None else row.get("drawing_unit", "mm")
    if value not in ("mm", "in"):
        raise ValueError(f"{owner}: drawing_unit must be 'mm' or 'in', got {value!r}")
    return value
