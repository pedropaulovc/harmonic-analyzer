r"""Create the curated machinist drawing for the magnifying wheel.

A Ø100 cast-iron spider: six tapered spokes, a grooved rim, a Ø30 boss with
the Ø.499 drum spigot, a reamed axle bore and two wire-tie holes.  Decimal-inch
sheet (#290); the hub stations and rim keep their millimetre nominals.  The wheel
axis is local +Z, so the FRONT view is the face (rim, spokes, fillets, bore,
ties) and SECTION A-A, cut along the face's horizontal centreline through the
0 and 180 deg spokes (the model's Top plane) and turned a quarter turn to lie
like the lathe holds it, is the hub profile, the rim's Ø, the groove and the
axial widths in solid lines (drawing-guidelines.md rule 9 (show internal
shape in solid lines; a spoked part is cut through a spoke)).  Every size
rides the part's marked dimensions; only the rim's axial width and the
rim-bore round's R (on its cut arc) are added on the sheet.  The rim's Ø and
the spokes' back-face offset come from a hidden reference sketch in A-A's plane,
shown in the part while A-A is cut (_drawing_hidden_sketches).  TIE 2,
radial inside the rim, shows in a broken-out window on the face
(TIE2_WINDOW).  The bore's and the spigot's matched fits are numbered notes
their own callouts link by "SEE NOTE n" (drawing-guidelines.md rule 7
(notes: few, flagged, never a method)), and the running bore carries the
part-owned roughness its fit needs (drawing-guidelines.md rule 6 (roughness
symbols only where a surface runs, slides or locates)).  A-A's cutting plane
carries the spokes' clocking on the face, and a drawn centreline the groove,
web and rim's shared plane on A-A (drawing-guidelines.md rule 26).

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_magnifying_wheel.py mg-magnifying-wheel
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _config
import _drawing_hidden_sketches
import _telemetry
from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
    set_reference_dimensions,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import ViewEdges, scan_view_edges
from _drawing_finish import add_surface_finish
from _drawing_leaders import (
    assert_leaders_clear,
    dimension_segments,
    leader_crossings,
    leader_segments,
    section_line_segments,
    set_near_side_diameter,
)
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_selection import _select_view_entity
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _layout_geometry import Box, estimate_text_box
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _machinist_review_mode import MachinistReviewMode
from _section_axis import position_section_caption
from _session import run_build
from _surface_finish import surface_finish_by_key
from _transgear_zone_line import (
    CENTER_LINE_STYLE,
    CENTER_LINE_WEIGHT,
    require_placed,
    sheet_to_sketch,
    sketch_lines,
)
from _mg_wheel_rim_geometry import RIM_AXIAL, RIM_INNER_DIA, RIM_OUTER_DIA
from mg_magnifying_wheel_geom import (
    HUB_BACK_Z,
    HUB_FRONT_Z,
    SPOKE_ROOT_WIDTH,
    SPOKE_TIP_WIDTH,
    SPOKE_X0,
)
from mg_magnifying_wheel_spec import (
    BORE_DIA,
    BORE_FIT_NOTE,
    CAST_ROUND_R,
    DIAMETER_REFERENCE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    DRAWING_REFERENCE_PRECISION,
    GROOVE_BOTTOM_DIA,
    GROOVE_SEAT_NOTE,
    HUB_DIA,
    HUB_FILLET_PRINTED,
    HUB_FILLET_R,
    REFERENCE_DIMENSIONS,
    RIM_FILLET_PRINTED,
    RIM_FILLET_R,
    ROUND_TEXT_SUFFIX,
    SPIGOT_DIA,
    SPIGOT_FIT_NOTE,
    SPOKE_AXIAL,
    SPOKE_PITCH_DEG,
    SURFACE_FINISHES,
    TIE1_CLOCK_DEG,
    TIE1_R,
    TIE2_CLOCK_DEG,
    TIE2_FROM_SPOKE_DEG,
    TIE_HOLE_DIA,
    clock_to_local_deg,
    fillet,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    view_name,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["mg_magnifying_wheel"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 1.0)
# The face stands far enough left that the rim's two Ø lines
# (SECTION_DIAMETER_KEEP) run left of A-A clear of the face's right-hand
# callouts; its leftmost texts (TIE 1's Y, the bore's block) keep their air
# to the border.
FRONT_CENTER = (0.100, 0.150)
# Section A-A stands right of the face, 15 mm above its axis (it is placed
# unaligned, so its y is set here): its native SECTION A-A caption is tall
# and needs the room between the hub's axial rows and the title block.
SECTION_CENTER = (0.255, 0.165)
# The isometric stands right of the section's groove and spigot Ø texts,
# ISO_CLEAR off them, and above the spigot length's row, whose one-line
# callout names the drum by number and runs right past the section.
ISO_CENTER = (0.372, 0.200)
ISO_CLEAR = 0.005

_RIM_R = RIM_OUTER_DIA * SHEET_SCALE[0] / 2000.0
# HubFrontZ's centre-plane extension line ends on the lower groove's bottom,
# inside the notch, so the .61 visibly lands on the groove it locates: with
# the line stopping a gap short of the OD, integration proof
# 20261109T105251629Z (r1) read every axial dimension as ending at a rim
# face and the groove as unlocated.
_GROOVE_BOTTOM_R = GROOVE_BOTTOM_DIA * SHEET_SCALE[0] / 2000.0
# The cutting line runs the face view's full width along the horizontal
# centreline, through the bore and the 0 and 180 deg spokes, this far past
# the OD at each end, clear of the tip width's extension lines; the A-A
# caption's top centre stands under the section's axial rows, above the
# title block.
SECTION_LINE_OVERRUN = 0.008
SECTION_LINE_LANDING = (0.0, _RIM_R + SECTION_LINE_OVERRUN + 0.005)
SECTION_CAPTION_XY = (SECTION_CENTER[0], 0.088)
# The turn's label stands centred under the caption (top-left anchored,
# capitals about 2.6 mm a character), above the title block.
ROTATION_NOTE_TOP = SECTION_CAPTION_XY[1] - 0.009
ROTATION_NOTE_CHAR = 0.0026
_SECTION_PLACEMENT_TOL = 1e-5

DRAWING_PRECISION_BY_NAME = {
    name: digits
    for names in DRAWING_PRECISION.values()
    for name, digits in names.items()
}

# Face view.  The sheet's front view is the model's XY plane at 1:1 (sheet x
# = model x), so each text point below is derived from the feature it names.
# Every text and finish symbol stands outside the rim's silhouette
# (drawing-guidelines.md rule 14 (keep text off the part)), and no leader or
# shoulder may cross another's line: a native rim Ø line would run rim to rim
# through the centre, under the shoulders.  The bore's Ø takes one arrow on
# its near rim (set_near_side_diameter), so only the bore's leader, its
# finish's and the spoke root's offset-text leader cross the face; the rim's
# two Ø print on A-A (rule 11).  The A-A cutting line runs along the
# horizontal centreline (y = 0): its arrows point up (the section looks along
# +Y) with their letters beyond the tips, so every face leader leaves its
# feature above or below it and none crosses it.
#
# A dimension's position is its text block's mid-height above the point its
# leader or shoulder meets (a one-line shoulder runs 2.8 mm under its point,
# a two-line one 5.6 mm; a multi-line callout stands on one shoulder under
# its last line), and its text runs away from the feature it measures.
_TEXT_LINE = 0.0056
# A leadered Ø callout's shoulder starts this far (mm) left of its point, and
# its stacked tolerance tops out this far over it.
_CALLOUT_SHOULDER_LEFT = 15.3
_CALLOUT_ABOVE = 6.3


def _face(x_mm: float, y_mm: float) -> tuple[float, float]:
    """A model XY point (mm) on the sheet (m)."""
    return (
        FRONT_CENTER[0] + x_mm * SHEET_SCALE[0] / 1000.0,
        FRONT_CENTER[1] + y_mm * SHEET_SCALE[0] / 1000.0,
    )


def _polar(origin_mm: tuple[float, float], bearing_deg: float, reach_mm: float):
    """The model point ``reach_mm`` from ``origin_mm`` along ``bearing_deg``."""
    bearing = math.radians(bearing_deg)
    return (
        origin_mm[0] + reach_mm * math.cos(bearing),
        origin_mm[1] + reach_mm * math.sin(bearing),
    )


def _over(attach_mm: tuple[float, float], lines: int) -> tuple[float, float]:
    """The text point whose ``lines``-line block stands on ``attach_mm``."""
    x, y = _face(*attach_mm)
    return (x, y + lines * _TEXT_LINE / 2.0)


def _printed_fillet(
    circle_r: float, fillet_r: float, outside: bool, printed: tuple[int, int]
) -> tuple[tuple[float, float], tuple[float, float]]:
    """The centre (model mm) of the fillet whose R the face view prints (the
    builder's first pick, mg_magnifying_wheel_spec.HUB_FILLET_PRINTED), and its
    arc's two end bearings (deg) from that centre."""
    seed = fillet(circle_r, fillet_r, outside)
    spoke, side = printed
    turn = math.radians(spoke * SPOKE_PITCH_DEG)

    def place(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point[0], side * point[1]
        return (
            x * math.cos(turn) - y * math.sin(turn),
            x * math.sin(turn) + y * math.cos(turn),
        )

    centre = place(seed["centre"])
    ends = tuple(
        math.degrees(math.atan2(end[1] - centre[1], end[0] - centre[0]))
        for end in (place(seed["on_side"]), place(seed["on_circle"]))
    )
    return centre, ends


_HUB_FILLET = _printed_fillet(HUB_DIA / 2.0, HUB_FILLET_R, True, HUB_FILLET_PRINTED)
_RIM_FILLET = _printed_fillet(
    RIM_INNER_DIA / 2.0, RIM_FILLET_R, False, RIM_FILLET_PRINTED
)
_TIE1 = _polar((0.0, 0.0), clock_to_local_deg(TIE1_CLOCK_DEG), TIE1_R)
# TIE 2's clock is the spoke reference's driven angle from the 180 deg
# spoke's centreline (on A-A's cutting line) to the hole's radial
# axis (outward at 223 deg), its vertex on the bore axis (drawing-guidelines.md
# rule 10: dimension from a real feature).  Its text stands
# _TIE2_CLOCK_TEXT_R out on the sector's bisector, past the OD: its arc
# crosses TIE 1's lower Y extension line well inside that line's end
# (78 mm out), and its text stands clear of the rim and of the Y's text.
_TIE2_OUTWARD = clock_to_local_deg(TIE2_CLOCK_DEG) % 360.0
_TIE2_CLOCK_SECTOR = (_TIE2_OUTWARD - TIE2_FROM_SPOKE_DEG, _TIE2_OUTWARD)
_TIE2_CLOCK_TEXT_R = 64.0
# TIE 2 runs inside the rim, so the hidden-lines-removed face view draws
# none of it.  A broken-out window on its axis cuts the rim at the wheel's
# mid-plane, the plane of TIE 2's axis and of the sketch its Ø and angle
# dimension, so both stand on the hole's cut walls (drawing-guidelines.md
# rule 9 (never dimension to a hidden line)).  The window is (s, t) mm about
# the hole: s out along its axis, t across it along _TIE2_ACROSS (sheet
# down-right).  It runs from the rim bore's air past the OD and stays narrow
# across the axis, so the clock's legs cross no hatch.
_TIE2_ALONG = (
    math.cos(math.radians(_TIE2_OUTWARD)),
    math.sin(math.radians(_TIE2_OUTWARD)),
)
_TIE2_ACROSS = (-_TIE2_ALONG[1], _TIE2_ALONG[0])
TIE2_WINDOW = (
    (43.4, 0.0),
    (44.2, -0.95),
    (47.0, -1.0),
    (50.2, -0.9),
    (51.0, 0.0),
    (50.2, 1.9),
    (47.0, 2.1),
    (44.2, 1.9),
)
# The face view looks at the hub's back face, the part's nearest, so the
# window's depth reaches the mid-plane from it; measured from the rim's own
# face instead it stops HUB_BACK_Z - RIM_AXIAL / 2 short, well inside TIE 2.
_TIE2_WINDOW_DEPTH = HUB_BACK_Z


def tie2_window_point(s: float, t: float) -> tuple[float, float]:
    """Model (x, y) mm of the TIE 2 window point (s, t)."""
    return (
        s * _TIE2_ALONG[0] + t * _TIE2_ACROSS[0],
        s * _TIE2_ALONG[1] + t * _TIE2_ACROSS[1],
    )


# A leader-borne radius's shoulder starts this far (mm) from its text's
# centre, on the leader's side (an "R.12 ±.03" block).  SolidWorks draws the
# leader on the ray from the arc's centre through that shoulder end, and
# lands its arrow where the ray meets the arc: each shoulder stands on a ray
# through its own fillet's arc.  The shoulder runs on under the whole text.
_RADIUS_SHOULDER_LEFT = 11.3


def _out_to(
    centre: tuple[float, float], bearing_deg: float, radius: float
) -> tuple[float, float]:
    """Where the ray from ``centre`` along ``bearing_deg`` reaches ``radius``
    from the wheel's axis (model mm)."""
    bearing = math.radians(bearing_deg)
    along = centre[0] * math.cos(bearing) + centre[1] * math.sin(bearing)
    reach = -along + math.sqrt(along**2 - centre[0] ** 2 - centre[1] ** 2 + radius**2)
    return _polar(centre, bearing_deg, reach)


# Both fillet R's print above A-A's cutting line, each arrow outside its
# arc on the ray from the arc's centre through its shoulder, the leader
# reaching it from the material side.  The hub fillet R's arc (the 120 deg
# spoke's, facing the 120-180 window) opens toward the hub, so its leader
# runs right at 10 deg over the 120 deg spoke's root, the hub's top and the
# 60 deg spoke's root, through the 0-60 window above the spoke widths'
# lines and the rim, to a shoulder right of the wheel above the A-A arrow's
# letter, its text right of the shoulder.  (An arrow from inside on the
# opposite side, which would let the leader come from the window, stays on
# the circle's undrawn near side: runs 20261107T101438062Z and
# 20261107T103514893Z, tip at 20 deg with the solid leader on or off.)  The
# rim fillet R's leader leaves the 60 deg spoke's 60-120 rim fillet through
# the rim on a ray parallel to the spoke pitch's 60 deg extension line,
# 6.7 mm left of it, to a shoulder above the wheel, its text left of the
# shoulder under the pitch's arc.
_HUB_FILLET_LEADER = 10.0
_HUB_FILLET_SHOULDER = _out_to(
    _HUB_FILLET[0], _HUB_FILLET_LEADER, RIM_OUTER_DIA / 2.0 + 6.0
)
_RIM_FILLET_LEADER = 60.0
_RIM_FILLET_SHOULDER = _out_to(
    _RIM_FILLET[0], _RIM_FILLET_LEADER, RIM_OUTER_DIA / 2.0 + 8.0
)
# The mates the tight bands and the tie holes name (drawing-guidelines.md
# rule 4 (tighten only for function, and name the mate)), by drawing number.
AXLE_NUMBER = str(_config.parts("mg-wheel-axle")["number"])
DRUM_NUMBER = str(_config.parts("mg-wheel-drum")["number"])
WIRE_NUMBER = str(_config.parts("sh-vn-music-wire")["number"])
# The tie holes are named plainly at their callouts (drawing-guidelines.md
# rule 26: WIRE TIE HOLE, no coined labels).  TIE 2's says where it runs:
# radial, from the groove's bottom (the groove sits on A-A's drawn
# centreline) through to the rim bore, clocked by its 43° from the
# horizontal.  Each takes at most two lines of words under its process
# (rule 7).
TIE1_CALLOUT = "DRILL THRU\nWIRE TIE HOLE"
TIE2_CALLOUT = "DRILL THRU\nRADIAL WIRE TIE HOLE\nFROM GROOVE BOTTOM"
# Each side of a centred tie block past the DRILL THRU line's half-width
# (capitals about 2.6 mm a character), mm.
_TIE_BLOCK_WIDEN = (
    (max(len(line) for line in TIE1_CALLOUT.splitlines()) - len("DRILL THRU"))
    * 2.6
    / 2.0
)


# The bore's matched fit is note BORE_FIT_NOTE (mg_magnifying_wheel_spec):
# its callout keeps the process and the link, so the block stays narrow left
# of the wheel.
BORE_CALLOUT = f"REAM THRU\nSEE NOTE {BORE_FIT_NOTE}"
# The bore's block: its widest line sets its width (2.45 mm a character);
# the block stands left of the wheel on a shoulder 38 mm above the axis,
# over the bore finish's symbol, its right end where a 145 deg ray from the
# axis meets that height, so the bore's leader runs out through the 120-180
# window.
_BORE_SHOULDER_Y = 38.0
_BORE_LEADER_BEARING = 145.0
_BORE_BLOCK_HALF = max(len(line) for line in BORE_CALLOUT.splitlines()) * 2.45 / 2.0
_BORE_BLOCK_X = (
    _BORE_SHOULDER_Y / math.tan(math.radians(_BORE_LEADER_BEARING)) - _BORE_BLOCK_HALF
)
FRONT_KEEP = {
    # Near-side, one arrow: the bore up-left through the 120-180 window to
    # its block's shoulder (stacked Ø plus its callout lines).
    "BoreDiaDim": _over(
        (_BORE_BLOCK_X, _BORE_SHOULDER_Y), 2 + len(BORE_CALLOUT.splitlines())
    ),
    # Each fillet R on its own fillet (_HUB_FILLET_SHOULDER right of the
    # wheel, its text right of the shoulder; _RIM_FILLET_SHOULDER above it,
    # its text left of the shoulder).
    "HubFilletR": _over(
        (_HUB_FILLET_SHOULDER[0] + _RADIUS_SHOULDER_LEFT, _HUB_FILLET_SHOULDER[1]), 2
    ),
    "RimFilletR": _over(
        (_RIM_FILLET_SHOULDER[0] - _RADIUS_SHOULDER_LEFT, _RIM_FILLET_SHOULDER[1]), 2
    ),
    # The spoke pattern's 6X 60° between the 60 and 120 deg spokes'
    # centrelines, above the wheel: the one-line value centres half a text
    # line under 30 mm past the OD.
    "SpokePitch": _face(0.0, RIM_OUTER_DIA / 2.0 + 30.0 - _TEXT_LINE * 500.0),
    # Each spoke width's line beside its own end: the root's inside the hub
    # fillets' feet, its text off on a leader (SPOKE_ROOT_TEXT_XY); the
    # tip's outside the rim, its text below the line beside the OD, so
    # neither's extension lines reach the other's line.
    "SpokeRootWidth": _face(SPOKE_X0 + 4.5, 0.0),
    "SpokeTipWidth": _over((RIM_OUTER_DIA / 2.0 + 3.0, -22.0), 2),
    # TIE 1's two coordinates from the bore centre.  The Y between its own
    # extension lines, which run left from the bore's and the hole's centres
    # past the OD, its text off the lower one, 26 mm outside the rim, below
    # the A-A arrow (the lines stand only 5.6 apart); the X below the wheel,
    # its extension lines down from the bore's centre and the hole's, its
    # text left of the bore's under the wheel and right of TIE 2's block.
    "Tie1Y": _face(-(RIM_OUTER_DIA / 2.0 + 26.0), _TIE1[1] - 5.4),
    "Tie1X": _face(-9.0, -RIM_OUTER_DIA / 2.0 - 16.0),
    # The two tie Ø callouts hang off the face, the block's leader from its
    # shoulder's near end (the shoulder runs 7.3 mm under the point).  Each
    # reads size, then process, then its plain name (rule 26), centred on
    # the point.  TIE 1's block stands below the wheel, its top 3.2 mm under
    # the OD, its shoulder's near end 20 mm right of the bore's centre (the
    # name line widens the block _TIE_BLOCK_WIDEN each side past the DRILL
    # THRU width the 15.3 mm shoulder offset was set for), so the leader runs
    # down-right from the hole, away from the X's extension line, and the
    # block stays left of the section's overall row.
    "Tie1HoleDia": _face(
        20.0 + _CALLOUT_SHOULDER_LEFT + _TIE_BLOCK_WIDEN,
        -RIM_OUTER_DIA / 2.0
        - 3.2
        - _CALLOUT_ABOVE
        - _TEXT_LINE * 1000.0 * len(TIE1_CALLOUT.splitlines()) / 2.0,
    ),
    "Tie2Clock": _face(
        *_polar((0.0, 0.0), sum(_TIE2_CLOCK_SECTOR) / 2.0, _TIE2_CLOCK_TEXT_R)
    ),
    # TIE 2's Ø is a linear width across the radial hole: its extension lines
    # run out along the hole's axis to the dimension line's foot, ~1 mm past
    # the text's projection onto the axis, so a block on that foot would sit
    # on both lines: the block stands 23.6 mm off the axis on the side away
    # from the clock, its projection 81.5 mm out (past the clock's arc,
    # which ends on the hole's axis between the lines); its wide name line
    # keeps it left of TIE 1's X and above the notes.
    "Tie2HoleDia": _face(
        *_polar(_polar((0.0, 0.0), _TIE2_OUTWARD, 81.5), _TIE2_OUTWARD + 90.0, 23.6)
    ),
}
# The spoke root's text hangs off its dimension line on an OffsetText leader
# (as the retired gooseneck spring-screw sheet did): the leader runs down-right across the
# 300-360 window and the rim to the LEFT end of the callout line, one text
# line under the point the value centres on.
# That end stands under the tip width's line, 14 mm below its block's foot:
# the block sits outside the OD, right of TIE 1's block and left of A-A.
_ROOT_CALLOUT = "6X ROOT"
SPOKE_ROOT_TEXT_XY = _face(
    RIM_OUTER_DIA / 2.0 + 3.0 + len(_ROOT_CALLOUT) * 2.45 / 2.0,
    -36.0 + _TEXT_LINE * 1000.0,
)
# Near-side leaders: no segment of these comes nearer the axis than half the
# circle's radius, and each ends on its own circle (sheet metres; a reading
# outside the band means the ink is not in sheet space).
NEAR_SIDE_DIAMETERS = {
    "BoreDiaDim": BORE_DIA,
}
# TIE 1's Ø takes one arrow on the rim nearest its block, down-right of the
# hole, and no line through the centre.  Every face leader near A-A's line
# is proven off it, each landing on its own feature's radius from the axis.
TIE1_NEAR_SIDE = "Tie1HoleDia"
_BORE_LANDING = (0.8 * BORE_DIA / 2000.0, 1.2 * BORE_DIA / 2000.0)
FACE_LEADER_LANDINGS = {
    "BoreDiaDim": _BORE_LANDING,
    "BoreFinish": _BORE_LANDING,
    TIE1_NEAR_SIDE: (
        (TIE1_R - TIE_HOLE_DIA) / 1000.0,
        (TIE1_R + TIE_HOLE_DIA) / 1000.0,
    ),
    "SectionLine": SECTION_LINE_LANDING,
}
# The template centre-marks each hole as the view is placed, so an explicit
# AutoInsertCenterMarks2 would print a second, identical mark.  Each mark
# keeps its cross only: extended lines run along the axes through the bore's
# Ø text and every window's dimension.  The face view is 1:1, so the mark's
# model-length arm is its sheet length.
CENTRE_MARK_ARM = 0.0025
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym
_MARK_ON_HOLE = 0.0005
# Section A-A looks along +Y; _orient_section turns it so sheet right =
# model -Z (the pen side, where the spigot stands) and model +X (the seed
# spoke) up, proves both, and puts the hub's back face on the axis at
# _section_x(HUB_BACK_Z), so the section centres on the part's axial extent
# and each hub face's sheet x follows from its z.
_SIDE_MID_Z = (HUB_BACK_Z + HUB_FRONT_Z) / 2.0


def _section_x(z_mm: float) -> float:
    """The section's sheet x (m) of the model plane at ``z_mm``."""
    return SECTION_CENTER[0] + (_SIDE_MID_Z - z_mm) * SHEET_SCALE[0] / 1000.0


# A dimension text's width per character.
_TEXT_CHAR = 0.00245
# Text kept this far off any extension line it does not own, past the half
# text height inside which the audit gates a crossing (DIM_CROSSING_TEXT_HEIGHTS).
_TEXT_OFF_LINE = 0.004


def _beside(face_x: float, side: int, chars: int, y: float) -> tuple[float, float]:
    """A ``chars``-wide text centred ``side`` (-1 left, +1 right) of ``face_x``."""
    return (face_x + side * (_TEXT_OFF_LINE + chars * _TEXT_CHAR / 2.0), y)


# Section text points: a size whose text stands between
# its extension lines prints it centred on the point, breaking its line round
# it; one whose text stands outside hangs it off the line's end, centred on
# the point (axial) or running from the point away from the view (diameters).
# A one-line text's point stands _ONE_LINE_UP over its dimension line, a
# stacked tolerance's _STACK_UP; the line runs 6.3 mm past the extension line
# away from its text.
_ONE_LINE_UP = 0.0028
_STACK_UP = 0.0045
# Measured text half-widths: the boss Ø's value, centred on its line, and
# the groove bottom's block ("PEN-WIRE SEAT").
_HUB_DIA_TEXT_HALF = 0.0098
_GROOVE_BLOCK_HALF = 0.0165
# Left of the view the Ø stack outward from the part, smallest nearest, so
# no extension line crosses another size's line and none runs over the
# isometric (rule 11's side view takes the rim's Ø too).  The boss Ø prints
# BETWEEN its extension lines, centred on the hub, its line _TEXT_OFF_LINE
# plus half its text left of the back face; the rim bore's between its own,
# under the hub, its line as far again left; the groove bottom's block up
# between the hub and the rim bore, under the rim bore's upper extension
# line, its line half the block and _TEXT_OFF_LINE left of the rim bore's;
# the rim OD outermost, _TEXT_OFF_LINE left of that block, its block BETWEEN
# its extension lines at the hub's height, breaking its own line, so it reads
# with A-A and not among the front view's annotations (machinist review of
# 84ed4d1fc: the block hung left over the rim read as a front-view size).
_HUB_DIA_X = _section_x(HUB_BACK_Z) - _TEXT_OFF_LINE - _HUB_DIA_TEXT_HALF
_RIM_BORE_DIA_X = _HUB_DIA_X - _HUB_DIA_TEXT_HALF - _TEXT_OFF_LINE
_GROOVE_DIA_X = _RIM_BORE_DIA_X - _TEXT_OFF_LINE - _GROOVE_BLOCK_HALF
_RIM_OD_DIA_X = _GROOVE_DIA_X - _GROOVE_BLOCK_HALF - _TEXT_OFF_LINE
# A-A cuts the 0 and 180 deg spokes, so the hatch runs from the hub to the
# rim on both; no dimension line runs over it (owner review 2026-11-07:
# solid from dimension lines at a glance).  Above the rim, three rows left
# of the rim's back face, the smallest span nearest the part: the spokes'
# back face from the rim's (".08", SpokeFaceOffset, imported from the
# hidden DIAMETER_REFERENCE sketch), then the spokes' thickness (".16"),
# whose extension lines start where the spoke meets the rim bore
# (_set_section_witnesses), as the ".08"'s spoke-side line does, then the
# rim's width (".31", added below).  Every line runs from the part leftward
# to its text.
_SPOKE_FACE_ROW = SECTION_CENTER[1] + _RIM_R + 0.006
_SPOKE_ROW = _SPOKE_FACE_ROW + 0.0055
_RIM_WIDTH_ROW = _SPOKE_ROW + 0.0055
SPOKE_FACE_TEXT_XY = _beside(
    _section_x(RIM_AXIAL / 2.0), -1, 8, _SPOKE_FACE_ROW + _ONE_LINE_UP
)
# The spigot Ø's dimension line, 7.2 mm past the spigot end.
_SPIGOT_DIM_X = _section_x(HUB_FRONT_Z) + 0.0072
# The hub's three axial sizes below the rim, one row each, all from the
# spigot's faced front end (drawing-guidelines.md rule 11 (turned parts read like the lathe)) and all texts right of it except
# the overall's; each text OUTSIDE its span so no extension line runs
# through a text.
# Nearest the part the spigot length (".354", the title block's .XXX), whose
# third place keeps the drum from standing proud (DRUM_RECESS); then the web's centre plane
# (".61"), which the rim and its groove share, its extension line rising
# toward the groove (_set_section_witnesses) on the drawn centreline that
# plane is (WEB_CENTRELINES), left of the spigot step's, so the row above
# stops short of it; last the overall (".772 ±.004"), which holds the
# axle's nut stack, left of the back face above the A-A caption.  Each
# length's need stands over its value (CALLOUTS_ABOVE); the .61, a location,
# prints its value and band alone (drawing-guidelines.md rule 7).  Each
# text is centred clear of the face it leaves.  The two right-hand sizes
# keep their arrows inside their spans, so no tail reaches a neighbouring
# extension line.
#
# _HUB_ROWS are the dimension lines.  A text block centres on its point, so
# a callout over the value lifts the point half a line more than
# _ONE_LINE_UP / _STACK_UP.  The overall's row stands over the caption; the
# plane's runs 5.4 mm above it; the spigot length's stands 11.9 mm over the
# plane's, so its block clears the plane's one-line value by more than the
# layout audit's text separation (3.57 mm).
_ABOVE_UP = _TEXT_LINE / 2.0
_HUB_ROWS = tuple(
    SECTION_CENTER[1] - _RIM_R - drop for drop in (0.0050, 0.0184, 0.0238)
)
# The spigot length's three places keep the drum under the spigot face
# (mg_magnifying_wheel_geom.DRUM_RECESS): its callout names the drum.
SPIGOT_LENGTH_CALLOUT = f"DRUM {DRUM_NUMBER} NOT PROUD"
# The overall sets the axle's locknut stack (mg_wheel_group): the callout
# names the stack and the axle by number on one short line, so its dimension
# line stops short of TIE 1's block.
HUB_LENGTH_CALLOUT = f"{AXLE_NUMBER} LOCKNUT STACK"
# The groove's two three-place sizes seat the pen wire (mg_magnifying_wheel_spec
# GROOVE_WIDTH_MIN, GROOVE_DEPTH_MIN): both link the one numbered note that
# names it (drawing-guidelines.md rule 4: a mate serving several features
# is named once, in one flagged note linked to the features).
GROOVE_CALLOUT = f"SEE NOTE {GROOVE_SEAT_NOTE}"
# The .61 locates the groove: it runs from the spigot face to the centre
# plane the groove, web and rim share, its extension line ending on the
# lower groove's bottom.  Two machinist reviews still read the groove as
# unlocated (integration proofs 20261109T105251629Z, 20261112T153723793Z).
# Rule 7 keeps the location dimension bare, so the groove's own size callout
# names the plane (delegated ruling: Repitch1038, 2026-11-12, #2144).  It
# stands on the groove's R, whose block has open sheet to its right: the
# groove bottom's Ø has about 33 mm between the rim's two Ø lines, too narrow
# for this line.  The ".61" is the dimension's own value at its printed
# places, so the words cannot drift from it.
_PLANE_TEXT = f"{abs(HUB_FRONT_Z) / 25.4:.{DRAWING_PRECISION_BY_NAME['HubFrontZ']}f}"
GROOVE_R_CALLOUT = f"{GROOVE_CALLOUT}\nCENTRED ON {_PLANE_TEXT.removeprefix('0')} PLANE"
# The web plane's value is ".61 ±.03": its text is centred this many
# characters (with the margin) right of the spigot face.
_PLANE_VALUE_CHARS = 8
# Capitals print wider than _TEXT_CHAR (about 2.6 mm a character), so a
# callout's span is estimated two characters wide.
_CALLOUT_MARGIN_CHARS = 2
# The drum callout is the one long all-capitals line, about 3.02 mm a
# character: its span is estimated at that pitch so it clears the spigot
# face's shared extension line.
_DRUM_CALLOUT_CHAR = 0.00302
# The spoke pitch's arc spans its two extension lines: outside, its 60 deg
# arrow's tail would stand within the layout audit's arrow-near-text gap of
# the rim OD's text.
ARROWS_INSIDE = ("SpigotLength", "HubFrontZ", "SpokePitch")
_DIM_ARROWS_INSIDE = 0  # swDimensionArrowsSide_e.swDimArrowsInside
SECTION_KEEP = {
    "HubDia": (_HUB_DIA_X, SECTION_CENTER[1]),
    "GrooveBottomDia": (_GROOVE_DIA_X, SECTION_CENTER[1] + 0.030),
    # Right of the view only the spigot's Ø, its line 7.2 mm past the spigot
    # end; its text hangs off that line on a leader (SPIGOT_TEXT_XY).
    "SpigotDia": (
        _SPIGOT_DIM_X,
        SECTION_CENTER[1] - SPIGOT_DIA / 2000.0 - 0.012 + _TEXT_LINE / 2.0,
    ),
    # Its ".16 ±.03" centred eight characters off the rim's back face.
    "SpokeAxial": _beside(_section_x(RIM_AXIAL / 2.0), -1, 8, _SPOKE_ROW + _ONE_LINE_UP),
    "SpigotLength": _beside(
        _section_x(HUB_FRONT_Z),
        1,
        math.ceil(len(SPIGOT_LENGTH_CALLOUT) * _DRUM_CALLOUT_CHAR / _TEXT_CHAR)
        + _CALLOUT_MARGIN_CHARS,
        _HUB_ROWS[0] + _ONE_LINE_UP + _ABOVE_UP,
    ),
    "HubFrontZ": _beside(
        _section_x(HUB_FRONT_Z),
        1,
        _PLANE_VALUE_CHARS + _CALLOUT_MARGIN_CHARS,
        _HUB_ROWS[1] + _ONE_LINE_UP,
    ),
    "HubLength": _beside(
        _section_x(HUB_BACK_Z),
        -1,
        len(HUB_LENGTH_CALLOUT) + _CALLOUT_MARGIN_CHARS,
        _HUB_ROWS[2] + _ONE_LINE_UP + _ABOVE_UP,
    ),
    # The groove's R up right, its leader down-left onto the groove at 35
    # deg, right of the axial rows' line ends; its shoulder over the top of
    # the rim-bore round's R block (ROUND_TEXT_XY), under its two callout
    # lines.  Its one-line value leaves the shoulder where the stacked band's
    # block put it; the second callout line lifts the point half a line, so
    # the shoulder stays.
    "GrooveR": (
        SECTION_CENTER[0] + 0.0344,
        SECTION_CENTER[1] + 0.0701 - (_STACK_UP - _ONE_LINE_UP) + _TEXT_LINE / 2.0,
    ),
}
# The spigot's two-line block ("(Ø.499)" over its note link) hangs on an
# OffsetText leader (SpokeRootWidth's) right of its dimension line, level
# with the axis, so neither the spigot's outline nor the dimension line
# crosses it (drawing-guidelines.md rule 14): ISO_CLEAR off the isometric,
# proven at build (_assert_text_off_iso).
SPIGOT_TEXT_XY = (
    _SPIGOT_DIM_X + 0.008 + len(f"SEE NOTE {SPIGOT_FIT_NOTE}") * 0.0026 / 2.0,
    SECTION_CENTER[1],
)
# The rim's two Ø and the spokes' back face, imported from the hidden
# DIAMETER_REFERENCE sketch in A-A's plane (mg_magnifying_wheel_spec): the
# rim bore's Ø between its extension lines under the hub; the rim OD's, an
# overall size printed bare (drawing-guidelines.md rule 7: no reason on an
# overall size), between its own at the hub's height, clear of the groove
# bottom's line to its right and the front view to its left; the back
# face's on its row above the rim (SPOKE_FACE_TEXT_XY).
SECTION_DIAMETER_KEEP = {
    "RimInnerDiaDim": (_RIM_BORE_DIA_X, SECTION_CENTER[1] - 0.030),
    "RimOuterDiaDim": (_RIM_OD_DIA_X, SECTION_CENTER[1]),
    "SpokeFaceOffset": SPOKE_FACE_TEXT_XY,
}
# The rim-bore round's R is a sheet radial on its cut arc: A-A cannot import
# a fillet radius whose arc IS the cut (neither the targeted import nor
# DragModelDimension lands CastRoundR there).  It takes the arc at the rim's
# front (sheet-right, model -Z) inner corner over the seed spoke, the
# circle's centre one R in from the bore and the side face.  A cut-face arc
# lies in the cut plane, so its axis is the cut's normal (model Y); the
# round's tangent circles beyond the cut keep the wheel's Z, and the axis
# keeps the pick off them.  Its callout stands right, between the spigot's
# Ø block and the groove's R: the value over its one callout line, the
# shoulder under it (5.6 mm a line), the block centred on its point.  The
# shoulder runs 4.3 mm under the arc's centre and 8 mm right, so the radial
# leader lands on the arc about 28 deg below the side face's tangent and
# crosses the rim's front face under the rim width's extension line, which
# rises from the OD.  The groove bottom's Ø holds the left.
_ROUND_ARC_CENTER = (
    RIM_INNER_DIA / 2.0 + CAST_ROUND_R,
    0.0,
    -(RIM_AXIAL / 2.0 - CAST_ROUND_R),
)
_CUT_NORMAL = (0.0, 1.0, 0.0)
ROUND_TEXT_XY = (
    SECTION_CENTER[0] + 0.0322,
    SECTION_CENTER[1] + 0.0517 - _TEXT_LINE / 2.0,
)
ROUND_CALLOUT = "2X RIM BORE EDGES"


# The two matched fits (drawing-guidelines.md rule 4 (tighten only for
# function, and name the mate)): each Ø is a reference nominal
# (REFERENCE_DIMENSIONS), and its callout links the numbered note that names
# the standard fit and the mate, the clearance or interference the finished
# pair makes as REF (mg_magnifying_wheel_spec.DRAWING_NOTES): the bore is
# reamed to run on the finished axle, and the spigot turned to press into
# the drum's finished reamed bore.  The groove's two three-place sizes link their one
# note; the tie holes read size, then process, then their plain name
# (drawing-guidelines.md rule 26).
DIMENSION_CALLOUTS = {
    "BoreDiaDim": BORE_CALLOUT,
    "SpigotDia": f"SEE NOTE {SPIGOT_FIT_NOTE}",
    "GrooveBottomDia": GROOVE_CALLOUT,
    "GrooveR": GROOVE_R_CALLOUT,
    "SpokeRootWidth": _ROOT_CALLOUT,
    "SpokeTipWidth": "6X TIP",
    "HubFilletR": "12X",
    "RimFilletR": "12X",
    "Tie1HoleDia": TIE1_CALLOUT,
    "Tie2HoleDia": TIE2_CALLOUT,
}
# Each axial length's need stands over its value.
CALLOUTS_ABOVE = {
    "SpigotLength": SPIGOT_LENGTH_CALLOUT,
    "HubLength": HUB_LENGTH_CALLOUT,
}
# SOLIDWORKS drops a multi-line callout above a value from the print
# (draw_dt_cone_gear).
if any("\n" in text for text in CALLOUTS_ABOVE.values()):
    raise AssertionError("an above-callout with a line break does not print")
# The notes, top-left anchored, under the two tie blocks and left of the
# title block.
NOTES_XY = (0.020, 0.062)
# drawing-guidelines.md rule 26: the spokes' clocking and the plane the .61
# locates are drawn lines, not sentences.  On the face, A-A's cutting line
# runs through the bore's axis and the two spokes on it (the seed spoke on
# local +X).  On A-A, the groove, web and rim's shared mid-plane (model
# z = 0, the plane HubFrontZ dimensions) along each cut spoke from the hub,
# CENTRELINE_OVERRUN past the OD.  Model mm.
CENTRELINE_OVERRUN = 2.0
_CENTRELINE_REACH = RIM_OUTER_DIA / 2.0 + CENTRELINE_OVERRUN
WEB_CENTRELINES = {
    side: ((sign * HUB_DIA / 2.0, 0.0, 0.0), (sign * _CENTRELINE_REACH, 0.0, 0.0))
    for side, sign in (("upper", 1.0), ("lower", -1.0))
}

# The rim's axial width spans its two side faces where A-A cuts them over
# the seed spoke: at the rim's top each is a straight cut-face line at
# z = +/-RIM_AXIAL/2, running from the rim-bore round's tangent
# (r = RIM_INNER_DIA/2 + CAST_ROUND_R) to the OD, picked through its
# midpoint as a native entity.  The section's scan holds no OD corner circle
# (r = 50, z = +/-4): edge-on, each lies under the cut face's boundary and
# the round's tangent circle, which A-A draws instead.  The OD is no single
# line to measure either: the groove splits it into two lands.
_RIM_SIDE_Y = (RIM_INNER_DIA / 2.0 + CAST_ROUND_R + RIM_OUTER_DIA / 2.0) / 2.0
_RIM_SIDE_POINTS = tuple(
    (_RIM_SIDE_Y, 0.0, z) for z in (RIM_AXIAL / 2.0, -RIM_AXIAL / 2.0)
)
# A failed section pick names every scanned edge passing this near its point.
_PICK_INVENTORY_MM = 6.0
# The bore's finish symbol stands outside the OD left of the wheel, under
# the bore's block; its leader lands on the bore on that bearing, clear
# below the bore's Ø leader and above the A-A arrow's letter.
_BORE_FINISH_BEARING = 158.0
BORE_FINISH_SYMBOL = _face(
    *_polar((0.0, 0.0), _BORE_FINISH_BEARING, RIM_OUTER_DIA / 2.0 + 21.2)
)
_BORE_FINISH_POINT = (*_polar((0.0, 0.0), _BORE_FINISH_BEARING, BORE_DIA / 2.0), 0.0)
FINISH_CHAR_HEIGHT = 0.0025
# The two fillet R's print one arrow outside their arc, the leader stopping
# there (draw_dt_arbor_pedestal's crown): no arc extension, no line on to
# the centre.  Each rebuilt arrow tip must lie on its fillet's arc within
# FILLET_TIP_TOL (m) of its radius and FILLET_SPAN_TOL (deg) of its span.
_ARROWS_OUTSIDE = 1  # swDimArrowsOutside
FILLET_TIP_TOL = 0.0002
FILLET_SPAN_TOL = 1.0
PRINTED_FILLETS = {
    "HubFilletR": (_HUB_FILLET, HUB_FILLET_R),
    "RimFilletR": (_RIM_FILLET, RIM_FILLET_R),
}


def _near_side_diameters(
    adapter: Any, annotations: list[Any], *, axis: tuple[float, float]
) -> None:
    """One arrow on each face-view diameter's near rim, proven off the face."""
    named = {
        dimension_name(adapter, annotation): annotation for annotation in annotations
    }
    for name in (*NEAR_SIDE_DIAMETERS, TIE1_NEAR_SIDE):
        set_near_side_diameter(named[name], f"wheel {name}")
    rebuild_drawing(adapter, label="wheel near-side diameters")
    radii = {
        name: diameter * SHEET_SCALE[0] / 2000.0
        for name, diameter in NEAR_SIDE_DIAMETERS.items()
    }
    assert_leaders_clear(
        {name: dimension_segments(named[name]) for name in NEAR_SIDE_DIAMETERS},
        centre=axis,
        keep_out={name: radius / 2.0 for name, radius in radii.items()},
        lands_within={
            name: (0.8 * radius, 1.2 * radius) for name, radius in radii.items()
        },
        label="wheel near-side diameters",
    )


def _trim_centre_marks(
    adapter: Any, view: Any, holes: dict[str, tuple[float, float]]
) -> None:
    """Keep the template's centre marks as bare crosses, one per hole, and
    fail on a second mark at any hole or a mark at no hole."""
    marks = [
        _early_bound(annotation, "IAnnotation")
        for annotation in _early_bound(view, "IView").GetAnnotationsByType(
            _CENTER_MARK_ANNOTATION
        )
        or ()
    ]
    for annotation in marks:
        mark = _early_bound(annotation.GetSpecificAnnotation(), "ICenterMark")
        mark.UseDocDisplaySettings = False
        mark.ShowLines = False
        mark.Size = CENTRE_MARK_ARM
    rebuild_drawing(adapter, label="trim wheel centre marks")
    marked = []
    for annotation in marks:
        mark = _early_bound(annotation.GetSpecificAnnotation(), "ICenterMark")
        if bool(mark.UseDocDisplaySettings) or bool(mark.ShowLines):
            raise RuntimeError("a wheel centre mark kept its extended lines")
        data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
        lines = [
            tuple(float(value) for value in data.GetLineAtIndex2(index))
            for index in range(int(data.GetLineCount()))
        ]
        if not lines:
            raise RuntimeError("a wheel centre mark draws no line")
        xs = [value for line in lines for value in (line[4], line[7])]
        ys = [value for line in lines for value in (line[5], line[8])]
        centre = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
        marked.append(
            next(
                (
                    name
                    for name, hole in holes.items()
                    if math.dist(hole, centre) <= _MARK_ON_HOLE
                ),
                f"no hole at {centre}",
            )
        )
    if (
        marked.count("bore") != 1
        or marked.count("tie 1") > 1
        or set(marked) - set(holes)
    ):
        raise RuntimeError(f"expected one centre mark per wheel hole, found {marked}")
    _telemetry.info(f"wheel centre marks: {sorted(marked)}")


def _assert_text_off_iso(adapter: Any, annotations: list[Any], iso: Any) -> None:
    """Fail when any dimension's text block comes within ISO_CLEAR of the
    isometric's outline.  Every text item a dimension draws (value, stacked tolerance,
    callout lines) is boxed by the layout audit's estimator, as
    draw_dt_cone_gear_shaft does: no API returns a text's width."""
    iso_box = Box(*(float(value) for value in _early_bound(iso, "IView").GetOutline()))
    nearest = math.inf
    crowding = []
    for annotation in annotations:
        annotation = _early_bound(annotation, "IAnnotation")
        label = dimension_name(adapter, annotation) or "unnamed dimension"
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        data = _early_bound(display.GetDisplayData(), "IDisplayData")
        for index in range(int(data.GetTextCount())):
            anchor = [float(value) for value in data.GetTextPositionAtIndex(index)]
            reference = int(data.GetTextRefPositionAtIndex(index))
            box = estimate_text_box(
                str(data.GetTextAtIndex(index) or ""),
                anchor=(anchor[0], anchor[1]),
                height=float(data.GetTextHeightAtIndex(index)),
                reference=reference if 0 <= reference <= 5 else 0,
                angle=float(data.GetTextAngleAtIndex(index)),
            )
            if box is None:
                continue
            gap = box.gap(iso_box)
            nearest = min(nearest, gap)
            if gap < ISO_CLEAR:
                crowding.append(f"{label} {box.format_mm()}")
    if crowding:
        raise RuntimeError(
            f"dimension text within {ISO_CLEAR * 1000:.0f} mm of the isometric "
            f"{iso_box.format_mm()}: {crowding}"
        )
    _telemetry.info(
        f"wheel dimension text clears the isometric {iso_box.format_mm()} by "
        f"{nearest * 1000:.1f} mm"
    )


def _handedness(
    back: tuple[float, float], front: tuple[float, float], top: tuple[float, float]
) -> float:
    """Positive when back -> spigot end -> rim top turn counter-clockwise on
    the sheet: a turn keeps the sign, a reversed cut (a mirror) flips it."""
    return (front[0] - back[0]) * (top[1] - back[1]) - (front[1] - back[1]) * (
        top[0] - back[0]
    )


def _orient_section(adapter: Any, section: Any) -> str:
    """Lay section A-A as SECTION_KEEP draws it and return its rotation label.

    The section stands as projected off the face's horizontal cutting line,
    the wheel's axis upright; it must lie across, the hub's back face left of
    the spigot and the seed spoke (+X) up, the back face on the axis at
    (_section_x(HUB_BACK_Z), SECTION_CENTER[1]).  A turn keeps the
    handedness of (back face, spigot end, rim top) and reversing the cut
    (looking from the other side of the plane) mirrors it, so the cut is
    reversed when the handedness is wrong and the view is then turned until
    +X stands up.  The label names the turn as read back on the sheet
    (drawing-guidelines.md rule 9: a rotated view says so), never from
    IView.Angle's sign.  The view is then moved by its projection, not its
    outline: the hub stands off the rim's mid-plane, so the outline's centre
    is not a hub face.
    """
    native = _early_bound(section, "IView")

    def read() -> list[tuple[float, float]]:
        return model_points_in_view(
            adapter,
            native,
            (
                (0.0, 0.0, HUB_BACK_Z / 1000.0),
                (0.0, 0.0, HUB_FRONT_Z / 1000.0),
                (RIM_OUTER_DIA / 2000.0, 0.0, HUB_BACK_Z / 1000.0),
            ),
            label="wheel section orientation",
            names=("hub back face", "spigot end", "rim top"),
        )

    def laid(points: list[tuple[float, float]]) -> bool:
        back, front, top = points
        return (
            back[0] < front[0]
            and top[1] > back[1]
            and abs(top[0] - back[0]) <= _SECTION_PLACEMENT_TOL
        )

    points = read()
    if _handedness(*points) < 0.0:
        cut = _early_bound(native.GetSection(), "IDrSection")
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="wheel section reversed")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("wheel section cut direction did not persist")
        points = read()
        if _handedness(*points) < 0.0:
            raise RuntimeError(f"wheel section A-A stayed mirrored: {points}")
    back, _front, top = points
    projected = math.atan2(top[1] - back[1], top[0] - back[0])
    turn = math.remainder(math.pi / 2.0 - projected, 2.0 * math.pi)
    if abs(abs(turn) - math.pi / 2.0) > 1e-6:
        raise RuntimeError(
            f"wheel section A-A projects +X at {math.degrees(projected):.3f} deg, "
            "not across the sheet"
        )
    start = float(native.Angle)
    for sign in (1.0, -1.0):
        native.Angle = start + sign * turn
        rebuild_drawing(adapter, label=f"wheel section turned ({sign:+g})")
        points = read()
        if laid(points):
            break
    else:
        raise RuntimeError(
            f"wheel section A-A is not back face left, +X up after turning "
            f"{math.degrees(turn):+.1f} deg either way: {points}"
        )
    label = f"ROTATED 90 DEG {'CCW' if turn > 0.0 else 'CW'}"
    back, front, top = points
    target = (_section_x(HUB_BACK_Z), SECTION_CENTER[1])
    for attempt in range(4):
        if math.dist(back, target) <= _SECTION_PLACEMENT_TOL:
            break
        position = tuple(float(value) for value in native.Position)
        moved = [position[axis] + target[axis] - back[axis] for axis in (0, 1)]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to move wheel section A-A")
        rebuild_drawing(adapter, label=f"wheel section placed, pass {attempt}")
        back, front, top = read()
    else:
        raise RuntimeError(
            f"wheel section A-A back face stayed at {back}, requested {target}"
        )
    _telemetry.info(
        f"wheel section: {label}, angle={float(native.Angle):.6f} rad, "
        f"back={back}, spigot end={front}, rim top={top}"
    )
    return label


def _set_arrows_inside(adapter: Any, annotations: list[Any]) -> None:
    """Stand each ARROWS_INSIDE dimension's arrows inside its extension lines,
    as draw_dt_cone_tip_block's _set_arrow_sides."""
    remaining = set(ARROWS_INSIDE)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        remaining.discard(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArrowSide = _DIM_ARROWS_INSIDE
        if int(display.ArrowSide) != _DIM_ARROWS_INSIDE:
            raise RuntimeError(f"{name} did not keep its arrows inside")
    if remaining:
        raise RuntimeError(f"no dimension to set arrows inside: {sorted(remaining)}")


def _fillet_tip(
    display: Any,
    name: str,
    centre: tuple[float, float],
    ends: tuple[float, float],
    radius: float,
) -> tuple[tuple[float, float], float, bool]:
    """``name``'s rebuilt arrow tip, its bearing (deg) from the fillet's sheet
    ``centre``, and whether it lies on the fillet's arc (FILLET_TIP_TOL,
    FILLET_SPAN_TOL)."""
    raw = display.GetDisplayData()
    if raw is None:
        raise RuntimeError(f"{name} has no rebuilt display data")
    data = _early_bound(raw, "IDisplayData")
    if int(data.GetArrowHeadCount()) != 1:
        raise RuntimeError(f"{name} must draw exactly one radial arrow")
    arrow = tuple(float(v) for v in data.GetArrowHeadAtIndex2(0))
    if len(arrow) != 12 or not all(math.isfinite(v) for v in arrow):
        raise RuntimeError(f"{name} has incomplete arrow-head coordinates")
    tip = (arrow[0], arrow[1])
    off = (tip[0] - centre[0], tip[1] - centre[1])
    bearing = math.degrees(math.atan2(off[1], off[0]))
    span = (ends[1] - ends[0] + 180.0) % 360.0 - 180.0
    mid = ends[0] + span / 2.0
    swing = abs((bearing - mid + 180.0) % 360.0 - 180.0)
    on_arc = (
        abs(math.hypot(*off) - radius / 1000.0) <= FILLET_TIP_TOL
        and swing <= abs(span) / 2.0 + FILLET_SPAN_TOL
    )
    return tip, bearing, on_arc


def _dress_fillet_radii(adapter: Any, annotations: list[Any]) -> None:
    """Print each PRINTED_FILLETS R with one arrow outside its arc and the
    leader stopping on it (_ARROWS_OUTSIDE), read back."""
    remaining = set(PRINTED_FILLETS)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        remaining.discard(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArcExtensionLineOrOppositeSide = False
        display.ArrowSide = _ARROWS_OUTSIDE
        display.SolidLeader = False
        if (
            bool(display.Diametric)
            or bool(display.ArcExtensionLineOrOppositeSide)
            or int(display.ArrowSide) != _ARROWS_OUTSIDE
            or bool(display.SolidLeader)
        ):
            raise RuntimeError(f"{name} did not keep its radial leader style")
    if remaining:
        raise RuntimeError(f"no fillet radius to dress: {sorted(remaining)}")


# Section A-A shows only hatch on its cut faces (drawing-guidelines.md rule
# 9).  Two model dimensions' extension lines rise from inside the hub: the
# spokes' thickness from the seed spoke's root corner, whose lines start
# instead where the cut spoke meets the rim bore and rise through the rim
# to their row above it; and the web's centre plane from the origin, whose
# line starts the document gap past the rim's OD instead, under the groove
# the plane locates.
_SPOKE_WITNESS_START = SECTION_CENTER[1] + RIM_INNER_DIA * SHEET_SCALE[0] / 2000.0


def _rising_witness_start(annotation: Any, x: float, label: str) -> float:
    """The lowest sheet y of ``annotation``'s vertical extension line at
    sheet ``x``: where a line rising to its dimension line starts."""
    starts = [
        min(a[1], b[1])
        for a, b in dimension_segments(annotation)
        if abs(a[0] - x) < 1e-4 and abs(b[0] - x) < 1e-4 and abs(a[1] - b[1]) > 1e-6
    ]
    if not starts:
        raise RuntimeError(f"{label}: no extension line at x={x:.4f} m")
    return min(starts)


def _start_spoke_witnesses(adapter: Any, spoke: Any) -> None:
    """Start SpokeAxial's two extension lines at the spoke's junction with the
    rim bore (_SPOKE_WITNESS_START) by their witness gaps, read back."""
    display = _early_bound(spoke.GetSpecificAnnotation(), "IDisplayDimension")
    xs = tuple(_section_x(z) for z in (SPOKE_AXIAL / 2.0, -SPOKE_AXIAL / 2.0))
    before = [_rising_witness_start(spoke, x, "SpokeAxial") for x in xs]
    if abs(before[0] - before[1]) > 1e-5:
        raise RuntimeError(f"SpokeAxial's extension lines start apart: {before}")
    rise = _SPOKE_WITNESS_START - before[0]
    if rise <= 0.0:
        _telemetry.info(f"SpokeAxial: extension lines already start at y={before[0]:.5f} m")
        return
    for index in (0, 1):
        ok, _use_doc, old_gap = display.GetWitnessLineGap(index, False, 0.0)
        if ok is not True:
            raise RuntimeError(f"SpokeAxial witness {index} gap could not be read")
        if display.SetWitnessLineGap(index, False, float(old_gap) + rise) is not True:
            raise RuntimeError(f"SpokeAxial witness {index} gap was refused")
    rebuild_drawing(adapter, label="spoke thickness witness gaps")
    after = [_rising_witness_start(spoke, x, "SpokeAxial") for x in xs]
    if any(abs(start - _SPOKE_WITNESS_START) > 1e-5 for start in after):
        raise RuntimeError(
            f"SpokeAxial's extension lines start at {after}, not at the rim bore "
            f"y={_SPOKE_WITNESS_START:.5f} m"
        )
    _telemetry.info(
        f"SpokeAxial: extension lines start at the rim bore y={after[0]:.5f} m "
        f"(were {before[0]:.5f})"
    )


@_telemetry.traced("wheel.section_witnesses")
def _set_section_witnesses(adapter: Any, annotations: list[Any]) -> None:
    """Keep SpokeAxial's extension lines off A-A's cut faces and run
    HubFrontZ's centre-plane line up into the lower groove to its bottom,
    read back."""
    named = {
        dimension_name(adapter, annotation): _early_bound(annotation, "IAnnotation")
        for annotation in annotations
    }
    missing = {"SpokeAxial", "HubFrontZ"} - set(named)
    if missing:
        raise RuntimeError(f"no section dimension to set: {sorted(missing)}")
    _start_spoke_witnesses(adapter, named["SpokeAxial"])
    plane = named["HubFrontZ"]
    display = _early_bound(plane.GetSpecificAnnotation(), "IDisplayDimension")
    plane_x = _section_x(0.0)

    def plane_witness_start() -> float:
        tops = [
            max(a[1], b[1])
            for a, b in dimension_segments(plane)
            if abs(a[0] - plane_x) < 1e-4
            and abs(b[0] - plane_x) < 1e-4
            and abs(a[1] - b[1]) > 1e-6
        ]
        if not tops:
            raise RuntimeError(f"HubFrontZ: no extension line at x={plane_x:.4f} m")
        return max(tops)

    before = plane_witness_start()
    # Which index is the plane's is SOLIDWORKS' to state: try each, keep the
    # one that moves the plane's line, restore the other.
    for index in (0, 1):
        ok, use_doc, old_gap = display.GetWitnessLineGap(index, False, 0.0)
        if ok is not True:
            raise RuntimeError(f"HubFrontZ witness {index} gap could not be read")
        target = SECTION_CENTER[1] - _GROOVE_BOTTOM_R
        gap = float(old_gap) + before - target
        if display.SetWitnessLineGap(index, False, gap) is not True:
            raise RuntimeError(f"HubFrontZ witness {index} gap was refused")
        rebuild_drawing(adapter, label=f"web centre witness {index} gap")
        start = plane_witness_start()
        if abs(start - target) < 1e-5:
            _telemetry.info(
                f"HubFrontZ: centre-plane witness {index} starts at y={start:.5f} m "
                f"(was {before:.5f}), gap {gap * 1000.0:.2f} mm"
            )
            return
        if display.SetWitnessLineGap(index, bool(use_doc), float(old_gap)) is not True:
            raise RuntimeError(f"HubFrontZ witness {index} gap could not be restored")
        rebuild_drawing(adapter, label=f"web centre witness {index} gap restored")
    raise RuntimeError(
        f"HubFrontZ: no witness gap moved the centre-plane line from y={before:.5f} m"
    )


@_telemetry.traced("wheel.break_out_tie2")
def _break_out_tie2(adapter: Any, front: Any) -> None:
    """Cut TIE2_WINDOW out of the face view to the mid-plane, read back."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    native = _early_bound(front, "IView")
    sheet = model_points_in_view(
        adapter,
        front,
        tuple(
            (*(value / 1000.0 for value in tie2_window_point(s, t)), 0.0)
            for s, t in TIE2_WINDOW
        ),
        label="TIE 2 window",
    )
    if not ddoc.ActivateView(view_name(adapter, front)):
        raise RuntimeError("failed to activate the face view for TIE 2's window")
    draw.ClearSelection2(True)
    points = sheet_to_sketch(adapter, front, [*sheet, sheet[0]])
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        spline = manager.CreateSpline(
            double_array([value for point in points for value in point[:3]])
        )
    finally:
        manager.AddToDB = previous
    if spline is None:
        raise RuntimeError("failed to sketch TIE 2's window")
    selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
    data = selection.CreateSelectData()
    data.View = native
    if not _early_bound(spline, "ISketchSegment").Select4(False, data):
        raise RuntimeError("failed to select TIE 2's window")
    if ddoc.CreateBreakOutSection(_TIE2_WINDOW_DEPTH / 1000.0) is not True:
        raise RuntimeError("TIE 2's broken-out section was refused")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="TIE 2 broken-out window")
    count = int(native.GetBreakOutSectionCount())
    if count != 1:
        raise RuntimeError(f"face view holds {count} broken-out sections, not 1")
    _telemetry.info(
        f"TIE 2 window cut {_TIE2_WINDOW_DEPTH:g} mm deep from the hub's back face"
    )


@_telemetry.traced("wheel.centrelines", label_param="label")
def _add_centrelines(
    adapter: Any,
    view: Any,
    ends_mm: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]],
    *,
    label: str,
) -> None:
    """Draw each of ``ends_mm`` (model mm) as a thin black centreline in
    ``view``'s sketch (_transgear_zone_line's direct-to-database lines), its
    font and ends read back after the rebuild."""
    keys = tuple(ends_mm)
    sheet = model_points_in_view(
        adapter,
        view,
        tuple(
            tuple(value / 1000.0 for value in end)
            for key in keys
            for end in ends_mm[key]
        ),
        label=label,
        names=tuple(f"{key} {end}" for key in keys for end in ("start", "end")),
    )
    lines = sketch_lines(
        adapter,
        view,
        {
            key: (sheet[2 * index], sheet[2 * index + 1])
            for index, key in enumerate(keys)
        },
        style=CENTER_LINE_STYLE,
        width=CENTER_LINE_WEIGHT,
        label=label,
    )
    rebuild_drawing(adapter, label=label)
    require_placed(
        adapter,
        lines,
        style=CENTER_LINE_STYLE,
        width=CENTER_LINE_WEIGHT,
        label=label,
        stage="rebuilt",
    )


def _width_dimension_lines(
    annotation: Any, axis_y: float, half_widths: tuple[float, ...]
) -> list[Any]:
    """A vertical width's ink less its extension lines: the horizontal strokes
    at the measured levels (``half_widths`` mm off ``axis_y``), which a leader
    may cross (drawing-guidelines.md rule 14)."""
    levels = [axis_y + half / 1000.0 for half in half_widths]
    return [
        segment
        for segment in dimension_segments(annotation)
        if not (
            abs(segment[0][1] - segment[1][1]) < 1e-6
            and any(abs(segment[0][1] - level) < 0.0003 for level in levels)
        )
    ]


def _assert_fillet_radii(
    adapter: Any,
    front: Any,
    annotations: list[Any],
    bore_finish: Any,
    *,
    axis: tuple[float, float],
) -> None:
    """Fail unless each printed fillet R's arrow tip lies on its own fillet's
    arc and its leader crosses no other leader, dimension line or the A-A
    line."""
    named = {
        dimension_name(adapter, annotation): annotation for annotation in annotations
    }
    centres = model_points_in_view(
        adapter,
        front,
        tuple(
            (centre[0] / 1000.0, centre[1] / 1000.0, 0.0)
            for (centre, _ends), _r in PRINTED_FILLETS.values()
        ),
        label="printed fillet centres",
        names=tuple(PRINTED_FILLETS),
    )
    for (name, ((_c, ends), radius)), centre in zip(
        PRINTED_FILLETS.items(), centres, strict=True
    ):
        display = _early_bound(
            _early_bound(named[name], "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        tip, bearing, on_arc = _fillet_tip(display, name, centre, ends, radius)
        if not on_arc:
            raise RuntimeError(
                f"{name}'s arrow tip {tip} is not on its fillet's arc (centre "
                f"{centre}, R {radius}, arc {ends[0]:.1f}..{ends[1]:.1f} deg, tip "
                f"at {bearing:.1f} deg)"
            )
        _telemetry.info(f"{name}: arrow tip {tip} on its fillet at {bearing:.1f} deg")
    groups = {name: dimension_segments(named[name]) for name in PRINTED_FILLETS}
    groups["SpokeRootWidth"] = _width_dimension_lines(
        named["SpokeRootWidth"],
        axis[1],
        (SPOKE_ROOT_WIDTH / 2.0, -SPOKE_ROOT_WIDTH / 2.0),
    )
    groups["SpokeTipWidth"] = _width_dimension_lines(
        named["SpokeTipWidth"], axis[1], (SPOKE_TIP_WIDTH / 2.0, -SPOKE_TIP_WIDTH / 2.0)
    )
    groups["Tie1Y"] = _width_dimension_lines(named["Tie1Y"], axis[1], (0.0, _TIE1[1]))
    for name in (*NEAR_SIDE_DIAMETERS, TIE1_NEAR_SIDE):
        groups[name] = dimension_segments(named[name])
    groups["BoreFinish"] = leader_segments(bore_finish.GetAnnotation())
    groups["SectionLine"] = section_line_segments(adapter, front)
    crossed = [
        pair for pair in leader_crossings(groups) if set(pair) & set(PRINTED_FILLETS)
    ]
    if crossed:
        raise RuntimeError(f"wheel fillet R leaders cross: {crossed}")


def _assert_face_leaders_clear(
    adapter: Any,
    front: Any,
    annotations: list[Any],
    bore_finish: Any,
    *,
    axis: tuple[float, float],
) -> None:
    """Fail unless the face's leaders, the bore finish's and the A-A cutting
    line cross none of each other (drawing-guidelines.md rule 14 (keep text off the part)), each landing on its own
    feature."""
    named = {
        dimension_name(adapter, annotation): annotation for annotation in annotations
    }
    groups = {
        name: dimension_segments(named[name])
        for name in (*NEAR_SIDE_DIAMETERS, TIE1_NEAR_SIDE)
    }
    groups["BoreFinish"] = leader_segments(bore_finish.GetAnnotation())
    groups["SectionLine"] = section_line_segments(adapter, front)
    assert_leaders_clear(
        groups,
        centre=axis,
        keep_out={},
        lands_within=FACE_LEADER_LANDINGS,
        label="wheel face leaders vs A-A",
    )


def _mm(values: Any) -> str:
    return "(" + ", ".join(f"{value:.3f}" for value in values) + ")"


def _edge_inventory(edges: ViewEdges, point_mm: tuple[float, float, float]) -> str:
    """Every scanned line and circle passing within _PICK_INVENTORY_MM of
    ``point_mm`` (model mm; a circle by its full curve), so a missed section
    pick names what the scan does hold there."""
    rows = []
    for item in edges.edges:
        if item.line is not None:
            start, end = item.line
            vector = [b - a for a, b in zip(start, end)]
            length_sq = sum(value * value for value in vector)
            t = 0.0
            if length_sq > 0.0:
                along = sum((p - a) * v for p, a, v in zip(point_mm, start, vector))
                t = min(1.0, max(0.0, along / length_sq))
            reach = math.dist(point_mm, [a + t * v for a, v in zip(start, vector)])
            text = f"line {_mm(start)}-{_mm(end)}"
        elif item.circle is not None:
            cx, cy, cz, nx, ny, nz, radius = item.circle
            offset = [p - c for p, c in zip(point_mm, (cx, cy, cz))]
            height = sum(o * n for o, n in zip(offset, (nx, ny, nz)))
            in_plane = math.sqrt(max(sum(o * o for o in offset) - height**2, 0.0))
            reach = math.hypot(height, in_plane - radius)
            text = f"circle c={_mm((cx, cy, cz))} n={_mm((nx, ny, nz))} r={radius:.3f}"
        else:
            continue
        if reach <= _PICK_INVENTORY_MM:
            rows.append(f"{text} {reach:.2f} off")
    return (
        f"{len(rows)} of {len(edges.edges)} scanned edges within "
        f"{_PICK_INVENTORY_MM:g} mm of {_mm(point_mm)}: {'; '.join(rows) or 'none'}"
    )


def _line_through(
    edges: ViewEdges, point_mm: tuple[float, float, float], *, label: str
) -> Any:
    """The section's cut-face line through ``point_mm``, its edge inventory
    on a miss."""
    try:
        return edges.exact_line_through(point_mm, label=label).edge
    except RuntimeError as error:
        raise RuntimeError(f"{error}; {_edge_inventory(edges, point_mm)}") from error


def _pass_through_places(display: Any, label: str) -> None:
    """Give a sheet-added dimension the places the spec owns for it
    (DRAWING_REFERENCE_PRECISION), so it prints the value the spec's walls
    are proved against."""
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    places = DRAWING_REFERENCE_PRECISION[label]
    if int(display.GetPrimaryPrecision2()) != places:
        raise RuntimeError(f"{label}: {places} decimal places did not persist")


def _add_round_radius(adapter: Any, section: Any, edges: ViewEdges) -> Any:
    """Dimension the rim-bore round on its A-A cut arc (the T rail root radius
    pattern of draw_fr_top_frame) and return its annotation.

    The arc is picked as a native entity from the section's edge scan, so a
    moved round fails loud in ``circle_at``; the radial must attach to that
    arc alone and measure the spec's R (``assert_dimension_measures``).  It
    prints a single limit, R.03 MAX (two places and the spec's suffix), the
    largest R ``TIE2_FACE_WALL`` is proved against; a sharp edge falls under
    the title block's edge break.
    """
    label = "rim bore round"
    try:
        arc = edges.circle_at(
            _ROUND_ARC_CENTER, CAST_ROUND_R, axis=_CUT_NORMAL, label=label
        ).edge
    except RuntimeError as error:
        inventory = _edge_inventory(edges, _ROUND_ARC_CENTER)
        raise RuntimeError(f"{error}; {inventory}") from error
    draw = adapter.currentModel
    _select_view_entity(adapter, section, "EDGE", None, label=label, entity=arc)
    display = draw.AddRadialDimension2(*ROUND_TEXT_XY, 0.0)
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to dimension the {label}")
    display = _early_bound(display, "IDisplayDimension")
    assert_dimension_measures(
        adapter,
        display,
        expected_mm=CAST_ROUND_R,
        label=label,
        entities=(arc,),
        entity_types=("EDGE",),
    )
    _pass_through_places(display, label)
    display.SetText(2, ROUND_TEXT_SUFFIX)  # swDimensionTextSuffix
    suffix = str(display.GetText(2) or "")
    if suffix != ROUND_TEXT_SUFFIX:
        raise RuntimeError(f"{label}: suffix {suffix!r} did not persist")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    set_dimension_callouts(
        adapter, [annotation], {dimension_name(adapter, annotation): ROUND_CALLOUT}
    )
    return annotation


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-wheel source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Magnifying Wheel Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying wheel; cast-iron spider; six spokes",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    # A-A is cut, and curated, while the part shows the rim's diameter
    # reference (draw_pd_platen's floor section): a section takes a hidden
    # sketch as the part stands when it is cut.  The spoke reference stays
    # hidden there: the face view's curate shows it in that view alone.
    with _drawing_hidden_sketches.part_sketches_shown(
        adapter,
        source_model,
        (DIAMETER_REFERENCE,),
        label="section A-A diameter reference",
        base_view=front,
    ):
        # Drawn left to right, the line's arrows point up: A-A looks along +Y.
        section = create_section_view(
            adapter,
            front,
            line_start=(
                FRONT_CENTER[0] - _RIM_R - SECTION_LINE_OVERRUN,
                FRONT_CENTER[1],
            ),
            line_end=(
                FRONT_CENTER[0] + _RIM_R + SECTION_LINE_OVERRUN,
                FRONT_CENTER[1],
            ),
            view_xy=SECTION_CENTER,
            section_label="A",
            scale=(1, 1),
            label="wheel section A-A",
        )
        rotation = _orient_section(adapter, section)
        # drawing-guidelines.md rule 9 (show internal shape in solid lines):
        # a section shows no hidden lines.
        set_hidden_lines_removed(adapter, section)
        section_annotations = _drawing_hidden_sketches.curate_view_dimensions(
            adapter,
            section,
            keep={**SECTION_KEEP, **SECTION_DIAMETER_KEEP},
            view_label="section",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    position_section_caption(adapter, section, SECTION_CAPTION_XY, label="wheel")
    # The turn prints under the caption (drawing-guidelines.md rule 9: a
    # rotated view says so), centred on it; the caption prints no scale, the
    # section being drawn at the sheet's.
    if (
        add_note(
            adapter,
            rotation,
            SECTION_CAPTION_XY[0] - len(rotation) * ROTATION_NOTE_CHAR / 2.0,
            ROTATION_NOTE_TOP,
        )
        is None
    ):
        raise RuntimeError(f"failed to label section A-A {rotation}")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # The face view needs no hidden lines once the section carries the hub.
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *_drawing_hidden_sketches.curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *section_annotations,
    ]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # The matched fits' Ø are reference nominals: "(Ø.499)", "(Ø.1885)".
    set_reference_dimensions(adapter, annotations, REFERENCE_DIMENSIONS)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    offset_dimension_text(
        adapter,
        annotations,
        {"SpokeRootWidth": SPOKE_ROOT_TEXT_XY, "SpigotDia": SPIGOT_TEXT_XY},
    )
    _set_arrows_inside(adapter, annotations)
    _dress_fillet_radii(adapter, annotations)
    _set_section_witnesses(adapter, annotations)
    axis, tie1, bore_landing = model_points_in_view(
        adapter,
        front,
        (
            (0.0, 0.0, 0.0),
            (_TIE1[0] / 1000.0, _TIE1[1] / 1000.0, 0.0),
            tuple(value / 1000.0 for value in _BORE_FINISH_POINT),
        ),
        label="wheel hole centres",
        names=("bore", "tie 1", "bore finish landing"),
    )
    _near_side_diameters(adapter, annotations, axis=axis)
    _trim_centre_marks(adapter, front, {"bore": axis, "tie 1": tie1})

    # drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the bore is a running fit (the general machined grade),
    # authored on the part and read back here.  The spigot is pressed into
    # the drum and the boss step is the drum's register face: neither takes
    # a symbol.
    bore_finish = add_surface_finish(
        adapter,
        front,
        edge_entity=visible_circle_edge(adapter, front, BORE_DIA),
        symbol_xy=BORE_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "mg_wheel_bore"),
        label="wheel bore finish",
        leader_attach_xy=bore_landing,
        char_height=FINISH_CHAR_HEIGHT,
    )
    _assert_face_leaders_clear(adapter, front, annotations, bore_finish, axis=axis)
    _assert_fillet_radii(adapter, front, annotations, bore_finish, axis=axis)
    _break_out_tie2(adapter, front)

    # The rim's axial width across the section between its side faces' cut
    # lines (_RIM_SIDE_POINTS), its text left of the rim's back face on its
    # own row (above).  Each line is selected as a native entity: a
    # coordinate hit-test finds no edge.  One sweep serves them and the
    # rim-bore round's arc.
    section_edges = scan_view_edges(section, label="wheel section edges")
    rim_sides = tuple(
        _line_through(section_edges, point, label=f"rim side cut line z={point[2]:+g}")
        for point in _RIM_SIDE_POINTS
    )
    rim_back, rim_front = model_points_in_view(
        adapter,
        section,
        tuple(tuple(value / 1000.0 for value in point) for point in _RIM_SIDE_POINTS),
        label="wheel section picks",
        names=("rim back side", "rim front side"),
    )
    rim_width = add_edge_dimension(
        adapter,
        section,
        p0=rim_back,
        p1=rim_front,
        text_xy=_beside(
            _section_x(RIM_AXIAL / 2.0), -1, 4, _RIM_WIDTH_ROW + _ONE_LINE_UP
        ),
        label="rim axial width",
        orientation="horizontal",
        entities=rim_sides,
    )
    assert_dimension_measures(
        adapter,
        rim_width,
        expected_mm=RIM_AXIAL,
        label="rim axial width",
        entities=rim_sides,
    )
    _pass_through_places(
        _early_bound(rim_width, "IDisplayDimension"), "rim axial width"
    )
    round_radius = _add_round_radius(adapter, section, section_edges)
    _add_centrelines(adapter, section, WEB_CENTRELINES, label="wheel web centreline")
    rebuild_drawing(adapter, label="wheel dimension layout")
    _assert_text_off_iso(
        adapter,
        [
            *annotations,
            _early_bound(rim_width, "IDisplayDimension").GetAnnotation(),
            round_radius,
        ],
        iso,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Wheel Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
