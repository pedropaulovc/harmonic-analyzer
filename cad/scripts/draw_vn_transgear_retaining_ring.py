"""Create the purchased reference drawing for the transgear retaining ring (MHA-VN-047, McMaster 97431A260)."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import sys
from typing import Any

import _telemetry
from _com import _early_bound
from _drawing_attachment import _is_same_attachment
from _drawing_edges import ViewEdges, scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_selection import _select_view_entity
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
import vn_transgear_retaining_ring_spec as ring
from vn_transgear_retaining_ring_application_drawing import add_application_gauges
from vn_transgear_retaining_ring_supplier_refs import THICKNESS_DIMENSION, THICKNESS_SKETCH
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing


SPEC = DRAWINGS_BY_NAME["vn_transgear_retaining_ring"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "E-STYLE EXTERNAL RETAINING RING"


def _thickness_edge(edges: ViewEdges) -> Any:
    """A real extruded corner spanning the ring's two Z faces, not its groove."""
    candidates = [
        item for item in edges.lines
        if abs(item.line[0][0] - item.line[1][0]) < 1e-6
        and abs(item.line[0][1] - item.line[1][1]) < 1e-6
        and abs(min(item.line[0][2], item.line[1][2])) < 1e-6
        and abs(max(item.line[0][2], item.line[1][2]) - ring.THICKNESS) < 1e-6
    ]
    if not candidates:
        raise RuntimeError("97431A260: no visible edge spans the exact ring thickness")
    return max(candidates, key=lambda item: item.midpoint_mm[1]).edge


def _edge_reference(
    adapter: Any,
    view: Any,
    edge: Any,
    *,
    label: str,
    expected_mm: float,
    text_xy: tuple[float, float],
    diameter: bool = False,
) -> Any:
    selected = _select_view_entity(
        adapter, view, "EDGE", None, label=label, entity=edge
    )
    draw = adapter.currentModel
    create = draw.AddDiameterDimension2 if diameter else draw.AddDimension2
    raw = create(*text_xy, 0.0)
    draw.ClearSelection2(True)
    if raw is None:
        raise RuntimeError(f"{label}: native supplier dimension was not created")
    display = _early_bound(raw, "IDisplayDimension")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    if len(attached) != 1 or not _is_same_attachment(
        adapter, attached[0], selected, "EDGE"
    ):
        raise RuntimeError(f"{label}: dimension did not stay on its selected ring edge")
    native = _early_bound(display.GetDimension2(0), "IDimension")
    native.DrivenState = 1  # swDimensionDriven: measurement, never geometry control
    if int(native.DrivenState) != 1:
        raise RuntimeError(f"{label}: supplier measurement did not remain driven")
    return supplier_reference_dimension(
        adapter, display, label=label, units="in",
        precision=ring.SUPPLIER_REFERENCE_PRECISION,
        expected_mm=expected_mm,
        presentation="diameter" if diameter else "length",
    )


def supplier_dimensions(adapter: Any, views: dict[str, Any]) -> Callable[[], None]:
    """The supplier's free gripping diameter, outside diameter and thickness."""
    front = views["*Front"]
    edges = scan_view_edges(front, label="97431A260 front supplier references")
    x0, y0, x1, y1 = (float(v) for v in front.GetOutline())
    references = []
    for label, diameter, text_xy in (
        ("97431A260 free gripping diameter", ring.FREE_DIA, (x1 + 0.009, y0 - 0.006)),
        ("97431A260 outside diameter", ring.OD, (x0 - 0.009, y1 + 0.006)),
    ):
        circle = edges.circle_at(
            (0.0, 0.0, ring.THICKNESS), diameter / 2.0,
            axis=(0.0, 0.0, 1.0), label=label,
            center_tol_mm=1e-6, radius_tol_mm=1e-6,
        )
        display = _edge_reference(
            adapter, front, circle.edge, label=label, expected_mm=diameter,
            text_xy=text_xy, diameter=True,
        )
        references.append((display, label, diameter))
    # Application-gauge isolation resets per-view sketch visibility. Do this
    # before showing the independently hidden physical thickness carrier.
    application_settled = add_application_gauges(adapter, views)
    top = views["*Top"]
    _thickness_edge(scan_view_edges(top, label="97431A260 physical thickness reference"))
    x0, y0, x1, y1 = (float(v) for v in top.GetOutline())
    annotations = curate_view_dimensions(
        adapter, top, keep={THICKNESS_DIMENSION: (x1 + 0.012, (y0 + y1) / 2.0)},
        view_label="97431A260 physical ring thickness",
        dimensions_by_feature={THICKNESS_SKETCH: (THICKNESS_DIMENSION,)},
    )
    if len(annotations) != 1:
        raise RuntimeError("97431A260: expected one imported source thickness reference")
    display = _early_bound(
        _early_bound(annotations[0], "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension",
    )
    supplier_reference_dimension(
        adapter, display, label="97431A260 ring thickness", units="in",
        precision=ring.SUPPLIER_REFERENCE_PRECISION, expected_mm=ring.THICKNESS,
    )
    band = ring.THICKNESS_TOL / 1000.0

    def settled() -> None:
        for orientation, expected_count in (
            ("*Front", 2), ("*Top", 1), ("*Right", 3), ("*Isometric", 0),
        ):
            count = int(_early_bound(views[orientation], "IView").GetDisplayDimensionCount())
            if count != expected_count:
                raise RuntimeError(
                    f"97431A260 {orientation}: expected {expected_count} native references, got {count}"
                )
        fresh_front = scan_view_edges(front, label="97431A260 settled front references")
        _thickness_edge(scan_view_edges(top, label="97431A260 settled physical thickness"))
        for measured, label, expected in references:
            assert_supplier_reference_dimension(
                adapter, measured, label=label, units="in",
                precision=ring.SUPPLIER_REFERENCE_PRECISION, expected_mm=expected,
                presentation="diameter",
            )
            if int(_early_bound(measured.GetDimension2(0), "IDimension").DrivenState) != 1:
                raise RuntimeError(f"{label}: settled reference no longer driven")
            actual = tuple(_early_bound(measured.GetAnnotation(), "IAnnotation").GetAttachedEntities3() or ())
            # Three prongs share one gripping circle. The fresh scan may order
            # those equally valid arcs differently after the final rebuild.
            expected_edges = [
                item.edge for item in fresh_front.circles
                if sum(abs(a - b) for a, b in zip(item.circle[:3], (0.0, 0.0, ring.THICKNESS))) < 1e-6
                and abs(item.circle[6] - expected / 2.0) < 1e-6
                and abs(abs(item.circle[5]) - 1.0) < 1e-6
            ]
            if len(actual) != 1 or not any(
                _is_same_attachment(adapter, actual[0], edge, "EDGE")
                for edge in expected_edges
            ):
                raise RuntimeError(f"{label}: settled reference lost its physical ring attachment")
        assert_supplier_reference_dimension(
            adapter, display, label="97431A260 ring thickness", units="in",
            precision=ring.SUPPLIER_REFERENCE_PRECISION, expected_mm=ring.THICKNESS,
        )
        settled_native = _early_bound(display.GetDimension2(0), "IDimension")
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        owner = str(settled_native.FullName).split("@")
        if (
            int(settled_native.DrivenState) != 1
            or str(settled_native.Name) != THICKNESS_DIMENSION
            or len(owner) < 2 or owner[1] != THICKNESS_SKETCH
            or int(annotation.Visible) != 1
        ):
            raise RuntimeError("97431A260: settled thickness lost its visible driven source owner")
        source = _early_bound(_early_bound(top, "IView").ReferencedDocument, "IPartDoc")
        feature = source.FeatureByName(THICKNESS_SKETCH)
        if feature is None or int(_early_bound(feature, "IFeature").Visible) != 1:
            raise RuntimeError("97431A260: thickness source carrier is missing or no longer saved hidden")
        source_sketch = _early_bound(feature, "IFeature").GetSpecificFeature2()
        actual = tuple(annotation.GetAttachedEntities3() or ())
        kinds = tuple(int(value) for value in (annotation.GetAttachedEntityTypes() or ()))
        if not actual or len(actual) != len(kinds):
            raise RuntimeError("97431A260: source thickness attachments are missing")
        for entity, kind in zip(actual, kinds, strict=True):
            if entity is None or kind not in (10, 11, 24, 25):
                raise RuntimeError("97431A260: thickness reference is not attached to its converted source")
            interface = "ISketchSegment" if kind in (10, 24) else "ISketchPoint"
            owner_sketch = _early_bound(entity, interface).GetSketch()
            if owner_sketch is None or int(adapter.swApp.IsSame(owner_sketch, source_sketch)) != 1:
                raise RuntimeError("97431A260: thickness attachment left its actual converted source sketch")
        settled_tolerance = _early_bound(settled_native.Tolerance, "IDimensionTolerance")
        if (
            int(settled_tolerance.Type) != 4
            or abs(float(settled_tolerance.GetMinValue()) + band) > 1e-12
            or abs(float(settled_tolerance.GetMaxValue()) - band) > 1e-12
            or int(display.GetPrimaryTolPrecision2()) != ring.SUPPLIER_REFERENCE_PRECISION
        ):
            raise RuntimeError("97431A260: settled model-owned thickness tolerance changed")
        application_settled()

    return settled


async def build(adapter: Any) -> dict[str, str]:
    checks: list[Callable[[], None]] = []

    def dimensions(active_adapter: Any, views: dict[str, Any]) -> None:
        checks.append(supplier_dimensions(active_adapter, views))

    def settled() -> None:
        if len(checks) != 1:
            raise RuntimeError("97431A260: supplier references must be authored exactly once")
        checks[0]()

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, supplier_dimensions=dimensions,
        supplier_margins={
            "*Front": (0.020, 0.020, 0.020, 0.020),
            "*Top": (0.020, 0.020, 0.035, 0.020),
            # Includes the separate application gauge and its native FOR ink.
            "*Right": (0.020, 0.020, 0.100, 0.020),
        },
        settled_checks=(settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
