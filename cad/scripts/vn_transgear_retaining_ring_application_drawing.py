"""Separately labelled native supplier application gauges in the Right cell."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array

from _com import _com_invoke, _early_bound
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_projection import model_points_in_view
from _purchased_fastener_drawing import _box, _inside, _literal_note
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
import vn_transgear_retaining_ring_spec as ring

_LABEL = "SUPPLIER APPLICATION GAUGES"


def _gauge_geometry(
    adapter: Any, view: Any
) -> tuple[Any, tuple[float, float, float, float]]:
    part = _early_bound(_early_bound(view, "IView").ReferencedDocument, "IPartDoc")
    raw_feature = part.FeatureByName(ring.SUPPLIER_APPLICATION_SKETCH)
    if raw_feature is None:
        raise RuntimeError("97431A260: source application gauge sketch is missing")
    feature = _early_bound(raw_feature, "IFeature")
    sketch = _early_bound(feature.GetSpecificFeature2(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform").Inverse()
    if transform is None:
        raise RuntimeError("97431A260: application gauge sketch transform is missing")
    utility = _com_invoke(adapter.swApp, "ISldWorks", "GetMathUtility")
    points = []
    for raw in sketch.GetSketchSegments() or ():
        if int(_early_bound(raw, "ISketchSegment").GetType()) != 0:
            raise RuntimeError(
                "97431A260: application gauge contour contains an unexpected entity"
            )
        point = _early_bound(
            _early_bound(raw, "ISketchLine").GetStartPoint2(), "ISketchPoint"
        )
        native = _com_invoke(
            utility,
            "IMathUtility",
            "CreatePoint",
            double_array([point.X, point.Y, point.Z]),
        )
        model_point = _com_invoke(native, "IMathPoint", "MultiplyTransform", transform)
        if model_point is None:
            raise RuntimeError(
                "97431A260: failed to transform actual application gauge vertex"
            )
        points.append(
            tuple(float(v) for v in _com_invoke(model_point, "IMathPoint", "ArrayData"))
        )
    if len(points) != 12:
        raise RuntimeError(
            "97431A260: expected one twelve-edge supplier application section"
        )
    projected = model_points_in_view(
        adapter, view, points, label="97431A260 application gauge section"
    )
    xs, ys = zip(*projected)
    return feature, (min(xs), min(ys), max(xs), max(ys))


def add_application_gauges(adapter: Any, views: dict[str, Any]) -> Callable[[], None]:
    """Show only Right's source gauge sketch; never create a fifth view or refit."""
    right = views["*Right"]
    feature, gauge_box = _gauge_geometry(adapter, right)
    if int(feature.Visible) != 1:
        raise RuntimeError("97431A260: application gauge sketch was not saved hidden")
    # Reset every view to the part's hidden sketch state, then show the gauge
    # only through Right's targeted import. This cannot reveal it on the ISO.
    for view in views.values():
        _early_bound(view, "IView").ResetSketchVisibility()
    original_boxes = {
        key: tuple(float(v) for v in view.GetOutline()) for key, view in views.items()
    }
    original_positions = {
        key: tuple(float(v) for v in view.Position) for key, view in views.items()
    }
    original_scales = {
        key: tuple(float(v) for v in view.ScaleRatio) for key, view in views.items()
    }
    ring_box = original_boxes["*Right"]
    if gauge_box[0] < ring_box[2] + 0.008:
        raise RuntimeError(
            "97431A260: application gauge section is not separately placed to the right of the ring"
        )
    center_x = (gauge_box[0] + gauge_box[2]) / 2.0
    center_y = (gauge_box[1] + gauge_box[3]) / 2.0
    expected = {
        "ApplicationShaftOD": (ring.SHAFT_DIA, "diameter", "FOR SHAFT OD", None),
        "ApplicationGrooveDiameter": (
            ring.GROOVE_DIA,
            "diameter",
            "FOR GROOVE DIA",
            ring.GROOVE_DIA_BAND,
        ),
        "ApplicationGrooveWidth": (
            ring.GROOVE_WIDTH,
            "length",
            "FOR GROOVE WIDTH",
            ring.GROOVE_WIDTH_BAND,
        ),
    }
    positions = {
        "ApplicationShaftOD": (gauge_box[2] + 0.010, center_y + 0.009),
        "ApplicationGrooveDiameter": (gauge_box[0] - 0.022, center_y - 0.004),
        "ApplicationGrooveWidth": (center_x, gauge_box[1] - 0.012),
    }
    annotations = curate_view_dimensions(
        adapter,
        right,
        keep=positions,
        view_label="97431A260 supplier application gauges",
        dimensions_by_feature=ring.SUPPLIER_APPLICATION_DIMENSIONS,
    )
    if len(annotations) != 3:
        raise RuntimeError(
            "97431A260: expected exactly three native application gauge references"
        )
    references = []
    for annotation in annotations:
        annotation = _early_bound(annotation, "IAnnotation")
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        native = _early_bound(display.GetDimension2(0), "IDimension")
        name = str(native.Name)
        if name not in expected:
            raise RuntimeError(
                f"97431A260: unexpected application gauge reference {name}"
            )
        value, presentation, callout, band = expected[name]
        settings = dict(
            label=f"97431A260 {name}",
            units="in",
            precision=ring.SUPPLIER_SUITABILITY_PRECISION,
            expected_mm=value,
            presentation=presentation,
            callout=callout,
        )
        supplier_reference_dimension(adapter, display, **settings)
        references.append((display, name, settings, band))
    if {name for _, name, _, _ in references} != set(expected):
        raise RuntimeError(
            "97431A260: application gauge dimensions are missing or duplicated"
        )
    label = _literal_note(adapter, _LABEL, gauge_box[0] - 0.020, gauge_box[3] + 0.022)

    def settled() -> None:
        if label.GetText() != _LABEL:
            raise RuntimeError(
                "97431A260: application gauge identification label changed"
            )
        label_box = _box(label.GetExtent(), label=_LABEL, kind="note")
        # Dedicated band within the original Right cell. No source dimension
        # is typed into this label and no gauge contour enters the ring glyph.
        if not _inside(label_box, (0.225, 0.150, 0.405, 0.182)):
            raise RuntimeError(
                "97431A260: application gauge label leaves its original Right-cell band"
            )
        fresh_feature, fresh_box = _gauge_geometry(adapter, right)
        if int(fresh_feature.Visible) != 1 or any(
            abs(a - b) > 1e-6 for a, b in zip(fresh_box, gauge_box)
        ):
            raise RuntimeError(
                "97431A260: application gauge model visibility or footprint changed"
            )
        source_sketch = _early_bound(fresh_feature, "IFeature").GetSpecificFeature2()
        for orientation, view in views.items():
            if (
                tuple(float(v) for v in view.Position)
                != original_positions[orientation]
                or tuple(float(v) for v in view.ScaleRatio)
                != original_scales[orientation]
            ):
                raise RuntimeError(
                    "97431A260: application gauge import moved or rescaled a fitted view"
                )
            if orientation != "*Right" and any(
                abs(a - b) > 1e-6
                for a, b in zip(view.GetOutline(), original_boxes[orientation])
            ):
                raise RuntimeError(
                    "97431A260: application gauge geometry leaked outside its Right view"
                )
        for display, name, settings, band in references:
            assert_supplier_reference_dimension(adapter, display, **settings)
            native = _early_bound(display.GetDimension2(0), "IDimension")
            annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
            owner = str(native.FullName).split("@")
            if (
                int(native.DrivenState) != 1
                or str(native.Name) != name
                or len(owner) < 2
                or owner[1] != ring.SUPPLIER_APPLICATION_SKETCH
                or int(annotation.Visible) != 1
            ):
                raise RuntimeError(
                    f"97431A260 {name}: settled reference is not attached to its separate visible source gauge"
                )
            attached = tuple(annotation.GetAttachedEntities3() or ())
            kinds = tuple(
                int(value) for value in (annotation.GetAttachedEntityTypes() or ())
            )
            if not attached or len(attached) != len(kinds):
                raise RuntimeError(
                    f"97431A260 {name}: source gauge attachments are missing"
                )
            for entity, kind in zip(attached, kinds, strict=True):
                if entity is None or kind not in (10, 11, 24, 25):
                    raise RuntimeError(
                        f"97431A260 {name}: application reference attaches to purchased-body geometry"
                    )
                interface = "ISketchSegment" if kind in (10, 24) else "ISketchPoint"
                owner_sketch = _early_bound(entity, interface).GetSketch()
                if (
                    owner_sketch is None
                    or int(adapter.swApp.IsSame(owner_sketch, source_sketch)) != 1
                ):
                    raise RuntimeError(
                        f"97431A260 {name}: application reference attaches outside its source gauge sketch"
                    )
            if band is not None:
                tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
                if (
                    int(tolerance.Type) != 2
                    or abs(float(tolerance.GetMinValue()) + band[1] / 1000.0) > 1e-12
                    or abs(float(tolerance.GetMaxValue()) - band[0] / 1000.0) > 1e-12
                    or int(display.GetPrimaryTolPrecision2())
                    != ring.SUPPLIER_SUITABILITY_PRECISION
                ):
                    raise RuntimeError(
                        f"97431A260 {name}: native supplier gauge tolerance changed"
                    )

    return settled
