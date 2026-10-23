"""Replay R44 native ink; this COM-free suite does not qualify a new export."""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import _supplier_screw_dimensions as screws
from _drawing_annotation_extent import CLEAR_GAP_M
from _layout_audit import (
    annotation_geometry,
    calibrate_sheet_advance,
    find_lines_through_own_text,
    find_text_clearance,
)
from _supplier_screw_layout import supplier_screw_lane_plan, supplier_top_text_geometry

_RECORDED = json.loads(
    (Path(__file__).parent / "testdata" / "supplier_top_r44.json").read_text(encoding="utf-8")
)["families"]


class _NativeDisplayReplay:
    """Paint-record replay of the documented coupled/offset placement modes.

    The pre-offset anchor transition follows the measured thumb-screw 012dd
    behavior: enabling offset mode puts the physical line on the old annotation
    anchor, not its font-dependent baseline. This is not a SolidWorks emulator.
    """

    def __init__(self, record, *, leak_station=False):
        self.record = copy.deepcopy(record)
        self.horizontal = record["name"] != "SupplierHeadHeight"
        if record["name"] in {"SupplierLength", "SupplierThreadLength"}:
            self.horizontal = False
        self._offset = False
        self.leak_station = leak_station
        self.source_state = ("model-owned", 0.006, "unchanged native tolerance")

    def GetAnnotation(self):
        return self

    def GetPosition(self):
        return tuple(self.record["pos"])

    def _move_station(self, delta):
        normal = 1 if self.horizontal else 0
        axis = 1 - normal
        arrows = self.record["display"]["arrows"]
        station = sum(row[normal] for row in arrows) / 2.0
        for raw in self.record["display"]["lines"]:
            points = [[raw[4], raw[5]], [raw[7], raw[8]]]
            if abs(points[0][normal] - points[1][normal]) < 1e-7:
                if abs(points[0][normal] - station) <= 1e-5:
                    for point in points:
                        point[normal] += delta
            elif abs(points[0][axis] - points[1][axis]) < 1e-7:
                end = min(range(2), key=lambda index: abs(points[index][normal] - station))
                points[end][normal] += delta
            raw[4], raw[5] = points[0]
            raw[7], raw[8] = points[1]
        for row in arrows:
            row[normal] += delta

    @property
    def OffsetText(self):
        return self._offset

    @OffsetText.setter
    def OffsetText(self, enabled):
        if enabled and not self._offset:
            normal = 1 if self.horizontal else 0
            station = sum(row[normal] for row in self.record["display"]["arrows"]) / 2.0
            self._move_station(self.record["pos"][normal] - station)
        self._offset = enabled

    def SetPosition2(self, x, y, z):
        dx, dy = x - self.record["pos"][0], y - self.record["pos"][1]
        if not self._offset or self.leak_station:
            self._move_station(dy if self.horizontal else dx)
        for text in self.record["display"]["texts"]:
            text["pos"][0] += dx
            text["pos"][1] += dy
        self.record["pos"] = [x, y, z]
        return True


@pytest.fixture
def native_replay(monkeypatch):
    monkeypatch.setattr(screws, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(
        screws, "_Reader", lambda _adapter: SimpleNamespace(take_errors=lambda: [])
    )
    monkeypatch.setattr(
        screws, "_dump_annotation", lambda _reader, display: copy.deepcopy(display.record)
    )
    phases = []
    monkeypatch.setattr(
        screws, "rebuild_drawing", lambda _adapter, *, label: phases.append(label)
    )
    return phases


def _displays(family, **kwargs):
    return {
        record["name"]: _NativeDisplayReplay(record, **kwargs)
        for view in _RECORDED[family].values() for record in view["annotations"]
    }


def _sheet(displays):
    records = [display.record for display in displays.values()]
    advance = calibrate_sheet_advance(records)
    return SimpleNamespace(
        name="R44 native-record replay",
        annotations=[
            annotation_geometry(record, owner="view", advance=advance)
            for record in records
        ],
    )


@pytest.mark.parametrize("family", tuple(_RECORDED))
def test_r44_actual_short_chords_get_clear_text_without_moving_stations(native_replay, family):
    displays = _displays(family)
    source_state = {name: display.source_state for name, display in displays.items()}
    before = {
        name: supplier_top_text_geometry(displays[name].record, horizontal=horizontal)
        for name, (horizontal, _side) in screws._SUPPLIER_TOP_SHELVES.items()
    }
    struck = {finding.a for finding in find_lines_through_own_text(_sheet(displays))}
    assert any("SupplierHeadHeight" in label for label in struck)
    assert any("SupplierThreadDiameter" in label for label in struck)
    assert any("SupplierDriveWidth" in label for label in struck)
    screws._shelf_supplier_top_text(None, displays)
    after = screws._assert_supplier_top_shelves(None, displays)
    assert set(after) == set(before)
    for name in before:
        screws._assert_supplier_top_stations(name, before[name], after[name])
        _horizontal, side = screws._SUPPLIER_TOP_SHELVES[name]
        text = after[name]["text"]
        gap = after[name]["left"] - text.xmax if side == "left" else text.xmin - after[name]["right"]
        assert gap >= CLEAR_GAP_M
        assert not find_lines_through_own_text(_sheet({name: displays[name]}))
    assert {name: display.source_state for name, display in displays.items()} == source_state
    assert len(native_replay) == 4


@pytest.mark.parametrize("family", tuple(_RECORDED))
def test_offset_text_leaking_into_native_stations_is_refused(native_replay, family):
    with pytest.raises(RuntimeError):
        screws._shelf_supplier_top_text(None, _displays(family, leak_station=True))


@pytest.mark.parametrize("field", ("tips", "witnesses", "physical_lines"))
def test_native_station_drift_negative_control(field):
    record = _displays("block")["SupplierDriveWidth"].record
    before = supplier_top_text_geometry(record, horizontal=True)
    after = copy.deepcopy(before)
    rows = list(after[field])
    rows[0] = (rows[0][0] + 0.0001, *rows[0][1:])
    after[field] = tuple(rows)
    with pytest.raises(RuntimeError):
        screws._assert_supplier_top_stations("SupplierDriveWidth", before, after)


def test_unregistered_offset_connector_is_not_a_new_physical_station():
    record = _displays("block")["SupplierDriveWidth"].record
    before = supplier_top_text_geometry(record, horizontal=True)
    y = before["tips"][0][1]
    record["display"]["lines"].append([
        0.0, 0.0, 0.0, 0.0, 0.150, y, 0.0, 0.180, y, 0.0
    ])
    after = supplier_top_text_geometry(record, horizontal=True)
    screws._assert_supplier_top_stations("SupplierDriveWidth", before, after)
    assert (after["left"], after["right"]) == (before["left"], before["right"])


@pytest.mark.parametrize("defect", ("arrows", "witnesses", "text_width", "reader", "placement"))
def test_unmeasured_or_failed_native_placement_does_not_succeed(native_replay, monkeypatch, defect):
    displays = _displays("block")
    display = displays["SupplierDriveWidth"]
    if defect == "arrows":
        display.record["display"]["arrows"] = []
    elif defect == "witnesses":
        display.record["display"]["lines"] = []
    elif defect == "text_width":
        display.record["display"]["texts"][0]["w"] = 0.0
    elif defect == "reader":
        monkeypatch.setattr(
            screws, "_Reader", lambda _adapter: SimpleNamespace(take_errors=lambda: ["native error"])
        )
    else:
        display.SetPosition2 = lambda *_args: False
    with pytest.raises(RuntimeError):
        screws._shelf_supplier_top_text(None, displays)


def test_settled_shelf_guard_refuses_return_of_r44_text_collision(native_replay):
    displays = _displays("rail")
    screws._shelf_supplier_top_text(None, displays)
    display = displays["SupplierDriveWidth"]
    raw = _RECORDED["rail"]["*Top"]["annotations"]
    original = next(row for row in raw if row["name"] == "SupplierDriveWidth")
    display.record["display"]["texts"] = copy.deepcopy(original["display"]["texts"])
    with pytest.raises(RuntimeError):
        screws._assert_supplier_top_shelves(None, displays)


def test_block_thread_length_uses_left_lane_and_recorded_texts_no_longer_overlap(native_replay):
    import ch_rocker_arm_tl_vn_oblique_block_screw_spec as supplier

    displays = _displays("block")
    lengths = {name: displays[name] for name in ("SupplierLength", "SupplierThreadLength")}
    assert find_text_clearance(_sheet(lengths))
    plan = supplier_screw_lane_plan(
        supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=supplier.SUPPLIER_REFERENCE_PLANES,
        sides=supplier.SUPPLIER_REFERENCE_SIDES,
    )
    outline = _RECORDED["block"]["*Front"]["outline"]
    for name, display in lengths.items():
        side, offset = plan[name]
        x = outline[0] - offset if side == "left" else outline[2] + offset
        _, y, z = display.GetPosition()
        assert display.SetPosition2(x, y, z)
    screws._shelf_supplier_top_text(None, displays)
    assert not find_text_clearance(_sheet(lengths))
    assert plan["SupplierLength"][0] == "right"
    assert plan["SupplierThreadLength"][0] == "left"


@pytest.mark.parametrize("layout", ("standard", "tall_top"))
def test_unaffected_layouts_do_not_read_or_change_offset_text(monkeypatch, layout):
    from test_purchased_fastener_drawing import _supplier_native

    case = _supplier_native(monkeypatch, value=0.006)
    case.native.FullName = "Length@SupplierReference@stock.SLDPRT"
    case.view.GetOrientationName = lambda: "*Front"
    case.view.GetOutline = lambda: (0.05, 0.10, 0.10, 0.15)
    case.view.UpdateViewDisplayGeometry = lambda: None
    case.view.GetAnnotations = lambda: [case.annotation]
    monkeypatch.setattr(screws, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(screws, "_binding", lambda *_args: ("Front", "stock.SLDPRT", "Default"))
    monkeypatch.setattr(screws, "_assert_source", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(screws, "iter_views", lambda _adapter: [case.view])
    monkeypatch.setattr(screws, "view_name", lambda *_args: "Front")
    monkeypatch.setattr(screws, "dimension_name", lambda *_args: "Length")
    monkeypatch.setattr(screws, "model_points_in_view", lambda *_args, **_kwargs: [(0.075, 0.125)])
    monkeypatch.setattr(screws, "curate_view_dimensions", lambda *_args, **_kwargs: [case.annotation])

    def unexpected_shelf(*_args, **_kwargs):
        raise AssertionError("unaffected layout entered supplier_top text placement")

    monkeypatch.setattr(screws, "_shelf_supplier_top_text", unexpected_shelf)
    monkeypatch.setattr(screws, "_assert_supplier_top_shelves", unexpected_shelf)
    checks = []
    result = screws.annotate_supplier_screw(
        None, {"*Front": case.view}, dimensions=(("Length", 6.0, "vertical"),),
        formats={"Length": (3, "length", None, None)}, settled_checks=checks, layout=layout,
    )
    assert result == {"Length": case.display}
    checks[0]()
    assert case.native.SystemValue == 0.006
    assert case.text[2] == " in)"


def _settled_block_replay(monkeypatch):
    """Keep real placement/final callbacks; isolate unrelated source COM readers."""
    import draw_ch_rocker_arm_tl_vn_oblique_block_screw as block

    displays = _displays("block")
    views = {}
    supplier = block.supplier
    for plane, feature in screws.FEATURE_BY_PLANE.items():
        rows = [
            displays[name] for name, _value, _orientation in supplier.SUPPLIER_REFERENCE_DIMENSIONS
            if supplier.SUPPLIER_REFERENCE_PLANES.get(name, "Front") == plane
        ]
        if not rows:
            continue
        for display in rows:
            name = display.record["name"]
            native = SimpleNamespace(
                FullName=f"{name}@{feature}@stock.SLDPRT",
                Tolerance=SimpleNamespace(
                    Type=5 if name in supplier.SUPPLIER_REFERENCE_MINIMUMS else 0,
                    GetMinValue=lambda: 0.0, GetMaxValue=lambda: 0.0,
                ),
            )
            display.GetDimension2 = lambda _index, native=native: native
            display.GetType = lambda: 4
            display.GetSpecificAnnotation = lambda display=display: display
            display.GetPrimaryTolPrecision2 = lambda: 3
        outline = _RECORDED["block"][f"*{plane}"]["outline"]
        views[f"*{plane}"] = SimpleNamespace(
            name=plane, rows=rows,
            GetOrientationName=lambda plane=plane: f"*{plane}",
            GetOutline=lambda outline=outline: outline,
            UpdateViewDisplayGeometry=lambda: None,
            GetAnnotations=lambda rows=rows: rows,
        )
    monkeypatch.setattr(block, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(screws, "_binding", lambda _adapter, view: (view.name, "stock.SLDPRT", "Default"))
    monkeypatch.setattr(screws, "_assert_source", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(screws, "supplier_reference_dimension", lambda _adapter, display, **_kwargs: display)
    monkeypatch.setattr(screws, "assert_supplier_reference_dimension", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(screws, "iter_views", lambda _adapter: list(views.values()))
    monkeypatch.setattr(screws, "view_name", lambda _adapter, view: view.name)
    monkeypatch.setattr(screws, "dimension_name", lambda _adapter, display: display.record["name"])
    monkeypatch.setattr(
        screws, "model_points_in_view",
        lambda _adapter, view, _points, **_kwargs: [display.GetPosition()[:2] for display in view.rows],
    )
    monkeypatch.setattr(
        screws, "curate_view_dimensions", lambda _adapter, view, **_kwargs: view.rows
    )
    return block, views, displays


@pytest.mark.parametrize("callback", ("shared", "block"))
@pytest.mark.parametrize("defect", (None, "station", "witness", "physical_line"))
def test_final_callbacks_retain_native_stations_even_when_text_stays_clear(
    native_replay, monkeypatch, callback, defect,
):
    block, views, displays = _settled_block_replay(monkeypatch)
    source_state = {name: display.source_state for name, display in displays.items()}

    def exercise(final_check):
        final_check()  # Healthy final readback must succeed before the mutation.
        if defect is None:
            return
        display = displays["SupplierDriveWidth"]
        geometry = supplier_top_text_geometry(display.record, horizontal=True)
        left_tip = min(geometry["tips"])
        if defect == "station":
            display._move_station(0.0001)
        else:
            for raw in display.record["display"]["lines"]:
                if defect == "witness" and raw[4] == raw[7] == left_tip[0]:
                    index = 5 if abs(raw[5] - left_tip[1]) > abs(raw[8] - left_tip[1]) else 8
                    raw[index] += 0.0001
                    break
                if (
                    defect == "physical_line" and raw[5] == raw[8] == left_tip[1]
                    and min(raw[4], raw[7]) < left_tip[0]
                ):
                    raw[4 if raw[4] < raw[7] else 7] -= 0.0001
                    break
            else:
                raise AssertionError("recorded native mutation target is absent")
        # Fresh clearance alone still accepts this final-rebuild drift.
        screws._assert_supplier_top_shelves(None, displays)
        with pytest.raises(RuntimeError):
            final_check()
        assert {name: display.source_state for name, display in displays.items()} == source_state

    if callback == "shared":
        checks = []
        screws.annotate_supplier_screw(
            None, views,
            dimensions=block.supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            formats=block.supplier.SUPPLIER_REFERENCE_FORMATS,
            starts=block.supplier.SUPPLIER_REFERENCE_STARTS,
            planes=block.supplier.SUPPLIER_REFERENCE_PLANES,
            sides=block.supplier.SUPPLIER_REFERENCE_SIDES,
            settled_checks=checks, layout="supplier_top",
        )
        exercise(checks[0])
    else:
        async def build_reference_sheet(adapter, _spec, **kwargs):
            kwargs["supplier_dimensions"](adapter, views)
            exercise(kwargs["settled_checks"][0])
            return {}

        monkeypatch.setattr(block, "build_purchased_fastener_drawing", build_reference_sheet)
        assert asyncio.run(block.build(None)) == {}
