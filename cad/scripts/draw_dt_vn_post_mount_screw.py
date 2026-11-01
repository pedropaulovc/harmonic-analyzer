r"""Create the modified-stock drawing for the MHA-DT-VN-61 cone pivot post mount screw.

MSC 40923906 is bought as 4 in stock and cut to length, so the sheet is a
modified-purchased-part drawing (the boss hook's pattern), not the purchased
reference sheet: a Front view carrying the cut length -- the part's hidden
reference-sketch dimension, imported at its model-owned places -- and an
isometric, both 1:1. No single length suits every in-band post and plate
(dt_vn_post_mount_screw_spec's U27 check), so the length prints as a REFERENCE
at CUT_LENGTH_MM, with no band and the cut-to-fit acceptance beneath it:
cut at assembly, end flush to the spec band's allowance short of the MHA-DT-20
underside, never proud (dt_vn_post_mount_screw_spec.CUT_TO_FIT_CALLOUT).
The cut end's break
is a deburr (Main's MHA-DT-VN-61 eye pass on #857): so small a dimension at 1:1
is illegible and a printed +0/-.003 band reads as allowing no break at all, so
the Front view carries no break dimension.  A 10:1 view of the tip carries
it instead as the single limit ".003 MAX" (the model's CutEndBreak at
swTolMAX, generated from the spec band).  CutEndBreak is a driving
dimension of the deburr cutter's profile.  The tip view is NOT a detail
view: no detail child of the Front ever offered CutEndBreak to an import
(see ``cropped_tip_view``), so it is a standalone 10:1 *Front model view,
moved to the tip and cropped to the detail's fence, that imports the break
by feature.  It reads as a detail on the sheet: a "DETAIL A  SCALE 10:1"
label owned by the view, and a circle and letter "A" on the Front at the
tip.  The Front is re-activated before the notes so they do not land in
the tip view.  The only
note says to deburr the cut end and that the
undimensioned purchased geometry is reference.  No installation sequence or rule number is
printed: the sequence is an MHA-DT-00 assembly step (Main's eye pass of
warm-c486, drawing-guidelines.md rule 7 (notes: few, flagged, never a method)).  The engagement minimum prints as a plain fact,
"ENGAGEMENT 0.90D MIN", on the cut-length callout's last line, never in a
note; the spec's asserts still guard its value.

The separate supplier maximum-limit sheet is a construction-only source
diagram, not a correction of the installed MSC solid (deferred in issue 1806).
Its coordinates belong to the source model sketch, not model XYZ or the
drawing crop sketch. Map them through the inverse model-to-sketch transform,
then measure and turn the projected axial direction onto sheet +X before
centering, cropping or importing dimensions. The intended fixed 2:1 full
profile is horizontal in its reserved cell and the 6:1 head uses the same
frame. A native PNG and source-vertex readback proved that the zero-body
view's GetOutline is not its displayed construction-ink extent. Before final
settling, capture canonical native geometry and frame probes in the actual
supplier configuration, then restore the original source configuration. Final
guards project only that immutable capture through the current native view and
retain native model-dimension association, crop, annotation and note checks.
The source is opened read-only and stays clean through preparation and capture.
Imported presentation runs afterwards: it can mark the source dirty, but never
authorizes writing it. Native read-only/path checks and a persisted SHA-256
witness bracket final drawing/PDF save, including errors.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_vn_post_mount_screw.py dt-vn-post-mount-screw
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
from pathlib import Path
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    curate_dimensions,
    iter_views,
    view_name,
)

from _com import _bind, _early_bound
from _dimensions import _feature_display_dimensions
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
import _drawing_dimension_import
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
import _drawing_hidden_sketches as hidden_sketches
from _drawing_detail_crop import native_circle_geometry, _transform_point
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME, DRAWING_TEMPLATES
from _part_properties import part_drawing_unit
from _drawing_view_display import set_hidden_lines_removed
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_sheet_region import sheet_drawable_region
from _layout_geometry import Box, estimate_text_box
from _purchased_fastener_drawing import (
    _box,
    _inside,
    _literal_note,
    assert_supplier_annotations_fit,
    _open_supplier_source_read_only,
    _source_file_sha256,
)
from _rebuild import active_configuration_name
from _session import run_build
import _seat_forensics
from _stock_trim_drawing import TrimSheet
import _telemetry
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_reference_geometry import (
    NativeSketchGeometry,
    capture_native_sketch_geometry,
    native_sketch_view_bounds,
)
from _supplier_screw_dimensions import _assert_dimension_source
from _visibility import visible_reference_geometry
from dt_vn_post_mount_screw_spec import (
    CUT_END_BREAK_DIMENSION,
    CUT_END_BREAK_BAND,
    CUT_END_BREAK_SKETCH,
    CUT_END_BREAK_MAX_MM,
    CUT_END_BREAK_TEXT,
    inch_text,
    CUT_END_BREAK_TOL_TYPE,
    CUT_LENGTH_DIMENSION,
    CUT_LENGTH_MM,
    CUT_LENGTH_SKETCH,
    CUT_TO_FIT_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FRONT_VIEW_DIMENSIONS,
    HEAD_H_MM,
    SKU,
    SUPPLIER_PRECISION,
    SUPPLIER_PROFILE_DIMENSIONS,
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_PROFILE_MM,
    SUPPLIER_PROFILE_SECTIONS,
    SUPPLIER_STOCK_CONFIGURATION,
    SUPPLIER_STOCK_DIMENSIONS,
    SUPPLIER_STOCK_FEATURE,
    SUPPLIER_STOCK_TITLE,
    SUPPLIER_THREAD_MAJOR_DIMENSION,
    THREAD_DIA_MM,
)

SPEC = DRAWINGS_BY_NAME["dt_vn_post_mount_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
TITLE = "Cone Pivot Post Mount Screw — Modified Stock Drawing"
DRAWING_SUMMARY = {
    0: TITLE,
    1: "Manufacturing controls for modified purchased stock",
    2: "Harmonic Analyzer Project",
    3: f"MHA-DT-VN-61; MSC Industrial Supply {SKU}",
    4: "Native dimension-driven cut length",
}

SHEET_SCALE = (1.0, 1.0)
# The screw stands head up in the Front view: under-head face at model y 0,
# cut end at -CUT_LENGTH_MM, head top ~6 above.
FRONT_CENTER = (0.100, 0.165)
ISO_CENTER = (0.270, 0.185)
# The cut length reads on the left, where its reference line runs along the
# shank's silhouette, midway along the span, far enough out that its
# five-line acceptance callout (22 capitals at its widest) clears the head
# and stays inside the border.
# The cut end's break is not dimensioned in this 1:1 view (see the module
# docstring).  (The view is placed by its outline's centre: the end face is
# half the screw's overall height below it.)
TIP_Y = FRONT_CENTER[1] - (CUT_LENGTH_MM + HEAD_H_MM) / 2000.0
FRONT_KEEP = {
    CUT_LENGTH_DIMENSION: (FRONT_CENTER[0] - 0.047, FRONT_CENTER[1]),
}
DIMENSION_CALLOUTS = {CUT_LENGTH_DIMENSION: CUT_TO_FIT_CALLOUT}

# The 20:1 tip view (a cropped model view that reads as detail A): its crop
# centres on the axis 0.5 mm above the cut end with a 3.48 mm fence, so both
# ends of the break's radial leg (r 3.099 and 3.175 on the end face) sit
# inside the crop -- a cropped view drops any dimension whose reference lies
# outside it.  At 20:1 the .003 break is 1.5 mm on paper, so its extension
# lines visibly land on the break's two edges (10:1 left them 0.76 mm apart,
# reading as landing on nothing).  It sits between the Front view and the
# isometric, above the note block and clear of the title block.  TIP_DETAIL
# keeps the sheet constants: the crop fence, the label's place and the Front
# letter's offset.
DETAIL_SCALE = (20.0, 1.0)
DETAIL_FENCE_MM = 3.48
DETAIL_OFFSET_MM = 0.5
# A sheet circle (the tip crop fence, the Front's tip mark) must land within
# this of its ask, in sheet metres; a snapped circle misses by a millimetre.
CIRCLE_TOL_M = 0.00005
DETAIL_CENTER = (0.185, 0.192)
DETAIL_RADIUS = DETAIL_FENCE_MM * DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
TIP_DETAIL = TrimSheet(
    sheet_scale=SHEET_SCALE,
    detail_center=DETAIL_CENTER,
    detail_scale=DETAIL_SCALE,
    fence_radius_mm=DETAIL_FENCE_MM,
    cut_end_y_mm=-CUT_LENGTH_MM,
    detail_offset_mm=DETAIL_OFFSET_MM,
    detail_label_xy=(
        DETAIL_CENTER[0] - 0.020,
        DETAIL_CENTER[1] - DETAIL_RADIUS - 0.007,
    ),
    parent_letter_offset=(0.008, 0.006),
)
TIP_LETTER = "A"
TIP_VIEW_LABEL = (
    f"DETAIL {TIP_LETTER}  SCALE {DETAIL_SCALE[0]:g}:{DETAIL_SCALE[1]:g}"
)
_CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
# The tip reference must land within 0.1 mm of DETAIL_CENTER after the move:
# draw_cylinder_gear's notch-detail outline-centre tolerance.
TIP_VIEW_POSITION_TOLERANCE_M = 1e-4


def _detail_point(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet position of a Front-view model point inside the tip view."""
    ratio = DETAIL_SCALE[0] / DETAIL_SCALE[1]
    ref_y = -CUT_LENGTH_MM + DETAIL_OFFSET_MM
    return (
        DETAIL_CENTER[0] + ratio * x_mm / 1000.0,
        DETAIL_CENTER[1] + ratio * (y_mm - ref_y) / 1000.0,
    )


# The break's text sits below the end face, under the right-hand rim.
BREAK_RIM_XY = _detail_point(THREAD_DIA_MM / 2.0, -CUT_LENGTH_MM)
DETAIL_KEEP = {
    CUT_END_BREAK_DIMENSION: (BREAK_RIM_XY[0] - 0.006, BREAK_RIM_XY[1] - 0.012)
}
FRONT_PRECISION = {
    CUT_LENGTH_DIMENSION: DRAWING_PRECISION_BY_NAME[CUT_LENGTH_DIMENSION]
}
DETAIL_PRECISION = {
    CUT_END_BREAK_DIMENSION: DRAWING_PRECISION_BY_NAME[CUT_END_BREAK_DIMENSION]
}
# Below the Front view (its lower end ~0.119), above the stock rows.
NOTES_XY = (0.016, 0.100)
STOCK_ROWS = (
    ("Supplier", 0.016, 0.060),
    ("Supplier SKUs", 0.080, 0.060),
    ("Stock Name", 0.016, 0.049),
)

SHEET_NAMES = ("FINISHED", "SUPPLIER-MAX-ENVELOPE")
STOCK_SCALE = (2.0, 1.0)
STOCK_CENTER = (0.235, 0.110)
STOCK_KEEP = {
    "SupplierStockLength": (0.235, 0.083),
    "SupplierThreadLength": (0.303, 0.151),
    # Right of the screw end's extension line (x ~0.343) and below the major's
    # own extension lines, so its dimension line stops short of the text.
    "SupplierThreadMajor": (0.366, 0.094),
}
STOCK_HEAD_SCALE = (6.0, 1.0)
STOCK_HEAD_CENTER = (0.100, 0.200)
STOCK_HEAD_RADIUS_MM = 8.5
STOCK_HEAD_KEEP = {
    "SupplierHeadOD": (0.035, 0.200),
    "SupplierHeadHeight": (0.100, 0.257),
    "SupplierStraightSkirt": (0.108, 0.149),  # Keep lower limit ink above the caption cell.
    "SupplierSlotWidth": (0.170, 0.200),
    "SupplierSlotDepth": (0.095, 0.237),
}
# Fixed source scales and reserved ink cells, not a post-dimension rescale.
STOCK_VIEW_CELL = (0.115, 0.073, 0.410, 0.177)
STOCK_HEAD_CELL = (0.018, 0.142, 0.193, 0.264)
STOCK_NOTES = (
    (SUPPLIER_STOCK_TITLE, 0.200, 0.258, (0.195, 0.247, 0.415, 0.264)),
    (
        f"SLOT-PLANE HEAD ENVELOPE  SCALE {STOCK_HEAD_SCALE[0]:g}:{STOCK_HEAD_SCALE[1]:g}",
        0.030, 0.139, (0.018, 0.128, 0.193, 0.142),
    ),
    (
        f"FULL SOURCE-STOCK ENVELOPE  SCALE {STOCK_SCALE[0]:g}:{STOCK_SCALE[1]:g}",
        0.200, 0.187, (0.195, 0.178, 0.410, 0.190),
    ),
)


def _supplier_contract(row) -> dict[str, Any]:
    return dict(
        label=row.name, expected_mm=row.expected_mm,
        units="in", precision=SUPPLIER_PRECISION, presentation=row.presentation,
        callout=row.callout, configuration=SUPPLIER_STOCK_CONFIGURATION,
    )


def _supplier_points_match(actual, expected, *, tolerance):
    """Unique within-tolerance matching; raw float ordering is not identity."""
    remaining = list(expected)
    if len(actual) != len(remaining):
        return False
    for point in actual:
        if len(point) != 3 or not all(math.isfinite(value) for value in point):
            return False
        matches = [
            index
            for index, target in enumerate(remaining)
            if math.dist(point, target) <= tolerance
        ]
        if len(matches) != 1:
            return False
        remaining.pop(matches[0])
    return not remaining


def _supplier_lines_match(actual, expected):
    """Match the entire native line inventory without endpoint ordering."""
    remaining = list(expected)
    if len(actual) != len(remaining):
        return False
    for pair in actual:
        matches = [
            index
            for index, targets in enumerate(remaining)
            if _supplier_points_match(pair, targets, tolerance=1e-8)
        ]
        if len(matches) != 1:
            return False
        remaining.pop(matches[0])
    return not remaining


def assert_supplier_profile_state(
    row, *, qualified_name, native_type, driven_state, tolerance_type,
    tolerance_band_mm, tolerance_precision,
) -> None:
    """Check current native source ownership, type and limit metadata."""
    if (
        str(qualified_name).split("@")[:2] != [row.name, SUPPLIER_STOCK_FEATURE]
        or native_type != row.native_type
        or driven_state != 1
    ):
        raise RuntimeError(f"{row.name}: native source profile ownership/type changed")
    band = row.deviations_mm
    if tolerance_type != (0 if band is None else 3):
        raise RuntimeError(f"{row.name}: native supplier limit type changed")
    if tolerance_precision != SUPPLIER_PRECISION:
        raise RuntimeError(f"{row.name}: supplier limit precision changed")
    expected_band = (0.0, 0.0) if band is None else band
    if len(tolerance_band_mm) != 2 or any(
        not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-8)
        for actual, expected in zip(tolerance_band_mm, expected_band, strict=True)
    ):
        raise RuntimeError(f"{row.name}: native supplier limit band changed")


def _assert_supplier_profile_vertices(row, attachment_points_mm):
    """Validate actual source-dimension points only while Supplier is active."""
    expected = [(*SUPPLIER_PROFILE_MM[index], 0.0) for index in row.vertices]
    if not _supplier_points_match(attachment_points_mm, expected, tolerance=1e-5):
        raise RuntimeError(f"{row.name}: native dimension left its source-diagram vertices")


def _supplier_profile_model_points(adapter, view, *, crop_head, label):
    """Map source-sketch origin, axes and semantic center into model metres."""
    referenced = _early_bound(view, "IView").ReferencedDocument
    if referenced is None:
        raise RuntimeError(f"{label}: supplier view has no referenced source model")
    source = _early_bound(referenced, "IPartDoc").FeatureByName(SUPPLIER_STOCK_FEATURE)
    if source is None:
        raise RuntimeError(f"{label}: supplier source profile is missing")
    sketch = _early_bound(
        _early_bound(source, "IFeature").GetSpecificFeature2(), "ISketch",
    )
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform").Inverse()
    if transform is None:
        raise RuntimeError(f"{label}: source sketch-to-model transform is unavailable")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    head_height = next(
        row.expected_mm for row in SUPPLIER_PROFILE_DIMENSIONS
        if row.name == "SupplierHeadHeight"
    )
    stock_length = next(
        row.expected_mm for row in SUPPLIER_PROFILE_DIMENSIONS
        if row.name == "SupplierStockLength"
    )
    center_x = -head_height / 2.0 if crop_head else (stock_length - head_height) / 2.0
    coordinates_mm = (
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
        (center_x, 0.0, 0.0),
    )
    model_points = []
    for coordinates in coordinates_mm:
        metres = tuple(value / 1000.0 for value in coordinates)
        raw = utility.CreatePoint(double_array(list(metres)))
        if raw is None:
            raise RuntimeError(f"{label}: cannot create supplier source point")
        point = _early_bound(raw, "IMathPoint")
        created = tuple(float(value) for value in point.ArrayData)
        if len(created) != 3 or any(
            not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12)
            for actual, expected in zip(created, metres, strict=True)
        ):
            raise RuntimeError(f"{label}: supplier source point marshaling changed")
        mapped = point.MultiplyTransform(transform)
        if mapped is None:
            raise RuntimeError(f"{label}: cannot map supplier source point to model")
        coordinates = tuple(
            float(value) for value in _early_bound(mapped, "IMathPoint").ArrayData
        )
        if len(coordinates) != 3 or not all(math.isfinite(value) for value in coordinates):
            raise RuntimeError(f"{label}: supplier source model point is invalid")
        model_points.append(coordinates)
    return tuple(model_points)


def _log_supplier_view_state(adapter, view, *, stage, geometry=False):
    """Read only: retain native evidence even when the next strict guard fails.

    GetOutline is a sheet-space box, not proof that the source sketch's
    projected axes describe all displayed geometry. Do not rebuild/refresh
    here: before/after snapshots must observe the operation being diagnosed.
    Diagnostic read errors are explicit and never replace the original guard.
    """
    view = _early_bound(view, "IView")

    def emit(field, read_value):
        try:
            value = read_value()
        except Exception as exc:
            value = {"read_error": f"{type(exc).__name__}: {exc}"}
        _telemetry.info(f"MSC native {stage} {field}={value!r}")

    def pose():
        return {
            "view": view_name(adapter, view),
            "configuration": str(view.ReferencedConfiguration),
            "use_sheet_scale": int(view.UseSheetScale),
            "scale": tuple(float(value) for value in view.ScaleRatio),
            "angle_rad": float(view.Angle),
            "position_m": tuple(float(value) for value in view.Position),
            "outline_m": tuple(float(value) for value in view.GetOutline()),
            "cropped": bool(view.IsCropped()),
        }

    emit("pose", pose)
    emit("model_to_view", lambda: tuple(
        float(value) for value in
        _early_bound(view.ModelToViewTransform, "IMathTransform").ArrayData
    ))
    if not geometry:
        return

    def source_geometry():
        referenced = _early_bound(view.ReferencedDocument, "IModelDoc2")
        feature = _early_bound(
            _early_bound(view.ReferencedDocument, "IPartDoc").FeatureByName(
                SUPPLIER_STOCK_FEATURE,
            ), "IFeature",
        )
        sketch = _early_bound(feature.GetSpecificFeature2(), "ISketch")
        transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
        inverse = transform.Inverse()
        utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
        local = []
        model = []
        for raw in sketch.GetSketchPoints2() or ():
            point = _early_bound(raw, "ISketchPoint")
            xyz = tuple(float(value) for value in (point.X, point.Y, point.Z))
            local.append(xyz)
            native = _early_bound(utility.CreatePoint(double_array(list(xyz))), "IMathPoint")
            model.append(tuple(float(value) for value in
                _early_bound(native.MultiplyTransform(inverse), "IMathPoint").ArrayData))
        projected = model_points_in_view(adapter, view, model, label=f"MSC native {stage}")
        segments = []
        for raw in sketch.GetSketchSegments() or ():
            segment = _early_bound(raw, "ISketchSegment")
            row = {"type": int(segment.GetType()), "construction": bool(segment.ConstructionGeometry)}
            if row["type"] == 0:  # swSketchLINE; endpoints remain in SOURCE sketch metres.
                line = _early_bound(raw, "ISketchLine")
                endpoints = []
                for raw_point in (line.GetStartPoint2(), line.GetEndPoint2()):
                    point = _early_bound(raw_point, "ISketchPoint")
                    endpoints.append(tuple(float(value) for value in (point.X, point.Y, point.Z)))
                row["endpoints_m"] = endpoints
            segments.append(row)
        return {
            "view": view_name(adapter, view),
            "source_path": str(referenced.GetPathName()),
            "source_active_configuration": str(_early_bound(
                _early_bound(referenced.ConfigurationManager, "IConfigurationManager").ActiveConfiguration,
                "IConfiguration",
            ).Name),
            "source_feature_visible": int(feature.Visible),
            "model_to_source_sketch": tuple(float(value) for value in transform.ArrayData),
            "source_points_m": local,
            "model_points_m": model,
            "sheet_points_m": projected,
            "sheet_vertex_bounds_m": (
                min(point[0] for point in projected), min(point[1] for point in projected),
                max(point[0] for point in projected), max(point[1] for point in projected),
            ) if projected else None,
            "segments": segments,
        }

    emit("source_geometry", source_geometry)
    # Source visibility is NOT the per-view UnblankSketch override. Retain
    # both this inventory and the failed native sheet rather than conflate them.
    emit("source_shown_references", lambda: visible_reference_geometry(
        view.ReferencedDocument, f"MSC native {stage}",
    ))
    emit("sheet_to_view_sketch", lambda: tuple(float(value) for value in _early_bound(
        _early_bound(view.GetSketch(), "ISketch").ModelToSketchTransform, "IMathTransform",
    ).ArrayData))


def _assert_supplier_profile_frame(
    adapter, view, center, scale, *, points, label,
):
    """Project captured native source probes through the current view frame."""
    # Rebuild does not guarantee Windows has repainted a moved view. Refresh
    # before reading ModelToViewTransform, including the first post-move proof.
    _early_bound(view, "IView").UpdateViewDisplayGeometry()
    origin, axial, radial, actual_center = model_points_in_view(
        adapter, view, points, label=label,
    )
    east = tuple(axial[index] - origin[index] for index in range(2))
    up = tuple(radial[index] - origin[index] for index in range(2))
    millimetre = scale[0] / scale[1] / 1000.0
    _telemetry.info(
        f"MSC native frame view={view_name(adapter, view)!r} label={label!r} "
        f"model_probes_m={points!r} origin_m={origin!r} axial_delta_m={east!r} "
        f"radial_delta_m={up!r} center_m={actual_center!r} "
        f"expected_center_m={center!r} expected_axis_m={millimetre!r}"
    )
    for actual, expected in ((east, (millimetre, 0.0)), (up, (0.0, millimetre))):
        if any(
            not math.isclose(value, target, rel_tol=0.0, abs_tol=1e-8)
            for value, target in zip(actual, expected, strict=True)
        ):
            raise RuntimeError(f"{label}: supplier source axes lost their horizontal frame")
    if any(
        not math.isclose(value, target, rel_tol=0.0, abs_tol=1e-8)
        for value, target in zip(actual_center, center, strict=True)
    ):
        raise RuntimeError(f"{label}: supplier source center moved from {center!r}")


def _supplier_stock_view(adapter, *, center, scale, label, crop_head=False):
    """Reveal, orient and center the source sketch before crop or annotations."""
    stock = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *center), "IView",
    )
    _log_supplier_view_state(adapter, stock, stage=f"{label}: placed")
    stock.ReferencedConfiguration = SUPPLIER_STOCK_CONFIGURATION
    if str(stock.ReferencedConfiguration) != SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError(f"{label}: cannot select supplier source configuration")
    set_hidden_lines_removed(adapter, stock)
    _log_supplier_view_state(adapter, stock, stage=f"{label}: configured HLR")
    shown = hidden_sketches._show_hidden_owners(
        adapter, stock, (SUPPLIER_STOCK_FEATURE,), view_label=label,
    )
    if set(shown) != {SUPPLIER_STOCK_FEATURE}:
        raise RuntimeError(f"{label}: supplier profile is not saved hidden")
    _log_supplier_view_state(adapter, stock, stage=f"{label}: revealed before rebuild")
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError(f"{label}: cannot rebuild revealed supplier profile")
    _log_supplier_view_state(adapter, stock, stage=f"{label}: before scale")
    stock.UseSheetScale = 0
    stock.ScaleRatio = double_array([float(value) for value in scale])
    _log_supplier_view_state(adapter, stock, stage=f"{label}: scale assigned")
    if (
        int(stock.UseSheetScale) != 0
        or tuple(float(value) for value in stock.ScaleRatio) != scale
    ):
        raise RuntimeError(f"{label}: supplier view did not retain its independent scale")
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError(f"{label}: cannot rebuild scaled supplier profile")
    _log_supplier_view_state(adapter, stock, stage=f"{label}: scaled before refresh")
    stock.UpdateViewDisplayGeometry()
    _log_supplier_view_state(adapter, stock, stage=f"{label}: scaled after refresh")
    _box(stock.GetOutline(), label=f"{label} revealed source profile")
    points = _supplier_profile_model_points(
        adapter, stock, crop_head=crop_head, label=label,
    )
    origin, axial, _radial, _source_center = model_points_in_view(
        adapter, stock, points, label=label,
    )
    dx, dy = axial[0] - origin[0], axial[1] - origin[1]
    if not all(math.isfinite(value) for value in (dx, dy)) or math.hypot(dx, dy) < 1e-9:
        raise RuntimeError(f"{label}: supplier source axis has no sheet projection")
    # The named Front need not share the source sketch's local axial frame.
    # Turn its measured direction, not an assumed model axis or quarter-turn.
    stock.Angle = float(stock.Angle) - math.atan2(dy, dx)
    _log_supplier_view_state(adapter, stock, stage=f"{label}: angle assigned")
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError(f"{label}: cannot rebuild horizontal supplier profile")
    _log_supplier_view_state(adapter, stock, stage=f"{label}: rotated before refresh")
    stock.UpdateViewDisplayGeometry()
    _log_supplier_view_state(adapter, stock, stage=f"{label}: rotated after refresh")
    projected = model_points_in_view(adapter, stock, points, label=label)[3]
    position = tuple(float(value) for value in stock.Position)
    if not stock.SetViewPosition(double_array([
        position[index] + center[index] - projected[index] for index in range(2)
    ]), False):
        raise RuntimeError(f"{label}: cannot position complete source profile")
    _log_supplier_view_state(adapter, stock, stage=f"{label}: position assigned")
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError(f"{label}: cannot rebuild positioned source profile")
    _log_supplier_view_state(adapter, stock, stage=f"{label}: positioned before refresh")
    _assert_supplier_profile_frame(
        adapter, stock, center, scale, points=_supplier_profile_model_points(
            adapter, stock, crop_head=crop_head, label=label,
        ), label=label,
    )
    _log_supplier_view_state(adapter, stock, stage=f"{label}: prepared", geometry=True)
    if crop_head:
        _activate(adapter, stock, label=label)
        circle = _sketch_circle(
            adapter, stock, center, STOCK_HEAD_RADIUS_MM * scale[0] / scale[1] / 1000.0,
            label="supplier head bounding profile crop",
        )
        _assert_supplier_crop_circle(adapter, stock, circle, STOCK_HEAD_CELL)
        status = int(stock.Crop2(False, True, 5))
        adapter.currentModel.ClearSelection2(True)
        if not adapter.currentModel.EditRebuild3():
            raise RuntimeError("cannot rebuild cropped source head profile")
        if status != _CROP_NO_ERROR or not bool(stock.IsCropped()):
            raise RuntimeError(f"source head profile crop failed ({status})")
        _log_supplier_view_state(adapter, stock, stage=f"{label}: cropped", geometry=True)
    return stock


def _present_supplier_stock_view(adapter, stock, *, keep, label):
    """Dress imported references only after clean immutable source capture."""
    annotations = hidden_sketches.curate_view_dimensions(
        adapter, stock, keep=keep, view_label=label,
        dimensions_by_feature=SUPPLIER_STOCK_DIMENSIONS,
    )
    annotations = curate_dimensions(adapter, annotations, reposition=keep)
    by_name = {row.name: row for row in SUPPLIER_REFERENCE_DIMENSIONS}
    for annotation in annotations:
        row = by_name[dimension_name(adapter, annotation)]
        supplier_reference_dimension(
            adapter, annotation.GetSpecificAnnotation(), **_supplier_contract(row),
        )
    _log_supplier_view_state(adapter, stock, stage=f"{label}: imported")


def _supplier_stock_sheet(adapter):
    full = _supplier_stock_view(
        adapter, center=STOCK_CENTER, scale=STOCK_SCALE,
        label="source full stock and factory thread",
    )
    head = _supplier_stock_view(
        adapter, center=STOCK_HEAD_CENTER, scale=STOCK_HEAD_SCALE,
        label="source head slot-plane bounding profile", crop_head=True,
    )
    _log_supplier_view_state(adapter, full, stage="full after head creation", geometry=True)
    return full, head


def _present_supplier_stock_sheet(adapter, full, head):
    _present_supplier_stock_view(
        adapter,
        full,
        keep=STOCK_KEEP,
        label="source full stock and factory thread",
    )
    _present_supplier_stock_view(
        adapter,
        head,
        keep=STOCK_HEAD_KEEP,
        label="source head slot-plane bounding profile",
    )
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    # ActivateView("") returns False for sheet context; require native context.
    ddoc.ActivateView("")
    if ddoc.GetEditSheet() is not True or ddoc.ActiveDrawingView is not None:
        raise RuntimeError("cannot activate source sheet for its labels")
    notes = []
    for text, x, y, cell in STOCK_NOTES:
        note = _literal_note(adapter, text, x, y)
        if int(_early_bound(note.GetAnnotation(), "IAnnotation").OwnerType) != 1:
            raise RuntimeError("source envelope label is not sheet-owned")
        notes.append((note, text, cell))
    return notes


def _assert_supplier_feature_valid(feature, *, label):
    """Refuse a sketch whose native segment inventory may be incomplete."""
    if feature is None:
        raise RuntimeError(f"{label}: missing supplier sketch feature")
    error = feature.GetErrorCode2()
    _telemetry.info(f"{label}: source_sketch_feature_error={error!r}")
    # The warning out-parameter is undefined for zero; only the integer return
    # proves success. GetSketchSegments can omit entities when a sketch errs.
    if (
        not isinstance(error, (tuple, list))
        or len(error) != 2
        or type(error[0]) is not int
        or error[0] != 0
    ):
        raise RuntimeError(
            f"{label}: supplier sketch feature error/unreadable status {error!r}"
        )


def _assert_supplier_crop_circle(adapter, view, circle, cell):
    """Check the actual selected circle before Crop2 consumes its profile."""
    label = f"MSC source crop {view_name(adapter, view)}"
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    centre, radius = native_circle_geometry(circle, label=label)
    inverse = _early_bound(sketch.ModelToSketchTransform, "IMathTransform").Inverse()
    if inverse is None:
        raise RuntimeError(f"{label}: crop sketch inverse is unavailable")
    sheet = [
        _transform_point(utility, point, inverse, label=label)
        for point in (
            centre,
            (centre[0] + radius, centre[1], centre[2]),
            (centre[0], centre[1] + radius, centre[2]),
        )
    ]
    cx, cy, _cz = sheet[0]
    dx = tuple(sheet[1][index] - sheet[0][index] for index in range(2))
    dy = tuple(sheet[2][index] - sheet[0][index] for index in range(2))
    rx, ry = math.hypot(*dx), math.hypot(*dy)
    expected_radius = (
        STOCK_HEAD_RADIUS_MM * STOCK_HEAD_SCALE[0] / STOCK_HEAD_SCALE[1] / 1000.0
    )
    if (
        any(abs(point[2]) > CIRCLE_TOL_M for point in sheet)
        or math.dist((cx, cy), STOCK_HEAD_CENTER) > CIRCLE_TOL_M
        or abs(rx - expected_radius) > CIRCLE_TOL_M
        or abs(ry - expected_radius) > CIRCLE_TOL_M
        or abs(dx[0] * dy[0] + dx[1] * dy[1]) > expected_radius**2 * 1e-8
    ):
        raise RuntimeError(f"{label}: crop frame changed: {sheet!r}")
    width, height = math.hypot(dx[0], dy[0]), math.hypot(dx[1], dy[1])
    bounds = (cx - width, cy - height, cx + width, cy + height)
    _telemetry.info(f"{label}: native_crop_bounds_m={bounds!r} cell_m={cell!r}")
    if not _inside(bounds, cell):
        raise RuntimeError(f"{label}: native source ink leaves its cell: {bounds!r}")


def _assert_supplier_profile_ink(adapter, view, cell, geometry, *, cropped):
    """Bound the verified native construction ink, not the model-view extent.

    a27's native PNG and vertex readbacks show the horizontal source profile
    while GetOutline retains a vertical extent from before the configuration
    switch. That extent is still logged; it is not a sketch-ink measurement.
    This path is restricted to the exact zero-body MSC source configuration.
    Presentation uses the existing view-scoped show/import path; corresponding
    IFeature.Visible is not a proven receipt of drawing-view visibility.
    """
    label = f"MSC source ink {view_name(adapter, view)}"
    view = _early_bound(view, "IView")
    if str(view.ReferencedConfiguration) != SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError(f"{label}: wrong source configuration")
    if cropped:
        # Crop2 consumes the selected profile. Its geometry was checked before
        # that call; GetSketch need not retain it as drawing-sketch segments.
        # Settled frame/binding and annotation checks remain caller-owned.
        if not bool(view.IsCropped()):
            raise RuntimeError(f"{label}: source head profile is no longer cropped")
        return
    drawing_sketch = _early_bound(view.GetSketch(), "ISketch")
    drawing_segments = tuple(drawing_sketch.GetSketchSegments() or ())
    drawing_types = [
        int(_early_bound(segment, "ISketchSegment").GetType())
        for segment in drawing_segments
    ]
    _telemetry.info(
        f"{label}: drawing_sketch_segment_count={len(drawing_segments)} "
        f"drawing_sketch_segment_types={drawing_types!r} cropped={bool(view.IsCropped())}"
    )
    if drawing_segments:
        raise RuntimeError(f"{label}: full view has unexpected drawing-sketch geometry")
    view.UpdateViewDisplayGeometry()
    bounds = native_sketch_view_bounds(adapter, view, geometry, label=label)
    _telemetry.info(f"{label}: native_ink_bounds_m={bounds!r} cell_m={cell!r}")
    if not _inside(bounds, cell):
        raise RuntimeError(f"{label}: native source ink leaves its cell: {bounds!r}")


@dataclass(frozen=True)
class SupplierStockCapture:
    """Actual Supplier geometry and model-metre probes; never live COM handles."""

    geometry: NativeSketchGeometry
    full_frame: tuple[tuple[float, float, float], ...]
    head_frame: tuple[tuple[float, float, float], ...]
    source_path: str


def _capture_supplier_stock(adapter, model, full, head):
    """Prove canonical source ink and dimensions in the active target config."""
    label = f"MSC source geometry {SUPPLIER_STOCK_CONFIGURATION!r}"
    feature = _early_bound(
        _early_bound(model, "IPartDoc").FeatureByName(SUPPLIER_STOCK_FEATURE),
        "IFeature",
    )
    _assert_supplier_feature_valid(feature, label=label)
    sketch = _early_bound(feature.GetSpecificFeature2(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    if transform is None:
        raise RuntimeError(f"{label}: missing sketch transform")
    frame = tuple(float(value) for value in transform.ArrayData)
    inventory = []
    segments = tuple(sketch.GetSketchSegments() or ())
    for raw in segments:
        segment = _early_bound(raw, "ISketchSegment")
        kind = int(segment.GetType())
        construction = bool(segment.ConstructionGeometry)
        pair = None
        if kind == 0:
            line = _early_bound(raw, "ISketchLine")
            points = [
                _early_bound(point, "ISketchPoint")
                for point in (line.GetStartPoint2(), line.GetEndPoint2())
            ]
            pair = tuple(
                tuple(float(value) for value in (point.X, point.Y, point.Z))
                for point in points
            )
        inventory.append((kind, construction, pair))
    _telemetry.info(
        f"MSC configured source geometry configuration={SUPPLIER_STOCK_CONFIGURATION!r} "
        f"ModelToSketchTransform={frame!r} native_line_inventory={inventory!r}"
    )
    if len(frame) != 16 or not all(math.isfinite(value) for value in frame[:13]):
        raise RuntimeError(f"{label}: malformed sketch transform")
    expected = [
        (SUPPLIER_PROFILE_MM[index], SUPPLIER_PROFILE_MM[(index + 1) % len(SUPPLIER_PROFILE_MM)])
        for index in range(len(SUPPLIER_PROFILE_MM))
    ] + [(SUPPLIER_PROFILE_MM[first], SUPPLIER_PROFILE_MM[last]) for first, last in SUPPLIER_PROFILE_SECTIONS]
    expected = [
        tuple((point[0] / 1000.0, point[1] / 1000.0, 0.0) for point in pair)
        for pair in expected
    ]
    if any(
        kind != 0 or not construction or pair is None
        or not all(math.isfinite(value) for point in pair for value in point)
        for kind, construction, pair in inventory
    ) or not _supplier_lines_match([pair for _, _, pair in inventory], expected):
        raise RuntimeError(f"{label}: invalid native line inventory/endpoints")
    for segment in segments:
        if _early_bound(full, "IView").GetCorresponding(segment) is None:
            raise RuntimeError(f"{label}: source segment has no drawing correspondence")

    # Source annotation points are in the actual target source sketch. Drawing
    # point IDs, drawing XYZ and raw cross-context sketch identity are NOT proof.
    rows = {row.name: row for row in SUPPLIER_REFERENCE_DIMENSIONS}
    found = []
    for raw in _feature_display_dimensions(feature):
        display = _early_bound(_bind(raw, "IDisplayDimension"), "IDisplayDimension")
        native = _early_bound(display.GetDimension2(0), "IDimension")
        owner = str(native.FullName).split("@")
        if len(owner) < 2 or owner[1] != SUPPLIER_STOCK_FEATURE or owner[0] not in rows:
            continue
        name = owner[0]
        source_dimension = model.Parameter(f"{name}@{SUPPLIER_STOCK_FEATURE}")
        if source_dimension is None or int(adapter.swApp.IsSame(native, source_dimension)) != 1:
            raise RuntimeError(f"{name}: source feature dimension identity changed")
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        kinds = tuple(int(value) for value in (annotation.GetAttachedEntityTypes() or ()))
        entities = tuple(annotation.GetAttachedEntities3() or ())
        if len(entities) != 2 or len(kinds) != 2 or any(kind not in (11, 25) for kind in kinds):
            raise RuntimeError(f"{name}: source dimension must attach to two diagram vertices")
        points = []
        for entity in entities:
            point = _early_bound(entity, "ISketchPoint")
            points.append(tuple(float(value) * 1000.0 for value in (point.X, point.Y, point.Z)))
        _telemetry.info(f"{label}: source_dimension={name!r} attachment_points_mm={points!r}")
        _assert_supplier_profile_vertices(rows[name], points)
        tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
        assert_supplier_profile_state(
            rows[name], qualified_name=str(native.FullName), native_type=int(display.Type2),
            driven_state=int(native.DrivenState), tolerance_type=int(tolerance.Type),
            tolerance_band_mm=(
                float(tolerance.GetMinValue()) * 1000.0,
                float(tolerance.GetMaxValue()) * 1000.0,
            ),
            tolerance_precision=int(display.GetPrimaryTolPrecision2()),
        )
        found.append(name)
    if sorted(found) != sorted(rows):
        raise RuntimeError(f"{label}: canonical source dimension coverage changed: {found!r}")
    geometry = capture_native_sketch_geometry(sketch, label=label)
    full_frame = _supplier_profile_model_points(adapter, full, crop_head=False, label=label)
    head_frame = _supplier_profile_model_points(adapter, head, crop_head=True, label=label)
    return SupplierStockCapture(geometry, full_frame, head_frame, str(Path(model.GetPathName()).resolve()))


def _assert_supplier_source_read_only(adapter, model, views, *, stage):
    """Read actual source state without clearing known presentation dirtiness."""
    state = {}
    errors = []
    for name, read in (
        ("path", lambda: str(model.GetPathName())),
        ("configuration", lambda: active_configuration_name(adapter, model)),
        ("dirty", lambda: bool(model.GetSaveFlag())),
        ("read_only", lambda: model.IsOpenedReadOnly()),
    ):
        try:
            state[name] = read()
        except BaseException as exc:
            state[name] = f"read_error: {type(exc).__name__}: {exc}"
            errors.append(exc)
    bindings = []
    for view in views:
        try:
            native = _early_bound(view, "IView")
            bindings.append((
                view_name(adapter, native), str(native.GetReferencedModelName()),
                int(adapter.swApp.IsSame(model, native.ReferencedDocument)),
            ))
        except BaseException as exc:
            bindings.append(f"read_error: {type(exc).__name__}: {exc}")
            errors.append(exc)
    _telemetry.info(f"MSC source {stage}: actual={state!r} view_bindings={bindings!r}")
    if errors:
        raise errors[0]
    expected = SOURCE.resolve()
    if Path(state["path"]).resolve() != expected or any(
        Path(path).resolve() != expected or same != 1 for _, path, same in bindings
    ):
        raise RuntimeError(f"MSC source {stage}: source identity/path changed")
    if state["read_only"] is not True:
        raise RuntimeError(f"MSC source {stage}: source is not read-only")
    return state["dirty"]


def _assert_supplier_source_clean(adapter, model, views, *, stage):
    if _assert_supplier_source_read_only(adapter, model, views, stage=stage):
        raise RuntimeError(f"MSC source {stage}: source is already dirty before clean capture")


def _assert_supplier_source_integrity(adapter, model, views, baseline, *, stage):
    """Prove native write protection and persisted bytes, including failures."""
    errors = []
    try:
        _assert_supplier_source_read_only(adapter, model, views, stage=stage)
    except BaseException as exc:
        errors.append(exc)
    try:
        actual = _source_file_sha256(SOURCE)
        _telemetry.info(
            f"MSC source {stage}: source_sha256_before={baseline!r} source_sha256_actual={actual!r}"
        )
        if actual != baseline:
            raise RuntimeError(f"MSC source {stage}: persisted source SHA-256 changed")
    except BaseException as exc:
        errors.append(exc)
    if errors:
        for error in errors[1:]:
            errors[0].add_note(f"MSC additional source integrity failure: {error}")
        raise errors[0]


def _assert_supplier_source_bodiless(adapter, full, head, solid_view):
    """Census actual configured bodies and restore the source before finalize."""
    views = [_early_bound(view, "IView") for view in (solid_view, full, head)]
    model = _early_bound(views[0].ReferencedDocument, "IModelDoc2")
    if model is None or any(
        int(adapter.swApp.IsSame(model, view.ReferencedDocument)) != 1 for view in views
    ):
        raise RuntimeError("MSC body census views do not reference the same source")
    installed = str(views[0].ReferencedConfiguration)
    if not installed or installed == SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError("MSC body census has no installed solid-view positive control")
    # IView.GetBodiesCount describes a multibody view selection. A zero is
    # ambiguous without a solid-view control; never use it as the body proof.
    view_counts = {}
    for view in views:
        name = view_name(adapter, view)
        try:
            view_counts[name] = {
                "configuration": str(view.ReferencedConfiguration),
                "GetBodiesCount": int(view.GetBodiesCount()),
            }
        except Exception as exc:
            view_counts[name] = {"read_error": f"{type(exc).__name__}: {exc}"}
    _telemetry.info(f"MSC native view body-count controls={view_counts!r}")
    original = active_configuration_name(adapter, model)
    was_dirty = bool(model.GetSaveFlag())

    def read_only_state():
        try:
            return bool(model.IsOpenedReadOnly())
        except Exception as exc:
            return f"read_error: {type(exc).__name__}: {exc}"

    _telemetry.info(
        f"MSC body census source before: configuration={original!r} "
        f"dirty={was_dirty!r} opened_read_only={read_only_state()!r}"
    )
    _assert_supplier_source_clean(adapter, model, views, stage="before body census")

    def show(configuration):
        if active_configuration_name(adapter, model) != configuration:
            if model.ShowConfiguration2(configuration) is not True:
                raise RuntimeError(f"MSC body census cannot activate {configuration!r}")
        if active_configuration_name(adapter, model) != configuration:
            raise RuntimeError(f"MSC body census configuration readback differs from {configuration!r}")
        if model.EditRebuild3() is not True:
            raise RuntimeError(f"MSC body census cannot rebuild {configuration!r}")
        if active_configuration_name(adapter, model) != configuration:
            raise RuntimeError(f"MSC body census rebuild changed configuration {configuration!r}")

    primary = None
    try:
        for configuration, expected_solids in (
            (installed, 1), (SUPPLIER_STOCK_CONFIGURATION, 0),
        ):
            show(configuration)
            part = _early_bound(model, "IPartDoc")
            counts = tuple(len(tuple(part.GetBodies2(kind, False) or ())) for kind in (0, 1))
            _telemetry.info(
                f"MSC native source body census configuration={configuration!r} "
                f"solid_bodies={counts[0]} sheet_bodies={counts[1]}"
            )
            if counts != (expected_solids, 0):
                raise RuntimeError(
                    f"MSC body census {configuration!r}: solid/sheet={counts!r}, "
                    f"expected={(expected_solids, 0)!r}"
                )
            if configuration == SUPPLIER_STOCK_CONFIGURATION:
                _assert_supplier_source_clean(
                    adapter, model, views, stage="target before immutable capture",
                )
                capture = _capture_supplier_stock(adapter, model, full, head)
    except BaseException as exc:
        primary = exc
        raise
    finally:
        try:
            show(original)
            is_dirty = bool(model.GetSaveFlag())
            _telemetry.info(
                f"MSC body census source restored: original={original!r} "
                f"configuration={active_configuration_name(adapter, model)!r} "
                f"dirty_before={was_dirty!r} dirty_after={is_dirty!r} "
                f"opened_read_only={read_only_state()!r}"
            )
            if is_dirty and not was_dirty:
                raise RuntimeError("MSC body census configuration switch dirtied the source")
            _assert_supplier_source_clean(adapter, model, views, stage="after body census restoration")
        except BaseException as restore_error:
            if primary is None:
                raise
            primary.add_note(f"MSC source configuration restoration also failed: {restore_error}")
    return capture


def _verify_supplier_stock(adapter, full, head, notes, capture: SupplierStockCapture) -> None:
    """Preserve the failed native sheet before session teardown closes it."""
    try:
        _check_supplier_stock(adapter, full, head, notes, capture)
    except Exception as exc:
        _seat_forensics.capture_com_failure(
            adapter, f"{PART_STEM}-supplier-envelope", str(exc),
            api="MSC settled supplier view guard", exception=exc, sheet_png=True,
        )


def _check_supplier_stock(adapter, full, head, notes, capture: SupplierStockCapture) -> None:
    """Check seven authentic source groups, the nominal major carrier and ink."""
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if ddoc.ActivateSheet(SHEET_NAMES[1]) is not True:
        raise RuntimeError("cannot activate settled source envelope sheet")
    full_name, head_name = view_name(adapter, full), view_name(adapter, head)
    views = {view_name(adapter, view): _early_bound(view, "IView") for view in iter_views(adapter)}
    if set(views) != {full_name, head_name}:
        raise RuntimeError("source envelope lost its two native views")
    for original in (full, head):
        name = view_name(adapter, original)
        view = views[name]
        same = int(adapter.swApp.IsSame(original, view))
        _telemetry.info(f"MSC native settled identity view={name!r} IsSame={same}")
        if same != 1:  # swObjectSame; unknown is not evidence of identity.
            raise RuntimeError(f"MSC source view identity changed: {name!r} ({same})")
        if (
            str(Path(view.GetReferencedModelName()).resolve()) != capture.source_path
            or str(
                Path(
                    _early_bound(view.ReferencedDocument, "IModelDoc2").GetPathName()
                ).resolve()
            )
            != capture.source_path
        ):
            raise RuntimeError(f"MSC source view path changed: {name!r}")
        _log_supplier_view_state(adapter, view, stage=f"{name}: settled before refresh")
        view.UpdateViewDisplayGeometry()
        _log_supplier_view_state(adapter, view, stage=f"{name}: settled after refresh")
    template = DRAWING_TEMPLATES[SPEC.layout]
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    region = sheet_drawable_region(
        adapter, sheet, width=template.width_m, height=template.height_m,
    )
    border = (region.xmin, region.ymin, region.xmax, region.ymax)
    rows = {row.name: row for row in SUPPLIER_REFERENCE_DIMENSIONS}
    found = []
    for view, keep, scale, center, cropped, cell in (
        (views[full_name], STOCK_KEEP, STOCK_SCALE, STOCK_CENTER, False, STOCK_VIEW_CELL),
        (views[head_name], STOCK_HEAD_KEEP, STOCK_HEAD_SCALE, STOCK_HEAD_CENTER, True, STOCK_HEAD_CELL),
    ):
        if not _inside(cell, border):
            raise RuntimeError("source annotation cell leaves the actual sheet border")
        if (
            str(view.ReferencedConfiguration) != SUPPLIER_STOCK_CONFIGURATION
            or int(view.UseSheetScale) != 0
            or tuple(float(value) for value in view.ScaleRatio) != scale
            or bool(view.IsCropped()) != cropped
        ):
            raise RuntimeError("supplier envelope view lost source configuration/scale/crop")
        _assert_supplier_profile_frame(
            adapter,
            view,
            center,
            scale,
            points=capture.head_frame if cropped else capture.full_frame,
            label="MSC source envelope",
        )
        _assert_supplier_profile_ink(adapter, view, cell, capture.geometry, cropped=cropped)
        assert_supplier_annotations_fit(adapter, view, cell, label=f"MSC source envelope {view_name(adapter, view)}")
        annotations = [
            _early_bound(raw, "IAnnotation") for raw in (view.GetAnnotations() or ())
            if dimension_name(adapter, _early_bound(raw, "IAnnotation"))
        ]
        names = [dimension_name(adapter, annotation) for annotation in annotations]
        if sorted(names) != sorted(keep):
            raise RuntimeError(f"source view required dimension coverage changed: {names}")
        found.extend(names)
        for annotation, name in zip(annotations, names, strict=True):
            if int(annotation.Visible) != 1:
                raise RuntimeError(f"{name}: supplier source dimension is hidden")
            row = rows[name]
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            assert_supplier_reference_dimension(adapter, display, **_supplier_contract(row))
            _assert_dimension_source(adapter, view, display, name=name, feature=SUPPLIER_STOCK_FEATURE)
            native = _early_bound(display.GetDimension2(0), "IDimension")
            tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
            assert_supplier_profile_state(
                row, qualified_name=str(native.FullName), native_type=int(display.Type2),
                driven_state=int(native.DrivenState), tolerance_type=int(tolerance.Type),
                tolerance_band_mm=(
                    float(tolerance.GetMinValue()) * 1000.0,
                    float(tolerance.GetMaxValue()) * 1000.0,
                ),
                tolerance_precision=int(display.GetPrimaryTolPrecision2()),
            )
    source_names = {row.name for row in SUPPLIER_PROFILE_DIMENSIONS}
    if len(source_names) != 7 or sorted(
        name for name in found if name in source_names
    ) != sorted(source_names):
        raise RuntimeError("supplier stock must retain all seven source groups exactly once")
    if (
        found.count(SUPPLIER_THREAD_MAJOR_DIMENSION.name) != 1
        or sorted(found) != sorted(rows)
    ):
        raise RuntimeError("source diagram lost its separate nominal thread-major reference")
    for note, text, cell in notes:
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        bounds = _box(note.GetExtent(), label=text, kind="note")
        if (
            str(note.GetText()).replace("\r\n", "\n") != text
            or int(annotation.Visible) != 1
            or int(annotation.OwnerType) != 1
            or not _inside(bounds, cell)
            or not _inside(bounds, border)
            or (
                bounds[2] > template.title_block_left_m
                and bounds[1] < template.title_block_top_m
            )
        ):
            raise RuntimeError(f"source label changed or leaves usable sheet space: {text!r}")


def _sketch_circle(
    adapter: Any,
    view: Any,
    center: tuple[float, float],
    radius: float,
    *,
    label: str,
) -> Any:
    """Sketch a circle in ``view``'s own sketch from SHEET coordinates.

    The sheet points go through the view sketch's ModelToSketchTransform
    (the cylinder-gear notch-fence recipe), so the circle lands where the
    sheet says whatever the view's scale.  The caller activates the view;
    the new circle is left SELECTED, which is what Crop2 consumes.

    The circle goes straight to the sketch database (AddToDB): with
    inference on, SolidWorks snaps the points onto nearby model edges within
    a screen-pixel tolerance, so the result depends on the seat.  r857-6e65
    drew the Front's tip mark at ~1.5 mm radius on the cut end where eae5
    drew the 3.6 mm fence 1 mm above it, from the same code.  The made
    circle is read back and must sit within CIRCLE_TOL_M of the sheet ask.
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
    prior = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = prior
    if circle is None:
        raise RuntimeError(f"cannot sketch the {label} circle")
    # Sketch units per sheet metre: the ask's radius in each space.
    asked = math.dist(points[0][:2], points[1][:2])
    tol = CIRCLE_TOL_M * asked / radius
    arc = _early_bound(circle, "ISketchArc")
    made = _early_bound(arc.GetCenterPoint2(), "ISketchPoint")
    off = math.dist((float(made.X), float(made.Y)), points[0][:2])
    made_radius = float(arc.GetRadius())
    _telemetry.info(
        f"{label}: sheet_center_m={center!r} sheet_radius_m={radius!r} "
        f"asked_sketch_points_m={points!r} "
        f"actual_sketch_center_m={(float(made.X), float(made.Y))!r} "
        f"actual_sketch_radius_m={made_radius!r}"
    )
    if off > tol or abs(made_radius - asked) > tol:
        raise RuntimeError(
            f"{label} circle landed off its ask: centre {off / asked * radius * 1000.0:.3f} mm "
            f"away, radius {made_radius / asked * radius * 1000.0:.3f} mm for "
            f"{radius * 1000.0:.3f} mm (tolerance {CIRCLE_TOL_M * 1000.0:.2f} mm)"
        )
    return circle


def _activate(adapter: Any, view: Any, *, label: str) -> str:
    name = view_name(adapter, view)
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


def _note_texts(view: Any) -> list[str]:
    return [
        str(_early_bound(note, "INote").GetText())
        for note in (_early_bound(view, "IView").GetNotes() or ())
    ]


def cropped_tip_view(adapter: Any) -> Any:
    """The 10:1 tip view: a standalone *Front model view, NOT a detail.

    Measured (diag/mha142-bisect, b6552f13b, farm worker swmaker000008): no
    detail child of the Front offered CutEndBreak to the model-item import
    under 10:1 HLR, 10:1 HLV, 5:1 and 2:1, imported before or after the
    Front's own import -- every one returned available=[], as the 10:1 HLR
    detail had in pms857-f543 (hidden reference sketch, source 1), -56f7
    (cutter profile, source 1), -6099 (cutter profile, source 0) and 918-top
    (source 0 after a visible-entity pre-read).  diag-9eca's lone detail
    success was not reproduced by replaying its pre-reads.  The same *Front
    placed at 10:1, moved so the tip lands on DETAIL_CENTER and cropped by a
    sketch circle (IView.Crop2 status 1, IsCropped True, HLR) imported
    CutEndBreak twice in that leaf.  So the crop, not a detail, carries it.

    Sequence: place_view at 10:1; move by the tip reference point's sheet
    error (ModelToViewTransform, SetViewPosition); ActivateView; a circle of
    the detail fence's sheet radius in the view's own sketch; Crop2 straight
    after it, while the circle is still the selection; an IsCropped
    read-back that raises.
    """
    draw = adapter.currentModel
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *DETAIL_CENTER, scale=DETAIL_SCALE),
        "IView",
    )
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != DETAIL_SCALE:
        raise RuntimeError(f"tip view scale {ratio!r}, expected {DETAIL_SCALE!r}")
    reference = tuple(value / 1000 for value in TIP_DETAIL.detail_reference_mm)
    tip = model_point_in_view(adapter, view, reference, label="tip view reference")
    position = tuple(float(value) for value in view.Position)
    target = [position[i] + DETAIL_CENTER[i] - tip[i] for i in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("cannot move the tip view onto its sheet position")
    draw.EditRebuild3()
    center = model_point_in_view(adapter, view, reference, label="tip view reference")
    if math.dist(center, DETAIL_CENTER) > TIP_VIEW_POSITION_TOLERANCE_M:
        raise RuntimeError(
            f"tip view reference sits at {center!r}, not {DETAIL_CENTER!r}"
        )
    _activate(adapter, view, label="tip view")
    _sketch_circle(adapter, view, center, DETAIL_RADIUS, label="tip view crop")
    status = int(view.Crop2(False, False, 5))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    cropped = bool(view.IsCropped())
    _telemetry.info(
        f"tip view {view_name(adapter, view)!r}: {ratio[0]:g}:{ratio[1]:g}, "
        f"Crop2 status {status}, IsCropped {cropped}"
    )
    if status != _CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"tip view is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    return view


def _curate_tip_view(adapter: Any, view: Any) -> list[Any]:
    """Import the break into the tip view by feature: only the deburr
    cutter's CutEndDeburrProfile is selected (source 1), never the entire
    model.  The cropped model view's entire-model import delivered it in
    b6552f13b; the targeted form is the one the Front already uses."""
    return _drawing_dimension_import.curate_view_dimensions(
        adapter,
        view,
        keep=DETAIL_KEEP,
        view_label="tip view break",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )


# swDimensionArrowsSide_e.swDimArrowsOutside: the arrows sit outside the
# extension lines and point in.
ARROWS_OUTSIDE = 1
# Clear sheet space between the break text's right edge and the tail of the
# left arrowhead.
BREAK_TEXT_GAP_M = 0.002
# GetArrowHeadAtIndex2 has no read on this project's seats yet: a width past
# this is not an arrowhead in sheet metres, and a move past the shift bound
# (text width + arrow + gap is ~10-25 mm) means a convention was misread.
# Either raises rather than parking the text somewhere nobody wants it.
_ARROW_WIDTH_MAX_M = 0.01
_BREAK_TEXT_SHIFT_MAX_M = 0.03
# A vertical run: its ends share x to within this.
_VERTICAL_TOLERANCE_M = 1e-6
# The display data's text must sit within this of the annotation's own
# position, or its frame is not the sheet and no clearance can be read.
_TEXT_FRAME_TOLERANCE_M = 0.05


@dataclass(frozen=True)
class BreakInk:
    """The break dimension's rendered ink on the sheet, metres.

    No API returns a dimension's rendered text width (INote::GetExtent is
    for notes only), so the text box is the display data's text anchor,
    reference corner and cap height, widened by the template's estimated
    glyph advance (_layout_geometry.estimate_text_box).
    """

    extension_x: tuple[float, float]
    arrow_left_x: float
    text: str
    height: float
    text_box: Box
    position: tuple[float, float]

    @property
    def left_limit(self) -> float:
        """The leftmost ink the text must clear: left line or arrow tail."""
        return min(self.extension_x[0], self.arrow_left_x)


def _floats(raw: Any) -> tuple[float, ...]:
    return tuple(float(value) for value in (raw or ()))


def _break_annotation(adapter: Any, annotations: list[Any]) -> Any:
    for item in annotations:
        annotation = _early_bound(item, "IAnnotation")
        if dimension_name(adapter, annotation) == CUT_END_BREAK_DIMENSION:
            return annotation
    raise RuntimeError(f"tip view has no {CUT_END_BREAK_DIMENSION} to place")


def _extension_x(data: Any) -> tuple[float, float]:
    """The x of the two vertical extension lines, from GetLineAtIndex2 (the
    read draw_frame_assembly already makes on the seat).  Each line ends with
    start[3], end[3] whichever overload's leading scalars precede them, so the
    points are read from the array's end, as drawing_layout_audit does."""
    xs: list[float] = []
    for index in range(int(data.GetLineCount())):
        values = _floats(data.GetLineAtIndex2(index))
        if len(values) < 10:
            raise RuntimeError(f"break dimension line {index} is incomplete: {values!r}")
        start = len(values) - 6
        x0, y0 = values[start], values[start + 1]
        x1, y1 = values[start + 3], values[start + 4]
        if abs(x0 - x1) > _VERTICAL_TOLERANCE_M or abs(y0 - y1) <= _VERTICAL_TOLERANCE_M:
            continue
        if all(abs(x0 - seen) > _VERTICAL_TOLERANCE_M for seen in xs):
            xs.append(x0)
    if len(xs) != 2:
        raise RuntimeError(
            f"break dimension must draw two extension lines, read x={sorted(xs)!r}"
        )
    left, right = sorted(xs)
    return (left, right)


def _arrow_left_x(data: Any, fallback: float) -> float:
    """The leftmost arrowhead ink.  GetArrowHeadAtIndex2 returns [tip[3],
    dir[3], width, ...]; the body is taken on BOTH sides of the tip, so the
    result does not rest on which way dir points."""
    lefts = [fallback]
    for index in range(int(data.GetArrowHeadCount())):
        values = _floats(data.GetArrowHeadAtIndex2(index))
        if len(values) < 7:
            raise RuntimeError(f"break arrowhead {index} is incomplete: {values!r}")
        dx, dy, dz = values[3:6]
        length = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        width = values[6]
        if not 0.0 <= width <= _ARROW_WIDTH_MAX_M:
            raise RuntimeError(
                f"break arrowhead {index} width {width!r} is not an arrowhead's"
            )
        lefts.append(values[0] - abs(dx / length) * width)
    return min(lefts)


def read_break_ink(annotation: Any) -> BreakInk:
    """Read the break's extension lines, arrowheads and text box back."""
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    data = _early_bound(display.GetDisplayData(), "IDisplayData")
    extension = _extension_x(data)
    arrow_left = _arrow_left_x(data, extension[0])
    count = int(data.GetTextCount())
    if count < 1:
        raise RuntimeError("break dimension draws no text")
    texts: list[str] = []
    boxes: list[Box] = []
    height = 0.0
    for index in range(count):
        text = str(data.GetTextAtIndex(index) or "")
        anchor = _floats(data.GetTextPositionAtIndex(index))
        size = float(data.GetTextHeightAtIndex(index))
        reference = int(data.GetTextRefPositionAtIndex(index))
        box = estimate_text_box(
            text,
            anchor=(anchor[0], anchor[1]),
            height=size,
            reference=reference if 0 <= reference <= 5 else 0,
            angle=float(data.GetTextAngleAtIndex(index)),
        )
        if box is None:
            continue
        texts.append(text)
        boxes.append(box)
        height = max(height, size)
    if not boxes:
        raise RuntimeError("break dimension text has no extent to read")
    text_box = Box(
        min(box.xmin for box in boxes),
        min(box.ymin for box in boxes),
        max(box.xmax for box in boxes),
        max(box.ymax for box in boxes),
    )
    position = _floats(annotation.GetPosition())[:2]
    centre = (
        (text_box.xmin + text_box.xmax) / 2.0,
        (text_box.ymin + text_box.ymax) / 2.0,
    )
    if math.dist(centre, position) > _TEXT_FRAME_TOLERANCE_M:
        raise RuntimeError(
            f"break text at {centre!r} is not in the sheet frame of its "
            f"annotation at {position!r}"
        )
    return BreakInk(
        extension_x=extension,
        arrow_left_x=arrow_left,
        text=" ".join(texts),
        height=height,
        text_box=text_box,
        position=(position[0], position[1]),
    )


def _log_break_ink(ink: BreakInk, *, stage: str) -> None:
    clearance = ink.left_limit - ink.text_box.xmax
    _telemetry.info(
        f"tip view break text {stage}: {ink.text!r} box x "
        f"{ink.text_box.xmin:.5f}..{ink.text_box.xmax:.5f} (width "
        f"{ink.text_box.width:.5f}, height {ink.height:.5f}), extension lines x "
        f"{ink.extension_x[0]:.5f}/{ink.extension_x[1]:.5f}, left arrow tail x "
        f"{ink.arrow_left_x:.5f}, anchor {ink.position[0]:.5f}, "
        f"clearance {clearance:.5f} m"
    )
    _telemetry.event(
        "drawing.tip_break_text",
        stage=stage,
        text=ink.text,
        text_box=(
            ink.text_box.xmin,
            ink.text_box.ymin,
            ink.text_box.xmax,
            ink.text_box.ymax,
        ),
        extension_x=ink.extension_x,
        arrow_left_x=ink.arrow_left_x,
        position=ink.position,
        clearance_m=clearance,
    )


def assert_break_text_outside(ink: BreakInk) -> None:
    """The text must sit wholly left of both extension lines and of the left
    arrow's tail: none of it between or across the lines."""
    if ink.text_box.xmax > ink.extension_x[0]:
        raise RuntimeError(
            f"break text box ends at x {ink.text_box.xmax:.5f}, across the left "
            f"extension line at {ink.extension_x[0]:.5f}"
        )
    if ink.text_box.xmax > ink.arrow_left_x:
        raise RuntimeError(
            f"break text box ends at x {ink.text_box.xmax:.5f}, over the left "
            f"arrow's tail at {ink.arrow_left_x:.5f}"
        )


def place_break_text_outside(adapter: Any, annotations: list[Any]) -> BreakInk:
    """Put the break's text LEFT of the leader, arrows outside pointing in.

    857-b835: the text sat centred almost on the 1 mm gap and overprinted
    both extension lines and the inner arrowheads.  Arrows go outside
    (ArrowSide), auto-centring is off (CenterText), and the text moves along
    the dimension line only, so its right edge sits BREAK_TEXT_GAP_M left of
    the left arrow's tail, measured from the display data's own read-back.
    """
    annotation = _break_annotation(adapter, annotations)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    display.CenterText = False
    display.ArrowSide = ARROWS_OUTSIDE
    if int(display.ArrowSide) != ARROWS_OUTSIDE or bool(display.CenterText):
        raise RuntimeError(
            f"break arrows/centring did not take: ArrowSide {display.ArrowSide}, "
            f"CenterText {display.CenterText}"
        )
    adapter.currentModel.EditRebuild3()
    before = read_break_ink(annotation)
    _log_break_ink(before, stage="imported")
    shift = before.left_limit - BREAK_TEXT_GAP_M - before.text_box.xmax
    if abs(shift) > _BREAK_TEXT_SHIFT_MAX_M:
        raise RuntimeError(
            f"break text would move {shift:.5f} m, past {_BREAK_TEXT_SHIFT_MAX_M} m: "
            "an arrowhead or text read-back convention is off"
        )
    x, y = before.position
    if not annotation.SetPosition2(x + shift, y, 0.0):
        raise RuntimeError("cannot move the break text left of its leader")
    adapter.currentModel.EditRebuild3()
    after = read_break_ink(annotation)
    _log_break_ink(after, stage="placed")
    assert_break_text_outside(after)
    return after


def label_tip_view(adapter: Any, view: Any) -> None:
    """Label the tip view "DETAIL A  SCALE 10:1".

    A model view has no native label the API can show (only detail, section
    and auxiliary views carry one; swDetailingOrthoViewLabelsEnableShow is
    documented "Not used"), so the label is a note inserted while the tip
    view is ACTIVE: the view owns it (IView.GetNotes) and it moves with the
    view.  Read back: the tip view carries that label exactly once.  Other
    notes on the view are logged, not refused: whether the template shows a
    native label on a model view has not been read on a seat.
    """
    _activate(adapter, view, label="tip view")
    if add_note(adapter, TIP_VIEW_LABEL, *TIP_DETAIL.detail_label_xy) is None:
        raise RuntimeError("failed to add the tip view label")
    texts = _note_texts(view)
    _telemetry.info(f"tip view notes after its label: {texts!r}")
    if texts.count(TIP_VIEW_LABEL) != 1:
        raise RuntimeError(
            f"tip view label did not land in the tip view: its notes are {texts!r}"
        )


def mark_tip_on_front(adapter: Any, front: Any) -> None:
    """Circle the tip on the Front and letter it "A", so the machinist finds
    detail A: a sketch circle of the tip view's crop fence (1:1) around the
    same reference point, and a note "A" owned by the Front.  Both are
    sheet-authored annotation, not dimensions."""
    _activate(adapter, front, label="Front view")
    reference = tuple(value / 1000 for value in TIP_DETAIL.detail_reference_mm)
    center = model_point_in_view(adapter, front, reference, label="Front tip mark")
    radius = DETAIL_FENCE_MM * SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0
    _sketch_circle(adapter, front, center, radius, label="Front tip mark")
    adapter.currentModel.ClearSelection2(True)
    offset = TIP_DETAIL.parent_letter_offset
    if add_note(adapter, TIP_LETTER, center[0] + offset[0], center[1] + offset[1]) is None:
        raise RuntimeError("failed to letter the Front's tip mark")
    texts = _note_texts(front)
    if texts.count(TIP_LETTER) != 1:
        raise RuntimeError(f"Front tip letter did not land in the Front: {texts!r}")


def activate_front_for_notes(adapter: Any, front: Any) -> None:
    """Make the Front the active view before the property-linked notes.

    A note lands in the ACTIVE view: with a detail active, the four notes
    landed inside it (pms857-diag-9eca, "found 5" notes on the detail).
    """
    name = view_name(adapter, front)
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate the Front view {name!r} for the notes")


def _view_dimension_names(adapter: Any, view: Any) -> list[str]:
    return [
        dimension_name(adapter, _early_bound(item, "IAnnotation"))
        for item in (_early_bound(view, "IView").GetAnnotations() or ())
    ]


def break_text(value_mm: float, places: int, tol_type: int, prefix: str, suffix: str) -> str:
    """The break dimension's printed text, composed from its read-back parts.

    The API exposes no rendered string for a toleranced value, so the seat
    check composes it: value in inches at its places, the MAX limit when the type is
    swTolMAX, and whatever prefix and suffix the display carries.
    """
    limit = " MAX" if tol_type == CUT_END_BREAK_TOL_TYPE else ""
    return f"{prefix}{inch_text(value_mm, places)}{limit}{suffix}"


def _verify_tip_view(adapter: Any, front: Any, tip: Any) -> None:
    """Seat read-back: the tip view is cropped at its scale, carries the one
    break dimension as a MAX limit reading the spec's text, with that text
    left of both extension lines, and the Front does not."""
    view = _early_bound(tip, "IView")
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != DETAIL_SCALE:
        raise RuntimeError(f"tip view scale {ratio!r}, expected {DETAIL_SCALE!r}")
    if not bool(view.IsCropped()):
        raise RuntimeError("tip view is no longer cropped")
    names = [name for name in _view_dimension_names(adapter, tip) if name]
    if names != [CUT_END_BREAK_DIMENSION]:
        raise RuntimeError(
            f"tip view must carry exactly one {CUT_END_BREAK_DIMENSION}: {names}"
        )
    front_names = _view_dimension_names(adapter, front)
    if CUT_END_BREAK_DIMENSION in front_names:
        raise RuntimeError(f"Front view still carries the 1:1 break: {front_names}")
    annotation = next(
        _early_bound(item, "IAnnotation")
        for item in view.GetAnnotations()
        if dimension_name(adapter, _early_bound(item, "IAnnotation"))
        == CUT_END_BREAK_DIMENSION
    )
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    value_mm = float(dimension.SystemValue) * 1000.0
    places = int(display.GetPrimaryPrecision2())
    tol_type = int(tolerance.Type)
    parenthesis = bool(display.ShowParenthesis)
    text = break_text(
        value_mm,
        places,
        tol_type,
        str(display.GetText(1) or ""),  # swDimensionTextPrefix
        str(display.GetText(2) or ""),  # swDimensionTextSuffix
    )
    _telemetry.event(
        "drawing.tip_detail_break",
        text=text,
        value_mm=value_mm,
        places=places,
        tol_type=tol_type,
        parenthesis=parenthesis,
        scale=f"{ratio[0]:g}:{ratio[1]:g}",
    )
    if (
        tol_type != CUT_END_BREAK_TOL_TYPE
        or abs(value_mm - CUT_END_BREAK_MAX_MM) > 1e-9
        or parenthesis
        or text != CUT_END_BREAK_TEXT
    ):
        raise RuntimeError(
            f"tip view break reads {text!r} (type {tol_type}, parenthesis "
            f"{parenthesis}), expected {CUT_END_BREAK_TEXT!r}"
        )
    ink = read_break_ink(annotation)
    _log_break_ink(ink, stage="verified")
    assert_break_text_outside(ink)
    _telemetry.success(f"tip view {ratio[0]:g}:{ratio[1]:g} reads {text}")


def _reference_cut_length(adapter: Any, annotations: list[Any]) -> None:
    """Re-read the imported cut length, then mark it reference.

    It must be the model's nominal and carry NO band (swTolNONE): a band
    would promise a fixed length the post and plate bands cannot honour.
    """
    for annotation in annotations:
        if dimension_name(adapter, annotation) != CUT_LENGTH_DIMENSION:
            continue
        display = _early_bound(
            _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        if abs(float(dimension.SystemValue) - CUT_LENGTH_MM / 1000.0) > 1e-9:
            raise RuntimeError(
                f"cut length {float(dimension.SystemValue)!r} m is not the "
                f"modelled {CUT_LENGTH_MM} mm"
            )
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        if int(tolerance.Type) != 0:  # swTolNONE
            raise RuntimeError("cut length carries a band; it must be reference")
        set_reference_dimension(adapter, annotation, label="cut length")
        return
    raise RuntimeError("Front view has no cut length to mark reference")


def _verify_finished_controls(adapter, front, tip, installed_configuration) -> None:
    """Read the original finished cut/fit and break controls after final rebuild."""
    for view in (front, tip):
        if str(_early_bound(view, "IView").ReferencedConfiguration) != installed_configuration:
            raise RuntimeError("finished view no longer references the unchanged installed solid")
    front_names = [name for name in _view_dimension_names(adapter, front) if name]
    if front_names != [CUT_LENGTH_DIMENSION]:
        raise RuntimeError("finished Front no longer carries only its original cut length")
    annotations = [
        _early_bound(raw, "IAnnotation")
        for raw in (_early_bound(front, "IView").GetAnnotations() or ())
        if dimension_name(adapter, _early_bound(raw, "IAnnotation")) == CUT_LENGTH_DIMENSION
    ]
    if len(annotations) != 1:
        raise RuntimeError("finished sheet lost its one cut-to-fit reference length")
    assert_imported_precision(adapter, annotations, FRONT_PRECISION)
    display = _early_bound(annotations[0].GetSpecificAnnotation(), "IDisplayDimension")
    native = _early_bound(display.GetDimension2(0), "IDimension")
    if (
        str(native.FullName).split("@")[:2] != [CUT_LENGTH_DIMENSION, CUT_LENGTH_SKETCH]
        or abs(float(native.SystemValue) * 1000.0 - CUT_LENGTH_MM) > 1e-6
        or int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0
        or str(display.GetText(1) or "") != "("
        or str(display.GetText(2) or "") != ")"
        or str(display.GetText(4) or "") != CUT_TO_FIT_CALLOUT
        or display.GetOverride()
        or not display.ShowDimensionValue
        or annotations[0].IsDangling()
        or not any(annotations[0].GetAttachedEntities3() or ())
    ):
        raise RuntimeError("finished cut-to-fit reference changed")
    _verify_tip_view(adapter, front, tip)
    tip_annotations = [
        _early_bound(raw, "IAnnotation")
        for raw in (_early_bound(tip, "IView").GetAnnotations() or ())
        if dimension_name(adapter, _early_bound(raw, "IAnnotation")) == CUT_END_BREAK_DIMENSION
    ]
    if len(tip_annotations) != 1:
        raise RuntimeError("finished sheet lost its one cut-end break dimension")
    assert_imported_precision(adapter, tip_annotations, DETAIL_PRECISION)
    tip_display = _early_bound(tip_annotations[0].GetSpecificAnnotation(), "IDisplayDimension")
    tip_native = _early_bound(tip_display.GetDimension2(0), "IDimension")
    tip_tolerance = _early_bound(tip_native.Tolerance, "IDimensionTolerance")
    upper, lower = CUT_END_BREAK_BAND
    if (
        str(tip_native.FullName).split("@")[:2] != [CUT_END_BREAK_DIMENSION, CUT_END_BREAK_SKETCH]
        or abs(float(tip_tolerance.GetMinValue()) * 1000.0 - lower) > 1e-8
        or abs(float(tip_tolerance.GetMaxValue()) * 1000.0 - upper) > 1e-8
        or tip_display.GetOverride()
        or not tip_display.ShowDimensionValue
    ):
        raise RuntimeError("finished cut-end break lost its original native band/attachment")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    source_sha256 = _source_file_sha256(SOURCE)
    source_model = _open_supplier_source_read_only(
        adapter, SOURCE, label="MSC modified-stock drawing source",
    )
    primary = None
    try:
        return await _build_read_only_source(adapter, source_model, source_sha256)
    except BaseException as exc:
        primary = exc
        raise
    finally:
        try:
            _assert_supplier_source_integrity(
                adapter, source_model, (), source_sha256, stage="drawing lifecycle exit",
            )
        except BaseException as integrity_error:
            if primary is None:
                raise
            details = "; ".join((
                str(integrity_error), *getattr(integrity_error, "__notes__", ()),
            ))
            primary.add_note(f"MSC source integrity check also failed: {details}")


async def _build_read_only_source(adapter, source_model, source_sha256):
    # finalize_drawing closes the drawing; view bindings are valid only here,
    # before its save. The outer finally retains only the live source handle.
    source_views = []
    _assert_supplier_source_clean(adapter, source_model, source_views, stage="opened before preparation")
    installed_configuration = str(_early_bound(
        _early_bound(source_model.ConfigurationManager, "IConfigurationManager").ActiveConfiguration,
        "IConfiguration",
    ).Name)
    if installed_configuration == SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError("source part was saved with the supplier envelope active")
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Stock Name",
        "Supplier",
        "Supplier SKUs",
        "Manufacturing Notes",
        "Supplier Reference Source",
        "Supplier Reference Title",
    )
    read_required_properties(adapter.currentModel, required, required=required)
    draw, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="post mount screw source package")
    drawing_doc = _early_bound(draw, "IDrawingDoc")
    if not drawing_doc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("cannot activate unchanged finished screw sheet")
    stamp_drawing_summary(adapter, draw, DRAWING_SUMMARY)
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=SHEET_SCALE)
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    source_views.extend((front, iso))
    try:
        _assert_supplier_source_clean(
            adapter,
            source_model,
            source_views,
            stage="before supplier preparation",
        )
        if not drawing_doc.ActivateSheet(SHEET_NAMES[1]):
            raise RuntimeError("cannot activate source max-limit envelope sheet")
        full_stock, source_head = _supplier_stock_sheet(adapter)
        source_views.extend((full_stock, source_head))
        _assert_supplier_source_clean(
            adapter,
            source_model,
            source_views,
            stage="prepared before capture",
        )
        supplier_capture = _assert_supplier_source_bodiless(
            adapter, full_stock, source_head, front
        )
        _assert_supplier_source_clean(
            adapter,
            source_model,
            source_views,
            stage="after clean source capture",
        )
    except Exception as exc:
        _seat_forensics.capture_com_failure(
            adapter,
            f"{PART_STEM}-supplier-envelope",
            str(exc),
            api="MSC pre-presentation source capture",
            exception=exc,
            sheet_png=True,
        )
    if not drawing_doc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("cannot activate finished screw sheet for presentation")

    # The cut length lives on a part-hidden reference sketch, so the Front
    # view takes the opt-in curation that shows it in this view only.
    annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="cut length",
        dimensions_by_feature=FRONT_VIEW_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, FRONT_PRECISION)
    _reference_cut_length(adapter, annotations)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)

    # The break is the deburr cutter's own dimension, imported by feature
    # into the cropped 10:1 tip view (see cropped_tip_view), which is then
    # labelled as detail A and circled and lettered on the Front.
    with _telemetry.span("drawing.tip_view", scale=f"{DETAIL_SCALE[0]:g}:1"):
        tip = cropped_tip_view(adapter)
        source_views.append(tip)
        set_hidden_lines_removed(adapter, tip)
        _early_bound(tip, "IView").UpdateViewDisplayGeometry()
        tip_annotations = _curate_tip_view(adapter, tip)
        assert_imported_precision(adapter, tip_annotations, DETAIL_PRECISION)
        place_break_text_outside(adapter, tip_annotations)
        _verify_tip_view(adapter, front, tip)
    label_tip_view(adapter, tip)
    mark_tip_on_front(adapter, front)

    activate_front_for_notes(adapter, front)
    add_property_linked_note(
        adapter, "Manufacturing Notes", *NOTES_XY, char_height=0.003
    )
    for name, x, y in STOCK_ROWS:
        add_property_linked_note(adapter, name, x, y, char_height=0.003)

    set_hidden_lines_removed(adapter, front)
    if not drawing_doc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("cannot activate source max-limit envelope sheet")
    stock_notes = _present_supplier_stock_sheet(adapter, full_stock, source_head)
    try:
        _assert_supplier_source_integrity(
            adapter,
            source_model,
            source_views,
            source_sha256,
            stage="before drawing finalization",
        )
    except Exception as exc:
        _seat_forensics.capture_com_failure(
            adapter,
            f"{PART_STEM}-supplier-envelope",
            str(exc),
            api="MSC pre-finalize source integrity",
            exception=exc,
            sheet_png=True,
        )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title=TITLE,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_scales={SHEET_NAMES[0]: SHEET_SCALE, SHEET_NAMES[1]: STOCK_SCALE},
        settled_checks=(
            lambda: _assert_supplier_source_read_only(
                adapter, source_model, source_views, stage="before settled checks",
            ),
            lambda: _verify_finished_controls(adapter, front, tip, installed_configuration),
            lambda: _verify_supplier_stock(adapter, full_stock, source_head, stock_notes, supplier_capture),
            lambda: _assert_supplier_source_integrity(
                adapter, source_model, source_views, source_sha256, stage="settled before drawing save",
            ),
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
