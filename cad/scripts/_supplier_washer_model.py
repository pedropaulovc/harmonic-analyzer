"""Model-owned supplier bands on exact, construction-only washer witnesses.

Stock recipes initially make +Y solids. Their optional normalization moves
bodies only, so witnesses are authored directly in the final model planes.
Neither this module nor the drawing changes a solid or a native size value.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import json
import math
from pathlib import Path
from typing import Any, Literal

from solidworks_mcp.adapters.com_variant import double_array

import _telemetry
from _check import check
from _com import _early_bound
from _drawing_marks import mark_dimensions_for_drawing
from _drawing_precision import _named_dimensions
from _feature_tree import name_last_feature
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
)
from _sketch_circle import define_circle

OUTER_DIAMETER = "supplier outer diameter"
BORE_DIAMETER = "supplier bore diameter"
THICKNESS = "supplier thickness"
FACE_FEATURE = "SupplierWasherFaceReference"
THICKNESS_FEATURE = "SupplierWasherThicknessReference"
SOURCE_DIMENSIONS = {
    OUTER_DIAMETER: (FACE_FEATURE, "SupplierOuterDiameter"),
    BORE_DIAMETER: (FACE_FEATURE, "SupplierBoreDiameter"),
    THICKNESS: (THICKNESS_FEATURE, "SupplierThickness"),
}


def _assert_supplier_washer_presentation(
    display: Any, *, label: str, units: Literal["in", "mm"],
    precision: int, expected_mm: float, callout: str | None,
) -> None:
    """Read model-owned ink without assuming a visible drawing-view owner."""
    display = _early_bound(display, "IDisplayDimension")
    allowed_types = (2, 11, 12) if label == THICKNESS else (6,)
    if int(display.Type2) not in allowed_types:
        raise RuntimeError(f"{label}: model supplier dimension has the wrong native type")
    raw = display.GetDimension2(0)
    if raw is None:
        raise RuntimeError(f"{label}: model supplier dimension is missing")
    native = _early_bound(raw, "IDimension")
    if not math.isclose(abs(float(native.SystemValue)), expected_mm / 1000.0,
                        rel_tol=0.0, abs_tol=1e-9):
        raise RuntimeError(f"{label}: model supplier dimension differs from its exact carrier")
    prefix = "(" if label == THICKNESS else "(<MOD-DIAM>"
    if (
        display.GetUseDocUnits()
        or int(display.GetUnits()) != {"mm": 0, "in": 3}[units]
        or int(display.GetFractionBase()) != 1  # swDECIMAL
        or int(display.GetPrimaryPrecision2()) != precision
        or int(display.GetPrimaryTolPrecision2()) != precision
        or display.ShowParenthesis
        or display.GetOverride()
        or not display.ShowDimensionValue
        or str(display.GetText(1) or "") != prefix
        or str(display.GetText(2) or "") != f" {units})"
        or str(display.GetText(4) or "") != (callout or "")
    ):
        raise RuntimeError(f"{label}: model supplier units/precision/reference ink changed")


def assert_supplier_washer_band(
    display: Any, *, nominal_mm: float,
    band: tuple[float, float, str] | None, precision: int, label: str,
) -> None:
    """Read only; supplier tolerance precision is not a millimetre precision."""
    native = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
    if band is None:
        if int(tolerance.Type) != 0:
            raise RuntimeError(f"{label}: unexpected native supplier tolerance")
        return
    lower, upper, style = band
    if (
        int(tolerance.Type) != {"bilateral": 2, "limits": 3, "symmetric": 4}[style]
        or not math.isclose(float(tolerance.GetMinValue()), (lower - nominal_mm) / 1000.0,
                            rel_tol=0.0, abs_tol=1e-12)
        or not math.isclose(float(tolerance.GetMaxValue()), (upper - nominal_mm) / 1000.0,
                            rel_tol=0.0, abs_tol=1e-12)
        or int(display.GetPrimaryTolPrecision2()) != precision
    ):
        raise RuntimeError(f"{label}: model-owned supplier band/type/precision changed")


@_telemetry.traced("part.assert_supplier_washer_body")
def assert_supplier_washer_body(
    model: Any, *, axis: Literal["y", "z"], bore_mm: float,
    outer_mm: float, thickness_mm: float,
) -> None:
    """Independently read actual solid circular edges, not witness metadata."""
    bodies = tuple(_early_bound(model, "IPartDoc").GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError("supplier washer must have exactly one solid body")
    circles = []
    for raw in _early_bound(bodies[0], "IBody2").GetEdges() or ():
        curve = _early_bound(_early_bound(raw, "IEdge").GetCurve(), "ICurve")
        if curve.IsCircle():
            circles.append(tuple(float(value) for value in curve.CircleParams))
    index = 1 if axis == "y" else 2
    if len(circles) != 4:
        raise RuntimeError("supplier washer solid must have four circular end rims")
    for diameter in (outer_mm, bore_mm):
        for station in (0.0, thickness_mm):
            center = [0.0, 0.0, 0.0]
            center[index] = station / 1000.0
            matches = [
                circle for circle in circles
                if all(math.isclose(a, b, rel_tol=0.0, abs_tol=1e-9)
                       for a, b in zip(circle[:3], center, strict=True))
                and math.isclose(circle[6], diameter / 2000.0, rel_tol=0.0, abs_tol=1e-9)
                and math.isclose(abs(circle[3 + index]), 1.0, rel_tol=0.0, abs_tol=1e-9)
            ]
            if len(matches) != 1:
                raise RuntimeError(f"supplier washer solid differs at {diameter:g} / {station:g} mm")


def _construction(adapter: Any, entity: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
    segment.ConstructionGeometry = True
    if segment.ConstructionGeometry is not True:
        raise RuntimeError("supplier washer witness is not construction geometry")


def _model_point(adapter: Any, sketch: Any, coordinates: tuple[float, ...]) -> tuple[float, ...]:
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform").Inverse()
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    # CreatePoint requires VT_ARRAY|VT_R8; a bare sequence can silently
    # marshal as variants and be read as the origin (_drawing_leaders).
    point = utility.CreatePoint(double_array(list(coordinates)))
    if transform is None or point is None:
        raise RuntimeError("supplier washer source coordinate mapping is unavailable")
    created = tuple(float(value) for value in _early_bound(point, "IMathPoint").ArrayData)
    _assert_point(created, coordinates, "supplier washer source point marshaling")
    mapped = _early_bound(point, "IMathPoint").MultiplyTransform(transform)
    if mapped is None:
        raise RuntimeError("supplier washer source coordinate mapping failed")
    return tuple(float(value) for value in _early_bound(mapped, "IMathPoint").ArrayData)


def _point_coordinates(point: Any) -> tuple[float, ...]:
    point = _early_bound(point, "ISketchPoint")
    return tuple(float(getattr(point, coordinate)) for coordinate in ("X", "Y", "Z"))


def _assert_point(actual: tuple[float, ...], expected: tuple[float, ...], label: str) -> None:
    if len(actual) != 3 or not all(
        math.isclose(a, b, rel_tol=0.0, abs_tol=1e-9)
        for a, b in zip(actual, expected, strict=True)
    ):
        raise RuntimeError(f"{label}: source geometry {actual!r} != {expected!r}")


def _washer_source_field(value: Any) -> dict[str, Any]:
    """Bound receipts without repr-ing COM objects or reading more properties."""
    field: dict[str, Any] = {"python_type": type(value).__name__}
    if value is None or type(value) in (bool, int, float):
        field["value"] = value
    elif isinstance(value, str):
        field["value"] = value[:512]
    elif type(value) in (tuple, list):
        field["count"] = len(value)
        field["items"] = [
            {"python_type": type(item).__name__,
             "value": item[:512] if isinstance(item, str) else item}
            if item is None or type(item) in (bool, int, float, str)
            else {"python_type": type(item).__name__, "present": True}
            for item in value[:4]
        ]
    else:
        field["present"] = True
    return field


class _WasherSourceReadback:
    """Only the bounded fields consumed by this read-only witness guard."""

    def __init__(self, adapter: Any, label: str) -> None:
        self.app = adapter.swApp
        self.label = label
        self.fields: dict[str, Any] = {}

    def __enter__(self) -> _WasherSourceReadback:
        return self

    def __exit__(self, _kind: Any, error: Any, _traceback: Any) -> None:
        if error is None or not isinstance(error, Exception):
            return
        try:
            message = "supplier washer source attachment readback: " + json.dumps(
                {"label": self.label, "reads": self.fields}, sort_keys=True,
            )
        except BaseException:
            return
        # Either transport may fail; neither may replace the original refusal.
        try:
            error.add_note(message)
        except BaseException:
            pass
        try:
            _telemetry.info(message)
        except BaseException:
            pass

    def read(self, field: str, getter: Callable[[], Any]) -> Any:
        try:
            value = getter()
        except BaseException as error:
            try:
                self.fields[field] = {
                    "error_type": type(error).__name__, "read_error": str(error)[:512],
                }
            except BaseException:
                pass
            raise
        self.fields[field] = _washer_source_field(value)
        return value

    def object(self, field: str, getter: Callable[[], Any], interface: str) -> Any:
        value = self.read(field, getter)
        if value is None:
            raise RuntimeError(f"{self.label}: {field} is unavailable")
        return self.read(f"{field}.interface", lambda: _early_bound(value, interface))

    def same(self, field: str, first: Any, second: Any) -> int:
        value = self.read(field, lambda: self.app.IsSame(first, second))
        if type(value) is not int or value not in (0, 1):
            raise RuntimeError(f"{self.label}: {field} is not a native integer identity")
        return value

    def matrix(self, field: str, rows: tuple[Any, ...], columns: tuple[Any, ...]) -> tuple:
        return tuple(tuple(self.same(f"{field}.{i}.{j}", row, column)
                           for j, column in enumerate(columns))
                     for i, row in enumerate(rows))


def _washer_view_source_context(
    proof: _WasherSourceReadback, model: Any, view: Any, feature: Any,
    native: Any, source_native: Any, owner: Any, *, feature_name: str,
) -> tuple[Any, Any, Any]:
    """Prove feature lineage; an already-part owner must not be reversed."""
    source = proof.object("source.document", lambda: model, "IModelDoc2")
    view = proof.object("view", lambda: view, "IView")
    kind = proof.read("source.document_type", source.GetType)
    referenced = proof.object("view.document", lambda: view.ReferencedDocument, "IModelDoc2")
    referenced_kind = proof.read("view.document_type", referenced.GetType)
    identity = proof.same("view.source_identity", referenced, source)
    paths = (
        proof.read("source.path", source.GetPathName),
        proof.read("view.document_path", referenced.GetPathName),
        proof.read("view.referenced_path", view.GetReferencedModelName),
    )
    configuration = proof.read("view.configuration", lambda: view.ReferencedConfiguration)
    if (
        type(kind) is not int or kind != 1  # swDocPART
        or type(referenced_kind) is not int or referenced_kind != 1
        or identity != 1
        or any(not isinstance(path, str) or not path.strip() for path in paths)
        or len({Path(path).resolve() for path in paths}) != 1
        or not isinstance(configuration, str) or not configuration.strip()
    ):
        raise RuntimeError(f"{proof.label}: source/view native part binding differs")
    # The caller independently captures/rechecks each view's configuration.
    # A source's one active configuration need not equal all legitimate views.
    if proof.same("dimension.source_identity", native, source_native) != 1:
        raise RuntimeError(f"{proof.label}: imported dimension is not its actual native source")
    mapped_feature = proof.object(
        "mapped.feature", lambda: view.GetCorresponding(feature), "IFeature",
    )
    mapped_name = proof.read("mapped.feature_name", lambda: mapped_feature.Name)
    mapped_type = proof.read("mapped.feature_type", mapped_feature.GetTypeName2)
    if mapped_name != feature_name or mapped_type != "ProfileFeature":
        raise RuntimeError(f"{proof.label}: mapped feature is not its named model witness")
    extension = proof.object("source.extension", lambda: source.Extension, "IModelDocExtension")
    reverse = proof.object(
        "mapped.feature_reverse", lambda: extension.GetCorresponding2(mapped_feature), "IFeature",
    )
    if proof.same("mapped.feature_reverse_identity", reverse, feature) != 1:
        raise RuntimeError(f"{proof.label}: mapped feature does not return to its source witness")
    mapped_sketch = proof.object(
        "mapped.feature_sketch", mapped_feature.GetSpecificFeature2, "ISketch",
    )
    owner = proof.object("dimension.owner", lambda: owner, "IFeature")
    owner_name = proof.read("dimension.owner_name", lambda: owner.Name)
    owner_type = proof.read("dimension.owner_type", owner.GetTypeName2)
    source_owner = proof.same("dimension.owner_source_identity", owner, feature)
    mapped_owner = proof.same("dimension.owner_mapped_identity", owner, mapped_feature)
    if owner_name != feature_name or owner_type != "ProfileFeature":
        raise RuntimeError(f"{proof.label}: imported dimension does not belong to its named model witness")
    if source_owner != 1:
        if mapped_owner != 1:
            raise RuntimeError(f"{proof.label}: imported dimension does not belong to its named model witness")
        reverse_owner = proof.object(
            "dimension.owner_reverse", lambda: extension.GetCorresponding2(owner), "IFeature",
        )
        if proof.same("dimension.owner_reverse_identity", reverse_owner, feature) != 1:
            raise RuntimeError(f"{proof.label}: imported dimension does not belong to its named model witness")
    return view, mapped_sketch, extension


def _assert_washer_view_attachments(
    proof: _WasherSourceReadback, view: Any, extension: Any, sketch: Any,
    mapped_sketch: Any, annotation: Any, inventory: tuple[Any, ...],
    selected: tuple[int, ...], *, points: bool,
) -> None:
    """A complete native forward bijection, never coordinate/ID matching."""
    interface = "ISketchPoint" if points else "ISketchSegment"
    identity = ((1, 0), (0, 1))
    if proof.matrix("source.self_distinct", inventory, inventory) != identity:
        raise RuntimeError(f"{proof.label}: source witness members are not independently distinct")
    mapped = []
    for index, entity in enumerate(inventory):
        member = proof.object(f"source.member.{index}", lambda: entity, interface)
        owning_sketch = proof.object(f"source.member.{index}.sketch", member.GetSketch, "ISketch")
        if proof.same(f"source.member.{index}.sketch_identity", owning_sketch, sketch) != 1:
            raise RuntimeError(f"{proof.label}: source entity belongs to another sketch")
        mapped_member = proof.object(
            f"mapped.member.{index}", lambda: view.GetCorresponding(entity), interface,
        )
        owning_sketch = proof.object(
            f"mapped.member.{index}.sketch", mapped_member.GetSketch, "ISketch",
        )
        if proof.same(f"mapped.member.{index}.sketch_identity", owning_sketch, mapped_sketch) != 1:
            raise RuntimeError(f"{proof.label}: mapped entity belongs to another sketch")
        mapped.append(mapped_member)
    mapped = tuple(mapped)
    if proof.matrix("mapped.self_distinct", mapped, mapped) != identity:
        raise RuntimeError(f"{proof.label}: mapped witness members are not independently distinct")
    if not points:
        for index, member in enumerate(mapped):
            reverse = proof.object(
                f"mapped.member.{index}.reverse",
                lambda: extension.GetCorresponding2(member), "ISketchSegment",
            )
            roundtrip = proof.object(
                f"mapped.member.{index}.roundtrip",
                lambda: view.GetCorresponding(reverse), "ISketchSegment",
            )
            if (
                proof.same(f"mapped.member.{index}.reverse_identity", reverse, inventory[index]) != 1
                or proof.same(f"mapped.member.{index}.roundtrip_identity", roundtrip, member) != 1
            ):
                raise RuntimeError(f"{proof.label}: construction circle correspondence differs")
    # GetSpecificFeature2 on the mapped FEATURE defines its sketch. Generic
    # sketch correspondence does not commute, and point inverse can be null.
    owner_type = proof.read("annotation.owner_type", lambda: annotation.OwnerType)
    owner = proof.object("annotation.owner", lambda: annotation.Owner, "IView")
    owner_identity = proof.same("annotation.owner_view_identity", owner, view)
    count = proof.read("annotation.count", annotation.GetAttachedEntityCount3)
    types = tuple(proof.read("annotation.types", annotation.GetAttachedEntityTypes) or ())
    attached = tuple(proof.read("annotation.entities", annotation.GetAttachedEntities3) or ())
    if type(owner_type) is not int or owner_type != 0 or owner_identity != 1:
        raise RuntimeError(f"{proof.label}: source attachment does not belong to its actual view")
    if (
        type(count) is not int or count != len(attached) or count != len(types)
        or count != len(selected)
    ):
        raise RuntimeError(f"{proof.label}: unexpected, hidden or dangling source attachments")
    allowed_types = (11, 25) if points else (10, 24)
    for entity, kind in zip(attached, types, strict=True):
        if entity is None or type(kind) is not int or kind not in allowed_types:
            raise RuntimeError(f"{proof.label}: attachment is not the independently resolved source entity")
    self_matrix = proof.matrix("attached.self_distinct", attached, attached)
    if self_matrix != tuple(tuple(int(i == j) for j in range(count)) for i in range(count)):
        raise RuntimeError(f"{proof.label}: unexpected, hidden or dangling source attachments")
    matrix = proof.matrix("attached.mapped", attached, mapped)
    indices = []
    for row in matrix:
        matches = [index for index, value in enumerate(row) if value == 1]
        if len(matches) != 1:
            raise RuntimeError(f"{proof.label}: attachment is not the independently resolved source entity")
        indices.append(matches[0])
    if len(set(indices)) != len(indices) or set(indices) != set(selected):
        raise RuntimeError(f"{proof.label}: attachment is not the independently resolved source entity")
    for index, entity in enumerate(attached):
        member = proof.object(f"attached.member.{index}", lambda: entity, interface)
        owning_sketch = proof.object(f"attached.member.{index}.sketch", member.GetSketch, "ISketch")
        if proof.same(f"attached.member.{index}.sketch_identity", owning_sketch, mapped_sketch) != 1:
            raise RuntimeError(f"{proof.label}: attachment is not the independently resolved source entity")
    if not points:
        for index, (entity, source_index) in enumerate(zip(attached, indices, strict=True)):
            reverse = proof.object(
                f"attached.member.{index}.reverse",
                lambda: extension.GetCorresponding2(entity), "ISketchSegment",
            )
            roundtrip = proof.object(
                f"attached.member.{index}.roundtrip",
                lambda: view.GetCorresponding(reverse), "ISketchSegment",
            )
            if (
                proof.same(f"attached.member.{index}.reverse_identity", reverse, inventory[source_index]) != 1
                or proof.same(f"attached.member.{index}.roundtrip_identity", roundtrip, entity) != 1
            ):
                raise RuntimeError(f"{proof.label}: attachment is not the independently resolved source entity")
    if proof.read("annotation.dangling", annotation.IsDangling) or (
        int(proof.read("annotation.visible", lambda: annotation.Visible)) != 1
    ):
        raise RuntimeError(f"{proof.label}: unexpected, hidden or dangling source attachments")


def assert_supplier_washer_source_attachment(
    adapter: Any, model: Any, display: Any, *, view: Any | None, label: str,
    axis: Literal["y", "z"], bore_mm: float, outer_mm: float, thickness_mm: float,
) -> None:
    """Independently prove exact source geometry and its actual attachment.

    Both contexts require the independently enumerated source IDimension and
    exact IModelDoc2.Parameter("Dimension@Feature") to have native identity.
    Explicit view=None proves the authoring part's exact owner and attachments;
    an actual view additionally proves full source/view lineage, visibility and
    complete entity correspondence, including circle reverse/roundtrip checks.
    """
    with _WasherSourceReadback(adapter, label) as proof:
        feature_name, dimension_name = SOURCE_DIMENSIONS[label]
        raw = proof.read("source.feature", lambda: _early_bound(model, "IPartDoc").FeatureByName(feature_name))
        if raw is None:
            raise RuntimeError(f"{label}: missing source feature {feature_name}")
        feature = _early_bound(raw, "IFeature")
        source_name = proof.read("source.feature_name", lambda: feature.Name)
        source_type = proof.read("source.feature_type", feature.GetTypeName2)
        if source_name != feature_name or source_type != "ProfileFeature":
            raise RuntimeError(f"{label}: source feature is not its named model witness")
        sketch = proof.object("source.feature_sketch", feature.GetSpecificFeature2, "ISketch")
        source_display, source_native = proof.read(
            "dimension.named_source",
            lambda: _named_dimensions(adapter, feature_name, {dimension_name}, feature=feature),
        )[dimension_name]
        native = proof.object("dimension.imported", lambda: display.GetDimension2(0), "IDimension")
        source_native = proof.object("dimension.source", lambda: source_native, "IDimension")
        source_model = proof.object("source.document", lambda: model, "IModelDoc2")
        parameter_name = proof.read(
            "dimension.model_parameter_query", lambda: f"{dimension_name}@{feature_name}",
        )
        parameter = proof.object(
            "dimension.model_parameter", lambda: source_model.Parameter(parameter_name), "IDimension",
        )
        # IsSame returns a native integer (VT_I4), not a truthy Boolean.
        # Names and values cannot replace any of these independent controls.
        imported_source = proof.same("dimension.source_identity", native, source_native)
        source_parameter = proof.same("dimension.source_parameter_identity", source_native, parameter)
        imported_parameter = proof.same("dimension.imported_parameter_identity", native, parameter)
        if imported_source != 1 or source_parameter != 1 or imported_parameter != 1:
            raise RuntimeError(f"{label}: imported dimension does not belong to its named model witness")
        full_name = str(proof.read("dimension.imported_full_name", lambda: native.FullName) or "")
        owner = proof.read("dimension.owner", native.GetFeatureOwner)
        if (
            full_name.split("@")[:2] != [dimension_name, feature_name]
            or str(proof.read("dimension.source_full_name", lambda: source_native.FullName)).split("@")[:2]
            != [dimension_name, feature_name]
            or owner is None
        ):
            raise RuntimeError(f"{label}: imported dimension does not belong to its named model witness")
        if view is None:
            if (
                proof.same("dimension.owner_source_identity", owner, feature) != 1
                or int(proof.read("dimension.imported_type2", lambda: display.Type2))
                != int(proof.read("dimension.source_type2", lambda: source_display.Type2))
            ):
                raise RuntimeError(f"{label}: imported dimension does not belong to its named model witness")
        else:
            display_type = proof.read("dimension.imported_type2", lambda: display.Type2)
            source_type = proof.read("dimension.source_type2", lambda: source_display.Type2)
            if type(display_type) is not int or type(source_type) is not int or display_type != source_type:
                raise RuntimeError(f"{label}: imported dimension does not belong to its named model witness")
            view, mapped_sketch, extension = _washer_view_source_context(
                proof, model, view, feature, native, source_native, owner, feature_name=feature_name,
            )
        segments = [_early_bound(segment, "ISketchSegment")
                    for segment in proof.read("source.segments", sketch.GetSketchSegments) or ()]
        if len(segments) != (1 if label == THICKNESS else 2) or any(
            proof.read(f"source.segment.{index}.construction", lambda: segment.ConstructionGeometry) is not True
            for index, segment in enumerate(segments)
        ):
            raise RuntimeError(f"{label}: unexpected source witness segment inventory")
        top_plane = (axis == "y") != (label == THICKNESS)
        # Independently check the sketch's final model plane, including Top's -Z.
        for index, (local, expected) in enumerate((
            ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            ((0.001, 0.0, 0.0), (0.001, 0.0, 0.0)),
            ((0.0, 0.001, 0.0), (0.0, 0.0, -0.001) if top_plane else (0.0, 0.001, 0.0)),
        )):
            _assert_point(proof.read(f"source.plane.{index}", lambda: _model_point(adapter, sketch, local)),
                          expected, label)
        if label == THICKNESS:
            segment = segments[0]
            if int(proof.read("source.segment.0.type", segment.GetType)) != 0 or int(display.Type2) not in (2, 11, 12):
                raise RuntimeError(f"{label}: source thickness is not a native line dimension")
            line = _early_bound(segment, "ISketchLine")
            points = (proof.read("source.start", line.GetStartPoint2), proof.read("source.end", line.GetEndPoint2))
            sign = 1.0 if axis == "y" else -1.0
            expected_local = ((outer_mm / 2000.0, 0.0, 0.0),
                              (outer_mm / 2000.0, sign * thickness_mm / 1000.0, 0.0))
            for index, (point, expected) in enumerate(zip(points, expected_local, strict=True)):
                _assert_point(proof.read(f"source.point.{index}", lambda: _point_coordinates(point)), expected, label)
            expected_entities = points
            inventory, selected = points, (0, 1)
        else:
            circles = []
            for index, segment in enumerate(segments):
                if int(proof.read(f"source.segment.{index}.type", segment.GetType)) != 1:
                    raise RuntimeError(f"{label}: source face contains a non-circle")
                circle = _early_bound(segment, "ISketchArc")
                if int(proof.read(f"source.segment.{index}.is_circle", circle.IsCircle)) != 1:
                    raise RuntimeError(f"{label}: source diameter is a partial arc")
                center = proof.read(f"source.segment.{index}.center", circle.GetCenterPoint2)
                _assert_point(proof.read(f"source.segment.{index}.center_coordinates",
                                        lambda: _point_coordinates(center)), (0.0, 0.0, 0.0), label)
                circles.append((segment, float(proof.read(f"source.segment.{index}.radius", circle.GetRadius)) * 2000.0))
            for diameter in (outer_mm, bore_mm):
                if sum(math.isclose(value, diameter, rel_tol=0.0, abs_tol=1e-6)
                       for _, value in circles) != 1:
                    raise RuntimeError(f"{label}: source circles differ from the exact solid recipe")
            expected_mm = outer_mm if label == OUTER_DIAMETER else bore_mm
            expected_entities = tuple(segment for segment, diameter in circles
                                      if math.isclose(diameter, expected_mm, rel_tol=0.0, abs_tol=1e-6))
            inventory = tuple(segment for segment, _ in circles)
            selected = tuple(index for index, (_, diameter) in enumerate(circles)
                             if math.isclose(diameter, expected_mm, rel_tol=0.0, abs_tol=1e-6))
            if int(display.Type2) != 6:
                raise RuntimeError(f"{label}: source diameter lost its native diameter type")
        annotation = proof.object("annotation", display.GetAnnotation, "IAnnotation")
        if view is not None:
            _assert_washer_view_attachments(
                proof, view, extension, sketch, mapped_sketch, annotation, inventory, selected,
                points=label == THICKNESS,
            )
            return
        attached = list(proof.read("annotation.entities", annotation.GetAttachedEntities3) or ())
        for entity in expected_entities:
            matches = [i for i, item in enumerate(attached)
                       if item is not None and proof.same("attached.source_identity", item, entity) == 1]
            if len(matches) != 1:
                raise RuntimeError(f"{label}: attachment is not the independently resolved source entity")
            attached.pop(matches[0])
        if attached or proof.read("annotation.dangling", annotation.IsDangling):
            raise RuntimeError(f"{label}: unexpected, hidden or dangling source attachments")


def _finish_reference(
    adapter: Any, dims: SketchDims, feature: str, labels: tuple[str, ...], *,
    values: Mapping[str, float], units: Literal["in", "mm"],
    precision: Mapping[str, int], bands: Mapping[str, tuple[float, float, str]],
    bore_callout: str | None,
) -> None:
    name_last_feature(adapter, feature)
    dims.apply(adapter, feature)
    named = _named_dimensions(adapter, feature, {SOURCE_DIMENSIONS[label][1] for label in labels})
    for label in labels:
        name = SOURCE_DIMENSIONS[label][1]
        display, native = named[name]
        nominal = values[label]
        lower, upper, style = bands[label]
        if not all(map(math.isfinite, (lower, upper))) or lower >= upper:
            raise ValueError(f"{label}: invalid supplier band")
        if style == "symmetric" and not math.isclose(nominal - lower, upper - nominal,
                                                     rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(f"{label}: symmetric source band is not centred on the exact carrier")
        tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
        tolerance.Type = {"bilateral": 2, "limits": 3, "symmetric": 4}[style]
        if not tolerance.SetValues((lower - nominal) / 1000.0, (upper - nominal) / 1000.0):
            raise RuntimeError(f"{label}: model supplier deviations were rejected")
        if display.GetOverride() or not display.ShowDimensionValue:
            raise RuntimeError(f"{label}: model supplier dimension hides or overrides its native value")
        # Source-model presentation is authored here, not through the shared
        # formatter whose attachment contract requires a visible drawing view.
        # swDECIMAL=1; HalfAway=0 preserves the supplier's decimal rounding.
        if int(display.SetUnits2(False, {"mm": 0, "in": 3}[units], 1, 0, False, 0)) != 0:
            raise RuntimeError(f"{label}: model supplier units were rejected")
        # Unlike _drawing_tolerances' mm-place inference, these are supplier
        # unit places. Both the native success status and readback are required.
        status = display.SetPrecision3(precision[label], -1, precision[label], -1)
        if int(status) != 0:
            raise RuntimeError(f"{label}: model supplier precision failed ({status!r})")
        display.ShowParenthesis = False
        display.SetText(1, "(" if label == THICKNESS else "(<MOD-DIAM>")
        display.SetText(2, f" {units})")
        display.SetText(4, bore_callout if label == BORE_DIAMETER and bore_callout else "")
        _assert_supplier_washer_presentation(
            display, label=label, units=units, precision=precision[label],
            expected_mm=nominal, callout=bore_callout if label == BORE_DIAMETER else None,
        )
        assert_supplier_washer_band(display, nominal_mm=nominal, band=bands[label],
                                    precision=precision[label], label=label)
    mark_dimensions_for_drawing(adapter, feature, {SOURCE_DIMENSIONS[label][1] for label in labels})


@_telemetry.traced("part.supplier_washer_source_author")
async def author_supplier_washer_references(
    adapter: Any, *, axis: Literal["y", "z"], bore_mm: float,
    outer_mm: float, thickness_mm: float, units: Literal["in", "mm"],
    precision: Mapping[str, int], bands: Mapping[str, tuple[float, float, str]],
    bore_callout: str | None = None,
) -> None:
    """Append only banded witnesses after the unchanged +Y stock recipe."""
    if set(bands) not in ({THICKNESS}, {OUTER_DIAMETER, BORE_DIAMETER, THICKNESS}):
        raise ValueError("unsupported washer supplier band coverage")
    model = adapter.currentModel
    assert_supplier_washer_body(model, axis="y", bore_mm=bore_mm,
                               outer_mm=outer_mm, thickness_mm=thickness_mm)
    values = {OUTER_DIAMETER: outer_mm, BORE_DIAMETER: bore_mm, THICKNESS: thickness_mm}
    face_labels = tuple(label for label in (OUTER_DIAMETER, BORE_DIAMETER) if label in bands)
    if face_labels:
        check("create supplier washer face reference",
              await adapter.create_sketch("Top" if axis == "y" else "Front"))
        dims = SketchDims()
        for label in face_labels:
            circle = await define_circle(
                adapter, 0.0, 0.0, values[label] / 2.0, label, dims=dims,
                names=(None, None, SOURCE_DIMENSIONS[label][1]),
            )
            _construction(adapter, circle)
        await ensure_fully_defined(adapter, "supplier washer face reference")
        check("exit supplier washer face reference", await adapter.exit_sketch())
        _finish_reference(adapter, dims, FACE_FEATURE, face_labels, values=values, units=units,
                          precision=precision, bands=bands, bore_callout=bore_callout)
    check("create supplier washer thickness reference",
          await adapter.create_sketch("Front" if axis == "y" else "Top"))
    dims = SketchDims()
    end = thickness_mm if axis == "y" else -thickness_mm
    (line,) = await add_line_chain(adapter, [(outer_mm / 2.0, 0.0), (outer_mm / 2.0, end)], close=False)
    _construction(adapter, line)
    await anchor_point_to_origin(adapter, f"{line}.start", outer_mm / 2.0, 0.0, "supplier OD flank")
    dims.record(None)  # Radial placement is not another printed supplier size.
    check("orient supplier thickness witness", await adapter.add_sketch_constraint(line, None, "vertical"))
    await dimension_between(adapter, f"{line}.start", f"{line}.end", "distance", thickness_mm, THICKNESS)
    dims.record("SupplierThickness")
    await ensure_fully_defined(adapter, "supplier washer thickness reference")
    check("exit supplier washer thickness reference", await adapter.exit_sketch())
    _finish_reference(adapter, dims, THICKNESS_FEATURE, (THICKNESS,), values=values, units=units,
                      precision=precision, bands=bands, bore_callout=bore_callout)
    assert_supplier_washer_references(
        adapter, model, axis=axis, bore_mm=bore_mm, outer_mm=outer_mm, thickness_mm=thickness_mm,
        units=units, precision=precision, bands=bands, bore_callout=bore_callout,
    )


@_telemetry.traced("part.assert_supplier_washer_source")
def assert_supplier_washer_references(
    adapter: Any, model: Any, *, axis: Literal["y", "z"], bore_mm: float,
    outer_mm: float, thickness_mm: float, units: Literal["in", "mm"],
    precision: Mapping[str, int], bands: Mapping[str, tuple[float, float, str]],
    bore_callout: str | None = None,
) -> None:
    values = {OUTER_DIAMETER: outer_mm, BORE_DIAMETER: bore_mm, THICKNESS: thickness_mm}
    part = _early_bound(model, "IPartDoc")
    for label, band in bands.items():
        feature, name = SOURCE_DIMENSIONS[label]
        raw = part.FeatureByName(feature)
        display, _ = _named_dimensions(adapter, feature, {name}, feature=raw)[name]
        assert_supplier_washer_source_attachment(
            adapter, model, display, view=None, label=label, axis=axis, bore_mm=bore_mm,
            outer_mm=outer_mm, thickness_mm=thickness_mm,
        )
        _assert_supplier_washer_presentation(
            display, label=label, units=units, precision=precision[label],
            expected_mm=values[label], callout=bore_callout if label == BORE_DIAMETER else None,
        )
        assert_supplier_washer_band(display, nominal_mm=values[label], band=band,
                                    precision=precision[label], label=label)
