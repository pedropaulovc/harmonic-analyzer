"""Native-I/O regressions for the observed R41 pin/washer failures; no COM seat."""

from __future__ import annotations

import copy
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
    )
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


@pytest.mark.parametrize("defect", ("source_value", "source_format", "source_band", "source_geometry"))
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
def test_washer_owner_identity_uses_the_part_or_exact_view_namespace(monkeypatch, label):
    from test_purchased_fastener_drawing import _washer_import_native

    case = _washer_import_native(monkeypatch)
    source = case.sources[label]
    imported = case.imports[label]
    orientation = "*Front" if label == case.helper.THICKNESS else "*Top"
    view = case.views[orientation]
    source_owner = source.native.GetFeatureOwner()
    imported_owner = imported.native.GetFeatureOwner()
    assert case.adapter.swApp.IsSame(source_owner, imported_owner) == 0
    assert case.adapter.swApp.IsSame(view.GetCorresponding(source_owner), imported_owner) == 1
    for display, owner_view in ((source.display, None), (imported.display, view)):
        case.source_helper.assert_supplier_washer_source_attachment(
            case.adapter, case.model, display, view=owner_view, label=label,
            axis="y", bore_mm=6.35, outer_mm=12.7, thickness_mm=1.5875,
        )


@pytest.mark.parametrize("defect", (
    "foreign_mapping", "missing_mapping", "part_owner", "missing_owner",
    "native_name", "source_name", "native_type",
))
def test_washer_view_owner_requires_native_identity_not_matching_metadata(monkeypatch, defect):
    case, label, display = _washer_failure_case(monkeypatch)
    source = case.sources[label]
    imported = case.imports[label]
    feature_name = case.source_helper.THICKNESS_FEATURE
    feature = case.model.FeatureByName(feature_name)
    if defect == "foreign_mapping":
        case.mapped[id(feature)] = SimpleNamespace(Name=feature_name, GetTypeName2=lambda: "ProfileFeature")
    elif defect == "missing_mapping":
        case.mapped.pop(id(feature))
    elif defect == "part_owner":
        imported.native.GetFeatureOwner = lambda: feature
    elif defect == "missing_owner":
        imported.native.GetFeatureOwner = lambda: None
    elif defect == "native_name":
        imported.native.FullName = "Other@SupplierWasherThicknessReference@stock"
    elif defect == "source_name":
        source.native.FullName = "Other@SupplierWasherThicknessReference@stock"
    else:
        imported.display.Type2 = 6
    with pytest.raises(RuntimeError, match="named model witness"):
        _assert_washer_source_attachment(case, label, display)


def test_washer_part_owner_cannot_be_replaced_with_a_drawing_owner(monkeypatch):
    case, label, _display = _washer_failure_case(monkeypatch)
    source = case.sources[label]
    mapped_owner = case.imports[label].native.GetFeatureOwner()
    source.native.GetFeatureOwner = lambda: mapped_owner
    with pytest.raises(RuntimeError, match="named model witness"):
        case.source_helper.assert_supplier_washer_source_attachment(
            case.adapter, case.model, source.display, view=None, label=label,
            axis="y", bore_mm=6.35, outer_mm=12.7, thickness_mm=1.5875,
        )


def test_washer_owner_failure_reports_remaining_context_despite_an_independent_reader_error(monkeypatch):
    case, label, display = _washer_failure_case(monkeypatch)
    observations = []

    def interrupted_type():
        raise RuntimeError("optional owner type reader failed")

    foreign_owner = SimpleNamespace(Name="Foreign", GetTypeName2=interrupted_type)
    case.imports[label].native.GetFeatureOwner = lambda: foreign_owner
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
    original = SystemExit("original native owner reader")
    observations = []

    def native_failure():
        raise original

    case.imports[label].native.GetFeatureOwner = native_failure
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
    with pytest.raises(KeyboardInterrupt) as caught:
        _assert_washer_source_attachment(case, label, display)
    assert caught.value is original


def test_washer_ordinary_observer_error_does_not_replace_original_native_failure(monkeypatch):
    case, label, display = _washer_failure_case(monkeypatch)
    original = RuntimeError("original native owner reader")

    def native_failure():
        raise original

    def log_failure(*_args, **_kwargs):
        raise ValueError("secondary observer failure")

    case.imports[label].native.GetFeatureOwner = native_failure
    monkeypatch.setattr(case.source_helper._telemetry, "info", log_failure)
    with pytest.raises(RuntimeError) as caught:
        _assert_washer_source_attachment(case, label, display)
    assert caught.value is original


def test_washer_healthy_owner_check_does_not_run_failure_only_observers(monkeypatch):
    case, label, display = _washer_failure_case(monkeypatch)

    def unexpected_observation(*_args, **_kwargs):
        raise AssertionError("healthy ownership path called failure-only diagnostics")

    monkeypatch.setattr(case.source_helper._telemetry, "info", unexpected_observation)
    case.model.GetPathName = unexpected_observation
    # The owner/source identity check is healthy, but the original display has
    # not been formatted by the drawing yet. The attachment proof itself is
    # independent of that presentation operation.
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


@pytest.mark.parametrize(
    "family,head_half,head_one,front_half,front_one",
    (
        ("carriage", 14.676, 18.176, 23.332567791611, 35.489135583221),
        ("block", 14.605, 18.034, 37.248070506164, 63.320141012327),
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
