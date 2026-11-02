r"""Pure-data contract for the separate MHA-DT-15 pinion grip crossrod.

The registry slug remains ``dt-pinion-handle`` because this is the operator's grip
component, but it is only the cold-finished crossrod.  The turned head, neck,
cross-hole, and arbor are one integral MHA-DT-22 part.
"""

from __future__ import annotations

import _config
from _package_units import drawing_unit
from dt_pinion_handle_geometry import (
    ROD_DIA as ROD_DIA,
    ROD_DOWN as ROD_DOWN,
    ROD_SPAN as ROD_SPAN,
    ROD_UP as ROD_UP,
)

# #290: the registry row's drawing_unit (in) is this sheet's unit.
UNIT = drawing_unit("parts/dt-pinion-handle", _config.parts("dt-pinion-handle"))

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"RodDia"},
    "Rod": {"RodSpan"},
}

# The cut length prints at the title block's .XX.  The as-bought 1/4 bar
# imports at three places, then the sheet prints it as its stock fraction,
# a REF the supplier's bar governs (ROD_FRACTION_DENOMINATOR).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RodProfile": {"RodDia": 3},
    "Rod": {"RodSpan": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked crossrod dimension needs authored places")
ROD_FRACTION_DENOMINATOR = 4  # 1/4

SURFACE_FINISHES = ()
# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): notes never carry a dimension.  The bar size is the registry's
# material specification and the imported RodDia.
# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): assembly requirements belong on the feature callout or the
# assembly step, never in a part's general notes.  ASSEMBLY_STEP is the
# pinion fit-up step text (pinion_rig_fitup) that owns this joint.
DRAWING_NOTES = "USE COLD-FINISHED BAR AS RECEIVED."
ASSEMBLY_STEP = (
    "BOND MHA-DT-15 INTO MHA-DT-22 HEAD WITH LOCTITE 638; "
    "INSTALLED ROD SHALL NOT TURN OR SLIDE BY HAND."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
