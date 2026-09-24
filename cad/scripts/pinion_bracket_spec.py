r"""Pinion-swing-bracket dimensional contract -- the single source of truth shared
by the part build (``build_pinion_bracket.py``) and its manufacturing drawing
(``draw_pinion_bracket.py``).

PURE DATA, no SolidWorks/COM imports: the marked-dimension -> kept-dimension
NAME map, the decimal places the MODEL authors for each of those dimensions,
the three fitted-bore bands and the roughness controls.  Keeping this in ONE
module means a rename or a nominal change is a single edit that reaches both
scripts, so the part-side ``mark_dimensions_for_drawing`` set and the
drawing-side ``keep`` maps cannot silently drift apart.

Build-graph consequence (intended): geometry lives in
``pinion_bracket_geometry`` so the drive-train assembly can consume it without
also depending on this module's drawing-only annotation contract.

The offline lockstep test (``test_pinion_bracket_drawing.py``) asserts the part
marks and the drawing keeps EXACTLY ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

from _fit_limits import REAM_H7, REAM_SLIDE
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pinion_bracket_geometry import (
    ARBOR_BORE as ARBOR_BORE,
    C2C as C2C,
    HALF_WIDTH as HALF_WIDTH,
    OVERALL_LENGTH as OVERALL_LENGTH,
    PIN_BORE as PIN_BORE,
    PIN_DROP as PIN_DROP,
    PIN_SEAT as PIN_SEAT,
    PIVOT_BORE as PIVOT_BORE,
    R_END as R_END,
    THICKNESS as THICKNESS,
    WIDTH as WIDTH,
)
import pinion_strap_pin_spec as _strap_pin

# --- Tolerance bands.  Only the three fitted bores carry one, and each traces
# to a NAMED fit class in ``_fit_limits``; every other feature is governed by
# its decimal places against the title block's general grades.  The strap's
# former per-part numbers (a +/-0.10 bore centre distance, +/-0.05 on the seat
# axis and through-thickness station, +/-0.05 on the bar thickness and a
# +0.10/0 seat depth) traced to no fit class and to no error-budget row: they
# were habit, not specification, and are gone. ---
# Option E-a: the strap is pinned to the torque shaft, which turns with it in
# the MHA-061 block bores.  The slide fit stays so the strap goes onto the
# shaft for fit-up and the cross hole can be match-drilled through both.
PIVOT_BORE_BAND = REAM_SLIDE
ARBOR_BORE_BAND = REAM_SLIDE  # pinion arbor turns in it
# The MHA-116 drill-rod stud slips into this seat and is bonded with LOCTITE
# 638 (U27; pinion_cam_pin_spec proves the 0.000-0.042 bond gap).
PIN_SEAT_DIA_BAND = REAM_H7

# Option E-a set-pin cross hole (pinion_strap_pin_spec).  Its location is a
# functional requirement, not habit: the hole is match-drilled on into the
# MHA-062 shaft, and every bit it runs off the bore axis comes straight off
# the shaft wall beside it (SHAFT_LIGAMENT_WORST).  The print states it on the
# hole's own callout -- ON the axis, CENTRED on the thickness -- the same form
# as the follower seat's, with no dimension to hang a band on (rule 6).  Read
# against the full .XX grade the shaft wall still clears the 1.5 floor.  The
# diameter carries the spring pin's own functional band (pinion_strap_pin_spec).
CROSS_HOLE_DIA = _strap_pin.HOLE_DIA
CROSS_HOLE_BAND = _strap_pin.HOLE_BAND
CROSS_HOLE_CALLOUT = "\n".join(
    (
        "THRU ON PIVOT-BORE AXIS",
        "CENTRED ON THICKNESS",
        "SUPPLY 1/16 X 1/2 SLOTTED SPRING",
        "PIN (ASME B18.8.2) LOOSE",
    )
)
if "SUPPLY " + _strap_pin.PIN_SUPPLY + " LOOSE" != " ".join(
    CROSS_HOLE_CALLOUT.splitlines()[2:]
):
    raise AssertionError("cross-hole callout drifted from the pin spec")

# Rule 12 (#842, U27; audit W23) worst-case web from the centred blind seat to
# either broad face: half the thickness at its .X minus band, minus the seat's
# upper-limit radius and the 0.05 drilled-hole allowance.  Printed from one
# face at .XX it was 1.18; centred it clears the 2.0 target.
THICKNESS_BAND = 0.8  # Depth prints .X
PIN_SEAT_WEB_WORST = (
    (THICKNESS - THICKNESS_BAND) / 2.0
    - (PIN_BORE + PIN_SEAT_DIA_BAND[0]) / 2.0
    - 0.05
)
if PIN_SEAT_WEB_WORST < 1.5:
    raise AssertionError(
        f"follower-seat web {PIN_SEAT_WEB_WORST:.2f} is under the 1.5 floor"
    )

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_pinion_bracket`` marks exactly these; ``draw_pinion_bracket``
# keeps exactly their union across its per-view ``keep`` maps. The offline test
# enforces ``union(marks) == union(keeps)``. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StrapProfile": {
        "PivotBoreDia",
        "ArborBoreDia",
        "ArborBoreCz",
        "BottomCapRadius",
        "TopCapRadius",
    },
    "Strap": {"Depth"},
    # Rule 12 (audit W23): the seat is printed CENTRED on the bar thickness
    # (its callout says so) instead of located by a .XX station from one face,
    # so only the .X thickness band reaches the web -- see PIN_SEAT_WEB_WORST.
    "PinSeatProfile": {"PinSeatDia", "PinSeatCy"},
    "PinSeat": {"PinSeatDepth"},
    # Option E-a: the set-pin cross hole, printed ON the pivot-bore axis and
    # centred on the thickness by its callout (pinion_strap_pin_spec), so its
    # diameter is the only marked dimension.
    "CrossHoleProfile": {"CrossHoleDia"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity policy rule
# 2), so the MODEL owns them: build_pinion_bracket applies this map to the
# .SLDPRT and draw_pinion_bracket only reads it back.
#
# Three places (title-block .XXX, +/-0.13) on PinSeatCy alone: the follower
# stud's height above the pivot axis sets how far the drum swings for a given
# cam lift, and the engaged pose is budgeted with 0.25 of air -- half a
# millimetre there is twice the whole clearance.  Everything else is two
# places (.XX, +/-0.51): the bore centre distance and the bar thickness are
# routine link geometry, and the two running bores plus the pressed seat carry
# their own bands on top.  One place (.X) on the two end radii and the seat
# depth: the ends are profiled to the bar's own width and the seat bottoms out
# on a flat-bottom reamer.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "StrapProfile": {
        "PivotBoreDia": 2,
        "ArborBoreDia": 2,
        "ArborBoreCz": 2,
        "BottomCapRadius": 1,
        "TopCapRadius": 1,
    },
    "Strap": {"Depth": 1},
    "PinSeatProfile": {"PinSeatDia": 2, "PinSeatCy": 3},
    "PinSeat": {"PinSeatDepth": 1},
    # Two places resolve the spring pin's +0.06/0 hole band.
    "CrossHoleProfile": {"CrossHoleDia": 2},
}

_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
):
    raise AssertionError("DRAWING_PRECISION names a dimension the part never marks")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked dimension must state its decimal places")

# The (43.0) overall is a REFERENCE the sheet derives from the outline (C2C
# plus both end radii), not a model dimension, so no part-side map can hand
# its decimal places over: the spec owns the digit and the sheet passes it to
# ``SetPrecision3`` instead of writing a literal (policy rule 2).  One place
# because the two end radii it sums are one-place dimensions.
DRAWING_REFERENCE_PRECISION = 1


SURFACE_FINISHES = (
    SurfaceFinishControl(
        key="pivot_bore",
        roughness_um=MACHINED_UM,
        face=CylinderFace(diameter_mm=PIVOT_BORE),
    ),
    SurfaceFinishControl(
        key="arbor_bore",
        roughness_um=MACHINED_UM,
        face=CylinderFace(diameter_mm=ARBOR_BORE),
    ),
)

# No manufacturing-note block.  Everything this strap needs is a dimension, a
# hole callout, a roughness symbol or a title-block field (drawing-simplicity
# policy rule 6); the retired block restated geometry the native dimensions
# and outline already define and prescribed an unnecessary fixturing method.
DRAWING_NOTES = ""

# Brackets carry no datums and no feature-control frames (policy rule 3): the
# end-arc profile frames this sheet used to print were form control on a
# clearance outline, which no +/- on a dimension was failing to express.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {}
