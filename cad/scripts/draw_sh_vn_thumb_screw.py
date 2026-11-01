"""Create the shared purchased reference sheet for McMaster 91882A221."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from math import dist, isfinite
from typing import Any

from solidworks_mcp.adapters import sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import dimension_name, iter_views

import _config
import _seat_forensics
import _telemetry
from _com import _early_bound
from _drawing_annotation_extent import CLEAR_GAP_M, PLACE_SETTLE_M, sheet_region
from _drawing_common import is_pictorial_orientation, rebuild_drawing
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_layout_audit import _Reader, _dump_annotation
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME, DRAWING_TEMPLATES
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import (
    assert_supplier_view_fits,
    build_purchased_fastener_drawing,
    fastener_view_cells,
    view_band_bottom,
)
from _session import run_build
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_screw_reference_names import FEATURE_BY_PLANE
from _layout_audit import (
    FindingSeverity,
    annotation_geometry,
    audit_dump,
    calibrate_sheet_advance,
    display_box,
    line_segment,
    severity,
)
import sh_vn_thumb_screw_spec as supplier
from _machinist_review_mode import MachinistReviewMode

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["sh_vn_thumb_screw"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#4-40 x 7/16 RAISED KNURLED-HEAD THUMB SCREW"
# The supplier puts the head span below and collar/thread spans above. Native
# text is wider than either .094 span, and at 2:1 also wider than the .438
# span. Decide which values need shelves from measured ink and witness span.
_AXIAL_NAMES = ("SupplierHeadHeight", "SupplierCollarHeight", "SupplierThreadLength")
_SUPPLIER_LANES = {
    "head_height": ("bottom", 0.008),
    "collar_height": ("top", 0.006),
    "thread_length": ("top", 0.016),
    "head_diameter": ("left", 0.020),
    "collar_diameter": ("right", 0.040),
    "thread_diameter": ("right", 0.012),
}
# Native 9aae text is 3.5 mm high; its line sits 2.7781 mm below the requested
# annotation point. These separated lanes need 16/20 mm below/above the actual
# padded outline, not the old stacked 24/34 mm. Fitting still measures every
# native scale: the observed 11.4028 mm fixed outline padding is not scaled.
# Preserve the native-observed text envelope during the initial view fit:
# head text reaches 14.0069 mm left and diameter text reaches 25.4278 mm right.
# The conservative 66.5 mm right reserve permits 4:1. Final diameter lanes
# are placed from measured witness lines and text bounds, not this budget.
_SUPPLIER_TEXT_ROOM = {"left": 0.0145, "bottom": 0.008, "right": 0.0265, "top": 0.004}
_POSITION_TOLERANCE_M = 1e-5  # Same 10 um as imported-dimension placement readback.
# Printed thread-diameter ink tops sit 1.06 mm above the native text box (farm
# audit 20261031T195237722Z): at the bare 2.2 mm drop the collar witness stood
# 1.14 mm from the ink and the thread line crossed it within half a text height.
# The extra 1.5 mm leaves ~2.6 mm printed clearance on both counts.
_THREAD_TEXT_DROP_M = 0.0015
SUPPLIER_MARGINS = {
    "*Front": tuple(
        max(offset for side, offset in _SUPPLIER_LANES.values() if side == edge)
        + _SUPPLIER_TEXT_ROOM[edge]
        for edge in ("left", "bottom", "right", "top")
    )
}


def _supplier_positions(
    outline: Sequence[float], axis: Sequence[tuple[float, float]]
) -> dict[str, tuple[float, float]]:
    """Route against the actual fitted outline, not a nominal scaled radius."""
    if (
        len(outline) != 4
        or len(axis) != 4
        or not all(isfinite(value) for value in outline)
        or not all(len(point) == 2 and all(map(isfinite, point)) for point in axis)
        or outline[0] >= outline[2]
        or outline[1] >= outline[3]
    ):
        raise RuntimeError("thumb supplier layout has no finite fitted geometry")
    if max(point[1] for point in axis) - min(point[1] for point in axis) > 1e-7:
        raise RuntimeError("thumb Front view does not project its axis horizontally")
    center_y = axis[0][1]
    centers = {
        "head_height": ((axis[0][0] + axis[1][0]) / 2.0, center_y),
        "collar_height": ((axis[1][0] + axis[2][0]) / 2.0, center_y),
        "thread_length": ((axis[2][0] + axis[3][0]) / 2.0, center_y),
        "head_diameter": (0.0, center_y),
        "collar_diameter": (0.0, center_y),
        # These are initial stations only. Native diameter text is measured
        # against the collar witnesses after formatting/import has settled.
        "thread_diameter": (0.0, center_y),
    }
    positions = {}
    for name, (side, offset) in _SUPPLIER_LANES.items():
        x, y = centers[name]
        if side == "left":
            x = outline[0] - offset
        elif side == "right":
            x = outline[2] + offset
        elif side == "bottom":
            y = outline[1] - offset
        else:
            y = outline[3] + offset
        positions[_supplier_name(name)] = (x, y)
    return positions


def _station_circle(edges: Any, station_mm: float, *, label: str) -> Any:
    """Find a physical rim at a finished axial face, including a chamfered rim.

    All fragments in the selected plane share the same axial station; the
    largest remaining circle avoids small thread/knurl cutter intersections.
    Its radius is not used as a nominal diameter.
    """
    circles = [
        item
        for item in edges.circles
        if abs(item.circle[0] - station_mm) < 1e-5
        and abs(item.circle[1]) < 1e-5
        and abs(item.circle[2]) < 1e-5
        and abs(abs(item.circle[3]) - 1.0) < 1e-6
    ]
    if not circles:
        raise RuntimeError(f"{label}: no physical circular rim at X={station_mm:g} mm")
    return max(circles, key=lambda item: item.circle[6]).edge


def _supplier_name(name: str) -> str:
    return "Supplier" + "".join(word.title() for word in name.split("_"))


def _name_supplier_dimension(display: Any, name: str) -> None:
    native = _early_bound(
        _early_bound(display, "IDisplayDimension").GetDimension2(0), "IDimension"
    )
    native.Name = _supplier_name(name)
    if str(native.FullName).split("@", 1)[0] != _supplier_name(name):
        raise RuntimeError(f"{name}: supplier dimension name did not persist")


def _assert_physical_rims(display: Any, stations: tuple[float, float]) -> None:
    """Reacquire final attachments and prove their physical finished planes."""
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    if len(attached) != 2:
        raise RuntimeError("thumb axial reference must retain two physical rims")
    actual = []
    for raw in attached:
        curve = _early_bound(raw, "IEdge").GetCurve()
        if curve is None:
            raise RuntimeError("thumb axial reference no longer attaches to a rim")
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            raise RuntimeError("thumb axial reference no longer attaches to a rim")
        values = tuple(float(value) for value in curve.CircleParams)
        if (
            abs(values[1]) > 1e-8
            or abs(values[2]) > 1e-8
            or abs(abs(values[3]) - 1.0) > 1e-6
        ):
            raise RuntimeError("thumb axial reference left its coaxial finished plane")
        actual.append(values[0] * 1000.0)
    if any(
        abs(value - expected) > 1e-5
        for value, expected in zip(sorted(actual), sorted(stations), strict=True)
    ):
        raise RuntimeError("thumb axial reference attaches to the wrong finished faces")


def _assert_reference_diameter(display: Any, name: str) -> None:
    """Prove the imported envelope still belongs to its exact model carrier."""
    native = _early_bound(display.GetDimension2(0), "IDimension")
    identity = str(native.FullName).split("@")
    if identity[:2] != [_supplier_name(name), FEATURE_BY_PLANE["Front"]]:
        raise RuntimeError(f"{name}: supplier envelope changed native source owner")


def _supplier_displays(adapter: Any) -> dict[str, Any]:
    """Reacquire the sheet's exact native display-dimension inventory."""
    views = list(iter_views(adapter))
    fronts = [view for view in views if view.GetOrientationName() == "*Front"]
    if len(fronts) != 1:
        raise RuntimeError(
            "thumb supplier sheet must have exactly one final Front view"
        )
    found = {}
    for raw_view in views:
        current_view = _early_bound(raw_view, "IView")
        display = current_view.GetFirstDisplayDimension6()
        while display is not None:
            display = _early_bound(display, "IDisplayDimension")
            native = _early_bound(display.GetDimension2(0), "IDimension")
            name = str(native.FullName).split("@", 1)[0]
            if name in found or current_view.GetOrientationName() != "*Front":
                raise RuntimeError(
                    "thumb supplier references duplicated or changed owner"
                )
            found[name] = display
            display = display.GetNext5()
    return found


def _assert_supplier_positions(
    found: Mapping[str, Any],
    positions: Mapping[str, tuple[float, float]],
    short_geometry: Mapping[str, Mapping[str, Any]],
) -> None:
    if set(found) != set(positions):
        raise RuntimeError("thumb sheet lost or added a supplier dimension")
    for name, display in found.items():
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        actual = tuple(float(value) for value in annotation.GetPosition())
        if (
            bool(display.OffsetText)
            != bool(short_geometry.get(name, {}).get("shelved"))
            or len(actual) != 3
            or not all(map(isfinite, actual))
            or dist(actual[:2], positions[name]) > _POSITION_TOLERANCE_M
        ):
            raise RuntimeError(
                f"{name}: settled thumb supplier dimension left its lane"
            )


def _supplier_annotation_record(adapter: Any, display: Any) -> dict[str, Any]:
    """Read the real audit record, including native offset-text leaders."""
    reader = _Reader(adapter)
    record = _dump_annotation(reader, display.GetAnnotation())
    refused = reader.take_errors()
    if refused or record is None or int(record.get("type", 0)) != 4:
        raise RuntimeError(f"thumb supplier annotation read failed: {refused}")
    data = record.get("display") or {}
    if not data.get("texts"):
        raise RuntimeError(
            "thumb supplier dimension has unreadable native text/line ink"
        )
    if any(
        not isfinite(float(row.get("w") or 0.0)) or float(row.get("w") or 0.0) <= 0.0
        for row in data["texts"]
    ):
        raise RuntimeError("thumb supplier text has no measured native width")
    return record


def _supplier_display_data(adapter: Any, display: Any) -> dict[str, Any]:
    return _supplier_annotation_record(adapter, display)["display"]


def _short_native_geometry(record: Mapping[str, Any]) -> dict[str, Any]:
    """Native witness stations and arrow tips, plus the fresh line/arrow reach."""
    data = record["display"]
    arrows = data.get("arrows") or ()
    if len(arrows) != 2 or any(
        len(row) < 8 or not all(isfinite(float(value)) for value in row)
        for row in arrows
    ):
        raise RuntimeError(
            "short thumb supplier dimension has unreadable native arrows"
        )
    tips = tuple(sorted((float(row[0]), float(row[1])) for row in arrows))
    geometry = annotation_geometry(
        record, owner="*Front", advance=calibrate_sheet_advance((record,))
    )
    if geometry is None:
        raise RuntimeError("short thumb supplier dimension has no native line geometry")
    witnesses = []
    for x, _y in tips:
        runs = [
            segment
            for segment in geometry.segments
            if segment.role == "ext-line"
            and abs(segment.x1 - segment.x0) < 1e-7
            and abs(segment.x0 - x) <= _POSITION_TOLERANCE_M
        ]
        if not runs:
            raise RuntimeError("short thumb supplier dimension lost a native witness")
        ys = [y for segment in runs for y in (segment.y0, segment.y1)]
        witnesses.append((x, min(ys), max(ys)))
    physical_lines = [
        segment
        for segment in geometry.segments
        if segment.role == "dim-line"
        and abs(segment.y1 - segment.y0) < 1e-7
        and any(
            dist(tip, endpoint) <= _POSITION_TOLERANCE_M
            for tip in tips
            for endpoint in ((segment.x0, segment.y0), (segment.x1, segment.y1))
        )
    ]
    if any(
        not any(
            dist(tip, endpoint) <= _POSITION_TOLERANCE_M
            for segment in physical_lines
            for endpoint in ((segment.x0, segment.y0), (segment.x1, segment.y1))
        )
        for tip in tips
    ):
        raise RuntimeError(
            "short thumb supplier dimension lost a tip-incident native line"
        )
    # Offset text can draw an unregistered connector and underline. When these
    # become collinear with the physical line they are also classified dim-line,
    # but neither has an endpoint at a physical arrow tip (native 012dd).
    # They remain in the full raw-path ink audit, never in the physical tail reach.
    reach = [
        x
        for segment in (
            *physical_lines,
            *(segment for segment in geometry.segments if segment.role == "arrow"),
        )
        for x in (segment.x0, segment.x1)
    ]
    if not reach:
        raise RuntimeError("short thumb supplier dimension lost native line/arrow ink")
    return {
        "tips": tips,
        "witnesses": tuple(witnesses),
        "left": min(reach),
        "physical_line_runs": tuple(
            {
                "start": (segment.x0, segment.y0),
                "end": (segment.x1, segment.y1),
                "length_m": segment.length,
            }
            for segment in physical_lines
        ),
    }


def _short_native_snapshot(
    adapter: Any, display: Any, record: Mapping[str, Any]
) -> dict[str, Any]:
    """Diagnostic-only readbacks; none of these policy reads approve geometry."""
    reader = _Reader(adapter)
    typed = reader.need(
        lambda: _early_bound(display, "IDisplayDimension"), name="IDisplayDimension"
    )
    properties = {}
    for name, expected_type in (
        ("OffsetText", bool),
        ("SmartWitness", bool),
        ("ArrowSide", int),
        ("LeaderVisibility", int),
        ("MaxWitnessLineLength", float),
    ):
        value = reader.need(
            lambda name=name: getattr(typed, name), name=f"IDisplayDimension.{name}"
        )
        properties[name] = (
            value
            if type(value) is expected_type
            else {"unmeasured": True, "unexpected_result": repr(value)}
        )
    gaps = {}
    for index in (0, 1):
        # The generated wrapper returns (success, UseDoc, Gap), not byref VARIANTs.
        result = reader.need(
            lambda index=index: typed.GetWitnessLineGap(index, False, 0.0),
            name=f"IDisplayDimension.GetWitnessLineGap[{index}]",
        )
        if (
            isinstance(result, (tuple, list))
            and len(result) == 3
            and type(result[0]) is bool
            and type(result[1]) is bool
            and type(result[2]) is float
            and isfinite(result[2])
        ):
            gaps[index] = {
                "success": result[0],
                "unmeasured": not result[0],
                "uses_document": result[1] if result[0] else None,
                "gap_m": result[2] if result[0] else None,
                "native_result": result,
            }
        else:
            gaps[index] = {"unmeasured": True, "unexpected_result": repr(result)}

    def document_gap() -> float:
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        if model is None:
            raise RuntimeError("no active drawing model for witness-gap diagnostic")
        extension = _early_bound(model.Extension, "IModelDocExtension")
        if extension is None:
            raise RuntimeError("no drawing extension for witness-gap diagnostic")
        return extension.GetUserPreferenceDouble(
            sw_type_info.constant("swDetailingWitnessLineGap"),
            sw_type_info.constant("swDetailingNoOptionSpecified"),
        )

    preference = reader.need(
        document_gap, name="IModelDocExtension.GetUserPreferenceDouble(witness-gap)"
    )
    snapshot = {
        "native": record,
        "properties": properties,
        "witness_gaps": gaps,
        "document_witness_gap_m": (
            preference
            if type(preference) is float and isfinite(preference)
            else {"unmeasured": True, "unexpected_result": repr(preference)}
        ),
        "read_errors": reader.take_errors(),
    }

    def segment_data(segment: Any) -> dict[str, Any]:
        return {
            "role": segment.role,
            "start": (segment.x0, segment.y0),
            "end": (segment.x1, segment.y1),
        }

    try:
        geometry = annotation_geometry(
            record, owner="*Front", advance=calibrate_sheet_advance((record,))
        )
        if geometry is None:
            raise RuntimeError("no classified native annotation geometry")
        snapshot["classified_segments"] = [
            segment_data(segment) for segment in geometry.segments
        ]
        snapshot["arrow_tails"] = [
            segment_data(segment) for segment in geometry.arrow_tails
        ]
        raw_lines = [
            (index, segment)
            for index, row in enumerate(record["display"].get("lines") or ())
            if (segment := line_segment(row)) is not None
        ]
        per_tip_runs = []
        for index, arrow in enumerate(record["display"].get("arrows") or ()):
            if len(arrow) < 2:
                continue
            x, y = float(arrow[0]), float(arrow[1])
            if not all(isfinite(value) for value in (x, y)):
                continue
            per_tip_runs.append(
                {
                    "arrow_index": index,
                    "tip": (x, y),
                    "classified_witness_runs": [
                        segment_data(segment)
                        for segment in geometry.segments
                        if segment.role == "ext-line"
                        and abs(segment.x1 - segment.x0) < 1e-7
                        and abs(segment.x0 - x) <= _POSITION_TOLERANCE_M
                    ],
                    # Keep the role-free raw rows too: a leader/shoulder that was
                    # misclassified must remain distinguishable from a real witness.
                    "raw_vertical_runs": [
                        {"line_index": row, **segment_data(segment)}
                        for row, segment in raw_lines
                        if abs(segment.x1 - segment.x0) < 1e-7
                        and abs(segment.x0 - x) <= _POSITION_TOLERANCE_M
                    ],
                }
            )
        snapshot["per_tip_runs"] = per_tip_runs
    except Exception as error:
        snapshot["classification_error"] = {
            "type": type(error).__name__,
            "message": str(error),
        }
    return snapshot


def _log_short_native_transition(phase: str, dimensions: Mapping[str, Any]) -> None:
    payload = {
        "schema": 1,
        "phase": phase,
        "tolerance_m": _POSITION_TOLERANCE_M,
        "dimensions": dimensions,
    }
    try:
        encoded = json.dumps(payload, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as error:
        # A malformed native value must not erase the evidence or replace the
        # original layout refusal with a JSON-serialization exception.
        encoded = json.dumps(
            {
                "schema": 1,
                "phase": phase,
                "serialization_error": str(error),
                "native_state_repr": repr(payload),
            },
            sort_keys=True,
            allow_nan=False,
        )
    _telemetry.info("thumb_supplier_native_geometry_transition " + encoded)


def _read_settled_short_geometry(
    adapter: Any,
    found: Mapping[str, Any],
    expected: Mapping[str, Mapping[str, Any]],
    *,
    phase: str,
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    if set(expected) != set(_AXIAL_NAMES):
        raise RuntimeError("thumb supplier axial-line proof inventory changed")
    fresh = {}
    transitions = {}
    failures = {}
    for name in _AXIAL_NAMES:
        before = expected[name]["native_before"]
        after = {}
        comparison = {}
        try:
            record = _supplier_annotation_record(adapter, found[name])
            after = _short_native_snapshot(adapter, found[name], record)
            actual = _short_native_geometry(record)
            after["computed"] = actual
            for key in ("tips", "witnesses"):
                old, new = expected[name][key], actual[key]
                pairs = [
                    {
                        "index": index,
                        "before": prior,
                        "after": current,
                        "delta_m": tuple(
                            b - a for a, b in zip(prior, current, strict=True)
                        ),
                        "distance_m": dist(prior, current),
                    }
                    for index, (prior, current) in enumerate(zip(old, new))
                ]
                comparison[key] = {
                    "count_before": len(old),
                    "count_after": len(new),
                    "pairs": pairs,
                    "max_distance_m": max(
                        (pair["distance_m"] for pair in pairs), default=0.0
                    ),
                    "changed": len(old) != len(new)
                    or any(
                        pair["distance_m"] > _POSITION_TOLERANCE_M for pair in pairs
                    ),
                }
            # Smart arrows may flip; their freshly classified ink, not stale
            # arrays, still governs clearance. The station guards are unchanged.
            fresh[name] = (record, actual)
        except Exception as error:
            failures[name] = error
            after["guard_error"] = {"type": type(error).__name__, "message": str(error)}
        transitions[name] = {
            "before": before,
            "after": after,
            "comparison": comparison,
            "shelved": expected[name]["shelved"],
        }
    # Collect every axial dimension before the first refusal, including the
    # complete unclassified display arrays and registered native leaders.
    _log_short_native_transition(phase, transitions)
    for name in _AXIAL_NAMES:
        if name in failures:
            raise failures[name]
        for key, change in transitions[name]["comparison"].items():
            if change["changed"]:
                raise RuntimeError(
                    f"{name}: native supplier witness/arrow station moved; "
                    f"phase={phase}; key={key}; max_distance_m={change['max_distance_m']:.9g}; "
                    f"counts={change['count_before']}->{change['count_after']}"
                )
    return fresh


def _assert_shelved_short_text(
    adapter: Any,
    found: Mapping[str, Any],
    expected: Mapping[str, Mapping[str, Any]],
    *,
    phase: str,
) -> None:
    for name, (record, actual) in _read_settled_short_geometry(
        adapter, found, expected, phase=phase
    ).items():
        text = display_box({"texts": record["display"]["texts"]})
        if text is None:
            raise RuntimeError(f"{name}: supplier axial text has no native ink")
        if expected[name]["shelved"]:
            clear = text.xmax <= actual["left"] - CLEAR_GAP_M
        else:
            left, right = (tip[0] for tip in actual["tips"])
            clear = text.xmin >= left + CLEAR_GAP_M and text.xmax <= right - CLEAR_GAP_M
        if not clear:
            raise RuntimeError(
                f"{name}: supplier axial text crowds its native line geometry"
            )


def _shelf_short_text(
    adapter: Any,
    found: Mapping[str, Any],
    positions: Mapping[str, tuple[float, float]],
    expected: Mapping[str, Mapping[str, Any]],
) -> dict[str, tuple[float, float]]:
    """Keep physical line stations fixed; shelf text beyond fresh native tails."""
    result = dict(positions)
    _log_short_native_transition(
        "before_offset_text_mode",
        {
            name: {
                "before": expected[name]["native_before"],
                "requested_text_position_m": (*positions[name], 0.0),
                "offset_text_requested": expected[name]["shelved"],
            }
            for name in _AXIAL_NAMES
        },
    )
    anchors = {}
    for name in _AXIAL_NAMES:
        if not expected[name]["shelved"]:
            continue
        display = found[name]
        if display.OffsetText is not False:
            raise RuntimeError(
                f"{name}: short supplier line was not placed before offset mode"
            )
        # Native 012dd made the offset-mode line pass through the old annotation
        # anchor, not its text baseline. Seed that anchor from BOTH measured
        # arrow tips before changing mode; never guess the font-dependent gap.
        left, right = expected[name]["tips"]
        if abs(left[1] - right[1]) > _POSITION_TOLERANCE_M:
            raise RuntimeError(
                f"{name}: short supplier dimension line is not horizontal"
            )
        anchor = (positions[name][0], (left[1] + right[1]) / 2)
        anchors[name] = anchor
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        if not annotation.SetPosition2(*anchor, 0.0):
            raise RuntimeError(
                f"{name}: failed to seed measured supplier offset anchor"
            )
    rebuild_drawing(adapter, label="thumb supplier measured pre-offset anchors")
    prepared = _supplier_displays(adapter)
    _log_short_native_transition(
        "prepared_offset_text_anchors",
        {
            name: {
                "before": expected[name]["native_before"],
                "prepared": _short_native_snapshot(
                    adapter,
                    prepared[name],
                    _supplier_annotation_record(adapter, prepared[name]),
                ),
                "measured_offset_anchor_m": (*anchors[name], 0.0),
            }
            for name in anchors
        },
    )
    for name, anchor in anchors.items():
        display = prepared[name]
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        actual = tuple(float(value) for value in annotation.GetPosition())
        if (
            len(actual) != 3
            or not all(isfinite(value) for value in actual)
            or dist(actual, (*anchor, 0.0)) > _POSITION_TOLERANCE_M
        ):
            raise RuntimeError(
                f"{name}: measured supplier offset anchor did not settle"
            )
        display.OffsetText = True
        if not annotation.SetPosition2(*anchor, 0.0):
            raise RuntimeError(
                f"{name}: failed to enable short thumb supplier text offset"
            )
    rebuild_drawing(adapter, label="thumb supplier short-span text mode")
    fresh = _supplier_displays(adapter)
    for name, (record, actual) in _read_settled_short_geometry(
        adapter, fresh, expected, phase="after_offset_text_mode"
    ).items():
        if not expected[name]["shelved"]:
            continue
        annotation = _early_bound(fresh[name].GetAnnotation(), "IAnnotation")
        text = display_box({"texts": record["display"]["texts"]})
        if text is None:
            raise RuntimeError(f"{name}: no settled native text for short-span shelf")
        current = tuple(float(value) for value in annotation.GetPosition())
        limit = actual["left"] - CLEAR_GAP_M - PLACE_SETTLE_M
        target = (current[0] + limit - text.xmax, positions[name][1])
        if not annotation.SetPosition2(*target, 0.0):
            raise RuntimeError(f"{name}: failed to shelf short thumb supplier text")
        result[name] = target
    rebuild_drawing(adapter, label="thumb supplier short-span text shelves")
    _assert_shelved_short_text(
        adapter, _supplier_displays(adapter), expected, phase="after_text_shelves"
    )
    return result


def _assert_supplier_paths(adapter: Any, found: Mapping[str, Any]) -> None:
    """Run the existing complete audit on native supplier records and live views.

    No PDF is available here; its printed ink/edge checks still belong to the
    final shared audit. Native leaders, text, arrows and view outlines are real.
    """
    records = [
        _supplier_annotation_record(adapter, display) for display in found.values()
    ]
    views = []
    for raw in iter_views(adapter):
        view = _early_bound(raw, "IView")
        orientation = str(view.GetOrientationName())
        views.append(
            {
                "name": str(view.GetName2()),
                "orientation": orientation,
                "pictorial": is_pictorial_orientation(orientation),
                "outline": tuple(float(value) for value in view.GetOutline()),
                "annotations": records if orientation == "*Front" else [],
            }
        )
    template = DRAWING_TEMPLATES[SPEC.layout]
    region = sheet_region(adapter)
    dump = {
        "sheet": "thumb supplier sheet",
        "width": template.width_m,
        "height": template.height_m,
        "zone": {
            "left": region.xmin,
            "bottom": region.ymin,
            "right": template.width_m - region.xmax,
            "top": template.height_m - region.ymax,
        },
        "views": views,
        "read_errors": {},
    }
    findings = [
        finding
        for finding in audit_dump(dump)
        if severity(finding) is FindingSeverity.GATING
    ]
    if findings:
        raise RuntimeError(
            "thumb supplier dimension paths are not clear:\n"
            + "\n".join(finding.format() for finding in findings)
        )


def _collar_native_stations(record: Mapping[str, Any]) -> tuple[float, float, float]:
    """The real vertical dimension line and its horizontal witness stations."""
    geometry = annotation_geometry(
        record, owner="*Front", advance=calibrate_sheet_advance((record,))
    )
    arrows = record["display"].get("arrows") or ()
    if geometry is None or len(arrows) != 2:
        raise RuntimeError("thumb collar diameter has no native line/witness geometry")
    vertical = [
        segment
        for segment in geometry.segments
        if segment.role == "dim-line" and abs(segment.x1 - segment.x0) < 1e-7
    ]
    tips = [float(row[1]) for row in arrows if len(row) >= 8]
    witnesses = [
        segment.y0
        for segment in geometry.segments
        if segment.role == "ext-line"
        and abs(segment.y1 - segment.y0) < 1e-7
        and any(abs(segment.y0 - y) <= _POSITION_TOLERANCE_M for y in tips)
    ]
    if not vertical or len(tips) != 2 or not witnesses:
        raise RuntimeError("thumb collar diameter lost a native line/witness station")
    x = vertical[0].x0
    lower, upper = min(witnesses), max(witnesses)
    if (
        not all(map(isfinite, (x, lower, upper)))
        or upper <= lower
        or any(abs(segment.x0 - x) > _POSITION_TOLERANCE_M for segment in vertical)
        or any(
            not any(abs(y - station) <= _POSITION_TOLERANCE_M for station in witnesses)
            for y in tips
        )
    ):
        raise RuntimeError("thumb collar diameter has inconsistent native stations")
    return x, lower, upper


def _diameter_vertical_gaps(
    adapter: Any, found: Mapping[str, Any]
) -> tuple[float, float, float]:
    collar_record = _supplier_annotation_record(
        adapter, found["SupplierCollarDiameter"]
    )
    _x, lower, upper = _collar_native_stations(collar_record)
    collar = display_box({"texts": collar_record["display"]["texts"]})
    thread = display_box(
        {
            "texts": _supplier_display_data(adapter, found["SupplierThreadDiameter"])[
                "texts"
            ]
        }
    )
    if collar is None or thread is None:
        raise RuntimeError("thumb supplier diameter has no measured native text")
    return collar.ymin - lower, upper - collar.ymax, lower - thread.ymax


def _assert_diameter_vertical_clearance(adapter: Any, found: Mapping[str, Any]) -> None:
    gaps = _diameter_vertical_gaps(adapter, found)
    if not all(isfinite(gap) and gap >= CLEAR_GAP_M for gap in gaps):
        raise RuntimeError(
            "thumb supplier diameter text crowds a native collar witness"
        )


def _place_diameter_vertical_stations(
    adapter: Any, positions: Mapping[str, tuple[float, float]]
) -> dict[str, tuple[float, float]]:
    """Center collar ink between witnesses; keep thread ink below the lower one."""
    result = dict(positions)
    # First author the measured stations, then settle any native text-alignment
    # change from moving inside/outside its span. Never refit or move a view.
    for _phase in range(2):
        found = _supplier_displays(adapter)
        collar_record = _supplier_annotation_record(
            adapter, found["SupplierCollarDiameter"]
        )
        _x, lower, upper = _collar_native_stations(collar_record)
        collar = display_box({"texts": collar_record["display"]["texts"]})
        thread = display_box(
            {
                "texts": _supplier_display_data(
                    adapter, found["SupplierThreadDiameter"]
                )["texts"]
            }
        )
        if collar is None or thread is None:
            raise RuntimeError("thumb supplier diameter has no measured native text")
        if collar.height + 2 * (CLEAR_GAP_M + PLACE_SETTLE_M) > upper - lower:
            raise RuntimeError(
                "thumb collar native text cannot fit between its witnesses"
            )
        shifts = {
            "SupplierCollarDiameter": (lower + upper) / 2 - collar.center()[1],
            "SupplierThreadDiameter": lower
            - CLEAR_GAP_M
            - PLACE_SETTLE_M
            - _THREAD_TEXT_DROP_M
            - thread.ymax,
        }
        moved = False
        for name, dy in shifts.items():
            if abs(dy) <= 1e-7:
                continue
            display = found[name]
            annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
            x, y, _z = (float(value) for value in annotation.GetPosition())
            target = (x, y + dy)
            display.OffsetText = False
            if not annotation.SetPosition2(*target, 0.0):
                raise RuntimeError(
                    f"{name}: failed to place measured diameter text station"
                )
            result[name] = target
            moved = True
        if not moved:
            break
        rebuild_drawing(adapter, label="thumb supplier measured diameter text stations")
    _assert_diameter_vertical_clearance(adapter, _supplier_displays(adapter))
    return result


def _diameter_text_gap(adapter: Any, found: Mapping[str, Any]) -> float:
    thread = found["SupplierThreadDiameter"]
    text = display_box({"texts": _supplier_display_data(adapter, thread)["texts"]})
    collar = _supplier_annotation_record(adapter, found["SupplierCollarDiameter"])
    if text is None:
        raise RuntimeError("thumb supplier thread diameter has no native text box")
    return _collar_native_stations(collar)[0] - text.xmax


def _assert_diameter_text_gap(adapter: Any, found: Mapping[str, Any]) -> None:
    gap = _diameter_text_gap(adapter, found)
    if not isfinite(gap) or gap < CLEAR_GAP_M:
        raise RuntimeError("thumb supplier collar line crowds the native thread text")


def _space_diameter_lines(
    adapter: Any, positions: Mapping[str, tuple[float, float]]
) -> dict[str, tuple[float, float]]:
    """Put the outer native line beyond measured inner text, after vertical fit."""
    found = _supplier_displays(adapter)
    gap = _diameter_text_gap(adapter, found)
    result = dict(positions)
    if not isfinite(gap):
        raise RuntimeError("thumb supplier diameter text spacing is not finite")
    if gap < CLEAR_GAP_M + PLACE_SETTLE_M:
        name = "SupplierCollarDiameter"
        display = found[name]
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        x, y = positions[name]
        target = (x + CLEAR_GAP_M + PLACE_SETTLE_M - gap, y)
        display.OffsetText = False
        if not annotation.SetPosition2(*target, 0.0):
            raise RuntimeError(
                "failed to space thumb supplier collar line beyond thread text"
            )
        result[name] = target
        rebuild_drawing(adapter, label="thumb supplier measured diameter text spacing")
    _assert_diameter_text_gap(adapter, _supplier_displays(adapter))
    return result


def _place_supplier_dimensions(
    adapter: Any, positions: Mapping[str, tuple[float, float]]
) -> tuple[dict[str, tuple[float, float]], dict[str, dict[str, Any]]]:
    """Place measured diameter stations and shelf axial text only where needed."""
    rebuild_drawing(adapter, label="thumb supplier formatting and import settled")
    found = _supplier_displays(adapter)
    if set(found) != set(positions):
        raise RuntimeError("thumb sheet lost or added a supplier dimension")
    for name, display in found.items():
        # SetPosition2 moves only the text while OffsetText is true. Turn it
        # off explicitly so the dimension line and witnesses follow the lane.
        display.OffsetText = False
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        x, y = positions[name]
        if not annotation.SetPosition2(x, y, 0.0):
            raise RuntimeError(f"{name}: failed to place thumb supplier dimension")
    rebuild_drawing(adapter, label="thumb supplier complete native lanes")
    result = _place_diameter_vertical_stations(adapter, positions)
    result = _space_diameter_lines(adapter, result)
    found = _supplier_displays(adapter)
    _assert_diameter_vertical_clearance(adapter, found)
    short_geometry = {}
    for name in _AXIAL_NAMES:
        record = _supplier_annotation_record(adapter, found[name])
        geometry = _short_native_geometry(record)
        text = display_box({"texts": record["display"]["texts"]})
        if text is None:
            raise RuntimeError(f"{name}: supplier axial text has no native ink")
        span = geometry["tips"][1][0] - geometry["tips"][0][0]
        geometry["shelved"] = text.width + 2 * (CLEAR_GAP_M + PLACE_SETTLE_M) > span
        before = _short_native_snapshot(adapter, found[name], record)
        before["computed"] = dict(geometry)
        geometry["native_before"] = before
        short_geometry[name] = geometry
    result = _shelf_short_text(adapter, found, result, short_geometry)
    _assert_supplier_positions(_supplier_displays(adapter), result, short_geometry)
    return result, short_geometry


@_telemetry.traced("drawing.thumb_supplier_settled")
def _assert_supplier_dimensions(
    adapter: Any,
    positions: Mapping[str, tuple[float, float]],
    short_geometry: Mapping[str, Mapping[str, Any]],
) -> None:
    """Prove all six native references after the finalizer's last rebuild."""
    found = _supplier_displays(adapter)
    _assert_supplier_positions(found, positions, short_geometry)
    _assert_shelved_short_text(
        adapter, found, short_geometry, phase="after_final_rebuild"
    )
    _assert_diameter_text_gap(adapter, found)
    _assert_diameter_vertical_clearance(adapter, found)
    _assert_supplier_paths(adapter, found)
    axial = {
        "head_height": (supplier.HEAD_H, (0.0, supplier.HEAD_H)),
        "collar_height": (
            supplier.COLLAR_H,
            (supplier.HEAD_H, supplier.HEAD_STACK_LEN),
        ),
        "thread_length": (
            supplier.SHANK_LEN,
            (supplier.HEAD_STACK_LEN, supplier.OVERALL_LEN),
        ),
    }
    diameters = {
        "head_diameter": supplier.HEAD_DIA,
        "collar_diameter": supplier.COLLAR_DIA,
        "thread_diameter": supplier.SHANK_DIA,
    }
    if set(found) != {_supplier_name(name) for name in (*axial, *diameters)}:
        raise RuntimeError("thumb sheet lost or added a supplier dimension")
    for name in (*axial, *diameters):
        display = found[_supplier_name(name)]
        value = axial[name][0] if name in axial else diameters[name]
        assert_supplier_reference_dimension(
            adapter,
            display,
            label=name,
            expected_mm=value,
            units=supplier.SUPPLIER_UNITS,
            precision=supplier.SUPPLIER_PRECISION[name],
            presentation="length" if name in axial else "diameter",
            callout=supplier.SUPPLIER_THREAD if name == "thread_diameter" else None,
        )
        native = _early_bound(display.GetDimension2(0), "IDimension")
        if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
            raise RuntimeError(f"{name}: supplier nominal acquired a fabrication band")
        if name in axial:
            _assert_physical_rims(display, axial[name][1])
        else:
            _assert_reference_diameter(display, name)


@_telemetry.traced("drawing.thumb_supplier_dimensions")
def supplier_dimensions(
    adapter: Any, views_by_orientation: dict[str, Any]
) -> tuple[dict[str, tuple[float, float]], dict[str, dict[str, Any]]]:
    """Three physical spans and three model-owned nominal diameter references."""
    view = _early_bound(views_by_orientation["*Front"], "IView")
    view.UpdateViewDisplayGeometry()
    stations = (0.0, supplier.HEAD_H, supplier.HEAD_STACK_LEN, supplier.OVERALL_LEN)
    axis = model_points_in_view(
        adapter,
        view,
        [(x / 1000.0, 0.0, 0.0) for x in stations],
        label="thumb supplier axial stations",
    )
    outline = tuple(float(value) for value in view.GetOutline())
    positions = _supplier_positions(outline, axis)
    # Use exactly the geometry bounds the pre-fit pass reserved, including
    # native sheet-space padding, rather than reconstructing a nominal radius.
    margin_left, margin_bottom, margin_right, margin_top = SUPPLIER_MARGINS["*Front"]
    envelope = (
        outline[0] - margin_left,
        outline[1] - margin_bottom,
        outline[2] + margin_right,
        outline[3] + margin_top,
    )
    notes = str(_config.parts(SPEC.source.stem).get("installation_notes", ""))
    cell = next(
        bounds
        for name, _, bounds in fastener_view_cells(
            view_band_bottom(notes, label=SPEC.artifact_stem)
        )
        if name == "*Front"
    )
    if (
        envelope[0] < cell[0]
        or envelope[1] < cell[1]
        or envelope[2] > cell[2]
        or envelope[3] > cell[3]
    ):
        raise RuntimeError(
            f"thumb supplier annotation lanes leave the actual Front cell: {envelope!r} vs {cell!r}"
        )
    edges = scan_view_edges(view, label="thumb supplier finished-face rims")
    rims = [
        _station_circle(edges, station, label=f"thumb station {station:g}")
        for station in stations
    ]
    for name, start, end, value in (
        ("head_height", 0, 1, supplier.HEAD_H),
        ("collar_height", 1, 2, supplier.COLLAR_H),
        ("thread_length", 2, 3, supplier.SHANK_LEN),
    ):
        entities = (rims[start], rims[end])
        display = add_edge_dimension(
            adapter,
            view,
            p0=axis[start],
            p1=axis[end],
            text_xy=positions[_supplier_name(name)],
            label=name,
            orientation="horizontal",
            entities=entities,
        )
        _name_supplier_dimension(display, name)
        assert_dimension_measures(
            adapter, display, expected_mm=value, label=name, entities=entities
        )
        supplier_reference_dimension(
            adapter,
            display,
            label=name,
            expected_mm=value,
            units=supplier.SUPPLIER_UNITS,
            precision=supplier.SUPPLIER_PRECISION[name],
        )
    locations = {
        name: positions[_supplier_name(name)]
        for name in ("head_diameter", "collar_diameter", "thread_diameter")
    }
    annotations = curate_view_dimensions(
        adapter,
        view,
        keep={_supplier_name(name): xy for name, xy in locations.items()},
        view_label="thumb supplier nominal envelope diameters",
        dimensions_by_feature={
            FEATURE_BY_PLANE["Front"]: {_supplier_name(name) for name in locations}
        },
    )
    native_to_name = {_supplier_name(name): name for name in locations}
    values = {
        "head_diameter": supplier.HEAD_DIA,
        "collar_diameter": supplier.COLLAR_DIA,
        "thread_diameter": supplier.SHANK_DIA,
    }
    for annotation in annotations:
        name = native_to_name[dimension_name(adapter, annotation)]
        display = _early_bound(
            _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        supplier_reference_dimension(
            adapter,
            display,
            label=name,
            expected_mm=values[name],
            units=supplier.SUPPLIER_UNITS,
            precision=supplier.SUPPLIER_PRECISION[name],
            presentation="diameter",
            callout=supplier.SUPPLIER_THREAD if name == "thread_diameter" else None,
        )
    # Formatting and the import/delete rebuild can displace an earlier
    # AddHorizontalDimension2 drop. Re-seat all six complete native lines,
    # never the fitted view, then measure actual text/line/arrow ink.
    positions, short_geometry = _place_supplier_dimensions(adapter, positions)
    view.UpdateViewDisplayGeometry()
    assert_supplier_view_fits(adapter, view, cell, label=f"{SPEC.artifact_stem} *Front")
    _assert_supplier_paths(adapter, _supplier_displays(adapter))
    return positions, short_geometry


def _capture_supplier_failure(adapter: Any, phase: str, error: Exception) -> None:
    """Preserve the live partial sheet without replacing its original failure."""
    try:
        _seat_forensics.capture_com_failure(
            adapter,
            f"thumb-supplier-{phase}",
            str(error),
            api="thumb supplier native dimension authoring/settled checks",
            exception=error,
            sheet_png=True,
            supplier_phase=phase,
            supplier_dimension_count=6,
            view_keys=("*Front",),
        )
    except Exception as capture_error:
        if capture_error is not error:
            error.add_note(f"thumb supplier forensic capture failed: {capture_error!r}")


async def build(adapter: Any) -> dict[str, str]:
    checks = []

    def annotate(current_adapter: Any, views: dict[str, Any]) -> None:
        try:
            positions, short_geometry = supplier_dimensions(current_adapter, views)
        except Exception as error:
            _capture_supplier_failure(current_adapter, "annotation", error)
            raise

        def settled() -> None:
            try:
                _assert_supplier_dimensions(current_adapter, positions, short_geometry)
            except Exception as error:
                _capture_supplier_failure(current_adapter, "settled", error)
                raise

        checks.append(settled)

    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=annotate,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=checks,
        unit=part_drawing_unit("sh-vn-thumb-screw"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
