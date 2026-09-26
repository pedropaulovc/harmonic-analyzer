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
            _telemetry.info(f"GDT-DIAG {label} symbol {json.dumps(record)}")
        view = view.GetNextView()
