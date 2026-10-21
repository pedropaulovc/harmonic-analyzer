r"""Create the curated machinist drawing for MHA-DT-35, the crank handle butt cup.

A plain steel cup (user rulings 2026-09-29 and 2026-09-30, ch11 p.14/p.15 and
ch30 eight-views-4).  The end view
carries only its centre mark and the cutting plane; the longitudinal section
A-A carries the original dimensions.  DETAIL B enlarges only the new pocket-side
floor-hole mouth bevel and carries its native model-owned LIMIT dimension.  The
section (drawing-guidelines.md rule 9 (show internal shape in solid lines)) shows
the pocket and the floor hole on cut edges rather than hidden lines (the
MHA-DT-35 machinist review).  The body diameter and the pocket depth are the
bands; the pocket is bored to suit the MHA-DT-32 head (a reference size whose
callout states the fit), and the floor hole carries its drill callout.  Every
band names its mate at the callout (MHA-DT-35 machinist ENFORCE, r1).
Owner ruling B on #1375 restores the pocket-wall floor in the model, so its
former shortfall note and property are not part of the sheet.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_crank_handle_butt_cup.py dt-crank-handle-butt-cup
"""

from __future__ import annotations

import argparse
import contextlib
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
from _drawing_detail_crop import native_circle_geometry, read_circular_detail_crop
from _drawing_detail_projection import settle_detail_projection
from _drawing_dimensions import (
    assert_imported_precision,
    move_model_dimension,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_layout_collect import check_drawing_layout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _section_axis import create_section_axis_centerline, position_section_caption
from _session import run_build
import _seat_forensics
import _telemetry
import _drawing_layout_audit
import _layout_audit
from _drawing_layout_check import LeaderSegment, _proper_crossing
from _drawing_projection import model_point_in_view
from _layout_geometry import Box, Segment, segment_box_distance
from dt_crank_handle_butt_cup_notes import (
    BODY_CHAMFER_CALLOUT,
    BODY_FIT_CALLOUT,
    FLOOR_HOLE_CALLOUT,
    FLOOR_HOLE_MOUTH_CHAMFER_CALLOUT,
    FLOOR_HOLE_MOUTH_CHAMFER_SUFFIX,
    POCKET_DEPTH_CALLOUT,
    POCKET_FIT_CALLOUT,
)
from dt_crank_handle_butt_cup_spec import (
    BODY_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FLOOR_HOLE_DIA,
    FLOOR_HOLE_MOUTH_CHAMFER,
    FLOOR_HOLE_MOUTH_CHAMFER_BAND,
    FLOOR_HOLE_MOUTH_CHAMFER_TOL_TYPE,
    OVERALL_LENGTH,
    POCKET_DEPTH,
    POCKET_FLOOR_CORNER_R_BAND,
    POCKET_FLOOR_CORNER_R_MAX,
    POCKET_FLOOR_CORNER_R_TOL_TYPE,
    REFERENCE_DIMENSIONS,
)
from _fit_deviations import deviations


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_crank_handle_butt_cup"]
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

# Ø9.6 x 8.1 at 5:1 reads 48 x 41 on the sheet.
SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
ISO_SCALE = (4, 1)
# Third angle: the end view left of the section looks at the chamfered
# floor face (*Left), not the counterbore mouth on the opposite end.
END_CENTER = (0.074, 0.165)
# 10 mm right of the r1 sheet: the body-fit callout needs the room between the
# floor-hole dimension and the section.
SECTION_CENTER = (0.225, 0.165)
ISO_CENTER = (0.368, 0.215)
# Below the floor end, clear of the floor-hole callout.
CAPTION_XY = (0.160, 0.114)
ISO_NOTE_POS = (0.335, 0.170)
# A section-child detail retains the cut interior; an HLR unsectioned side
# view would hide this mouth behind the body.  Only the NEW dimension moves.
MOUTH_DETAIL_LABEL = "B"  # distinct from SECTION A-A
MOUTH_DETAIL_CENTER = (0.313, 0.111)
MOUTH_DETAIL_SCALE = (20.0, 1.0)
MOUTH_DETAIL_RADIUS_MM = 0.8
MOUTH_DETAIL_CAPTION = (0.313, 0.084)
MOUTH_DETAIL_LETTER = (0.229, 0.173)
MOUTH_DETAIL_KEEP = {"FloorHoleMouthChamfer": (0.373, 0.136)}
MOUTH_GEOMETRY_TOL_M = 0.00005

_S = VIEW_SCALE[0] / 1000.0
BODY_R = BODY_DIA * _S / 2.0  # 0.024
HALF_LENGTH = OVERALL_LENGTH * _S / 2.0  # 0.02025
# The section lays the part's +X to the right (the draw_crank_pinion
# convention), so the face is the right edge and the floor the left.
FACE_X = SECTION_CENTER[0] + HALF_LENGTH

# The pocket opens right; the smaller floor-hole dimension nests closest to
# the floor end, with the body diameter outboard.  Axial sizes remain above
# (overall) and below (pocket depth), both measured from the face.
#
# Sheet-mm solve from the 22821a1d2 native r2 findings (2026-10-19), not a
# symmetric text-box estimate.  All view centres and scales stay unchanged:
# - R0.1 MAX at keep (217.75,190.75) printed glyphs [207.3,188.9]..[228.3,192.5]
#   and a 25.9 mm shoulder (231.5,188.0)->(205.6,188.0).  The chamfer's
#   witness reaches y191.5 and its outside-arrow tail runs x206.8..213.1 at
#   y190.5.  Raise ONLY the radius row 6.75: shoulder y194.75 is 3.25 above
#   that witness, and glyph bottom y195.65 is 5.15 above the arrow tail.
#   Keep X217.75, so the text still faces the real 90..180-degree quarter arc.
# - Overall's arrow barb bottom y194.3 was 1.87 mm from the radius glyphs;
#   its glyphs [221.9,195.7]..[227.2,199.2] had only 3.18 mm block separation.
#   Raise overall 8: the arrow-to-radius gap becomes 3.05 and the text gap
#   4.45 mm (>3.57).  Both full witnesses remain outside the radius shoulder.
# - PocketDepth's upper row [268.8,140.2]..[286.9,143.8] met PocketDia's
#   outside-arrow tail x284.2, y142.9..149.2.  Lower the whole depth block
#   3.5: its top is y140.3, 2.6 below the tail, including its far endpoint.
# - The 031202 native floor-hole keep (136.75,141) put DRILL THRU on a
#   shoulder at keep_y-5.583, with its main glyph top at keep_y+3.5267.
#   Keep the same below-witness/hung-text regime (keep_y <154.5), but nest
#   its column at x201.75, 3 left of the floor, instead of crossing BodyDia's
#   x166.75 column.  For 2 mm air above BodyDia's y144.5 lower witness and
#   3.57 mm below its r2 y160.4 text-break boundary, the keep-Y range is
#   152.083..153.3033; choose 152.5.  The shoulder is then y146.917 and the
#   main glyph top y156.0267, 4.3733 below BodyDia's lower row.  DRILL THRU's
#   full 24.0285 mm row hangs LEFT of keep X, so all text ends at x201.75,
#   3 mm from the actual floor silhouette x204.75, not on the section.
# Rounded r2 coordinates have 0.05 mm uncertainty; offline contracts retain it.
SECTION_KEEP = {
    "PocketDia": (FACE_X + 0.039, SECTION_CENTER[1] + 0.001),
    "BodyDia": (SECTION_CENTER[0] - HALF_LENGTH - 0.038, SECTION_CENTER[1] + 0.001),
    # Smaller diameter closest to the floor; the complete two-row hung block
    # fits above the body witness without moving into the hole's witness span.
    "FloorHoleDia": (
        SECTION_CENTER[0] - HALF_LENGTH - 0.003,
        SECTION_CENTER[1] - 0.0125,
    ),
    "OverallLength": (SECTION_CENTER[0], SECTION_CENTER[1] + BODY_R + 0.020),
    "PocketDepth": (FACE_X + 0.033, SECTION_CENTER[1] - BODY_R - 0.0115),
    "BodyChamfer": (
        SECTION_CENTER[0] - HALF_LENGTH - 0.0295,
        SECTION_CENTER[1] + BODY_R + 0.0161,
    ),
    "PocketFloorRadius": (
        FACE_X - POCKET_DEPTH * _S,
        SECTION_CENTER[1] + BODY_R + 0.012,
    ),
}
ALL_KEEP = {**SECTION_KEEP, **MOUTH_DETAIL_KEEP}
DIMENSION_CALLOUTS = {
    "BodyChamfer": BODY_CHAMFER_CALLOUT,
    "BodyDia": BODY_FIT_CALLOUT,
    "FloorHoleDia": FLOOR_HOLE_CALLOUT,
    "PocketDepth": POCKET_DEPTH_CALLOUT,
    "PocketDia": POCKET_FIT_CALLOUT,
    "FloorHoleMouthChamfer": FLOOR_HOLE_MOUTH_CHAMFER_CALLOUT,
}
# *Left reverses *Right's horizontal basis.  Reverse the cut as well to
# retain the section's physical viewing direction and +X-right orientation.
CUT_START = (END_CENTER[0], END_CENTER[1] + BODY_R + 0.006)
CUT_END = (END_CENTER[0], END_CENTER[1] - BODY_R - 0.006)


def _dress_pocket_floor_radius(annotation: Any) -> None:
    """Keep the imported model radius controlling, MAX, and on its real arc."""
    label = "MHA-DT-35 PocketFloorRadius"
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric) or int(display.Type2) != 5:  # swRadialDimension
        raise RuntimeError(f"{label}: imported as a non-radial dimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    lower, upper = deviations(POCKET_FLOOR_CORNER_R_BAND)
    if (
        not math.isclose(
            float(dimension.SystemValue),
            POCKET_FLOOR_CORNER_R_MAX / 1000.0,
            abs_tol=1e-9,
        )
        or int(tolerance.Type) != POCKET_FLOOR_CORNER_R_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: imported radius lost its model MAX limit")
    if (
        bool(dimension.IsReference())
        or bool(display.ShowParenthesis)
        or any(
            "(" in str(display.GetText(index) or "")
            or ")" in str(display.GetText(index) or "")
            for index in (1, 2)
        )
    ):
        raise RuntimeError(f"{label}: imported as a reference")
    display.ArcExtensionLineOrOppositeSide = False
    display.ArrowSide = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
    display.SolidLeader = False
    if (
        bool(display.ArcExtensionLineOrOppositeSide)
        or int(display.ArrowSide) != 1
        or bool(display.SolidLeader)
    ):
        raise RuntimeError(f"{label}: radial leader style did not persist")


def _assert_floor_hole_mouth_chamfer(annotation: Any) -> None:
    """Read native feature identity, real value, limits, precision and prose."""
    label = "MHA-DT-35 FloorHoleMouthChamfer"
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    if (
        int(display.Type2) not in (2, 11)  # native linear/horizontal linear
        or bool(display.Diametric)
        or str(dimension.FullName).split("@")[:2]
        != ["FloorHoleMouthChamfer", "CupProfile"]
        or bool(dimension.IsReference())
        or bool(display.ShowParenthesis)
        or bool(display.GetOverride())
        or not bool(display.ShowDimensionValue)
        or str(display.GetText(1) or "").strip()
        or str(display.GetText(2) or "") != FLOOR_HOLE_MOUTH_CHAMFER_SUFFIX
        or str(display.GetText(3) or "").strip()
        or str(display.GetText(4) or "").replace("\r\n", "\n")
        != FLOOR_HOLE_MOUTH_CHAMFER_CALLOUT
    ):
        raise RuntimeError(
            f"{label}: lost its controlling native leg, owner or attached prose"
        )
    lower, upper = deviations(FLOOR_HOLE_MOUTH_CHAMFER_BAND)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if (
        not math.isclose(
            float(dimension.SystemValue),
            FLOOR_HOLE_MOUTH_CHAMFER / 1000.0,
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        or int(tolerance.Type) != FLOOR_HOLE_MOUTH_CHAMFER_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, rel_tol=0.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, rel_tol=0.0, abs_tol=1e-12
        )
        or int(display.GetPrimaryPrecision2()) != 2
        or int(display.GetPrimaryTolPrecision2()) != 2
    ):
        raise RuntimeError(f"{label}: lost its model-owned two-place LIMIT band")


def _mouth_model_reference(adapter: Any, section: Any) -> tuple[float, float, float]:
    """Use the real CupProfile frame, not an assumed global axis convention."""
    document = _early_bound(
        _early_bound(section, "IView").ReferencedDocument, "IPartDoc"
    )
    feature = document.FeatureByName("CupProfile")
    if feature is None:
        raise RuntimeError("mouth detail: source CupProfile is missing")
    sketch = _early_bound(
        _early_bound(feature, "IFeature").GetSpecificFeature2(), "ISketch"
    )
    inverse = _early_bound(sketch.ModelToSketchTransform, "IMathTransform").Inverse()
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xyz = (
        (-POCKET_DEPTH - FLOOR_HOLE_MOUTH_CHAMFER / 2.0) / 1000.0,
        (FLOOR_HOLE_DIA / 2.0 + FLOOR_HOLE_MOUTH_CHAMFER / 2.0) / 1000.0,
        0.0,
    )
    point = _early_bound(utility.CreatePoint(double_array(xyz)), "IMathPoint")
    result = tuple(
        float(v)
        for v in _early_bound(point.MultiplyTransform(inverse), "IMathPoint").ArrayData
    )
    if len(result) != 3 or not all(map(math.isfinite, result)):
        raise RuntimeError(f"mouth detail: invalid native model reference {result!r}")
    return result


def _create_mouth_detail(adapter: Any, section: Any) -> Any:
    """Enlarge the real section mouth with a persisted native circle, DETAIL B."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, section)):
        raise RuntimeError("mouth detail: cannot activate the section parent")
    draw.ClearSelection2(True)
    reference = _mouth_model_reference(adapter, section)
    center = model_point_in_view(
        adapter, section, reference, label="mouth detail centre"
    )
    radius = MOUTH_DETAIL_RADIUS_MM * VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
    sketch = _early_bound(_early_bound(section, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for xy in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array((*xy, 0.0))), "IMathPoint"
        )
        points.append(
            tuple(
                float(v)
                for v in _early_bound(
                    point.MultiplyTransform(transform), "IMathPoint"
                ).ArrayData
            )
        )
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    prior = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = prior
    if circle is None:
        raise RuntimeError("mouth detail: native circle creation failed")
    actual_center, actual_radius = native_circle_geometry(
        circle, label="mouth detail fence"
    )
    asked_radius = math.dist(points[0], points[1])
    sketch_tolerance = MOUTH_GEOMETRY_TOL_M * asked_radius / radius
    if (
        math.dist(actual_center, points[0]) > sketch_tolerance
        or abs(actual_radius - asked_radius) > sketch_tolerance
    ):
        raise RuntimeError(
            "mouth detail: native fence snapped away from its model mouth"
        )
    selection = _early_bound(draw.SelectionManager, "ISelectionMgr").CreateSelectData()
    selection.View = section
    if not _early_bound(circle, "ISketchSegment").Select4(False, selection):
        raise RuntimeError("mouth detail: native circle selection failed")
    detail = drawing.CreateDetailViewAt4(
        *MOUTH_DETAIL_CENTER,
        0.0,
        0,
        *MOUTH_DETAIL_SCALE,
        MOUTH_DETAIL_LABEL,
        1,
        False,
        False,
        True,
        5,
    )
    draw.ClearSelection2(True)
    if detail is None:
        raise RuntimeError("mouth detail: CreateDetailViewAt4 returned no view")
    detail = _early_bound(detail, "IView")
    rebuild_drawing(adapter, label="create cup mouth detail")
    # The native outline can be asymmetric for a cut corner.  Settle by the
    # ACTUAL projected model point, behind the established display barrier.
    detail.UpdateViewDisplayGeometry()
    projected = model_point_in_view(
        adapter, detail, reference, label="mouth detail placement"
    )
    position = tuple(float(v) for v in detail.Position)
    target = [position[i] + MOUTH_DETAIL_CENTER[i] - projected[i] for i in range(2)]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("mouth detail: cannot place the native crop")
    rebuild_drawing(adapter, label="place cup mouth detail")
    settle_detail_projection(
        adapter,
        detail,
        reference,
        ink_xy=MOUTH_DETAIL_CENTER,
        tolerance_xy=(MOUTH_GEOMETRY_TOL_M, MOUTH_GEOMETRY_TOL_M),
        label="cup mouth detail",
    )
    fence = _early_bound(detail.GetDetail(), "IDetailCircle")
    fence.SetLabelPosition(*MOUTH_DETAIL_LETTER)
    if (
        math.dist(
            tuple(float(v) for v in fence.GetLabelPosition()), MOUTH_DETAIL_LETTER
        )
        > 1e-6
    ):
        raise RuntimeError("mouth detail: native parent letter placement changed")
    position_section_caption(
        adapter, detail, MOUTH_DETAIL_CAPTION, label="cup mouth DETAIL B"
    )
    set_hidden_lines_removed(adapter, detail)
    _assert_mouth_detail(adapter, section, detail)
    return detail


def _assert_mouth_detail(adapter: Any, section: Any, detail: Any) -> Any:
    """Re-read the persisted circle, model centre, parent, scale and safe field."""
    detail = _early_bound(detail, "IView")
    section = _early_bound(section, "IView")
    if (
        int(detail.Type) != 3
        or int(section.Type) != 2
        or section.GetSection() is None
        or int(detail.GetDisplayMode2()) != 2
    ):
        raise RuntimeError(
            "mouth detail: not an HLR detail of actual cut section geometry"
        )
    readback = read_circular_detail_crop(adapter, detail, label="cup mouth DETAIL B")
    if (
        readback.label != MOUTH_DETAIL_LABEL
        or view_name(adapter, readback.parent) != view_name(adapter, section)
        or readback.detail_ratio != MOUTH_DETAIL_SCALE
        or readback.parent_ratio != tuple(float(v) for v in VIEW_SCALE)
    ):
        raise RuntimeError("mouth detail: native label, parent or scale changed")
    center = model_point_in_view(
        adapter,
        section,
        _mouth_model_reference(adapter, section),
        label="mouth parent readback",
    )
    radius = MOUTH_DETAIL_RADIUS_MM * VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
    if (
        math.dist(center, readback.parent_centre) > MOUTH_GEOMETRY_TOL_M
        or abs(readback.parent_radius - radius) > MOUTH_GEOMETRY_TOL_M
    ):
        raise RuntimeError(
            "mouth detail: persisted crop no longer encloses the actual model mouth"
        )
    cx = (readback.crop[0] + readback.crop[2]) / 2.0
    cy = (readback.crop[1] + readback.crop[3]) / 2.0
    if math.dist((cx, cy), MOUTH_DETAIL_CENTER) > MOUTH_GEOMETRY_TOL_M:
        raise RuntimeError("mouth detail: actual crop centre moved")
    # The new crop stays entirely in the unused lower-right corridor, above
    # the title block and below the old pocket-depth/ISO-note lanes.
    if not (
        0.290 <= readback.crop[0] < readback.crop[2] <= 0.336
        and 0.090 <= readback.crop[1] < readback.crop[3] <= 0.132
    ):
        raise RuntimeError(
            f"mouth detail: actual crop escaped its blank field: {readback.crop!r}"
        )
    fence = _early_bound(detail.GetDetail(), "IDetailCircle")
    if (
        math.dist(
            tuple(float(v) for v in fence.GetLabelPosition()), MOUTH_DETAIL_LETTER
        )
        > 1e-6
    ):
        raise RuntimeError("mouth detail: settled parent letter moved")
    return readback


def _measured_annotation_ink(
    record: dict[str, Any], label: str
) -> tuple[list[Segment], list[Box], list[str]]:
    """Decode collected primitives strictly: no anchor boxes or guessed widths."""
    strokes, boxes, errors = [], [], []
    display = record.get("display") or {}
    sizes = {
        "lines": 8,
        "arcs": 17,
        "polylines": 7,
        "polygons": 5,
        "triangles": 9,
        "arrows": 8,
    }
    if not display:
        errors.append(f"{label}: missing actual display ink")
    if not isinstance(display, dict):
        return strokes, boxes, [f"{label}: malformed actual display inventory"]
    for kind, rows in display.items():
        if kind not in (*sizes, "texts") and rows:
            errors.append(f"{label}: unsupported actual {kind} ink")
            continue
        if not isinstance(rows, (list, tuple)):
            errors.append(f"{label}: malformed actual {kind} inventory")
            continue
        for index, raw in enumerate(rows):
            try:
                if kind == "texts":
                    values = (*raw["pos"], raw["h"], raw["w"], raw["ang"])
                    if (
                        len(raw["pos"]) < 2
                        or not all(math.isfinite(float(v)) for v in values)
                        or raw["h"] <= 0
                        or raw["w"] <= 0
                    ):
                        raise ValueError("missing/nonfinite measured text bounds")
                    box = _layout_audit.display_box({"texts": [raw]})
                    if box is None:
                        raise ValueError("no actual text hull")
                    boxes.append(box)
                    continue
                values = tuple(float(v) for v in raw)
                if len(values) < sizes[kind] or not all(map(math.isfinite, values)):
                    raise ValueError("truncated/nonfinite primitive")
                if kind == "polylines":
                    count = int(values[6])
                    if count < 2 or not (
                        len(values) >= 7 + 3 * count
                        or len(values) >= 7 + int(values[1]) + 3 * count
                    ):
                        raise ValueError("truncated polyline points")
                if kind == "polygons" and (
                    int(values[4]) < 2 or len(values) < 5 + 3 * int(values[4])
                ):
                    raise ValueError("truncated polygon points")
                if kind == "arrows" and (
                    math.hypot(values[3], values[4]) <= 0
                    or values[6] <= 0
                    or values[7] <= 0
                ):
                    raise ValueError("invalid native arrow")
                decoded = _layout_audit._display_segments({kind: [values]})
                if not decoded:
                    raise ValueError("primitive decoded to no ink")
                strokes.extend(decoded)
            except (KeyError, TypeError, ValueError, OverflowError, IndexError) as exc:
                errors.append(f"{label}: unreadable actual {kind}[{index}]: {exc}")
    for index, raw in enumerate(record.get("leaders") or ()):
        try:
            values = tuple(float(v) for v in raw)
            if (
                len(values) < 6
                or len(values) % 3
                or not all(map(math.isfinite, values))
            ):
                raise ValueError("truncated/nonfinite registered leader")
            strokes.extend(
                Segment(values[i], values[i + 1], values[i + 3], values[i + 4])
                for i in range(0, len(values) - 3, 3)
            )
        except (TypeError, ValueError, OverflowError) as exc:
            errors.append(
                f"{label}: unreadable actual registered leader[{index}]: {exc}"
            )
    return strokes, boxes, errors


def _assert_mouth_annotation_ink(
    dumps: list[dict[str, Any]],
    *,
    collection_errors: tuple[str, ...] = (),
    mouth_crop: tuple[float, float, float, float] | None = None,
) -> None:
    """Gate every actual new-mouth ink conflict, retaining the old sheet lanes."""
    errors = list(collection_errors)
    required = set(DRAWING_PRECISION_BY_NAME)
    found = {name: [] for name in required}
    all_ink = []
    if not dumps:
        errors.append("no drawing sheets collected")
    for sheet in dumps:
        if sheet.get("read_errors"):
            errors.append(f"native collection errors: {sheet['read_errors']!r}")
        for record in _layout_audit.audited_annotations(
            _layout_audit.printed_dump(sheet)
        ):
            if record.get("owner_type") == 2:
                continue
            name = record.get("dimension_name", "")
            label = name or str(record.get("name") or "unnamed")
            strokes, boxes, faults = _measured_annotation_ink(record, label)
            display = record.get("display") or {}
            if not isinstance(display, dict):
                display = {}  # the strict decoder already recorded the refusal
            errors.extend(faults)
            if name in found:
                found[name].append(record)
                if record.get("owner_type") != 0 or record.get("visible") != 1:
                    errors.append(
                        f"{label}: lost native view ownership or print visibility"
                    )
                if name == "FloorHoleMouthChamfer":
                    texts = display.get("texts") or ()
                    if not isinstance(texts, (list, tuple)):
                        texts = ()  # keep collecting faults in this and later records
                    printed = " ".join(
                        " ".join(
                            str(t.get("t") or "") for t in texts if isinstance(t, dict)
                        ).split()
                    )
                    for token in (
                        f"{FLOOR_HOLE_MOUTH_CHAMFER + FLOOR_HOLE_MOUTH_CHAMFER_BAND[1]:.2f}",
                        f"{FLOOR_HOLE_MOUTH_CHAMFER + FLOOR_HOLE_MOUTH_CHAMFER_BAND[0]:.2f}",
                        FLOOR_HOLE_MOUTH_CHAMFER_SUFFIX.strip(),
                        *FLOOR_HOLE_MOUTH_CHAMFER_CALLOUT.splitlines(),
                    ):
                        if token not in printed:
                            errors.append(
                                f"{label}: actual rendered text lost {token!r}"
                            )
                if (
                    not boxes
                    or not strokes
                    or not display.get("arrows")
                    or not display.get("lines")
                ):
                    errors.append(
                        f"{label}: missing actual native text/witness/arrow inventory"
                    )
            # Every generated ink primitive, not merely the new text anchor,
            # stays within the frame and outside the unchanged title block.
            for box in [*boxes, *(stroke.box() for stroke in strokes)]:
                if not (
                    0.0127 <= box.xmin <= box.xmax <= 0.4191
                    and 0.0127 <= box.ymin <= box.ymax <= 0.2667
                ):
                    errors.append(f"{label}: actual ink outside inner border: {box!r}")
                if box.xmax > 0.216 and box.ymin < 0.070:
                    errors.append(f"{label}: actual ink enters title block: {box!r}")
            if mouth_crop is not None:
                crop = Box(*mouth_crop)
                if any(box.gap(crop) < 0.002 for box in boxes):
                    errors.append(
                        f"{label}: actual text crowds the mouth crop's model geometry"
                    )
                if name != "FloorHoleMouthChamfer" and any(
                    segment_box_distance(line, crop) < 0.002 for line in strokes
                ):
                    errors.append(
                        f"{label}: actual foreign annotation ink enters the mouth crop"
                    )
            all_ink.append((name, label, strokes, boxes))
    for name, rows in found.items():
        if len(rows) != 1:
            errors.append(
                f"{name}: expected one printed native dimension, found {len(rows)}"
            )
    mouths = [entry for entry in all_ink if entry[0] == "FloorHoleMouthChamfer"]
    for _, label, strokes, boxes in mouths:
        for other_name, other_label, other_strokes, other_boxes in all_ink:
            if other_name == "FloorHoleMouthChamfer":
                continue
            if any(a.gap(b) < 0.00357 for a in boxes for b in other_boxes):
                errors.append(f"{label} vs {other_label}: actual text blocks crowd")
            if any(
                segment_box_distance(line, box) < 0.002
                for line in strokes
                for box in other_boxes
            ):
                errors.append(
                    f"{label} vs {other_label}: actual new witness/leader/arrow crowds foreign text"
                )
            if any(
                segment_box_distance(line, box) < 0.002
                for line in other_strokes
                for box in boxes
            ):
                errors.append(
                    f"{label} vs {other_label}: actual foreign ink crowds new text"
                )
            crossing = False
            for a in strokes:
                for b in other_strokes:
                    aa = LeaderSegment(label, "dim", a.x0, a.y0, a.x1, a.y1, "")
                    bb = LeaderSegment(other_label, "dim", b.x0, b.y0, b.x1, b.y1, "")
                    if _proper_crossing(aa, bb, tol=1e-7) is not None:
                        crossing = True
                    if a.length and b.length:
                        ux, uy = (a.x1 - a.x0) / a.length, (a.y1 - a.y0) / a.length
                        near = all(
                            abs((x - a.x0) * uy - (y - a.y0) * ux) <= 0.00005
                            for x, y in ((b.x0, b.y0), (b.x1, b.y1))
                        )
                        projections = [
                            (x - a.x0) * ux + (y - a.y0) * uy
                            for x, y in ((b.x0, b.y0), (b.x1, b.y1))
                        ]
                        if (
                            near
                            and min(a.length, max(projections))
                            - max(0.0, min(projections))
                            > 0.0001
                        ):
                            crossing = True
            if crossing:
                errors.append(
                    f"{label} vs {other_label}: actual foreign leader/witness/arrow crossing"
                )
    if errors:
        raise RuntimeError(
            "MHA-DT-35 mouth annotation ink violations:\n" + "\n".join(errors)
        )


def assert_final_mouth_detail(adapter: Any, section: Any, detail: Any) -> None:
    """Collect the settled print, rather than trusting requested placements."""
    errors, dumps, crop = [], [], None
    try:
        crop = _assert_mouth_detail(adapter, section, detail).crop
    except Exception as exc:
        errors.append(f"mouth native crop readback: {exc}")
    try:
        native = _early_bound(detail, "IView")
        owned = [
            _early_bound(a, "IAnnotation")
            for a in (native.GetAnnotations() or ())
            if dimension_name(adapter, a)
        ]
        if [dimension_name(adapter, a) for a in owned] != ["FloorHoleMouthChamfer"]:
            raise RuntimeError("DETAIL B must own ONLY FloorHoleMouthChamfer")
        _assert_floor_hole_mouth_chamfer(owned[0])
    except Exception as exc:
        errors.append(f"mouth native detail/readback: {exc}")
    reader = _drawing_layout_audit._Reader(adapter)
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    try:
        rows = drawing.GetViews() or ()
        names = tuple(drawing.GetSheetNames() or ())
        if not names or len(names) != len(rows):
            errors.append("native sheet/view inventory mismatch")
    except Exception as exc:
        rows = ()
        errors.append(f"native sheet inventory: {exc}")
    for index, row in enumerate(rows):
        dump = {"sheet": str(index), "views": [], "sheet_annotations": []}
        for view_index, raw_view in enumerate(row):
            records = []
            try:
                view = _early_bound(raw_view, "IView")
                for raw in view.GetAnnotations() or ():
                    try:
                        record = _drawing_layout_audit._dump_annotation(reader, raw)
                        if record is None:
                            raise RuntimeError("unreadable native annotation")
                        if record.get("type") == 4:
                            record["dimension_name"] = dimension_name(adapter, raw)
                        records.append(record)
                    except Exception as exc:
                        errors.append(f"view[{view_index}] native annotation: {exc}")
                if view_index == 0:
                    dump["sheet_annotations"] = records
                else:
                    dump["views"].append({"annotations": records})
            except Exception as exc:
                errors.append(f"view[{view_index}] native inventory: {exc}")
        try:
            dump["layers"] = _drawing_layout_audit._layer_states(reader, dump)
        except Exception as exc:
            errors.append(f"native layer inventory: {exc}")
        dump["read_errors"] = reader.take_errors()
        dumps.append(dump)
    _assert_mouth_annotation_ink(
        dumps, collection_errors=tuple(errors), mouth_crop=crop
    )


async def _build_drawing(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-handle-butt-cup source", await adapter.open_model(str(SOURCE)))
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
            0: "Crank Handle Butt Cup Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank handle butt cup; turned plain steel cup",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    end = place_view(adapter, str(SOURCE), "*Left", *END_CENTER, scale=VIEW_SCALE)
    section = create_section_view(
        adapter,
        end,
        line_start=CUT_START,
        line_end=CUT_END,
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="butt cup longitudinal section",
    )
    position_section_caption(adapter, section, CAPTION_XY, label="butt cup")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (end, section, iso):
        set_hidden_lines_removed(adapter, view)
    detail = _create_mouth_detail(adapter, section)

    annotations = curate_view_dimensions(
        adapter,
        section,
        keep=ALL_KEEP,
        view_label="longitudinal section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Import from the real source section, then use native model-dimension
    # transfer: a free drawing dimension or numeric note is not a substitute.
    by_name = {dimension_name(adapter, a): a for a in annotations}
    mouth = move_model_dimension(
        adapter,
        by_name["FloorHoleMouthChamfer"],
        detail,
        MOUTH_DETAIL_KEEP["FloorHoleMouthChamfer"],
        source_view=section,
    )
    annotations = [
        a for a in annotations if dimension_name(adapter, a) != "FloorHoleMouthChamfer"
    ] + [mouth]
    _early_bound(mouth.GetSpecificAnnotation(), "IDisplayDimension").SetText(
        2, FLOOR_HOLE_MOUTH_CHAMFER_SUFFIX
    )
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    by_name = {dimension_name(adapter, a): a for a in annotations}
    for name in sorted(REFERENCE_DIMENSIONS):
        set_reference_dimension(
            adapter, by_name[name], label=f"MHA-DT-35 {name}", diameter=True
        )
    _dress_pocket_floor_radius(by_name["PocketFloorRadius"])
    _assert_floor_hole_mouth_chamfer(by_name["FloorHoleMouthChamfer"])
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the cup end view")
    create_section_axis_centerline(
        adapter, section, length_mm=OVERALL_LENGTH, label="butt cup axis"
    )

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_POS)
    rebuild_drawing(adapter, label="crank-handle-butt-cup layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Handle Butt Cup Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(lambda: assert_final_mouth_detail(adapter, section, detail),),
    )


async def build(adapter: Any) -> dict[str, str]:
    """Capture the still-open native drawing before propagating its refusal."""
    try:
        return await _build_drawing(adapter)
    except Exception as original:
        try:
            _seat_forensics.capture_com_failure(
                adapter,
                f"{PART_STEM}-drawing-build",
                str(original),
                api="MHA-DT-35 drawing build",
                exception=original,
                sheet_png=True,
                phase="drawing-build",
            )
        except Exception as capture_exc:  # noqa: BLE001 - retain the original refusal
            if capture_exc is not original:
                with contextlib.suppress(Exception):
                    _telemetry.warn(
                        f"MHA-DT-35 drawing secondary capture failure: {capture_exc!r}"
                    )
        raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
