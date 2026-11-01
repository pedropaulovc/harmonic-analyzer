r"""Create the curated machinist drawing for the connecting rod.

The SLDPRT remains authoritative.  This recipe supplies only the connecting-rod
views, dimension layout, callout text, and manufacturing notes;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.

The rod is a tall thin lollipop (~184 mm ring-bottom to fork crown), so the
sheet runs at 1:1 with a 1:2 isometric; the fork's side profile (tines, slot
and the plate's near face located from one fork face) prints in a 3:1 detail
of the side view, and the side view carries the plate's thickness at the ring
and the overall length as a reference.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_connecting_rod.py ch-connecting-rod
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

import _config
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
from _drawing_detail_crop import native_circle_geometry
from _drawing_detail_projection import settle_detail_projection
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_arc_endpoints_to_center,
    set_basic_dimension,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import face_silhouettes_through
from _drawing_finish import add_surface_finish
from _drawing_gdt import add_datum_feature, add_feature_control_frame
from _drawing_leaders import set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _gtol_cylinder import CylinderFace
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from ch_connecting_rod_notes import DRAWING_DIMENSIONS, DRAWING_PRECISION
from ch_connecting_rod_spec import (
    CENTER_DISTANCE,
    FORK_BASE_Y,
    FORK_SLOT_WIDTH,
    FORK_THICKNESS,
    FORK_TOP_Y,
    FORK_WIDTH,
    GEOMETRIC_TOLERANCES_IN,
    PIN_HOLE_DIA,
    RING_BORE_DIA,
    RING_BOTTOM_Y,
    RING_OUTER_RADIUS,
    SHANK_WIDTH,
    STRAP_DIAMETRAL_CLEARANCE,
    SURFACE_FINISHES,
)
from ch_rod_pivot_pin_spec import BUDGET as PIN_JOINT_BUDGET


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["ch_connecting_rod"]
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
_PIN_HOLE_DIA = PIN_HOLE_DIA

SHEET_SCALE = (1.0, 1.0)  # 1:1

# Front-view model bbox: X symmetric about 0, Y from the ring bottom up to the
# fork crown.  The left view shares it (Z symmetric about the mid-plane).
_BBOX_CY = (RING_BOTTOM_Y + FORK_TOP_Y) / 2.0

FRONT_CENTER = (0.180, 0.135)
# Third-angle left view, aligned with the front view: it shows the stepped
# thickness and carries the fork detail's circle.
LEFT_CENTER = (0.080, FRONT_CENTER[1])
ISO_CENTER = (0.398, 0.212)
# Over the isometric: below it, the detail's boss-length witness runs out.
ISO_NOTE_XY = (0.352, 0.262)

# The mates the tight bands name (drawing-guidelines.md rule 7).
CAM_NUMBER = str(_config.parts("dt-cylinder-gear")["number"])
ARM_NUMBER = str(_config.parts("ch-rocker-arm")["number"])
PIN_NUMBER = str(_config.parts("ch-rod-pivot-pin")["number"])
ROD_NUMBER = str(_config.parts("ch-connecting-rod")["number"])


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (1:1)."""
    return (
        FRONT_CENTER[0] + mx / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) / 1000.0,
    )


def _left_xy(offset: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) ``offset`` mm right of the left view's mid-plane at model
    height ``my`` (1:1)."""
    return (
        LEFT_CENTER[0] + offset / 1000.0,
        LEFT_CENTER[1] + (my - _BBOX_CY) / 1000.0,
    )


FRONT_KEEP = {
    # Both ring diameters stand outside the ring, down-left, their leaders
    # meeting the rims (inside the ring the texts sat on the ring's ink). The
    # outer's text stands clear right of the centre distance's line (r1).
    "RingOuterDia": (0.145, 0.100),
    "StrapBoreDia": (0.130, 0.040),
    # Right of the shank, so the flanks never strike the value.
    "ShankWidthDim": (0.198, 0.150),
    "ForkWidthDim": _sheet_xy(0.0, FORK_TOP_Y + 8.0),
    # The reamed pin hole's value stands right of the fork, below the position
    # FCF's level leader, so the two leaders cannot cross.
    "PinHoleDia": (0.218, 0.196),
}
# One arrow on the rim nearest each text (set_near_side_diameter).
NEAR_SIDE_DIAMETERS = ("RingOuterDia", "StrapBoreDia")
# Descriptive text beneath each native value/band: the strap bore and its
# cam; the fork's crown, a full round on the pin tangent to its sides; the
# reamed press hole and its pin (drawing-guidelines.md rule 12 (hole and slot
# callouts say what to do): the decimal Ø and the process).
_CLEARANCE_LEAST, _CLEARANCE_MOST = STRAP_DIAMETRAL_CLEARANCE
_PRESS_LEAST = PIN_JOINT_BUDGET["interference_min"]
_PRESS_MOST = PIN_JOINT_BUDGET["interference_max"]


def _inch(value_mm: float, places: int) -> str:
    """A millimetre value as inch text at ``places``, no leading zero."""
    return f"{value_mm / 25.4:.{places}f}".removeprefix("0")


FRONT_CALLOUTS = {
    "StrapBoreDia": (
        f"BORE; RUNS ON CAM OF\n{CAM_NUMBER},"
        f" {_inch(_CLEARANCE_LEAST, 3)}-{_inch(_CLEARANCE_MOST, 3)}\n"
        "DIAMETRAL CLEARANCE"
    ),
    "ForkWidthDim": "FULL R",
    "PinHoleDia": (
        f"THRU - REAM; PRESS\nFIT ON PIN {PIN_NUMBER},\n"
        f"{_inch(_PRESS_LEAST, 5)}-{_inch(_PRESS_MOST, 5)} INTERFERENCE"
    ),
}

# The side view at 1:1: the plate's thickness at the ring (#982 review r1),
# its value out to the left below the ring so its witnesses drop from the
# ring's bottom corners.
LEFT_KEEP = {
    "RingThick": (0.045, _left_xy(0.0, RING_BOTTOM_Y)[1] - 0.007),
}
# Three short lines: two long ones ran into the sheet border (r2).
LEFT_CALLOUTS = {
    "RingThick": f"RING AND SHANK;\nRUNS IN CAM SLOT\nOF {CAM_NUMBER}",
}
# The overall length, ring bottom to crown top, as a reference: the side
# view's ring-bottom silhouette and the far tine's crown-top silhouette,
# named by their faces and projected model points (a coordinate hit-test on
# the 2 mm ring bottom missed on the farm, r2), right of the side view, clear
# of the detail circle's letter on its left. Model points in mm.
OVERALL_LENGTH = FORK_TOP_Y - RING_BOTTOM_Y
OVERALL_BOTTOM_MM = (0.0, RING_BOTTOM_Y, 0.0)
OVERALL_TOP_MM = (0.0, FORK_TOP_Y, (FORK_THICKNESS + FORK_SLOT_WIDTH) / 4.0)
OVERALL_FACES = {
    "ring bottom": CylinderFace(2.0 * RING_OUTER_RADIUS),
    # The slot splits the crown's full round into one face per tine.
    "crown top": CylinderFace(FORK_WIDTH, contains_z_mm=OVERALL_TOP_MM[2]),
}
OVERALL_TEXT_XY = (0.100, 0.175)

# DETAIL C: the fork's side profile at 3:1. At 1:1 the tines, slot and ring
# faces are 1.7-2.7 mm features and their dimensions crowded the side view
# (baseline review). The fence centres on the rod axis midway between the
# crown top and the ring-face references' lower ends and takes in both.
DETAIL_SCALE = (3, 1)
# 12.5: the fence the passing layouts printed (an inferred draw had snapped
# the authored 11.0 out to ~12.4), clear of the slot depth's text inside it.
DETAIL_RADIUS_MM = 12.5
DETAIL_FENCE_Y_MM = (FORK_TOP_Y + FORK_BASE_Y - 2.0) / 2.0
# Right of the front view's pin-hole callout and FCF, below the isometric,
# above the title block.
DETAIL_CENTER = (0.325, 0.135)
# How far the fence centre may print from DETAIL_CENTER once placed (the
# 0.5 mm the section and detail settle reads allow, draw_dt_cone_swing_platform).
DETAIL_PLACEMENT_TOL_M = 0.0005
_DETAIL_MM = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
_DETAIL_FENCE_R = DETAIL_RADIUS_MM * _DETAIL_MM
if DETAIL_RADIUS_MM <= math.hypot(FORK_THICKNESS / 2.0, FORK_TOP_Y - DETAIL_FENCE_Y_MM):
    raise AssertionError("DETAIL C's fence must take in the whole crown top")
# The label stands right of the fence, between the boss length's witnesses.
DETAIL_LABEL_XY = (0.395, 0.140)
# The fence's letter on the side view, up-left of its circle.
DETAIL_LETTER_XY = (
    LEFT_CENTER[0] - DETAIL_RADIUS_MM / 1000.0 - 0.006,
    LEFT_CENTER[1] + (DETAIL_FENCE_Y_MM - _BBOX_CY + DETAIL_RADIUS_MM) / 1000.0,
)


def _detail_xy(z_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet (x, y) of side-view point (model z, model y) in DETAIL C: the
    *Left view runs model +Z to the right, so the datum fork face (model -Z,
    the build's sketch +x) stands on the LEFT."""
    return (
        DETAIL_CENTER[0] + z_mm * _DETAIL_MM,
        DETAIL_CENTER[1] + (y_mm - DETAIL_FENCE_Y_MM) * _DETAIL_MM,
    )


_FACE_X = _detail_xy(-FORK_THICKNESS / 2.0, FORK_TOP_Y)[0]
_FAR_X = _detail_xy(FORK_THICKNESS / 2.0, FORK_TOP_Y)[0]
_TINE_TOP_Y = _detail_xy(0.0, FORK_TOP_Y)[1]
_ROOT_Y = _detail_xy(0.0, FORK_BASE_Y)[1]
# The ring-face references' lower ends (build_ch_connecting_rod).
_REF_END_Y = _detail_xy(0.0, FORK_BASE_Y - 2.0)[1]
DETAIL_KEEP = {
    # Over the tines, nearest first: the near tine (text wholly left of the
    # datum face's witness), the slot (text right of the far face), the
    # reference thickness centred over the fork.
    "TineNear": (_FACE_X - 0.030, _TINE_TOP_Y + 0.012),
    "SlotWidth": (_FAR_X + 0.030, _TINE_TOP_Y + 0.016),
    "ForkThick": (DETAIL_CENTER[0], _TINE_TOP_Y + 0.028),
    # Down the right-hand side from the crown top: the slot depth inside, the
    # boss length outside.
    "SlotDepth": (_FAR_X + 0.016, (_TINE_TOP_Y + _ROOT_Y) / 2.0 + 0.004),
    "ForkBossLength": (_FAR_X + 0.034, (_TINE_TOP_Y + _ROOT_Y) / 2.0),
    # Under the fork, from the datum face: the plate's near face (text left
    # of the datum face, its longest line 5 mm clear of the face's witness;
    # at 30 mm the witness ran through MHA-DT-12, ENFORCE review).
    "RingFaceNear": (_FACE_X - 0.036, _REF_END_Y - 0.010),
}
# The near tine's band locates the slot from the datum face (the channel's
# axial budget) and, with the far tine's, holds the gap to the next channel's
# rod (#982 review r2: a clearance alone would not need it). Its printed lower
# limit is the tines' known shortfall against the .080 wall target, named
# TINE WALL (rule 20; MHA-CH-03 RV-02).
DETAIL_CALLOUTS = {
    "TineNear": f"2X TINE WALL;\nLOCATES SLOT;\nCLEARS NEXT ROD\n{ROD_NUMBER}",
    "SlotWidth": f"RUNS ON ARM\n{ARM_NUMBER}",
    "RingFaceNear": f"PLATE FACE; RING IN\nCAM SLOT OF {CAM_NUMBER}",
}

BORE_FINISH_EDGE = _sheet_xy(RING_BORE_DIA / 2.0, 0.0)
# At the plate's 2.5 mm character height (the default printed 5 mm and its
# roughness text ran into the detail's plate-face callout, r1 and r2).
BORE_FINISH_SYMBOL = (BORE_FINISH_EDGE[0] + 0.020, BORE_FINISH_EDGE[1] + 0.015)
BORE_FINISH_CHAR_HEIGHT = 0.0025
# Datum A on the strap bore at 5 o'clock, its tag below the ring: at 9
# o'clock its leader lay on the centre distance's witness (r1); inside the
# bore (r2) the tag crowded the two diameters' leaders and the centre lines.
# The edge attachment lands where the tag's leader meets the bore, so the
# tag stands on the pick's ray, between the outer diameter's leader (-55
# deg) and the vertical centre line.
_DATUM_A_ANGLE = math.radians(-72.0)
DATUM_A_EDGE = _sheet_xy(
    RING_BORE_DIA / 2.0 * math.cos(_DATUM_A_ANGLE),
    RING_BORE_DIA / 2.0 * math.sin(_DATUM_A_ANGLE),
)
_DATUM_A_TAG_R = 34.0
DATUM_A_SYMBOL = _sheet_xy(
    _DATUM_A_TAG_R * math.cos(_DATUM_A_ANGLE),
    _DATUM_A_TAG_R * math.sin(_DATUM_A_ANGLE),
)
# Datum B on the shank's left flank. The tag's edge attachment re-solves
# square to the flank, so its leader runs level at the tag's height, 4.5 mm
# above the shank width's dimension line (its text stands right of the shank).
DATUM_B_EDGE = _sheet_xy(-SHANK_WIDTH / 2.0, 100.0)
DATUM_B_SYMBOL = (DATUM_B_EDGE[0] - 0.016, FRONT_KEEP["ShankWidthDim"][1] + 0.0045)
# The .16 BASIC (datum B to the pin axis) runs on the shank, its text out
# to the left: over the pin its line lay on the position FCF's level leader
# and under the ream leader (baseline review); inside the head it crowded
# the hole and the ream callout's leader crossed it (#982 review r3); just
# below the fork root the leader still crossed its right-hand arrow
# (ENFORCE review). Below the ream callout's lowest line the leader, which
# runs up-left from that line to the hole, cannot reach it; above datum B's
# tag. On the shank its arrow lands on the flank itself, datum B's edge.
PIN_OFFSET_TEXT_XY = (0.150, _sheet_xy(0.0, 111.0)[1])
# The .16 BASIC from datum A (the bore axis) to datum B (the shank's left
# flank) completes the frame (ENFORCE review: nothing placed B sideways from
# A): its witness rises from the bore centre up the shank, its text out to
# the left on the shank above the ring, clear over the ring OD's text.
DATUM_B_FROM_A_TEXT_XY = (0.150, _sheet_xy(0.0, 55.0)[1])


def _fork_detail(adapter: Any, left: Any) -> Any:
    """DETAIL C: a native 3:1 detail of the side view's fork."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(left, "IView")
    if not drawing.ActivateView(view_name(adapter, left)):
        raise RuntimeError("failed to activate the fork detail's parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        left,
        (0.0, DETAIL_FENCE_Y_MM / 1000.0, 0.0),
        label="fork detail centre",
    )
    radius = DETAIL_RADIUS_MM * SHEET_SCALE[0] / 1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    # ENFORCE farm runs: an inferred circle snapped in screen space (a 12.4
    # and then a 9.7 mm fence, each off the rod axis), so the detail's fork
    # wandered under its fixed texts and their lines struck them. The fence
    # goes straight to the database and is read back before the detail
    # selects it (draw_dt_pinion_lever._hub_detail's recipe).
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        fence = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if fence is None:
        raise RuntimeError("failed to create the fork detail fence")
    placed_centre, placed_radius = native_circle_geometry(fence, label="fork detail fence")
    if math.dist(placed_centre[:2], points[0][:2]) > 1e-9 or not math.isclose(
        placed_radius, math.dist(points[0][:2], points[1][:2]), abs_tol=1e-9
    ):
        raise RuntimeError("the fork detail fence moved from where it was placed")
    draw.ClearSelection2(True)
    if not _early_bound(fence, "ISketchSegment").Select4(False, None):
        raise RuntimeError("failed to select the fork detail fence")
    detail = drawing.CreateDetailViewAt4(
        *DETAIL_CENTER,
        0.0,
        0,  # swDetViewSTANDARD
        *DETAIL_SCALE,
        "C",
        1,  # swDetCircleCIRCLE
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError("failed to create the fork detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    # A fresh detail's display geometry can lag its creation
    # (_drawing_detail_projection): refresh it before its outline places it.
    detail.UpdateViewDisplayGeometry()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("the fork detail has invalid bounds")
    target = [
        position[axis] + DETAIL_CENTER[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position the fork detail")
    draw.EditRebuild3()
    # DETAIL_KEEP assumes the fence centre (on the rod axis) prints at
    # DETAIL_CENTER: read it back through the settled detail.
    settle_detail_projection(
        adapter,
        detail,
        (0.0, DETAIL_FENCE_Y_MM / 1000.0, 0.0),
        ink_xy=DETAIL_CENTER,
        tolerance_xy=(DETAIL_PLACEMENT_TOL_M, DETAIL_PLACEMENT_TOL_M),
        label="fork detail fence centre",
    )
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*DETAIL_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError("failed to position the fork detail label")
    draw.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"the fork detail label did not persist: {actual}")
    circles = tuple(_read_member(parent, "GetDetailCircles") or ())
    if len(circles) != 1:
        raise RuntimeError(f"expected one detail circle on the side view, found {len(circles)}")
    circle = _early_bound(circles[0], "IDetailCircle")
    circle.SetLabelPosition(*DETAIL_LETTER_XY)
    draw.EditRebuild3()
    letter = tuple(float(value) for value in circle.GetLabelPosition())
    if len(letter) != 2 or math.dist(letter, DETAIL_LETTER_XY) > 1e-8:
        raise RuntimeError(f"the detail circle's letter did not persist: {letter}")
    return detail


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open connecting-rod source", await adapter.open_model(str(SOURCE)))
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
        unit=part_drawing_unit("ch-connecting-rod"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Connecting Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "connecting rod; 1018 steel; fork and cam strap",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    # The 1:1 left view (third angle: placed LEFT of the front) shows the
    # stepped thickness -- one .086 plate for ring and shank, and the .240
    # fork split by its slot into two tines -- and carries DETAIL C's circle.
    # The right-hand column belongs to the title block, so the side view lives
    # on the left.
    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (front, left, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    left_annotations = curate_view_dimensions(
        adapter,
        left,
        keep=LEFT_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    detail = _fork_detail(adapter, left)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="fork detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # The bands import with their named model dimensions, at the part's
    # places; the drawing owns only the callout text beneath them.
    assert_imported_precision(
        adapter,
        front_annotations,
        DRAWING_PRECISION["PinHoleProfile"],
    )
    assert_imported_precision(adapter, left_annotations, DRAWING_PRECISION["Plate"])
    assert_imported_precision(
        adapter,
        detail_annotations,
        {**DRAWING_PRECISION["ForkBoss"], **DRAWING_PRECISION["ForkSlotProfile"]},
    )
    set_dimension_callouts(adapter, front_annotations, FRONT_CALLOUTS)
    set_dimension_callouts(adapter, left_annotations, LEFT_CALLOUTS)
    set_dimension_callouts(adapter, detail_annotations, DETAIL_CALLOUTS)
    # Native, both ring diameters ran rim to rim through the bore's centre and
    # crossed there, under datum A's leader (#982 review r2): one arrow each on
    # the rim nearest its text keeps the bore clear.
    for name in NEAR_SIDE_DIAMETERS:
        matches = [
            annotation
            for annotation in front_annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
        set_near_side_diameter(matches[0], f"ring {name}")
    rebuild_drawing(adapter, label="ring diameters' near-side leaders")
    # Two tines and the slot set the fork over the tines: it prints as a
    # reference.
    fork_thick = [
        annotation
        for annotation in detail_annotations
        if dimension_name(adapter, annotation) == "ForkThick"
    ]
    if len(fork_thick) != 1:
        raise RuntimeError("fork detail does not carry exactly one fork thickness")
    set_reference_dimension(adapter, fork_thick[0], label="fork over the tines")
    # Overall length, ring bottom to crown top: the side view's two
    # horizontal silhouettes, so the dimension is their plain distance (two
    # circle picks in the front view would dimension centre to centre).
    picks = model_points_in_view(
        adapter,
        left,
        [
            tuple(v / 1000.0 for v in point)
            for point in (OVERALL_BOTTOM_MM, OVERALL_TOP_MM)
        ],
        label="overall length picks",
        names=tuple(OVERALL_FACES),
    )
    silhouettes = face_silhouettes_through(
        adapter,
        left,
        {
            key: (face, xy)
            for (key, face), xy in zip(OVERALL_FACES.items(), picks, strict=True)
        },
        label="overall length",
    )
    ends = tuple(silhouettes[key] for key in OVERALL_FACES)
    overall = add_edge_dimension(
        adapter,
        left,
        p0=picks[0],
        p1=picks[1],
        text_xy=OVERALL_TEXT_XY,
        label="overall length",
        orientation="vertical",
        entity_type="SILHOUETTE",
        entities=ends,
    )
    assert_dimension_measures(
        adapter,
        overall,
        expected_mm=OVERALL_LENGTH,
        label="overall length",
        entities=ends,
        entity_types=("SILHOUETTE", "SILHOUETTE"),
    )
    overall = _early_bound(overall, "IDisplayDimension")
    set_reference_dimension(adapter, overall.GetAnnotation(), label="overall length")

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    # Centre distance: ring bore edge to the rocker-pin bore edge (SolidWorks
    # dimensions circle edges centre-to-centre); box it BASIC.  Pick each bore's
    # LEFT rim -- the pin bore is tiny and sits inside the fork crown, so a TOP
    # pick snapped to the crown arc (read 145.07); the left rim is on the pin
    # circle, clear of the wider crown.
    ring_rim = _sheet_xy(-RING_BORE_DIA / 2.0, 0.0)
    pin_rim = _sheet_xy(-_PIN_HOLE_DIA / 2.0, CENTER_DISTANCE)
    centre_distance = add_edge_dimension(
        adapter,
        front,
        p0=ring_rim,
        p1=pin_rim,
        text_xy=(0.125, FRONT_CENTER[1]),
        label="rod centre distance",
    )
    set_basic_dimension(adapter, centre_distance, label="rod centre distance")

    # Datum A on the strap bore axis (picked at 5 o'clock, the tag below the
    # ring), Ra on the bore at 3 o'clock, and a position FCF tying the rocker
    # pin hole to A.
    add_datum_feature(
        adapter,
        front,
        edge_xy=DATUM_A_EDGE,
        symbol_xy=DATUM_A_SYMBOL,
        datum="A",
        label="strap bore axis",
    )
    # Datum B: the shank's left flank.  A alone leaves rotation about the bore
    # axis unconstrained, so the pin-hole position (and the centre distance's
    # direction) could not be inspected; B clocks the rod, the .16 BASIC from
    # A places B, and the .16 BASIC from B places the pin on the shank
    # centreline.
    add_datum_feature(
        adapter,
        front,
        edge_xy=DATUM_B_EDGE,
        symbol_xy=DATUM_B_SYMBOL,
        datum="B",
        label="shank left flank",
    )
    # Both .16 BASICs run from the flank to a circle's CENTRE (datum A's bore,
    # the pin's axis), set explicitly rather than left to the arc condition the
    # pick resolves to. Value-only: both picks are coordinate hits.
    datum_b_offset = add_edge_dimension(
        adapter,
        front,
        p0=DATUM_B_EDGE,
        p1=ring_rim,
        text_xy=DATUM_B_FROM_A_TEXT_XY,
        label="datum B from datum A",
        orientation="horizontal",
    )
    set_arc_endpoints_to_center(adapter, datum_b_offset, label="datum B from datum A")
    assert_dimension_measures(
        adapter,
        datum_b_offset,
        expected_mm=SHANK_WIDTH / 2.0,
        label="datum B from datum A",
    )
    set_basic_dimension(adapter, datum_b_offset, label="datum B from datum A")
    pin_offset = add_edge_dimension(
        adapter,
        front,
        p0=DATUM_B_EDGE,
        p1=pin_rim,
        text_xy=PIN_OFFSET_TEXT_XY,
        label="pin C/L from shank flank",
        orientation="horizontal",
    )
    set_arc_endpoints_to_center(adapter, pin_offset, label="pin C/L from shank flank")
    assert_dimension_measures(
        adapter,
        pin_offset,
        expected_mm=SHANK_WIDTH / 2.0,
        label="pin C/L from shank flank",
    )
    set_basic_dimension(adapter, pin_offset, label="pin C/L from shank flank")
    add_surface_finish(
        adapter,
        front,
        edge_xy=BORE_FINISH_EDGE,
        symbol_xy=BORE_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "strap_bore"),
        label="strap bore finish",
        char_height=BORE_FINISH_CHAR_HEIGHT,
    )
    # The position FCF attaches at the reamed pin hole's 3-o'clock rim with a
    # level leader, above the Ø callout's lane.
    pin_fcf_rim = _sheet_xy(_PIN_HOLE_DIA / 2.0, CENTER_DISTANCE)
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=pin_fcf_rim,
        frame_xy=(0.222, 0.222),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_IN["rocker pin hole position"],
        datums=("A", "B"),
        diameter=True,
        label="rocker pin hole position",
    )

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Connecting Rod Manufacturing Drawing",
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
