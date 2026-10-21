r"""Native quarter-inch lever sheet with an enlarged flat-thread-end detail.

The independent model detail imports its dimensions before its circular crop,
as on MHA-MG-04. Native diameters/lengths/limits remain associative. The model
retains UNC-2A metadata; drawing instances defer the default class to the title.
Only the free end domes; its note attaches to the identified spherical face,
including actual visible-silhouette faces when face enumeration omits them.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, dimension_full_name, dimension_name, place_view

from _check import check
from _com import _early_bound
from _drawing_common import DrawingOutputs, finalize_drawing, new_project_drawing, read_required_properties, rebuild_drawing, stamp_drawing_summary, view_name
from _drawing_dimension_import import curate_view_dimensions, import_cosmetic_threads
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edges import visible_view_entities
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions as curate_hidden_dimensions
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _gtol_face_read import face_geometry
from _gtol_sphere import SphereFace
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from mg_lever_thread_joint import INCOMPLETE_THREAD_MAX, ROD_DIA, ROD_LENGTH, THREAD_LENGTH, TIP_CHAMFER
from mg_magnifying_lever_spec import DRAWING_DIMENSIONS, DRAWING_PRECISION, FREE_END_CALLOUT, LEAD_CALLOUT, PRINT_THREAD_CALLOUT, ROD_DIA_CALLOUT, SCREW_SEAT_CALLOUT, SURFACE_FINISHES, THREAD_CALLOUT

SPEC = DRAWINGS_BY_NAME["mg_magnifying_lever"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"])
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (1, 1)
FRONT_CENTER = (0.115, 0.120)
ISO_CENTER = (0.350, 0.105)
ISO_SCALE = (1, 2)
DETAIL_CENTER = (0.310, 0.190)
DETAIL_SCALE = (3, 1)
DETAIL_FOCUS = (0.156, 0.0, 0.0)
DETAIL_RADIUS_MM = 12.5
# Four thread/shape rows fit between the native length witnesses. The upper
# lane keeps the descending leader outside the mate text and below the 18 line.
DETAIL_KEEP = {"ThreadLength": (0.323, 0.255), "IncompleteLength": (0.377, 0.165)}
FRONT_KEEP = {"OverallLength": (0.115, 0.088), "RodDia": (0.118, 0.150)}
DETAIL_THREAD_NOTE_XY = (0.2926, 0.245)
DETAIL_THREAD_CALLOUT = PRINT_THREAD_CALLOUT.replace(" BRACKET", "\nBRACKET")
CALLOUTS = {"RodDia": ROD_DIA_CALLOUT, "IncompleteLength": LEAD_CALLOUT}


def _activate(adapter: Any, view: Any) -> None:
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError("could not activate lever drawing view")
    adapter.currentModel.ClearSelection2(True)


def _note(adapter: Any, view: Any, text: str, xy: tuple[float, float]) -> None:
    _activate(adapter, view)
    if add_note(adapter, text, *xy) is None:
        raise RuntimeError(f"could not add lever note {text!r}")
    texts = [" ".join(str(_early_bound(found, "INote").GetText() or "").split()) for found in (_early_bound(view, "IView").GetNotes() or ())]
    if texts.count(" ".join(text.split())) != 1:
        raise RuntimeError(f"lever note is not owned by its view: {text!r}")


def _circle(adapter: Any, view: Any, center: tuple[float, float], radius: float, *, mark: bool = False) -> None:
    _activate(adapter, view)
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = mark
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous
    if circle is None:
        raise RuntimeError("could not create lever detail circle")
    if mark:
        segment = _early_bound(circle, "ISketchSegment")
        segment.Color = 0
        if int(segment.Color) != 0:
            raise RuntimeError("lever detail mark is not black")
        adapter.currentModel.ClearSelection2(True)


def _detail(adapter: Any) -> tuple[Any, list[Any]]:
    view = _early_bound(place_view(adapter, str(SOURCE), "*Front", *DETAIL_CENTER, scale=DETAIL_SCALE), "IView")
    if tuple(float(value) for value in view.ScaleRatio) != DETAIL_SCALE:
        raise RuntimeError("lever thread detail lost its native scale")
    focus = model_point_in_view(adapter, view, DETAIL_FOCUS, label="lever thread focus")
    position = tuple(float(value) for value in view.Position)
    if not view.SetViewPosition(double_array([position[i] + DETAIL_CENTER[i] - focus[i] for i in range(2)]), False):
        raise RuntimeError("could not position lever thread detail")
    rebuild_drawing(adapter, label="position lever thread detail")
    if math.dist(model_point_in_view(adapter, view, DETAIL_FOCUS, label="positioned lever focus"), DETAIL_CENTER) > 0.00005:
        raise RuntimeError("lever thread detail focus shifted")
    set_hidden_lines_removed(adapter, view)
    annotations = curate_hidden_dimensions(adapter, view, keep=DETAIL_KEEP, view_label="lever thread-end detail", dimensions_by_feature=DRAWING_DIMENSIONS)
    _circle(adapter, view, DETAIL_CENTER, DETAIL_RADIUS_MM * DETAIL_SCALE[0] / 1000.0)
    status = int(view.Crop2(False, False, 1))
    adapter.currentModel.ClearSelection2(True)
    rebuild_drawing(adapter, label="crop lever thread detail")
    view.UpdateViewDisplayGeometry()
    if status != 1 or not bool(view.IsCropped()) or bool(view.CropViewJaggedOutline) or bool(view.CropViewNoOutline):
        raise RuntimeError(f"lever thread detail crop failed: {status}")
    names = {dimension_name(adapter, _early_bound(annotation, "IAnnotation")) for annotation in (view.GetAnnotations() or ())}
    if not set(DETAIL_KEEP) <= names:
        raise RuntimeError(f"lever thread detail crop lost dimensions: {set(DETAIL_KEEP) - names}")
    return view, annotations


def _free_end_face(adapter: Any, view: Any, annotations: list[Any]) -> Any:
    """Read visible face provenance and require the known rod as a positive control."""
    hemisphere = SphereFace(ROD_DIA, center_mm=(ROD_DIA / 2.0, 0.0, 0.0))
    body = surface_finish_by_key(SURFACE_FINISHES, "clamp_screw_seat").face
    direct = visible_view_entities(view, 3, label="lever visible faces")  # swViewEntityType_Face
    silhouettes = visible_view_entities(view, 4, label="lever visible silhouette faces")
    candidates = list(direct)
    null_faces = 0
    for silhouette in silhouettes:
        face = _early_bound(silhouette, "ISilhouetteEdge").GetFace()
        if face is None:
            null_faces += 1
        else:
            candidates.append(face)
    faces, records, matches, body_matches = [], [], [], []
    for face in candidates:
        if any(int(adapter.swApp.IsSame(face, seen)) == 1 for seen in faces):
            continue
        faces.append(face)
        geometry = face_geometry(face)
        box = geometry.box if geometry is not None else ()
        if not box:
            # Unknown surface identities still need actual model-space bounds
            # for diagnosis; GetBox is approximate, never a sphere selector.
            box = tuple(_early_bound(face, "IFace2").GetBox() or ())
        record = {"identity": None, "parameters": (), "box": box}
        if geometry is not None:
            record.update(
                identity=geometry.identity,
                surface_type={4001: "plane", 4002: "cylinder", 4003: "cone", 4004: "sphere", 4005: "torus"}.get(geometry.identity, "unhandled native surface identity"),
                parameters=geometry.parameters,
            )
            if geometry.identity == 4004:
                record.update(
                    sphere_center_m=geometry.parameters[:3],
                    sphere_radius_m=geometry.parameters[3],
                    sphere_center_mm=tuple(value * 1000.0 for value in geometry.parameters[:3]),
                    sphere_diameter_mm=geometry.parameters[3] * 2000.0,
                )
            if hemisphere.matches(geometry):
                matches.append(face)
            if body.matches(geometry):
                body_matches.append(face)
        records.append(record)
    expected_dimensions = {
        "OverallLength@RodProfile": ROD_LENGTH, "RodDia@RodProfile": ROD_DIA,
        "TipChamfer@RodProfile": TIP_CHAMFER, "ThreadLength@ThreadExtent": THREAD_LENGTH,
        "IncompleteLength@ThreadExtent": INCOMPLETE_THREAD_MAX,
    }
    source = {"requested_path": str(SOURCE), "dimensions": []}
    referenced = None
    try:
        referenced = _early_bound(_early_bound(view, "IView").ReferencedDocument, "IModelDoc2")
        source["actual_path"] = str(referenced.GetPathName())
        source["path_matches"] = source["actual_path"].replace("\\", "/").casefold() == str(SOURCE).replace("\\", "/").casefold()
    except Exception as exc:  # Diagnostics must not replace the strict face failure.
        source["read_error"] = f"{type(exc).__name__}: {exc}"
    for name, expected_mm in expected_dimensions.items():
        row = {"requested_name": name, "expected_mm": expected_mm, "matches_source": False}
        try:
            parameter = referenced.Parameter(name) if referenced is not None else None
            if parameter is None:
                row["read_error"] = "native source dimension unavailable"
            else:
                parameter = _early_bound(parameter, "IDimension")
                row["full_name"] = str(parameter.FullName)
                row["actual_m"] = float(parameter.SystemValue)
                row["actual_mm"] = row["actual_m"] * 1000.0
                row["matches_source"] = math.isclose(row["actual_mm"], expected_mm, rel_tol=0.0, abs_tol=1e-6)
        except Exception as exc:
            row["read_error"] = f"{type(exc).__name__}: {exc}"
        source["dimensions"].append(row)
    source["all_dimensions_match"] = all(row["matches_source"] for row in source["dimensions"])
    projection = {}
    try:
        bound_view = _early_bound(view, "IView")
        matrix = tuple(float(value) for value in _early_bound(bound_view.ModelToViewTransform, "IMathTransform").ArrayData)
        projection = {
            "model_to_view": matrix, "rotation": matrix[:9], "translation_m": matrix[9:12],
            "scale": matrix[12], "orientation": str(bound_view.GetOrientationName()),
        }
    except Exception as exc:
        projection["read_error"] = f"{type(exc).__name__}: {exc}"
    imported = []
    for annotation in annotations:
        full_name = dimension_full_name(adapter, _early_bound(annotation, "IAnnotation"))
        parts = full_name.split("@")
        imported.append({"full_name": full_name, "source_feature": parts[1] if len(parts) > 1 else ""})
    census = {
        "direct_faces": len(direct), "silhouettes": len(silhouettes),
        "null_silhouette_faces": null_faces, "unique_faces": len(faces),
        "plain_body_matches": len(body_matches), "hemisphere_matches": len(matches),
        "faces": records,
        "coordinate_frame": "referenced part model", "length_units": "metres",
        "expected_sphere_center_mm": (ROD_DIA / 2.0, 0.0, 0.0), "expected_sphere_diameter_mm": ROD_DIA,
        "source": source, "view": projection, "imported_dimensions": imported,
    }
    diagnostic = json.dumps(census, sort_keys=True)
    _telemetry.info(f"lever visible-face census: {diagnostic}")
    if len(body_matches) != 1:
        raise RuntimeError(f"lever visible-face census failed its plain-body positive control: {diagnostic}")
    if len(matches) != 1:
        raise RuntimeError(f"lever free hemisphere: expected one visible spherical face, got {len(matches)}; census={diagnostic}")
    return matches[0]


def _print_native_thread_callout(adapter: Any, view: Any) -> None:
    """Edit ICThread's drawing INote, not the part's cosmetic-thread metadata."""
    native = _early_bound(view, "IView")
    count = int(native.GetCThreadCount())
    thread = _early_bound(native.GetFirstCThread(), "ICThread")
    if count != 1 or thread is None or thread.GetNext() is not None:
        raise RuntimeError(f"lever front needs one native cosmetic-thread seed, reported {count}")
    note = _early_bound(thread.ThreadCallout, "INote")
    if note is None:
        raise RuntimeError("lever front cosmetic thread has no native drawing callout note")
    original = str(note.GetText() or "")
    if " ".join(original.split()) != " ".join(THREAD_CALLOUT.split()):
        raise RuntimeError(f"unexpected native lever thread callout: {original!r}")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    owner = annotation.Owner
    owner_type = int(annotation.OwnerType)
    if owner_type not in (0, 1) or owner is None:  # swAnnotationOwner_DrawingView/Sheet
        raise RuntimeError("native lever thread callout is not owned by a drawing view or sheet")
    entities = tuple(annotation.GetAttachedEntities3() or ())
    entity_types = tuple(annotation.GetAttachedEntityTypes() or ())
    entity_count = int(annotation.GetAttachedEntityCount3())
    dangling = bool(annotation.IsDangling())
    if len(entities) != entity_count or len(entity_types) != entity_count:
        raise RuntimeError("native lever thread callout attachment census is incomplete")
    app = adapter.swApp
    self_comparisons = []
    for label, identity_field, obj in (
        ("callout", "before.note_self", note), ("owner", "before.owner_self", owner),
        *(("attachment", f"before.entity_self[{index}]", entity) for index, entity in enumerate(entities)),
    ):
        try:
            result = int(app.IsSame(obj, obj))
        except Exception as exc:
            raise RuntimeError(f"native lever ISldWorks.IsSame reader {identity_field} failed: {exc}") from exc
        self_comparisons.append({"role": label, "field": identity_field, "code": result})
        if result != 1:
            raise RuntimeError(f"native lever {label} identity comparison unsupported: self={result} ({identity_field})")
    try:
        owner_to_front = int(app.IsSame(owner, native)) if owner_type == 0 else None
    except Exception as exc:
        raise RuntimeError(f"native lever ISldWorks.IsSame reader before.owner_to_front failed: {exc}") from exc
    if owner_type == 0 and owner_to_front != 1:
        raise RuntimeError("native lever thread callout belongs to another drawing view")
    # R8 INote readback canonicalizes line endings to CRLF. Preserve every row
    # and space; send and compare the same native payload, not normalized text.
    native_text = PRINT_THREAD_CALLOUT.replace("\n", "\r\n")
    audit = {
        "portable_text": PRINT_THREAD_CALLOUT,
        "requested_text": native_text,
        "stage": "before_set_text",
        "before": {
            "text": original, "owner_type": owner_type, "owner_present": True,
            "attached_count": entity_count, "attached_types": entity_types,
            "entities_reported": len(entities), "dangling": dangling,
            "self_comparisons": self_comparisons, "owner_to_front": owner_to_front,
        },
        "after": {},
    }
    evidence = json.dumps(audit, sort_keys=True)
    _telemetry.info(
        f"lever native thread callout audit: {evidence}",
        operation_stage=audit["stage"], auditJSON=evidence, failed_conditions="[]",
    )
    audit["setter_result"] = bool(note.SetText(native_text))
    if not audit["setter_result"]:
        raise RuntimeError("native lever thread drawing callout refused its print-only text")
    rebuild_drawing(adapter, label="omit title-block thread class from lever drawing callout")
    audit["stage"] = "readback"
    audit["read_errors"] = []
    audit["unavailable"] = {}
    after = audit["after"]
    missing = object()

    def read_field(field: str, member: str, reader: Any, *, record: bool = True) -> Any:
        """Collect independent native results; never invent a value on failure."""
        try:
            value = reader()
        except Exception as exc:
            audit["read_errors"].append({
                "field": field, "member": member, "kind": "exception",
                "type": type(exc).__name__, "message": str(exc),
            })
            return missing
        if record:
            after[field] = value
        if value is None:
            audit["read_errors"].append({
                "field": field, "member": member, "kind": "returned_none", "value": None,
            })
        return value

    annotation_fields = (
        "owner_type", "owner_present", "owner_same", "owner_self", "entities_reported",
        "attached_count", "attached_types", "entity_handles", "entity_same", "entity_self", "dangling",
    )
    current_entities = missing
    current = read_field("note_handle", "ICThread.ThreadCallout", lambda: _early_bound(thread.ThreadCallout, "INote"), record=False)
    if current is not missing:
        after["note_present"] = current is not None
    else:
        audit["unavailable"]["note_present"] = "note_handle"
    if current is not missing and current is not None:
        read_field("text", "INote.GetText", lambda: current.GetText())
        read_field("note_same", "ISldWorks.IsSame(note,current)", lambda: app.IsSame(note, current))
        read_field("note_self", "ISldWorks.IsSame(current,current)", lambda: app.IsSame(current, current))
        current_annotation = read_field(
            "annotation_handle", "INote.GetAnnotation",
            lambda: _early_bound(current.GetAnnotation(), "IAnnotation"), record=False,
        )
        if current_annotation is not missing:
            after["annotation_present"] = current_annotation is not None
        else:
            audit["unavailable"]["annotation_present"] = "annotation_handle"
        if current_annotation is not missing and current_annotation is not None:
            read_field("owner_type", "IAnnotation.OwnerType", lambda: current_annotation.OwnerType)
            current_owner = read_field("owner_handle", "IAnnotation.Owner", lambda: current_annotation.Owner, record=False)
            if current_owner is not missing:
                after["owner_present"] = current_owner is not None
            else:
                audit["unavailable"]["owner_present"] = "owner_handle"
            if current_owner is not missing and current_owner is not None:
                read_field("owner_same", "ISldWorks.IsSame(owner,current_owner)", lambda: app.IsSame(owner, current_owner))
                read_field("owner_self", "ISldWorks.IsSame(current_owner,current_owner)", lambda: app.IsSame(current_owner, current_owner))
            else:
                audit["unavailable"].update(dict.fromkeys(("owner_same", "owner_self"), "owner_handle"))
            # Nullable native attachment arrays are a valid empty inventory.
            current_entities = read_field(
                "attached_entities", "IAnnotation.GetAttachedEntities3",
                lambda: tuple(current_annotation.GetAttachedEntities3() or ()), record=False,
            )
            if current_entities is not missing:
                after["entities_reported"] = len(current_entities)
            else:
                audit["unavailable"]["entities_reported"] = "attached_entities"
            read_field("attached_count", "IAnnotation.GetAttachedEntityCount3", lambda: current_annotation.GetAttachedEntityCount3())
            read_field(
                "attached_types", "IAnnotation.GetAttachedEntityTypes",
                lambda: tuple(current_annotation.GetAttachedEntityTypes() or ()),
            )
            if current_entities is not missing:
                after["entity_same"], after["entity_self"] = [], []
                after["entity_handles"] = [
                    {"index": index, "present": entity is not None} for index, entity in enumerate(current_entities)
                ]
                # GetAttachedEntities3 can retain a null entry for an unavailable
                # entity. Its slot/count remain real; IsSame needs actual handles.
                for index, current_entity in enumerate(current_entities):
                    if current_entity is None:
                        dependency = f"attached_entities[{index}]"
                        audit["read_errors"].append({
                            "field": dependency, "member": "IAnnotation.GetAttachedEntities3",
                            "kind": "missing_entity_handle", "index": index, "value": None,
                            "reason": "native attachment array entry is None",
                        })
                        audit["unavailable"][f"entity_self[{index}]"] = dependency
                        if index < len(entities):
                            audit["unavailable"][f"entity_same[{index}]"] = dependency
                for index, (before_entity, current_entity) in enumerate(zip(entities, current_entities)):
                    if current_entity is None:
                        after["entity_same"].append({"index": index, "unavailable": True})
                        continue
                    code = read_field(
                        f"entity_same[{index}]", f"ISldWorks.IsSame(before_entity[{index}],current_entity[{index}])",
                        lambda: app.IsSame(before_entity, current_entity), record=False,
                    )
                    after["entity_same"].append(
                        {"index": index, "unavailable": True} if code is missing else {"index": index, "code": code}
                    )
                for index, current_entity in enumerate(current_entities):
                    if current_entity is None:
                        after["entity_self"].append({"index": index, "unavailable": True})
                        continue
                    code = read_field(
                        f"entity_self[{index}]", f"ISldWorks.IsSame(current_entity[{index}],current_entity[{index}])",
                        lambda: app.IsSame(current_entity, current_entity), record=False,
                    )
                    after["entity_self"].append(
                        {"index": index, "unavailable": True} if code is missing else {"index": index, "code": code}
                    )
            else:
                audit["unavailable"].update(dict.fromkeys(("entity_handles", "entity_same", "entity_self"), "attached_entities"))
            read_field("dangling", "IAnnotation.IsDangling", lambda: current_annotation.IsDangling())
        else:
            audit["unavailable"].update(dict.fromkeys(annotation_fields, "annotation_handle"))
    else:
        audit["unavailable"].update(dict.fromkeys(
            ("text", "note_same", "note_self", "annotation_present", *annotation_fields), "note_handle",
        ))
    # Only missing handles prevent dependent reads. A failed scalar/type reader
    # cannot hide the remaining ownership, attachment, identity or dangling data.
    conditions = {
        "note_present": after.get("note_present", False),
        "note_identity": after.get("note_same") == 1,
        "text": after.get("text") == native_text,
        "owner_type": after.get("owner_type") == owner_type,
        "owner_identity": after.get("owner_present", False) and after.get("owner_same") == 1,
        "attached_count": after.get("attached_count") == entity_count,
        "attached_types": after.get("attached_types") == entity_types,
        "entities_reported": after.get("entities_reported") == len(entities),
        "entity_identity": current_entities is not missing and all(
            entity is not None for entity in current_entities
        ) and all(item.get("code") == 1 for item in after.get("entity_same", ())),
        "dangling": after.get("dangling") == dangling,
    }
    audit["stage"] = "readback_complete"
    audit["conditions"] = conditions
    audit["failed"] = [name for name, passed in conditions.items() if not passed]
    if audit["read_errors"]:
        audit["failed"].append("reader_unavailable")
    evidence = json.dumps(audit, sort_keys=True, default=repr)
    _telemetry.info(
        f"lever native thread callout audit: {evidence}",
        operation_stage=audit["stage"], auditJSON=evidence,
        failed_conditions=json.dumps(audit["failed"]),
    )
    if audit["read_errors"]:
        raise RuntimeError(f"lever native thread callout readback failed; audit={evidence}")
    if not conditions["note_present"] or not conditions["note_identity"]:
        raise RuntimeError(f"lever thread text mutation replaced its native drawing callout; audit={evidence}")
    if audit["failed"]:
        raise RuntimeError(f"lever thread drawing callout lost its text, ownership or native attachment; audit={evidence}")



async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    check("open quarter-inch lever source", await adapter.open_model(str(SOURCE)))
    read_required_properties(adapter.currentModel, ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity", "Iso View Note"), required=("Number", "Material Specification", "Finish", "Quantity", "Iso View Note"))
    drawing, _sheet = new_project_drawing(adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout)
    stamp_drawing_summary(adapter, drawing, {0: "Magnifying Lever Rod Manufacturing Drawing", 1: "Harmonic Analyzer hobby-machinist book drawing", 2: "Harmonic Analyzer Project", 3: "quarter-inch brass lever; flat UNC-2A end; external die runout", 4: "Generated from the project-owned ASME B drawing standard"})
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    # Import the small details first: the same RodProfile owns the full view.
    detail, detailed = _detail(adapter)
    full = curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="lever full length", dimensions_by_feature=DRAWING_DIMENSIONS)
    annotations = [*detailed, *full]
    assert_imported_precision(adapter, annotations, {name: places for names in DRAWING_PRECISION.values() for name, places in names.items()})
    set_dimension_callouts(adapter, annotations, CALLOUTS)
    thread_pick = model_point_in_view(adapter, detail, (0.158, ROD_DIA / 2000.0, 0.0), label="lever thread callout landing")
    add_attached_note(adapter, detail, text=DETAIL_THREAD_CALLOUT, entity_xy=thread_pick, note_xy=DETAIL_THREAD_NOTE_XY, label="native quarter-inch external thread", entity_type="SILHOUETTE")
    free_end = _free_end_face(adapter, front, annotations)
    add_attached_note(adapter, front, text=FREE_END_CALLOUT, entity=free_end, attached_to=free_end, note_xy=(0.030, 0.185), label="free end hemisphere", entity_type="FACE")
    seat_pick = model_point_in_view(adapter, front, (0.040, ROD_DIA / 4000.0, 0.0), label="whole-body screw seat finish")
    symbol = (seat_pick[0] - 0.010, FRONT_CENTER[1] + 0.020)
    add_surface_finish(adapter, front, edge_xy=seat_pick, entity_type="FACE", symbol_xy=symbol, leader_attach_xy=seat_pick, control=surface_finish_by_key(SURFACE_FINISHES, "clamp_screw_seat"), label="lever clamp screw seat finish", char_height=0.0025)
    _note(adapter, front, SCREW_SEAT_CALLOUT, (symbol[0] - 0.0025, symbol[1] + 0.013))
    focus = model_point_in_view(adapter, front, DETAIL_FOCUS, label="parent thread-detail mark")
    _circle(adapter, front, focus, DETAIL_RADIUS_MM / 1000.0, mark=True)
    _note(adapter, front, "A", (focus[0] + 0.016, focus[1] + 0.016))
    _note(adapter, detail, "DETAIL A  SCALE 3:1", (0.277, 0.142))
    add_property_linked_note(adapter, "Iso View Note", 0.320, 0.071)
    seeds, instances = import_cosmetic_threads(adapter, iso)
    if (seeds, instances) != (1, 1):
        raise RuntimeError(f"lever isometric external thread missing: {(seeds, instances)}")
    _print_native_thread_callout(adapter, front)
    return await finalize_drawing(adapter, OUTPUTS, pdf_title="Magnifying Lever Rod Manufacturing Drawing", scale=SHEET_SCALE, layout=SPEC.layout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
