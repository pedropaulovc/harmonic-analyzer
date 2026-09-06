"""Native placement and measured packing for explicitly migrated drawings only.

Keep this entry point out of _drawing_common: static helper-closure analysis
must not make every manufacturing print depend on the native-layout pilot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Sequence

from _common import _early_bound
from _drawing_common import _TITLE_BLOCK_LEFT_M, _TITLE_BLOCK_TOP_M
import _telemetry

if TYPE_CHECKING:
    from _drawing_native_layout import AxisLink, LayoutNote, NativeLayoutReport
    from _drawing_view_packing import AxisOrder


@_telemetry.traced("drawing.project_native_layout")
def repair_project_drawing_layout(
    adapter: Any,
    *,
    views: Mapping[str, Any],
    alignments: Sequence[AxisLink] = (),
    orderings: Sequence[AxisOrder] = (),
    notes: Sequence[LayoutNote] = (),
) -> NativeLayoutReport:
    """Space native callouts and pack the complete measured single-sheet drawing.

    This is an explicit recipe choice while the fleet migrates to semantic
    attachments. It preserves view scale, annotation content and text format.
    Initial recipe coordinates seed native placement; they never identify model
    geometry or substitute for measured final fit. An unfit sheet is not exported.
    """
    from _drawing_annotation_bounds import annotation_box
    from _drawing_native_gtol import arrange_native_gtol_columns
    from _drawing_measurement_handoff import AnnotationMeasurementHandoff
    from _drawing_native_layout import NativeLayoutStatus, repair_native_layout
    from _drawing_view_packing import Rect
    from dataclasses import asdict
    import json

    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    properties = tuple(sheet.GetProperties2() or ())
    if len(properties) != 8:
        raise RuntimeError("native project layout requires complete sheet properties")
    title_block = Rect(
        _TITLE_BLOCK_LEFT_M, 0.0, float(properties[5]), _TITLE_BLOCK_TOP_M
    )
    handoff = AnnotationMeasurementHandoff(
        adapter, views=views, measure_annotation=annotation_box
    )
    try:
        arrange_native_gtol_columns(
            adapter,
            views=views,
            measure_annotation=annotation_box,
            record_measurement=handoff.record,
        )
        handoff.seal()
        report = repair_native_layout(
            adapter,
            views=views,
            title_block=title_block,
            measure_annotation=annotation_box,
            initial_measure_annotation=handoff.initial_measure,
            # Observed INote.GetExtent changes after exact anchor moves were up
            # to 0.266 mm. Extra planning room is not a native error bound or a
            # relaxation of the final 2 mm clearance check.
            planning_headroom_m=0.0005,
            alignments=alignments,
            orderings=orderings,
            notes=notes,
        )
    finally:
        handoff.close()
    _telemetry.info(
        "native sheet layout measured",
        layout_status=report.status.value,
        layout_report=json.dumps(asdict(report), default=lambda value: value.value),
    )
    if report.status in (NativeLayoutStatus.NO_FIT, NativeLayoutStatus.SEARCH_LIMIT):
        raise RuntimeError(f"native drawing layout {report.status.value}: {report.reason}")
    return report

