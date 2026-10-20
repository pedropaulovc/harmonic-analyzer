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

import math

from _fit_ream_h7 import REAM_H7
from _fit_ream_slide import REAM_SLIDE
from _gtol_cylinder import CylinderFace
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
    WIDTH as WIDTH,
)
import vn_pinion_strap_pin_spec as _strap_pin

# --- Tolerance bands.  Only the three fitted bores carry one, and each traces
# to a NAMED fit class in ``_fit_ream_h7`` or ``_fit_ream_slide``; every other feature is governed by
# its decimal places against the title block's general grades.  The strap's
# former per-part numbers (a +/-0.10 bore centre distance, +/-0.05 on the seat
# axis and through-thickness station, +/-0.05 on the bar thickness and a
# +0.10/0 seat depth) traced to no fit class and to no error-budget row: they
# were habit, not specification, and are gone.  The one non-fit band that
# survives is PIN_SEAT_STATION_TOL below, and it traces to a web. ---
# Option E-a: the strap is pinned to the torque shaft, which turns with it in
# the MHA-DT-018 block bores.  The slide fit stays so the strap goes onto the
# shaft for fit-up and the cross hole can be match-drilled through both.
PIVOT_BORE_BAND = REAM_SLIDE
ARBOR_BORE_BAND = REAM_SLIDE  # pinion arbor turns in it
# The MHA-DT-025 drill-rod stud slips into this seat and is bonded with LOCTITE
# 638 (U27; dt_pinion_cam_pin_spec proves the 0.000-0.042 bond gap).
PIN_SEAT_DIA_BAND = REAM_H7

# Option E-a set-pin cross hole (vn_pinion_strap_pin_spec).  Its location is a
# functional requirement, not habit: the hole is match-drilled on into the
# MHA-DT-019 shaft, and every bit it runs off the bore axis comes straight off
# the shaft wall beside it (SHAFT_LIGAMENT_WORST).  Codex #858 P2, user
# ruling (a): no location lives in prose.  Through the thickness the model's
# own CrossHoleCz (half the thickness from broad face A) prints at .XX; its
# far-face web is STRAP_FACE_WEB_WORST.  Across the bar the hole's centre sits
# ON the pivot-axis line the flank view draws (where the 7.000 starts), so it
# needs no offset: the former 3.18 from the pivot-bore wall (a hidden
# reference sketch) ran to a hidden line, which rule 9 forbids (r1 machinist
# review, #1007).  The diameter carries the spring pin's own functional band
# (vn_pinion_strap_pin_spec), and the hole is drilled (rule 12).
CROSS_HOLE_DIA = _strap_pin.HOLE_DIA
CROSS_HOLE_BAND = _strap_pin.HOLE_BAND
# The pin is its own BOM line (MHA-VN-033), so the callout names it
# instead of supplying one loose with each strap; test_dt_pinion_bracket_drawing
# keeps the number in step with the parts registry.  The band is tighter than
# DRILLED HOLES, so the callout also names the fit (rule 4; r2 review): a
# slotted spring pin grips its hole by compression.
CROSS_HOLE_CALLOUT = "DRILL THRU\nFOR MHA-VN-033\nSPRING PIN, PRESS FIT"

# drawing-guidelines.md rule 17 (walls and webs) (#842, U27; audit W23) worst-case web from the blind seat to a broad
# face.  Codex #858 P2, user ruling (a) (2026-09-25): the seat's station is
# printed from broad face A as the model's own PinSeatCz, not as "CENTRED ON
# THICKNESS" prose.  At the general .XX grade that web was 1.18, under the 1.5
# floor, so the user approved tightening the station alone to +/-0.10: a
# functional band that traces to this web, not habit.  The far face then sees
# the thinnest bar (.X minus band) less the station at its upper limit, the
# seat's upper-limit radius and the 0.05 drilled-hole allowance: 1.54, over
# the 1.5 floor (the 2.0 target gives way to the printed location).  The near
# face keeps PIN_SEAT_NEAR_WEB_WORST.
# Symmetric, so the print reads +/- (ASME Y14.5), not an equal bilateral pair.
PIN_SEAT_STATION_TOL = 0.10
_PIN_SEAT_MAX = PIN_BORE + PIN_SEAT_DIA_BAND[0]
PIN_SEAT_WEB_WORST = (
    (THICKNESS - THICKNESS_BAND)
    - (THICKNESS / 2.0 + PIN_SEAT_STATION_TOL)
    - _PIN_SEAT_MAX / 2.0
    - 0.05
)
PIN_SEAT_NEAR_WEB_WORST = (
    THICKNESS / 2.0 - PIN_SEAT_STATION_TOL - _PIN_SEAT_MAX / 2.0 - 0.05
)
if PIN_SEAT_WEB_WORST < 1.5:
    raise AssertionError(
        f"follower-seat web {PIN_SEAT_WEB_WORST:.2f} is under the 1.5 floor"
    )
# The sheet states the far-face wall as a plain fact (rule 20), rounded down
# so it never claims more than the worst case: the owner-ruled shortfall
# declared as RV-01 in draw_dt_pinion_bracket.exceptions.yaml.
PIN_SEAT_WALL_CALLOUT = f"WALL {math.floor(PIN_SEAT_WEB_WORST * 10) / 10:.1f} MIN"

# The seat floor is modelled sharp; the corner allowance lets the builder pick
# a flat-bottom reamer or end mill (rule 16, r2/r3 machinist review, #1007):
# a stud bottomed on that corner stands off at most this radius, well inside
# the seat depth's .X band.  Three rows, so the block grows right, not up
# into the isometric view.
PIN_SEAT_FLOOR_CORNER_R_MAX = 0.2
PIN_SEAT_DEPTH_CALLOUT = (
    "FOLLOWER SEAT REAM DEPTH\nFROM ENTRY FACE\n"
    f"FLOOR CORNERS R{PIN_SEAT_FLOOR_CORNER_R_MAX:.1f} MAX"
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
    # face A prints as the model's own PinSeatCz at +/-0.10 -- see
    # PIN_SEAT_WEB_WORST.
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
        "BottomCapRadius": END_RADIUS_PLACES,
        "TopCapRadius": END_RADIUS_PLACES,
    },
    "Strap": {"Depth": THICKNESS_PLACES},
    # Two places on PinSeatCz resolve its +/-0.10 band.
    "PinSeatProfile": {"PinSeatDia": 2, "PinSeatCy": 3, "PinSeatCz": 2},
    "PinSeat": {"PinSeatDepth": 1},
    # Two places resolve the spring pin's +0.06/0 hole band; its station is
    # routine .XX (its worst cases clear the 1.5 floor at that grade).
    "CrossHoleProfile": {"CrossHoleDia": 2, "CrossHoleCz": CROSS_HOLE_CZ_PLACES},
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
# ``SetPrecision3`` instead of writing a literal (drawing-simplicity-policy.md `How the repository implements the guidelines`).  One place
# because the two end radii it sums are one-place dimensions.
DRAWING_REFERENCE_PRECISION = 1


# The arbor bore runs on the MHA-DT-022 arbor.  The pivot bore takes no
# symbol: the strap is pinned to the MHA-DT-019 shaft (option E-a), so nothing
# runs in it (rule 6; r1 machinist review, #1007).
SURFACE_FINISHES = (
    SurfaceFinishControl(
        key="arbor_bore",
        roughness_um=MACHINED_UM,
        face=CylinderFace(diameter_mm=ARBOR_BORE),
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
