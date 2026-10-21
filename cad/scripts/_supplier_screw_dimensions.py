"""Import model-owned nominal supplier envelopes, preserving native values."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from math import isfinite
from pathlib import Path
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, iter_views, view_name

from _com import _bind, _early_bound
from _dimensions import _feature_display_dimensions
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_projection import model_points_in_view
from _supplier_dimensions import assert_supplier_reference_dimension, supplier_reference_dimension
from _supplier_screw_layout import supplier_screw_lane_plan
from _supplier_screw_reference_names import FEATURE_BY_PLANE
import _telemetry


def _reference_settings(
    name: str, feature: str, value: float, row: tuple[int, str, int | None, str | None],
    *, configuration: str, units: str = "in",
) -> dict[str, Any]:
    precision, presentation, denominator, callout = row
    angular = presentation == "angle"
    return {
        "label": f"{name}@{feature}",
        "units": "deg" if angular else units,
        "precision": precision,
        "expected_mm": None if angular else abs(value),
        "expected_degrees": value if angular else None,
        "presentation": presentation,
        "fraction_denominator": denominator,
        "callout": callout,
        "configuration": configuration,
    }


def _binding(adapter: Any, raw_view: Any) -> tuple[str, str, str]:
    view = _early_bound(raw_view, "IView")
    name = str(view_name(adapter, view) or "")
    source = str(view.GetReferencedModelName() or "")
    configuration = str(view.ReferencedConfiguration or "")
    if not name or not source or not configuration:
        raise RuntimeError("supplier view has no native name/source/configuration")
    model = _early_bound(view.ReferencedDocument, "IModelDoc2")
    if (
        model is None
        or int(model.GetType()) != 1  # swDocPART
        or Path(model.GetPathName()).resolve() != Path(source).resolve()
        or model.GetConfigurationByName(configuration) is None
    ):
        raise RuntimeError(f"{name}: supplier view source/configuration is missing")
    return name, str(Path(source).resolve()), configuration


def _source_feature_dimensions(
    adapter: Any, source_feature: Any, native: Any
) -> list[dict[str, Any]]:
    """Prove membership by model dimensions, not drawing-context feature wrappers."""
    inventory = []
    for raw_display in _feature_display_dimensions(source_feature):
        display = _bind(raw_display, "IDisplayDimension")
        raw_dimension = display.GetDimension2(0)
        if raw_dimension is None:
            raise RuntimeError("source feature display has no native dimension")
        dimension = _early_bound(raw_dimension, "IDimension")
        inventory.append(
            {
                "full_name": str(dimension.FullName),
                "dimension_is_same": int(adapter.swApp.IsSame(native, dimension)),
            }
        )
    return inventory


def _source_owner_context(
    adapter: Any,
    view: Any,
    model: Any,
    native: Any,
    source_dimension: Any,
    source_feature: Any,
    feature_owner: Any,
    dimension_same: int | None,
    feature_same: int | None,
    feature_dimensions: list[dict[str, Any]],
    feature_dimensions_error: dict[str, str] | None,
) -> dict[str, Any]:
    """Scalar evidence only; a failed diagnostic must not hide the refusal."""

    def probe(read: Callable[[], Any]) -> Any:
        try:
            return read()
        except Exception as exc:
            return {"error_type": type(exc).__name__, "message": str(exc)}

    def feature_name(raw: Any) -> str | None:
        return None if raw is None else str(_early_bound(raw, "IFeature").Name)

    def feature_type(raw: Any) -> str | None:
        return (
            None if raw is None else str(_early_bound(raw, "IFeature").GetTypeName2())
        )

    def dimension_name(raw: Any) -> str | None:
        return None if raw is None else str(_early_bound(raw, "IDimension").FullName)

    return {
        "drawing_path": probe(
            lambda: str(_early_bound(adapter.currentModel, "IModelDoc2").GetPathName())
        ),
        "view_name": probe(lambda: str(view_name(adapter, view))),
        "view_orientation": probe(lambda: str(view.GetOrientationName())),
        "view_source_path": probe(lambda: str(view.GetReferencedModelName())),
        "view_source_configuration": probe(lambda: str(view.ReferencedConfiguration)),
        "source_document_path": probe(lambda: str(model.GetPathName())),
        "native_dimension_name": probe(lambda: dimension_name(native)),
        "source_dimension_name": probe(lambda: dimension_name(source_dimension)),
        "source_dimension_present": source_dimension is not None,
        "source_feature_present": source_feature is not None,
        "native_feature_owner_present": feature_owner is not None,
        "native_feature_owner_name": probe(lambda: feature_name(feature_owner)),
        "native_feature_owner_type": probe(lambda: feature_type(feature_owner)),
        "source_feature_name": probe(lambda: feature_name(source_feature)),
        "source_feature_type": probe(lambda: feature_type(source_feature)),
        "source_feature_dimension_names": [
            row["full_name"] for row in feature_dimensions
        ],
        "source_feature_dimensions": feature_dimensions,
        "source_feature_dimensions_error": feature_dimensions_error,
        "dimension_is_same": dimension_same,
        "feature_is_same": feature_same,
    }


def _assert_source(
    adapter: Any, view: Any, display: Any, *, name: str, feature: str
) -> None:
    """Prove this carrier belongs to this model feature and this drawing view."""
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    owner = annotation.Owner
    if (
        int(annotation.OwnerType) != 0
        or owner is None
        or int(adapter.swApp.IsSame(owner, view)) != 1
    ):
        raise RuntimeError(f"{name}: supplier reference changed drawing-view owner")
    raw = display.GetDimension2(0)
    if raw is None:
        raise RuntimeError(f"{name}: supplier reference lost its native dimension")
    native = _early_bound(raw, "IDimension")
    model = _early_bound(view.ReferencedDocument, "IModelDoc2")
    source_dimension = model.Parameter(f"{name}@{feature}")
    source_feature = _early_bound(view.ReferencedDocument, "IPartDoc").FeatureByName(feature)
    feature_owner = native.GetFeatureOwner()
    dimension_same = (
        None
        if source_dimension is None
        else int(adapter.swApp.IsSame(native, source_dimension))
    )
    feature_same = (
        None
        if feature_owner is None or source_feature is None
        else int(adapter.swApp.IsSame(feature_owner, source_feature))
    )
    feature_dimensions = []
    feature_dimensions_error = None
    if source_feature is not None:
        try:
            feature_dimensions = _source_feature_dimensions(
                adapter, source_feature, native
            )
        except Exception as exc:
            feature_dimensions_error = {
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
    feature_members = [
        row
        for row in feature_dimensions
        if row["full_name"].split("@")[:2] == [name, feature]
        and row["dimension_is_same"] == 1
    ]
    if (
        source_dimension is None
        or source_feature is None
        or dimension_same != 1
        or feature_dimensions_error is not None
        or not feature_members
    ):
        context = _source_owner_context(
            adapter,
            view,
            model,
            native,
            source_dimension,
            source_feature,
            feature_owner,
            dimension_same,
            feature_same,
            feature_dimensions,
            feature_dimensions_error,
        )
        _telemetry.info(
            f"supplier_source_owner_failure {name}@{feature}: "
            + json.dumps(context, sort_keys=True, allow_nan=False)
        )
        raise RuntimeError(f"{name}: supplier reference changed native model/feature owner")
    _telemetry.info(
        f"supplier_source_owner_proof {name}@{feature}: "
        + json.dumps(
            {
                "dimension_is_same": dimension_same,
                "feature_is_same": feature_same,
                "source_feature_dimension": feature_members[0],
            },
            sort_keys=True,
            allow_nan=False,
        )
    )
    source_sketch = _early_bound(source_feature, "IFeature").GetSpecificFeature2()
    entities = tuple(annotation.GetAttachedEntities3() or ())
    types = tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ()))
    if source_sketch is None or not entities or len(entities) != len(types):
        raise RuntimeError(f"{name}: supplier reference lost its source sketch attachments")
    for entity, kind in zip(entities, types, strict=True):
        if entity is None or kind not in (10, 11):  # swSelSKETCHSEGS / swSelSKETCHPOINTS
            raise RuntimeError(f"{name}: nominal supplier reference is not sketch-attached")
        interface = "ISketchSegment" if kind == 10 else "ISketchPoint"
        sketch = _early_bound(entity, interface).GetSketch()
        if sketch is None or int(adapter.swApp.IsSame(sketch, source_sketch)) != 1:
            raise RuntimeError(f"{name}: nominal supplier attachment changed source sketch")


@_telemetry.traced("drawing.supplier_screw_settled_check")
def assert_supplier_screw(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    dimensions: Sequence[tuple[str, float, str]],
    formats: Mapping[str, tuple[int, str, int | None, str | None]],
    planes: Mapping[str, str] | None = None,
    units: Mapping[str, str] | None = None,
    _bindings: Mapping[str, tuple[str, str, str]] | None = None,
) -> dict[str, Any]:
    """Reacquire final native carriers and refuse missing, duplicate or alien ink."""
    planes = planes or {}
    units = units or {}
    supplier_screw_lane_plan(dimensions, planes=planes)
    expected = {name: value for name, value, _ in dimensions}
    if set(formats) != set(expected):
        raise ValueError("supplier screw references and display formats must match")
    if set(units) - set(expected) or any(unit not in ("in", "mm") for unit in units.values()):
        raise ValueError("supplier reference units must name source dimensions in inches or millimetres")
    bindings = _bindings or {key: _binding(adapter, view) for key, view in views.items()}
    actual = list(iter_views(adapter))
    by_name = {str(view_name(adapter, view)): view for view in actual}
    if len(by_name) != len(actual):
        raise RuntimeError("duplicate settled supplier drawing view names")
    found: dict[str, Any] = {}
    for orientation, (native_name, source, configuration) in bindings.items():
        if native_name not in by_name:
            raise RuntimeError(f"{orientation}: settled supplier view is missing")
        view = _early_bound(by_name[native_name], "IView")
        if _binding(adapter, view) != (native_name, source, configuration) or str(view.GetOrientationName()) != orientation:
            raise RuntimeError(f"{orientation}: settled supplier view changed source/configuration/orientation")
        for raw_annotation in view.GetAnnotations() or ():
            annotation = _early_bound(raw_annotation, "IAnnotation")
            if int(annotation.GetType()) != 4:  # swDisplayDimension
                continue
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            raw_dimension = display.GetDimension2(0)
            if raw_dimension is None:
                raise RuntimeError(f"{orientation}: settled supplier annotation has no dimension")
            native = _early_bound(raw_dimension, "IDimension")
            full_name = str(native.FullName)
            identity = full_name.split("@")
            if len(identity) < 2 or identity[1] not in FEATURE_BY_PLANE.values():
                continue
            name, feature = identity[:2]
            if name not in expected:
                raise RuntimeError(f"unexpected settled supplier reference {full_name}")
            plane = planes.get(name, "Front")
            if feature != FEATURE_BY_PLANE[plane] or orientation != f"*{plane}":
                raise RuntimeError(f"{name}: settled supplier reference changed source feature/view")
            if name in found:
                raise RuntimeError(f"{name}: duplicate settled supplier reference")
            _assert_source(adapter, view, display, name=name, feature=feature)
            assert_supplier_reference_dimension(
                adapter, display,
                **_reference_settings(
                    name, feature, expected[name], formats[name],
                    configuration=configuration, units=units.get(name, "in"),
                ),
            )
            found[name] = display
    if set(found) != set(expected):
        raise RuntimeError(f"settled supplier references missing {sorted(set(expected) - set(found))}")
    return found


@_telemetry.traced("drawing.supplier_screw_dimensions")
def annotate_supplier_screw(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    dimensions: Sequence[tuple[str, float, str]],
    formats: Mapping[str, tuple[int, str, int | None, str | None]],
    starts: Mapping[str, tuple[float, float]] | None = None,
    planes: Mapping[str, str] | None = None,
    sides: Mapping[str, str] | None = None,
    units: Mapping[str, str] | None = None,
    settled_checks: list[Callable[[], None]] | None = None,
) -> dict[str, Any]:
    """Curate exact native sizes into their orthographic annotation lanes.

    Hidden construction carriers are nominal supplier references, not proof
    that an ideal envelope survives a physical groove, slot or simplification.
    Physical-edge dimensions use their own existing attachment checks.
    Per-row units retain metric supplier prints; omitted rows use inches.
    Geometry always remains exact millimetres, with angles in degrees.
    """
    starts = starts or {}
    planes = planes or {}
    units = units or {}
    names = {name for name, _, _ in dimensions}
    if names != set(formats) or len(names) != len(dimensions) or set(starts) - names:
        raise ValueError("supplier screw references and display formats must match")
    if set(units) - names or any(unit not in ("in", "mm") for unit in units.values()):
        raise ValueError("supplier reference units must name source dimensions in inches or millimetres")
    lane_plan = supplier_screw_lane_plan(dimensions, planes=planes, sides=sides)
    bindings = {key: _binding(adapter, view) for key, view in views.items()}
    displays: dict[str, Any] = {}
    for plane, feature in FEATURE_BY_PLANE.items():
        rows = [row for row in dimensions if planes.get(row[0], "Front") == plane]
        if not rows:
            continue
        orientation_name = f"*{plane}"
        view = _early_bound(views[orientation_name], "IView")
        if str(view.GetOrientationName()) != orientation_name:
            raise RuntimeError(f"{plane}: supplier references target the wrong orientation")
        view.UpdateViewDisplayGeometry()
        outline = tuple(float(value) for value in view.GetOutline())
        if len(outline) != 4 or not all(isfinite(value) for value in outline):
            raise RuntimeError(f"{plane}: supplier reference view has no finite outline")
        points = []
        for name, value, orientation in rows:
            start = starts.get(name, (0.0, 0.0))
            if len(start) != 2 or not all(isfinite(value) for value in start):
                raise ValueError(f"{name}: supplier reference start must be a finite coordinate pair")
            x, y = start
            if orientation == "horizontal":
                x += value / 2.0
            elif orientation == "vertical":
                y += value / 2.0
            points.append(
                (x / 1000.0, y / 1000.0, 0.0) if plane == "Front"
                else (x / 1000.0, 0.0, -y / 1000.0)
            )
        projected = model_points_in_view(adapter, view, points, label=f"{plane} supplier reference centres")
        keep = {}
        for (name, _, _), (x, y) in zip(rows, projected, strict=True):
            side, offset = lane_plan[name]
            if side == "left":
                x = outline[0] - offset
            elif side == "right":
                x = outline[2] + offset
            elif side == "bottom":
                y = outline[1] - offset
            else:
                y = outline[3] + offset
            if not isfinite(x) or not isfinite(y):
                raise RuntimeError(f"{name}: supplier reference lane is not finite")
            keep[name] = (x, y)
        annotations = curate_view_dimensions(
            adapter, view, keep=keep, view_label=f"{plane} supplier references",
            dimensions_by_feature={feature: set(keep)},
        )
        values = {name: value for name, value, _ in rows}
        for annotation in annotations:
            name = dimension_name(adapter, annotation)
            if name not in values or name in displays:
                raise RuntimeError(f"{name}: unexpected or duplicate imported supplier reference")
            display = _early_bound(_early_bound(annotation, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension")
            _assert_source(adapter, view, display, name=name, feature=feature)
            displays[name] = supplier_reference_dimension(
                adapter, display,
                **_reference_settings(
                    name, feature, values[name], formats[name],
                    configuration=bindings[orientation_name][2], units=units.get(name, "in"),
                ),
            )
    if set(displays) != names:
        raise RuntimeError(f"supplier references missing {sorted(names - set(displays))}")
    if settled_checks is not None:
        settled_checks.append(partial(
            assert_supplier_screw, adapter, views, dimensions=dimensions,
            formats=formats, planes=planes, units=units, _bindings=bindings,
        ))
    return displays
