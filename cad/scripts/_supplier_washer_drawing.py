"""Import model-owned washer supplier bands; add only unbanded rim refs.

The part owns every banded dimension's native value, tolerance and supplier
presentation. Imports retain the source's explicit display units; precision,
reference ink and bands are never rewritten.

Source-attachment refusals add a bounded, read-only native-context receipt and
still fail the original strict assertion; the receipt never accepts a mapping.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, view_name

from _com import _bind, _early_bound
from _drawing_attachment import _is_same_attachment
from _drawing_edges import ViewEdges, scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_precision import _named_dimensions
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_washer_model import (
    BORE_DIAMETER,
    OUTER_DIAMETER,
    SOURCE_DIMENSIONS,
    THICKNESS,
    _assert_supplier_washer_presentation,
    assert_supplier_washer_band,
    assert_supplier_washer_body,
    assert_supplier_washer_source_attachment,
)
import _telemetry


@dataclass(frozen=True)
class _WasherReference:
    view: Any
    selection_name: str
    full_name: str
    label: str
    expected_mm: float
    presentation: Literal["length", "diameter"]
    imported: bool
    callout: str | None = None


@dataclass(frozen=True)
class SupplierWasherProof:
    """Keep the live finalizer check callable; audit saved bytes separately."""

    settled_check: Callable[[], None]
    saved_check: Callable[[Any, Path], None]

    def __call__(self) -> None:
        self.settled_check()


def _persist_imported_units(
    adapter: Any, view: Any, display: Any, *, label: str,
    units: Literal["in", "mm"], precision: int, expected_mm: float,
    callout: str | None,
) -> None:
    """Transfer only unit-display ownership lost by native model-item import."""
    model = _early_bound(view, "IView").ReferencedDocument
    if model is None:
        raise RuntimeError(f"{label}: imported supplier dimension has no source part")
    feature_name, name = SOURCE_DIMENSIONS[label]
    feature = _early_bound(model, "IPartDoc").FeatureByName(feature_name)
    if feature is None:
        raise RuntimeError(f"{label}: imported supplier source feature is missing")
    source, native = _named_dimensions(adapter, feature_name, {name}, feature=feature)[name]
    try:
        _assert_supplier_washer_presentation(
            source, label=label, units=units, precision=precision,
            expected_mm=expected_mm, callout=callout,
        )
        identity = adapter.swApp.IsSame(display.GetDimension2(0), native)
        if type(identity) is not int or identity != 1:
            raise RuntimeError(f"{label}: imported supplier dimension is not its native source")
        # Import selects drawing-document units even when the source display has
        # explicit units. SDK GetUnits/GetFractionBase then return -1, not the
        # supplier settings. FractDenom is meaningful only for fractional inches;
        # transfer the source getter unchanged rather than inventing a denominator.
        # HalfAway=0 is the source author's documented decimal-rounding choice.
        status = display.SetUnits2(
            False, source.GetUnits(), source.GetFractionBase(),
            source.GetFractionValue(), source.GetRoundToFraction(), 0,
        )
        if type(status) is not int or status != 0:
            raise RuntimeError(f"{label}: imported supplier units were rejected ({status!r})")
        assert_supplier_reference_dimension(
            adapter, display, label=label, units=units, precision=precision,
            expected_mm=expected_mm, presentation="length" if label == THICKNESS else "diameter",
            callout=callout,
        )
    except Exception as error:
        error.add_note("supplier washer source/import readback: " + json.dumps(
            {"source": _saved_display_readback(source), "imported": _saved_display_readback(display)},
            sort_keys=True, default=repr,
        ))
        raise


def _rim(
    edges: ViewEdges, *, axis: Literal["y", "z"], station_mm: float,
    diameter_mm: float, label: str,
) -> Any:
    center = (0.0, station_mm, 0.0) if axis == "y" else (0.0, 0.0, station_mm)
    normal = (0.0, 1.0, 0.0) if axis == "y" else (0.0, 0.0, 1.0)
    return edges.circle_at(
        center, diameter_mm / 2.0, axis=normal, label=label,
        center_tol_mm=1e-6, radius_tol_mm=1e-6,
    ).edge


def _assert_rim(adapter: Any, display: Any, rim: Any, *, label: str) -> None:
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    attached = list(annotation.GetAttachedEntities3() or ())
    if (
        len(attached) != 1 or attached[0] is None
        or not _is_same_attachment(adapter, attached[0], rim, "EDGE")
        or annotation.IsDangling() or int(annotation.Visible) != 1
    ):
        raise RuntimeError(f"{label}: native unbanded diameter lost its exact physical rim")


def _native_diameter(
    adapter: Any, view: Any, rim: Any, *, text_xy: tuple[float, float], label: str,
) -> Any:
    """The policy exception: an unbanded reference on an actual solid rim."""
    draw = adapter.currentModel
    if not _early_bound(draw, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"{label}: failed to activate drawing view")
    draw.ClearSelection2(True)
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    data = manager.CreateSelectData()
    data.View = view
    if _early_bound(rim, "IEntity").Select4(False, data) is not True:
        raise RuntimeError(f"{label}: failed to select physical rim")
    if (
        int(manager.GetSelectedObjectCount2(-1)) != 1
        or int(adapter.swApp.IsSame(manager.GetSelectedObject6(1, -1), rim)) != 1
    ):
        raise RuntimeError(f"{label}: selection is not the intended physical rim")
    display, status = _early_bound(draw.Extension, "IModelDocExtension").AddSpecificDimension(
        text_xy[0], text_xy[1], 0.0, 6, 0  # swDiameterDimension
    )
    draw.ClearSelection2(True)
    if display is None or int(status) != 0:
        raise RuntimeError(f"{label}: native diameter failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    _assert_rim(adapter, display, rim, label=label)
    return display


def _reference(
    display: Any, view: Any, label: str, expected_mm: float, *,
    imported: bool, callout: str | None = None,
) -> _WasherReference:
    selection_name = str(display.GetNameForSelection() or "")
    full_name = str(_early_bound(display.GetDimension2(0), "IDimension").FullName or "")
    if not selection_name or not full_name:
        raise RuntimeError(f"{label}: native dimension has no stable selection/full name")
    return _WasherReference(view, selection_name, full_name, label, expected_mm,
                            "length" if label == THICKNESS else "diameter", imported, callout)


def _visible_dimensions(view: Any) -> list[Any]:
    visible = []
    raw = _early_bound(view, "IView").GetFirstDisplayDimension5()
    while raw is not None:
        display = _early_bound(raw, "IDisplayDimension")
        if int(_early_bound(display.GetAnnotation(), "IAnnotation").Visible) == 1:
            visible.append(display)
        raw = display.GetNext5()
    return visible


def _source_attachment_failure_readback(
    adapter: Any, model: Any, view: Any, display: Any, *, label: str,
) -> dict[str, Any]:
    """Snapshot failed native contexts, without repairing or interpreting them.

    Indices preserve each SDK array's order, not an assumed correspondence.
    GetID pairs are sketch- and element-type-scoped, NOT persistent identities.
    Only native IsSame receipts compare contexts; coordinates/IDs decide nothing.
    Raw transport and an independent explicitly bound chain remain separate:
    typed_* matrices never replace or reinterpret the original native results.
    The sixteen-member cap bounds pathological inventories and all cross-products;
    an explicit skipped remainder records overflow rather than hiding it.
    """
    reads: dict[str, Any] = {}
    matrices: dict[str, Any] = {}
    values: dict[str, Any] = {}
    unavailable = object()
    limit = 16

    def receipt(getter: Callable[[], Any], *, handle: bool = False) -> tuple[Any, dict[str, Any]]:
        try:
            value = getter()
            field = {"present": value is not None} if handle else {"value": value}
            return value, {**field, "python_type": type(value).__name__}
        except Exception as error:
            return unavailable, {
                "read_error": {"type": type(error).__name__, "message": str(error)},
            }

    def take(
        name: str, getter: Callable[..., Any], *dependencies: str, handle: bool = False,
    ) -> str:
        missing = next((key for key in dependencies
                        if values.get(key, unavailable) is unavailable or values[key] is None), None)
        if missing is not None:
            values[name] = unavailable
            reads[name] = {"skipped": f"{missing} unavailable"}
        else:
            values[name], reads[name] = receipt(
                lambda: getter(*(values[key] for key in dependencies)), handle=handle,
            )
        return name

    def same_receipt(left: str, right: str) -> dict[str, Any]:
        for key in (left, right):
            if values.get(key, unavailable) is unavailable or values[key] is None:
                return {"skipped": f"{key} unavailable"}
        return receipt(lambda: adapter.swApp.IsSame(values[left], values[right]))[1]

    def same(name: str, left: str, right: str) -> None:
        reads[name] = same_receipt(left, right)

    def bound(
        name: str, source: str, interface: str | None, *, kind_key: str | None = None,
    ) -> str:
        if interface is None:
            missing_kind = values.get(kind_key, unavailable)
            missing_source = values.get(source, unavailable)
            values[name] = unavailable
            if missing_source is unavailable or missing_source is None:
                reason = f"{source} unavailable"
            elif missing_kind is unavailable or missing_kind is None:
                reason = f"{kind_key} unavailable"
            else:
                reason = f"{kind_key} does not identify an available sketch interface"
            reads[name] = {"skipped": reason}
            return name
        return take(name, lambda raw: _early_bound(_bind(raw, interface), interface),
                    source, handle=True)

    def object_read(
        name: str, getter: Callable[..., Any], *dependencies: str,
        typed: bool = False, interface: str | None = None,
    ) -> str:
        raw = take(f"{name}.raw" if typed else name, getter, *dependencies, handle=True)
        return bound(name, raw, interface) if typed else raw

    def forward(
        name: str, source: str, *, typed: bool = False, interface: str | None = None,
    ) -> str:
        return object_read(
            name, lambda target, entity: _early_bound(target, "IView").GetCorresponding(entity),
            "typed.view.handle" if typed else "view.handle", source,
            typed=typed, interface=interface,
        )

    def reverse(
        name: str, source: str, *, typed: bool = False, interface: str | None = None,
    ) -> str:
        return object_read(
            name, lambda extension, entity: _early_bound(
                extension, "IModelDocExtension").GetCorresponding2(entity),
            "typed.source.extension" if typed else "source.extension", source,
            typed=typed, interface=interface,
        )

    def inventory(name: str) -> list[str] | None:
        raw = values.get(name, unavailable)
        if raw is unavailable or raw is None:
            return None
        # Native array results contain handles, so only their presence/type and
        # each member's presence/type enter JSON, never the dispatch objects.
        keys = []
        try:
            for index in range(min(len(raw), limit)):
                keys.append(take(f"{name}.{index}", lambda: raw[index], handle=True))
            if len(raw) > limit:
                reads[f"{name}.remainder"] = {
                    "skipped": f"{name} inventory beyond diagnostic limit {limit}",
                }
        except Exception as error:
            reads[f"{name}.inventory"] = {
                "read_error": {"type": type(error).__name__, "message": str(error)},
            }
            return None
        return keys

    def matrix(name: str, left: list[str] | None, right: list[str] | None,
               *, left_name: str, right_name: str) -> None:
        if left is None or right is None:
            missing = left_name if left is None else right_name
            matrices[name] = [[{"skipped": f"{missing} unavailable"}]]
        else:
            matrices[name] = [[same_receipt(a, b) for b in right] for a in left]

    def member(
        key: str, interface: str | None, *, space: Literal["source", "view"],
        kind_key: str | None = None, typed: bool = False,
    ) -> None:
        if interface is None:
            missing_kind = values.get(kind_key, unavailable)
            reason = (
                f"{kind_key} unavailable" if missing_kind is unavailable or missing_kind is None
                else f"{kind_key} does not identify an available sketch interface"
            )
            for field in (
                "id", "sketch", "sketch_source_identity", "sketch_feature_identity",
                "sketch_view", "sketch_view_identity", "sketch_reverse",
                "sketch_reverse_identity", "sketch_reverse_feature_identity",
                "sketch_mapped_feature_identity", "geometry",
            ):
                values[f"{key}.{field}"] = unavailable
                reads[f"{key}.{field}"] = {"skipped": reason}
            return
        take(f"{key}.id", lambda entity: _early_bound(entity, interface).GetID(), key)
        source = "typed.source" if typed else "source"
        sketch = object_read(f"{key}.sketch", lambda entity: _early_bound(entity, interface).GetSketch(),
                             key, typed=typed, interface="ISketch")
        same(f"{key}.sketch_source_identity", sketch, f"{source}.sketch")
        same(f"{key}.sketch_feature_identity", sketch, f"{source}.feature_sketch")
        # Each hop receives the documented source context, not the same sketch
        # blindly sent in both directions. Derived points inherit this space.
        if space == "source":
            mapped_sketch = forward(f"{key}.sketch_view", sketch, typed=typed, interface="ISketch")
            reversed_sketch = reverse(f"{key}.sketch_reverse", mapped_sketch,
                                      typed=typed, interface="ISketch")
        else:
            reversed_sketch = reverse(f"{key}.sketch_reverse", sketch, typed=typed, interface="ISketch")
            mapped_sketch = forward(f"{key}.sketch_view", reversed_sketch,
                                    typed=typed, interface="ISketch")
        same(f"{key}.sketch_view_identity", mapped_sketch, f"{source}.sketch_view")
        same(f"{key}.sketch_reverse_identity", reversed_sketch, f"{source}.sketch")
        same(f"{key}.sketch_reverse_feature_identity", reversed_sketch, f"{source}.feature_sketch")
        same(f"{key}.sketch_mapped_feature_identity", sketch, f"{source}.feature_view_sketch")
        if interface == "ISketchPoint":
            for coordinate in ("x", "y", "z"):
                take(f"{key}.{coordinate}", lambda entity, axis=coordinate: getattr(
                    _early_bound(entity, "ISketchPoint"), axis.upper()), key)
        else:
            kind = take(f"{key}.type", lambda entity: _early_bound(entity, "ISketchSegment").GetType(),
                        key)
            take(f"{key}.construction", lambda entity: _early_bound(
                entity, "ISketchSegment").ConstructionGeometry, key)
            # Dispatch only by the actual documented segment kind. A failed/null
            # kind is not coerced to a line; the other field receipts still stand.
            if type(values[kind]) is int and values[kind] == 0:  # swSketchLINE
                for end, method in (("start", "GetStartPoint2"), ("end", "GetEndPoint2")):
                    point = object_read(f"{key}.{end}", lambda entity, getter=method: getattr(
                        _early_bound(entity, "ISketchLine"), getter)(), key,
                        typed=typed, interface="ISketchPoint")
                    member(point, "ISketchPoint", space=space, typed=typed)
            elif type(values[kind]) is int and values[kind] == 1:  # swSketchARC
                take(f"{key}.is_circle", lambda entity: _early_bound(entity, "ISketchArc").IsCircle(),
                     key)
                take(f"{key}.radius", lambda entity: _early_bound(entity, "ISketchArc").GetRadius(),
                     key)
                center = object_read(f"{key}.center", lambda entity: _early_bound(
                    entity, "ISketchArc").GetCenterPoint2(), key,
                    typed=typed, interface="ISketchPoint")
                member(center, "ISketchPoint", space=space, typed=typed)
            else:
                reads[f"{key}.geometry"] = {
                    "skipped": f"{kind} does not identify an available line or arc interface",
                }

    take("source.model", lambda: model, handle=True)
    take("view.handle", lambda: view, handle=True)
    take("dimension.imported_display", lambda: display, handle=True)
    take("source.path", lambda source: _early_bound(source, "IModelDoc2").GetPathName(), "source.model")
    take("source.type", lambda source: _early_bound(source, "IModelDoc2").GetType(), "source.model")
    take("source.configuration_manager", lambda source: _early_bound(
        source, "IModelDoc2").ConfigurationManager, "source.model", handle=True)
    take("source.active_configuration", lambda manager: _early_bound(
        manager, "IConfigurationManager").ActiveConfiguration, "source.configuration_manager", handle=True)
    take("source.configuration", lambda configuration: _early_bound(
        configuration, "IConfiguration").Name, "source.active_configuration")
    take("source.extension", lambda source: _early_bound(source, "IModelDoc2").Extension,
         "source.model", handle=True)
    take("view.orientation", lambda target: _early_bound(target, "IView").GetOrientationName(),
         "view.handle")
    take("view.configuration", lambda target: _early_bound(target, "IView").ReferencedConfiguration,
         "view.handle")
    take("view.source_document", lambda target: _early_bound(target, "IView").ReferencedDocument,
         "view.handle", handle=True)
    take("view.source_path", lambda source: _early_bound(source, "IModelDoc2").GetPathName(),
         "view.source_document")
    take("view.source_type", lambda source: _early_bound(source, "IModelDoc2").GetType(),
         "view.source_document")
    take("view.referenced_model_name", lambda target: _early_bound(target, "IView").GetReferencedModelName(),
         "view.handle")
    same("view.source_identity", "view.source_document", "source.model")

    feature_name, dimension_name = SOURCE_DIMENSIONS[label]
    take("source.feature", lambda source: _early_bound(source, "IPartDoc").FeatureByName(feature_name),
         "source.model", handle=True)
    take("source.feature_name", lambda feature: _early_bound(feature, "IFeature").Name,
         "source.feature")
    take("source.feature_type", lambda feature: _early_bound(feature, "IFeature").GetTypeName2(),
         "source.feature")
    take("source.sketch", lambda feature: _early_bound(feature, "IFeature").GetSpecificFeature2(),
         "source.feature", handle=True)
    # Independently read the feature's specific object for owner comparisons.
    # ISketch has NO GetFeature getter; never invent a reverse feature lookup.
    take("source.feature_sketch", lambda feature: _early_bound(feature, "IFeature").GetSpecificFeature2(),
         "source.feature", handle=True)
    same("source.sketch_feature_identity", "source.sketch", "source.feature_sketch")
    forward("source.sketch_view", "source.sketch")
    reverse("source.sketch_reverse", "source.sketch_view")
    same("source.sketch_reverse_identity", "source.sketch_reverse", "source.sketch")
    forward("source.feature_view", "source.feature")
    reverse("source.feature_reverse", "source.feature_view")
    same("source.feature_reverse_identity", "source.feature_reverse", "source.feature")
    take("source.feature_view_sketch", lambda feature: _early_bound(
        feature, "IFeature").GetSpecificFeature2(), "source.feature_view", handle=True)
    same("source.sketch_view_feature_identity", "source.sketch_view", "source.feature_view_sketch")

    take("dimension.named_source", lambda feature: _named_dimensions(
        adapter, feature_name, {dimension_name}, feature=feature),
         "source.feature", handle=True)
    take("dimension.source_display", lambda named: named[dimension_name][0],
         "dimension.named_source", handle=True)
    take("dimension.source_native", lambda named: named[dimension_name][1],
         "dimension.named_source", handle=True)
    take("dimension.imported_native", lambda imported: _early_bound(
        imported, "IDisplayDimension").GetDimension2(0), "dimension.imported_display", handle=True)
    for context in ("source", "imported"):
        native = f"dimension.{context}_native"
        native_display = f"dimension.{context}_display"
        take(f"dimension.{context}_full_name", lambda dimension: _early_bound(
            dimension, "IDimension").FullName, native)
        take(f"dimension.{context}_type2", lambda item: _early_bound(
            item, "IDisplayDimension").Type2, native_display)
        take(f"dimension.{context}_selection_name", lambda item: _early_bound(
            item, "IDisplayDimension").GetNameForSelection(), native_display)
        owner = take(f"dimension.{context}_owner", lambda dimension: _early_bound(
            dimension, "IDimension").GetFeatureOwner(), native, handle=True)
        same(f"dimension.{context}_owner_identity", owner, "source.feature")
        take(f"dimension.{context}_owner_name", lambda feature: _early_bound(
            feature, "IFeature").Name, owner)
        take(f"dimension.{context}_owner_type", lambda feature: _early_bound(
            feature, "IFeature").GetTypeName2(), owner)
        owner_sketch = take(f"dimension.{context}_owner_sketch", lambda feature: _early_bound(
            feature, "IFeature").GetSpecificFeature2(), owner, handle=True)
        same(f"dimension.{context}_owner_sketch_identity", owner_sketch, "source.sketch")
        same(f"dimension.{context}_self_identity", native, native)
        take(f"dimension.{context}_annotation", lambda item: _early_bound(
            item, "IDisplayDimension").GetAnnotation(), native_display, handle=True)
        take(f"dimension.{context}_annotation_owner", lambda annotation: _early_bound(
            annotation, "IAnnotation").Owner, f"dimension.{context}_annotation", handle=True)
        take(f"dimension.{context}_annotation_owner_type", lambda annotation: _early_bound(
            annotation, "IAnnotation").OwnerType, f"dimension.{context}_annotation")
        if context == "source":
            owner_view = forward(f"dimension.{context}_owner_view", owner)
            reverse(f"dimension.{context}_owner_reverse", owner_view)
        else:
            owner_source = reverse(f"dimension.{context}_owner_reverse", owner)
            forward(f"dimension.{context}_owner_view", owner_source)
        same(f"dimension.{context}_owner_reverse_identity",
             f"dimension.{context}_owner_reverse", "source.feature")
    same("dimension.source_import_identity", "dimension.source_native", "dimension.imported_native")
    same("dimension.import_source_identity", "dimension.imported_native", "dimension.source_native")
    same("dimension.owner_identity", "dimension.source_owner", "dimension.imported_owner")
    same("dimension.imported_view_owner_identity", "dimension.imported_owner", "source.feature_view")
    same("dimension.source_annotation_owner_identity", "dimension.source_annotation_owner", "source.model")

    take("annotation.handle", lambda imported: _early_bound(
        imported, "IDisplayDimension").GetAnnotation(), "dimension.imported_display", handle=True)
    for name, getter in (
        ("count", lambda annotation: annotation.GetAttachedEntityCount3()),
        ("types", lambda annotation: annotation.GetAttachedEntityTypes()),
        ("dangling", lambda annotation: annotation.IsDangling()),
        ("visible", lambda annotation: annotation.Visible),
        ("owner_type", lambda annotation: annotation.OwnerType),
    ):
        take(f"annotation.{name}", lambda annotation, read=getter: read(
            _early_bound(annotation, "IAnnotation")), "annotation.handle")
    take("annotation.owner", lambda annotation: _early_bound(annotation, "IAnnotation").Owner,
         "annotation.handle", handle=True)
    same("annotation.owner_view_identity", "annotation.owner", "view.handle")

    take("source.segments", lambda sketch: _early_bound(sketch, "ISketch").GetSketchSegments(),
         "source.sketch", handle=True)
    if label == THICKNESS:
        take("source.members", lambda sketch: _early_bound(sketch, "ISketch").GetSketchPoints2(),
             "source.sketch", handle=True)
    else:
        # Reuse the actual segment array without rereading or choosing a circle.
        take("source.members", lambda segments: segments, "source.segments", handle=True)
    take("attachment.members", lambda annotation: _early_bound(
        annotation, "IAnnotation").GetAttachedEntities3(), "annotation.handle", handle=True)
    sources = inventory("source.members")
    attachments = inventory("attachment.members")
    segments = inventory("source.segments")
    interface = "ISketchPoint" if label == THICKNESS else "ISketchSegment"
    for key in sources or ():
        member(key, interface, space="source")
    attachment_interfaces: list[tuple[str | None, str]] = []
    for index, key in enumerate(attachments or ()):
        kind_key = take(f"{key}.attached_type", lambda kinds: kinds[index], "annotation.types")
        kind = values[kind_key]
        # GetAttachedEntityTypes declares the actual incoming interface, not the
        # dimension label. Never send a sketch DISPID to an unexpected edge.
        actual_interface = None
        if type(kind) is int:
            if kind in (11, 25):  # swSelSKETCHPOINTS / swSelEXTSKETCHPOINTS
                actual_interface = "ISketchPoint"
            elif kind in (10, 24):  # swSelSKETCHSEGS / swSelEXTSKETCHSEGS
                actual_interface = "ISketchSegment"
        attachment_interfaces.append((actual_interface, kind_key))
        member(key, actual_interface, space="view", kind_key=kind_key)
    mapped = None if sources is None else [
        forward(f"view.members.{index}", key) for index, key in enumerate(sources)
    ]
    normalized = None if attachments is None else [
        reverse(f"normalized.members.{index}", key) for index, key in enumerate(attachments)
    ]
    roundtrips = None if normalized is None else [
        forward(f"roundtrip.members.{index}", key) for index, key in enumerate(normalized)
    ]
    for key in mapped or ():
        member(key, interface, space="view")
    for keys, space in ((normalized, "source"), (roundtrips, "view")):
        for key, (actual_interface, kind_key) in zip(keys or (), attachment_interfaces, strict=True):
            member(key, actual_interface, space=space, kind_key=kind_key)

    endpoints: list[str] | None = None if segments is None else []
    for key in segments or ():
        member(key, "ISketchSegment", space="source")
        for end in ("start", "end"):
            point = f"{key}.{end}"
            if point in reads:
                endpoints.append(point)
    for name, left, right, left_name, right_name in (
        ("source_self_distinct", sources, sources, "source.members", "source.members"),
        ("view_self_distinct", mapped, mapped, "view.members", "view.members"),
        ("attachment_self_distinct", attachments, attachments, "attachment.members", "attachment.members"),
        ("attachment_source", attachments, sources, "attachment.members", "source.members"),
        ("attachment_view", attachments, mapped, "attachment.members", "view.members"),
        ("normalized_source", normalized, sources, "normalized.members", "source.members"),
        ("roundtrip_attachment", roundtrips, attachments, "roundtrip.members", "attachment.members"),
        ("endpoint_source", endpoints, sources, "source.segments", "source.members"),
    ):
        matrix(name, left, right, left_name=left_name, right_name=right_name)

    # Keep the raw transport evidence above intact. This independent, explicitly
    # bound chain mirrors the existing supplier attachment correspondence path;
    # it diagnoses wrapper identity separately from drawing/model context.
    bound("typed.source.model", "source.model", "IModelDoc2")
    bound("typed.source.part", "source.model", "IPartDoc")
    bound("typed.view.handle", "view.handle", "IView")
    object_read("typed.source.extension", lambda source: source.Extension,
                "typed.source.model", typed=True, interface="IModelDocExtension")
    object_read("typed.source.feature", lambda part: part.FeatureByName(feature_name),
                "typed.source.part", typed=True, interface="IFeature")
    for key in ("typed.source.sketch", "typed.source.feature_sketch"):
        object_read(key, lambda feature: feature.GetSpecificFeature2(),
                    "typed.source.feature", typed=True, interface="ISketch")
    take("typed.source.feature_name", lambda feature: feature.Name, "typed.source.feature")
    take("typed.source.feature_type", lambda feature: feature.GetTypeName2(), "typed.source.feature")
    same("typed.source.sketch_feature_identity", "typed.source.sketch", "typed.source.feature_sketch")
    forward("typed.source.sketch_view", "typed.source.sketch", typed=True, interface="ISketch")
    reverse("typed.source.sketch_reverse", "typed.source.sketch_view", typed=True, interface="ISketch")
    same("typed.source.sketch_reverse_identity", "typed.source.sketch_reverse", "typed.source.sketch")
    forward("typed.source.feature_view", "typed.source.feature", typed=True, interface="IFeature")
    reverse("typed.source.feature_reverse", "typed.source.feature_view", typed=True, interface="IFeature")
    same("typed.source.feature_reverse_identity", "typed.source.feature_reverse", "typed.source.feature")
    object_read("typed.source.feature_view_sketch", lambda feature: feature.GetSpecificFeature2(),
                "typed.source.feature_view", typed=True, interface="ISketch")
    same("typed.source.sketch_view_feature_identity",
         "typed.source.sketch_view", "typed.source.feature_view_sketch")

    bound("typed.dimension.imported_display", "dimension.imported_display", "IDisplayDimension")
    take("typed.dimension.named_source", lambda feature: _named_dimensions(
        adapter, feature_name, {dimension_name}, feature=feature),
         "typed.source.feature", handle=True)
    object_read("typed.dimension.source_display", lambda named: named[dimension_name][0],
                "typed.dimension.named_source", typed=True, interface="IDisplayDimension")
    object_read("typed.dimension.source_native", lambda named: named[dimension_name][1],
                "typed.dimension.named_source", typed=True, interface="IDimension")
    object_read("typed.dimension.imported_native", lambda imported: imported.GetDimension2(0),
                "typed.dimension.imported_display", typed=True, interface="IDimension")
    for context in ("source", "imported"):
        native = f"typed.dimension.{context}_native"
        native_display = f"typed.dimension.{context}_display"
        take(f"typed.dimension.{context}_full_name", lambda dimension: dimension.FullName, native)
        take(f"typed.dimension.{context}_type2", lambda item: item.Type2, native_display)
        owner = object_read(f"typed.dimension.{context}_owner",
                            lambda dimension: dimension.GetFeatureOwner(), native,
                            typed=True, interface="IFeature")
        take(f"typed.dimension.{context}_owner_name", lambda feature: feature.Name, owner)
        take(f"typed.dimension.{context}_owner_type", lambda feature: feature.GetTypeName2(), owner)
        same(f"typed.dimension.{context}_owner_identity", owner, "typed.source.feature")
        same(f"typed.dimension.{context}_self_identity", native, native)
        owner_sketch = object_read(f"typed.dimension.{context}_owner_sketch",
                                   lambda feature: feature.GetSpecificFeature2(), owner,
                                   typed=True, interface="ISketch")
        same(f"typed.dimension.{context}_owner_sketch_identity", owner_sketch, "typed.source.sketch")
        if context == "source":
            owner_view = forward(f"typed.dimension.{context}_owner_view", owner,
                                 typed=True, interface="IFeature")
            reverse(f"typed.dimension.{context}_owner_reverse", owner_view,
                    typed=True, interface="IFeature")
        else:
            owner_source = reverse(f"typed.dimension.{context}_owner_reverse", owner,
                                   typed=True, interface="IFeature")
            forward(f"typed.dimension.{context}_owner_view", owner_source,
                    typed=True, interface="IFeature")
        same(f"typed.dimension.{context}_owner_reverse_identity",
             f"typed.dimension.{context}_owner_reverse", "typed.source.feature")
    same("typed.dimension.source_import_identity",
         "typed.dimension.source_native", "typed.dimension.imported_native")
    same("typed.dimension.import_source_identity",
         "typed.dimension.imported_native", "typed.dimension.source_native")
    same("typed.dimension.owner_identity", "typed.dimension.source_owner", "typed.dimension.imported_owner")
    same("typed.dimension.imported_view_owner_identity",
         "typed.dimension.imported_owner", "typed.source.feature_view")

    object_read("typed.annotation", lambda imported: imported.GetAnnotation(),
                "typed.dimension.imported_display", typed=True, interface="IAnnotation")
    take("typed.annotation.types", lambda annotation: annotation.GetAttachedEntityTypes(),
         "typed.annotation")
    take("typed.annotation.count", lambda annotation: annotation.GetAttachedEntityCount3(),
         "typed.annotation")
    take("typed.source.inventory", lambda sketch: (
        sketch.GetSketchPoints2() if label == THICKNESS else sketch.GetSketchSegments()
    ), "typed.source.sketch", handle=True)
    take("typed.attachment.inventory", lambda annotation: annotation.GetAttachedEntities3(),
         "typed.annotation", handle=True)
    typed_source_raw = inventory("typed.source.inventory")
    typed_attachment_raw = inventory("typed.attachment.inventory")
    typed_sources = None if typed_source_raw is None else [
        bound(f"typed.source.members.{index}", key, interface)
        for index, key in enumerate(typed_source_raw)
    ]
    typed_mapped = None if typed_sources is None else [
        forward(f"typed.view.members.{index}", key, typed=True, interface=interface)
        for index, key in enumerate(typed_sources)
    ]
    typed_attachments: list[str] | None = None if typed_attachment_raw is None else []
    typed_normalized: list[str] | None = None if typed_attachment_raw is None else []
    typed_roundtrips: list[str] | None = None if typed_attachment_raw is None else []
    for index, key in enumerate(typed_attachment_raw or ()):
        kind_key = take(f"typed.attachment.members.{index}.attached_type",
                        lambda kinds: kinds[index], "typed.annotation.types")
        kind = values[kind_key]
        actual_interface = None
        if type(kind) is int:
            if kind in (11, 25):  # swSelSKETCHPOINTS / swSelEXTSKETCHPOINTS
                actual_interface = "ISketchPoint"
            elif kind in (10, 24):  # swSelSKETCHSEGS / swSelEXTSKETCHSEGS
                actual_interface = "ISketchSegment"
        attached = bound(f"typed.attachment.members.{index}", key, actual_interface, kind_key=kind_key)
        normalized_key = reverse(f"typed.normalized.members.{index}", attached,
                                 typed=True, interface=actual_interface)
        roundtrip = forward(f"typed.roundtrip.members.{index}", normalized_key,
                            typed=True, interface=actual_interface)
        typed_attachments.append(attached)
        typed_normalized.append(normalized_key)
        typed_roundtrips.append(roundtrip)
        for member_key, space in ((attached, "view"), (normalized_key, "source"), (roundtrip, "view")):
            member(member_key, actual_interface, space=space, kind_key=kind_key, typed=True)
    for keys, space in ((typed_sources, "source"), (typed_mapped, "view")):
        for key in keys or ():
            member(key, interface, space=space, typed=True)
    for name, left, right, left_name, right_name in (
        ("typed_source_self_distinct", typed_sources, typed_sources,
         "typed.source.members", "typed.source.members"),
        ("typed_view_self_distinct", typed_mapped, typed_mapped,
         "typed.view.members", "typed.view.members"),
        ("typed_attachment_self_distinct", typed_attachments, typed_attachments,
         "typed.attachment.members", "typed.attachment.members"),
        ("typed_attachment_source", typed_attachments, typed_sources,
         "typed.attachment.members", "typed.source.members"),
        ("typed_attachment_view", typed_attachments, typed_mapped,
         "typed.attachment.members", "typed.view.members"),
        ("typed_normalized_source", typed_normalized, typed_sources,
         "typed.normalized.members", "typed.source.members"),
        ("typed_roundtrip_attachment", typed_roundtrips, typed_attachments,
         "typed.roundtrip.members", "typed.attachment.members"),
    ):
        matrix(name, left, right, left_name=left_name, right_name=right_name)

    # IAnnotation is a documented generic correspondence input. IDimension is
    # NOT assumed to be one: bridge only through an actual display annotation.
    object_read("typed.annotation.source", lambda source: source.GetAnnotation(),
                "typed.dimension.source_display", typed=True, interface="IAnnotation")
    for typed, prefix, source_annotation, imported_annotation, dimension_prefix in (
        (False, "annotation", "dimension.source_annotation", "dimension.imported_annotation", "dimension"),
        (True, "typed.annotation", "typed.annotation.source", "typed.annotation", "typed.dimension"),
    ):
        mapped_annotation = forward(f"{prefix}.source_forward", source_annotation,
                                    typed=typed, interface="IAnnotation")
        reversed_annotation = reverse(f"{prefix}.imported_reverse", imported_annotation,
                                      typed=typed, interface="IAnnotation")
        same(f"{prefix}.source_forward_identity", mapped_annotation, imported_annotation)
        same(f"{prefix}.imported_reverse_identity", reversed_annotation, source_annotation)
        for direction, annotation, target in (
            ("source_forward", mapped_annotation, "imported"),
            ("imported_reverse", reversed_annotation, "source"),
        ):
            key = f"{prefix}.{direction}"
            kind_key = take(f"{key}_type", lambda item: _early_bound(item, "IAnnotation").GetType(),
                            annotation)
            kind = values[kind_key]
            if type(kind) is int and kind == 4:  # swAnnotationType_e.swDisplayDimension
                bridge_display = object_read(
                    f"{key}_display", lambda item: _early_bound(
                        item, "IAnnotation").GetSpecificAnnotation(),
                    annotation, typed=typed, interface="IDisplayDimension",
                )
                bridge_native = object_read(
                    f"{key}_native", lambda item: _early_bound(
                        item, "IDisplayDimension").GetDimension2(0),
                    bridge_display, typed=typed, interface="IDimension",
                )
            else:
                reason = (
                    f"{kind_key} unavailable" if kind is unavailable or kind is None
                    else f"{kind_key} does not identify an IDisplayDimension"
                )
                bridge_display, bridge_native = f"{key}_display", f"{key}_native"
                for unavailable_key in (bridge_display, bridge_native):
                    values[unavailable_key] = unavailable
                    reads[unavailable_key] = {"skipped": reason}
                    if typed:
                        values[f"{unavailable_key}.raw"] = unavailable
                        reads[f"{unavailable_key}.raw"] = {"skipped": reason}
            take(f"{key}_native_full_name", lambda item: _early_bound(
                item, "IDimension").FullName, bridge_native)
            same(f"{key}_display_identity", bridge_display, f"{dimension_prefix}.{target}_display")
            same(f"{key}_native_identity", bridge_native, f"{dimension_prefix}.{target}_native")
    return {"label": label, "reads": reads, "matrices": matrices}


@_telemetry.traced("drawing.assert_supplier_washer_dimensions")
def assert_supplier_washer_dimensions(
    adapter: Any, views: dict[str, Any], references: tuple[_WasherReference, ...], *,
    axis: Literal["y", "z"], bore_mm: float, outer_mm: float, thickness_mm: float,
    units: Literal["in", "mm"], precision: Mapping[str, int],
    bands: Mapping[str, tuple[float, float, str]],
) -> None:
    """Reacquire displays, source entities and final solid rims after rebuild."""
    if len(references) != 3 or {reference.label for reference in references} != {
        OUTER_DIAMETER, BORE_DIAMETER, THICKNESS,
    }:
        raise RuntimeError("supplier washer must export exactly OD, bore and thickness")
    face = views["*Top" if axis == "y" else "*Front"]
    side = views["*Front" if axis == "y" else "*Top"]
    model = _early_bound(face, "IView").ReferencedDocument
    if model is None:
        raise RuntimeError("supplier washer drawing has no referenced source part")
    assert_supplier_washer_body(model, axis=axis, bore_mm=bore_mm,
                               outer_mm=outer_mm, thickness_mm=thickness_mm)
    face_edges = scan_view_edges(face, label="settled supplier washer face rims")
    side_edges = scan_view_edges(side, label="settled supplier washer axial rims")
    # Body-backed proof remains independent of construction-sketch attachments.
    face_rims = {
        label: _rim(face_edges, axis=axis, station_mm=thickness_mm,
                    diameter_mm=diameter, label=label)
        for label, diameter in ((OUTER_DIAMETER, outer_mm), (BORE_DIAMETER, bore_mm))
    }
    for station in (0.0, thickness_mm):
        _rim(side_edges, axis=axis, station_mm=station, diameter_mm=outer_mm, label=THICKNESS)
    current: dict[str, Any] = {}
    for orientation, view in views.items():
        expected = [reference for reference in references
                    if int(adapter.swApp.IsSame(reference.view, view)) == 1]
        visible = _visible_dimensions(view)
        required_count = 2 if orientation == ("*Top" if axis == "y" else "*Front") else (
            1 if orientation == ("*Front" if axis == "y" else "*Top") else 0
        )
        if len(expected) != required_count or len(visible) != required_count:
            raise RuntimeError(f"supplier washer {orientation} exports {len(visible)} dimensions, expected {required_count}")
        for reference in expected:
            matches = [display for display in visible
                       if str(display.GetNameForSelection() or "") == reference.selection_name]
            if len(matches) != 1:
                raise RuntimeError(f"{reference.label}: settled native display census failed")
            display = matches[0]
            native = _early_bound(display.GetDimension2(0), "IDimension")
            if str(native.FullName or "") != reference.full_name:
                raise RuntimeError(f"{reference.label}: settled display resolves to another native dimension")
            current[reference.label] = display
    for reference in references:
        display = current[reference.label]
        assert_supplier_reference_dimension(
            adapter, display, label=reference.label, units=units,
            precision=precision[reference.label], expected_mm=reference.expected_mm,
            presentation=reference.presentation, callout=reference.callout,
        )
        if reference.imported:
            try:
                assert_supplier_washer_source_attachment(
                    adapter, model, display, label=reference.label, axis=axis,
                    bore_mm=bore_mm, outer_mm=outer_mm, thickness_mm=thickness_mm, visible=True,
                )
            except Exception as error:
                try:
                    message = "supplier washer source attachment readback: " + json.dumps(
                        _source_attachment_failure_readback(
                            adapter, model, reference.view, display, label=reference.label,
                        ),
                        sort_keys=True, default=repr,
                    )
                except BaseException as diagnostic_error:
                    try:
                        error.add_note(
                            "supplier washer source attachment readback failed: "
                            f"{type(diagnostic_error).__name__}: {diagnostic_error}"
                        )
                    except BaseException:
                        pass
                else:
                    for destination in ("exception note", "telemetry log"):
                        try:
                            if destination == "exception note":
                                error.add_note(message)
                            else:
                                _telemetry.info(message)
                        except BaseException as diagnostic_error:
                            try:
                                error.add_note(
                                    "supplier washer source attachment readback reporting failed: "
                                    f"{type(diagnostic_error).__name__}: {diagnostic_error}"
                                )
                            except BaseException:
                                pass
                raise
        else:
            _assert_rim(adapter, display, face_rims[reference.label], label=reference.label)
        assert_supplier_washer_band(
            display, nominal_mm=reference.expected_mm, band=bands.get(reference.label),
            precision=precision[reference.label], label=reference.label,
        )


_WASHER_ORIENTATIONS = frozenset(("*Front", "*Top", "*Right", "*Isometric"))


def _native_path(value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{label}: native document path is missing")
    return Path(value).resolve()


def _saved_washer_identity(model: Any, path: Path) -> Any:
    model = _early_bound(model, "IModelDoc2")
    if _native_path(model.GetPathName(), label="saved washer drawing") != path:
        raise RuntimeError("saved washer drawing resolved to another document path")
    if type(kind := model.GetType()) is not int or kind != 3:  # swDocDRAWING
        raise RuntimeError("saved washer drawing is not a native drawing document")
    return model


def _saved_display_readback(display: Any) -> dict[str, Any]:
    """Read telemetry independently of strict predicates; never repair a field."""
    result: dict[str, Any] = {"source_native_identity": None}
    native = annotation = tolerance = None
    try:
        native = _early_bound(display.GetDimension2(0), "IDimension")
    except Exception as error:
        result["native_dimension_read_error"] = f"{type(error).__name__}: {error}"
    try:
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    except Exception as error:
        result["annotation_read_error"] = f"{type(error).__name__}: {error}"
    try:
        tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
    except Exception as error:
        result["tolerance_read_error"] = f"{type(error).__name__}: {error}"
    for field, read in (
        ("selection_name", lambda: display.GetNameForSelection()),
        ("full_name", lambda: native.FullName),
        ("system_value", lambda: native.SystemValue),
        ("units", lambda: display.GetUnits()),
        ("precision", lambda: display.GetPrimaryPrecision2()),
        ("tolerance_precision", lambda: display.GetPrimaryTolPrecision2()),
        ("prefix", lambda: display.GetText(1)),
        ("suffix", lambda: display.GetText(2)),
        ("below", lambda: display.GetText(4)),
        ("use_document_units", lambda: display.GetUseDocUnits()),
        ("fraction_base", lambda: display.GetFractionBase()),
        ("fraction_value", lambda: display.GetFractionValue()),
        ("round_to_fraction", lambda: display.GetRoundToFraction()),
        ("parentheses", lambda: display.ShowParenthesis),
        ("override", lambda: display.GetOverride()),
        ("show_value", lambda: display.ShowDimensionValue),
        ("attachment_count", lambda: annotation.GetAttachedEntityCount3()),
        ("attachment_types", lambda: list(annotation.GetAttachedEntityTypes() or ())),
        ("dangling", lambda: annotation.IsDangling()),
        ("tolerance_type", lambda: tolerance.Type),
        ("tolerance_min", lambda: tolerance.GetMinValue() if tolerance.Type else None),
        ("tolerance_max", lambda: tolerance.GetMaxValue() if tolerance.Type else None),
    ):
        try:
            result[field] = read()
        except Exception as error:
            result[field] = {"read_error": f"{type(error).__name__}: {error}"}
    return result


def _supplier_washer_proof(
    adapter: Any, views: dict[str, Any], references: tuple[_WasherReference, ...], *,
    axis: Literal["y", "z"], bore_mm: float, outer_mm: float, thickness_mm: float,
    units: Literal["in", "mm"], precision: Mapping[str, int],
    bands: Mapping[str, tuple[float, float, str]],
) -> SupplierWasherProof:
    """Capture source path/configurations before the authoring views close.

    The saved reader never activates, rebuilds, dresses or saves a document.
    Only the drawing it opens is closed; the builder owns source preservation.
    """
    if set(views) != _WASHER_ORIENTATIONS:
        raise RuntimeError("supplier washer proof requires exactly four standard views")
    source = _early_bound(views["*Front"], "IView").ReferencedDocument
    if source is None:
        raise RuntimeError("supplier washer proof has no authoring source part")
    source = _early_bound(source, "IModelDoc2")
    source_path = _native_path(source.GetPathName(), label="authoring washer source")
    if type(kind := source.GetType()) is not int or kind != 1:  # swDocPART
        raise RuntimeError("supplier washer proof source is not a native part")
    configurations: dict[str, str] = {}
    for orientation, raw in views.items():
        view = _early_bound(raw, "IView")
        model = view.ReferencedDocument
        configuration = view.ReferencedConfiguration
        identity = None if model is None else adapter.swApp.IsSame(model, source)
        if (
            view.GetOrientationName() != orientation
            or type(identity) is not int or identity != 1
            or _native_path(view.GetReferencedModelName(), label=orientation) != source_path
            or not isinstance(configuration, str) or not configuration.strip()
        ):
            raise RuntimeError(f"{orientation}: authoring washer source/view identity differs")
        configurations[orientation] = configuration
    # The saved callback retains only scalar reference expectations, never an
    # authoring IView or source COM handle that closing the drawing may unload.
    saved_references = tuple(
        (_early_bound(reference.view, "IView").GetOrientationName(),
         reference.label, reference.expected_mm, reference.imported, reference.callout)
        for reference in references
    )
    if any(reference[0] not in configurations for reference in saved_references):
        raise RuntimeError("supplier washer reference has no captured standard orientation")
    # Freeze expectations independently of both caller mappings and reopened state.
    precision, bands = dict(precision), dict(bands)

    def settled_check() -> None:
        assert_supplier_washer_dimensions(
            adapter, views, references, axis=axis, bore_mm=bore_mm,
            outer_mm=outer_mm, thickness_mm=thickness_mm, units=units,
            precision=precision, bands=bands,
        )

    @_telemetry.traced("drawing.saved_supplier_washer_dimensions")
    def saved_check(saved_adapter: Any, path: Path) -> None:
        saved_path = Path(path).resolve()
        if saved_path.suffix.lower() != ".slddrw" or not saved_path.is_file():
            raise ValueError("saved washer proof requires an existing native SLDDRW")
        app = _early_bound(saved_adapter.swApp, "ISldWorks")
        path_string = str(saved_path)
        if app.GetOpenDocumentByName(path_string) is not None:
            raise RuntimeError("finalize and close the washer drawing before saved proof")
        # The finalizer has closed this drawing. Drop its adapter-held wrapper
        # before OpenDoc6 so a stale document cannot survive the saved reopen.
        saved_adapter.currentModel = None
        with saved_path.open("rb") as saved_file:
            before = hashlib.file_digest(saved_file, "sha256").hexdigest()
        opened_model = None
        primary: BaseException | None = None
        receipt: dict[str, Any] = dict(
            drawing_path=str(saved_path), sha256=before,
            source_resident_before_open=app.GetOpenDocumentByName(str(source_path)) is not None,
        )
        try:
            # Generated OpenDoc6 appends the two native [out] LONGs. No BYREF
            # variants, ViewOnly/detailing mode, activation or fresh adapter model.
            opened = app.OpenDoc6(path_string, 3, 1 | 2, "", 0, 0)
            if not isinstance(opened, tuple) or len(opened) != 3:
                raise RuntimeError("saved washer OpenDoc6 did not return (model, errors, warnings)")
            opened_model, errors, warnings = opened
            receipt.update(open_errors=errors, open_warnings=warnings)
            if type(errors) is not int or type(warnings) is not int:
                raise RuntimeError("saved washer OpenDoc6 returned non-native error/warning codes")
            if opened_model is None or errors != 0:
                raise RuntimeError(f"saved washer native open failed ({errors=}, {warnings=})")
            model = _saved_washer_identity(opened_model, saved_path)
            read_only = model.IsOpenedReadOnly()
            receipt["read_only"] = read_only
            if read_only is not True:
                raise RuntimeError("saved washer drawing did not open read-only")
            # Closing the finalizer's drawing can unload its hidden source.
            # The saved drawing autoloads that source; reacquire its live model
            # from the captured path, never from a view or an old COM handle.
            loaded_source = app.GetOpenDocumentByName(str(source_path))
            if loaded_source is None:
                raise RuntimeError("saved washer source context was not loaded by the drawing")
            loaded_source = _early_bound(loaded_source, "IModelDoc2")
            receipt["source_path"] = loaded_source.GetPathName()
            if _native_path(receipt["source_path"], label="saved washer source") != source_path:
                raise RuntimeError("saved washer source path changed")
            receipt["source_type"] = kind = loaded_source.GetType()
            if type(kind) is not int or kind != 1:
                raise RuntimeError("saved washer source context is not a native part")
            receipt["source_read_only"] = loaded_source.IsOpenedReadOnly()
            if receipt["source_read_only"] is not True:
                raise RuntimeError("saved washer source context is not read-only")
            try:
                receipt["source_save_flag"] = loaded_source.GetSaveFlag()
            except Exception as error:
                receipt["source_save_flag"] = {"read_error": f"{type(error).__name__}: {error}"}
                raise
            if receipt["source_save_flag"] is not False:
                raise RuntimeError("saved washer source context is dirty or has an unreadable save flag")
            sheets = tuple(_early_bound(model, "IDrawingDoc").GetViews() or ())
            if len(sheets) != 1:
                raise RuntimeError("saved washer drawing must contain exactly one sheet")
            sheet_views = tuple(sheets[0] or ())
            if len(sheet_views) != 5:  # first IView is the sheet, not a model view
                raise RuntimeError("saved washer drawing must contain exactly four model views")
            fresh: dict[str, Any] = {}
            view_receipts = []
            for raw in sheet_views[1:]:
                view = _early_bound(raw, "IView")
                orientation = view.GetOrientationName()
                if orientation not in configurations or orientation in fresh:
                    raise RuntimeError("saved washer view orientation is unexpected or duplicated")
                referenced = view.ReferencedDocument
                identity = None if referenced is None else app.IsSame(referenced, loaded_source)
                if type(identity) is not int or identity != 1:
                    raise RuntimeError(f"{orientation}: saved washer references another source identity")
                actual_path = _native_path(
                    _early_bound(referenced, "IModelDoc2").GetPathName(), label=orientation,
                )
                named_path = _native_path(view.GetReferencedModelName(), label=orientation)
                configuration = view.ReferencedConfiguration
                if actual_path != source_path or named_path != source_path:
                    raise RuntimeError(f"{orientation}: saved washer references another source path")
                if configuration != configurations[orientation]:
                    raise RuntimeError(f"{orientation}: saved washer source configuration changed")
                fresh[orientation] = view
                view_receipts.append(dict(
                    orientation=orientation, source_path=str(actual_path),
                    configuration=configuration, source_native_identity=identity,
                ))
            if set(fresh) != _WASHER_ORIENTATIONS:
                raise RuntimeError("saved washer standard view census differs")
            # SaveAs can rename a drawing-owned dimension's model component.
            # Rebind by source semantics or exact physical attachment, never by
            # the old document's names, displayed value or presentation text.
            displays = {orientation: _visible_dimensions(view)
                        for orientation, view in fresh.items()}
            receipt["views"] = view_receipts
            receipt["dimensions"] = []
            readbacks = {}
            for orientation, visible in displays.items():
                for display in visible:
                    row = _saved_display_readback(display)
                    row["orientation"] = orientation
                    receipt["dimensions"].append(row)
                    readbacks[id(display)] = row  # Telemetry index, not native identity proof.
            rim_scans: dict[str, ViewEdges] = {}
            fresh_references = []
            for orientation, label, expected_mm, imported, callout in saved_references:
                view = fresh[orientation]
                matches = []
                if imported:
                    feature_name, source_name = SOURCE_DIMENSIONS[label]
                    feature = _early_bound(loaded_source, "IPartDoc").FeatureByName(feature_name)
                    if feature is None:
                        raise RuntimeError(f"{label}: saved supplier source feature is missing")
                    source_display, source_native = _named_dimensions(
                        saved_adapter, feature_name, {source_name}, feature=feature,
                    )[source_name]
                    source_row = _saved_display_readback(source_display)
                    source_row["label"] = label
                    receipt.setdefault("source_dimensions", []).append(source_row)
                    _assert_supplier_washer_presentation(
                        source_display, label=label, units=units, precision=precision[label],
                        expected_mm=expected_mm, callout=callout,
                    )
                    for display in displays[orientation]:
                        raw = display.GetDimension2(0)
                        if raw is not None and str(
                            _early_bound(raw, "IDimension").FullName or ""
                        ).split("@")[:2] == [source_name, feature_name]:
                            native_identity = app.IsSame(raw, source_native)
                            readbacks[id(display)]["source_native_identity"] = native_identity
                            if type(native_identity) is not int or native_identity != 1:
                                raise RuntimeError(
                                    f"{label}: saved imported dimension is not its actual native source"
                                )
                            matches.append(display)
                else:
                    if orientation not in rim_scans:
                        rim_scans[orientation] = scan_view_edges(
                            view, label="saved supplier washer semantic rim lookup",
                        )
                    rim = _rim(
                        rim_scans[orientation], axis=axis, station_mm=thickness_mm,
                        diameter_mm=expected_mm, label=label,
                    )
                    for display in displays[orientation]:
                        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
                        attached = tuple(annotation.GetAttachedEntities3() or ())
                        if (
                            len(attached) == 1 and attached[0] is not None
                            and _is_same_attachment(saved_adapter, attached[0], rim, "EDGE")
                        ):
                            matches.append(display)
                if len(matches) != 1:
                    raise RuntimeError(
                        f"{label}: saved semantic native display census failed "
                        f"(found {len(matches)}, expected one)"
                    )
                fresh_reference = _reference(
                    matches[0], view, label, expected_mm,
                    imported=imported, callout=callout,
                )
                fresh_references.append(fresh_reference)
            assert_supplier_washer_dimensions(
                saved_adapter, fresh, tuple(fresh_references), axis=axis, bore_mm=bore_mm,
                outer_mm=outer_mm, thickness_mm=thickness_mm, units=units,
                precision=precision, bands=bands,
            )
        except BaseException as error:
            primary = error
            raise
        finally:
            cleanup_errors = []
            try:
                loaded = app.GetOpenDocumentByName(path_string)
                if loaded is not None:
                    loaded = _saved_washer_identity(loaded, saved_path)
                    identity = None if opened_model is None else app.IsSame(loaded, opened_model)
                    if opened_model is not None and (type(identity) is not int or identity != 1):
                        raise RuntimeError("saved washer cleanup refuses a different loaded identity")
                    title = loaded.GetTitle()
                    if not isinstance(title, str) or not title.strip():
                        raise RuntimeError("saved washer cleanup refuses an empty document title")
                    app.CloseDoc(title)  # VT_VOID, closes only this invocation's target
                    if app.GetOpenDocumentByName(path_string) is not None:
                        raise RuntimeError("saved washer proof document did not close")
            except Exception as error:
                cleanup_errors.append(error)
            try:
                with saved_path.open("rb") as saved_file:
                    after = hashlib.file_digest(saved_file, "sha256").hexdigest()
                receipt["sha256_after"] = after
                if after != before:
                    raise RuntimeError("saved washer proof changed the native drawing bytes")
            except Exception as error:
                cleanup_errors.append(error)
            if primary is not None:
                primary.add_note("saved washer native readback: " + json.dumps(
                    receipt, sort_keys=True, default=repr,
                ))
            if cleanup_errors:
                if primary is not None:
                    for error in cleanup_errors:
                        primary.add_note(f"saved washer cleanup: {type(error).__name__}: {error}")
                else:
                    error = cleanup_errors[0]
                    for extra in cleanup_errors[1:]:
                        error.add_note(f"saved washer cleanup: {type(extra).__name__}: {extra}")
                    error.add_note("saved washer native readback: " + json.dumps(
                        receipt, sort_keys=True, default=repr,
                    ))
                    raise error
        _telemetry.info("supplier washer saved native proof: " + json.dumps(
            receipt, sort_keys=True, default=repr,
        ))

    return SupplierWasherProof(settled_check, saved_check)


@_telemetry.traced("drawing.supplier_washer_dimensions")
def supplier_washer_dimensions(
    adapter: Any, views: dict[str, Any], *, axis: Literal["y", "z"],
    bore_mm: float, outer_mm: float, thickness_mm: float, units: Literal["in", "mm"],
    precision: Mapping[str, int], bands: Mapping[str, tuple[float, float, str]],
    bore_callout: str | None = None,
) -> SupplierWasherProof:
    """Import every banded size; author only bandless OD/ID physical refs."""
    if set(bands) not in ({THICKNESS}, {OUTER_DIAMETER, BORE_DIAMETER, THICKNESS}):
        raise ValueError("unsupported washer supplier band coverage")
    face = views["*Top" if axis == "y" else "*Front"]
    side = views["*Front" if axis == "y" else "*Top"]
    bounds = tuple(float(value) for value in face.GetOutline())
    center_y = (bounds[1] + bounds[3]) / 2.0
    positions = {
        OUTER_DIAMETER: (bounds[2] + 0.012, center_y + 0.012),
        BORE_DIAMETER: (bounds[2] + 0.012, center_y - 0.012),
    }
    side_bounds = tuple(float(value) for value in side.GetOutline())
    positions[THICKNESS] = (side_bounds[2] + 0.014, (side_bounds[1] + side_bounds[3]) / 2.0)
    values = {OUTER_DIAMETER: outer_mm, BORE_DIAMETER: bore_mm, THICKNESS: thickness_mm}
    references: list[_WasherReference] = []
    for view, labels in ((face, (OUTER_DIAMETER, BORE_DIAMETER)), (side, (THICKNESS,))):
        imported_labels = tuple(label for label in labels if label in bands)
        if not imported_labels:
            continue
        annotations = curate_view_dimensions(
            adapter, view,
            keep={SOURCE_DIMENSIONS[label][1]: positions[label] for label in imported_labels},
            view_label="supplier washer face" if view is face else "supplier washer thickness",
            dimensions_by_feature={
                SOURCE_DIMENSIONS[label][0]: tuple(SOURCE_DIMENSIONS[item][1]
                                                  for item in imported_labels
                                                  if SOURCE_DIMENSIONS[item][0] == SOURCE_DIMENSIONS[label][0])
                for label in imported_labels
            },
        )
        named = {dimension_name(adapter, annotation): annotation for annotation in annotations}
        for label in imported_labels:
            annotation = named[SOURCE_DIMENSIONS[label][1]]
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            _persist_imported_units(
                adapter, view, display, label=label, units=units,
                precision=precision[label], expected_mm=values[label],
                callout=bore_callout if label == BORE_DIAMETER else None,
            )
            references.append(_reference(display, view, label, values[label], imported=True,
                                         callout=bore_callout if label == BORE_DIAMETER else None))
    unbanded = tuple(label for label in (OUTER_DIAMETER, BORE_DIAMETER) if label not in bands)
    if unbanded:
        edges = scan_view_edges(face, label="supplier washer unbanded face rims")
        for label in unbanded:
            rim = _rim(edges, axis=axis, station_mm=thickness_mm,
                       diameter_mm=values[label], label=label)
            display = _native_diameter(adapter, face, rim, text_xy=positions[label], label=label)
            display = supplier_reference_dimension(
                adapter, display, label=label, units=units, precision=precision[label],
                expected_mm=values[label], presentation="diameter",
                callout=bore_callout if label == BORE_DIAMETER else None,
            )
            references.append(_reference(display, face, label, values[label], imported=False,
                                         callout=bore_callout if label == BORE_DIAMETER else None))

    return _supplier_washer_proof(
        adapter, views, tuple(references), axis=axis, bore_mm=bore_mm,
        outer_mm=outer_mm, thickness_mm=thickness_mm, units=units,
        precision=precision, bands=bands,
    )
