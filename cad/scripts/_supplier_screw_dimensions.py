"""Import exact supplier screw envelopes and dress their native reference sizes.

The part owns every measured value. Supplier spelling is only units/precision;
rounded drawing text never becomes construction geometry or a value override.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name

from _com import _early_bound
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_projection import model_points_in_view
from _supplier_dimensions import supplier_reference_dimension
from _supplier_screw_reference import FEATURE_BY_PLANE


def annotate_supplier_screw(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    dimensions: Sequence[tuple[str, float, str]],
    formats: Mapping[str, tuple[int, str, int | None, str | None]],
    starts: Mapping[str, tuple[float, float]] | None = None,
    planes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Curate the model's supplier dimensions into their own orthographic views.

    ``formats`` rows are precision, length/diameter/angle, optional inch fraction
    denominator and optional below-callout. Values remain the exact model sizes.
    Sketch coordinates are millimetres in the source Front/Top plane. Native
    projection places short head-height sizes at the head, not mid-shank.
    """
    starts = starts or {}
    planes = planes or {}
    names = {name for name, _, _ in dimensions}
    if names != set(formats) or len(names) != len(dimensions):
        raise ValueError("supplier screw references and display formats must match")
    displays: dict[str, Any] = {}
    for plane, feature in FEATURE_BY_PLANE.items():
        rows = [row for row in dimensions if planes.get(row[0], "Front") == plane]
        if not rows:
            continue
        view = _early_bound(views[f"*{plane}"], "IView")
        outline = tuple(float(value) for value in view.GetOutline())
        if len(outline) != 4:
            raise RuntimeError(f"{plane}: supplier reference view has no native outline")
        points = []
        for name, value, orientation in rows:
            x, y = starts.get(name, (0.0, 0.0))
            if orientation == "horizontal":
                x += value / 2.0
            elif orientation == "vertical":
                y += value / 2.0
            points.append(
                (x / 1000.0, y / 1000.0, 0.0)
                if plane == "Front"
                else (x / 1000.0, 0.0, -y / 1000.0)
            )
        projected = model_points_in_view(
            adapter, view, points, label=f"{plane} supplier reference centres"
        )
        keep = {}
        lanes = {"horizontal": 0, "vertical": 0, "angle": 0}
        for (name, _, orientation), (x, y) in zip(rows, projected, strict=True):
            lane = lanes[orientation]
            lanes[orientation] += 1
            offset = 0.006 + (lane // 2) * 0.008
            if orientation == "vertical":
                x = outline[2] + offset if lane % 2 == 0 else outline[0] - offset
            elif orientation == "horizontal":
                y = outline[3] + offset if lane % 2 == 0 else outline[1] - offset
            else:
                x = outline[0] - offset
            keep[name] = (x, y)
        annotations = curate_view_dimensions(
            adapter,
            view,
            keep=keep,
            view_label=f"{plane} supplier screw references",
            dimensions_by_feature={feature: set(keep)},
        )
        values = {name: value for name, value, _ in rows}
        for annotation in annotations:
            name = dimension_name(adapter, annotation)
            precision, presentation, denominator, callout = formats[name]
            display = _early_bound(annotation, "IAnnotation").GetSpecificAnnotation()
            angular = presentation == "angle"
            displays[name] = supplier_reference_dimension(
                adapter,
                display,
                label=f"{name}@{feature}",
                units="deg" if angular else "in",
                precision=precision,
                expected_mm=None if angular else abs(values[name]),
                expected_degrees=values[name] if angular else None,
                presentation=presentation,
                fraction_denominator=denominator,
                callout=callout,
            )
    return displays
