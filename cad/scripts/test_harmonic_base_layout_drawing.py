"""Actual table-compaction and native-packer contracts without a COM seat."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

import _drawing_harmonic_base_layout as layout
from _drawing_annotation_bounds import AnnotationBounds, TextRun
from _drawing_native_layout import NativeLayoutStatus
from _drawing_view_packing import Rect
from test_native_layout_drawing import Annotation, View, scene


def _font():
    return SimpleNamespace(
        TypeFaceName="Century Gothic",
        CharHeight=0.0035,
        CharHeightInPts=13,
        WidthFactor=1.0,
        CharSpacingFactor=1.0,
        LineLength=0.0,
        LineSpacing=1.0,
        Escapement=0.0,
        ObliqueAngle=0.0,
        Bold=False,
        Italic=False,
        Underline=False,
        Strikeout=False,
        BackWards=False,
        UpsideDown=False,
        Vertical=False,
        IsHeightSpecifiedInPts=lambda: False,
    )


class Table:
    RowCount = TotalRowCount = 18
    ColumnCount = TotalColumnCount = 4
    AnchorType = 1
    Anchored = False

    def __init__(self):
        self.annotation = Annotation(
            "hole-table", Rect(0.274, -0.014, 0.418, 0.256), kind=14
        )
        self.heights = [0.015] * 18
        self.minimums = [0.008] + [0.006] * 17
        self.widths = [0.028, 0.028, 0.028, 0.060]
        self.gaps = [0.001] * 18
        self.locks = [False] * 18
        self.cells = [[f"cell-{row}-{col}" for col in range(4)] for row in range(18)]
        self.fonts = [[_font() for _col in range(4)] for _row in range(18)]
        self.font = _font()
        self.row_writes = []
        self.on_row = lambda _row: None
        self.split = (0, 0, 1, 0, 17)

    def GetAnnotation(self):
        return self.annotation

    def GetSplitInformation(self, *_args):
        return self.split

    def GetRowHeight(self, row):
        return self.heights[row]

    def GetColumnWidth(self, column):
        return self.widths[column]

    def GetRowVerticalGap(self, row):
        return self.gaps[row]

    def GetLockRowHeight(self, row):
        return self.locks[row]

    def GetUseDocTextFormat(self):
        return True

    def GetTextFormat(self):
        return self.font

    def GetCellUseDocTextFormat(self, _row, _column):
        return True

    def GetCellTextFormat(self, row, column):
        return self.fonts[row][column]

    def DisplayedText(self, row, column):
        return self.cells[row][column]

    def SetRowHeight(self, row, height, options):
        self.row_writes.append((row, height, options))
        self.heights[row] = max(height, self.minimums[row])
        self.on_row(row)
        return self.heights[row]


def _measure(_adapter, annotation):
    box = annotation.rectangle
    return AnnotationBounds(
        name=annotation.name,
        kind=annotation.kind,
        anchor=annotation.position[:2],
        body=box,
        envelope=box,
        text_boxes=(box,),
        text_runs=(
            TextRun(
                annotation.text,
                annotation.position[:2],
                0.0035,
                annotation.font,
                0.0,
                1,
                0,
            ),
        ),
        leader_segments=(),
        format_signature=(annotation.font, 0.0035),
        native_strokes=(),
    )


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(layout, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(layout, "annotation_box", _measure)
    table = Table()
    top = View("top", Rect(-0.003, 0.125, 0.226, 0.240))
    top.ScaleRatio = (1.0, 2.0)
    side = View("side", Rect(0.270, 0.080, 0.384, 0.086))
    side.ScaleRatio = (1.0, 4.0)
    manufacturing = Annotation("manufacturing", Rect(0.016, 0.030, 0.246, 0.090))
    caption = Annotation("side-caption", Rect(0.260, 0.095, 0.340, 0.105))
    adapter, _options, _events = scene(
        monkeypatch,
        {"top": top, "side": side},
        [table.annotation, manufacturing, caption],
    )
    adapter.swApp.ActiveDoc = adapter.currentModel
    sheet_view = adapter.currentModel.GetFirstView()
    sheet = adapter.currentModel.GetCurrentSheet()
    sheet.GetProperties2 = lambda: (0, 0, 1, 2, 0, 0.4318, 0.2794, 0)
    sheet.GetZoneMargin = lambda _index: 0.0127
    sheet_view.GetTableAnnotations = lambda: [table]
    top.GetTableAnnotations = side.GetTableAnnotations = lambda: []
    options = dict(
        table=table,
        views={"top": top, "side": side},
        manufacturing_note=SimpleNamespace(GetAnnotation=lambda: manufacturing),
        side_note=SimpleNamespace(GetAnnotation=lambda: caption),
    )
    return SimpleNamespace(
        adapter=adapter,
        table=table,
        top=top,
        side=side,
        sheet_view=sheet_view,
        manufacturing=manufacturing,
        caption=caption,
        options=options,
    )


def _compact(setup):
    drawable, title = layout._sheet_bounds(setup.adapter)
    return layout._compact_table(
        setup.adapter,
        setup.table,
        setup.table.annotation,
        drawable,
        title,
    )


def test_native_minimum_readbacks_preserve_all_cells_formats_and_padding(setup):
    before = layout._table_state(setup.table)
    result = _compact(setup)
    assert result == replace(before, heights=tuple(setup.table.minimums))
    assert setup.table.row_writes == [(row, 0.0, 0) for row in range(18)]
    assert setup.table.annotation.GetPosition() == pytest.approx((0.2746, 0.2662, 0.0))
    assert layout._box(
        result, setup.table.annotation.GetPosition()
    ).bounds == pytest.approx((0.2746, 0.1562, 0.4186, 0.2662))


@pytest.mark.parametrize("result", [0.0, -1.0, float("nan"), float("inf"), 0.016])
def test_bad_native_row_height_stops_before_table_or_view_movement(setup, result):
    setup.table.SetRowHeight = lambda *_args: result
    with pytest.raises(RuntimeError, match="row 0 rejected minimum height"):
        _compact(setup)
    assert setup.table.annotation.moves == []
    assert setup.top.moves == setup.side.moves == []


def test_row_readback_mismatch_stops_before_later_rows_or_anchor_write(setup):
    original = setup.table.SetRowHeight

    def mismatch(row, height, options):
        original(row, height, options)
        return 0.007

    setup.table.SetRowHeight = mismatch
    with pytest.raises(RuntimeError, match="row 0 height readback differs"):
        _compact(setup)
    assert setup.table.row_writes == [(0, 0.0, 0)]
    assert setup.table.annotation.moves == []


def test_native_row_exception_is_retained_without_downstream_writes(setup):
    error = RuntimeError("native row setter rejected this cell")

    def reject(row):
        if row == 2:
            raise error

    setup.table.on_row = reject
    with pytest.raises(
        RuntimeError, match="native row setter rejected this cell"
    ) as caught:
        _compact(setup)
    assert caught.value is error
    assert setup.table.row_writes == [(row, 0.0, 0) for row in range(3)]
    assert setup.table.annotation.moves == []


@pytest.mark.parametrize("field", layout._FORMAT_FIELDS)
def test_any_last_cell_font_field_change_during_compaction_is_rejected(setup, field):
    def drift(row):
        if row != 17:
            return
        fmt = setup.table.fonts[17][3]
        before = getattr(fmt, field)
        setattr(fmt, field, "Other font" if isinstance(before, str) else before + 0.25)

    setup.table.on_row = drift
    with pytest.raises(RuntimeError, match="compaction changed table content/font"):
        _compact(setup)
    assert setup.table.annotation.moves == []


@pytest.mark.parametrize(
    "change", ["text", "table_font", "points_mode", "width", "gap", "lock", "anchor"]
)
def test_other_table_drift_is_rejected_before_positioning(setup, change):
    def drift(row):
        if row != 17:
            return
        table = setup.table
        if change == "text":
            table.cells[17][3] = "WRONG DRILL SIZE"
        if change == "table_font":
            table.font.CharHeight = 0.002
        if change == "points_mode":
            table.fonts[17][3].IsHeightSpecifiedInPts = lambda: True
        if change == "width":
            table.widths[3] += 0.001
        if change == "gap":
            table.gaps[17] += 0.001
        if change == "lock":
            table.locks[17] = True
        if change == "anchor":
            table.annotation.position = (0.273, 0.256, 0.0)

    setup.table.on_row = drift
    with pytest.raises(RuntimeError, match="compaction changed table content/font"):
        _compact(setup)
    assert setup.table.annotation.moves == []


@pytest.mark.parametrize("change", ["locks", "position"])
def test_failed_compaction_retains_expected_actual_heights_and_changed_fields(
    setup,
    monkeypatch,
    change,
):
    before = layout._table_state(setup.table)
    original_position = setup.table.annotation.position
    records = []
    monkeypatch.setattr(
        layout._telemetry,
        "error",
        lambda message, **attrs: records.append((message, attrs)),
    )

    def drift(row):
        if row != 17:
            return
        if change == "locks":
            setup.table.locks[0] = True
        if change == "position":
            setup.table.annotation.position = (0.274, 0.250, 0.0)

    setup.table.on_row = drift
    with pytest.raises(
        RuntimeError, match="compaction changed table content/font"
    ) as caught:
        _compact(setup)
    evidence = caught.value.evidence
    assert evidence["changed_fields"] == [change]
    assert evidence["actual_heights"] == tuple(setup.table.minimums)
    assert evidence["expected_position"] == original_position
    assert evidence["actual_position"] == setup.table.annotation.position
    assert evidence["expected_state"]["heights"] == tuple(setup.table.minimums)
    assert evidence["expected_state"]["cells"] == before.cells
    assert evidence["actual_state"]["cells"] == before.cells
    assert evidence["position_read_error"] is None
    assert records[0][1]["changed_fields"] == [change]
    assert records[0][1]["actual_heights"] == tuple(setup.table.minimums)
    assert setup.table.annotation.moves == []


@pytest.mark.parametrize("secondary", ["position", "telemetry"])
def test_failed_compaction_diagnostics_cannot_replace_preservation_failure(
    setup, monkeypatch, secondary
):
    error = OSError(f"native {secondary} diagnostic failed")
    telemetry_error = layout._telemetry.error

    def drift(row):
        if row != 17:
            return
        setup.table.locks[0] = True

        def reject(*_args, **_kwargs):
            raise error

        if secondary == "position":
            monkeypatch.setattr(setup.table.annotation, "GetPosition", reject)
        if secondary == "telemetry":

            def reject_diagnostic(message, **attrs):
                # Exercise this newly inserted write, not the existing outer
                # telemetry span's separate exception-reporting boundary.
                if "expected_state" in attrs:
                    raise error
                return telemetry_error(message, **attrs)

            monkeypatch.setattr(layout._telemetry, "error", reject_diagnostic)

    setup.table.on_row = drift
    with pytest.raises(
        layout.TableCompactionReadbackError,
        match="compaction changed table content/font",
    ) as caught:
        _compact(setup)
    evidence = caught.value.evidence
    assert evidence["actual_heights"] == tuple(setup.table.minimums)
    assert evidence["actual_state"]["locks"][0] == 1
    assert evidence["expected_state"]["locks"][0] == 0
    assert "locks" in evidence["changed_fields"]
    if secondary == "position":
        assert evidence["actual_position"] is None
        assert evidence["position_read_error"] == repr(error)
    if secondary == "telemetry":
        assert any(repr(error) in note for note in caught.value.__notes__)
        assert evidence["position_read_error"] is None
    assert setup.table.annotation.moves == []
    assert setup.top.moves == setup.side.moves == []


@pytest.mark.parametrize(
    "inventory",
    ["tables", "annotations", "unknown_table", "unknown_annotation", "null_annotation"],
)
def test_missing_or_unknown_native_table_is_rejected_before_any_write(setup, inventory):
    if inventory == "tables":
        setup.sheet_view.GetTableAnnotations = lambda: []
    if inventory == "annotations":
        setup.sheet_view.annotations.remove(setup.table.annotation)
    if inventory == "unknown_table":
        setup.sheet_view.GetTableAnnotations = lambda: [setup.table, Table()]
    if inventory == "unknown_annotation":
        setup.sheet_view.annotations.append(Table().annotation)
    if inventory == "null_annotation":
        setup.sheet_view.annotations.append(None)
    with pytest.raises(
        RuntimeError, match="missing from native|unexpected|contains null"
    ):
        layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert setup.table.row_writes == []
    assert setup.table.annotation.moves == []
    assert setup.top.moves == setup.side.moves == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("RowCount", 17),
        ("TotalRowCount", 19),
        ("ColumnCount", 3),
        ("TotalColumnCount", 5),
        ("AnchorType", 2),
        ("Anchored", True),
        ("split", (1, 0, 2, 0, 8)),
    ],
)
def test_changed_native_table_shape_or_anchor_is_rejected_before_writes(
    setup, field, value
):
    setattr(setup.table, field, value)
    with pytest.raises(RuntimeError, match="must retain|must remain"):
        layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert setup.table.row_writes == []
    assert setup.table.annotation.moves == []


@pytest.mark.parametrize(
    "movement,message",
    [
        ("reject", "rejected measured upper-right"),
        ("ignore", "did not reach measured upper-right"),
    ],
)
def test_table_anchor_failure_is_not_reported_as_measured_fit(setup, movement, message):
    setup.table.annotation.movement = movement
    with pytest.raises(RuntimeError, match=message):
        layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert setup.top.moves == setup.side.moves == []


def test_native_minimum_too_tall_reports_no_fit_without_moving_any_anchor(setup):
    setup.table.minimums = [0.014] * 18
    with pytest.raises(RuntimeError, match="compacted table no_fit"):
        layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert setup.table.heights == [0.014] * 18
    assert setup.table.annotation.moves == []
    assert setup.top.moves == setup.side.moves == []


def test_actual_packer_moves_views_and_caption_around_the_exact_measured_table(setup):
    table_before = layout._table_state(setup.table)
    caption_before = setup.caption.position
    result = layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert result.status is NativeLayoutStatus.APPLIED
    assert setup.top.moves
    assert setup.top.ScaleRatio == (1.0, 2.0)
    assert setup.side.ScaleRatio == (1.0, 4.0)
    assert layout._table_state(setup.table) == replace(
        table_before, heights=tuple(setup.table.minimums)
    )
    assert len(setup.table.annotation.moves) == 1  # Never moved by the packer.
    table_bounds = layout._box(
        layout._table_state(setup.table), setup.table.annotation.position
    )
    assert table_bounds in result.fixed_bounds.values()
    assert setup.caption.position[:2] == pytest.approx(
        tuple(
            a + b
            for a, b in zip(
                caption_before[:2], result.translations["view:side"], strict=True
            )
        )
    )
    for box in result.after_bounds.values():
        assert box.xmin >= result.drawable.xmin
        assert box.ymin >= result.drawable.ymin
        assert box.xmax <= result.drawable.xmax
        assert box.ymax <= result.drawable.ymax
        assert (
            max(
                table_bounds.xmin - box.xmax,
                box.xmin - table_bounds.xmax,
                table_bounds.ymin - box.ymax,
                box.ymin - table_bounds.ymax,
            )
            >= 0.002 - 1e-12
        )


def test_actual_packer_no_fit_preserves_deliberate_view_scales(setup):
    setup.top.rectangle = Rect(0, 0, 0.45, 0.15)
    with pytest.raises(RuntimeError, match="native print no_fit"):
        layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert setup.top.moves == setup.side.moves == []
    assert setup.top.ScaleRatio == (1.0, 2.0)
    assert setup.side.ScaleRatio == (1.0, 4.0)


@pytest.mark.parametrize("active", [None, object()])
def test_wrong_active_document_prevents_all_layout_writes(setup, active):
    setup.adapter.swApp.ActiveDoc = active
    with pytest.raises(RuntimeError, match="not the active drawing"):
        layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert setup.table.row_writes == []
    assert setup.table.annotation.moves == []
    assert setup.top.moves == setup.side.moves == []


def test_callable_active_document_dispatch_is_read_as_property_not_invoked(setup):
    class CallableDocument(SimpleNamespace):
        def __call__(self):
            raise AssertionError("COM object-valued property must not be invoked")

    model = CallableDocument(**vars(setup.adapter.currentModel))
    setup.adapter.currentModel = setup.adapter.swApp.ActiveDoc = model
    result = layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert result.status is NativeLayoutStatus.APPLIED


@pytest.mark.parametrize("change", ["cell", "font", "height", "replace", "unknown"])
def test_rebuild_table_drift_cannot_pass_final_packing(setup, change):
    def rebuild():
        if change == "cell":
            setup.table.cells[17][3] = "WRONG FINAL SIZE"
        if change == "font":
            setup.table.fonts[17][3].CharHeight = 0.002
        if change == "height":
            setup.table.heights[17] += 0.001
        if change == "replace":
            setup.table.annotation = deepcopy(setup.table.annotation)
        if change == "unknown":
            setup.sheet_view.GetTableAnnotations = lambda: [setup.table, Table()]
        return True

    setup.adapter.currentModel.EditRebuild3 = rebuild
    with pytest.raises(
        RuntimeError,
        match="changed during packing|replaced/unknown|unexpected native table",
    ):
        layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
