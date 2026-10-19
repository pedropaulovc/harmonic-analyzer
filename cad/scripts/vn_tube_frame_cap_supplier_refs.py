"""Associative supplier measurements of 9275K141's unchanged native section.

Depth converts the actual CapSection roof and mouth segments. Bore converts
its actual straight-wall/flare circular edge, projected onto the Top plane.
Neither carrier adds stock, cuts material, nor substitutes rounded supplier
ink for the source's exact geometry. Both sketches are saved hidden.
"""

from __future__ import annotations

from functools import wraps
import math
from typing import Any

from solidworks_mcp.adapters.sw_type_info import constant

from _check import check
from _com import _early_bound
from _feature_tree import name_last_feature
from _preferences import PreferenceSpec, preference_override
from _sketch import blank_reference_sketches
from diagnostics.diag_build_9275K141 import build_9275K141 as _build_source
import vn_tube_frame_cap_spec as cap


def _segments(sketch: Any) -> tuple[Any, ...]:
    if sketch is None:
        raise RuntimeError("9275K141: no native sketch for supplier reference")
    return tuple(_early_bound(sketch, "ISketch").GetSketchSegments() or ())


def _line_ends(segment: Any) -> tuple[tuple[float, float, float], ...] | None:
    if int(_early_bound(segment, "ISketchSegment").GetType()) != 0:  # swSketchLINE
        return None
    line = _early_bound(segment, "ISketchLine")
    result = []
    for raw in (line.GetStartPoint2(), line.GetEndPoint2()):
        if raw is None:
            raise RuntimeError("9275K141: source section line has no endpoint")
        point = _early_bound(raw, "ISketchPoint")
        result.append(tuple(float(v) * 1000.0 for v in (point.X, point.Y, point.Z)))
    return tuple(result)


def _line_at(segments: tuple[Any, ...], start: tuple, end: tuple, *, label: str) -> Any:
    matches = []
    for segment in segments:
        actual = _line_ends(segment)
        if actual is None:
            continue
        if any(
            math.dist(actual[0], a) < 1e-6 and math.dist(actual[1], b) < 1e-6
            for a, b in ((start, end), (end, start))
        ):
            matches.append(segment)
    if len(matches) != 1:
        raise RuntimeError(f"9275K141 {label}: expected one exact source line, got {len(matches)}")
    return matches[0]


def _straight_bore_rim(model: Any) -> Any:
    """The real bore/flare junction, not the larger mouth or outer envelope."""
    matches = []
    for raw_body in _early_bound(model, "IPartDoc").GetBodies2(0, False) or ():
        for raw_edge in _early_bound(raw_body, "IBody2").GetEdges() or ():
            curve = _early_bound(raw_edge, "IEdge").GetCurve()
            if curve is None:
                continue
            curve = _early_bound(curve, "ICurve")
            if not curve.IsCircle():
                continue
            cx, cy, cz, nx, ny, nz, radius = map(float, curve.CircleParams)
            if (
                math.dist((cx * 1000.0, cy * 1000.0, cz * 1000.0), (0.0, cap.FLARE_HEIGHT, 0.0)) < 1e-6
                and abs(radius * 2000.0 - cap.INNER_DIAMETER) < 1e-6
                and abs(abs(ny) - 1.0) < 1e-8
                and abs(nx) < 1e-8 and abs(nz) < 1e-8
            ):
                matches.append(raw_edge)
    if len(matches) != 1:
        raise RuntimeError(f"9275K141: expected one straight bore rim, got {len(matches)}")
    return matches[0]


def _select(model: Any, entities: tuple[Any, ...], *, sketch: bool) -> None:
    model.ClearSelection2(True)
    manager = _early_bound(model.SelectionManager, "ISelectionMgr")
    data = manager.CreateSelectData()
    if data is None:
        raise RuntimeError("9275K141: no native supplier reference selection data")
    for index, entity in enumerate(entities):
        selectable = _early_bound(entity, "ISketchSegment" if sketch else "IEntity")
        if not selectable.Select4(index > 0, data):
            raise RuntimeError("9275K141: native supplier source entity was not selected")
    if int(manager.GetSelectedObjectCount2(-1)) != len(entities):
        raise RuntimeError("9275K141: native supplier source selection count changed")


def _reference(raw: Any, *, name: str, expected_mm: float, kinds: tuple[int, ...]) -> None:
    if raw is None:
        raise RuntimeError(f"9275K141 {name}: native reference dimension was not created")
    display = _early_bound(raw, "IDisplayDimension")
    if int(display.Type2) not in kinds:
        raise RuntimeError(f"9275K141 {name}: native reference has the wrong dimension type")
    raw_dimension = display.GetDimension2(0)
    if raw_dimension is None:
        raise RuntimeError(f"9275K141 {name}: no native source dimension")
    dimension = _early_bound(raw_dimension, "IDimension")
    dimension.DrivenState = 1  # swDimensionDriven, never drive the copied section
    dimension.Name = name
    display.MarkedForDrawing = True
    if (
        int(dimension.DrivenState) != 1
        or str(dimension.Name) != name
        or not display.MarkedForDrawing
        or not math.isclose(float(dimension.SystemValue) * 1000.0, expected_mm, rel_tol=0.0, abs_tol=1e-6)
    ):
        raise RuntimeError(f"9275K141 {name}: exact native source measurement did not persist")


async def author_supplier_references(adapter: Any) -> None:
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    raw_feature = _early_bound(model, "IPartDoc").FeatureByName("CapSection")
    if raw_feature is None:
        raise RuntimeError("9275K141: missing original CapSection")
    section = _early_bound(raw_feature, "IFeature").GetSpecificFeature2()
    source = _segments(section)
    roof_ends = ((0.0, cap.INSIDE_HEIGHT, 0.0), (cap.TOP_FLAT_RADIUS, cap.INSIDE_HEIGHT, 0.0))
    mouth_ends = ((cap.MOUTH_INNER_DIAMETER / 2.0, 0.0, 0.0), (cap.MAX_OUTER_DIAMETER / 2.0, 0.0, 0.0))
    roof = _line_at(source, *roof_ends, label="inside roof")
    mouth = _line_at(source, *mouth_ends, label="mouth plane")
    bore = _straight_bore_rim(model)

    check("create supplier inside depth sketch", await adapter.create_sketch("Front"))
    _select(model, (roof, mouth), sketch=True)
    if not _early_bound(adapter.currentSketchManager, "ISketchManager").SketchUseEdge3(False, False):
        raise RuntimeError("9275K141: exact section roof/mouth conversion failed")
    model.ClearSelection2(True)
    converted = _segments(model.GetActiveSketch2())
    roof_copy = _line_at(converted, *roof_ends, label="converted inside roof")
    mouth_copy = _line_at(converted, *mouth_ends, label="converted mouth plane")
    # swInputDimValOnCreate=10: a measured reference must never open value input.
    app = _early_bound(adapter.swApp, "ISldWorks")
    app.SetUserPreferenceToggle(10, False)
    if app.GetUserPreferenceToggle(10):
        raise RuntimeError("9275K141: dimension value input remains enabled")
    toggles = {
        constant("swSketchOverdefiningDimsPromptToSetState"): False,
        constant("swSketchOverdefiningDimsSetDrivenByDefault"): True,
    }
    preferences = PreferenceSpec(
        label="9275K141-driven-supplier-references", toggles=toggles,
        baseline_toggles=dict.fromkeys(toggles, False),
    )
    with preference_override(adapter, preferences):
        if any(bool(app.GetUserPreferenceToggle(key)) != wanted for key, wanted in toggles.items()):
            raise RuntimeError("9275K141: driven supplier reference creation preferences were refused")
        _select(model, (roof_copy, mouth_copy), sketch=True)
        _reference(
            model.AddVerticalDimension2(0.020, cap.INSIDE_HEIGHT / 2000.0, 0.0),
            name="SupplierInsideDepth", expected_mm=cap.INSIDE_HEIGHT, kinds=(2, 12),
        )
    model.ClearSelection2(True)
    check("exit supplier inside depth sketch", await adapter.exit_sketch())
    name_last_feature(adapter, "CapSupplierDepth")

    check("create supplier straight bore sketch", await adapter.create_sketch("Top"))
    _select(model, (bore,), sketch=False)
    if not _early_bound(adapter.currentSketchManager, "ISketchManager").SketchUseEdge3(False, False):
        raise RuntimeError("9275K141: exact straight bore projection failed")
    model.ClearSelection2(True)
    converted = _segments(model.GetActiveSketch2())
    if len(converted) != 1 or int(_early_bound(converted[0], "ISketchSegment").GetType()) != 1:
        raise RuntimeError("9275K141: straight bore projection is not one native circle")
    app.SetUserPreferenceToggle(10, False)
    if app.GetUserPreferenceToggle(10):
        raise RuntimeError("9275K141: dimension value input remains enabled")
    with preference_override(adapter, preferences):
        if any(bool(app.GetUserPreferenceToggle(key)) != wanted for key, wanted in toggles.items()):
            raise RuntimeError("9275K141: driven supplier reference creation preferences were refused")
        _select(model, converted, sketch=True)
        _reference(
            model.AddDiameterDimension2(0.020, 0.0, 0.0),
            name="SupplierTubeOD", expected_mm=cap.INNER_DIAMETER, kinds=(6,),
        )
    model.ClearSelection2(True)
    check("exit supplier straight bore sketch", await adapter.exit_sketch())
    name_last_feature(adapter, "CapSupplierBore")
    blank_reference_sketches(adapter, tuple(cap.SUPPLIER_DIMENSIONS))


@wraps(_build_source)
async def build_9275K141(adapter: Any, truth: Any = None) -> None:
    """Retain the registered source author's identity and unchanged solid replay."""
    await _build_source(adapter, truth)
    await author_supplier_references(adapter)
