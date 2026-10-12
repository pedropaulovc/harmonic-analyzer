r"""Create the curated machinist drawing for the rocker arm.

The SLDPRT remains authoritative.  This recipe supplies only the rocker-arm
views, dimension layout, hole callouts, and manufacturing notes;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.

The strap is a long thin curved seesaw (~292 mm tip to tip, 16 mm deep, 2.5 mm
thick). The front carries the BASIC arc system and A-to-pin coordinates;
parent-linked D (4:1) and E (2:1) carry the hub and rod-end controls. The
1:1 side carries thickness/hub length; the 1:4 isometric supplements them.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_arm.py ch-rocker-arm
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import re
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
import _surface_finish
import ch_rocker_arm_notes as rocker_notes
import ch_rocker_arm_spec as rocker
from _feature_requirements import part_metadata, requirement
from _printed_limits import drilled_limits as _drilled_band
from _printed_limits import limits as _band
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
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
    set_arc_endpoints_to_center,
    set_basic_dimension,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import ViewEdge, scan_view_edges
from _drawing_finish import add_surface_finish
from _drawing_gdt import add_datum_feature, add_feature_control_frame

# The part saves TopEdgeReference hidden (#880): this form shows it in the
# view that imports its dimension.
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_layout_audit import _Reader, _dump_annotation, _dump_display
from _drawing_layout_collect import check_drawing_layout
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
from _drawing_notes import add_property_linked_note, set_note_text_height
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _drawing_projection import model_points_in_view
from _drawing_selection import _select_view_entity
from _drawing_sheet_region import sheet_drawable_region
from _drawing_view_display import set_hidden_lines_removed, set_hidden_lines_visible
from _gear_drawing_entities import visible_circle_edge
from _layout_audit import (
    _detail_circles,
    _registered_leaders,
    annotation_geometry,
    calibrate_sheet_advance,
)
from _layout_geometry import Box, segment_box_distance, text_overlap, union_boxes
from _hole_spec import blind_cut_dia_mm, drill_process
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _seat_forensics
import _telemetry
from ch_rocker_arm_notes import (
    DEFAULT_DRAWING_PRECISION,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
)
from ch_rocker_arm_spec import (
    ARM_DEPTH,
    ARM_THICKNESS,
    BOT_END_X,
    CENTER_Y,
    GEOMETRIC_TOLERANCES_MM,
    HUB_DIA,
    HUB_LENGTH,
    PIVOT_HOLE_DIA,
    PIVOT_HOLE_BAND,
    PIVOT_MID_Y,
    R_TOP,
    R_BOTTOM,
    ROD_HOLE_SPEC,
    ROD_HOLE_X,
    ROD_HOLE_Y,
    ROD_TIP_X,
    SURFACE_FINISHES,
    TIP_FACE,
    TOP_ARC_LEN,
    TOP_EDGE_BAND,
    TOP_END_X,
    TOP_END_Y,
    _ALPHA_TOP,
)


SPEC = DRAWINGS_BY_NAME["ch_rocker_arm"]
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

SHEET_SCALE = (1.0, 2.0)  # 1:2

_ROD_HOLE_DIA = blind_cut_dia_mm(ROD_HOLE_SPEC)

_P = rocker_notes.DEFAULT_DRAWING_PRECISION
_AXIS = ((0.0, 0.0, 1.0), ("__frame__",))
_CENTRE = ([0.0, rocker.PIVOT_MID_Y, 0.0], ("PIVOT_MID_Y",))

part_metadata(
    fields={
        "precision": (_P, (("ch_rocker_arm_notes", "DEFAULT_DRAWING_PRECISION"),)),
        "material.thickness": (rocker.ARM_THICKNESS, ("ARM_THICKNESS",)),
    },
    model_sources=("ARM_THICKNESS", "HUB_LENGTH"),
    precision_sources=(("ch_rocker_arm_notes", "DRAWING_PRECISION"), ("ch_rocker_arm_notes", "DEFAULT_DRAWING_PRECISION"), ("ch_rocker_arm_notes", "DRAWING_NOTES"), ("_surface_finish", "ra")),
)

FRONT_CENTER = (0.180, 0.175)
RIGHT_CENTER = (0.300, 0.165)
ISO_CENTER = (0.345, 0.205)
ROD_HOLE = requirement(
    "rod_hole", kind="hole", faces=(CylinderFace(blind_cut_dia_mm(rocker.ROD_HOLE_SPEC)),),
    requirements=("at", "dia", "thru", "position_dia"), fields={
        "at": ([rocker.ROD_HOLE_X, rocker.ROD_HOLE_Y, 0.0], ("ROD_HOLE_X", "ROD_HOLE_Y")),
        "axis": _AXIS, "drill": (rocker.ROD_HOLE_SPEC.size, ("ROD_HOLE_SPEC",)),
        "dia": (_drilled_band(blind_cut_dia_mm(rocker.ROD_HOLE_SPEC), _P), ("ROD_HOLE_SPEC", ("_hole_spec", "NUMBER_DRILL_MM"), ("_drawing_hole_callout", "add_native_hole_callout"))),
        "nominal_dia": (blind_cut_dia_mm(rocker.ROD_HOLE_SPEC), ("ROD_HOLE_SPEC", ("_hole_spec", "NUMBER_DRILL_MM"))),
        "thru": (rocker.ROD_HOLE_SPEC.end == "through_all", ("ROD_HOLE_SPEC", ("_drawing_hole_callout", "add_native_hole_callout"))),
        "position_dia": (float(rocker.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"]), ("GEOMETRIC_TOLERANCES_MM",)),
        "position_datums": (["A", "B", "C"], (("draw_ch_rocker_arm", "build"),)),
        "dimension_type": ("basic", (("draw_ch_rocker_arm", "build"),)),
    }, precision={"at": "unknown", "dia": _P, "position_dia": _P},
)
HUB_CENTER = (0.180, 0.095)
END_CENTER = (0.330, 0.110)
HUB_SCALE = (4.0, 1.0)
END_SCALE = (2.0, 1.0)
DETAIL_LETTER_XY = {"D": (0.167, 0.155), "E": (0.264, 0.148)}
# The rod-pin FCF lands on the southeast rim, clear of the acute land angle.
FCF_XY = (0.365, 0.090)
ROD_CALLOUT_XY = (0.270, 0.145)
# The iso caption's top-left, under the iso's right half and right of the end
# view. Beside the end view (0.315, 0.150) it read as that
# view's label, 0.4 mm from HubLength's "+0.05" (r743-p1s-B2 render).
ISO_CAPTION_XY = (0.325, 0.183)

# Re-express the part-owned one-sided height envelope as a normal profile zone:
# no second numeric tolerance lives in the drawing prose. The zero lower limit
# is pinned by the rocker contract; it is Ⓤ0 on the lower (inside-material) arc.
ARC_PROFILE_ZONE_MM = f"{TOP_EDGE_BAND[0]:g}"
ARC_PROFILE_OUTSIDE_MM = {
    "TopRadius": ARC_PROFILE_ZONE_MM,
    "BottomRadius": f"{TOP_EDGE_BAND[1]:g}",
}

# The two frames control one nominal concentric arc system. Their material
# sides differ: top outside is +Y, bottom inside is +Y. A single shared frame
# would put one of the zones on the wrong side of its basic arc.
ARC_PROFILE_FRAME_XY = {
    "TopRadius": (0.130, 0.207),
    "BottomRadius": (0.020, 0.160),
}
ARC_PROFILE_PICK_X_MM = {"TopRadius": -130.0, "BottomRadius": -110.0}
# Sheet-layout clearance, NOT a manufacturing tolerance. SIDE_SMART may put
# the native junction on either frame edge; prove its rebuilt route, not a
# junction inferred from the requested top-left or a fixed frame width.
ARC_PROFILE_TEXT_CLEARANCE_M = 0.001

# General notes. The linked block renders ~4.1 mm a line, so its 18 lines run
# ~75 mm. Anchored by its top at y 0.082, the last two ran past the bottom
# border into the zone band (r743-p1s-B2 render). The block is now seated from
# its MEASURED extent: rendered bottom NOTES_BORDER_CLEARANCE above the
# sheet's drawable region, left edge on NOTES_LEFT. A block that then reaches
# NOTES_CEILING, reserved below the front-view callouts, fails the build.
NOTES_LEFT = 0.020
NOTES_BORDER_CLEARANCE = 0.003
NOTES_CEILING = 0.110
NOTES_SEAT_PASSES = 3
NOTES_SEAT_SETTLE = 0.00005
# Below any note text height this sheet prints (the linked block pitches ~4.1).
NOTES_MIN_LINE_PITCH = 0.0025

# Tip-face midpoint (model mm): the top-arc endpoint pushed half the tip face
# outward along the end radius -- where datum C (clocking) attaches.
_TIP_FACE_MID_X = TOP_END_X + (TIP_FACE / 2.0) * (TOP_END_X / R_TOP)
_TIP_FACE_MID_Y = TOP_END_Y - (TIP_FACE / 2.0) * math.cos(TOP_ARC_LEN / 2.0 / R_TOP)
_ROD_TIP_Y = TOP_END_Y - TIP_FACE * math.cos(_ALPHA_TOP)
_BOT_END_Y = CENTER_Y - math.sqrt(R_BOTTOM**2 - BOT_END_X**2)

# Full witnesses connect the overall row to the actual physical tips.
OVERALL_WIDTH_TEXT_XY = (FRONT_CENTER[0], 0.215)
TAPER_INTERSECTION_TEXT_XY = (0.219, 0.132)
PIN_X_TEXT_XY = (0.219, 0.197)
PIN_Y_TEXT_XY = (0.267, 0.162)
LAND_ANGLE_TEXT_REACH = 0.032
LAND_ANGLE_WITNESS_LENGTH = 0.008
LAND_DATUM_STANDOFF = 0.014
STRAP_OFFSET_TEXT_XY = (RIGHT_CENTER[0] - 0.018, RIGHT_CENTER[1] + 0.030)
STRAP_OFFSET_WITNESS_LENGTH = 0.010


def _plane_between(
    start: tuple[float, float], end: tuple[float, float],
) -> PlanarFace:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    normal = (-dy / length, dx / length, 0.0)
    return PlanarFace(normal, normal[0] * start[0] + normal[1] * start[1])


def _rocker_points() -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    top = (rocker.TOP_END_X, rocker.TOP_END_Y)
    bottom = (rocker.BOT_END_X, rocker.CENTER_Y - math.sqrt(rocker.R_BOTTOM**2 - rocker.BOT_END_X**2))
    tip = (rocker.ROD_TIP_X, rocker.TOP_END_Y + rocker.TIP_FACE * (rocker.TOP_END_Y - rocker.CENTER_Y) / rocker.R_TOP)
    return top, tip, bottom


_TOP, _TIP, _BOTTOM = _rocker_points()
_RIGHT = (_plane_between(_TOP, _TIP), _plane_between(_TIP, _BOTTOM))
_TIPS = tuple(PlanarFace((-face.normal[0], face.normal[1], 0.0), face.offset_mm) for face in _RIGHT)
_LAND_ANGLE = math.degrees(math.acos(
    sum((_TIP[i] - _TOP[i]) * _RIGHT[0].normal[i] for i in (0, 1)) / rocker.TIP_FACE
))
_ANGULAR = float(_config.title_block("angular")["value_deg"])

for _name, _sign, _face in (("tip_land_pos_x", 1, _RIGHT[0]), ("tip_land_neg_x", -1, _TIPS[0])):
    requirement(
        _name, kind="face", faces=(_face,), requirements=("tip_land", "land_angle_deg"), fields={
            "tip_land": (_band(rocker.TIP_FACE, _P), ("TIP_FACE", ("ch_rocker_arm_notes", "DRAWING_NOTES"))),
            "land_angle_deg": ([round(_LAND_ANGLE, 0) - _ANGULAR, round(_LAND_ANGLE, 0) + _ANGULAR], ("TIP_FACE", "TOP_END_X", "TOP_END_Y", "ROD_TIP_X", "R_TOP", "CENTER_Y", ("ch_rocker_arm_notes", "DRAWING_NOTES"))),
            "land_angle_nominal_deg": (_LAND_ANGLE, ("TOP_END_X", "TOP_END_Y", "ROD_TIP_X", "TIP_FACE", "R_TOP", "CENTER_Y", ("ch_rocker_arm_notes", "DRAWING_NOTES"))),
            "radial_tip_end": ([_sign * _TIP[0], _TIP[1]], ("ROD_TIP_X", "TOP_END_Y", "TIP_FACE", "R_TOP", "CENTER_Y")),
            "top_edge_feature": ("top_edge", (("ch_rocker_arm_notes", "DRAWING_NOTES"),)),
            **({"datum": ("C", (("draw_ch_rocker_arm", "build"),))} if _sign == 1 else {}),
        }, precision={"tip_land": _P, "land_angle_deg": 0},
    )

part_metadata(datums={
    "C": ({"feature": "tip_land_pos_x", "surface": "rod-side (+X) radial tip land"}, (("draw_ch_rocker_arm", "build"),)),
})




def _project(adapter: Any, view: Any, points: Any, *, label: str) -> list[tuple[float, float]]:
    """Native geometry barrier precedes every detail-centre/attachment projection."""
    _early_bound(view, "IView").UpdateViewDisplayGeometry()  # VT_VOID
    projected = model_points_in_view(adapter, view, points, label=label)
    if (len(projected) != len(points)
            or any(len(xy) != 2 or not all(math.isfinite(v) for v in xy) for xy in projected)):
        raise RuntimeError(f"{label}: invalid native projected points: {projected!r}")
    return projected


def _outline(view: Any, *, label: str) -> tuple[float, float, float, float]:
    """Native view extent, which is not the detail's bare crop-circle box."""
    outline = tuple(float(v) for v in (_early_bound(view, "IView").GetOutline() or ()))
    if (len(outline) != 4 or not all(math.isfinite(v) for v in outline)
            or outline[0] >= outline[2] or outline[1] >= outline[3]):
        raise RuntimeError(f"{label} has invalid native outline: {outline!r}")
    return outline


_DETAIL_GEOMETRY_TOL_M = 0.00005
# R12 native caption air read 22.761 -> 3.221 -> 3.221 -> 2.745 mm:
# GetExtent moved by 0.476569 mm, one pixel at the logged 2.098 px/mm.
# Aim at 4 mm so that readback quantization cannot chase the 3 mm hard guard.
# Half the extra 1 mm permits one-pixel ink settling, not less required air.
_DETAIL_CAPTION_TARGET_AIR_M = 0.004
_DETAIL_CAPTION_SETTLE_M = (_DETAIL_CAPTION_TARGET_AIR_M - 0.003) / 2.0


def _detail_fence(label: str) -> tuple[tuple[float, float, float], float]:
    """Source model point/radius for a cosmetic, recipe-private detail fence."""
    if label == "D":
        return (0.0, PIVOT_MID_Y / 1000.0, 0.0), HUB_DIA / 2.0 + PIVOT_HOLE_DIA / 4.0
    if label != "E":
        raise RuntimeError(f"unknown rocker detail {label!r}")
    centre_mm = ((BOT_END_X + ROD_TIP_X) / 2.0, (_BOT_END_Y + TOP_END_Y) / 2.0)
    radius_mm = max(
        math.dist(centre_mm, point)
        for point in ((BOT_END_X, _BOT_END_Y), (ROD_TIP_X, _ROD_TIP_Y),
                      (TOP_END_X, TOP_END_Y))
    )
    radius_mm = max(
        radius_mm, math.dist(centre_mm, (ROD_HOLE_X, ROD_HOLE_Y)) + _ROD_HOLE_DIA / 2.0,
    ) + 0.5  # Cosmetic crop air, not a feature dimension.
    return (centre_mm[0] / 1000.0, centre_mm[1] / 1000.0, 0.0), radius_mm


def _view_scale_ratio(view: Any, *, label: str) -> tuple[float, float]:
    ratio = tuple(float(v) for v in (_early_bound(view, "IView").ScaleRatio or ()))
    if len(ratio) != 2 or not all(math.isfinite(v) and v > 0.0 for v in ratio):
        raise RuntimeError(f"{label}: invalid native ScaleRatio={ratio!r}")
    return ratio


def _native_circle_geometry(circle: Any, *, label: str) -> tuple[tuple[float, float, float], float]:
    segment = _early_bound(circle, "ISketchSegment")
    if segment is None or int(segment.GetType()) != 1:  # swSketchARC
        raise RuntimeError(f"{label}: native fence is not a sketch arc")
    arc = _early_bound(circle, "ISketchArc")
    if int(arc.IsCircle()) != 1:  # INT 1/0, not VT_BOOL
        raise RuntimeError(f"{label}: native fence is not a complete circle")
    point = _early_bound(arc.GetCenterPoint2(), "ISketchPoint")
    if point is None:
        raise RuntimeError(f"{label}: native circle has no centre point")
    centre = (float(point.X), float(point.Y), float(point.Z))
    radius = float(arc.GetRadius())
    if not all(math.isfinite(v) for v in (*centre, radius)) or radius <= 0.0:
        raise RuntimeError(f"{label}: invalid native circle centre={centre}, radius={radius!r}")
    return centre, radius


def _detail_crop(adapter: Any, view: Any, *, label: str) -> tuple[float, float, float, float]:
    """Read the persisted circle, reversing the exact drawing-sketch mapping.

    GetOutline is a native VIEW bbox (e.g. R10 D was 75.736 mm); it does not
    promise the 53.8 mm crop circle. No measured/guessed padding is subtracted.
    """
    view = _early_bound(view, "IView")
    bbox = _outline(view, label=f"detail {label} view bbox")
    _telemetry.info(f"detail {label}: native_view_bbox={bbox} (view extent, not crop)")
    parent = _early_bound(view.GetBaseView(), "IView")
    detail_circle = _early_bound(view.GetDetail(), "IDetailCircle")
    if parent is None or detail_circle is None:
        raise RuntimeError(f"detail {label}: missing native parent or persisted detail circle")
    actual_flags = (detail_circle.GetLabel(), int(detail_circle.GetDisplay()),
                    detail_circle.NoOutline, detail_circle.JaggedOutline, detail_circle.HasFullOutline())
    if actual_flags != (label, 1, False, False, True):
        raise RuntimeError(f"detail {label}: actual circle label/display/outline flags={actual_flags!r}, "
                           f"required={(label, 1, False, False, True)!r}, native_view_bbox={bbox}")
    profiles = tuple(detail_circle.GetProfileItems() or ())
    if len(profiles) != 1:
        raise RuntimeError(f"detail {label}: expected one persisted circle profile, got {len(profiles)}")
    raw_centre, raw_radius = _native_circle_geometry(profiles[0], label=f"detail {label} persisted profile")
    sketch = _early_bound(_early_bound(profiles[0], "ISketchSegment").GetSketch(), "ISketch")
    if sketch is None:
        raise RuntimeError(f"detail {label}: persisted circle has no native sketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    if transform is None:
        raise RuntimeError(f"detail {label}: persisted circle has no native sketch transform")
    matrix = tuple(float(v) for v in (transform.ArrayData or ()))
    if len(matrix) != 16 or not all(math.isfinite(v) for v in matrix):
        raise RuntimeError(f"detail {label}: invalid native sketch transform={matrix!r}")
    # Use the documented automation method (DISPID 9), not IInverse (DISPID
    # 10): the R11 native IDispatch call rejected IInverse as write-only.
    inverse = _early_bound(transform.Inverse(), "IMathTransform")
    if inverse is None:
        raise RuntimeError(f"detail {label}: native sketch transform cannot be inverted")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    if utility is None:
        raise RuntimeError(f"detail {label}: missing native math utility for profile readback")
    sheet_points = []
    # Creation maps SHEET -> drawing sketch. Its inverse already returns sheet
    # points; applying parent.ModelToViewTransform here would double-project.
    for xyz in (raw_centre,
                (raw_centre[0] + raw_radius, raw_centre[1], raw_centre[2]),
                (raw_centre[0], raw_centre[1] + raw_radius, raw_centre[2])):
        point = _early_bound(utility.CreatePoint(double_array(list(xyz))), "IMathPoint")
        if point is None:
            raise RuntimeError(f"detail {label}: cannot create native profile point")
        projected = _early_bound(point.MultiplyTransform(inverse), "IMathPoint")
        if projected is None:
            raise RuntimeError(f"detail {label}: cannot reverse native sketch mapping")
        coordinates = tuple(float(v) for v in (projected.ArrayData or ()))
        if len(coordinates) != 3 or not all(math.isfinite(v) for v in coordinates):
            raise RuntimeError(f"detail {label}: invalid inverse-mapped circle point={coordinates!r}")
        if abs(coordinates[2]) > _DETAIL_GEOMETRY_TOL_M:
            raise RuntimeError(f"detail {label}: inverse-mapped circle point={coordinates!r}, required_sheet_z=0, "
                               f"geometry_tolerance_m={_DETAIL_GEOMETRY_TOL_M}, raw_sketch_centre={raw_centre}, "
                               f"raw_sketch_radius={raw_radius}, sketch_transform={matrix}, native_view_bbox={bbox}")
        sheet_points.append(coordinates[:2])
    parent_centre, rim_x, rim_y = sheet_points
    parent_radius = math.dist(parent_centre, rim_x)
    radius_y = math.dist(parent_centre, rim_y)
    centre, radius_mm = _detail_fence(label)
    parent_ratio = _view_scale_ratio(parent, label=f"detail {label} parent")
    parent_scale = parent_ratio[0] / parent_ratio[1]
    expected_parent_radius = radius_mm / 1000.0 * parent_scale
    expected_parent_centre, projected_rim = _project(
        adapter, parent, (centre, (centre[0] + radius_mm / 1000.0, centre[1], centre[2])),
        label=f"detail {label} independent parent fence",
    )
    projected_radius = math.dist(expected_parent_centre, projected_rim)
    context = (f"detail {label}: raw_sketch_centre={raw_centre}, raw_sketch_radius={raw_radius}, "
               f"sketch_transform={matrix}, inverse_parent_sheet_centre={parent_centre}, "
               f"required_parent_sheet_centre={expected_parent_centre}, "
               f"actual_parent_sheet_radius_mm={parent_radius * 1000.0:.6f}, radius_y_mm={radius_y * 1000.0:.6f}, "
               f"projected_parent_radius_mm={projected_radius * 1000.0:.6f}, "
               f"required_parent_radius_mm={expected_parent_radius * 1000.0:.6f}, parent_scale={parent_ratio}, "
               f"geometry_tolerance_mm={_DETAIL_GEOMETRY_TOL_M * 1000.0:.6f}, native_view_bbox={bbox}")
    _telemetry.info(context)
    if (math.dist(parent_centre, expected_parent_centre) > _DETAIL_GEOMETRY_TOL_M
            or abs(parent_radius - expected_parent_radius) > _DETAIL_GEOMETRY_TOL_M
            or abs(projected_radius - expected_parent_radius) > _DETAIL_GEOMETRY_TOL_M
            or abs(radius_y - parent_radius) > _DETAIL_GEOMETRY_TOL_M):
        raise RuntimeError(f"{context}: persisted native circle geometry/frame/parent scale mismatch")
    ratio = _view_scale_ratio(view, label=f"detail {label}")
    expected_ratio = {"D": HUB_SCALE, "E": END_SCALE}[label]
    scale = ratio[0] / ratio[1]
    if (not math.isclose(scale, expected_ratio[0] / expected_ratio[1], abs_tol=1e-10)
            or view.UseParentScale is not False or int(view.UseSheetScale) != 0):
        raise RuntimeError(f"{context}: native detail scale/independence changed: {ratio!r}")
    (physical,) = _project(adapter, view, (centre,), label=f"detail {label} actual physical centre")
    magnification = scale / parent_scale
    crop_centre = tuple(physical[i] + (parent_centre[i] - expected_parent_centre[i]) * magnification
                        for i in range(2))
    radius = parent_radius * magnification
    crop = (crop_centre[0] - radius, crop_centre[1] - radius,
            crop_centre[0] + radius, crop_centre[1] + radius)
    _telemetry.info(f"{context}, actual_detail_projected_centre={physical}, native_detail_scale={ratio}, "
                    f"actual_crop_box={crop}, native_view_bbox={bbox}")
    return crop


def _create_detail(
    adapter: Any, parent: Any, *, centre: tuple[float, float, float],
    radius_mm: float, target: tuple[float, float], scale: tuple[float, float], label: str,
) -> Any:
    """Rocker-private cone-gear-shaft native circle/barrier/settling pattern."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(parent, "IView")
    if drawing.ActivateView(view_name(adapter, parent)) is not True:
        raise RuntimeError(f"detail {label}: cannot activate parent")
    draw.ClearSelection2(True)
    rim = (centre[0] + radius_mm / 1000.0, centre[1], centre[2])
    sheet_points = _project(adapter, parent, (centre, rim), label=f"detail {label} fence")
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    if sketch is None:
        raise RuntimeError(f"detail {label}: parent has no native drawing sketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    if transform is None or utility is None:
        raise RuntimeError(f"detail {label}: missing native sketch transform or math utility")
    mapped = []
    for x, y in sheet_points:
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        if point is None:
            raise RuntimeError(f"detail {label}: cannot create native fence point")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        if projected is None:
            raise RuntimeError(f"detail {label}: cannot map native fence point to sketch")
        coordinates = tuple(float(v) for v in (projected.ArrayData or ()))
        if len(coordinates) != 3 or not all(math.isfinite(v) for v in coordinates):
            raise RuntimeError(f"detail {label}: invalid native sketch fence point={coordinates!r}")
        mapped.append(coordinates)
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        circle = manager.CreateCircle(*mapped[0], *mapped[1])
    finally:
        manager.AddToDB = previous
    if circle is None:
        raise RuntimeError(f"detail {label}: native fence creation failed")
    actual_centre, actual_radius = _native_circle_geometry(circle, label=f"detail {label} created fence")
    asked_radius = math.dist(mapped[0], mapped[1])
    parent_ratio = _view_scale_ratio(parent, label=f"detail {label} parent")
    parent_radius = radius_mm / 1000.0 * parent_ratio[0] / parent_ratio[1]
    projected_radius = math.dist(*sheet_points)
    if parent_radius <= 0.0 or asked_radius <= 0.0:
        raise RuntimeError(f"detail {label}: invalid requested native fence radius")
    tolerance = _DETAIL_GEOMETRY_TOL_M * asked_radius / parent_radius
    context = (f"detail {label} created fence: requested_sketch_centre={mapped[0]}, "
               f"actual_sketch_centre={actual_centre}, requested_sketch_radius={asked_radius}, "
               f"actual_sketch_radius={actual_radius}, geometry_tolerance_sketch_units={tolerance}, "
               f"projected_parent_sheet_radius={projected_radius}, required_parent_sheet_radius={parent_radius}, "
               f"native_parent_scale={parent_ratio}")
    _telemetry.info(context)
    if (math.dist(actual_centre, mapped[0]) > tolerance
            or abs(actual_radius - asked_radius) > tolerance
            or abs(projected_radius - parent_radius) > _DETAIL_GEOMETRY_TOL_M):
        raise RuntimeError(f"{context}: created native circle geometry or parent projection scale mismatch")
    selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
    data = _early_bound(selection.CreateSelectData(), "ISelectData")
    data.View = parent
    if _early_bound(circle, "ISketchSegment").Select4(False, data) is not True:
        raise RuntimeError(f"detail {label}: cannot select parent fence")
    native = drawing.CreateDetailViewAt4(
        *target, 0.0, 0, *scale, label, 1, True, False, False, 5,
    )
    draw.ClearSelection2(True)
    if native is None:
        raise RuntimeError(f"detail {label}: CreateDetailViewAt4 returned no view")
    detail = _early_bound(native, "IView")
    detail.UseParentScale = False
    detail.UseSheetScale = 0
    detail.ScaleRatio = double_array(list(scale))
    set_hidden_lines_removed(adapter, detail)
    rebuild_drawing(adapter, label=f"create detail {label}")
    base = detail.GetBaseView()
    if base is None or int(adapter.swApp.IsSame(base, parent)) != 1:
        raise RuntimeError(f"detail {label}: native parent link is not the front")
    for attempt in range(4):
        ratio = _view_scale_ratio(detail, label=f"detail {label}")
        if (not math.isclose(ratio[0] / ratio[1], scale[0] / scale[1], abs_tol=1e-10)
                or detail.UseParentScale is not False or int(detail.UseSheetScale) != 0):
            raise RuntimeError(f"detail {label}: native scale is {ratio}, not {scale}")
        crop = _detail_crop(adapter, detail, label=label)
        outline = _outline(detail, label=f"detail {label} view bbox")
        landed = ((crop[0] + crop[2]) / 2.0, (crop[1] + crop[3]) / 2.0)
        (physical,) = _project(adapter, detail, (centre,), label=f"detail {label} centre {attempt}")
        _telemetry.info(f"detail {label}: pass={attempt}, native_view_bbox={outline}, actual_crop={crop}, physical_centre={physical}, scale={ratio}")
        if math.dist(physical, target) <= _DETAIL_GEOMETRY_TOL_M:
            if math.dist(landed, target) > _DETAIL_GEOMETRY_TOL_M:
                raise RuntimeError(f"detail {label}: settled physical centre={physical} but actual crop centre={landed}, "
                                   f"required_centre={target}, tolerance_m={_DETAIL_GEOMETRY_TOL_M}, "
                                   f"actual_crop={crop}, native_view_bbox={outline}")
            break
        anchor = tuple(float(v) for v in (detail.Position or ()))
        if len(anchor) != 2 or not all(math.isfinite(v) for v in anchor):
            raise RuntimeError(f"detail {label}: invalid Position={anchor!r}")
        move = [anchor[i] + target[i] - physical[i] for i in range(2)]
        if detail.SetViewPosition(double_array(move), False) is not True:
            raise RuntimeError(f"detail {label}: native position refused")
        rebuild_drawing(adapter, label=f"settle detail {label}")
    else:
        raise RuntimeError(f"detail {label}: unsettled native crop/physical centre: view_bbox={outline}, crop={crop}, projected={physical}, target={target}")
    return detail


def _place_detail_letters(adapter: Any, front: Any) -> None:
    circles = tuple(_early_bound(front, "IView").GetDetailCircles() or ())
    labels = [_early_bound(circle, "IDetailCircle").GetLabel() for circle in circles]
    if len(circles) != 2 or sorted(labels) != ["D", "E"]:
        raise RuntimeError(f"rocker requires exactly D/E native parent circles, got {labels!r}")
    for label, xy in DETAIL_LETTER_XY.items():
        circle = _early_bound(circles[labels.index(label)], "IDetailCircle")
        circle.SetLabelPosition(*xy)  # VT_VOID; getter returns two out doubles
        rebuild_drawing(adapter, label=f"place detail {label} parent letter")
        actual = tuple(float(v) for v in circle.GetLabelPosition())
        if len(actual) != 2 or not all(math.isfinite(v) for v in actual) or math.dist(actual, xy) > 1e-8:
            raise RuntimeError(f"detail {label}: native letter stayed at {actual!r}, requested {xy}")


def _pin_sheet_scale(adapter: Any, sheet: Any) -> None:
    sheet = _early_bound(sheet, "ISheet")
    if sheet.SetScale(*SHEET_SCALE, False, False) is not True:
        raise RuntimeError("cannot pin rocker sheet scale before native captions")
    properties = tuple(float(v) for v in (sheet.GetProperties2() or ()))
    if len(properties) < 4 or tuple(properties[2:4]) != SHEET_SCALE:
        raise RuntimeError(f"rocker sheet scale did not persist: {properties!r}")


def _title_block_top(adapter: Any, sheet: Any) -> float:
    """Read the actual template's top rule; registry coordinates identify its span."""
    sketch = _early_bound(_early_bound(sheet, "ISheet").GetTemplateSketch(), "ISketch")
    if sketch is None:
        raise RuntimeError("detail E: cannot read native title-block sketch")
    template = DRAWING_TEMPLATES[SPEC.layout]
    tops = []
    for raw in sketch.GetSketchSegments() or ():
        segment = _early_bound(raw, "ISketchSegment")
        if int(segment.GetType()) != 0:  # swSketchLINE
            continue
        line = _early_bound(raw, "ISketchLine")
        a = _early_bound(line.GetStartPoint2(), "ISketchPoint")
        b = _early_bound(line.GetEndPoint2(), "ISketchPoint")
        if a is None or b is None:
            raise RuntimeError("detail E: native title-block rule endpoint unavailable")
        values = (float(a.X), float(a.Y), float(b.X), float(b.Y))
        if not all(math.isfinite(v) for v in values):
            raise RuntimeError("detail E: invalid native title-block rule")
        x0, x1 = sorted((values[0], values[2]))
        if (abs(values[1] - values[3]) < 1e-8
                and abs(x0 - template.title_block_left_m) < 0.001
                and x1 > template.width_m - 0.020
                and 0.0 < values[1] < NOTES_CEILING):
            tops.append(values[1])
    if not tops:
        raise RuntimeError("detail E: native title-block top rule could not be measured")
    return max(tops)


def _record_detail_caption(adapter: Any, view: Any, sheet: Any, *, label: str, stage: str) -> None:
    """Read-only R14 probe; decoder boxes are estimates, NEVER a guard fallback.

    GetExtent documents a note box, not individual printed glyph bounds. Keep
    its native six coordinates separate from DisplayData's native fragments
    and the existing layout decoder's estimated text boxes until a failure
    sheet shows what actually printed. Refused reads remain explicit errors.
    """
    report: dict[str, Any] = {"label": label, "stage": stage}
    reader = _Reader(adapter)
    try:
        bound_view = reader.bind(view, "IView")
        raw_notes = reader.call(lambda: bound_view.GetNotes())
        notes = tuple(raw_notes or ())
        report["native_note_count"] = (
            len(notes) if not {"GetNotes", "bind IView"}.intersection(reader.errors) else None
        )
        report["native_title_rule_top_m"] = reader.need(lambda: _title_block_top(adapter, sheet))
        report["notes"] = []
        for raw_note in notes:
            note = reader.bind(raw_note, "INote")
            text = reader.need(lambda: note.GetText())
            lines = (text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
                     if type(text) is str and text else [] if text == "" else None)
            entry: dict[str, Any] = {
                "native_property_linked_text": reader.need(lambda: note.PropertyLinkedText),
                "native_get_text": text,
                "resolved_lines": lines,
                "resolved_line_count": len(lines) if lines is not None else None,
                "native_note_get_extent": reader.need(lambda: note.GetExtent()),
                "native_note_get_height": reader.need(lambda: note.GetHeight()),
                "native_note_get_height_in_points": reader.need(lambda: note.GetHeightInPoints()),
                "native_has_multiple_fonts": reader.need(lambda: note.HasMultipleFonts),
            }
            report["notes"].append(entry)
            annotation = reader.bind(reader.need(lambda: note.GetAnnotation()), "IAnnotation")
            count = reader.need(lambda: annotation.GetTextFormatCount())
            entry["native_text_format_count"] = count
            formats = []
            entry["native_text_formats"] = formats
            for index in range(count if type(count) is int and count >= 0 else 0):
                text_format = reader.bind(
                    reader.need(lambda i=index: annotation.GetTextFormat(i)), "ITextFormat"
                )
                formats.append({
                    "index": index,
                    "use_doc_text_format": reader.need(lambda i=index: annotation.GetUseDocTextFormat(i)),
                    "char_height_m": reader.need(lambda: text_format.CharHeight),
                    "char_height_pts": reader.need(lambda: text_format.CharHeightInPts),
                    "is_height_specified_in_pts": reader.need(lambda: text_format.IsHeightSpecifiedInPts()),
                    "type_face_name": reader.need(lambda: text_format.TypeFaceName),
                    "line_spacing": reader.need(lambda: text_format.LineSpacing),
                })
            data = reader.need(lambda: annotation.GetDisplayData())
            before_display = dict(reader.errors)
            display = _dump_display(reader, data)
            # Font/spacing are optional to the shared audit, but native fields
            # in THIS probe must not turn a None answer into "" or zero.
            bound_data = reader.bind(data, "IDisplayData")
            for index, fragment in enumerate(display.get("texts", [])):
                fragment["font"] = reader.need(lambda i=index: bound_data.GetTextFontAtIndex(i))
                fragment["ls"] = reader.need(lambda i=index: bound_data.GetTextLineSpacingAtIndex(i))
            display_errors = {
                name: count - before_display.get(name, 0)
                for name, count in reader.errors.items() if count > before_display.get(name, 0)
            }
            # The shared tolerant reader uses audit defaults after a refusal.
            # Do not present those defaults as native observations in this probe.
            refused_fields = {
                "GetTextAtIndex": "t", "GetTextPositionAtIndex": "pos",
                "GetTextHeightAtIndex": "h", "GetTextRefPositionAtIndex": "ref",
                "GetTextAngleAtIndex": "ang", "GetTextFontAtIndex": "font",
                "GetTextLineSpacingAtIndex": "ls",
            }
            fragments = display.get("texts", [])
            for accessor, field in refused_fields.items():
                if accessor in display_errors:
                    for fragment in fragments:
                        fragment[field] = None
            entry["native_display_data"] = display
            entry["native_display_read_errors"] = display_errors
            entry["display_fragment_count"] = (
                len(fragments) if data is not None and not {
                    "GetTextCount", "bind IDisplayData"
                }.intersection(display_errors) else None
            )
            entry["native_display_fragment_positions"] = [fragment["pos"] for fragment in fragments]
            entry["native_display_position_basis"] = "offsets from DisplayData origin per API; not measured sheet glyph bounds"
            # Deliberately omit note.GetExtent from the decoder input: otherwise
            # the free-note branch would just echo it as an "exact" text box.
            record = {"type": 6, "name": f"detail {label} caption", "display": display}
            advance = calibrate_sheet_advance((record,)) if not display_errors else None
            geometry = (annotation_geometry(record, owner=f"detail {label}", advance=advance)
                        if advance is not None else None)
            boxes = list(geometry.text_boxes) if geometry is not None else []
            estimated = union_boxes(boxes)
            entry["display_decoder_estimate"] = {
                "coordinate_basis": "existing decoder interpretation of native DisplayData; not printed glyph ink",
                "advance_ratio": advance,
                "text_boxes_m": [(box.xmin, box.ymin, box.xmax, box.ymax) for box in boxes],
                "extent_m": ((estimated.xmin, estimated.ymin, estimated.xmax, estimated.ymax)
                             if estimated is not None else None),
            }
    except Exception as exc:  # noqa: BLE001 - instrumentation cannot replace the guard
        report["diagnostic_error"] = f"{type(exc).__name__}: {exc}"
    report["native_read_errors"] = reader.take_errors()
    with contextlib.suppress(Exception):
        _telemetry.info(f"detail {label} caption native diagnostics: {json.dumps(report, default=str, sort_keys=True)}")

# The shared DisplayData audit records heights to 0.1 um. Permit that native
# numeric quantization, not a pixel-sized or point-sized font mismatch.
_NOTE_HEIGHT_READBACK_TOL_M = 1e-7
_CAPTION_FIELDS = ("<VLNAME>", "<VLLABEL>", "<VLSCALE>", "<VLSCALEV>")


def _caption_fields(note: Any, *, label: str) -> tuple[str, ...]:
    linked = note.PropertyLinkedText
    if type(linked) is not str:
        raise RuntimeError(f"detail {label}: unavailable native caption links")
    fields = tuple(re.findall(r"<VL[^>]*>", linked))
    if fields != _CAPTION_FIELDS:
        raise RuntimeError(f"detail {label}: native caption field identities/order/counts={fields!r}")
    return fields


def _native_note_fragments(note: Any, *, label: str) -> tuple[tuple[str, float, str], ...]:
    """Strict native text/height/font reads, never tolerant decoder defaults."""
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError(f"{label}: missing native annotation")
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    if data is None:
        raise RuntimeError(f"{label}: missing native DisplayData")
    count = data.GetTextCount()
    if type(count) is not int or count <= 0:
        raise RuntimeError(f"{label}: missing/invalid native text fragment count={count!r}")
    fragments = []
    for index in range(count):
        text = data.GetTextAtIndex(index)
        height = data.GetTextHeightAtIndex(index)
        font = data.GetTextFontAtIndex(index)
        if (type(text) is not str or type(height) not in (float, int)
                or not math.isfinite(height) or height <= 0.0
                or type(font) is not str or not font):
            raise RuntimeError(f"{label}: invalid native fragment {index}: {(text, height, font)!r}")
        fragments.append((text, float(height), font))
    if not any(text.strip() for text, _height, _font in fragments):
        raise RuntimeError(f"{label}: native DisplayData has no displayed text fragments")
    return tuple(fragments)


def _native_font_authority(text_format: Any, use_doc: Any, *, label: str) -> dict[str, Any]:
    if text_format is None or type(use_doc) is not bool:
        raise RuntimeError(f"{label}: missing native font/format authority")
    text_format = _early_bound(text_format, "ITextFormat")
    in_points = text_format.IsHeightSpecifiedInPts()
    if type(in_points) is not bool:
        raise RuntimeError(f"{label}: unavailable native height authority={in_points!r}")
    return {
        "use_doc": use_doc, "is_height_specified_in_pts": in_points,
        "char_height_m": text_format.CharHeight,
        "char_height_pts": text_format.CharHeightInPts,
        "font": text_format.TypeFaceName,
    }


def _ordinary_note_height(adapter: Any, note: Any) -> float:
    """Source this sheet's normal size from its existing Manufacturing Notes."""
    adapter.currentModel.GraphicsRedraw2()  # VT_VOID; native reads carry signal.
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError("Manufacturing Notes: missing native annotation")
    authority = _native_font_authority(
        annotation.GetTextFormat(0), annotation.GetUseDocTextFormat(0),
        label="Manufacturing Notes",
    )
    fragments = _native_note_fragments(note, label="Manufacturing Notes")
    height = fragments[0][1]
    _telemetry.info(
        f"Manufacturing Notes native height source: font_authority={authority!r}, "
        f"display_fragments={fragments!r}, source=IDisplayData.GetTextHeightAtIndex"
    )
    if (any(abs(actual - height) > _NOTE_HEIGHT_READBACK_TOL_M
            for _text, actual, _font in fragments)
            or len({font for _text, _height, font in fragments}) != 1):
        raise RuntimeError(f"Manufacturing Notes: mixed native source fragments={fragments!r}")
    # GetTextFormat can describe inherited rich text, not these native fragments.
    return height


def _caption_view_state(adapter: Any, view: Any, front: Any, *, label: str) -> tuple[Any, ...]:
    parent = view.GetBaseView()
    if parent is None or int(adapter.swApp.IsSame(parent, front)) != 1:
        raise RuntimeError(f"detail {label}: native caption view lost front ownership")
    position = tuple(float(value) for value in (view.Position or ()))
    if len(position) != 2 or not all(math.isfinite(value) for value in position):
        raise RuntimeError(f"detail {label}: invalid native view position={position!r}")
    return (position, _view_scale_ratio(view, label=f"detail {label} caption style"),
            view.UseParentScale, view.UseSheetScale)


def _normalize_detail_caption(
    adapter: Any, view: Any, front: Any, height: float, *, label: str,
) -> None:
    view = _early_bound(view, "IView")
    notes = tuple(view.GetNotes() or ())
    if len(notes) != 1:
        raise RuntimeError(f"detail {label}: expected one native caption, got {len(notes)}")
    note = _early_bound(notes[0], "INote")
    fields = _caption_fields(note, label=label)
    before_view = _caption_view_state(adapter, view, front, label=label)
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError(f"detail {label}: missing native caption annotation")
    before = _native_note_fragments(note, label=f"detail {label} caption before reset")
    set_note_text_height(note, height, label=f"detail {label} caption", remove_rich_text=True)
    if _caption_fields(note, label=label) != fields:
        raise RuntimeError(f"detail {label}: native caption lost fields during rich-text reset")
    rebuild_drawing(adapter, label=f"normalize detail {label} caption font")
    adapter.currentModel.GraphicsRedraw2()
    after = _native_note_fragments(note, label=f"detail {label} caption after reset")
    read_notes = tuple(view.GetNotes() or ())
    if (len(read_notes) != 1 or read_notes[0] is None
            or int(adapter.swApp.IsSame(read_notes[0], note)) != 1
            or _caption_view_state(adapter, view, front, label=label) != before_view):
        raise RuntimeError(f"detail {label}: native caption/view ownership or position changed during font reset")
    if _caption_fields(note, label=label) != fields:
        raise RuntimeError(f"detail {label}: native caption lost fields after rebuild")
    # Rich-text removal can merge runs; compare the actual native run content,
    # not GetText (which returns spaces/newlines for view fields on the seat).
    before_text = re.sub(r"\s+", "", "".join(text for text, _height, _font in before))
    after_text = re.sub(r"\s+", "", "".join(text for text, _height, _font in after))
    if (after_text != before_text or note.HasMultipleFonts is not False
            or annotation.GetUseDocTextFormat(0) is not False
            or len({font for _text, _height, font in after}) != 1
            or any(abs(actual - height) > _NOTE_HEIGHT_READBACK_TOL_M
                   for _text, actual, _font in after)):
        raise RuntimeError(f"detail {label}: native caption font/content readback mismatch: source_height_m={height}, before={before!r}, after={after!r}")
    _telemetry.info(f"detail {label}: native caption font normalized from Manufacturing Notes: source_height_m={height}, fields={fields!r}, native_fragments={after!r}")


def _normalize_detail_circle(
    adapter: Any, front: Any, view: Any, height: float, *, label: str,
) -> None:
    front = _early_bound(front, "IView")
    circles = tuple(front.GetDetailCircles() or ())
    bound = [_early_bound(circle, "IDetailCircle") for circle in circles]
    labels = [circle.GetLabel() for circle in bound]
    if len(bound) != 2 or sorted(labels) != ["D", "E"]:
        raise RuntimeError(f"detail {label}: expected exactly D/E native source circles, got {labels!r}")
    circle = bound[labels.index(label)]
    position = tuple(float(value) for value in circle.GetLabelPosition())
    if len(position) != 2 or not all(math.isfinite(value) for value in position):
        raise RuntimeError(f"detail {label}: invalid source-circle label position={position!r}")
    for owner, expected in ((circle.GetView(), front), (circle.GetDetailView(), view)):
        if owner is None or int(adapter.swApp.IsSame(owner, expected)) != 1:
            raise RuntimeError(f"detail {label}: native source-circle ownership mismatch")
    text_format = _early_bound(circle.GetTextFormat(), "ITextFormat")
    before = _native_font_authority(text_format, circle.GetUseDocTextFormat(), label=f"detail {label} circle")
    # Both labels take the same sheet-sourced size, including a changed normal
    # note size. This is local to the existing native circles, never a doc pref.
    text_format.CharHeight = height
    if circle.SetTextFormat(False, text_format) is not True:
        raise RuntimeError(f"detail {label}: native source-circle font setter refused")
    rebuild_drawing(adapter, label=f"normalize detail {label} source-circle font")
    adapter.currentModel.GraphicsRedraw2()
    after = _native_font_authority(
        circle.GetTextFormat(), circle.GetUseDocTextFormat(), label=f"detail {label} circle readback",
    )
    if (after["use_doc"] is not False or after["is_height_specified_in_pts"] is not False
            or type(after["char_height_m"]) not in (int, float)
            or not math.isfinite(after["char_height_m"])
            or abs(after["char_height_m"] - height) > _NOTE_HEIGHT_READBACK_TOL_M):
        raise RuntimeError(f"detail {label}: native source-circle format/height mismatch: source_height_m={height}, before={before!r}, after={after!r}")
    if circle.GetLabel() != label or tuple(circle.GetLabelPosition()) != position:
        raise RuntimeError(f"detail {label}: source-circle label/position changed during font normalization")
    for owner, expected in ((circle.GetView(), front), (circle.GetDetailView(), view)):
        if owner is None or int(adapter.swApp.IsSame(owner, expected)) != 1:
            raise RuntimeError(f"detail {label}: source-circle ownership changed during font normalization")
    _telemetry.info(f"detail {label}: native source-circle font normalized: source_height_m={height}, before={before!r}, after={after!r}, label_position={position!r}")


def _require_detail_circle_display_heights(front: Any, height: float) -> None:
    """Prove both native displayed heights after BOTH circles are normalized."""
    # GetDetailCircleInfo2 textPt is not promised to equal GetLabelPosition.
    # Every entry must have the same sourced height, so no anchor/order join
    # is needed. Keep the complete flat-record/arrow validation before decoding.
    front = _early_bound(front, "IView")
    info = front.GetDetailCircleInfo2()
    if (type(info) not in (tuple, list) or not info or info[0] != 2
            or any(type(value) not in (float, int) or not math.isfinite(value) for value in info)):
        raise RuntimeError(f"detail D/E: invalid native circle display data={info!r}")
    index = 1
    for _number in range(2):
        if index + 16 > len(info):
            raise RuntimeError(f"detail D/E: truncated native circle display data={info!r}")
        arrows = info[index + 15]
        if arrows < 0 or arrows != int(arrows):
            raise RuntimeError(f"detail D/E: invalid native circle arrow count={arrows!r}")
        index += 16 + int(arrows) * 9
    if index != len(info):
        raise RuntimeError(f"detail D/E: malformed native circle display data={info!r}")
    decoded = _detail_circles(info)
    if len(decoded) != 2:
        raise RuntimeError(f"detail D/E: expected exactly two native circle display-height readbacks={decoded!r}")
    heights = tuple(entry[4][0] for entry in decoded)
    if any(not math.isfinite(actual) or abs(actual - height) > _NOTE_HEIGHT_READBACK_TOL_M
           for actual in heights):
        raise RuntimeError(f"detail D/E: native circle displayed-height mismatch: actual_heights_m={heights!r}, source_height_m={height}")
    _telemetry.info(f"detail D/E: native source-circle displayed heights verified after both font writes: source_height_m={height}, displayed_heights_m={heights!r}")


def _capture_caption_failure(adapter: Any, label: str, exc: Exception) -> None:
    """Capture while the seat is open; never replace the original refusal."""
    try:
        _seat_forensics.capture_com_failure(
            adapter, f"{PART_STEM}-detail-{label}-caption", str(exc),
            api="rocker native caption guard", exception=exc, sheet_png=True,
            detail_label=label,
        )
    except Exception as capture_exc:  # noqa: BLE001 - always retain the original guard
        if capture_exc is not exc:
            with contextlib.suppress(Exception):
                _telemetry.warn(f"detail {label} caption secondary capture failure: {capture_exc!r}")


def _normalize_detail_caption_styles(
    adapter: Any, front: Any, hub: Any, end: Any, source_note: Any,
) -> None:
    """Normalize BOTH linked captions/parent letters before seating diagnostics."""
    label = "styles"
    try:
        height = _ordinary_note_height(adapter, source_note)
        for label, view in (("D", hub), ("E", end)):
            _normalize_detail_caption(adapter, view, front, height, label=label)
            _normalize_detail_circle(adapter, front, view, height, label=label)
        label = "styles"
        _require_detail_circle_display_heights(front, height)
    except Exception as exc:
        _capture_caption_failure(adapter, label, exc)
        raise



def _seat_detail_caption(adapter: Any, view: Any, sheet: Any, *, label: str) -> None:
    """Seat the native note box; any refusal preserves the active failed sheet."""
    try:
        _record_detail_caption(adapter, view, sheet, label=label, stage="before guards")
        _pin_sheet_scale(adapter, sheet)
        notes = tuple(_early_bound(view, "IView").GetNotes() or ())
        if len(notes) != 1:
            raise RuntimeError(f"detail {label}: expected one native caption, got {len(notes)}")
        note = _early_bound(notes[0], "INote")
        linked = note.PropertyLinkedText
        if type(linked) is not str or not linked:
            raise RuntimeError(f"detail {label}: caption has no native linked fields")
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        crop = _detail_crop(adapter, view, label=label)
        ceiling = crop[1] - 0.003
        lower_boundary = (_title_block_top(adapter, sheet) if label == "E"
                          else float(_early_bound(sheet, "ISheet").GetZoneMargin(1)))
        floor = lower_boundary + 0.003
        slot = (f"detail {label}: native_crop={crop}, native_lower_boundary_m={lower_boundary!r}, "
                f"native_title_rule_top_m={lower_boundary if label == 'E' else None!r}, "
                f"floor_m={floor!r}, ceiling_m={ceiling!r}, slot_height_mm={(ceiling - floor) * 1000.0:.6f}, "
                "required_air_mm=3.000")
        _telemetry.info(slot)
        if not math.isfinite(floor) or floor >= ceiling:
            raise RuntimeError(f"{slot}: invalid native caption slot")
        for attempt in range(4):
            _record_detail_caption(adapter, view, sheet, label=label, stage=f"placement {attempt}")
            box = _note_extent(adapter, note, label=f"detail {label} caption")
            context = (f"{slot}, native_caption_get_extent_box={box}, "
                       f"actual_crop_air_mm={(crop[1] - box[3]) * 1000.0:.3f}, "
                       f"actual_lower_air_mm={(box[1] - lower_boundary) * 1000.0:.3f}")
            _telemetry.info(context)
            if box[3] - box[1] > ceiling - floor:
                raise RuntimeError(f"{context}: actual caption cannot fit between crop and lower boundary")
            error = ((crop[0] + crop[2] - box[0] - box[2]) / 2.0,
                     crop[1] - _DETAIL_CAPTION_TARGET_AIR_M - box[3])
            if max(abs(v) for v in error) <= _DETAIL_CAPTION_SETTLE_M:
                break
            position = tuple(float(v) for v in (annotation.GetPosition() or ()))
            if len(position) != 3 or not all(math.isfinite(v) for v in position):
                raise RuntimeError(f"detail {label}: invalid native caption position")
            if annotation.SetPosition2(position[0] + error[0], position[1] + error[1], position[2]) is not True:
                raise RuntimeError(f"detail {label}: native caption placement refused")
            rebuild_drawing(adapter, label=f"seat detail {label} caption {attempt}")
        else:
            raise RuntimeError(f"{context}: caption ink did not settle")
        if note.PropertyLinkedText != linked or box[1] < floor - 1e-9 or box[3] > ceiling + 1e-9:
            raise RuntimeError(f"{context}: native caption lost links or required air")
        if label == "D" and box[2] > DRAWING_TEMPLATES[SPEC.layout].title_block_left_m - 0.003:
            air = DRAWING_TEMPLATES[SPEC.layout].title_block_left_m - box[2]
            raise RuntimeError(f"{context}: caption must stay left of title block: actual_horizontal_air_mm={air * 1000.0:.3f}, required_air_mm=3.000")
        _telemetry.info(f"detail {label} caption native GetExtent box={box}, crop={crop}, lower_limit={floor}")
    except Exception as exc:
        _capture_caption_failure(adapter, label, exc)
        raise


def _require_dimension_census(adapter: Any, views: Any) -> None:
    marked = set().union(*DRAWING_DIMENSIONS.values())
    total = []
    for label, view, keep in views:
        names = [dimension_name(adapter, ann)
                 for ann in (_early_bound(view, "IView").GetAnnotations() or ())]
        names = [name for name in names if name in marked]
        _telemetry.info(f"rocker {label} native marked-dimension census={names!r}")
        if sorted(names) != sorted(keep):
            raise RuntimeError(f"rocker {label}: native dimension owners {names!r}, expected {sorted(keep)!r}")
        total.extend(names)
    if len(total) != len(marked) or set(total) != marked:
        raise RuntimeError(f"rocker native marked-dimension union is not exact: {total!r}")




# Detail D makes the two concentric rims distinguishable at their actual 4:1
# projection. A coordinate pick must still resolve to the diameter-picked bore.
PIVOT_DATUM_STANDOFF = 0.020
PIVOT_DATUM_ANGLE = math.radians(135.0)
PIVOT_PICK_FRACTIONS = (1.0, 0.6)

PIVOT_BORE = requirement(
    "pivot_bore", kind="hole", faces=(CylinderFace(rocker.PIVOT_HOLE_DIA),),
    requirements=("dia", "thru", "finish_ra", "process"), fields={
        "at": _CENTRE, "axis": _AXIS,
        "dia": (_band(rocker.PIVOT_HOLE_DIA, _P, rocker.PIVOT_HOLE_BAND), ("PIVOT_HOLE_DIA", "PIVOT_HOLE_BAND")),
        "nominal_dia": (rocker.PIVOT_HOLE_DIA, ("PIVOT_HOLE_DIA",)),
        "thru": (True, (("ch_rocker_arm_notes", "DRAWING_NOTES"),)),
        "finish_ra": (_surface_finish.MACHINED_UM, ("SURFACE_FINISHES",)),
        "process": ("ream", (("ch_rocker_arm_notes", "DRAWING_NOTES"),)), "datum": ("A", (("draw_ch_rocker_arm", "build"),)),
    }, precision={"dia": _P, "finish_ra": 1},
)

part_metadata(
    frames={
        name: ({"origin": [0.0, rocker.PIVOT_MID_Y, sign * rocker.HUB_LENGTH / 2], "x": [1.0, 0.0, 0.0], "y": [0.0, float(sign), 0.0], "z": [0.0, 0.0, float(sign)], "binding": "unknown"}, ("PIVOT_MID_Y", "HUB_LENGTH"))
        for name, sign in (("A", 1), ("B", -1))
    },
    datums={"A": ({"feature": "pivot_bore", "surface": "pivot bore cylinder"}, (("draw_ch_rocker_arm", "build"),))},
)


def _assert_pivot_precision(
    adapter: Any, drawing_model: Any, annotations: list[Any]
) -> None:
    """Read PivotDia's effective primary precision without rewriting its import."""
    expected = PIVOT_BORE.precision["dia"]
    for annotation in annotations:
        annotation = adapter._attempt(
            lambda a=annotation: _early_bound(a, "IAnnotation")
        )
        name = adapter._attempt(lambda a=annotation: dimension_name(adapter, a))
        if type(name) is not str or not name:
            raise RuntimeError(
                f"PivotDia precision: expected {expected}; unreadable dimension name"
            )
        if name != "PivotDia":
            continue
        display = adapter._attempt(
            lambda a=annotation: _early_bound(
                a.GetSpecificAnnotation(), "IDisplayDimension"
            )
        )
        primary = adapter._attempt(lambda d=display: d.GetPrimaryPrecision2())
        if type(primary) is not int:
            raise RuntimeError(
                f"PivotDia precision: expected {expected}; "
                f"unreadable primary precision {primary!r}"
            )
        effective = primary
        # swDimensionPrecisionSettings_e.swPrecisionFollowsDocumentSetting = -2.
        if primary == -2:
            extension = adapter._attempt(
                lambda: _early_bound(
                    _early_bound(drawing_model, "IModelDoc2").Extension,
                    "IModelDocExtension",
                )
            )
            # swconst R2026x: swDetailingLinearDimPrecision = 24;
            # swDetailingDiameterDimension = 204. Units decimals are not this getter.
            effective = adapter._attempt(
                lambda: extension.GetUserPreferenceInteger(24, 204)
            )
        if type(effective) is not int or effective < 0:
            raise RuntimeError(
                f"PivotDia precision: expected {expected}; "
                f"unreadable effective precision {effective!r} (primary {primary})"
            )
        if effective != expected:
            raise RuntimeError(
                f"PivotDia precision: expected {expected}; "
                f"effective {effective} decimal places (primary {primary})"
            )
        return
    raise RuntimeError(
        f"PivotDia precision: expected {expected}; missing dimension, "
        "effective precision unreadable"
    )


def _pivot_datum_request(centre: tuple[float, float], radius: float) -> tuple[float, float]:
    """Detail-space junction on the upper-left ray, using its projected bore."""
    reach = radius + PIVOT_DATUM_STANDOFF
    return (
        centre[0] + reach * math.cos(PIVOT_DATUM_ANGLE),
        centre[1] + reach * math.sin(PIVOT_DATUM_ANGLE),
    )


def _pick_pivot_bore(
    adapter: Any, view: Any, bore_edge: Any, centre: tuple[float, float], radius: float,
) -> tuple[float, float]:
    """Return a detail-space point whose EDGE pick resolves to the bore."""
    results = []
    for fraction in PIVOT_PICK_FRACTIONS:
        radius_at_pick = radius * fraction
        xy = (
            centre[0] + radius_at_pick * math.cos(PIVOT_DATUM_ANGLE),
            centre[1] + radius_at_pick * math.sin(PIVOT_DATUM_ANGLE),
        )
        try:
            picked = _select_view_entity(
                adapter, view, "EDGE", xy, label="pivot bore datum pick"
            )
        except RuntimeError as error:
            results.append((fraction, str(error)))
            _telemetry.event("datum.bore_pick", fraction=fraction, same=-2)
            continue
        same = int(adapter.swApp.IsSame(picked, bore_edge))
        results.append((fraction, same))
        _telemetry.event("datum.bore_pick", fraction=fraction, same=same)
        adapter.currentModel.ClearSelection2(True)
        if same == 1:
            return xy
    raise RuntimeError(
        "no pick on datum A's ray resolves to the O6.5 pivot bore "
        f"(fraction of bore radius, IsSame or error): {results!r}"
    )


def _require_datum_on_bore(app: Any, tag: Any, bore_edge: Any) -> None:
    """Raise unless datum A is attached to the pivot bore edge alone."""
    annotation = _early_bound(tag.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError("datum A has no native annotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    if len(attached) != 1 or attached[0] is None:
        raise RuntimeError(
            f"datum A needs one attached edge, has {len(attached)}: {attached!r}"
        )
    # swObjectSame = 1; different (0) and unknown (-1) both fail.
    if int(app.IsSame(attached[0], bore_edge)) != 1:
        raise RuntimeError(
            "datum A is attached to an edge other than the O6.5 pivot bore "
            "(r743-4D: the concentric O10 hub)"
        )
    if annotation.IsDangling():
        raise RuntimeError("datum A is dangling")


# Bore finish in D's lower-right quadrant; never either hub end face.
PIVOT_FINISH_ANGLE = math.radians(-45.0)
PIVOT_FINISH_OFFSET = (0.012, -0.013)
PIVOT_FINISH_CHAR_HEIGHT = 0.0025


def _pivot_finish_placement(
    adapter: Any, hub: Any,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Project the real bore rim through D's native transform."""
    radius = PIVOT_HOLE_DIA / 2.0
    (rim,) = _project(
        adapter, hub,
        [(radius * math.cos(PIVOT_FINISH_ANGLE) / 1000.0,
          (PIVOT_MID_Y + radius * math.sin(PIVOT_FINISH_ANGLE)) / 1000.0, 0.0)],
        label="detail D bore finish rim",
    )
    return rim, (rim[0] + PIVOT_FINISH_OFFSET[0], rim[1] + PIVOT_FINISH_OFFSET[1])


# Every marked model dimension has exactly one face-view owner.
FRONT_KEEP = {
    "TopRadius": (0.145, 0.136),
    "BottomRadius": (0.170, 0.128),
    "TopAbovePivot": (0.165, 0.191),
}

_TOP_P = rocker_notes.DRAWING_PRECISION["TopEdgeReference"]["TopAbovePivot"]
TOP_EDGE = requirement(
    "top_edge", kind="profile", faces=(CylinderFace(2 * rocker.R_TOP),),
    requirements=("height_above_pivot", "radius", "profile_zone", "arc_len"), fields={
        "height_above_pivot": (rocker.TOP_EDGE_ABOVE_PIVOT, ("TOP_EDGE_ABOVE_PIVOT", ("draw_ch_rocker_arm", "_basic_profile_dimensions"))),
        "height_from": ("pivot_bore", (("draw_ch_rocker_arm", "build"),)),
        "radius": (rocker.R_TOP, ("R_TOP", ("draw_ch_rocker_arm", "_basic_profile_dimensions"))), "radius_nominal": (rocker.R_TOP, ("R_TOP",)),
        "dimension_type": ("basic", (("draw_ch_rocker_arm", "_basic_profile_dimensions"),)),
        "profile_zone": (float(ARC_PROFILE_ZONE_MM), (("ch_rocker_arm_notes", "ARC_PROFILE_ZONE_MM"),)),
        "outside_disposition": (float(ARC_PROFILE_OUTSIDE_MM["TopRadius"]), (("ch_rocker_arm_notes", "ARC_PROFILE_OUTSIDE_MM"),)),
        "profile_datums": (["A", "B", "C"], (("draw_ch_rocker_arm", "_add_arc_profiles"),)),
        "arc_len": (_band(rocker.TOP_ARC_LEN, _P), ("TOP_ARC_LEN", ("ch_rocker_arm_notes", "DRAWING_NOTES"))),
        "arc_centre": ([0.0, rocker.CENTER_Y, 0.0], ("CENTER_Y",)),
        "centre_from_pivot_ref": (rocker.CENTER_Y - rocker.PIVOT_MID_Y, ("CENTER_Y", "PIVOT_MID_Y", ("ch_rocker_arm_notes", "DRAWING_NOTES"))),
        "end": (list(_TOP), ("TOP_END_X", "TOP_END_Y")),
    }, precision={"height_above_pivot": _TOP_P, "radius": _P, "arc_len": _P},
)
PROFILE_OUTER = requirement(
    "profile_outer", kind="profile", faces=(CylinderFace(2 * rocker.R_BOTTOM), _RIGHT[1], _TIPS[1]),
    requirements=("bottom_radius", "profile_zone", "bottom_arc_len", "mirror_symmetric"), fields={
        "bottom_radius": (rocker.R_BOTTOM, ("R_BOTTOM", ("draw_ch_rocker_arm", "_basic_profile_dimensions"))),
        "bottom_radius_nominal": (rocker.R_BOTTOM, ("R_BOTTOM",)),
        "dimension_type": ("basic", (("draw_ch_rocker_arm", "_basic_profile_dimensions"),)),
        "profile_zone": (float(ARC_PROFILE_ZONE_MM), (("ch_rocker_arm_notes", "ARC_PROFILE_ZONE_MM"),)),
        "outside_disposition": (float(ARC_PROFILE_OUTSIDE_MM["BottomRadius"]), (("ch_rocker_arm_notes", "ARC_PROFILE_OUTSIDE_MM"),)),
        "profile_datums": (["A", "B", "C"], (("draw_ch_rocker_arm", "_add_arc_profiles"),)),
        "arc_centre": ([0.0, rocker.CENTER_Y, 0.0], ("CENTER_Y",)), "top_edge_feature": ("top_edge", (("ch_rocker_arm_notes", "DRAWING_NOTES"),)),
        "bottom_arc_len": (_band(rocker.BOT_ARC_LEN, _P), ("BOT_ARC_LEN", ("ch_rocker_arm_notes", "DRAWING_NOTES"))),
        "mirror_symmetric": (True, (("ch_rocker_arm_notes", "DRAWING_NOTES"),)), "depth_ref": (rocker.ARM_DEPTH, ("ARM_DEPTH", ("ch_rocker_arm_notes", "DRAWING_NOTES"))),
        "bottom_end": (list(_BOTTOM), ("BOT_END_X", "R_BOTTOM", "CENTER_Y")),
        "radial_tip_end": (list(_TIP), ("ROD_TIP_X", "TOP_END_Y", "TIP_FACE", "R_TOP", "CENTER_Y")),
    }, precision={"bottom_radius": _P, "bottom_arc_len": _P},
)
HUB_OD = requirement(
    "hub_od", kind="boss", faces=(CylinderFace(rocker.HUB_DIA),),
    requirements=("dia", "coaxiality_dia"), fields={
        "at": _CENTRE, "axis": _AXIS,
        "dia": (_band(rocker.HUB_DIA, _P), ("HUB_DIA",)),
        "dia_nominal": (rocker.HUB_DIA, ("HUB_DIA",)),
        "coaxiality_dia": (rocker.HUB_COAXIALITY_DIA, ("HUB_COAXIALITY_DIA", ("ch_rocker_arm_notes", "DRAWING_NOTES"))),
        "coaxial_to": ("pivot_bore", (("ch_rocker_arm_notes", "DRAWING_NOTES"),)),
    }, precision={"dia": _P, "coaxiality_dia": _P},
)
HUB_KEEP = {
    "PivotDia": (0.120, 0.086),
    "HubDia": (0.210, 0.122),
}
END_KEEP = {"RodTipLen": (0.377, 0.130)}
# The hub length (+0.05/0, #743 PR2) under the end view, where the hub shows
# its full length (the end view is 1:1, centred on the pivot mid-depth).
# The strap thickness (+/-0.025, ARM_THICKNESS_BAND, Main ruling 2026-10
# option b) right of the end view, its line across the strap ABOVE the hub
# and 3 mm above datum B's attachment (broad_face, RIGHT_CENTER y + 0.007),
# so its outside arrows clear datum B's down-left leader; the text sits under
# the iso caption (top y 0.183) and right of the end view.
STRAP_THICKNESS_TEXT_XY = (RIGHT_CENTER[0] + 0.017, RIGHT_CENTER[1] + 0.010)
RIGHT_KEEP: dict[str, tuple[float, float]] = {
    "HubLength": (RIGHT_CENTER[0], RIGHT_CENTER[1] - (PIVOT_MID_Y + 12.0) / 1000.0),
    "StrapThickness": STRAP_THICKNESS_TEXT_XY,
}

_HUB_P = rocker_notes.DRAWING_PRECISION["Hub"]["HubLength"]
_STRAP_P = rocker_notes.DRAWING_PRECISION["Strap"]["StrapThickness"]
_STRAP_BAND = (_band(rocker.ARM_THICKNESS, _STRAP_P, rocker.ARM_THICKNESS_BAND), ("ARM_THICKNESS", "ARM_THICKNESS_BAND"))
HUB_FACES = requirement(
    "hub_faces", kind="face",
    faces=tuple(PlanarFace((0, 0, sign), rocker.HUB_LENGTH / 2) for sign in (-1, 1)),
    requirements=("length",), fields={
        "length": (_band(rocker.HUB_LENGTH, _HUB_P, rocker.HUB_LENGTH_BAND), ("HUB_LENGTH", "HUB_LENGTH_BAND")),
        "length_nominal": (rocker.HUB_LENGTH, ("HUB_LENGTH",)),
        "upper_z": (rocker.HUB_LENGTH / 2, ("HUB_LENGTH",)),
        "lower_z": (-rocker.HUB_LENGTH / 2, ("HUB_LENGTH",)),
    }, precision={"length": _HUB_P},
)
STRAP_FACES = requirement(
    "strap_faces", kind="face", faces=(PlanarFace((0, 0, -1), rocker.ARM_THICKNESS / 2),),
    requirements=("thickness",), fields={
        "thickness": _STRAP_BAND,
        "thickness_nominal": (rocker.ARM_THICKNESS, ("ARM_THICKNESS",)),
        "upper_z": (rocker.ARM_THICKNESS / 2, ("ARM_THICKNESS",)),
        "lower_z": (-rocker.ARM_THICKNESS / 2, ("ARM_THICKNESS",)),
    }, precision={"thickness": _STRAP_P},
)
STRAP_DATUM_B = requirement(
    "strap_datum_b", kind="face", faces=(PlanarFace((0, 0, 1), rocker.ARM_THICKNESS / 2),),
    requirements=("thickness",), fields={
        "thickness": _STRAP_BAND,
        "thickness_nominal": (rocker.ARM_THICKNESS, ("ARM_THICKNESS",)),
        "plane": ({"frame": "model", "axis": "z", "value": rocker.ARM_THICKNESS / 2}, ("ARM_THICKNESS",)),
        "datum": ("B", (("draw_ch_rocker_arm", "build"),)),
    }, precision={"thickness": _STRAP_P},
)
part_metadata(datums={
    "B": ({"feature": "strap_datum_b", "surface": "+Z broad strap face"}, (("draw_ch_rocker_arm", "build"),)),
})
TOP_KEEP: dict[str, tuple[float, float]] = {}
BASIC_PROFILE_DIMENSIONS = {"TopRadius", "BottomRadius", "TopAbovePivot"}


def _basic_profile_dimensions(adapter: Any, annotations: list[Any]) -> None:
    """Make the imported profile nominals BASIC without saving the source part."""
    remaining = set(BASIC_PROFILE_DIMENSIONS)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        set_basic_dimension(adapter, display, label=f"arc-system {name}")
        if name in ARC_PROFILE_OUTSIDE_MM:
            # Dress exterior radius callouts with the pinion-arbor and
            # arbor-pedestal leader pattern. The text must also be outside
            # its parent circle: these flags alone did not remove the centre
            # line when the R800 text was inside that circle.
            display.ShortenedRadius = False
            display.ArcExtensionLineOrOppositeSide = False
            display.ArrowSide = 1  # swDimArrowsOutside
            display.SolidLeader = False
            if (
                bool(display.ShortenedRadius)
                or bool(display.ArcExtensionLineOrOppositeSide)
                or int(display.ArrowSide) != 1
                or bool(display.SolidLeader)
            ):
                raise RuntimeError(f"{name} retained its centre-directed radius leader")
        remaining.remove(name)
    if remaining:
        raise RuntimeError(f"arc-system BASIC dimensions missing: {sorted(remaining)}")


def _dress_detail_dimensions(
    adapter: Any, annotations: list[Any], *, keep: dict[str, tuple[float, float]],
) -> None:
    """Read D/E imported sizes; preserve the native pivot size and ream band."""
    expected = {"RodTipLen": TIP_FACE, "HubDia": HUB_DIA, "PivotDia": PIVOT_HOLE_DIA}
    remaining = {name: expected[name] for name in keep}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        assert_dimension_measures(
            adapter, display, expected_mm=remaining.pop(name), label=f"imported {name}"
        )
        if name == "RodTipLen":
            continue
        # Single exterior arrows, not diametral lines through both concentric
        # circles: otherwise the new hub OD and pivot bore leaders intersect.
        display.ArrowSide = 1  # swDimArrowsOutside
        display.SetSecondArrow(False, False)
        display.SolidLeader = False
        if (
            int(display.ArrowSide) != 1
            or display.GetUseDocSecondArrow()
            or display.GetSecondArrow()
            or display.SolidLeader
        ):
            raise RuntimeError(f"{name} retained a centre-crossing diameter leader")
        if name != "PivotDia":
            continue
        model_dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(model_dimension.Tolerance, "IDimensionTolerance")
        band = (float(tolerance.GetMaxValue()), float(tolerance.GetMinValue()))
        if not all(math.isfinite(value) for value in band) or any(
            abs(actual - expected / 1000.0) > 1e-9
            for actual, expected in zip(band, PIVOT_HOLE_BAND)
        ):
            raise RuntimeError(f"pivot bore lost its part-owned ream tolerance: {band}")
        tolerance_type = int(model_dimension.GetToleranceType())
        prefix = str(display.GetText(5) or "")  # native prefix definition
        suffix = str(display.GetText(6) or "")  # native suffix definition
        callouts = (str(display.GetText(7) or ""), str(display.GetText(8) or ""))
        # A custom prefix replaces the automatic diameter glyph, so retain its
        # native symbol token when the original prefix compartment is empty.
        ream_prefix = "REAM " + (prefix if prefix else "<MOD-DIAM>")
        through_suffix = suffix.rstrip() + " THRU"
        display.SetText(1, ream_prefix)
        display.SetText(2, through_suffix)
        if (
            str(display.GetText(5) or "") != ream_prefix
            or str(display.GetText(6) or "") != through_suffix
            or (str(display.GetText(7) or ""), str(display.GetText(8) or "")) != callouts
            or not display.ShowDimensionValue
            or int(model_dimension.GetToleranceType()) != tolerance_type
            or (float(tolerance.GetMaxValue()), float(tolerance.GetMinValue())) != band
        ):
            raise RuntimeError("pivot ream/through text did not preserve its native dimension")
    if remaining:
        raise RuntimeError(f"detail source dimensions missing: {sorted(remaining)}")
    if any(dimension_name(adapter, ann) == "HubDia" for ann in annotations):
        assert_imported_precision(
            adapter, annotations, {"HubDia": DEFAULT_DRAWING_PRECISION}
        )


def _require_native_angle(
    display: Any, *, expected_degrees: float, label: str
) -> float:
    """Read native radians, never a formatted text value or a supplementary guess."""
    if display is None:
        raise RuntimeError(f"{label} has no native angular display dimension")
    display = _early_bound(display, "IDisplayDimension")
    if display.Type2 != 3:  # swAngularDimension
        raise RuntimeError(f"{label} is not a native angular dimension")
    native_dimension = display.GetDimension2(0)
    if native_dimension is None:
        raise RuntimeError(f"{label} has no native model dimension")
    dimension = _early_bound(native_dimension, "IDimension")
    value = dimension.SystemValue
    if value is None:
        raise RuntimeError(f"{label} has no measured native angle")
    radians = abs(float(value))
    expected = math.radians(expected_degrees)
    if not math.isfinite(radians) or abs(radians - expected) > 1e-8:
        raise RuntimeError(
            f"{label} measures {math.degrees(radians):g} degrees, "
            f"expected {expected_degrees:g} degrees"
        )
    return math.degrees(radians)


def _land_vertical(adapter: Any, view: Any, points: list[tuple[float, float]]) -> Any:
    """A short view-owned vertical ray through F, parallel to the mirror plane.

    The upper endpoint has the CAD land's top height; no model dimension or
    nominal is introduced. Map sheet points into the active view sketch as in
    draw_dt_cone_tip_block._add_adjuster_axis, never feed raw sheet coordinates
    to a view-owned CreateCenterLine.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    view = _early_bound(view, "IView")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the land-angle detail view")
    draw.ClearSelection2(True)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    if sketch is None:
        raise RuntimeError("land-angle detail has no native drawing sketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    mapped = []
    for x, y in points:
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        mapped.append(
            tuple(_early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData)
        )
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    old_add_to_db = bool(manager.AddToDB)
    old_display = bool(manager.DisplayWhenAdded)
    manager.AddToDB = True
    manager.DisplayWhenAdded = True
    try:
        centerline = manager.CreateCenterLine(*mapped[0], *mapped[1])
    finally:
        manager.AddToDB = old_add_to_db
        manager.DisplayWhenAdded = old_display
    if centerline is None:
        raise RuntimeError("failed to create the detail-view land angle ray")
    segment = _early_bound(centerline, "ISketchSegment")
    segment.Color = 0
    if int(segment.Color) != 0:
        raise RuntimeError("land angle centreline colour did not persist")
    draw.ClearSelection2(True)
    return segment


def _add_land_angle(adapter: Any, view: Any, land: ViewEdge) -> Any:
    """Measure the CAD radial land against a local parallel to the mirror plane.

    Use the outer endpoint F, not the top-arc endpoint T: the upward acute
    sector at F is outside the material. The actual mirror-axis line intersects
    this land at the off-sheet R800 parent centre, so it is not a usable witness.
    """
    outer, upper = sorted(land.line, key=lambda point: point[0], reverse=True)
    outer_xy, upper_xy = _project(
        adapter, view, [tuple(v / 1000.0 for v in point) for point in (outer, upper)],
        label="rod land angular endpoints",
    )
    vertical_end = (outer_xy[0], upper_xy[1])
    vertical = _land_vertical(adapter, view, [outer_xy, vertical_end])
    dx, dy = upper_xy[0] - outer_xy[0], upper_xy[1] - outer_xy[1]
    length = math.hypot(dx, dy)
    bisector = (dx / length, dy / length + 1.0)
    reach = LAND_ANGLE_TEXT_REACH / math.hypot(*bisector)
    text_xy = (
        outer_xy[0] + bisector[0] * reach,
        outer_xy[1] + bisector[1] * reach,
    )
    display = add_edge_dimension(
        adapter, view,
        p0=((outer_xy[0] + upper_xy[0]) / 2.0, (outer_xy[1] + upper_xy[1]) / 2.0),
        p1=((outer_xy[0] + vertical_end[0]) / 2.0, (outer_xy[1] + vertical_end[1]) / 2.0),
        text_xy=text_xy, label="radial land angle to mirror axis",
        orientation="angular", entities=(land.edge, vertical),
        entity_types=("EDGE", "SKETCHSEGMENT"),
    )
    display = _early_bound(display, "IDisplayDimension")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError("land angle has no native annotation")
    attached = list(annotation.GetAttachedEntities3() or ())
    if (
        len(attached) != 2
        or any(actual is None for actual in attached)
        or annotation.IsDangling()
        or not all(
            any(int(adapter.swApp.IsSame(actual, entity)) == 1 for actual in attached)
            for entity in (land.edge, vertical)
        )
    ):
        raise RuntimeError("land angle is not attached to its exact land and local vertical")
    set_basic_dimension(adapter, display, label="radial land angle")
    if int(_early_bound(display.GetDimension2(0), "IDimension").GetToleranceType()) != 1:
        raise RuntimeError("radial land angle did not retain BASIC tolerance")
    _require_native_angle(
        display, expected_degrees=math.degrees(_ALPHA_TOP), label="radial land angle"
    )
    display.MaxWitnessLineLength = LAND_ANGLE_WITNESS_LENGTH
    if abs(float(display.MaxWitnessLineLength) - LAND_ANGLE_WITNESS_LENGTH) > 1e-9:
        raise RuntimeError("land angle retained crossing full-height witnesses")
    display.SetText(4, "TO MIRROR PLANE")
    if str(display.GetText(4) or "") != "TO MIRROR PLANE":
        raise RuntimeError("land angle direction callout did not persist")
    return display


def _add_rocker_outline_dimensions(adapter: Any, front: Any) -> None:
    """Import profile nominals and measure the remaining actual CAD outline."""
    annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _basic_profile_dimensions(adapter, annotations)
    edges = scan_view_edges(front, label="rocker front outline")
    width_points = (
        (-ROD_TIP_X, _ROD_TIP_Y, ARM_THICKNESS / 2.0),
        (ROD_TIP_X, _ROD_TIP_Y, ARM_THICKNESS / 2.0),
    )
    vertices = tuple(
        edges.exact_vertex_at(point, label=f"overall width tip {index}")
        for index, point in enumerate(width_points)
    )
    width_xy = model_points_in_view(
        adapter, front, [tuple(v / 1000.0 for v in point) for point in width_points],
        label="overall width vertices",
    )
    width = add_edge_dimension(
        adapter, front, p0=width_xy[0], p1=width_xy[1],
        text_xy=OVERALL_WIDTH_TEXT_XY, label="rocker overall width",
        orientation="horizontal", entities=vertices, entity_types=("VERTEX", "VERTEX"),
    )
    assert_dimension_measures(
        adapter, width, expected_mm=2.0 * ROD_TIP_X, label="rocker overall width",
        entities=vertices, entity_types=("VERTEX", "VERTEX"),
    )
    pivot = visible_circle_edge(adapter, front, PIVOT_HOLE_DIA)
    taper_point = (BOT_END_X, _BOT_END_Y, ARM_THICKNESS / 2.0)
    taper = edges.exact_vertex_at(taper_point, label="+Z taper/lower-arc intersection")
    taper_xy, pivot_xy = model_points_in_view(
        adapter, front,
        [tuple(v / 1000.0 for v in taper_point), (0.0, PIVOT_MID_Y / 1000.0, 0.0)],
        label="taper intersection and pivot mirror axis",
    )
    taper_dimension = add_edge_dimension(
        adapter, front, p0=pivot_xy, p1=taper_xy,
        text_xy=TAPER_INTERSECTION_TEXT_XY, label="taper intersection X",
        orientation="horizontal", entities=(pivot, taper),
        entity_types=("EDGE", "VERTEX"),
    )
    set_arc_endpoints_to_center(adapter, taper_dimension, label="taper mirror-axis origin")
    assert_dimension_measures(
        adapter, taper_dimension, expected_mm=BOT_END_X, label="taper intersection X",
        entities=(pivot, taper), entity_types=("EDGE", "VERTEX"),
    )
    taper_dimension = _early_bound(taper_dimension, "IDisplayDimension")
    taper_dimension.SetText(4, "R816/TAPER")
    if str(taper_dimension.GetText(4) or "") != "R816/TAPER":
        raise RuntimeError("taper endpoint identity label did not persist")


def _add_pin_coordinates(adapter: Any, front: Any) -> None:
    """Two centred native circular endpoints locate the pin from physical A."""
    pivot_bore_edge = visible_circle_edge(adapter, front, PIVOT_HOLE_DIA)
    rod_hole_edge = visible_circle_edge(adapter, front, _ROD_HOLE_DIA)
    pivot_xy, rod_xy = _project(
        adapter, front,
        ((0.0, PIVOT_MID_Y / 1000.0, 0.0),
         (ROD_HOLE_X / 1000.0, ROD_HOLE_Y / 1000.0, 0.0)),
        label="physical A and rod-pin axes",
    )
    for axis, orientation, expected, text_xy in (
        ("X", "horizontal", ROD_HOLE_X, PIN_X_TEXT_XY),
        ("Y", "vertical", ROD_HOLE_Y - PIVOT_MID_Y, PIN_Y_TEXT_XY),
    ):
        label = f"rod-pin {axis} location"
        dimension = add_edge_dimension(
            adapter, front, p0=pivot_xy, p1=rod_xy, text_xy=text_xy,
            label=label, orientation=orientation, entities=(pivot_bore_edge, rod_hole_edge),
        )
        set_arc_endpoints_to_center(adapter, dimension, label=label)
        model = _early_bound(_early_bound(dimension, "IDisplayDimension").GetDimension2(0), "IDimension")
        if any(int(model.GetArcEndCondition(index)) != 1 for index in (1, 2)):
            raise RuntimeError(f"{label}: both physical bore endpoints must be centred")
        assert_dimension_measures(
            adapter, dimension, expected_mm=expected, label=label,
            entities=(pivot_bore_edge, rod_hole_edge),
        )
        set_basic_dimension(adapter, dimension, label=label)
        display = _early_bound(dimension, "IDisplayDimension")
        display.SetText(4, "PIN AXIS")
        if str(display.GetText(4) or "") != "PIN AXIS":
            raise RuntimeError(f"{label}: native PIN AXIS label did not persist")


def _require_rod_through_callout(callout: Any) -> None:
    """Read actual Hole Wizard ink, not unsupported GetText compartments."""
    display = _early_bound(callout, "IDisplayDimension")
    data = _early_bound(display.GetDisplayData(), "IDisplayData")
    if data is None:
        raise RuntimeError("detail E rod-pin callout has no native rendered display data")
    count = data.GetTextCount()
    if type(count) is not int or count <= 0:
        raise RuntimeError(f"detail E rod-pin callout has invalid native rendered text count: {count!r}")
    texts = tuple(data.GetTextAtIndex(index) for index in range(count))
    if any(type(text) is not str for text in texts):
        raise RuntimeError(f"detail E rod-pin callout has unreadable native rendered text: {texts!r}")
    native_text = " ".join(texts)
    _telemetry.info(f"detail E rod-pin callout: actual_native_rendered_text={native_text!r}, required='THRU'")
    if "THRU" not in native_text.upper():
        raise RuntimeError(f"detail E rod-pin callout lost its native through condition: {native_text!r}")


def _require_ream_clearance(
    adapter: Any, hub: Any, notes_box: tuple[float, float, float, float],
) -> None:
    """Prove actual native REAM text clears D and the seated notes by 1 mm."""
    reader = _Reader(adapter)
    annotations = tuple(_early_bound(hub, "IView").GetAnnotations() or ())
    matches = [ann for ann in annotations if dimension_name(adapter, ann) == "PivotDia"]
    if len(matches) != 1:
        raise RuntimeError("detail D: expected one native pivot REAM dimension")
    record = _dump_annotation(reader, matches[0])
    errors = reader.take_errors()
    if record is None or errors:
        raise RuntimeError(f"detail D: cannot measure native REAM text: {errors!r}")
    geometry = _arc_callout_geometry(record, calibrate_sheet_advance([record]))
    crop = Box(*_detail_crop(adapter, hub, label="D"))
    notes = Box(*notes_box)
    for box in geometry.text_boxes:
        for label, obstacle in (("D crop", crop), ("seated notes", notes)):
            gap = _box_air(box, obstacle)
            detail = f"detail D REAM: requested_xy_mm={tuple(v * 1000.0 for v in HUB_KEEP['PivotDia'])}, actual_GetPosition={record.get('pos')}, text_ink={box.format_mm()}, obstacle={label}:{obstacle.format_mm()}, actual_air_mm={gap * 1000.0:.3f}, required_air_mm=1.000"
            _telemetry.info(detail)
            if gap < 0.001 - 1e-12:
                raise RuntimeError(detail)


def _box_air(box: Box, obstacle: Box) -> float:
    return math.hypot(
        max(obstacle.xmin - box.xmax, box.xmin - obstacle.xmax, 0.0),
        max(obstacle.ymin - box.ymax, box.ymin - obstacle.ymax, 0.0),
    )


def _require_front_detail_air(adapter: Any, front: Any, hub: Any, end: Any) -> None:
    """Every actual front-callout text box clears both settled detail crops."""
    reader = _Reader(adapter)
    records = [_dump_annotation(reader, ann)
               for ann in (_early_bound(front, "IView").GetAnnotations() or ())]
    errors = reader.take_errors()
    if not records or any(record is None for record in records) or errors:
        raise RuntimeError(f"front/detail text air cannot be measured: {errors!r}")
    advance = calibrate_sheet_advance(records)
    obstacles = (("D", Box(*_detail_crop(adapter, hub, label="D"))),
                 ("E", Box(*_detail_crop(adapter, end, label="E"))))
    for record in records:
        if record.get("visible") in (2, 3) or record.get("type") in (13, 15):
            continue
        geometry = _arc_callout_geometry(record, advance)
        for box in geometry.text_boxes:
            for label, obstacle in obstacles:
                air = _box_air(box, obstacle)
                detail = f"front {record.get('name')!r}: actual_GetPosition={record.get('pos')}, native_text_bbox_mm={box.format_mm()}, detail_{label}_crop_mm={obstacle.format_mm()}, actual_air_mm={air * 1000.0:.3f}, required_air_mm=1.000"
                _telemetry.info(detail)
                if air < 0.001 - 1e-12:
                    raise RuntimeError(detail)


def _require_radius_exterior(adapter: Any, front: Any) -> None:
    """Native projected parent circles, not front-only scale predictions."""
    reader = _Reader(adapter)
    annotations = tuple(_early_bound(front, "IView").GetAnnotations() or ())
    centre, top_rim, bottom_rim = _project(
        adapter, front,
        ((0.0, CENTER_Y / 1000.0, 0.0),
         (R_TOP / 1000.0, CENTER_Y / 1000.0, 0.0),
         (R_BOTTOM / 1000.0, CENTER_Y / 1000.0, 0.0)),
        label="BASIC radius parent circles",
    )
    for name, rim in (("TopRadius", top_rim), ("BottomRadius", bottom_rim)):
        matches = [ann for ann in annotations if dimension_name(adapter, ann) == name]
        if len(matches) != 1:
            raise RuntimeError(f"{name}: expected one native BASIC radius")
        record = _dump_annotation(reader, matches[0])
        errors = reader.take_errors()
        if record is None or errors:
            raise RuntimeError(f"{name}: cannot measure native BASIC radius ink: {errors!r}")
        radius = math.dist(centre, rim)
        if not math.isfinite(radius) or radius <= 0.0:
            raise RuntimeError(f"{name}: invalid native projected circle radius={radius!r}")
        geometry = _arc_callout_geometry(record, calibrate_sheet_advance([record]))
        for box in geometry.text_boxes:
            distance = math.hypot(
                max(box.xmin - centre[0], centre[0] - box.xmax, 0.0),
                max(box.ymin - centre[1], centre[1] - box.ymax, 0.0),
            )
            detail = f"{name}: requested_xy_mm={tuple(v * 1000.0 for v in FRONT_KEEP[name])}, actual_GetPosition={record.get('pos')}, native_text_bbox_mm={box.format_mm()}, native_circle_centre={centre}, native_circle_radius_mm={radius * 1000.0:.3f}, actual_exterior_air_mm={(distance - radius) * 1000.0:.3f}, required_exterior_air_mm=0.000"
            _telemetry.info(detail)
            if distance <= radius:
                raise RuntimeError(detail)


def _add_strap_offset_dimension(adapter: Any, right: Any) -> Any:
    """Measure hub +Z end to strap +Z face, as a band-free parenthesized reference."""
    edges = scan_view_edges(right, label="rocker right offset")
    strap = edges.exact_line_through(
        (_TIP_FACE_MID_X, _TIP_FACE_MID_Y, ARM_THICKNESS / 2.0),
        label="+Z strap face at radial land",
    )
    hub = edges.circle_at(
        (0.0, PIVOT_MID_Y, HUB_LENGTH / 2.0), HUB_DIA / 2.0,
        axis=(0.0, 0.0, 1.0), label="+Z hub end rim",
    )
    points = model_points_in_view(
        adapter, right,
        [
            (0.0, (PIVOT_MID_Y + HUB_DIA / 2.0) / 1000.0, HUB_LENGTH / 2000.0),
            tuple(v / 1000.0 for v in strap.midpoint_mm),
        ],
        label="hub end and strap face offset",
    )
    dimension = add_edge_dimension(
        adapter, right, p0=points[0], p1=points[1],
        text_xy=STRAP_OFFSET_TEXT_XY, label="strap offset from hub end",
        orientation="horizontal", entities=(hub.edge, strap.edge),
    )
    # In the right view the end rim projects to a straight, constant-Z line;
    # it has no drawing circular endpoint to centre. The native X measurement
    # and attachment readbacks below prove the end-plane offset directly.
    assert_dimension_measures(
        adapter, dimension, expected_mm=(HUB_LENGTH - ARM_THICKNESS) / 2.0,
        label="strap offset from hub end", entities=(hub.edge, strap.edge),
    )
    display = _early_bound(dimension, "IDisplayDimension")
    model_dimension = _early_bound(display.GetDimension2(0), "IDimension")
    if int(model_dimension.GetToleranceType()) != 0:  # swTolNONE
        raise RuntimeError("strap offset reference acquired an acceptance band")
    display.SetPrecision3(DEFAULT_DRAWING_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DEFAULT_DRAWING_PRECISION:
        raise RuntimeError("strap offset reference lost normal drawing precision")
    display.MaxWitnessLineLength = STRAP_OFFSET_WITNESS_LENGTH
    if abs(float(display.MaxWitnessLineLength) - STRAP_OFFSET_WITNESS_LENGTH) > 1e-9:
        raise RuntimeError("strap offset retained crossing full-height witnesses")
    set_reference_dimension(
        adapter, display.GetAnnotation(), label="strap offset from hub end"
    )
    return display


def _add_land_datum(adapter: Any, front: Any, land: ViewEdge) -> Any:
    """Attach C to the exact +Z radial land, with its triangle on the midpoint."""
    if (
        land.line is None
        or any(abs(point[2] - ARM_THICKNESS / 2.0) > 1e-5 for point in land.line)
        or abs(land.length_mm - TIP_FACE) > 1e-5
    ):
        raise RuntimeError("datum C needs the exact +Z radial land edge")
    start, end = _project(
        adapter, front, [tuple(v / 1000.0 for v in point) for point in land.line],
        label="datum C exact land endpoints",
    )
    midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    dx, dy = end[0] - start[0], end[1] - start[1]
    nx, ny = -dy, dx
    if nx < 0.0:
        nx, ny = -nx, -ny
    reach = LAND_DATUM_STANDOFF / math.hypot(nx, ny)
    return add_datum_feature(
        adapter, front, edge_entity=land.edge, leader_attach_xy=midpoint,
        symbol_xy=(midpoint[0] + nx * reach, midpoint[1] + ny * reach),
        datum="C", label="+Z rod-side radial land",
    )


def _arc_profile_point(name: str) -> tuple[float, float, float]:
    """Real model point on a supported arc, away from the taper vertex."""
    radius = {"TopRadius": R_TOP, "BottomRadius": R_BOTTOM}[name]
    limit = {"TopRadius": TOP_END_X, "BottomRadius": BOT_END_X}[name]
    x = ARC_PROFILE_PICK_X_MM[name]
    if abs(x) >= limit:
        raise RuntimeError(f"{name}: profile landing lies outside the actual arc domain")
    return (x / 1000.0, (CENTER_Y - math.sqrt(radius**2 - x**2)) / 1000.0, 0.0)


def _add_arc_profiles(adapter: Any, front: Any) -> dict[str, Any]:
    """Attach and retain native frames: Ⓤ0.5 top, Ⓤ0 bottom, total zone 0.5."""
    profiles = {}
    for name, radius in (("TopRadius", R_TOP), ("BottomRadius", R_BOTTOM)):
        edge = visible_circle_edge(adapter, front, 2.0 * radius)
        (landing,) = _project(adapter, front, (_arc_profile_point(name),), label=f"{name} profile landing")
        profiles[name] = add_feature_control_frame(
            adapter,
            front,
            edge_entity=edge,
            leader_attach_xy=landing,
            frame_xy=ARC_PROFILE_FRAME_XY[name],
            characteristic="profile_surface",
            tolerance=ARC_PROFILE_ZONE_MM,
            outside_disposition=ARC_PROFILE_OUTSIDE_MM[name],
            datums=("A", "B", "C"),
            label=f"arc-system {name} profile",
        )
    return profiles


def _arc_callout_geometry(record: dict[str, Any], advance: float) -> Any:
    """Validate required native data before the audit's tolerant geometry parser."""
    position = record.get("pos", ())
    if len(position) != 3 or not all(math.isfinite(v) for v in position):
        raise ValueError(f"invalid native GetPosition={position!r}")
    display = record.get("display") or {}
    texts = display.get("texts", ())
    if not texts or not any(item["t"].strip() for item in texts):
        raise ValueError("missing native callout text")
    for item in texts:
        if (
            len(item["pos"]) != 3
            or not all(math.isfinite(v) for v in item["pos"])
            or not math.isfinite(item["h"]) or item["h"] <= 0.0
            or not math.isfinite(item["ang"])
            or item["ref"] not in range(6)
        ):
            raise ValueError(f"invalid native text geometry={item!r}")
    for key, rows in display.items():
        if key == "texts":
            continue
        for row in rows:
            if not all(math.isfinite(v) for v in row):
                raise ValueError(f"invalid native {key} geometry={row!r}")
            if key == "lines" and len(row) != 10:
                raise ValueError(f"invalid native line geometry={row!r}")
    geometry = annotation_geometry(record, owner="front", advance=advance)
    if geometry is None or not geometry.text_boxes:
        raise ValueError("missing native callout text bbox")
    for box in geometry.text_boxes:
        if (
            not all(math.isfinite(v) for v in (box.xmin, box.ymin, box.xmax, box.ymax))
            or box.xmin >= box.xmax or box.ymin >= box.ymax
        ):
            raise ValueError(f"invalid native callout text bbox={box!r}")
    return geometry


def _require_arc_profile_clearance(
    adapter: Any, front: Any, profiles: dict[str, Any]
) -> None:
    """After the final rebuild, prove native profile leaders clear other callouts.

    This is PDF-free: the final enforced ink audit remains authoritative for
    printed glyphs. Native text positions/heights and the audit's existing row
    width model give an early refusal, not a claim of exact PDF text widths.
    """
    reader = _Reader(adapter)
    records = []
    profile_names = {}
    problems = []
    for name in ARC_PROFILE_FRAME_XY:
        try:
            gtol = reader.bind(profiles.get(name), "IGtol")
            if gtol is None:
                raise ValueError("missing native IGtol")
            annotation = reader.bind(reader.need(lambda: gtol.GetAnnotation()), "IAnnotation")
            if annotation is None:
                raise ValueError("missing native IAnnotation")
            native_name = reader.need(lambda: annotation.GetName(), "")
            if type(native_name) is not str or not native_name:
                raise ValueError(f"invalid native annotation name={native_name!r}")
            profile_names[name] = native_name
        except (TypeError, ValueError) as exc:
            problems.append(f"arc-system {name} profile: {exc}")
    if len(set(profile_names.values())) != len(profile_names):
        problems.append("native arc-profile frames have duplicate annotation names")
    try:
        view = reader.bind(front, "IView")
        raw_annotations = reader.need(lambda: view.GetAnnotations(), ())
        for raw in raw_annotations:
            try:
                record = _dump_annotation(reader, raw)
                if record is None:
                    problems.append("front-view annotation could not be read")
                else:
                    records.append(record)
            except (TypeError, ValueError, OverflowError) as exc:
                bound = reader.bind(raw, "IAnnotation")
                label = reader.need(lambda: bound.GetName(), "<unreadable>")
                problems.append(f"front-view callout {label!r}: invalid native readback: {exc}")
    except (TypeError, ValueError, OverflowError) as exc:
        problems.append(f"invalid native front-view readback: {exc}")

    def mm(values: Any) -> tuple[float, ...]:
        return tuple(round(value * 1000.0, 3) for value in values)

    # Log every available native read before any refusal, on success too.
    for name in ARC_PROFILE_FRAME_XY:
        matches = [r for r in records if r.get("name") == profile_names.get(name)]
        if len(matches) != 1:
            problems.append(f"arc-system {name} profile: expected one native front-view frame, got {len(matches)}")
        for record in matches:
            _telemetry.info(
                f"arc-system {name} profile native readback: "
                f"requested_frame_mm={mm(ARC_PROFILE_FRAME_XY[name])!r}, "
                f"actual_GetPosition_mm={mm(record.get('pos', ()))!r}, "
                f"native_leader_points_mm={[mm(p) for p in record.get('leaders', ())]!r}, "
                f"landing_mm={[mm(p[-3:]) for p in record.get('leaders', ())]!r}"
            )
    refused = reader.take_errors()
    if refused:
        problems.append(f"native COM reads refused: {refused!r}")
    geometries = {}
    try:
        advance = calibrate_sheet_advance(records)
        for record in records:
            if record.get("owner_type") == 2 or record.get("visible") in (2, 3):
                continue
            # Construction marks carry no callout text; every other annotation
            # must be measurable, rather than quietly dropping a foreign box.
            if record.get("type") in (1, 13, 15):
                continue
            try:
                geometries[id(record)] = _arc_callout_geometry(record, advance)
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                problems.append(f"front-view callout {record.get('name')!r}: {exc}")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        problems.append(f"invalid native text calibration: {exc}")
    measured = []
    for name in ARC_PROFILE_FRAME_XY:
        matches = [r for r in records if r.get("name") == profile_names.get(name)]
        if len(matches) != 1:
            continue
        record = matches[0]
        source = geometries.get(id(record))
        context = (
            f"arc-system {name} profile requested_frame_mm={mm(ARC_PROFILE_FRAME_XY[name])!r}, "
            f"actual_GetPosition_mm={mm(record.get('pos', ()))!r}, "
            f"native_leader_points_mm={[mm(p) for p in record.get('leaders', ())]!r}"
        )
        leaders = record.get("leaders", ())
        if (
            record.get("type") != 5 or record.get("owner_type") != 0
            or source is None or len(leaders) != 1
            or any(len(p) != 9 or not all(math.isfinite(v) for v in p) for p in leaders)
        ):
            problems.append(f"{context}: missing/invalid native bent-profile geometry")
            continue
        segments = _registered_leaders(record)
        if any(segment.length <= 0.0 for segment in segments):
            problems.append(f"{context}: invalid zero-length native leader segment")
            continue
        frame_lines = [
            s for s in source.segments
            if s.role not in ("leader", "arrow") and s.length > 0.0
        ]
        frame_box = union_boxes([*source.text_boxes, *(s.box() for s in frame_lines)])
        if not frame_lines or frame_box is None:
            problems.append(f"{context}: missing native frame ink bbox")
            continue
        context += f", native_frame_ink_bbox_mm={frame_box.format_mm()}"
        _telemetry.info(context)
        native_segments = [
            LeaderSegment(source.label, source.kind, s.x0, s.y0, s.x1, s.y1, "front")
            for s in segments
        ]
        for other in records:
            target = geometries.get(id(other))
            if other is record or target is None:
                continue
            native_segments.extend(
                LeaderSegment(target.label, target.kind, s.x0, s.y0, s.x1, s.y1, "front")
                for s in target.leader_segments()
            )
        for crossing in find_leader_leader_crossings(native_segments):
            if source.label not in (crossing.a.label, crossing.b.label):
                continue
            detail = f"{context}: actual native leader crossing: {crossing.describe()}, intersection_mm={(crossing.x * 1000.0, crossing.y * 1000.0)}"
            _telemetry.info(detail)
            problems.append(detail)
        distances = [
            (segment_box_distance(segment, box), target, box, segment)
            for other in records if other is not record
            for target in (geometries.get(id(other)),) if target is not None
            for box in target.text_boxes for segment in segments
        ]
        if not distances:
            problems.append(f"{context}: missing other native front-view callout bboxes")
            continue
        distance, target, box, segment = min(distances, key=lambda item: item[0])
        penetration, _span = text_overlap(segment, target, box)
        detail = (
            f"{context}, minimum_clearance_mm={distance * 1000.0:.3f}, "
            f"required_clearance_mm={ARC_PROFILE_TEXT_CLEARANCE_M * 1000.0:.3f}, "
            f"offending_callout={target.label!r}, bbox_mm={box.format_mm()}, "
            f"native_segment={segment.format_mm()}, penetration_mm={penetration * 1000.0:.3f}"
        )
        _telemetry.info(detail)
        measured.append(detail)
        if distance < ARC_PROFILE_TEXT_CLEARANCE_M and not math.isclose(
            distance, ARC_PROFILE_TEXT_CLEARANCE_M, rel_tol=0.0, abs_tol=1e-12
        ):
            problems.append(detail)
    if problems:
        raise RuntimeError(
            "rocker arc-profile native clearance failed:\n"
            + "\n".join(problems + [d for d in measured if d not in problems])
        )


def _note_extent(adapter: Any, note: Any, *, label: str = "manufacturing notes") -> tuple[float, float, float, float]:
    """Native GetExtent sheet-space note BOX, not proven printed glyph ink."""
    adapter.currentModel.GraphicsRedraw2()
    extent = tuple(
        float(value) for value in (_early_bound(note, "INote").GetExtent() or ())
    )
    if (len(extent) != 6 or not all(math.isfinite(v) for v in extent)
            or extent[3] <= extent[0] or extent[4] <= extent[1]):
        raise RuntimeError(f"{label} have no rendered extent: {extent!r}")
    return (extent[0], extent[1], extent[3], extent[4])


def _seat_notes_on_border(
    adapter: Any, note: Any, sheet: Any
) -> tuple[float, float, float, float]:
    """Steer the notes' RENDERED bottom-left corner onto NOTES_LEFT,
    NOTES_BORDER_CLEARANCE above the sheet's drawable region (the insertion
    point is neither the text box's corner nor tracked by it 1:1)."""
    template = DRAWING_TEMPLATES[SPEC.layout]
    region = sheet_drawable_region(
        adapter, sheet, width=template.width_m, height=template.height_m
    )
    target = (NOTES_LEFT, region.ymin + NOTES_BORDER_CLEARANCE)
    annotation = _early_bound(
        _early_bound(note, "INote").GetAnnotation(), "IAnnotation"
    )
    # A property-linked note shows its resolved text only after a rebuild; an
    # extent read before it would seat the one-line link token, not the block.
    rebuild_drawing(adapter, label="manufacturing notes link resolve")
    extent = _note_extent(adapter, note)
    lines = len(DRAWING_NOTES.splitlines())
    if extent[3] - extent[1] < lines * NOTES_MIN_LINE_PITCH:
        raise RuntimeError(
            f"manufacturing notes render {(extent[3] - extent[1]) * 1000.0:.1f} mm "
            f"tall, under {lines} lines at {NOTES_MIN_LINE_PITCH * 1000.0:.1f} mm: "
            "the property link has not resolved"
        )
    for _pass in range(NOTES_SEAT_PASSES):
        shift = (target[0] - extent[0], target[1] - extent[1])
        if max(abs(shift[0]), abs(shift[1])) <= NOTES_SEAT_SETTLE:
            break
        position = tuple(float(value) for value in (annotation.GetPosition() or ()))
        if len(position) != 3:
            raise RuntimeError(f"manufacturing notes position unreadable: {position!r}")
        if not annotation.SetPosition(
            position[0] + shift[0], position[1] + shift[1], position[2]
        ):
            raise RuntimeError("manufacturing notes SetPosition failed")
        extent = _note_extent(adapter, note)
    extent_mm = tuple(round(value * 1000.0, 2) for value in extent)
    _telemetry.info(
        f"manufacturing notes seated: extent_mm={extent_mm!r}, "
        f"drawable bottom {region.ymin * 1000.0:.2f} mm"
    )
    if extent[1] < region.ymin or extent[3] > NOTES_CEILING:
        raise RuntimeError(
            "manufacturing notes do not fit between the border "
            f"({region.ymin * 1000.0:.2f} mm) and the front view's annotations "
            f"({NOTES_CEILING * 1000.0:.1f} mm): rendered extent {extent_mm!r}"
        )
    return extent


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-arm source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Arm Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm; tapered strap; seesaw pivot",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    # Explicit per-view scale (an auto-scaled view shifts every coordinate pick).
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    # 1:1 right end view: the 2.50 x ~29 strap section -- prints the strap
    # thickness and hub length, gives the through direction, and carries datum B
    # (the broad face) so the rod-pin position frame has an orientation datum.
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (right, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, front)

    # Import the source radii and top height too: these are the BASIC nominal
    # geometry of the profile zone, not independent radius/height bands.
    _add_rocker_outline_dimensions(adapter, front)
    hub_centre, hub_radius_mm = _detail_fence("D")
    hub = _create_detail(
        adapter, front, centre=hub_centre, radius_mm=hub_radius_mm,
        target=HUB_CENTER, scale=HUB_SCALE, label="D",
    )
    end_centre, end_radius_mm = _detail_fence("E")
    end = _create_detail(
        adapter, front, centre=end_centre, radius_mm=end_radius_mm,
        target=END_CENTER, scale=END_SCALE, label="E",
    )
    hub_annotations = curate_view_dimensions(
        adapter, hub, keep=HUB_KEEP, view_label="detail D",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _dress_detail_dimensions(adapter, hub_annotations, keep=HUB_KEEP)
    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="detail E",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _dress_detail_dimensions(adapter, end_annotations, keep=END_KEEP)
    rod_land = scan_view_edges(end, label="detail E rod land").exact_line_through(
        (_TIP_FACE_MID_X, _TIP_FACE_MID_Y, ARM_THICKNESS / 2.0),
        label="+Z rod-side radial land",
    )
    _add_land_angle(adapter, end, rod_land)
    # The hub length and the strap thickness only show in the end view; the
    # front looks down their direction. Codex #936 (PRRT_kwDOPHDy386mRk__):
    # RIGHT_KEEP was declared but never curated, so the +0.05/0 band that sets
    # all 20 channel stations never printed. Targeted by feature, so only
    # Hub's and Strap's dimensions arrive, each selected by its feature name.
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    imported_annotations = [
        *front_annotations, *hub_annotations, *end_annotations, *right_annotations,
    ]
    _assert_pivot_precision(adapter, drawing_model, imported_annotations)
    assert_imported_precision(
        adapter,
        imported_annotations,
        {
            "TopAbovePivot": TOP_EDGE.precision["height_above_pivot"],
            "HubLength": HUB_FACES.precision["length"],
            "StrapThickness": STRAP_DATUM_B.precision["thickness"],
        },
    )
    _add_strap_offset_dimension(adapter, right)

    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    for label, view in (("front", front), ("detail D", hub), ("detail E", end)):
        if drawing.ActivateView(view_name(adapter, view)) is not True:
            raise RuntimeError(f"failed to activate {label} before center marks")
        active = _early_bound(drawing.ActiveDrawingView, "IView")
        if active is None or int(adapter.swApp.IsSame(active, view)) != 1:
            raise RuntimeError(f"no matching active native view for {label} center marks")
        if auto_center_marks(adapter, active, holes=True, size=0.0025) is not True:
            raise RuntimeError(f"failed to add ASME center marks to {label}")

    # E's native wizard-hole callout keeps the source through condition.
    rod_hole_edge = visible_circle_edge(adapter, end, _ROD_HOLE_DIA)
    rod_callout = add_native_hole_callout(
        adapter,
        end,
        edge=rod_hole_edge,
        callout_xy=ROD_CALLOUT_XY,
        label="rod-pin hole",
        process=drill_process(ROD_HOLE_SPEC) + "\n",
    )
    _require_rod_through_callout(rod_callout)

    _add_pin_coordinates(adapter, front)

    pivot_bore_edge = visible_circle_edge(adapter, hub, PIVOT_HOLE_DIA)
    pivot_centre, bore_right = _project(
        adapter, hub,
        ((0.0, PIVOT_MID_Y / 1000.0, 0.0),
         (PIVOT_HOLE_DIA / 2000.0, PIVOT_MID_Y / 1000.0, 0.0)),
        label="detail D bore centre and radius",
    )
    projected_radius = math.dist(pivot_centre, bore_right)
    pivot_datum_pick = _pick_pivot_bore(
        adapter, hub, pivot_bore_edge, pivot_centre, projected_radius,
    )
    datum_a = add_datum_feature(
        adapter, hub, edge_xy=pivot_datum_pick,
        symbol_xy=_pivot_datum_request(pivot_centre, projected_radius),
        datum="A", label="pivot bore cylindrical datum feature", shoulder=True,
    )
    _require_datum_on_bore(adapter.swApp, datum_a, pivot_bore_edge)
    pivot_finish_rim, pivot_finish_symbol = _pivot_finish_placement(adapter, hub)
    add_surface_finish(
        adapter,
        hub,
        edge_entity=pivot_bore_edge,
        symbol_xy=pivot_finish_symbol,
        leader_attach_xy=pivot_finish_rim,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bore"),
        label="pivot bore finish",
        char_height=PIVOT_FINISH_CHAR_HEIGHT,
    )
    # Then a position FCF tying the rod-pin hole to the complete A-B-C frame.
    # Datum B (broad face, on the end view) orients the hole axes; datum C
    # (the +X tip face) clocks rotation about the pivot axis, so the X/Y BASIC
    # coordinates above have an inspectable direction.
    # Datum B on the strap's broad face in the end view, picked ABOVE the hub
    # band (the O10 hub hides the flank over y 3..13 since 2026-09-02); the
    # end view is centred on the strap's mid-depth (PIVOT_MID_Y).
    broad_face = (
        RIGHT_CENTER[0] - ARM_THICKNESS / 2000.0,
        RIGHT_CENTER[1]
        + (ARM_DEPTH - 1.0 - PIVOT_MID_Y) / 1000.0,  # right view is 1:1,
    )
    add_datum_feature(
        adapter,
        right,
        edge_xy=broad_face,
        symbol_xy=(broad_face[0] - 0.016, broad_face[1] - 0.014),
        datum=STRAP_DATUM_B.fields["datum"][0],
        label="broad face",
    )
    _add_land_datum(adapter, end, rod_land)
    (rod_position_landing,) = _project(
        adapter, end,
        ((ROD_HOLE_X / 1000.0 + _ROD_HOLE_DIA / (2000.0 * math.sqrt(2.0)),
          ROD_HOLE_Y / 1000.0 - _ROD_HOLE_DIA / (2000.0 * math.sqrt(2.0)), 0.0),),
        label="detail E southeast rod-hole position landing",
    )
    add_feature_control_frame(
        adapter,
        end,
        edge_entity=rod_hole_edge,
        leader_attach_xy=rod_position_landing,
        frame_xy=FCF_XY,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["rod-pin hole position"],
        datums=tuple(ROD_HOLE.fields["position_datums"][0]),
        diameter=True,
        label="rod-pin hole position",
    )
    arc_profiles = _add_arc_profiles(adapter, front)

    notes = add_property_linked_note(
        adapter, "Manufacturing Notes", NOTES_LEFT, NOTES_CEILING
    )
    notes_box = _seat_notes_on_border(adapter, notes, sheet)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_CAPTION_XY)
    _place_detail_letters(adapter, front)
    _normalize_detail_caption_styles(adapter, front, hub, end, notes)
    # Record BOTH native labels before D can abort and discard E's evidence.
    _record_detail_caption(adapter, hub, sheet, label="D", stage="before either caption guard")
    _record_detail_caption(adapter, end, sheet, label="E", stage="before either caption guard")
    _seat_detail_caption(adapter, hub, sheet, label="D")
    _seat_detail_caption(adapter, end, sheet, label="E")
    # The shared gate: no overlaps, border crossings or leader crossings.
    rebuild_drawing(adapter, label="rocker-arm layout audit")
    _require_dimension_census(adapter, (
        ("front", front, FRONT_KEEP), ("detail D", hub, HUB_KEEP),
        ("detail E", end, END_KEEP), ("right", right, RIGHT_KEEP), ("iso", iso, {}),
    ))
    _require_ream_clearance(adapter, hub, notes_box)
    _require_front_detail_air(adapter, front, hub, end)
    _require_radius_exterior(adapter, front)
    _require_arc_profile_clearance(adapter, front, arc_profiles)
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Manufacturing Drawing",
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
