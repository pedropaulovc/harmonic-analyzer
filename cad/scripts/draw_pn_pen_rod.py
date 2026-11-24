r"""Create the curated machinist drawing for the pen square rod.

The SLDPRT remains authoritative.  This recipe supplies only the rod's views,
the placement of its imported model dimensions, the stud-tap callout, the
overall-length reference, VIEW A's viewing arrow and the property-linked
notes; sheet/template and export behavior lives in ``_drawing_common``.
Places, bands, mate callouts and the pivot's fit note are authored on the
part (``pn_pen_rod_spec``, the groove's in ``pn_pen_rod_groove_spec``).

The sheet prints decimal inch (the part's ``drawing_unit: in``).  The side
view (2:1, the sheet scale) lays the rod axis horizontal, as the bar sits in
the lathe (drawing-guidelines.md rule 11), and carries the square's and the
pivot's lengths from the shoulder, the pivot's banded diameter between its
flanks (SEE NOTE 1: its mate), the shoulder root's R MAX, the (4.82)
end-to-end reference and VIEW A's lettered arrow onto the tapped top face;
VIEW A (5:1) under it looks at that face and carries the square's banded SQ
size, the native Hole Wizard callout of the #0-80 stud tap, its drill Ø at
.XXX and both depths at .XX, and the tap's .067 MIN wall (RV-01, from the
part's hidden TapWallReference sketch, shown in that view only).  DETAIL B
(5:1, a cropped *Front model view turned like the side view: the
draw_mg_wheel_axle detail-A recipe) carries the set-screw relief groove
(#2439): both walls from the shoulder and the floor's Ø, each SEE NOTE 2.
The labelled 1:1 isometric sits right, the notes in the field under the
side view.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pn_pen_rod.py pn-pen-rod
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
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
    view_name,
)
from _drawing_detail_crop import native_circle_geometry
from _drawing_dimension_import import import_cosmetic_threads
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import ViewEdges, scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leader_notes import add_leader_note
from _drawing_view_arrow import square_view_arrow
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _printed_limits import drilled_limits, limits
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import pn_pen_rod_groove_spec as groove
import pn_pen_rod_spec as rod
from pn_pen_rod_spec import (
    DRAWING_REFERENCE_PRECISION,
    END_VIEW_LETTER,
    END_VIEW_NOTE,
    PIVOT_DIA,
    PIVOT_LENGTH,
    ROD_SECTION,
    SHOULDER_FILLET_R,
    SHOULDER_FILLET_TOL_TYPE,
    SQUARE_LENGTH,
    STUD_TAP_DEPTH_PLACES,
    STUD_TAP_DRILL_DIA,
    STUD_TAP_SPEC,
    TAP_WALL_MIN_MM,
    TAP_WALL_START_R,
    TOTAL_LENGTH,
)

# The rod's marked dimensions, places and callouts: pn_pen_rod_spec's and
# the groove's (build_pn_pen_rod marks the same union).
DRAWING_DIMENSIONS = {**rod.DRAWING_DIMENSIONS, **groove.DRAWING_DIMENSIONS}
DRAWING_PRECISION_BY_NAME = {
    **rod.DRAWING_PRECISION_BY_NAME,
    **{
        name: places
        for names in groove.DRAWING_PRECISION.values()
        for name, places in names.items()
    },
}
DIMENSION_CALLOUTS = {**rod.DIMENSION_CALLOUTS, **groove.DIMENSION_CALLOUTS}

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["pn_pen_rod"]
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
# Hole Wizard length variables of the blind stud tap's callout, by native
# name: the drill's Ø prints .XXX, both depths the spec's places (.XX).
STUD_TAP_PRECISION = {
    "hw-tapdrldia": 3,
    "hw-tapdrldepth": STUD_TAP_DEPTH_PLACES,
    "hw-threaddepth": STUD_TAP_DEPTH_PLACES,
}

# Rule 15: at 1:1 the side view stood 5 mm tall in the top half of the sheet
# (final review 2026-10-14); 2:1 lays the rod 245 mm long and 10 mm tall.
SHEET_SCALE = (2.0, 1.0)
SIDE_SCALE = (2, 1)
# The 5 mm square's end at 5:1 (25 mm) holds the SQ size's four-row block
# BETWEEN its extension lines with air; at 4:1 (20 mm) the 19.1 mm block's
# bottom row sat on the lower one (final review: read as an underline).
END_SCALE = (5, 1)
ISO_SCALE = (1, 1)  # 115 mm tall; labelled, as the fleet labels its isos
# The rod is modelled axis-along-+Y (its assembly pose), so the side view is
# "*Front" turned -90 deg before any import (IView.Angle,
# draw_dt_cylinder_gear_shaft's PROFILE_ROTATION): model +Y -> sheet +x,
# model +X -> sheet -y.  Pivot end left, tapped top face right; the shoulder
# (model y 0) both axial dimensions start from is near the left end.
SIDE_ROTATION = -math.pi / 2.0
_SIDE_K = SIDE_SCALE[0] / SIDE_SCALE[1] / 1000.0

# The view centres on the part's bounding box: model y -PIVOT_LENGTH to
# SQUARE_LENGTH, x and z +/- S/2.  _prove_side_view_frame reads the frame
# back before anything is placed by it.
_CY = (SQUARE_LENGTH - PIVOT_LENGTH) / 2.0

# Sheet layout (meters; border 0.0127, title block x >= 0.2155, y <= 0.0655).
# The 2:1 side view spans the sheet's left three quarters on y 0.170, its
# dimension rows and pin callout above, the R MAX below; the labelled 5:1
# end view fills the lower-left field under it; the 1:1 isometric stands
# at the right, its note under it.
SIDE_CENTER = (0.205, 0.170)
END_CENTER = (0.080, 0.075)
ISO_CENTER = (0.380, 0.175)


def _sx(model_y_mm: float) -> float:
    """Sheet x of a station along the rod axis (model y) in the side view."""
    return SIDE_CENTER[0] + (model_y_mm - _CY) * _SIDE_K


def _sy(model_x_mm: float) -> float:
    """Sheet y of a model x in the side view (model +X points down)."""
    return SIDE_CENTER[1] - model_x_mm * _SIDE_K


def _end_x(center: tuple[float, float], model_x_mm: float) -> float:
    return center[0] + model_x_mm * END_SCALE[0] / END_SCALE[1] / 1000.0


def _end_y(center: tuple[float, float], model_z_mm: float) -> float:
    """Sheet y of a model z in the end view ("*Top": model +Z points down)."""
    return center[1] - model_z_mm * END_SCALE[0] / END_SCALE[1] / 1000.0


_HALF = ROD_SECTION / 2.0
_END_HALF_M = _HALF * END_SCALE[0] / END_SCALE[1] / 1000.0

# Side view stations: pivot end x 0.0825, shoulder x 0.1035, top face
# x 0.3275; square y 0.165..0.175, pivot flanks y 0.166/0.174.
#
# A vertical dimension whose text stands off its span runs its line to a
# shoulder under the text's bottom row, the block hanging to ONE side of
# that line with its edge ON it (farm audit 20261014T045316872Z, PivotDia
# keep (0.084, 0.142): line x 0.0840, "MHA-PN-05 PIVOT BORE" 0.02821 +
# 0.05579 = 0.0840, shoulder y 0.13192 = keep y - 0.0101, top row's top
# ~0.152 = keep y + 0.010).  Text BELOW its span therefore has the line run
# up the block's whole edge (the review's "E struck by the line"); text
# ABOVE meets it only at the shoulder's end, as every side-view diameter
# of draw_dt_cone_gear_shaft does.
#
# Above the rod, three rows baselined from the shoulder / end faces, each
# sharing its extension lines with the row below at the common face (text
# offsets are sheet millimetres, as on the green 1:1 sheet):
#   row 1 (y 0.1845, 9.5 mm over the square): 4.41, shoulder to top face,
#     text mid-span (x 0.2155);
#   row 2 (y 0.1945): .41, pivot end to shoulder.  At 2:1 the span is
#     21 mm, so the ~11.6 mm text stands centred over it (x 0.0872..0.0988,
#     4.7 mm from each extension line), its arrows FORCED inside
#     (ARROW_SIDES) so no outside tail runs left toward the Ø's line;
#   row 3 (y 0.2045): the (4.82) reference, end face to end face, its line
#     at y ~0.2017 and its text ~0.2026..0.2061 (audit offsets).
# Ø.1260 -.0005/-.0020 between the pivot flanks: its line stands 5.75 mm
#   left of the pivot end (x 0.07675), the flanks' extension lines reaching
#   it, so it rises past every row clear of their lines (all start at the
#   pivot end or right of it) to the four-row ~56 x 20 mm block centred at
#   y 0.2225: shoulder y ~0.2124 (6.3 mm over the (4.82) text), top
#   ~0.2325.  Hanging left it spans x 0.0210..0.0768 (8.3 mm inside the
#   border), hanging right 0.0768..0.1326; either way only its bottom row's
#   end meets the line, at the shoulder.  Under the rod its outside-arrow
#   tail (6.35 mm) runs to y ~0.1597 at x 0.0768, where nothing else is.
# Below the rod, where the ShoulderRadius's arc is (model +X, the root the
# vertical layout's leader found):
#   R.008 MAX / SEATS ON PEN V-BLOCK / MHA-PN-05 down-right of the root:
#     farm audit 20261014T053239477Z drew that block x keep-0.0281..
#     keep+0.0265 with its shoulder 8.35 mm under the anchor, so at
#     (0.16925, 0.1475) it spans x 0.1412..0.1958, y 0.1392..0.1559 (9.1 mm
#     under the square), its leader from the shoulder's left end up-left at
#     ~35 deg to the root (0.1035, 0.1656), over everything else below the
#     rod (the end view's tap callout tops out at y 0.1135, x <= 0.1248).
SIDE_KEEP = {
    "Length": (_sx(SQUARE_LENGTH / 2.0), _sy(-_HALF) + 0.0095),
    "PivotLength": (_sx(-PIVOT_LENGTH / 2.0), _sy(-_HALF) + 0.0195),
    "PivotDia": (_sx(-PIVOT_LENGTH) - 0.00575, _sy(-_HALF) + 0.0475),
    "ShoulderRadius": (_sx(0.0) + 0.06575, _sy(_HALF) - 0.0175),
}
# swDimensionArrowsSide_e (swDimArrowsInside 0, swDimArrowsOutside 1), read
# back (draw_dt_cone_tip_block's _set_arrow_sides): the .41's inside its
# 21 mm span; the SQ size's outside its 25 mm span, so only its text stands
# between the extension lines (the green 4:1 sheet drew them outside too).
ARROW_SIDES = {"PivotLength": 0, "Depth": 1}
OVERALL_REF_XY = (_sx(_CY), _sy(-_HALF) + 0.0295)
# Picks are ENTITIES from the side view's edge scan, not sheet hit-tests:
# the pivot end is a circular edge seen edge-on, and a SelectByID2 point on
# it found nothing (farm leaf 20261014T002718Z: "failed to select pen-rod
# overall length reference edge 1 at sheet (0.069, 0.08875)").  The top face's
# near edge is the visible straight edge across the square at y 112; the
# pivot end is the circle of the pivot's diameter about the rod axis at
# y -PIVOT_LENGTH.  The sheet points passed beside them only document the layout.
OVERALL_TOP_SHEET_XY = (_sx(SQUARE_LENGTH), _sy(-_HALF + 1.0))
OVERALL_END_SHEET_XY = (_sx(-PIVOT_LENGTH), _sy(-PIVOT_DIA / 2.0 + 1.0))
_EDGE_TOL_MM = 1e-4
# How far the side view's projected stations may sit from the _sx/_sy frame
# every position above is computed in before the build stops.
_FRAME_TOL_M = 2.5e-4
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym

# End view (5:1, square 0.0675..0.0925 x 0.0625..0.0875).  The SQ size's
# four-row block centres on its dimension line (audit 20261014T053239477Z:
# rows 66.6 mm wide at most, from keep y - 10.08 to keep y + 9.06 mm), so
# keep y = centre + 0.51 mm centres it: y 0.0654..0.0846, 2.9 mm inside
# each extension line (0.0625/0.0875).  Its line 52 mm right of the
# centre puts the block at x 0.0987..0.1653, 6.2 mm right of the square
# and ~3 mm past the centre mark's extended arm.  The tap callout keeps the
# green sheet's offsets from the hole (text centred on keep x, 45.6 mm wide,
# shoulder 5.6 mm under keep y): x 0.0792..0.1248, y 0.1044..0.1135, 17 mm
# over the square, 18 mm over the block, 7 mm left of the SQ line's upper
# arrow piece (x 0.132, to y ~0.0939); its leader drops almost straight to
# the drill rim.  The view label (anchored top-left, text 4.5 mm under its
# anchor, END_NOTE_WIDTH long at the scale note's ~2.5 mm a character)
# centred 7 mm under the square, left of the SQ line's lower arrow piece
# (x 0.132, to y ~0.0561).
END_KEEP = {
    "Depth": (END_CENTER[0] + 0.052, END_CENTER[1] + 0.00051),
    "TapWallMin": (
        END_CENTER[0] - _END_HALF_M - 0.010,
        _end_y(END_CENTER, TAP_WALL_START_R + TAP_WALL_MIN_MM / 2.0),
    ),
}
# RV-01's tap wall (.067 MIN over TAP WALL) stands left of the square, the
# one empty side: its reference line runs from the thread's rim straight
# down the vertical centreline toward the bottom flat (sheet y ~0.0712 to
# ~0.0627), so its extension lines run left from the centreline, under the
# centre mark's horizontal arm and clear of the tap callout's leader (which
# drops onto the rim from above), to its line 10 mm left of the square.
# The 8.5 mm run cannot hold the ~21 x 9 mm two-row text, so native
# OffsetText parks it on a leader further left (draw_pn_pen_frame's
# TAP_WALL_TEXT_XY): x ~0.027..0.052, its right edge ~4.5 mm clear of the
# extension lines' ends and ~7 mm over the view label's top.  The anchor is
# the value row's bottom centre.
TAP_WALL_TEXT_XY = (END_CENTER[0] - _END_HALF_M - 0.028, END_KEEP["TapWallMin"][1])
_TEXT_SETTLE_M = 0.0005
TAP_CALLOUT_XY = (END_CENTER[0] + 0.022, END_CENTER[1] + 0.035)
END_NOTE_WIDTH = len(END_VIEW_NOTE) * 0.0025
END_NOTE_XY = (
    END_CENTER[0] - END_NOTE_WIDTH / 2.0,
    END_CENTER[1] - _END_HALF_M - 0.007,
)
# VIEW A's viewing arrow (rule 9): a letter note whose straight leader is the
# arrow (draw_fr_top_frame._add_view_arrow; the native projected-view arrow
# is not switchable through the API), level on the rod axis and pointing
# left onto the tapped top face it looks at, its tip 3.5 mm off that face,
# the 5 mm letter 10 mm right of the tip: x ~0.331..0.345 on y 0.170, in
# the 43 mm field between the top face's extension lines and the isometric
# (x 0.3709).
VIEW_LETTER_HEIGHT = 0.005
VIEW_ARROW_TIP_GAP = 0.0035
VIEW_ARROW_RUN = 0.010
_VIEW_A_TIP = (_sx(SQUARE_LENGTH) + VIEW_ARROW_TIP_GAP, _sy(0.0))
VIEW_A_ARROW = (
    (_VIEW_A_TIP[0] + VIEW_ARROW_RUN, _VIEW_A_TIP[1] + VIEW_LETTER_HEIGHT / 2.0),
    _VIEW_A_TIP,
)
# Notes 1 (the pivot's mate, two lines of at most ~53 characters) and 2 (the
# groove's screw, one ~51-character line), ~125 x 14 mm at ~2.35 mm a
# character, anchored top-left, in the empty field under the side view:
# x 0.135..0.260, y ~0.114..0.128, 11 mm under the R MAX block (bottom
# 0.139), 10 mm right of the stud tap's callout (x <= 0.1248) and 7 mm left
# of DETAIL B's crop.
NOTES_XY = (0.135, 0.128)

# --- DETAIL B: the set-screw relief groove at 5:1 (#2439) -------------------
# Native detail views import no dimensions (draw_mg_wheel_axle detail A), so
# DETAIL B is a second *Front model view at 5:1, turned like the side view
# (model +Y to paper right, +X down the paper), moved so the fence's focus
# lands on DETAIL_CENTER and cropped to the fence circle.  At 2:1 the groove
# is a 0.5 mm notch; at 5:1 its .010 depth draws 1.3 mm.
DETAIL_SCALE = (5, 1)
_DETAIL_K = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
DETAIL_LETTER = "B"
DETAIL_LABEL_TEXT = (
    f"DETAIL {DETAIL_LETTER}\nSCALE {DETAIL_SCALE[0]} : {DETAIL_SCALE[1]}"
)
# The fence, model mm (x radial, y axial): on the axis midway from the
# shoulder to the groove's end-side wall.  Radius 4.6 holds the shoulder's
# pivot corners (4.31 off), both walls and both floors (the far floor corner
# 4.22 off), so every reference a kept dimension takes survives the crop.
DETAIL_FOCUS_MM = (0.0, -groove.GROOVE_FAR_STATION / 2.0)
_DETAIL_FOCUS_M = (DETAIL_FOCUS_MM[0] / 1000.0, DETAIL_FOCUS_MM[1] / 1000.0, 0.0)
DETAIL_RADIUS_MM = 4.6
DETAIL_CROP_RADIUS = DETAIL_RADIUS_MM * _DETAIL_K
# Lower right, between the notes and the isometric's note, over the title
# block: crop x 0.267..0.313, y 0.087..0.133.
DETAIL_CENTER = (0.290, 0.110)
CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
DETAIL_POSITION_TOL_M = 1e-4
CIRCLE_TOL_M = 1e-7


def _detail_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of model (x, y) mm in DETAIL B (model +Y runs right, +X
    down)."""
    return (
        DETAIL_CENTER[0] + (y_mm - DETAIL_FOCUS_MM[1]) * _DETAIL_K,
        DETAIL_CENTER[1] - (x_mm - DETAIL_FOCUS_MM[0]) * _DETAIL_K,
    )


_DETAIL_SHOULDER_X = _detail_xy(0.0, 0.0)[0]  # 0.310
_DETAIL_FAR_WALL_X = _detail_xy(0.0, -groove.GROOVE_FAR_STATION)[0]  # 0.270
_DETAIL_GROOVE_MID_X = _detail_xy(
    0.0, -(groove.GROOVE_NEAR_STATION + groove.GROOVE_FAR_STATION) / 2.0
)[0]  # 0.2795
# Over the crop, both walls baselined from the shoulder (rule 10), each
# value over SEE NOTE 2:
#   GrooveStation (y 0.140): the 21 mm span cannot hold its ~25 mm block, so
#     the text stands right of the shoulder's extension line (x ~0.315..
#     0.340), clear of the isometric's note (x >= 0.350);
#   GrooveEndStation (y 0.152): the 40 mm span holds its block centred
#     between the far wall's and the shoulder's extension lines, 8 mm under
#     the side view's square (y 0.165) and over the first row's line.
# Under the crop, GrooveDia: its line runs between the two floors at
# mid-groove and drops through the groove's lower mouth to its block
# (y ~0.073..0.083), over the title block (y 0.0655).
DETAIL_KEEP = {
    "GrooveStation": (_DETAIL_SHOULDER_X + 0.017, DETAIL_CENTER[1] + 0.030),
    "GrooveEndStation": (
        (_DETAIL_FAR_WALL_X + _DETAIL_SHOULDER_X) / 2.0,
        DETAIL_CENTER[1] + 0.042,
    ),
    "GrooveDia": (_DETAIL_GROOVE_MID_X, DETAIL_CENTER[1] - 0.032),
}
# Left of the crop, its top 16 mm under note 2's line (farm r1 placed it 0.105,
# 5 mm under, where it read as a third note) and clear over GrooveDia's
# block (top ~0.083).
DETAIL_LABEL_XY = (0.235, DETAIL_CENTER[1] - 0.011)
# The mark's letter on the side view, under-left of the mark circle round
# the groove (x 0.0863..0.1047, y 0.1608..0.1792), clear of the Ø.1260's
# outside-arrow tail (x 0.0768, to y ~0.1597).
PARENT_LETTER_XY = (0.087, 0.158)
# The isometric (1:1 outline 18.2 x 115.3 mm: x 0.3709..0.3891, y
# 0.1174..0.2327, 43 mm right of the top face's extension lines) takes its
# ~60 mm scale note 8 mm under it: x 0.350..0.410, y ~0.1050..0.1085.
ISO_NOTE_XY = (ISO_CENTER[0] - 0.030, ISO_CENTER[1] - 0.0577 - 0.008)

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, beside the constants of the
# code that prints it, in the part frame (pn_pen_rod_spec: the origin on the
# rod axis at the shoulder, the square running +Y to its tapped top face,
# its flats square to X and Z; the pivot running -Y).  The square is bought
# key stock left as supplied (its SQ band holds the catalogue section).  The
# shoulder root's R.008 MAX rides on the pivot.  The declarations print
# nothing.
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_pn_pen_rod"
_GROOVE = "pn_pen_rod_groove_spec"
_FRAME = ("build_pn_pen_rod", "__frame__")
_FLAT_SOURCES = ("ROD_SECTION", "SECTION_BAND", "UNIT", (_SELF, "END_KEEP"))
_TAP_DRILL_PLACES = STUD_TAP_PRECISION["hw-tapdrldia"]


def _plane(axis: str, value: float) -> dict[str, Any]:
    return {"frame": "model", "axis": axis, "value": value}


part_metadata(
    model_sources=(_FRAME, "ROD_SECTION", "SQUARE_LENGTH", "PIVOT_LENGTH"),
    precision_sources=(
        "DRAWING_PRECISION",
        (_GROOVE, "DRAWING_PRECISION"),
        (_SELF, "DRAWING_PRECISION_BY_NAME"),
        (_SELF, "STUD_TAP_PRECISION"),
    ),
)
# The shoulder, the square's bottom face seated on the v-block: the square's
# length .XX (SIDE_KEEP "Length") and the pivot's run from it.
requirement(
    "shoulder_face",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={"plane": (_plane("y", 0.0), (_FRAME,))},
)
requirement(
    "top_face",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), rod.SQUARE_LENGTH),),
    requirements=("plane", "station"),
    fields={
        "plane": (_plane("y", rod.SQUARE_LENGTH), (_FRAME, "SQUARE_LENGTH")),
        "station": (
            limits(rod.SQUARE_LENGTH, _P["Length"], unit=rod.UNIT),
            ("SQUARE_LENGTH", "UNIT", (_SELF, "SIDE_KEEP")),
        ),
        "station_nominal": (rod.SQUARE_LENGTH, ("SQUARE_LENGTH",)),
        "station_from": ("shoulder_face", ((_SELF, "SIDE_KEEP"),)),
    },
    precision={"station": _P["Length"]},
)
requirement(
    "pivot_end",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), rod.PIVOT_LENGTH),),
    requirements=("plane",),
    fields={"plane": (_plane("y", -rod.PIVOT_LENGTH), (_FRAME, "PIVOT_LENGTH"))},
)
# The square's four flats, the bought key stock's: .197 +.000/-.002 SQ, the
# hanger's slots cut to it (END_KEEP "Depth"), across each pair.
for _name, _axis, _sign, _pair in (
    ("flat_x_pos", "x", 1.0, "flat_x_neg"),
    ("flat_x_neg", "x", -1.0, None),
    ("flat_z_pos", "z", 1.0, "flat_z_neg"),
    ("flat_z_neg", "z", -1.0, None),
):
    _normal = (_sign, 0.0, 0.0) if _axis == "x" else (0.0, 0.0, _sign)
    _fields: dict[str, tuple[Any, tuple[Any, ...]]] = {
        "plane": (
            _plane(_axis, _sign * rod.ROD_SECTION / 2.0),
            (_FRAME, "ROD_SECTION"),
        ),
    }
    if _pair is not None:
        _fields |= {
            "across": (
                limits(rod.ROD_SECTION, _P["Depth"], rod.SECTION_BAND, unit=rod.UNIT),
                _FLAT_SOURCES,
            ),
            "across_nominal": (rod.ROD_SECTION, ("ROD_SECTION",)),
            "across_from": (_pair, ((_SELF, "END_KEEP"),)),
            "callout": (rod.DIMENSION_CALLOUTS["Depth"], ("DIMENSION_CALLOUTS",)),
            "stock": (
                f"McMASTER-CARR {rod.STOCK_SKU}",
                ("STOCK_SKU", "STOCK_SECTION_MIN", "STOCK_SECTION_MAX"),
            ),
        }
    requirement(
        _name,
        kind="face",
        faces=(PlanarFace(_normal, rod.ROD_SECTION / 2.0),),
        requirements=("plane", "across") if _pair is not None else ("plane",),
        fields=_fields,
        precision={"across": _P["Depth"]} if _pair is not None else None,
    )
# The turned pivot: Ø.1240-.1255, a sliding fit in the v-block's reamed
# pivot bore (note 1; SIDE_KEEP "PivotDia"), .41 long from the shoulder
# (SIDE_KEEP "PivotLength"), its root R.008 MAX (SIDE_KEEP "ShoulderRadius").
requirement(
    "pivot",
    kind="outside_cylinder",
    faces=(CylinderFace(rod.PIVOT_DIA),),
    requirements=("dia", "length", "corner_radius_max"),
    fields={
        "at": ([0.0, 0.0, 0.0], (_FRAME,)),
        "axis": ([0.0, -1.0, 0.0], (_FRAME,)),
        "dia": (
            limits(rod.PIVOT_DIA, _P["PivotDia"], rod.PIVOT_BAND, unit=rod.UNIT),
            ("PIVOT_DIA", "PIVOT_BAND", "UNIT", (_SELF, "SIDE_KEEP")),
        ),
        "nominal_dia": (rod.PIVOT_DIA, ("PIVOT_DIA",)),
        "callout": (rod.DIMENSION_CALLOUTS["PivotDia"], ("DIMENSION_CALLOUTS",)),
        "diametral_clearance": (
            list(rod.PIVOT_CLEARANCE_MM),
            ("PIVOT_CLEARANCE_MM", "DRAWING_NOTES"),
        ),
        "note": (rod.DRAWING_NOTES, ("DRAWING_NOTES", "PIVOT_FIT_NOTE")),
        "length": (
            limits(rod.PIVOT_LENGTH, _P["PivotLength"], unit=rod.UNIT),
            ("PIVOT_LENGTH", "UNIT", (_SELF, "SIDE_KEEP")),
        ),
        "length_nominal": (rod.PIVOT_LENGTH, ("PIVOT_LENGTH",)),
        "corner_radius_max": (
            rod.SHOULDER_FILLET_R,
            ("SHOULDER_FILLET_R", "SHOULDER_FILLET_TOL_TYPE", (_SELF, "SIDE_KEEP")),
        ),
        "corner_callout": (
            rod.DIMENSION_CALLOUTS["ShoulderRadius"],
            ("DIMENSION_CALLOUTS",),
        ),
    },
    precision={
        "dia": _P["PivotDia"],
        "length": _P["PivotLength"],
        "corner_radius_max": _P["ShoulderRadius"],
    },
)
# The set-screw groove round the pivot (owner ruling B on #2439): Ø.106,
# its walls .165 and .315 from the shoulder, all at .XXX and flagged to note 2
# (DETAIL_KEEP).  Its position is the shoulder-side wall.
requirement(
    "groove",
    kind="groove",
    faces=(
        CylinderFace(groove.GROOVE_DIA),
        PlanarFace((0.0, -1.0, 0.0), groove.GROOVE_NEAR_STATION),
        PlanarFace((0.0, 1.0, 0.0), -groove.GROOVE_FAR_STATION),
    ),
    requirements=("dia", "station", "end_station"),
    fields={
        "at": (
            [0.0, -groove.GROOVE_NEAR_STATION, 0.0],
            (_FRAME, (_GROOVE, "GROOVE_NEAR_STATION")),
        ),
        "axis": ([0.0, -1.0, 0.0], (_FRAME,)),
        "dia": (
            limits(groove.GROOVE_DIA, _P["GrooveDia"], unit=rod.UNIT),
            ((_GROOVE, "GROOVE_DIA"), "UNIT", (_SELF, "DETAIL_KEEP")),
        ),
        "dia_nominal": (groove.GROOVE_DIA, ((_GROOVE, "GROOVE_DIA"),)),
        "station": (
            limits(groove.GROOVE_NEAR_STATION, _P["GrooveStation"], unit=rod.UNIT),
            ((_GROOVE, "GROOVE_NEAR_STATION"), "UNIT", (_SELF, "DETAIL_KEEP")),
        ),
        "station_nominal": (
            groove.GROOVE_NEAR_STATION,
            ((_GROOVE, "GROOVE_NEAR_STATION"),),
        ),
        "station_from": ("shoulder_face", ((_SELF, "DETAIL_KEEP"),)),
        "end_station": (
            limits(groove.GROOVE_FAR_STATION, _P["GrooveEndStation"], unit=rod.UNIT),
            ((_GROOVE, "GROOVE_FAR_STATION"), "UNIT", (_SELF, "DETAIL_KEEP")),
        ),
        "end_station_nominal": (
            groove.GROOVE_FAR_STATION,
            ((_GROOVE, "GROOVE_FAR_STATION"),),
        ),
        "callout": (groove.GROOVE_CALLOUT, ((_GROOVE, "GROOVE_CALLOUT"),)),
        "note": (groove.GROOVE_NOTE_TEXT, ((_GROOVE, "GROOVE_NOTE_TEXT"),)),
    },
    precision={
        "dia": _P["GrooveDia"],
        "station": _P["GrooveStation"],
        "end_station": _P["GrooveEndStation"],
    },
)
# The adjuster stud's #0-80 blind tap in the top face, on the axis: its
# wizard callout (tap drill .XXX under DRILLED HOLES, both depths .XX) and
# RV-01's tap wall .067 MIN (END_KEEP "TapWallMin").
requirement(
    "stud_tap",
    kind="threaded_hole",
    faces=(CylinderFace(rod.STUD_TAP_DRILL_DIA),),
    requirements=("thread", "dia", "drill_depth", "thread_depth", "wall_min"),
    fields={
        "at": ([0.0, rod.SQUARE_LENGTH, 0.0], (_FRAME, "SQUARE_LENGTH")),
        "axis": ([0.0, -1.0, 0.0], (_FRAME,)),
        "thread": (
            f"{rod.STUD_THREAD} UNF-{rod.STUD_TAP_SPEC.thread_class}",
            ("STUD_THREAD", "STUD_TAP_SPEC"),
        ),
        "dia": (
            drilled_limits(rod.STUD_TAP_DRILL_DIA, _TAP_DRILL_PLACES, unit=rod.UNIT),
            ("STUD_TAP_DRILL_DIA", "UNIT", (_SELF, "STUD_TAP_PRECISION")),
        ),
        "nominal_dia": (rod.STUD_TAP_DRILL_DIA, ("STUD_TAP_DRILL_DIA",)),
        "process": ("drill", ("STUD_TAP_SPEC",)),
        "drill_depth": (
            limits(
                rod.STUD_TAP_SPEC.depth_mm, rod.STUD_TAP_DEPTH_PLACES, unit=rod.UNIT
            ),
            ("STUD_TAP_SPEC", "STUD_TAP_DEPTH_PLACES", "UNIT"),
        ),
        "drill_depth_nominal": (rod.STUD_TAP_SPEC.depth_mm, ("STUD_TAP_SPEC",)),
        "thread_depth": (
            limits(
                rod.STUD_TAP_SPEC.overrides_mm["ThreadDepth"],
                rod.STUD_TAP_DEPTH_PLACES,
                unit=rod.UNIT,
            ),
            ("STUD_TAP_SPEC", "STUD_TAP_DEPTH_PLACES", "UNIT"),
        ),
        "thread_depth_nominal": (
            rod.STUD_TAP_SPEC.overrides_mm["ThreadDepth"],
            ("STUD_TAP_SPEC",),
        ),
        "wall_min": (
            rod.TAP_WALL_MIN_MM,
            ("TAP_WALL_MIN_MM", "TAP_WALL_MIN_TOL_TYPE", (_SELF, "END_KEEP")),
        ),
        "wall_callout": (rod.TAP_WALL_CALLOUT, ("TAP_WALL_CALLOUT",)),
    },
    precision={
        "dia": _TAP_DRILL_PLACES,
        "drill_depth": rod.STUD_TAP_DEPTH_PLACES,
        "thread_depth": rod.STUD_TAP_DEPTH_PLACES,
        "wall_min": _P["TapWallMin"],
    },
)


def _add_view_arrow(adapter: Any, side: Any) -> None:
    """VIEW A's letter arrow on the side view, square onto the top face
    (draw_fr_top_frame._add_view_arrow, the letter on the arrow's right)."""
    text_xy, tip_xy = VIEW_A_ARROW
    label = f"view {END_VIEW_LETTER} viewing arrow"
    note = add_leader_note(
        adapter, END_VIEW_LETTER, text_xy=text_xy, attach_xy=tip_xy, view=side, label=label
    )
    points = square_view_arrow(
        adapter, note, text_xy=text_xy, tip_xy=tip_xy, axis=1, label=label,
        letter_height=VIEW_LETTER_HEIGHT,
    )
    if points[0] <= tip_xy[0]:
        raise RuntimeError(f"{label} does not point left onto the top face: {points}")


def _lay_side_view_horizontal(adapter: Any, side: Any) -> None:
    """Turn "*Front" by SIDE_ROTATION (rod axis horizontal) and read it back."""
    native = _early_bound(side, "IView")
    native.Angle = SIDE_ROTATION
    rebuild_drawing(adapter, label="lay pen-rod side view horizontal")
    applied = float(native.Angle)
    if abs(math.remainder(applied - SIDE_ROTATION, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError(
            f"pen-rod side view rotation did not take: {applied!r} rad, "
            f"expected {SIDE_ROTATION!r}"
        )


def _prove_side_view_frame(adapter: Any, side: Any) -> None:
    """Every side-view keep, pick and text position is computed in the
    _sx/_sy frame; project the stations it rests on through the turned view
    (ModelToViewTransform) and stop if any lands off it -- the end faces
    prove the axis runs +x at scale and the view centres on its bounding
    box, the square's +X flat at the shoulder that model +X points down."""
    stations = {
        "pivot end": ((0.0, -PIVOT_LENGTH, 0.0), (_sx(-PIVOT_LENGTH), _sy(0.0))),
        "top face": ((0.0, SQUARE_LENGTH, 0.0), (_sx(SQUARE_LENGTH), _sy(0.0))),
        "shoulder +X flat": ((_HALF, 0.0, 0.0), (_sx(0.0), _sy(_HALF))),
    }
    projected = model_points_in_view(
        adapter,
        side,
        [tuple(value / 1000.0 for value in model) for model, _ in stations.values()],
        label="pen-rod side view frame",
        names=list(stations),
    )
    misses = {
        name: (sheet, expected)
        for (name, (_, expected)), sheet in zip(stations.items(), projected)
        if math.dist(sheet, expected) > _FRAME_TOL_M
    }
    if misses:
        raise RuntimeError(f"pen-rod side view is not in its layout frame: {misses}")
    _telemetry.info(f"pen-rod side view frame: {dict(zip(stations, projected))}")


def _activate_view(adapter: Any, view: Any, *, label: str) -> str:
    """Make ``view`` the active view (sketch entities and notes land in it)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


@_telemetry.traced("pen_rod.exact_circle", label_param="label")
def _exact_circle(
    adapter: Any,
    view: Any,
    center: tuple[float, float],
    radius: float,
    *,
    label: str,
) -> Any:
    """Sketch a circle in the ACTIVE ``view``'s own sketch from sheet points,
    straight to the sketch database (no inference snapping the centre or rim
    to view geometry), and read it back (draw_mg_wheel_axle._exact_circle)."""
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError(f"failed to sketch the {label} circle")
    actual_centre, actual_radius = native_circle_geometry(circle, label=label)
    asked_radius = math.dist(points[0], points[1])
    _telemetry.info(
        f"{label} circle: centre {actual_centre} (asked {points[0]}), radius "
        f"{actual_radius} (asked {asked_radius})"
    )
    if (
        math.dist(actual_centre, points[0]) > CIRCLE_TOL_M
        or abs(actual_radius - asked_radius) > CIRCLE_TOL_M
    ):
        raise RuntimeError(f"the {label} circle moved or changed radius")
    return circle


@_telemetry.traced("pen_rod.detail_place")
def _placed_detail_view(adapter: Any) -> Any:
    """DETAIL B, uncropped: a 5:1 *Front model view turned like the side view
    and moved so the fence's focus lands on DETAIL_CENTER; a groove floor
    corner is projected too, so a view at another scale or handing than
    _detail_xy assumes raises."""
    draw = adapter.currentModel
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *DETAIL_CENTER, scale=DETAIL_SCALE),
        "IView",
    )
    view.Angle = SIDE_ROTATION
    if abs(math.remainder(float(view.Angle) - SIDE_ROTATION, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to rotate the groove detail")
    draw.EditRebuild3()
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != tuple(float(value) for value in DETAIL_SCALE):
        raise RuntimeError(f"groove detail scale {ratio!r}, expected {DETAIL_SCALE!r}")
    center = model_point_in_view(
        adapter, view, _DETAIL_FOCUS_M, label="groove detail focus"
    )
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + DETAIL_CENTER[axis] - center[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to move the groove detail onto its sheet position")
    draw.EditRebuild3()
    corner_mm = (groove.GROOVE_DIA / 2.0, -groove.GROOVE_NEAR_STATION)
    for point, expected, label in (
        (_DETAIL_FOCUS_M, DETAIL_CENTER, "groove detail focus"),
        (
            (corner_mm[0] / 1000.0, corner_mm[1] / 1000.0, 0.0),
            _detail_xy(*corner_mm),
            "groove floor's shoulder-side corner",
        ),
    ):
        found = model_point_in_view(adapter, view, point, label=label)
        if math.dist(found, expected) > DETAIL_POSITION_TOL_M:
            raise RuntimeError(f"{label} sits at {found!r}, not {expected!r}")
    return view


@_telemetry.traced("pen_rod.detail_crop")
def _crop_detail_view(adapter: Any, view: Any) -> None:
    """Crop DETAIL B to its exact fence circle round DETAIL_CENTER; status,
    IsCropped, the outline and its style are read back and raise."""
    draw = adapter.currentModel
    view = _early_bound(view, "IView")
    uncropped = tuple(float(value) for value in view.GetOutline())
    name = _activate_view(adapter, view, label="groove detail")
    circle = _exact_circle(
        adapter, view, DETAIL_CENTER, DETAIL_CROP_RADIUS, label="groove-detail crop"
    )
    selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
    data = _early_bound(selection.CreateSelectData(), "ISelectData")
    data.View = view
    if _early_bound(circle, "ISketchSegment").Select4(False, data) is not True:
        raise RuntimeError("cannot select the groove-detail crop circle")
    status = int(view.Crop2(False, False, 1))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    outline = tuple(float(value) for value in view.GetOutline())
    _telemetry.info(
        f"pen-rod: groove detail {name!r}, Crop2 status {status}, IsCropped "
        f"{cropped}, outline {tuple(round(value * 1000, 1) for value in outline)} mm",
        crop_status=status,
        cropped=cropped,
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"groove detail is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    # Uncropped, the 5:1 view spans the whole 122 rod (~610 mm of sheet), the
    # crop 46 mm, so a crop that took at least halves the width.
    if (
        len(outline) != 4
        or len(uncropped) != 4
        or outline[2] - outline[0] > (uncropped[2] - uncropped[0]) / 2.0
    ):
        raise RuntimeError(
            f"groove-detail crop did not take: outline {outline!r}, before {uncropped!r}"
        )
    boundary = (bool(view.CropViewJaggedOutline), bool(view.CropViewNoOutline))
    if boundary != (False, False):
        raise RuntimeError(
            f"groove detail's crop boundary is not its plain circle: jagged, "
            f"no-outline {boundary!r}"
        )


_ANNOTATION_DISPLAY_DIMENSION = 4  # swAnnotationType_e.swDisplayDimension


def _view_dimension_names(adapter: Any, view: Any) -> list[str]:
    """The model-dimension names ``view`` holds, sorted (notes skipped)."""
    annotations = (
        _early_bound(annotation, "IAnnotation")
        for annotation in (_early_bound(view, "IView").GetAnnotations() or ())
    )
    return sorted(
        name
        for name in (
            dimension_name(adapter, annotation)
            for annotation in annotations
            if int(annotation.GetType()) == _ANNOTATION_DISPLAY_DIMENSION
        )
        if name
    )


@_telemetry.traced("pen_rod.detail_dimensions")
def _dimension_then_crop_detail(adapter: Any, detail: Any) -> list[Any]:
    """Import and curate DETAIL B's dimensions uncropped, then crop it; any
    kept dimension the crop drops raises."""
    annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="groove detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    before = _view_dimension_names(adapter, detail)
    _crop_detail_view(adapter, detail)
    after = _view_dimension_names(adapter, detail)
    lost = sorted(set(DETAIL_KEEP) - set(after))
    _telemetry.event(
        "groove_detail.crop",
        dimensions_before=",".join(before),
        dimensions_after=",".join(after),
        lost=",".join(lost),
    )
    if lost:
        raise RuntimeError(
            f"groove detail lost {lost} to its crop; before {before}, after {after}"
        )
    return annotations


@_telemetry.traced("pen_rod.detail_mark")
def _mark_detail_on_side(adapter: Any, side: Any) -> None:
    """Circle DETAIL B's fence on the side view in the outline's black."""
    _activate_view(adapter, side, label="side view")
    center = model_point_in_view(
        adapter, side, _DETAIL_FOCUS_M, label="groove detail mark"
    )
    circle = _exact_circle(
        adapter,
        side,
        center,
        DETAIL_RADIUS_MM * _SIDE_K,
        label="groove-detail mark",
    )
    segment = _early_bound(circle, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError("groove-detail mark circle colour did not persist")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()


def _plain_text(text: str) -> str:
    """A note's words with its line breaks and spacing folded to single spaces."""
    return " ".join(str(text).split())


_NOTE_POSITION_TOL_M = 1e-5


def _add_view_note(
    adapter: Any, view: Any, text: str, xy: tuple[float, float], *, label: str
) -> None:
    """A free note in ``view`` at ``xy`` (its top-left corner); a note that
    did not land in its view, or did not keep its position, raises."""
    _activate_view(adapter, view, label=label)
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to add the {label} note")
    annotation = _early_bound(
        _early_bound(note, "INote").GetAnnotation(), "IAnnotation"
    )
    position = tuple(float(value) for value in (annotation.GetPosition() or ()))
    if len(position) < 2 or math.dist(position[:2], xy) > _NOTE_POSITION_TOL_M:
        raise RuntimeError(f"{label} note sits at {position!r}, not {xy!r}")
    texts = [
        _plain_text(_early_bound(found, "INote").GetText() or "")
        for found in (_early_bound(view, "IView").GetNotes() or ())
    ]
    if texts.count(_plain_text(text)) != 1:
        raise RuntimeError(f"{label} note did not land in its view: {texts!r}")


@_telemetry.traced("pen_rod.detail_label")
def _label_detail(adapter: Any, detail: Any, side: Any) -> None:
    """Label DETAIL B beside its crop and letter its mark on the side view."""
    sheet = _early_bound(
        _early_bound(adapter.currentModel, "IDrawingDoc").GetCurrentSheet(), "ISheet"
    )
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError(
            "failed to pin sheet scale before labelling the groove detail"
        )
    for view, text, xy, label in (
        (detail, DETAIL_LABEL_TEXT, DETAIL_LABEL_XY, "groove-detail label"),
        (side, DETAIL_LETTER, PARENT_LETTER_XY, "groove-detail letter"),
    ):
        _add_view_note(adapter, view, text, xy, label=label)


def _set_arrow_sides(adapter: Any, annotations: list[Any]) -> None:
    """Stand each ARROW_SIDES dimension's arrows on its side and read the
    side back (draw_dt_cone_tip_block's _set_arrow_sides): the layout above
    is proven against those arrows, not the sheet's automatic choice."""
    remaining = dict(ARROW_SIDES)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        side = remaining.pop(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArrowSide = side
        if int(display.ArrowSide) != side:
            raise RuntimeError(f"{name} did not keep its arrows on side {side}")
    if remaining:
        raise RuntimeError(
            f"no pen-rod dimension to set arrow sides: {sorted(remaining)}"
        )


def _dress_shoulder_radius(adapter: Any, annotations: list[Any]) -> None:
    """Prove the side view's imported ShoulderRadius prints the part's R MAX
    with its callout, and stop its leader at the corner.

    Read back: radial (not a diameter), measuring SHOULDER_FILLET_R, the
    native swTolMAX the part set, and the mate callout under the value.  The
    text stands down-right of the corner (the vertical layout's up-right,
    turned with the view), outside the arc's own quadrant, so the leader
    ends on the arc's extension; ``ArcExtensionLineOrOppositeSide`` False
    keeps it from running on through the arc centre into the pivot
    (draw_dt_arbor_pedestal's crown, draw_fr_harmonic_base's corner arcs).
    """
    found = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == "ShoulderRadius"
    ]
    if len(found) != 1:
        raise RuntimeError(
            f"expected one ShoulderRadius on the side view, found {len(found)}"
        )
    annotation = _early_bound(found[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError("the imported shoulder radius is not radial")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != SHOULDER_FILLET_TOL_TYPE:
        raise RuntimeError(
            f"ShoulderRadius lost its native MAX type: {int(tolerance.Type)}"
        )
    if not math.isclose(
        float(dimension.SystemValue), SHOULDER_FILLET_R / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError("ShoulderRadius does not measure the shoulder fillet")
    callout = str(display.GetText(4) or "")  # swDimensionTextCalloutBelow
    if callout != DIMENSION_CALLOUTS["ShoulderRadius"]:
        raise RuntimeError(f"ShoulderRadius callout did not persist: {callout!r}")
    display.ArcExtensionLineOrOppositeSide = False
    if display.ArcExtensionLineOrOppositeSide is not False:
        raise RuntimeError("ShoulderRadius leader still runs to the opposite side")
    _telemetry.info(
        f"shoulder radius: text {display.GetText(1)!r}, MAX type, callout {callout!r}"
    )


def _offset_tap_wall_text(adapter: Any, annotations: list[Any]) -> None:
    """Park the tap wall's text on its leader shelf and read it back."""
    offset_dimension_text(adapter, annotations, {"TapWallMin": TAP_WALL_TEXT_XY})
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        if dimension_name(adapter, annotation) != "TapWallMin":
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        position = annotation.GetPosition()
        if (
            not bool(display.OffsetText)
            or position is None
            or math.dist(position[:2], TAP_WALL_TEXT_XY) > _TEXT_SETTLE_M
        ):
            raise RuntimeError(
                f"tap wall text at {position!r}, not offset to {TAP_WALL_TEXT_XY!r}"
            )


def _center_mark_count(view: Any) -> int:
    """The view's centre-mark annotations (a bare view answers None)."""
    return len(
        _early_bound(view, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )


def _edge_inventory(edges: ViewEdges, y_mm: float) -> str:
    """The scan's lines and circles near model y ``y_mm`` (1 mm either
    side), so a failed pick names what the view really holds there."""
    rows = []
    for item in edges.edges:
        if item.line is not None:
            start, end = item.line
            if min(abs(start[1] - y_mm), abs(end[1] - y_mm)) <= 1.0:
                rows.append(f"line {start}-{end}")
        elif item.circle is not None:
            if abs(item.circle[1] - y_mm) <= 1.0:
                rows.append(f"circle {item.circle}")
    return f"{len(rows)} of {len(edges.edges)} edges near y {y_mm:g}: {rows}"


def _top_face_edge(edges: ViewEdges) -> Any:
    """The square's top-face edge nearest the viewer: the visible straight
    edge from (-S/2, SQUARE_LENGTH, +S/2) to (+S/2, SQUARE_LENGTH, +S/2)
    (the far edge at z -S/2 projects onto it, so z pins the one picked)."""
    ends = ((-_HALF, SQUARE_LENGTH, _HALF), (_HALF, SQUARE_LENGTH, _HALF))
    found = [
        item
        for item in edges.lines
        if all(
            any(math.dist(point, end) <= _EDGE_TOL_MM for end in ends)
            for point in item.line
        )
        and item.length_mm > ROD_SECTION / 2.0
    ]
    if len(found) != 1:
        raise RuntimeError(
            f"expected one visible top-face edge across the square, found "
            f"{len(found)}; {_edge_inventory(edges, SQUARE_LENGTH)}"
        )
    return found[0].edge


def _pivot_end_edge(edges: ViewEdges) -> Any:
    """The pivot's end-face rim: the Ø PIVOT_DIA circle on the rod axis at
    y -PIVOT_LENGTH, seen edge-on in the side view."""
    try:
        return edges.circle_at(
            (0.0, -PIVOT_LENGTH, 0.0),
            PIVOT_DIA / 2.0,
            axis=(0.0, 1.0, 0.0),
            label="pivot end rim",
        ).edge
    except RuntimeError as error:
        raise RuntimeError(
            f"{error}; {_edge_inventory(edges, -PIVOT_LENGTH)}"
        ) from error


@_telemetry.traced("drawing.pen_rod.overall_reference")
def _overall_reference(adapter: Any, side: Any) -> None:
    """(4.82): top face to pivot end, a reference the square and pivot
    lengths own (rule 10); a drawing-added edge dimension between two
    scanned entities, proved attached to exactly them and measuring
    TOTAL_LENGTH before it is parenthesised."""
    label = "pen-rod overall length reference"
    # Scanned after every display change to the side view (turn, HLR).
    edges = scan_view_edges(side, label="pen-rod side")
    picks = (_top_face_edge(edges), _pivot_end_edge(edges))
    display = add_edge_dimension(
        adapter,
        side,
        # Documentation only: both picks are by entity.
        p0=OVERALL_TOP_SHEET_XY,
        p1=OVERALL_END_SHEET_XY,
        text_xy=OVERALL_REF_XY,
        label=label,
        # SHEET horizontal: the turned view's axis runs along sheet x (a
        # turned view's vertical measured its sheet-vertical model +Z in
        # draw_mg_magnifying_bracket's _arm_end_reference).
        orientation="horizontal",
        entities=picks,
    )
    display = _early_bound(display, "IDisplayDimension")
    dimension_type = int(display.Type2)
    # swLinearDimension, swHorLinearDimension
    if dimension_type not in (2, 11):
        raise RuntimeError(
            f"{label}: expected a linear dimension, got type {dimension_type}"
        )
    # The rim lies in the plane y -PIVOT_LENGTH, so any arc end condition reads the
    # same distance; the attachments and the value prove the picks.
    assert_dimension_measures(
        adapter,
        display,
        expected_mm=TOTAL_LENGTH,
        label=label,
        entities=picks,
        tolerance_mm=1e-3,
    )
    set_reference_dimension(adapter, display.GetAnnotation(), label=label)
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError(f"{label} precision did not persist")


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-rod source", adapter.open_model(str(SOURCE)))
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
            "End View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("pn-pen-rod"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen rod; square brass slide rod; turned pivot end; tapped top",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=SIDE_SCALE)
    # Turned before HLR, the edge scan and every import, so each lands in
    # the horizontal frame; proved against _sx/_sy before anything uses it.
    _lay_side_view_horizontal(adapter, side)
    _prove_side_view_frame(adapter, side)
    end = place_view(adapter, str(SOURCE), "*Top", *END_CENTER, scale=END_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The iso too: a new view already reads Shaded With Edges, so
    # finalize_drawing's SetDisplayMode4 is a no-op that leaves its cosmetic
    # threads at draft quality (farm c0b95549c readback cosmetic_threads=False).
    # From HLR the shading call really changes the mode and takes precision.
    for view in (side, end, iso):
        set_hidden_lines_removed(adapter, view)

    # DETAIL B is placed and dimensioned FIRST: the groove's dimensions live
    # in a Front-plane sketch the side view would import too, and a dimension
    # already on the sheet is never imported again (draw_mg_wheel_axle).
    detail = _placed_detail_view(adapter)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = _dimension_then_crop_detail(adapter, detail)

    # PivotDia imports straight into the side view: every farm leaf of the
    # vertical layout logged its targeted *Front import delivering it
    # (unrequested, then deleted), so the turned pivot's banded diameter is
    # dimensioned between its flanks where the lathe reads it (rule 11).
    annotations = [
        *detail_annotations,
        *curate_view_dimensions(
            adapter,
            side,
            keep=SIDE_KEEP,
            view_label="side",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            end,
            keep=END_KEEP,
            view_label="end",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _dress_shoulder_radius(adapter, annotations)
    _set_arrow_sides(adapter, annotations)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _offset_tap_wall_text(adapter, annotations)
    # The template may centre-mark the tap as the view is placed: farm run
    # 20261023T212137739Z's layout audit found two identical marks on it
    # (duplicate-annotation, fleet issue #913) after the explicit call.  Mark
    # only a bare view, then prove the tap carries exactly one.
    if _center_mark_count(end) == 0 and not auto_center_marks(
        adapter, end, holes=True, size=0.0025
    ):
        raise RuntimeError("failed to add ASME center mark to the stud tap")
    if (found := _center_mark_count(end)) != 1:
        raise RuntimeError(
            f"end view carries {found} centre marks, not the stud tap's one"
        )

    # Pick the tap-drill rim, not the cosmetic thread or the hole centre.
    stud_callout = add_native_hole_callout(
        adapter,
        end,
        edge_xy=(_end_x(END_CENTER, STUD_TAP_DRILL_DIA / 2.0), END_CENTER[1]),
        callout_xy=TAP_CALLOUT_XY,
        label="adjuster stud blind tap",
    )
    # Size first (rule 26): no process prefix; the title block's THREADS row
    # owns the general thread class (rule 2).
    omit_title_block_thread_class(stud_callout, label="adjuster stud blind tap")
    set_hole_callout_precision(
        stud_callout, STUD_TAP_PRECISION, label="adjuster stud blind tap"
    )

    _overall_reference(adapter, side)
    _add_view_arrow(adapter, side)
    # The mark and the labels go on once every side-view pick is done, so no
    # coordinate pick meets the mark circle.
    _mark_detail_on_side(adapter, side)
    _label_detail(adapter, detail, side)

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "End View Note", *END_NOTE_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    # Materialize the iso's cosmetic thread before the strict final note cleanup;
    # otherwise its descriptive label first appears during the native drawing save.
    import_cosmetic_threads(adapter, iso)

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Rod Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=(f"{STUD_TAP_SPEC.size} Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
