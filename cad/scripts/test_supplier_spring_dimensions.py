"""Offline configured-reference and final annotation readback contracts; no native run."""

from __future__ import annotations

import asyncio
import math
from types import SimpleNamespace

import pytest

import _supplier_disc_spring_drawing as disc
import _supplier_extension_spring as extension
import _supplier_spring_drawing as layout
import _supplier_spring_reference as refs
import ch_vn_channel_spring_installed_spec as channel
import ch_vn_rocker_bank_spring_spec as rocker
import dt_vn_cylinder_bank_spring_spec as cylinder
import pd_vn_transgear_pivot_spring_spec as pivot
import sm_vn_counter_spring_spec as counter
import vn_disc_spring_supplier_stock as stock


class _View:
    def __init__(self, name, configuration):
        self.name = name
        self.ReferencedConfiguration = configuration
        self.annotations = []
        self.source_points = ((0.0, 0.0), (0.1, 0.02))
        self.Position = (0.1, 0.1)
        self.ScaleRatio = (1, 1)
        self.kept_positions = {}

    def GetAnnotations(self):
        return self.annotations

    def GetDisplayDimensionCount(self):
        return len(self.annotations)

    def GetOutline(self):
        raise AssertionError("supplier source ink must not use a padded GetOutline")


def _captured_reference_bounds(views):
    """Family callback fixture: immutable source coordinates, current view transform."""
    captured = {
        key: tuple(tuple(point) for point in view.source_points)
        for key, view in views.items()
        if not key.startswith("installed_")
    }

    def reference_bounds(key):
        view = views[key]
        factor = view.ScaleRatio[0] / view.ScaleRatio[1]
        projected = tuple(
            (view.Position[0] + x * factor, view.Position[1] + y * factor)
            for x, y in captured[key]
        )
        return (
            min(x for x, _y in projected),
            min(y for _x, y in projected),
            max(x for x, _y in projected),
            max(y for _x, y in projected),
        )

    return reference_bounds


def _native_annotation(name, owner, value, band=None):
    tolerance = SimpleNamespace(
        Type=0 if band is None else (4 if math.isclose(band[0], -band[1]) else 2),
        GetMinValue=lambda: 0.0 if band is None else band[1] / 1000,
        GetMaxValue=lambda: 0.0 if band is None else band[0] / 1000,
    )
    native = SimpleNamespace(
        FullName=f"{name}@{owner}@Source", value=value, Tolerance=tolerance
    )
    native.GetSystemValue3 = lambda option, names: (native.value / 1000,)
    display = SimpleNamespace(
        GetDimension2=lambda index: native, GetPrimaryTolPrecision2=lambda: 3
    )
    annotation = SimpleNamespace(
        name=name,
        GetType=lambda: 4,
        GetSpecificAnnotation=lambda: display,
    )
    return annotation


def _readback_environment(monkeypatch, module, views):
    """Leave family inventory/configured-SI/band proofs real; core formatting is independent."""
    monkeypatch.setattr(layout, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(layout, "iter_views", lambda adapter: tuple(views.values()))
    monkeypatch.setattr(layout, "view_name", lambda adapter, view: view.name)
    monkeypatch.setattr(module, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(
        module, "dimension_name", lambda adapter, annotation: annotation.name
    )
    monkeypatch.setattr(
        module,
        "supplier_reference_dimension",
        lambda adapter, display, **kwargs: display,
    )
    monkeypatch.setattr(
        module, "assert_supplier_reference_dimension", lambda *args, **kwargs: None
    )

    def curate(adapter, view, *, keep, **kwargs):
        view.kept_positions = dict(keep)
        return [
            annotation for annotation in view.annotations if annotation.name in keep
        ]

    monkeypatch.setattr(module, "curate_view_dimensions", curate)


def _extension_views(spec):
    views = {
        "free_front": _View("free", refs.SUPPLIER_FREE_CONFIGURATION),
        "free_right": _View("section", refs.SUPPLIER_FREE_CONFIGURATION),
        "max_front": _View("maximum", refs.SUPPLIER_MAX_CONFIGURATION),
        "installed_iso": _View("installed", "OriginalInstalled"),
    }
    values = {
        extension.FREE_LENGTH: spec.FREE_LENGTH_MM,
        extension.MAX_LENGTH: spec.MAX_LENGTH_MM,
        extension.COIL_OD: spec.SUPPLIER_COIL_OD_MM,
        extension.WIRE_DIA: spec.SUPPLIER_WIRE_DIA_MM,
    }
    for key, names in (
        ("free_front", (extension.FREE_LENGTH,)),
        ("free_right", (extension.COIL_OD, extension.WIRE_DIA)),
        ("max_front", (extension.MAX_LENGTH,)),
    ):
        for name in names:
            owner = next(
                owner
                for owner, owned in extension.DIMENSIONS_BY_FEATURE.items()
                if name in owned
            )
            band = (
                (
                    channel.SUPPLIER_COIL_OD_TOLERANCE_MM,
                    -channel.SUPPLIER_COIL_OD_TOLERANCE_MM,
                )
                if spec is channel and name == extension.COIL_OD
                else None
            )
            views[key].annotations.append(
                _native_annotation(name, owner, values[name], band)
            )
    return views


def _extension_checks(spec, views):
    return layout.extension_spring_dimensions(
        object(),
        views,
        free_length_mm=spec.FREE_LENGTH_MM,
        max_length_mm=spec.MAX_LENGTH_MM,
        reference_bounds=_captured_reference_bounds(views),
        coil_od_mm=spec.SUPPLIER_COIL_OD_MM,
        wire_dia_mm=spec.SUPPLIER_WIRE_DIA_MM,
        precision=spec.SUPPLIER_PRECISION,
        od_tolerance_mm=getattr(spec, "SUPPLIER_COIL_OD_TOLERANCE_MM", None),
        od_tolerance_precision=getattr(
            spec, "SUPPLIER_COIL_OD_TOLERANCE_PRECISION", None
        ),
    )


@pytest.mark.parametrize("spec", [channel, counter], ids=["9432K31", "1330K524"])
@pytest.mark.parametrize(
    "corruption",
    [
        "owner",
        "config",
        "exact_value",
        "missing",
        "duplicate",
        "installed_dimension",
        "unexpected_band",
    ],
)
def test_extension_final_checks_reacquire_actual_annotations(
    monkeypatch, spec, corruption
):
    views = _extension_views(spec)
    _readback_environment(monkeypatch, layout, views)
    checks = _extension_checks(spec, views)
    for check in checks:
        check()
    view = views["max_front"]
    annotation = view.annotations[0]
    native = annotation.GetSpecificAnnotation().GetDimension2(0)
    if corruption == "owner":
        native.FullName = f"{extension.MAX_LENGTH}@InstalledGeometry@Source"
    elif corruption == "config":
        view.ReferencedConfiguration = "OriginalInstalled"
    elif corruption == "exact_value":
        native.value = round(spec.MAX_LENGTH_MM / 25.4, 2) * 25.4 + 0.01
    elif corruption == "missing":
        view.annotations.clear()
    elif corruption == "duplicate":
        view.annotations.append(annotation)
    elif corruption == "installed_dimension":
        views["installed_iso"].annotations.append(annotation)
    else:
        native.Tolerance.Type = 4
    with pytest.raises(RuntimeError):
        for check in checks:
            check()


@pytest.mark.parametrize("corruption", ["type", "lower", "upper", "precision"])
def test_channel_source_od_band_is_rechecked_after_rebuild(monkeypatch, corruption):
    views = _extension_views(channel)
    _readback_environment(monkeypatch, layout, views)
    checks = _extension_checks(channel, views)
    display = views["free_right"].annotations[0].GetSpecificAnnotation()
    tolerance = display.GetDimension2(0).Tolerance
    if corruption == "type":
        tolerance.Type = 0
    elif corruption == "lower":
        tolerance.GetMinValue = lambda: 0.0
    elif corruption == "upper":
        tolerance.GetMaxValue = lambda: 0.0
    else:
        display.GetPrimaryTolPrecision2 = lambda: 0
    with pytest.raises(RuntimeError, match="band changed after final rebuild"):
        for check in checks:
            check()


def _disc_views(spec):
    rows = {"free_front": ("THICKNESS", "FREE_HEIGHT"), "free_top": ("ID", "OD")}
    application = spec.SUPPLIER_APPLICATION_DIMENSIONS
    if "SHAFT_DIA" in application:
        rows["free_top"] += ("SHAFT_DIA",)
    heights = tuple(
        name for name in application if name in ("WORKING_HEIGHT", "WORKING_DEFLECTION")
    )
    if heights:
        rows["free_right"] = heights
    views = {key: _View(key, refs.SUPPLIER_DIAGRAM_CONFIGURATION) for key in rows}
    views["installed_iso"] = _View("installed", "OriginalInstalled")
    for key, semantics in rows.items():
        for semantic in semantics:
            name = stock.SUPPLIER_DIMENSION_NAMES[semantic]
            owner = next(
                owner
                for owner, names in stock.SUPPLIER_DIMENSIONS_BY_FEATURE.items()
                if name in names
            )
            views[key].annotations.append(
                _native_annotation(
                    name,
                    owner,
                    getattr(spec, semantic),
                    getattr(spec, f"{semantic}_BAND", None),
                )
            )
    return views


@pytest.mark.parametrize("spec,count", [(cylinder, 4), (rocker, 4), (pivot, 6)])
@pytest.mark.parametrize(
    "corruption", ["owner", "config", "value", "missing", "extra", "band"]
)
def test_disc_final_checks_reacquire_source_and_application_gauges(
    monkeypatch, spec, count, corruption
):
    views = _disc_views(spec)
    _readback_environment(monkeypatch, disc, views)
    checks = []
    disc.supplier_disc_spring_dimensions(
        object(),
        views,
        spec=spec,
        reference_bounds=_captured_reference_bounds(views),
        settled_checks=checks,
    )
    assert sum(len(view.annotations) for view in views.values()) == count
    for check in checks:
        check()
    view = views["free_top"]
    native = view.annotations[0].GetSpecificAnnotation().GetDimension2(0)
    if corruption == "owner":
        native.FullName = "SupplierID@InstalledAnnulus@Source"
    elif corruption == "config":
        view.ReferencedConfiguration = "OriginalInstalled"
    elif corruption == "value":
        native.value += 0.01
    elif corruption == "missing":
        view.annotations.pop()
    elif corruption == "extra":
        views["installed_iso"].annotations.append(view.annotations[0])
    else:
        native.Tolerance.Type = 0 if spec is not pivot else 4
    with pytest.raises(RuntimeError):
        for check in checks:
            check()


@pytest.mark.parametrize(
    "spec,expected",
    [
        (
            cylinder,
            {
                "OD": 0.500,
                "ID": 0.385,
                "FREE_HEIGHT": 0.050,
                "THICKNESS": 0.005,
            },
        ),
        (rocker, {"OD": 0.367, "ID": 0.265, "FREE_HEIGHT": 0.03, "THICKNESS": 0.006}),
        (
            pivot,
            {
                "OD": 0.423,
                "ID": 0.2,
                "FREE_HEIGHT": 0.047,
                "THICKNESS": 0.0113,
                "WORKING_HEIGHT": 0.027,
                "SHAFT_DIA": 0.19,
            },
        ),
    ],
)
def test_exact_nominal_source_inventory_never_uses_installed_height(spec, expected):
    assert set(spec.SUPPLIER_DRAWING_PRECISION) == set(expected)
    for semantic, inches in expected.items():
        assert getattr(spec, semantic) == pytest.approx(inches * 25.4)
    assert spec.FREE_HEIGHT != spec.MODEL_HEIGHT
    if spec is pivot:
        assert spec.SUPPLIER_DRAWING_PRECISION["THICKNESS"] == 3
        assert spec.SUPPLIER_DRAWING_PRECISION["ID"] == 1
        assert spec.SUPPLIER_DRAWING_PRECISION["SHAFT_DIA"] == 2
    elif spec is rocker:
        assert (
            spec.OD_BAND == spec.ID_BAND == pytest.approx((0.010 * 25.4, -0.020 * 25.4))
        )
        assert spec.SUPPLIER_DRAWING_PRECISION["FREE_HEIGHT"] == 2
    else:
        assert (
            spec.OD_BAND == spec.ID_BAND == pytest.approx((0.010 * 25.4, -0.010 * 25.4))
        )


def test_nominal_disc_datums_and_application_gauges_are_not_loaded_shapes():
    assert stock.source_free_height_limits(rocker) == pytest.approx((-0.0762, 0.6858))
    for spec in (cylinder, pivot):
        baseline, compressed, free_upper = stock.supplier_application_planes(spec)
        assert compressed - baseline == pytest.approx(spec.WORKING_HEIGHT)
        assert free_upper - baseline == pytest.approx(spec.FREE_HEIGHT)
        assert free_upper - compressed == pytest.approx(spec.WORKING_DEFLECTION)


def test_disc_segments_are_construction_only_and_exact(monkeypatch):
    segments = [
        SimpleNamespace(
            ConstructionGeometry=False, GetType=lambda: 0, GetLength=lambda: 0.001
        )
    ]
    sketch = SimpleNamespace(GetSketchSegments=lambda: segments)
    model = SimpleNamespace(GetActiveSketch2=lambda: sketch)
    adapter = SimpleNamespace(currentModel=model)

    async def exit_sketch():
        return True

    adapter.exit_sketch = exit_sketch

    async def fully_defined(*args):
        return None

    dims = SimpleNamespace(apply=lambda *args: None)
    display = SimpleNamespace(MarkedForDrawing=True)
    native = SimpleNamespace(SystemValue=0.001)
    monkeypatch.setattr(stock, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(stock, "ensure_fully_defined", fully_defined)
    monkeypatch.setattr(stock, "check", lambda label, result: result)
    monkeypatch.setattr(stock, "name_last_feature", lambda *args: None)
    monkeypatch.setattr(stock, "mark_dimensions_for_drawing", lambda *args: None)
    monkeypatch.setattr(stock, "_named_dimension", lambda *args: (display, native))
    asyncio.run(
        stock._finish_reference(
            adapter,
            "Diagram",
            dims,
            ("FREE_HEIGHT",),
            spec=SimpleNamespace(FREE_HEIGHT=1.0),
            segment_lengths_mm=(1.0,),
        )
    )
    assert all(segment.ConstructionGeometry for segment in segments)


@pytest.mark.parametrize("spec", [channel, counter], ids=["9432K31", "1330K524"])
@pytest.mark.parametrize("scale", [(1, 1), (3, 2)])
def test_extension_dimension_positions_follow_actual_one_dimensional_native_ink(
    monkeypatch, spec, scale
):
    views = _extension_views(spec)
    for key, length, position in (
        ("free_front", spec.FREE_LENGTH_MM, (0.12, 0.17)),
        ("max_front", spec.MAX_LENGTH_MM, (0.19, 0.08)),
    ):
        views[key].source_points = ((-length / 2000, 0.0), (length / 2000, 0.0))
        views[key].Position = position
        views[key].ScaleRatio = scale
    radius = spec.SUPPLIER_COIL_OD_MM / 2000
    views["free_right"].source_points = ((-radius, -radius), (radius, radius))
    views["free_right"].Position = (0.30, 0.21)
    views["free_right"].ScaleRatio = scale
    _readback_environment(monkeypatch, layout, views)
    _extension_checks(spec, views)
    assert views["free_front"].kept_positions[extension.FREE_LENGTH] == pytest.approx(
        (0.12, 0.18)
    )
    assert views["max_front"].kept_positions[extension.MAX_LENGTH] == pytest.approx(
        (0.19, 0.09)
    )
    projected_radius = radius * scale[0] / scale[1]
    assert views["free_right"].kept_positions[extension.COIL_OD] == pytest.approx(
        (0.30 + projected_radius + 0.006, 0.21 + projected_radius + 0.005)
    )
    assert views["free_right"].kept_positions[extension.WIRE_DIA] == pytest.approx(
        (0.30 + projected_radius + 0.006, 0.21 - projected_radius - 0.009)
    )


@pytest.mark.parametrize(
    "spec", [cylinder, rocker, pivot], ids=["9714K392", "9714K24", "9715K43"]
)
def test_disc_stock_and_application_positions_follow_actual_native_ink(
    monkeypatch, spec
):
    views = _disc_views(spec)
    radius = spec.OD / 2000
    low, high = stock.source_free_height_limits(spec)
    views["free_front"].source_points = ((-radius, low / 1000), (radius, high / 1000))
    views["free_front"].Position = (0.08, 0.10)
    views["free_front"].ScaleRatio = (2, 1)
    views["free_top"].source_points = ((-radius, -radius), (radius, radius))
    views["free_top"].Position = (0.12, 0.21)
    views["free_top"].ScaleRatio = (3, 2)
    if "free_right" in views:
        baseline, compressed, free_upper = stock.supplier_application_planes(spec)
        gauge_upper = (
            free_upper
            if "WORKING_DEFLECTION" in spec.SUPPLIER_APPLICATION_DIMENSIONS
            else compressed
        )
        views["free_right"].source_points = (
            (-radius, baseline / 1000),
            (radius, gauge_upper / 1000),
        )
        views["free_right"].Position = (0.31, 0.08)
        views["free_right"].ScaleRatio = (1, 2)
    _readback_environment(monkeypatch, disc, views)
    disc.supplier_disc_spring_dimensions(
        object(),
        views,
        spec=spec,
        reference_bounds=_captured_reference_bounds(views),
        settled_checks=[],
    )
    assert views["free_top"].kept_positions["SupplierID"] == pytest.approx(
        (0.12 - radius * 1.5 - 0.018, 0.21)
    )
    assert views["free_top"].kept_positions["SupplierOD"] == pytest.approx(
        (0.12 + radius * 1.5 + 0.018, 0.21)
    )
    front_mid_y = 0.10 + (low + high) / 1000
    assert views["free_front"].kept_positions["SupplierThickness"] == pytest.approx(
        (0.08 - radius * 2 - 0.018, front_mid_y)
    )
    assert views["free_front"].kept_positions["SupplierFreeHeight"] == pytest.approx(
        (0.08 + radius * 2 + 0.018, front_mid_y)
    )
    if "SHAFT_DIA" in spec.SUPPLIER_APPLICATION_DIMENSIONS:
        assert views["free_top"].kept_positions["SupplierShaftDia"] == pytest.approx(
            (0.12, 0.21 + radius * 1.5 + 0.010)
        )
    if "free_right" in views:
        right_mid_y = 0.08 + (baseline + gauge_upper) / 4000
        assert views["free_right"].kept_positions[
            "SupplierWorkingHeight"
        ] == pytest.approx((0.31 - radius * 0.5 - 0.014, right_mid_y))
        if "WORKING_DEFLECTION" in spec.SUPPLIER_APPLICATION_DIMENSIONS:
            assert views["free_right"].kept_positions[
                "SupplierWorkingDeflection"
            ] == pytest.approx((0.31 + radius * 0.5 + 0.014, right_mid_y))


@pytest.mark.parametrize(
    "spec,source_spans_mm",
    [
        (
            cylinder,
            {
                "free_front": (12.7, 1.27),
                "free_top": (12.7, 12.7),
            },
        ),
        (rocker, {"free_front": (9.3218, 0.762), "free_top": (9.3218, 9.3218)}),
        (
            pivot,
            {
                "free_front": (10.7442, 1.1938),
                "free_top": (10.7442, 10.7442),
                "free_right": (10.7442, 0.6858),
            },
        ),
    ],
    ids=["9714K392", "9714K24", "9715K43"],
)
@pytest.mark.parametrize(
    "source_error_m,rejected",
    [
        (-0.001, True),
        (-2e-7, True),
        (-5e-8, False),
        (0.0, False),
        (5e-8, False),
        (2e-7, True),
        (0.001, True),
    ],
)
def test_disc_prefit_guard_checks_native_ink_against_independent_nominal_geometry(
    monkeypatch,
    spec,
    source_spans_mm,
    source_error_m,
    rejected,
):
    views = _disc_views(spec)
    for key, (width, height) in source_spans_mm.items():
        error = source_error_m if key == "free_front" else 0.0
        views[key].source_points = ((0.0, 0.0), (width / 1000 + error, height / 1000))
    _readback_environment(monkeypatch, disc, views)
    monkeypatch.setattr(
        disc,
        "_show_hidden_owners",
        lambda adapter, view, owners, **kwargs: list(owners),
    )
    checks = disc.prepare_supplier_disc_diagram(
        object(),
        views,
        spec=spec,
        reference_bounds=_captured_reference_bounds(views),
    )
    if rejected:
        with pytest.raises(RuntimeError, match="native diagram ink"):
            for check in checks:
                check()
    else:
        for check in checks:
            check()


def test_disc_preparation_defers_capture_then_reuses_it_for_fitted_annotations(
    monkeypatch,
):
    views = _disc_views(cylinder)
    for key, span in {
        "free_front": (0.0127, 0.00127),
        "free_top": (0.0127, 0.0127),
    }.items():
        views[key].source_points = ((0.0, 0.0), span)
    _readback_environment(monkeypatch, disc, views)
    shown = []

    def show_owners(adapter, view, owners, **kwargs):
        shown.extend(owners)
        return list(owners)

    monkeypatch.setattr(disc, "_show_hidden_owners", show_owners)
    captured_bounds = None
    bounds_reads = []

    def reference_bounds(key):
        assert captured_bounds is not None, (
            "preparation must not project before capture"
        )
        bounds_reads.append(key)
        return captured_bounds(key)

    checks = disc.prepare_supplier_disc_diagram(
        object(),
        views,
        spec=cylinder,
        reference_bounds=reference_bounds,
    )
    assert shown
    assert not bounds_reads
    captured_bounds = _captured_reference_bounds(views)
    for check in checks:
        check()
    # The fixture snapshot no longer reads live source coordinates. Fit changes
    # only the view transform, which the same callback projects at each read.
    views["free_front"].source_points = ((500.0, 500.0), (1000.0, 1000.0))
    views["free_front"].Position = (0.20, 0.15)
    views["free_front"].ScaleRatio = (2, 1)
    disc.supplier_disc_spring_dimensions(
        object(),
        views,
        spec=cylinder,
        reference_bounds=reference_bounds,
        settled_checks=[],
    )
    assert views["free_front"].kept_positions["SupplierThickness"] == pytest.approx(
        (0.182, 0.15127)
    )
    assert views["free_front"].kept_positions["SupplierFreeHeight"] == pytest.approx(
        (0.2434, 0.15127)
    )


@pytest.mark.parametrize("spec", [channel, counter], ids=["9432K31", "1330K524"])
def test_extension_preparation_only_shows_owners_before_capture(monkeypatch, spec):
    views = _extension_views(spec)
    shown = {}

    def show_owners(adapter, view, owners, *, view_label):
        shown[view_label] = tuple(owners)
        return list(owners)

    def unavailable_bounds(key):
        raise AssertionError("preparation must not project before capture")

    monkeypatch.setattr(layout, "_show_hidden_owners", show_owners)
    assert (
        layout.prepare_extension_spring_diagrams(
            object(),
            views,
            reference_bounds=unavailable_bounds,
        )
        == ()
    )
    assert shown == {
        "free_front": ("SupplierFreeLengthReference",),
        "free_right": ("SupplierNominalSections",),
        "max_front": ("SupplierMaximumLengthReference",),
    }
