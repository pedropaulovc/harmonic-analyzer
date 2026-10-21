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

The strap-mouth relief prints as two separate, model-owned scalar dimensions:
width with its explicit band and angle under the title-block angular tolerance.
Their native text footprints share the removed section's open band, with each
kept clear of the other dimension's text and linework without reducing fonts.

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
from _drawing_dimension_import import curate_view_dimensions
from _drawing_layout_audit import _Reader, _dump_annotation
from _drawing_dimensions import (
    assert_imported_precision,
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
from _drawing_registry import DRAWINGS_BY_NAME, DRAWING_TEMPLATES
from _drawing_sections import create_section_view
from _drawing_sheet_region import sheet_drawable_region
from _drawing_view_display import set_hidden_lines_removed
from _gtol_cylinder import CylinderFace
from _layout_audit import annotation_geometry, calibrate_sheet_advance
from _layout_geometry import (
    Box, Segment, point_segment_distance, segment_box_distance, union_boxes,
)
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
    GEOMETRIC_TOLERANCES_MM,
    PIN_HOLE_DIA,
    RING_BORE_DIA,
    RING_BOTTOM_Y,
    RING_OUTER_RADIUS,
    RING_THICKNESS,
    ROOT_RELIEF_ANGLE_DEG,
    ROOT_RELIEF_BAND,
    ROOT_RELIEF_SIZE,
    SHANK_WIDTH,
    STRAP_DIAMETRAL_CLEARANCE,
    SURFACE_FINISHES,
)
from ch_rod_pivot_pin_spec import BUDGET as PIN_JOINT_BUDGET


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
# The one-line note stands in the open field between the front view's shank
# and the detail, clear of the bore's finish symbol.
NOTES_XY = (0.205, 0.130)

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
    # The inside corners' radius off the shank's +X flank onto the ring
    # (build_ch_connecting_rod's first fillet edge), up-right in the open
    # field right of the shank, above the bore's finish symbol.
    "InsideCornerR": (0.225, 0.106),
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
FRONT_CALLOUTS = {
    "StrapBoreDia": (
        f"BORE; RUNS ON CAM OF\n{CAM_NUMBER},"
        f" {_CLEARANCE_LEAST:.2f}-{_CLEARANCE_MOST:.2f}\nDIAMETRAL CLEARANCE"
    ),
    "ForkWidthDim": "FULL R",
    "InsideCornerR": "ALL INSIDE CORNERS",
    "PinHoleDia": (
        f"THRU - REAM; PRESS\nFIT ON PIN {PIN_NUMBER},\n"
        f"{_PRESS_LEAST:.3f}-{_PRESS_MOST:.3f} INTERFERENCE"
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
DETAIL_RADIUS_MM = 11.0
DETAIL_FENCE_Y_MM = (FORK_TOP_Y + FORK_BASE_Y - 2.0) / 2.0
# Right of the front view's pin-hole callout and FCF, below the isometric,
# above the title block.
DETAIL_CENTER = (0.325, 0.135)
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
    # of the datum face).
    "RingFaceNear": (_FACE_X - 0.030, _REF_END_Y - 0.010),
}
# The near tine's band locates the slot from the datum face (the channel's
# axial budget) and, with the far tine's, holds the gap to the next channel's
# rod (#982 review r2: a clearance alone would not need it).
DETAIL_CALLOUTS = {
    "TineNear": f"2X; LOCATES SLOT;\nCLEARS NEXT ROD\n{ROD_NUMBER}",
    "SlotWidth": f"RUNS ON ARM\n{ARM_NUMBER}",
    "RingFaceNear": f"PLATE FACE; RING IN\nCAM SLOT OF {CAM_NUMBER}",
}
# Removed section D-D and its native scalar dimensions occupy the open band BELOW the
# fork-detail fence and ABOVE the title block. Three-to-one preserves the
# ordinary text size while leaving room for the native section caption.
_ROOT_LAYOUT_GAP = 0.003
_ROOT_TEMPLATE = DRAWING_TEMPLATES[SPEC.layout]
_ROOT_BAND_BOTTOM = _ROOT_TEMPLATE.title_block_top_m + _ROOT_LAYOUT_GAP
_ROOT_BAND_TOP = DETAIL_CENTER[1] - _DETAIL_FENCE_R - _ROOT_LAYOUT_GAP
ROOT_SECTION_CENTER = (
    _ROOT_TEMPLATE.width_m - 0.035,
    (_ROOT_BAND_BOTTOM + _ROOT_BAND_TOP) / 2.0,
)
ROOT_SECTION_SCALE = (3, 1)
ROOT_SECTION_KEEP = {
    "RootReliefSize": (
        (_ROOT_TEMPLATE.title_block_left_m + ROOT_SECTION_CENTER[0]) / 2.0,
        _ROOT_BAND_BOTTOM + 0.010,
    ),
    # Only an import seed: native text/line readbacks seat both dimensions.
    "RootReliefAngle": (
        _ROOT_TEMPLATE.title_block_left_m + _ROOT_LAYOUT_GAP,
        (_ROOT_BAND_BOTTOM + _ROOT_BAND_TOP) / 2.0,
    ),
}
ROOT_SECTION_CALLOUTS = {
    "RootReliefSize": f"ONE SIDE ONLY;\n{CAM_NUMBER} WEB SIDE",
}
# A horizontal cut in LEFT spans the plate thickness at Y=0, giving a true
# XZ radial/axial section in the native chamfer dimensions' model plane.
_ROOT_CUT_MODEL_POINTS = (
    (0.0, 0.0, -(RING_THICKNESS / 2.0 + 1.0) / 1000.0),
    (0.0, 0.0, (RING_THICKNESS / 2.0 + 1.0) / 1000.0),
)


BORE_FINISH_EDGE = _sheet_xy(RING_BORE_DIA / 2.0, 0.0)
# At the plate's 2.5 mm character height (the default printed 5 mm and its
# "Ra 1.6" ran into the detail's plate-face callout, r1 and r2).
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
# Seed the half-shank BASIC in the open band between the datum/shank
# annotation and the pin callout. Native display-ink readbacks below seat
# its actual dimension line there, preserving both native endpoints.
PIN_OFFSET_TEXT_XY = (
    0.150, (DATUM_B_SYMBOL[1] + FRONT_KEEP["PinHoleDia"][1]) / 2.0,
)


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
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create the fork detail fence")
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


def _root_section_frame(adapter: Any, view: Any) -> tuple[tuple[float, float], ...]:
    origin = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label="strap origin")
    points = [
        model_point_in_view(adapter, view, point, label="strap section axis")
        for point in ((0.001, 0.0, 0.0), (0.0, 0.0, 0.001))
    ]
    return tuple(tuple(point[i] - origin[i] for i in (0, 1)) for point in points)


def _pin_offset_layout(
    adapter: Any, display: Any, front_annotations: list[Any], datum_b: Any,
    *, seat: bool = False,
) -> None:
    """Keep the BASIC's dimension line BELOW the whole native pin callout.

    Its vertical extension lines may cross the press-fit leader; the BASIC
    dimension line itself may not. Moving only its annotation preserves both
    originally selected native endpoints.
    """
    pin = [item for item in front_annotations if dimension_name(adapter, item) == "PinHoleDia"]
    shank = [item for item in front_annotations if dimension_name(adapter, item) == "ShankWidthDim"]
    if len(pin) != 1 or len(shank) != 1:
        raise RuntimeError("pin-offset layout needs the native pin and shank dimensions")
    display = _early_bound(display, "IDisplayDimension")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    if (
        annotation.IsDangling()
        or not any(entity is not None for entity in (annotation.GetAttachedEntities3() or ()))
        or not math.isclose(
            float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue) * 1000.0,
            SHANK_WIDTH / 2.0, abs_tol=1e-6,
        )
    ):
        raise RuntimeError("pin-offset BASIC lost its associated native half-shank dimension")
    reader = _Reader(adapter)
    records = [
        _dump_annotation(reader, raw)
        for raw in [
            pin[0], shank[0],
            _early_bound(datum_b, "IDatumTag").GetAnnotation(), annotation,
        ]
    ]
    errors = reader.take_errors()
    if errors or any(record is None for record in records):
        raise RuntimeError(f"pin-offset native layout reads refused: {errors}")
    advance = calibrate_sheet_advance(records)
    geometries = [
        annotation_geometry(record, owner="pin-offset layout", advance=advance)
        for record in records
    ]
    if any(geometry is None for geometry in geometries):
        raise RuntimeError("pin-offset layout has unreadable native ink")
    pin_ink = union_boxes([
        *geometries[0].text_boxes,
        *(segment.box() for segment in geometries[0].segments),
    ])
    lower_ink = union_boxes([
        box for geometry in geometries[1:3]
        for box in (
            *geometry.text_boxes,
            *(segment.box() for segment in geometry.segments if segment.role != "ext-line"),
        )
    ])
    basic_ink = union_boxes([
        *geometries[3].text_boxes,
        *(segment.box() for segment in geometries[3].segments if segment.role != "ext-line"),
    ])
    if pin_ink is None or lower_ink is None or basic_ink is None:
        raise RuntimeError("pin-offset layout has missing native text or dimension line")
    floor, ceiling = lower_ink.ymax + _ROOT_LAYOUT_GAP, pin_ink.ymin - _ROOT_LAYOUT_GAP
    if basic_ink.height > ceiling - floor:
        raise RuntimeError(
            f"pin-offset BASIC cannot fit between native datum/shank and pin callout: "
            f"basic={basic_ink}; floor={floor}; ceiling={ceiling}"
        )
    if seat:
        position = tuple(float(value) for value in annotation.GetPosition())
        shift = (floor + ceiling - basic_ink.height) / 2.0 - basic_ink.ymin
        if not annotation.SetPosition2(position[0], position[1] + shift, position[2]):
            raise RuntimeError("pin-offset BASIC native annotation placement refused")
        rebuild_drawing(adapter, label="pin-offset BASIC below press-fit callout")
        _pin_offset_layout(adapter, display, front_annotations, datum_b)
    elif basic_ink.ymin < floor - 1e-8 or basic_ink.ymax > ceiling + 1e-8:
        raise RuntimeError(
            f"pin-offset BASIC dimension line/text leaves its native clear lane: "
            f"basic={basic_ink}; floor={floor}; ceiling={ceiling}"
        )
    else:
        _telemetry.info(
            f"pin-offset BASIC native ink={basic_ink}; datum/shank ink={lower_ink}; "
            f"pin-callout ink={pin_ink}; required air={_ROOT_LAYOUT_GAP}"
        )


def _root_section_band(adapter: Any, sheet: Any) -> Box:
    region = sheet_drawable_region(
        adapter, sheet, width=_ROOT_TEMPLATE.width_m, height=_ROOT_TEMPLATE.height_m,
    )
    return Box(
        max(region.xmin, _ROOT_TEMPLATE.title_block_left_m) + _ROOT_LAYOUT_GAP,
        _ROOT_BAND_BOTTOM,
        region.xmax - _ROOT_LAYOUT_GAP,
        _ROOT_BAND_TOP,
    )


def _root_section_boxes(view: Any) -> tuple[Box, ...]:
    """Refreshed native view outline and native caption extent, in sheet metres."""
    view = _early_bound(view, "IView")
    # A rebuild does not return control to the window's repaint loop.
    # UpdateViewDisplayGeometry is VT_VOID and exposes the changed geometry now.
    view.UpdateViewDisplayGeometry()
    outline = tuple(float(value) for value in view.GetOutline())
    if (
        len(outline) != 4 or not all(math.isfinite(value) for value in outline)
        or outline[2] <= outline[0] or outline[3] <= outline[1]
    ):
        raise RuntimeError(f"strap section has invalid native outline {outline}")
    boxes = [Box(*outline)]
    notes = tuple(view.GetNotes() or ())
    if len(notes) != 1:
        raise RuntimeError("strap section must retain its one native section caption")
    extent = tuple(float(value) for value in _early_bound(notes[0], "INote").GetExtent())
    if (
        len(extent) != 6 or not all(math.isfinite(value) for value in extent)
        or extent[3] <= extent[0] or extent[4] <= extent[1]
    ):
        raise RuntimeError(f"strap section has invalid native caption extent {extent}")
    boxes.append(Box(extent[0], extent[1], extent[3], extent[4]))
    return tuple(boxes)


def _root_section_shift(boxes: tuple[Box, ...], band: Box) -> tuple[float, float]:
    """Seat the measured section/caption group without discarding native extents."""
    whole = union_boxes(list(boxes))
    # INote.GetExtent is screen-quantized. Leave air at the band's right edge
    # rather than seating its caption exactly on a fatal containment boundary.
    right = band.xmax - _ROOT_LAYOUT_GAP
    if whole.width > right - band.xmin or whole.height > band.height:
        raise RuntimeError(
            f"strap section and native caption do not fit their open band: "
            f"outline={boxes[0]}; caption={boxes[1]}; union={whole}; band={band}"
        )
    return right - whole.xmax, band.center()[1] - whole.center()[1]


def _root_layout_geometry(
    adapter: Any, view: Any, annotations: list[Any], detail_annotations: list[Any],
) -> tuple[dict[str, tuple[Box, tuple[Segment, ...]]], tuple[Box, ...]]:
    """Use the shared audit's native positions and calibrated dimension widths.

    Dimension widths remain estimates until the exported PDF audit; their
    baselines/heights and all linework come from actual native display data.
    """
    names = [dimension_name(adapter, annotation) for annotation in annotations]
    if sorted(names) != ["RootReliefAngle", "RootReliefSize"]:
        raise RuntimeError("strap section layout requires one native width and one angle")
    reader = _Reader(adapter)
    caption = _early_bound(tuple(view.GetNotes())[0], "INote").GetAnnotation()
    records = [
        _dump_annotation(reader, annotation)
        for annotation in [*annotations, *detail_annotations, caption]
    ]
    errors = reader.take_errors()
    if errors or any(record is None for record in records):
        raise RuntimeError(f"strap section native layout reads refused: {errors}")
    advance = calibrate_sheet_advance(records)
    geometries = [
        annotation_geometry(record, owner="strap section layout", advance=advance)
        for record in records
    ]
    if any(geometry is None for geometry in geometries):
        raise RuntimeError("strap section layout contains unreadable native annotation ink")
    dimensions = {}
    for name, geometry in zip(names, geometries[:2], strict=True):
        text = union_boxes(list(geometry.text_boxes))
        if text is None:
            raise RuntimeError(f"strap section {name} has no native rendered text")
        dimensions[name] = (
            text, tuple(segment for segment in geometry.segments if segment.length > 0.0),
        )
    obstacles = tuple(
        box for geometry in geometries[2:-1]
        for box in (
            *geometry.text_boxes,
            *(segment.box() for segment in geometry.segments if segment.length > 0.0),
        )
    )
    return dimensions, obstacles


def _root_text_target(
    text: Box, band: Box, obstacles: tuple[Box, ...], lines: tuple[Segment, ...] = (),
) -> Box:
    """Choose an empty lane from native obstacle edges, not a text-centre guess."""
    gap = _ROOT_LAYOUT_GAP
    xs = {band.xmin, band.xmax - text.width}
    ys = {band.ymin, band.ymax - text.height}
    for obstacle in (*obstacles, *(segment.box() for segment in lines)):
        xs.update((obstacle.xmin - gap - text.width, obstacle.xmax + gap))
        ys.update((obstacle.ymin - gap - text.height, obstacle.ymax + gap))
    for y in sorted(ys):
        for x in sorted(xs, reverse=True):
            candidate = Box(x, y, x + text.width, y + text.height)
            if (
                candidate.xmin < band.xmin - 1e-9
                or candidate.ymin < band.ymin - 1e-9
                or candidate.xmax > band.xmax + 1e-9
                or candidate.ymax > band.ymax + 1e-9
            ):
                continue
            if (
                all(candidate.gap(obstacle) >= gap - 1e-9 for obstacle in obstacles)
                and all(segment_box_distance(line, candidate) >= gap - 1e-9 for line in lines)
            ):
                return candidate
    raise RuntimeError(
        "strap section callout cannot fit below Detail C without shrinking text: "
        f"text={text}, band={band}, obstacles={obstacles}, other dimension lines={lines}"
    )


def _assert_root_section_layout(
    adapter: Any, view: Any, annotations: list[Any],
    detail_annotations: list[Any], band: Box,
) -> None:
    boxes = _root_section_boxes(view)
    dimensions, detail_ink = _root_layout_geometry(adapter, view, annotations, detail_annotations)
    texts = tuple(text for text, _lines in dimensions.values())
    for box in (*boxes, *texts):
        if (
            box.xmin < band.xmin - 1e-8 or box.ymin < band.ymin - 1e-8
            or box.xmax > band.xmax + 1e-8 or box.ymax > band.ymax + 1e-8
        ):
            raise RuntimeError(f"strap section/caption/callout leaves its open band: {box}; {band}")
    if any(
        box.gap(other) < _ROOT_LAYOUT_GAP - 1e-8
        for box in (*boxes, *texts) for other in detail_ink
    ):
        raise RuntimeError("strap section/caption/callout crowds actual Detail C text or lines")
    for name, (text, _lines) in dimensions.items():
        if any(text.gap(box) < _ROOT_LAYOUT_GAP - 1e-8 for box in boxes):
            raise RuntimeError(f"strap section {name} crowds its native section or caption")
        for other_name, (other_text, other_lines) in dimensions.items():
            if other_name == name:
                continue
            if (
                text.gap(other_text) < _ROOT_LAYOUT_GAP - 1e-8
                or any(
                    segment_box_distance(line, text) < _ROOT_LAYOUT_GAP - 1e-8
                    for line in other_lines
                )
            ):
                raise RuntimeError(f"strap section {name} crowds {other_name} text or lines")
    _telemetry.info(
        f"strap section layout: native view/caption boxes={boxes}; "
        f"native-position/calibrated-width scalar text boxes={texts}; open band={band}"
    )


def _seat_root_callout(
    adapter: Any, view: Any, annotations: list[Any],
    detail_annotations: list[Any], band: Box, view_boxes: tuple[Box, ...],
) -> None:
    rebuild_drawing(adapter, label="strap section native callout rows")
    # Seat the wider width/callout stack first, then the separate angle. Read
    # native ink again after each move: an angular arc is not a translated box.
    for name in ("RootReliefSize", "RootReliefAngle"):
        dimensions, detail_ink = _root_layout_geometry(
            adapter, view, annotations, detail_annotations,
        )
        text, _lines = dimensions[name]
        others = [geometry for other_name, geometry in dimensions.items() if other_name != name]
        target = _root_text_target(
            text, band,
            (*view_boxes, *detail_ink, *(other_text for other_text, _ in others)),
            tuple(line for _other_text, other_lines in others for line in other_lines),
        )
        annotation = _early_bound(
            next(item for item in annotations if dimension_name(adapter, item) == name),
            "IAnnotation",
        )
        position = tuple(float(value) for value in annotation.GetPosition())
        if not annotation.SetPosition2(
            position[0] + target.xmin - text.xmin,
            position[1] + target.ymin - text.ymin,
            position[2],
        ):
            raise RuntimeError(f"strap section native {name} placement refused")
        rebuild_drawing(adapter, label=f"strap section native {name} seated")
    _assert_root_section_layout(adapter, view, annotations, detail_annotations, band)


def _root_cut_profile_points() -> tuple[tuple[float, float, float], ...]:
    """The complete +X wall in the Y=0 section, including the -Z chamfer."""
    bore, outer, half = RING_BORE_DIA / 2.0, RING_OUTER_RADIUS, RING_THICKNESS / 2.0
    return tuple(
        (x / 1000.0, 0.0, z / 1000.0)
        for x, z in (
            (bore, half), (outer, half), (outer, -half),
            (bore + ROOT_RELIEF_SIZE, -half), (bore, -half + ROOT_RELIEF_SIZE),
        )
    )


def _root_polyline_segments(raw: Any) -> tuple[Segment, ...]:
    """Decode the documented GetPolylines7 buffer for this straight cut profile."""
    values = tuple(float(value) for value in (raw or ()))
    if not values or not all(math.isfinite(value) for value in values):
        raise RuntimeError(f"strap cut has empty/nonfinite native polylines: {values!r}")
    index, segments = 0, []
    while index < len(values):
        # Type, GeomDataSize, six line/layer fields, NumPolyPoints, then XYZs.
        if len(values) - index < 9 or values[index:index + 2] != (0.0, 0.0):
            raise RuntimeError(f"strap cut has an incomplete/nonlinear polyline at {index}: {values!r}")
        count = values[index + 8]
        if not count.is_integer() or count < 2:
            raise RuntimeError(f"strap cut has invalid native polyline point count {count!r}")
        end = index + 9 + 3 * int(count)
        if end > len(values):
            raise RuntimeError(f"strap cut has truncated native polyline at {index}: {values!r}")
        points = tuple(
            (values[offset], values[offset + 1])
            for offset in range(index + 9, end, 3)
        )
        segments.extend(
            segment for first, second in zip(points, points[1:])
            if (segment := Segment(*first, *second)).length > 1e-12
        )
        index = end
    return tuple(segments)


def _assert_root_profile_lines(lines: tuple[Segment, ...], corners: Any) -> None:
    """The displayed cut must retain every true wall/chamfer edge and no other wall."""
    tolerance = 1e-7  # sheet m; 0.1 um numerical readback tolerance, not a size allowance
    expected = tuple(
        Segment(*first, *second)
        for first, second in zip(corners, (*corners[1:], corners[0]))
    )
    if not lines or any(
        not any(
            point_segment_distance((line.x0, line.y0), edge) <= tolerance
            and point_segment_distance((line.x1, line.y1), edge) <= tolerance
            for edge in expected
        )
        for line in lines
    ):
        raise RuntimeError(f"strap cut contains off-profile/other-wall native edges: {lines!r}")
    for edge in expected:
        length = edge.length
        direction = ((edge.x1 - edge.x0) / length, (edge.y1 - edge.y0) / length)
        intervals = []
        for line in lines:
            endpoints = ((line.x0, line.y0), (line.x1, line.y1))
            if all(point_segment_distance(point, edge) <= tolerance for point in endpoints):
                projected = [
                    (point[0] - edge.x0) * direction[0] + (point[1] - edge.y0) * direction[1]
                    for point in endpoints
                ]
                intervals.append((max(0.0, min(projected)), min(length, max(projected))))
        covered = 0.0
        for start, end in sorted(intervals):
            if start > covered + tolerance:
                raise RuntimeError(f"strap cut omits a wall/chamfer interval on {edge}: {intervals!r}")
            covered = max(covered, end)
        if covered < length - tolerance:
            raise RuntimeError(f"strap cut clips a wall/chamfer edge {edge}: {intervals!r}")


def _assert_root_cut_profile(adapter: Any, view: Any) -> None:
    native = _early_bound(view, "IView")
    native.UpdateViewDisplayGeometry()  # VT_VOID
    result = native.GetPolylines7(1)  # exclude hatch; makepy returns (edges, polylines)
    if not isinstance(result, tuple) or len(result) != 2:
        raise RuntimeError(f"strap cut has invalid native edge/polyline pair: {result!r}")
    lines = _root_polyline_segments(result[1])
    corners = model_points_in_view(
        adapter, native, _root_cut_profile_points(), label="complete strap cut wall",
    )
    _assert_root_profile_lines(lines, corners)
    _telemetry.info(
        f"strap cut +X wall/chamfer retained: native lines={len(lines)}; "
        f"projected physical corners={corners!r}; cropped={bool(native.IsCropped())}"
    )


def _crop_root_section(adapter: Any, view: Any) -> None:
    """Existing native cropped-section pattern, retaining 1 mm air around +X wall."""
    from _com import _bind

    draw = adapter.currentModel
    document = _early_bound(draw, "IDrawingDoc")
    view = _early_bound(view, "IView")
    margin = 1.0
    points = model_points_in_view(
        adapter, view,
        [
            (x / 1000.0, 0.0, z / 1000.0)
            for x in (RING_BORE_DIA / 2.0 - margin, RING_OUTER_RADIUS + margin)
            for z in (-RING_THICKNESS / 2.0 - margin, RING_THICKNESS / 2.0 + margin)
        ],
        label="strap section complete wall crop fence",
    )
    fence = Box.from_points(points)
    if fence is None or not document.ActivateView(view_name(adapter, view)):
        raise RuntimeError("strap section crop has no projected fence/active view")
    draw.ClearSelection2(True)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    corners = []
    for x, y in ((fence.xmin, fence.ymax), (fence.xmax, fence.ymin)):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        if point is None:
            raise RuntimeError("strap crop fence point is missing")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        if projected is None:
            raise RuntimeError("strap crop fence sketch projection is missing")
        corners.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        segments = tuple(manager.CreateCornerRectangle(*corners[0], *corners[1]) or ())
    finally:
        manager.AddToDB = previous
    if len(segments) != 4:
        raise RuntimeError(f"strap crop fence has {len(segments)} sketch segments, expected 4")
    for segment in segments:
        if not _early_bound(_bind(segment, "ISketchSegment"), "ISketchSegment").Select4(True, None):
            raise RuntimeError("strap crop fence segment selection refused")
    status = int(view.Crop2(False, True, 0))  # swCropViewErrors_NoError == 1
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="strap XZ section cropped to complete +X wall")
    view.UpdateViewDisplayGeometry()
    if status != 1 or not bool(view.IsCropped()) or not bool(view.CropViewNoOutline):
        raise RuntimeError(f"strap section native crop refused: status={status}, fence={fence}")
    draw.ViewZoomtofit2()  # documented prerequisite for all native polylines
    _assert_root_cut_profile(adapter, view)


def _root_dimensions(adapter: Any, view: Any) -> list[Any]:
    """Import this feature directly; a native refusal retains source/selection evidence."""
    from types import SimpleNamespace

    from solidworks_mcp.adapters.pywin32_adapter import null_callout
    from solidworks_mcp.adapters.solidworks.drawing import curate_dimensions

    from _com import _bind
    from _drawing_dimension_import import _model_item_paths, _select_model_feature
    from _drawing_precision import _named_dimensions

    draw = adapter.currentModel
    document = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not document.ActivateView(name):
        raise RuntimeError("strap dimensions cannot activate their native section")
    draw.ClearSelection2(True)
    try:
        if not draw.Extension.SelectByID2(
            name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0,
        ):
            raise RuntimeError("strap dimensions cannot select their native section")
        paths = _model_item_paths(adapter, view)
        selected = _select_model_feature(adapter, "CamRootRelief", paths=paths)
        selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
        count = int(selection.GetSelectedObjectCount2(-1))
        _telemetry.info(
            f"strap native model-item selection: view={name!r}; paths={paths!r}; "
            f"feature={selected!r}; types="
            f"{tuple(int(selection.GetSelectedObjectType3(i, -1)) for i in range(1, count + 1))!r}"
        )
        result = document.InsertModelAnnotations3(1, 0x28000, False, True, True, False)
        annotations = [
            _early_bound(_bind(item, "IAnnotation"), "IAnnotation")
            for item in (result or ())
        ]
        names = [dimension_name(adapter, annotation) for annotation in annotations]
        if sorted(names) != sorted(ROOT_SECTION_KEEP):
            raise RuntimeError(f"strap native section import missing/extra dimensions: {names!r}")
        return curate_dimensions(adapter, annotations, reposition=dict(ROOT_SECTION_KEEP))
    except Exception:
        try:
            source = _early_bound(_early_bound(view, "IView").ReferencedDocument, "IModelDoc2")
            dimensions = _named_dimensions(
                SimpleNamespace(currentModel=source), "CamRootRelief", set(ROOT_SECTION_KEEP),
            )
            _telemetry.info(
                "strap native import refusal source census: "
                + repr([
                    {
                        "identity": str(dimension.FullName), "type": int(display.Type2),
                        "value": float(dimension.SystemValue), "marked": bool(display.MarkedForDrawing),
                        "plane": tuple(_early_bound(display.GetAnnotation(), "IAnnotation").GetPlane() or ()),
                    }
                    for display, dimension in dimensions.values()
                ])
            )
        except Exception as census_error:
            _telemetry.info(f"strap source census refused: {census_error!r}")
        raise
    finally:
        draw.ClearSelection2(True)


def _assert_root_parent_clearance(adapter: Any, view: Any, annotations: list[Any]) -> None:
    """The native LEFT cutting line/arrows/letters must clear its plate dimension."""
    from _layout_audit import _section_geometry

    reader = _Reader(adapter)
    records = [_dump_annotation(reader, annotation) for annotation in annotations]
    errors = reader.take_errors()
    if errors or any(record is None for record in records):
        raise RuntimeError(f"strap parent dimension ink is unreadable: {errors}")
    advance = calibrate_sheet_advance(records)
    cut = _early_bound(_early_bound(view, "IView").GetSection(), "IDrSection")
    height = float(_early_bound(cut.GetTextFormat(), "ITextFormat").CharHeight)
    arrows, texts = tuple(cut.GetArrowInfo() or ()), tuple(cut.GetTextInfo() or ())
    if len(arrows) != 12 or len(texts) != 6 or not math.isfinite(height) or height <= 0.0:
        raise RuntimeError("strap parent cutting line has unreadable native arrows/letters")
    section = _section_geometry(
        {"label": str(cut.GetLabel()), "arrows": arrows, "texts": texts, "text_height": height},
        owner="strap section parent", advance=advance,
    )
    parents = [
        annotation_geometry(record, owner="strap section parent", advance=advance)
        for record in records
    ]
    if section is None or any(parent is None for parent in parents):
        raise RuntimeError("strap parent cutting line/dimension ink is missing")
    section_boxes = (
        *section.text_boxes, *(line.box() for line in section.segments if line.length > 0.0),
    )
    parent_boxes = tuple(
        box for parent in parents
        for box in (*parent.text_boxes, *(line.box() for line in parent.segments if line.length > 0.0))
    )
    if any(box.gap(other) < _ROOT_LAYOUT_GAP - 1e-8 for box in section_boxes for other in parent_boxes):
        raise RuntimeError("strap native cutting line/arrows/letters crowd the LEFT plate dimension")
    _telemetry.info(f"strap parent cutting-line ink={section_boxes!r}; plate dimension ink={parent_boxes!r}")


def _root_section(adapter: Any, left: Any, band: Box) -> tuple[Any, list[Any]]:
    start, end = model_points_in_view(
        adapter, left, _ROOT_CUT_MODEL_POINTS, label="strap XZ section in left parent",
    )
    view = create_section_view(
        adapter, left,
        line_start=start, line_end=end,
        view_xy=ROOT_SECTION_CENTER, section_label="D", scale=ROOT_SECTION_SCALE,
        partial=False, label="one web-facing strap-mouth relief",
    )
    view = _early_bound(view, "IView")
    cut = _early_bound(view.GetSection(), "IDrSection")
    cut.SetDisplayOnlySurfaceCut(True)  # native void setter; dedicated readback below
    horizontal, vertical = _root_section_frame(adapter, view)
    if horizontal[0] * vertical[1] - horizontal[1] * vertical[0] < 0.0:
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="strap section cut reversed")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("strap section cutting direction did not persist")
        horizontal, _vertical = _root_section_frame(adapter, view)
    view.Angle = float(view.Angle) - math.atan2(horizontal[1], horizontal[0])
    rebuild_drawing(adapter, label="strap section +X right, +Z up")
    set_hidden_lines_removed(adapter, view)
    # Oblique-carrier's native positive control: full sections import model
    # dimensions that partial sections refuse; crop only AFTER importing.
    # A crop can otherwise exclude the model display's annotation origin.
    annotations = _root_dimensions(adapter, view)
    _crop_root_section(adapter, view)
    # Put the native caption BESIDE the small section, not below it. This
    # saves the narrow band's height without changing any character height.
    outline, caption_box = _root_section_boxes(view)
    caption = _early_bound(tuple(view.GetNotes())[0], "INote")
    annotation = _early_bound(caption.GetAnnotation(), "IAnnotation")
    at = tuple(float(value) for value in annotation.GetPosition())
    if not annotation.SetPosition2(
        at[0] + outline.xmax + _ROOT_LAYOUT_GAP - caption_box.xmin,
        at[1] + outline.center()[1] - caption_box.center()[1],
        at[2],
    ):
        raise RuntimeError("strap section native caption could not be placed beside its view")
    rebuild_drawing(adapter, label="strap section native caption beside view")
    boxes = _root_section_boxes(view)
    _telemetry.info(
        f"strap section before placement: native outline={boxes[0]}; "
        f"native caption={boxes[1]}; band={band}"
    )
    shift = _root_section_shift(boxes, band)
    position = tuple(float(value) for value in view.Position)
    target = [position[index] + shift[index] for index in (0, 1)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("strap section could not be seated in its open band")
    set_hidden_lines_removed(adapter, view)
    rebuild_drawing(adapter, label="strap section below Detail C fence")
    boxes = _root_section_boxes(view)
    for box in boxes:
        if (
            box.xmin < band.xmin - 1e-8 or box.ymin < band.ymin - 1e-8
            or box.xmax > band.xmax + 1e-8 or box.ymax > band.ymax + 1e-8
        ):
            raise RuntimeError(
                f"strap section/caption leaves its open band after placement: {box}; {band}"
            )
    _telemetry.info(
        f"strap section positioned and regenerated: native outline={boxes[0]}; "
        f"native caption={boxes[1]}; band={band}"
    )
    return view, annotations


def _assert_root_section(adapter: Any, view: Any, annotations: list[Any]) -> None:
    """Settled native section and both separately owned scalar dimensions."""
    view = _early_bound(view, "IView")
    cut = _early_bound(view.GetSection(), "IDrSection")
    horizontal, vertical = _root_section_frame(adapter, view)
    if (
        int(view.GetDisplayMode2()) != 2  # swHIDDEN (hidden lines removed)
        or bool(view.GetUseParentDisplayMode())
        or bool(cut.GetPartialSection())
        or not bool(cut.GetDisplayOnlySurfaceCut())
        or not bool(view.IsCropped())
        or horizontal[0] <= 0.0
        or abs(horizontal[1]) > 1e-8
        or vertical[1] <= 0.0
        or abs(vertical[0]) > 1e-8
        or tuple(float(value) for value in view.ScaleRatio) != ROOT_SECTION_SCALE
    ):
        raise RuntimeError("strap section lost cut-only/cropped/full/scale/+X-right/+Z-up frame")
    names = [dimension_name(adapter, annotation) for annotation in annotations]
    if sorted(names) != ["RootReliefAngle", "RootReliefSize"]:
        raise RuntimeError("strap section must carry exactly one native width and one angle")
    # Imported feature display dimensions have no generic attached-edge array
    # (native source and LEFT positive control both read zero). Their model
    # parameter identity plus actual destination-view membership is authoritative.
    owned = [
        _early_bound(item, "IAnnotation") for item in (view.GetAnnotations() or ())
        if dimension_name(adapter, _early_bound(item, "IAnnotation")) in ROOT_SECTION_KEEP
    ]
    owned_identities = [
        str(_early_bound(
            _early_bound(item.GetSpecificAnnotation(), "IDisplayDimension").GetDimension2(0),
            "IDimension",
        ).FullName)
        for item in owned
    ]
    if sorted(dimension_name(adapter, item) for item in owned) != sorted(names):
        raise RuntimeError("strap section native dimensions are not owned exactly once by its view")
    for name, item in zip(names, annotations, strict=True):
        annotation = _early_bound(item, "IAnnotation")
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        is_width = name == "RootReliefSize"
        expected_type = 2 if is_width else 3  # swLinearDimension / swAngularDimension
        expected_value = ROOT_RELIEF_SIZE / 1000.0 if is_width else math.radians(ROOT_RELIEF_ANGLE_DEG)
        if (
            bool(annotation.IsDangling())
            or int(annotation.OwnerType) != 0  # swAnnotationOwner_DrawingView
            or owned_identities.count(str(dimension.FullName)) != 1
            or int(display.Type2) != expected_type
            or str(dimension.FullName).split("@")[:2] != [name, "CamRootRelief"]
            or not math.isclose(
                float(dimension.SystemValue), expected_value, rel_tol=0.0,
                abs_tol=1e-9 if is_width else 1e-10,
            )
            or int(tolerance.Type) != (4 if is_width else 0)  # symmetric / title block
        ):
            raise RuntimeError(
                f"strap section {name} lost its associative native source/type/value/view owner/band"
            )
        if is_width and (
            not math.isclose(
                float(tolerance.GetMinValue()) * 1000.0, ROOT_RELIEF_BAND[1], abs_tol=1e-9
            )
            or not math.isclose(
                float(tolerance.GetMaxValue()) * 1000.0, ROOT_RELIEF_BAND[0], abs_tol=1e-9
            )
        ):
            raise RuntimeError("strap section width lost its native symmetric band")
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION["CamRootRelief"])
    _telemetry.success(
        "strap section D-D: ONE local -Z relief, separate native width/band and angle"
    )


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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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
    # stepped thickness -- one 2.175 plate for ring and shank, and the 6.075
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
    root_band = _root_section_band(adapter, _sheet)
    root_section, root_annotations = _root_section(adapter, left, root_band)
    root_view_boxes = _root_section_boxes(root_section)
    # The bands import with their named model dimensions, at the part's
    # places; the drawing owns only the callout text beneath them.
    assert_imported_precision(
        adapter,
        front_annotations,
        {**DRAWING_PRECISION["PinHoleProfile"], **DRAWING_PRECISION["InsideCorners"]},
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
    set_dimension_callouts(adapter, root_annotations, ROOT_SECTION_CALLOUTS)
    _seat_root_callout(
        adapter, root_section, root_annotations, detail_annotations, root_band,
        root_view_boxes,
    )
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
    # axis unconstrained, so the pin-hole position (and the 147.67 direction)
    # could not be inspected; B clocks the rod and the 4.00 BASIC below ties
    # the pin to the shank centreline.
    datum_b = add_datum_feature(
        adapter,
        front,
        edge_xy=DATUM_B_EDGE,
        symbol_xy=DATUM_B_SYMBOL,
        datum="B",
        label="shank left flank",
    )
    pin_offset = add_edge_dimension(
        adapter,
        front,
        p0=DATUM_B_EDGE,
        p1=pin_rim,
        text_xy=PIN_OFFSET_TEXT_XY,
        label="pin C/L from shank flank",
        orientation="horizontal",
    )
    set_basic_dimension(adapter, pin_offset, label="pin C/L from shank flank")
    _pin_offset_layout(adapter, pin_offset, front_annotations, datum_b, seat=True)
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
        tolerance=GEOMETRIC_TOLERANCES_MM["rocker pin hole position"],
        datums=("A", "B"),
        diameter=True,
        label="rocker pin hole position",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Connecting Rod Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(
            lambda: _assert_root_section(adapter, root_section, root_annotations),
            lambda: _assert_root_cut_profile(adapter, root_section),
            lambda: _assert_root_parent_clearance(adapter, root_section, left_annotations),
            lambda: _assert_root_section_layout(
                adapter, root_section, root_annotations, detail_annotations, root_band,
            ),
            lambda: _pin_offset_layout(adapter, pin_offset, front_annotations, datum_b),
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
