"""Actual construction-curve ink, independent of a drawing view's padded outline.

Callers prove the source model part, configuration, owning feature's error-free
state and shown reference inventory. Only unbroken, uncropped full views are
supported; callers settle UpdateViewDisplayGeometry before reading their frame.
Native 2-D construction lines and complete circles are captured once through
the actual sketch inverse, then projected through each current view frame.
Circle extrema are analytic projected-ellipse extrema, never nominal boxes.
Partial arcs and other unsupported ink refuse. A one-dimensional span is valid.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from _com import _bind, _early_bound
from _drawing_projection import model_points_in_view

# Same 1 nm coincidence budget as _sketch_closure, without importing that build
# verdict module into every supplier drawing's recipe dependency closure.
_VISIBLE_SPAN_TOL_M = 1e-9


@dataclass(frozen=True)
class NativeSketchGeometry:
    """Immutable actual model-metre geometry, with no live native handles."""

    model_points: tuple[tuple[float, float, float], ...]
    line_offsets: tuple[int, ...]
    circle_offsets: tuple[int, ...]

    def __post_init__(self) -> None:
        label = "captured native sketch geometry"
        if any(
            type(field) is not tuple
            for field in (
                self.model_points,
                self.line_offsets,
                self.circle_offsets,
            )
        ):
            raise RuntimeError(
                f"{label}: point and offset fields must be immutable tuples"
            )
        for index, point in enumerate(self.model_points):
            if (
                type(point) is not tuple
                or len(point) != 3
                or any(
                    type(value) is not float or not math.isfinite(value)
                    for value in point
                )
            ):
                raise RuntimeError(
                    f"{label}: model point {index} must be a finite float3 tuple"
                )
        for noun, offsets in (
            ("line", self.line_offsets),
            ("circle", self.circle_offsets),
        ):
            previous = -1
            for offset in offsets:
                if type(offset) is not int or offset <= previous:
                    raise RuntimeError(
                        f"{label}: {noun} offsets must be strictly increasing nonnegative integers"
                    )
                previous = offset
        if not self.line_offsets and not self.circle_offsets:
            raise RuntimeError(f"{label}: at least one curve is required")
        line = circle = cursor = 0
        while line < len(self.line_offsets) or circle < len(self.circle_offsets):
            if circle == len(self.circle_offsets) or (
                line < len(self.line_offsets)
                and self.line_offsets[line] < self.circle_offsets[circle]
            ):
                offset, count = self.line_offsets[line], 2
                line += 1
            else:
                offset, count = self.circle_offsets[circle], 3
                circle += 1
            if offset != cursor:
                raise RuntimeError(
                    f"{label}: curve offsets must cover every point exactly once"
                )
            cursor += count
        if cursor != len(self.model_points):
            raise RuntimeError(
                f"{label}: curve offsets must cover every point exactly once"
            )


def _point(raw: Any, *, label: str) -> tuple[float, float, float]:
    point = _early_bound(_bind(raw, "ISketchPoint"), "ISketchPoint")
    if point is None:
        raise RuntimeError(f"{label}: native construction point is missing")
    values = (float(point.X), float(point.Y), float(point.Z))
    if not all(map(math.isfinite, values)):
        raise RuntimeError(
            f"{label}: native construction point is nonfinite: {values!r}"
        )
    return values


def capture_native_sketch_geometry(sketch: Any, *, label: str) -> NativeSketchGeometry:
    """Capture actual model-part construction geometry without changing it.

    The caller proves the requested source configuration and an error-free
    owning IFeature before this call: erroneous sketches can return a partial
    GetSketchSegments inventory. The caller binds the returned value to its
    source document/configuration/view before restoring the source.

    Only actual rigid, unit-scale sketch transforms are supported. No nominal
    boxes, drawing-sketch coordinates, component transforms or live handles are
    returned. Unsupported ink refuses rather than disappearing from the bounds.
    """
    sketch = _early_bound(_bind(sketch, "ISketch"), "ISketch")
    if sketch is None or sketch.Is3D() is not False:
        raise RuntimeError(
            f"{label}: native construction bounds require a 2-D source sketch"
        )
    if sketch.GetSketchBlockInstanceCount() != 0:
        raise RuntimeError(f"{label}: unsupported native construction sketch blocks")
    if tuple(sketch.GetSketchTextSegments() or ()):
        raise RuntimeError(f"{label}: unsupported native construction sketch text")
    # Explicit user points are ink; automatic line endpoints/circle centres are
    # not separate point entities and must not be confused with this inventory.
    if sketch.GetUserPointsCount() != 0:
        raise RuntimeError(
            f"{label}: unsupported native construction sketch user points"
        )
    transform = _early_bound(
        _bind(sketch.ModelToSketchTransform, "IMathTransform"), "IMathTransform"
    )
    if transform is None:
        raise RuntimeError(f"{label}: source sketch transform is unavailable")
    inverse = _early_bound(
        _bind(transform.Inverse(), "IMathTransform"), "IMathTransform"
    )
    if inverse is None:
        raise RuntimeError(f"{label}: source sketch inverse is unavailable")
    matrix = tuple(float(value) for value in (inverse.ArrayData or ()))
    if (
        len(matrix) != 16
        or not all(map(math.isfinite, matrix))
        or abs(matrix[12] - 1.0) > 1e-12
    ):
        raise RuntimeError(f"{label}: invalid native source sketch inverse: {matrix!r}")
    segments = tuple(sketch.GetSketchSegments() or ())
    if not segments:
        raise RuntimeError(f"{label}: native construction sketch has no segments")
    local: list[tuple[float, float, float]] = []
    lines: list[int] = []
    circles: list[int] = []
    for index, raw in enumerate(segments):
        context = f"{label} segment {index}"
        segment = _early_bound(_bind(raw, "ISketchSegment"), "ISketchSegment")
        if segment is None or segment.ConstructionGeometry is not True:
            raise RuntimeError(
                f"{context}: native segment is not construction geometry"
            )
        kind = int(segment.GetType())
        offset = len(local)
        if kind == 0:  # swSketchLINE
            line = _early_bound(_bind(raw, "ISketchLine"), "ISketchLine")
            start = _point(line.GetStartPoint2(), label=context)
            end = _point(line.GetEndPoint2(), label=context)
            if start == end:
                raise RuntimeError(
                    f"{context}: native construction line has zero length"
                )
            local.extend((start, end))
            lines.append(offset)
        elif kind == 1:  # swSketchARC; only actual complete circles are supported.
            arc = _early_bound(_bind(raw, "ISketchArc"), "ISketchArc")
            if arc.IsCircle() != 1:  # VT_I4, not VT_BOOL
                raise RuntimeError(f"{context}: unsupported native partial arc")
            center = _point(arc.GetCenterPoint2(), label=context)
            radius = float(arc.GetRadius())
            if not math.isfinite(radius) or radius <= 0.0:
                raise RuntimeError(
                    f"{context}: invalid native circular geometry/radius"
                )
            local.extend(
                (
                    center,
                    (center[0] + radius, center[1], center[2]),
                    (center[0], center[1] + radius, center[2]),
                )
            )
            circles.append(offset)
        else:
            raise RuntimeError(
                f"{context}: unsupported native sketch segment type {kind}"
            )
    # Native SOLIDWORKS row-vector ArrayData, as in the frame assembly drawing.
    # Capture the actual source inverse ONCE; no native MathPoint per point.
    scale = matrix[12]
    model = tuple(
        (
            scale * (point[0] * matrix[0] + point[1] * matrix[3] + point[2] * matrix[6])
            + matrix[9],
            scale * (point[0] * matrix[1] + point[1] * matrix[4] + point[2] * matrix[7])
            + matrix[10],
            scale * (point[0] * matrix[2] + point[1] * matrix[5] + point[2] * matrix[8])
            + matrix[11],
        )
        for point in local
    )
    try:
        return NativeSketchGeometry(model, tuple(lines), tuple(circles))
    except RuntimeError as error:
        raise RuntimeError(f"{label}: {error}") from error


def native_sketch_view_bounds(
    adapter: Any,
    view: Any,
    geometry: NativeSketchGeometry,
    *,
    label: str,
) -> tuple[float, float, float, float]:
    """Project an immutable native capture through the current view frame.

    The caller proves the same model-part document/configuration/view binding,
    an uncropped/unbroken full view, and refreshes UpdateViewDisplayGeometry
    immediately before this call. No source document/configuration/geometry is
    read or changed here, including during final settled checks.
    """
    if type(geometry) is not NativeSketchGeometry:
        raise RuntimeError(f"{label}: expected immutable NativeSketchGeometry capture")
    projected = model_points_in_view(adapter, view, geometry.model_points, label=label)
    # The shared projector guarantees pairs, not finite values. Validate EVERY
    # result before min/max can silently discard a non-first NaN.
    if not all(math.isfinite(value) for point in projected for value in point):
        raise RuntimeError(f"{label}: invalid native construction projection")
    occupied = []
    for offset in geometry.line_offsets:
        occupied.extend(projected[offset : offset + 2])
    for offset in geometry.circle_offsets:
        center, xpoint, ypoint = projected[offset : offset + 3]
        a = (xpoint[0] - center[0], xpoint[1] - center[1])
        b = (ypoint[0] - center[0], ypoint[1] - center[1])
        rx, ry = (math.hypot(a[axis], b[axis]) for axis in (0, 1))
        occupied.extend(
            ((center[0] - rx, center[1] - ry), (center[0] + rx, center[1] + ry))
        )
    bounds = (
        min(point[0] for point in occupied),
        min(point[1] for point in occupied),
        max(point[0] for point in occupied),
        max(point[1] for point in occupied),
    )
    if (
        not all(map(math.isfinite, bounds))
        or max(bounds[2] - bounds[0], bounds[3] - bounds[1]) <= _VISIBLE_SPAN_TOL_M
    ):
        raise RuntimeError(f"{label}: native construction has no finite visible span")
    return bounds
