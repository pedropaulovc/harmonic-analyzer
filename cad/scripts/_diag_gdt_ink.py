"""Diag only (never merge): dump every GD&T symbol's raw geometry on the sheet.

pc-858x928b: ``_drawing_common._measured_gdt_box`` read MHA-062's leadered
feature-control frames as a few-mm patch near a leader end, not the frame.
This logs, for every datum tag, feature-control frame and surface-finish
symbol on the current sheet, what SolidWorks reports -- position, text points,
every line/arc/triangle primitive, attach point, leader points -- next to the
box the audit computes, so the shared fix can rest on data.
"""

from __future__ import annotations

import json
from typing import Any

import _telemetry
from _common import _early_bound
from _drawing_common import (
    _ANNOT_GTOL,
    _GDT_IFACE,
    _GDT_TYPES,
    _gdt_element,
    _measured_gdt_box,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info


def _floats(value: Any) -> list[float] | None:
    if value is None:
        return None
    try:
        return [round(float(v), 6) for v in value]
    except TypeError:
        return [round(float(value), 6)]


def _try(record: dict[str, Any], key: str, call) -> None:
    try:
        record[key] = call()
    except Exception as exc:  # diag: record the failure, keep walking
        record[key] = f"!! {type(exc).__name__}: {exc}"


def _indexed(spec: Any, count: str, at: str) -> list[list[float] | None]:
    n = int(getattr(spec, count)() or 0)
    return [_floats(getattr(spec, at)(i)) for i in range(n)]


def _display_data(annotation: Any) -> dict[str, Any]:
    """IAnnotation.GetDisplayData, every primitive family, sheet space (#902)."""
    data = _sw_type_info.early_bound_or_flag(
        annotation.GetDisplayData(), "IDisplayData"
    )
    out: dict[str, Any] = {}

    def line(i: int) -> list[float] | None:
        try:
            return _floats(data.GetLineAtIndex3(i))
        except Exception:
            return _floats(data.GetLineAtIndex2(i))

    _try(out, "lines", lambda: [line(i) for i in range(int(data.GetLineCount() or 0))])
    _try(
        out,
        "arcs",
        lambda: [
            _floats(data.GetArcAtIndex2(i)) for i in range(int(data.GetArcCount() or 0))
        ],
    )
    _try(
        out,
        "polylines",
        lambda: [
            _floats(data.GetPolylineAtIndex2(i))
            for i in range(int(data.GetPolyLineCount() or 0))
        ],
    )
    _try(
        out,
        "triangles",
        lambda: [
            _floats(data.GetTriangleAtIndex(i))
            for i in range(int(data.GetTriangleCount() or 0))
        ],
    )
    _try(
        out,
        "ellipses",
        lambda: [
            _floats(data.GetEllipseAtIndex2(i))
            for i in range(int(data.GetEllipseCount() or 0))
        ],
    )

    def text(i: int) -> dict[str, Any]:
        item: dict[str, Any] = {"text": str(data.GetTextAtIndex(i))}
        _try(item, "position", lambda: _floats(data.GetTextPositionAtIndex(i)))
        _try(item, "height", lambda: float(data.GetTextHeightAtIndex(i)))
        _try(item, "angle", lambda: float(data.GetTextAngleAtIndex(i)))
        _try(item, "ref", lambda: int(data.GetTextRefPositionAtIndex(i)))
        _try(item, "box_w", lambda: float(data.GetTextInBoxWidthAtIndex(i)))
        _try(item, "box_h", lambda: float(data.GetTextInBoxHeightAtIndex(i)))
        return item

    _try(out, "texts", lambda: [text(i) for i in range(int(data.GetTextCount() or 0))])
    return out


def dump_sheet_gdt(adapter: Any, *, label: str) -> None:
    """Log one JSON record per GD&T symbol on every view of the current sheet."""
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    view = ddoc.GetFirstView()
    while view is not None:
        view = _early_bound(view, "IView")
        view_name = str(view.GetName2())
        view_record: dict[str, Any] = {"view": view_name}
        _try(view_record, "outline", lambda: _floats(view.GetOutline()))
        _try(view_record, "position", lambda: _floats(view.Position))
        _try(view_record, "scale", lambda: float(view.ScaleDecimal))
        _telemetry.info(f"GDT-DIAG {label} view {json.dumps(view_record)}")
        for raw in view.GetAnnotations() or ():
            annotation = _early_bound(raw, "IAnnotation")
            kind = int(annotation.GetType())
            if kind not in _GDT_TYPES:
                continue
            name = str(annotation.GetName())
            record: dict[str, Any] = {"view": view_name, "name": name, "kind": kind}
            _try(record, "position", lambda: _floats(annotation.GetPosition()))
            _try(
                record,
                "measured_box",
                lambda: _floats(_measured_gdt_box(adapter, annotation, kind)),
            )
            _try(
                record,
                "element_box",
                lambda: _floats(
                    (lambda e: (e.xmin, e.ymin, e.xmax, e.ymax))(
                        _gdt_element(adapter, annotation, name, kind)
                    )
                ),
            )
            _try(record, "leader_count", lambda: int(annotation.GetLeaderCount()))
            _try(record, "leader_style", lambda: int(annotation.GetLeaderStyle()))
            _try(
                record,
                "leader_points",
                lambda: [
                    _floats(annotation.GetLeaderPointsAtIndex(i))
                    for i in range(int(annotation.GetLeaderCount() or 0))
                ],
            )
            spec = _sw_type_info.early_bound_or_flag(
                annotation.GetSpecificAnnotation(), _GDT_IFACE[kind]
            )
            _try(
                record,
                "lines",
                lambda: _indexed(spec, "GetLineCount", "GetLineAtIndex"),
            )
            _try(record, "arcs", lambda: _indexed(spec, "GetArcCount", "GetArcAtIndex"))
            _try(
                record,
                "triangles",
                lambda: _indexed(spec, "GetTriangleCount", "GetTriangleAtIndex"),
            )
            _try(
                record,
                "text_positions",
                lambda: [
                    [
                        str(spec.GetTextAtIndex(i)),
                        _floats(spec.GetTextPositionAtIndex(i)),
                    ]
                    for i in range(int(spec.GetTextCount() or 0))
                ],
            )
            if kind == _ANNOT_GTOL:
                _try(record, "text_point", lambda: _floats(spec.GetTextPoint()))
                _try(record, "attach_pos", lambda: _floats(spec.GetAttachPos()))
                _try(record, "height", lambda: float(spec.GetHeight()))
                _try(record, "frame_count", lambda: int(spec.GetFrameCount()))
                _try(
                    record,
                    "leader_info",
                    lambda: _floats(spec.GetLeaderInfo()),
                )
            _try(record, "display_data", lambda: _display_data(annotation))
            if kind == _ANNOT_GTOL:
                sym: dict[str, Any] = {}
                for index in range(4):
                    _try(
                        sym,
                        f"edge_counts_{index}",
                        lambda: _floats(spec.GetSymEdgeCounts(index)),
                    )
                    _try(
                        sym, f"lines_{index}", lambda: _floats(spec.GetSymLines(index))
                    )
                    _try(sym, f"arcs_{index}", lambda: _floats(spec.GetSymArcs(index)))
                record["sym"] = sym
            _telemetry.info(f"GDT-DIAG {label} symbol {json.dumps(record)}")
        view = view.GetNextView()
