"""Native supplier source references, never changes to the purchased ring solid.

A separately labelled grooved-shaft section carries the supplier's three FOR
sizes. Its axial envelope is schematic only; its shaft diameter, groove-root
diameter and groove width are exact supplier dimensions. Only the three driven
measurement dimensions are marked for drawing import. The hidden Right-plane
sketch is independent of the subsequent rigid transform of the real ring body.

The physical thickness carrier is converted from the normalized ring's actual
edge in the stock builder's before-save hook, after its rigid body transform.
"""

from __future__ import annotations

from functools import wraps
import math
from typing import Any

from solidworks_mcp.adapters.sw_type_info import constant

from _check import check
from _com import _early_bound
from _dimensions import _feature_display_dimensions
from _drawing_precision import _named_dimension
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _feature_tree import name_last_feature
from _preferences import PreferenceSpec, preference_override
from _sketch import add_line_chain, blank_reference_sketches, ensure_fully_defined
from _sketch_chains import define_rectilinear_chain
from _supplier_dimensions import supplier_reference_dimension
from diagnostics.diag_build_97431A260 import build_97431A260 as _build_source
import vn_transgear_retaining_ring_spec as ring

# Complete native hidden-sketch inventory, consumed by authoring and routing.
REFERENCE_SKETCHES = ("SupplierThicknessReference", "SupplierApplicationGauges")
THICKNESS_SKETCH = REFERENCE_SKETCHES[0]
APPLICATION_SKETCH = REFERENCE_SKETCHES[1]
THICKNESS_DIMENSION = "SupplierThickness"


def application_profile() -> list[tuple[float, float]]:
    """Closed schematic shaft section; all three FOR measurements are geometric."""
    u = ring.SUPPLIER_GAUGE_CENTER_U
    half_length = ring.SUPPLIER_GAUGE_AXIAL_SPAN / 2.0
    half_width = ring.GROOVE_WIDTH / 2.0
    shaft_r = ring.SHAFT_DIA / 2.0
    groove_r = ring.GROOVE_DIA / 2.0
    return [
        (u - half_length, shaft_r),
        (u - half_width, shaft_r),
        (u - half_width, groove_r),
        (u + half_width, groove_r),
        (u + half_width, shaft_r),
        (u + half_length, shaft_r),
        (u + half_length, -shaft_r),
        (u + half_width, -shaft_r),
        (u + half_width, -groove_r),
        (u - half_width, -groove_r),
        (u - half_width, -shaft_r),
        (u - half_length, -shaft_r),
    ]


def _select_lines(adapter: Any, lines: list[str], indices: tuple[int, int]) -> None:
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    data = _early_bound(model.SelectionManager, "ISelectionMgr").CreateSelectData()
    if data is None:
        raise RuntimeError("97431A260: no application gauge selection data")
    for position, index in enumerate(indices):
        line = _early_bound(adapter._sketch_entities[lines[index]], "ISketchSegment")
        if not line.Select4(position > 0, data):
            raise RuntimeError("97431A260: application gauge contour selection failed")


def _driven(raw: Any, name: str, expected_mm: float) -> None:
    if raw is None:
        raise RuntimeError(
            f"97431A260 {name}: native application gauge dimension failed"
        )
    display = _early_bound(raw, "IDisplayDimension")
    if int(display.Type2) not in (2, 11, 12):
        raise RuntimeError(
            f"97431A260 {name}: application gauge is not a linear measurement"
        )
    native = _early_bound(display.GetDimension2(0), "IDimension")
    native.DrivenState = 1
    native.Name = name
    if (
        int(native.DrivenState) != 1
        or str(native.Name) != name
        or not math.isclose(
            float(native.SystemValue) * 1000.0, expected_mm, rel_tol=0.0, abs_tol=1e-6
        )
    ):
        raise RuntimeError(
            f"97431A260 {name}: exact driven application gauge value changed"
        )


def _thickness_model_edge(model: Any) -> Any:
    """Find an actual normalized +Z edge spanning only the purchased ring."""
    candidates = []
    for raw_body in _early_bound(model, "IPartDoc").GetBodies2(0, False) or ():
        for raw_edge in _early_bound(raw_body, "IBody2").GetEdges() or ():
            edge = _early_bound(raw_edge, "IEdge")
            raw_curve = edge.GetCurve()
            if raw_curve is None or not _early_bound(raw_curve, "ICurve").IsLine():
                continue
            vertices = (edge.GetStartVertex(), edge.GetEndVertex())
            if any(vertex is None for vertex in vertices):
                continue
            a, b = (
                tuple(
                    float(value) * 1000.0
                    for value in _early_bound(vertex, "IVertex").GetPoint()
                )
                for vertex in vertices
            )
            if (
                abs(a[0] - b[0]) < 1e-6
                and abs(a[1] - b[1]) < 1e-6
                and abs(min(a[2], b[2])) < 1e-6
                and abs(max(a[2], b[2]) - ring.THICKNESS) < 1e-6
            ):
                candidates.append(((a[1] + b[1]) / 2.0, raw_edge))
    if not candidates:
        raise RuntimeError(
            "97431A260: no normalized solid edge spans the actual ring thickness"
        )
    return max(candidates, key=lambda item: item[0])[1]


async def author_thickness_reference(adapter: Any) -> None:
    """Convert the actual final ring edge and own its supplier band in the part."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    edge = _thickness_model_edge(model)
    check("create native ring thickness carrier", await adapter.create_sketch("Top"))
    model.ClearSelection2(True)
    data = _early_bound(model.SelectionManager, "ISelectionMgr").CreateSelectData()
    if data is None or not _early_bound(edge, "IEntity").Select4(False, data):
        raise RuntimeError("97431A260: actual thickness edge selection failed")
    if not _early_bound(adapter.currentSketchManager, "ISketchManager").SketchUseEdge3(
        False, False
    ):
        raise RuntimeError("97431A260: actual thickness edge conversion failed")
    model.ClearSelection2(True)
    sketch = _early_bound(model.GetActiveSketch2(), "ISketch")
    segments = tuple(sketch.GetSketchSegments() or ())
    if (
        len(segments) != 1
        or int(_early_bound(segments[0], "ISketchSegment").GetType()) != 0
    ):
        raise RuntimeError(
            "97431A260: thickness carrier is not one converted native line"
        )
    if not _early_bound(segments[0], "ISketchSegment").Select4(False, data):
        raise RuntimeError("97431A260: converted thickness line selection failed")
    app = _early_bound(adapter.swApp, "ISldWorks")
    app.SetUserPreferenceToggle(10, False)
    if app.GetUserPreferenceToggle(10):
        raise RuntimeError(
            "97431A260: thickness measurement value input remains enabled"
        )
    toggles = {
        constant("swSketchOverdefiningDimsPromptToSetState"): False,
        constant("swSketchOverdefiningDimsSetDrivenByDefault"): True,
    }
    preferences = PreferenceSpec(
        label="97431A260-driven-thickness-reference",
        toggles=toggles,
        baseline_toggles=dict.fromkeys(toggles, False),
    )
    with preference_override(adapter, preferences):
        if any(
            bool(app.GetUserPreferenceToggle(key)) != wanted
            for key, wanted in toggles.items()
        ):
            raise RuntimeError(
                "97431A260: native thickness creation preferences were refused"
            )
        _driven(
            model.AddDimension2(0.006, 0.003, 0.0), THICKNESS_DIMENSION, ring.THICKNESS
        )
    model.ClearSelection2(True)
    check("exit native ring thickness carrier", await adapter.exit_sketch())
    name_last_feature(adapter, THICKNESS_SKETCH)
    display, _native = _named_dimension(adapter, THICKNESS_SKETCH, THICKNESS_DIMENSION)
    display.MarkedForDrawing = True
    if not bool(display.MarkedForDrawing):
        raise RuntimeError(
            "97431A260: source thickness reference was not marked for import"
        )
    set_dimension_symmetric_tolerance(
        adapter,
        THICKNESS_SKETCH,
        THICKNESS_DIMENSION,
        ring.THICKNESS_TOL,
    )
    supplier_reference_dimension(
        adapter,
        display,
        label="97431A260 ring thickness",
        units="in",
        precision=ring.SUPPLIER_REFERENCE_PRECISION,
        expected_mm=ring.THICKNESS,
    )
    places = ring.SUPPLIER_REFERENCE_PRECISION
    if int(display.SetPrecision3(places, places, places, places)) != 0:
        raise RuntimeError(
            "97431A260: source thickness precision settings were rejected"
        )
    tolerance = _early_bound(_native.Tolerance, "IDimensionTolerance")
    band = ring.THICKNESS_TOL / 1000.0
    if (
        int(tolerance.Type) != 4
        or abs(float(tolerance.GetMinValue()) + band) > 1e-12
        or abs(float(tolerance.GetMaxValue()) - band) > 1e-12
        or int(display.GetPrimaryPrecision2()) != ring.SUPPLIER_REFERENCE_PRECISION
        or int(display.GetPrimaryTolPrecision2()) != ring.SUPPLIER_REFERENCE_PRECISION
    ):
        raise RuntimeError("97431A260: model-owned thickness tolerance did not persist")
    blank_reference_sketches(adapter, (THICKNESS_SKETCH,))


async def author_application_gauges(adapter: Any) -> None:
    check("create supplier application gauges", await adapter.create_sketch("Right"))
    points = application_profile()
    lines = await add_line_chain(adapter, points, close=True)
    await define_rectilinear_chain(
        adapter, lines, points, label="supplier application gauge section"
    )
    await ensure_fully_defined(adapter, "supplier application gauge section")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    app = _early_bound(adapter.swApp, "ISldWorks")
    app.SetUserPreferenceToggle(10, False)  # swInputDimValOnCreate
    if app.GetUserPreferenceToggle(10):
        raise RuntimeError(
            "97431A260: application gauge dimension input remains enabled"
        )
    toggles = {
        constant("swSketchOverdefiningDimsPromptToSetState"): False,
        constant("swSketchOverdefiningDimsSetDrivenByDefault"): True,
    }
    preferences = PreferenceSpec(
        label="97431A260-driven-application-gauges",
        toggles=toggles,
        baseline_toggles=dict.fromkeys(toggles, False),
    )
    with preference_override(adapter, preferences):
        if any(
            bool(app.GetUserPreferenceToggle(key)) != wanted
            for key, wanted in toggles.items()
        ):
            raise RuntimeError(
                "97431A260: driven application gauge creation preferences were refused"
            )
        for name, indices, expected, horizontal in (
            ("ApplicationShaftOD", (0, 10), ring.SHAFT_DIA, False),
            ("ApplicationGrooveDiameter", (2, 8), ring.GROOVE_DIA, False),
            ("ApplicationGrooveWidth", (1, 3), ring.GROOVE_WIDTH, True),
        ):
            _select_lines(adapter, lines, indices)
            create = (
                model.AddHorizontalDimension2
                if horizontal
                else model.AddVerticalDimension2
            )
            _driven(
                create(ring.SUPPLIER_GAUGE_CENTER_U / 1000.0, -0.004, 0.0),
                name,
                expected,
            )
    model.ClearSelection2(True)
    check("exit supplier application gauges", await adapter.exit_sketch())
    name_last_feature(adapter, APPLICATION_SKETCH)
    feature = _early_bound(model, "IPartDoc").FeatureByName(APPLICATION_SKETCH)
    if feature is None:
        raise RuntimeError("97431A260: named application gauge sketch is missing")
    required = set(ring.SUPPLIER_APPLICATION_DIMENSIONS[APPLICATION_SKETCH])
    for raw in _feature_display_dimensions(feature):
        display = _early_bound(raw, "IDisplayDimension")
        name = str(_early_bound(display.GetDimension2(0), "IDimension").Name)
        display.MarkedForDrawing = name in required
        if bool(display.MarkedForDrawing) != (name in required):
            raise RuntimeError("97431A260: application gauge import marking changed")
    for name, band in (
        ("ApplicationGrooveDiameter", ring.GROOVE_DIA_BAND),
        ("ApplicationGrooveWidth", ring.GROOVE_WIDTH_BAND),
    ):
        set_dimension_bilateral_tolerance(
            adapter,
            APPLICATION_SKETCH,
            name,
            -band[1],
            band[0],
        )
    for name, expected, presentation in (
        ("ApplicationShaftOD", ring.SHAFT_DIA, "diameter"),
        ("ApplicationGrooveDiameter", ring.GROOVE_DIA, "diameter"),
        ("ApplicationGrooveWidth", ring.GROOVE_WIDTH, "length"),
    ):
        display, _native = _named_dimension(adapter, APPLICATION_SKETCH, name)
        supplier_reference_dimension(
            adapter,
            display,
            label=f"97431A260 {name}",
            units="in",
            precision=ring.SUPPLIER_SUITABILITY_PRECISION,
            expected_mm=expected,
            presentation=presentation,
        )
        display.SetPrecision3(-1, -1, ring.SUPPLIER_SUITABILITY_PRECISION, -1)
        if (
            int(display.GetPrimaryTolPrecision2())
            != ring.SUPPLIER_SUITABILITY_PRECISION
        ):
            raise RuntimeError(
                f"97431A260 {name}: source supplier tolerance places changed"
            )
    blank_reference_sketches(adapter, (APPLICATION_SKETCH,))


@wraps(_build_source)
async def build_97431A260(adapter: Any, truth: Any = None) -> None:
    await _build_source(adapter, truth)
    await author_application_gauges(adapter)
