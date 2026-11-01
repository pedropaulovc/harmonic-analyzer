"""Import model-owned nominal supplier envelopes, preserving native values."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from math import isfinite
from pathlib import Path
from typing import Any, Literal

from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    iter_views,
    view_name,
)

from _com import _bind, _early_bound
from _dimensions import _feature_display_dimensions
from _drawing_annotation_extent import CLEAR_GAP_M, PLACE_SETTLE_M
from _drawing_common import rebuild_drawing
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_layout_audit import _Reader, _dump_annotation
from _drawing_projection import model_points_in_view
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_screw_layout import supplier_screw_lane_plan, supplier_top_text_geometry
from _supplier_screw_reference_names import FEATURE_BY_PLANE
import _seat_forensics
import _telemetry


def _reference_settings(
    name: str,
    feature: str,
    value: float,
    row: tuple[int, str, int | None, str | None],
    *,
    configuration: str,
    units: str = "in",
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
    adapter: Any,
    source_feature: Any,
    source_dimension: Any,
) -> list[dict[str, Any]]:
    """Prove the named parameter belongs to the actual source feature."""
    inventory = []
    for raw_display in _feature_display_dimensions(source_feature):
        display = _bind(raw_display, "IDisplayDimension")
        raw_dimension = display.GetDimension2(0)
        if raw_dimension is None:
            raise RuntimeError("source feature display has no native dimension")
        dimension = _early_bound(raw_dimension, "IDimension")
        row = {
            "full_name": str(dimension.FullName),
            "dimension_is_same": int(adapter.swApp.IsSame(source_dimension, dimension)),
        }
        inventory.append(row)
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


def _attachment_correspondence(
    adapter: Any,
    view: Any,
    *,
    source_sketch: Any,
    entities: tuple[Any, ...],
    types: tuple[int, ...],
) -> dict[str, Any]:
    """Prove direct source-member identity in this drawing view.

    Enumerate only the actual model sketch and map every point or segment with
    IView.GetCorresponding. Native positive controls establish its point mapping.
    Require complete, distinct model/view inventories and supported comparisons.
    Sketch mapping, inverse mapping, IDs, coordinates and raw cross-context
    identity are not alternative attachment proofs.
    """
    census: dict[str, Any] = {"sources": [], "attachments": []}

    def error(exc: Exception) -> dict[str, str]:
        return {"error_type": type(exc).__name__, "message": str(exc)}

    def read_object(
        row: dict[str, Any], key: str, interface: str, read: Callable[[], Any]
    ) -> Any:
        try:
            raw = read()
            obj = (
                None if raw is None else _early_bound(_bind(raw, interface), interface)
            )
        except Exception as exc:
            row[key] = error(exc)
            return None
        row[key] = {"present": obj is not None}
        return obj

    def same(left: Any, right: Any) -> Any:
        if left is None or right is None:
            return None
        try:
            return int(adapter.swApp.IsSame(left, right))
        except Exception as exc:
            return error(exc)

    mapped_members: dict[int, list[Any]] = {}
    source_members: dict[int, list[Any]] = {}
    attached_members: dict[int, Any] = {}
    mapping_complete: dict[int, bool] = {}
    for kind in sorted(set(types)):
        source: dict[str, Any] = {
            "kind": kind,
            "members": [],
            "distinctness": [],
            "inventory_complete": False,
        }
        census["sources"].append(source)
        mapped_members[kind] = []
        mapping_complete[kind] = False
        if kind not in (10, 11):
            source["invalid_attachment_type"] = True
            continue
        interface = "ISketchSegment" if kind == 10 else "ISketchPoint"
        try:
            raw_members = tuple(
                (
                    source_sketch.GetSketchSegments()
                    if kind == 10
                    else source_sketch.GetSketchPoints2()
                )
                or ()
            )
            source["inventory_complete"] = True
        except Exception as exc:
            source["inventory_error"] = error(exc)
            raw_members = ()
        originals: list[Any] = []
        source_members[kind] = originals
        for index, raw_member in enumerate(raw_members):
            member: dict[str, Any] = {"index": index}
            source["members"].append(member)
            original = read_object(member, "native", interface, lambda: raw_member)
            if original is None:
                member["forward"] = {"present": False, "skipped": "null_input"}
                mapped = None
            else:
                mapped = read_object(
                    member,
                    "forward",
                    interface,
                    lambda: view.GetCorresponding(original),
                )
            member["self"] = same(original, original)
            member["forward_self"] = same(mapped, mapped)
            originals.append(original)
            mapped_members[kind].append(mapped)
        # One comparison per unordered pair proves injectivity in both contexts.
        for left in range(len(originals)):
            for right in range(left + 1, len(originals)):
                source["distinctness"].append(
                    {
                        "left_index": left,
                        "right_index": right,
                        "source_is_same": same(originals[left], originals[right]),
                        "forward_is_same": same(
                            mapped_members[kind][left], mapped_members[kind][right]
                        ),
                    }
                )
        source["source_member_count"] = len(originals)
        source["mapped_member_count"] = sum(
            member is not None for member in mapped_members[kind]
        )
        mapping_complete[kind] = (
            source["inventory_complete"]
            and source["source_member_count"] > 0
            and source["source_member_count"] == source["mapped_member_count"]
            and all(
                member["self"] == 1 and member["forward_self"] == 1
                for member in source["members"]
            )
            and all(
                pair["source_is_same"] == 0 and pair["forward_is_same"] == 0
                for pair in source["distinctness"]
            )
        )
        source["mapping_complete"] = mapping_complete[kind]

    for index, (raw_entity, kind) in enumerate(zip(entities, types, strict=True)):
        proof: dict[str, Any] = {
            "index": index,
            "kind": kind,
            "member_proof": "direct_view_corresponding",
            "proven": False,
        }
        census["attachments"].append(proof)
        if kind not in (10, 11):
            proof["invalid_attachment_type"] = True
            continue
        interface = "ISketchSegment" if kind == 10 else "ISketchPoint"
        entity = read_object(proof, "native", interface, lambda: raw_entity)
        attached_members[index] = entity
        proof["self"] = same(entity, entity)
        comparisons = [same(entity, mapped) for mapped in mapped_members[kind]]
        proof["view_source_entity_is_same"] = comparisons
        matches = [
            member_index
            for member_index, equality in enumerate(comparisons)
            if equality == 1
        ]
        proof["matched_mapped_members"] = matches
        proof["negative_controls_proven"] = all(
            equality == 0
            for member_index, equality in enumerate(comparisons)
            if member_index not in matches
        )
        proof["proven"] = (
            entity is not None
            and proof["self"] == 1
            and mapping_complete[kind]
            and len(matches) == 1
            and proof["negative_controls_proven"]
        )
    proven_members: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for proof in census["attachments"]:
        if proof["proven"]:
            token = (proof["kind"], proof["matched_mapped_members"][0])
            proven_members.setdefault(token, []).append(proof)
    for owners in proven_members.values():
        if len(owners) > 1:
            for proof in owners:
                proof["proven"] = False
                proof["duplicate_mapped_member"] = True
    census["proven"] = bool(census["attachments"]) and all(
        proof["proven"] for proof in census["attachments"]
    )
    if not census["proven"]:
        # Private, short-lived handoff of the exact refused predicate objects.
        census["_failure_native_objects"] = {
            "source": source_members, "mapped": mapped_members, "attached": attached_members,
        }
    return census


def _assert_dimension_source(
    adapter: Any, view: Any, display: Any, *, name: str, feature: str
) -> Any:
    """Validate an imported model dimension and return its native source feature."""
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
    source_feature = _early_bound(view.ReferencedDocument, "IPartDoc").FeatureByName(
        feature
    )
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
                adapter, source_feature, source_dimension
            )
        except Exception as exc:
            feature_dimensions_error = {
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
    # GetDimension2 returns the model dimension used to create the display.
    # Native drawing/source wrappers need not support cross-context IsSame, and
    # GetCorresponding(source annotation) can be absent for these imports.
    # Retain qualified identity plus actual source membership and view ownership.
    # Imported point wrappers need not equal source or GetCorresponding wrappers.
    feature_members = [
        row
        for row in feature_dimensions
        if row["full_name"].split("@")[:2] == [name, feature]
        and row["dimension_is_same"] == 1
        and row["full_name"] == str(native.FullName)
        and row["full_name"] == str(source_dimension.FullName)
    ]
    if (
        source_dimension is None
        or source_feature is None
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
        raise RuntimeError(
            f"{name}: supplier reference changed native model/feature owner"
        )
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
    return source_feature


def _assert_source(
    adapter: Any, view: Any, display: Any, *, name: str, feature: str
) -> None:
    """Also prove mapped attachments for callers with that native contract."""
    source_feature = _assert_dimension_source(
        adapter, view, display, name=name, feature=feature
    )
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    source_sketch: Any = None
    correspondence: dict[str, Any] = {}
    try:
        raw_sketch = _early_bound(source_feature, "IFeature").GetSpecificFeature2()
        source_sketch = _early_bound(_bind(raw_sketch, "ISketch"), "ISketch")
        entities = tuple(annotation.GetAttachedEntities3() or ())
        types = tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ()))
        if source_sketch is None or not entities or len(entities) != len(types):
            raise RuntimeError(
                f"{name}: supplier reference lost its source sketch attachments"
            )
        correspondence = _attachment_correspondence(
            adapter,
            view,
            source_sketch=source_sketch,
            entities=entities,
            types=types,
        )
        if not correspondence["proven"]:
            raise RuntimeError(
                f"{name}: nominal supplier attachment changed source sketch"
            )
    except Exception as exc:
        cached_objects = correspondence.pop("_failure_native_objects", None)
        # Read-only refusal evidence, never an alternative identity proof. IDs
        # are sketch-local; native XYZ coincidence is not identity or a common frame.
        def read_error(member: str, failure: Exception) -> dict[str, str]:
            try:
                message = str(failure)
            except Exception:
                message = "<exception message could not be read>"
            return {
                "member": member,
                "error_type": type(failure).__name__,
                "message": message,
            }

        def scalar(member: str, read: Callable[[], Any]) -> Any:
            try:
                value = read()
                if value is None:
                    raise RuntimeError("native scalar getter returned null")
                return json.loads(json.dumps(value, allow_nan=False))
            except Exception as failure:
                return read_error(member, failure)

        def native(
            row: dict[str, Any], key: str, interface: str,
            member: str, read: Callable[[], Any],
        ) -> Any:
            try:
                raw = read()
                obj = _early_bound(_bind(raw, interface), interface)
                row[key] = {"member": member, "present": obj is not None}
                return obj
            except Exception as failure:
                row[key] = read_error(member, failure)
                return None

        def same(left: Any, right: Any) -> Any:
            def compare() -> int:
                if left is None or right is None:
                    raise RuntimeError("native comparison operand is unavailable")
                return int(adapter.swApp.IsSame(left, right))
            return scalar("ISldWorks.IsSame", compare)

        def both(left: Any, right: Any) -> dict[str, Any]:
            return {
                "left_to_right": same(left, right),
                "right_to_left": same(right, left),
            }

        def sketch_frame(sketch: Any) -> Any:
            return scalar(
                "ISketch.ModelToSketchTransform / IMathTransform.ArrayData",
                lambda: tuple(float(value) for value in _early_bound(
                    sketch.ModelToSketchTransform, "IMathTransform",
                ).ArrayData),
            )

        context = {
            "dimension": name,
            "source_feature": feature,
            "attachment_correspondence": correspondence,
            "attachment_error": read_error("attachment proof", exc),
        }
        batch: dict[str, Any] = {}
        context["failure_native_readback"] = batch
        members: list[tuple[str, int, Any, Any]] = []
        try:
            diagnostic_view = native(batch, "view", "IView", "IView", lambda: view)
            model = native(
                batch, "source_document", "IModelDoc2",
                "IView.ReferencedDocument", lambda: diagnostic_view.ReferencedDocument,
            )
            drawing = native(
                batch, "drawing_document", "IModelDoc2",
                "adapter.currentModel", lambda: adapter.currentModel,
            )
            view_sketch = native(
                batch, "view_sketch", "ISketch", "IView.GetSketch",
                lambda: diagnostic_view.GetSketch(),
            )
            batch["context"] = {
                "view_name": scalar("IView.GetName2", lambda: diagnostic_view.GetName2()),
                "view_source_path": scalar("IView.GetReferencedModelName", lambda: diagnostic_view.GetReferencedModelName()),
                "view_configuration": scalar("IView.ReferencedConfiguration", lambda: diagnostic_view.ReferencedConfiguration),
                "view_orientation": scalar("IView.GetOrientationName", lambda: diagnostic_view.GetOrientationName()),
                "source_path": scalar("IModelDoc2.GetPathName", lambda: model.GetPathName()),
                "source_active_configuration": scalar(
                    "IModelDoc2.ConfigurationManager / IConfigurationManager.ActiveConfiguration / IConfiguration.Name",
                    lambda: _early_bound(_early_bound(
                        model.ConfigurationManager, "IConfigurationManager",
                    ).ActiveConfiguration, "IConfiguration").Name,
                ),
                "drawing_path": scalar("IModelDoc2.GetPathName", lambda: drawing.GetPathName()),
                "drawing_edit_sheet": scalar("IDrawingDoc.GetEditSheet", lambda: _early_bound(drawing, "IDrawingDoc").GetEditSheet()),
                "source_feature_name": scalar("IFeature.Name", lambda: source_feature.Name),
                "source_feature_type": scalar(
                    "IFeature.GetTypeName2",
                    lambda: _early_bound(source_feature, "IFeature").GetTypeName2(),
                ),
                "model_to_view": scalar(
                    "IView.ModelToViewTransform / IMathTransform.ArrayData",
                    lambda: tuple(float(value) for value in _early_bound(
                        diagnostic_view.ModelToViewTransform, "IMathTransform",
                    ).ArrayData),
                ),
            }
            sketches = {"source": source_sketch, "view": view_sketch}
            for label, document in (("source", model), ("drawing", drawing)):
                sketches[f"{label}_active"] = native(
                    batch, f"{label}_active_sketch", "ISketch",
                    "IModelDoc2.SketchManager / ISketchManager.ActiveSketch",
                    lambda document=document: _early_bound(
                        document.SketchManager, "ISketchManager",
                    ).ActiveSketch,
                )
            active_view = native(
                batch, "active_drawing_view", "IView", "IDrawingDoc.ActiveDrawingView",
                lambda: _early_bound(drawing, "IDrawingDoc").ActiveDrawingView,
            )
            batch["active_drawing_view_is_same"] = both(active_view, diagnostic_view)
            batch["sketches"] = {
                label: {"present": sketch is not None, "self": same(sketch, sketch),
                        "model_to_sketch": sketch_frame(sketch)}
                for label, sketch in sketches.items()
            }
            batch["sketch_comparisons"] = [
                {"left": left, "right": right, "is_same": both(sketches[left], sketches[right])}
                for index, left in enumerate(sketches)
                for right in tuple(sketches)[index + 1:]
            ]

            def point_fields(point: Any) -> dict[str, Any]:
                return {
                    "id": scalar("ISketchPoint.GetID", lambda: tuple(int(value) for value in point.GetID())),
                    "xyz_native_m": {
                        axis: scalar(f"ISketchPoint.{axis}", lambda axis=axis: float(getattr(point, axis)))
                        for axis in ("X", "Y", "Z")
                    },
                }

            def entity_fields(raw: Any, kind: int, label: str) -> dict[str, Any]:
                row: dict[str, Any] = {"label": label, "kind": kind}
                if kind not in (10, 11):
                    row["read_error"] = {"member": "IAnnotation.GetAttachedEntityTypes", "unsupported_kind": kind}
                    return row
                interface = "ISketchPoint" if kind == 11 else "ISketchSegment"
                entity = raw  # Already typed by the predicate; do not rebind it.
                row["native"] = {"member": f"{interface} predicate cache", "present": entity is not None}
                row["self"] = same(entity, entity)
                if kind == 11:
                    row.update(point_fields(entity))
                    row["type"] = scalar("ISketchPoint.Type", lambda: int(entity.Type))
                else:
                    row["id"] = scalar("ISketchSegment.GetID", lambda: tuple(int(value) for value in entity.GetID()))
                    row["type"] = scalar("ISketchSegment.GetType", lambda: int(entity.GetType()))
                    row["construction"] = scalar("ISketchSegment.ConstructionGeometry", lambda: entity.ConstructionGeometry)
                    if row["type"] == 0:  # swSketchLINE; other segment types are labelled, not guessed.
                        for endpoint, getter in (("start", "GetStartPoint2"), ("end", "GetEndPoint2")):
                            endpoint_row: dict[str, Any] = {}
                            point = native(
                                endpoint_row, "native", "ISketchPoint", f"ISketchLine.{getter}",
                                lambda getter=getter: getattr(_early_bound(entity, "ISketchLine"), getter)(),
                            )
                            endpoint_row.update(point_fields(point))
                            row[endpoint] = endpoint_row
                    else:
                        row["endpoints"] = {"not_read": "ISketchLine endpoints require a readable swSketchLINE type"}
                owner = native(row, "sketch_owner", "ISketch", f"{interface}.GetSketch", lambda: entity.GetSketch())
                row["sketch_owner"]["self"] = same(owner, owner)
                row["sketch_owner"]["model_to_sketch"] = sketch_frame(owner)
                row["sketch_owner"]["is_same"] = {
                    key: both(owner, sketch) for key, sketch in sketches.items()
                }
                members.append((label, kind, entity, owner))
                return row

            # These are the exact objects used by the refused predicate. Never
            # refresh/re-enumerate the sketch or call GetCorresponding again:
            # a new mapping cannot explain the already-refused cached mapping.
            batch["predicate_inventory"] = {
                "scope": "exact cached predicate kinds only; no supplemental point/segment enumeration",
                "uncaptured_kinds": {
                    str(kind): {
                        "status": "unavailable",
                        "reason": "not inventoried by the refused predicate; no supplemental enumeration attempted",
                    }
                    for kind in (10, 11)
                    if cached_objects is None or kind not in cached_objects["source"]
                },
            }
            if cached_objects is None:
                batch["predicate_inventory"]["read_error"] = {
                    "member": "_attachment_correspondence failure cache",
                    "message": "predicate objects were not returned; no re-enumeration attempted",
                }
            else:
                for group in ("source", "mapped"):
                    batch["predicate_inventory"][group] = [
                        entity_fields(raw, kind, f"{group}:{kind}:{index}")
                        for kind, objects in cached_objects[group].items()
                        for index, raw in enumerate(objects)
                    ]
            attachments: dict[str, Any] = {}
            batch["attachments"] = attachments
            attachments["types"] = scalar(
                "IAnnotation.GetAttachedEntityTypes cached result", lambda: types,
            )
            if cached_objects is None:
                attachments["read_error"] = {
                    "member": "_attachment_correspondence typed attachment cache",
                    "message": "no typed predicate attachments returned; raw attachments were not rebound",
                }
            else:
                attachments["members"] = [
                    entity_fields(cached_objects["attached"].get(index), kind, f"attached:{index}")
                    for index, kind in enumerate(types)
                ]
            batch["member_comparisons"] = [
                {"left": left[0], "right": right[0],
                 "is_same": both(left[2], right[2]),
                 "sketch_owner_is_same": both(left[3], right[3])}
                for index, left in enumerate(members)
                for right in members[index + 1:] if left[1] == right[1]
            ]
            dimension_row: dict[str, Any] = {}
            batch["native_dimension"] = dimension_row
            dimension = native(
                dimension_row, "native", "IDimension", "IDisplayDimension.GetDimension2",
                lambda: display.GetDimension2(0),
            )
            dimension_row["full_name"] = scalar("IDimension.FullName", lambda: dimension.FullName)
            dimension_row["self"] = same(dimension, dimension)
            dimension_row["system_values"] = scalar(
                "IDimension.GetSystemValue3(swSpecifyConfiguration)",
                lambda: tuple(float(value) for value in dimension.GetSystemValue3(
                    3, diagnostic_view.ReferencedConfiguration,  # swSpecifyConfiguration
                )),
            )
            dimension_row["driven_state"] = scalar("IDimension.DrivenState", lambda: int(dimension.DrivenState))
            owner = native(
                dimension_row, "feature_owner", "IFeature", "IDimension.GetFeatureOwner",
                lambda: dimension.GetFeatureOwner(),
            )
            dimension_row["feature_owner"]["name"] = scalar("IFeature.Name", lambda: owner.Name)
            dimension_row["feature_owner"]["is_same"] = both(owner, source_feature)
        except Exception as failure:
            # An unexpected diagnostic implementation/binding error is evidence,
            # never permission to replace the original attachment refusal.
            batch["read_error"] = read_error("failure_native_readback", failure)
        finally:
            # Drop every private COM reference before serialization or delivery,
            # including when a reader fails. Nothing is retained in the context.
            members.clear()
            if cached_objects is not None:
                cached_objects.clear()
                cached_objects = None
        try:
            _telemetry.info(
                f"supplier_source_attachment_failure {name}@{feature}: "
                + json.dumps(context, sort_keys=True, allow_nan=False)
            )
        except Exception as failure:
            context["diagnostic_log_error"] = read_error("supplier_source_attachment_failure logging", failure)
        try:
            # Preserve the refused partial drawing, even if its native dimensions
            # are non-dangling. A forensic snapshot is not source/layout approval.
            _seat_forensics.capture_com_failure(
                adapter,
                f"supplier-attachment-{name}",
                str(exc),
                api="IView.GetCorresponding supplier source attachment",
                exception=exc,
                sheet_png=True,
                sketch=source_sketch,
                attachment_context=context,
            )
        except Exception as capture_error:
            if capture_error is not exc:
                try:
                    _telemetry.warn(
                        f"{name}: attachment forensic capture failed: {capture_error}"
                    )
                except Exception:
                    pass  # Even warning delivery must preserve the original refusal.
        raise
    _telemetry.info(
        f"supplier_source_attachment_proof {name}@{feature}: "
        + json.dumps(correspondence, sort_keys=True, allow_nan=False)
    )


# These short native chords carry horizontal text much wider than their span.
# Only the explicitly selected supplier_top layout uses offset-text shelves.
_SUPPLIER_TOP_SHELVES = {
    "SupplierHeadHeight": (False, "left"),
    "SupplierThreadDiameter": (True, "right"),
    "SupplierHeadDiameter": (True, "right"),
    "SupplierDriveWidth": (True, "right"),
}


def _supplier_top_record(adapter: Any, display: Any) -> dict[str, Any]:
    reader = _Reader(adapter)
    record = _dump_annotation(reader, display.GetAnnotation())
    errors = reader.take_errors()
    if errors or record is None or int(record.get("type", 0)) != 4:
        raise RuntimeError(f"supplier Top shelf annotation read failed: {errors}")
    texts = (record.get("display") or {}).get("texts") or ()
    if not texts or any(
        not isfinite(float(row.get("w") or 0.0)) or float(row.get("w") or 0.0) <= 0.0
        for row in texts
    ):
        raise RuntimeError("supplier Top shelf text has no measured native width")
    return record


def _assert_supplier_top_stations(
    name: str, before: Mapping[str, Any], after: Mapping[str, Any]
) -> None:
    for field in ("tips", "witnesses", "physical_lines"):
        if len(before[field]) != len(after[field]) or any(
            len(prior) != len(current)
            or any(abs(a - b) > 1e-5 for a, b in zip(prior, current, strict=True))
            for prior, current in zip(before[field], after[field], strict=True)
        ):
            raise RuntimeError(f"{name}: supplier Top shelf moved native {field}")


def _assert_supplier_top_shelves(
    adapter: Any, displays: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    measured = {}
    for name, (horizontal, side) in _SUPPLIER_TOP_SHELVES.items():
        if name not in displays:
            continue
        display = _early_bound(displays[name], "IDisplayDimension")
        actual = supplier_top_text_geometry(
            _supplier_top_record(adapter, display), horizontal=horizontal
        )
        text = actual["text"]
        gap = (
            actual["left"] - text.xmax if side == "left"
            else text.xmin - actual["right"]
        )
        if display.OffsetText is not True or gap < CLEAR_GAP_M:
            raise RuntimeError(f"{name}: supplier Top text shelf is not clear")
        measured[name] = actual
    return measured


def _shelf_supplier_top_text(
    adapter: Any, displays: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    """Move text only, after formatting; retain measured native line stations."""
    rebuild_drawing(adapter, label="supplier Top formatting and native lanes settled")
    before = {}
    positions = {}
    anchors = {}
    for name, (horizontal, _side) in _SUPPLIER_TOP_SHELVES.items():
        if name not in displays:
            continue
        display = _early_bound(displays[name], "IDisplayDimension")
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        position = tuple(float(value) for value in annotation.GetPosition())
        if len(position) != 3 or not all(map(isfinite, position)):
            raise RuntimeError(f"{name}: supplier Top shelf has no native position")
        actual = supplier_top_text_geometry(
            _supplier_top_record(adapter, display), horizontal=horizontal
        )
        before[name], positions[name] = actual, position
        # OffsetText makes the old annotation anchor the physical line station.
        # Seed it from the measured arrow tips first, as on the thumb screw.
        normal = 1 if horizontal else 0
        anchor = list(position[:2])
        anchor[normal] = sum(tip[normal] for tip in actual["tips"]) / 2.0
        anchors[name] = tuple(anchor)
        if not annotation.SetPosition2(*anchor, 0.0):
            raise RuntimeError(f"{name}: failed to prepare supplier Top offset anchor")
    rebuild_drawing(adapter, label="supplier Top measured pre-offset anchors")
    for name, anchor in anchors.items():
        display = _early_bound(displays[name], "IDisplayDimension")
        display.OffsetText = True
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        if not annotation.SetPosition2(*anchor, 0.0):
            raise RuntimeError(f"{name}: failed to enable supplier Top text offset")
    rebuild_drawing(adapter, label="supplier Top native offset-text mode")
    for name, (horizontal, side) in _SUPPLIER_TOP_SHELVES.items():
        if name not in before:
            continue
        display = _early_bound(displays[name], "IDisplayDimension")
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        actual = supplier_top_text_geometry(
            _supplier_top_record(adapter, display), horizontal=horizontal
        )
        _assert_supplier_top_stations(name, before[name], actual)
        text = actual["text"]
        gap = CLEAR_GAP_M + PLACE_SETTLE_M
        dx = (
            actual["left"] - gap - text.xmax if side == "left"
            else actual["right"] + gap - text.xmin
        )
        current = tuple(float(value) for value in annotation.GetPosition())
        if not annotation.SetPosition2(current[0] + dx, positions[name][1], 0.0):
            raise RuntimeError(f"{name}: failed to place supplier Top text shelf")
    rebuild_drawing(adapter, label="supplier Top text shelves settled")
    for name, actual in _assert_supplier_top_shelves(adapter, displays).items():
        _assert_supplier_top_stations(name, before[name], actual)
    return before


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
    layout: Literal["standard", "supplier_top", "tall_top"] = "standard",
    shelf_stations: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Reacquire final native carriers and refuse missing, duplicate or alien ink."""
    planes = planes or {}
    units = units or {}
    supplier_screw_lane_plan(dimensions, planes=planes)
    expected = {name: value for name, value, _ in dimensions}
    if set(formats) != set(expected):
        raise ValueError("supplier screw references and display formats must match")
    if set(units) - set(expected) or any(
        unit not in ("in", "mm") for unit in units.values()
    ):
        raise ValueError(
            "supplier reference units must name source dimensions in inches or millimetres"
        )
    bindings = _bindings or {
        key: _binding(adapter, view) for key, view in views.items()
    }
    actual = list(iter_views(adapter))
    by_name = {str(view_name(adapter, view)): view for view in actual}
    if len(by_name) != len(actual):
        raise RuntimeError("duplicate settled supplier drawing view names")
    found: dict[str, Any] = {}
    for orientation, (native_name, source, configuration) in bindings.items():
        if native_name not in by_name:
            raise RuntimeError(f"{orientation}: settled supplier view is missing")
        view = _early_bound(by_name[native_name], "IView")
        if (
            _binding(adapter, view) != (native_name, source, configuration)
            or str(view.GetOrientationName()) != orientation
        ):
            raise RuntimeError(
                f"{orientation}: settled supplier view changed source/configuration/orientation"
            )
        for raw_annotation in view.GetAnnotations() or ():
            annotation = _early_bound(raw_annotation, "IAnnotation")
            if int(annotation.GetType()) != 4:  # swDisplayDimension
                continue
            display = _early_bound(
                annotation.GetSpecificAnnotation(), "IDisplayDimension"
            )
            raw_dimension = display.GetDimension2(0)
            if raw_dimension is None:
                raise RuntimeError(
                    f"{orientation}: settled supplier annotation has no dimension"
                )
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
                raise RuntimeError(
                    f"{name}: settled supplier reference changed source feature/view"
                )
            if name in found:
                raise RuntimeError(f"{name}: duplicate settled supplier reference")
            _assert_source(adapter, view, display, name=name, feature=feature)
            assert_supplier_reference_dimension(
                adapter,
                display,
                **_reference_settings(
                    name,
                    feature,
                    expected[name],
                    formats[name],
                    configuration=configuration,
                    units=units.get(name, "in"),
                ),
            )
            found[name] = display
    if set(found) != set(expected):
        raise RuntimeError(
            f"settled supplier references missing {sorted(set(expected) - set(found))}"
        )
    if layout == "supplier_top":
        measured = _assert_supplier_top_shelves(adapter, found)
        if shelf_stations is None or set(shelf_stations) != set(measured):
            raise RuntimeError("supplier Top settled check has no retained native stations")
        for name, actual in measured.items():
            _assert_supplier_top_stations(name, shelf_stations[name], actual)
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
    layout: Literal["standard", "supplier_top", "tall_top"] = "standard",
    shelf_stations: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Curate exact native sizes into their orthographic annotation lanes.

    Hidden construction carriers are nominal supplier references, not proof
    that an ideal envelope survives a physical groove, slot or simplification.
    Physical-edge dimensions use their own existing attachment checks.
    Per-row units retain metric supplier prints; omitted rows use inches.
    Geometry always remains exact millimetres, with angles in degrees.
    Custom settled checks retain the caller-owned shelf_stations mapping.
    """
    starts = starts or {}
    planes = planes or {}
    units = units or {}
    names = {name for name, _, _ in dimensions}
    if names != set(formats) or len(names) != len(dimensions) or set(starts) - names:
        raise ValueError("supplier screw references and display formats must match")
    if set(units) - names or any(unit not in ("in", "mm") for unit in units.values()):
        raise ValueError(
            "supplier reference units must name source dimensions in inches or millimetres"
        )
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
            raise RuntimeError(
                f"{plane}: supplier references target the wrong orientation"
            )
        view.UpdateViewDisplayGeometry()
        outline = tuple(float(value) for value in view.GetOutline())
        if len(outline) != 4 or not all(isfinite(value) for value in outline):
            raise RuntimeError(
                f"{plane}: supplier reference view has no finite outline"
            )
        points = []
        for name, value, orientation in rows:
            start = starts.get(name, (0.0, 0.0))
            if len(start) != 2 or not all(isfinite(value) for value in start):
                raise ValueError(
                    f"{name}: supplier reference start must be a finite coordinate pair"
                )
            x, y = start
            if orientation == "horizontal":
                x += value / 2.0
            elif orientation == "vertical":
                y += value / 2.0
            points.append(
                (x / 1000.0, y / 1000.0, 0.0)
                if plane == "Front"
                else (x / 1000.0, 0.0, -y / 1000.0)
            )
        projected = model_points_in_view(
            adapter, view, points, label=f"{plane} supplier reference centres"
        )
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
            adapter,
            view,
            keep=keep,
            view_label=f"{plane} supplier references",
            dimensions_by_feature={feature: set(keep)},
        )
        values = {name: value for name, value, _ in rows}
        for annotation in annotations:
            name = dimension_name(adapter, annotation)
            if name not in values or name in displays:
                raise RuntimeError(
                    f"{name}: unexpected or duplicate imported supplier reference"
                )
            display = _early_bound(
                _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
                "IDisplayDimension",
            )
            _assert_source(adapter, view, display, name=name, feature=feature)
            displays[name] = supplier_reference_dimension(
                adapter,
                display,
                **_reference_settings(
                    name,
                    feature,
                    values[name],
                    formats[name],
                    configuration=bindings[orientation_name][2],
                    units=units.get(name, "in"),
                ),
            )
            if layout == "supplier_top":
                # A model annotation may inherit offset mode. Place the whole
                # dimension in its lane before opting into text-only movement.
                display = _early_bound(displays[name], "IDisplayDimension")
                display.OffsetText = False
                annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
                if not annotation.SetPosition2(*keep[name], 0.0):
                    raise RuntimeError(f"{name}: failed to settle supplier Top lane")
    if set(displays) != names:
        raise RuntimeError(
            f"supplier references missing {sorted(names - set(displays))}"
        )
    stations = {}
    if layout == "supplier_top":
        stations = _shelf_supplier_top_text(adapter, displays)
        if shelf_stations is not None:
            shelf_stations.update(stations)
    if settled_checks is not None:
        settled_checks.append(
            partial(
                assert_supplier_screw,
                adapter,
                views,
                dimensions=dimensions,
                formats=formats,
                planes=planes,
                units=units,
                _bindings=bindings,
                layout=layout,
                shelf_stations=stations,
            )
        )
    return displays
