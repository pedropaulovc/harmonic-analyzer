r"""Create the drawing for the oblique-trammel jig's pivot block (MHA-CH-006-TL-22)."""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
)

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
from _drawing_gdt import add_datum_feature, add_feature_control_frame
from _drawing_dimension_import import curate_view_dimensions
import _drawing_hidden_sketches as hidden_sketches
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hole_callout import (
    add_native_hole_callout,
    compose_hole_callout_prefix,
    set_hole_callout_precision,
)
from _drawing_leaders import set_near_side_diameter
from _drawing_leader_notes import add_leader_note
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _paths import CAD_ROOT
from _printed_limits import limits
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_oblique_pivot_block_spec as part_spec
from ch_rocker_arm_tl_oblique_pivot_block_spec import (
    BLOCK_HEIGHT,
    BLOCK_WIDTH,
    BLOCK_X0,
    BLOCK_X1,
    BOLT_X,
    BOLT_Y,
    BORE_X,
    CALLOUTS_ABOVE,
    CALLOUTS_BELOW,
    CBORE_FLOOR,
    CBORE_FLOOR_REFERENCE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    GEOMETRIC_TOLERANCES_MM,
    SCREW_MATE_CALLOUT,
    SIDE_CALLOUT_BELOW,
    SIDE_CALLOUT_PRECISION,
    SIDE_CBORE_DIA,
    SIDE_HOLE_DIA,
    SIDE_SCREW_HOLES,
    SIDE_SCREW_REFERENCE,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_pivot_block"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 70 x 40 x 24 block at 2:1. The plan view (*Front: the model's +Z top
# face) carries the plan sizes and every station, X from the -X end face
# (one baseline stack below the view, shortest nearest) and Y from the -Y
# side face (a stack right of it), plus the screw holes' one native
# counterbore callout above it. Section A-A on the bore axis, below the
# plan, shows the two-sided seats, their depths and corners, the shoulder
# hole and the height. Full section B-B through the -X counterbores,
# right of the plan, carries the counterbore floor's height
# from the carriage seat. The side view (*Top, the +Y face) right of A
# carries the nut-bracket screws' stations and their native counterbore
# callout; the shaded isometric stands at the upper right.
#
# Section arrows point away from their view (A's up), and SolidWorks prints
# each letter 15-22 mm past its arrow's tail (draw_fr_top_frame
# SECTION_LETTER_EXTENTS), so A's letters stand above the cutting line's
# two ends. Farm run jig-r1 (fa975d169) failed with a hole-size shoulder
# across a second section line and the size callouts over the top border.
# Jig-r2 (c2f7d1c03) put the five-row BoreDia block over the plan: its
# "2X" and tolerance stack printed over the top border (ink top 270.2 mm),
# and its native leader ran rim to rim through the bore and across line A.
# It now stands left of the plan in seven narrow rows
# (part_spec.BORE_CALLOUT), its single arrow on the near rim
# (set_near_side_diameter), above line A's left end. Jig-r3 (fbf443c77)
# chained the stations from the pattern centre (now from the faces) and
# the Ø27 inside section A (now under it). r5: the counterbore floor, the
# face that sets the M4 x 20's engagement in the carriage, prints from the
# carriage seat in B-B (part_spec.CBORE_FLOOR), and the native callout's
# depth is its reference "(8.40)". PR C4 adds the side view under the Y
# stack, so the isometric drops to 1:2 in the corner. r6: the web hole (now
# Ø25) and the two-place sizes print their functions with their values
# (part_spec.CALLOUTS_BELOW/ABOVE), and B-B stands aligned with its cutting
# line between the plan's width and the isometric. r7: B-B is a full
# section (its partial cut's open end broke the hatch into dashes), and the
# 70 drops to its own tier.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
ISO_SCALE = (1, 2)
# Plan outline x 60..200, y 152..232 mm; the block centre at (130, 192), so
# a model point maps to sheet (160 + 2x, 192 + 2y).
PLAN_CENTER = (0.130, 0.192)
# Outline y 49..97 (model +Z prints DOWN in A-A: sheet y = 73 - 2(z - 12)),
# x 60..200 (sheet x = 130 + 2(x + 15)), under the plan's (tl22-r2 review:
# 10 mm left of it, it read as projected but misaligned). The depths' lines
# stand 14 mm left of it (x 46), each block hung beyond its span (review
# r12: inside the 20 mm span the four-row block ran past both extension
# lines and the line struck its first and last rows), datum A's box
# between them and the outline. The height stands right, one row at x
# ~201..215, y ~70..76, over the title block's top (y 64.5; its left edge
# x 215.5, 6 mm right of the height's witness ends). The Ø25 hangs under it
# and the seat corner over it, under the plan's lowest station row (y
# ~113). The 24 mm block (r4: BEARING_SHOULDER 4) grows the outline 4 mm;
# the centre drops 1 mm so the seat corner's text keeps its gap over the
# bottom seat's mouth.
SECTION_A_CENTER = (PLAN_CENTER[0], 0.073)
# The 48 x 37 mm pictorial (1:2, review r7: B-B needs the corner under it):
# x ~361..409, y ~213..251, inside the right border (419.1) and under the
# top one (267); its note (left-anchored, ~59 mm) under it, over B-B's
# floor text (y <= 187).
ISO_CENTER = (0.385, 0.232)
ISO_NOTE_XY = (0.355, 0.200)
# Right of the Ø25's witness lines (x 71, 121; down to y ~20) and its
# outside arrow (to x ~127.3; tl22-r1 put the caption's left end on it),
# under A-A: the ~46 mm caption at x ~132..178.
CAPTION_A_XY = (0.155, 0.024)
# Side view (*Top: looking at the +Y face, X right, model +Z DOWN): outline
# x 238..378, y 76..124, so a model point maps to sheet (338 + 2x, 124 - 2z);
# 11 mm over the title block (y 65). c4 review: 4 mm further right than
# c4r3; close-c4-r4: 4 mm more, so the side row's 9.000 block, now in A-A
# (x ~208..232), keeps its gap to the view.
SIDE_CENTER = (0.308, 0.102)
# Review c4r3: the side view stands out of projection (above the plan there
# is no room for its 48 mm), so it is a removed view: "VIEW C" under it and a
# letter arrow on the plan's +Y edge, the face it looks at (the cone tip
# block's VIEW B/C recipe: a pointer note whose straight leader is the
# viewing arrow). The tip at model X -30 (sheet x 100), the 5 mm letter
# 10.5 mm over it (y ~237..243): right of the bore callout (x <= 55), left
# of B-B's upper letter (x ~149) and the screw callout (x >= 158).
SIDE_VIEW_LETTER = "C"
SIDE_VIEW_LETTER_HEIGHT = 0.005
SIDE_VIEW_ARROW_TIP = (-30.0, BLOCK_WIDTH / 2.0, BLOCK_HEIGHT)
SIDE_VIEW_LETTER_OFFSET = (-0.0018, 0.0105)
# Under the view's centre (outline bottom y 76), over the title block (65).
SIDE_VIEW_CAPTION = f"VIEW {SIDE_VIEW_LETTER}"
SIDE_VIEW_CAPTION_XY = (0.3005, 0.0775)
# Cutting line on the top face, past the outline (model mm).
CUT_A_X = (BLOCK_X0 - 4.0, BLOCK_X1 + 4.0)
# Section B-B's full cut along Y through both -X counterbores, on the
# build's CboreSectionPlane (X = -BOLT_X). Review r5: cut along X, its
# left letter and arrow sat on the Ø29.976 bore circle, and no X-wise cut
# can clear it (the arrow must stand left of the counterbore, X <= -17.5,
# the letter right of the bore, X >= -15). Along Y the line runs 4 past
# both side faces (sheet y 144..240) at sheet x 134, crossing line A at
# the block centre. Drawn bottom to top, its arrows point +X (A's, drawn
# left to right, point up: the arrow turns clockwise from the line's run)
# and the letters stand ~17 mm along them, at sheet x ~151: the upper one
# over the plan's top edge, the lower one (y ~142..149) under its bottom
# edge (y 152), right of the 18.00 text (x <= 85) and over the 63.000 line
# (y 128). Review r7: the partial cut (Y 8 up) ended inside the Ø4.5 hole's
# wall band, its open end left no outline, and the hatch below the hole
# broke into dashes; a full cut has a face on every side.
CUT_B_Y = (-BLOCK_WIDTH / 2.0 - 4.0, BLOCK_WIDTH / 2.0 + 4.0)
# Review r6: B-B printed turned (+Z down) with no ROTATED label. It stands
# aligned with its cutting line: the line runs +Y up the plan, so +Y runs
# up the section, and seen along the +X arrows +Z reads right
# (_orient_section_b proves both). The strip (Z 0..24 across, Y -20..20
# up: 48 x 80 mm at 2:1) centred at x 320, y 193, so x 296..344, y 153..233:
# right of the plan's BlockWidth text (x <= 281), left of the isometric
# (x 361) and its note (x 355), over the side view's stations (y <= 141).
SECTION_B_CENTER = (0.320, 0.193)
SECTION_B_ANCHOR = (-BOLT_X, 0.0, BLOCK_HEIGHT / 2.0)
# Under the strip (y 153): x ~297..343, y ~143..150, 2 mm over the side
# stations' lines (y <= 141), right of their text (x <= 295) and left of
# the side callout (x 352).
CAPTION_B_XY = (0.320, 0.150)
# The floor height runs across the strip from the carriage seat (x 296)
# on witness lines rising from the reference line (the Ø4.5 hole's +Y
# wall, Y 15.25, y 223.5). Its one engagement row stands over the value
# (part_spec.CALLOUTS_ABOVE), so the line runs under "15.600" (review r7:
# under the rows, it struck "(5 DEEP THREAD)"; review r8: the three-row
# block never printed). The ~11 x 76 mm block: line y ~239 (6 mm over the
# strip's top, y 233), top y ~250 (under the top border, 267), x ~274..350,
# right of the BlockWidth text and the screw callout (x <= 218), centred on
# the 15.6 span.
SECTION_B_KEEP: dict[str, tuple[float, float, float]] = {
    "CboreFloor": (-BOLT_X, BLOCK_WIDTH / 2.0 + 8.5, CBORE_FLOOR / 2.0),
}

# Every dimension's text position is a MODEL point (mm) off the part, mapped
# onto its view at run time. Jig-r2 readback: a position stands 1.0 mm over
# the middle of its text block, the block running from its last row's
# baseline (where the shoulder runs) to 3.5 mm over its first row's; rows
# run 5.56 mm apart on the sheet (2.8 model mm at 2:1), and a "2X" over a
# stacked tolerance 9.05 mm over the value's baseline. Rows are centred on
# the position's x.
_H = BLOCK_HEIGHT
_HW = BLOCK_WIDTH / 2.0
_HOLE_PLACES = part_spec.HOLE_STATION_PLACES
PLAN_KEEP: dict[str, tuple[float, float, float]] = {
    # X stations from the -X end, one baseline stack under the view at a
    # 7 mm (sheet) pitch, shortest nearest (lines y 141, 134, 127, 112). The
    # X datum is the top face's -Y/-X corner, so every datum witness line
    # runs down the end face's corner; the hole stations print on the -Y row
    # (build _top_seat_sketch). Each text stands off the witness lines that
    # end just over it (bore x 96, -X hole column x 134).
    "BoreStationX": (-41.0, -_HW - 4.0, _H),
    "HoleColumn1X": (-25.0, -_HW - 7.5, _H),
    "HoleColumn2X": (-5.0, -_HW - 11.0, _H),
    # The block's length on its own tier, line y ~112.5 (3 mm over the seat
    # corner's "2X", y 109.4): its function row under the value, on the
    # line (part_spec.CALLOUTS_BELOW), a two-row block topping at y ~121.5,
    # 5.5 under the 63.000 line (review r7: three rows rose to y 130 and
    # that line struck "70.00"; close-c4-r5: 3.7 under it, the row read as
    # either line's). The ~67 mm row centres at x 165 (x ~131..199), inside
    # the +X end's witness line (x 200).
    "BlockLength": (2.5, -_HW - 17.0, _H),
    # Y stations from the -Y side, a stack right of the view at a 10 mm
    # (sheet) pitch (x 220, 230, 240), each text centred in its span,
    # off the witness lines of the stations beyond it. The datum is the
    # top face's -Y/+X corner; the bore's witness line runs on line A as
    # BoltY's did (jig-r3). c4 review: 8 mm further right, so line A's
    # right arrow and letter (x ~205..210) stand left of the whole stack.
    "HoleRow1Y": (30.0, -16.5, _H),
    "BoreStationY": (35.0, -10.0, _H),
    "HoleRow2Y": (40.0, -3.5, _H),
    # The width, outermost at x 264: its three ~35 mm rows (x ~247..281)
    # stand 7 mm right of HoleRow2Y's line (x 240).
    "BlockWidth": (52.0, 8.0, _H),
    # The bore left of the view: "2X", the value and five rows under it, a
    # 40.3 mm (sheet) block about 35 mm wide (the value row with its
    # tolerance stack). Its shoulder at y 202 mm stands 10 mm over line A
    # (y 192), whose left end, arrow and letter (x ~48..60) lie under it,
    # and its top at ~243 mm is 23 mm inside the border. The block's x
    # ~19..55 keeps 6 mm off the left border and 5 mm off the outline (x 60);
    # the near-rim leader runs ~11 mm to the rim at ~(67..70, 199..206).
    "BoreDia": (BLOCK_X0 - 11.5, 15.5, _H),
}
SECTION_A_KEEP: dict[str, tuple[float, float, float]] = {
    # The side screws' row from the carriage seat (A-A's top edge: model +Z
    # prints down), right of the +X end (x 208). Close-c4-r4 review: from
    # View C alone the reader took A-A's top edge for the counterbored face,
    # so the section names its own top face. Beyond its span, over the
    # section, the six rows hang right of the line, away from the part
    # (draw_pd_support_bar; close-c4-r5 render: four rows at x ~208..232),
    # centred at y ~117 (y ~101..133): right of the plan's +X witness line
    # (x 200) and the 70's line end, left of View C (x 238).
    "SideScrewRowZ": (BLOCK_X1 + 4.0, 0.0, -10.5),
    # Left of the -X end: each seat floor's witness line leaves the bore
    # wall and crosses only the 3 mm end wall (jig-r3 ran them right across
    # the whole hatched block), to a line at x 46. Review r12: requested
    # inside the 20 mm span, the four-row block ran past both extension
    # lines and the line struck "10.000" and "FOR PULLER". Each now stands
    # beyond its span, so SolidWorks hangs it LEFT of the line (right edge
    # on it, x ~17..46), centred on the requested height over a
    # shoulder at its last row: the bottom seat's over the bottom face (y
    # 97; block y ~101..127, left of the plan's -X witness lines at x 60),
    # the top seat's under the top face (y 49; block y ~20..46, left of
    # the Ø25's rows).
    "TopBoreDepth": (BLOCK_X0 - 7.0, 0.0, _H + 8.25),
    "BottomBoreDepth": (BLOCK_X0 - 7.0, 0.0, -8.75),
    # Under the view (model +Z down), off the silhouette: its witness lines
    # drop from the web hole's walls through the open top seat (x 71, 121);
    # five rows (value, THRU, the three-row function), the widest ~43 mm
    # (x ~75..117) inside them, y ~20..46 (2.5 under the outline, 7 over
    # the bottom border).
    "ShoulderHoleDia": (BORE_X, 0.0, _H + 7.5),
    # Over the view, "2X" above: the leader rises from a corner through the
    # open bottom seat (y 97 at the mouth, between the bore walls).
    "SeatFilletR": (-20.0, 0.0, -4.0),
}
# Hung under the top face, the top seat's block runs beside its dimension
# line from the face down to its shoulder, the block's right edge on the
# line (tl22-r1: "NEEDS 3.0" ended 0.2 mm from it). Two trailing spaces on
# every row stand the glyphs ~2.5 mm off the line; the bottom seat's block
# stands over its shoulder, clear of its line, and keeps the spec's rows.
HUNG_BESIDE_LINE = ("TopBoreDepth",)
_HUNG_PAD = "  "


def _hung_clear(callouts: dict[str, str]) -> dict[str, str]:
    return callouts | {
        name: "\n".join(row + _HUNG_PAD for row in callouts[name].splitlines())
        for name in HUNG_BESIDE_LINE
    }


SIDE_KEEP: dict[str, tuple[float, float, float]] = {
    # X stations from the -X end over the view (model -Z is sheet up), rows
    # y 132 and 140, each text left of the +X hole's witness line (x 348);
    # left of section B-B's caption.
    "SideScrew1X": (-29.5, _HW, -4.0),
    "SideScrew2X": (-24.5, _HW, -8.0),
    # The 24.00 right of the +X end (line x 386, text ~380..393 centred in
    # its span at y 100), under the side callout (y >= 135), inside the
    # border (419). Close-c4-r4: A-A's right lane now holds the side row.
    "BlockHeight": (BLOCK_X1 + 4.0, _HW, _H / 2.0),
}

# The screw holes' native callout over the plan, right of section B-B's
# upper letter (x ~149..153) and under the top border: four rows (4X DRILL
# Ø4.50 THRU ALL, the counterbore, the two mate rows), ~60 x 22 mm (x
# ~158..218, y ~239..261, over the BlockWidth witness line at y 232).
# ``callout_xy`` is the text block's centre (draw_mg_output_fixture). The
# leader lands on the (+13, +13) counterbore's upper-right rim, inside the
# outline and over the HoleRow2Y witness line (y 218), clear of every
# witness line.
SCREW_CALLOUT_XY = (0.188, 0.250)
_CBORE_R = part_spec.CBORE_DIA / 2.0
SCREW_CALLOUT_EDGE = (
    BOLT_X + _CBORE_R * math.sqrt(0.5),
    BOLT_Y + _CBORE_R * math.sqrt(0.5),
    _H,
)
# The counterbore row's depth prints as the floor's reference complement.
_CBORE_DEPTH_TOKEN = re.compile(r"(<HOLE-DEPTH>\s*)(<[^<>()]+>|[0-9.]+)\s*$")
SCREW_HOLE_PROCESS = "DRILL"

# Seat coaxiality (part_spec docstring): datum A on the bottom seat in A-A,
# the position frame on the top seat opposite it (review r12: on the plan's
# visible rim the reader could not tell the controlled bore from the datum
# bore). The tl22-r2 review read both inside their cavities as text on the
# part (rule 14); both now stand outside the outline.
#
# SolidWorks sets a datum triangle level with its box (jig-r11: over the
# seat's mouth it went onto the -X wall's extension above the face, read as
# "face A"), so the box stands left of the end wall, level with the bottom
# seat (z 5, y 87): its leader edge here (x 57, between the depths' line at
# x 46 and the outline at x 60; the box x ~50..57, y ~84..91, between the
# seat's witness lines at y 77 and 97), the triangle on the -X wall (x 66)
# across the 3 mm end wall.
SEAT_DATUM_EDGE = (BORE_X - part_spec.BORE_DIA / 2.0, 0.0, 3.0)
SEAT_DATUM_SYMBOL = (BLOCK_X0 - 1.5, 0.0, 5.0)
# The frame (~29 x 7 mm, its top-left corner here: x ~123..152, y ~38..45)
# under the top face, right of the Ø25's right witness line (x 121) and
# over the caption (y <= 24). Its leader rises from the frame's left end
# through the top seat's open mouth (crossing the face's y 49 ~2 mm inside
# the +X wall at x 126) to that wall 1.5 mm over the floor (sheet ~(126,
# 66)), crossing no line.
SEAT_FRAME_EDGE = (
    BORE_X + part_spec.BORE_DIA / 2.0,
    0.0,
    part_spec.BORE_DEPTH + part_spec.SHOULDER + 1.5,
)
SEAT_FRAME_CORNER = (BORE_X + part_spec.SHOULDER_HOLE_DIA / 2.0 + 1.0, 0.0, _H + 2.0)
_SEAT_GDT_SOURCE = ("draw_ch_rocker_arm_tl_oblique_pivot_block", "_seat_gdt")

# The side screws' native callout right of the side view, over it and under
# the isometric's note (y 200): four rows (2X DRILL Ø4.98 THRU ALL, the
# counterbore, the mate, the walls' shortfall), ~60 x 22 mm at x ~352..412,
# y ~135..157. Its leader drops to the +X counterbore's upper-right rim
# (x ~350), right of the 55.000 station's witness line (x 344).
SIDE_CALLOUT_XY = (0.382, 0.146)
_SIDE_CBORE_R = SIDE_CBORE_DIA / 2.0
SIDE_CALLOUT_EDGE = (
    SIDE_SCREW_HOLES[1][0] + _SIDE_CBORE_R * math.sqrt(0.5),
    _HW,
    SIDE_SCREW_HOLES[1][1] - _SIDE_CBORE_R * math.sqrt(0.5),
)

_UP = [0.0, 0.0, 1.0]
_DOWN = [0.0, 0.0, -1.0]
_INTO_Y = [0.0, -1.0, 0.0]


part_metadata(
    precision_sources=(
        "DRAWING_PRECISION_BY_NAME",
        "SIDE_CALLOUT_PRECISION",
        ("_drawing_hole_callout", "add_native_hole_callout"),
        ("_drawing_hole_callout", "set_hole_callout_precision"),
    )
)
part_metadata(
    datums={
        part_spec.SEAT_DATUM: (
            {"feature": "bottom_bearing_seat", "surface": "bottom 6200 seat cylinder"},
            ("SEAT_DATUM", _SEAT_GDT_SOURCE),
        ),
    }
)

requirement(
    "top_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.BLOCK_HEIGHT),),
    requirements=("height", "length", "width"),
    fields={
        "normal": (_UP, ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.BLOCK_HEIGHT},
            ("BLOCK_HEIGHT",),
        ),
        "height": (limits(part_spec.BLOCK_HEIGHT, 2), ("BLOCK_HEIGHT",)),
        "height_nominal": (part_spec.BLOCK_HEIGHT, ("BLOCK_HEIGHT",)),
        "length": (limits(part_spec.BLOCK_LENGTH, 2), ("BLOCK_LENGTH",)),
        "length_nominal": (part_spec.BLOCK_LENGTH, ("BLOCK_LENGTH",)),
        "width": (limits(part_spec.BLOCK_WIDTH, 2), ("BLOCK_WIDTH",)),
        "width_nominal": (part_spec.BLOCK_WIDTH, ("BLOCK_WIDTH",)),
    },
    precision={"height": 2, "length": 2, "width": 2},
)

requirement(
    "carriage_seat",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("height",),
    fields={
        "normal": (_DOWN, ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "height": (limits(part_spec.BLOCK_HEIGHT, 2), ("BLOCK_HEIGHT",)),
    },
    precision={"height": 2},
)

requirement(
    "minus_x_end",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), -part_spec.BLOCK_X0),),
    requirements=("length",),
    fields={
        "normal": ([-1.0, 0.0, 0.0], ("__frame__",)),
        # The datum every X station prints from; the +X end from it.
        "length": (limits(part_spec.BLOCK_LENGTH, 2), ("BLOCK_LENGTH", "DATUM_X")),
        "length_nominal": (part_spec.BLOCK_LENGTH, ("BLOCK_LENGTH",)),
    },
    precision={"length": 2},
)

for _side, _face_z, _entry_z, _axis, _coaxial in (
    (
        "top",
        part_spec.BLOCK_HEIGHT - part_spec.BORE_DEPTH / 2.0,
        part_spec.BLOCK_HEIGHT,
        _DOWN,
        {
            # The position frame to A (_seat_gdt), docstring "Seat coaxiality".
            "coaxiality_dia": (
                part_spec.SEAT_POSITION_DIA,
                ("SEAT_POSITION_DIA", "GEOMETRIC_TOLERANCES_MM", _SEAT_GDT_SOURCE),
            ),
            "coaxial_to": ("bottom_bearing_seat", (_SEAT_GDT_SOURCE,)),
            "position_datums": (
                [part_spec.SEAT_DATUM],
                ("SEAT_DATUM", _SEAT_GDT_SOURCE),
            ),
        },
    ),
    ("bottom", part_spec.BORE_DEPTH / 2.0, 0.0, _UP, {}),
):
    requirement(
        f"{_side}_bearing_seat",
        kind="hole",
        faces=(
            CylinderFace(
                part_spec.BORE_DIA,
                contains_x_mm=part_spec.BORE_X,
                contains_z_mm=_face_z,
            ),
        ),
        requirements=(
            "station",
            "width",
            "dia",
            "depth",
            "note",
            *(("coaxiality_dia",) if _coaxial else ()),
        ),
        fields={
            "at": (
                [part_spec.BORE_X, 0.0, _entry_z],
                ("BORE_X", "BLOCK_HEIGHT", "__frame__"),
            ),
            "axis": (_axis, ("__frame__",)),
            # From the -X end face and the -Y side face; two places, since
            # the carriages slide and the bore's place sets no radius.
            "station": (
                limits(part_spec.BORE_STATION_X, 2),
                ("BORE_X", "DATUM_X"),
            ),
            "station_nominal": (part_spec.BORE_STATION_X, ("BORE_X", "DATUM_X")),
            "width": (limits(part_spec.BORE_STATION_Y, 2), ("DATUM_Y",)),
            "width_nominal": (part_spec.BORE_STATION_Y, ("DATUM_Y",)),
            "dia": (
                limits(part_spec.BORE_DIA, 3, part_spec.BORE_BAND),
                ("BORE_DIA", "BORE_BAND", "N6_BAND"),
            ),
            "dia_nominal": (part_spec.BORE_DIA, ("BORE_DIA",)),
            "depth": (
                limits(part_spec.BORE_DEPTH, 3),
                ("BORE_DEPTH", "PULLER_GAP_MIN"),
            ),
            "depth_ref": (part_spec.BORE_DEPTH, ("BORE_DEPTH",)),
            "thru": (False, ("BORE_DEPTH",)),
            # The rule-4 matched-fit callout names the mate (BORE_MATE).
            "note": (
                " ".join(part_spec.BORE_CALLOUT.splitlines()),
                ("BORE_CALLOUT", "BORE_MATE", "BEARING_OD_BAND"),
            ),
            **_coaxial,
        },
        precision={"station": 2, "width": 2, "dia": 3, "depth": 3}
        | ({"coaxiality_dia": 2} if _coaxial else {}),
    )

requirement(
    "shoulder_hole",
    kind="hole",
    faces=(
        CylinderFace(
            part_spec.SHOULDER_HOLE_DIA,
            contains_x_mm=part_spec.BORE_X,
            contains_z_mm=part_spec.BLOCK_HEIGHT / 2.0,
        ),
    ),
    requirements=("dia", "thru"),
    fields={
        "at": (
            [part_spec.BORE_X, 0.0, part_spec.BORE_DEPTH + part_spec.SHOULDER],
            ("BORE_X", "BORE_DEPTH", "SHOULDER"),
        ),
        "axis": (_DOWN, ("__frame__",)),
        "dia": (
            limits(part_spec.SHOULDER_HOLE_DIA, 1),
            ("SHOULDER_HOLE_DIA", "BEARING_DA_MAX", "BEARING_INNER_SHOULDER_D2"),
        ),
        "dia_nominal": (part_spec.SHOULDER_HOLE_DIA, ("SHOULDER_HOLE_DIA",)),
        "thru": (True, ("CALLOUTS_BELOW",)),
    },
    precision={"dia": 1},
)

for _index, (_x, _y) in enumerate(part_spec.BOLT_POINTS, start=1):
    requirement(
        f"screw_hole_{_index}",
        kind="hole",
        faces=(CylinderFace(part_spec.HOLE_DIA, contains_x_mm=_x, contains_y_mm=_y),),
        requirements=("station", "width", "dia", "thru"),
        fields={
            "at": ([_x, _y, part_spec.BLOCK_HEIGHT], ("BOLT_POINTS", "BLOCK_HEIGHT")),
            "axis": (_DOWN, ("__frame__",)),
            # From the -X end face and the -Y side face, hole to hole within
            # the M4 screws' float (spec SCREW_FLOAT).
            "station": (
                limits(_x - part_spec.DATUM_X, _HOLE_PLACES),
                ("BOLT_POINTS", "DATUM_X", "SCREW_FLOAT"),
            ),
            "station_nominal": (_x - part_spec.DATUM_X, ("BOLT_POINTS", "DATUM_X")),
            "width": (
                limits(_y - part_spec.DATUM_Y, _HOLE_PLACES),
                ("BOLT_POINTS", "DATUM_Y", "SCREW_FLOAT"),
            ),
            "width_nominal": (_y - part_spec.DATUM_Y, ("BOLT_POINTS", "DATUM_Y")),
            "dia": (
                limits(
                    part_spec.HOLE_DIA, part_spec.CALLOUT_PLACES, part_spec.DRILLED_BAND
                ),
                ("HOLE_DIA", "DRILLED_BAND"),
            ),
            "dia_nominal": (part_spec.HOLE_DIA, ("HOLE_DIA",)),
            "thru": (True, ("SCREW_HOLE_SPEC",)),
        },
        precision={
            "station": _HOLE_PLACES,
            "width": _HOLE_PLACES,
            "dia": part_spec.CALLOUT_PLACES,
        },
    )
    requirement(
        f"screw_hole_{_index}_counterbore",
        kind="counterbore",
        faces=(CylinderFace(part_spec.CBORE_DIA, contains_x_mm=_x, contains_y_mm=_y),),
        requirements=("dia", "height"),
        fields={
            "parent": (
                f"screw_hole_{_index}",
                ("HOLE_DIA", ("draw_ch_rocker_arm_tl_oblique_pivot_block", "build")),
            ),
            "dia": (
                limits(part_spec.CBORE_DIA, part_spec.CALLOUT_PLACES),
                ("CBORE_DIA", "SCREW_HEAD_DIA"),
            ),
            "dia_nominal": (part_spec.CBORE_DIA, ("CBORE_DIA",)),
            # The floor from the carriage seat (section B-B) sets the M4 x
            # 20's engagement in the carriage; the callout's depth is its
            # reference complement.
            "height": (
                limits(part_spec.CBORE_FLOOR, part_spec.CBORE_FLOOR_PLACES),
                ("CBORE_FLOOR", "ENGAGEMENT_MIN", "ENGAGEMENT_MAX"),
            ),
            "height_nominal": (part_spec.CBORE_FLOOR, ("CBORE_FLOOR",)),
            "height_from": ("carriage_seat", ("CBORE_FLOOR",)),
            "note": (part_spec.CBORE_FLOOR_CALLOUT, ("CBORE_FLOOR_CALLOUT",)),
            "depth_ref": (part_spec.CBORE_DEPTH, ("CBORE_DEPTH",)),
        },
        precision={
            "dia": part_spec.CALLOUT_PLACES,
            "height": part_spec.CBORE_FLOOR_PLACES,
        },
    )


_SIDE_PLACES = part_spec.SIDE_STATION_PLACES
_SIDE_CBORE_PLACES = part_spec.SIDE_CBORE_PLACES
_SIDE_DIA_PRINTED = round(SIDE_HOLE_DIA, part_spec.SIDE_THRU_PLACES)
for _index, (_x, _z) in enumerate(SIDE_SCREW_HOLES, start=1):
    # Stations from the -X end and the bottom face at .XXX: the pair holds
    # TL-29's tapped pair inside the #8 screws' float (spec SIDE_SCREW_FLOAT).
    requirement(
        f"side_screw_hole_{_index}",
        kind="hole",
        faces=(CylinderFace(SIDE_HOLE_DIA, contains_x_mm=_x, contains_z_mm=_z),),
        requirements=("station", "height", "dia", "thru", "note"),
        fields={
            "at": ([_x, _HW, _z], ("SIDE_SCREW_HOLES", "BLOCK_WIDTH")),
            "axis": (_INTO_Y, ("__frame__",)),
            "station": (
                limits(_x - part_spec.DATUM_X, _SIDE_PLACES),
                ("SIDE_SCREW_HOLES", "DATUM_X", "SIDE_SCREW_FLOAT"),
            ),
            "station_nominal": (
                _x - part_spec.DATUM_X,
                ("SIDE_SCREW_HOLES", "DATUM_X"),
            ),
            "height": (
                limits(_z, _SIDE_PLACES),
                ("SIDE_SCREW_HOLES", "SIDE_SCREW_FLOAT"),
            ),
            "height_nominal": (_z, ("SIDE_SCREW_HOLES",)),
            # The row's dimension says so (CALLOUTS_BELOW, c4 review).
            "height_from": ("bottom_face", ("SIDE_ROW_CALLOUT", "CALLOUTS_BELOW")),
            "dia": (
                limits(
                    _SIDE_DIA_PRINTED,
                    part_spec.SIDE_THRU_PLACES,
                    part_spec.DRILLED_BAND,
                ),
                ("SIDE_HOLE_DIA", "SIDE_SCREW_HOLE_SPEC", "DRILLED_BAND"),
            ),
            "dia_nominal": (_SIDE_DIA_PRINTED, ("SIDE_HOLE_DIA",)),
            "thru": (True, ("SIDE_SCREW_HOLE_SPEC",)),
            # The pair's tight band names its mate; the walls' shortfall
            # (rule 20) prints under it.
            "note": (
                " ".join(SIDE_CALLOUT_BELOW.split("\n")),
                ("SIDE_CALLOUT_BELOW", "SIDE_SCREW_MATE", "SIDE_WALL_CALLOUT"),
            ),
        },
        precision={
            "station": _SIDE_PLACES,
            "height": _SIDE_PLACES,
            "dia": part_spec.SIDE_THRU_PLACES,
        },
    )
    requirement(
        f"side_screw_hole_{_index}_counterbore",
        kind="counterbore",
        faces=(CylinderFace(SIDE_CBORE_DIA, contains_x_mm=_x, contains_z_mm=_z),),
        requirements=("dia", "depth"),
        fields={
            "parent": (
                f"side_screw_hole_{_index}",
                (
                    "SIDE_HOLE_DIA",
                    ("draw_ch_rocker_arm_tl_oblique_pivot_block", "build"),
                ),
            ),
            "dia": (
                limits(SIDE_CBORE_DIA, _SIDE_CBORE_PLACES),
                ("SIDE_CBORE_DIA", "SIDE_SCREW_HEAD_DIA", "WORST_WALLS"),
            ),
            "dia_nominal": (SIDE_CBORE_DIA, ("SIDE_CBORE_DIA",)),
            "depth": (
                limits(part_spec.SIDE_CBORE_DEPTH, _SIDE_CBORE_PLACES),
                ("SIDE_CBORE_DEPTH", "SIDE_SCREW_HEAD_HEIGHT", "WORST_WALLS"),
            ),
            "depth_ref": (part_spec.SIDE_CBORE_DEPTH, ("SIDE_CBORE_DEPTH",)),
        },
        precision={"dia": _SIDE_CBORE_PLACES, "depth": _SIDE_CBORE_PLACES},
    )


def screw_hole_callout_definitions(
    definitions: dict[int, str], below: str, *, reference_depth: bool
) -> dict[int, str]:
    """DRILL in the native THRU row, ``below`` under the callout and, with
    ``reference_depth``, the counterbore depth as a reference.

    A counterbored callout prints its THRU row from the CalloutAbove part (7)
    and its counterbore row from the Prefix part (5), so a Prefix process
    would read "DRILL ⌴Ø8.00" (draw_ch_fulcrum_keeper). The process goes into
    the THRU part instead, after its instance count ("4X DRILL Ø4.50 THRU
    ALL"); the CalloutBelow part (8) carries ``below``: the mate the
    three-place hole stations serve (rule 4), and for the side screws the
    counterbore walls' rule-20 shortfall. For the carriage screws the
    counterbore row's one depth variable is bracketed, "↧ (8.40)": the
    floor's height from the carriage seat (section B-B) is the dimension
    (draw_mg_output_fixture's reference thread depth).
    """
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected screw-hole callout parts: {definitions!r}")
    thru_parts = [part for part, text in definitions.items() if "THRU" in text.upper()]
    if len(thru_parts) != 1 or thru_parts[0] == 8:
        raise RuntimeError(
            f"screw-hole THRU row is not one upper part: {definitions!r}"
        )
    if definitions[8].strip():
        raise RuntimeError(f"screw-hole callout already prints below: {definitions!r}")
    part = thru_parts[0]
    bracketed: dict[int, str] = {}
    if reference_depth:
        depth_parts = [p for p, text in definitions.items() if "<HOLE-DEPTH>" in text]
        depth = (
            _CBORE_DEPTH_TOKEN.search(definitions[depth_parts[0]])
            if len(depth_parts) == 1
            else None
        )
        if (
            depth is None
            or depth_parts[0] in (part, 8)
            or definitions[depth_parts[0]].count("<HOLE-DEPTH>") != 1
        ):
            raise RuntimeError(
                "screw-hole callout has no single bare counterbore depth: "
                f"{definitions!r}"
            )
        depth_text = definitions[depth_parts[0]]
        bracketed = {depth_parts[0]: f"{depth_text[: depth.start(2)]}({depth[2]})"}
    text = definitions[part]
    count = re.match(r"\s*<NUM_INST>X ", text)
    if count:
        updated = f"{text[: count.end()]}{SCREW_HOLE_PROCESS} {text[count.end() :]}"
    else:
        updated = compose_hole_callout_prefix(SCREW_HOLE_PROCESS, text)
    return {**definitions, part: updated, **bracketed, 8: below}


@_telemetry.traced("drawing.pivot_block.screw_hole_callout", label_param="label")
def _set_screw_hole_callout(
    display: Any, below: str, *, reference: str | None, label: str
) -> None:
    """Write a screw callout's process and lower rows, and its reference
    depth when ``reference`` names it; prove they persisted."""
    native = _early_bound(display, "IDisplayDimension")

    def read(parts: tuple[int, ...]) -> dict[int, str]:
        # Multi-line text may read back with CR LF (draw_pd_support_bar).
        return {
            part: str(native.GetText(part) or "").replace("\r", "") for part in parts
        }

    definitions = read((5, 6, 7, 8))
    updated = screw_hole_callout_definitions(
        definitions, below, reference_depth=reference is not None
    )
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = read((5, 6, 7, 8))
    resolved = read((1, 2, 3, 4))
    joined = "\n".join(resolved.values())
    if (
        persisted != updated
        or SCREW_HOLE_PROCESS not in (resolved[3] + resolved[1])
        or (reference is not None and joined.count(reference) != 1)
    ):
        raise RuntimeError(
            f"{label}: callout rows did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}, "
            f"expected reference depth {reference}"
        )
    _telemetry.info(f"{label} callout: {resolved!r}")


def _view_mapper(adapter: Any, view: Any):
    """Return model point (mm) -> sheet xy (m) through the view's transform."""
    transform = _early_bound(
        _early_bound(view, "IView").ModelToViewTransform, "IMathTransform"
    )
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")

    def to_sheet(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        point = _early_bound(
            math_utility.CreatePoint(double_array([c / 1000.0 for c in model_mm])),
            "IMathPoint",
        )
        data = _early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData
        return float(data[0]), float(data[1])

    return to_sheet


def _seat_gdt(adapter: Any, section_a: Any, on_a: Any) -> None:
    """Datum A on the bottom seat (A-A's -X wall) and the top seat's native
    position frame to it on the top seat's +X wall: the seats are bored from
    opposite faces, and only this ties them on one axis (review r8); both in
    A-A, so the reader sees which seat is which (review r12)."""
    add_datum_feature(
        adapter,
        section_a,
        edge_xy=on_a(SEAT_DATUM_EDGE),
        symbol_xy=on_a(SEAT_DATUM_SYMBOL),
        datum=part_spec.SEAT_DATUM,
        label="pivot block bottom seat datum A",
    )
    add_feature_control_frame(
        adapter,
        section_a,
        edge_xy=on_a(SEAT_FRAME_EDGE),
        frame_xy=on_a(SEAT_FRAME_CORNER),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["top seat position to bottom seat"],
        datums=(part_spec.SEAT_DATUM,),
        diameter=True,
        label="pivot block top seat position to A",
    )


def _orient_section_b(adapter: Any, section: Any) -> None:
    """Turn section B-B into alignment with its cutting line: model +Y (the
    line's run up the plan) runs UP the sheet, so no ROTATED label is due
    (review r6). The cut direction stays the one SolidWorks gives it: a
    reversed partial section showing its far side imported nothing (carrier
    jig-r4). Seen along the +X arrows, +Z must then read right; anything
    else would contradict the arrows."""
    native = _early_bound(section, "IView")

    def axis(offset: tuple[float, float, float]) -> tuple[float, float]:
        on_b = _view_mapper(adapter, native)
        origin = on_b(SECTION_B_ANCHOR)
        moved = on_b(tuple(a + b for a, b in zip(SECTION_B_ANCHOR, offset)))
        return moved[0] - origin[0], moved[1] - origin[1]

    plus_y = axis((0.0, 1.0, 0.0))
    native.Angle = (
        float(native.Angle) + math.pi / 2.0 - math.atan2(plus_y[1], plus_y[0])
    )
    rebuild_drawing(adapter, label="pivot block section B-B aligned")
    plus_y, plus_z = axis((0.0, 1.0, 0.0)), axis((0.0, 0.0, 1.0))
    if plus_y[1] <= 0.0 or abs(plus_y[0]) > 1e-7:
        raise RuntimeError(f"pivot block section B-B is not +Y up: {plus_y=}")
    if plus_z[0] <= 0.0 or abs(plus_z[1]) > 1e-7:
        raise RuntimeError(
            f"pivot block section B-B does not read +Z right along +X: {plus_z=}"
        )


def _centre_section_b(adapter: Any, section: Any) -> None:
    """Land the strip's centre on SECTION_B_CENTER through a projected model
    point, not the outline (carrier ``_centre_section``)."""
    native = _early_bound(section, "IView")
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        projected = _view_mapper(adapter, native)(SECTION_B_ANCHOR)
        if math.dist(projected, SECTION_B_CENTER) <= 1e-4:
            return
        position = tuple(float(value) for value in native.Position)
        moved = [
            position[axis] + SECTION_B_CENTER[axis] - projected[axis] for axis in (0, 1)
        ]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to re-centre pivot block section B-B")
        rebuild_drawing(adapter, label=f"pivot block section B-B re-centred {attempt}")
    raise RuntimeError(
        f"pivot block section B-B centre {projected} missed {SECTION_B_CENTER}"
    )


def _cbore_floor_section(adapter: Any, source_model: Any, plan: Any) -> list[Any]:
    """Full section B-B through both -X counterbores, carrying the floor's
    height from the carriage seat.

    The floor's hidden owner sketch lies in the cutting plane; a derived view
    takes it from the part as it stands when cut and selects it through its
    base view, so the section is cut and curated while the part shows it
    (draw_pd_platen ``_floor_section``). A section shows no hidden lines.
    """
    on_plan = _view_mapper(adapter, plan)
    with hidden_sketches.part_sketches_shown(
        adapter,
        source_model,
        (CBORE_FLOOR_REFERENCE,),
        label="section B-B counterbore floor reference",
        base_view=plan,
    ):
        section = create_section_view(
            adapter,
            plan,
            line_start=on_plan((-BOLT_X, CUT_B_Y[0], _H)),
            line_end=on_plan((-BOLT_X, CUT_B_Y[1], _H)),
            view_xy=SECTION_B_CENTER,
            section_label="B",
            scale=VIEW_SCALE,
            partial=False,
            label="pivot block counterbore section",
        )
        _orient_section_b(adapter, section)
        set_hidden_lines_removed(adapter, section)
        _centre_section_b(adapter, section)
        on_b = _view_mapper(adapter, section)
        annotations = hidden_sketches.curate_view_dimensions(
            adapter,
            section,
            keep={name: on_b(xyz) for name, xyz in SECTION_B_KEEP.items()},
            view_label="section B-B",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    position_section_caption(adapter, section, CAPTION_B_XY, label="pivot block B")
    return annotations


def _bore_axis_section(
    adapter: Any, source_model: Any, plan: Any
) -> tuple[Any, list[Any]]:
    """Section A-A on the bore axis, with the side screws' row height.

    The row's 9.000 lives on SideScrewReference, a sketch the part saves
    hidden on the Top plane (Y = 0, A-A's cutting plane), so the section is
    cut and curated while the part shows it, as B-B is
    (``_cbore_floor_section``).
    """
    on_plan = _view_mapper(adapter, plan)
    with hidden_sketches.part_sketches_shown(
        adapter,
        source_model,
        (SIDE_SCREW_REFERENCE,),
        label="section A-A side screw reference",
        base_view=plan,
    ):
        section = create_section_view(
            adapter,
            plan,
            line_start=on_plan((CUT_A_X[0], 0.0, _H)),
            line_end=on_plan((CUT_A_X[1], 0.0, _H)),
            view_xy=SECTION_A_CENTER,
            section_label="A",
            scale=VIEW_SCALE,
            label="pivot block bore-axis section",
        )
        set_hidden_lines_removed(adapter, section)
        on_a = _view_mapper(adapter, section)
        annotations = hidden_sketches.curate_view_dimensions(
            adapter,
            section,
            keep={name: on_a(xyz) for name, xyz in SECTION_A_KEEP.items()},
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    position_section_caption(adapter, section, CAPTION_A_XY, label="pivot block A")
    return section, annotations


def _label_side_view(adapter: Any, plan: Any, on_plan: Any) -> None:
    """Name the removed side view: its letter arrow on the plan's +Y edge
    and its caption (review c4r3: out of projection, unlabelled)."""
    tip = on_plan(SIDE_VIEW_ARROW_TIP)
    note = add_leader_note(
        adapter,
        SIDE_VIEW_LETTER,
        text_xy=(
            tip[0] + SIDE_VIEW_LETTER_OFFSET[0],
            tip[1] + SIDE_VIEW_LETTER_OFFSET[1],
        ),
        attach_xy=tip,
        view=plan,
        height=SIDE_VIEW_LETTER_HEIGHT,
        label=f"view {SIDE_VIEW_LETTER} viewing arrow",
    )
    if note is None:
        raise RuntimeError(f"failed to add the view {SIDE_VIEW_LETTER} arrow")
    if add_note(adapter, SIDE_VIEW_CAPTION, *SIDE_VIEW_CAPTION_XY) is None:
        raise RuntimeError(f"failed to add the {SIDE_VIEW_CAPTION!r} caption")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pivot block source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Oblique Trammel Pivot Block Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker oblique trammel pivot block; 6061-T6; MHA-CH-006-TL-22",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=VIEW_SCALE)
    on_plan = _view_mapper(adapter, plan)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    side = place_view(adapter, str(SOURCE), "*Top", *SIDE_CENTER, scale=VIEW_SCALE)
    for view in (plan, iso, side):
        set_hidden_lines_removed(adapter, view)

    on_side = _view_mapper(adapter, side)
    annotations = curate_view_dimensions(
        adapter,
        plan,
        keep={name: on_plan(xyz) for name, xyz in PLAN_KEEP.items()},
        view_label="plan view",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_a, side_row = _bore_axis_section(adapter, source_model, plan)
    annotations += side_row
    on_a = _view_mapper(adapter, section_a)
    # The side stations live on SideScrewReference, a sketch the part saves
    # hidden: the side view shows it per view (_drawing_hidden_sketches).
    annotations += hidden_sketches.curate_view_dimensions(
        adapter,
        side,
        keep={name: on_side(xyz) for name, xyz in SIDE_KEEP.items()},
        view_label="side view",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # The floor height lives on CboreFloorReference, a sketch the part saves
    # hidden: _drawing_hidden_sketches shows it while B-B is cut and curated.
    annotations += _cbore_floor_section(adapter, source_model, plan)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, _hung_clear(CALLOUTS_BELOW))
    # Natively the bore's leader runs rim to rim through the centre and across
    # line A (jig-r2); one arrow on the near (left) rim keeps it short and
    # above the line.
    bore_dia = [a for a in annotations if dimension_name(adapter, a) == "BoreDia"]
    if len(bore_dia) != 1:
        raise RuntimeError(f"expected one BoreDia dimension, found {len(bore_dia)}")
    set_near_side_diameter(bore_dia[0], "pivot block bore diameter")
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _set_screw_hole_callout(
        add_native_hole_callout(
            adapter,
            plan,
            edge_xy=on_plan(SCREW_CALLOUT_EDGE),
            callout_xy=SCREW_CALLOUT_XY,
            label="carriage screw counterbores",
        ),
        SCREW_MATE_CALLOUT,
        reference=f"({part_spec.CBORE_DEPTH:.{part_spec.CALLOUT_PLACES}f})",
        label="carriage screw holes",
    )
    side_callout = add_native_hole_callout(
        adapter,
        side,
        edge_xy=on_side(SIDE_CALLOUT_EDGE),
        callout_xy=SIDE_CALLOUT_XY,
        label="nut-bracket screw counterbores",
    )
    _set_screw_hole_callout(
        side_callout, SIDE_CALLOUT_BELOW, reference=None, label="side screw holes"
    )
    # The counterbore's walls take three places; the THRU size the template's two.
    set_hole_callout_precision(
        side_callout, SIDE_CALLOUT_PRECISION, label="nut-bracket screw counterbores"
    )
    _seat_gdt(adapter, section_a, on_a)
    _label_side_view(adapter, plan, on_plan)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Oblique Trammel Pivot Block Drawing",
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
