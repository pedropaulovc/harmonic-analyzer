r"""Pure-data dimensional contract shared by the pinion engage lever and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A hub slipped over the lift rod's front
end, with a tapered grip rod rising out of it -- turned steel.  The MHA-135 pin
(U36) match-drilled through hub and rod at assembly carries the drive torque, so
the bore is a plain slip fit.  The nominals drive the part's named equation
globals AND the drawing's coordinate math; the marked-dimension map keeps the
part marks and drawing keeps in lockstep (``test_pinion_lever_drawing.py``).
"""

from __future__ import annotations

from _fit_limits import REAM_SLIDE
from pinion_lever_geometry import (
    BORE as BORE,
    BORE_DEPTH as BORE_DEPTH,
    CAP_RADIUS as CAP_RADIUS,
    CAP_SAG as CAP_SAG,
    HUB_LEN as HUB_LEN,
    HUB_OD as HUB_OD,
    PIN_HOLE_DIA as PIN_HOLE_DIA,
    PIN_HOLE_FROM_MOUTH as PIN_HOLE_FROM_MOUTH,
    PIN_HOLE_Z as PIN_HOLE_Z,
    ROD_LEN as ROD_LEN,
    ROD_ROOT_DIA as ROD_ROOT_DIA,
    ROD_TIP_DIA as ROD_TIP_DIA,
    ROD_Y0 as ROD_Y0,
    WALL_T as WALL_T,
)

LIFT_ROD_NUMBER = "MHA-060"
PIN_NUMBER = "MHA-135"

# U36: the pin carries the torque, so the hub only has to slide onto the h-band
# 6.35 lift rod.  Codex P2 (#844): the former 6.35-6.40 band's minimum met the
# rod's maximum line-to-line; REAM_SLIDE (+0.025/+0.010, the fit MHA-056 and
# MHA-061 hold on the same shafts) guarantees 0.010 of clearance.
BORE_BAND = REAM_SLIDE
# The blind bore's bottom wall is the thinnest section a novice turns (U27:
# >= 1.5 floor); the .XX row would allow 1.49, so it carries its own band.
END_WALL_TOLERANCE_MM = 0.25

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarrelProfile": {"HubOd", "HubBore"},
    "Barrel": {"BoreDepth"},
    "Wall": {"EndWall"},
    # The taper prints as root and tip diameters over the 86.0 height.  The
    # r7 render showed the 0.7-degree half-angle's extension line running to
    # the cone's virtual apex, 163 mm below the root and off the sheet.
    "RodProfile": {"RodTipY", "RodTipDia", "RodRootDia"},
    "CapProfile": {"CapR"},
    "PinHoleProfile": {"PinHoleDia"},
    # Rule 2 reference sketches: the grip axis and the pin-hole station are
    # printed from face B (the flat mouth face), but neither is any feature's
    # own dimension, so each gets a one-line construction sketch whose single
    # driving dimension IS the value.
    "GripStationReference": {"GripFromB"},
    "PinHoleStationReference": {"PinHoleFromB"},
}

# Decimal places ARE the tolerance statement (policy rule 2); the part authors
# them and the drawing reads them back.  Three on the banded bore; two on the
# end wall (own band) and the grip station (the old +/-0.10 note, now the .XX
# row); one everywhere a turned or hand-finished feature is routine.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BarrelProfile": {"HubOd": 1, "HubBore": 3},
    "Barrel": {"BoreDepth": 1},
    "Wall": {"EndWall": 2},
    "RodProfile": {"RodTipY": 1, "RodTipDia": 1, "RodRootDia": 1},
    "CapProfile": {"CapR": 1},
    "PinHoleProfile": {"PinHoleDia": 2},
    "GripStationReference": {"GripFromB": 2},
    "PinHoleStationReference": {"PinHoleFromB": 1},
}
_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked dimension must state its decimal places")

# Rule 5: nothing on the lever runs or slides any more -- the pinned hub is a
# static slip fit -- so no surface carries a roughness symbol.
SURFACE_FINISHES = ()

# The match-drill requirement rides the pin hole's own callout (rule 6: matched
# fits belong on the feature), so the note block keeps only the crown break.
PIN_HOLE_CALLOUT = "\n".join(
    (
        f"MATCH-DRILL THRU AT ASSEMBLY ON {LIFT_ROD_NUMBER},",
        f"GRIP PARKED; DRIVE {PIN_NUMBER}, PEEN FLUSH",
    )
)
DRAWING_NOTES = "\n".join(
    (
        "LEAVE THE CROWN ROOT CIRCLE SHARP;",
        "  EXEMPT FROM TITLE-BLOCK EDGE-BREAK REQUIREMENT.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
