r"""Create the curated machinist drawing for the pinion return leaf spring.

NOT a coil spring: a bent 17-7 PH stainless leaf.  A .015 blank -- a 1/4 in
strip with a square screw pad at its free end -- formed as a flat screw-down
foot, an R.130 bend up to a blade leaning back over the foot's bend, then an
R.130 crest turning 25 deg out to a short free flat.  The solid is the installed shape;
the front view also shows the part's hidden FreeForm reference sketch as the
phantom free form; the bend and the free crest are baselined from the pad
hole's axis (the screw) on it.  The projected top view carries the blank's
pad (its wing also from the hole's axis), its bend relief, the strip width
and the hole; a 5:1 detail carries the installed crest's radius and flat and,
on the phantom free crest beside it, the kink's included angle between its
drawn legs.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_pinion_spring.py dt-pinion-spring
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    view_name,
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
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edge_dimensions import add_edge_dimension
import _drawing_hidden_sketches as hidden_sketches
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from dt_pinion_spring_geometry import (
    BEND_CX,
    FLAT_TIP,
    FOOT_END,
    FOOT_TAN,
    FREE_FLAT_TIP,
    FREE_KINK_EXIT,
    FREE_KINK_INCLUDED_BISECTOR,
    FREE_KINK_START,
    FREE_KINK_VERTEX,
    HOLE_DIA,
    HOLE_FROM_END,
    KINK_C,
    KINK_EXIT,
    KINK_INCLUDED_DEG,
    PAD_WIDTH,
    PAD_WING_LEN,
    PAD_Z,
    R_KINK,
    THICK,
    WIDTH,
)
from dt_pinion_spring_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FREE_KINK_ANGLE,
    HOLE_CALLOUT_PRECISION,
    PAD_LEN_CALLOUT,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["dt_pinion_spring"]
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

SHEET_SCALE = (2.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0

# Front view (XY): the profile -- the foot along the bottom running right to
# its free end, the blade rising at the left and leaning back over the bend.
# Views centre on their bounding boxes; the profile spans the crest's outer
# face to the foot's free end and the foot's underside to the free tip.
_PROFILE_MIN_X = KINK_C[0] - (R_KINK + THICK)
FRONT_BBOX_CX = (_PROFILE_MIN_X + FOOT_END[0]) / 2.0
FRONT_BBOX_CY = (FLAT_TIP[1] + THICK) / 2.0
FRONT_CENTER = (0.110, 0.118)
# Third-angle projection: the top view sits ABOVE the front and shares its X
# station (both views span the same model x range), so the pad and hole read
# straight up from the profile's free end.
TOP_CENTER = (FRONT_CENTER[0], 0.228)
ISO_CENTER = (0.350, 0.150)
# Detail A is a cropped 5:1 *Front MODEL view, not a native detail view.  The
# native detail's targeted import of SpringProfile brought FlatLen in pc-r11
# and pc-r12 but only KinkR in pc-r13 (leaf 20260927T001822Z-1-ba1f4546),
# with the same script and a dimensionally identical part; a cropped model
# view takes a targeted import like any principal view (MHA-DT-22's detail A,
# 522920510; draw_crank_arm's top view).  Its crop circle's centre is where
# pc-r12 printed the native detail's.
DETAIL_CENTER = (0.240, 0.184)
DETAIL_SCALE = (5, 1)
DETAIL_RATIO = DETAIL_SCALE[0] / DETAIL_SCALE[1]
# The kink detail's fence takes both crests: the phantom free crest, whose
# kink angle prints between its drawn blade and flat (machinist review
# 69eda6e4c: at 2:1 the 155 deg vertex floated on a faint phantom and its
# extension lines followed no drawn edge), and the installed crest with its
# radius and flat.  Centred between the free vertex and the installed crest's
# centre, it holds both, the free legs out past the angle's arc and the
# installed flat's tip (test_kink_crop_holds_its_dimensions_and_labels...).
DETAIL_FOCUS = (
    (FREE_KINK_VERTEX[0] + KINK_C[0]) / 2.0,
    (FREE_KINK_VERTEX[1] + KINK_C[1]) / 2.0,
)
DETAIL_RADIUS_MM = 5.0
DETAIL_CROP_RADIUS = DETAIL_RATIO * DETAIL_RADIUS_MM / 1000.0
DETAIL_LETTER = "A"
# A model view has no native label the API can show, so the label is a note
# the view owns, in the native detail label's words, its top edge this far
# under the crop circle (where pc-r12's native label sat).
DETAIL_LABEL_TEXT = (
    f"DETAIL {DETAIL_LETTER}\nSCALE {DETAIL_SCALE[0]} : {DETAIL_SCALE[1]}"
)
DETAIL_LABEL_DROP = 0.007
DETAIL_LABEL_XY = (
    DETAIL_CENTER[0],
    DETAIL_CENTER[1] - DETAIL_CROP_RADIUS - DETAIL_LABEL_DROP,
)
# The fence's "A" goes EAST of the fence, level with its centre: above it,
# it sat on the FREE, TO KINK TANGENT row (stacktop-dbe47ae3, spring-r1);
# west, the free-form phantom ran under it (PR #1675 review r1).  East of the
# fence is the open bay between the blade and the hole axis's extension line
# up to FreeKinkH's row, which the letter stays 2 mm west of.
PARENT_LETTER_OFFSET = (DETAIL_RADIUS_MM * _S + 0.0025, 0.002)
# swCropViewErrors_e.swCropViewErrors_NoError
CROP_NO_ERROR = 1
# The kink focus must land within 0.1 mm of DETAIL_CENTER after the move.
DETAIL_POSITION_TOL_M = 1e-4
NOTE_CENTRING_TOL_M = 0.001
NOTE_CENTRING_PASSES = 2


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + (model_x_mm - FRONT_BBOX_CX) * _S


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * _S


_FOOT_MID_X = (FOOT_END[0] + FREE_KINK_START[0]) / 2.0
_PROFILE_TOP = _front_y(max(FLAT_TIP[1], FREE_FLAT_TIP[1]))
_PAD_EAST = _front_x(FOOT_END[0])
# The pad hole's axis, the profile's and the wing's datum (the screw).
_HOLE_AXIS_X = _front_x(FOOT_END[0] - HOLE_FROM_END)
# Half the printed width of each qualified dimension's text lines, as pc-r12's
# render measured them (sheet metres, 11.8 px/mm; the preload line scaled
# from those).  A text wider than its own dimension goes east of the hole
# axis's extension line, which the FootLen and FreeKinkH rows share:
# centred between the extension lines, pc-r12 printed those lines through
# FREE, BEND and TANGENT.
PRELOAD_REASON = "SETS PRELOAD ON MHA-DT-14"
QUALIFIER_HALF_WIDTH = {
    "FREE, TO KINK TANGENT": 0.026,
    "TO BEND TANGENT": 0.021,
    PRELOAD_REASON: 0.033,
    PAD_LEN_CALLOUT: 0.024,
}
# The dimensions banded +/-0.5 set the crest's preload on the MHA-DT-14 strap
# (dt_pinion_spring_spec.FORMED_BANDED_DIMENSIONS), so each names that mate
# (drawing-guidelines.md rule 4); the kink angle and FlatLen ride the
# title-block rows, bare.  The wing, located from the hole's axis at .XX,
# clears the bend at FootLen's low limit, and the web it leaves the hole is
# stated (rule 20; Codex, PR #1675).
DIMENSION_CALLOUTS = {
    "FootLen": f"TO BEND TANGENT\n{PRELOAD_REASON}",
    "FreeKinkH": f"FREE, TO KINK TANGENT\n{PRELOAD_REASON}",
    "FreeKinkV": f"FREE, TO KINK TANGENT\n{PRELOAD_REASON}",
    "BendR": PRELOAD_REASON,
    "KinkR": PRELOAD_REASON,
    "PadLen": PAD_LEN_CALLOUT,
}


def callout_half_width(name: str) -> float:
    """Half the printed width of ``name``'s widest callout line."""
    return max(QUALIFIER_HALF_WIDTH[line] for line in DIMENSION_CALLOUTS[name].split("\n"))


TEXT_TO_EXTENSION_GAP = 0.003
_KINK_TEXT_X = _HOLE_AXIS_X + TEXT_TO_EXTENSION_GAP + callout_half_width("FreeKinkH")
# The kink angle's text (and so its arc) this far from the free vertex in
# detail A (sheet metres, 2.2 model mm at 5:1), down the bisector of the
# segments' own included wedge, between the blade running down and the flat
# running up: the arc ends ON both drawn phantom legs (past the flat's start,
# short of its tip), so it needs no extension line, and "155°" stands in the
# open bay between the free crest and the installed one.
KINK_ANGLE_TEXT_RADIUS = 0.011
# The legs' included wedge opens away from the crest's convex side.
KINK_ARC_BISECTOR = (-FREE_KINK_INCLUDED_BISECTOR[0], -FREE_KINK_INCLUDED_BISECTOR[1])
# The arc ends on the drawn flat, between its start and its tip (sheet
# metres, the free vertex's distances to them at the detail's scale); the
# blade, below, is drawn far longer than either.
KINK_ARC_RADIUS_RANGE = tuple(
    math.dist(FREE_KINK_VERTEX, point) * DETAIL_RATIO / 1000.0
    for point in (FREE_KINK_EXIT, FREE_FLAT_TIP)
)
# The arc must centre on the vertex and every drawn point lie within this of
# the wedge's bisector (half the wedge plus room for outside arrows); the
# acute wedges' arcs reach 102.5 deg off it, the opposite included one's more.
KINK_ARC_CENTRE_TOL = 0.0005
KINK_ARC_HALF_SPREAD_DEG = KINK_INCLUDED_DEG / 2.0 + 15.0
FRONT_KEEP = {
    "FootLen": (
        _HOLE_AXIS_X + TEXT_TO_EXTENSION_GAP + callout_half_width("FootLen"),
        _front_y(0.0) - 0.010,
    ),
    # West of the foot's bend tangent extension line, which runs down past
    # the radius's two-line text.
    "BendR": (_front_x(BEND_CX) - 0.045, _front_y(0.0) - 0.004),
    # The free locations, on the FreeForm phantom.  FreeKinkV's dimension
    # line runs where its text sits, east of the foot end.
    "FreeKinkV": (_KINK_TEXT_X, _front_y(FREE_KINK_START[1] / 2.0)),
    # East of the hole axis on the outer row: the kink row's text does not
    # fit between its extension lines.  The top view stands clear above it
    # (spring r1: the row's text met the pad's edge).
    "FreeKinkH": (_KINK_TEXT_X, _PROFILE_TOP + 0.032),
}
# The vertical extension lines each qualified row's text sits among: its own
# two, the hole axis's being the east one of both horizontal rows.
FRONT_ROW_EXTENSION_X = {
    "FootLen": (_front_x(FOOT_TAN[0]), _HOLE_AXIS_X),
    "FreeKinkV": (_HOLE_AXIS_X,),
    "FreeKinkH": (_front_x(FREE_KINK_START[0]), _HOLE_AXIS_X),
}
# Top view (third-angle: model +z, forward, runs DOWN the sheet).  The view
# centres on the pad, so the hole centre is level with TOP_CENTER, the strip's
# aft edge (flush with the pad's) 9.5 mm (sheet) above it, the strip's forward
# edge 3.2 below and the pad's forward edge 9.5 below.
_TOP_AFT = TOP_CENTER[1] + (PAD_Z + WIDTH / 2.0) * _S
_TOP_STRIP_FWD = TOP_CENTER[1] + (PAD_Z - WIDTH / 2.0) * _S
_TOP_PAD_FWD = TOP_CENTER[1] - PAD_WIDTH / 2.0 * _S
_WING_WEST = _front_x(FOOT_END[0] - PAD_WING_LEN)
TOP_KEEP = {
    # Below the pad, east of the hole axis's extension line: its text centred
    # between its extension lines was struck by them, and the relief's leader
    # ran into it (spring r13).
    "PadLen": (
        _HOLE_AXIS_X + TEXT_TO_EXTENSION_GAP + callout_half_width("PadLen"),
        _TOP_PAD_FWD - 0.009,
    ),
    # East, witnessed on the pad's free end, outboard of the hole-edge 4.75
    # (HOLE_EDGE_TEXT_XY) that shares its lower extension line.
    "PadWidth": (_PAD_EAST + 0.016, TOP_CENTER[1] + 0.003),
    # Below-left of the relief round, its leader clear of PadLen's extension
    # line up the wing's west edge and of the strip width's lines above.
    "PadReliefR": (_WING_WEST - 0.015, _TOP_PAD_FWD - 0.0055),
}


def _detail_xy(model_mm: tuple[float, float]) -> tuple[float, float]:
    """Where a front-plane model point (mm) prints in detail A (sheet metres)."""
    return (
        DETAIL_CENTER[0] + (model_mm[0] - DETAIL_FOCUS[0]) * DETAIL_RATIO / 1000.0,
        DETAIL_CENTER[1] + (model_mm[1] - DETAIL_FOCUS[1]) * DETAIL_RATIO / 1000.0,
    )


_DETAIL_KINK_C = _detail_xy(KINK_C)
_DETAIL_FREE_VERTEX = _detail_xy(FREE_KINK_VERTEX)
DETAIL_KEEP = {
    # The flick turns right (east) in this view: the radius leader goes
    # upper-left of the fence, the flat's length to its right, each where
    # 69eda6e4c printed it relative to the installed crest.
    "KinkR": (_DETAIL_KINK_C[0] - 0.0405, _DETAIL_KINK_C[1] + 0.056),
    "FlatLen": (_DETAIL_KINK_C[0] + 0.0365, _DETAIL_KINK_C[1] + 0.024),
    # The free crest's included angle, between its drawn legs.
    FREE_KINK_ANGLE: (
        _DETAIL_FREE_VERTEX[0] + KINK_ANGLE_TEXT_RADIUS * KINK_ARC_BISECTOR[0],
        _DETAIL_FREE_VERTEX[1] + KINK_ANGLE_TEXT_RADIUS * KINK_ARC_BISECTOR[1],
    ),
}
HOLE_END_TEXT_XY = (_front_x(FOOT_END[0] - HOLE_FROM_END / 2.0), _TOP_AFT + 0.0095)
# East of the pad, inboard of PadWidth: west, its extension lines ran from the
# hole through the wing and the strip.
HOLE_EDGE_TEXT_XY = (_PAD_EAST + 0.007, (_TOP_PAD_FWD + TOP_CENTER[1]) / 2.0 - 0.0016)
# The strip's width, picked on the free flat's two edges (the flat, topmost
# in this view, runs straight across the crest's top), printed west of the
# crest: east of the pad its extension lines were witnessed at nothing
# (spring r1).
STRIP_PICK_X = (KINK_EXIT[0] + FLAT_TIP[0]) / 2.0
STRIP_PICK_Y = (KINK_EXIT[1] + FLAT_TIP[1]) / 2.0
STRIP_WIDTH_TEXT_XY = (
    _front_x(_PROFILE_MIN_X) - 0.011,
    (_TOP_AFT + _TOP_STRIP_FWD) / 2.0,
)
# Above-left of the pad: below it the leader crossed the front view's FREE,
# TO TIP row (spring r1).  The note centres on this point; its leader lands
# on the hole's upper-left rim, west of the 4.50's extension line at the
# hole centre.  The 4.50's arrows stand inside its span: left smart, its
# outside tail ran west past the hole axis's extension line, and this leader
# crossed it (spring r15).
HOLE_CALLOUT_XY = (_front_x(FOOT_END[0] - HOLE_FROM_END) - 0.040, _TOP_AFT + 0.0165)
_DIM_ARROWS_INSIDE = 0  # swDimensionArrowsSide_e.swDimArrowsInside
# The #4 normal clearance (3.264 mm = 0.1285 in) is a No. 30 drill; the shop
# reaches for the number, the native size compartment still prints the diameter.
HOLE_PROCESS = "#30 DRILL"
# The pad hole where build_pinion_spring's Hole Wizard puts it (model mm): on
# the foot's top face, centred across the pad, which stands PAD_Z off the
# strip's centre plane.  The callout picks its rim upper-left (-x, -z: aft is
# up the sheet), off the centre mark's arms.  pc-r11 (0c5636eab) picked z
# HOLE_DIA/2, the rim while the pad was centred on the strip; once 6c9d4f476
# moved the pad, that point sat 0.06 mm from the hole's centre, and
# SelectByID2 found no edge there.
HOLE_CENTER = (FOOT_END[0] - HOLE_FROM_END, THICK, PAD_Z)
_RIM_DIAGONAL = HOLE_DIA / 2.0 / math.sqrt(2.0)
HOLE_EDGE_PICK = (
    HOLE_CENTER[0] - _RIM_DIAGONAL,
    HOLE_CENTER[1],
    HOLE_CENTER[2] - _RIM_DIAGONAL,
)
# The hole's axis is the datum the bend, the free kink start and the wing are
# located from, so it prints as a centreline in both views, this far past the
# part (model mm): across the foot's edge in the profile, and from the hole's
# centre mark down past the pad's forward edge, where PadLen's extension line
# leaves it, in the plan.
HOLE_AXIS_OVERSHOOT = 1.0
FRONT_HOLE_AXIS_ENDS = (
    (HOLE_CENTER[0], -HOLE_AXIS_OVERSHOOT, 0.0),
    (HOLE_CENTER[0], THICK + HOLE_AXIS_OVERSHOOT, 0.0),
)
TOP_HOLE_AXIS_ENDS = (
    HOLE_CENTER,
    (HOLE_CENTER[0], THICK, PAD_Z + PAD_WIDTH / 2.0 + HOLE_AXIS_OVERSHOOT),
)


def _activate_view(adapter: Any, view: Any, *, label: str) -> str:
    """Make ``view`` the active view (sketch entities and notes land in it)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


def _sketch_circle(
    adapter: Any,
    view: Any,
    center: tuple[float, float],
    radius: float,
    *,
    label: str,
    add_to_db: bool = False,
) -> Any:
    """Sketch a circle in the ACTIVE ``view``'s own sketch from sheet points.

    The sheet points go through the view sketch's ModelToSketchTransform (the
    recipe the native fence and draw_crank_arm's crop used).  Without
    ``add_to_db`` the circle is left SELECTED, which is what Crop2 consumes.
    """
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
    manager.AddToDB = add_to_db
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError(f"failed to sketch the {label} circle")
    return circle


def _mark_kink_on_front(adapter: Any, front: Any) -> tuple[float, float]:
    """Circle detail A's region on the front view; returns its sheet centre.

    The fence the native detail was cut from, now a plain view-sketch circle
    drawn direct to the database in the outline's black.
    """
    _activate_view(adapter, front, label="formed-profile view")
    center = model_point_in_view(
        adapter,
        front,
        (DETAIL_FOCUS[0] / 1000.0, DETAIL_FOCUS[1] / 1000.0, 0.0),
        label="kink detail centre",
    )
    circle = _sketch_circle(
        adapter,
        front,
        center,
        DETAIL_RADIUS_MM * _S,
        label="kink-detail mark",
        add_to_db=True,
    )
    segment = _early_bound(circle, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError("kink-detail mark circle colour did not persist")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    return center


def _hole_axis_centerline(
    adapter: Any,
    view: Any,
    ends_mm: tuple[tuple[float, float, float], tuple[float, float, float]],
    *,
    label: str,
) -> None:
    """A black centreline on the pad hole's axis in ``view``'s own sketch.

    draw_sm_summing_lever._owned_centerline's recipe: the part-mm ends are
    projected to the sheet, taken into the view sketch's frame, placed direct
    to the database (an inferred end snaps onto nearby edges) and read back.
    """
    _activate_view(adapter, view, label=label)
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for end in ends_mm:
        x, y = model_point_in_view(
            adapter, view, tuple(value / 1000.0 for value in end), label=f"{label} end"
        )
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        segment = manager.CreateCenterLine(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if segment is None:
        raise RuntimeError(f"failed to create the {label}")
    line = _early_bound(segment, "ISketchLine")
    for expected, accessor in zip(
        points, ("GetStartPoint2", "GetEndPoint2"), strict=True
    ):
        placed = _early_bound(adapter._get_attr_or_call(line, accessor), "ISketchPoint")
        actual = [float(adapter._get_attr_or_call(placed, axis)) for axis in "XYZ"]
        drift = max(abs(a - b) for a, b in zip(actual, expected, strict=True))
        if drift > 1e-9:
            raise RuntimeError(
                f"{label} {accessor[3:-6].lower()} point sits "
                f"{drift * 1000.0:.4g} mm from where it was authored"
            )
    segment = _early_bound(segment, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError(f"{label} colour did not persist")
    adapter.currentModel.ClearSelection2(True)
    rebuild_drawing(adapter, label=label)


def _placed_kink_view(adapter: Any) -> Any:
    """Detail A, uncropped: a standalone 5:1 *Front model view, moved so the
    kink focus lands on DETAIL_CENTER (checked to DETAIL_POSITION_TOL_M).

    The part hides FreeForm, so the view shows the installed crest until its
    curation shows the phantom free crest in it (_dimension_then_crop_kink_view).
    It is dimensioned before _crop_kink_view crops it: pc-r14 (6aebefd18,
    leaf 20260927T005429Z-1-555a9662) imported into the cropped view and got
    FlatLen but not KinkR, where the uncropped *Front imports both.
    """
    draw = adapter.currentModel
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *DETAIL_CENTER, scale=DETAIL_SCALE),
        "IView",
    )
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != tuple(float(value) for value in DETAIL_SCALE):
        raise RuntimeError(f"kink detail scale {ratio!r}, expected {DETAIL_SCALE!r}")
    focus = (DETAIL_FOCUS[0] / 1000.0, DETAIL_FOCUS[1] / 1000.0, 0.0)
    center = model_point_in_view(adapter, view, focus, label="kink detail focus")
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + DETAIL_CENTER[axis] - center[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to move the kink detail onto its sheet position")
    draw.EditRebuild3()
    center = model_point_in_view(adapter, view, focus, label="kink detail focus")
    if math.dist(center, DETAIL_CENTER) > DETAIL_POSITION_TOL_M:
        raise RuntimeError(f"kink focus sits at {center!r}, not {DETAIL_CENTER!r}")
    return view


def _crop_kink_view(adapter: Any, view: Any) -> None:
    """Crop detail A to the fence's 5:1 circle round DETAIL_CENTER.

    Activate the view, sketch the circle in its own sketch and Crop2 while
    the circle is still selected, with the circle as its outline, as the
    native detail printed it.  Crop status, IsCropped, the outline and its
    style are read back and raise.
    """
    draw = adapter.currentModel
    view = _early_bound(view, "IView")
    ratio = tuple(float(value) for value in view.ScaleRatio)
    uncropped = tuple(float(value) for value in view.GetOutline())
    name = _activate_view(adapter, view, label="kink detail")
    _sketch_circle(
        adapter, view, DETAIL_CENTER, DETAIL_CROP_RADIUS, label="kink-detail crop"
    )
    status = int(view.Crop2(False, False, 1))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    outline = tuple(float(value) for value in view.GetOutline())
    _telemetry.info(
        f"pinion-spring: kink detail {name!r} {ratio[0]:g}:{ratio[1]:g}, Crop2 "
        f"status {status}, IsCropped {cropped}, outline "
        f"{tuple(round(value * 1000, 1) for value in outline)} mm",
        crop_status=status,
        cropped=cropped,
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"kink detail is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    # The uncropped 5:1 view spans the whole ~47 mm spring (~235 mm on the
    # sheet), the crop 35 mm, so a crop that took at least halves the height.
    if (
        len(outline) != 4
        or len(uncropped) != 4
        or outline[3] - outline[1] > (uncropped[3] - uncropped[1]) / 2.0
    ):
        raise RuntimeError(
            f"kink-detail crop did not take: outline {outline!r}, before {uncropped!r}"
        )
    boundary = (bool(view.CropViewJaggedOutline), bool(view.CropViewNoOutline))
    if boundary != (False, False):
        raise RuntimeError(
            f"kink detail's crop boundary is not its plain circle: jagged, "
            f"no-outline {boundary!r}"
        )


def _view_dimension_names(adapter: Any, view: Any) -> list[str]:
    """The model-dimension names ``view`` holds, sorted."""
    return sorted(
        name
        for name in (
            dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
            for annotation in (_early_bound(view, "IView").GetAnnotations() or ())
        )
        if name
    )


def _dimension_then_crop_kink_view(adapter: Any, detail: Any) -> list[Any]:
    """Import and curate detail A's dimensions while it is uncropped, then crop.

    The free kink angle lives in the part-hidden FreeForm sketch, so the
    detail takes the opt-in curation that shows that sketch (the phantom free
    crest) in this view.  The dimension names are read back before and after
    the crop and recorded as one ``kink_detail.crop`` event, so the log shows
    whether a crop keeps dimensions already attached; any kept one missing
    afterwards raises.  Returns the curated annotations.
    """
    annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="kink detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    before = _view_dimension_names(adapter, detail)
    _crop_kink_view(adapter, detail)
    after = _view_dimension_names(adapter, detail)
    lost = sorted(set(DETAIL_KEEP) - set(after))
    _telemetry.event(
        "kink_detail.crop",
        dimensions_before=",".join(before),
        dimensions_after=",".join(after),
        lost=",".join(lost),
    )
    _telemetry.info(
        f"pinion-spring: kink detail dimensions before crop {before}, after {after}"
    )
    if lost:
        raise RuntimeError(
            f"kink detail lost {lost} to its crop; before {before}, after {after}"
        )
    return annotations


def _plain_text(text: str) -> str:
    """A note's words with its line breaks and spacing folded to single spaces."""
    return " ".join(str(text).split())


def _note_box(note: Any, *, label: str) -> tuple[float, float, float, float]:
    """``INote.GetExtent``'s lower-left and upper-right corners, sheet metres."""
    values = tuple(float(value) for value in (note.GetExtent() or ()))
    if len(values) != 6 or not all(map(math.isfinite, values)):
        raise RuntimeError(f"{label}: invalid note extent {values!r}")
    box = (values[0], values[1], values[3], values[4])
    if box[0] >= box[2] or box[1] >= box[3]:
        raise RuntimeError(f"{label}: empty note extent {values!r}")
    return box


def _note_centring_error(
    box: tuple[float, float, float, float],
    center_x: float,
    top: float | None,
    center_y: float | None,
) -> tuple[float, float]:
    """How far a note's extent sits from its target: its horizontal centre
    against ``center_x``, and its top edge against ``top`` or else its
    vertical centre against ``center_y``."""
    error_x = (box[0] + box[2]) / 2.0 - center_x
    if top is not None:
        return error_x, box[3] - top
    if center_y is None:
        raise ValueError("a centred note needs a top edge or a centre height")
    return error_x, (box[1] + box[3]) / 2.0 - center_y


def _centred_view_note(
    adapter: Any,
    view: Any,
    text: str,
    *,
    center_x: float,
    top: float | None = None,
    center_y: float | None = None,
    label: str,
) -> tuple[float, float, float, float]:
    """Insert a note owned by ``view``, centred on ``center_x`` by its extent.

    A note lands in the ACTIVE view, so the view is activated first.  The
    rendered extent (INote.GetExtent) is read and the note moved by the
    centring error; ``top`` pins its top edge, ``center_y`` its middle.  A
    note that does not centre, or lands in another view, raises.
    """
    _activate_view(adapter, view, label=label)
    y = top if top is not None else center_y
    note = add_note(adapter, text, center_x, y)
    if note is None:
        raise RuntimeError(f"failed to add the {label} note")
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    box = _note_box(note, label=label)
    for _ in range(NOTE_CENTRING_PASSES):
        error_x, error_y = _note_centring_error(box, center_x, top, center_y)
        if max(abs(error_x), abs(error_y)) <= NOTE_CENTRING_TOL_M / 10.0:
            break
        position = tuple(
            float(value) for value in _read_member(annotation, "GetPosition")
        )
        if not annotation.SetPosition2(
            position[0] - error_x, position[1] - error_y, 0.0
        ):
            raise RuntimeError(f"failed to centre the {label} note")
        adapter.currentModel.EditRebuild3()
        box = _note_box(note, label=label)
    error_x, error_y = _note_centring_error(box, center_x, top, center_y)
    _telemetry.info(
        f"pinion-spring: {label} note {text!r} extent "
        f"({box[0] * 1000:.1f}, {box[1] * 1000:.1f})-({box[2] * 1000:.1f}, "
        f"{box[3] * 1000:.1f}) mm",
        label=label,
    )
    if max(abs(error_x), abs(error_y)) > NOTE_CENTRING_TOL_M:
        raise RuntimeError(
            f"{label} note did not centre: off by ({error_x * 1000:.2f}, "
            f"{error_y * 1000:.2f}) mm"
        )
    first_line = _plain_text(text.split("\n")[0])
    texts = [
        _plain_text(_early_bound(found, "INote").GetText() or "")
        for found in (_early_bound(view, "IView").GetNotes() or ())
    ]
    if sum(found.startswith(first_line) for found in texts) != 1:
        raise RuntimeError(
            f"{label} note did not land in its view: its notes are {texts!r}"
        )
    return box


def _label_kink_detail(
    adapter: Any, detail: Any, front: Any, mark: tuple[float, float]
) -> None:
    """Label detail A under its crop circle and letter its mark on the front."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError("failed to pin sheet scale before labelling the kink detail")
    _centred_view_note(
        adapter,
        detail,
        DETAIL_LABEL_TEXT,
        center_x=DETAIL_LABEL_XY[0],
        top=DETAIL_LABEL_XY[1],
        label="kink-detail label",
    )
    _centred_view_note(
        adapter,
        front,
        DETAIL_LETTER,
        center_x=mark[0] + PARENT_LETTER_OFFSET[0],
        center_y=mark[1] + PARENT_LETTER_OFFSET[1],
        label="kink-detail letter",
    )


def kink_arc_faults(
    arcs: list[tuple[tuple[float, float], list[tuple[float, float]]]],
    vertex: tuple[float, float],
) -> list[str]:
    """Why the kink angle's drawn arcs do not read as the included wedge
    between the free form's drawn legs, the blade running down and the flat
    running up from their crossing (draw_dt_cone_gear.clock_arc_faults'
    reading): centred on the crossing, every point within
    KINK_ARC_HALF_SPREAD_DEG of the wedge's bisector, spanning it, at a
    radius that ends the arc on the drawn flat (KINK_ARC_RADIUS_RANGE), so
    no extension line runs off the legs.  Empty when they do."""
    if not arcs:
        return ["no arc"]
    bisector = math.atan2(KINK_ARC_BISECTOR[1], KINK_ARC_BISECTOR[0])
    low, high = KINK_ARC_RADIUS_RANGE
    faults = []
    offsets = []
    for centre, points in arcs:
        off = math.dist(centre, vertex)
        if off > KINK_ARC_CENTRE_TOL:
            faults.append(f"arc centred {off * 1000:.2f} mm off the vertex")
        radius = math.dist(points[0], centre) if points else 0.0
        if not low < radius < high:
            faults.append(
                f"arc radius {radius * 1000:.2f} mm ends off the drawn flat "
                f"({low * 1000:.2f}-{high * 1000:.2f} mm)"
            )
        for x, y in points:
            turn = math.atan2(y - vertex[1], x - vertex[0]) - bisector
            offsets.append(math.degrees((turn + math.pi) % (2.0 * math.pi) - math.pi))
    wide = [offset for offset in offsets if abs(offset) > KINK_ARC_HALF_SPREAD_DEG]
    if wide:
        faults.append(
            f"{len(wide)} point(s) outside the wedge, up to {max(map(abs, wide)):.1f} deg "
            "off its bisector"
        )
    if not offsets or min(offsets) > 0.0 or max(offsets) < 0.0:
        faults.append("the arcs do not span the wedge's bisector")
    return faults


def kink_arc_summary(
    arcs: list[tuple[tuple[float, float], list[tuple[float, float]]]],
    vertex: tuple[float, float],
) -> str:
    """Each drawn arc's centre offset and radius (mm) and its first, last,
    least and greatest direction off the legs' wedge bisector (deg), for the
    leaf log."""
    bisector = math.atan2(KINK_ARC_BISECTOR[1], KINK_ARC_BISECTOR[0])
    parts = []
    for centre, points in arcs:
        offsets = [
            math.degrees(
                (math.atan2(y - vertex[1], x - vertex[0]) - bisector + math.pi)
                % (2.0 * math.pi)
                - math.pi
            )
            for x, y in points
        ]
        radius = math.dist(points[0], centre) if points else 0.0
        parts.append(
            f"arc centre {math.dist(centre, vertex) * 1000:.2f} mm off, "
            f"r {radius * 1000:.2f} mm, {len(points)} pts, deg first "
            f"{offsets[0]:.1f} last {offsets[-1]:.1f}, spanning {min(offsets):.1f} "
            f"to {max(offsets):.1f}"
            if offsets
            else "empty arc"
        )
    return f"{len(arcs)} arc(s) [{' | '.join(parts)}]"


def minor_arc_points(
    centre: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
    steps: int = 16,
) -> list[tuple[float, float]]:
    """Points along the arc from ``start`` to ``end`` about ``centre`` the
    short way round.  An angle dimension's arc never sweeps past 180 deg, and
    its GetArcAtIndex2 sense flag is not read: at r9, read through the
    flag-driven tessellation (_layout_audit.arc_segments), the 155 deg arc
    had points up to 180 deg off its wedge's bisector."""
    radius = math.dist(start, centre)
    first = math.atan2(start[1] - centre[1], start[0] - centre[0])
    last = math.atan2(end[1] - centre[1], end[0] - centre[0])
    sweep = (last - first + math.pi) % (2.0 * math.pi) - math.pi
    return [
        (
            centre[0] + radius * math.cos(first + sweep * step / steps),
            centre[1] + radius * math.sin(first + sweep * step / steps),
        )
        for step in range(steps + 1)
    ]


def _kink_arcs(
    display: Any,
) -> list[tuple[tuple[float, float], list[tuple[float, float]]]]:
    data = _early_bound(display.GetDisplayData(), "IDisplayData")
    arcs = []
    for index in range(int(data.GetArcCount())):
        raw = tuple(float(value) for value in (data.GetArcAtIndex2(index) or ()))
        if len(raw) < 17:
            continue
        centre = (raw[10], raw[11])
        start, end = (raw[4], raw[5]), (raw[7], raw[8])
        _telemetry.info(
            f"kink angle arc {index}: start {start} end {end} centre {centre} "
            f"normal z {raw[15]} direction {raw[16]}"
        )
        arcs.append((centre, minor_arc_points(centre, start, end)))
    return arcs


def _assert_kink_angle_wedge(adapter: Any, detail: Any, annotations: list[Any]) -> None:
    """Fail unless detail A's kink angle draws its arc in the included wedge
    between the free form's drawn legs (kink_arc_faults).  The angle drives
    the free form, so the only turn allowed is to the vertically opposite
    wedge, the same 155 deg (the value is read back after the turn).  The
    sketch's dimension measures the segments' own wedge (spring r10: blade
    down to flat up), so an import that lands across the crossing is turned
    the way the setting bar's flank angle is
    (draw_ch_rocker_arm_tl_trammel_setting_bar): the dimension selected alone
    in its view by name -- unselected, the turn returned True and drew
    nothing new (r10) -- turned, its text re-seated at its keep, and the
    drawing rebuilt."""
    matches = [
        item for item in annotations if dimension_name(adapter, item) == FREE_KINK_ANGLE
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {FREE_KINK_ANGLE}, found {len(matches)}")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name:
        raise RuntimeError(f"{FREE_KINK_ANGLE} has no selection name")
    model = adapter.currentModel
    rebuild_drawing(adapter, label="kink angle wedge")
    vertex = model_point_in_view(
        adapter,
        detail,
        (FREE_KINK_VERTEX[0] / 1000.0, FREE_KINK_VERTEX[1] / 1000.0, 0.0),
        label="free kink vertex",
    )
    arcs = _kink_arcs(display)
    faults = kink_arc_faults(arcs, vertex)
    placed = f"{kink_arc_summary(arcs, vertex)}; faults {faults}"
    turned = False
    if faults:
        _activate_view(adapter, detail, label="kink detail")
        if not model.Extension.SelectByID2(
            selection_name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
        ):
            raise RuntimeError(f"failed to select {FREE_KINK_ANGLE} {selection_name!r}")
        flipped = display.VerticallyOppositeAngle()
        model.ClearSelection2(True)
        if not flipped:
            raise RuntimeError(f"{FREE_KINK_ANGLE}: VerticallyOppositeAngle refused")
        turned = True
        if not annotation.SetPosition2(*DETAIL_KEEP[FREE_KINK_ANGLE], 0.0):
            raise RuntimeError(f"failed to re-seat {FREE_KINK_ANGLE}")
        rebuild_drawing(adapter, label="kink angle turned")
        arcs = _kink_arcs(display)
        faults = kink_arc_faults(arcs, vertex)
    value = abs(float(_read_member(dimension, "SystemValue")))
    if abs(value - math.radians(KINK_INCLUDED_DEG)) > 1e-8:
        faults.append(f"value {math.degrees(value):.6f} deg, not {KINK_INCLUDED_DEG:g}")
    _telemetry.info(
        f"kink angle: free kink vertex "
        f"{tuple(round(v * 1000, 2) for v in vertex)} mm; as placed {placed}; "
        f"turned vertically opposite {turned}: "
        f"{kink_arc_summary(arcs, vertex)}; faults {faults}",
        kink_arc_count=len(arcs),
        kink_arc_turned=turned,
    )
    if faults:
        raise RuntimeError(f"{FREE_KINK_ANGLE} arc: {'; '.join(faults)}")


def _blank_dimensions(adapter: Any, top: Any) -> None:
    """Locate the pad hole from the foot's free end and the pad's lower edge,
    and size the strip across its free flat.

    The Hole Wizard placement sketch cannot carry a datum point (drawing-guidelines.md rule 10 (dimension from a real feature)), so the
    print dimensions the hole from the blank's own edges with driven sheet
    dimensions picked on both features; they print at the .XX row.  The
    strip's width is the extrusion's depth in the model, which has no edge to
    witness in this view, so it too is a driven dimension on the strip's two
    edges.
    """
    hole_x = (FOOT_END[0] - HOLE_FROM_END) / 1000.0
    hole_r = HOLE_DIA / 2000.0
    top_y = THICK / 1000.0
    edge_picks = {
        sign: model_point_in_view(
            adapter,
            top,
            (hole_x, top_y, (PAD_Z + sign * PAD_WIDTH / 2.0) / 1000.0),
            label=f"pad long edge z{sign:+g}",
        )
        for sign in (-1.0, 1.0)
    }
    lower = min(edge_picks, key=lambda sign: edge_picks[sign][1])
    locations = (
        (
            "hole from the foot's free end",
            model_point_in_view(
                adapter,
                top,
                (
                    FOOT_END[0] / 1000.0,
                    top_y,
                    (PAD_Z - lower * PAD_WIDTH / 4.0) / 1000.0,
                ),
                label="pad free end",
            ),
            model_point_in_view(
                adapter,
                top,
                (hole_x + hole_r, top_y, PAD_Z / 1000.0),
                label="hole east edge",
            ),
            HOLE_END_TEXT_XY,
            "horizontal",
            HOLE_FROM_END,
            _DIM_ARROWS_INSIDE,
        ),
        (
            "hole from the pad's lower edge",
            (edge_picks[lower][0] + 0.004, edge_picks[lower][1]),
            model_point_in_view(
                adapter,
                top,
                (hole_x, top_y, PAD_Z / 1000.0 + lower * hole_r),
                label="hole lower edge",
            ),
            HOLE_EDGE_TEXT_XY,
            "vertical",
            PAD_WIDTH / 2.0,
            None,
        ),
        (
            "strip width across the free flat",
            *(
                model_point_in_view(
                    adapter,
                    top,
                    (
                        STRIP_PICK_X / 1000.0,
                        STRIP_PICK_Y / 1000.0,
                        sign * WIDTH / 2000.0,
                    ),
                    label=f"strip edge z{sign:+g}",
                )
                for sign in (-1.0, 1.0)
            ),
            STRIP_WIDTH_TEXT_XY,
            "vertical",
            WIDTH,
            None,
        ),
    )
    for label, p0, p1, text_xy, orientation, expected, arrow_side in locations:
        display = add_edge_dimension(
            adapter,
            top,
            p0=p0,
            p1=p1,
            text_xy=text_xy,
            label=label,
            orientation=orientation,
        )
        display = _early_bound(display, "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        measured_mm = abs(float(dimension.SystemValue) * 1000.0)
        if abs(measured_mm - expected) > 1e-5:
            raise RuntimeError(
                f"{label} measured {measured_mm:g}, expected {expected:g} mm"
            )
        if arrow_side is not None:
            display.ArrowSide = arrow_side
            if int(display.ArrowSide) != arrow_side:
                raise RuntimeError(f"{label} did not keep its arrows inside")


def _prove_pad_hole_centre_mark(adapter: Any, top: Any) -> None:
    """Prove the template's one mark; never author or clean up unknown marks."""
    marks = list(_early_bound(top, "IView").GetAnnotationsByType(13) or ())
    if len(marks) != 1:
        raise RuntimeError(
            f"pad top view carries {len(marks)} centre marks, expected the "
            "template's one on the hole axis"
        )
    data = _early_bound(marks[0], "IAnnotation").GetDisplayData()
    if data is None:
        raise RuntimeError("pad hole centre mark has no display data")
    data = _early_bound(data, "IDisplayData")
    count = int(data.GetLineCount())
    if count <= 0:
        raise RuntimeError("pad hole centre mark draws no lines")
    xs: list[float] = []
    ys: list[float] = []
    for index in range(count):
        line = [float(value) for value in data.GetLineAtIndex2(index)]
        if len(line) < 10 or not all(math.isfinite(value) for value in line[4:10]):
            raise RuntimeError("pad hole centre mark has invalid display lines")
        xs.extend((line[4], line[7]))
        ys.extend((line[5], line[8]))
    ink = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
    axis = model_point_in_view(
        adapter,
        top,
        tuple(value / 1000.0 for value in HOLE_CENTER),
        label="pad hole axis",
    )
    offset = math.hypot(ink[0] - axis[0], ink[1] - axis[1])
    # Same 0.5 mm sheet-space display tolerance as the magnifying-bracket census.
    if not math.isfinite(offset) or offset > 0.0005:
        raise RuntimeError(
            f"pad hole centre mark prints {offset * 1000.0:.2f} mm off the hole axis"
        )
    _telemetry.success(
        f"pad top view: one centre mark, {offset * 1000.0:.2f} mm off the hole axis"
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-spring source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
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
            0: "Pinion Return Leaf Spring Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion return spring; bent stainless leaf; formed blank",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # drawing-guidelines.md rule 9 (show internal shape in solid lines): nothing on this part is communicated by a hidden line -- the
    # hole is defined by its callout -- so every view is hidden-lines-removed.
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)

    # The kink detail is created and dimensioned FIRST, while nothing is on
    # the sheet: KinkR and FlatLen live in SpringProfile with the profile's
    # FootLen and BendR, and the free kink angle in FreeForm with FreeKinkH
    # and FreeKinkV, so the targeted import delivers those too.  pc-r10
    # (37495ac47) ran the profile first and deleted the pair; the detail's
    # import then brought KinkR back but not FlatLen.  A dimension already on
    # the sheet is never imported again (the arbor's detail A imports first
    # for the same reason), so the profile's import now skips what the detail
    # holds and takes back what the detail deleted.  The detail is
    # dimensioned uncropped and cropped after (_placed_kink_view says why).
    detail = _placed_kink_view(adapter)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = _dimension_then_crop_kink_view(adapter, detail)
    # The front view imports the part-hidden FreeForm reference sketch too, so
    # it takes the same opt-in curation that shows it (the phantom) there.
    front_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="formed profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="blank top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *top_annotations, *detail_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _assert_kink_angle_wedge(adapter, detail, detail_annotations)
    # The fence and the labels go on once every import is done, so nothing
    # of the front view's own sketch is near its import.
    mark = _mark_kink_on_front(adapter, front)
    _label_kink_detail(adapter, detail, front, mark)
    _hole_axis_centerline(
        adapter, front, FRONT_HOLE_AXIS_ENDS, label="profile hole-axis centreline"
    )

    # The template already supplies this mark; reinsertion prints identical ink twice.
    _prove_pad_hole_centre_mark(adapter, top)
    _blank_dimensions(adapter, top)
    hole_edge = model_point_in_view(
        adapter,
        top,
        (
            HOLE_EDGE_PICK[0] / 1000.0,
            HOLE_EDGE_PICK[1] / 1000.0,
            HOLE_EDGE_PICK[2] / 1000.0,
        ),
        label="pad hole edge",
    )
    hole_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=hole_edge,
        callout_xy=HOLE_CALLOUT_XY,
        label="spring pad clearance hole",
        process=HOLE_PROCESS,
    )
    set_hole_callout_precision(
        hole_callout, {"hw-diam": HOLE_CALLOUT_PRECISION}, label="spring pad clearance hole"
    )
    # After every pick on the hole: its forward rim lies on this line.
    _hole_axis_centerline(
        adapter, top, TOP_HOLE_AXIS_ENDS, label="pad hole-axis centreline"
    )

    # Under FootLen's two-line callout (its dimension line sits ~0.058).
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.048)
    add_property_linked_note(adapter, "Isometric View Note", 0.325, 0.115)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Return Leaf Spring Manufacturing Drawing",
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
