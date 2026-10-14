"""Persisted native circular-detail geometry, independent of drawing recipes.

The sketch inverse returns parent SHEET coordinates, not model coordinates.
Only the centre then goes through parent SHEET -> MODEL -> detail SHEET.
GetOutline remains the native extent; the occupied box is the geometric circle.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array

from _com import _early_bound
import _telemetry


DETAIL_GEOMETRY_TOL_M = 0.00005


@dataclass(frozen=True)
class CircularDetailCrop:
    label: str
    parent: Any
    parent_centre: tuple[float, float]
    parent_radius: float
    parent_radius_y: float
    parent_ratio: tuple[float, float]
    detail_ratio: tuple[float, float]
    crop: tuple[float, float, float, float]
    outline: tuple[float, float, float, float]


def native_circle_geometry(
    circle: Any, *, label: str
) -> tuple[tuple[float, float, float], float]:
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
        raise RuntimeError(
            f"{label}: invalid native circle centre={centre}, radius={radius!r}"
        )
    return centre, radius


def _box(values: Any, *, label: str) -> tuple[float, float, float, float]:
    try:
        box = tuple(float(v) for v in values)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError(f"{label}: invalid native box={values!r}") from exc
    if (
        len(box) != 4
        or not all(math.isfinite(v) for v in box)
        or box[0] >= box[2]
        or box[1] >= box[3]
    ):
        raise RuntimeError(f"{label}: invalid native box={box!r}")
    return box


def _scale_ratio(view: Any, *, label: str) -> tuple[float, float]:
    ratio = tuple(float(v) for v in (view.ScaleRatio or ()))
    if len(ratio) != 2 or not all(math.isfinite(v) and v > 0.0 for v in ratio):
        raise RuntimeError(f"{label}: invalid native ScaleRatio={ratio!r}")
    return ratio


def _transform_point(
    utility: Any,
    xyz: tuple[float, float, float],
    transform: Any,
    *,
    label: str,
) -> tuple[float, float, float]:
    point = _early_bound(utility.CreatePoint(double_array(list(xyz))), "IMathPoint")
    if point is None:
        raise RuntimeError(f"{label}: cannot create native profile point")
    projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
    if projected is None:
        raise RuntimeError(f"{label}: cannot transform native profile point")
    coordinates = tuple(float(v) for v in (projected.ArrayData or ()))
    if len(coordinates) != 3 or not all(math.isfinite(v) for v in coordinates):
        raise RuntimeError(f"{label}: invalid transformed circle point={coordinates!r}")
    return coordinates


def read_circular_detail_crop(
    adapter: Any,
    view: Any,
    *,
    label: str,
) -> CircularDetailCrop:
    """Read one persisted circle and require its box inside ONE current outline.

    Native failures raise directly; there is no GetOutline fallback or clipping.
    Outline/display flags are recipe-specific: a complete persisted circle also
    exists for NoOutline details, whose full/jagged outline accessors are invalid.
    """
    view = _early_bound(view, "IView")
    parent = _early_bound(view.GetBaseView(), "IView")
    detail_circle = _early_bound(view.GetDetail(), "IDetailCircle")
    if parent is None or detail_circle is None:
        raise RuntimeError(f"{label}: missing native parent or persisted detail circle")
    # Both barriers precede the ONE outline read and ALL transform reads.
    # A just-created detail can have a stale undersized outline as well as a
    # stale transform; strict containment must use the refreshed geometry.
    parent.UpdateViewDisplayGeometry()  # VT_VOID
    view.UpdateViewDisplayGeometry()  # VT_VOID
    try:
        outline = view.GetOutline()
    except Exception as exc:
        raise RuntimeError(
            f"{label}: cannot read current native outline after display geometry update"
        ) from exc
    bbox = _box(outline, label=f"{label} native outline")
    _telemetry.info(f"{label}: native_view_bbox={bbox} (view extent, not crop)")
    circle_label = detail_circle.GetLabel()
    if type(circle_label) is not str or not circle_label:
        raise RuntimeError(
            f"{label}: invalid native detail circle label={circle_label!r}"
        )
    profiles = tuple(detail_circle.GetProfileItems() or ())
    if len(profiles) != 1:
        raise RuntimeError(
            f"{label}: expected one persisted circle profile, got {len(profiles)}"
        )
    raw_centre, raw_radius = native_circle_geometry(
        profiles[0], label=f"{label} persisted profile"
    )
    sketch = _early_bound(
        _early_bound(profiles[0], "ISketchSegment").GetSketch(), "ISketch"
    )
    if sketch is None:
        raise RuntimeError(f"{label}: persisted circle has no native sketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    if transform is None:
        raise RuntimeError(f"{label}: persisted circle has no native sketch transform")
    matrix = tuple(float(v) for v in (transform.ArrayData or ()))
    if len(matrix) != 16 or not all(math.isfinite(v) for v in matrix):
        raise RuntimeError(f"{label}: invalid native sketch transform={matrix!r}")
    # Automation Inverse (DISPID 9), NOT IInverse: R11 rejected the latter.
    inverse = _early_bound(transform.Inverse(), "IMathTransform")
    if inverse is None:
        raise RuntimeError(f"{label}: native sketch transform cannot be inverted")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    if utility is None:
        raise RuntimeError(f"{label}: missing native math utility for profile readback")
    sheet_points = []
    # R18 proved this sketch -> parent SHEET hop. Applying the parent's forward
    # model transform here would double-project points already on the sheet.
    for xyz in (
        raw_centre,
        (raw_centre[0] + raw_radius, raw_centre[1], raw_centre[2]),
        (raw_centre[0], raw_centre[1] + raw_radius, raw_centre[2]),
    ):
        coordinates = _transform_point(
            utility, xyz, inverse, label=f"{label} sketch to parent sheet"
        )
        if abs(coordinates[2]) > DETAIL_GEOMETRY_TOL_M:
            raise RuntimeError(
                f"{label}: inverse-mapped circle point={coordinates!r}, required_sheet_z=0, "
                f"geometry_tolerance_m={DETAIL_GEOMETRY_TOL_M}, raw_sketch_centre={raw_centre}, "
                f"raw_sketch_radius={raw_radius}, sketch_transform={matrix}, native_view_bbox={bbox}"
            )
        sheet_points.append(coordinates[:2])
    parent_centre, rim_x, rim_y = sheet_points
    parent_radius = math.dist(parent_centre, rim_x)
    radius_y = math.dist(parent_centre, rim_y)
    if (
        not all(math.isfinite(r) and r > 0.0 for r in (parent_radius, radius_y))
        or abs(radius_y - parent_radius) > DETAIL_GEOMETRY_TOL_M
    ):
        raise RuntimeError(
            f"{label}: invalid parent-sheet circle radii={parent_radius!r}, {radius_y!r}, "
            f"geometry_tolerance_m={DETAIL_GEOMETRY_TOL_M}, native_view_bbox={bbox}"
        )
    parent_ratio = _scale_ratio(parent, label=f"{label} parent")
    detail_ratio = _scale_ratio(view, label=label)
    magnification = (detail_ratio[0] / detail_ratio[1]) / (
        parent_ratio[0] / parent_ratio[1]
    )
    parent_transform = _early_bound(parent.ModelToViewTransform, "IMathTransform")
    detail_transform = _early_bound(view.ModelToViewTransform, "IMathTransform")
    if parent_transform is None or detail_transform is None:
        raise RuntimeError(f"{label}: missing native parent or detail view transform")
    # NEW essential R19 hop: invert the parent VIEW transform through the same
    # bound automation API R18 exercised for the sketch. No optional probes.
    parent_inverse = _early_bound(parent_transform.Inverse(), "IMathTransform")
    if parent_inverse is None:
        raise RuntimeError(f"{label}: native parent view transform cannot be inverted")
    model_centre = _transform_point(
        utility,
        (*parent_centre, 0.0),
        parent_inverse,
        label=f"{label} parent sheet to model",
    )
    detail_centre = _transform_point(
        utility,
        model_centre,
        detail_transform,
        label=f"{label} model to detail sheet",
    )
    radius = parent_radius * magnification
    crop = _box(
        (
            detail_centre[0] - radius,
            detail_centre[1] - radius,
            detail_centre[0] + radius,
            detail_centre[1] + radius,
        ),
        label=f"{label} circular crop",
    )
    context = (
        f"{label}: native_circle_label={circle_label!r}, raw_sketch_centre={raw_centre}, "
        f"raw_sketch_radius={raw_radius}, sketch_transform={matrix}, "
        f"inverse_parent_sheet_centre={parent_centre}, parent_sheet_radius={parent_radius}, "
        f"parent_sheet_radius_y={radius_y}, native_parent_scale={parent_ratio}, "
        f"native_detail_scale={detail_ratio}, model_centre={model_centre}, "
        f"detail_sheet_centre={detail_centre}, actual_crop_box={crop}, native_view_bbox={bbox}"
    )
    _telemetry.info(context)
    # EXACT zero containment slack: edge equality is accepted; one ULP outside
    # refuses. Only occupancy shrinks, so unchanged collision policies cannot
    # gain findings. Do not clip, intersect, or guess an outline padding.
    if not (
        bbox[0] <= crop[0]
        and bbox[1] <= crop[1]
        and crop[2] <= bbox[2]
        and crop[3] <= bbox[3]
    ):
        raise RuntimeError(
            f"{context}: circular crop is outside native outline (containment tolerance=0)"
        )
    return CircularDetailCrop(
        circle_label,
        parent,
        parent_centre,
        parent_radius,
        radius_y,
        parent_ratio,
        detail_ratio,
        crop,
        bbox,
    )
