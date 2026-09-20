r"""Pure-data dimensional contract shared by the pinion turning handle and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A turned tee: a fat grip cylinder with a
domed cap, a cross rod through the grip, and a blind tubular hub that seats over
the pinion arbor stub.  The nominals drive the part's named equation globals AND
the drawing's coordinate math; the marked-dimension map keeps the part marks and
drawing keeps in lockstep (``test_pinion_handle_drawing.py``).
"""

from __future__ import annotations

from pinion_handle_geometry import (
    CAP_RADIUS as CAP_RADIUS,
    CAP_SAG as CAP_SAG,
    GRIP_DIA as GRIP_DIA,
    GRIP_LEN as GRIP_LEN,
    ROD_DIA as ROD_DIA,
    ROD_DOWN as ROD_DOWN,
    ROD_HOLE_DIA as ROD_HOLE_DIA,
    ROD_SPAN as ROD_SPAN,
    ROD_UP as ROD_UP,
    TUBE_ID as TUBE_ID,
    TUBE_LEN as TUBE_LEN,
    TUBE_OD as TUBE_OD,
    WALL_T as WALL_T,
)

# No local size bands. The socket is a slip clearance over the arbor stub and
# the seating depth is a turned shoulder: neither is a running fit, a gear
# feature nor a locating seat, so both take the title-block general grade
# (drilled holes +0.10/0, linear by decimal place) -- cad/docs/tolerance-policy.md
# "How a critical-feature tolerance is decided" and drawing-simplicity-policy
# rule 2. A band that cannot cite a fit class or the error budget is a habit.

# ``HubReference``, ``CrossHoleReference`` and ``RodReference`` are hidden
# construction sketches whose one job is to OWN the axial values the sheet
# prints but no feature dimension carries (policy rule 2): the hub length and
# the body overall from the socket end, the cross-hole axis from the socket
# end, and the rod's reach below the body axis.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GripProfile": {"GripDia"},
    "CapProfile": {"CapR"},
    "TubeProfile": {"TubeOd", "TubeId"},
    "Tube": {"TubeLen"},
    "RodProfile": {"RodDia"},
    "Rod": {"RodSpan"},
    "RodHoleProfile": {"RodHoleDia"},
    "HubReference": {"HubLen", "BodyLen"},
    "CrossHoleReference": {"RodHoleZ"},
    "RodReference": {"RodDown"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity policy rule
# 2), so the MODEL owns them: build_pinion_handle applies this map to the
# .SLDPRT and draw_pinion_handle only reads it back.  Two places on the
# reamed socket alone, because 8.00 is the arbor stub's nominal the callout
# names; one place everywhere else, so the title block's .X row governs a
# turned handle nothing runs on (cad/docs/tolerance-policy.md).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GripProfile": {"GripDia": 1},
    "CapProfile": {"CapR": 1},
    "TubeProfile": {"TubeOd": 1, "TubeId": 2},
    "Tube": {"TubeLen": 1},
    "RodProfile": {"RodDia": 1},
    "Rod": {"RodSpan": 1},
    "RodHoleProfile": {"RodHoleDia": 1},
    "HubReference": {"HubLen": 1, "BodyLen": 1},
    "CrossHoleReference": {"RodHoleZ": 1},
    "RodReference": {"RodDown": 1},
}

_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
):
    raise AssertionError("DRAWING_PRECISION names a dimension the part never marks")
if any(
    name not in {name for names in DRAWING_PRECISION.values() for name in names}
    for names in DRAWING_DIMENSIONS.values()
    for name in names
):
    raise AssertionError("a marked dimension prints without part-authored places")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")

# The one sheet-derived dimension: the parenthesised socket-end-to-crown-root
# station, a read-only difference of the overall and the cap sagitta with no
# model dimension to import.  Its places are still specification, so the
# sheet reads them here instead of typing a literal (policy rule 2).
DRAWING_REFERENCE_PRECISION: dict[str, int] = {"socket end to crown root": 1}

# The handle and arbor rotate together. This static socket is not a running
# bearing, so it has no local roughness requirement under the simplicity policy.
SURFACE_FINISHES = ()

DRAWING_NOTES = "MATCH CROSS ROD TO BODY FOR LIGHT PRESS FIT."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
