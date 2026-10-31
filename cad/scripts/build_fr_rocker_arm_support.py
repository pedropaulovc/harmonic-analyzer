r"""Reproduction script: rocker-arm support (manual feature-tree replay).

Feature-tree replay of ``fr-rocker-arm-support.SLDPRT`` with stock-compatible
hold-down clearance holes: a thin-walled cast bracket with a trapezoidal wedge
wall (wide foot, narrow top) stood **Y-up**, lightened by a window that
opens on the two big front/back faces, with a mounting foot drilled for four
top-down hex-head screws, the window rim broken by a fillet + chamfer, and a
top face tapped for the rocker pivot brackets' hold-down screws.

The part is oriented to match the source SLDPRT's standard views: the **Front**
view (along Z) looks square-on at the rounded window; the **Right** view (along
X) shows the trapezoid taper; the **Top** view (along Y) shows the two channels,
the central web, and the four foot holes.

The original is hand-built; this rebuilds it feature-for-feature, matching the
source's tree STRUCTURE and sketch construction but with SEMANTIC feature names
(the convention of the other tracked parts) rather than the source's generic
auto-names. The tree is Wall (``Boss-Extrude1``) -> CavityCut/WindowCut1/
WindowCut2 (``Cut-Extrude2/3/4``) -> CornerFillet (``Fillet3``) ->
PocketCornerFillet -> PocketFloorFillet -> FootClearanceHoles (5/16 DRILL
THRU, HoleWzd) -> RimChamfer (``Chamfer2``) -> BracketSeats (#743, HoleWzd)
-> SeatStationReference/CavityLocationReference/WebLocationReference (hidden
drawing-reference sketches). The trapezoid lives
on the **Right plane** (sketch-x -> model Z taper, sketch-y -> model Y height,
mid-plane extrude along X); the window/cavity cuts use SINGLE origin-centred
squares on the **Front plane** (matching the source's window/cavity sketches).
The source casting's per-stage ``volume_check`` targets were native SolidWorks
measurements; the thicker web adds exact analytic deltas to them (see the
volume-target block), and the hole, chamfer and seat targets are analytic
expectations, all within the original 200 mm³ check tolerance.

Geometry (mm), source casting with the corrected top-down hold-down interface
(model frame: X = extrude/width, Y = height with the wide foot at Y=-88.9,
Z = wall thickness):

* **Wall** -- trapezoid, wide foot ``Z ±31.75`` at ``Y=-88.9`` tapering to
  ``Z ±8.382`` (.330) at ``Y=+88.9``; mid-plane extrude 180.4924 (7.106,
  ``X ±90.2462``): the source's 177.8, widened .053 an end for the pivot
  brackets' feet (``fr_rocker_arm_support_spec.SUPPORT_HALF_MACHINE_Z``).
* **CavityCut** -- 127 mm cavity square (``±63.5``), Through-All-Both -> the
  central cavity, leaving 6.35 mm shell walls (whole ``CavityProfile``).
* **WindowCut1 / WindowCut2** -- ONE shared 165.1 mm window square
  (``WindowProfile``, ``±82.55``), so the top rail is the source's 6.35, as
  deep as the side posts and the foot. Each cut is a Through-All that STARTS
  ``WEB`` (6.35) off the sketch plane in the opposite direction (forward /
  reverse, the second re-selecting ``WindowProfile`` -> a shared-sketch
  reference), so the 2*WEB band between them survives as the central web --
  the source's ``FromOffsetDistance`` / ``ReverseDirection`` pair, reproducing
  the two-sketches-feed-three-cuts tree. The web is 12.70 (1/2 in), uniform
  along the length and symmetric about the centre plane, up from the source's
  6.35, to carry the bracket seats (owner Q13c, 2026-10-16).
* **CornerFillet** -- R12.7 on the four cavity corner edges.
* **PocketCornerFillet** -- R6.35 on the four corners of each opposed pocket.
* **PocketFloorFillet** -- R0.8 around each pocket's floor-to-wall corner,
  inside the title block's ``INSIDE CORNERS R.040 MAX`` (no local callout).
* **FootClearanceHoles** -- a single Hole Wizard (``HoleWzd``) feature, 4x
  5/16 in clearance drills through the 6.35 mm foot from its top seat
  (Y=-82.55) at ``(X ±60.325, Z ±17.4498)`` (2.375, .687). One feature carries all four
  placement points; the visible 1/4-20 hex-head screws install from the top
  into through-tapped seats in the harmonic base.
* **RimChamfer** -- .05 / 45° on the 12 inner-frame opening edges, the +X
  end face's foot and top edges, the two slant faces, the -X end face, and one
  fillet face, with tangent propagation -- i.e. the whole window rim and all
  twelve outside edges.
* **BracketSeats** -- one Hole Wizard feature, 2x #8-32 bottoming-tapped seats
  down from the top face on the centreline, under the MHA-CH-08 pivot
  brackets' hold-down holes, each over a window side edge: the post outboard,
  the web inboard (``rocker_bracket_seat_layout`` owns their stack; the print
  transfers them from the set brackets at assembly).
* **SeatStationReference** -- a blanked Top-plane sketch of two construction
  lines, each end face to its seat's centre, whose dimensions VIEW B prints as
  REF (the transfer stays the method; the REF says where the seats land).
* **CavityLocationReference** / **WebLocationReference** -- blanked Front- and
  Right-plane sketches of construction chords on drawn edges, whose dimensions
  locate the cavity and the pockets from the -X end face and the top face (the
  front view), and the web from the base's edge and each top-flat edge from
  its nearer web face (section A-A; owner Q13d).

Like the 71 tracked parts, this is **equation-driven and self-naming**: eight
equation-manager globals (``FootHalf``/``TopHalf``/``HalfHeight``/``CavHalf``/
``WindowOuter``/``WallWidth``, plus the seats' ``SeatEastX``/``SeatWestX``,
all ``mm``) drive every profile sketch's dimensions, the seats' Hole Wizard
placements, their REF stations and the drawing's locations (named e.g.
``WallHeight@WallProfile``, ``WinWidth@WindowProfile``), the sketches and
features carry stable names, and the drive equations are applied in one deferred
batch after a rebuild. A final "equations neutral" ``volume_check`` proves the
driving did not move the geometry, so a GUI edit to a global reshapes the part
and round-trips. See ``build_fr_top_frame.py`` for the reference pattern.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_fr_rocker_arm_support.py
"""

from __future__ import annotations

import math
import sys
from typing import NamedTuple

from _appearance import CASTING_GREEN, apply_color, apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _document_units import apply_package_model_units
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_polygon_chain
from _sketch_rectangle import define_centered_rectangle
from _holes import blind_hole_volume_mm3, wizard_holes
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _hole_spec import blind_cut_dia_mm
from _part_pmi import author_part_pmi
from fr_rocker_arm_support_drawing_spec import SURFACE_FINISHES
from fr_rocker_arm_support_section_spec import (
    BIG,
    FOOT_THICKNESS,
    HALF_Y,
    NARROW,
    WIDE,
)
from fr_rocker_arm_support_spec import (
    HOLD_DOWN_LOCAL_HALF_X,
    HOLD_DOWN_LOCAL_HALF_Z,
    HOLE_DIA,
    HOLE_SPEC,
    SUPPORT_HALF_MACHINE_Z,
)
from rocker_bracket_seat_layout import (
    SEAT_LOCAL_X,
    SEAT_SPEC,
    TOP_FLAT_EDGE_FROM_WEB,
    TOP_FLAT_PLACES,
    WEB,
    WEB_PLACES,
)

PART_NAME = "fr-rocker-arm-support"
# The source repro was authored in steel, but this casting is now the machine's
# green rocker-arm-support (it replaced rocker-arm-portal): match the other cast
# structure (harmonic-base, top-frame) and the registry row (Gray Cast Iron,
# materials.yaml casting_green_parts) so it renders green, not steel-grey.
MATERIAL = "Gray Cast Iron"

# Trapezoid (Sketch1) -- wide foot / narrow top: WIDE / NARROW / HALF_Y, the
# window half BIG and the FOOT_THICKNESS they leave are
# fr_rocker_arm_support_section_spec's (pure data, so the base, frame, drive
# train and drawing spec read them without importing this COM script). On the
# Right plane: sketch-x -> model Z (taper), sketch-y -> model Y (height).
BOSS_DEPTH = 2.0 * SUPPORT_HALF_MACHINE_Z  # mid-plane extrude along X (180.4924, 7.106)
# The source casting's length. The window and the cavity cut through the
# wall's thickness inside the side posts, so the longer wall only thickens
# both posts: every stage's measured volume gains the trapezoid's area times
# the added length, and no cut or edge treatment changes.
SOURCE_BOSS_DEPTH = 177.8
WALL_GROWTH_VOLUME = (WIDE + NARROW) * 2.0 * HALF_Y * (BOSS_DEPTH - SOURCE_BOSS_DEPTH)
SOURCE_WALL_VOLUME = 1_271_363
SOURCE_CAVITY_CUT_VOLUME = 622_708
# The source's top half-width. NARROW now puts each top-flat edge .080 off
# its web face (TOP_FLAT_EDGE_FROM_WEB), so each stage's measured volume over
# the source length also moves by exact analytic terms: the trapezoid's area
# by TAPER_DELTA * 2 * HALF_Y, and each through cut over a region symmetric in
# Y removes TAPER_DELTA * its area from each face half on average (the slant
# faces move by TAPER_DELTA * (y + HALF_Y) / (2 * HALF_Y)).
SOURCE_NARROW = 8.4665
TAPER_DELTA = NARROW - SOURCE_NARROW
TAPER_WALL_VOLUME = TAPER_DELTA * 2.0 * HALF_Y * SOURCE_BOSS_DEPTH

CAV = 63.5  # 127 mm square half (Cut-Extrude2)
# The window is the source's 165.1 square (half BIG), its edges FOOT_THICKNESS
# inside the foot and top faces. WEB, the window cuts' start offset (the
# 2*WEB band left as the web), is rocker_bracket_seat_layout's: the seats'
# thread walls ride on it. The source casting's was SOURCE_WEB.
SOURCE_WEB = 3.175

FILLET_R = 12.7
FILLET_EDGES = [  # four inner-frame corner edges (run along Z through the web)
    [63.5, 63.5, 0.0],
    [-63.5, 63.5, 0.0],
    [63.5, -63.5, 0.0],
    [-63.5, -63.5, 0.0],
]
POCKET_FILLET_R = 6.35


def _wall_half_z_at(y_mm: float) -> float:
    fraction = (y_mm + HALF_Y) / (2.0 * HALF_Y)
    return WIDE + (NARROW - WIDE) * fraction


POCKET_FILLET_EDGES = [
    [
        x_sign * BIG,
        y_sign * BIG,
        face_sign * (WEB + _wall_half_z_at(y_sign * BIG)) / 2.0,
    ]
    for x_sign in (-1, 1)
    for y_sign in (-1, 1)
    for face_sign in (-1, 1)
]

# Volume targets. The source casting's (square window, 6.35 web) are native
# SolidWorks measurements; the thicker web's are those plus exact analytic
# deltas (WEB_GROWTH a face), so the first build re-proves them:
# * each window cut leaves the pocket WEB_GROWTH shallower over the window
#   less the through cavity (the cuts' net area, the same at every depth);
# * the cavity's four corner edges run through the web, so CornerFillet's
#   R12.7 spandrels ((1 - pi/4) R^2) grow by 2 * WEB_GROWTH each;
# * each of the eight pocket-corner edges starts at a web face, so its R6.35
#   spandrel loses WEB_GROWTH (the web face is square to the edge).
# The TAPER_* terms carry NARROW's move from SOURCE_NARROW the same way: the
# cavity and each window cut remove their region's thickness change, and the
# eight pocket-corner edges (four high, four low: their slant-face ends move
# by TAPER_DELTA in sum per pair) shorten their R6.35 spandrels.
SQUARE_WINDOW_CUT1_VOLUME = 434_257
SQUARE_WINDOW_CUT2_VOLUME = 245_806
SQUARE_CORNER_FILLET_VOLUME = 246_685
SQUARE_POCKET_FILLET_VOLUME = 247_860
SQUARE_RIM_CHAMFER_REMOVAL = 3_153
WEB_GROWTH = WEB - SOURCE_WEB  # 3.175
WINDOW_NET_AREA = (2.0 * BIG) ** 2 - (2.0 * CAV) ** 2
WEB_BAND_VOLUME = WINDOW_NET_AREA * WEB_GROWTH  # left per window cut
CORNER_FILLET_GROWTH = 4.0 * (1.0 - math.pi / 4.0) * FILLET_R**2 * 2.0 * WEB_GROWTH
POCKET_FILLET_LOSS = 8.0 * (1.0 - math.pi / 4.0) * POCKET_FILLET_R**2 * WEB_GROWTH
TAPER_CAVITY_VOLUME = TAPER_WALL_VOLUME - TAPER_DELTA * (2.0 * CAV) ** 2
TAPER_WINDOW_CUT1_VOLUME = TAPER_CAVITY_VOLUME - TAPER_DELTA * WINDOW_NET_AREA / 2.0
TAPER_WINDOW_CUT2_VOLUME = TAPER_CAVITY_VOLUME - TAPER_DELTA * WINDOW_NET_AREA
TAPER_POCKET_FILLET_GROWTH = -4.0 * (1.0 - math.pi / 4.0) * POCKET_FILLET_R**2 * TAPER_DELTA
WALL_VOLUME = SOURCE_WALL_VOLUME + WALL_GROWTH_VOLUME + TAPER_WALL_VOLUME
CAVITY_CUT_VOLUME = SOURCE_CAVITY_CUT_VOLUME + WALL_GROWTH_VOLUME + TAPER_CAVITY_VOLUME
WINDOW_CUT1_VOLUME = (
    SQUARE_WINDOW_CUT1_VOLUME + WEB_BAND_VOLUME + WALL_GROWTH_VOLUME
    + TAPER_WINDOW_CUT1_VOLUME
)
WINDOW_CUT2_VOLUME = (
    SQUARE_WINDOW_CUT2_VOLUME + 2.0 * WEB_BAND_VOLUME + WALL_GROWTH_VOLUME
    + TAPER_WINDOW_CUT2_VOLUME
)
CORNER_FILLET_VOLUME = (
    SQUARE_CORNER_FILLET_VOLUME
    + 2.0 * WEB_BAND_VOLUME
    + CORNER_FILLET_GROWTH
    + WALL_GROWTH_VOLUME
    + TAPER_WINDOW_CUT2_VOLUME
)
POCKET_FILLET_VOLUME = (
    SQUARE_POCKET_FILLET_VOLUME
    + 2.0 * WEB_BAND_VOLUME
    + CORNER_FILLET_GROWTH
    - POCKET_FILLET_LOSS
    + WALL_GROWTH_VOLUME
    + TAPER_WINDOW_CUT2_VOLUME
    + TAPER_POCKET_FILLET_GROWTH
)

# PocketFloorFillet: each pocket's floor (the web face) meets its four walls
# and four R6.35 corners in one tangent loop. The r7 machinist review asked
# what that corner may be; the title block's INSIDE CORNERS R.040 MAX answers
# it, so the sheet prints no local limit (ENFORCE review 2026-10-23: a bespoke
# R0.8 MAX named no mate or function, drawing-guidelines rule 2). R0.8 is the
# modelled corner within that band. Its spandrel
# ((1 - pi/4) R^2) runs the four straight walls and, by Pappus, the four
# corner quarter-turns at the R6.35 wall radius less the spandrel's centroid
# offset R (10 - 3 pi) / (3 (4 - pi)). The fillet sits at |Z| >= WEB, clear
# of the seats (thread inside the web) and of the clearance holes' heads.
POCKET_FLOOR_R = 0.8
# One point per pocket on its top-rail floor edge (Z = +WEB first);
# tangent propagation takes the rest of each loop.
POCKET_FLOOR_FILLET_EDGES = [[0.0, BIG, WEB], [0.0, BIG, -WEB]]
_FLOOR_SPANDREL = (1.0 - math.pi / 4.0) * POCKET_FLOOR_R**2
_FLOOR_CENTROID = POCKET_FLOOR_R * (10.0 - 3.0 * math.pi) / (3.0 * (4.0 - math.pi))
POCKET_FLOOR_FILLET_GROWTH = (
    2.0
    * _FLOOR_SPANDREL
    * (
        4.0 * (2.0 * BIG - 2.0 * POCKET_FILLET_R)
        + 2.0 * math.pi * (POCKET_FILLET_R - _FLOOR_CENTROID)
    )
)
POCKET_FLOOR_FILLET_VOLUME = POCKET_FILLET_VOLUME + POCKET_FLOOR_FILLET_GROWTH

HOLES = [
    (sx * HOLD_DOWN_LOCAL_HALF_X, sz * HOLD_DOWN_LOCAL_HALF_Z)
    for sz in (1, -1)
    for sx in (1, -1)
]

# The manufacturing print's dimension set (draw_fr_rocker_arm_support.py imports
# exactly these marked dimensions; its keep maps must stay in lockstep).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    # Each top-flat edge prints off its nearer web face (WebLocationReference,
    # owner Q13d), so the profile's TaperRun and TopSpan stay off the print.
    "WallProfile": {"FootSpan", "WallHeight"},
    "Wall": {"Depth"},
    # A single associative size plus an SQ callout defines each square.
    "WindowProfile": {"WinWidth"},
    "CavityProfile": {"CavWidth"},
    "CornerFillet": {"CavityRadius"},
    "PocketCornerFillet": {"PocketRadius"},
    "RimChamfer": {"RimChamferSize"},
    "SeatStationReference": {"SeatEastStation", "SeatWestStation"},
    "CavityLocationReference": {
        "CavityEndStation",
        "CavityTopStation",
        "PocketEndStation",
        "PocketBottomStation",
    },
    # The section is symmetric about the web: one top-flat edge prints, its
    # BOTH SIDES covering the other (r6 review); TopFlatMinusZStation stays
    # in the sketch, unprinted.
    "WebLocationReference": {
        "WebFaceStation",
        "TopFlatPlusZStation",
    },
}

# Decimal places the PART owns (drawing-simplicity-policy.md: the model owns
# tolerance and precision; the drawing imports the dimension verbatim and only
# reads its places back).
# A chamfer never needs extra places (drawing-guidelines.md rule 3): no stack
# reads RimChamferSize, so .05 prints on the .XX band (no .X on a cut feature).
RIM_CHAMFER_PLACES = 2
# The seats' REF stations off the end faces print .XXX: they follow the
# MHA-CH-08 seat stations (rocker_bracket_seat_layout), which flow through
# from the channel and may sit off the .001 grid.
SEAT_STATION_PLACES = 3
# The cavity's and the pocket's end locations come off the 7.106 length's
# half (3.553) and sit on the .001 grid (1.053, .303), so they print .XXX; the
# top and bottom locations, the web's location across the base and each
# top-flat edge off its nearer web face are .XX (1.00, .25, 1.00, .08). The
# bracket feet stand on the flat and the transferred seats follow them, so
# the flat holds the seats' threads clear of the web's faces (owner Q13d,
# rocker_bracket_seat_layout's web-wall stack).
END_LOCATION_PLACES = 3
HEIGHT_LOCATION_PLACES = 2
SECTION_LOCATION_PLACES = WEB_PLACES
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RimChamfer": {"RimChamferSize": RIM_CHAMFER_PLACES},
    "SeatStationReference": {
        "SeatEastStation": SEAT_STATION_PLACES,
        "SeatWestStation": SEAT_STATION_PLACES,
    },
    "CavityLocationReference": {
        "CavityEndStation": END_LOCATION_PLACES,
        "CavityTopStation": HEIGHT_LOCATION_PLACES,
        "PocketEndStation": END_LOCATION_PLACES,
        "PocketBottomStation": HEIGHT_LOCATION_PLACES,
    },
    "WebLocationReference": {
        "WebFaceStation": SECTION_LOCATION_PLACES,
        "TopFlatPlusZStation": TOP_FLAT_PLACES,
    },
}

# The seats' REF stations (r7 machinist review: the seats print with no
# location, and read as crowding the end wall). Two construction lines on the
# Top plane (sketch x = model X, sketch y = model -Z), on the centreline, each
# from an end face to its seat's centre, so VIEW B shows the end-wall stock
# the seat leaves. The part saves the sketch blanked; VIEW B shows it through
# the hidden-owner import.
#
# Both ends of each line follow the model (PR #1469 round-3 review: with an
# undriven length, 178.8 -> 180.8 on WallWidth kept the east REF at 4.95
# while the seat stood 5.95 in). The end face is "WallWidth" / 2 off the
# centre plane; the seat is its own global, the one its BracketSeats
# placement dimension is driven by; the station is their difference. Both
# globals are unsigned, as the placement distance is: each point keeps the
# side it was authored on, and each station measures from the end face on
# that same side.
REFERENCE_SKETCHES = (
    "SeatStationReference",
    "CavityLocationReference",
    "WebLocationReference",
)


class SeatStation(NamedTuple):
    """One REF station: its sketch dimension, the end face's and the seat's
    model X, the seat's global and the placement dimension it drives."""

    dimension: str
    end_x: float
    seat_x: float
    seat_global: str
    placement: str


SEAT_STATION_LINES = (
    SeatStation(
        "SeatEastStation",
        BOSS_DEPTH / 2.0,
        max(SEAT_LOCAL_X),
        "SeatEastX",
        "SeatEastCx",
    ),
    SeatStation(
        "SeatWestStation",
        -BOSS_DEPTH / 2.0,
        min(SEAT_LOCAL_X),
        "SeatWestX",
        "SeatWestCx",
    ),
)
if any(
    row.end_x * row.seat_x <= 0.0 or abs(row.seat_x) >= abs(row.end_x)
    for row in SEAT_STATION_LINES
):
    raise AssertionError("a seat REF station's drive needs the seat inboard of its end")
END_FACE_DRIVE = '"WallWidth" / 2'
SEAT_GLOBALS = {row.seat_global: abs(row.seat_x) for row in SEAT_STATION_LINES}
SEAT_STATION_DRIVES = {
    row.dimension: f'{END_FACE_DRIVE} - "{row.seat_global}"'
    for row in SEAT_STATION_LINES
}

# The cavity's, the pockets' and the web's locations (PR #1469 r4 machinist
# review: the 127.0 SQ cavity and the 165.1 SQ pockets printed with no
# position, and section A-A placed neither the 9.53 web nor the 16.9 top
# face across the 63.5 base; owner ruling 2026-10-16, rule 10: dimension
# from a real feature); nothing models them, so two blanked reference
# sketches do, each printed location one driving dimension:
# * CavityLocationReference (Front plane, sketch (u, v) = model (X, Y)): the
#   -X end face to the cavity's and to the pocket's side wall, the top face
#   down to the cavity's top wall, and the bottom (mounting) face up to the
#   pocket's bottom wall (r6 review: the pocket had no vertical location);
# * WebLocationReference (Right plane, sketch (u, v) = model (-Z, Y)): the
#   base's -Z edge to the web's -Z face, and each web face out to the top
#   flat's edge on its side (owner Q13d, 2026-10-16: a real surface, not the
#   web's centre plane Q13-B used, nor TaperRun@WallProfile off the base).
# A shown reference sketch prints, so each is short construction chords
# lying on lines its view draws (build_fr_nameplate's FaceReference idiom),
# and each location spans two chords' starts. The locations and the chords'
# lines are driven from the globals (the web's face is the window cuts' WEB
# start offset), so a GUI edit keeps them on their features; where a chord
# sits along its line is unprinted: REFERENCE_EDGE_STATION off a corner, or
# that far into a cavity or pocket wall's straight run past its corner
# radius. The low web chord stands REFERENCE_CHORD above the lower pocket
# floor's fillet, below where the drawing picks the web's faces for its
# 12.70; each high web chord runs down the web's face from REFERENCE_CHORD
# under the upper floor fillet, and each flat chord runs in along the top
# face from its edge (the profile's sharp, under the rim chamfer).
REFERENCE_CHORD = 1.0
REFERENCE_EDGE_STATION = 5.0
CAVITY_END_STATION = BOSS_DEPTH / 2.0 - CAV  # 26.7462, 1.053
CAVITY_TOP_STATION = HALF_Y - CAV  # 25.4, 1.00
POCKET_END_STATION = BOSS_DEPTH / 2.0 - BIG  # 7.6962, .303
POCKET_BOTTOM_STATION = HALF_Y - BIG  # 6.35, .25
WEB_FACE_STATION = WIDE - WEB  # 25.4, 1.00
LOCATION_DRIVES = {
    "CavityEndStation": f'{END_FACE_DRIVE} - "CavHalf"',
    "CavityTopStation": '"HalfHeight" - "CavHalf"',
    "PocketEndStation": f'{END_FACE_DRIVE} - "WindowOuter"',
    "PocketBottomStation": '"HalfHeight" - "WindowOuter"',
    "WebFaceStation": f'"FootHalf" - {WEB}mm',
    "TopFlatMinusZStation": f'"TopHalf" - {WEB}mm',
    "TopFlatPlusZStation": f'"TopHalf" - {WEB}mm',
}


class TopFlatStation(NamedTuple):
    """One top-flat edge location: sketch u (= model -Z) of its web face's
    chord and of its flat chord's start."""

    face_u: float
    edge_u: float


TOP_FLAT_STATIONS = {
    "TopFlatMinusZStation": TopFlatStation(WEB, NARROW),
    "TopFlatPlusZStation": TopFlatStation(-WEB, -NARROW),
}
if any(
    abs(abs(row.edge_u) - abs(row.face_u) - TOP_FLAT_EDGE_FROM_WEB) > 1e-12
    for row in TOP_FLAT_STATIONS.values()
):
    raise AssertionError("a top-flat station is not the seat stack's edge offset")

# PocketFloorFillet volume minus four through clearance drills.
FOOT_HOLED_VOLUME = (
    POCKET_FLOOR_FILLET_VOLUME
    - len(HOLES) * math.pi / 4.0 * HOLE_DIA**2 * FOOT_THICKNESS
)

CHAMFER = 1.27  # leg, 45°
# The measured window-rim chamfer removal: none of the chamfered edges changes
# length with the web (the cavity rim loops lie on the web faces, the window
# rim on the slant faces), so it carries over unchanged.
RIM_CHAMFER_VOLUME = FOOT_HOLED_VOLUME - SQUARE_RIM_CHAMFER_REMOVAL
# The rocker brackets' two bottoming-tapped seats, down from the top face on
# the centreline (rocker_bracket_seat_layout owns their stack). Each runs in
# solid iron for its whole length: the post outboard of the window edge, the
# web column (wider than the drill) inboard of it.
SEAT_POINTS = [[x, HALF_Y, 0.0] for x in SEAT_LOCAL_X]
# Each seat's placement, in SEAT_POINTS order: sketch x is model X on the +Y
# top face (harmonic-base's +Y deck seats map the same way) and the seats sit
# on the centreline (Z = 0), so the y coordinate takes the origin relation.
_SEAT_STATION_AT = {row.seat_x: row for row in SEAT_STATION_LINES}
SEAT_PLACEMENT_DIMS = [
    (
        (_SEAT_STATION_AT[x].placement, f'"{_SEAT_STATION_AT[x].seat_global}"'),
        (None, None),
    )
    for x, _y, _z in SEAT_POINTS
]
BRACKET_SEATS_VOLUME = RIM_CHAMFER_VOLUME - len(SEAT_POINTS) * blind_hole_volume_mm3(
    blind_cut_dia_mm(SEAT_SPEC), SEAT_SPEC.depth_mm
)
# The chamfer's ONE size dimension lands on the first selected edge, and a
# chamfer size prints only where its edge is seen end-on. The +X end face's
# foot edge (along Z) goes first, so the front view shows the size at the
# view's bottom-right outside corner (r7 machinist review: the size sat on a
# cavity rim no view shows plainly). That end face is therefore selected as
# its two edges the slant faces do not already own (foot and top), not as a
# face: same edges, same chamfer, same volume.
CHAMFER_EDGES = [
    [BOSS_DEPTH / 2.0, -HALF_Y, 0.0],  # +X end face's foot edge (sized)
    [BOSS_DEPTH / 2.0, HALF_Y, 0.0],  # +X end face's top edge
    # 12 inner-frame opening edges, both web faces (Z = ±WEB)
    [0.0, -63.5, -WEB],
    [63.5, 0.0, -WEB],
    [59.78, 59.78, -WEB],
    [0.0, 63.5, -WEB],
    [-63.5, 0.0, -WEB],
    [-59.78, -59.78, -WEB],
    [0.0, -63.5, WEB],
    [-59.78, -59.78, WEB],
    [-63.5, 0.0, WEB],
    [-59.78, 59.78, WEB],
    [0.0, 63.5, WEB],
    [63.5, 0.0, WEB],
]
CHAMFER_FACES = [  # whole faces whose every edge is chamfered (tangent-propagated)
    [0.0, -85.0, _wall_half_z_at(-85.0)],
    [0.0, -85.0, -_wall_half_z_at(-85.0)],  # ±Z slant window surrounds
    [-BOSS_DEPTH / 2.0, 0.0, 0.0],  # back trapezoid (-X) face
    [59.78, -59.78, 0.0],  # one inner fillet face
]


async def _seat_station_reference(adapter) -> list[tuple[str, str]]:
    """The blanked REF sketch: per seat, a construction line on the Top
    plane's x axis from the end face to the seat centre, its length the
    station; returns the drive jobs. The start follows the end face
    (END_FACE_DRIVE) and the length is the end face less the seat's global
    (SEAT_STATION_DRIVES), so the line ends on the seat for any WallWidth or
    seat edit: a REF reports, it does not control."""
    sketch = REFERENCE_SKETCHES[0]
    dims = SketchDims()
    check(f"create_sketch {sketch}", await adapter.create_sketch("Top"))
    for row in SEAT_STATION_LINES:
        name = row.dimension
        # Direct-to-DB: both lines lie on the sketch's x axis, so creation-
        # time inference would snap in the relations added below.
        set_sketch_direct_db(adapter, True)
        line = check(
            f"{name} line", await adapter.add_line(row.end_x, 0.0, row.seat_x, 0.0)
        )
        set_sketch_direct_db(adapter, False)
        segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError(f"{name} line did not take the construction flag")
        check(
            f"{name} horizontal",
            await adapter.add_sketch_constraint(line, None, "horizontal"),
        )
        await anchor_point_to_origin(
            adapter, f"{line}.start", row.end_x, 0.0, f"{name} end face"
        )
        dims.record(f"{name}Anchor", END_FACE_DRIVE)
        await dimension_between(
            adapter,
            f"{line}.start",
            f"{line}.end",
            "horizontal_distance",
            abs(row.end_x - row.seat_x),
            f"{name} from the end face",
        )
        dims.record(name, SEAT_STATION_DRIVES[name])
    await ensure_fully_defined(adapter, f"{sketch} sketch")
    check(f"exit_sketch {sketch}", await adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    return dims.apply(adapter, sketch)


async def _reference_chord(
    adapter,
    sketch: str,
    dims: SketchDims,
    name: str,
    start: tuple[float, float],
    end: tuple[float, float],
) -> str:
    """One unprinted construction chord from ``start`` along a line its view
    draws, held horizontal or vertical at its length ``name``. Direct-to-DB,
    as the seat lines are, so creation-time inference adds no relation."""
    relation = "horizontal" if start[1] == end[1] else "vertical"
    set_sketch_direct_db(adapter, True)
    line = check(f"{sketch} {name}", await adapter.add_line(*start, *end))
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{sketch} {name} did not take the construction flag")
    check(
        f"{sketch} {name} {relation}",
        await adapter.add_sketch_constraint(line, None, relation),
    )
    await _location(
        adapter,
        sketch,
        dims,
        name,
        f"{line}.start",
        f"{line}.end",
        f"{relation}_distance",
        math.dist(start, end),
    )
    return line


async def _location(
    adapter,
    sketch: str,
    dims: SketchDims,
    name: str,
    ref1: str,
    ref2: str,
    kind: str,
    value: float,
    drive: str | None = None,
) -> None:
    """One dimension between two point refs, recorded as ``name``."""
    await dimension_between(adapter, ref1, ref2, kind, value, f"{sketch} {name}")
    dims.record(name, drive)


async def _cavity_location_reference(adapter) -> list[tuple[str, str]]:
    """CavityLocationReference on the Front plane, sketch (u, v) = model
    (X, Y); returns the drive jobs.

    Chords down the -X end face and along the top and bottom faces, each
    REFERENCE_EDGE_STATION from their corner; down the cavity's and the
    pocket's -X side walls and along the cavity's top wall and the pocket's
    bottom wall, each that far into the wall's straight run. The end chord's
    start locates both side walls (CavityEndStation, PocketEndStation), the
    top chord's the cavity's top wall (CavityTopStation), the bottom chord's
    the pocket's bottom wall (PocketBottomStation). 7 x 4 DOF less: three
    anchored starts (6), seven square relations and lengths (14), four
    locations and four places along a wall (8) = 0.
    """
    sketch = REFERENCE_SKETCHES[1]
    dims = SketchDims()
    station, chord = REFERENCE_EDGE_STATION, REFERENCE_CHORD
    check(f"create_sketch {sketch}", await adapter.create_sketch("Front"))
    end_x, end_y = -BOSS_DEPTH / 2.0, HALF_Y - station
    end = await _reference_chord(
        adapter, sketch, dims, "EndChord", (end_x, end_y), (end_x, end_y - chord)
    )
    await anchor_point_to_origin(
        adapter, f"{end}.start", end_x, end_y, f"{sketch} end face chord"
    )
    dims.record("EndChordX", END_FACE_DRIVE)
    dims.record("EndChordY")
    top_x = end_x + station
    top = await _reference_chord(
        adapter, sketch, dims, "TopChord", (top_x, HALF_Y), (top_x + chord, HALF_Y)
    )
    await anchor_point_to_origin(
        adapter, f"{top}.start", top_x, HALF_Y, f"{sketch} top face chord"
    )
    dims.record("TopChordX")
    dims.record("TopChordY", '"HalfHeight"')
    cavity_run = CAV - FILLET_R - station
    for name, value, chord_name, x, y in (
        ("CavityEndStation", CAVITY_END_STATION, "CavitySideChord", -CAV, cavity_run),
        (
            "PocketEndStation",
            POCKET_END_STATION,
            "PocketSideChord",
            -BIG,
            BIG - POCKET_FILLET_R - station,
        ),
    ):
        side = await _reference_chord(
            adapter, sketch, dims, chord_name, (x, y), (x, y - chord)
        )
        await _location(
            adapter,
            sketch,
            dims,
            name,
            f"{end}.start",
            f"{side}.start",
            "horizontal_distance",
            value,
            LOCATION_DRIVES[name],
        )
        await _location(
            adapter,
            sketch,
            dims,
            f"{chord_name}Y",
            f"{side}.start",
            "origin",
            "vertical_distance",
            y,
        )
    cavity_top = await _reference_chord(
        adapter,
        sketch,
        dims,
        "CavityTopChord",
        (-cavity_run, CAV),
        (-cavity_run + chord, CAV),
    )
    await _location(
        adapter,
        sketch,
        dims,
        "CavityTopStation",
        f"{top}.start",
        f"{cavity_top}.start",
        "vertical_distance",
        CAVITY_TOP_STATION,
        LOCATION_DRIVES["CavityTopStation"],
    )
    await _location(
        adapter,
        sketch,
        dims,
        "CavityTopChordX",
        f"{cavity_top}.start",
        "origin",
        "horizontal_distance",
        cavity_run,
    )
    # The pocket's bottom wall up from the bottom (mounting) face, the
    # pocket's vertical location (r6 review).
    bottom = await _reference_chord(
        adapter,
        sketch,
        dims,
        "BottomChord",
        (top_x, -HALF_Y),
        (top_x + chord, -HALF_Y),
    )
    await anchor_point_to_origin(
        adapter, f"{bottom}.start", top_x, -HALF_Y, f"{sketch} bottom face chord"
    )
    dims.record("BottomChordX")
    dims.record("BottomChordY", '"HalfHeight"')
    pocket_run = BIG - POCKET_FILLET_R - station
    pocket_bottom = await _reference_chord(
        adapter,
        sketch,
        dims,
        "PocketBottomChord",
        (-pocket_run, -BIG),
        (-pocket_run + chord, -BIG),
    )
    await _location(
        adapter,
        sketch,
        dims,
        "PocketBottomStation",
        f"{bottom}.start",
        f"{pocket_bottom}.start",
        "vertical_distance",
        POCKET_BOTTOM_STATION,
        LOCATION_DRIVES["PocketBottomStation"],
    )
    await _location(
        adapter,
        sketch,
        dims,
        "PocketBottomChordX",
        f"{pocket_bottom}.start",
        "origin",
        "horizontal_distance",
        pocket_run,
    )
    await ensure_fully_defined(adapter, f"{sketch} sketch")
    check(f"exit_sketch {sketch}", await adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    return dims.apply(adapter, sketch)


async def _web_location_reference(adapter) -> list[tuple[str, str]]:
    """WebLocationReference on the Right plane, section A-A's cutting plane,
    sketch (u, v) = model (-Z, Y); returns the drive jobs.

    Chords along the base from its -Z edge (the sharp the 63.5 measures from
    too) and up the web's -Z face from REFERENCE_CHORD above the lower pocket
    floor's fillet; WebFaceStation spans their starts. Per top-flat edge, a
    chord down its side's web face from REFERENCE_CHORD under the upper floor
    fillet and one in along the top face from the edge; each TopFlat*Station
    spans the face chord's start to the edge's (owner Q13d). 6 x 4 DOF less:
    the base chord's anchored start (2), six square relations and lengths
    (12), the web location and the low web chord's height (2), each high web
    chord's place (4), each flat chord's height and station (4) = 0.
    """
    sketch = REFERENCE_SKETCHES[2]
    dims = SketchDims()
    check(f"create_sketch {sketch}", await adapter.create_sketch("Right"))
    base = await _reference_chord(
        adapter,
        sketch,
        dims,
        "BaseChord",
        (WIDE, -HALF_Y),
        (WIDE - REFERENCE_EDGE_STATION, -HALF_Y),
    )
    await anchor_point_to_origin(
        adapter, f"{base}.start", WIDE, -HALF_Y, f"{sketch} base edge chord"
    )
    dims.record("BaseChordZ", '"FootHalf"')
    dims.record("BaseChordY", '"HalfHeight"')
    web_y = -(BIG - POCKET_FLOOR_R - REFERENCE_CHORD)
    web = await _reference_chord(
        adapter, sketch, dims, "WebChord", (WEB, web_y), (WEB, web_y + REFERENCE_CHORD)
    )
    await _location(
        adapter,
        sketch,
        dims,
        "WebFaceStation",
        f"{base}.start",
        f"{web}.start",
        "horizontal_distance",
        WEB_FACE_STATION,
        LOCATION_DRIVES["WebFaceStation"],
    )
    await _location(
        adapter,
        sketch,
        dims,
        "WebChordY",
        f"{web}.start",
        "origin",
        "vertical_distance",
        -web_y,
    )
    # Each top-flat edge off the web face on its side (owner Q13d): the face
    # chord runs down from under the upper pocket floor's fillet, inside the
    # web's straight run above the cavity's rim chamfer.
    face_y = BIG - POCKET_FLOOR_R - REFERENCE_CHORD
    for name, row in TOP_FLAT_STATIONS.items():
        face = await _reference_chord(
            adapter,
            sketch,
            dims,
            f"{name}FaceChord",
            (row.face_u, face_y),
            (row.face_u, face_y - REFERENCE_CHORD),
        )
        await _location(
            adapter,
            sketch,
            dims,
            f"{name}FaceChordZ",
            f"{face}.start",
            "origin",
            "horizontal_distance",
            abs(row.face_u),
        )
        await _location(
            adapter,
            sketch,
            dims,
            f"{name}FaceChordY",
            f"{face}.start",
            "origin",
            "vertical_distance",
            face_y,
        )
        inward = -math.copysign(REFERENCE_CHORD, row.edge_u)
        flat = await _reference_chord(
            adapter,
            sketch,
            dims,
            f"{name}Chord",
            (row.edge_u, HALF_Y),
            (row.edge_u + inward, HALF_Y),
        )
        await _location(
            adapter,
            sketch,
            dims,
            f"{name}ChordY",
            f"{flat}.start",
            "origin",
            "vertical_distance",
            HALF_Y,
            '"HalfHeight"',
        )
        await _location(
            adapter,
            sketch,
            dims,
            name,
            f"{face}.start",
            f"{flat}.start",
            "horizontal_distance",
            TOP_FLAT_EDGE_FROM_WEB,
            LOCATION_DRIVES[name],
        )
    await ensure_fully_defined(adapter, f"{sketch} sketch")
    check(f"exit_sketch {sketch}", await adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    return dims.apply(adapter, sketch)


def _add_construction_diagonals(adapter, half_mm: float) -> None:
    """Add the two corner-to-corner CONSTRUCTION diagonals that the center-
    rectangle tool draws, so a ``define_centered_rectangle`` square matches the
    source sketch's segment set (4 real sides + 2 construction diagonals).

    The diagonal endpoints sit on the square's existing corners (exact coords,
    so the suppressed-inference DB merges them onto the corner vertices); pinned
    to fully-defined corners, the diagonals add no DOF and the sketch stays
    fully defined.
    """
    sm = adapter.currentSketchManager
    sm = _early_bound(sm, "ISketchManager")
    h = half_mm / 1000.0
    prev = bool(sm.AddToDB)
    sm.AddToDB = True
    try:
        for (x1, y1), (x2, y2) in (((-h, -h), (h, h)), ((-h, h), (h, -h))):
            seg = sm.CreateLine(x1, y1, 0.0, x2, y2, 0.0)
            seg = _early_bound(seg, "ISketchSegment")
            seg.ConstructionGeometry = True
    finally:
        sm.AddToDB = prev


def _select_sketch(adapter, name: str) -> None:
    """Select a sketch by name for the next feature (shared-sketch friendly: a
    second select of an already-consumed sketch is how WindowCut2 reuses
    WindowProfile, which SolidWorks then shows as a ``<2>`` reference)."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"select sketch {name!r} failed")


def _cut_through_all(
    adapter,
    sketch_name: str,
    *,
    both: bool,
    reverse_dir: bool,
    start_offset_mm: float = 0.0,
    flip_start: bool = False,
):
    """Through-all ``FeatureCut4`` on the named sketch.

    ``both`` -> Through-All-Both (the cavity). A single-direction cut with
    ``start_offset_mm`` reproduces the windows: each window cut shares one
    centered window square but STARTS ``start_offset_mm`` off the sketch plane
    (forward / reverse, opposite ``flip_start``), so the 2*offset band between
    them survives as the central web -- exactly the source's
    ``FromOffsetDistance``/``ReverseDirection`` pair.
    """
    model = adapter.currentModel
    model = _early_bound(model, "IModelDoc2")
    fm = model.FeatureManager
    fm = _early_bound(fm, "IFeatureManager")
    _select_sketch(adapter, sketch_name)

    through = adapter.constants.get("swEndCondThroughAll", 1)
    t0 = (
        adapter.constants.get("swStartOffset", 3)
        if start_offset_mm
        else adapter.constants.get("swStartSketchPlane", 0)
    )
    # 27-param FeatureCut4: T0/StartOffset/FlipStartOffset are the start-condition
    # tail (26-param is the SW-2025 form).
    args = (
        not both,
        False,
        reverse_dir,
        through,
        through,
        0.0,
        0.0,
        False,
        False,
        False,
        False,
        0.0,
        0.0,
        False,
        False,
        False,
        False,
        False,
        False,
        True,
        False,
        False,
        False,
        t0,
        start_offset_mm / 1000.0,
        flip_start,
        False,
    )
    feat = adapter._attempt(lambda: fm.FeatureCut4(*args), default=None)
    if not feat:
        feat = adapter._attempt(lambda: fm.FeatureCut4(*args[:-1]), default=None)
    model.ClearSelection2(True)
    if not feat:
        raise RuntimeError(f"FeatureCut4 on {sketch_name} failed")
    return feat


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs: named equation-manager globals (mm) that drive every
    # profile sketch's dimensions, so a GUI edit to a global reshapes the part
    # and round-trips into the script (same self-naming treatment as the 71
    # tracked parts -- see build_fr_top_frame.py). Lengths carry an explicit `mm`:
    # the part is modelled inch, and the equation manager evaluates bare numbers
    # in DOCUMENT units, so an unsuffixed global would be read as inches.
    await set_global(adapter, "FootHalf", f"{WIDE}mm")  # trapezoid foot half-width (Z)
    await set_global(adapter, "TopHalf", f"{NARROW}mm")  # trapezoid top half-width (Z)
    await set_global(adapter, "HalfHeight", f"{HALF_Y}mm")  # trapezoid half-height (Y)
    await set_global(adapter, "CavHalf", f"{CAV}mm")  # cavity square half
    await set_global(adapter, "WindowOuter", f"{BIG}mm")  # window square half
    await set_global(
        adapter, "WallWidth", f"{BOSS_DEPTH}mm"
    )  # mid-plane extrude span (X)
    # The seats' stations off the centre plane (X): their Hole Wizard
    # placements and the REF stations both read them.
    for seat_global, station in SEAT_GLOBALS.items():
        await set_global(adapter, seat_global, f"{station}mm")

    # Each sketch records its dim names + drive equations inline as it is drawn
    # (per-sketch SketchDims); the (dim@feature, expr) jobs are collected here and
    # applied in ONE deferred batch after the whole model + a rebuild exist, so
    # every equation target resolves. The neutrality volume_check at the end is
    # the proof that driving did not move the geometry.
    drive_jobs: list[tuple[str, str]] = []

    # 1. Boss: trapezoid on the Right plane (sketch-x -> model Z, sketch-y ->
    #    model Y, so the wide foot sits at Y=-88.9), mid-plane extruded 180.5
    #    along X. A polygon chain (two slanted sides) anchored at the foot's
    #    -Z corner; the six dims drive off FootHalf/TopHalf/HalfHeight.
    trap = SketchDims()
    check("sketch boss", await adapter.create_sketch("Right"))
    trap_pts = [(-WIDE, -HALF_Y), (WIDE, -HALF_Y), (NARROW, HALF_Y), (-NARROW, HALF_Y)]
    trap_lines = await add_line_chain(adapter, trap_pts)
    await define_polygon_chain(
        adapter,
        trap_lines,
        trap_pts,
        anchor=0,
        label="trapezoid",
        dims=trap,
        names=[
            "FootAnchorZ",
            "FootAnchorY",
            "FootSpan",
            "TaperRun",
            "WallHeight",
            "TopSpan",
        ],
        drives=[
            '"FootHalf"',
            '"HalfHeight"',
            '2 * "FootHalf"',
            '"FootHalf" - "TopHalf"',
            '2 * "HalfHeight"',
            '2 * "TopHalf"',
        ],
    )
    await ensure_fully_defined(adapter, "trapezoid")
    check("exit boss", await adapter.exit_sketch())
    name_last_feature(adapter, "WallProfile")
    drive_jobs += trap.apply(adapter, "WallProfile")
    check(
        "boss",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BOSS_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Wall")
    depth_dim = name_dimensions(adapter, "Wall", ["Depth"])
    drive_jobs += [(depth_dim[0], '"WallWidth"')]
    await volume_check(adapter, "Wall", WALL_VOLUME, 200)

    # 2-4. Two sketches drive three cuts, exactly as the source tree does (only
    # the names are semantic here, not the source's Sketch11/Cut-ExtrudeN). Both
    # window/cavity sketches are SINGLE origin-centred squares on the Front plane,
    # drawn center-rectangle style (four real sides + two construction diagonals),
    # matching the source's segment set:
    #   * WindowProfile -- the 165.1 mm window square. WindowCut1 and WindowCut2
    #     BOTH consume this ONE sketch (the second re-selects it -> a shared-sketch
    #     reference), each a Through-All cut that STARTS WEB (6.35) off the
    #     sketch plane in the opposite direction, so the 2*WEB band between them
    #     survives as the central web -- the source's FromOffsetDistance/
    #     ReverseDirection pair, not a sketch gap. The square drives off
    #     WindowOuter.
    #   * CavityProfile -- the 127 mm cavity square; CavityCut consumes it whole
    #     (Through-All-Both). Drives off CavHalf.
    # Built in the source's creation order (window profile, then cavity) and cut
    # in the source's order (cavity, then the two windows).
    windows = SketchDims()
    check("sketch windows", await adapter.create_sketch("Front"))
    await define_centered_rectangle(
        adapter,
        BIG,
        BIG,
        "window",
        dims=windows,
        name_width="WinWidth",
        drive_width='2 * "WindowOuter"',
        name_depth="WinHeight",
        drive_depth='2 * "WindowOuter"',
    )
    await ensure_fully_defined(adapter, "window")
    check("exit windows", await adapter.exit_sketch())
    name_last_feature(adapter, "WindowProfile")
    drive_jobs += windows.apply(adapter, "WindowProfile")

    cavity = SketchDims()
    check("sketch cavity", await adapter.create_sketch("Front"))
    await define_centered_rectangle(
        adapter,
        CAV,
        CAV,
        "cavity",
        dims=cavity,
        name_width="CavWidth",
        drive_width='2 * "CavHalf"',
        name_depth="CavDepth",
        drive_depth='2 * "CavHalf"',
    )
    await ensure_fully_defined(adapter, "cavity")
    check("exit cavity", await adapter.exit_sketch())
    name_last_feature(adapter, "CavityProfile")
    drive_jobs += cavity.apply(adapter, "CavityProfile")

    # CavityCut: cavity -- whole CavityProfile, Through-All-Both.
    _cut_through_all(adapter, "CavityProfile", both=True, reverse_dir=False)
    name_last_feature(adapter, "CavityCut")
    await volume_check(adapter, "CavityCut", CAVITY_CUT_VOLUME, 200)

    # WindowCut1: one window -- Through-All forward, started WEB off-plane.
    _cut_through_all(
        adapter,
        "WindowProfile",
        both=False,
        reverse_dir=False,
        start_offset_mm=WEB,
        flip_start=True,
    )
    name_last_feature(adapter, "WindowCut1")
    await volume_check(adapter, "WindowCut1", WINDOW_CUT1_VOLUME, 200)

    # WindowCut2: the other window -- the SAME WindowProfile, Through-All reverse,
    # started WEB off-plane the other way (leaves the 2*WEB central web).
    _cut_through_all(
        adapter,
        "WindowProfile",
        both=False,
        reverse_dir=True,
        start_offset_mm=WEB,
        flip_start=False,
    )
    name_last_feature(adapter, "WindowCut2")
    await volume_check(adapter, "WindowCut2", WINDOW_CUT2_VOLUME, 200)

    # 5. CornerFillet: R12.7 on the four cavity corners.
    check("fillet cavity corners", await adapter.add_fillet(FILLET_R, FILLET_EDGES))
    name_last_feature(adapter, "CornerFillet")
    await volume_check(adapter, "CornerFillet", CORNER_FILLET_VOLUME, 200)
    name_dimensions(adapter, "CornerFillet", ["CavityRadius"])

    # 6. PocketCornerFillet: R6.35 on both opposed pocket openings.
    check(
        "fillet pocket corners",
        await adapter.add_fillet(POCKET_FILLET_R, POCKET_FILLET_EDGES),
    )
    name_last_feature(adapter, "PocketCornerFillet")
    name_dimensions(adapter, "PocketCornerFillet", ["PocketRadius"])
    await volume_check(adapter, "PocketCornerFillet", POCKET_FILLET_VOLUME, 20)

    # 6b. PocketFloorFillet: R0.8 around both pocket floors.
    check(
        "fillet pocket floors",
        await adapter.add_fillet(
            POCKET_FLOOR_R, POCKET_FLOOR_FILLET_EDGES, propagate=True
        ),
    )
    name_last_feature(adapter, "PocketFloorFillet")
    name_dimensions(adapter, "PocketFloorFillet", ["PocketFloorRadius"])
    await volume_check(adapter, "PocketFloorFillet", POCKET_FLOOR_FILLET_VOLUME, 20)

    # 7. FootClearanceHoles: one native Hole Wizard feature, four 5/16 drills.
    wizard_holes(
        adapter,
        HOLE_SPEC,
        [[x, -BIG, z] for x, z in HOLES],
        (0.0, 1.0, 0.0),
        "rocker-support top-down clearance holes (5/16)",
        name="FootClearanceHoles",
        expect_dia_mm=HOLE_DIA,
    )
    await volume_check(adapter, "FootClearanceHoles", FOOT_HOLED_VOLUME, 200)

    # 8. RimChamfer: 1.27 mm / 45° around the whole window rim and every
    #    outside edge -- the +X end face's foot edge first (it carries the
    #    size), its top edge, the 12 inner-frame opening edges, plus the
    #    slant/back-end/fillet faces, tangent-propagated.
    check(
        "chamfer",
        await adapter.add_chamfer(
            CHAMFER, CHAMFER_EDGES, face_points=CHAMFER_FACES, tangent_propagation=True
        ),
    )
    name_last_feature(adapter, "RimChamfer")
    name_dimensions(adapter, "RimChamfer", ["RimChamferSize"])
    await volume_check(adapter, "RimChamfer", RIM_CHAMFER_VOLUME, 200)

    # 9. BracketSeats: the rocker brackets' two #8-32 bottoming-tapped seats,
    #    down from the top face over the window's side edges. Located at their
    #    nominal stations; the print says TRANSFER FROM MHA-CH-08 AT ASSEMBLY.
    bracket_seats = wizard_holes(
        adapter,
        SEAT_SPEC,
        SEAT_POINTS,
        (0.0, 1.0, 0.0),
        "rocker-bracket hold-down bottoming-tapped seats (#8-32)",
        name="BracketSeats",
        placement_dims=SEAT_PLACEMENT_DIMS,
    )
    drive_jobs += bracket_seats.placement_drive_jobs
    await volume_check(adapter, "BracketSeats", BRACKET_SEATS_VOLUME, 200)

    # 10. SeatStationReference: the seats' REF stations for VIEW B; the
    #     cavity's, the pockets', and the web's locations for the front view
    #     and section A-A.
    drive_jobs += await _seat_station_reference(adapter)
    drive_jobs += await _cavity_location_reference(adapter)
    drive_jobs += await _web_location_reference(adapter)

    # Apply the deferred drive equations now that the whole model + a rebuild
    # exist, so every named-dim target resolves. Each equation evaluates to the
    # value just built, so the geometry must not move -- the re-check below is
    # the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven part (equations neutral)", BRACKET_SEATS_VOLUME, 200
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)

    await apply_material(adapter, MATERIAL)
    await apply_color(
        adapter, CASTING_GREEN
    )  # green-painted casting, like the base/top-frame
    await report_mass_properties(adapter)
    apply_drawing_properties(adapter, PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
