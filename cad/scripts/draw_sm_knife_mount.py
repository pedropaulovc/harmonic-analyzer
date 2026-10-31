r"""Create the curated machinist drawing for the knife-mount bearing block.

A machined, heat-treated steel block (25.4 wide x ~29.6 tall x 14 deep) with a
single Ø12 bore.  The bore is the knife-edge bearing: the summing-lever
trunnion's top vertex rides its upper inner wall in line contact (ch18 p.42:
unpainted hardened steel, close bore -- 2026-09-02 user re-read).  Every face
and the bore are real edges, so
the block dimensions ride the auto-imported profile marks (block + bore) with the
depth added across the right-view section.  The MHA-SM-VN-53 dowels press into
the crossbar and slip into this block (owner ruling 2026-10-24, T+H3): its
round slip hole, datum B, prints its reamed Ø, band and mate and a ⊥Ø0.015
frame to A that carries B, located on the +X side and front faces at general
tolerance; its slot, datum C, open to the -X face, prints its width, band and
mate under a position frame to A|B stacked over a ⊥0.015 frame to A, the
stack carrying C (owner ruling 2026-10-27, #2016), its half-round end
located from B, all
in the top view.  Their shared flat-floor depth is in section A-A, cut from
the top view through the tap and dowel axes (drawing-guidelines.md rule 9
(show internal shape in solid lines): the floor is hidden in the front view,
so it is dimensioned where the cut shows it); the tap axis, run on through
the bore's centre, stands BASIC 7.632 from B's axis there.  The reamed bore
carries a composite position frame to A|B|C (owner ruling 2026-10-27,
#2016), its centre a BASIC height under A; the
#10-24 tap a position frame to the same A|B|C, its #25
pilot at three places under the title block's DRILLED HOLES row, its full
thread at two with its own native +/-0.13, its class the title block's
thread row, its drill depth banded, its drill point dimensioned (under the
general angular band) and its mating bolt named on its hole callout.
The bore carries Ra 1.6, the top seat Ra 3.2.  Every view is
hidden-lines-removed.

Run with SolidWorks open::

    uv run python cad\scripts\draw_sm_knife_mount.py sm-knife-mount
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    remove_notes_matching,
    view_name,
)

import _config
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
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_arc_endpoints_to_center,
    set_basic_dimension,
    set_dimension_callouts,
)
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_finish import add_surface_finish
from _drawing_gdt import (
    add_datum_feature,
    add_feature_control_frame,
    add_frame_datum_feature,
    assert_frame_datums_defined,
)
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leaders import set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from build_sm_knife_mount import BORE_CENTRE_DEPTH
from sm_knife_mount_spec import (
    BLK_BOT,
    BLK_HALF_X,
    BLK_TOP,
    BORE_CY,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    GEOMETRIC_TOLERANCES_IN,
    HOLE_ROW_FACE_DISTANCE,
    PIN_DEPTH_CALLOUT,
    PIN_HOLE_CALLOUT,
    PIN_HOLE_DEPTH,
    PIN_HOLE_DIA,
    PIN_HOLE_SIDE_DISTANCE,
    PIN_HOLE_X,
    R_BORE,
    SLOT_END_FROM_B,
    SLOT_WIDTH,
    SLOT_WIDTH_CALLOUT,
    STUD_TAP_DIA,
    STUD_TAP_DRILL_DEPTH,
    STUD_TAP_DRILL_DEPTH_BAND,
    STUD_TAP_DRILL_DEPTH_PLACES,
    STUD_TAP_POINT_ANGLE_DEG,
    STUD_TAP_POINT_ANGLE_PLACES,
    STUD_TAP_THREAD_DEPTH,
    STUD_TAP_THREAD_DEPTH_BAND,
    STUD_TAP_THREAD_DEPTH_PLACES,
    SUPPORT_Z_THICK,
    SURFACE_FINISHES,
    UNIT,
    TAP_CALLOUT_REASON,
    TAP_DRILL_CALLOUT,
)

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["sm_knife_mount"]
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
# SolidWorks' own descriptive thread note; the tap's hole callout states the tap.
TAPPED_HOLE_NOTE = "Tapped Hole"
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym

SHEET_SCALE = (2.0, 1.0)
_BLOCK_CY = (BLK_TOP + BLK_BOT) / 2.0  # block centre height (model mm)

# The front and right views stand 15 mm under their former 0.140 (owner
# ruling 2026-10-24, T+H3): the band between the front and top views takes
# the tap's callout and frame lowered under the datum-C slot frame and its
# tag, left of the top view.  The 25.4 under the front view stays ~67 mm
# over the border.
FRONT_CENTER = (0.115, 0.125)
RIGHT_CENTER = (0.220, 0.125)
TOP_CENTER = (0.115, 0.235)
ISO_CENTER = (0.345, 0.210)
# Section A-A stands right of the right view and under the isometric, clear
# of the title block (x > 0.216 below y 0.066): the block spans sheet y
# 0.0955..0.1545 at 2:1 and its label hangs under it.
SECTION_CENTER = (0.300, 0.125)
# The cutting line (model z = 0, through the tap and dowel axes) runs this
# far past each block face in the top view.
SECTION_LINE_OVERRUN_MM = 2.5
SECTION_LINE_MODEL_MM = (
    (-(BLK_HALF_X + SECTION_LINE_OVERRUN_MM), BLK_TOP, 0.0),
    (BLK_HALF_X + SECTION_LINE_OVERRUN_MM, BLK_TOP, 0.0),
)


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - _BLOCK_CY) * SHEET_SCALE[0] / 1000.0


def _section_y(model_y_mm: float) -> float:
    """Sheet y of a model y in section A-A (it looks along -Z, as the front)."""
    return SECTION_CENTER[1] + (model_y_mm - _BLOCK_CY) * SHEET_SCALE[0] / 1000.0


def _section_x(model_x_mm: float) -> float:
    """Sheet x of a model x in section A-A (+X right, as the front)."""
    return SECTION_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _sheet_x(model_x_mm: float) -> float:
    """Sheet x of a model x in the front and top views (shared column)."""
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


# The 29.6 height's dimension line stands at sheet x 0.024, 65.6 mm off the
# block's -X face (its text 6 mm inside the border), and the bore's Ø, its
# bored band and its three callout
# rows (BORE THRU, then the knife seat's mate, BORE_CALLOUT below) sit in
# the band between them: the 5ff8fba5d render ran the
# height line (then x 0.063) 3.62 mm through the Ø (text 58.5..75.3 mm).
# BORE_DIA_TEXT_HALF_WIDTH is half the widest row, "MHA-SM-03 TRUNNION": 18
# capitals at the ~2.52 mm a character the tap callout's 31-character reason
# row printed (78 mm, run 20261024T081603839Z), 45.4 mm.
BORE_DIA_TEXT_HALF_WIDTH = 0.0227
# SolidWorks centres the five rows (+0.03 / Ø12.00 0.00 / three callout rows)
# on the text position: farm run 20261024T114146582Z printed the top row
# 12.8 mm over a position 30 mm above the bore centre, through the block
# top's 29.6 extension line (sheet y 169.6, text-on-line).  At 23 mm the
# top row stands ~164.2, 5.4 mm under that line, and the bottom row stays
# above the bore centre so the leader descends to the upper-left rim.
BORE_DIA_TEXT_RISE = 0.023
BORE_DIA_TEXT_TOP_REACH = 0.0128
FRONT_KEEP = {
    "BlockWidth": (FRONT_CENTER[0], _front_y(BLK_BOT) - 0.016),
    "BlockHeight": (FRONT_CENTER[0] - 0.091, FRONT_CENTER[1]),
    "BoreDia": (FRONT_CENTER[0] - 0.0565, _front_y(BORE_CY) + BORE_DIA_TEXT_RISE),
}
# The hole and slot floor depth stands right of the section, its witness
# lines off the cut top seat and that floor; "2X FLAT BOTTOM" with it
# states that the slot's floor, cut in the same pass, is the same; its
# corner is the title block's (sm_knife_mount_spec.PIN_DEPTH_CALLOUT).  The
# dimension line stands at BLK_HALF_X + 12.0, x
# 349.4 mm (farm run 20261027T175429300Z), 14.9 mm right of the 7.632
# BASIC's shoulder end (x 334.5 mm, farm run 20261027T133857303Z); its
# witness lines run to x 350.4.  Left in line, the value and its rows
# printed the value across the top seat's witness and the dimension line's
# outer tail (y 152.9..156.4 mm, run 20261027T175429300Z:
# extension-through-own-text, dim-line-through-own-text), so the text
# parks on a jog right of the witness lines' ends, draw_fr_top_frame's
# HANGER_PIN_DEPTH_OFFSET_XY form.  That form's three-row callout (value,
# "4X FLAT BOTTOM,", "CORNER R0.1 MAX") printed in run 20261027T175429300Z
# with every row centred on the offset x, the value's baseline 2.78 mm over
# the offset y and the rows' 5.56 mm under each other, 3.5 mm tall, the
# widest 41.94 mm; the leader left the dimension line's midpoint for the
# underline's left end, the underline under the last row.  This block's
# two rows keep that 42 mm slot centred on the same x.
DEPTH_VALUE_RISE = 0.00278
DEPTH_ROW_PITCH = 0.00556
DEPTH_TEXT_HEIGHT = 0.0035
DEPTH_TEXT_ROWS = 1 + len(PIN_DEPTH_CALLOUT.splitlines())
DEPTH_ROW_HALF_WIDTH = 0.021
# The underline's left end 5.9 mm right of the dimension line (the F-F
# jog's 5.88), 4.9 mm past the witness lines' ends; the block's rows centred
# on the hole's mid-depth, between the witness lines, so the leader falls
# 7.3 mm to the underline and crosses nothing.  The block's right end,
# ~397.3 mm, stands 21.8 mm inside the border, under the isometric's caption
# (y 170.5 mm) by 17.8 mm.
DEPTH_LEADER_RUN = 0.0059
PIN_DEPTH_LINE_X = SECTION_CENTER[0] + (BLK_HALF_X + 12.0) * SHEET_SCALE[0] / 1000.0
_PIN_DEPTH_MID_Y = _section_y(BLK_TOP - PIN_HOLE_DEPTH / 2.0)
SECTION_KEEP = {"PinHoleDepth": (PIN_DEPTH_LINE_X, _PIN_DEPTH_MID_Y)}
# The block runs from the value's top, RISE + HEIGHT over the offset y, to
# the underline, RISE - (ROWS - 1) * PITCH from it.
PIN_DEPTH_OFFSET_XY = (
    PIN_DEPTH_LINE_X + DEPTH_LEADER_RUN + DEPTH_ROW_HALF_WIDTH,
    _PIN_DEPTH_MID_Y
    - DEPTH_VALUE_RISE
    - (DEPTH_TEXT_HEIGHT - (DEPTH_TEXT_ROWS - 1) * DEPTH_ROW_PITCH) / 2.0,
)
# Datum A's tag on the front view's top edge, 8 mm right of centre (build()).
DATUM_A_X = FRONT_CENTER[0] + 0.008
# The tap and bore frames reference A|B|C, so the tap axis stands BASIC
# 7.632 from datum B's axis (blind machinist review, 2026-10-10: the implied
# centre left the tap and bore with no explicit horizontal location).  It is
# dimensioned in section A-A, the one view that cuts the tap, the bore and
# B's hole together, between two owned axes: the tap's, run on down through
# the bore's centre so one axis carries both, and B's.  Each starts
# SECTION_AXIS_OVERRUN_MM above the top seat and ends SECTION_AXIS_TAIL_MM
# past its feature (the bore's bottom, the hole's floor), inside the block.
SECTION_AXIS_OVERRUN_MM = 2.0
SECTION_AXIS_TAIL_MM = 1.0
# The dimension line stands 8 mm over the cut top seat, in the open band
# under the isometric's caption.  Its boxed value (~14 mm) all but fills the
# 15.3 mm between the axes, so it parks on a leader right of B's axis
# (draw_fr_top_frame's F-F station precedent: text past the arrows
# otherwise rides the dimension line), over the depth's top witness line.
TAP_STATION_TEXT_XY = (_section_x(PIN_HOLE_X / 2.0), _section_y(BLK_TOP) + 0.008)
TAP_STATION_OFFSET_XY = (_section_x(PIN_HOLE_X) + 0.012, TAP_STATION_TEXT_XY[1])
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
TOP_HALF_Z = SUPPORT_Z_THICK / 2.0 * SHEET_SCALE[0] / 1000.0
# Datum B's Ø and its three callout lines park in the open band right of
# and below the top view (drawing-guidelines.md rule 14 (keep text off the
# part): callout text outside the silhouette, no text on a line).
# SolidWorks hangs the block left of its text position by half the widest
# line plus the shoulder's overhang, centres the rows on that position and
# runs the shoulder under the last line; its leader leaves the shoulder's
# near end radially for the hole's centre (farm run 20261014T010316127Z: a
# shoulder at (146.4, 222.2) mm landed the arrow at -38.6 deg).  The dda9a33a8
# render measured a 5-row label at 84.5 mm wide, its shoulder 1.6 mm past it
# and 12.86 mm under the text position; four rows stand a half row (~2.1 mm)
# less.  The widest row, "0.047-0.093 DIAMETRAL CLEARANCE", is 31 capitals
# at ~2.52 mm (78 mm).  The shoulder starts 22 mm under the hole row, so the
# leader rises at ~-58 deg into the hole across the front-face edge inside
# the block (x 139.1 mm), under the B row's 7.0 and its witness line.
PIN_CALLOUT_HALF_WIDTH = 0.039
PIN_CALLOUT_SHOULDER_OVERHANG = 0.0016
PIN_CALLOUT_SHOULDER_DROP = 0.0105
PIN_CALLOUT_SHOULDER_START = (_sheet_x(BLK_HALF_X) + 0.0126, TOP_CENTER[1] - 0.036)
# The slot's inner end, its half-round end's centre from B's axis
# (SlotEndFromB, a model dimension), runs above the top view between the two
# centres, where the dowel pair's BASIC span stood, its value 1 mm right of
# centre so the side-face 5.07's left arrow (a row up) stands clear of it.
SLOT_END_TEXT_XY = (
    _sheet_x((PIN_HOLE_X + PIN_HOLE_X - SLOT_END_FROM_B) / 2.0) + 0.001,
    TOP_CENTER[1] + TOP_HALF_Z + 0.0075,
)
# B's face locations (blind machinist review, 2026-10-09), both in the top
# view: its axis from the +X side face, a row above the slot end's (under
# the view, the 20261010T001553082Z render ran a frame's leader across its
# side-face extension line; on the next row down, 20261010T002544960Z, the
# two dimensions' outside arrows met under it and its right arrow ran into
# the cutting line's "A", top 256.9 mm).  Its arrows clear that letter by
# ~2.8 mm and its text the border by ~2.8 mm.
PIN_SIDE_TEXT_XY = (
    _sheet_x(BLK_HALF_X - PIN_HOLE_SIDE_DISTANCE / 2.0),
    TOP_CENTER[1] + TOP_HALF_Z + 0.0135,
)
# B's axis from the front face (the view's lower edge), its line 9.6 mm right
# of the +X face, 4.6 mm right of the A-A cutting line's arrow, its witness
# line from B's axis riding the cutting line's end.  Left of the block the
# datum-C slot's width and frame take the band (a vertical row dimension
# there would cross the slot width's witness lines).
ROW_FACE_TEXT_XY = (
    _sheet_x(BLK_HALF_X) + 0.0096,
    TOP_CENTER[1] - TOP_HALF_Z + HOLE_ROW_FACE_DISTANCE * SHEET_SCALE[0] / 1000.0 / 2.0,
)
# The slot's width (SlotWidth, a model dimension) stands left of the block.
# SolidWorks prints a vertical dimension's text left of its dimension line,
# so the line stands at the text position's x and the three rows (the width,
# OPEN-END SLOT, the mate, ~59 mm) end just left of it.  At 43.6 mm off the
# -X face the rows ran 25.8 mm past the left border (layout audit, farm run
# 20261027T030041319Z: box x -13.1..82.1 mm, its right end the extension
# lines from the slot's sides).  At 11.6 mm off the face the line stands
# 6.6 mm left of the A-A cutting line's end (84.6 mm) and the rows ~17..76.
SLOT_WIDTH_TEXT_XY = (_sheet_x(-BLK_HALF_X) - 0.0116, TOP_CENTER[1] + 0.017)
TOP_KEEP = {
    "PinHoleDia": (
        PIN_CALLOUT_SHOULDER_START[0]
        + PIN_CALLOUT_SHOULDER_OVERHANG
        + PIN_CALLOUT_HALF_WIDTH,
        PIN_CALLOUT_SHOULDER_START[1] + PIN_CALLOUT_SHOULDER_DROP,
    ),
    "SlotWidth": SLOT_WIDTH_TEXT_XY,
    "SlotEndFromB": SLOT_END_TEXT_XY,
}
# The knife bore is reamed (Ra 1.6, +0.03/0 band): the process is stated
# (blind machinist review, 2026-10-09: a bare THRU left drill or ream open),
# and the band's mate under it (ENFORCE review, 2026-10-24, rule 4): the
# summing lever's hex trunnion, whose top ridge rocks on the bore's crown,
# the knife seat.  The mate's number is drawing text only, read here, not in
# sm_knife_mount_spec: the spec is in MHA-FR-02's and the frame assembly's
# import closure, which must not key on the lever's registry row.  Datum
# B's slip band and the slot's name their mate (owner ruling 2026-10-24,
# T+H3); the floor depth states it holds for both.
LEVER_NUMBER = str(_config.parts("sm-summing-lever")["number"])
BORE_CALLOUT = "\n".join(("BORE THRU", "KNIFE SEAT FOR", f"{LEVER_NUMBER} TRUNNION"))
DIMENSION_CALLOUTS = {
    "BoreDia": BORE_CALLOUT,
    "PinHoleDia": PIN_HOLE_CALLOUT,
    "SlotWidth": SLOT_WIDTH_CALLOUT,
    "PinHoleDepth": PIN_DEPTH_CALLOUT,
}
# Datum C's frames stand left of and under the slot: its width's ⌖0.05 to
# A|B and, stacked under it on the same leader, its ⊥0.015 to A (owner
# ruling 2026-10-27, #2016: a width, so a planar zone, no Ø); datum C's
# symbol hangs under the stack.  The stack's top stands 6 mm over the single
# frame farm run 20261027T133857303Z printed (top 214.0 mm), so the C box
# (195..202 mm, 1 mm lower than that run's) stands 4.7 mm over the tap
# callout's printed top row (190.3 mm), 3.6 over its TAP_CALLOUT_TOP_REACH
# envelope.  The stack also stands 5 mm further right, so the leader's root
# (the upper row's mid-height, 6.35 mm right of its right end) climbs more
# steeply.  The leader lands on the slot's lower (front) wall
# SLOT_FRAME_WALL_X along the line, 4.2 mm inside the -X face, and passes
# ~3 mm under the end of the slot width's lower arrow tail (78.0, 225.41 mm
# in that run).  The stack is
# ~34.7 mm wide: the ⊥ glyph widens the symbol column to 8.4 mm and
# "0.015" the value column to ~14.5 (farm run 20261024T121140093Z printed
# the bore's stacked ⌖/⊥ frames with an 8.4 symbol column; "0.05" took an
# 11.9 column in run 20261027T133857303Z, at 2.6 mm a digit).
SLOT_FRAME_XY = (_sheet_x(-BLK_HALF_X) - 0.0646, TOP_CENTER[1] - 0.015)
_GTOL_ROW = 0.007
SLOT_FRAME_SIZE = (0.0347, 2 * _GTOL_ROW)
SLOT_FRAME_WALL_X = -(BLK_HALF_X - 4.2)
DATUM_TAG_BOX = 0.007
DATUM_TAG_STEM = 0.004
SLOT_DATUM_C_XY = (
    SLOT_FRAME_XY[0] + SLOT_FRAME_SIZE[0] / 2.0,
    SLOT_FRAME_XY[1] - SLOT_FRAME_SIZE[1] - DATUM_TAG_STEM - DATUM_TAG_BOX,
)
# Datum B's hole carries ⊥Ø0.015 to A (owner ruling 2026-10-27, #2016), and
# datum B's symbol hangs under that frame (ASME Y14.5: the datum feature
# symbol on the feature's frame).  The frame stands in the band between the
# top and front views, right of the tap frame's leader and under the Ø
# callout's shoulder (y 198.36 mm from x 151.74): ⊥ 8.4 + Ø0.015 ~18.7 +
# A 6.3, ~33.4 mm wide.  Its leader leaves a 6.35 shoulder off the frame's
# left end and lands on B's lower-left rim PIN_FRAME_RIM_DEG round from the
# view's +X, wholly left of the frame (so SolidWorks leaves the left end),
# ~2.5 mm left of B's vertical centre line (the centre mark's arm and the
# 14.40's witness line, x 130.26 mm) and ~4 mm round the rim from the Ø's
# arrow (131.9, 232.2 mm).  B's symbol hangs under the frame's middle on a
# stem 1 mm shorter than C's, its box (178..185 mm) left of the bore frame
# (x from 150.0, top 173.62 mm).  A tag on a frame is positioned relative
# to that frame (_drawing_gdt.add_frame_datum_feature), so on equal stems B
# and C both read (0, -4) mm in the view and the layout audit took one for a
# duplicate of the other (duplicate-annotation, farm run
# 20261027T162806664Z).
PIN_FRAME_XY = (0.1295, 0.195)
PIN_FRAME_SIZE = (0.0334, _GTOL_ROW)
PIN_FRAME_RIM_DEG = -140.0
PIN_DATUM_B_STEM = DATUM_TAG_STEM - 0.001
PIN_DATUM_B_XY = (
    PIN_FRAME_XY[0] + PIN_FRAME_SIZE[0] / 2.0,
    PIN_FRAME_XY[1] - PIN_FRAME_SIZE[1] - PIN_DATUM_B_STEM - DATUM_TAG_BOX,
)
# The #10-24 tap is stated once, on its Hole Wizard callout in the top view
# (fr-top-frame's KEEPER TAP precedent), not in a note.  Its drill row names
# the pilot by its drill, ``#25 DRILL`` (sm_knife_mount_spec.TAP_DRILL_CALLOUT),
# written in the native size token's place once the Hole Wizard's own drill
# Ø reads back as the #25's 3.797 (_prove_tap_drill): blind machinist review
# R4 read a three-place Ø3.797 as a precision no drill holds.  The named
# drill takes the title block's DRILLED HOLES row
# (sm_knife_mount_spec.STUD_TAP_DIA_BAND, indexed, not printed), and the
# thread its UNC with no class, the title block's thread row's 2B
# (drawing-guidelines.md rule 2 (the title block is the general
# specification)).  The full thread prints 9.65 with its own native +/-0.13
# (sm_knife_mount_spec.STUD_TAP_THREAD_DEPTH_BAND: bare, two places would
# claim the .XX row's +/-0.51), and the drill depth an explicit +/-0.05, the
# band the crown web and the tap's runout leave between them
# (sm_knife_mount_spec.STUD_TAP_DRILL_DEPTH_BAND).  The drill row also
# dimensions the drill's point -- SolidWorks' drill-angle variable after the
# drill depth, ``X 118°`` -- so the title block's angular band governs the
# point the crown web charges (sm_knife_mount_spec.STUD_TAP_POINT_ANGLE_MIN_DEG).
# Three printed rows: the drill row, the thread, and under it the reason the
# thread's band is there, naming the bolt
# (sm_knife_mount_spec.TAP_CALLOUT_REASON, in the below definition; no tap
# tool is named, rule 7); both bands are symmetric, printed inline, so none
# stacks a row of its own.  Farm build
# 20261013T225639.450330Z (c673e62ee) printed five, the pilot's stacked
# +0.10 and the mate each a row of its own (tall-block), at anchor (58.6,
# 209.0) mm: block x 20.0..97.1 (77.1 wide, the drill row the widest), top
# 217.4 (the +0.10 row 213.8..217.4), and RD4's (the 7.0's) outside tail
# (77.6, 221.0)->(77.6, 214.7) ran through that top row (text-on-line).  The
# three rows stand inside that envelope whichever way SolidWorks restacks
# them, so the block and its frame move down together by 6.0 mm: the top
# stays at or under 211.4, 3.3 mm under the tail's end (arrow-near-text gates
# under ARROW_TEXT_CLEARANCE_M, 2 mm), and the frame keeps the 15.6 mm under
# the anchor it printed at with no finding against the block.  The reason
# row, 16.13 em of Century Gothic, prints ~78 mm at the 4.83 mm an em the
# drill row's 15.97 em and 77.1 mm give: the widest row, inside the 88 mm the
# half width allows, its left end ~19.6 mm, 6.9 mm inside the 12.7 mm inner
# border (drawing-guidelines.md rule 13 (stay inside the border)), its right
# end, where the leader leaves, ~97.6.
TAP_CALLOUT_HALF_WIDTH = 0.044
TAP_CALLOUT_TOP_REACH = 0.0084
# T+H3 (2026-10-24): 20 mm lower again, under datum C's tag (bottom ~196 mm),
# its frame ~5.8 mm over the lowered front view's top edge.
TAP_CALLOUT_XY = (_sheet_x(-BLK_HALF_X) - 0.031, TOP_CENTER[1] - TOP_HALF_Z - 0.038)
# Each native length the callout prints and its own band, (upper, lower) mm.
# The full thread's band and the drill depth's are symmetric, +/-.005 and
# +/-.002.
TAP_CALLOUT_BANDS: dict[str, tuple[float, tuple[float, float]]] = {
    "hw-threaddepth": (
        STUD_TAP_THREAD_DEPTH,
        (STUD_TAP_THREAD_DEPTH_BAND, -STUD_TAP_THREAD_DEPTH_BAND),
    ),
    "hw-tapdrldepth": (
        STUD_TAP_DRILL_DEPTH,
        (STUD_TAP_DRILL_DEPTH_BAND, -STUD_TAP_DRILL_DEPTH_BAND),
    ),
}
# Both bands print their deviations at three places, ±.005 and ±.002.
TAP_CALLOUT_BAND_PLACES = 3
# swTolType_e: no band of its own, bilateral, symmetric.
_TOL_NONE = 0
_TOL_BILATERAL = 2
_TOL_SYMMETRIC = 4
# The callout's places, the spec's: the full thread and the drill depth at
# three (each its explicit band).  The pilot prints no Ø to place.
TAP_CALLOUT_PLACES = {
    "hw-threaddepth": STUD_TAP_THREAD_DEPTH_PLACES,
    "hw-tapdrldepth": STUD_TAP_DRILL_DEPTH_PLACES,
}
# swDimensionTextParts_e: a hole callout's definitions (5-8: prefix, suffix,
# callout above, callout below) and the writable part each is set through
# (1-4), the draw_mg_output_fixture._reference_thread_depth precedent.  The
# reason row is the below definition, under the thread.
_CALLOUT_DEFINITION_PARTS = {5: 1, 6: 2, 7: 3, 8: 4}
_CALLOUT_BELOW_DEFINITION = 8
# The Hole Wizard's tap-drill Ø variable and the native size run that prints
# it, Ø and all; the drill's name replaces that run, so the sheet reads
# ``#25 DRILL`` where it read ``Ø3.797``.
TAP_DRILL_DIA_VARIABLE = "hw-tapdrldia"
_TAP_DRILL_SIZE_PATTERN = re.compile(
    r"<MOD-DIAM>[ \t]*" + re.escape(f"<{TAP_DRILL_DIA_VARIABLE}>")
)
# The wizard's #25 may carry its inch size's fourth place (0.1495 in =
# 3.7973 mm); the readback holds it to the catalogue 3.797's last place.
_TAP_DRILL_DIA_READBACK_TOL = 0.0005
TAP_DRILL_DEPTH_TOKEN = "<hw-tapdrldepth>"
# The thread's class variable, and the separator before it: the title
# block's thread row (UNC/UNF, class 2A/2B) states the class, so the
# callout prints none (drawing-guidelines.md rule 2 (the title block is the
# general specification); the draw_pd_transgear_arm precedent).  The Hole
# Wizard feature keeps its 2B (sm_knife_mount_spec.STUD_TAP_SPEC).
TAP_THREAD_CLASS_TOKEN = "<hw-threadclass>"
_THREAD_CLASS_PATTERN = re.compile(
    r"[ \t]*(?:-[ \t]*)?" + re.escape(TAP_THREAD_CLASS_TOKEN)
)
# SolidWorks' documented "Drill Angle" callout variable (calloutformat.txt;
# swCalloutVariable_e.swCalloutVariable_Drill_Angle, an angle variable).
TAP_POINT_ANGLE_VARIABLE = "hw-drlang"
TAP_POINT_ANGLE_TOKEN = f"<{TAP_POINT_ANGLE_VARIABLE}>"
_CALLOUT_ANGLE_VARIABLE = 2  # swCalloutVariableType_e.swCalloutVariableType_Angle
_DRILL_ANGLE_VARIABLE = 16  # swCalloutVariable_e.swCalloutVariable_Drill_Angle
# The tap's position frame hangs under its callout block, on its own leader
# to the tap.  The two leaders land on the tap's two lower rims (model x
# side): the callout's on the lower-left, nearer its block, the frame's on
# the lower-right, so the frame's leader, climbing from the frame's right
# end, stays right of the callout's.  Both on the lower-left rim, it crossed
# the callout's 2 mm short of the tip (leader-crosses-leader, farm run
# 20261009T164113078Z).  The frame's top keeps TAP_FRAME_DROP under the
# callout's anchor, where c673e62ee printed it under the five-row block.
# Moved down with the block, it also moves left: its leader leaves a 6.35
# shoulder off the frame's right end (113.5, 163.9 mm at farm run
# 20261027T133857303Z) and climbs to the tap's lower-right rim (117.6,
# 232.2), passing datum B's former bare tag box (x 116.5..123.5, y
# 207.7..214.7) 0.08 mm off its left edge; in farm run 20261027T143609236Z
# it crossed it (leader-crosses-line).  10 mm further left the leader stands
# right of the callout's leader root (102.6) and, at datum B's frame's
# leader shoulder (PIN_FRAME_XY), ~14 mm left of it.
TAP_FRAME_DROP = 0.0156
TAP_FRAME_XY = (
    _sheet_x(-BLK_HALF_X) - 0.034,
    TAP_CALLOUT_XY[1] - TAP_FRAME_DROP,
)
TAP_CALLOUT_RIM_SIDE = -1.0
TAP_FRAME_RIM_SIDE = 1.0
# The bore's composite frame stands above the block's upper-right corner,
# right of the datum-A tag; its BASIC height under A runs down the block's
# right side.  Its top row, measured on farm run 20261027T154115830Z, ran x
# 150.0..191.6 mm, y 166.6..173.6, its leader off the left end at y 170.1;
# the lower segment adds one 7.0 mm row under it, as main's stacked ⊥ frame
# did (farm run 20261024T121140093Z: 14.0 mm, the view then 15 mm higher),
# so its bottom, y 159.6, stands 5.0 mm over the block's top edge (y 154.6)
# and the 20.616 BASIC's top extension line, nothing else within x 150..192
# under it (datum A's tag ends at x 126.5, the right view's Ra 3.2 starts at
# x 214.0).
BORE_FRAME_XY = (FRONT_CENTER[0] + 0.035, _front_y(BLK_TOP) + 0.019)
BORE_BASIC_TEXT_XY = (
    _sheet_x(BLK_HALF_X) + 0.012,
    _front_y(BLK_TOP - BORE_CENTRE_DEPTH / 2.0),
)

RIGHT_HALF_Z = SUPPORT_Z_THICK / 2.0 * SHEET_SCALE[0] / 1000.0
RIGHT_HALF_Y = (BLK_TOP - BLK_BOT) / 2.0 * SHEET_SCALE[0] / 1000.0
# The top seat's Ra 3.2 lands left of the right view's top edge middle, its
# symbol a short leader up and right of it.
TOP_SEAT_FINISH_EDGE_XY = (RIGHT_CENTER[0] - 0.006, RIGHT_CENTER[1] + RIGHT_HALF_Y)
TOP_SEAT_FINISH_XY = (RIGHT_CENTER[0] + 0.004, RIGHT_CENTER[1] + RIGHT_HALF_Y + 0.010)
# The bore's Ra 1.6 lands on the rim 30 deg below the centre line: at 0 deg
# its leader left the rim on the 20.616's centre-height witness line and
# crossed it 0.6 mm out (layout audit leader-crosses-line, run
# 20261010T022724164Z).
BORE_FINISH_RIM_DEG = -30.0
BORE_FINISH_RIM_XY = (
    FRONT_CENTER[0]
    + R_BORE * math.cos(math.radians(BORE_FINISH_RIM_DEG)) * SHEET_SCALE[0] / 1000.0,
    _front_y(BORE_CY)
    + R_BORE * math.sin(math.radians(BORE_FINISH_RIM_DEG)) * SHEET_SCALE[0] / 1000.0,
)


def _set_sheet_precision(display: Any, *, label: str) -> None:
    """Give one sheet-added dimension the places the part's spec owns
    (``DRAWING_REFERENCE_PRECISION``, the draw_fr_top_frame precedent)."""
    places = DRAWING_REFERENCE_PRECISION[label]
    display = _early_bound(display, "IDisplayDimension")
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    applied = int(display.GetPrimaryPrecision2())
    if applied != places:
        raise RuntimeError(
            f"{label}: asked for {places} decimal places, dimension reads {applied}"
        )


def _sheet_dimension_mm(display: Any) -> float:
    """The value a sheet-added dimension measures, mm."""
    native = _early_bound(display, "IDisplayDimension")
    return (
        abs(float(_early_bound(native.GetDimension2(0), "IDimension").SystemValue))
        * 1000.0
    )


def _add_section_axes(
    adapter: Any,
    view: Any,
    axes: tuple[tuple[tuple[float, float, float], tuple[float, float, float]], ...],
) -> list[Any]:
    """Draw owned centerlines (model mm end to end) in ``view``'s own sketch.

    The draw_fr_top_frame ``_add_view_centerlines`` idiom: each end is the
    model point projected to the sheet and taken into the view's sketch
    frame, placed direct to the database (an inferred end snaps onto nearby
    ink) and read back.  Returns each ``ISketchSegment``, in order, for a
    dimension to pick (``"SKETCHSEGMENT"``).
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the view for its owned axes")
    draw.ClearSelection2(True)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    segments = []
    for start, end in axes:
        points = []
        for xyz in (start, end):
            x, y = model_point_in_view(
                adapter,
                view,
                tuple(value / 1000.0 for value in xyz),
                label="owned axis end",
            )
            point = _early_bound(
                utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
            )
            projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
            points.append(tuple(float(value) for value in projected.ArrayData))
        previous_add_to_db = bool(manager.AddToDB)
        manager.AddToDB = True
        try:
            segment = manager.CreateCenterLine(*points[0], *points[1])
        finally:
            manager.AddToDB = previous_add_to_db
        if segment is None:
            raise RuntimeError("failed to create an owned axis")
        line = _early_bound(segment, "ISketchLine")
        for expected, accessor in zip(points, ("GetStartPoint2", "GetEndPoint2")):
            placed = _early_bound(
                adapter._get_attr_or_call(line, accessor), "ISketchPoint"
            )
            actual = [
                float(adapter._get_attr_or_call(placed, axis))
                for axis in ("X", "Y", "Z")
            ]
            drift = max(abs(a - b) for a, b in zip(actual, expected))
            if drift > 1e-9:
                raise RuntimeError(
                    f"owned axis {accessor[3:-6].lower()} point sits "
                    f"{drift * 1000.0:.4g} mm from where it was authored"
                )
        segment = _early_bound(segment, "ISketchSegment")
        segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
        if int(segment.Color) != 0:
            raise RuntimeError("owned axis color did not persist")
        segments.append(segment)
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="section A-A owned axes")
    return segments


def _look_section_along_minus_z(adapter: Any, section: Any) -> None:
    """Point section A-A's sight line along -Z, so it reads as the front view.

    The direction is read from the section's own projection (the
    draw_dt_cone_swing_platform section C-C idiom): with screen-right r and
    screen-up u the sight line is u x r, which runs along -z exactly when
    model +x's sheet-x sign times model +y's sheet-y sign is positive.  Then
    the dowel hole stands right of the tap axis, beside SECTION_KEEP's depth.
    """
    cut = _early_bound(section.GetSection(), "IDrSection")

    def x_direction() -> float:
        base = model_point_in_view(
            adapter, section, (0.0, 0.0, 0.0), label="A-A origin"
        )
        east = model_point_in_view(adapter, section, (0.001, 0.0, 0.0), label="A-A +x")
        up = model_point_in_view(adapter, section, (0.0, 0.001, 0.0), label="A-A +y")
        return (east[0] - base[0]) * (up[1] - base[1])

    if x_direction() < 0.0:
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="section A-A looks along -Z")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("section A-A cut direction did not persist")
    direction = x_direction()
    if not direction > 0.0:
        raise RuntimeError(
            f"section A-A still looks along +Z (sign product {direction})"
        )


def tap_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """The callout's definitions with the pilot named by its drill, the
    native size run ``<MOD-DIAM> <hw-tapdrldia>`` become ``#25 DRILL``; the
    drill's point dimensioned right after the drill depth,
    ``<hw-tapdrldepth> X <hw-drlang>``; the thread's class variable dropped
    with its separator; and the reason row (``TAP_CALLOUT_REASON``) written
    into the empty below definition, under the thread.  Every other
    character is as it was.

    The drill's size run, the drill depth and the thread class must each be
    defined exactly once, the drill angle, the drill's name and the reason
    not yet, and the below definition empty, so the block prints three rows.
    The depth and angle variables stay in the definition, so the printed
    depths and angle are the Hole Wizard feature's own.
    """
    joined = "\n".join(definitions.values())
    if (
        len(_TAP_DRILL_SIZE_PATTERN.findall(joined)) != 1
        or joined.count(TAP_DRILL_DEPTH_TOKEN) != 1
        or joined.count(TAP_THREAD_CLASS_TOKEN) != 1
        or TAP_POINT_ANGLE_TOKEN in joined
        or TAP_DRILL_CALLOUT in joined
        or TAP_CALLOUT_REASON in joined
        or definitions[_CALLOUT_BELOW_DEFINITION].strip()
    ):
        raise RuntimeError(
            f"expected one {_TAP_DRILL_SIZE_PATTERN.pattern!r}, one "
            f"{TAP_DRILL_DEPTH_TOKEN}, one {TAP_THREAD_CLASS_TOKEN}, no "
            f"{TAP_POINT_ANGLE_TOKEN}, {TAP_DRILL_CALLOUT!r} or "
            f"{TAP_CALLOUT_REASON!r} and an empty below definition in the "
            f"knife-hanger tap callout's definitions: {definitions!r}"
        )
    wanted = {
        part: _TAP_DRILL_SIZE_PATTERN.sub(
            TAP_DRILL_CALLOUT, _THREAD_CLASS_PATTERN.sub("", text)
        ).replace(
            TAP_DRILL_DEPTH_TOKEN, f"{TAP_DRILL_DEPTH_TOKEN} X {TAP_POINT_ANGLE_TOKEN}"
        )
        for part, text in definitions.items()
    }
    wanted[_CALLOUT_BELOW_DEFINITION] = TAP_CALLOUT_REASON
    return wanted


def _prove_tap_drill(callout: Any) -> None:
    """The Hole Wizard's own tap-drill Ø, read off the callout before its
    size run is replaced, is the #25 drill the callout names
    (sm_knife_mount_spec.STUD_TAP_DRILL, 3.797): the name stands for the
    feature's drill, not beside it."""
    from win32com.client.dynamic import Dispatch as dynamic_dispatch

    diameters = [
        float(_early_bound(raw, "ICalloutLengthVariable").Length) * 1000.0
        for raw in callout.GetHoleCalloutVariables() or ()
        if str(dynamic_dispatch(raw._oleobj_).VariableName) == TAP_DRILL_DIA_VARIABLE
    ]
    if len(diameters) != 1:
        raise RuntimeError(
            f"knife-hanger tap callout carries {len(diameters)} native "
            f"{TAP_DRILL_DIA_VARIABLE} variables, not one"
        )
    if abs(diameters[0] - STUD_TAP_DIA) > _TAP_DRILL_DIA_READBACK_TOL:
        raise RuntimeError(
            f"knife-hanger tap callout {TAP_DRILL_DIA_VARIABLE} reads "
            f"{diameters[0]:g}, not the {TAP_DRILL_CALLOUT}'s {STUD_TAP_DIA:g} mm"
        )


def _write_tap_callout_definitions(adapter: Any, callout: Any) -> None:
    """Name the drill, write its point and the reason row into the native
    callout, and drop its class.

    The drill's native Ø is proven the #25's first; only the definitions
    that change are written; the readback must hold all four.
    """
    _prove_tap_drill(callout)
    before = {
        part: str(callout.GetText(part) or "") for part in _CALLOUT_DEFINITION_PARTS
    }
    wanted = tap_callout_definitions(before)
    written = {part: text for part, text in wanted.items() if text != before[part]}
    for part, text in written.items():
        callout.SetText(_CALLOUT_DEFINITION_PARTS[part], text)
    after = {
        part: str(callout.GetText(part) or "") for part in _CALLOUT_DEFINITION_PARTS
    }
    if after != wanted:
        raise RuntimeError(
            "knife-hanger tap drill name, point, reason and thread class did not "
            f"persist: wanted {wanted!r}, read {after!r}"
        )
    rebuild_drawing(adapter, label="knife-hanger tap drill name, point and class")
    _telemetry.info(f"knife-hanger tap callout definitions written: {written!r}")


def tap_callout_tolerance(band: tuple[float, float]) -> tuple[int, float, float]:
    """The swTolType_e and (lower, upper) deviations, mm, a callout band
    writes: symmetric when its limits mirror, else bilateral."""
    lower, upper = min(band), max(band)
    kind = _TOL_SYMMETRIC if math.isclose(lower, -upper) else _TOL_BILATERAL
    return kind, lower, upper


def _band_tap_callout(callout: Any) -> None:
    """Author the tap's bands on its hole callout -- the full thread's
    +/-0.13, the drill depth's +/-0.05 -- and prove the drill point its
    118 deg.  The pilot prints its drill's name, no Ø, so the title block's
    DRILLED HOLES row governs it (``_prove_tap_drill`` read its Ø).

    A hole callout variable carries its OWN tolerance (SW 2016+:
    ``ICalloutVariable.ToleranceType``), so each band is set and read back
    on the callout (the draw_sm_summing_lever bracket-tap and
    draw_fr_top_frame hanger-clearance precedents): the full thread's two
    places would claim the .XX row's +/-0.51, a shallowest thread the bolt's
    tip bottoms in, and the title block's band on the drill depth would
    leave under one pitch of drill past the deepest full thread, or break
    the crown web.
    """
    from win32com.client.dynamic import Dispatch as dynamic_dispatch

    required = dict(TAP_CALLOUT_BANDS)
    points: list[Any] = []
    for raw in callout.GetHoleCalloutVariables() or ():
        # Concrete callout interfaces alias the generic metadata DISPIDs.
        variable = dynamic_dispatch(raw._oleobj_)
        variable_name = str(variable.VariableName)
        if variable_name == TAP_POINT_ANGLE_VARIABLE:
            points.append(raw)
            continue
        if variable_name not in required:
            continue
        nominal, band = required.pop(variable_name)
        length = _early_bound(raw, "ICalloutLengthVariable")
        actual = float(length.Length) * 1000.0
        if abs(actual - nominal) > 1e-5:
            raise RuntimeError(
                f"knife-hanger tap callout {variable_name} reads "
                f"{actual:g}, expected {nominal:g} mm"
            )
        kind, lower, upper = tap_callout_tolerance(band)
        variable.ToleranceType = kind
        variable.ToleranceMin = lower / 1000.0
        variable.ToleranceMax = upper / 1000.0
        length.TolerancePrecision = TAP_CALLOUT_BAND_PLACES
        if (
            int(variable.ToleranceType) != kind
            or abs(float(variable.ToleranceMin) * 1000.0 - lower) > 1e-5
            or abs(float(variable.ToleranceMax) * 1000.0 - upper) > 1e-5
            or int(length.TolerancePrecision) != TAP_CALLOUT_BAND_PLACES
        ):
            raise RuntimeError(
                f"knife-hanger tap callout band for {variable_name} did not "
                f"persist: wanted swTolType_e {kind}, deviations {(lower, upper)} mm at "
                f"{TAP_CALLOUT_BAND_PLACES} places"
            )
    if required:
        raise RuntimeError(f"knife-hanger tap callout omits native lengths: {required}")
    if len(points) != 1:
        raise RuntimeError(
            f"knife-hanger tap callout carries {len(points)} native drill points, not one"
        )
    _prove_tap_point(points[0])


def _prove_tap_point(raw: Any) -> None:
    """The callout's drill point is SolidWorks' drill-angle variable reading
    the feature's 118 deg, printed in whole degrees with no band of its own,
    so the title block's angular tolerance governs it (the crown web charges
    its 117 deg limit, sm_knife_mount_spec.STUD_TAP_POINT_ANGLE_MIN_DEG)."""
    from win32com.client.dynamic import Dispatch as dynamic_dispatch

    variable = dynamic_dispatch(raw._oleobj_)
    kinds = (int(variable.Type), int(variable.VariableType))
    if kinds != (_CALLOUT_ANGLE_VARIABLE, _DRILL_ANGLE_VARIABLE):
        raise RuntimeError(
            f"knife-hanger tap callout {TAP_POINT_ANGLE_VARIABLE} is type {kinds}, "
            f"not the drill angle {(_CALLOUT_ANGLE_VARIABLE, _DRILL_ANGLE_VARIABLE)}"
        )
    angle = _early_bound(raw, "ICalloutAngleVariable")
    degrees = math.degrees(float(angle.Angle))
    if abs(degrees - STUD_TAP_POINT_ANGLE_DEG) > 1e-5:
        raise RuntimeError(
            f"knife-hanger tap drill point reads {degrees:g} deg, "
            f"expected {STUD_TAP_POINT_ANGLE_DEG:g}"
        )
    variable.ToleranceType = _TOL_NONE
    angle.Precision = STUD_TAP_POINT_ANGLE_PLACES
    if (
        int(variable.ToleranceType) != _TOL_NONE
        or int(angle.Precision) != STUD_TAP_POINT_ANGLE_PLACES
    ):
        raise RuntimeError(
            "knife-hanger tap drill point did not persist unbanded at "
            f"{STUD_TAP_POINT_ANGLE_PLACES} places"
        )


# Section A-A cuts the tap on its axis: SolidWorks' cosmetic-thread
# annotation printed its major Ø there dashed, as a hidden thread (blind
# machinist review, 2026-10-09).  It moves onto a visible thin continuous
# layer, the section's own thread line.  The front and right views are
# drawn hidden-lines-removed, which does not touch the annotation (the
# draw_fr_top_frame._hide_cosmetic_threads measurement), so their threads,
# hidden in both, move onto an invisible layer.
SECTION_THREAD_LAYER = "TAP-THREAD-SECTION"
HIDDEN_THREAD_LAYER = "TAP-THREAD-HIDDEN"
_COSMETIC_THREAD_ANNOTATION = 1  # swAnnotationType_e.swCosmeticThread


def _layer_cosmetic_threads(
    adapter: Any, view: Any, *, layer_name: str, visible: bool, label: str
) -> int:
    """Move one view's cosmetic-thread annotations onto ``layer_name``.

    The layer is created thin and continuous (``ILayerMgr::AddLayer``),
    shown or hidden by ``visible``, the draw_fr_top_frame precedent: both the
    layer state and every annotation's layer are read back.  Returns the
    count moved; the caller decides whether none is a failure.
    """
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(layer_name)
    if layer is None:
        # COLORREF black, swLineCONTINUOUS (0), swLW_THIN (0).
        if int(manager.AddLayer(layer_name, label, 0, 0, 0)) != 1:
            raise RuntimeError(f"{label}: failed to add layer {layer_name}")
        layer = manager.GetLayer(layer_name)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = visible
    if bool(layer.Visible) != visible or (not visible and bool(layer.Printable)):
        raise RuntimeError(
            f"{label}: layer {layer_name} reads visible={layer.Visible!r}, "
            f"printable={layer.Printable!r}; wanted visible={visible}"
        )
    if visible and (int(layer.Style) != 0 or int(layer.Width) != 0):
        raise RuntimeError(
            f"{label}: layer {layer_name} reads style {layer.Style!r}, width "
            f"{layer.Width!r}; wanted thin continuous"
        )
    moved = 0
    for raw_annotation in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != _COSMETIC_THREAD_ANNOTATION:
            continue
        annotation.Layer = layer_name
        if str(annotation.Layer or "") != layer_name:
            raise RuntimeError(f"{label}: a cosmetic thread refused layer {layer_name}")
        moved += 1
    rebuild_drawing(adapter, label=f"cosmetic threads to {layer_name}")
    _telemetry.info(f"{label}: moved {moved} cosmetic thread(s) to {layer_name}")
    return moved


def _tap_lower_rim(adapter: Any, top: Any, x_side: float) -> tuple[float, float]:
    """The #10-24 tap's drill rim at 45 deg on model ``x_side``, below its
    centre in the top view: picked on whichever side of the cutting line
    model -Z/+Z projects below it."""
    rim_mm = STUD_TAP_DIA / 2.0 / math.sqrt(2.0)
    return min(
        (
            model_point_in_view(
                adapter,
                top,
                (x_side * rim_mm / 1000.0, BLK_TOP / 1000.0, side * rim_mm / 1000.0),
                label=f"knife-hanger tap rim x{x_side:+.0f} z{side:+.0f}",
            )
            for side in (1.0, -1.0)
        ),
        key=lambda point: point[1],
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open knife-mount source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=UNIT,
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Knife-Mount Bearing Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "knife mount; hardened steel bearing block; knife-edge bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # Section A-A cuts the top view on z = 0 through the tap and dowel axes:
    # the blind dowel hole's floor is hidden in the front view (drawing-guidelines.md rule 9 (show internal shape in solid lines)),
    # so its depth is dimensioned on the cut.
    section_ends = [
        model_point_in_view(
            adapter,
            top,
            tuple(value / 1000.0 for value in point),
            label=f"section A-A line end {index}",
        )
        for index, point in enumerate(SECTION_LINE_MODEL_MM)
    ]
    section = create_section_view(
        adapter,
        top,
        line_start=section_ends[0],
        line_end=section_ends[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(2, 1),
        label="dowel and tap axis section",
    )
    _look_section_along_minus_z(adapter, section)
    set_hidden_lines_removed(adapter, section)
    # Every view is drawn hidden-lines-removed (2026-10-10 ruling): the top
    # view's dashed cross-bore restated the front view's bore, and the front
    # view's dashed tap and dowel holes restated their callouts and section
    # A-A, which cuts both on their axes (machinist reviews r3/r4); the right
    # view's dashed tap, dowel and bore restated all three (2026-10-09).
    for view in (iso, right, front, top):
        set_hidden_lines_removed(adapter, view)

    # The dowel hole's floor depth (section A-A) is imported before its
    # profile's Ø and station (top), the MHA-PD-18 section-before-end order.
    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            section,
            keep=SECTION_KEEP,
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            top,
            keep=TOP_KEEP,
            view_label="top",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Places and the ream band are authored on the part; the sheet only proves
    # the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # The depth's value and two rows park on a jog right of its witness
    # lines' ends (PIN_DEPTH_OFFSET_XY).
    offset_dimension_text(adapter, annotations, {"PinHoleDepth": PIN_DEPTH_OFFSET_XY})
    if not _layer_cosmetic_threads(
        adapter,
        section,
        layer_name=SECTION_THREAD_LAYER,
        visible=True,
        label="section A-A tap thread",
    ):
        raise RuntimeError("section A-A carries no cosmetic thread; the tap moved?")
    for view, view_label in ((front, "front"), (right, "right")):
        _layer_cosmetic_threads(
            adapter,
            view,
            layer_name=HIDDEN_THREAD_LAYER,
            visible=False,
            label=f"{view_label} view hidden tap thread",
        )
    # SolidWorks pins its own raw "#10-24 Tapped Hole" note to a view that
    # imports from the tapped part (the dda9a33a8 render put it on the top
    # view, through the dowel callout).  The tap is stated once, on its hole
    # callout below (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)), so every such note goes.  Which views receive
    # one is SolidWorks' choice (draw_fr_top_frame._auto_tapped_hole_notes),
    # so the count is logged, not gated; finalize_drawing then proves none is
    # left.
    removed_tap_notes = remove_notes_matching(adapter, TAPPED_HOLE_NOTE)
    _telemetry.info(f"removed {removed_tap_notes} automatic tapped-hole note(s)")
    tap_rim = _tap_lower_rim(adapter, top, TAP_CALLOUT_RIM_SIDE)
    tap_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=tap_rim,
        callout_xy=TAP_CALLOUT_XY,
        label="knife-hanger bolt bottoming tap",
    )
    _write_tap_callout_definitions(adapter, tap_callout)
    _band_tap_callout(tap_callout)
    set_hole_callout_precision(
        tap_callout,
        TAP_CALLOUT_PLACES,
        label="knife-hanger tap depths",
    )
    # One arrow on the bore's near (upper-left) rim, its leader short from
    # the text on the left; native, the Ø line ran rim to rim through the
    # centre and across the view to a shoulder left of it.
    bore_dia = [a for a in annotations if dimension_name(adapter, a) == "BoreDia"]
    if len(bore_dia) != 1:
        raise RuntimeError(f"expected one BoreDia dimension, found {len(bore_dia)}")
    set_near_side_diameter(bore_dia[0], "knife-bore diameter")
    # The template centre-marks every hole as each view is placed (the top
    # view's two holes and section A-A carry marks no call asked for), so an
    # explicit AutoInsertCenterMarks2 on the front view printed the bore's
    # mark twice (DetailItem346/352 at one point; #913).  Prove the one mark.
    marks = (
        _early_bound(front, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )
    if len(marks) != 1:
        raise RuntimeError(f"expected one knife-bore centre mark, found {len(marks)}")

    # Block depth (14.0, .X like the width and height): dimension the right
    # view's flat front/back faces.
    depth = add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - RIGHT_HALF_Z, RIGHT_CENTER[1]),
        p1=(RIGHT_CENTER[0] + RIGHT_HALF_Z, RIGHT_CENTER[1]),
        text_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] - RIGHT_HALF_Y - 0.014),
        label="block-depth overall",
    )
    _set_sheet_precision(depth, label="block-depth overall")

    # Datum B (the round slip hole) on the block's outside faces at general
    # tolerance (blind machinist review, 2026-10-09): across X, its axis from
    # the +X side face; across Z, from the front face.  Each face is picked
    # off the cutting line, the hole on its upper outer rim at 45 deg.
    pin_rim_mm = PIN_HOLE_DIA / 2.0 / math.sqrt(2.0)
    b_pick = max(
        (
            model_point_in_view(
                adapter,
                top,
                (
                    (PIN_HOLE_X + pin_rim_mm) / 1000.0,
                    BLK_TOP / 1000.0,
                    z_side * pin_rim_mm / 1000.0,
                ),
                label=f"datum B hole rim z{z_side:+.0f}",
            )
            for z_side in (1.0, -1.0)
        ),
        key=lambda point: point[1],
    )
    side_face = model_point_in_view(
        adapter,
        top,
        (BLK_HALF_X / 1000.0, BLK_TOP / 1000.0, SUPPORT_Z_THICK / 4.0 / 1000.0),
        label="+X side face",
    )
    side = add_edge_dimension(
        adapter,
        top,
        p0=side_face,
        p1=b_pick,
        text_xy=PIN_SIDE_TEXT_XY,
        label="dowel hole from side face",
        orientation="horizontal",
    )
    set_arc_endpoints_to_center(adapter, side, label="dowel hole from side face")
    if abs(_sheet_dimension_mm(side) - PIN_HOLE_SIDE_DISTANCE) > 1e-5:
        raise RuntimeError(
            f"datum B's hole measures {_sheet_dimension_mm(side):g} from the side "
            f"face, expected {PIN_HOLE_SIDE_DISTANCE:g} mm"
        )
    _set_sheet_precision(side, label="dowel hole from side face")
    front_face = model_point_in_view(
        adapter,
        top,
        (
            (BLK_HALF_X + PIN_HOLE_X) / 2.0 / 1000.0,
            BLK_TOP / 1000.0,
            SUPPORT_Z_THICK / 2.0 / 1000.0,
        ),
        label="front face",
    )
    row_y = model_point_in_view(
        adapter,
        top,
        (PIN_HOLE_X / 1000.0, BLK_TOP / 1000.0, 0.0),
        label="datum B axis",
    )[1]
    if not front_face[1] < row_y:
        raise RuntimeError(
            f"the front face projects at sheet y {front_face[1]:g}, not below the "
            f"hole row ({row_y:g}): ROW_FACE_TEXT_XY assumes the top view's lower edge"
        )
    row = add_edge_dimension(
        adapter,
        top,
        p0=front_face,
        p1=b_pick,
        text_xy=ROW_FACE_TEXT_XY,
        label="hole row from front face",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(adapter, row, label="hole row from front face")
    if abs(_sheet_dimension_mm(row) - HOLE_ROW_FACE_DISTANCE) > 1e-5:
        raise RuntimeError(
            f"datum B's hole measures {_sheet_dimension_mm(row):g} from the front "
            f"face, expected {HOLE_ROW_FACE_DISTANCE:g} mm"
        )
    _set_sheet_precision(row, label="hole row from front face")

    # The tap axis BASIC from datum B's axis, in section A-A between owned
    # axes (TAP_STATION_TEXT_XY); the tap's axis runs on through the bore's
    # centre, so the one BASIC locates both from B.
    tap_axis_x = model_point_in_view(
        adapter, section, (0.0, BLK_TOP / 1000.0, 0.0), label="A-A tap axis"
    )[0]
    pin_axis_x = model_point_in_view(
        adapter,
        section,
        (PIN_HOLE_X / 1000.0, BLK_TOP / 1000.0, 0.0),
        label="A-A datum B axis",
    )[0]
    if not pin_axis_x > tap_axis_x:
        raise RuntimeError(
            f"section A-A draws datum B's axis at sheet x {pin_axis_x:g}, not right "
            f"of the tap axis ({tap_axis_x:g}): TAP_STATION_OFFSET_XY assumes +X right"
        )
    axis_top = BLK_TOP + SECTION_AXIS_OVERRUN_MM
    tap_axis, pin_axis = _add_section_axes(
        adapter,
        section,
        (
            ((0.0, axis_top, 0.0), (0.0, BORE_CY - R_BORE - SECTION_AXIS_TAIL_MM, 0.0)),
            (
                (PIN_HOLE_X, axis_top, 0.0),
                (PIN_HOLE_X, BLK_TOP - PIN_HOLE_DEPTH - SECTION_AXIS_TAIL_MM, 0.0),
            ),
        ),
    )
    station_picks = [
        model_point_in_view(
            adapter,
            section,
            (x / 1000.0, (BLK_TOP + SECTION_AXIS_OVERRUN_MM / 2.0) / 1000.0, 0.0),
            label=f"A-A axis pick x{x:+g}",
        )
        for x in (0.0, PIN_HOLE_X)
    ]
    station = add_edge_dimension(
        adapter,
        section,
        p0=station_picks[0],
        p1=station_picks[1],
        text_xy=TAP_STATION_TEXT_XY,
        label="dowel hole from tap axis",
        orientation="horizontal",
        entity_types=("SKETCHSEGMENT", "SKETCHSEGMENT"),
        entities=(tap_axis, pin_axis),
    )
    if abs(_sheet_dimension_mm(station) - PIN_HOLE_X) > 1e-5:
        raise RuntimeError(
            f"datum B's axis measures {_sheet_dimension_mm(station):g} from the "
            f"tap axis, expected {PIN_HOLE_X:g} mm"
        )
    _set_sheet_precision(station, label="dowel hole from tap axis")
    station_annotation = _early_bound(
        _early_bound(station, "IDisplayDimension").GetAnnotation(), "IAnnotation"
    )
    offset_dimension_text(
        adapter,
        [station_annotation],
        {dimension_name(adapter, station_annotation): TAP_STATION_OFFSET_XY},
    )
    set_basic_dimension(adapter, station, label="dowel hole from tap axis")

    # Datum A = the block top seat (clamped to the top-frame casting underside;
    # carries the #10-24 knife-hanger-bolt tap and the MHA-SM-VN-53 slip hole
    # and slot), tagged DATUM_A_X right of the view's centre: on the centre,
    # the tap frame's leader, climbing past at x ~114 mm from the lowered
    # frame to the tap's rim, ran through its box (layout audit, farm run
    # 20261027T030041319Z).  Ra 1.6 (MACHINED_UM) on the bore's working upper
    # wall, tagged on the bore rim (a real circular edge).
    add_datum_feature(
        adapter,
        front,
        edge_xy=(DATUM_A_X, _front_y(BLK_TOP)),
        symbol_xy=(DATUM_A_X, _front_y(BLK_TOP) + 0.018),
        datum="A",
        label="block top seat",
    )
    # Datum B = the round slip hole (owner ruling 2026-10-24, T+H3), its axis
    # ⊥Ø0.015 to A (owner ruling 2026-10-27, #2016) on a frame whose leader
    # lands on the hole's lower-left rim at PIN_FRAME_RIM_DEG, clear of the
    # Ø's leader; B's symbol hangs on that frame (add_frame_datum_feature).
    # No other edge stands within the pick there: the centre mark is an
    # annotation, not an edge.
    b_frame_angle = math.radians(PIN_FRAME_RIM_DEG)
    pin_hole_r_mm = PIN_HOLE_DIA / 2.0
    b_frame_rim = min(
        (
            model_point_in_view(
                adapter,
                top,
                (
                    (PIN_HOLE_X + pin_hole_r_mm * math.cos(b_frame_angle)) / 1000.0,
                    BLK_TOP / 1000.0,
                    z_side * pin_hole_r_mm * abs(math.sin(b_frame_angle)) / 1000.0,
                ),
                label=f"datum B rim z{z_side:+.0f}",
            )
            for z_side in (1.0, -1.0)
        ),
        key=lambda point: point[1],
    )
    pin_frame = add_feature_control_frame(
        adapter,
        top,
        edge_xy=b_frame_rim,
        leader_attach_xy=b_frame_rim,
        frame_xy=PIN_FRAME_XY,
        characteristic="perpendicularity",
        tolerance=GEOMETRIC_TOLERANCES_IN["dowel hole perpendicularity"],
        datums=("A",),
        diameter=True,
        label="dowel hole perpendicularity",
    )
    add_frame_datum_feature(
        adapter,
        top,
        pin_frame,
        datum="B",
        symbol_xy=PIN_DATUM_B_XY,
        label="datum B slip hole",
    )
    # Datum C = the slot's width, ⌖0.05 to A|B (the crossbar's former slot
    # frame, moved with the slot) and, stacked under it, ⊥0.015 to A (owner
    # ruling 2026-10-27, #2016; a width: no Ø), its symbol on that stack
    # (add_frame_datum_feature: a frame's datum identifier read back and
    # printed nothing, run 20261009T171439353Z).  The leader lands on the
    # slot's front wall SLOT_FRAME_WALL_X along the line, inside the -X face.
    slot_wall = min(
        (
            model_point_in_view(
                adapter,
                top,
                (
                    SLOT_FRAME_WALL_X / 1000.0,
                    BLK_TOP / 1000.0,
                    z_side * SLOT_WIDTH / 2.0 / 1000.0,
                ),
                label=f"dowel slot wall z{z_side:+.0f}",
            )
            for z_side in (1.0, -1.0)
        ),
        key=lambda point: point[1],
    )
    slot_frame = add_feature_control_frame(
        adapter,
        top,
        edge_xy=slot_wall,
        leader_attach_xy=slot_wall,
        frame_xy=SLOT_FRAME_XY,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_IN["dowel slot position"],
        datums=("A", "B"),
        lower_frame=(
            "perpendicularity",
            GEOMETRIC_TOLERANCES_IN["dowel slot perpendicularity"],
            ("A",),
        ),
        label="dowel slot position",
    )
    add_frame_datum_feature(
        adapter,
        top,
        slot_frame,
        datum="C",
        symbol_xy=SLOT_DATUM_C_XY,
        label="dowel slot datum C",
    )
    # The bore: composite position to A|B|C (owner ruling 2026-10-27, #2016),
    # Ø0.20 locating it over Ø0.05 holding its axis parallel to A and clocked
    # to the B-C line, the refinement the rock budget charges as the far
    # end's offset (sm_knife_mount_spec).  Its centre is BASIC under A;
    # across, BASIC 7.632 from B's axis.
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], _front_y(BORE_CY) + R_BORE * SHEET_SCALE[0] / 1000.0),
        frame_xy=BORE_FRAME_XY,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_IN["knife-bore position"],
        datums=("A", "B", "C"),
        diameter=True,
        lower_frame=(
            "position",
            GEOMETRIC_TOLERANCES_IN["knife-bore orientation"],
            ("A", "B", "C"),
        ),
        composite=True,
        label="knife-bore position",
    )
    bore_basic = add_edge_dimension(
        adapter,
        front,
        p0=(_sheet_x(0.6 * BLK_HALF_X), _front_y(BLK_TOP)),
        p1=(_sheet_x(R_BORE), _front_y(BORE_CY)),
        text_xy=BORE_BASIC_TEXT_XY,
        label="knife-bore centre from top seat",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(
        adapter, bore_basic, label="knife-bore centre from top seat"
    )
    if abs(_sheet_dimension_mm(bore_basic) - BORE_CENTRE_DEPTH) > 1e-5:
        raise RuntimeError(
            f"knife-bore centre measures {_sheet_dimension_mm(bore_basic):g} under "
            f"the top seat, expected {BORE_CENTRE_DEPTH:g} mm"
        )
    _set_sheet_precision(bore_basic, label="knife-bore centre from top seat")
    set_basic_dimension(adapter, bore_basic, label="knife-bore centre from top seat")
    # The #10-24 tap: Ø0.14 to A|B|C, the bolt axis the crossbar's clearance
    # hole floats round (build_sm_summing_assembly's knife-hanger stack).
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=_tap_lower_rim(adapter, top, TAP_FRAME_RIM_SIDE),
        frame_xy=TAP_FRAME_XY,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_IN["knife-hanger tap position"],
        datums=("A", "B", "C"),
        diameter=True,
        label="knife-hanger tap position",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=BORE_FINISH_RIM_XY,
        symbol_xy=(FRONT_CENTER[0] + 0.052, _front_y(BORE_CY) - 0.020),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_bore"),
        label="knife bore finish",
        # The fleet's finish height (62 of 75 finishes): the document default
        # is the dimension height, and Ra 1.6 printed twice the sheet's notes.
        char_height=0.0025,
    )
    # The top seat, datum A (machinist review r3, 2026-10-10: the dowelled
    # seat the screw clamps had no finish).  Tagged on the right view's top
    # edge, the open band over that bare view, clear of the front view's
    # datum-A tag and the bore and tap frames.
    add_surface_finish(
        adapter,
        right,
        edge_xy=TOP_SEAT_FINISH_EDGE_XY,
        symbol_xy=TOP_SEAT_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "top_seat"),
        label="top seat finish",
        char_height=0.0025,
    )
    # Every datum a frame names is printed (A on the front view, B on its
    # hole's ⊥ frame, C on the slot's stack), so no frame references a datum
    # the sheet never names.
    assert_frame_datums_defined(
        (front, right, top, section), label="sm-knife-mount frame datums"
    )

    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.175)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Knife-Mount Bearing Block Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=(TAPPED_HOLE_NOTE,),
        expected_redundant_notes=0,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
