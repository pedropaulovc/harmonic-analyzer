"""Native post-rebuild position gates for the crank cutover parts."""

from __future__ import annotations

import json
import math
from typing import Any

import _telemetry
from _common import _early_bound, _feature_by_name, _read_member

_POSITION_TOL_MM = 1e-6


def _circle_center_mm(adapter: Any, sketch_name: str) -> tuple[float, float]:
    feature = _feature_by_name(adapter, sketch_name)
    raw_sketch = _read_member(feature, "GetSpecificFeature2")
    if raw_sketch is None:
        raise RuntimeError(f"{sketch_name}: GetSpecificFeature2 returned null")
    sketch = _early_bound(raw_sketch, "ISketch")
    raw_segments = _read_member(sketch, "GetSketchSegments")
    if raw_segments is None:
        raise RuntimeError(f"{sketch_name}: GetSketchSegments returned null")
    segments = tuple(raw_segments)
    if len(segments) != 1:
        raise RuntimeError(
            f"{sketch_name}: expected one circle, found {len(segments)} segments"
        )
    arc = _early_bound(segments[0], "ISketchArc")
    point = _read_member(arc, "GetCenterPoint2")
    if point is None:
        raise RuntimeError(f"{sketch_name}: GetCenterPoint2 returned null")
    point = _early_bound(point, "ISketchPoint")
    center = tuple(float(_read_member(point, axis)) * 1000.0 for axis in ("X", "Y"))
    if len(center) != 2 or not all(math.isfinite(value) for value in center):
        raise RuntimeError(f"{sketch_name}: invalid native centre {center!r}")
    return center


def _axis_points_mm(adapter: Any, axis_name: str) -> tuple[float, ...]:
    feature = _feature_by_name(adapter, axis_name)
    raw_axis = _read_member(feature, "GetSpecificFeature2")
    if raw_axis is None:
        raise RuntimeError(f"{axis_name}: GetSpecificFeature2 returned null")
    axis = _early_bound(raw_axis, "IRefAxis")
    raw = _read_member(axis, "GetRefAxisParams")
    if raw is None:
        raise RuntimeError(f"{axis_name}: GetRefAxisParams returned null")
    points = tuple(float(value) * 1000.0 for value in raw)
    if len(points) != 6 or not all(math.isfinite(value) for value in points):
        raise RuntimeError(f"{axis_name}: invalid native axis endpoints {points!r}")
    return points


def assert_signed_circle_center(
    adapter: Any,
    sketch_name: str,
    *,
    label: str,
    expected_sketch_xy_mm: tuple[float, float],
    expected_model_xyz_mm: tuple[float, float, float],
    axis_name: str | None = None,
    axis_expected_components_mm: dict[int, float] | None = None,
) -> None:
    """Read rebuilt native geometry and reject a mirrored signed-distance branch.

    Sketch coordinates are read from the actual ``ISketchArc`` centre after the
    final equation rebuild.  Seam grooves additionally read their named
    ``IRefAxis`` endpoints and compare the model-space components perpendicular
    to the axis, tying the cut to the assembly reference rather than its seed.
    """

    actual = _circle_center_mm(adapter, sketch_name)
    axis_points: tuple[float, ...] | None = None
    if axis_name is not None:
        if not axis_expected_components_mm:
            raise ValueError(f"{label}: axis expectations are required")
        axis_points = _axis_points_mm(adapter, axis_name)

    record: dict[str, Any] = {
        "label": label,
        "sketch": sketch_name,
        "sketch_actual_xy_mm": list(actual),
        "sketch_expected_xy_mm": list(expected_sketch_xy_mm),
        "model_expected_xyz_mm": list(expected_model_xyz_mm),
        "tolerance_mm": _POSITION_TOL_MM,
    }
    if axis_points is not None:
        record["axis"] = {
            "name": axis_name,
            "actual_start_xyz_mm": list(axis_points[:3]),
            "actual_end_xyz_mm": list(axis_points[3:]),
            "expected_components_mm": {
                str(index): value
                for index, value in sorted(axis_expected_components_mm.items())
            },
        }
    _telemetry.info("crank.signed_center " + json.dumps(record, sort_keys=True))

    mismatches = [
        f"sketch[{index}] actual {actual[index]:.9g}, expected {expected:.9g}"
        for index, expected in enumerate(expected_sketch_xy_mm)
        if not math.isclose(
            actual[index], expected, rel_tol=0.0, abs_tol=_POSITION_TOL_MM
        )
    ]
    if axis_points is not None:
        for index, expected in axis_expected_components_mm.items():
            start = axis_points[index]
            end = axis_points[index + 3]
            if not math.isclose(
                start, expected, rel_tol=0.0, abs_tol=_POSITION_TOL_MM
            ) or not math.isclose(
                end, expected, rel_tol=0.0, abs_tol=_POSITION_TOL_MM
            ):
                mismatches.append(
                    f"axis[{index}] start/end ({start:.9g}, {end:.9g}), "
                    f"expected {expected:.9g}"
                )
    if mismatches:
        raise RuntimeError(f"{label}: rebuilt signed position mismatch: " + "; ".join(mismatches))
