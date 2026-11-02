r"""Create the curated machinist drawing for MHA-SM-01, the gooseneck weldment.

The SLDPRT remains authoritative.  This recipe supplies the views, places the
part's marked dimensions and the end piece's native tap callout, and links
the notes; sheet/template and export behaviour lives in ``_drawing_common``.

The gooseneck is a 1/2 in 4130-N tube bent R3.0, its arm ending flush in a
solid Ø.500 end piece brazed on a shank inside the tube and tapped 1/4-28
blind, with a 5/8 in sleeve brazed over the leg (owner rulings 2026-10-27,
#1951).  The made MHA-SM-04 spring screw is NOT part of this weldment.  The
sheet carries, at 1:3:

* the ELEVATION (``*Front``): the leg length (foot to the bend tangent) and
  the arm straight (bend tangent to the end face) on the tube's axes, from
  the part's hidden ``StationReference``; the bend's centreline radius; the
  sleeve length from the foot and the sleeve's stock Ø with its fit on the
  tube; the reference overall height and reach to real faces, from the
  part's hidden ``OverallReference``;
* the END VIEW (``*Left``, third-angle left of the elevation): the end face,
  carrying the native blind-tap callout with its depth datum and the thread
  axis's location limit;

and at 3:1 SECTION A-A, a full section on the arm axis (cut faces only)
cropped to the end piece, the tube's cut walls hatched across the end
piece's and ended in a freehand break: the head Ø (flush) and length, the
braze shank Ø (its fit) and length, and the counterbore's LIMIT Ø (with the
stated wall) and depth (with its floor-corner limit, which names the mate).
The isometric is at 1:4.  The sheet prints decimal inch (#290, the registry
row's drawing_unit).

Run with SolidWorks open::

    uv run python cad\scripts\draw_sm_gooseneck.py sm-gooseneck
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    remove_notes_matching,
    view_name,
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
from _drawing_dimensions import assert_imported_precision
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _hole_callout_thread_class import omit_title_block_thread_class
from _holes import DIAMETER_TOLERANCE_MM, _verify_tap_metadata
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
from sm_gooseneck_geom import (
    ARM_END_X,
    ARM_Y,
    BEND_R,
    LEG_BOTTOM,
    LEG_TOP,
    PLUG_HEAD_LENGTH,
    PLUG_SHANK_LENGTH,
    SLEEVE_DIA,
    SLEEVE_TOP,
    TUBE_BORE_DIA,
    TUBE_DIA,
    TUBE_END_X,
)
from sm_gooseneck_spec import (
    DIMENSION_CALLOUTS_ABOVE_BY_NAME,
    DIMENSION_CALLOUTS_BY_NAME,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    TAP_CALLOUT_BELOW,
    TAP_CALLOUT_PRECISION,
    TUBE_OD_REF_Y,
)
from sm_gooseneck_spring_joint import (
    TAP_DRILL_DEPTH_FROM_FLOOR,
    TAP_DRILL_DIA,
    TAP_SPEC,
    TAP_THREAD_DEPTH_FROM_FLOOR,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["sm_gooseneck"]
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

SHEET_SCALE = (1.0, 3.0)  # 1:3 whole sheet (~500 mm tall gooseneck)
VIEW_SCALE = (1, 3)
SECTION_SCALE = (3, 1)
ISO_SCALE = (1, 4)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet metres per model mm
_SECTION_S = SECTION_SCALE[0] / SECTION_SCALE[1] / 1000.0

# A placed view centres its model bounding box: x from the end face to the
# sleeve's far side, y from the leg's foot to the arm's top.
_SLEEVE_R = SLEEVE_DIA / 2.0
_TUBE_R = TUBE_DIA / 2.0
_BOX_MID_X = (ARM_END_X + _SLEEVE_R) / 2.0
_BOX_MID_Y = (LEG_BOTTOM + ARM_Y + _TUBE_R) / 2.0

# Sheet layout (metres), left to right: section A-A over the notes, the end
# view, the elevation with its dimensions on the leg's right, the isometric.
# The end view stands right of section A-A's braze-fit callout (farm run
# 20261027T224212504Z: at 0.190 its leg crossed that text).
FRONT_CENTER = (0.255, 0.150)
END_CENTER = (0.205, FRONT_CENTER[1])
ISO_CENTER = (0.375, 0.165)


def _front_x(model_x: float) -> float:
    return FRONT_CENTER[0] + (model_x - _BOX_MID_X) * _S


def _front_y(model_y: float) -> float:
    return FRONT_CENTER[1] + (model_y - _BOX_MID_Y) * _S


LEG_AXIS_X = _front_x(0.0)
ARM_AXIS_Y = _front_y(ARM_Y)
END_FACE_X = _front_x(ARM_END_X)
FOOT_Y = _front_y(LEG_BOTTOM)
BEND_TANGENT_Y = _front_y(LEG_TOP)
SLEEVE_TOP_Y = _front_y(SLEEVE_TOP)

# The elevation's dimensions: both vertical runs on the leg's right, the
# sleeve's inside the leg's; the sleeve's Ø with its fit callout on the leg's
# left, between the end view's leg and the elevation's, above the title block
# (top y 0.066); the arm straight over the arm; the bend radius
# right of the bend, its line 10 degrees above the leg's tangent so it passes
# under section line A's right arrow and label (at about 40 degrees it ran
# through the label, farm run 20261027T224212504Z) and over the leg length's
# upper extension line.  The tube's reference Ø crosses the bare leg on its
# left, level with the hidden reference line, opposite the leg length.
# The reference overall height (foot face to the arm's top) stands outermost
# on the leg's right, beyond the leg length (its text ended at x 0.310 in farm
# run 20261101T004958072Z) and clear of the isometric (left edge x 0.358),
# its text at the view's mid-height, 22 mm below the leg length's.  The
# reference reach (end face to the leg's outer side) runs over the arm
# straight, its text between that one's (top y 0.247) and the view label
# (bottom y 0.258).  Machinist review r5 of that run.  The arm straight's
# text stands outside its short span, left of the end face: centred over the
# span it straddled the end face's extension line, which the reach shares
# (text-on-line, farm run 20261101T022045634Z: 27.16 at x 235.3-246.6 mm).
FRONT_KEEP = {
    "SleeveLength": (LEG_AXIS_X + 0.018, (FOOT_Y + SLEEVE_TOP_Y) / 2.0),
    "SleeveDia": (LEG_AXIS_X - 0.034, FOOT_Y + 0.040),
    "LegLength": (LEG_AXIS_X + 0.034, (SLEEVE_TOP_Y + BEND_TANGENT_Y) / 2.0),
    "TubeOdRef": (LEG_AXIS_X - 0.030, _front_y(TUBE_OD_REF_Y)),
    "ArmStraight": (END_FACE_X - 0.010, ARM_AXIS_Y + 0.014),
    "BendRadius": (LEG_AXIS_X + 0.019, ARM_AXIS_Y - 0.0176),
    "OverallHeight": (
        LEG_AXIS_X + 0.052,
        (FOOT_Y + _front_y(ARM_Y + _TUBE_R)) / 2.0,
    ),
    "OverallReach": (
        (END_FACE_X + _front_x(_TUBE_R)) / 2.0,
        ARM_AXIS_Y + 0.021,
    ),
}

# The end view (*Left) looks at the end face along +X: sheet x is model +Z.
# The tap's native callout stands up and left of it, clear of the section's
# upper dimensions and of the elevation's arm-straight text, its top inside
# the border (at 0.266 it crossed it, farm run 20261027T224212504Z).
TAP_CALLOUT_XY = (0.158, 0.252)

# Section A-A: a full section on the horizontal plane through the arm axis,
# cut faces only, cropped to the end piece and the tube over its shank.  A
# PARTIAL (removed) section along the same span does not import the end
# piece's Ø or the counterbore's Ø; the full section imports all six
# (probe farm runs 20261027T211151181Z, 20261027T213158937Z).  The plane
# also cuts the bend's top, out to where the bend's outer wall drops below
# it, so the cutting line runs from outside the end face to past that and the
# crop keeps only SECTION_CROP_X_MM: to just past the braze shank, short of
# the bend tangent.  The view is turned until model +X runs right and model
# -Z up (looking down on the arm-axis plane, where the end piece's and
# counterbore's sketches lie), and set so the end face's centre lands on
# SECTION_FACE_XY.
_BEND_CUT_END_X = -BEND_R + math.sqrt((BEND_R + _TUBE_R) ** 2 - BEND_R**2)
SECTION_LINE_X_MM = (ARM_END_X - 2.0, _BEND_CUT_END_X + 10.0)
SECTION_CROP_X_MM = (ARM_END_X - 2.0, TUBE_END_X + PLUG_SHANK_LENGTH + 0.8)
if SECTION_CROP_X_MM[1] >= -BEND_R:
    raise AssertionError("section A-A's crop reaches the bend")
if SECTION_LINE_X_MM[1] >= 0.0:
    raise AssertionError("section A-A's cutting line reaches the leg")
# Created below the cutting line, so its arrows look down on the arm.
SECTION_CREATE_XY = (0.110, 0.195)
SECTION_FACE_XY = (0.075, 0.200)
_SX0, _SY0 = SECTION_FACE_XY
_SECTION_HALF = _TUBE_R * _SECTION_S
SECTION_CAPTION_XY = (_SX0 + 0.030, _SY0 - _SECTION_HALF - 0.064)


def _section_x(model_x: float) -> float:
    return _SX0 + (model_x - ARM_END_X) * _SECTION_S


# Section A-A's dimensions: the two lengths in one row over the part; the
# counterbore depth's LIMIT pair above them, left of the face; the
# counterbore Ø's LIMIT pair (with its mate and max rows) left of the end
# face, between its extension lines; the head and shank Ø below the part, the
# head's block carrying the counterbore wall and its "AT C'BORE MAX" two rows
# lower, the shank's longer fit callout lower.  The Ø's block centres on its
# keep, 0.45 mm high: r8 (farm run 20261101T035809796Z) inked the pair and two
# rows y 190.4-209.6 between the extension lines at 189.5 and 210.5.  The
# head's block, value and four rows, inked y 148.9-174.8, 6 mm under the part
# (180.95), its last row x 94.8-129.9, left of the shank's line (x 146.2).
# Each Ø's text
# starts at its dimension line and runs right, so the head's line stands
# near the end face and its text ends short of the shank's line (at
# ARM_END_X + 10 the shank's line ran through it, farm run
# 20261027T224212504Z).  The floor corner's
# "R.004 MAX" block stands up-left of the end face, between the
# counterbore Ø and the depth: its arc lies on the sketch's +v side, model -Z,
# the section's top (ArmAxisPlane is offset from the Top plane), so its leader
# runs down-right through the counterbore's mouth to the corner, above the
# Ø's upper extension line.  Its leader's shoulder underlines the whole
# block, so the block ends short of the end face's extension lines (x 0.075;
# a 21-character row reached 0.0754 and crossed them, farm run
# 20261028T083207316Z).  With the counterbore's axis limit (r8: the Ø's rows
# carry its mate and max) the block runs to value and three rows, ~20.3 mm
# of ink (r8: value and two rows 14.7 mm, centred on the keep, shoulder 0.9
# mm under): centred at keep y 230.65 its shoulder (~219.6) stands 2.8 mm
# over the Ø's upper dimension line (its end at 216.8) and its top (~240.8)
# 2.9 mm under the depth's shoulder (243.7).
SECTION_KEEP = {
    "PlugHeadLength": (
        _section_x(ARM_END_X + PLUG_HEAD_LENGTH / 2.0),
        _SY0 + _SECTION_HALF + 0.010,
    ),
    "PlugShankLength": (
        _section_x(TUBE_END_X + PLUG_SHANK_LENGTH / 2.0),
        _SY0 + _SECTION_HALF + 0.010,
    ),
    "CounterboreDepth": (_SX0 - 0.012, _SY0 + _SECTION_HALF + 0.032),
    "CounterboreDia": (_SX0 - 0.030, _SY0 - 0.0005),
    "CounterboreFloorCornerR": (_SX0 - 0.032, _SY0 + _SECTION_HALF + 0.0116),
    "PlugDia": (_section_x(ARM_END_X + 4.0), _SY0 - _SECTION_HALF - 0.019),
    # 1.5 mm left of the shank's centre: the four-place braze window ran
    # the text 0.26 mm onto the elevation (#290 batch 0).
    "PlugShankDia": (
        _section_x(TUBE_END_X + PLUG_SHANK_LENGTH / 2.0) - 0.0015,
        _SY0 - _SECTION_HALF - 0.044,
    ),
}
if set(FRONT_KEEP) | set(SECTION_KEEP) != {
    name for names in DRAWING_DIMENSIONS.values() for name in names
}:
    raise AssertionError("the gooseneck sheet does not place every marked dimension")

# The four note lines run long, so they sit in the bottom left, under the
# end view's foot (y ~0.067) and left of the title block (x 0.216); the
# isometric's note sits under it.  The elevation's foot stands on the title
# block's top and its bounding box spans the end face to the leg, so its note
# stands over the view's upper right, right of the arm straight and clear of
# the border (left of the foot it printed inside the view's box, farm run
# 20261027T233507330Z).
NOTES_XY = (0.016, 0.062)
ELEVATION_NOTE_XY = (0.262, 0.262)
ISO_NOTE_XY = (0.345, 0.085)
TAPPED_HOLE_NOTE = "Tapped Hole"


def _require_saved_tap(model: Any) -> None:
    """Require the saved native receiver's size, class, blind ends, drill Ø
    and both depths."""
    feature = _early_bound(model, "IPartDoc").FeatureByName("ThreadBore")
    if feature is None:
        raise RuntimeError("saved gooseneck has no native ThreadBore")
    feature = _early_bound(feature, "IFeature")
    if str(feature.GetTypeName2()) != "HoleWzd":
        raise RuntimeError("saved gooseneck ThreadBore is not a native Hole Wizard tap")
    definition = feature.GetDefinition()
    if definition is None:
        raise RuntimeError("saved gooseneck ThreadBore has no hole definition")
    definition = _early_bound(definition, "IWizardHoleFeatureData2")
    if str(definition.FastenerSize).strip() != TAP_SPEC.size:
        raise RuntimeError("saved gooseneck ThreadBore has the wrong thread size")
    _verify_tap_metadata(definition, TAP_SPEC, "saved gooseneck ThreadBore")
    for member, expected, what in (
        ("TapDrillDiameter", TAP_DRILL_DIA, "tap drill"),
        ("TapDrillDepth", TAP_DRILL_DEPTH_FROM_FLOOR, "tap drill depth"),
        ("ThreadDepth", TAP_THREAD_DEPTH_FROM_FLOOR, "thread depth"),
    ):
        value = float(getattr(definition, member)) * 1000.0
        if not math.isfinite(value) or abs(value - expected) > DIAMETER_TOLERANCE_MM:
            raise RuntimeError(
                f"saved gooseneck {what} {value:.3f} != {expected:.3f} mm"
            )


def _section_axes(
    adapter: Any, native: Any
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Sheet directions of model +X and -Z (1 mm each) in section A-A."""
    native.UpdateViewDisplayGeometry()
    x0, y0 = ARM_END_X / 1000.0, ARM_Y / 1000.0
    origin, plus_x, minus_z = model_points_in_view(
        adapter,
        native,
        ((x0, y0, 0.0), (x0 + 0.001, y0, 0.0), (x0, y0, -0.001)),
        label="section A-A axes",
        names=("end face centre", "plus x", "minus z"),
    )
    return (
        (plus_x[0] - origin[0], plus_x[1] - origin[1]),
        (minus_z[0] - origin[0], minus_z[1] - origin[1]),
    )


def _orient_section(adapter: Any, native: Any, cut: Any) -> None:
    """Look down on the arm-axis plane: model +X right, model -Z up.

    Looking along -Y with -Z up puts +X on the right, a right-handed pair on
    the sheet; a left-handed pair is the cut looking UP, so the cut direction
    is reversed.  The view then turns until +X reads right
    (draw_pn_pen_hanger ``_orient_section``).
    """
    right, up = _section_axes(adapter, native)
    if right[0] * up[1] - right[1] * up[0] < 0.0:
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="section A-A reversed")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("section A-A cut direction did not persist")
        right, up = _section_axes(adapter, native)
    native.Angle = float(native.Angle) - math.atan2(right[1], right[0])
    rebuild_drawing(adapter, label="section A-A turned")
    right, up = _section_axes(adapter, native)
    tolerance = 1e-7
    if (
        right[0] <= 0.0
        or abs(right[1]) > tolerance
        or up[1] <= 0.0
        or abs(up[0]) > tolerance
    ):
        raise RuntimeError(
            f"section A-A is not looking down on the arm axis: {right=}, {up=}"
        )


def _place_section(adapter: Any, native: Any) -> None:
    """Land the end face's centre on SECTION_FACE_XY: ``SetViewPosition``
    moves the ink by the difference from the Position it reads."""
    anchor = (ARM_END_X / 1000.0, ARM_Y / 1000.0, 0.0)
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        projected = model_point_in_view(
            adapter, native, anchor, label=f"section A-A end face, pass {attempt}"
        )
        if math.dist(projected, SECTION_FACE_XY) <= 1e-4:
            return
        position = tuple(float(value) for value in native.Position)
        moved = [
            position[axis] + SECTION_FACE_XY[axis] - projected[axis] for axis in (0, 1)
        ]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to place section A-A")
        rebuild_drawing(adapter, label="section A-A placed")
    raise RuntimeError(f"section A-A end face did not land on {SECTION_FACE_XY}")


def _crop_section(adapter: Any, section: Any) -> None:
    """Crop section A-A to SECTION_CROP_X_MM across the tube's Ø plus 1 mm,
    a sheet rectangle sketched direct to the database in the view's own sketch
    and handed to ``IView.Crop2`` with no boundary drawn
    (draw_dt_cone_swing_platform ``_crop_section_to_fence``).  The crop is
    proved by the outline still holding the fence and losing the bend."""
    left, right = (_section_x(x) for x in SECTION_CROP_X_MM)
    half = (_TUBE_R + 1.0) * _SECTION_S
    foot, head = _SY0 - half, _SY0 + half
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    native = _early_bound(section, "IView")
    if not ddoc.ActivateView(view_name(adapter, section)):
        raise RuntimeError("failed to activate section A-A for its crop")
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
            f"section A-A crop fence has {len(segments)} segments, not 4"
        )
    for segment in segments:
        if not _early_bound(segment, "ISketchSegment").Select4(True, None):
            raise RuntimeError("failed to select the section A-A crop fence")
    # IView.Crop2 returns swCropViewErrors_e, where 1 is NoError.
    status = int(native.Crop2(False, True, 0))
    draw.ClearSelection2(True)
    if status != 1:
        raise RuntimeError(f"failed to crop section A-A: Crop2 status {status}")
    rebuild_drawing(adapter, label="section A-A cropped")
    native.UpdateViewDisplayGeometry()
    if not bool(native.IsCropped()):
        raise RuntimeError("section A-A did not retain its crop")
    after = tuple(float(value) for value in native.GetOutline())
    # The outline pads past the fence (draw_dt_cone_swing_platform), and the
    # full cut runs on over the bend: 0.345 m wide before the probe's crop
    # (farm run 20261027T213158937Z), 0.108 after.
    if (
        len(after) != 4
        or after[0] > left
        or after[1] > foot
        or after[2] < right
        or after[3] < head
        or after[2] - after[0] > (right - left) + 0.03
        or after[2] - after[0] > 0.75 * (before[2] - before[0])
    ):
        raise RuntimeError(
            f"section A-A crop is not its fence {(left, foot, right, head)}: "
            f"outline {before} -> {after}"
        )


# The tube's cut walls hatch at a right angle to the end piece's, so the two
# bodies of the weldment (build_sm_gooseneck) read as two parts (drafting
# practice for adjacent parts; machinist review of 3c0b5d87c).
TUBE_HATCH_TURN = math.pi / 2.0
# A section face whose model box starts on the end face's side of this
# station is the end piece's: the tube's walls start at TUBE_END_X.
_END_PIECE_SPLIT_X_M = (ARM_END_X + TUBE_END_X) / 2.0 / 1000.0


def _section_face_hatches(adapter: Any, section: Any) -> list[Any]:
    """Section A-A's IFaceHatch objects, null slots dropped; a fresh section
    can return only null slots (draw_mg_magnifying_clamp._face_hatches), so
    one rebuild is allowed before giving up."""
    view = _early_bound(section, "IView")
    for attempt in range(2):
        hatches = [
            _early_bound(raw, "IFaceHatch")
            for raw in (view.GetFaceHatches() or ())
            if raw is not None
        ]
        if hatches:
            return hatches
        if attempt == 0:
            rebuild_drawing(adapter, label="section A-A face hatches")
            view.UpdateViewDisplayGeometry()
    raise RuntimeError("section A-A returned no face hatches")


def _split_hatches(hatches: list[Any]) -> tuple[list[Any], list[Any]]:
    """``(end_piece, tube)`` hatches, by where each cut face starts."""
    end_piece, tube = [], []
    for hatch in hatches:
        face = hatch.Face
        if face is None:
            raise RuntimeError("a section A-A face hatch has no face")
        box = tuple(float(value) for value in _early_bound(face, "IFace2").GetBox())
        (end_piece if min(box[0], box[3]) < _END_PIECE_SPLIT_X_M else tube).append(
            hatch
        )
    if not end_piece or not tube:
        raise RuntimeError(
            f"section A-A hatches {len(end_piece)} end-piece and {len(tube)} tube "
            "faces; the weldment must cut as two bodies"
        )
    return end_piece, tube


# swAreaHatchingScope_e: a face hatch's edit applies to its Body (3) or only
# its Region (0); the section's default reached the end piece's hatch too
# (farm run 20261028T135841794Z), so the tube's edit is scoped first.
_HATCH_SCOPES = (("body", 3), ("region", 0))


def _hatch_tube_apart(adapter: Any, section: Any) -> None:
    """Turn the tube's crosshatch a right angle from the end piece's and read
    it back, scoped to the tube's body (else to each of its regions, the end
    piece's own regions pinned at their angle); the end piece keeps its
    angle."""
    end_piece, tube = _split_hatches(_section_face_hatches(adapter, section))
    base = float(end_piece[0].Angle)
    readings: list[str] = []
    for scope_name, scope in _HATCH_SCOPES:
        if scope == 0:
            for hatch in end_piece:
                hatch.HatchScope = scope
                hatch.Angle = base
        for hatch in tube:
            hatch.HatchScope = scope
            hatch.UseMaterialHatch = False
            hatch.Angle = base + TUBE_HATCH_TURN
        rebuild_drawing(adapter, label=f"section A-A tube hatch turned ({scope_name})")
        end_piece, tube = _split_hatches(_section_face_hatches(adapter, section))
        turns = [
            abs(math.remainder(float(hatch.Angle) - base, math.pi)) for hatch in tube
        ]
        kept = [float(hatch.Angle) for hatch in end_piece]
        readings.append(
            f"{scope_name}: tube turns {turns!r}, end piece {kept!r} (base {base!r})"
        )
        if all(
            math.isclose(turn, TUBE_HATCH_TURN, abs_tol=1e-6) for turn in turns
        ) and all(math.isclose(angle, base, abs_tol=1e-6) for angle in kept):
            _telemetry.success(
                f"section A-A: {len(tube)} tube hatch(es) turned 90 deg from "
                f"{len(end_piece)} end-piece hatch(es), {scope_name} scope"
            )
            return
    raise RuntimeError(
        "section A-A tube hatch did not turn apart: " + "; ".join(readings)
    )


# The tube runs on past the crop, so each cut wall ends in a freehand break
# (machinist review of 3c0b5d87c), short of the crop's edge so the whole
# curve shows: an S across the wall about TUBE_BREAK_X, model mm.
TUBE_BREAK_X = SECTION_CROP_X_MM[1] - 0.4
_TUBE_BREAK_WAVE = 0.25
if not TUBE_END_X + PLUG_SHANK_LENGTH < TUBE_BREAK_X - _TUBE_BREAK_WAVE:
    raise AssertionError("section A-A's tube break reaches the shank end")


def _sketch_tube_break(adapter: Any, section: Any) -> None:
    """Draw the freehand break across each of the tube's cut walls, in the
    view's own sketch (as ``_crop_section``)."""
    inner, outer = TUBE_BORE_DIA / 2.0, _TUBE_R
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    native = _early_bound(section, "IView")
    if not ddoc.ActivateView(view_name(adapter, section)):
        raise RuntimeError("failed to activate section A-A for its tube break")
    draw.ClearSelection2(True)
    sketch = _early_bound(native.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")

    def to_sketch(xy: tuple[float, float]) -> list[float]:
        point = _early_bound(
            math_utility.CreatePoint(double_array([xy[0], xy[1], 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        return [float(value) for value in projected.ArrayData]

    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    for side in (1.0, -1.0):
        wave = ((0.0, 0.0), (1.0 / 3.0, 1.0), (2.0 / 3.0, -1.0), (1.0, 0.0))
        points = [
            to_sketch(
                (
                    _section_x(TUBE_BREAK_X + sway * _TUBE_BREAK_WAVE),
                    _SY0 + side * (inner + (outer - inner) * share) * _SECTION_S,
                )
            )
            for share, sway in wave
        ]
        # CreateSpline2 always adds straight to the database.
        spline = sketch_manager.CreateSpline2(
            double_array([value for point in points for value in point]), False
        )
        if spline is None:
            raise RuntimeError(f"section A-A tube break ({side:+.0f}) failed")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="section A-A tube break")


_SECTION_THREAD_LAYER = "SECTION-COSMETIC-THREADS-HIDDEN"


def _hide_section_cosmetic_threads(adapter: Any, section: Any) -> None:
    """Put section A-A's cosmetic threads on a hidden, non-printing layer.

    Drawn in the cut, the tap's major-diameter lines printed dashed, and a
    section never carries hidden lines (drawing-guidelines.md rule 9; machinist
    review of 1d60c6832).  The tap stays fully defined by its native callout
    on the end view (rule 9: a standard hole needs neither hidden lines nor a
    section), and the section still shows the drilled bore solid.  As
    draw_dt_cone_swing_platform._hide_profile_cosmetic_threads."""
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    if manager.GetLayer(_SECTION_THREAD_LAYER) is None and (
        int(
            manager.AddLayer(
                _SECTION_THREAD_LAYER, "section A-A cosmetic threads", 0, 0, 0
            )
        )
        != 1
    ):
        raise RuntimeError("failed to add the hidden section-thread layer")
    layer = _early_bound(manager.GetLayer(_SECTION_THREAD_LAYER), "ILayer")
    layer.Visible = False
    layer.Printable = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("section-thread layer did not stay hidden")
    hidden = 0
    for raw in _early_bound(section, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.GetType()) != 1:  # swCosmeticThread
            continue
        annotation.Layer = _SECTION_THREAD_LAYER
        if str(annotation.Layer or "") != _SECTION_THREAD_LAYER:
            raise RuntimeError("section A-A cosmetic thread refused the hidden layer")
        hidden += 1
    if not hidden:
        raise RuntimeError("section A-A has no cosmetic thread to hide")
    rebuild_drawing(adapter, label="section A-A cosmetic threads hidden")


def _end_piece_section(adapter: Any, front: Any) -> Any:
    """Section A-A along the arm axis, cropped to the end piece."""
    line = model_points_in_view(
        adapter,
        front,
        tuple((x / 1000.0, ARM_Y / 1000.0, 0.0) for x in SECTION_LINE_X_MM),
        label="section A-A cutting line",
        names=("outside the end face", "past the bend's cut"),
    )
    section = create_section_view(
        adapter,
        front,
        line_start=line[0],
        line_end=line[1],
        view_xy=SECTION_CREATE_XY,
        section_label="A",
        scale=SECTION_SCALE,
        label="end piece section A-A",
    )
    native = _early_bound(section, "IView")
    cut = _early_bound(native.GetSection(), "IDrSection")
    # R2026x declares SetDisplayOnlySurfaceCut as a void setter; only its
    # dedicated bool getter may be truth-tested.
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="section A-A cut faces only")
    if not cut.GetDisplayOnlySurfaceCut() or cut.GetPartialSection():
        raise RuntimeError("section A-A must be a full, cut-faces-only section")
    ratio = tuple(float(value) for value in native.ScaleRatio)
    if not math.isclose(ratio[0] / ratio[1], SECTION_SCALE[0] / SECTION_SCALE[1]):
        raise RuntimeError(f"section A-A scale did not persist: {ratio}")
    _orient_section(adapter, native, cut)
    # A section shows no hidden lines (drawing-guidelines.md rule 9); set
    # before placing so the display change cannot shift the placed ink.
    set_hidden_lines_removed(adapter, section)
    _place_section(adapter, native)
    # Hatched before the crop: a cropped view's hatch reads are not relied on.
    _hatch_tube_apart(adapter, section)
    _crop_section(adapter, section)
    # The crop must not move the placed ink.
    _place_section(adapter, native)
    _sketch_tube_break(adapter, section)
    position_section_caption(
        adapter, section, SECTION_CAPTION_XY, label="gooseneck end piece"
    )
    return section


def _assert_part_callouts(adapter: Any, annotations: list[Any]) -> None:
    """The part authors every callout below or above its dimension's value;
    the import must carry each one unchanged (the drawing never writes them,
    #1942)."""
    # swDimensionTextCalloutBelow = 4, swDimensionTextCalloutAbove = 3.
    expected = {
        (4, name): text for name, text in DIMENSION_CALLOUTS_BY_NAME.items()
    } | {(3, name): text for name, text in DIMENSION_CALLOUTS_ABOVE_BY_NAME.items()}
    found: dict[tuple[int, str], str] = {}
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        slots = [slot for slot, expected_name in expected if expected_name == name]
        if not slots:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        for slot in slots:
            found[(slot, name)] = str(display.GetText(slot) or "").replace("\r\n", "\n")
    if found != expected:
        raise RuntimeError(
            f"gooseneck dimension callouts did not import: {found!r} != {expected!r}"
        )


@_telemetry.traced("drawing.hole_callout_below")
def _set_tap_callout_below(display: Any, text: str) -> None:
    """Write ``text`` under the native tap callout and read it back.

    swDimensionTextCalloutBelowDefinition (8) pairs with the writable
    swDimensionTextCalloutBelow (4); the prefix, size and depth definitions
    stay untouched, so the Hole Wizard variables stay associative
    (draw_pd_guide_lock._set_hole_callout_below)."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    # SolidWorks may store CRLF row breaks; compare both sides without CR.
    below = definitions[8].replace("\r", "").rstrip()
    updated = f"{below}\n{text}" if below else text
    display.SetText(4, updated)
    if str(display.GetText(8) or "").replace("\r", "") != updated or any(
        str(display.GetText(part) or "") != definitions[part] for part in (5, 6, 7)
    ):
        raise RuntimeError(
            "gooseneck tap callout location rows or native definitions did not "
            f"persist: {[str(display.GetText(part) or '') for part in (5, 6, 7, 8)]!r}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open gooseneck source", await adapter.open_model(str(SOURCE)))
    _require_saved_tap(adapter.currentModel)
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
            "Elevation View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Elevation View Note",
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
            0: "Gooseneck Post Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "gooseneck; bent 4130 tube; brazed end piece; spring post",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Left", *END_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, end, iso):
        set_hidden_lines_removed(adapter, view)
    # The section derives from the elevation BEFORE the elevation shows the
    # hidden StationReference, so the section never inherits its lines.
    section = _end_piece_section(adapter, front)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="elevation",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="end piece section A-A",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *section_annotations]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _assert_part_callouts(adapter, annotations)
    _hide_section_cosmetic_threads(adapter, section)

    # The end piece's blind tap, natively called out on the end face: the
    # title block's THREADS row owns the 2B class (drawing-guidelines.md
    # rule 2), its depths print at two places, its location limits below.
    tap_callout = add_native_hole_callout(
        adapter,
        end,
        edge=visible_circle_edge(adapter, end, TAP_DRILL_DIA),
        callout_xy=TAP_CALLOUT_XY,
        label=f"gooseneck end piece {TAP_SPEC.size} blind tap",
    )
    omit_title_block_thread_class(tap_callout, label="gooseneck end piece tap")
    set_hole_callout_precision(
        tap_callout, TAP_CALLOUT_PRECISION, label="gooseneck end piece tap depths"
    )
    _set_tap_callout_below(tap_callout, TAP_CALLOUT_BELOW)
    rebuild_drawing(adapter, label="gooseneck tap callout")

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Elevation View Note", *ELEVATION_NOTE_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    # SolidWorks pins its own "1/4-28 Tapped Hole" note beside a tap's native
    # callout; the callout already states the thread, so any such label goes,
    # and finalize_drawing's count then proves none is left.
    removed_tap_labels = remove_notes_matching(adapter, TAPPED_HOLE_NOTE)
    _telemetry.info(f"removed {removed_tap_labels} automatic tapped-hole label(s)")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Gooseneck Post Manufacturing Drawing",
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
