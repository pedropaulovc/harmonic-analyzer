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
    CAM_RELIEF_RADIUS as CAM_RELIEF_RADIUS,
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

# --- Tolerance bands.  Only the three fitted bores carry one, and each traces
# to a NAMED fit class in ``_fit_limits``; every other feature is governed by
# its decimal places against the title block's general grades.  The strap's
# former per-part numbers (a +/-0.10 bore centre distance, +/-0.05 on the seat
# axis and through-thickness station, +/-0.05 on the bar thickness and a
# +0.10/0 seat depth) traced to no fit class and to no error-budget row: they
# were habit, not specification, and are gone. ---
PIVOT_BORE_BAND = REAM_SLIDE  # torque shaft turns in it
ARBOR_BORE_BAND = REAM_SLIDE  # pinion arbor turns in it
PIN_SEAT_DIA_BAND = REAM_H7  # follower stud is pressed into it

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
    # The cam-clearance scallops are two plunges of one cutter: each centre
    # from the pivot-bore axis, each carrying the cutter radius (both radii
    # are driven by one equation global, so they cannot drift apart).
    "CamReliefParkProfile": {"CamReliefParkX", "CamReliefParkY", "CamReliefParkR"},
    "CamReliefEngagedProfile": {
        "CamReliefEngagedX",
        "CamReliefEngagedY",
        "CamReliefEngagedR",
    },
    # PinSeatCz locates the blind follower seat THROUGH the bar thickness, so
    # the seat is fully located rather than merely drawn centred.
    "PinSeatProfile": {"PinSeatDia", "PinSeatCy", "PinSeatCz"},
    "PinSeat": {"PinSeatDepth"},
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
# routine link geometry, the scallops are clearance, and the two running
# bores plus the pressed seat carry their own bands on top.  One place (.X)
# on the two end radii and the seat depth: the ends are profiled to the bar's
# own width and the seat bottoms out on a flat-bottom reamer.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "StrapProfile": {
        "PivotBoreDia": 2,
        "ArborBoreDia": 2,
        "ArborBoreCz": 2,
        "BottomCapRadius": 1,
        "TopCapRadius": 1,
    },
    "Strap": {"Depth": 1},
    "CamReliefParkProfile": {
        "CamReliefParkX": 2,
        "CamReliefParkY": 2,
        "CamReliefParkR": 2,
    },
    "CamReliefEngagedProfile": {
        "CamReliefEngagedX": 2,
        "CamReliefEngagedY": 2,
        "CamReliefEngagedR": 2,
    },
    "PinSeatProfile": {"PinSeatDia": 2, "PinSeatCy": 3, "PinSeatCz": 2},
    "PinSeat": {"PinSeatDepth": 1},
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
# policy rule 6); the retired block restated the profile the outline already
# draws, prescribed a fixturing method, and repeated the ligament the
# dimensioned scallop centres already guarantee.
DRAWING_NOTES = ""

# Brackets carry no datums and no feature-control frames (policy rule 3): the
# end-arc profile frames this sheet used to print were form control on a
# clearance outline, which no +/- on a dimension was failing to express.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {}
