"""Fresh native proof of the two supplier physical head-height dimensions.

``Type2 == swLinearDimension`` alone says nothing about sheet orientation.  The
native arrow records must independently prove a vertical dimension at the exact
projected physical stations, at the view's current scale, as well as passing the
unchanged named-edge/native-value assertion.

The 1e-8 m sheet-position bound inherits the recipes' exact physical-edge
GetClosestPointOn predicate and equals the existing 1e-5 mm model-height
precision.  For these sub-metre coordinates it conservatively exceeds IEEE
double transform roundoff; it is not fitted to a native receipt.  The independent
model-height tolerance remains unchanged.  The 1e-9 normalized direction bound
is an exact-axis numerical check, not an angular layout allowance.

SDK: IDisplayDimension.Type2 / swDimensionType_e.swLinearDimension (2),
IAnnotation.GetDisplayData, IDisplayData.GetArrowHeadCount / GetArrowHeadAtIndex2
([tipXYZ, directionXYZ, width, height, style, normalXYZ]), and IView.ScaleDecimal
(getter only).  This assertion never selects, modifies, rebuilds, or saves.
"""

from __future__ import annotations

import math
from typing import Any

from _com import _early_bound
from _drawing_edge_dimensions import assert_dimension_measures
from _drawing_projection import model_points_in_view
import _telemetry


__all__ = ["assert_native_physical_head_height"]

_POSITION_TOL_M = 1e-8
_DIRECTION_TOL = 1e-9


def _native_integer(value: Any, name: str) -> int:
    # Do not truncate a malformed count/type (2.5), parse text, or accept bool.
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a native integer, got {repr(value)[:120]}")
    return value


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number, got {repr(value)[:120]}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite, got {number!r}")
    return number


@_telemetry.traced("drawing.physical_head_height_native_assert", label_param="label")
def assert_native_physical_head_height(
    adapter: Any,
    view: Any,
    display: Any,
    *,
    entities: tuple[Any, Any],
    points_m: tuple[tuple[float, float, float], tuple[float, float, float]],
    expected_mm: float,
    label: str = "SupplierHeadHeight",
) -> float:
    """Return the unchanged shared measured millimetres only if every proof holds.

    All native metadata, attachments, value, arrows, scale and projected stations
    are read anew on every invocation, including settled/saved callers.  Failure
    evidence is bounded, records the failing stage, and chains the original
    binder/getter/proof exception rather than replacing it with diagnostic work.
    """
    snapshot: dict[str, Any] = {"display_null": display is None}
    stage = "display"
    try:
        if display is None:
            raise RuntimeError("native display dimension is null")
        stage = "display_bind"
        display = _early_bound(display, "IDisplayDimension")
        stage = "annotation"
        raw_annotation = display.GetAnnotation()
        snapshot["annotation_null"] = raw_annotation is None
        if raw_annotation is None:
            raise RuntimeError("native dimension has no annotation")
        stage = "annotation_bind"
        annotation = _early_bound(raw_annotation, "IAnnotation")
        stage = "application_bind"
        app = _early_bound(adapter.swApp, "ISldWorks")
        stage = "type2"
        snapshot["type2"] = _native_integer(display.Type2, "Type2")
        stage = "attached_count"
        snapshot["attached_count"] = _native_integer(
            annotation.GetAttachedEntityCount3(), "attached count"
        )
        stage = "attached_entities"
        attached = annotation.GetAttachedEntities3()
        attached_length = 0 if attached is None else len(attached)
        snapshot["attached_length"] = attached_length
        snapshot["attached_nulls"] = tuple(
            attached[index] is None for index in range(min(attached_length, 4))
        )
        stage = "attached_types"
        raw_kinds = annotation.GetAttachedEntityTypes()
        kinds_length = 0 if raw_kinds is None else len(raw_kinds)
        snapshot["kinds_length"] = kinds_length
        snapshot["kinds"] = tuple(
            _native_integer(raw_kinds[index], f"attachment type {index}")
            for index in range(min(kinds_length, 4))
        )
        stage = "dangling"
        dangling = annotation.IsDangling()
        if not isinstance(dangling, bool):
            raise TypeError("IsDangling must return a native boolean")
        snapshot["dangling"] = dangling
        stage = "owner_type"
        snapshot["owner_type"] = _native_integer(annotation.OwnerType, "OwnerType")
        stage = "owner"
        owner = annotation.Owner
        snapshot["owner_null"] = owner is None
        stage = "owner_same"
        snapshot["owner_same"] = (
            None if owner is None else _native_integer(app.IsSame(owner, view), "owner IsSame")
        )

        stage = "metadata_predicates"
        if snapshot["type2"] != 2:  # swDimensionType_e.swLinearDimension ONLY
            raise RuntimeError("expected linear dimension Type2=2")
        if snapshot["owner_type"] != 0 or snapshot["owner_null"] or snapshot["owner_same"] != 1:
            raise RuntimeError("expected exact front-view owner (OwnerType=0, IsSame=1)")
        if (
            snapshot["attached_count"] != 2 or attached_length != 2
            or kinds_length != 2 or snapshot["kinds"] != (1, 1)  # swSelEDGES
            or any(snapshot["attached_nulls"]) or snapshot["dangling"]
        ):
            raise RuntimeError("expected two nonnull actual edge attachments, not dangling")

        stage = "physical_inputs"
        if len(entities) != 2 or any(entity is None for entity in entities):
            raise ValueError("expected two nonnull named physical edges")
        expected = _finite_number(expected_mm, "expected_mm")
        if expected <= 0:
            raise ValueError("expected_mm must be positive")
        if len(points_m) != 2 or any(len(point) != 3 for point in points_m):
            raise ValueError("expected exactly two physical model XYZ stations")
        physical_points = tuple(
            tuple(_finite_number(value, f"physical station {index} coordinate {axis}")
                  for axis, value in enumerate(point))
            for index, point in enumerate(points_m)
        )
        snapshot["points_m"] = physical_points
        stage = "physical_measurement"
        # Preserve the existing exact unordered edge bijection, finiteness and
        # native model-value tolerance (default 1e-5 mm), without a second guard.
        measured_mm = assert_dimension_measures(
            adapter, display, expected_mm=expected_mm, label=label, entities=entities
        )
        snapshot["measured_mm"] = measured_mm

        stage = "display_data"
        raw_data = annotation.GetDisplayData()
        snapshot["display_data_null"] = raw_data is None
        if raw_data is None:
            raise RuntimeError("native annotation has no display data")
        stage = "display_data_bind"
        data = _early_bound(raw_data, "IDisplayData")
        stage = "arrow_count"
        snapshot["arrow_count"] = _native_integer(data.GetArrowHeadCount(), "arrow count")
        if snapshot["arrow_count"] != 2:
            raise RuntimeError("expected exactly two native arrow heads")
        arrow_heads: list[tuple[float, ...]] = []
        arrow_lengths: list[int | None] = []
        snapshot["arrow_heads"] = arrow_heads
        snapshot["arrow_lengths"] = arrow_lengths
        directions: list[tuple[float, float, float]] = []
        for index in range(2):
            stage = f"arrow_head_{index}"
            raw_arrow = data.GetArrowHeadAtIndex2(index)
            length = None if raw_arrow is None else len(raw_arrow)
            arrow_lengths.append(length)
            if raw_arrow is None:
                raise RuntimeError(f"native arrow head {index} is null")
            # Only evidence is truncated: acceptance always requires all 12 SDK
            # doubles, including width/height/style/normal, finite and present.
            arrow = tuple(
                _finite_number(raw_arrow[slot], f"arrow head {index} slot {slot}")
                for slot in range(min(length, 12))
            )
            arrow_heads.append(arrow)
            if length != 12:
                raise RuntimeError(f"native arrow head {index} must contain exactly 12 doubles")
            stage = f"arrow_direction_{index}"
            norm = math.hypot(*arrow[3:6])
            if not math.isfinite(norm) or norm <= 0:
                raise RuntimeError(f"native arrow head {index} direction must be finite and nonzero")
            unit = (arrow[3] / norm, arrow[4] / norm, arrow[5] / norm)
            directions.append(unit)
            if (
                abs(unit[0]) > _DIRECTION_TOL or abs(unit[2]) > _DIRECTION_TOL
                or abs(abs(unit[1]) - 1.0) > _DIRECTION_TOL
            ):
                raise RuntimeError(f"native arrow head {index} direction is not sheet-vertical")
        tips = tuple(arrow[:3] for arrow in arrow_heads)
        snapshot["arrow_tips"] = tips
        snapshot["arrow_directions"] = tuple(directions)
        stage = "arrow_geometry"
        if directions[0][1] * directions[1][1] >= 0:
            raise RuntimeError("native vertical arrow directions must have opposite Y signs")
        if any(abs(tip[2]) > _POSITION_TOL_M for tip in tips):
            raise RuntimeError("native arrow tips must lie in the sheet Z plane")
        if abs(tips[0][0] - tips[1][0]) > _POSITION_TOL_M:
            raise RuntimeError("native vertical arrow tips must have the same sheet X")
        native_ys = tuple(sorted(tip[1] for tip in tips))
        span_m = native_ys[1] - native_ys[0]
        snapshot["span_m"] = span_m
        if not math.isfinite(span_m) or span_m <= 0:
            raise RuntimeError("native vertical arrow span must be finite and positive")

        stage = "view_bind"
        native_view = _early_bound(view, "IView")
        stage = "scale_decimal"
        scale = _finite_number(native_view.ScaleDecimal, "ScaleDecimal")
        snapshot["scale_decimal"] = scale
        if scale <= 0:
            raise RuntimeError("native view ScaleDecimal must be positive")
        expected_span_m = expected / 1000.0 * scale
        snapshot["expected_span_m"] = expected_span_m
        if not math.isfinite(expected_span_m) or expected_span_m <= 0:
            raise RuntimeError("scaled physical height must be finite and positive")
        stage = "station_projection"
        projected = model_points_in_view(adapter, view, points_m, label=label)
        snapshot["projected_length"] = len(projected)
        if len(projected) != 2 or any(len(point) != 2 for point in projected):
            raise RuntimeError("expected exactly two projected physical sheet XY stations")
        sheet_points = tuple(
            tuple(_finite_number(value, f"projected station {index} coordinate {axis}")
                  for axis, value in enumerate(point))
            for index, point in enumerate(projected)
        )
        station_ys = tuple(sorted(point[1] for point in sheet_points))
        snapshot["projected_station_ys"] = station_ys
        projected_span = station_ys[1] - station_ys[0]
        snapshot["projected_span_m"] = projected_span
        stage = "station_geometry"
        if not math.isfinite(projected_span) or projected_span <= 0:
            raise RuntimeError("projected physical station span must be finite and positive")
        if abs(projected_span - expected_span_m) > _POSITION_TOL_M:
            raise RuntimeError("projected physical station span disagrees with scaled physical height")
        if any(abs(actual - station) > _POSITION_TOL_M
               for actual, station in zip(native_ys, station_ys, strict=True)):
            raise RuntimeError("native arrow tips do not match the projected physical station Ys")
        if (
            abs(span_m - projected_span) > _POSITION_TOL_M
            or abs(span_m - expected_span_m) > _POSITION_TOL_M
        ):
            raise RuntimeError("native arrow span disagrees with projected/scaled physical height")
    except Exception as exc:
        reason = str(exc)[:500]
        snapshot.update(
            failure_stage=stage, failure_error_type=type(exc).__name__, failure_error=reason
        )
        _telemetry.event("drawing.physical_head_height_native_refusal", reason=reason, **snapshot)
        prefix = "" if reason.startswith(label) else f"{label}: "
        raise RuntimeError(f"{prefix}{reason}; native_snapshot={snapshot!r}") from exc

    _telemetry.event("drawing.physical_head_height_native_proof", **snapshot)
    return measured_mm
