r"""Create the curated machinist drawing for the cone swing platform.

The SLDPRT remains authoritative.  The plan imports the plate outline,
post-mount pattern, lock notch and corner radii; the native Hole Wizard callout
defines the reamed pivot bore; section A-A exposes the shallow pivot-head
relief and plate thickness in solid lines.  Display precision comes from the
model.

The platform is an asymmetric steel wedge with a 1/4-in reamed H7 pivot
bore on the stock screw shoulder, paired 1/4-20 post-mount taps, an open
west-edge lock notch, four rounded plan corners and the counterbored #4
clearance hole for the tip block's single hold-down screw, rising from the
underside (user ruling 2026-09-29).  The three plan views run 1:2 and pivot
section A-A 2:1.  Detail B enlarges a 12 mm radius around the pivot-to-hole
region at 2:1 for the hole's station; section C-C (3:2, cropped to the
strip), cut on the plate-profile plan through the hole's axis, shows the
underside counterbore in solid lines and carries its native Hole Wizard
callout. The isometric
runs 1:3.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_cone_swing_platform.py dt-cone-swing-platform
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from collections.abc import Callable
from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    view_name,
    visible_component_entities,
)

from _check import check
from _com import _early_bound, _read_member
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_detail_crop import _transform_point
from _drawing_detail_projection import settle_detail_projection
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edges import visible_view_entities
from _drawing_finish import add_surface_finish
from _drawing_hole_callout import (
    add_native_hole_callout,
    compose_hole_callout_prefix,
    set_hole_callout_precision,
)
from _drawing_tolerances import _tolerance_places
from _drawing_layout_collect import check_drawing_layout
from _drawing_leader_notes import add_leader_note
from _drawing_notes import add_property_linked_note, property_link
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_scan import _zoomed_on
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _part_properties import part_drawing_unit
from _surface_finish import surface_finish_by_key
import _telemetry
import build_dt_cone_swing_platform as _part
from diagnostics.drawing_layout_audit import (
    _display_data,
    _display_lines,
    collect_document,
    describe_sheet,
)
from dt_cone_swing_platform_drawing_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HOLDDOWN_CALLOUT_BELOW,
    HOLDDOWN_PROCESS,
    PIVOT_BORE_CALLOUT_BELOW,
    PIVOT_PROCESS,
    POST_MOUNT_LOCATING_CALLOUT,
    RELIEF_WIDTH_CALLOUT,
    TOP_FACE_LABEL,
    UNDERSIDE_LABEL,
)
from dt_cone_swing_platform_spec import (
    HOLDDOWN_CBORE_DIA,
    HOLDDOWN_CLEARANCE_DIA,
    HOLDDOWN_LOCAL_X,
    HOLDDOWN_LOCAL_Z,
    PIVOT_BEARING_RELIEF_DEPTH,
    PLATE_STOCK_CALLOUT,
    PLATE_THICKNESS,
    POST_MOUNT_SPEC,
    SURFACE_FINISHES,
    UNIT,
)
from dt_cone_swing_platform_pivot_spec import PIVOT_HOLE_DIA


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_cone_swing_platform"]
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

SHEET_SCALE = (1.0, 2.0)  # title block states the principal (plan) scale; iso and section carry their own
SHEET_NAMES = ("PLATFORM",)
SHEET_SCALES = {SHEET_NAMES[0]: SHEET_SCALE}


# Sheet layout (meters).  Three 1:2 plan views separate the profile, hole
# pattern and lock-notch definitions instead of routing unrelated leaders
# through one narrow 224-mm wedge.  The section and pictorial occupy the
# right-hand field.
#
# The plans and every annotation laid out on them stand PLAN_DROP lower than
# at r1 (run 20261018T193840449Z): the post-mount taps' callout above the
# hole-location plan grew from two rows (10.3 mm, centred on its requested y)
# to four -- the break override and the mate under the thread -- and the
# plate's top edge (248.0 mm at r1) would have run through them.
PLAN_DROP = 0.009


def _planned(x: float, y: float) -> tuple[float, float]:
    return (x, y - PLAN_DROP)


PROFILE_CENTER = _planned(0.075, 0.190)
FEATURE_CENTER = _planned(0.180, 0.190)
NOTCH_CENTER = _planned(0.260, 0.190)
ISO_CENTER = (0.355, 0.205)
# The section group sits up and right in the open field below the isometric,
# clear of the lock-notch caption; every section annotation shares this shift.
# The group's right-hand ink ends ~410 mm, inside the 419 mm border.
SECTION_SHIFT = (0.030, 0.015)


def _shifted(x: float, y: float) -> tuple[float, float]:
    return (x + SECTION_SHIFT[0], y + SECTION_SHIFT[1])


SECTION_CENTER = _shifted(0.335, 0.105)
# A-A looks south like C-C (machinist review of e04fd60: looking north it
# drew the top face at its foot, opposite to C-C), so the top seat stands up
# and the base slide down.  The layout audit boxes an Ra symbol 39 mm right
# of its anchor, so neither anchor takes SECTION_SHIFT's extra 10 mm past the
# border (0.4189).  The seat's symbol stands over the left-hand piece, right
# of the PlateThk text and left of the relief note's leader (x >= 0.357; the
# symbol has no audit box to collide with that note's text-to-tip box); its
# leader drops right to that piece's top face.  The base slide's stands
# under the bore's gap and the right-hand piece, its leader rising left
# (smart side) to the left-hand piece's underside, clear of its text.
SEAT_FINISH_XY = (0.337, 0.134)
BASE_SLIDE_FINISH_XY = (0.370, 0.099)
# A-A's native caption, top centre, lowered 8 mm under the base-slide symbol
# into the open band above the title block (top 0.066).
SECTION_LABEL_XY = _shifted(0.335, 0.077)

# The pivot on the profile plan, where the farm run at 039e557da landed it
# (the plate's current outline re-centres the 1:2 view), less PLAN_DROP.
PROFILE_PIVOT_XY = _planned(0.0718, 0.1357)


def corner_fillet_centre_mm(label: str) -> tuple[float, float]:
    """Model plan (x, z) of a corner fillet's centre, from the part's own corners.

    The build fillets the sharp ``PLATE_CORNERS`` vertex, so the arc centre
    lies on the interior bisector, r / sin(theta / 2) from the vertex.
    """
    corners = _part.PLATE_CORNERS
    idx = [corner[0] for corner in corners].index(label)
    _label, x, z, radius = corners[idx]
    rays = []
    for _n, nx, nz, _r in (corners[idx - 1], corners[(idx + 1) % len(corners)]):
        length = math.hypot(nx - x, nz - z)
        rays.append(((nx - x) / length, (nz - z) / length))
    bx, bz = rays[0][0] + rays[1][0], rays[0][1] + rays[1][1]
    norm = math.hypot(bx, bz)
    reach = radius / math.sin(_part._corner_theta(label) / 2.0)
    return (x + bx / norm * reach, z + bz / norm * reach)


# A left-standing radius's leader knee (where its shelf meets the radial
# leader) relative to the text position SetPosition sets: measured on the R12
# corner, (+8.6, -2.8) mm on the run-20261009T172850508Z render, and the
# ray from the arc centre through it read 183.5 deg against the 183.3 deg
# arrow of run 20261010T072401692Z. The leader runs this far past the arc.
RADIUS_KNEE_FROM_TEXT = (0.0086, -0.0028)
CORNER_LEADER_REACH = 0.004


def corner_radius_text_xy(label: str) -> tuple[float, float]:
    """Text position that lands a corner radius's arrow at its arc's middle.

    The arc's middle lies on the ray from the fillet centre to the sharp
    ``PLATE_CORNERS`` vertex it rounds, in model space; the 1:2 plan maps
    model (x, z) to sheet (x, -z) about PROFILE_PIVOT_XY. A fixed sheet
    station went stale when the plate outline moved: CornerSER's
    near-horizontal shelf landed its arrow 5 deg past the R12 arc's end, on
    the east edge (run 20261010T072401692Z).
    """
    per_mm = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0
    corners = {corner[0]: corner for corner in _part.PLATE_CORNERS}
    _label, vx, vz, radius = corners[label]
    cx, cz = corner_fillet_centre_mm(label)
    length = math.hypot(vx - cx, vz - cz)
    ux, uy = (vx - cx) / length, -(vz - cz) / length
    reach = radius * per_mm + CORNER_LEADER_REACH
    knee = (
        PROFILE_PIVOT_XY[0] + cx * per_mm + ux * reach,
        PROFILE_PIVOT_XY[1] - cz * per_mm + uy * reach,
    )
    return (knee[0] - RADIUS_KNEE_FROM_TEXT[0], knee[1] - RADIUS_KNEE_FROM_TEXT[1])


PROFILE_KEEP = {
    "PlateLenDim": (0.025, PROFILE_CENTER[1]),
    "NorthEastX": _planned(0.045, 0.105),
    "NorthWestX": _planned(0.100, 0.115),
    "SouthWestX": _planned(0.104, 0.258),
    "SouthEastX": _planned(0.045, 0.259),
    # Radial rays must meet actual trimmed corners, not circle extensions.
    # CornerNE/R10 is left and CornerNW/R8 is right in this view.  Keep
    # their shelves down/outward from the fillet centres so native radius
    # arrows remain on the trimmed arcs, not their circle extensions.
    "CornerNER": _planned(0.045, 0.139),
    "CornerNWR": _planned(0.137, 0.110),
    "CornerSWR": _planned(0.110, 0.249),
    # R12's arrow lands at its arc's middle (corner_radius_text_xy); its
    # text stands between the 223.4 south witness and the 24.0 line.
    "CornerSER": corner_radius_text_xy("SE"),
}
FEATURE_KEEP = {
    # Short lines (12 characters, ~34 mm at most) between the 195.09 line
    # (x 0.130) and the plate's west edge (x 0.1679): on three the 50 mm
    # "OPEN TO NORTH EDGE" ran through both (8783776d).  The block stands on
    # its shelf (y 0.1438 at r1) and grows up, 5.6 mm a line, under the
    # 13.12 row.
    "PivotBearingReliefDia": _planned(0.1490, 0.155),
    "PostMountWestX": _planned(0.150, 0.185),
    "PostMountWestZ": _planned(0.225, 0.175),
    "PostMountEastX": _planned(0.205, 0.185),
    "PostMountEastZ": _planned(0.130, 0.175),
}
NOTCH_KEEP = {
    # Pivot-to-north-edge lives here, sharing the 205.81 pivot witness: in the
    # profile the R8 corner ray has no path that clears this dimension.
    "NorthEdgeZ": _planned(0.270, 0.150),
    # Text between its witnesses: outside, it read as spanning from the corner.
    "CapECx": _planned(0.2652, 0.258),
    # 9 mm left of r1's line (0.305): PLAN_DROP brings its pivot witness down
    # beside section A-A's PlateThk text (x >= 0.3035), and the pivot relief
    # note stands right of the line (RELIEF_NOTE_XY).
    "CapECz": _planned(0.296, 0.180),
    # r15 native envelope: the shelf is 2.8049 mm below the position;
    # on the left it ends 10.0455 mm to the right.  Aim down-left at the
    # physical concave cap, below the 33.00 line (y 246.2219 mm).
    # The measured 16.916 mm text block needs this lower station: at y224
    # the plan's left outline is x245.4, not x248.  Here both it and the
    # neighbouring x225 station line clear the text by at least 2 mm.
    # Saved-envelope prediction only; require a new native sheet eye proof.
    "CapEDia": _planned(0.2355, 0.209),
}
SECTION_KEEP = {
    # Outside its witnesses, the text hangs LEFT of the dimension line (away
    # from the plate), right edge on the line and centred on this y.  The
    # three lines (~26 x 15.3 mm) sit in x 0.3035..0.3295, y 0.1213..0.1366:
    # under the 205.81 witness (0.1379).  The flush widest line sits above
    # the top witness, the set-back last line beside the arrowhead (aa9766da:
    # "AS SUPPLIED" there ran its D into it).
    "PlateThk": _shifted(0.300, 0.114),
    # Text right of the dimension line on its shelf, over the strip's head:
    # with the relief now at the head, the shelf (~0.132) stands over the
    # upper arrowhead (top ~0.1302) and the text 2 mm clear of it.
    "PivotBearingReliefDepth": _shifted(0.365, 0.1195),
}

# Tip-block hold-down hole (user ruling 2026-09-29): its 10.45 station from
# the pivot bore is too small to dimension at 1:2 beside the relief, so
# DETAIL B enlarges the pivot-to-hole region of the hole-location plan to 2:1
# and carries HoldDownZ and HoldDownX.  The detail inherits the plan's
# hidden-lines-removed style: the counterbore is on the underside, and its
# size is stated by the native Hole Wizard callout on section C-C, where it
# shows in solid lines.
#
# The free band is x 0.0127..0.216 under the plan captions (y <= 0.0805)
# and above the bottom border (y >= 0.0127).  Run e86bf319 put the detail in
# its right half, where the title block (x >= 0.216, y <= 0.066) boxed its
# callouts in and its native label fell 8.9 mm through the bottom border.
# So the detail takes the band's left half and section C-C its right half.
# Sheet +x is model +x (west) and sheet +y is model -z (south) in these plans.
DETAIL_MODEL_Z = -6.0  # detail circle centre, between the pivot and the hole
DETAIL_RADIUS_MM = 12.0
DETAIL_SCALE = (2, 1)
# The former B letter stood 0.28 mm off the relief-width arrow and 0.62 mm
# over the pivot station witness. Its native anchor now puts the printed
# box at about [189.2,138.4]..[192.8,144.6] mm, clear of both and the circle.
DETAIL_PARENT_LETTER_XY = (0.188, 0.145)
_DETAIL_S = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
# The layout audit boxes a detail view by its native outline, which run
# eaafbc73 measured at the circle plus 10.4 mm a side ([53.6, 9.6]..
# [122.4, 78.4] mm around a 48 mm circle): it crossed the 9.7 mm zone border
# by 0.1 and ran 3.5 into the relief note.  Centred here, the outline sits
# at [49.1, 10.6]..[117.9, 79.4]: right of the label, under the plan
# captions (80.5) and 2.1 short of the note.
DETAIL_CENTER = (0.0835, 0.045)
DETAIL_OUTLINE_PAD = 0.0104
DETAIL_SHEET_RADIUS = DETAIL_RADIUS_MM * _DETAIL_S
DETAIL_PIVOT_Y = DETAIL_CENTER[1] + DETAIL_MODEL_Z * _DETAIL_S
DETAIL_HOLDDOWN_Y = DETAIL_CENTER[1] + (DETAIL_MODEL_Z - HOLDDOWN_LOCAL_Z) * _DETAIL_S
DETAIL_HOLDDOWN_X = DETAIL_CENTER[0] + HOLDDOWN_LOCAL_X * _DETAIL_S
# Between its extension lines a vertical dimension's text is CENTRED on its
# dimension line, which then runs through it (81788ce9: "11.|00"); outside
# them the text hangs outward, one edge on the line, centred on the keep y.
# So HoldDownZ stands LEFT of the detail outline (x 0.0491), its text above
# the hole's extension line, hanging left toward the border (0.0127) and
# above the detail label, leaving the band's right half to section C-C.
# HoldDownX (1.00, pivot bore to hole, 2 mm apart at 2:1) is far too short
# to hold its text, so the text hangs off its dimension line to sheet-right.
# Inside the circle it has no clean home: above the hole's rim (0.0634) the
# ~18.5 mm "1.00 ±0.1" ran out through the detail outline (run
# 20260930T030604208Z, machinist review 2026-09-30), and in the band under
# the rim the plate's east edge struck through its "0.1" (run
# 20260930T041147948Z).  So the text stands OUTSIDE the circle, right of
# it, and its dimension line runs out across the plate edge and the outline
# (user ruling 2026-09-30).  On that run the audit read the text frame
# (" 1.00 ±0.1 ", spaces included) 21.96 x 3.5 mm, centred on the keep x
# and standing on the dimension line, 2.78 mm under the keep y.  Here the
# line passes 1.1 mm under the hole's rim, the frame's lower-left corner
# stands 1 mm off the circle and its right end 4 mm short of section C-C's
# view box.
HOLDDOWN_X_TEXT_SIZE = (0.02196, 0.0035)
HOLDDOWN_X_LINE_DROP = 0.00278
HOLDDOWN_X_LINE_Y = (
    DETAIL_HOLDDOWN_Y - HOLDDOWN_CLEARANCE_DIA / 2.0 * _DETAIL_S - 0.0011
)
_HOLDDOWN_X_TEXT_X = (
    DETAIL_CENTER[0]
    + math.sqrt(
        (DETAIL_SHEET_RADIUS + 0.001) ** 2 - (HOLDDOWN_X_LINE_Y - DETAIL_CENTER[1]) ** 2
    )
    + HOLDDOWN_X_TEXT_SIZE[0] / 2.0
)
DETAIL_KEEP = {
    "HoldDownZ": (0.044, DETAIL_HOLDDOWN_Y + 0.0045),
    "HoldDownX": (_HOLDDOWN_X_TEXT_X, HOLDDOWN_X_LINE_Y + HOLDDOWN_X_LINE_DROP),
}
# The native "DETAIL B / SCALE 2:1" label, moved by its measured extent:
# lower left of its box, in the band's lower-left corner.  0.5 mm under r1's
# 0.015: HoldDownZ's arrow stood 1.91 mm over the label's text (layout audit
# arrow-near-text, clearance 2.0).
DETAIL_LABEL_LOWER_LEFT = (0.016, 0.0145)
# The pivot relief-fit note (2.5 mm text, six rows of at most 23
# characters), anchored by its upper-left corner in the open field over
# section A-A: right of the 213.56 dimension line (x 0.296), over the
# PlateThk text (top 0.1366), under the isometric caption.  Its leader
# leaves the note's right end and drops to the top relief's floor on the
# left-hand piece (relief_floor_tip_xy), now at A-A's head: rule 7, a
# matched fit is flagged at the feature (machinist review r1: under section
# C-C it read as C-C's).  The note's right end (~0.357) stands over the
# left-hand floor, so the leader falls nearly straight, between the seat's
# Ra symbol (x <= ~0.353) and the TOP FACE label on the right-hand piece.
# The layout audit boxes the note from its text to its tip (r2 of this fix:
# 0.2999..0.3633 x 0.1259..0.1654), so no other note may stand over the
# strip left of the tip.
# r3 put the top row on the 213.56 text (bottom ~0.169, right end ~0.3025):
# the note's top stands under it, its bottom row (~0.141) over the PlateThk
# text.
# r11 left 2.68 mm to the 213.56 text; 1.2 mm lower clears the 3.57 mm
# text-separation threshold while preserving the relief-floor leader route.
RELIEF_NOTE_XY = (0.300, 0.1653)
# The leader's tip, this far (model mm) into the relief floor from the bore
# wall: mid-floor (the floor runs 2.075 from the bore to the relief wall), so
# the leader meets the floor through the relief's open air, off the hatch.
RELIEF_TIP_INSET_MM = 1.0
# The isometric's caption, 22 mm higher than r1's 0.158 (still 9 mm under
# the isometric's ink, ~0.189), to free the field the relief note stands in.
ISO_CAPTION_UPPER_LEFT = (0.315, 0.180)
# The MHA-DT-VN-61 named-exception note (2.5 mm text, one line), anchored
# upper-left in the empty band above the title block (0.066): right of the
# plan caption row (x <= 0.2185) and left of the A-A label (x >= 0.342). A
# sheet must state the shortfall pending ruling #1019 (codex review of
# 68565ace, blocker B1).
ENGAGEMENT_NOTE_XY = (0.222, 0.0795)
# SECTION C-C cuts across the plate through the hold-down hole's axis, so
# the counterbore opening from the underside shows in solid lines and the
# native Hole Wizard callout lands on its wall.  Its cutting line lives on
# the 1:2 plate-profile plan, not in detail B (there it lay ON the hole's
# extension line).  On the plan the default arrows (looking north,
# sheet-down) ran beside the 8.0 extension line and through the R8 leader,
# so the cut looks SOUTH (arrows sheet-up).
#
# The line runs PAST both plate edges (a full section, 27.06 mm across at
# the hold-down station): as a +-9 mm partial cut its sheet-up arrows sat
# inside the plate, and the west letter, 42..55 mm south of the cut where the
# plate flares, landed on the sloped west edge (Main's eye-pass of 8783776d).
# Each end clears its edge at the letter's far station by the letter's half
# width (5.5 model mm at 1:2) plus 1.5.
HOLDDOWN_SECTION_LINE_X_MM = (-26.0, 24.0)
# 3:2, full width, cropped to the strip: the plate edge-on, 26.79 x 6.35 at
# the hold-down station.  At 1:1 (through r8) the Ø3.05/Ø5.56 step was 2.85
# and 3.5 mm of sheet, and machinist review r8 (run 20261019T005546454Z, two
# of three runs, confirmed) read the counterbore as opening on the TOP FACE
# label's side.  Uncropped, the section's outline is the whole plate seen
# past the cut (r8: 71 x 17.5 mm at 1:1), across detail B and into the
# title block.  A fence HOLDDOWN_CROP_MARGIN_MM (model) outside the strip
# crops the view to the strip, with no crop boundary drawn: the fence lies
# off the part, so every printed edge is a real one.  GetOutline pads the
# cropped view 10.95 mm across and 6.86 mm up and down past the strip
# itself, whatever the fence (r9 at a 1.0 mm fence, r10 at 0.5, both 2:1).
# The layout audit holds foreign text out of that padded box, 2 mm inset,
# and the blocking audit the native label within 1.5 mm.  At 2:1 (r10, run
# 20261019T025545367Z) the label under it, detail B's HoldDownX text left of
# it and the title block right of the callout left no place for the strip.
HOLDDOWN_SECTION_SCALE = (3, 2)
HOLDDOWN_CROP_MARGIN_MM = 0.25
# The strip's lower-left (east underside) corner on the sheet, where the
# view is moved once cropped.  Detail B's HoldDownX text (x ..0.1300, y
# 0.0498..0.0533) clears C-C's padded box both ways: its inset left 0.1306
# stands right of the text's end, its inset top 0.0496 under the text's
# foot.  The padded box's foot (0.0283) stands 0.7 mm over the native
# label's top (0.0291), inside the blocking audit's 1.5 mm.
HOLDDOWN_STRIP_LOWER_LEFT = (0.1395, 0.0352)
# The hold-down callout, above and right of the hole: DRILL Ø3.05 THRU ALL,
# the Ø5.56 counterbore row and its 3.50 depth, then FROM UNDERSIDE and the
# mate (HOLDDOWN_CALLOUT_BELOW).  SolidWorks centres each row on the
# requested point, the second row's baseline on its y; the leader leaves
# the last row's underline at its left end, 1.6 mm before the widest row
# (r8: rows 0.0696..0.0528 for y 0.064, underline from 0.1371 for x
# 0.175).  The leader lands on the counterbore's sheet-right wall at the
# underside (r8's tip).  At 1:1 (r8) that line ran across the strip's left
# piece; here the underline's left end (~0.1564, y 0.0545) stands up and
# left of the hole so the leader drops through the Ø3.05 hole into the
# counterbore, ~1.1 mm clear of the hole's left wall at the top face and of
# its right wall at the step.  The block's right end (~0.209) stands 7 mm
# off the title block, its top row (~0.0748) 5.7 mm under the plan
# captions (0.0805).
HOLDDOWN_CALLOUT_XY = (0.1830, 0.0657)
# Face labels on both sections (machinist review r3 blocker): both sections
# look south (sheet-up arrows), so each draws the top face at its head and
# the underside at its foot (machinist review of e04fd60: A-A looking north
# drew the plate the other way up from C-C).  With no face named a reader
# cannot tell the relief (top) from the counterbore (underside).  Each label
# is a pointer note on its face: (view key, text, model x candidates in mm, model
# y in mm, which candidate -- the one furthest "max" right or "min" left on
# the sheet -- and the note's upper-left corner relative to the tip).  A
# label's text is 22.1 (TOP FACE) / 24.7 (UNDERSIDE) x 3.6 mm (r8).  Each
# tip stands ~2 mm beyond one end of its text, so the leader leaves that end
# without running back through the letters (r6: two leader-through-own-text
# with tips over the text's span).  The layout audit boxes a note with its
# leader, text to tip.  Positions are measured on r3..r8's renders; the tip
# is projected on the face.  A-A's TOP FACE stands over the right-hand piece,
# right of the relief note's text-to-tip box (x <= 0.3637) and over the
# (0.25) text (top ~0.1352); C-C's UNDERSIDE names the face
# its callout's FROM UNDERSIDE names.  No field right of C-C's strip
# holds a 22 mm label short of the hold-down callout and the title block.
FACE_LABELS = (
    # Over A-A's strip, starting 2 mm right of its tip on the right-hand
    # piece's top face (model 5.25..8.95 outboard of the relief).
    ("A-A", TOP_FACE_LABEL, (-6.8, 7.5), PLATE_THICKNESS, "max", (0.002, 0.01815)),
    # Under C-C's strip, left of its native label: the tip on the left
    # piece's underside (0.1463, 0.0352), the text 0.1198..0.1445 x
    # 0.0288..0.0324, 2.0 mm right of detail B's outline (0.1179) and 4.0 mm
    # left of the native label; the leader rises from the text's right end.
    (
        "C-C",
        UNDERSIDE_LABEL,
        (HOLDDOWN_LOCAL_X - 11.1, HOLDDOWN_LOCAL_X + 11.1),
        0.0,
        "min",
        (-0.0265, -0.0028),
    ),
)
# Rows printed under native hole callouts (swDimensionTextCalloutBelow).
# Each tight band names its mate at its own callout (rule 4; machinist
# review r1 blocker: the +-0.1 stations named none).
POST_MOUNT_CALLOUT_BELOW = (POST_MOUNT_LOCATING_CALLOUT,)
# The post-mount taps' callout over the hole-location plan.  The block is
# centred on the requested point: r3's four rows ran from the inner border
# (top 0.2665, ~0.3 mm air) to their underline at 0.2453, 6.6 mm over the
# plate's top edge (0.2387).  The underline runs 92 mm under the long
# break row: r5, 3 mm lower, ran it (0.1530..0.2454 at y 0.2424) across
# the notch view (x 0.2394 up, top 0.2444).  2 mm lower than r3 and 9 mm
# left, the underline stops 3 mm short of that view.
POST_MOUNT_CALLOUT_XY = (0.191, 0.2545)
# The reamed pivot bore's callout, below the A-A cutting line between its
# arrows: right of the plate the 189.26 dimension line crosses any callout
# wider than ~40 mm.  Its fit row hangs under it, over the plan caption row
# (top 0.085).
# r11 left 2.16 mm to the A identifier; 2 mm lower gives more than one
# text-height of separation without crowding the plan caption.
PIVOT_BORE_CALLOUT_XY = (0.215, 0.097)
# The lock-notch caption sits directly under its own view, not on the plan
# caption row (aa9766da printed it there, where it read as a section's
# caption).  Its 59.7 x 4.8 mm box, anchored upper-left and centred under
# the notch plan, clears the 7.0 arrow tip (y 0.1276 at r1, less PLAN_DROP).
NOTCH_CAPTION_UPPER_LEFT = (NOTCH_CENTER[0] - 0.02985, _planned(0.0, 0.1255)[1])


def plate_edge_mm(z_mm: float, side: int) -> float:
    """Model x of the plate's straight east (-1) / west (+1) edge at ``z_mm``."""
    run = (_part.NORTH_OVERHANG - z_mm) / _part.PLATE_LEN
    if side < 0:
        return -(_part.HALF_WIDTH_N + (_part.EAST_HALF_S - _part.HALF_WIDTH_N) * run)
    return _part.WEST_HALF_N + (_part.WEST_HALF_S - _part.WEST_HALF_N) * run


def holddown_strip_box() -> tuple[float, float, float, float]:
    """Section C-C's strip on the sheet (x0, y0, x1, y1) once placed: the
    east edge at the left (looking south, sheet +x is model +x), the
    underside at the foot."""
    scale = HOLDDOWN_SECTION_SCALE[0] / HOLDDOWN_SECTION_SCALE[1] / 1000.0
    width = plate_edge_mm(HOLDDOWN_LOCAL_Z, 1) - plate_edge_mm(HOLDDOWN_LOCAL_Z, -1)
    x0, y0 = HOLDDOWN_STRIP_LOWER_LEFT
    return (x0, y0, x0 + width * scale, y0 + PLATE_THICKNESS * scale)


def holddown_hole_sheet_x() -> float:
    """The hold-down hole's axis on section C-C's placed strip."""
    scale = HOLDDOWN_SECTION_SCALE[0] / HOLDDOWN_SECTION_SCALE[1] / 1000.0
    east = plate_edge_mm(HOLDDOWN_LOCAL_Z, -1)
    return HOLDDOWN_STRIP_LOWER_LEFT[0] + (HOLDDOWN_LOCAL_X - east) * scale


# The native label: GetExtent 46.2 x 16.45 mm from the requested lower-left
# (r10: 0.15078..0.19694 x 0.01262..0.02907 for (0.1507, 0.0126)), which the
# blocking audit reads; the PDF prints it 2.0 mm left of and 1.7 mm over
# that, 45.9 x 14.6 (r8).  Under the strip, right of C-C's UNDERSIDE label:
# printed 0.1485..0.1944 x 0.0143..0.0289, 4.0 mm right of that label's
# text, its top 6.3 mm under the strip's foot, 1.6 mm over the border.
HOLDDOWN_SECTION_LABEL_LOWER_LEFT = (0.1505, 0.0126)


def holddown_section_line_model_points() -> tuple[tuple[float, float, float], ...]:
    """The C-C cutting line's ends, part metres, past both edges at the hole."""
    return tuple(
        (x / 1000.0, PLATE_THICKNESS / 1000.0, HOLDDOWN_LOCAL_Z / 1000.0)
        for x in HOLDDOWN_SECTION_LINE_X_MM
    )




def _set_end_only_section_lines(drawing_model: Any) -> None:
    """Keep the pivot cut distinct from the coincident station witnesses (#1029)."""
    # swDetailingSectionViewLineStyleDisplay = StandardWithoutConnector.
    # Retain the actual full cutting plane; only its connector ink is omitted.
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceInteger(542, 0, 1):
        raise RuntimeError("failed to set end-only section cutting lines")
    if extension.GetUserPreferenceInteger(542, 0) != 1:
        raise RuntimeError("section cutting-line style did not persist")


def _place_detail_parent_letter(adapter: Any, parent: Any) -> None:
    circles = tuple(_read_member(_early_bound(parent, "IView"), "GetDetailCircles") or ())
    if len(circles) != 1:
        raise RuntimeError(f"expected one detail circle, found {len(circles)}")
    circle = _early_bound(circles[0], "IDetailCircle")
    if circle.GetLabel() != "B":
        raise RuntimeError("expected detail B on the hole-location plan")
    circle.SetLabelPosition(*DETAIL_PARENT_LETTER_XY)  # VT_VOID; prove by readback.
    rebuild_drawing(adapter, label="place detail B parent letter")
    actual = tuple(float(value) for value in circle.GetLabelPosition())
    if (
        len(actual) != 2
        or not all(math.isfinite(value) for value in actual)
        or math.dist(actual, DETAIL_PARENT_LETTER_XY) > 1e-8
    ):
        raise RuntimeError(f"detail B parent letter did not persist: {actual}")


_COSMETIC_THREAD_LAYER = "COSMETIC-THREADS-HIDDEN"


def _hide_profile_cosmetic_threads(adapter: Any, view: Any) -> None:
    """Hide the redundant model cosmetic-thread callout in the profile view."""
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    if layer is None:
        if (
            int(
                manager.AddLayer(
                    _COSMETIC_THREAD_LAYER,
                    "cosmetic thread ink hidden in profile view",
                    0,
                    0,
                    0,
                )
            )
            != 1
        ):
            raise RuntimeError("failed to add hidden cosmetic-thread layer")
        layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("cosmetic-thread layer did not remain hidden")

    hidden = 0
    hidden_callouts = 0
    for raw_annotation in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != 1:  # swCosmeticThread
            continue
        annotation.Layer = _COSMETIC_THREAD_LAYER
        if str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
            raise RuntimeError("profile cosmetic thread refused the hidden layer")
        thread = _early_bound(annotation.GetSpecificAnnotation(), "ICThread")
        raw_callout = _read_member(thread, "ThreadCallout")
        if raw_callout is not None:
            callout = _early_bound(raw_callout, "INote")
            callout_annotation = _early_bound(
                _read_member(callout, "GetAnnotation"), "IAnnotation"
            )
            callout_annotation.Layer = _COSMETIC_THREAD_LAYER
            if str(callout_annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
                raise RuntimeError("profile thread callout refused the hidden layer")
            hidden_callouts += 1
        hidden += 1
    if not hidden:
        raise RuntimeError("profile view has no cosmetic thread to hide")
    if not hidden_callouts:
        raise RuntimeError("profile cosmetic threads have no callout note to hide")
    rebuild_drawing(adapter, label="hide profile cosmetic threads")


def _position_section_label(adapter: Any, section: Any) -> None:
    """Keep the native section caption below, rather than inside, the section."""
    notes = tuple(_read_member(section, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native section label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    target = (*SECTION_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*target):
        raise RuntimeError("failed to position native section label")
    adapter.currentModel.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if max(abs(actual[i] - target[i]) for i in range(3)) > 1e-8:
        raise RuntimeError(
            f"native section label position did not persist: {actual}; "
            f"requested={target}"
        )


# INote.GetExtent is read off the drawing as displayed, to the pixel: every
# maximised 1280x752 seat (2.1 px/mm) read detail B's box at the same point,
# 0.22/-0.16 mm off its request, and a 1024x640 one (0.95 px/mm) left it
# 0.70/-0.39 mm off after both corrections -- each residual under one pixel.
# The label is moved and read zoomed onto its own box, plus this margin, so
# a pixel is about a tenth of a millimetre whatever the seat's window.
VIEW_LABEL_ZOOM_MARGIN = 0.005


def _position_view_label(
    adapter: Any,
    view: Any,
    lower_left: tuple[float, float],
    *,
    label: str,
) -> None:
    """Move a view's native label so its box's lower-left lands at ``lower_left``.

    The label's anchor is not its box corner, so the move is measured: read
    ``INote.GetExtent``, shift the anchor by the corner's error, read back,
    all zoomed onto the requested box (:data:`VIEW_LABEL_ZOOM_MARGIN`).
    The sheet scale is pinned first; finalization re-applying it must not
    move a dynamic label after this readback.  The script's only notes in
    these views are the face labels (:data:`FACE_LABELS`); the native label
    is the view's one other note.
    """
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError(f"cannot pin sheet scale before {label} placement")
    face_labels = {text for _key, text, *_ in FACE_LABELS}
    notes = tuple(
        note
        for note in (
            _early_bound(item, "INote") for item in _read_member(view, "GetNotes") or ()
        )
        if str(note.GetText()) not in face_labels
    )
    if len(notes) != 1:
        raise RuntimeError(f"expected one native {label}, found {len(notes)} notes")
    note = notes[0]
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    extent = tuple(float(v) for v in note.GetExtent())
    size = (extent[3] - extent[0], extent[4] - extent[1])
    centre = (lower_left[0] + size[0] / 2.0, lower_left[1] + size[1] / 2.0)
    with _zoomed_on(adapter, centre, max(size) / 2.0 + VIEW_LABEL_ZOOM_MARGIN):
        for _attempt in range(2):
            extent = tuple(float(v) for v in note.GetExtent())
            error = (lower_left[0] - extent[0], lower_left[1] - extent[1])
            if max(abs(error[0]), abs(error[1])) < 0.0002:
                break
            anchor = tuple(float(v) for v in _read_member(annotation, "GetPosition"))
            moved = (anchor[0] + error[0], anchor[1] + error[1], 0.0)
            if not annotation.SetPosition2(*moved):
                raise RuntimeError(f"failed to position native {label}")
            adapter.currentModel.EditRebuild3()
        extent = tuple(float(v) for v in note.GetExtent())
    print(f"{label}: requested lower-left={lower_left} extent={extent}")
    if max(abs(lower_left[0] - extent[0]), abs(lower_left[1] - extent[1])) > 0.0005:
        raise RuntimeError(
            f"native {label} landed at {extent[:2]}, requested {lower_left}"
        )


def _create_detail_view(
    adapter: Any,
    parent_view: Any,
    *,
    model_center_mm: tuple[float, float, float],
    radius_mm: float,
    view_xy: tuple[float, float],
    detail_label: str,
    scale: tuple[int, int],
    label: str,
) -> Any:
    """Create a circular detail view around one model point of ``parent_view``.

    The circle is sketched in the parent view's own sketch space: the model
    point is projected to the sheet, then through the sketch transform, the same
    path ``create_section_view`` uses for its cutting line.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    if not ddoc.ActivateView(view_name(adapter, parent_view)):
        raise RuntimeError(f"failed to activate detail parent view ({label})")
    draw.ClearSelection2(True)
    center_m = tuple(value / 1000.0 for value in model_center_mm)
    rim_m = (center_m[0] + radius_mm / 1000.0, center_m[1], center_m[2])
    sheet = [
        model_point_in_view(adapter, parent_view, point, label=f"{label} {name}")
        for name, point in (("centre", center_m), ("rim", rim_m))
    ]
    sketch = _early_bound(_early_bound(parent_view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in sheet:
        point = _early_bound(
            math_utility.CreatePoint(double_array([float(x), float(y), 0.0])),
            "IMathPoint",
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    previous_add_to_db = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        circle = sketch_manager.CreateCircle(*points[0], *points[1])
    finally:
        sketch_manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError(f"failed to sketch the detail circle ({label})")
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    selection_data = selection_manager.CreateSelectData()
    selection_data.View = parent_view
    selectable = _sw_type_info.early_bound_or_flag(circle, "ISketchSegment", "Select4")
    if not selectable.Select4(False, selection_data):
        raise RuntimeError(f"failed to select the detail circle ({label})")
    detail = ddoc.CreateDetailViewAt4(
        float(view_xy[0]),
        float(view_xy[1]),
        0.0,
        0,  # swDetViewSTANDARD
        float(scale[0]),
        float(scale[1]),
        detail_label,
        1,  # swDetCircleCIRCLE
        True,  # FullOutline
        False,  # JaggedOutline
        False,  # NoOutline
        5,
    )
    draw.ClearSelection2(True)
    if detail is None:
        raise RuntimeError(f"CreateDetailViewAt4 returned no view ({label})")
    detail = _sw_type_info.early_bound_or_flag(
        detail, "IView", "SetViewPosition", "Position"
    )
    rebuild_drawing(adapter, label=f"create detail view {detail_label}")
    # CreateDetailViewAt4 puts the circle's centre on (x, y), but a fresh
    # detail view's readbacks lag its ink: on leaf 20260928T075849Z-1-882b4704
    # the outline was centred on the request while ModelToViewTransform
    # projected the centre 99 mm below it and Position read 99 mm below where
    # SetViewPosition later had to put it.  A loop that trusted the
    # projection moved a correctly placed view 99 mm up and needed a second
    # move to bring it back; on three #1105 leaves the projection then read
    # "on target" while the outline sat 99 mm high, and the view stayed there.
    # GetOutline is the ink (a 2:1 circle of DETAIL_RADIUS_MM, its label is
    # placed separately), and SetViewPosition moves that ink by the
    # difference from the Position it reads, so place by the outline and only
    # verify the projection afterwards, once it has caught up.
    landed = view_xy
    for attempt in range(4):
        outline = tuple(float(v) for v in detail.GetOutline())
        landed = ((outline[0] + outline[2]) / 2.0, (outline[1] + outline[3]) / 2.0)
        anchor = tuple(float(v) for v in detail.Position)
        print(
            f"detail {detail_label} pass {attempt}: anchor={anchor} "
            f"outline_centre={landed} outline={outline}"
        )
        if max(abs(landed[0] - view_xy[0]), abs(landed[1] - view_xy[1])) < 0.0002:
            break
        moved = (
            anchor[0] + view_xy[0] - landed[0],
            anchor[1] + view_xy[1] - landed[1],
        )
        if not detail.SetViewPosition(double_array(list(moved)), False):
            raise RuntimeError(f"failed to position the detail view ({label})")
        rebuild_drawing(adapter, label=f"place detail view {detail_label}")
    else:
        raise RuntimeError(
            f"detail {detail_label} outline centre stayed at {landed}, "
            f"requested {view_xy}"
        )
    # Every later placement on this view projects through its transform, so
    # it must agree with the ink before anything is hung on it.  Rebuilds
    # alone left it stale through three reads on 4 of 41 leaves (#1336); the
    # settle reads it behind the view barrier.
    projected = settle_detail_projection(
        adapter,
        detail,
        center_m,
        ink_xy=landed,
        tolerance_xy=(0.0005, 0.0005),
        label=f"detail {detail_label}",
    )
    print(
        f"detail {detail_label}: parent_sheet_centre={sheet[0]} "
        f"sketch_centre={points[0]} requested={view_xy} landed={landed} "
        f"projected={projected} outline={tuple(float(v) for v in detail.GetOutline())}"
    )
    return detail


def _look_section_south(
    adapter: Any, parent: Any, section: Any, cut: Any, *, z_mm: float, label: str
) -> None:
    """Point a plan section's arrows sheet-up (looking south), top face up.

    The view direction is read from the section's own projection, not from
    arrow-array layouts: with screen-right r and screen-up u, the sight line
    is u x r, so it runs along -z (south) exactly when model +x's sheet-x sign
    times model +y's sheet-y sign is positive.  Folded about the cutting line
    as projected, model +x stays sheet-right and the top face (+y) stands at
    the head; a view turned 180 degrees also looks south but reads both signs
    negative and is refused.  Both sections share this orientation (machinist
    review of e04fd60: A-A looking north drew the top face at its foot,
    opposite to C-C).
    """
    z = z_mm / 1000.0

    def steps() -> tuple[float, float]:
        base = model_point_in_view(
            adapter, section, (0.0, 0.003, z), label=f"{label} origin"
        )
        east = model_point_in_view(
            adapter, section, (0.001, 0.003, z), label=f"{label} +x"
        )
        up = model_point_in_view(adapter, section, (0.0, 0.004, z), label=f"{label} +y")
        return (float(east[0] - base[0]), float(up[1] - base[1]))

    east_step, up_step = steps()
    if east_step * up_step < 0.0:
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label=f"section {label} looks south")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError(f"section {label} cut direction did not persist")
        east_step, up_step = steps()
    if not (east_step > 0.0 and up_step > 0.0):
        raise RuntimeError(
            f"section {label} does not look south top face up: sheet steps of "
            f"model +x {east_step}, +y {up_step}"
        )
    print(
        f"section {label}: reversed={bool(cut.GetReversedCutDirection())} "
        f"east_step={east_step} up_step={up_step} "
        f"arrows={tuple(float(v) for v in (cut.GetArrowInfo() or ()))} "
        f"texts={tuple(float(v) for v in (cut.GetTextInfo() or ()))} "
        f"parent_line_info="
        f"{tuple(float(v) for v in (_early_bound(parent, 'IView').GetSectionLineInfo2() or ()))}"
    )


# A-A's bore axis at the underside on the sheet: the strip's foot, centred on
# SECTION_CENTER's y as when the section looked north (the PlateThk witness
# check reads this level and the top face's, 2 x 6.35 mm above it), and the
# axis where it stood then.  Reversed, SolidWorks kept the cut-plane origin
# (the underside) at its old sheet y, 0.12635, and drew the strip upward from
# there, 12.7 mm higher (run 20261023T181910549Z: relief floor at 0.13855).
PIVOT_SECTION_BORE_XY = (0.372, SECTION_SHIFT[1] + 0.09865)
# Looking south, A-A's outline is the whole plate south of the cut, 131 mm
# across at 2:1 (run 20261023T182942818Z: 28.2 mm past the border), as C-C's
# was (r9), so it is cropped to its strip the same way -- but only once its
# model dimensions are imported and curated: cropped first, the PlateThk
# import found nothing to attach to (run 20261023T185029293Z), its native
# witnesses standing at the plate's far south-west extent.  The carrier
# section crops after curating the same way.
PIVOT_CROP_MARGIN_MM = HOLDDOWN_CROP_MARGIN_MM


def _place_pivot_section(adapter: Any, section: Any) -> None:
    """Move A-A so its bore axis at the underside stands on
    PIVOT_SECTION_BORE_XY."""
    native = _early_bound(section, "IView")
    target = PIVOT_SECTION_BORE_XY
    for _attempt in range(3):
        origin = model_point_in_view(
            adapter, section, (0.0, 0.0, 0.0), label="A-A underside at the bore"
        )
        error = (target[0] - float(origin[0]), target[1] - float(origin[1]))
        if max(abs(error[0]), abs(error[1])) < 0.00005:
            break
        position = tuple(float(value) for value in native.Position)
        moved = [position[0] + error[0], position[1] + error[1]]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to move section A-A onto its strip station")
        rebuild_drawing(adapter, label="place section A-A strip")
    else:
        raise RuntimeError(
            f"section A-A bore axis landed at {tuple(origin[:2])}, requested {target}"
        )
    print(
        f"section A-A bore axis at the underside: {tuple(float(v) for v in origin[:2])} "
        f"outline={tuple(float(value) for value in native.GetOutline())}"
    )


def _crop_pivot_section(adapter: Any, section: Any) -> None:
    """Crop A-A to its strip, then prove its bore axis still stands on
    PIVOT_SECTION_BORE_XY."""
    corners = [
        model_point_in_view(
            adapter,
            section,
            (plate_edge_mm(0.0, side) / 1000.0, y_mm / 1000.0, 0.0),
            label=f"A-A strip corner {side:+d}",
        )
        for side, y_mm in ((-1, 0.0), (1, PLATE_THICKNESS))
    ]
    margin = PIVOT_CROP_MARGIN_MM * 2.0 / 1000.0
    xs = [float(corner[0]) for corner in corners]
    ys = [float(corner[1]) for corner in corners]
    fence = (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)
    _crop_section_to_fence(adapter, section, fence, label="A-A")
    _place_pivot_section(adapter, section)


def _look_holddown_section_south(
    adapter: Any, parent: Any, section: Any, cut: Any
) -> None:
    """Point section C-C's arrows sheet-up (looking south) and prove the strip.

    The strip must be the full width of the 6.35 plate at the hold-down
    station, at HOLDDOWN_SECTION_SCALE.
    """
    _look_section_south(
        adapter, parent, section, cut, z_mm=HOLDDOWN_LOCAL_Z, label="C-C"
    )
    low, high = _holddown_strip_corners(adapter, section)
    span = (high[0] - low[0], high[1] - low[1])
    print(f"section C-C: strip_span_m={span}")
    strip = holddown_strip_box()
    expected = (strip[2] - strip[0], strip[3] - strip[1])
    if any(abs(abs(span[i]) - expected[i]) > 1e-6 for i in (0, 1)):
        raise RuntimeError(
            f"section C-C strip is {span}, expected the "
            f"{HOLDDOWN_SECTION_SCALE[0]}:{HOLDDOWN_SECTION_SCALE[1]} {expected} full width"
        )


def _holddown_strip_corners(
    adapter: Any, section: Any
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Section C-C's strip as projected: (east underside, west top), sheet m."""
    z = HOLDDOWN_LOCAL_Z / 1000.0
    east = plate_edge_mm(HOLDDOWN_LOCAL_Z, -1) / 1000.0
    west = plate_edge_mm(HOLDDOWN_LOCAL_Z, +1) / 1000.0
    low = model_point_in_view(
        adapter, section, (east, 0.0, z), label="C-C strip east underside"
    )
    high = model_point_in_view(
        adapter, section, (west, PLATE_THICKNESS / 1000.0, z), label="C-C strip west top"
    )
    return (float(low[0]), float(low[1])), (float(high[0]), float(high[1]))


def _crop_section_to_fence(
    adapter: Any, section: Any, fence: tuple[float, float, float, float], *, label: str
) -> None:
    """Crop a section view to a sheet rectangle (left, foot, right, head).

    The fence is sketched direct to the database in the view's own sketch and
    handed to ``IView.Crop2`` with no boundary drawn (the rocker-arm
    support's VIEW B crop).  The crop is proved by the outline still holding
    the fence and shrinking.
    """
    left, foot, right, head = fence
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    native = _early_bound(section, "IView")
    if not ddoc.ActivateView(view_name(adapter, section)):
        raise RuntimeError(f"failed to activate section {label} for its crop")
    draw.ClearSelection2(True)
    before = tuple(float(value) for value in native.GetOutline())
    sketch = _early_bound(native.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    corners = []
    for x, y in ((left, head), (right, foot)):
        point = _early_bound(
            math_utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        corners.append(tuple(float(value) for value in projected.ArrayData))
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        segments = tuple(
            sketch_manager.CreateCornerRectangle(*corners[0], *corners[1]) or ()
        )
    finally:
        sketch_manager.AddToDB = previous_add_to_db
    if len(segments) != 4:
        raise RuntimeError(
            f"section {label} crop fence has {len(segments)} segments, not 4"
        )
    for segment in segments:
        if not _early_bound(segment, "ISketchSegment").Select4(True, None):
            raise RuntimeError(f"failed to select the section {label} crop fence")
    selected = int(draw.SelectionManager.GetSelectedObjectCount2(-1))
    # IView.Crop2 returns swCropViewErrors_e, where 1 is NoError.
    status = int(native.Crop2(False, True, 0))
    print(f"section {label} Crop2 status {status} with {selected} entities selected")
    if status != 1:
        raise RuntimeError(
            f"failed to crop section {label} to its strip: Crop2 status {status}"
        )
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    native.UpdateViewDisplayGeometry()
    if not bool(native.IsCropped()):
        raise RuntimeError(f"section {label} did not retain its crop")
    after = tuple(float(value) for value in native.GetOutline())
    print(f"section {label} outline: before crop {before}, after {after}")
    # The outline pads past the fence (r9: +19.9 mm across a 55.6 mm fence,
    # +11.7 mm up a 14.7 mm one; the carrier's and nameplate's crops read
    # the same), so the proof is the carrier section's: the outline still
    # holds the fence and lost the plate past it (r9: 131 -> 75.5 mm).
    if (
        len(after) != 4
        or after[0] > left
        or after[1] > foot
        or after[2] < right
        or after[3] < head
        or after[2] - after[0] > 0.75 * (before[2] - before[0])
        or after[2] - after[0] > (right - left) + 0.03
    ):
        raise RuntimeError(
            f"section {label} crop is not its strip fence "
            f"{(left, foot, right, head)}: outline {before} -> {after}"
        )


def _crop_and_place_holddown_section(adapter: Any, section: Any) -> None:
    """Crop section C-C to its strip, then move the strip onto
    HOLDDOWN_STRIP_LOWER_LEFT.

    The fence is a rectangle HOLDDOWN_CROP_MARGIN_MM (model) outside the
    strip (:func:`_crop_section_to_fence`); the move is proved by the
    projected strip landing on its target.
    """
    native = _early_bound(section, "IView")
    scale = HOLDDOWN_SECTION_SCALE[0] / HOLDDOWN_SECTION_SCALE[1] / 1000.0
    margin = HOLDDOWN_CROP_MARGIN_MM * scale
    low, high = _holddown_strip_corners(adapter, native)
    left, right = min(low[0], high[0]) - margin, max(low[0], high[0]) + margin
    foot, head = min(low[1], high[1]) - margin, max(low[1], high[1]) + margin
    _crop_section_to_fence(adapter, section, (left, foot, right, head), label="C-C")
    target = HOLDDOWN_STRIP_LOWER_LEFT
    for _attempt in range(3):
        low, high = _holddown_strip_corners(adapter, native)
        lower_left = (min(low[0], high[0]), min(low[1], high[1]))
        error = (target[0] - lower_left[0], target[1] - lower_left[1])
        if max(abs(error[0]), abs(error[1])) < 0.0001:
            break
        position = tuple(float(value) for value in native.Position)
        moved = [position[0] + error[0], position[1] + error[1]]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to move section C-C onto its strip target")
        rebuild_drawing(adapter, label="place section C-C strip")
    else:
        raise RuntimeError(
            f"section C-C strip landed at {lower_left}, requested {target}"
        )
    print(
        f"section C-C strip lower-left={lower_left} requested={target} "
        f"outline={tuple(float(value) for value in native.GetOutline())}"
    )


def callout_below_definitions(
    definitions: dict[int, str], rows: tuple[str, ...]
) -> dict[int, str]:
    """``rows`` in the CalloutBelow definition (8), every other part as read.

    swDimensionTextCalloutBelowDefinition (8) pairs with the writable
    swDimensionTextCalloutBelow (4); the prefix, suffix and above
    definitions (5, 6, 7) keep their Hole Wizard variables, so the size,
    depth and thread stay associative (draw_ch_channel_lever's
    _name_hole_mate).
    """
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected hole callout parts: {definitions!r}")
    if definitions[8].strip():
        raise RuntimeError(f"hole callout already prints below: {definitions!r}")
    return {**definitions, 8: "\n".join(rows)}


def holddown_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """HOLDDOWN_PROCESS in the native THRU row; the face and mate below.

    The process goes into the one part holding THRU, after any instance
    count, so the drilled size reads first and the counterbore row stays
    "⌴ Ø5.56 ↧3.50" (machinist review r1: "DRILL ⌴ Ø5.56" read as drilling
    the counterbore).
    """
    updated = callout_below_definitions(definitions, HOLDDOWN_CALLOUT_BELOW)
    thru_parts = [part for part in (5, 6, 7) if "THRU" in definitions[part].upper()]
    if len(thru_parts) != 1:
        raise RuntimeError(f"hold-down THRU row is not one upper part: {definitions!r}")
    part = thru_parts[0]
    text = definitions[part]
    count = re.match(r"\s*<NUM_INST>X ", text)
    updated[part] = (
        f"{text[: count.end()]}{HOLDDOWN_PROCESS} {text[count.end() :]}"
        if count
        else compose_hole_callout_prefix(HOLDDOWN_PROCESS, text)
    )
    return updated


def _omit_post_mount_thread_class(display: Any) -> None:
    """Rule 2: the title block owns class 2B; keep the native tap variables.

    The existing helper proves the prefix definition lost only its class
    token/dash.  Resolved-row readback also refuses a still-printed class.
    This changes no Hole Wizard thread metadata or model association.
    """
    # #912: remove this local wrapper/callsite once add_native_hole_callout
    # applies the existing omission helper and readback by default.
    if POST_MOUNT_SPEC.thread_class != "2B":
        raise RuntimeError(
            "v2 post-mount tapped holes: only title-block default class 2B "
            f"may be omitted, got {POST_MOUNT_SPEC.thread_class!r}"
        )
    omit_title_block_thread_class(display, label="v2 post-mount tapped holes")
    native = _early_bound(display, "IDisplayDimension")
    resolved = [str(native.GetText(part) or "") for part in (1, 2, 3, 4)]
    if any(POST_MOUNT_SPEC.thread_class in text for text in resolved):
        raise RuntimeError(
            f"v2 post-mount tapped holes: callout still prints its class: {resolved!r}"
        )


def _rewrite_hole_callout(
    display: Any,
    rewrite: Callable[[dict[int, str]], dict[int, str]],
    *,
    label: str,
) -> None:
    """Write ``rewrite(definitions)`` into a native hole callout; prove it.

    Only parts whose definition changes are written, each through its
    writable twin (definition 5..8 -> writable 1..4).  Multi-line text reads
    back with CR LF (draw_pd_support_bar), so both sides compare without CR.
    """
    native = _early_bound(display, "IDisplayDimension")

    def read(parts: tuple[int, ...]) -> dict[int, str]:
        return {
            part: str(native.GetText(part) or "").replace("\r", "") for part in parts
        }

    definitions = read((5, 6, 7, 8))
    updated = rewrite(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = read((5, 6, 7, 8))
    resolved = read((1, 2, 3, 4))
    if persisted != updated:
        raise RuntimeError(
            f"{label}: hole callout rows did not persist: "
            f"definitions={persisted!r}, expected={updated!r}, resolved={resolved!r}"
        )
    print(f"{label} callout: definitions={persisted!r} resolved={resolved!r}")


def _print_pivot_band_exactly(display: Any) -> None:
    """Print the pivot ream's size and band at the places they need, natively.

    The callout's ``<hw-diam>`` shows the Hole Wizard feature's band at the
    template's tolerance places, so the H7 band read "+.00/.00".
    ``SetPrecision3`` cannot set a hole callout's places;
    ``ICalloutLengthVariable`` can: the reamed .2500 and its band print the
    band's four places.
    """
    from win32com.client.dynamic import Dispatch as dynamic_dispatch  # noqa: PLC0415

    places = _tolerance_places(*_part.PIVOT_HOLE_BAND, display_unit=UNIT)
    for raw in display.GetHoleCalloutVariables() or ():
        if str(dynamic_dispatch(raw._oleobj_).VariableName) != "hw-diam":
            continue
        length = _early_bound(raw, "ICalloutLengthVariable")
        length.Precision = places
        length.TolerancePrecision = places
        if (int(length.Precision), int(length.TolerancePrecision)) != (places, places):
            raise RuntimeError("pivot reamed bore: places did not persist")
        return
    raise RuntimeError("pivot reamed bore: callout has no <hw-diam> variable")


# Hole Wizard callouts print three inch places (#290).
HOLDDOWN_CALLOUT_PRECISION = {"hw-thruholedia": 3, "hw-cbdia": 3, "hw-cbdepth": 3}


def _add_holddown_callout(adapter: Any, section: Any) -> Any:
    """The hold-down's native Hole Wizard callout, on its counterbore wall.

    Section C-C cuts through the hole's axis, so the counterbore opening from
    the underside shows in solid lines; the callout's leader lands on the
    counterbore wall on the callout's (sheet-right, model +x) side.  The
    callout names the face the counterbore is cut from and the mate its
    +-0.1 stations in detail B locate.
    """
    walls = _section_hole_walls(
        section,
        HOLDDOWN_CBORE_DIA / 2.0,
        center_x_mm=HOLDDOWN_LOCAL_X,
        label="hold-down counterbore",
    )
    display = add_native_hole_callout(
        adapter,
        section,
        callout_xy=HOLDDOWN_CALLOUT_XY,
        label="tip-block hold-down counterbored hole",
        edge=walls[1],
    )
    _rewrite_hole_callout(
        display,
        holddown_callout_definitions,
        label="tip-block hold-down counterbored hole",
    )
    set_hole_callout_precision(
        display, HOLDDOWN_CALLOUT_PRECISION, label="tip-block hold-down counterbored hole"
    )
    rebuild_drawing(adapter, label="hold-down callout rows")
    return display


def section_point_xy(
    adapter: Any,
    section: Any,
    model_xs_mm: tuple[float, ...],
    model_y_mm: float,
    model_z_mm: float,
    *,
    pick: str,
    label: str,
) -> tuple[float, float]:
    """Sheet point of the candidate model point furthest right ("max") or
    left ("min") on the sheet.

    A section's sheet x runs along model x one way or the other with its
    viewing direction, so a point on a named piece (the right-hand piece of
    A-A, say) is chosen by where it projects, not by its model sign.
    """
    candidates = [
        model_point_in_view(
            adapter,
            section,
            (x / 1000.0, model_y_mm / 1000.0, model_z_mm / 1000.0),
            label=f"{label} x={x:+.2f}",
        )
        for x in model_xs_mm
    ]
    chooser = {"max": max, "min": min}[pick]
    tip = chooser(candidates, key=lambda point: point[0])
    print(f"{label}: candidates={candidates} tip={tip[:2]}")
    return (float(tip[0]), float(tip[1]))


def relief_floor_tip_xy(adapter: Any, section: Any) -> tuple[float, float]:
    """Sheet point on the top relief's floor on A-A's left-hand piece,
    RELIEF_TIP_INSET_MM out from the pivot bore's wall.

    The section is cut on the pivot's axis (model z = 0), so the floor stands
    PIVOT_BEARING_RELIEF_DEPTH under the plate's top face either side of the
    bore.
    """
    x = PIVOT_HOLE_DIA / 2.0 + RELIEF_TIP_INSET_MM
    return section_point_xy(
        adapter,
        section,
        (-x, x),
        PLATE_THICKNESS - PIVOT_BEARING_RELIEF_DEPTH,
        0.0,
        pick="min",
        label="relief floor tip",
    )


def _add_face_labels(adapter: Any, sections: dict[str, Any]) -> None:
    """TOP FACE and UNDERSIDE pointer notes on sections A-A and C-C."""
    model_z_mm = {"A-A": 0.0, "C-C": HOLDDOWN_LOCAL_Z}
    for key, text, xs, model_y, pick, offset in FACE_LABELS:
        label = f"{key} {text.lower()} label"
        tip = section_point_xy(
            adapter,
            sections[key],
            xs,
            model_y,
            model_z_mm[key],
            pick=pick,
            label=label,
        )
        add_leader_note(
            adapter,
            text,
            text_xy=(tip[0] + offset[0], tip[1] + offset[1]),
            attach_xy=tip,
            label=label,
            view=sections[key],
            height=0.0025,
        )


def _visible_plan_controls(adapter: Any, view: Any) -> tuple[Any, Any]:
    """Return the pivot and post-mount rims from the plan view.

    The north-end and long-straight-side edges were dropped with the GD&T that
    referenced them (see ``build``) -- nothing else on this sheet attaches to
    them.
    """
    expected_radius_m = PIVOT_HOLE_DIA / 2000.0
    expected_mount_radius_m = blind_cut_dia_mm(POST_MOUNT_SPEC) / 2000.0
    pivot_edges: list[Any] = []
    mount_edges: list[Any] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: visible_component_entities(view, c, 1), default=()
            )
            or ()
        )
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            values = tuple(float(value) for value in curve.CircleParams)
            if abs(values[6] - expected_radius_m) <= 1e-6:
                pivot_edges.append(edge)
            if abs(values[6] - expected_mount_radius_m) <= 1e-6:
                mount_edges.append(edge)
    if not pivot_edges or len(mount_edges) < 2:
        raise RuntimeError("cone-platform plan view is missing pivot/mount controls")
    return pivot_edges[0], mount_edges[0]


# swSFSymType_e.swSFBasic: the any-process symbol (open vee, no bar).
SF_ANY_PROCESS = 0


def _set_any_process_finish(adapter: Any, symbol: Any, *, label: str) -> None:
    """Turn a broad-face finish into the any-process form.

    Both broad faces stay as the cold-finished stock supplies them (U41: the
    thickness is the stock's, "1/4 PLATE AS SUPPLIED"), so their roughness is
    met by any process.  The material-removal-required form asked the shop
    to cut faces whose thickness the same view keeps as supplied (machinist
    review of 8c9acd48, confirmed r2+r3 blocker).
    """
    native = _early_bound(symbol, "ISFSymbol")
    if not native.SetSymbol(SF_ANY_PROCESS, 0, False):
        raise RuntimeError(f"failed to set the any-process finish symbol ({label})")
    rebuild_drawing(adapter, label=f"{label} any-process symbol")
    if int(native.GetSymbol()) != SF_ANY_PROCESS:
        raise RuntimeError(f"any-process finish symbol did not persist ({label})")


def _horizontal_section_edge(
    view: Any, y_mm: float, *, label: str, prefer_right: bool = False
) -> Any:
    """Return a horizontal section edge on one broad-face station."""
    candidates: list[tuple[float, float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label=f"{label} section edges"):
        edge = _early_bound(raw_edge, "IEdge")
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = tuple(float(value) * 1000.0 for value in _early_bound(start, "IVertex").GetPoint())
        p1 = tuple(float(value) * 1000.0 for value in _early_bound(end, "IVertex").GetPoint())
        if abs(p0[1] - y_mm) <= 0.01 and abs(p1[1] - y_mm) <= 0.01:
            candidates.append((abs(p1[0] - p0[0]), 0.5 * (p0[0] + p1[0]), edge))
    if not candidates:
        raise RuntimeError(f"pivot section has no {label} edge at y={y_mm:.3f} mm")
    key_index = 1 if prefer_right else 0
    return max(candidates, key=lambda item: item[key_index])[2]


def _section_hole_walls(
    section: Any, radius_mm: float, *, center_x_mm: float, label: str
) -> dict[int, Any]:
    """Return the two vertical wall edges of a hole cut at its axis in a section.

    The section edges carry model coordinates; a hole whose axis stands at
    model x = center_x_mm shows its walls at center_x_mm -/+ radius, keyed
    -1 / +1.
    """
    walls: dict[int, Any] = {}
    for raw_edge in visible_view_entities(section, 1, label=f"{label} wall edges"):
        edge = _early_bound(raw_edge, "IEdge")
        start, end = edge.GetStartVertex(), edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = tuple(float(v) * 1000.0 for v in _early_bound(start, "IVertex").GetPoint())
        p1 = tuple(float(v) * 1000.0 for v in _early_bound(end, "IVertex").GetPoint())
        if abs(p0[1] - p1[1]) < 1.0:
            continue
        for side in (-1, 1):
            if all(abs(p[0] - (center_x_mm + side * radius_mm)) <= 0.01 for p in (p0, p1)):
                walls[side] = edge
                print(f"{label} wall {side:+d}: {p0} -> {p1}")
    if set(walls) != {-1, 1}:
        raise RuntimeError(f"{label}: section shows {len(walls)} walls, expected 2")
    return walls


def _add_section_hole_axis(
    adapter: Any, section: Any, radius_mm: float, *, center_x_mm: float, label: str
) -> None:
    """Draw a hole's axis between the two cut slices of a cut-face-only section.

    The cut-face-only section shows the hole as a bare gap; without its axis a
    reader takes one slice for an unrelated fragment.
    """
    walls = _section_hole_walls(section, radius_mm, center_x_mm=center_x_mm, label=label)
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, section)):
        raise RuntimeError(f"failed to activate the section for the {label} axis")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for index, side in enumerate((-1, 1)):
        data = selection_manager.CreateSelectData()
        data.View = section
        if not _early_bound(walls[side], "IEntity").Select4(index > 0, data):
            raise RuntimeError(f"failed to select {label} wall {side:+d}")
    if int(selection_manager.GetSelectedObjectCount2(-1)) != 2:
        raise RuntimeError(f"{label} axis needs exactly the two wall edges selected")
    before = len(tuple(_read_member(section, "GetCenterLines") or ()))
    centerline = ddoc.InsertCenterLine2()
    draw.ClearSelection2(True)
    if centerline is None:
        raise RuntimeError(f"failed to insert the {label} axis")
    rebuild_drawing(adapter, label=f"{label} axis")
    lines = tuple(_read_member(section, "GetCenterLines") or ())
    if len(lines) != before + 1:
        raise RuntimeError(f"{label} axis did not persist ({before} -> {len(lines)})")
    print(f"{label} centerlines: {len(lines)}")


def _section_edge_midpoint(
    adapter: Any, view: Any, edge: Any, *, label: str
) -> tuple[float, float]:
    """Return the sheet point at the middle of one broad-face section edge."""
    points = [
        tuple(float(value) for value in _early_bound(vertex, "IVertex").GetPoint())
        for vertex in (edge.GetStartVertex(), edge.GetEndVertex())
    ]
    middle = tuple(0.5 * (points[0][i] + points[1][i]) for i in range(3))
    if abs(middle[0]) * 1000.0 <= PIVOT_HOLE_DIA / 2.0 + 0.5:
        raise RuntimeError(f"{label} edge midpoint falls in the pivot hole: {middle}")
    sheet = model_point_in_view(adapter, view, middle, label=f"{label} edge midpoint")
    print(
        f"{label} finish attach: edge_model_m={points} middle_model_m={middle} "
        f"sheet_m=({sheet[0]:.5f},{sheet[1]:.5f})"
    )
    return (sheet[0], sheet[1])


def expected_corner_arcs(feature_name: str) -> int:
    """Visible plan arcs a corner fillet leaves: 2 where the W18 relief crosses it.

    Derived from the same overlap the part build credits in its fillet volume
    gate (``_north_fillet_relief_overlap``), so the drawing and the model agree
    on where the open relief splits a fillet's top edge.
    """
    label = feature_name.removeprefix("Corner")
    radius = {corner[0]: corner[3] for corner in _part.PLATE_CORNERS}[label]
    return 2 if _part._north_fillet_relief_overlap(label, radius) > 0.0 else 1


def check_corner_arc_plan(
    name: str, plan: list[tuple[float, float, float]], expected: int
) -> None:
    """Exactly the expected owned arcs, all on one plan circle (x, z, radius)."""
    if len(plan) != expected:
        raise RuntimeError(
            f"expected {expected} owned visible {name} arc(s) at corner station, "
            f"found {len(plan)}"
        )
    if any(math.dist(item, plan[0]) > 1e-8 for item in plan[1:]):
        raise RuntimeError(f"{name} owned arcs do not share one plan circle: {plan!r}")


def _assert_corner_radius_attachment(
    adapter: Any, view: Any, annotations: list[Any], *,
    name: str, feature_name: str, radius_m: float,
) -> None:
    """Prove a native radius dimension's arrow lies on its owned visible arc."""
    matches = [item for item in annotations if dimension_name(adapter, item) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one native {name} radius annotation")
    annotation = _early_bound(matches[0], "IAnnotation")
    # Imported fillet dimensions can return unsupported/null annotation entities.
    # Record that API honestly; model-dimension ownership below is authoritative.
    entities = annotation.GetAttachedEntities3()
    entity_types = annotation.GetAttachedEntityTypes()
    print(
        f"{name} annotation entities_none={entities is None} "
        f"entity_nulls={tuple(item is None for item in (entities or ()))} types={entity_types!r}"
    )
    dangling = annotation.IsDangling()
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    owner = _early_bound(dimension.GetFeatureOwner(), "IFeature")
    print(f"{name} native model dimension owner={owner.Name!r} dangling={dangling!r}")
    if dangling is not False or str(owner.Name) != feature_name:
        raise RuntimeError(f"{name} is dangling or is not owned by native {feature_name}")
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    arrows = [
        tuple(float(value) for value in data.GetArrowHeadAtIndex2(index))
        for index in range(int(data.GetArrowHeadCount()))
    ]
    if len(arrows) != 1 or len(arrows[0]) < 3:
        raise RuntimeError(f"expected one {name} arrow tip, found {arrows}")
    arrow = arrows[0]
    visible = visible_view_entities(view, 1, label=f"{name} visible corner edges")
    centre_mm = corner_fillet_centre_mm(feature_name.removeprefix("Corner"))
    candidates = []
    for raw_face in owner.GetFaces() or ():
        face = _early_bound(raw_face, "IFace2")
        if str(_early_bound(face.GetFeature(), "IFeature").Name) != feature_name:
            continue
        for raw_edge in face.GetEdges() or ():
            edge = _early_bound(raw_edge, "IEdge")
            if not any(int(adapter.swApp.IsSame(edge, item)) == 1 for item in visible):
                continue
            if any(int(adapter.swApp.IsSame(edge, item[0])) == 1 for item in candidates):
                continue
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            circle = tuple(float(value) for value in curve.CircleParams)
            if abs(circle[6] - radius_m) > 1e-8:
                continue
            # The owned arc's centre must be this corner's, in model space;
            # sheet stations went stale whenever the plate moved on the sheet.
            if math.dist((circle[0] * 1000.0, circle[2] * 1000.0), centre_mm) > 0.01:
                continue
            center = model_point_in_view(adapter, view, circle[:3], label=f"{name} owned circle")
            candidates.append((edge, circle, center))
    # W18 (5db29554, run d9711228): the open pivot relief crosses the NW
    # fillet, so its plan arc is two physical edges on one circle -- one on
    # the 6.35 top, one on the 6.10 relief floor.  Every owned visible arc
    # must share the plan centre and radius; the arrow must land on one.
    plan = [(circle[0], circle[2], circle[6]) for _edge, circle, _center in candidates]
    check_corner_arc_plan(name, plan, expected_corner_arcs(feature_name))
    distances = []
    for edge, circle, center in candidates:
        # Invert the measured plan-view X/Z basis at this owned edge's model Y.
        px = model_point_in_view(adapter, view, (circle[0] + 0.001, circle[1], circle[2]), label=f"{name} X basis")
        pz = model_point_in_view(adapter, view, (circle[0], circle[1], circle[2] + 0.001), label=f"{name} Z basis")
        xx, xy = px[0] - center[0], px[1] - center[1]
        zx, zy = pz[0] - center[0], pz[1] - center[1]
        det = xx * zy - zx * xy
        if abs(det) < 1e-12:
            raise RuntimeError(f"{name} plan projection is singular")
        dx, dy = arrow[0] - center[0], arrow[1] - center[1]
        model_tip = (
            circle[0] + 0.001 * (dx * zy - zx * dy) / det,
            circle[1],
            circle[2] + 0.001 * (xx * dy - dx * xy) / det,
        )
        # IEdge, not ICurve: the closest point is on the trimmed physical edge.
        closest = tuple(float(value) for value in edge.GetClosestPointOn(*model_tip))
        trim = _early_bound(edge.GetCurveParams3(), "ICurveParamData")
        distance = math.dist(model_tip, closest[:3])
        distances.append(distance)
        print(
            f"{name} owned visible trimmed edge: arrow_sheet_m={arrow[:3]} radius_m={circle[6]} "
            f"center_model_m={circle[:3]} trim_u=({trim.UMinValue},{trim.UMaxValue}) "
            f"closest_u={closest[3]} arrow_model_m={model_tip} "
            f"closest_model_m={closest[:3]} distance_m={distance}"
        )
    if not min(distances) <= 0.00002:  # 0.01 mm on this 1:2 sheet; unchanged physical-edge bound.
        raise RuntimeError(f"{name} arrow does not land on its owned physical corner arc")
    # Which face's arc the arrow names: a reader should see the radius on the
    # 6.35 top outline, not the 6.10 relief floor (Main, 2026-09-24).
    hit = candidates[distances.index(min(distances))][1]
    _telemetry.info(
        f"{name} arrow lands on the arc at model y={hit[1] * 1000.0:.3f} mm "
        f"({len(candidates)} owned arc(s); plate top {PLATE_THICKNESS:.2f})"
    )


def _profile_corner_edges(adapter: Any, view: Any, index: int) -> tuple[Any, Any]:
    """Actual straight top-face supports; nearest segment if a notch splits one."""
    corners = _part.PLATE_CORNERS
    label, x, z, _radius = corners[index]
    result = []
    visible = visible_view_entities(view, 1, label=f"{label} virtual sharp supports")
    for neighbour in (corners[index - 1], corners[(index + 1) % len(corners)]):
        direction = (neighbour[1] - x, neighbour[2] - z)
        length = math.hypot(*direction)
        direction = (direction[0] / length, direction[1] / length)
        candidates = []
        for raw in visible:
            edge = _early_bound(raw, "IEdge")
            if not _early_bound(edge.GetCurve(), "ICurve").IsLine():
                continue
            vertices = (edge.GetStartVertex(), edge.GetEndVertex())
            if any(item is None for item in vertices):
                continue
            xyz = [
                tuple(
                    float(v) * 1000.0 for v in _early_bound(item, "IVertex").GetPoint()
                )
                for item in vertices
            ]
            if any(abs(point[1] - PLATE_THICKNESS) > 0.001 for point in xyz):
                continue
            plan = [(point[0], point[2]) for point in xyz]
            if math.dist(*plan) < 0.001:
                continue
            if any(
                abs((p[0] - x) * direction[1] - (p[1] - z) * direction[0]) > 0.001
                for p in plan
            ):
                continue
            candidates.append((min(math.dist(p, (x, z)) for p in plan), edge))
        if not candidates:
            raise RuntimeError(f"{label}: missing actual straight top-face support")
        result.append(min(candidates, key=lambda item: item[0])[1])
    if int(adapter.swApp.IsSame(*result)) != 0:
        raise RuntimeError(f"{label}: virtual sharp requires two different supports")
    return result[0], result[1]


def _virtual_sharp_witness_groups(view: Any) -> list[list[tuple[float, ...]]]:
    """Parse style3 straight-line groups observed in r23, without assuming a frame.

    Each group is five attributes, tag0, line count and six values per line.
    An empty arc trailer was absent in r23's single observed style3 group.
    Source placement is proved separately by the native Type4 point.
    """
    count, size = view.GetWitnessEntitiesCount()
    raw = tuple(float(v) for v in (view.GetWitnessGeomInfo() or ()))
    if not all(
        math.isfinite(value) and value >= 0 and int(value) == value
        for value in (count, size)
    ):
        raise RuntimeError("profile virtual sharp witness counts are invalid")
    if int(size) != len(raw) or not all(math.isfinite(v) for v in raw):
        raise RuntimeError("profile virtual sharp witness data has invalid size/values")
    if bool(count) != bool(raw):
        raise RuntimeError(
            "profile virtual sharp witness count disagrees with geometry"
        )
    groups = []
    offset = 0
    while offset < len(raw):
        if offset + 7 > len(raw):
            raise RuntimeError("profile virtual sharp witness line header is truncated")
        offset += 5  # colour, line style/weight, layer, override
        if raw[offset] != 0:
            raise RuntimeError(
                "profile virtual sharp witness geometry is not straight lines"
            )
        lines = int(raw[offset + 1])
        if lines < 0 or raw[offset + 1] != lines:
            raise RuntimeError("profile virtual sharp witness line count is invalid")
        offset += 2
        end = offset + lines * 6
        if end > len(raw):
            raise RuntimeError("profile virtual sharp witness lines are truncated")
        segments = [raw[i : i + 6] for i in range(offset, end, 6)]
        offset = end
        groups.append(segments)
    if sum(len(group) for group in groups) != int(count):
        raise RuntimeError(
            "profile virtual sharp witness entity count disagrees with lines"
        )
    return groups


def _insert_profile_virtual_sharp(adapter: Any, view: Any, index: int) -> None:
    """Require native Type4, profile ownership, source position and witness lines."""
    draw = _early_bound(adapter.currentModel, "IModelDoc2")
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    label, x, z, _radius = _part.PLATE_CORNERS[index]
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"{label}: cannot activate profile for virtual sharp")
    native = _early_bound(view, "IView")
    sketch = _early_bound(native.GetSketch(), "ISketch")
    creation_preference = _sw_type_info.constant("swDisplayVirtualSharps")
    application = _early_bound(adapter.swApp, "ISldWorks")
    factory = _early_bound(draw.SketchManager, "ISketchManager")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    expected = model_point_in_view(
        adapter,
        native,
        (x / 1000.0, PLATE_THICKNESS / 1000.0, z / 1000.0),
        label=f"{label} original PlateProfile sharp",
    )
    factory_coordinates = _transform_point(
        utility,
        (expected[0], expected[1], 0.0),
        transform,
        label=f"{label} source corner sheet to sketch",
    )

    def points():
        result = {}
        for raw in sketch.GetSketchPoints2() or ():
            point = _early_bound(raw, "ISketchPoint")
            key = tuple(int(v) for v in point.GetID())
            if key in result:
                raise RuntimeError(f"{label}: duplicate native sketch point ID")
            result[key] = point
        return result

    def snapshot(native_points):
        count, size = native.GetWitnessEntitiesCount()
        return {
            "point_count": len(native_points),
            "point_ids_types": [
                (key, int(point.Type)) for key, point in sorted(native_points.items())
            ],
            "witness_count": int(count),
            "witness_size": int(size),
            "raw_witness": tuple(float(v) for v in (native.GetWitnessGeomInfo() or ())),
            "virtual_sharp_xyz": [
                (key, (float(point.X), float(point.Y), float(point.Z)))
                for key, point in sorted(native_points.items())
                if int(point.Type) == 4
            ],
            # SDK SO_Miscellaneous describes creation at virtual intersections.
            # Observe only: this recipe must not establish a global seat baseline.
            "display_virtual_sharps_sdk_id": creation_preference,
            "display_virtual_sharps": bool(
                application.GetUserPreferenceToggle(creation_preference)
            ),
        }

    before = points()
    before_snapshot = snapshot(before)
    groups_before = _virtual_sharp_witness_groups(native)
    edges = _profile_corner_edges(adapter, native, index)
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    draw.ClearSelection2(True)
    try:
        for i, edge in enumerate(edges):
            data = manager.CreateSelectData()
            data.View = native
            if not _early_bound(edge, "IEntity").Select4(i > 0, data):
                raise RuntimeError(
                    f"{label}: cannot select native virtual sharp support {i}"
                )
        if int(manager.GetSelectedObjectCount2(-1)) != 2:
            raise RuntimeError(
                f"{label}: virtual sharp requires exactly two selected edges"
            )
        for i, edge in enumerate(edges):
            selected = manager.GetSelectedObject6(i + 1, -1)
            if selected is None or int(adapter.swApp.IsSame(selected, edge)) != 1:
                raise RuntimeError(
                    f"{label}: selected support {i} failed native identity readback"
                )
        # SDK CreatePoint returns a nullable sketch point. Selected-edge Type4
        # creation is unproved: only the native readbacks below can accept it.
        raw_point = factory.CreatePoint(*factory_coordinates)
        returned = (
            None if raw_point is None else _early_bound(raw_point, "ISketchPoint")
        )
        returned_snapshot = (
            None
            if returned is None
            else {
                "id": tuple(int(value) for value in returned.GetID()),
                "type": int(returned.Type),
            }
        )
        immediate_snapshot = snapshot(points())  # Before clearing the two supports.
    finally:
        draw.ClearSelection2(True)
    rebuild_drawing(adapter, label=f"{label} native virtual sharp")
    native.UpdateViewDisplayGeometry()
    after = points()
    rebuilt_snapshot = snapshot(after)
    evidence = (
        f"CreatePoint_sketch_coordinates={factory_coordinates} returned={returned_snapshot} "
        f"before={before_snapshot} immediately_after_CreatePoint={immediate_snapshot} "
        f"after_rebuild={rebuilt_snapshot}"
    )
    if returned is None:
        raise RuntimeError(f"{label}: CreatePoint returned null; {evidence}")
    new = set(after) - set(before)
    sharp_ids = [key for key in new if int(after[key].Type) == 4]
    if len(new) != 2 or len(sharp_ids) != 1 or not set(before) <= set(after):
        raise RuntimeError(
            f"{label}: expected exactly one new native virtual sharp point plus returned Type1 trigger; {evidence}"
        )
    keeper_id = sharp_ids[0]
    point = after[keeper_id]
    extra = new - {keeper_id}
    if returned_snapshot["type"] != 1 or tuple(returned_snapshot["id"]) not in extra:
        raise RuntimeError(
            f"{label}: CreatePoint return differs from the new Type1 trigger; {evidence}"
        )
    trigger_id = next(iter(extra))
    trigger = after[trigger_id]
    if int(trigger.Type) != 1 or int(adapter.swApp.IsSame(returned, trigger)) != 1:
        raise RuntimeError(
            f"{label}: extra point is not the native Type1 CreatePoint return; {evidence}"
        )
    # r23 observed a natural Type4 plus the returned ordinary trigger point.
    # Delete only that identity-proved return, never a type/coordinate match.
    draw.ClearSelection2(True)
    try:
        data = manager.CreateSelectData()
        data.View = native
        if not returned.Select4(False, data):
            raise RuntimeError(
                f"{label}: cannot select returned trigger point; {evidence}"
            )
        if (
            int(manager.GetSelectedObjectCount2(-1)) != 1
            or int(adapter.swApp.IsSame(manager.GetSelectedObject6(1, -1), returned))
            != 1
        ):
            raise RuntimeError(
                f"{label}: trigger selection identity/count failed; {evidence}"
            )
        extension = _early_bound(draw.Extension, "IModelDocExtension")
        if not extension.DeleteSelection2(0):  # No absorbed/child deletion flags.
            raise RuntimeError(
                f"{label}: cannot delete returned trigger point; {evidence}"
            )
    finally:
        draw.ClearSelection2(True)
    rebuild_drawing(adapter, label=f"{label} returned trigger cleanup")
    native.UpdateViewDisplayGeometry()
    cleaned = points()
    evidence += f" after_trigger_cleanup={snapshot(cleaned)}"
    if set(cleaned) != set(before) | {keeper_id}:
        raise RuntimeError(
            f"{label}: trigger cleanup changed unexpected profile point IDs; {evidence}"
        )
    if int(adapter.swApp.IsSame(cleaned[keeper_id], point)) != 1:
        raise RuntimeError(
            f"{label}: trigger cleanup replaced the native virtual sharp; {evidence}"
        )
    point = cleaned[keeper_id]
    if int(point.Type) != 4:  # Natural Type4 only; never assigned.
        raise RuntimeError(
            f"{label}: CreatePoint result is not naturally a native virtual sharp; {evidence}"
        )
    if int(adapter.swApp.IsSame(point.GetSketch(), sketch)) != 1:
        raise RuntimeError(
            f"{label}: native virtual sharp is not owned by the profile sketch; {evidence}"
        )
    inverse = transform.Inverse()
    sheet = _transform_point(
        utility,
        (float(point.X), float(point.Y), float(point.Z)),
        inverse,
        label=f"{label} virtual sharp sketch to sheet",
    )
    if math.dist(sheet[:2], expected[:2]) > 0.00002 or abs(sheet[2]) > 0.00002:
        raise RuntimeError(
            f"{label}: native virtual sharp {sheet} misses source corner {expected}; {evidence}"
        )
    try:
        groups = _virtual_sharp_witness_groups(native)
    except RuntimeError as exc:
        raise RuntimeError(f"{label}: {exc}; {evidence}") from exc
    if len(groups) != len(groups_before) + 1 or not all(
        sum(math.dist(segment[:3], segment[3:]) > 1e-8 for segment in group) >= 2
        for group in groups
    ):
        raise RuntimeError(
            f"{label}: native virtual sharp has no genuine witness lines; {evidence}"
        )
    print(
        f"{label} native virtual sharp: type=4 source_model_mm={(x, PLATE_THICKNESS, z)} "
        f"sheet_m={sheet} witness_groups={len(groups)}"
    )


def _add_profile_virtual_sharps(adapter: Any, view: Any) -> None:
    """Mark all four rounded-away 16/8/37/24 width endpoints, not just 37."""
    # r20: vendored sldworks.tlb wrappers do not populate win32com's swconst
    # globals, and adapter.constants is a small legacy map. Read the installed
    # swconst.tlb enum metadata through the established SDK resolver instead.
    preference = _sw_type_info.constant("swDetailingVirtualSharpStyle")
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceInteger(preference, 0, 3):
        raise RuntimeError("cannot set document virtual sharp witness style")
    if int(extension.GetUserPreferenceInteger(preference, 0)) != 3:
        raise RuntimeError("document virtual sharp witness style did not persist")
    print(f"swDetailingVirtualSharpStyle SDK ordinal={preference}, witness style=3")
    for index in range(len(_part.PLATE_CORNERS)):
        _insert_profile_virtual_sharp(adapter, view, index)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-swing-platform source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Profile View Note",
            "Feature View Note",
            "Notch View Note",
            "Isometric View Note",
            "Pivot Relief Fit",
            "Post Mount Engagement",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Profile View Note",
            "Feature View Note",
            "Notch View Note",
            "Isometric View Note",
            "Pivot Relief Fit",
            "Post Mount Engagement",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("dt-cone-swing-platform"),
    )
    create_blank_drawing_sheets(
        adapter, SHEET_NAMES, label="cone swing platform package"
    )
    _set_end_only_section_lines(drawing_model)
    ddoc = _early_bound(drawing_model, "IDrawingDoc")
    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate the platform sheet")
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Swing Platform Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone swing platform; wedge plate; pivot; lock notch",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    profile = place_view(
        adapter, str(SOURCE), "*Top", *PROFILE_CENTER, scale=(1, 2)
    )
    feature = place_view(
        adapter, str(SOURCE), "*Top", *FEATURE_CENTER, scale=(1, 2)
    )
    notch = place_view(adapter, str(SOURCE), "*Top", *NOTCH_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 3))
    for view in (profile, feature, notch, iso):
        set_hidden_lines_removed(adapter, view)

    # Keep the transverse pivot plane, but put its native end-only indicator
    # on the profile: the feature plan's PostMount Z witnesses are collinear.
    profile_section_pivot = model_point_in_view(
        adapter, profile, (0.0, 0.0, 0.0), label="pivot section station"
    )
    section = create_section_view(
        adapter,
        profile,
        # End-only ends: the left one clears R10's text.  The right one
        # stands 18 mm off the plate's edge (R8's leader runs ~8 mm under
        # its stub): at x 0.123 its sheet-up arrow and letter stood beside
        # HOLE LOCATIONS' 202.84 line and read as that view's cut (machinist
        # review of 31547443, confirmed r1-r3).
        line_start=(PROFILE_CENTER[0] - 0.046, profile_section_pivot[1]),
        line_end=(PROFILE_CENTER[0] + 0.019, profile_section_pivot[1]),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(2, 1),
        label="pivot bearing section",
    )
    cut = _early_bound(section.GetSection(), "IDrSection")
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="pivot section cut faces only")
    if cut.GetDisplayOnlySurfaceCut() is not True:
        raise RuntimeError("pivot section retained geometry beyond the cutting plane")
    _look_section_south(adapter, profile, section, cut, z_mm=0.0, label="A-A")
    _place_pivot_section(adapter, section)
    _position_section_label(adapter, section)
    set_hidden_lines_removed(adapter, section)
    _add_section_hole_axis(
        adapter,
        section,
        PIVOT_HOLE_DIA / 2.0,
        center_x_mm=0.0,
        label="section A-A pivot hole",
    )

    detail = _create_detail_view(
        adapter,
        feature,
        model_center_mm=(0.0, PLATE_THICKNESS, DETAIL_MODEL_Z),
        radius_mm=DETAIL_RADIUS_MM,
        view_xy=DETAIL_CENTER,
        detail_label="B",
        scale=DETAIL_SCALE,
        label="hold-down station detail",
    )
    _place_detail_parent_letter(adapter, feature)
    # Hidden lines removed: HoldDownZ and HoldDownX run between the pivot bore
    # and the hold-down hole's visible top-face rims, never to the underside
    # counterbore.
    set_hidden_lines_removed(adapter, detail)
    profile_pivot = model_point_in_view(
        adapter, profile, (0.0, PLATE_THICKNESS / 1000.0, 0.0), label="profile pivot"
    )
    print(f"profile pivot: sheet_xy={profile_pivot[:2]} expected={PROFILE_PIVOT_XY}")
    if math.dist(profile_pivot[:2], PROFILE_PIVOT_XY) > 0.0005:
        # The C-C arrow clearances in the tests are laid out from it.
        _telemetry.warn(
            f"profile pivot landed at {profile_pivot[:2]}, layout assumes {PROFILE_PIVOT_XY}"
        )
    holddown_ends = [
        model_point_in_view(adapter, profile, point, label=f"hold-down section end {index}")
        for index, point in enumerate(holddown_section_line_model_points())
    ]
    holddown_section = create_section_view(
        adapter,
        profile,
        line_start=holddown_ends[0],
        line_end=holddown_ends[1],
        view_xy=(
            (holddown_strip_box()[0] + holddown_strip_box()[2]) / 2.0,
            (holddown_strip_box()[1] + holddown_strip_box()[3]) / 2.0,
        ),
        section_label="C",
        scale=HOLDDOWN_SECTION_SCALE,
        partial=False,
        label="hold-down hole section",
    )
    holddown_cut = _early_bound(holddown_section.GetSection(), "IDrSection")
    holddown_cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="hold-down section cut faces only")
    _look_holddown_section_south(adapter, profile, holddown_section, holddown_cut)
    _crop_and_place_holddown_section(adapter, holddown_section)
    set_hidden_lines_removed(adapter, holddown_section)
    _add_section_hole_axis(
        adapter,
        holddown_section,
        HOLDDOWN_CLEARANCE_DIA / 2.0,
        center_x_mm=HOLDDOWN_LOCAL_X,
        label="section C-C hold-down hole",
    )

    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="profile plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _add_profile_virtual_sharps(adapter, profile)
    _hide_profile_cosmetic_threads(adapter, profile)
    feature_annotations = curate_view_dimensions(
        adapter,
        feature,
        keep=FEATURE_KEEP,
        view_label="feature plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Name the relief so the reader ties the width to the fit note; it is
    # open through the north edge (drawing-guidelines.md rule 17 (walls and webs) W18), round-ended at the pivot.
    set_dimension_callouts(
        adapter,
        feature_annotations,
        {"PivotBearingReliefDia": RELIEF_WIDTH_CALLOUT},
    )
    notch_annotations = curate_view_dimensions(
        adapter,
        notch,
        keep=NOTCH_KEEP,
        view_label="notch plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="pivot section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    for annotation in section_annotations:
        if dimension_name(adapter, annotation) == "PlateThk":
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            # The witnesses run from the faces' native origin, right of the
            # strip (x415 before SECTION_SHIFT when A-A looked north), to the
            # dimension line.  Read where they start rather than assume that
            # origin, and widen each gap so they start 1.2 mm right of the
            # cut edge (x339), without changing the model dimension or hiding
            # either witness.
            starts = [
                max(segment.x0, segment.x1)
                for segment in _display_lines(
                    adapter, _display_data(adapter, annotation)
                )
                if abs(segment.y0 - segment.y1) < 1e-8
                and any(
                    abs(segment.y0 - SECTION_SHIFT[1] - level) < 0.0001
                    for level in (0.09865, 0.11135)
                )
            ]
            if len(starts) != 2 or abs(starts[0] - starts[1]) > 0.0001:
                raise RuntimeError(f"plate thickness witnesses read {starts}")
            widen = max(starts) - (SECTION_SHIFT[0] + 0.309)
            print(f"PlateThk witness starts {starts}: widening gaps by {widen}")
            for witness_index in (0, 1):
                ok, _use_doc, old_gap = display.GetWitnessLineGap(witness_index, False, 0.0)
                if ok is not True:
                    raise RuntimeError("plate thickness witness gap could not be read")
                gap = float(old_gap) + widen
                if display.SetWitnessLineGap(witness_index, False, gap) is not True:
                    raise RuntimeError("plate thickness witness gap was refused")
                ok, use_doc, actual_gap = display.GetWitnessLineGap(witness_index, False, 0.0)
                if ok is not True or use_doc or abs(float(actual_gap) - gap) > 1e-8:
                    raise RuntimeError("plate thickness witness gap did not persist")
                print(f"PlateThk witness {witness_index}: old_gap_m={old_gap} gap_m={actual_gap}")
            rebuild_drawing(adapter, label="plate thickness cut-edge witness gaps")
    _crop_pivot_section(adapter, section)
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="hold-down station detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # U41: the thickness is the stock's, a reference with no band.
    thickness_annotations = [
        item for item in section_annotations
        if dimension_name(adapter, item) == "PlateThk"
    ]
    if len(thickness_annotations) != 1:
        raise RuntimeError("expected one native plate thickness")
    thickness_reference = set_reference_dimension(
        adapter, thickness_annotations[0], label="stock plate thickness reference"
    )
    set_dimension_callouts(
        adapter, thickness_annotations, {"PlateThk": PLATE_STOCK_CALLOUT}
    )
    relief_annotations = [
        item for item in section_annotations
        if dimension_name(adapter, item) == "PivotBearingReliefDepth"
    ]
    if len(relief_annotations) != 1:
        raise RuntimeError("expected one native pivot relief depth")
    relief_reference = set_reference_dimension(
        adapter, relief_annotations[0], label="matched pivot relief reference depth"
    )
    annotations = [
        *profile_annotations,
        *feature_annotations,
        *notch_annotations,
        *section_annotations,
        *detail_annotations,
    ]
    # No explicit AutoInsertCenterMarks2: the template centre-marks every
    # hole as the plan is placed, and r1's explicit call printed each of the
    # four marks twice (layout audit duplicate-annotation; fleet issue #913).
    pivot_edge, mount_edge = _visible_plan_controls(adapter, feature)
    pivot_callout = add_native_hole_callout(
        adapter,
        feature,
        callout_xy=PIVOT_BORE_CALLOUT_XY,
        label="pivot reamed bore",
        edge=pivot_edge,
        process=PIVOT_PROCESS,
    )
    _rewrite_hole_callout(
        pivot_callout,
        lambda definitions: callout_below_definitions(
            definitions, PIVOT_BORE_CALLOUT_BELOW
        ),
        label="pivot reamed bore",
    )
    _print_pivot_band_exactly(pivot_callout)
    post_mount_callout = add_native_hole_callout(
        adapter,
        feature,
        callout_xy=POST_MOUNT_CALLOUT_XY,
        label="v2 post-mount tapped holes",
        edge=mount_edge,
    )
    _rewrite_hole_callout(
        post_mount_callout,
        lambda definitions: callout_below_definitions(
            definitions, POST_MOUNT_CALLOUT_BELOW
        ),
        label="v2 post-mount tapped holes",
    )
    _omit_post_mount_thread_class(post_mount_callout)
    rebuild_drawing(adapter, label="plan hole callout rows")
    # The section shows the top seat at its head and the base slide at its
    # foot.  Arrows land mid-face so neither symbol reads as controlling a
    # corner, hole wall or outer edge: both on the left-hand piece, the
    # longest edge of each face.
    seat_edge = _horizontal_section_edge(section, 6.35, label="top seat")
    seat_symbol = add_surface_finish(
        adapter,
        section,
        symbol_xy=SEAT_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "post_seat"),
        label="post and tip-block seat finish",
        char_height=0.0025,
        entity=seat_edge,
        leader_attach_xy=_section_edge_midpoint(adapter, section, seat_edge, label="top seat"),
    )
    slide_edge = _horizontal_section_edge(section, 0.0, label="base slide")
    slide_symbol = add_surface_finish(
        adapter,
        section,
        symbol_xy=BASE_SLIDE_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "base_slide"),
        label="base sliding-face finish",
        char_height=0.0025,
        entity=slide_edge,
        leader_attach_xy=_section_edge_midpoint(adapter, section, slide_edge, label="base slide"),
    )
    for symbol, label in (
        (seat_symbol, "post and tip-block seat finish"),
        (slide_symbol, "base sliding-face finish"),
    ):
        _set_any_process_finish(adapter, symbol, label=label)

    add_property_linked_note(adapter, "Profile View Note", 0.045, 0.085)
    add_property_linked_note(adapter, "Feature View Note", 0.150, 0.085)
    add_property_linked_note(adapter, "Notch View Note", *NOTCH_CAPTION_UPPER_LEFT)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_CAPTION_UPPER_LEFT)
    add_property_linked_note(
        adapter, "Post Mount Engagement", *ENGAGEMENT_NOTE_XY, char_height=0.0025
    )
    add_leader_note(
        adapter,
        property_link("Pivot Relief Fit"),
        text_xy=RELIEF_NOTE_XY,
        attach_xy=relief_floor_tip_xy(adapter, section),
        label="pivot relief fit",
        view=section,
        height=0.0025,
    )
    # The hold-down's size, from the underside, where section C-C shows its
    # counterbore in solid lines (user ruling 2026-09-29).
    _add_holddown_callout(adapter, holddown_section)
    _add_face_labels(adapter, {"A-A": section, "C-C": holddown_section})

    # Annotation insertion can invalidate the exported display geometry.
    for view in (profile, feature, notch, section, detail, holddown_section, iso):
        set_hidden_lines_removed(adapter, view)
    # Last, after every annotation and display-mode regen could re-lay it.
    _position_view_label(
        adapter,
        detail,
        DETAIL_LABEL_LOWER_LEFT,
        label="detail B label",
    )
    _position_view_label(
        adapter,
        holddown_section,
        HOLDDOWN_SECTION_LABEL_LOWER_LEFT,
        label="section C-C label",
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if (str(relief_reference.GetText(1)), str(relief_reference.GetText(2))) != ("(", ")"):
        raise RuntimeError("pivot relief reference state did not persist")
    if (
        str(thickness_reference.GetText(1)),
        str(thickness_reference.GetText(2)),
    ) != ("(", ")"):
        raise RuntimeError("stock plate thickness reference state did not persist")
    for name, feature_name, radius_m in (
        ("CornerSWR", "CornerSW", 0.005),
        ("CornerNWR", "CornerNW", 0.008),
        ("CornerNER", "CornerNE", 0.010),
        ("CornerSER", "CornerSE", 0.012),
    ):
        _assert_corner_radius_attachment(
            adapter, profile, profile_annotations,
            name=name, feature_name=feature_name, radius_m=radius_m,
        )
    if cut.GetDisplayOnlySurfaceCut() is not True:
        raise RuntimeError("pivot section lost its cut-only display after annotation")
    for face_name, model_y in (
        ("post_seat", PLATE_THICKNESS / 1000.0),
        ("base_slide", 0.0),
    ):
        projected = model_point_in_view(
            adapter, section, (0.0, model_y, 0.0), label=f"{face_name} projection"
        )
        print(
            f"section face {face_name}: model_y_mm={model_y * 1000:.3f} "
            f"sheet_xy_mm=({projected[0] * 1000:.3f},{projected[1] * 1000:.3f})"
        )
    for sheet_geometry in collect_document(adapter):
        print(describe_sheet(sheet_geometry))
        if sheet_geometry.name != SHEET_NAMES[0]:
            continue
        thickness_geometry = [
            item for item in sheet_geometry.annotations if item.label == "PlateThk"
        ]
        if len(thickness_geometry) != 1:
            raise RuntimeError("expected one measured plate thickness annotation")
        witnesses = [
            segment for segment in thickness_geometry[0].segments
            if abs(segment.y0 - segment.y1) < 1e-8
            and any(
                abs(segment.y0 - SECTION_SHIFT[1] - level) < 0.0001
                for level in (0.09865, 0.11135)
            )
        ]
        if len(witnesses) != 2 or any(
            abs(max(segment.x0, segment.x1) - SECTION_SHIFT[0] - 0.309) > 0.0005
            or abs(min(segment.x0, segment.x1) - SECTION_SHIFT[0] - 0.299) > 0.0005
            for segment in witnesses
        ):
            raise RuntimeError(f"plate thickness witnesses did not shorten to the cut edge: {witnesses}")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Swing Platform Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
        sheet_scales=SHEET_SCALES,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
