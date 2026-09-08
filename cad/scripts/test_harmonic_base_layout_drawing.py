"""Two-sheet table preservation and actual native-packer controls, without COM."""

from __future__ import annotations

from copy import deepcopy
import json
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
        self.heights = [0.010318318595770792] + [0.011322391897878521] * 17
        self.widths = [0.028, 0.028, 0.028, 0.060]
        self.gaps = [0.001] * 18
        self.locks = [False] * 18
        self.cells = [[f"cell-{row}-{col}" for col in range(4)] for row in range(18)]
        self.fonts = [[_font() for _col in range(4)] for _row in range(18)]
        self.font = _font()
        self.row_writes = []
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
        raise AssertionError("production must not compact or resize native rows")


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
    sheet_view.annotations = [table.annotation]
    sheet_view.next = top
    top.next = None
    manufacturing_view = View("manufacturing-sheet", Rect(0, 0, 0.4318, 0.2794))
    manufacturing_view.annotations = [manufacturing, caption]
    manufacturing_view.next = side
    manufacturing_view.GetTableAnnotations = lambda: []
    top.GetTableAnnotations = side.GetTableAnnotations = lambda: []
    side.next = None
    state = SimpleNamespace(active="PLAN AND HOLE TABLE", activations=[], rebuilds=[])
    sheet.GetName = lambda: state.active
    adapter.currentModel.GetSheetNames = lambda: (
        "PLAN AND HOLE TABLE",
        "MANUFACTURING",
    )
    adapter.currentModel.GetFirstView = lambda: (
        sheet_view if state.active == "PLAN AND HOLE TABLE" else manufacturing_view
    )

    def activate(name):
        state.activations.append(name)
        state.active = name
        return True

    def rebuild():
        state.rebuilds.append(state.active)
        return True

    adapter.currentModel.ActivateSheet = activate
    adapter.currentModel.EditRebuild3 = rebuild
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
        manufacturing_view=manufacturing_view,
        state=state,
        manufacturing=manufacturing,
        caption=caption,
        options=options,
    )


def test_two_sheet_packer_never_compacts_and_preserves_complete_resolved_table(setup):
    before = layout._table_state(setup.table)
    caption_before = setup.caption.position
    reports = layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert tuple(reports) == ("PLAN AND HOLE TABLE", "MANUFACTURING")
    assert setup.state.rebuilds[0] == "PLAN AND HOLE TABLE"
    assert setup.table.row_writes == []
    assert layout._table_state(setup.table) == before
    assert setup.top.ScaleRatio == (1.0, 2.0)
    assert setup.side.ScaleRatio == (1.0, 4.0)
    assert len(setup.table.annotation.moves) == 1
    assert setup.table.annotation.position == pytest.approx((0.0132, 0.2662, 0.0))
    plan, manufacturing = reports.values()
    assert plan.status is NativeLayoutStatus.APPLIED
    assert set(plan.after_bounds) == {"view:top"}
    assert set(manufacturing.after_bounds) == {"view:side", "note:manufacturing"}
    table_bounds = layout._box(before, setup.table.annotation.position)
    assert table_bounds in plan.fixed_bounds.values()
    assert table_bounds not in manufacturing.fixed_bounds.values()
    for report in reports.values():
        for box in report.after_bounds.values():
            assert box.xmin >= report.drawable.xmin
            assert box.ymin >= report.drawable.ymin
            assert box.xmax <= report.drawable.xmax
            assert box.ymax <= report.drawable.ymax
    assert setup.caption.position[:2] == pytest.approx(
        tuple(
            a + b
            for a, b in zip(
                caption_before[:2], manufacturing.translations["view:side"], strict=True
            )
        )
    )
    assert setup.state.active == "PLAN AND HOLE TABLE"


def test_checked_resolution_logs_exact_precision_change_before_freezing(
    setup, monkeypatch
):
    setup.table.cells[1][3] = "DIA 9 THRU"
    records = []
    monkeypatch.setattr(
        layout._telemetry,
        "info",
        lambda message, **attrs: records.append((message, attrs)),
    )

    def resolve():
        setup.table.cells[1][3] = "DIA 9.00 THRU"
        return True

    setup.adapter.currentModel.EditRebuild3 = resolve
    reports = layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert len(reports) == 2
    record = next(attrs for _message, attrs in records if "text_changes" in attrs)
    assert json.loads(record["text_changes"]) == [
        {"row": 1, "column": 3, "before": "DIA 9 THRU", "after": "DIA 9.00 THRU"}
    ]
    assert json.loads(record["before_state"])["cells"][7][2] == "DIA 9 THRU"
    assert json.loads(record["resolved_state"])["cells"][7][2] == "DIA 9.00 THRU"
    assert setup.table.cells[1][3] == "DIA 9.00 THRU"
    assert setup.table.row_writes == []


@pytest.mark.parametrize("result", [False, OSError("native rebuild failed")])
def test_resolution_rebuild_failure_stops_before_positioning(setup, result):
    def rebuild():
        if isinstance(result, BaseException):
            raise result
        return result

    setup.adapter.currentModel.EditRebuild3 = rebuild
    with pytest.raises((RuntimeError, OSError), match="rebuild.*failed") as caught:
        layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    if isinstance(result, BaseException):
        assert caught.value is result
    assert setup.table.annotation.moves == []
    assert setup.top.moves == setup.side.moves == []


@pytest.mark.parametrize("field", layout._FORMAT_FIELDS)
def test_resolution_cannot_change_any_last_cell_font_field(setup, field):
    def rebuild():
        fmt = setup.table.fonts[17][3]
        before = getattr(fmt, field)
        setattr(fmt, field, "Other font" if isinstance(before, str) else before + 0.25)
        return True

    setup.adapter.currentModel.EditRebuild3 = rebuild
    with pytest.raises(
        layout.TableReadbackError, match="rebuild changed table formatting"
    ):
        layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert setup.table.annotation.moves == []


@pytest.mark.parametrize(
    "change", ["table_font", "points_mode", "width", "gap", "lock", "anchor", "height"]
)
def test_resolution_cannot_change_other_table_geometry_or_metadata(setup, change):
    def rebuild():
        if change == "table_font":
            setup.table.font.CharHeight = 0.002
        if change == "points_mode":
            setup.table.fonts[17][3].IsHeightSpecifiedInPts = lambda: True
        if change == "width":
            setup.table.widths[3] += 0.001
        if change == "gap":
            setup.table.gaps[17] += 0.001
        if change == "lock":
            setup.table.locks[17] = True
        if change == "anchor":
            setup.table.annotation.position = (0.273, 0.256, 0.0)
        if change == "height":
            setup.table.heights[17] += 0.001
        return True

    setup.adapter.currentModel.EditRebuild3 = rebuild
    with pytest.raises(
        layout.TableReadbackError, match="rebuild changed table formatting"
    ):
        layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert setup.table.annotation.moves == []


@pytest.mark.parametrize(
    "inventory",
    [
        "tables",
        "annotations",
        "unknown_table",
        "unknown_annotation",
        "null_annotation",
        "manufacturing_table",
        "manufacturing_annotation",
        "wrong_top",
        "wrong_side",
        "extra_view",
    ],
)
def test_both_sheet_inventories_are_proven_before_any_table_or_view_movement(
    setup, inventory
):
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
    if inventory == "manufacturing_table":
        setup.manufacturing_view.GetTableAnnotations = lambda: [setup.table]
    if inventory == "manufacturing_annotation":
        setup.manufacturing_view.annotations.append(setup.table.annotation)
    if inventory == "wrong_top":
        setup.sheet_view.next = setup.side
    if inventory == "wrong_side":
        setup.manufacturing_view.next = setup.top
    if inventory == "extra_view":
        setup.top.next = setup.side
    with pytest.raises(
        RuntimeError,
        match="missing from native|unexpected|contains null|ownership differs",
    ):
        layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert setup.state.rebuilds == []
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


@pytest.mark.parametrize("failure", ["names", "activate", "readback"])
def test_sheet_activation_contract_fails_before_native_table_changes(setup, failure):
    if failure == "names":
        setup.adapter.currentModel.GetSheetNames = lambda: (
            "MANUFACTURING",
            "PLAN AND HOLE TABLE",
        )
    if failure == "activate":
        setup.adapter.currentModel.ActivateSheet = lambda _name: False
    if failure == "readback":
        setup.adapter.currentModel.GetCurrentSheet().GetName = lambda: "wrong sheet"
    with pytest.raises(
        RuntimeError, match="sheet names/order|activate sheet|sheet readback"
    ):
        layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert setup.state.rebuilds == []
    assert setup.table.annotation.moves == []
    assert setup.top.moves == setup.side.moves == []


@pytest.mark.parametrize(
    "movement,message",
    [
        ("reject", "rejected measured upper-left"),
        ("ignore", "changed during table placement"),
    ],
)
def test_table_anchor_failure_is_not_reported_as_measured_fit(setup, movement, message):
    setup.table.annotation.movement = movement
    with pytest.raises(RuntimeError, match=message):
        layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert setup.top.moves == setup.side.moves == []


def test_unchanged_table_too_tall_reports_no_fit_without_compaction(setup):
    setup.table.heights = [0.015] * 18
    with pytest.raises(RuntimeError, match="unchanged table no_fit"):
        layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert setup.table.heights == [0.015] * 18
    assert setup.table.row_writes == []
    assert setup.table.annotation.moves == []
    assert setup.top.moves == setup.side.moves == []


@pytest.mark.parametrize("view", ["top", "side"])
def test_either_sheet_no_fit_preserves_deliberate_view_scales(setup, view):
    getattr(setup, view).rectangle = Rect(0, 0, 0.45, 0.15)
    with pytest.raises(RuntimeError, match="native print no_fit"):
        layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert getattr(setup, view).moves == []
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
    reports = layout.repair_harmonic_base_layout(setup.adapter, **setup.options)
    assert len(reports) == 2


@pytest.mark.parametrize(
    "change", ["cell", "precision", "font", "height", "replace", "unknown"]
)
def test_post_resolution_table_drift_cannot_pass_final_packing(setup, change):
    calls = []
    setup.table.cells[17][3] = "DIA 9 THRU"

    def rebuild():
        calls.append(setup.state.active)
        if len(calls) == 1:
            return True
        if change == "cell":
            setup.table.cells[17][3] = "WRONG FINAL SIZE"
        if change == "precision":
            setup.table.cells[17][3] = "DIA 9.00 THRU"
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


def test_failed_position_read_with_unchanged_state_retains_structured_evidence(setup):
    expected = layout._table_state(setup.table)
    position = setup.table.annotation.position
    error = OSError("native GetPosition failed")

    def reject():
        raise error

    setup.table.annotation.GetPosition = reject
    with pytest.raises(
        layout.TableReadbackError, match="changed during readback"
    ) as caught:
        layout._preserve_table(
            setup.table, setup.table.annotation, expected, position, phase="readback"
        )
    assert caught.value.evidence["position_read_error"] == repr(error)
    assert caught.value.evidence["changed_fields"] == ["position"]
    assert (
        caught.value.evidence["expected_state"] == caught.value.evidence["actual_state"]
    )
    assert caught.value.evidence["actual_heights"] == expected.heights


def test_failed_preservation_telemetry_does_not_replace_exact_cell_evidence(
    setup, monkeypatch
):
    expected = layout._table_state(setup.table)
    setup.table.cells[17][3] = "WRONG FINAL SIZE"
    error = OSError("diagnostic writer failed")

    def reject(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(layout._telemetry, "error", reject)
    with pytest.raises(
        layout.TableReadbackError, match="changed during readback"
    ) as caught:
        layout._preserve_table(
            setup.table,
            setup.table.annotation,
            expected,
            setup.table.annotation.position,
            phase="readback",
        )
    assert caught.value.evidence["changed_fields"] == ["cells"]
    assert any(repr(error) in note for note in caught.value.__notes__)
