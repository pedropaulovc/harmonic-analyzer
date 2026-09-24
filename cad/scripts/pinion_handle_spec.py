r"""Pure-data contract for the separate MHA-058 pinion grip crossrod.

The registry slug remains ``pinion-handle`` because this is the operator's grip
component, but it is only the cold-finished crossrod.  The turned head, neck,
cross-hole, and arbor are one integral MHA-102 part.
"""

from __future__ import annotations

from pinion_handle_geometry import (
    ROD_DIA as ROD_DIA,
    ROD_DOWN as ROD_DOWN,
    ROD_SPAN as ROD_SPAN,
    ROD_UP as ROD_UP,
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"RodDia"},
    "Rod": {"RodSpan"},
}

DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RodProfile": {"RodDia": 1},
    "Rod": {"RodSpan": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked crossrod dimension needs authored places")

SURFACE_FINISHES = ()
DRAWING_NOTES = "\n".join(
    (
        "USE COLD-FINISHED DIA 6 BAR AS RECEIVED.",
        "ON ASSEMBLY: BOND INTO MHA-102 HEAD WITH LOCTITE 638.",
        "INSTALLED ROD SHALL NOT TURN OR SLIDE BY HAND.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
