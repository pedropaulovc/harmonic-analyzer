"""The ``drawing_unit`` a package declares, validated in one place.

A package (a part's ``cad/config/parts/<dashed-stem>.yaml`` row or an
assembly's ``cad/config/assemblies/<dashed-stem>.yaml`` contract) may declare
``drawing_unit: mm`` or ``drawing_unit: in`` (issue #290).  The TOL_* stamping,
the drawing's document units and the model's document units all follow that one
selection.  A package that declares nothing keeps the legacy millimetre sheet
until the final migration; any other value is refused.

Pure data: no config reads, no SolidWorks.  Both the part stamping and the
assembly contract import it, so it must stay free of ``_config`` and
``_assembly_contract`` (either would widen every importing recipe).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, cast

DrawingUnit = Literal["mm", "in"]

DRAWING_UNITS: tuple[DrawingUnit, ...] = ("mm", "in")

# A package without a declaration prints the legacy millimetre sheet.
LEGACY_DRAWING_UNIT: DrawingUnit = "mm"

DRAWING_UNIT_KEY = "drawing_unit"


def checked_drawing_unit(owner: str, value: object) -> DrawingUnit:
    """``value`` as a drawing unit; anything but ``"mm"``/``"in"`` raises."""
    if isinstance(value, str) and value in DRAWING_UNITS:
        return cast(DrawingUnit, value)
    raise ValueError(
        f"{owner}: {DRAWING_UNIT_KEY} must be one of {list(DRAWING_UNITS)}, got {value!r}"
    )


def declared_drawing_unit(owner: str, row: Mapping[str, Any]) -> DrawingUnit | None:
    """The unit ``row`` declares, or ``None`` when it declares none."""
    if DRAWING_UNIT_KEY not in row:
        return None
    return checked_drawing_unit(owner, row[DRAWING_UNIT_KEY])


def resolved_drawing_unit(declared: DrawingUnit | None) -> DrawingUnit:
    """The unit a package prints: its validated declaration, else the legacy
    millimetre.  The ONE place the legacy fallback lives: a registry row
    (:func:`drawing_unit`), an assembly contract and a drawing package all
    resolve their declaration through it."""
    return LEGACY_DRAWING_UNIT if declared is None else declared


def drawing_unit(owner: str, row: Mapping[str, Any] | None) -> DrawingUnit:
    """The unit ``row`` selects: its declaration, else the legacy millimetre.

    ``row`` is ``None`` for an unregistered package (no row to declare one)."""
    declared = None if row is None else declared_drawing_unit(owner, row)
    return resolved_drawing_unit(declared)
