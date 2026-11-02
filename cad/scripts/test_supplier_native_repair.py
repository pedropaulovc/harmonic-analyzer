"""Native-I/O regressions for the observed R41 pin/washer failures; no COM seat."""

from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def _pin_import_case(monkeypatch, kind, *, defect=None):
    import _supplier_pin_drawing as drawing
    import _supplier_pin_model as source_helpers
    from _supplier_pin_data import MATING_HOLE_DIMENSION
    from test_purchased_fastener_drawing import _supplier_native

    for module in (drawing, source_helpers):
        monkeypatch.setattr(module, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(source_helpers, "_bind", lambda value, _interface: value)
    source = SimpleNamespace(
        sku="native-pin", units="in", unit_mm=25.4,
        diameter_mm=2.38125, diameter_precision=3,
        diameter_band=(-0.01, 0.01), diameter_uses_limits=False,
        diameter_deviations_mm=(-0.01, 0.01),
        wall_mm=0.381, wall_precision=3,
        application_hole_limits=(0.09375, 0.0945),
        application_hole_precision=4, application_hole_center=(2.0, 0.0),
        sheet_unit="mm",
    )
    # The sheet the drawing opened; a mismatch with the part's declared unit
    # is refused before anything is imported.
    monkeypatch.setattr(drawing, "sheet_units", lambda _adapter: "in" if defect == "sheet_unit" else "mm")
    # Expected metadata is independent of the production contract/formatter.
    feature, name, value_mm, precision, band, callout = {
        "diameter": (source_helpers.DIAMETER_FEATURE, "SupplierPinDiameter", 2.38125,
                     3, (-0.00001, 0.00001, 2), ""),
        "wall": (source_helpers.WALL_FEATURE, "SupplierPinWall", 0.381,
                 3, (0.0, 0.0, 0), "WALL"),
        "mating_hole": (source_helpers.MATING_HOLE_FEATURE, MATING_HOLE_DIMENSION, 2.38125,
                        4, (0.0, 0.00001905, 3), "MATING HOLE\nSUPPLIER APPLICATION ONLY"),
    }[kind]
    is_wall = kind == "wall"
    outer_radius, inner_radius = 0.001190625, 0.000809625
    if is_wall:
        entities = tuple(SimpleNamespace(X=radius, Y=0.0, Z=0.0)
                         for radius in (inner_radius, outer_radius))
        segment = SimpleNamespace(
            ConstructionGeometry=True, GetType=lambda: 0,
            GetStartPoint2=lambda: entities[0], GetEndPoint2=lambda: entities[1],
        )
    else:
        center = SimpleNamespace(X=0.002 if kind == "mating_hole" else 0.0, Y=0.0, Z=0.0)
        segment = SimpleNamespace(
            ConstructionGeometry=True, GetType=lambda: 1, IsCircle=lambda: 1,
            GetCenterPoint2=lambda: center, GetRadius=lambda: outer_radius,
        )
        entities = (segment,)
    sketch = SimpleNamespace(GetSketchSegments=lambda: (segment,))
    owner = SimpleNamespace(GetSpecificFeature2=lambda: sketch)
    surfaces = []
    for radius in ((inner_radius, outer_radius) if is_wall else (outer_radius,)):
        direction = (1.0, 0.0, 0.0) if is_wall else (0.0, 1.0, 0.0)
        surface = SimpleNamespace(IsCylinder=lambda: True,
                                  CylinderParams=(0.0, 0.0, 0.0, *direction, radius))
        surfaces.append(SimpleNamespace(GetSurface=lambda surface=surface: surface))
    model = SimpleNamespace(
        FeatureByName=lambda requested: owner if requested == feature else None,
        GetBodies2=lambda *_args: (SimpleNamespace(GetFaces=lambda: surfaces),),
    )
    mapped = tuple(SimpleNamespace(**vars(entity)) for entity in entities)
    view = SimpleNamespace(ReferencedDocument=model)

    def corresponding(entity):
        index = next(index for index, actual in enumerate(entities) if actual is entity)
        if defect == "missing_mapping":
            return None
        return mapped[0] if defect == "duplicate_mapping" else mapped[index]

    view.GetCorresponding = corresponding
    cases = []
    for imported in (False, True):
        case = _supplier_native(monkeypatch, value=value_mm / 1000.0, kind=2 if is_wall else 6)
        case.native.FullName = f"{name}@{feature}@{'drawing' if imported else 'source'}"
        case.native.GetSystemValue3 = lambda *_args, case=case: (case.native.SystemValue,)
        lower, upper, tolerance_kind = band
        case.native.Tolerance = SimpleNamespace(Type=tolerance_kind, lower=lower, upper=upper)
        tolerance = case.native.Tolerance
        tolerance.GetMinValue = lambda tolerance=tolerance: tolerance.lower
        tolerance.GetMaxValue = lambda tolerance=tolerance: tolerance.upper
        case.state.use_doc = imported
        case.state.tolerance_precision = -1 if imported else precision
        case.display.GetUseDocUnits = lambda case=case: case.state.use_doc
        case.display.GetPrimaryTolPrecision2 = lambda case=case: case.state.tolerance_precision
        case.display.GetNameForSelection = lambda: f"{name}@View"
        original_units, original_precision = case.display.SetUnits2, case.display.SetPrecision3

        def units(use_doc, *args, case=case, original=original_units):
            case.state.use_doc = use_doc
            return original(use_doc, *args)

        def places(primary, dual, tolerance, dual_tolerance, case=case, original=original_precision):
            if tolerance >= 0:
                case.state.tolerance_precision = tolerance
            return original(primary, dual, tolerance, dual_tolerance)

        case.display.SetUnits2, case.display.SetPrecision3 = units, places
        if not imported:
            case.state.unit, case.state.precision = 3, precision
            case.text.update({1: "(" if is_wall else "(<MOD-DIAM>", 2: " in)", 4: callout})

            def forbidden_source_write(*_args, **_kwargs):
                raise AssertionError("drawing attempted to write original model presentation")

            case.display.SetUnits2 = forbidden_source_write
            case.display.SetPrecision3 = forbidden_source_write
            case.display.SetText = forbidden_source_write
        case.annotation.entities = mapped if imported else entities
        case.annotation.Owner = view
        cases.append(case)
    original, imported = cases
    def lookup(*_args, **_kwargs):
        return {name: (original.display, original.native)}

    monkeypatch.setattr(drawing, "_named_dimensions", lookup)
    monkeypatch.setattr(source_helpers, "_named_dimensions", lookup)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, _annotation: name)
    imports = []

    def import_annotations(*_args, **_kwargs):
        imports.append(name)
        if defect == "source_changed_on_import":
            original.state.use_doc = True
        elif defect == "source_document":
            view.ReferencedDocument = object()
        return [imported.annotation]

    monkeypatch.setattr(drawing, "curate_view_dimensions", import_annotations)
    if defect == "source_value":
        original.native.SystemValue += 0.001
    elif defect == "source_format":
        original.state.use_doc = True
    elif defect == "source_band":
        original.native.Tolerance.Type = 9
    elif defect == "source_geometry":
        segment.ConstructionGeometry = False
    elif defect == "import_value":
        imported.native.SystemValue += 0.001
    elif defect == "import_band":
        imported.native.Tolerance.Type = 9
    elif defect == "source_attachment":
        imported.annotation.entities = entities
    elif defect == "foreign_attachment":
        imported.annotation.entities = (SimpleNamespace(**vars(mapped[0])), *mapped[1:])
    elif defect == "extra_attachment":
        imported.annotation.entities = (*mapped, object())
    elif defect == "duplicate_attachment":
        imported.annotation.entities = (mapped[0], mapped[0])
    view.GetAnnotationsByType = lambda _kind: (imported.annotation,)
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda left, right: int(left is right)))

    def import_and_settle():
        result = drawing._import_model_references(adapter, view, source, {name: (0.1, 0.1)})
        display, guard = result[name]
        return drawing._settled_pin_check(
            adapter, {"*Top": view}, [("*Top", display, guard)], expected_count=1, label=source.sku,
        )

    def source_snapshot():
        return (original.native.SystemValue, copy.deepcopy(vars(original.state)),
                copy.deepcopy(original.text), copy.deepcopy(vars(original.native.Tolerance)))

    return SimpleNamespace(
        import_and_settle=import_and_settle, source_snapshot=source_snapshot,
        original=original, imported=imported, imports=imports, view=view, model=model,
    )


@pytest.mark.parametrize("kind", ("diameter", "wall", "mating_hole"))
def test_pin_import_uses_local_presentation_and_actual_view_witnesses_without_source_writes(monkeypatch, kind):
    case = _pin_import_case(monkeypatch, kind)
    before = case.source_snapshot()
    settled = case.import_and_settle()
    settled()
    assert case.imported.display.GetUseDocUnits() is False
    assert case.imported.native.SystemValue == before[0]
    assert case.source_snapshot() == before


@pytest.mark.parametrize("defect", ("source_value", "source_format", "source_band", "source_geometry", "sheet_unit"))
def test_pin_invalid_original_is_rejected_before_import(monkeypatch, defect):
    case = _pin_import_case(monkeypatch, "diameter", defect=defect)
    with pytest.raises(RuntimeError):
        case.import_and_settle()
    assert case.imports == []


@pytest.mark.parametrize("kind", ("diameter", "wall", "mating_hole"))
@pytest.mark.parametrize("defect", (
    "import_value", "import_band", "source_attachment", "foreign_attachment",
    "extra_attachment", "missing_mapping", "source_changed_on_import", "source_document",
))
def test_pin_import_rejects_wrong_native_value_band_context_or_source_mutation(monkeypatch, kind, defect):
    case = _pin_import_case(monkeypatch, kind, defect=defect)
    with pytest.raises(RuntimeError):
        case.import_and_settle()


@pytest.mark.parametrize("defect", ("duplicate_attachment", "duplicate_mapping"))
def test_pin_wall_requires_two_distinct_correct_view_endpoints(monkeypatch, defect):
    case = _pin_import_case(monkeypatch, "wall", defect=defect)
    with pytest.raises(RuntimeError):
        case.import_and_settle()


@pytest.mark.parametrize("drift", ("source_value", "source_format", "source_document", "import_value"))
def test_pin_final_export_rechecks_original_source_and_import_after_rebuild(monkeypatch, drift):
    case = _pin_import_case(monkeypatch, "diameter")
    settled = case.import_and_settle()
    if drift == "source_value":
        case.original.native.SystemValue += 0.001
    elif drift == "source_format":
        case.original.state.use_doc = True
    elif drift == "source_document":
        case.view.ReferencedDocument = object()
    else:
        case.imported.native.SystemValue += 0.001
    with pytest.raises(RuntimeError):
        settled()


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


def test_washer_import_refuses_uninherited_tolerance_precision_without_repairing_source(monkeypatch):
    from test_purchased_fastener_drawing import _washer_import_native

    case = _washer_import_native(monkeypatch)
    label = case.helper.THICKNESS
    before = (
        case.sources[label].native.SystemValue,
        case.sources[label].native.Tolerance.Type,
        dict(vars(case.sources[label].state)),
    )
    case.imports[label].display.GetPrimaryTolPrecision2 = lambda: 2
    with pytest.raises(RuntimeError, match="precision|band"):
        case.helper.supplier_washer_dimensions(case.adapter, case.views, **case.kwargs)
    assert (
        case.sources[label].native.SystemValue,
        case.sources[label].native.Tolerance.Type,
        dict(vars(case.sources[label].state)),
    ) == before


def _r48_washer_layout(monkeypatch, *, axis="z", banded="thickness"):
    from test_purchased_fastener_drawing import _washer_import_native
    import _supplier_washer_drawing as washer

    case = _washer_import_native(monkeypatch, axis=axis, values={
        washer.OUTER_DIAMETER: 11.1252, washer.BORE_DIAMETER: 5.08, washer.THICKNESS: .91,
    })
    # The captured limits stack, not a nominal-value-only surrogate.
    case.bands[washer.THICKNESS] = (.7366, 1.0922, "limits")
    for collection in (case.sources, case.imports):
        native = collection[washer.THICKNESS].native
        native.Tolerance.Type = 3
        native.Tolerance.GetMinValue = lambda: (.7366 - .91) / 1000
        native.Tolerance.GetMaxValue = lambda: (1.0922 - .91) / 1000
    if banded == "thickness":
        case.kwargs["bands"] = {washer.THICKNESS: case.bands[washer.THICKNESS]}
    qualifier = "FOR No. 10 SCREW SIZE"
    case.sources[washer.BORE_DIAMETER].text[4] = qualifier
    case.kwargs["bore_callout"] = qualifier
    return case


def _washer_source_state(case):
    return {
        label: (item.native.SystemValue, item.native.Tolerance.Type,
                item.native.Tolerance.GetMinValue(), item.native.Tolerance.GetMaxValue(),
                dict(vars(item.state)), dict(item.text), tuple(item.annotation.entities))
        for label, item in case.sources.items()
    }


@pytest.mark.parametrize("axis", ("y", "z"))
@pytest.mark.parametrize("banded", ("thickness", "all"))
def test_washer_complete_consumer_replay_clears_limits_and_diameters_without_moving_witnesses(
    monkeypatch, axis, banded,
):
    import copy
    from _layout_audit import display_box
    from _supplier_screw_layout import supplier_top_text_geometry

    case = _r48_washer_layout(monkeypatch, axis=axis, banded=banded)
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
    units, precision, bands = part.SUPPLIER_UNITS, part.DRAWING_REFERENCE_PRECISION, part.SUPPLIER_TOLERANCES
    qualifier = getattr(part, "SUPPLIER_BORE_CALLOUT", None)
    case.kwargs.update(units=units, precision=precision, bands=bands, bore_callout=qualifier)
    for label, value in values.items():
        for collection in (case.sources, case.imports):
            item = collection[label]
            item.state.unit = 3 if units == "in" else 0
            item.state.precision = precision[label]
            item.display.GetPrimaryTolPrecision2 = lambda places=precision[label]: places
            item.text.update({2: f" {units})",
                              4: (qualifier or "") if label == washer.BORE_DIAMETER else ""})
            lower, upper, style = bands.get(label, (value, value, None))
            item.native.Tolerance.Type = {"bilateral": 2, "limits": 3, "symmetric": 4, None: 0}[style]
            item.native.Tolerance.GetMinValue = lambda deviation=(lower - value) / 1000: deviation
            item.native.Tolerance.GetMaxValue = lambda deviation=(upper - value) / 1000: deviation
        case.paint[label].record = copy.deepcopy(captured["records"][label])
    # These captures are the settled exported sheets, where the thickness
    # already uses OffsetText. Replaying them must not move its witnesses.
    case.imports[washer.THICKNESS].display.OffsetText = True
    for orientation, outline in captured["view_outlines"].items():
        case.views[orientation].GetOutline = lambda outline=outline: tuple(outline)
    return case, captured


@pytest.mark.parametrize("scope", (
    "ch-lever", "ch-thrust", "sm-hanger", "mg-back", "mg-front",
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


@pytest.mark.parametrize(
    "family,head_half,head_one,front_half,front_one",
    (
        ("carriage", 14.676, 18.176, 23.332567791611, 35.489135583221),
        ("bracket", 14.605, 18.034, 21.353286632314, 31.530573264629),
        ("rail", 14.605, 18.034, 22.950425184312, 34.724850368624),
        ("clamp", 15.9385, 20.701, 25.705462650093, 40.234925300185),
        ("lever", 17.129125, 23.08225, 28.115608490064, 45.055216980128),
    ),
)
def test_ch_supplier_screw_consumers_fit_actual_padded_outlines_and_keep_annotation_lanes(
    monkeypatch, tmp_path, family, head_half, head_one, front_half, front_one,
):
    import asyncio
    import importlib

    import _purchased_fastener_drawing as purchased
    from test_purchased_fastener_drawing import _Drawing, _View

    # Recorded R38 native GetOutline sizes at 1:2 and 1:1. Interpolating these
    # two measurements retains the observed fixed sheet-space padding; this is
    # not a catalogue-only body rectangle or a scaled 1:1 native outline.
    sizes = {
        "*Front": ((head_half, front_half), (head_one, front_one)),
        "*Top": ((head_half, head_half), (head_one, head_one)),
        "*Right": ((head_half, front_half), (head_one, front_one)),
    }

    class NativeView(_View):
        @property
        def Position(self):
            return self._center

        def GetOutline(self):
            half, one = sizes[self._orientation]
            ratio = self.ScaleRatio[0] / self.ScaleRatio[1]
            width, height = (
                (2 * (full - small) * ratio + 2 * small - full) / 1000.0
                for small, full in zip(half, one, strict=True)
            )
            x, y = self._center
            return (x - width / 2, y - height / 2, x + width / 2, y + height / 2)

        def SetViewPosition(self, position, _update):
            self._center = tuple(position)
            return True

    monkeypatch.setattr(purchased, "double_array", tuple)
    consumer = importlib.import_module(
        f"draw_ch_rocker_arm_tl_vn_oblique_{family}_screw"
    )

    async def fit_native(_adapter, spec, *, view_layout, supplier_margins, **_kwargs):
        stock = purchased.fastener(spec.artifact_stem)
        notes = str(purchased._config.parts(stock.part_name).get("installation_notes", ""))
        caption_y = purchased.view_band_bottom(notes, label=spec.artifact_stem)

        def fit(layout):
            outer = purchased.fastener_view_cells(caption_y, layout=layout)
            fitted = purchased.supplier_fit_cells(
                outer, supplier_margins, label=spec.artifact_stem,
            )
            members = [
                (NativeView(name, tmp_path / "supplier.SLDPRT", center), (name, center, box))
                for name, center, box in fitted if name in sizes
            ]
            scale = purchased._fit_group(_Drawing(), members)
            return scale, outer, members

        # The original native failure: constant outline padding leaves no
        # supported standard scale inside the ordinary Top annotation lanes.
        with pytest.raises(RuntimeError, match="no project-standard scale"):
            fit("standard")
        scale, outer, members = fit(view_layout)
        assert scale == (1, 2)
        outer_bounds = {name: box for name, _, box in outer}
        for view, (name, _center, geometry_cell) in members:
            bounds = view.GetOutline()
            assert purchased._inside(bounds, geometry_cell)
            left, bottom, right, top = supplier_margins.get(name, (0.0,) * 4)
            complete = (
                bounds[0] - left, bounds[1] - bottom,
                bounds[2] + right, bounds[3] + top,
            )
            assert purchased._inside(complete, outer_bounds[name])
        return {"orthographic": scale}

    monkeypatch.setattr(consumer, "build_purchased_fastener_drawing", fit_native)
    assert asyncio.run(consumer.build(object())) == {"orthographic": (1, 2)}
