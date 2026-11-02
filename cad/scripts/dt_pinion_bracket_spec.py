r"""Pinion-swing-bracket dimensional contract -- the single source of truth shared
by the part build (``build_dt_pinion_bracket.py``) and its manufacturing drawing
(``draw_dt_pinion_bracket.py``).

PURE DATA, no SolidWorks/COM imports: the marked-dimension -> kept-dimension
NAME map, the decimal places the MODEL authors for each of those dimensions,
the three fitted-bore bands and the roughness controls.  Keeping this in ONE
module means a rename or a nominal change is a single edit that reaches both
scripts, so the part-side ``mark_dimensions_for_drawing`` set and the
drawing-side ``keep`` maps cannot silently drift apart.

Build-graph consequence (intended): geometry lives in
``dt_pinion_bracket_geometry`` so the drive-train assembly can consume it without
also depending on this module's drawing-only annotation contract.

The offline lockstep test (``test_dt_pinion_bracket_drawing.py``) asserts the part
marks and the drawing keeps EXACTLY ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

from _fit_ream_h7 import REAM_H7
from _fit_ream_slide import REAM_SLIDE
from _gtol_cylinder import CylinderFace
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import printed_deviations
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from dt_pinion_bracket_geometry import (
    ARBOR_BORE as ARBOR_BORE,
    C2C as C2C,
    CROSS_HOLE_CZ_PLACES,
    END_RADIUS_PLACES,
    HALF_WIDTH as HALF_WIDTH,
    OVERALL_LENGTH as OVERALL_LENGTH,
    PIN_BORE as PIN_BORE,
    PIN_DROP as PIN_DROP,
    PIN_SEAT as PIN_SEAT,
    PIVOT_BORE as PIVOT_BORE,
    R_END as R_END,
    THICKNESS as THICKNESS,
    THICKNESS_BAND as THICKNESS_BAND,
    THICKNESS_PLACES,
    UNIT as UNIT,
    WIDTH as WIDTH,
)
import dt_vn_pinion_strap_pin_spec as _strap_pin

# --- Tolerance bands.  Only the three fitted bores and the cross hole carry
# one, and each traces to a NAMED fit class in ``_fit_ream_h7`` or
# ``_fit_ream_slide`` or to the spring pin's own window; every other feature is
# governed by its decimal places against the title block's general grades.
# The strap's former per-part numbers (a +/-0.10 bore centre distance, +/-0.05
# on the seat axis and through-thickness station, +/-0.05 on the bar thickness
# and a +0.10/0 seat depth) traced to no fit class and to no error-budget row:
# they were habit, not specification, and are gone. ---
# Option E-a: the strap is pinned to the torque shaft, which turns with it in
# the MHA-DT-18 block bores.  The slide fit stays so the strap goes onto the
# shaft for fit-up and the cross hole can be match-drilled through both.
PIVOT_BORE_BAND = REAM_SLIDE
ARBOR_BORE_BAND = REAM_SLIDE  # pinion arbor turns in it
# The MHA-DT-25 5/32 drill-rod stud slips into this seat, cut by the .1570
# chucking reamer, and is bonded with LOCTITE 638 (U27; dt_pinion_cam_pin_spec
# proves the bond gap).
PIN_SEAT_DIA_BAND = REAM_H7

# Option E-a set-pin cross hole (dt_vn_pinion_strap_pin_spec).  Its location is a
# functional requirement, not habit: the hole is match-drilled on into the
# MHA-DT-19 shaft, and every bit it runs off the bore axis comes straight off
# the shaft wall beside it (SHAFT_LIGAMENT_WORST).  Codex #858 P2, user
# ruling (a): no location lives in prose.  Through the thickness the model's
# own CrossHoleCz (half the thickness from broad face A) prints at .XX; its
# far-face web is STRAP_FACE_WEB_WORST.  Across the bar the hole's centre sits
# ON the pivot-axis line the flank view draws (where the 7.000 starts), so it
# needs no offset: the former 3.18 from the pivot-bore wall (a hidden
# reference sketch) ran to a hidden line, which rule 9 forbids (r1 machinist
# review, #1007).  The diameter carries the spring pin's own functional band
# (dt_vn_pinion_strap_pin_spec), and the hole is drilled (rule 12).
CROSS_HOLE_DIA = _strap_pin.HOLE_DIA
CROSS_HOLE_BAND = _strap_pin.HOLE_BAND
# The pin is its own BOM line (MHA-DT-VN-63), so the callout names it
# instead of supplying one loose with each strap; test_dt_pinion_bracket_drawing
# keeps the number in step with the parts registry.  The band is tighter than
# DRILLED HOLES, so the callout also names the fit (rule 4; r2 review): a
# slotted spring pin grips its hole by compression.
CROSS_HOLE_CALLOUT = "DRILL THRU\nFOR MHA-DT-VN-63\nSPRING PIN, PRESS FIT"

# drawing-guidelines.md rule 17 (walls and webs) (#842, U27; audit W23) worst-case web from the blind seat to a broad
# face.  Codex #858 P2, user ruling (a) (2026-09-25): the seat's station is
# printed from broad face A as the model's own PinSeatCz, not as "CENTRED ON
# THICKNESS" prose.  #290: at the .XXX thickness and station rows the far face
# sees the thinnest bar less the station at its upper limit, the seat's
# upper-limit radius and the 0.05 drilled-hole allowance, over the .080 in
# target, so the station needs no band of its own (the mm sheet's +/-0.10 and
# owner-minor RV-01 are gone).
_SEAT_STATION_LOWER, _SEAT_STATION_UPPER = printed_deviations(
    THICKNESS / 2.0, 3, unit=UNIT
)
_THICKNESS_LOWER = printed_deviations(THICKNESS, THICKNESS_PLACES, unit=UNIT)[0]
_PIN_SEAT_MAX = PIN_BORE + PIN_SEAT_DIA_BAND[0]
PIN_SEAT_WEB_WORST = (
    (THICKNESS + _THICKNESS_LOWER)
    - (THICKNESS / 2.0 + _SEAT_STATION_UPPER)
    - _PIN_SEAT_MAX / 2.0
    - 0.05
)
PIN_SEAT_NEAR_WEB_WORST = (
    THICKNESS / 2.0 + _SEAT_STATION_LOWER - _PIN_SEAT_MAX / 2.0 - 0.05
)
if min(PIN_SEAT_WEB_WORST, PIN_SEAT_NEAR_WEB_WORST) < WALL_TARGET_MM:
    raise AssertionError(
        f"follower-seat web {PIN_SEAT_WEB_WORST:.3f} is under the .080 in target"
    )

# The seat floor is modelled sharp; the corner allowance lets the builder pick
# a flat-bottom reamer or end mill (rule 16, r2/r3 machinist review, #1007):
# a stud bottomed on that corner stands off at most this radius, well inside
# the seat depth's .XX band.  Three rows, so the block grows right, not up
# into the isometric view.
PIN_SEAT_FLOOR_CORNER_R_MAX = 0.2032  # .008
PIN_SEAT_DEPTH_CALLOUT = (
    "FOLLOWER SEAT REAM DEPTH\nFROM ENTRY FACE\nFLOOR CORNERS R.008 MAX"
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_dt_pinion_bracket`` marks exactly these; ``draw_dt_pinion_bracket``
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
    # drawing-guidelines.md rule 17 (walls and webs) (audit W23) and user ruling (a): the seat's station from broad
    # face A prints as the model's own PinSeatCz -- see PIN_SEAT_WEB_WORST.
    "PinSeatProfile": {"PinSeatDia", "PinSeatCy", "PinSeatCz"},
    "PinSeat": {"PinSeatDepth"},
    # Option E-a: the set-pin cross hole.  Its size and its station from
    # broad face A (Codex #858 P2); its centre sits on the pivot-axis line.
    "CrossHoleProfile": {"CrossHoleDia", "CrossHoleCz"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity-policy.md `How the repository implements the guidelines`
# ), so the MODEL owns them: build_dt_pinion_bracket applies this map to the
# .SLDPRT and draw_dt_pinion_bracket only reads it back.
#
# #290 inch sheet.  Four places on the three reamed bores and the cross hole,
# whose +.0015/+.0010, +.0005/.0000 and +.0025/.0000 bands need them.  Three
# (.XXX, +/-.005) where a stack or web reads the row, each naming its function
# at the dimension: PinSeatCy (the follower stud's height above the pivot sets
# how far the drum swings for a given cam lift), the bar thickness (the axial
# stack between the MHA-DT-18 blocks) and the seat's station (its far-face web
# fails at .XX).  Two (.XX) on the rest: the bore centre distance (no check
# reads its band; at the engaged pose a .010 error moves the mesh centre a
# quarter of that), the unmated end radii, the cross hole's station and the
# seat depth, which a flat-bottom reamer bottoms out.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "StrapProfile": {
        "PivotBoreDia": 4,
        "ArborBoreDia": 4,
        "ArborBoreCz": 2,
        "BottomCapRadius": END_RADIUS_PLACES,
        "TopCapRadius": END_RADIUS_PLACES,
    },
    "Strap": {"Depth": THICKNESS_PLACES},
    "PinSeatProfile": {"PinSeatDia": 4, "PinSeatCy": 3, "PinSeatCz": 3},
    "PinSeat": {"PinSeatDepth": 2},
    "CrossHoleProfile": {"CrossHoleDia": 4, "CrossHoleCz": CROSS_HOLE_CZ_PLACES},
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

# The (1.7) overall is a REFERENCE the sheet derives from the outline (C2C
# plus both end radii), not a model dimension, so no part-side map can hand
# its decimal places over: the spec owns the digit and the sheet passes it to
# ``SetPrecision3`` instead of writing a literal (drawing-simplicity-policy.md `How the repository implements the guidelines`).  One
# place: the printed 1.10 + 2 x .30 sums to 1.70, which (1.69) would contradict.
DRAWING_REFERENCE_PRECISION = 1


# The arbor bore runs on the MHA-DT-22 arbor.  The pivot bore takes no
# symbol: the strap is pinned to the MHA-DT-19 shaft (option E-a), so nothing
# runs in it (rule 6; r1 machinist review, #1007).
SURFACE_FINISHES = (
    SurfaceFinishControl(
        key="arbor_bore",
        roughness_um=MACHINED_UM,
        face=CylinderFace(diameter_mm=ARBOR_BORE),
        display_unit=UNIT,
    ),
)

# No manufacturing-note block.  Everything this strap needs is a dimension, a
# hole callout, a roughness symbol or a title-block field (drawing-simplicity
# drawing-guidelines.md rule 7 (notes: few, flagged, never a method)); the retired block restated geometry the native dimensions
# and outline already define and prescribed an unnecessary fixturing method.
DRAWING_NOTES = ""

# Brackets carry no datums and no feature-control frames (drawing-guidelines.md rule 5 (avoid excessive GD&T)): the
# end-arc profile frames this sheet used to print were form control on a
# clearance outline, which no +/- on a dimension was failing to express.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {}
