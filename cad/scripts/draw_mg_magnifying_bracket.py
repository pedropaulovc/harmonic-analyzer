r"""Create the curated machinist drawing for the magnifying-lever bracket.

The bracket is the black fitting that affixes the Ø6 magnifying lever
(MHA-MG-003) to the summing plate: an extruded COLLAR tube (Ø12 OD, 10 long
about local X) whose bore is the lever's PRESS seat, a rectangular ARM
cantilevering +Z, and a mounting FLANGE whose +Z face butts the summing-plate
front face.  One third-angle set (blind machinist review, mreview09):

- FRONT (the part's ``*Top`` named view: +X right, +Z DOWN): the plan
  rectangles' marked dimensions -- the arm's width, the flange's width and
  thickness -- the arm-to-flange inside corners' single MAX radius, the
  collar's length (naming the lever's press zone it matches) above the
  collar it measures, and the letter arrow naming VIEW A.
- BOTTOM (``*Front``, under the front view, looking at the mounting face,
  captioned VIEW A): the flange's height, the two mounting holes'
  coordinates from the flange's west end and lower face, the native plain
  clearance-hole callout (naming the MHA-SM-003 summing lever's tapped holes
  the banded pattern matches) and, from the part's blanked
  ``ArmFootprint`` witness, the arm's thickness and its lower face from the
  flange's hole-datum edge (both controlling), beside the arm's end face
  the view draws face-on inside the flange.  Together with ``ArmBelowAxis``
  in the side view, ``FootprintOffset`` locates the bore axis without a
  duplicate flange-to-axis reference.
- RIGHT SIDE (``*Right`` TURNED so model +Z runs down the sheet and pinned by
  projection at the front view's origin height): the collar end-on with its
  OD and its bore -- a reference nominal under the matched-fit callout --
  (near-side single-arrow leaders), and, from the part's
  blanked ``ArmSection`` witness, the arm's lower face from the bore axis
  (controlling) and the bore axis' ONE toleranced chain along Z -- the
  flange's mounting face from the axis, the arm's end past that face --
  with the arm's end from the axis printed as that chain's parenthesised
  sum, a drawing-native reference dimension.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_magnifying_bracket.py mg-magnifying-bracket
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Mapping, Sequence
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, dimension_name, place_view

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
from _drawing_annotation_extent import move_annotation
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    set_arc_endpoints_to_center,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import ViewEdge, ViewEdges, scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions as curate_hidden_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_leaders import (
    Segment,
    assert_leaders_clear,
    dimension_segments,
    dimension_text_points,
    distance_to_box,
    distance_to_line,
    segments_cross,
    set_near_side_diameter,
)
from _drawing_leader_notes import add_leader_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from magnifying_bracket_joint_layout import (
    BRACKET_HOLE_POINTS,
    CLEARANCE_DIA,
    SIDE_PLATE_Z,
)
from build_mg_magnifying_bracket import ARM_HALF_X, ARM_Y, ARM_Z, COLLAR_OD
from mg_lever_press_fit_geom import COLLAR_BORE_DIA
from mg_magnifying_bracket_spec import (
    COLLAR_BORE_CALLOUT,
    COLLAR_LENGTH_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_REFERENCE_PRECISION,
    FLANGE_DEPTH_CALLOUT,
)
from mg_magnifying_lever_geom import COLLAR_HALF_LEN

SPEC = DRAWINGS_BY_NAME["mg_magnifying_bracket"]
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
# The sheet's FRONT view is the part's *Top named view (viewer +Y): sheet
# x = 98 + X, y = 230.15 - Z mm.  The BOTTOM view (*Front, viewer +Z) sits
# under it in third angle: its x = 98 + X too.  The *Right named view is
# placed, then turned and pinned into projection by _project_side_view;
# SIDE_CENTER only drops it nearby.
# The A1 pose (#1559) put the collar 45.21 mm further from the mounting face
# (arm end Z 58.30 -> 103.51).  The layout below is the retry09..retry15
# native-audited sheet translated, not re-invented: everything tied to the
# collar (the collar's diameters and length, the in-span stations from the
# bore axis) rose 24 mm with the bore axis (206.15 -> 230.15 mm), everything
# tied to the arm's end and the flange (the arm width, the flange's plan
# dimensions, the side view's stacks under the arm, the whole bottom view
# with its coordinates, caption and hole callout) fell 21.21 mm, and
# the front and bottom views with their dimensions moved 36 mm left (x 134
# -> 98 + X) so the hole callout, carried down with the bottom view,
# stays left of the title block (x > 216 mm under y 66 mm).  The isometric,
# now 1:2, moves up right.
FRONT_ORIGIN_Y = 0.23015
# The collar's Z -6 and the arm's end centre the front view's outline
# (ARM_Z[1] - 6) / 2 mm below the origin.  The build measures the origin in
# both views and pins the side view to the FRONT view's reading; these
# constants only place the texts.
FRONT_CENTER = (0.079, FRONT_ORIGIN_Y - (ARM_Z[1] - COLLAR_OD / 2.0) / 2000.0)
BOTTOM_CENTER = (0.079, 0.08879)
SIDE_CENTER = (0.228, FRONT_CENTER[1])
# At 1:1 the A1 part's isometric (~137 x 92 mm) would crowd the side view's
# stacks and the sheet's right edge; at 1:2 (~69 x 46 mm) it spans x ~316..
# 384 mm, y ~137..183 mm, right of every side-view row (x <= 303 mm).
ISO_CENTER = (0.350, 0.160)
ISO_SCALE = (1, 2)
ISO_NOTE_XY = (0.316, 0.125)
# Where the side view's bore axis prints (x).
SIDE_AXIS_X = 0.228

# The three plan dimensions ride the FRONT view (both extruded rectangles lie
# on the part's Top plane), as does the collar's mid-plane extrude length
# (along X).  +Z runs DOWN the front view (the collar, Z -6..6, sits at its
# top, y 224.15..236.15 mm; the arm's end, Z 103.51, at its bottom, y 126.64
# mm).  The collar's length reads above the collar, its witnesses 4 mm long;
# retry09 printed its three rows (centred on the requested x, the line at
# the lowest row's baseline 3.55 mm over the collar) over x ~98..140 mm, y
# ~239.7..254.3 mm with the value requested at y 248 mm.  The callout now
# names the lever's press zone the length matches on a third callout row
# (27 characters, ~74.7 mm at retry09's 41.5 mm for 15), so the value rose
# one row pitch; r3b printed the tolerance stack's "0.00" upper limit with its
# top at ~266.4 mm, 0.3 mm under the drawable top (266.7 mm), the rows over
# x 82.9..155.1 mm and the line at the lowest row's baseline, y 240.7 mm.
# The block now sits 1.5 mm lower: the "0.00" top ~264.9 mm (1.8 mm under
# the drawable top), the line at ~239.2 mm, 3.05 mm over the collar's top
# (y 236.15 mm), its witnesses from 237.15 mm.
# A HORIZONTAL dimension's rows requested beyond its span print centred on
# the requested x, and its dimension line runs on under the lowest row to that
# row's far end (retry09 native audit).  The arm width therefore reads BELOW
# the arm's end (y 126.64 mm), between the aligned front and bottom views,
# hung left of its span (x 93..103 mm): rows over x ~64..90 mm, y 111.8..
# 121.3 mm, the dimension line at y 111.2 mm and its witnesses dropping
# through air from the arm's end, 11 mm over the bottom view's top (y 100.7
# mm) and clear of the flange depth's column at x 53 mm.  The flange's two
# plan dimensions keep their retry09 places from the flange (the width's
# value row ~62 mm over the mounting face, y 129.75 mm), left of the arm;
# the flange depth's block sits a text height plus under the flange width's,
# its rows centred on x ~36.5 mm with their near end on its column (x 53
# mm): the value (y 178.79 mm, as r3b), then three rows
# (FLANGE_DEPTH_CALLOUT, widest "FLANGE DEPTH", 33.1 mm over x 19.9..53 mm)
# naming the MHA-VN-050 screws' grip the three places hold, the lowest at y
# ~162.1 mm: left of the flange width's west witness (x 55 mm) and the arm
# root's block (x >= 59.6 mm).  A block's value row prints (rows - 2) half
# pitches over the requested y (r3b: 2 rows +0, 3 rows +2.78 mm, 4 rows
# +5.56 mm), so the four-row block is requested one pitch under its value.
# The arm-to-flange inside corner at the arm's west face (X -5, the flange's
# front face Z 97.22: sheet (93, 132.93) mm) prints as an arc; its MAX
# radius reads up-left of it, its block (two 7..8-character label rows, ~21
# mm) centred on x 72 mm over y ~138..154 mm: right of the flange width's
# west witness (x 55 mm), left of the arm (x 93 mm), over the flange's front
# face (y 132.93 mm) and under the flange width's line (y ~189 mm).
# The arm's length from its buried start (Z 4, inside the collar) is not
# dimensioned: the arm's end is located from the bore axis in the side view.
FRONT_KEEP = {
    "ArmWidth": (0.077, 0.11679),
    "FlangeWidth": (0.068, 0.19479),
    "FlangeDepth": (0.053, 0.17879 - 0.00556),
    "CollarLen": (0.119, 0.248 + 0.00556 - 0.0015),
    "ArmRootR": (0.072, 0.150),
}
# VIEW A's letter arrow on the front view: the bottom view looks up the
# sheet (+Z toward -Z) at the mounting face, whose edge prints at y 129.75
# mm (Z 100.40).  The arrow's tip sits on that edge at x 58 mm (X -40, west
# of both holes), its 5 mm letter under it, upper-left at (56.2, 124.25)
# mm: x 56.2..59.8 mm, y ~119.25..124.25 mm, 3.2 mm right of the flange
# depth's column (x 53 mm) and 4.2 mm left of the arm width's rows (x >= 64
# mm), over the bottom view (its outline's top y ~100.7 mm).
# VIEW_A_ARROW is (letter upper-left, tip).
VIEW_LETTER_HEIGHT = 0.005
_VIEW_A_TIP = (0.058, FRONT_ORIGIN_Y - SIDE_PLATE_Z[1] / 1000.0)
VIEW_A_ARROW = (
    (_VIEW_A_TIP[0] - 0.36 * VIEW_LETTER_HEIGHT, _VIEW_A_TIP[1] - 0.0055),
    _VIEW_A_TIP,
)
# The bottom view's numbers below are the retry09..retry15 audits' in the
# pre-A1 frame; the A1 sheet carries this whole group (views, dimensions,
# caption, callout) 36 mm left and 21.21 mm down: sheet x = 98 + X, y =
# 88.79 + Y mm, so subtract (36, 21.21) mm from every coordinate quoted.
# East of the bottom view (x = 134 + X, y = 110 + Y mm: the flange's east end
# at x 139 mm, its hole-datum face at y 103.65 mm, its top at 116.35 mm; the
# arm's end face, drawn face-on inside the flange, over x 129..139 mm, y
# 107..114.5 mm) three VERTICAL dimensions stand in columns, every one with
# its arrows OUTSIDE (_set_arrow_sides): a vertical dimension with outside
# arrows draws NO line between its witnesses (retry10 ink: the 12.70's
# in-span text and the 6.35's hung row both printed only their outside
# tails, the run under the hung row and the witnesses), so a foreign
# witness may pass through its span -- only a tail, a run or a shoulder
# can be crossed, and only text within 2 mm of a foreign witness is
# reported (extension-near-text; own witnesses are not).  Each outside
# arrow's tail runs 6.35 mm past its witness; the arrowhead is 3.556 mm
# long.  The arm's thickness (7.50) has a tail across the hole-datum face's
# level (y 100.65..107 mm) and one across the flange top's (114.5..120.85
# mm), so it stands OUTERMOST, where no witness reaches; the other two are
# hung, their rows outside their spans, so the thickness' witnesses (y 107
# and 114.5 mm) cross their empty spans and nothing else:
#   - the arm's lower face from the hole-datum face (FootprintOffset, 3.35,
#     witnesses y 103.65 and 107 mm from the flange's and the arm's east
#     corners, x 140..151 mm): column x 150 mm, its row hung BELOW (a lone
#     row hung off a short vertical span prints beside its column on a
#     shoulder 2.78 mm under the requested y, on whichever hand SolidWorks
#     takes: the bottom view's 6.35, retry09/10): " 3.35 " (12.2 mm) at y
#     97.1..100.6 mm over x 137.8..162.2 mm at most; the 0.4 mm lower drop
#     clears retry15's flange-height witness by 2.03 mm on its native text;
#     the upper tail y 107..113.35 mm, 1.15 mm short of the thickness'
#     upper witness; the hole callout's leader passes x <= 132.5 mm
#     at the row's height, 5 mm left of its widest reach;
#   - the flange's height (FlangeHeight, 12.70, witnesses y 103.65 mm --
#     over the offset's, collinear -- and 116.35 mm, x 140..167 mm): column
#     x 166 mm, its row hung ABOVE: " 12.70 " (14.2 mm) at y 123.5..127 mm
#     over x 151.8..180.2 mm at most, 1.6 mm over the view's outline (y
#     121.9 mm) and 5.4 mm under the front view's arm width line (y 132.4
#     mm); the run y 116.35..123.5 mm, the lower tail y 103.65..97.3 mm,
#     3.8 mm right of the offset's row at its widest;
#   - the arm's thickness (FootprintThickness, 7.50, witnesses y 107 and
#     114.5 mm from the arm's east corners, x 140..176 mm): column x 175
#     mm, its text IN-SPAN (a text requested inside a vertical span prints
#     centred on the column, its box's bottom 2.78 mm under the requested
#     y: the 12.70, retry10): " 7.50 " over x 168.9..181.1 mm, y 109..112.5
#     mm, 2 mm inside its own witnesses, 4.3 mm from the flange height's
#     upper witness end (x 167 mm); its tails end at y 100.65 and 120.85
#     mm, 2.65 mm under the flange height's row.
# The hole callout's block (x ~174..250 mm, y ~74.9..95.1 mm when it had
# four rows; three now) starts 11.8 mm right of the offset's row at its
# widest and ends 5.5 mm under the thickness' lower tail; the side view's
# lowest rows start at x 179.5 mm, y 172 mm.
BOTTOM_KEEP = {"FlangeHeight": (0.130, 0.10509)}
BOTTOM_FOOTPRINT_KEEP = {
    "FootprintOffset": (0.114, 0.07869),
    "FootprintThickness": (0.139, 0.09057),
}
# The caption belongs BELOW the lower view, not between it and the front view.
# Centre it on the measured bottom-view outline, below that view's lowest
# coordinate witness/text (retry15: MountingX1 ends at y 80.02 mm). The
# callout block is to the right; its diagonal leader is independently proven
# clear of the caption's actual extent.  The caption names the view the
# front view's letter arrow points (machinist review r1: no viewing arrow).
BOTTOM_CAPTION = "VIEW A"
BOTTOM_CAPTION_XY = (0.0505, 0.05619)
BOTTOM_CAPTION_GAP_M = 0.002
# INote.GetExtent reads ~0.3 mm apart between sessions; settle within twice.
CAPTION_SETTLE_M = 0.0006
# The mounting holes' coordinates on the bottom view (viewer +Z: x = 134 + X,
# y = 110 + Y mm; the flange's west end at x 91 mm, its lower face at y 103.65
# mm, the holes at x 95 and 108.7 mm, y 110 mm).  Each coordinate sketch
# chain runs west corner -> hole station on the lower face -> hole, so the X
# witnesses drop from the lower face (y 102.65 mm) and the holes' row reads
# from the lower face up to the hole.  The two X coordinates share the
# west-end baseline and stack under the view, 8 mm apart, the shorter nearer
# the part, hung LEFT of that baseline (horizontal rule, retry09: a lone row
# prints centred on the requested x with its bottom on the dimension line,
# 2.78 mm under the requested y, and the line runs from the row's far end
# through both witnesses to an outside-arrow tail 6.4 mm past the far one):
# " 4.00 ±0.05 " (24.5 mm) over x 62.75..87.25 mm on the line at y 89 mm, its
# tail to x 101.4 mm; " 17.70 ±0.05 " (27.1 mm) over x 61.45..88.55 mm on the
# line at y 81 mm, its tail to x 115.1 mm; 4.5 mm of air between the rows and
# 11.5 mm over the y 69.5 mm level below them.  The holes' row
# from the lower face (6.35 mm, too short a span for its row: requested AT
# its witness it printed centred on its own column, retry09) hangs ABOVE and
# left of its column at x 80 mm, its shoulder 2.78 mm under the requested y:
# the row over x 55.5..80 mm on a shoulder at y 113.8 mm (its box y 114.7..
# 118.3 mm, 4.7 mm over the holes' row witness); the column's outside-arrow
# tail ends 6.4 mm under the lower face, at y 97.25 mm, 3.75 mm over the
# 4.00's row box.  The holes' row witness runs over the flange from 5.4 mm
# past the hole (x 100.4 mm, retry09's measured overrun) to x 79 mm.
BOTTOM_HOLE_KEEP = {
    "MountingX0": (0.039, 0.07059),
    "MountingX1": (0.039, 0.06259),
    "MountingY0": (0.044, 0.09539),
}
# The collar's end-on circles: the annulus sketch lies on the part's Right
# plane, so its two diameters import to the side view, whose collar centre is
# the pinned origin (SIDE_AXIS_X, FRONT_ORIGIN_Y) = (228, 230.15) mm (the
# quoted y below are pre-A1: add 24 mm).  A
# diameter's block prints centred on the requested x, its value row's bottom
# at the requested y (1 mm higher with a tolerance stack), the callout rows
# 5.6 mm apart under it (the first 4.5 mm under a toleranced value), its
# elbow 1.6 mm past the lowest row's near end on that row's baseline
# (retry09: "COLLAR OD" requested at (284, 196) mm printed over x 270.4..
# 297.7 mm, y 190.4..199.5 mm, its elbow at (268.8, 190.4) mm; the bore's
# three rows requested at (226, 147) mm printed y 136.9..156.1 mm, the
# elbow at (258.3, 136.9) mm).  Both read ABOVE the collar, the OD on the
# left ("COLLAR OD" 27.3 mm over x 189.2..216.5 mm, y 219..222.5 mm, "Ø12.00"
# over it, the elbow at (218.05, 219) mm), the bore on the right (retry09's
# 24-character "REAM OR BORE: PRESS SEAT" printed 61.5 mm wide).  The bore
# now reads as a REFERENCE nominal, "(Ø5.986)" with no tolerance stack,
# over three matched-fit rows (COLLAR_BORE_CALLOUT).  Measured on r3b: that
# four-row block prints vertically CENTRED on the requested y, not hung under
# it -- requested (272.4, 258.65) mm, the value row's top at 268.8 mm (2.1 mm
# over the drawable top, 266.7 mm), the rows' baselines at 258.6, 253.1 and
# 247.5 mm, each row centred on the requested x, the widest ("DIAMETRAL
# INTERFERENCE ON", 67.0 mm) over x 238.9..305.9 mm and the elbow on the
# lowest baseline 1.6 mm before that row's near end, at (237.3, 247.5) mm.
# So the block's top is the requested y + 10.15 mm and its lowest baseline
# the requested y - 11.15 mm.  The first row now says THRU (30 characters,
# ~74.4 mm in Century Gothic, the widest), so the block is requested at
# (270.4, 254.65) mm: top ~264.8 mm (1.9 mm under the border), lowest
# baseline ~243.5 mm, rows over x ~233.2..307.6 mm, the elbow at ~(231.6,
# 243.5) mm -- right of the OD's rows and elbow (x <= 218.05 mm), 7.4 mm over
# the collar's top and 9 mm left of the isometric's outline (x 316.6 mm).
# Each leader runs
# steeply down from its elbow to the NEAR rim and stops there: the near-side
# single-arrow style (set_near_side_diameter -- Diametric, one outside
# arrow, no second arrow, a broken horizontal leader; the alignment pinion's
# OD), the OD's arrow on its upper-left rim at ~(224.3, 210.9) mm, the
# bore's on its upper-right rim at ~(230, 208.3) mm.  Retry10's default
# style ran each diameter line on through the centre to the far rim, and
# both chords crossed the mounting face's witness from the origin (y 230.15
# mm, which starts at the collar's far edge, x 234 mm, and runs left through
# the centre to its column): two dim-line-crosses-extension findings.
# Landing above the axis, neither leader reaches y 230.15 mm;
# _prove_collar_diameters_clear reads the ink back after the rebuild and
# fails on any crossing with either axis witness, a landing off its rim or
# ink inside the rim.
SIDE_KEEP = {
    "CollarOd": (SIDE_AXIS_X - 0.0252, FRONT_ORIGIN_Y + 0.0185),
    "CollarBore": (SIDE_AXIS_X + 0.0424, FRONT_ORIGIN_Y + 0.0245),
}
# The arm's section, from the part's ArmSection witness (shown in the side
# view by curate_hidden_dimensions).  Turned into projection, the view's
# sheet-right is model -Y: the arm (Y -3..4.5) spans x 223.5..231 mm, the
# flange edge-on (Y +/-6.35) x 221.65..234.35 mm at y 129.75..132.93 mm (its
# mounting face, Z 100.40, at the bottom), the arm's end at y 126.64 mm, the
# collar's centre at (228, 230.15) mm.  A witness leaves its point 1 mm out
# and runs 1 mm past the dimension line (retry09).
# The bore axis has ONE toleranced chain along Z (mreview10 blocker 2: the
# face and the arm's end both from the axis over-located the arm's end):
#   - the mounting face from the bore axis, "100.40 / MOUNTING FACE / TO BORE
#     AXIS" (~37 mm), VERTICAL and in-span (a text requested inside a
#     vertical span prints centred on the column and breaks the line: the
#     bottom view's 12.70, retry09), on the LEFT: its seat corner is at Y
#     +6.35, the flange's left end (x 221.65 mm), so its witness continues
#     the mounting face's edge leftward; column x 198 mm, rows x ~179.5..
#     216.5 mm, y ~172..186.6 mm, 5.15 mm left of the flange; its witness
#     from the origin starts at the collar's far edge (x 234 mm, retry10)
#     and runs left through the centre to the column;
#   - the arm's physical overhang, "3.11 / ARM PAST / MOUNTING / FACE"
#     (ArmPastSeat), VERTICAL and hung BELOW its 3.11 mm span.  Its
#     column stays at x 212 mm, short of the 3.00's left tail at x 221.65
#     mm; its widest row (22.8 mm, either hand) stays over x 189.2..234.8
#     mm, clear of the bottom view's east stack (x <= 181.1 mm).  Requested
#     at y 119.5 mm, the four-row block stays under the 3.00's line at
#     y 134.44 mm and over the hole callout's top at y 95.1 mm.
#     Its witnesses still name the arm's end and the mounting face;
#     the upper tail ends at y 157.31 mm, under the mounting-face rows.
#     This remains an ordinary .XX control, not a tight overhang band.
# The arm's end from the bore axis, "(103.51) / ARM END / FROM BORE AXIS", is
# the chain's SUM (100.40 + 3.11 = 103.51) and prints as the sheet's
# drawing-native REFERENCE (_arm_end_reference: a vertical dimension
# between the collar's OD rim, re-anchored to its CENTRE, and the arm's end
# edge, proven to measure ARM_Z[1] on those two entities, parenthesised, its
# places from the spec's DRAWING_REFERENCE_PRECISION): in-span on the RIGHT
# where retry10's model ArmEndFromAxis stood, its corner on the arm's lower
# face, Y -3 (x 231 mm), so the witness continues the arm's end edge
# rightward, 3.1 mm under the mounting face; column x 259 mm, rows x
# ~240.1..277.9 mm, y ~170.5..185.1 mm, 5.75 mm right of the flange.
# ONE dimension across the arm, HORIZONTAL (model Y): the arm's lower face
# from the bore axis (ArmBelowAxis, x 228..231 mm), hung off its 3 mm span
# below the arm's end, its witnesses dropping from the arm's end corner and
# the centerline's end (y 146.85 mm).  Retry10 stacked it with the arm's
# thickness and its offset from the flange's hole-datum edge, and each
# outside arrow's 6.4 mm tail past its far witness ran across the next
# dimension's witness (two dim-line-crosses-extension findings); those two
# now control the arm in the BOTTOM view, where the arm's end face is seen
# (BOTTOM_FOOTPRINT_KEEP), and the 3.00 stands alone with its arrows
# OUTSIDE (no 3 mm span fits two 3.556 mm arrowheads inside: retry11 rule,
# no inside-arrowhead overlap): "NEAR ARM FACE / TO BORE AXIS" names the
# Y -3 face, nearer the bore axis than the opposite Y +4.5 face. Its two
# label rows keep the native 3.00 block to three rows, still centred at
# x 264 mm with the value at y 140 mm; the lowest row/line at y 128.89 mm
# spans x ~245.5..282.5 mm at the widest observed letter pitch. It stays
# right of the flange's witnesses, left of the isometric and a text height
# under the arm end's witness (y 147.85 mm).
# The line runs from the rows' near end left through both
# witnesses to its tail at x 221.65 mm, clear of the overhang's column at
# x 212 mm and the mounting face's at x 198 mm.  The overhang's labelled
# block hangs well under this line; the hole callout ends at y ~95
# mm (pre-A1 frame) and the 1:2 isometric starts at x ~316 mm.  _assert_dimensions_clear
# still proves the complete rebuilt side-view ink, without exemptions.
# A1 (#1559): the stations from the bore axis (SeatToAxis, the arm end's
# reference) rose 24 mm with it, staying in-span; the stacks under the arm's
# end (ArmPastSeat, ArmBelowAxis) fell 21.21 mm with it, keeping the quoted
# clearances to the arm's end and to the hole callout under them.
# Subtract 21.21 mm from the y quoted above for those two, add 24 mm for the
# other two and for the collar's diameters.
# r3b's native layout audit then measured the arm end reference's arrow,
# (259.0, 126.6)->(258.6, 130.2) mm on the arm end's witness (y 126.6 mm),
# 0.86 mm from the 3.00's value text [259.6, 122.5]..[268.4, 126.1] mm
# (arrow-near-text needs 2.0 mm; its witness stood 0.57 mm off).  The 3.00
# block now hangs 2.5 mm lower: its value text's top ~123.6 mm, 3.0 mm under
# that witness and arrow; its line at ~108.0 mm stays over the hole
# callout's block (top ~63.3 mm) and right of the overhang's column.
SIDE_SECTION_KEEP = {
    "SeatToAxis": (SIDE_AXIS_X - 0.030, 0.2025),
    "ArmPastSeat": (SIDE_AXIS_X - 0.016, 0.09829),
    "ArmBelowAxis": (SIDE_AXIS_X + 0.036, 0.11879 - 0.0025),
}
# The sheet-derived reference: its spec key (DRAWING_REFERENCE_PRECISION),
# its in-span text position and its callout-below rows.
ARM_END_REFERENCE = "arm end from bore axis"
ARM_END_REFERENCE_XY = (SIDE_AXIS_X + 0.031, 0.201)
ARM_END_REFERENCE_CALLOUT = "ARM END\nFROM BORE AXIS"
# swDimensionType_e: swLinearDimension, swHorLinearDimension,
# swVertLinearDimension. Angular type 3 is never a linear distance.
_LINEAR_DIMENSION_TYPES = (2, 11, 12)
# swDimensionArrowsSide_e: every short span in both stacks stands its
# arrows OUTSIDE -- no 3 or 3.35 mm span fits two 3.556 mm arrowheads
# inside (retry11 rule: no inside-arrowhead overlap) -- forced rather than
# left to the sheet's automatic choice, so the ink the layouts above are
# proven against is the ink the sheet draws.
_ARROWS_INSIDE = 0
_ARROWS_OUTSIDE = 1
SECTION_ARROW_SIDES = {"ArmBelowAxis": _ARROWS_OUTSIDE}
BOTTOM_ARROW_SIDES = {
    "FlangeHeight": _ARROWS_OUTSIDE,
    "FootprintOffset": _ARROWS_OUTSIDE,
    "FootprintThickness": _ARROWS_OUTSIDE,
}
# The sheet axis each proven dimension measures along: "x" for the one
# across the arm in the side view (dimension line horizontal, witnesses
# vertical), "y" for the side view's Z stations and the bottom view's three
# east of the flange (the reverse).  _section_crossings sorts each
# dimension's ink by it.
SECTION_AXES = {
    "ArmBelowAxis": "x",
    "SeatToAxis": "y",
    "ArmPastSeat": "y",
    ARM_END_REFERENCE: "y",
}
BOTTOM_AXES = {name: "y" for name in (*BOTTOM_KEEP, *BOTTOM_FOOTPRINT_KEEP)}
BOTTOM_WEST_AXES = {
    "MountingX0": "x",
    "MountingX1": "x",
    "MountingY0": "y",
}
# Blind-review round 1: the plan values read unattached at a glance -- label
# each with the feature it controls.  The collar's length names its
# direction (machinist review: 10.00 vs the Ø12 read as one feature) and the
# stack its band sets, the lever's press zone (machinist review r1, blocker:
# the band named no stack).  The flange's thickness prints three places, the
# title block's .XXX band, because it is the MHA-VN-050 screws' grip
# (machinist review r2: the third place named no function); the callout,
# derived in the spec with the stack that needs it, says so.  The
# arm-to-flange inside corners' MAX radius names the corners it controls.
DIMENSION_CALLOUTS = {
    "ArmWidth": "ARM WIDTH",
    "FlangeWidth": "FLANGE WIDTH",
    "FlangeDepth": FLANGE_DEPTH_CALLOUT,
    "CollarLen": COLLAR_LENGTH_CALLOUT,
    "ArmRootR": "ARM ROOT\nCORNERS",
}
# The bore names its process (drawing-guidelines.md rule 7 (notes: few,
# flagged, never a method)), the part it seats and the matched fit it needs.
SIDE_CALLOUTS = {
    "CollarOd": "COLLAR OD",
    "CollarBore": COLLAR_BORE_CALLOUT,
}
# The section labels name the physical arm face, mounting face and overhang.
# Split the overhang's words across three rows so the native block hangs clear
# under the side view without reaching the bottom view's east-stack ink.
# The footprint pair's face-on witnesses still name their actual edges.
SECTION_CALLOUTS = {
    "ArmBelowAxis": "NEAR ARM FACE\nTO BORE AXIS",
    "SeatToAxis": "MOUNTING FACE\nTO BORE AXIS",
    "ArmPastSeat": "ARM PAST\nMOUNTING\nFACE",
}
# The hole callout names the mate its banded coordinates match (machinist
# review r1, blocker: the ±0.05 pattern named no mate): the summing lever's
# two tapped holes the bracket screws into.  Two mate rows, then the process
# word (machinist review r2, rule 12: say drill) joined to the native size
# row (compose_hole_callout_prefix: no trailing break joins the two with one
# space), "DRILL 2X Ø2.59 THRU ALL" -- three physical rows.  The size row is
# the widest and the lowest, the leader's elbow at its near end, so neither
# row over it reaches past that end toward the leader.
MOUNTING_HOLE_PROCESS = "MATCHES MHA-SM-003\nSUMMING LEVER TAPS\nDRILL"

# Third-angle projection of the side view: model +Z (down the front view)
# points down the sheet, model +Y left (the viewer is at +X, the front view's
# right).  Angles are sheet radians, counter-clockwise from sheet +x.
SIDE_DOWN_AXIS = (0.0, 0.0, 1.0)
SIDE_LEFT_AXIS = (0.0, 1.0, 0.0)
PROJECTION_ANGLE_TOL = 1e-6
PROJECTION_TOL_M = 1e-4  # the latch hook's _PIN_TOL_M


def _mounting_rims(edges: ViewEdges) -> list[Any]:
    """The through holes' rims on the mounting face, from its one edge sweep:
    the bottom view looks from +Z at the plain holes' exit rims."""
    return [
        edges.circle_at(
            (point[0], point[1], SIDE_PLATE_Z[1]),
            CLEARANCE_DIA / 2.0,
            axis=(0.0, 0.0, 1.0),
            label=f"bracket mounting hole {index}",
        )
        for index, point in enumerate(BRACKET_HOLE_POINTS)
    ]


def _axis_direction(
    adapter: Any, view: Any, axis_mm: tuple[float, float, float], label: str
) -> tuple[float, float]:
    """Sheet direction (metres) of a model axis in ``view``."""
    origin = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label=f"{label} origin")
    tip = model_point_in_view(
        adapter, view, tuple(v / 1000.0 for v in axis_mm), label=f"{label} tip"
    )
    return tip[0] - origin[0], tip[1] - origin[1]


def _require_axis_along(
    adapter: Any,
    view: Any,
    axis_mm: tuple[float, float, float],
    sheet_angle: float,
    label: str,
) -> None:
    dx, dy = _axis_direction(adapter, view, axis_mm, label)
    error = math.remainder(math.atan2(dy, dx) - sheet_angle, math.tau)
    if abs(error) > PROJECTION_ANGLE_TOL:
        raise RuntimeError(
            f"{label}: model {axis_mm} points {math.atan2(dy, dx):g} rad on the "
            f"sheet, expected {sheet_angle:g}"
        )


def _project_side_view(adapter: Any, front: Any, side: Any) -> None:
    """Turn the side view into third-angle projection with the front view
    and pin its origin to the front view's origin height.

    ``*Right`` arrives with model +Y up and +Z to the sheet's left (mreview09
    blocker 1: the collar's circle beside an arm running left read as a
    different part).  The turn is measured, not assumed: model +Z is
    projected before and after ``IView::Angle`` (the cradle's ``_turn``), and
    +Y must then point left.  The move is by the origin's projection, read
    back (the latch hook's ``_pin_origin``): the side view's origin lands at
    SIDE_AXIS_X on the FRONT view's measured origin height.
    """
    native = _early_bound(side, "IView")
    dx, dy = _axis_direction(adapter, native, SIDE_DOWN_AXIS, "side view +Z")
    native.Angle = float(native.Angle) - math.pi / 2.0 - math.atan2(dy, dx)
    rebuild_drawing(adapter, label="turn side view")
    _require_axis_along(adapter, native, SIDE_DOWN_AXIS, -math.pi / 2.0, "side view +Z")
    _require_axis_along(adapter, native, SIDE_LEFT_AXIS, math.pi, "side view +Y")
    front_origin = model_point_in_view(
        adapter, front, (0.0, 0.0, 0.0), label="front view origin"
    )
    target = (SIDE_AXIS_X, front_origin[1])
    at = model_point_in_view(adapter, native, (0.0, 0.0, 0.0), label="side view origin")
    position = tuple(float(value) for value in native.Position)
    moved = [position[axis] + target[axis] - at[axis] for axis in range(2)]
    if native.SetViewPosition(double_array(moved), False) is not True:
        raise RuntimeError("failed to move the side view into projection")
    rebuild_drawing(adapter, label="project side view")
    at = model_point_in_view(adapter, native, (0.0, 0.0, 0.0), label="side view origin")
    if math.dist(at, target) > PROJECTION_TOL_M:
        raise RuntimeError(
            f"side view origin sits at ({at[0] * 1000.0:.2f}, {at[1] * 1000.0:.2f}) mm, "
            f"not at ({target[0] * 1000.0:.2f}, {target[1] * 1000.0:.2f}) mm"
        )
    _telemetry.success(
        f"side view in third-angle projection: +Z down, +Y left, origin at "
        f"({at[0] * 1000.0:.2f}, {at[1] * 1000.0:.2f}) mm on the front view's "
        f"origin height {front_origin[1] * 1000.0:.2f} mm"
    )


# swAnnotationType_e: swCenterMark (ISO 13).
_CENTER_MARK_ANNOTATION = 13
# A centre mark's ink centre against the projected bore axis: its lines come
# back from GetDisplayData as sheet coordinates, so half a millimetre bounds
# a mark drawn on the wrong circle without arguing over a pixel.
CENTER_MARK_AXIS_SLOP = 0.0005


def _collar_bore_rim(edges: ViewEdges) -> ViewEdge:
    """The bore's rim on the collar's near end face.  The side view looks from
    +X (the arm, +Z, runs down the sheet), so the face at +COLLAR_HALF_LEN
    carries the visible circles; the far rim is coaxial and prints under it."""
    return edges.circle_at(
        (COLLAR_HALF_LEN, 0.0, 0.0),
        COLLAR_BORE_DIA / 2.0,
        axis=(1.0, 0.0, 0.0),
        label="bracket collar bore rim",
    )


def _collar_od_rim(edges: ViewEdges) -> ViewEdge:
    """The OD's rim on the same near end face: the circle the sheet-derived
    arm-end reference is anchored to (at its centre, the bore axis)."""
    return edges.circle_at(
        (COLLAR_HALF_LEN, 0.0, 0.0),
        COLLAR_OD / 2.0,
        axis=(1.0, 0.0, 0.0),
        label="bracket collar OD rim",
    )


def _arm_end_edge(edges: ViewEdges) -> ViewEdge:
    """The arm's end edge the side view draws: the end face's edge nearest the
    viewer (+X, at +ARM_HALF_X), running the arm's thickness at Z ARM_Z[1].
    Picked exactly through the edge's midpoint (the far, -X edge prints under
    it but is 2 * ARM_HALF_X away in model space), then proven to span the
    thickness, so no other edge through that point could resolve."""
    midpoint = (ARM_HALF_X, (ARM_Y[0] + ARM_Y[1]) / 2.0, ARM_Z[1])
    edge = edges.exact_line_through(midpoint, label="bracket arm end edge")
    start, end = edge.line
    ys = sorted((start[1], end[1]))
    if (
        abs(edge.length_mm - (ARM_Y[1] - ARM_Y[0])) > 1e-6
        or abs(ys[0] - ARM_Y[0]) > 1e-6
        or abs(ys[1] - ARM_Y[1]) > 1e-6
        or any(abs(p[0] - ARM_HALF_X) > 1e-6 or abs(p[2] - ARM_Z[1]) > 1e-6 for p in (start, end))
    ):
        raise RuntimeError(f"bracket arm end edge resolved to {edge.line}, not the end face's edge")
    return edge


def _collar_axis(adapter: Any, side: Any, rim: ViewEdge) -> tuple[float, float]:
    """Where the bore's axis prints on the sheet (metres), from the rim's centre."""
    cx, cy, cz, *_ = rim.circle
    return model_point_in_view(
        adapter, side, (cx / 1000.0, cy / 1000.0, cz / 1000.0), label="collar bore axis"
    )


def _set_arrow_sides(
    adapter: Any, annotations: Sequence[Any], sides: Mapping[str, int], *, label: str
) -> None:
    """Stand each named dimension's arrows on its swDimensionArrowsSide_e side
    (the cone tip block's _set_arrow_sides); the setter reports nothing, so
    the side is read back."""
    remaining = dict(sides)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        side = remaining.pop(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArrowSide = side
        if int(display.ArrowSide) != side:
            raise RuntimeError(f"{label} {name} did not keep its arrows on side {side}")
    if remaining:
        raise RuntimeError(f"no {label} dimension to set arrow sides: {sorted(remaining)}")


# A stroke along or across a sheet axis within this (metres); the audit's
# collinear tolerance.
_AXIS_TOL = 1e-4


def _stroke_axis(segment: Segment) -> str | None:
    """``"x"`` for a sheet-horizontal stroke, ``"y"`` for a vertical one, None
    for a slanted one; a zero-length stroke reads as ``""``."""
    (x0, y0), (x1, y1) = segment
    flat, upright = abs(y1 - y0) <= _AXIS_TOL, abs(x1 - x0) <= _AXIS_TOL
    if flat and upright:
        return ""
    if flat:
        return "x"
    if upright:
        return "y"
    return None


def _section_crossings(
    ink: Mapping[str, Sequence[Segment]], axes: Mapping[str, str]
) -> list[tuple[str, str]]:
    """Every ``(owner, crossed)`` where ``owner``'s dimension line runs over
    ``crossed``'s extension line or dimension line: the layout audit's
    dim-line-crosses-extension, decided on the rendered ink of a set of
    axis-aligned dimensions before the sheet is published.

    ``axes[name]`` is the sheet axis the dimension measures along; a stroke
    along it is dimension-line ink (the line, its run under hung rows, an
    outside arrow's tail), one across it a witness (a hung row's shoulder
    sorts with the witnesses: nothing may run over it either).  A line
    meeting a witness collinear with one of the owner's own (within
    _AXIS_TOL) is exempt, as the audit exempts shared extension lines;
    witness over witness is not a crossing.  A slanted stroke is reported as
    ``(name, "slanted")``: nothing here may draw one.
    """
    lines: dict[str, list[Segment]] = {}
    witnesses: dict[str, list[Segment]] = {}
    crossings: list[tuple[str, str]] = []
    for name, segments in ink.items():
        lines[name], witnesses[name] = [], []
        for segment in segments:
            axis = _stroke_axis(segment)
            if axis == "":
                continue
            if axis is None:
                crossings.append((name, "slanted"))
            elif axis == axes[name]:
                lines[name].append(segment)
            else:
                witnesses[name].append(segment)
    for owner in ink:
        for other in ink:
            if other == owner:
                continue
            over_line = any(
                segments_cross(line, foreign)
                for line in lines[owner]
                for foreign in lines[other]
            )
            over_witness = any(
                segments_cross(line, foreign)
                and not any(
                    _stroke_axis(mine) == _stroke_axis(foreign)
                    and distance_to_line(mine, foreign[0]) <= _AXIS_TOL
                    for mine in witnesses[owner]
                )
                for line in lines[owner]
                for foreign in witnesses[other]
            )
            if over_line or over_witness:
                crossings.append((owner, other))
    return crossings


def _assert_dimensions_clear(
    annotations: Mapping[str, Any], axes: Mapping[str, str], *, label: str
) -> None:
    """Prove, on the rebuilt ink, that no named dimension's line runs over
    another's witness (retry10's two under-arm findings)."""
    ink = {name: dimension_segments(annotation) for name, annotation in annotations.items()}
    empty = sorted(name for name, segments in ink.items() if not segments)
    if empty:
        raise RuntimeError(f"{label} dimensions draw no lines: {empty}")
    crossings = _section_crossings(ink, axes)
    summary = {name: f"{len(segments)} seg" for name, segments in ink.items()}
    _telemetry.event(
        "drawing.dimensions_clear",
        label=label,
        crossings=str(crossings),
        segments=str(summary),
    )
    if crossings:
        raise RuntimeError(f"{label} dimension lines run over witnesses: {crossings}; ink {ink}")
    _telemetry.success(f"{label}: no dimension line over a foreign witness {summary}")


# The native sheet's default caption height; inherited rather than overridden.
TEXT_HEIGHT_M = 0.0035


def _note_extent(note: Any, label: str) -> tuple[float, ...]:
    extent = tuple(float(value) for value in _early_bound(note, "INote").GetExtent())
    if (
        len(extent) != 6
        or not all(math.isfinite(value) for value in extent)
        or extent[3] <= extent[0]
        or extent[4] <= extent[1]
    ):
        raise RuntimeError(f"{label}: note has no rendered extent: {extent!r}")
    return extent


def _place_bottom_caption(
    adapter: Any,
    view: Any,
    annotations: Sequence[Any],
    hole_callout: Any,
) -> None:
    """Centre the caption below the lower view's actual outline and ink.

    All lower-view controls contribute their rebuilt witnesses and text
    positions. The caption's top clears their lowest extent and its box
    clears the hole callout's leader. No view centre or projection moves.
    """
    sheet = _early_bound(
        _early_bound(adapter.currentModel, "IDrawingDoc").GetCurrentSheet(), "ISheet"
    )
    if sheet.SetScale(*SHEET_SCALE, False, False) is not True:
        raise RuntimeError("cannot pin the sheet scale before the bottom view caption")
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if (
        len(outline) != 4
        or not all(math.isfinite(value) for value in outline)
        or outline[2] <= outline[0]
        or outline[3] <= outline[1]
    ):
        raise RuntimeError(f"bottom view has an invalid outline: {outline!r}")
    lowest = outline[1]
    if not annotations:
        raise RuntimeError("the bottom view has no controls to clear the caption from")
    for annotation in annotations:
        lines = dimension_segments(annotation)
        texts = dimension_text_points(annotation)
        if not lines or not texts:
            raise RuntimeError("a bottom view control drew no witness/text to clear the caption from")
        lowest = min(lowest, *(p[1] for s in lines for p in s), *(p[1] for p in texts))
    target = (
        (outline[0] + outline[2]) / 2.0,
        lowest - BOTTOM_CAPTION_GAP_M - CAPTION_SETTLE_M,
    )
    raw_note = add_note(adapter, BOTTOM_CAPTION, *BOTTOM_CAPTION_XY)
    if raw_note is None:
        raise RuntimeError("the bottom view caption was not inserted")
    note = _early_bound(raw_note, "INote")
    text = note.GetText()
    if type(text) is not str or text != BOTTOM_CAPTION:
        raise RuntimeError(f"bottom view caption text did not persist: {text!r}")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError("bottom view caption has no annotation")
    text_format = _early_bound(annotation.GetTextFormat(0), "ITextFormat")
    if text_format is None or not math.isclose(
        float(text_format.CharHeight), TEXT_HEIGHT_M, abs_tol=1e-6
    ):
        raise RuntimeError("bottom view caption did not keep the sheet's native text height")
    for _attempt in range(4):
        extent = _note_extent(note, "bottom view caption")
        error = (target[0] - (extent[0] + extent[3]) / 2.0, target[1] - extent[4])
        if max(abs(error[0]), abs(error[1])) < CAPTION_SETTLE_M:
            break
        move_annotation(adapter, annotation, *error, label="bottom view caption")
    else:
        raise RuntimeError(
            f"bottom view caption stayed at {extent}, its top centre requested at {target}"
        )
    if lowest - extent[4] < BOTTOM_CAPTION_GAP_M:
        raise RuntimeError(
            f"bottom view caption {extent} does not fit below its controls (y {lowest})"
        )
    callout_annotation = _early_bound(hole_callout, "IDisplayDimension").GetAnnotation()
    callout_ink = dimension_segments(callout_annotation)
    box = (extent[0], extent[1], extent[3], extent[4])
    if not callout_ink or any(
        distance_to_box(segment, box) < BOTTOM_CAPTION_GAP_M for segment in callout_ink
    ):
        raise RuntimeError("bottom view caption crowds the native hole callout's leader")
    _telemetry.info(
        f"bottom view caption: outline {outline}, lowest control y {lowest}, extent {extent}"
    )


def _add_view_a_arrow(adapter: Any, front: Any) -> None:
    """The letter arrow on the front view naming VIEW A, the bottom view:
    its tip on the mounting face's edge, pointing up the sheet (+Z to -Z)."""
    text_xy, tip_xy = VIEW_A_ARROW
    add_leader_note(
        adapter,
        "A",
        text_xy=text_xy,
        attach_xy=tip_xy,
        view=front,
        label="view A viewing arrow",
        height=VIEW_LETTER_HEIGHT,
    )


# Each diameter's one arrow lands on its own rim and none of its ink comes
# nearer the axis than this fraction of that rim (the crank drive gear's
# bands); the axis witnesses pass through the centre by design, so they take
# a band from the centre to the collar's far edge and no keep-out.
_OD_LANDING = (0.8, 1.2)
_BORE_LANDING = (0.5, 1.5)
_RIM_KEEP_OUT = 0.8


def _near_side_collar_diameters(adapter: Any, annotations: Sequence[Any]) -> dict[str, Any]:
    """Give both collar diameters the near-side single-arrow style; returns
    them by name for the proof after the rebuild."""
    diameters: dict[str, Any] = {}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in SIDE_KEEP:
            set_near_side_diameter(annotation, f"collar {name}")
            diameters[name] = annotation
    missing = sorted(set(SIDE_KEEP) - set(diameters))
    if missing:
        raise RuntimeError(f"collar diameters not imported to the side view: {missing}")
    return diameters


def _prove_collar_diameters_clear(
    diameters: Mapping[str, Any], stations: Mapping[str, Any], *, axis: tuple[float, float]
) -> None:
    """After the rebuild: each diameter's arrow lands on its own rim, no
    diameter ink crosses its rim inward, and neither crosses an axis witness
    (the mounting face's and the arm-end reference's both run along y
    230.15 mm through the centre -- collinear, so one group per station)."""
    od_r = COLLAR_OD / 2000.0
    bore_r = COLLAR_BORE_DIA / 2000.0
    ink = {name: dimension_segments(a) for name, a in (*diameters.items(), *stations.items())}
    lands_within = {
        "CollarOd": (_OD_LANDING[0] * od_r, _OD_LANDING[1] * od_r),
        "CollarBore": (_BORE_LANDING[0] * bore_r, _BORE_LANDING[1] * bore_r),
    }
    keep_out = {"CollarOd": _RIM_KEEP_OUT * od_r, "CollarBore": _RIM_KEEP_OUT * bore_r}
    for station in stations:
        assert_leaders_clear(
            {name: ink[name] for name in (*diameters, station)},
            centre=axis,
            keep_out=keep_out,
            lands_within={**lands_within, station: (0.0, od_r + 0.002)},
            label=f"collar diameters against {station}",
        )


def _set_reference_precision(adapter: Any, display: Any, *, label: str) -> None:
    """Give a SHEET-derived reference its spec-authored places, checking the
    integer SetPrecision3 status and the applied primary precision."""
    places = DRAWING_REFERENCE_PRECISION[label]
    display = _early_bound(display, "IDisplayDimension")
    # -1: swDimensionPrecisionSettings_e do-not-change for dual/tolerance.
    # Keep the spec lookup at the call site for the specification-purity gate.
    status = adapter._attempt(
        lambda: display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    )
    if type(status) is not int or status != 0:
        raise RuntimeError(f"{label}: SetPrecision3 did not succeed: {status!r}")
    applied = adapter._attempt(display.GetPrimaryPrecision2)
    if type(applied) is not int or applied != places:
        raise RuntimeError(
            f"{label}: sheet dimension prints {applied} decimal places, not {places}"
        )


def _set_callout_below(display: Any, text: str, label: str) -> None:
    """The rows under a dimension's value (the crank hub's _set_callout_below);
    ``SetText`` reports nothing, so it is read back."""
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(4, text)  # swDimensionTextCalloutBelow
    applied = display.GetText(4)
    if type(applied) is not str or applied.replace("\r", "") != text:
        raise RuntimeError(f"{label}: callout-below text did not persist: {applied!r}")


def _label_near_arm_face(adapter: Any, annotation: Any) -> None:
    """Label the existing model control from the arm's Y -3 face to the axis.

    ArmSection owns the witness (end.start at ArmY0, axis.start at Y 0);
    no sheet dimension or new reference is created. 'Near' means nearest
    the bore axis, not nearest the side-view observer (+X).
    """
    if not 0.0 < -ARM_Y[0] < ARM_Y[1]:
        raise RuntimeError("ArmBelowAxis does not identify the arm face nearest the bore axis")
    display = _early_bound(annotation, "IAnnotation").GetSpecificAnnotation()
    if display is None:
        raise RuntimeError("ArmBelowAxis: controlling dimension has no display annotation")
    display = _early_bound(display, "IDisplayDimension")
    kind = display.Type2
    if type(kind) is not int or kind not in _LINEAR_DIMENSION_TYPES:
        raise RuntimeError(f"ArmBelowAxis: expected a linear dimension, got type {kind!r}")
    # The targeted ArmSection import owns the model identity/attachments;
    # this is its value readback, not a new pair of drawing-entity picks.
    assert_dimension_measures(
        adapter, display, expected_mm=-ARM_Y[0], label="ArmBelowAxis"
    )
    _set_callout_below(display, SECTION_CALLOUTS["ArmBelowAxis"], "ArmBelowAxis")


def _arm_end_reference(adapter: Any, side: Any, edges: ViewEdges) -> Any:
    """The arm's end from the bore axis as a parenthesised SHEET dimension.

    A vertical drawing dimension between the collar's OD rim and the arm's
    end edge, both named entities, the rim's end re-anchored to its CENTRE
    (swArcEndCondition_e swArcEndConditionCenter) so it reads the bore
    axis; proven linear (IDisplayDimension::Type2), attached to exactly
    those two entities and measuring ARM_Z[1] (assert_dimension_measures)
    before it is parenthesised, given the spec's places and its callout
    rows.  It states nothing the toleranced chain (SeatToAxis + ArmPastSeat)
    does not: it is their sum, read for the machinist.  Returns its
    IAnnotation.
    """
    rim = _collar_od_rim(edges)
    end = _arm_end_edge(edges)
    dimension = add_edge_dimension(
        adapter,
        side,
        # Documentation only: both picks are by entity.
        p0=(SIDE_AXIS_X, FRONT_ORIGIN_Y + COLLAR_OD / 2000.0),
        p1=(SIDE_AXIS_X - (ARM_Y[0] + ARM_Y[1]) / 2000.0, FRONT_ORIGIN_Y - ARM_Z[1] / 1000.0),
        text_xy=ARM_END_REFERENCE_XY,
        label=ARM_END_REFERENCE,
        orientation="vertical",
        entities=(rim.edge, end.edge),
    )
    display = _early_bound(dimension, "IDisplayDimension")
    kind = display.Type2
    if type(kind) is not int or kind not in _LINEAR_DIMENSION_TYPES:
        raise RuntimeError(f"{ARM_END_REFERENCE}: expected a linear dimension, got type {kind!r}")
    set_arc_endpoints_to_center(adapter, dimension, label=ARM_END_REFERENCE)
    assert_dimension_measures(
        adapter,
        dimension,
        expected_mm=ARM_Z[1],
        label=ARM_END_REFERENCE,
        entities=(rim.edge, end.edge),
    )
    raw_annotation = display.GetAnnotation()
    if raw_annotation is None:
        raise RuntimeError(f"{ARM_END_REFERENCE}: sheet dimension has no annotation")
    annotation = _early_bound(raw_annotation, "IAnnotation")
    set_reference_dimension(adapter, annotation, label=ARM_END_REFERENCE)
    _set_reference_precision(adapter, display, label=ARM_END_REFERENCE)
    _set_callout_below(display, ARM_END_REFERENCE_CALLOUT, ARM_END_REFERENCE)
    return annotation


def _ink_centre(annotation: Any, label: str) -> tuple[float, float]:
    """Centre of a centre mark's rendered lines (sheet metres)."""
    data = _early_bound(annotation, "IAnnotation").GetDisplayData()
    if data is None:
        raise RuntimeError(f"{label}: centre mark has no display data")
    data = _early_bound(data, "IDisplayData")
    count = int(data.GetLineCount())
    if count <= 0:
        raise RuntimeError(f"{label}: centre mark draws no lines")
    xs: list[float] = []
    ys: list[float] = []
    for index in range(count):
        line = [float(v) for v in data.GetLineAtIndex2(index)]
        xs.extend((line[4], line[7]))
        ys.extend((line[5], line[8]))
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)


def _prove_collar_centre_mark(adapter: Any, side: Any, axis: tuple[float, float]) -> None:
    """Prove the collar's end view carries exactly ONE centre mark, on the
    bore's axis (``axis``: the bore rim's centre projected to the sheet).

    The project template centre-marks the extruded annulus's bore as the
    view is placed (its extended lines end at the bore radius plus 2.5 mm),
    so the explicit ``auto_center_marks(holes=True)`` the v41 sheet also
    ran printed a second, identical mark over it: retry09 native audit
    (20261012T124257186Z) counted DetailItem351 and DetailItem352 at
    (266.15, 180) mm, the same lines twice (the washer's annulus end view
    read 1 -> 2 the same way, #913).  This sheet adds none and proves the
    template's; zero marks or two fail loud, the proof is not a cleaner.
    """
    marks = list(
        _early_bound(side, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )
    if len(marks) != 1:
        raise RuntimeError(
            f"collar end view carries {len(marks)} centre marks, expected the "
            "template's one on the bore axis"
        )
    ink = _ink_centre(marks[0], "collar bore centre mark")
    offset = math.hypot(ink[0] - axis[0], ink[1] - axis[1])
    if offset > CENTER_MARK_AXIS_SLOP:
        raise RuntimeError(
            f"collar centre mark prints {offset * 1000.0:.2f} mm off the bore axis "
            f"(ink {ink[0] * 1000.0:.2f}, {ink[1] * 1000.0:.2f} mm; axis "
            f"{axis[0] * 1000.0:.2f}, {axis[1] * 1000.0:.2f} mm)"
        )
    _telemetry.success(
        f"collar end view: one centre mark, {offset * 1000.0:.2f} mm off the bore "
        f"axis at ({axis[0] * 1000.0:.2f}, {axis[1] * 1000.0:.2f}) mm"
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-bracket source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Magnifying Bracket Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying bracket; collar + arm + flange; steel fitting",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Top", *FRONT_CENTER, scale=(1, 1))
    bottom = place_view(adapter, str(SOURCE), "*Front", *BOTTOM_CENTER, scale=(1, 1))
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The collar bore and the mounting holes are fully defined by their callouts
    # (mreview09: the front view's dashed lines only cluttered the 10.00 and
    # 3.175), so every view prints hidden lines removed.
    for view in (front, bottom, side, iso):
        set_hidden_lines_removed(adapter, view)
    _project_side_view(adapter, front, side)

    # Targeted imports: each view selects only the features owning its keep
    # map (the entire-model fallback warned on every view and imported the
    # whole marked set to delete most of it).
    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    bottom_annotations = curate_view_dimensions(
        adapter,
        bottom,
        keep=BOTTOM_KEEP,
        view_label="bottom",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, side_annotations, SIDE_CALLOUTS)
    diameters = _near_side_collar_diameters(adapter, side_annotations)
    # The bore's nominal is a REFERENCE: the matched-fit callout under it
    # states the acceptance (mg_magnifying_bracket_spec.COLLAR_BORE_CALLOUT).
    set_reference_dimension(
        adapter, diameters["CollarBore"], label="collar bore reference nominal", diameter=True
    )
    # The arm's section: the part blanks ArmSection, so this targeted import
    # shows it in the side view first (it stays shown there, printing the
    # bore axis as a centerline down to the arm's end; its construction lines
    # lie on the view's own edges).
    section_annotations = curate_hidden_dimensions(
        adapter,
        side,
        keep=SIDE_SECTION_KEEP,
        view_label="side arm section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, section_annotations, SECTION_CALLOUTS)
    _set_arrow_sides(adapter, section_annotations, SECTION_ARROW_SIDES, label="arm section")
    section = {dimension_name(adapter, a): a for a in section_annotations}
    if set(section) != set(SIDE_SECTION_KEEP) or len(section) != len(section_annotations):
        raise RuntimeError(
            f"arm section imported {sorted(section)}, expected {sorted(SIDE_SECTION_KEEP)}"
        )
    _label_near_arm_face(adapter, section["ArmBelowAxis"])
    overhang_display = section["ArmPastSeat"].GetSpecificAnnotation()
    if overhang_display is None:
        raise RuntimeError("ArmPastSeat: controlling dimension has no display annotation")
    _set_callout_below(overhang_display, SECTION_CALLOUTS["ArmPastSeat"], "ArmPastSeat")
    # One sweep of the side view's edges serves the sheet reference's two
    # picks and the bore axis both proofs below measure from.
    side_edges = scan_view_edges(side, label="bracket collar end")
    bore_axis = _collar_axis(adapter, side, _collar_bore_rim(side_edges))
    section[ARM_END_REFERENCE] = _arm_end_reference(adapter, side, side_edges)
    # The side view's ink is read back once it has settled: no dimension line
    # over a foreign witness under the arm, and the diameters' leaders clear
    # of both axis witnesses (retry10's four dim-line-crosses-extension).
    rebuild_drawing(adapter, label="side view annotations")
    _assert_dimensions_clear(section, SECTION_AXES, label="side arm section")
    _prove_collar_diameters_clear(
        diameters,
        {name: section[name] for name in ("SeatToAxis", ARM_END_REFERENCE)},
        axis=bore_axis,
    )
    bottom_edges = scan_view_edges(bottom, label="bracket mounting face")
    rims = _mounting_rims(bottom_edges)

    hole_callout = add_native_hole_callout(
        adapter,
        bottom,
        # The east hole (x 72.7 mm), nearer the block.  Two rows naming the
        # summing lever's taps over the native size row, which the process
        # word leads ("DRILL 2X Ø2.59 THRU ALL"): three physical rows
        # (~14.6 mm), each centred on the anchor's x, the block centred 1 mm
        # under its y.  r3b measured the block at (162, 56) mm: baselines at
        # y 58.8, 53.25 and 47.7 mm, "MATCHES MHA-SM-003" (the widest, 51.2
        # mm) over x 136.4..187.6 mm, the size row 45.1 mm, the elbow 1.6 mm
        # before the widest row's near end, at (134.8, 47.6) mm.  "DRILL"
        # widens the size row to ~56.7 mm, now the widest, so the anchor moves
        # 6 mm right: rows over x ~139.6..196.4 mm, two text heights right of
        # the flange height's column (x 130 mm) and right of the offset's text
        # (x <= 126.2 mm), left of the title block (x > 216 mm under y 66 mm),
        # left of the iso and over the drawable border; the elbow at ~(138,
        # 47.7) mm, the leader's slope ~0.63 against r3b's 0.66.
        # The leader leaves the lowest row's near end and climbs left toward
        # the hole, clear of its own upper rows, both mounting X dimensions,
        # the offset's shoulder and the caption under the coordinate stack.
        # Those witness/caption clearances still have their native readbacks;
        # no hole variable, tolerance or shared callout helper is rewritten.
        edge=rims[1].edge,
        callout_xy=(0.168, 0.056),
        label="two bracket mounting holes",
        process=MOUNTING_HOLE_PROCESS,
    )
    hole_annotations = curate_hidden_dimensions(
        adapter,
        bottom,
        keep=BOTTOM_HOLE_KEEP,
        view_label="bracket mounting coordinates",
        dimensions_by_feature={
            "MountingCoordinates": ("MountingX0", "MountingX1", "MountingY0"),
        },
    )
    # The arm's footprint: the part blanks ArmFootprint, so this targeted
    # import shows it in the bottom view first (it stays shown there; its two
    # construction lines lie on the flange's east edge the view draws).  The
    # flange's height, imported with the view, stands in the same east stack,
    # so the three take their arrow sides together and the stack is proven
    # on the rebuilt ink: no dimension line over a foreign witness.
    footprint_annotations = curate_hidden_dimensions(
        adapter,
        bottom,
        keep=BOTTOM_FOOTPRINT_KEEP,
        view_label="bottom arm footprint",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    east_annotations = [*bottom_annotations, *footprint_annotations]
    east = {dimension_name(adapter, a): a for a in east_annotations}
    if set(east) != set(BOTTOM_AXES) or len(east) != len(east_annotations):
        raise RuntimeError(
            f"bottom view's east stack imported {sorted(east)}, expected {sorted(BOTTOM_AXES)}"
        )
    _set_arrow_sides(adapter, east_annotations, BOTTOM_ARROW_SIDES, label="bottom view")
    west = {dimension_name(adapter, a): a for a in hole_annotations}
    if set(west) != set(BOTTOM_HOLE_KEEP) or len(west) != len(hole_annotations):
        raise RuntimeError(
            f"bottom view's coordinates imported {sorted(west)}, expected {sorted(BOTTOM_HOLE_KEEP)}"
        )
    rebuild_drawing(adapter, label="bottom view annotations")
    _assert_dimensions_clear(east, BOTTOM_AXES, label="bottom view east stack")
    _assert_dimensions_clear(west, BOTTOM_WEST_AXES, label="bottom view mounting coordinates")

    # The collar bore's ASME centre mark is the template's, placed with the
    # end view: the sheet proves it (one, on the axis) rather than adding a
    # second over it.
    _prove_collar_centre_mark(adapter, side, bore_axis)

    rebuild_drawing(adapter, label="bottom caption clearance")
    _place_bottom_caption(
        adapter, bottom, [*east_annotations, *hole_annotations], hole_callout
    )
    _add_view_a_arrow(adapter, front)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Bracket Manufacturing Drawing",
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
