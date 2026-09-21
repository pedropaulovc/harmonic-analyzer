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

# Photo-derived reconstruction of the separate handle-to-arbor retention joint.
# The upper tee's OD10.5 socket shows a small flush pin distinct from the Ø6
# grip cross rod.  Its diameter and mid-socket station are reconstruction
# choices within the photographic evidence, not historical measurements.
RETENTION_PIN_DIA = 2.0
RETENTION_PIN_STATION_FROM_FLOOR = TUBE_LEN / 2.0
RETENTION_PIN_STATION_FROM_MOUTH = TUBE_LEN - RETENTION_PIN_STATION_FROM_FLOOR
RETENTION_PIN_CENTER_Z = (
    GRIP_LEN / 2.0 + WALL_T + RETENTION_PIN_STATION_FROM_FLOOR
)
RETENTION_PIN_LEN = TUBE_OD
if RETENTION_PIN_STATION_FROM_FLOOR != RETENTION_PIN_STATION_FROM_MOUTH:
    raise AssertionError("handle retention pin must remain at socket mid-length")

# No local size bands. The socket is a slip clearance over the arbor stub and
# the seating depth is a turned shoulder: neither is a running fit, a gear
# feature nor a locating seat, so both take the title-block general grade.
# The retention hole is reamed to the actual MHA-136 pin for a stated light
# drive fit, so stock variation cannot undermine positive retention and needs
# no independent band (drawing-simplicity-policy rule 2).

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
    "RetentionHoleProfile": {"RetentionHoleDia"},
    "HubReference": {"HubLen", "BodyLen"},
    "CrossHoleReference": {"RodHoleZ"},
    "RetentionReference": {"RetentionPinFromMouth"},
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
    "RetentionHoleProfile": {"RetentionHoleDia": 1},
    "RodHoleProfile": {"RodHoleDia": 1},
    "HubReference": {"HubLen": 1, "BodyLen": 1},
    "CrossHoleReference": {"RodHoleZ": 1},
    "RetentionReference": {"RetentionPinFromMouth": 1},
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


# The handle and arbor rotate together. This static socket is not a running
# bearing, so it has no local roughness requirement under the simplicity policy.
SURFACE_FINISHES = ()

RETENTION_HOLE_CALLOUT = (
    "MATCH-DRILL WITH MHA-102\n"
    "REAM TO ACTUAL MHA-136\n"
    "LIGHT DRIVE FIT"
)

DRAWING_NOTES = "\n".join(
    (
        "MATCH CROSS ROD TO BODY FOR LIGHT PRESS FIT.",
        "MHA-136 ENDS FLUSH WITH SOCKET O.D. AFTER ASSEMBLY.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
