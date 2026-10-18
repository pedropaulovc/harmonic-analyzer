r"""Pure-data dimensional contract shared by the pinion engage lever and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A hub slipped over the lift rod's front
end, with a straight Ø6 grip rod rising out of it -- turned steel.  The MHA-DT-030 pin
(U36) match-drilled through hub and rod at assembly carries the drive torque, so
the bore is a plain slip fit.  The nominals drive the part's named equation
globals AND the drawing's coordinate math; the marked-dimension map keeps the
part marks and drawing keeps in lockstep (``test_dt_pinion_lever_drawing.py``).
"""

from __future__ import annotations

from _fit_ream_slide import REAM_SLIDE
from _printed_tolerance import printed_band_mm
from dt_pinion_lever_geometry import (
    BORE as BORE,
    BORE_DEPTH as BORE_DEPTH,
    BORE_DEPTH_PLACES as BORE_DEPTH_PLACES,
    CAP_RADIUS as CAP_RADIUS,
    CAP_SAG as CAP_SAG,
    GRIP_FROM_B_PLACES as GRIP_FROM_B_PLACES,
    HUB_LEN as HUB_LEN,
    HUB_OD as HUB_OD,
    OVERALL_FROM_B as OVERALL_FROM_B,
    OVERALL_FROM_B_PLACES as OVERALL_FROM_B_PLACES,
    PIN_HOLE_DIA as PIN_HOLE_DIA,
    PIN_HOLE_FROM_MOUTH as PIN_HOLE_FROM_MOUTH,
    PIN_HOLE_Z as PIN_HOLE_Z,
    ROD_DIA as ROD_DIA,
    ROD_DIA_PLACES as ROD_DIA_PLACES,
    ROD_LEN as ROD_LEN,
    ROD_Y0 as ROD_Y0,
    WALL_T as WALL_T,
)

LIFT_ROD_NUMBER = "MHA-DT-017"

# U36: the pin carries the torque, so the hub only has to slide onto the h-band
# 6.35 lift rod.  Codex P2 (#844): the former 6.35-6.40 band's minimum met the
# rod's maximum line-to-line; REAM_SLIDE (+0.025/+0.010, the fit MHA-DT-014 and
# MHA-DT-018 hold on the same shafts) guarantees 0.010 of clearance.
BORE_BAND = REAM_SLIDE
# drawing-guidelines.md rule 17 (walls 2.0 target / 1.5 floor at the worst
# printed bands): the end wall behind the blind bore is what the two .X
# baselines from face B leave -- the overall length to the crown apex less
# the bore depth.  ENFORCE r1 (#1011) struck its former own +/-0.25 band (a
# tight band rescuing a wall, naming no mate); the deeper crown carries it.
END_WALL_ON_AXIS_WORST = (OVERALL_FROM_B - printed_band_mm(OVERALL_FROM_B_PLACES)) - (
    BORE_DEPTH + printed_band_mm(BORE_DEPTH_PLACES)
)
# Off the axis the dome falls away: at the floor's corner (the largest bore)
# it drops most on the smallest printed SR.
_CAP_R_MIN = CAP_RADIUS - printed_band_mm(1)
_FLOOR_CORNER_R = BORE / 2.0 + BORE_BAND[0]
END_WALL_AT_FLOOR_CORNER_WORST = END_WALL_ON_AXIS_WORST - (
    _CAP_R_MIN - (_CAP_R_MIN**2 - _FLOOR_CORNER_R**2) ** 0.5
)
if END_WALL_ON_AXIS_WORST < 2.0 or END_WALL_AT_FLOOR_CORNER_WORST < 1.5:
    raise AssertionError(
        f"end wall {END_WALL_ON_AXIS_WORST:.2f} on the axis, "
        f"{END_WALL_AT_FLOOR_CORNER_WORST:.2f} at the floor corner: rule 17"
    )

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarrelProfile": {"HubOd", "HubBore"},
    # The straight grip rod prints its one diameter and its 86.0 height.
    "RodProfile": {"RodTipY", "RodDia"},
    "CapProfile": {"CapR"},
    "PinHoleProfile": {"PinHoleDia"},
    # drawing-simplicity-policy.md `How the repository implements the guidelines` reference sketches: every axial station is
    # printed from face B (the flat mouth face, rule 10's one baseline), but
    # none is any feature's own dimension, so each gets a one-line
    # construction sketch whose single driving dimension IS the value.
    "GripStationReference": {"GripFromB"},
    "PinHoleStationReference": {"PinHoleFromB"},
    "BoreDepthReference": {"BoreDepthFromB"},
    "OverallLengthReference": {"OverallFromB"},
}
# All saved hidden (#880); the drawing's hub detail is created and dimensioned
# while the part shows them (_drawing_hidden_sketches.part_sketches_shown).
REFERENCE_SKETCHES = (
    "GripStationReference",
    "PinHoleStationReference",
    "BoreDepthReference",
    "OverallLengthReference",
)

# Decimal places ARE the tolerance statement (drawing-simplicity-policy.md `How the repository implements the guidelines`); the part authors
# them and the drawing reads them back.  Three on the banded bore; two on the
# grip station (the old +/-0.10 note, now the .XX row); one everywhere a
# turned or hand-finished feature is routine.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BarrelProfile": {"HubOd": 1, "HubBore": 3},
    "RodProfile": {"RodTipY": 1, "RodDia": ROD_DIA_PLACES},
    "CapProfile": {"CapR": 1},
    "PinHoleProfile": {"PinHoleDia": 2},
    "GripStationReference": {"GripFromB": GRIP_FROM_B_PLACES},
    "PinHoleStationReference": {"PinHoleFromB": 1},
    "BoreDepthReference": {"BoreDepthFromB": BORE_DEPTH_PLACES},
    "OverallLengthReference": {"OverallFromB": OVERALL_FROM_B_PLACES},
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

# drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): nothing on the lever runs or slides any more -- the pinned hub is a
# static slip fit -- so no surface carries a roughness symbol.
SURFACE_FINISHES = ()

# The match-drill requirement rides the pin hole's own callout (drawing-guidelines.md rule 7 (notes: few, flagged, never a method): matched
# fits belong on the feature).  ENFORCE r1 (#1011) struck the crown-root
# "leave sharp" note (the title-block edge break serves the crown root like
# any other edge); the one note left is the shop's inside-corner ceiling for
# the grip rod's root on the hub, owner ruling 2026-10-18 (fr-top-frame
# precedent, dt_arbor_pedestal_spec) until #1625 puts it in the title block.
# The callout is the hole specification only: the grip-parked pose and the
# drive and peen are dt_pinion_lever_pin_spec.ASSEMBLY_STEP (LEVER PIN SET).
PIN_HOLE_CALLOUT = f"MATCH-DRILL THRU AT ASSEMBLY ON {LIFT_ROD_NUMBER}"
DRAWING_NOTES = "INSIDE CORNERS R1.0 MAX."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
