"""Offline configured-reference and final annotation readback contracts; no native run."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import math
from types import SimpleNamespace

import pytest

import _drawing_leaders as leaders
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
from test_supplier_spring_layout_drawing import (
    _ReferenceInkView,
    _sibling_view,
    reference_scene as reference_scene,
)


class _View:
    def __init__(self, name, configuration):
        self.name = name
        self.ReferencedConfiguration = configuration
        self.annotations = []
        self.source_points = ((0.0, 0.0), (0.1, 0.02))
        self.Position = (0.1, 0.1)
        self.ScaleRatio = (1, 1)
        self.kept_positions = {}
        self.text_positions = {}

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
        GetDimension2=lambda index: native, GetPrimaryTolPrecision2=lambda: 3,
        OffsetText=False,
    )
    annotation = SimpleNamespace(
        name=name,
        GetType=lambda: 4,
        GetSpecificAnnotation=lambda: display,
        position=(0.0, 0.0, 0.0),
    )

    def set_position(x, y, z):
        annotation.position = (x, y, z)
        return True

    annotation.SetPosition2 = set_position
    annotation.GetPosition = lambda: annotation.position
    display.GetAnnotation = lambda: annotation
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
    if module is disc:
        def near_side(annotation, label):
            # Command fake only: the recorded native paths below are the
            # independent failure fixtures, not outputs of this setter.
            display = annotation.GetSpecificAnnotation()
            display.Diametric = True
            display.ArrowSide = 1
            display.SolidLeader = False
            display.GetUseDocBrokenLeader = lambda: False
            display.GetBrokenLeader2 = lambda: 2
            display.GetUseDocSecondArrow = lambda: False
            display.GetSecondArrow = lambda: False

        def diameter_segments(annotation):
            # Idealized separated near-rim rays keep unrelated source/value
            # tests independent of COM graphics. Never native after-fix proof.
            view = views["free_top"]
            x0, y0, x1, y1 = _captured_reference_bounds(views)("free_top")
            od = next(item for item in view.annotations if item.name == "SupplierOD")
            value = annotation.GetSpecificAnnotation().GetDimension2(0).value
            outside = od.GetSpecificAnnotation().GetDimension2(0).value
            radius = (x1 - x0) * value / (2 * outside)
            angle = {
                "SupplierID": 135, "SupplierOD": -45, "SupplierShaftDia": 60
            }[annotation.name]
            ux, uy = math.cos(math.radians(angle)), math.sin(math.radians(angle))
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            return [
                ((cx + radius * ux, cy + radius * uy),
                 (cx + 2 * radius * ux, cy + 2 * radius * uy))
            ]

        monkeypatch.setattr(module, "set_near_side_diameter", near_side)
        monkeypatch.setattr(module, "dimension_segments", diameter_segments)
        monkeypatch.setattr(module, "rebuild_drawing", lambda *args, **kwargs: None)

        def offset_text(adapter, annotations, positions):
            remaining = dict(positions)
            for view in views.values():
                for annotation in view.annotations:
                    if annotation in annotations and annotation.name in remaining:
                        xy = remaining.pop(annotation.name)
                        annotation.GetSpecificAnnotation().OffsetText = True
                        annotation.position = (*xy, 0.0)
                        view.text_positions[annotation.name] = xy
            if remaining:
                raise RuntimeError(f"dimension text not offset: {sorted(remaining)}")

        monkeypatch.setattr(module, "offset_dimension_text", offset_text)


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


@pytest.mark.parametrize("spec,count", [(cylinder, 6), (rocker, 4), (pivot, 6)])
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
    "spec,name,key",
    [
        (cylinder, "SupplierWorkingHeight", "free_right"),
        (cylinder, "SupplierWorkingDeflection", "free_right"),
        (pivot, "SupplierWorkingHeight", "free_right"),
        (cylinder, "SupplierThickness", "free_front"),
        (cylinder, "SupplierFreeHeight", "free_front"),
        (pivot, "SupplierThickness", "free_front"),
        (pivot, "SupplierFreeHeight", "free_front"),
        (rocker, "SupplierThickness", "free_front"),
        (rocker, "SupplierFreeHeight", "free_front"),
    ],
)
@pytest.mark.parametrize("corruption", ["offset", "position", "nonfinite", "missing"])
def test_disc_final_check_refuses_text_leaving_its_offset_shelf(
    monkeypatch, spec, name, key, corruption
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
    for check in checks:
        check()
    annotation = next(item for item in views[key].annotations if item.name == name)
    if corruption == "offset":
        annotation.GetSpecificAnnotation().OffsetText = False
    elif corruption == "position":
        annotation.position = (
            annotation.position[0], annotation.position[1] + 0.003, annotation.position[2]
        )
    elif corruption == "nonfinite":
        annotation.position = (math.nan, *annotation.position[1:])
    else:
        annotation.position = ()
    with pytest.raises(RuntimeError, match="(application|nominal) text (lost|moved)"):
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
                "WORKING_HEIGHT": 0.024,
                "WORKING_DEFLECTION": 0.026,
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
        (0.12 - radius * 1.5 - 0.026, 0.21 + radius * 1.5 - 0.004)
    )
    assert views["free_top"].kept_positions["SupplierOD"] == pytest.approx(
        (0.12 + radius * 1.5 + 0.026, 0.21 - radius * 1.5 + 0.004)
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
            (0.14, 0.21 + radius * 1.5 + 0.010)
        )
    if "free_right" in views:
        right_mid_y = 0.08 + (baseline + gauge_upper) / 4000
        assert views["free_right"].kept_positions[
            "SupplierWorkingHeight"
        ] == pytest.approx((0.31 - radius * 0.5 - 0.014, right_mid_y))
        assert views["free_right"].text_positions["SupplierWorkingHeight"] == pytest.approx(
            (0.31, 0.08 + baseline / 2000 - 0.014)
        )
        if "WORKING_DEFLECTION" in spec.SUPPLIER_APPLICATION_DIMENSIONS:
            assert views["free_right"].kept_positions[
                "SupplierWorkingDeflection"
            ] == pytest.approx((0.31 + radius * 0.5 + 0.014, right_mid_y))
            assert views["free_right"].text_positions[
                "SupplierWorkingDeflection"
            ] == pytest.approx((0.31, 0.08 + gauge_upper / 2000 + 0.014))
    assert views["free_front"].text_positions["SupplierThickness"] == pytest.approx(
        (0.08, 0.10 + low / 500 - 0.014)
    )
    assert views["free_front"].text_positions["SupplierFreeHeight"] == pytest.approx(
        (0.08, 0.10 + high / 500 + 0.014)
    )
    assert all(
        annotation.GetSpecificAnnotation().OffsetText
        for annotation in views["free_front"].annotations
    )
    assert not views["free_top"].text_positions
    assert all(
        not annotation.GetSpecificAnnotation().OffsetText
        for annotation in views["free_top"].annotations
    )


@pytest.mark.parametrize(
    "spec,name",
    [
        (cylinder, "SupplierID"),
        (rocker, "SupplierOD"),
        (pivot, "SupplierShaftDia"),
    ],
)
@pytest.mark.parametrize(
    "member,value",
    [
        ("Diametric", False),
        ("ArrowSide", 0),
        ("SolidLeader", True),
        ("GetUseDocBrokenLeader", True),
        ("GetBrokenLeader2", 1),
        ("GetUseDocSecondArrow", True),
        ("GetSecondArrow", True),
    ],
)
def test_disc_final_check_refuses_reverted_native_diameter_style(
    monkeypatch, spec, name, member, value
):
    views = _disc_views(spec)
    _readback_environment(monkeypatch, disc, views)
    checks = []
    disc.supplier_disc_spring_dimensions(
        object(), views, spec=spec,
        reference_bounds=_captured_reference_bounds(views), settled_checks=checks,
    )
    for check in checks:
        check()
    annotation = next(item for item in views["free_top"].annotations if item.name == name)
    setattr(
        annotation.GetSpecificAnnotation(), member,
        (lambda: value) if member.startswith("Get") else value,
    )
    with pytest.raises(RuntimeError, match="near-side diameter style changed"):
        for check in checks:
            check()


@pytest.mark.parametrize(
    "spec,name",
    [
        (cylinder, "SupplierID"),
        (cylinder, "SupplierOD"),
        (rocker, "SupplierID"),
        (pivot, "SupplierShaftDia"),
    ],
)
@pytest.mark.parametrize("corruption", ["position", "nonfinite", "missing", "short"])
def test_disc_final_check_refuses_diameter_text_leaving_its_settled_target(
    monkeypatch, spec, name, corruption
):
    views = _disc_views(spec)
    _readback_environment(monkeypatch, disc, views)
    checks = []
    disc.supplier_disc_spring_dimensions(
        object(), views, spec=spec,
        reference_bounds=_captured_reference_bounds(views), settled_checks=checks,
    )
    for check in checks:
        check()
    annotation = next(item for item in views["free_top"].annotations if item.name == name)
    if corruption == "position":
        x, y, z = annotation.position
        annotation.position = (x, y + 0.003, z)
    elif corruption == "nonfinite":
        annotation.position = (math.inf, *annotation.position[1:])
    elif corruption == "missing":
        annotation.position = ()
    else:
        annotation.position = annotation.position[:2]
    with pytest.raises(RuntimeError, match="diameter text moved from its target"):
        for check in checks:
            check()


@pytest.mark.parametrize("drift_m,rejected", [(5e-7, False), (2e-6, True)])
def test_diameter_position_readback_keeps_existing_one_micron_convention(
    monkeypatch, drift_m, rejected
):
    views = _disc_views(rocker)
    _readback_environment(monkeypatch, disc, views)
    checks = []
    disc.supplier_disc_spring_dimensions(
        object(), views, spec=rocker,
        reference_bounds=_captured_reference_bounds(views), settled_checks=checks,
    )
    annotation = next(
        item for item in views["free_top"].annotations if item.name == "SupplierID"
    )
    x, y, z = annotation.position
    annotation.position = (x + drift_m, y, z)
    if rejected:
        with pytest.raises(RuntimeError, match="diameter text moved from its target"):
            for check in checks:
                check()
    else:
        for check in checks:
            check()


def test_disc_reuses_documented_native_near_side_diameter_presentation():
    assert disc.set_near_side_diameter is leaders.set_near_side_diameter


# Exact-source 78aa9ab6, native run
# 20261022T183845810Z-2dce64ede16d43a3b28349706195a7cc.out:
# reports/layout-audit/{dt-vn-cylinder-bank-spring,pd-vn-transgear-pivot-spring}.json
# supplies the annotation positions, display lines and actual PDF glyph boxes.
# Gray source rails are from those actual PDFs' PyMuPDF vector paths, not
# _pdf_ink's deliberately black-only stroke list. Coordinates below are sheet
# metres, rounded to the native report's 0.1 um resolution. The fixture's old
# paths/boxes are native evidence; translated boxes and setter fakes are ONLY
# candidate-placement controls, never native after-fix proof.
_RECORDED_DISC_NOMINAL = (
    {
        "spec": cylinder,
        "bounds": {
            "free_front": (0.1188, 0.13223, 0.1442, 0.13477),
            "free_top": (0.1188, 0.2143, 0.1442, 0.2397),
        },
        "front": {
            "SupplierThickness": {
                "pos": (0.1008, 0.1335),
                "box": (0.0913316, 0.1307691, 0.1102684, 0.1352865),
                "striking": (
                    ((0.1305, 0.133373), (0.0998, 0.133373)),
                    ((0.1008, 0.133373), (0.1008, 0.127023)),
                ),
            },
            "SupplierFreeHeight": {
                "pos": (0.1622, 0.1335),
                "box": (0.1527316, 0.1307691, 0.1716684, 0.1352865),
                "striking": (
                    ((0.1198, 0.13223), (0.1632, 0.13223)),
                    ((0.1622, 0.13223), (0.1622, 0.12588)),
                ),
            },
        },
        "rails": (
            ((0.1188, 0.13223), (0.1442, 0.13223)),
            ((0.1188, 0.13477), (0.1442, 0.13477)),
            ((0.1315, 0.133373), (0.134421, 0.133373)),
            ((0.1315, 0.133627), (0.134421, 0.133627)),
        ),
        "diameters": {
            "SupplierID": (
                ((0.1223622, 0.2235173), (0.1241406, 0.2241951)),
                ((0.1406378, 0.2304827), (0.1223622, 0.2235173)),
            ),
            "SupplierOD": (
                ((0.1433673, 0.2224771), (0.1388594, 0.2241951)),
                ((0.1196327, 0.2315229), (0.1433673, 0.2224771)),
            ),
        },
        "plan_text": {
            "SupplierID": (
                (0.1008, 0.227),
                (0.0809457, 0.2242958, 0.1206536, 0.2288132),
            ),
            "SupplierOD": (
                (0.1622, 0.227),
                (0.1423457, 0.2242958, 0.1820536, 0.2288132),
            ),
        },
    },
    {
        "spec": pivot,
        "bounds": {
            "free_front": (0.1207558, 0.1300562, 0.1422442, 0.1324438),
            "free_top": (0.1207558, 0.2072558, 0.1422442, 0.2287442),
        },
        "front": {
            "SupplierThickness": {
                "pos": (0.1027558, 0.13125),
                "box": (0.0932874, 0.1285191, 0.1122242, 0.1330365),
                "striking": (
                    ((0.1305, 0.130963), (0.1017558, 0.130963)),
                    ((0.1027558, 0.130963), (0.1027558, 0.124613)),
                ),
            },
            "SupplierFreeHeight": {
                "pos": (0.1602442, 0.13125),
                "box": (0.1507758, 0.1285191, 0.1697126, 0.1330365),
                "striking": (
                    ((0.1217558, 0.1300562), (0.1612442, 0.1300562)),
                    ((0.1602442, 0.1300562), (0.1602442, 0.1237062)),
                ),
            },
        },
        "rails": (
            ((0.1207558, 0.1300562), (0.1422442, 0.1300562)),
            ((0.1207558, 0.1324438), (0.1422442, 0.1324438)),
            ((0.1315, 0.130963), (0.1371642, 0.130963)),
            ((0.1315, 0.131537), (0.1371642, 0.131537)),
        ),
        "diameters": {
            "SupplierID": (
                ((0.1264988, 0.2171086), (0.1157641, 0.2151951)),
                ((0.1365012, 0.2188914), (0.1264988, 0.2171086)),
                ((0.1157641, 0.2151951), (0.091335, 0.2151951)),
            ),
            "SupplierOD": (
                ((0.1422442, 0.218), (0.1734305, 0.2113479)),
                ((0.1420078, 0.2157587), (0.1446498, 0.2151951)),
                ((0.1209922, 0.2202413), (0.1420078, 0.2157587)),
                ((0.1446498, 0.2151951), (0.1742511, 0.2151951)),
            ),
            "SupplierShaftDia": (
                ((0.1346979, 0.2216143), (0.1449146, 0.2331612)),
                ((0.1283021, 0.2143857), (0.1346979, 0.2216143)),
                ((0.1449146, 0.2331612), (0.1196729, 0.2331612)),
            ),
        },
        "plan_text": {
            "SupplierID": (
                (0.1027558, 0.218),
                (0.0932338, 0.2152958, 0.1122775, 0.2198132),
            ),
            "SupplierOD": (
                (0.1602442, 0.218),
                (0.1481361, 0.2152959, 0.1723518, 0.2198132),
            ),
            "SupplierShaftDia": (
                (0.1315, 0.2387442),
                (0.1200788, 0.2340951, 0.1432524, 0.2433355),
            ),
        },
    },
)


def _place_recorded_disc(monkeypatch, case):
    views = _disc_views(case["spec"])
    for key, (x0, y0, x1, y1) in case["bounds"].items():
        views[key].source_points = ((x0, y0), (x1, y1))
        views[key].Position = (0.0, 0.0)
    _readback_environment(monkeypatch, disc, views)
    checks = []
    disc.supplier_disc_spring_dimensions(
        object(), views, spec=case["spec"],
        reference_bounds=_captured_reference_bounds(views), settled_checks=checks,
    )
    return views, checks


def _translated_box(box, before, after):
    dx, dy = after[0] - before[0], after[1] - before[1]
    return box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy


@pytest.mark.parametrize("case", _RECORDED_DISC_NOMINAL, ids=["cylinder", "pivot"])
def test_recorded_nominal_front_strikes_need_text_shelves_not_moved_dimension_lines(
    monkeypatch, case
):
    views, _checks = _place_recorded_disc(monkeypatch, case)
    view = views["free_front"]
    for name, recorded in case["front"].items():
        assert all(
            leaders.distance_to_box(line, recorded["box"]) == 0.0
            for line in recorded["striking"]
        )
        assert view.kept_positions[name] == pytest.approx(recorded["pos"])
        candidate = _translated_box(
            recorded["box"], recorded["pos"], view.text_positions[name]
        )
        assert all(
            leaders.distance_to_box(line, candidate) > 0.002
            for line in (*recorded["striking"], *case["rails"])
        )
    assert view.text_positions["SupplierThickness"][1] < case["bounds"]["free_front"][1]
    assert view.text_positions["SupplierFreeHeight"][1] > case["bounds"]["free_front"][3]


@pytest.mark.parametrize("case", _RECORDED_DISC_NOMINAL, ids=["cylinder", "pivot"])
def test_recorded_diameter_crossings_refuse_even_if_native_style_flags_claim_success(
    monkeypatch, case
):
    _views, checks = _place_recorded_disc(monkeypatch, case)
    assert ("SupplierID", "SupplierOD") in leaders.leader_crossings(case["diameters"])
    monkeypatch.setattr(
        disc, "dimension_segments",
        lambda annotation: case["diameters"][annotation.name],
    )
    with pytest.raises(RuntimeError, match="leaders not clear.*crossings"):
        for check in checks:
            check()


def test_recorded_pivot_od_native_extension_really_strikes_its_own_pdf_glyphs():
    case = _RECORDED_DISC_NOMINAL[1]
    od_box = case["plan_text"]["SupplierOD"][1]
    assert leaders.distance_to_box(case["diameters"]["SupplierOD"][0], od_box) == 0.0


@pytest.mark.parametrize("case", _RECORDED_DISC_NOMINAL, ids=["cylinder", "pivot"])
def test_candidate_diameter_origins_clear_recorded_circles_without_cell_changes(
    monkeypatch, case
):
    views, _checks = _place_recorded_disc(monkeypatch, case)
    x0, y0, x1, y1 = case["bounds"]["free_top"]
    field = next(
        cell for key, _center, cell in layout.supplier_state_cells(0.077, maximum=False)
        if key == "free_top"
    )
    for name, (old_origin, glyphs) in case["plan_text"].items():
        candidate = _translated_box(
            glyphs, old_origin, views["free_top"].kept_positions[name]
        )
        left, bottom, right, top = candidate
        assert right < x0 or left > x1 or top < y0 or bottom > y1
        assert field[0] < left < right < field[2]
        assert field[1] < bottom < top < field[3]


@pytest.mark.parametrize(
    "relative_box",
    [
        (-0.02175, -0.0027042, 0.02175, 0.0018132),
        (-0.024, -0.005, 0.024, 0.005),
    ],
    ids=["recorded-single-row-offsets", "adversarial-stacked-band-envelope"],
)
def test_rocker_four_to_one_diameter_origins_fit_unchanged_top_cell(
    monkeypatch, relative_box
):
    """Placement control, not recorded rocker ink or native after-fix proof.

    The first envelope retains the recorded cylinder row's vertical offsets;
    the second deliberately models a 48 x 10 mm asymmetric stacked-band block.
    Neither substitutes for the rocker's final native whole-ink containment.
    """
    views = _disc_views(rocker)
    radius = rocker.OD / 2000.0
    view = views["free_top"]
    view.source_points = ((-radius, -radius), (radius, radius))
    view.Position = (0.1315, 0.227)
    view.ScaleRatio = (4, 1)
    reference_bounds = _captured_reference_bounds(views)
    _readback_environment(monkeypatch, disc, views)
    disc.supplier_disc_spring_dimensions(
        object(), views, spec=rocker,
        reference_bounds=reference_bounds, settled_checks=[],
    )
    field = next(
        cell for key, _center, cell in layout.supplier_state_cells(0.077, maximum=False)
        if key == "free_top"
    )
    assert field == (0.028, 0.207, 0.235, 0.247)
    assert 4 * rocker.OD / 1000.0 <= field[3] - field[1]
    assert 5 * rocker.OD / 1000.0 > field[3] - field[1]
    x0, y0, x1, y1 = reference_bounds("free_top")
    assert view.kept_positions["SupplierID"] == pytest.approx((0.0868564, 0.2416436))
    assert view.kept_positions["SupplierOD"] == pytest.approx((0.1761436, 0.2123564))
    for name in ("SupplierID", "SupplierOD"):
        left, bottom, right, top = _translated_box(
            relative_box, (0.0, 0.0), view.kept_positions[name]
        )
        assert field[0] < left < right < field[2]
        assert field[1] < bottom < top < field[3]
        assert right < x0 or left > x1 or top < y0 or bottom > y1
    # The reviewed +2 mm origin fails both envelopes at the unchanged ceiling.
    assert y1 + 0.002 + relative_box[3] > field[3]


@pytest.mark.parametrize("corruption", ["empty", "wrong_space", "centre_tail"])
def test_final_diameter_route_check_requires_actual_near_rim_sheet_space_ink(
    monkeypatch, corruption
):
    case = _RECORDED_DISC_NOMINAL[1]
    _views, checks = _place_recorded_disc(monkeypatch, case)
    for check in checks:
        check()
    original = disc.dimension_segments
    x0, y0, x1, y1 = case["bounds"]["free_top"]
    centre = ((x0 + x1) / 2, (y0 + y1) / 2)

    def corrupted(annotation):
        segments = original(annotation)
        if annotation.name != "SupplierID":
            return segments
        if corruption == "empty":
            return []
        if corruption == "wrong_space":
            return [
                ((a[0] + 1.0, a[1]), (b[0] + 1.0, b[1])) for a, b in segments
            ]
        return [*segments, (segments[0][0], centre)]

    monkeypatch.setattr(disc, "dimension_segments", corrupted)
    with pytest.raises(RuntimeError, match="leaders not clear"):
        for check in checks:
            check()


@pytest.mark.parametrize(
    "radial_error_m,rejected",
    [(-2e-7, True), (-5e-8, False), (5e-8, False), (2e-7, True)],
)
def test_diameter_landing_budget_is_not_widened_for_audit_json_rounding(
    monkeypatch, radial_error_m, rejected
):
    case = _RECORDED_DISC_NOMINAL[1]
    _views, checks = _place_recorded_disc(monkeypatch, case)
    original = disc.dimension_segments
    x0, y0, x1, y1 = case["bounds"]["free_top"]
    centre = ((x0 + x1) / 2, (y0 + y1) / 2)

    def shifted_landing(annotation):
        segments = original(annotation)
        if annotation.name != "SupplierID":
            return segments
        (ax, ay), end = segments[0]
        radius = math.dist((ax, ay), centre)
        factor = (radius + radial_error_m) / radius
        start = (
            centre[0] + (ax - centre[0]) * factor,
            centre[1] + (ay - centre[1]) * factor,
        )
        return [(start, end)]

    monkeypatch.setattr(disc, "dimension_segments", shifted_landing)
    if rejected:
        with pytest.raises(RuntimeError, match="leaders not clear"):
            for check in checks:
                check()
    else:
        for check in checks:
            check()


@pytest.mark.parametrize(
    "spec,source_spans_mm",
    [
        (
            cylinder,
            {
                "free_front": (12.7, 1.27),
                "free_top": (12.7, 12.7),
                "free_right": (12.7, 1.27),
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
        "free_right": (0.0127, 0.00127),
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


class _CaptionLoopReached(Exception):
    """Stop the real builder before unrelated footer/export work."""


@pytest.fixture
def caption_builder(monkeypatch, tmp_path, reference_scene):
    """Reuse the reference-capture scene; fake only native drawing boundaries."""
    source = tmp_path / "supplier.SLDPRT"
    source.write_bytes(b"offline supplier bytes")
    first = _ReferenceInkView(((0.002, 0.003), (0.015, 0.004)), name="front")
    installed = _sibling_view(first, "installed", "Installed")
    harness = reference_scene(views={"free_front": first, "installed_iso": installed})
    harness.model.path = source.resolve()
    for view in harness.views.values():
        view.referenced_path = source.resolve()
    harness.adapter.swApp.documents = {
        harness.model.GetTitle(): harness.model,
        harness.draw.GetTitle(): harness.draw,
    }
    harness.adapter._get_attr_or_call = lambda obj, name: getattr(obj, name)()
    sheet = SimpleNamespace(
        GetProperties2=lambda: (0, 0, 1.0, 1.0, False, 0.43, 0.28, False),
        SetProperties2=lambda *args: None,
    )
    notes, events = [], []
    options = {"owner": 1, "position_ok": True, "finish": False, "overflow": None}
    spec = SimpleNamespace(
        source=source, source_kind="part", artifact_stem="supplier", layout="test",
        outputs={"slddrw": source.with_suffix(".SLDDRW"),
                 "pdf": source.with_suffix(".pdf"), "png": source.with_suffix(".png")},
    )

    def open_readonly(adapter, path, *, label):
        assert path == source
        adapter.currentModel = harness.model
        return harness.model

    def drawing(adapter, *, layout):
        adapter.currentModel = harness.draw
        return harness.draw, sheet

    def place(adapter, path, orientation, x, y, *, scale):
        view = first if orientation == "*Front" else installed
        view.Position, view.ScaleRatio = (x, y), scale
        view.GetOrientationName = lambda: orientation
        return view

    def literal(adapter, text, x, y):
        is_installed = len(notes) == 1
        annotation = SimpleNamespace(
            OwnerType=options["owner"] if is_installed else 1,
            position=(x, y, 0.027 if is_installed else 0.0),
        )

        def position(px, py, pz):
            events.append(("SetPosition", text, (px, py, pz)))
            annotation.position = (px, py, pz)
            return True

        def position2(px, py, pz):
            events.append(("SetPosition2", text, (px, py, pz)))
            if options["position_ok"]:
                annotation.position = (px, py, pz)
            return options["position_ok"]

        def extent():
            events.append(("extent", text))
            px, py, pz = annotation.position
            # Installed ink deliberately does not start at its insertion point.
            dx, dy = (0.007, 0.0015) if is_installed else (0.0, 0.0)
            width = 0.500 if is_installed and options["overflow"] == "width" else 0.040
            height = 0.020 if is_installed and options["overflow"] == "height" else (
                0.006 if "\n" in text else 0.004
            )
            return (px + dx, py + dy - height, pz, px + dx + width, py + dy, pz)

        annotation.GetPosition = lambda: annotation.position
        annotation.SetPosition, annotation.SetPosition2 = position, position2
        note = SimpleNamespace(
            PropertyLinkedText=text, GetText=lambda: text,
            GetAnnotation=lambda: annotation, GetExtent=extent,
        )
        notes.append(note)
        return note

    def footer(*args, **kwargs):
        if not options["finish"]:
            raise _CaptionLoopReached
        return ()

    async def finalize(*args, **kwargs):
        raise _CaptionLoopReached

    monkeypatch.setattr(layout, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(layout, "_open_supplier_source_read_only", open_readonly)
    monkeypatch.setattr(layout, "read_required_properties", lambda *args, **kwargs: {
        "Material Specification": "Steel", "Finish": "None", "Manufacturing Notes": "",
        "Title": "Supplier", "Supplier": "Vendor", "Supplier SKUs": "SKU",
    })
    monkeypatch.setattr(layout, "check_item", lambda *args, **kwargs: None)
    monkeypatch.setattr(layout, "new_project_drawing", drawing)
    monkeypatch.setattr(layout, "_purchased_title_block", lambda *args, **kwargs: ())
    monkeypatch.setattr(layout, "stamp_drawing_summary", lambda *args, **kwargs: None)
    monkeypatch.setattr(layout, "place_view", place)
    monkeypatch.setattr(layout, "set_hidden_lines_removed", lambda *args: None)
    monkeypatch.setattr(layout, "double_array", tuple)
    monkeypatch.setattr(layout, "_fit_group", lambda *args, **kwargs: (1, 1))
    monkeypatch.setattr(layout, "_center_marks_without_lines", lambda *args: None)
    monkeypatch.setattr(layout, "assert_asme_b_sheet", lambda *args, **kwargs: None)
    monkeypatch.setattr(layout, "_literal_note", literal)
    monkeypatch.setattr(layout, "_rebuild", lambda draw, *, phase: events.append(("rebuild", phase)))
    monkeypatch.setattr(layout, "add_purchased_footer", footer)
    monkeypatch.setattr(layout, "iter_views", lambda adapter: tuple(harness.views.values()))
    monkeypatch.setitem(
        layout.DRAWING_TEMPLATES, "test", SimpleNamespace(width_m=0.43, height_m=0.28)
    )
    monkeypatch.setattr(layout, "sheet_drawable_region", lambda *args, **kwargs: (
        SimpleNamespace(xmin=0.015, ymin=0.015, xmax=0.416, ymax=0.265)
    ))
    monkeypatch.setattr(layout, "finalize_drawing", finalize)
    outline = (0.310, 0.150, 0.360, 0.180)

    def installed_outline():
        events.append(("outline",))
        return outline

    installed.GetOutline = installed_outline

    def run(**kwargs):
        return asyncio.run(layout.build_supplier_spring_drawing(
            harness.adapter, spec, item="1",
            supplier_dimensions=lambda *args, **kwargs: (),
            supplier_margins={"free_front": (0.0, 0.0, 0.0, 0.018)},
            supplier_reference_features={"free_front": ("SupplierSection",)},
            stock_configuration="SupplierReference", include_right=False, include_top=False,
            spring_metadata=True, **kwargs,
        ))

    return SimpleNamespace(
        run=run, notes=notes, events=events, options=options, outline=outline,
    )


@pytest.mark.parametrize("caption", ["INSTALLED ENVELOPE", "INSTALLED CONICAL\nREPRESENTATION"])
def test_installed_caption_gap_centers_measured_ink_below_outline_preserving_z(
    caption_builder, caption
):
    scene = caption_builder
    with pytest.raises(_CaptionLoopReached):
        scene.run(installed_caption=caption, installed_caption_gap=0.003)
    note = scene.notes[1]
    bounds = note.GetExtent()
    assert note.GetText() == note.PropertyLinkedText == f"{caption}  1:1"
    assert (bounds[0] + bounds[3]) / 2 == pytest.approx((0.267 + 0.406) / 2)
    assert bounds[4] == pytest.approx(scene.outline[1] - 0.003)
    assert note.GetAnnotation().GetPosition()[2] == 0.027
    assert [event[0] for event in scene.events if event[0].startswith("SetPosition")] == [
        "SetPosition", "SetPosition2",
    ]
    measured = scene.events.index(("rebuild", "measure installed state caption"))
    moved = next(i for i, event in enumerate(scene.events) if event[0] == "SetPosition2")
    rebuilt = scene.events.index(("rebuild", "position installed state caption"))
    assert measured < scene.events.index(("extent", f"{caption}  1:1")) < moved < rebuilt


@pytest.mark.parametrize(
    "option,value,message",
    [("owner", 2, "not sheet-owned"), ("position_ok", False, "cannot place measured caption")],
)
def test_installed_caption_gap_refuses_native_owner_or_position_failure(
    caption_builder, option, value, message
):
    caption_builder.options[option] = value
    with pytest.raises(RuntimeError, match=message):
        caption_builder.run(installed_caption_gap=0.003)
    assert ("rebuild", "position installed state caption") not in caption_builder.events
    if option == "owner":
        assert ("outline",) not in caption_builder.events


@pytest.mark.parametrize("overflow", [None, "width", "height"])
def test_installed_caption_gap_retains_strict_final_note_containment(
    caption_builder, overflow
):
    caption_builder.options.update(finish=True, overflow=overflow)
    if overflow is None:
        with pytest.raises(_CaptionLoopReached):
            caption_builder.run(installed_caption_gap=0.003)
    else:
        with pytest.raises(RuntimeError, match="sheet note readback/owner/border contract"):
            caption_builder.run(installed_caption_gap=0.003)


def test_installed_caption_default_none_retains_cell_floor_without_outline_or_rebuilds(
    caption_builder
):
    assert inspect.signature(layout.build_supplier_spring_drawing).parameters[
        "installed_caption_gap"
    ].default is None
    with pytest.raises(_CaptionLoopReached):
        caption_builder.run()
    # include_right=False substitutes the installed cell's lower boundary.
    floor = layout.view_band_bottom("", label="default caption") + 0.026
    position = caption_builder.notes[1].GetAnnotation().GetPosition()
    assert position == pytest.approx(((0.267 + 0.406) / 2 - 0.020, floor - 0.012, 0.0))
    assert ("outline",) not in caption_builder.events
    assert [event for event in caption_builder.events if event[0] == "rebuild"] == [
        ("rebuild", "supplier states before fitting"),
    ]
    assert not any(event[0] == "SetPosition2" for event in caption_builder.events)


@pytest.mark.parametrize("gap", [0.0, -0.003, math.inf, -math.inf, math.nan])
def test_installed_caption_gap_rejects_nonfinite_or_nonpositive_before_source_access(gap):
    # No source attribute exists: validation must precede even source-path access.
    with pytest.raises(ValueError, match="finite and positive"):
        asyncio.run(layout.build_supplier_spring_drawing(
            object(), SimpleNamespace(), item="1", supplier_dimensions=lambda *args: (),
            supplier_margins={}, supplier_reference_features={}, installed_caption_gap=gap,
        ))


@pytest.mark.parametrize(
    "module_name,caption",
    [
        ("draw_dt_vn_cylinder_bank_spring", "INSTALLED ENVELOPE"),
        ("draw_pd_vn_transgear_pivot_spring", "INSTALLED CONICAL REPRESENTATION"),
        ("draw_ch_vn_rocker_bank_spring", "INSTALLED ENVELOPE"),
    ],
)
def test_disc_recipe_build_forwards_measured_caption_gap_and_exact_text(
    monkeypatch, module_name, caption
):
    recipe = importlib.import_module(module_name)
    adapter, result = object(), {"offline": "captured"}
    calls = []

    async def capture(actual_adapter, spec, **kwargs):
        assert actual_adapter is adapter and spec is recipe.SPEC
        calls.append(kwargs)
        return result

    monkeypatch.setattr(recipe, "build_supplier_spring_drawing", capture)
    assert asyncio.run(recipe.build(adapter)) is result
    assert len(calls) == 1
    assert calls[0]["installed_caption_gap"] == 0.003
    assert calls[0]["installed_caption"] == caption
