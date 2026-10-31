r"""Reproduction script: one-piece platen paper holder (book ch. 22, pp. 54-55).

One of the two bright brass holders hugging the platen front's extreme
left/right edges, running from the TOP edge down 3.29 in.  The reference
photos (ch22 img02 front, img03 close-up) show one slotted sheet: a flat screw
rail along the platen edge and a spring rail toward the paper, separated by
two narrow open-ended slits that stop either side of one intact middle bridge.
Each free half of the spring rail lifts off the platen in a smooth shallow bow
and comes back down to lie flat at its rounded paper-contact end.

The model is one merged brass body with no added end flange and no faceted
creases: the spring rail is a mid-plane thin extrusion of one tangent
line/arc path, so every bend is a smooth cylindrical band.  In plan, the
spring ends are full half-rounds, the screw rail's corners are rounded
(large on the outer edge, small at the slit), and each slit ends in a full
half-round at the bridge, as img03 shows.  The two slotted pan heads sit
directly on the flat .032 sheet (img03: no raised seats); the platen's rear
socket bosses take the rest of the stock shank as thread
(pd_platen_spec.SOCKET_BOSS_H).

Used twice in pd-paper-drive.SLDASM.  Length is local +X, total width is local +Y,
and the flat rail's outward face is local z = 0.  The assembly turns the holder
-90 degrees about Z and places local z = SHEET_T against the platen.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_platen_clip.py
"""

from __future__ import annotations

import math
import sys

import _config
import _telemetry
from _appearance import apply_material
from _check import check
from _com import _early_bound, _read_member
from _dimensions import (
    _dim_value_mm,
    _display_dimensions,
    _rename_dimensions,
    drive_dimension,
    name_dimensions,
    set_global,
)
from _feature_tree import _feature_by_name, feature_name_by_type, name_last_feature
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _hole_spec import THREAD_MAJOR_MM
from _holes import CLEARANCE_MM, HoleSpec, SharedCoordinate, wizard_holes
from _inch_wall_limits import WALL_TARGET_MM
from _document_units import apply_package_model_units
from _package_units import drawing_unit
from _part_properties import part_drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm, printed_deviations
from pd_vn_platen_clip_screw_spec import (
    HEAD_DIA,
    HEAD_DIA_MIN,
    PITCH,
    SHANK_DIA,
    SHANK_LEN,
    THREAD,
)
from pd_platen_spec import PLATE_THICKNESS, SOCKET_BOSS_H, SOCKET_THREAD_ENGAGEMENT

PART_NAME = "pd-platen-clip"
MATERIAL = "Brass"  # see _appearance.apply_material docstring
# #290: the registry row's drawing_unit (in) is this sheet's unit; lengths are
# physical millimetres, each the exact decimal of its printed inch value.
UNIT = drawing_unit(f"parts/{PART_NAME}", _config.parts(PART_NAME))

# ch22 p.55 rear photo: 86.7 of the 140 mm plate (0.619) x PLATE_HEIGHT
# 134.82 = 83.5, on the .XX grid.
CLIP_LENGTH = 83.566  # 3.29
# ch30-p002 Pose Studio: the photographed clip is 10 * 0.8988 wide.
PHOTO_CLIP_WIDTH = 8.988
# The sheet is the stock's (the print gives it as a reference over SHEET
# STOCK): 0.032 in C26000 strip, whose thickness ASTM B248 (Table 1, 0.026 to
# 0.037 in, to 8 in wide) holds to +/-0.002 in.
STOCK_THICKNESS_IN = 0.032
STOCK_THICKNESS_TOL_IN = 0.002
SHEET_T = STOCK_THICKNESS_IN * 25.4
CLIP_THICKNESS = SHEET_T  # assembly stand-off: one sheet, not a face stack

# ch22 img03 (one clip, 603 x 68 px of brass): the spring rail is 32 px wide
# and the slit beside it 4 px, of the photographed width.
PHOTO_SLIT_WIDTH = PHOTO_CLIP_WIDTH * 4.0 / 68.0
PHOTO_SPRING_RAIL_WIDTH = PHOTO_CLIP_WIDTH * 32.0 / 68.0
# The photographed 32-px (4.23) screw rail cannot hold a #2 clearance hole
# with its rule-17 ligament on both sides (user ruling 2026-10-14, option A:
# widen the screw rail; Main 2026-10-31, option B for the inch print: the
# .080 target on both sides).  The hole row stays .XXX for pattern float (the
# hole floats over the shank by both patterns' zones only at .XXX, below) and
# the clip is held on the plate; the rail width prints .XX
# (RAIL_WIDTH_PLACES).  With the row at .XXX and the rail at .XX, the slit
# side binds: W - .01 - (HOLE_Y + .005) - r_max >= .080, so W >= .300 for the
# #2 loose hole drilled at its printed Ø.116.
SCREW_RAIL_WIDTH = 7.62  # .30
RAIL_WIDTH_PLACES = 2
# The overall width keeps the clip's inboard edge 2.0 off the recording paper
# with the platen's clip sockets (pd_platen_spec.SOCKET_X; test_pd_platen_refit
# asserts the gap): the spring rail is what the screw rail and the slit leave
# of it (.130, the photograph's 4.23 short of the widened screw rail).
CLIP_WIDTH = 11.938  # .47
# The slit frees the spring rail to flex out of the sheet on its own while the
# screw rail stays clamped; the book's clip does that through the photographed
# 0.53 slit, so the print's narrowest slit keeps at least that open.  It
# prints .XX (the title block's general band, +/-.01): the nominal is the
# floor plus the band, rounded up to the .01 grid, .04.
SLIT_PLACES = 2
SLIT_GAP_FLOOR = PHOTO_SLIT_WIDTH
NOTCH_WIDTH = (
    math.ceil(
        round(
            (SLIT_GAP_FLOOR + printed_band_mm(SLIT_PLACES, unit=UNIT)) / 25.4 * 100.0, 9
        )
    )
    / 100.0
    * 25.4
)
SPRING_RAIL_WIDTH = CLIP_WIDTH - SCREW_RAIL_WIDTH - NOTCH_WIDTH
SPRING_RAIL_Y0 = SCREW_RAIL_WIDTH + NOTCH_WIDTH
# img03: the slits stop 77 px apart on their centreline; with their full
# half-round ends (2 px radius) the tangent points sit 81 px apart (81/603 of
# the length, .44), snapped to .45 so both bridge ends print on the .XX grid.
# The bridge length is that tangent-point span, which is also the spring
# rail's flat middle run; the wider slit's full round (radius NOTCH_WIDTH / 2)
# ends at the same tangent points.
CENTER_BRIDGE_LENGTH = 11.43  # .45
SLIT_END_RADIUS = NOTCH_WIDTH / 2.0
BRIDGE_X0 = (CLIP_LENGTH - CENTER_BRIDGE_LENGTH) / 2.0  # 1.42
BRIDGE_X1 = BRIDGE_X0 + CENTER_BRIDGE_LENGTH  # 1.87
# img03 plan corners: the spring rail ends are full half-rounds; the screw
# rail's outer corners round at ~18 px (2.5 mm) and its slit-side corners at
# ~6 px (0.75 mm).
SPRING_END_RADIUS = SPRING_RAIL_WIDTH / 2.0
SCREW_RAIL_END_RADIUS = 2.54  # .10
SCREW_RAIL_SLIT_RADIUS = 0.762  # .03
ARCH_RISE = 1.524  # .06: shallow outward bow; editable as ArchRise in Tools > Equations

# The brass #2-56 slotted pan-head screws (pd-vn-platen-clip-screw; img03's heads
# read ~2.6-3.0 mm, user ruling 2026-10-15 for the pan head's bearing land)
# retain their lengthwise stations in the flat rail, .145 in from its outer
# edge (above); each head lies wholly on the rail.
HOLE_INSET = 7.1882  # .283: ch30-p002 Pose Studio, 8 * 0.8988 from each end
HOLE_Y = 3.683  # .145
CLEARANCE_SIZE = THREAD.split("-")[0]  # "#2"
# #2 LOOSE (user ruling 2026-10-14): the screws are fixed in the platen's
# taps, so the hole's float over the shank must hold both patterns' printed
# positions (HOLE_FLOAT_MIN below).
HOLE_FIT = "loose"
HOLE_SPEC = HoleSpec("clearance", CLEARANCE_SIZE, fit=HOLE_FIT)
HOLE_DIA = CLEARANCE_MM[(CLEARANCE_SIZE, HOLE_FIT)]  # 2.946 (.116)
HEAD_TO_SPRING_RAIL = SPRING_RAIL_Y0 - (HOLE_Y + HEAD_DIA / 2.0)
# The head stands nearer the rail's outer edge than its slit edge.
HEAD_RAIL_MARGIN = min(HOLE_Y, SCREW_RAIL_WIDTH - HOLE_Y) - HEAD_DIA / 2.0

# Worst case of the printed sheet (drawing-guidelines.md rule 17): the hole
# stations and the hole row print at .XXX, the screw-rail width at .XX, the
# holes are DRILLED at the size their callout prints (HOLE_CALLOUT_PRECISION).
POSITION_PLACES = 3  # pd-platen-clip RV-01
_POSITION_BAND = printed_band_mm(POSITION_PLACES, unit=UNIT)
HOLE_CALLOUT_PRECISION = {"hw-diam": 3}
HOLE_DIA_MAX = (
    HOLE_DIA
    + printed_deviations(
        HOLE_DIA,
        HOLE_CALLOUT_PRECISION["hw-diam"],
        (0.0, drilled_oversize_mm(unit=UNIT)),
        unit=UNIT,
    )[1]
)
# The slit-side ligament meets the .080 target exactly; allow float rounding.
LIGAMENT_FLOOR = WALL_TARGET_MM - 1e-9
EDGE_LIGAMENT_MIN = HOLE_Y - _POSITION_BAND - HOLE_DIA_MAX / 2.0
SLIT_LIGAMENT_MIN = (
    SCREW_RAIL_WIDTH
    - printed_band_mm(RAIL_WIDTH_PLACES, unit=UNIT)
    - (HOLE_Y + _POSITION_BAND)
    - HOLE_DIA_MAX / 2.0
)
END_LIGAMENT_MIN = HOLE_INSET - _POSITION_BAND - HOLE_DIA_MAX / 2.0
# The far hole stands at its own .XXX station from the near end, so the far
# end's ligament also spends the overall length's printed band.
LENGTH_PLACES = 2
FAR_END_LIGAMENT_MIN = (
    CLIP_LENGTH
    - printed_band_mm(LENGTH_PLACES, unit=UNIT)
    - (CLIP_LENGTH - HOLE_INSET + _POSITION_BAND)
    - HOLE_DIA_MAX / 2.0
)
# Fixed-fastener float: each pattern's two .XXX coordinates bound its holes
# to a diametral zone of 2 * sqrt(2) * band; the clip's hole and the platen's
# tap share the smallest hole's clearance over the shank.
PATTERN_POSITION_ZONE = 2.0 * math.sqrt(2.0) * _POSITION_BAND
HOLE_FLOAT_MIN = HOLE_DIA - SHANK_DIA
# The least catalogue head (ASME B18.6.3) over the largest drilled hole,
# concentric: the least bearing land (an offset head only uncovers less hole).
HEAD_BEARING_LAND_MIN = (HEAD_DIA_MIN - HOLE_DIA_MAX) / 2.0
# Clip-joint thread engagement at the worst case (drawing-guidelines.md rule
# 18): the shortest catalogue screw (ASME B18.6.3, to 1 in: +0/-0.03 in) under
# the thickest stock sheet reaches the least into the platen's through tap,
# less one pitch of incomplete lead and the tap mouth's title-block edge break.
SCREW_LENGTH_MINUS = 0.03 * 25.4
TAP_MOUTH_BREAK = 0.254  # .010
SHEET_T_MAX = (STOCK_THICKNESS_IN + STOCK_THICKNESS_TOL_IN) * 25.4
CLIP_SCREW_ENGAGEMENT_MIN = (
    SHANK_LEN - SCREW_LENGTH_MINUS - SHEET_T_MAX - PITCH - TAP_MOUTH_BREAK
)
# The overall width prints .XX from the outer edge, as the slit (SLIT_PLACES)
# does: the spring rail is what they leave beside the screw rail (a reference).
WIDTH_PLACES = 2
# Spring rail section (local X, Z) as its sheet MID-SURFACE: the free tip lies
# flat from its end-round centre out to the screw station, then each free half
# lifts in one smooth bow of three tangent arcs of equal radius (concave,
# convex crown, concave) and lies flat again over the middle bridge.  For a
# bow of run L and rise h, R = L^2 / (16 h) + h / 4 and each concave arc turns
# asin(L / 4R); the crown turns twice that.  Offsetting the mid-surface by
# SHEET_T / 2 keeps the same run and rise on both faces.
BOW_RUN = BRIDGE_X0 - HOLE_INSET
BEND_RADIUS = BOW_RUN**2 / (16.0 * ARCH_RISE) + ARCH_RISE / 4.0
BEND_ANGLE = math.asin(BOW_RUN / (4.0 * BEND_RADIUS))
TIP_FLAT_LENGTH = HOLE_INSET - SPRING_END_RADIUS
MID_SURFACE_LENGTH = (
    2.0 * TIP_FLAT_LENGTH + CENTER_BRIDGE_LENGTH + 2.0 * 4.0 * BEND_RADIUS * BEND_ANGLE
)
# Each formed finger's flat length in the blank, from the bridge to its tip
# (the mid-surface's developed bow and tip flat, and the end round): the
# blank's fingers stand this far past the bridge, longer than the formed
# ones, so forming draws each tip back flush with its rail end.
FLAT_FINGER_LENGTH = HOLE_INSET + 4.0 * BEND_RADIUS * BEND_ANGLE
# The tangent stations of the two bows' four arcs each, from the near end
# (the mid-surface's joins): each bow starts and ends flat, and its lift and
# return arcs meet the crown a quarter of the run in (R sin(a) = run / 4).
TANGENT_STATIONS = (
    ("TangentX1", HOLE_INSET, '"HoleInset"'),
    ("TangentX2", HOLE_INSET + BOW_RUN / 4.0, '"HoleInset" + "BowRun" / 4'),
    ("TangentX3", HOLE_INSET + 3.0 * BOW_RUN / 4.0, '"HoleInset" + 3 * "BowRun" / 4'),
    ("TangentX4", BRIDGE_X0, '"BridgeX0"'),
    ("TangentX5", BRIDGE_X1, '"BridgeX0" + "CenterBridgeL"'),
    ("TangentX6", BRIDGE_X1 + BOW_RUN / 4.0, '"HoleFarX" - 3 * "BowRun" / 4'),
    ("TangentX7", BRIDGE_X1 + 3.0 * BOW_RUN / 4.0, '"HoleFarX" - "BowRun" / 4'),
    ("TangentX8", CLIP_LENGTH - HOLE_INSET, '"HoleFarX"'),
)
# The stations the profile prints, as references: where each bow leaves and
# rejoins the flat (the hole and bridge stations).  The quarter-run joins
# between the lift and crown arcs follow from the rise and the radius, and
# printed they read as the finger crossing the body line (r4 rule 10).
DRAWN_TANGENT_STATIONS = tuple(
    station
    for station in TANGENT_STATIONS
    if station[0] in {"TangentX1", "TangentX4", "TangentX5", "TangentX8"}
)
# The far bow's crest station, where the drawing's rise reference stands.
FAR_CREST_X = BRIDGE_X1 + BOW_RUN / 2.0

MODEL_FEATURES = (
    "FlatSheet",
    "SpringRail",
    "RoundedSpringEnds",
    "ScrewHoles",
)
BOSS_DRIVES = {
    "FlatSheet": ('"SheetT"',),
    "RoundedSpringEnds": ('"SheetT"',),
}
# The spring rail's thin extrusion carries three display dimensions, matched
# by their built value (all distinct): (name, value mm, driving expression).
SPRING_RAIL_DRIVES = (
    ("SpringRailWidth", SPRING_RAIL_WIDTH, '"SpringRailW"'),
    ("StartOffset", SPRING_RAIL_Y0, '"SpringRailY0"'),
    ("WallT", SHEET_T, '"SheetT"'),
)
# Native equation self-test: each knob is flexed, rebuilt, checked against the
# analytic volume and z span, then restored.  NotchW is how SpringRailY0
# moves (it is the derived "ScrewRailW" + "NotchW"); widening the slit opens a
# gap at the bridge unless the spring rail's start offset follows.
EQUATION_FLEX = (
    ("SheetT", SHEET_T, 1.0, "sheet_t"),
    ("NotchW", NOTCH_WIDTH, 0.6, "notch_w"),
)
_CORNER_LOSS = (
    (1.0 - math.pi / 4.0) * 2.0 * (SCREW_RAIL_END_RADIUS**2 + SCREW_RAIL_SLIT_RADIUS**2)
)

# --- Drawing contract: feature -> the parametric dimension NAMES the print
# shows.  The build marks exactly these and authors their places;
# ``draw_pd_platen_clip`` keeps exactly their union across its views.  The plan
# shows the formed clip square to its screw rail: the overall (FORMED) length,
# the bridge's two ends (the slits' rounded ends) from the near end, the hole
# row, the screw rail's width and the overall width from the outer edge, the
# slit, the corner radii and the hole stations; the spring rail's width is
# what they leave, a reference.  The
# formed profile carries the bows' rise and, as references, the four stations
# where the bows leave and rejoin the flat, their radius, the developed finger
# and the sheet stock.  Hidden reference sketches own the overall width, the
# rise, the stations and the developed finger.  The hole size ships as a
# native Hole Wizard callout. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FlatSheetProfile": {
        "Length",
        "RailWidth",
        "SlitWidth",
        "BridgeX0",
        "BridgeX1",
        "EndR1",
        "SlitCornerR1",
    },
    "FlatSheet": {"SheetDepth"},
    "SpringRail": {"SpringRailWidth"},
    "SpringRailPath": {"BendR5"},
    "ScrewHoles": {"LeftX", "RightX", "LeftZ"},
    "PlanReference": {"OverallWidth"},
    "ProfileReference": {
        *(name for name, _x, _drive in DRAWN_TANGENT_STATIONS),
        "CrestRise",
        "FlatFinger",
    },
}
# Places.  The hole stations and the hole row's height (their pattern matches
# the platen's taps: the holes float over the shanks by both patterns' zones
# only at .XXX) print .XXX (POSITION_PLACES); the bow tangent stations on the
# hole stations are references spelled as those are, the rest as the bridge
# ends they meet.  Everything else prints .XX: on a part this small the .X
# band (+/-.1) would swallow the rail, the slit and the bow; the stock sheet
# and the spring rail are three-place references.
_TANGENT_PLACES = {"TangentX1": POSITION_PLACES, "TangentX8": POSITION_PLACES}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "FlatSheetProfile": {
        "Length": LENGTH_PLACES,
        "RailWidth": RAIL_WIDTH_PLACES,
        "SlitWidth": SLIT_PLACES,
        "BridgeX0": 2,
        "BridgeX1": 2,
        "EndR1": 2,
        "SlitCornerR1": 2,
    },
    "FlatSheet": {"SheetDepth": 3},
    "SpringRail": {"SpringRailWidth": 3},
    "SpringRailPath": {"BendR5": 2},
    "ScrewHoles": {name: POSITION_PLACES for name in ("LeftX", "RightX", "LeftZ")},
    "PlanReference": {"OverallWidth": WIDTH_PLACES},
    "ProfileReference": {
        **{
            name: _TANGENT_PLACES.get(name, 2)
            for name, _x, _d in DRAWN_TANGENT_STATIONS
        },
        "CrestRise": 2,
        "FlatFinger": 2,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if DRAWING_PRECISION.keys() != DRAWING_DIMENSIONS.keys() or any(
    set(DRAWING_PRECISION[feature]) != names
    for feature, names in DRAWING_DIMENSIONS.items()
):
    raise AssertionError("every marked platen-clip dimension needs authored places")
# Printed as references (parenthesised): the sheet stock, the spring rail's
# width (what the overall width, the screw rail and the slit leave), the bows'
# drawn stations and radius (the rise and the plan's hole and bridge stations
# fix them), and the developed finger.
REFERENCE_DIMENSIONS = frozenset(
    {
        "SheetDepth",
        "SpringRailWidth",
        "BendR5",
        "FlatFinger",
        *(name for name, _x, _drive in DRAWN_TANGENT_STATIONS),
    }
)
# Construction-only reference sketches the part saves hidden; the drawing
# shows each in the view that dimensions it.
REFERENCE_SKETCHES = ("PlanReference", "ProfileReference")
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"


def clip_volumes(
    sheet_t: float = SHEET_T, notch_w: float = NOTCH_WIDTH
) -> tuple[float, float, float, float]:
    """(flat sheet, spring rail, rounded ends, holes) volumes in mm^3.

    Parametric in the two knobs ``EQUATION_FLEX`` edits: the sheet thickness,
    and the slit width, which narrows the spring rail and its end rounds.
    """
    spring_w = CLIP_WIDTH - SCREW_RAIL_WIDTH - notch_w
    end_r = spring_w / 2.0
    # Plan area of the screw rail with its four rounded corners, plus the
    # bridge between the slits' half-round ends.
    flat = (
        CLIP_LENGTH * SCREW_RAIL_WIDTH
        - _CORNER_LOSS
        + CENTER_BRIDGE_LENGTH * notch_w
        - math.pi * (notch_w / 2.0) ** 2
    ) * sheet_t
    # A mid-plane thin wall's section area is exactly sheet_t x path length.
    path = (
        2.0 * (HOLE_INSET - end_r)
        + CENTER_BRIDGE_LENGTH
        + 2.0 * 4.0 * BEND_RADIUS * BEND_ANGLE
    )
    spring = path * sheet_t * spring_w
    # Each full end circle overlaps one half-circle of the flat tip run,
    # leaving exactly two outer half-circles of additional material.
    ends = math.pi * end_r**2 * sheet_t
    holes = 2.0 * math.pi * (HOLE_DIA / 2.0) ** 2 * sheet_t
    return flat, spring, ends, holes


V_FLAT_SHEET, V_SPRING_RAIL, V_ROUNDED_ENDS, V_HOLES = clip_volumes()
V_FINAL = V_FLAT_SHEET + V_SPRING_RAIL + V_ROUNDED_ENDS - V_HOLES

if not math.isclose(
    SCREW_RAIL_WIDTH + NOTCH_WIDTH + SPRING_RAIL_WIDTH,
    CLIP_WIDTH,
    abs_tol=1e-9,
):
    raise AssertionError("platen clip lane widths must close to ClipWidth")
if HOLE_Y - HOLE_DIA / 2.0 <= 0.0 or HOLE_Y + HOLE_DIA / 2.0 >= SCREW_RAIL_WIDTH:
    raise AssertionError(
        "platen clip screw holes must stay wholly inside the flat rail"
    )
if HEAD_TO_SPRING_RAIL <= 0.0:
    raise AssertionError("platen clip screw heads must clear the spring rail in plan")
if HEAD_RAIL_MARGIN <= 0.0:
    raise AssertionError("platen clip screw heads must lie wholly on the screw rail")
if HOLE_INSET - HEAD_DIA / 2.0 <= SCREW_RAIL_END_RADIUS:
    raise AssertionError("platen clip screw heads must sit clear of the rounded ends")
if SCREW_RAIL_END_RADIUS + SCREW_RAIL_SLIT_RADIUS >= SCREW_RAIL_WIDTH:
    raise AssertionError("screw rail corner rounds must leave a straight end")
if CENTER_BRIDGE_LENGTH <= 2.0 * SLIT_END_RADIUS:
    raise AssertionError("slit end rounds must leave an intact bridge")
# The end round must lie wholly on the flat tip, before the bow lifts.
if TIP_FLAT_LENGTH < SPRING_END_RADIUS or BOW_RUN <= 0.0 or ARCH_RISE <= 0.0:
    raise AssertionError(
        "platen clip spring bows need a flat tip, positive run and rise"
    )
if BEND_RADIUS <= SHEET_T / 2.0:
    raise AssertionError("platen clip bend radius must exceed half the sheet")
# Heads seat directly on the sheet: the shank's remainder is all thread.
if abs(CLIP_THICKNESS + SOCKET_THREAD_ENGAGEMENT - SHANK_LEN) > 1e-9:
    raise AssertionError("clip/platen stack no longer finishes at the screw tip")
if abs(SOCKET_THREAD_ENGAGEMENT - (PLATE_THICKNESS + SOCKET_BOSS_H)) > 1e-9:
    raise AssertionError("clip screw receiver no longer runs through plate and boss")
if SOCKET_THREAD_ENGAGEMENT + 1e-9 < 1.5 * THREAD_MAJOR_MM[THREAD]:
    raise AssertionError(
        f"clip {THREAD} engagement {SOCKET_THREAD_ENGAGEMENT:.4f} < 1.5D (drawing-guidelines.md rule 18 (thread engagement))"
    )
if HOLE_DIA < SHANK_DIA:
    raise AssertionError("stock clip-screw shank does not clear the clip")
if (
    min(EDGE_LIGAMENT_MIN, SLIT_LIGAMENT_MIN, END_LIGAMENT_MIN, FAR_END_LIGAMENT_MIN)
    < LIGAMENT_FLOOR
):
    raise AssertionError(
        "platen clip screw-hole ligaments at the printed worst case "
        f"(edge {EDGE_LIGAMENT_MIN:.3f}, slit {SLIT_LIGAMENT_MIN:.3f}, end "
        f"{END_LIGAMENT_MIN:.3f}, far end {FAR_END_LIGAMENT_MIN:.3f}) under the "
        ".080 in target (drawing-guidelines.md rule 17)"
    )
# The slit prints its own .XX width; its worst case keeps the floor open.
SLIT_WIDTH_MIN = NOTCH_WIDTH - printed_band_mm(SLIT_PLACES, unit=UNIT)
if SLIT_WIDTH_MIN < SLIT_GAP_FLOOR - 1e-9:
    raise AssertionError(
        f"platen clip slit narrows to {SLIT_WIDTH_MIN:.3f} at the printed worst "
        f"case, under the photographed {SLIT_GAP_FLOOR:.3f} it must keep open"
    )
if CLIP_SCREW_ENGAGEMENT_MIN < 1.5 * THREAD_MAJOR_MM[THREAD]:
    raise AssertionError(
        f"clip {THREAD} worst-case engagement {CLIP_SCREW_ENGAGEMENT_MIN:.3f} < 1.5D "
        "(drawing-guidelines.md rule 18 (thread engagement))"
    )
if HOLE_FLOAT_MIN < 2.0 * PATTERN_POSITION_ZONE:
    raise AssertionError(
        f"platen clip {CLEARANCE_SIZE} {HOLE_FIT} hole floats {HOLE_FLOAT_MIN:.3f} "
        f"over the shank, under the two patterns' {2.0 * PATTERN_POSITION_ZONE:.3f}"
    )
if HEAD_BEARING_LAND_MIN <= 0.0:
    raise AssertionError("platen clip screw head pulls through the largest hole")


def _bow_points(x0: float, s0: float) -> dict[str, tuple[float, float]]:
    """One bow's arc centres and joins in the Top sketch, (x, s = -Z)."""
    r, a = BEND_RADIUS, BEND_ANGLE
    x1 = x0 + BOW_RUN
    lift = s0 + r * (1.0 - math.cos(a))
    return {
        "c1": (x0, s0 + r),
        "p1": (x0 + r * math.sin(a), lift),
        "c2": (x0 + BOW_RUN / 2.0, s0 + ARCH_RISE - r),
        "p2": (x1 - r * math.sin(a), lift),
        "c3": (x1, s0 + r),
    }


_BOW_JOINS = [
    x
    for x0 in (HOLE_INSET, BRIDGE_X1)
    for x in (
        x0,
        _bow_points(x0, 0.0)["p1"][0],
        _bow_points(x0, 0.0)["p2"][0],
        x0 + BOW_RUN,
    )
]
if len(_BOW_JOINS) != len(TANGENT_STATIONS) or any(
    not math.isclose(x, join, abs_tol=1e-9)
    for (_name, x, _drive), join in zip(TANGENT_STATIONS, _BOW_JOINS)
):
    raise AssertionError("platen clip tangent stations must be the bows' arc joins")


async def _flat_sheet_outline(adapter) -> SketchDims:
    """Screw rail plus middle bridge in the open Front sketch, fully defined.

    Drawn counter-clockwise from the outer edge: rounded outer corners, the
    slit-side corners, then the bridge between the slits' half-round ends.
    add_arc runs counter-clockwise start -> end, so the two slit-end arcs
    (traversed clockwise by the outline) are entered end-first.
    """
    dims = SketchDims()
    length, rail = CLIP_LENGTH, SCREW_RAIL_WIDTH
    ro, ri, rs = SCREW_RAIL_END_RADIUS, SCREW_RAIL_SLIT_RADIUS, SLIT_END_RADIUS
    y0 = SPRING_RAIL_Y0
    set_sketch_direct_db(adapter, True)
    bottom = check("outer edge", await adapter.add_line(ro, 0.0, length - ro, 0.0))
    c_br = check(
        "outer far corner",
        await adapter.add_arc(length - ro, ro, length - ro, 0.0, length, ro),
    )
    right = check("far end", await adapter.add_line(length, ro, length, rail - ri))
    c_tr = check(
        "slit far corner",
        await adapter.add_arc(
            length - ri, rail - ri, length, rail - ri, length - ri, rail
        ),
    )
    top_r = check(
        "far slit edge", await adapter.add_line(length - ri, rail, BRIDGE_X1, rail)
    )
    slit_r = check(
        "far slit end",
        await adapter.add_arc(BRIDGE_X1, rail + rs, BRIDGE_X1, y0, BRIDGE_X1, rail),
    )
    bridge = check("bridge edge", await adapter.add_line(BRIDGE_X1, y0, BRIDGE_X0, y0))
    slit_l = check(
        "near slit end",
        await adapter.add_arc(BRIDGE_X0, rail + rs, BRIDGE_X0, rail, BRIDGE_X0, y0),
    )
    top_l = check("near slit edge", await adapter.add_line(BRIDGE_X0, rail, ri, rail))
    c_tl = check(
        "slit near corner",
        await adapter.add_arc(ri, rail - ri, ri, rail, 0.0, rail - ri),
    )
    left = check("near end", await adapter.add_line(0.0, rail - ri, 0.0, ro))
    c_bl = check("outer near corner", await adapter.add_arc(ro, ro, 0.0, ro, ro, 0.0))
    set_sketch_direct_db(adapter, False)

    for label, first, second, relation in (
        ("outer edge horizontal", bottom, None, "horizontal"),
        ("far slit edge horizontal", top_r, None, "horizontal"),
        ("bridge edge horizontal", bridge, None, "horizontal"),
        ("near slit edge horizontal", top_l, None, "horizontal"),
        ("far end vertical", right, None, "vertical"),
        ("near end vertical", left, None, "vertical"),
        ("outer far corner tangent edge", c_br, bottom, "tangent"),
        ("outer far corner tangent end", c_br, right, "tangent"),
        ("slit far corner tangent end", c_tr, right, "tangent"),
        ("slit far corner tangent slit", c_tr, top_r, "tangent"),
        ("far slit end tangent rail", slit_r, top_r, "tangent"),
        ("far slit end tangent bridge", slit_r, bridge, "tangent"),
        ("near slit end tangent bridge", slit_l, bridge, "tangent"),
        ("near slit end tangent rail", slit_l, top_l, "tangent"),
        ("slit near corner tangent slit", c_tl, top_l, "tangent"),
        ("slit near corner tangent end", c_tl, left, "tangent"),
        ("outer near corner tangent end", c_bl, left, "tangent"),
        ("outer near corner tangent edge", c_bl, bottom, "tangent"),
        ("slit edges one line", top_l, top_r, "collinear"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, relation))

    await anchor_point_to_origin(
        adapter, f"{bottom}.start", ro, 0.0, "outer edge start"
    )
    dims.record("EdgeStartX", '"ScrewRailEndR"')
    # The overall length, end to end (the print's one length dimension).
    await dimension_between(
        adapter,
        f"{left}.start",
        f"{right}.start",
        "horizontal_distance",
        length,
        "clip length",
    )
    dims.record("Length", '"ClipLength"')
    for name, arc, radius, expr in (
        ("EndR1", c_br, ro, '"ScrewRailEndR"'),
        ("EndR2", c_bl, ro, '"ScrewRailEndR"'),
        ("SlitCornerR1", c_tr, ri, '"ScrewRailSlitR"'),
        ("SlitCornerR2", c_tl, ri, '"ScrewRailSlitR"'),
    ):
        check(
            f"{name} radius",
            await adapter.add_sketch_dimension(arc, None, "radial", radius),
        )
        dims.record(name, expr)
    await dimension_between(
        adapter,
        f"{bottom}.start",
        f"{top_l}.end",
        "vertical_distance",
        rail,
        "screw rail width",
    )
    dims.record("RailWidth", '"ScrewRailW"')
    # The slit's own width, across its rounded end at the near bridge end.
    await dimension_between(
        adapter,
        f"{top_l}.start",
        f"{bridge}.end",
        "vertical_distance",
        NOTCH_WIDTH,
        "slit width",
    )
    dims.record("SlitWidth", '"NotchW"')
    # The bridge's two ends (the slits' rounded ends) from the near end.
    await dimension_between(
        adapter,
        "origin",
        f"{bridge}.end",
        "horizontal_distance",
        BRIDGE_X0,
        "bridge start",
    )
    dims.record("BridgeX0", '"BridgeX0"')
    await dimension_between(
        adapter,
        "origin",
        f"{bridge}.start",
        "horizontal_distance",
        BRIDGE_X1,
        "bridge end",
    )
    dims.record("BridgeX1", '"BridgeX0" + "CenterBridgeL"')
    return dims


async def _spring_mid_surface(adapter) -> SketchDims:
    """The spring rail's mid-surface path in the open Top sketch, fully defined.

    Top-plane sketch (x, s) is part (X, -Z): the flats lie at s = -SHEET_T/2
    and the bows rise toward +s, away from the platen.  Drawn left to right,
    endpoints merged at creation (inference OFF); the convex crown arcs run
    counter-clockwise against the travel, so they are entered end-first.
    """
    dims = SketchDims()
    s0 = -SHEET_T / 2.0
    tip_x0 = SPRING_END_RADIUS
    tip_x1 = CLIP_LENGTH - SPRING_END_RADIUS
    near = _bow_points(HOLE_INSET, s0)
    far = _bow_points(BRIDGE_X1, s0)
    far_end = CLIP_LENGTH - HOLE_INSET
    set_sketch_direct_db(adapter, True)
    tip_l = check("near tip flat", await adapter.add_line(tip_x0, s0, HOLE_INSET, s0))
    a1 = check(
        "near lift",
        await adapter.add_arc(*near["c1"], HOLE_INSET, s0, *near["p1"]),
    )
    a2 = check(
        "near crown", await adapter.add_arc(*near["c2"], *near["p2"], *near["p1"])
    )
    a3 = check(
        "near return", await adapter.add_arc(*near["c3"], *near["p2"], BRIDGE_X0, s0)
    )
    mid = check("bridge flat", await adapter.add_line(BRIDGE_X0, s0, BRIDGE_X1, s0))
    a4 = check("far lift", await adapter.add_arc(*far["c1"], BRIDGE_X1, s0, *far["p1"]))
    a5 = check("far crown", await adapter.add_arc(*far["c2"], *far["p2"], *far["p1"]))
    a6 = check("far return", await adapter.add_arc(*far["c3"], *far["p2"], far_end, s0))
    tip_r = check("far tip flat", await adapter.add_line(far_end, s0, tip_x1, s0))
    set_sketch_direct_db(adapter, False)

    for label, first, second, relation in (
        ("near tip horizontal", tip_l, None, "horizontal"),
        ("bridge flat horizontal", mid, None, "horizontal"),
        ("far tip horizontal", tip_r, None, "horizontal"),
        ("near lift tangent tip", a1, tip_l, "tangent"),
        ("near crown tangent lift", a2, a1, "tangent"),
        ("near return tangent crown", a3, a2, "tangent"),
        ("near return tangent bridge", a3, mid, "tangent"),
        ("far lift tangent bridge", a4, mid, "tangent"),
        ("far crown tangent lift", a5, a4, "tangent"),
        ("far return tangent crown", a6, a5, "tangent"),
        ("far return tangent tip", a6, tip_r, "tangent"),
        ("bridge flat in the sheet plane", mid, tip_l, "collinear"),
        ("far tip in the sheet plane", tip_r, tip_l, "collinear"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, relation))

    await anchor_point_to_origin(adapter, f"{tip_l}.start", tip_x0, s0, "tip start")
    dims.record("PathStartX", '"SpringEndR"')
    dims.record("PathStartZ", '"SheetT" / 2')
    # The bow's start station from the near end (the tip flat's length is what
    # it leaves past the end round).
    await dimension_between(
        adapter,
        "origin",
        f"{tip_l}.end",
        "horizontal_distance",
        HOLE_INSET,
        "near bow start",
    )
    dims.record("BowStartX", '"HoleInset"')
    for index, arc in enumerate((a1, a2, a3, a4, a5, a6), start=1):
        check(
            f"bend {index} radius",
            await adapter.add_sketch_dimension(arc, None, "radial", BEND_RADIUS),
        )
        dims.record(f"BendR{index}", '"BendR"')
    await dimension_between(
        adapter,
        "origin",
        f"{mid}.start",
        "horizontal_distance",
        BRIDGE_X0,
        "near bow end",
    )
    dims.record("BridgeX0", '"BridgeX0"')
    check(
        "bridge flat length",
        await adapter.add_sketch_dimension(mid, None, "linear", CENTER_BRIDGE_LENGTH),
    )
    dims.record("BridgeLength", '"CenterBridgeL"')
    await dimension_between(
        adapter,
        "origin",
        f"{tip_r}.start",
        "horizontal_distance",
        far_end,
        "far bow end",
    )
    dims.record("FarBowEndX", '"HoleFarX"')
    check(
        "far tip flat length",
        await adapter.add_sketch_dimension(tip_r, None, "linear", TIP_FLAT_LENGTH),
    )
    dims.record("TipFlatL2", '"HoleInset" - "SpringEndR"')
    return dims


def _construction(adapter, segment: str, label: str) -> None:
    """Flag one sketch segment as construction geometry, read back."""
    entity = _early_bound(adapter._sketch_entities[segment], "ISketchSegment")
    entity.ConstructionGeometry = True
    if not bool(entity.ConstructionGeometry):
        raise RuntimeError(f"{label} did not take the construction flag")


async def _plan_reference(adapter) -> SketchDims:
    """Drawing-only overall width in the open Front sketch, fully defined.

    One construction line up the near end's line, from the outer edge's
    level (the origin) to the spring rail's outer edge: the plan prints the
    overall width from the outer edge, where the profile sketches leave it
    only as the sum of the screw rail, the slit and the spring rail.
    """
    dims = SketchDims()
    set_sketch_direct_db(adapter, True)
    line = check(
        "overall width reference line",
        await adapter.add_line(0.0, 0.0, 0.0, CLIP_WIDTH),
    )
    set_sketch_direct_db(adapter, False)
    _construction(adapter, line, "overall width reference")
    check(
        "overall width reference vertical",
        await adapter.add_sketch_constraint(line, None, "vertical"),
    )
    await anchor_point_to_origin(
        adapter, f"{line}.start", 0.0, 0.0, "overall width at the outer edge"
    )
    await dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        "vertical_distance",
        CLIP_WIDTH,
        "overall width",
    )
    dims.record("OverallWidth", '"ClipWidth"')
    return dims


async def _profile_reference(adapter) -> SketchDims:
    """Drawing-only bow references in the open Top sketch, fully defined.

    Top-plane (x, s) is part (X, -Z), as in ``_spring_mid_surface``: the flat
    sheet spans s = -SHEET_T..0 and the bows rise toward +s, so the face the
    bows rise from is s = 0 and their crest on it s = ARCH_RISE.  All
    construction: a chain along the sheet's back face (s = -SHEET_T) whose
    joins stand at the drawn stations (DRAWN_TANGENT_STATIONS), each
    dimensioned from the near end; a riser up from the far end's face, whose
    span is the rise, and a
    level from its top back to the far bow's crest (outside the part, as the
    rise's extension lines would run); and a line along the near finger's face
    from the bridge end, as long as the finger's developed (flat) length.
    """
    dims = SketchDims()
    t = SHEET_T
    set_sketch_direct_db(adapter, True)
    chain: list[str] = []
    x_prev = 0.0
    for name, x, _drive in DRAWN_TANGENT_STATIONS:
        chain.append(
            check(f"{name} station line", await adapter.add_line(x_prev, -t, x, -t))
        )
        x_prev = x
    riser = check(
        "crest rise line",
        await adapter.add_line(CLIP_LENGTH, 0.0, CLIP_LENGTH, ARCH_RISE),
    )
    level = check(
        "crest level line",
        await adapter.add_line(CLIP_LENGTH, ARCH_RISE, FAR_CREST_X, ARCH_RISE),
    )
    finger = check(
        "developed finger line",
        await adapter.add_line(BRIDGE_X0, 0.0, BRIDGE_X0 - FLAT_FINGER_LENGTH, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    for segment in (*chain, riser, level, finger):
        _construction(adapter, segment, "bow reference")
    for segment, relation in (
        *((segment, "horizontal") for segment in chain),
        (riser, "vertical"),
        (level, "horizontal"),
        (finger, "horizontal"),
    ):
        check(
            f"bow reference {relation}",
            await adapter.add_sketch_constraint(segment, None, relation),
        )

    await anchor_point_to_origin(
        adapter, f"{chain[0]}.start", 0.0, -t, "stations on the back face"
    )
    dims.record(None, '"SheetT"')
    for (name, x, drive), segment in zip(DRAWN_TANGENT_STATIONS, chain):
        await dimension_between(
            adapter,
            f"{chain[0]}.start",
            f"{segment}.end",
            "horizontal_distance",
            x,
            name,
        )
        dims.record(name, drive)

    await anchor_point_to_origin(
        adapter, f"{riser}.start", CLIP_LENGTH, 0.0, "rise at the far end"
    )
    dims.record(None, '"ClipLength"')
    await dimension_between(
        adapter, "origin", f"{level}.end", "horizontal_distance", FAR_CREST_X, "crest"
    )
    dims.record(None, '"HoleFarX" - "BowRun" / 2')
    await dimension_between(
        adapter,
        f"{riser}.start",
        f"{riser}.end",
        "vertical_distance",
        ARCH_RISE,
        "crest rise",
    )
    dims.record("CrestRise", '"ArchRise"')

    await anchor_point_to_origin(
        adapter, f"{finger}.start", BRIDGE_X0, 0.0, "finger from the bridge"
    )
    dims.record(None, '"BridgeX0"')
    # Developed length: no trig in the equation manager (build_ch_rocker_arm),
    # so it is the as-built value, re-derived from the knobs on every build.
    await dimension_between(
        adapter,
        f"{finger}.start",
        f"{finger}.end",
        "horizontal_distance",
        FLAT_FINGER_LENGTH,
        "developed finger",
    )
    dims.record("FlatFinger")
    return dims


def _thin_extrude_at_offset(
    adapter, depth: float, offset: float, thickness: float
) -> str:
    """Mid-plane thin boss of the last exited open sketch, offset from its plane.

    The adapter's thin extrusion only starts at the sketch plane, and
    ``_extrude.extrude_at_offset`` makes solid bosses only, so this is the
    same raw ``FeatureExtrusion3``-style call on ``FeatureExtrusionThin2``
    with T0 = swStartOffset and the wall split evenly about the path
    (RevThinDir 2, mid-plane).  Millimetre arguments; returns the feature name.
    """
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    sketch_name = feature_name_by_type(adapter, "ProfileFeature")
    if not sketch_name:
        raise RuntimeError("thin extrude: no sketch found to consume")
    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        sketch_name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"thin extrude: cannot select sketch {sketch_name!r}")
    feature = model.FeatureManager.FeatureExtrusionThin2(
        True,  # Sd: single direction
        False,  # Flip (unused)
        False,  # Dir: along the sketch normal
        0,  # T1: swEndCondBlind
        0,  # T2
        depth / 1000.0,  # D1
        0.0,  # D2
        False,
        False,  # Dchk1/2
        False,
        False,  # Ddir1/2
        0.0,
        0.0,  # Dang1/2
        False,
        False,  # OffsetReverse1/2
        False,
        False,  # TranslateSurface1/2
        True,  # Merge
        thickness / 1000.0,  # Thk1: total wall for mid-plane
        0.0,  # Thk2 (two-direction only)
        0.0,  # EndThk
        2,  # RevThinDir: mid-plane
        0,  # CapEnds
        False,  # AddBends
        0.0,  # BendRad
        False,  # UseFeatScope
        True,  # UseAutoSelect
        3,  # T0: swStartOffset
        offset / 1000.0,  # StartOffset
        False,  # FlipStartOffset
    )
    model.ClearSelection2(True)
    if feature is None:
        raise RuntimeError("thin extrude: FeatureExtrusionThin2 returned None")
    name = str(_read_member(feature, "Name"))
    _telemetry.success(f"thin extrude {sketch_name} @ +{offset:g} -> {name}")
    return name


def _z_extremes(adapter) -> tuple[float, float]:
    """(min, max) local Z (mm) of the part's single solid body.

    ``IBody2::GetExtremePoint`` is exact; the early-bound wrapper returns
    (ok, x, y, z) in metres.
    """
    doc = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = adapter._attempt(lambda: doc.GetBodies2(0, False)) or []
    if len(bodies) != 1:
        raise RuntimeError(f"platen clip: expected one solid body, found {len(bodies)}")
    body = _early_bound(bodies[0], "IBody2")
    out = []
    for direction in ((0.0, 0.0, -1.0), (0.0, 0.0, 1.0)):
        res = adapter._attempt(
            lambda d=direction: body.GetExtremePoint(*d), default=None
        )
        if not res or len(res) < 4:
            raise RuntimeError("platen clip: GetExtremePoint failed")
        out.append(float(res[3]) * 1000.0)
    return out[0], out[1]


def _check_z_span(adapter, label: str, sheet_t: float) -> None:
    """One body, platen face at SheetT, bow crests ArchRise outboard of z = 0."""
    z_min, z_max = _z_extremes(adapter)
    if abs(z_min + ARCH_RISE) > 0.01 or abs(z_max - sheet_t) > 0.01:
        raise RuntimeError(
            f"platen clip {label}: z span {z_min:.4f}..{z_max:.4f}, expected "
            f"{-ARCH_RISE:g}..{sheet_t:g}"
        )
    _telemetry.success(f"platen clip {label}: z span {z_min:.4f}..{z_max:.4f}")


def _name_spring_rail_dimensions(adapter) -> list[tuple[str, str]]:
    """Name the thin extrusion's width, start offset and wall; drive jobs.

    Each SPRING_RAIL_DRIVES value must match exactly one of the feature's own
    display dimensions, so a parameter SolidWorks does not expose fails the
    build with the full dimension list instead of staying silently literal.
    """
    feature = _feature_by_name(adapter, "SpringRail")
    dims = list(_display_dimensions(feature, "SpringRail"))
    values = [abs(_dim_value_mm(idim)) for idim in dims]
    names: list[str | None] = [None] * len(dims)
    for name, value, _expr in SPRING_RAIL_DRIVES:
        hits = [i for i, v in enumerate(values) if abs(v - value) < 1e-6]
        if len(hits) != 1:
            raise RuntimeError(
                f"SpringRail exposes {len(hits)} display dimensions of {name} "
                f"{value:.6f} mm (need exactly one); its dimensions read "
                f"{[round(v, 6) for v in values]}"
            )
        names[hits[0]] = name
    _rename_dimensions(dims, "SpringRail", names)
    return [(f"{name}@SpringRail", expr) for name, _value, expr in SPRING_RAIL_DRIVES]


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations).  The mm suffix is load-bearing because
    # the template is IPS and bare equation-manager numbers are document units.
    await set_global(adapter, "ClipLength", f"{CLIP_LENGTH}mm")
    await set_global(adapter, "ClipWidth", f"{CLIP_WIDTH}mm")
    await set_global(adapter, "SheetT", f"{SHEET_T}mm")
    await set_global(adapter, "ScrewRailW", f"{SCREW_RAIL_WIDTH}mm")
    await set_global(adapter, "NotchW", f"{NOTCH_WIDTH}mm")
    await set_global(adapter, "SpringRailW", '"ClipWidth" - "ScrewRailW" - "NotchW"')
    await set_global(adapter, "SpringRailY0", '"ScrewRailW" + "NotchW"')
    await set_global(adapter, "CenterBridgeL", f"{CENTER_BRIDGE_LENGTH}mm")
    await set_global(adapter, "BridgeX0", '("ClipLength" - "CenterBridgeL") / 2')
    await set_global(adapter, "SpringEndR", '"SpringRailW" / 2')
    await set_global(adapter, "ScrewRailEndR", f"{SCREW_RAIL_END_RADIUS}mm")
    await set_global(adapter, "ScrewRailSlitR", f"{SCREW_RAIL_SLIT_RADIUS}mm")
    await set_global(adapter, "HoleInset", f"{HOLE_INSET}mm")
    await set_global(adapter, "HoleY", f"{HOLE_Y}mm")
    await set_global(adapter, "HoleFarX", '"ClipLength" - "HoleInset"')
    await set_global(adapter, "ArchRise", f"{ARCH_RISE}mm")
    await set_global(adapter, "BowRun", '"BridgeX0" - "HoleInset"')
    await set_global(
        adapter, "BendR", '"BowRun" * "BowRun" / (16 * "ArchRise") + "ArchRise" / 4'
    )

    drive_jobs: list[tuple[str, str]] = []

    # Flat sheet: the screw rail (the only lane drilled for the two retaining
    # screws) and the middle bridge between the two slits' rounded ends.
    check("create_sketch flat sheet", await adapter.create_sketch("Front"))
    flat = await _flat_sheet_outline(adapter)
    await ensure_fully_defined(adapter, "flat sheet outline")
    check("exit_sketch flat sheet", await adapter.exit_sketch())
    name_last_feature(adapter, "FlatSheetProfile")
    drive_jobs += flat.apply(adapter, "FlatSheetProfile")
    check(
        "extrude flat sheet",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHEET_T)),
    )
    name_last_feature(adapter, "FlatSheet")
    flat_dims = name_dimensions(adapter, "FlatSheet", ["SheetDepth"])
    drive_jobs += [(flat_dims[0], BOSS_DRIVES["FlatSheet"][0])]
    volume = V_FLAT_SHEET
    await volume_check(adapter, "flat sheet", volume, 0.005 * volume)

    # Spring rail: one smooth mid-surface path thickened SheetT about itself
    # and swept SpringRailW across, starting SpringRailY0 off the Top plane.
    # Its flat middle run lands face-to-face on the bridge's slit-side edge.
    check("create_sketch spring rail", await adapter.create_sketch("Top"))
    path = await _spring_mid_surface(adapter)
    await ensure_fully_defined(adapter, "spring rail mid-surface")
    check("exit_sketch spring rail", await adapter.exit_sketch())
    name_last_feature(adapter, "SpringRailPath")
    drive_jobs += path.apply(adapter, "SpringRailPath")
    _thin_extrude_at_offset(adapter, SPRING_RAIL_WIDTH, SPRING_RAIL_Y0, SHEET_T)
    name_last_feature(adapter, "SpringRail")
    drive_jobs += _name_spring_rail_dimensions(adapter)
    volume += V_SPRING_RAIL
    await volume_check(adapter, "flat sheet and spring rail", volume, 0.005 * volume)
    _check_z_span(adapter, "spring rail", SHEET_T)

    # Full circles overlap the flat tip run of the spring rail by one half
    # each.  Their exposed halves give both free ends a rounded planform.
    ends = SketchDims()
    check("create_sketch rounded spring ends", await adapter.create_sketch("Front"))
    spring_y = SPRING_RAIL_Y0 + SPRING_END_RADIUS
    define_jobs = (
        (
            SPRING_END_RADIUS,
            ("LeftEndX", "EndY", "LeftEndDia"),
            ('"SpringEndR"', '"SpringRailY0" + "SpringEndR"', '2 * "SpringEndR"'),
        ),
        (
            CLIP_LENGTH - SPRING_END_RADIUS,
            ("RightEndX", "RightEndY", "RightEndDia"),
            (
                '"ClipLength" - "SpringEndR"',
                '"SpringRailY0" + "SpringEndR"',
                '2 * "SpringEndR"',
            ),
        ),
    )
    for x, names, drives in define_jobs:
        await define_circle(
            adapter,
            x,
            spring_y,
            SPRING_END_RADIUS,
            "rounded spring end",
            dims=ends,
            names=names,
            drives=drives,
        )
    await ensure_fully_defined(adapter, "rounded spring ends")
    check("exit_sketch rounded spring ends", await adapter.exit_sketch())
    name_last_feature(adapter, "SpringEndProfiles")
    drive_jobs += ends.apply(adapter, "SpringEndProfiles")
    check(
        "extrude rounded spring ends",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHEET_T)),
    )
    name_last_feature(adapter, "RoundedSpringEnds")
    end_dims = name_dimensions(adapter, "RoundedSpringEnds", ["SheetDepth"])
    drive_jobs += [(end_dims[0], BOSS_DRIVES["RoundedSpringEnds"][0])]
    volume += V_ROUNDED_ENDS
    await volume_check(adapter, "rounded spring ends", volume, 0.005 * volume)

    # End screw holes: ONE native Hole Wizard #2 clearance feature (2 points)
    # from the screw rail's outer face at local z = 0, where the heads seat.
    hole_cut = wizard_holes(
        adapter,
        HOLE_SPEC,
        [
            [HOLE_INSET, HOLE_Y, 0.0],
            [CLIP_LENGTH - HOLE_INSET, HOLE_Y, 0.0],
        ],
        (0.0, 0.0, -1.0),
        f"flat-rail screw holes ({CLEARANCE_SIZE} {HOLE_FIT} clearance)",
        name="ScrewHoles",
        placement_dims=[
            (("LeftX", '"HoleInset"'), ("LeftZ", '"HoleY"')),
            (("RightX", '"HoleFarX"'), SharedCoordinate(0)),
        ],
    )
    drive_jobs += hole_cut.placement_drive_jobs
    await volume_check(adapter, "one-piece clip", V_FINAL, 0.005 * V_FINAL)

    # Drawing-only reference sketches (construction geometry, childless, saved
    # hidden below): each sits on the plane of the view that prints it, the
    # plan's on Front and the profile's on Top (build_pd_platen's floor).
    for plane, feature, define in (
        ("Front", "PlanReference", _plan_reference),
        ("Top", "ProfileReference", _profile_reference),
    ):
        check(f"create_sketch {feature}", await adapter.create_sketch(plane))
        reference = await define(adapter)
        await ensure_fully_defined(adapter, f"{feature} sketch")
        check(f"exit_sketch {feature}", await adapter.exit_sketch())
        name_last_feature(adapter, feature)
        drive_jobs += reference.apply(adapter, feature)

    # Apply deferred equations after every target exists.  Their initial values
    # are neutral, so the second volume check also catches a mis-bound knob.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven one-piece clip (equations neutral)", V_FINAL, 0.005 * V_FINAL
    )
    # Equation self-test (EQUATION_FLEX): a knob that only reshapes part of
    # the sheet misses the analytic volume, opens a second body or moves the
    # z span; every knob is restored before the part is saved.
    for knob, neutral, flexed, knob_arg in EQUATION_FLEX:
        flat, spring, ends, holes = clip_volumes(**{knob_arg: flexed})
        expected = flat + spring + ends - holes
        await set_global(adapter, knob, f"{flexed}mm")
        await force_rebuild(adapter)
        await volume_check(adapter, f"{knob} = {flexed} mm", expected, 0.005 * expected)
        span_t = flexed if knob_arg == "sheet_t" else SHEET_T
        _check_z_span(adapter, f"{knob} = {flexed} mm", span_t)
        await set_global(adapter, knob, f"{neutral}mm")
        await force_rebuild(adapter)
        await volume_check(adapter, f"{knob} restored", V_FINAL, 0.005 * V_FINAL)
        _check_z_span(adapter, f"{knob} restored", SHEET_T)

    await apply_material(adapter, MATERIAL)

    # Manufacturing drawing support: every printed dimension's places live on
    # the model (drawing-simplicity-policy.md `How the repository implements
    # the guidelines`), then mark exactly the print's dimensions (the drawing
    # imports the marked set and must find every one) and stamp the view note.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    await report_mass_properties(adapter)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    # Hidden, so no assembly renders them; the drawing shows each in its view
    # through _drawing_hidden_sketches to import its dimensions.
    for sketch in REFERENCE_SKETCHES:
        blank_sketch(adapter, sketch)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
