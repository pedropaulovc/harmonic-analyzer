"""Native-I/O regressions for the observed R41 pin/washer failures; no COM seat."""

from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def _washer_failure_case(monkeypatch):
    from test_purchased_fastener_drawing import _washer_import_native

    case = _washer_import_native(monkeypatch)
    label = case.helper.THICKNESS
    display = case.imports[label].display
    feature = case.model.FeatureByName(case.source_helper.THICKNESS_FEATURE)
    feature.Name = case.source_helper.THICKNESS_FEATURE
    feature.GetTypeName2 = lambda: "ProfileFeature"
    case.model.GetPathName = lambda: "C:/native-washer.SLDPRT"
    return case, label, display


def _assert_washer_source_attachment(case, label, display):
    case.source_helper.assert_supplier_washer_source_attachment(
        case.adapter, case.model, display, view=case.views["*Front"], label=label,
        axis="y", bore_mm=6.35, outer_mm=12.7, thickness_mm=1.5875,
    )


@pytest.mark.parametrize("label", (
    "supplier outer diameter", "supplier bore diameter", "supplier thickness",
))
@pytest.mark.parametrize("axis", ("y", "z"))
@pytest.mark.parametrize("owner_namespace", ("source", "view"))
def test_washer_canonical_dimension_and_view_entities_do_not_depend_on_feature_owner(
    monkeypatch, label, axis, owner_namespace,
):
    from test_purchased_fastener_drawing import _washer_import_native

    case = _washer_import_native(monkeypatch, axis=axis)
    source = case.sources[label]
    imported = case.imports[label]
    side = "*Front" if axis == "y" else "*Top"
    face = "*Top" if axis == "y" else "*Front"
    view = case.views[side if label == case.helper.THICKNESS else face]
    feature_name, dimension_name = case.source_helper.SOURCE_DIMENSIONS[label]
    source_owner = source.native.GetFeatureOwner()
    if owner_namespace == "source":
        imported.native.GetFeatureOwner = lambda: source_owner
    observed_owner = imported.native.GetFeatureOwner()
    assert case.adapter.swApp.IsSame(observed_owner, source_owner) == (owner_namespace == "source")
    assert case.adapter.swApp.IsSame(
        observed_owner, view.GetCorresponding(source_owner)) == (owner_namespace == "view")
    assert case.adapter.swApp.IsSame(imported.native, source.native) == 1
    assert case.adapter.swApp.IsSame(
        imported.native, case.model.Parameter(f"{dimension_name}@{feature_name}")) == 1
    before = (source.native.SystemValue, dict(vars(source.state)), dict(source.text),
              source.native.Tolerance.Type, source.annotation.entities)
    for display, owner_view in ((source.display, None), (imported.display, view)):
        case.source_helper.assert_supplier_washer_source_attachment(
            case.adapter, case.model, display, view=owner_view, label=label,
            axis=axis, bore_mm=6.35, outer_mm=12.7, thickness_mm=1.5875,
        )
    assert (source.native.SystemValue, dict(vars(source.state)), dict(source.text),
            source.native.Tolerance.Type, source.annotation.entities) == before


@pytest.mark.parametrize("defect", ("native_name", "source_name", "native_type"))
def test_washer_canonical_dimension_still_requires_correct_names_and_type(monkeypatch, defect):
    case, label, display = _washer_failure_case(monkeypatch)
    source = case.sources[label]
    imported = case.imports[label]
    if defect == "native_name":
        imported.native.FullName = "Other@SupplierWasherThicknessReference@stock"
    elif defect == "source_name":
        source.native.FullName = "Other@SupplierWasherThicknessReference@stock"
    else:
        imported.display.Type2 = 6
    with pytest.raises(RuntimeError):
        _assert_washer_source_attachment(case, label, display)


@pytest.mark.parametrize("label", (
    "supplier outer diameter", "supplier bore diameter", "supplier thickness",
))
def test_washer_part_uses_canonical_dimension_despite_different_feature_owner(monkeypatch, label):
    from test_purchased_fastener_drawing import _washer_import_native

    case = _washer_import_native(monkeypatch)
    source = case.sources[label]
    feature_name, dimension_name = case.source_helper.SOURCE_DIMENSIONS[label]
    feature = case.model.FeatureByName(feature_name)
    feature.Name = feature_name
    feature.GetTypeName2 = lambda: "ProfileFeature"
    other_owner = SimpleNamespace(Name=feature_name, GetTypeName2=lambda: "ProfileFeature")
    source.native.GetFeatureOwner = lambda: other_owner
    assert case.adapter.swApp.IsSame(other_owner, feature) == 0
    assert case.adapter.swApp.IsSame(
        source.native, case.model.Parameter(f"{dimension_name}@{feature_name}")) == 1
    before = (source.native.SystemValue, dict(vars(source.state)), dict(source.text),
              source.native.Tolerance.Type, source.annotation.entities)
    case.source_helper.assert_supplier_washer_source_attachment(
        case.adapter, case.model, source.display, view=None, label=label,
        axis="y", bore_mm=6.35, outer_mm=12.7, thickness_mm=1.5875,
    )
    assert (source.native.SystemValue, dict(vars(source.state)), dict(source.text),
            source.native.Tolerance.Type, source.annotation.entities) == before


@pytest.mark.parametrize("defect", (
    "wrong_parameter", "missing_parameter", "wrong_enumerated", "missing_enumerated",
    "wrong_native", "missing_native",
))
@pytest.mark.parametrize("context", ("part", "drawing"))
def test_washer_rejects_other_canonical_dimensions_despite_matching_metadata(monkeypatch, defect, context):
    case, label, _display = _washer_failure_case(monkeypatch)
    source = case.sources[label]
    original = source.native
    display = source.display if context == "part" else case.imports[label].display
    other = SimpleNamespace(**vars(original))
    assert other.FullName == original.FullName and other.SystemValue == original.SystemValue
    before = (original.SystemValue, dict(vars(source.state)), dict(source.text),
              original.Tolerance.Type, source.annotation.entities)
    if defect == "wrong_parameter":
        case.model.Parameter = lambda _name: other
    elif defect == "missing_parameter":
        case.model.Parameter = lambda _name: None
    elif defect == "wrong_enumerated":
        source.native = other
    elif defect == "missing_enumerated":
        source.native = None
    elif defect == "wrong_native":
        display.GetDimension2 = lambda _index: other
    else:
        display.GetDimension2 = lambda _index: None
    with pytest.raises(RuntimeError):
        case.source_helper.assert_supplier_washer_source_attachment(
            case.adapter, case.model, display, view=None if context == "part" else case.views["*Front"], label=label,
            axis="y", bore_mm=6.35, outer_mm=12.7, thickness_mm=1.5875,
        )
    assert (original.SystemValue, dict(vars(source.state)), dict(source.text),
            original.Tolerance.Type, source.annotation.entities) == before


@pytest.mark.parametrize("context", ("part", "drawing"))
def test_washer_parameter_reader_failure_is_not_retried_by_diagnostics(monkeypatch, context):
    case, label, _display = _washer_failure_case(monkeypatch)
    original = RuntimeError("canonical source-part parameter lookup failed")
    observations = []
    responses = iter((original, case.sources[label].native))

    def failed_parameter(_name):
        response = next(responses)
        if response is original:
            raise original
        return response

    case.model.Parameter = failed_parameter
    monkeypatch.setattr(case.source_helper._telemetry, "info", lambda _message, **fields: observations.append(fields))
    with pytest.raises(RuntimeError) as caught:
        case.source_helper.assert_supplier_washer_source_attachment(
            case.adapter, case.model,
            case.sources[label].display if context == "part" else case.imports[label].display,
            view=None if context == "part" else case.views["*Front"], label=label,
            axis="y", bore_mm=6.35, outer_mm=12.7, thickness_mm=1.5875,
        )
    assert caught.value is original
    fields, = observations
    assert fields["model_parameter_handle_state"] == "UNAVAILABLE"
    assert fields["model_parameter_handle_reason"] == "source-part parameter lookup did not complete"


def test_washer_owner_failure_reports_remaining_context_despite_an_independent_reader_error(monkeypatch):
    case, label, display = _washer_failure_case(monkeypatch)
    observations = []

    def interrupted_type():
        raise RuntimeError("optional owner type reader failed")

    foreign_owner = SimpleNamespace(Name="Foreign", GetTypeName2=interrupted_type)
    case.imports[label].native.GetFeatureOwner = lambda: foreign_owner
    case.model.Parameter = lambda _name: SimpleNamespace(**vars(case.sources[label].native))
    monkeypatch.setattr(case.source_helper._telemetry, "info", lambda _message, **fields: observations.append(fields))
    with pytest.raises(RuntimeError, match="named model witness"):
        _assert_washer_source_attachment(case, label, display)
    fields, = observations
    assert fields["owner_same_source"] == 0
    assert fields["owner_type_state"] == "UNAVAILABLE"
    assert fields["owner_type_error_type"] == "RuntimeError"
    assert fields["source_feature_type"] == "ProfileFeature"
    assert fields["source_path"] == "C:/native-washer.SLDPRT"
    assert fields["view_source_same"] == 1
    assert fields["native_type"] == fields["source_type"] == 2
    assert fields["mapped_candidate_present"] == (True, True)
    assert fields["attachment_same_source_row_major"] == (0, 0, 0, 0)
    assert fields["attachment_same_view_row_major"] == (1, 0, 0, 1)


def test_washer_original_native_interrupt_aborts_without_failure_only_observers(monkeypatch):
    case, label, display = _washer_failure_case(monkeypatch)
    original = SystemExit("original native parameter reader")
    observations = []

    def native_failure(_name):
        raise original

    case.model.Parameter = native_failure
    monkeypatch.setattr(
        case.source_helper._telemetry, "info",
        lambda *_args, **_kwargs: observations.append("observed"),
    )
    with pytest.raises(SystemExit) as caught:
        _assert_washer_source_attachment(case, label, display)
    assert caught.value is original
    assert observations == []


def test_washer_failure_observer_interrupt_aborts_immediately(monkeypatch):
    case, label, display = _washer_failure_case(monkeypatch)
    original = KeyboardInterrupt("interrupt during optional owner type read")

    def interrupted_type():
        raise original

    foreign_owner = SimpleNamespace(Name="Foreign", GetTypeName2=interrupted_type)
    case.imports[label].native.GetFeatureOwner = lambda: foreign_owner
    case.model.Parameter = lambda _name: SimpleNamespace(**vars(case.sources[label].native))
    with pytest.raises(KeyboardInterrupt) as caught:
        _assert_washer_source_attachment(case, label, display)
    assert caught.value is original


def test_washer_ordinary_observer_error_does_not_replace_original_native_failure(monkeypatch):
    case, label, display = _washer_failure_case(monkeypatch)
    original = RuntimeError("original native parameter reader")

    def native_failure(_name):
        raise original

    def log_failure(*_args, **_kwargs):
        raise ValueError("secondary observer failure")

    case.model.Parameter = native_failure
    monkeypatch.setattr(case.source_helper._telemetry, "info", log_failure)
    with pytest.raises(RuntimeError) as caught:
        _assert_washer_source_attachment(case, label, display)
    assert caught.value is original


def test_washer_healthy_canonical_check_does_not_read_feature_owners_or_diagnostics(monkeypatch):
    case, label, display = _washer_failure_case(monkeypatch)

    def unexpected_observation(*_args, **_kwargs):
        raise AssertionError("healthy ownership path called failure-only diagnostics")

    monkeypatch.setattr(case.source_helper._telemetry, "info", unexpected_observation)
    case.model.GetPathName = unexpected_observation
    case.sources[label].native.GetFeatureOwner = unexpected_observation
    case.imports[label].native.GetFeatureOwner = unexpected_observation
    # Canonical identity and physical attachments are independent of optional
    # feature-owner observations and the later drawing presentation operation.
    _assert_washer_source_attachment(case, label, display)


def _r48_washer_layout(monkeypatch, *, axis="z", witnessed="thickness"):
    from test_purchased_fastener_drawing import _washer_import_native
    import _supplier_washer_drawing as washer

    case = _washer_import_native(monkeypatch, axis=axis, values={
        washer.OUTER_DIAMETER: 11.1252, washer.BORE_DIAMETER: 5.08, washer.THICKNESS: .91,
    })
    if witnessed == "thickness":
        case.kwargs["model_references"] = frozenset({washer.THICKNESS})
    qualifier = "FOR No. 10 SCREW SIZE"
    case.sources[washer.BORE_DIAMETER].text[4] = qualifier
    case.kwargs["bore_callout"] = qualifier
    return case


def _washer_source_state(case):
    return {
        label: (item.native.SystemValue, item.native.Tolerance.Type,
                dict(vars(item.state)), dict(item.text), tuple(item.annotation.entities))
        for label, item in case.sources.items()
    }


@pytest.mark.parametrize("axis", ("y", "z"))
@pytest.mark.parametrize("witnessed", ("thickness", "all"))
def test_washer_complete_consumer_replay_clears_thickness_and_diameters_without_moving_witnesses(
    monkeypatch, axis, witnessed,
):
    import copy
    from _layout_audit import display_box
    from _supplier_screw_layout import supplier_top_text_geometry

    case = _r48_washer_layout(monkeypatch, axis=axis, witnessed=witnessed)
    thick = case.helper.THICKNESS
    diameters = (case.helper.OUTER_DIAMETER, case.helper.BORE_DIAMETER)
    before = _washer_source_state(case)
    before_records = copy.deepcopy({label: paint.record for label, paint in case.paint.items()})
    before_stations = supplier_top_text_geometry(before_records[thick], horizontal=False)
    face = case.views["*Top" if axis == "y" else "*Front"]
    assert before_stations["text"].xmin < before_stations["right"]
    assert all(display_box({"texts": before_records[label]["display"]["texts"]}).xmin
               < face.GetOutline()[2] for label in diameters)
    # Offset mode changes the full native block only on rebuild. Measuring the
    # pre-mode box would leave 6 mm of this real-width stack in the witness lane.
    case.paint[thick].offset_shift = -.006
    diameter_y = {label: case.paint[label].record["pos"][1] for label in diameters}
    settled = case.helper.supplier_washer_dimensions(case.adapter, case.views, **case.kwargs)
    settled()
    after = supplier_top_text_geometry(case.paint[thick].record, horizontal=False)
    for field in ("tips", "witnesses", "physical_lines"):
        assert after[field] == before_stations[field]
    assert after["text"].xmin - after["right"] >= .002
    for label in diameters:
        assert display_box({"texts": case.paint[label].record["display"]["texts"]}).xmin - face.GetOutline()[2] >= .002
        assert case.paint[label].record["pos"][1] == diameter_y[label]
        assert case.imports[label].display.OffsetText is False
    assert _washer_source_state(case) == before
    # A subsequent native layout regression must be caught at the real final
    # consumer guard, even when every value, band and source identity is sound.
    case.paint[case.helper.BORE_DIAMETER].record = before_records[case.helper.BORE_DIAMETER]
    with pytest.raises(RuntimeError):
        settled()


@pytest.mark.parametrize("label", ("thickness", "bore"))
def test_washer_final_guard_refuses_r48_old_crossing_even_with_offset_flag_true(monkeypatch, label):
    import copy

    case = _r48_washer_layout(monkeypatch)
    key = case.helper.THICKNESS if label == "thickness" else case.helper.BORE_DIAMETER
    old = copy.deepcopy(case.paint[key].record)
    settled = case.helper.supplier_washer_dimensions(case.adapter, case.views, **case.kwargs)
    settled()
    case.paint[key].record = old
    assert case.imports[case.helper.THICKNESS].display.OffsetText is True
    with pytest.raises(RuntimeError):
        settled()


@pytest.mark.parametrize("defect", ("reject", "clamp", "refuse_mode"))
def test_washer_refuses_unrealized_native_thickness_shelf_without_altering_source(monkeypatch, defect):
    case = _r48_washer_layout(monkeypatch)
    before = _washer_source_state(case)
    setattr(case.paint[case.helper.THICKNESS], defect, True)
    with pytest.raises(RuntimeError):
        case.helper.supplier_washer_dimensions(case.adapter, case.views, **case.kwargs)
    assert _washer_source_state(case) == before


@pytest.mark.parametrize("drift", ("witness", "outer_y", "bore_y"))
def test_washer_final_guard_refuses_physical_station_drift_with_clear_text(monkeypatch, drift):
    case = _r48_washer_layout(monkeypatch)
    settled = case.helper.supplier_washer_dimensions(case.adapter, case.views, **case.kwargs)
    settled()
    if drift == "witness":
        case.paint[case.helper.THICKNESS].record["display"]["lines"][0][4] += .003
    else:
        label = case.helper.OUTER_DIAMETER if drift == "outer_y" else case.helper.BORE_DIAMETER
        case.paint[label].record["pos"][1] += .003
    with pytest.raises(RuntimeError):
        settled()


@pytest.mark.parametrize("defect", ("position", "width"))
def test_washer_refuses_unavailable_measured_paint_instead_of_estimated_text(monkeypatch, defect):
    case = _r48_washer_layout(monkeypatch)
    record = case.paint[case.helper.THICKNESS].record
    if defect == "position":
        record["pos"][0] = float("nan")
    else:
        record["display"]["texts"][0]["w"] = 0.0
    with pytest.raises(RuntimeError):
        case.helper.supplier_washer_dimensions(case.adapter, case.views, **case.kwargs)


def _retained_washer_layout(monkeypatch, scope):
    from test_purchased_fastener_drawing import _washer_import_native
    import _supplier_washer_drawing as washer

    captures = json.loads(Path(__file__).with_name("test_supplier_washer_native_paint.json").read_text())
    captured = captures["cases"][scope]
    part = importlib.import_module(f"{captured['stem']}_spec")
    values = {
        washer.OUTER_DIAMETER: part.OD,
        washer.BORE_DIAMETER: part.ID,
        washer.THICKNESS: getattr(part, captured["thickness_attribute"]),
    }
    case = _washer_import_native(monkeypatch, axis=captured["axis"], values=values)
    units, precision = part.SUPPLIER_UNITS, part.DRAWING_REFERENCE_PRECISION
    qualifier = getattr(part, "SUPPLIER_BORE_CALLOUT", None)
    case.kwargs.update(units=units, precision=precision,
                       model_references=part.SUPPLIER_MODEL_REFERENCES, bore_callout=qualifier)
    for label in values:
        for collection in (case.sources, case.imports):
            item = collection[label]
            item.state.unit = 3 if units == "in" else 0
            item.state.precision = precision[label]
            item.text.update({2: f" {units})",
                              4: (qualifier or "") if label == washer.BORE_DIAMETER else ""})
        case.paint[label].record = copy.deepcopy(captured["records"][label])
    # These captures are the settled exported sheets, where the thickness
    # already uses OffsetText. Replaying them must not move its witnesses.
    case.imports[washer.THICKNESS].display.OffsetText = True
    for orientation, outline in captured["view_outlines"].items():
        case.views[orientation].GetOutline = lambda outline=outline: tuple(outline)
    return case, captured


@pytest.mark.parametrize("scope", (
    "ch-thrust", "sm-hanger", "mg-back", "mg-front",
))
def test_washer_consumer_clears_retained_native_od_blocks_and_preserves_neighbors(monkeypatch, scope):
    from _layout_audit import display_box
    from _supplier_screw_layout import supplier_top_text_geometry

    case, captured = _retained_washer_layout(monkeypatch, scope)
    outer, thick = case.helper.OUTER_DIAMETER, case.helper.THICKNESS
    before_source = _washer_source_state(case)
    before = copy.deepcopy(case.paint[outer].record)
    before_station = supplier_top_text_geometry(case.paint[thick].record, horizontal=False)
    face = case.views["*Top" if captured["axis"] == "y" else "*Front"]
    assert display_box({"texts": before["display"]["texts"]}).xmin < face.GetOutline()[2]

    settled = case.helper.supplier_washer_dimensions(case.adapter, case.views, **case.kwargs)
    settled()
    record = case.paint[outer].record
    box = display_box({"texts": record["display"]["texts"]})
    assert box.xmin - face.GetOutline()[2] >= .002
    assert record["pos"][1] == before["pos"][1]
    assert record["pos"][0] > before["pos"][0]
    assert [(row["t"], row["w"], row["h"]) for row in record["display"]["texts"]] == [
        (row["t"], row["w"], row["h"]) for row in before["display"]["texts"]
    ]
    assert case.imports[outer].display.OffsetText is False
    after_station = supplier_top_text_geometry(case.paint[thick].record, horizontal=False)
    for field in ("tips", "witnesses", "physical_lines"):
        assert after_station[field] == before_station[field]
    bounds = tuple(value * 1000 for value in (box.xmin, box.ymin, box.xmax, box.ymax))
    left, bottom, right, top = captured["printable_mm"]
    assert left <= bounds[0] < bounds[2] <= right
    assert bottom <= bounds[1] < bounds[3] <= top
    for neighbor in captured["neighbors"]:
        x0, y0, x1, y1 = neighbor["bounds_mm"]
        assert bounds[2] < x0 or bounds[0] > x1 or bounds[3] < y0 or bounds[1] > y1
    assert _washer_source_state(case) == before_source


def test_washer_final_consumer_refuses_actual_r50_od_strike_after_other_guards_pass(monkeypatch):
    from _layout_audit import display_box

    case, captured = _retained_washer_layout(monkeypatch, "ch-thrust")
    outer = case.helper.OUTER_DIAMETER
    old = copy.deepcopy(case.paint[outer].record)
    point = tuple(value / 1000 for value in captured["observed_od_contact_mm"])
    old_box = display_box({"texts": old["display"]["texts"]})
    assert old_box.xmin < point[0] < old_box.xmax
    assert old_box.ymin < point[1] < old_box.ymax
    before = _washer_source_state(case)
    settled = case.helper.supplier_washer_dimensions(case.adapter, case.views, **case.kwargs)
    settled()
    new_box = display_box({"texts": case.paint[outer].record["display"]["texts"]})
    assert new_box.xmin > point[0]
    case.paint[outer].record = old
    with pytest.raises(RuntimeError):
        settled()
    assert _washer_source_state(case) == before


@pytest.mark.parametrize("label", ("supplier outer diameter", "supplier bore diameter"))
@pytest.mark.parametrize("defect", ("reject", "clamp"))
def test_washer_refuses_unrealized_diameter_text_clearance_without_source_changes(monkeypatch, label, defect):
    case = _r48_washer_layout(monkeypatch)
    before = _washer_source_state(case)
    setattr(case.paint[label], defect, True)
    with pytest.raises(RuntimeError):
        case.helper.supplier_washer_dimensions(case.adapter, case.views, **case.kwargs)
    assert _washer_source_state(case) == before


def test_washer_already_clear_od_is_unchanged_without_repositioning(monkeypatch):
    case = _r48_washer_layout(monkeypatch)
    record = case.paint[case.helper.OUTER_DIAMETER].record
    for row in record["display"]["texts"]:
        row["pos"][0] += .05
    record["pos"][0] += .05
    before = copy.deepcopy(record)
    case.paint[case.helper.OUTER_DIAMETER].reject = True
    settled = case.helper.supplier_washer_dimensions(case.adapter, case.views, **case.kwargs)
    settled()
    assert case.paint[case.helper.OUTER_DIAMETER].record == before
