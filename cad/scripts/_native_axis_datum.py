"""Native-positioned axis datums for the lift rod and rack-pinion drawings.

This deliberately narrow helper does not change the general datum helper or
request a sheet position. Stability is measured from SolidWorks' own placement;
cold reopen, move/scale and current-ink print checks remain separate gates.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Literal, Sequence

import _drawing_common as drawing
import _telemetry
from _common import _early_bound


def _axis_parameters(
    parameters: Sequence[float], *, radius_m: float, label: str
) -> None:
    """Match the circle/cylinder to the intended origin-Z axis and radius."""
    values = tuple(parameters)
    if len(values) != 7 or not all(
        type(value) in (int, float) and math.isfinite(value) for value in values
    ):
        raise RuntimeError(f"{label}: invalid datum axis parameters {values!r}")
    # Geometric identification bounds from the native lifecycle positive
    # control; independent of manufacturing and sheet-position tolerances.
    if max(
        abs(values[0]), abs(values[1]), abs(values[3]), abs(values[4]),
        abs(abs(values[5]) - 1.0), abs(values[6] - radius_m),
    ) > 1e-8:
        raise RuntimeError(f"{label}: datum does not control the intended Z axis")


def _validate_source_edge(
    app: Any, view: Any, entity: Any, source_path: Path,
    *, radius_m: float, label: str,
) -> tuple[int, int]:
    reference = view.ReferencedDocument
    if reference is None or reference == "":
        raise RuntimeError(f"{label}: datum view has no referenced source part")
    model = _early_bound(reference, "IModelDoc2")
    actual_path = str(model.GetPathName() or "")
    if int(model.GetType()) != 1:  # swDocumentTypes_e.swDocPART
        raise RuntimeError(f"{label}: datum view does not reference a part")
    if not actual_path or Path(actual_path).resolve() != source_path:
        raise RuntimeError(f"{label}: datum view references the wrong source path")
    part = _early_bound(model, "IPartDoc")
    bodies = tuple(part.GetBodies2(0, False) or ())  # swBodyType_e.swSolidBody
    if len(bodies) != 1 or bodies[0] is None:
        raise RuntimeError(f"{label}: source must have exactly one solid body")
    # Drawing-context edges and their bodies are not the source-part objects.
    # Map into the verified source, then require the exact view-edge roundtrip;
    # neither same-radius geometry nor a raw cross-context body comparison
    # establishes this correspondence (native receipt: body-correspondence.json).
    extension = _early_bound(model.Extension, "IModelDocExtension")
    canonical = extension.GetCorrespondingEntity2(entity)
    if canonical is None:
        raise RuntimeError(f"{label}: drawing edge has no source correspondence")
    roundtrip = view.GetCorrespondingEntity(canonical)
    if roundtrip is None or int(app.IsSame(roundtrip, entity)) != 1:
        raise RuntimeError(f"{label}: datum source-to-view roundtrip is missing or different")
    edge = _early_bound(canonical, "IEdge")
    body = edge.GetBody()
    if body is None or int(app.IsSame(body, bodies[0])) != 1:
        raise RuntimeError(f"{label}: datum edge belongs to a different source body")
    raw_curve = edge.GetCurve()
    if raw_curve is None:
        raise RuntimeError(f"{label}: datum edge has no curve")
    curve = _early_bound(raw_curve, "ICurve")
    if not curve.IsCircle():
        raise RuntimeError(f"{label}: datum edge is not circular")
    _axis_parameters(curve.CircleParams or (), radius_m=radius_m, label=label)
    faces = tuple(edge.GetTwoAdjacentFaces2() or ())
    if len(faces) != 2 or any(face is None for face in faces):
        raise RuntimeError(f"{label}: datum edge requires exactly two adjacent faces")
    if int(app.IsSame(faces[0], faces[1])) != 0:
        raise RuntimeError(f"{label}: datum adjacent faces are duplicate or unknown")
    cylinders = []
    for raw_face in faces:
        face = _early_bound(raw_face, "IFace2")
        raw_surface = face.GetSurface()
        if raw_surface is None:
            raise RuntimeError(f"{label}: adjacent datum face has no surface")
        surface = _early_bound(raw_surface, "ISurface")
        if surface.IsCylinder():
            cylinders.append(tuple(surface.CylinderParams or ()))
    if len(cylinders) != 1:
        raise RuntimeError(
            f"{label}: datum edge bounds {len(cylinders)} cylinders; expected one"
        )
    _axis_parameters(cylinders[0], radius_m=radius_m, label=label)
    return len(bodies), len(faces)


def _readback(
    app: Any, view: Any, inserted: Any, entity: Any, *, datum: str, label: str,
) -> tuple[tuple[float, float], Literal["straight", "shouldered"], int]:
    tags = tuple(view.GetDatumTags() or ())
    if len(tags) != 1 or tags[0] is None or int(app.IsSame(tags[0], inserted)) != 1:
        raise RuntimeError(f"{label}: native datum insertion is missing or stale")
    tag = _early_bound(tags[0], "IDatumTag")
    raw_annotation = tag.GetAnnotation()
    if raw_annotation is None:
        raise RuntimeError(f"{label}: native datum has no annotation")
    annotation = _early_bound(raw_annotation, "IAnnotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    types = tuple(annotation.GetAttachedEntityTypes() or ())
    if len(attached) != 1 or types != (1,) or attached[0] is None:
        raise RuntimeError(
            f"{label}: native datum needs one attached edge; "
            f"count={len(attached)}, types={types!r}"
        )
    # swObjectSame = 1; both different (0) and unknown (-1) fail.
    attachment_equality = int(app.IsSame(attached[0], entity))
    if attachment_equality != 1:
        raise RuntimeError(f"{label}: native datum attached to a different edge")
    if annotation.IsDangling():
        raise RuntimeError(f"{label}: native datum is dangling")
    if str(tag.GetLabel()) != datum:
        raise RuntimeError(f"datum feature label did not persist ({label})")
    position = tuple(annotation.GetPosition() or ())
    if len(position) != 3 or not all(
        type(value) in (int, float) and math.isfinite(value) for value in position
    ):
        raise RuntimeError(f"{label}: native datum has invalid position {position!r}")
    return (
        (position[0], position[1]),
        "shouldered" if tag.Shoulder else "straight",
        attachment_equality,
    )


@_telemetry.traced("drawing.native_axis_datum", label_param="label")
def add_native_axis_datum(
    adapter: Any, view: Any, *, entity: Any, source_path: Path,
    radius_m: float, datum: str, label: str, stability_tolerance_m: float,
    shoulder: bool = False,
) -> Any:
    """Let SolidWorks place one origin-Z cylinder datum; verify its stability.

    The two consuming parts must each have exactly one solid body. The view
    must initially contain no datum tags. The unchanged recipe-specific 20/100
    um limits bound native XY drift across rebuild, not requested-XY accuracy.
    """
    if entity is None:
        raise ValueError(f"{label}: native datum requires an explicit EDGE entity")
    if (
        type(stability_tolerance_m) not in (int, float)
        or not math.isfinite(stability_tolerance_m) or stability_tolerance_m <= 0.0
    ):
        raise ValueError(f"{label}: native stability tolerance must be finite and positive")
    if (
        type(radius_m) not in (int, float)
        or not math.isfinite(radius_m) or radius_m <= 0.0
    ):
        raise ValueError(f"{label}: native radius must be finite and positive")
    if not datum or len(datum) > 2:
        raise ValueError(f"{label}: datum label must contain one or two characters")
    source_path = Path(source_path).resolve(strict=True)
    if not source_path.is_file() or source_path.suffix.casefold() != ".sldprt":
        raise ValueError(f"{label}: source must be an existing SLDPRT file")
    draw = _early_bound(adapter.currentModel, "IModelDoc2")
    if int(draw.GetType()) != 3:  # swDocumentTypes_e.swDocDRAWING
        raise RuntimeError(f"{label}: native datum requires an active drawing")
    view = _early_bound(view, "IView")
    app = adapter.swApp
    _validate_source_edge(app, view, entity, source_path, radius_m=radius_m, label=label)
    if view.GetDatumTags():
        raise RuntimeError(f"{label}: native axis view already has datum tags")
    selected = drawing._select_annotation_entity(
        adapter, view, edge_xy=None, edge_entity=None, entity=entity,
        entity_type="EDGE", label=label,
    )
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    if int(manager.GetSelectedObjectCount2(-1)) != 1:
        raise RuntimeError(f"{label}: expected exactly one selected datum edge")
    if selected is None or int(app.IsSame(selected, entity)) != 1:
        raise RuntimeError(f"{label}: drawing selected a different datum edge")
    raw_tag = draw.InsertDatumTag2()
    if raw_tag is None:
        raise RuntimeError(f"failed to insert datum {datum} ({label})")
    tag = _early_bound(raw_tag, "IDatumTag")
    if not tag.SetLabel(datum):
        raise RuntimeError(f"failed to label datum feature {datum} ({label})")
    if shoulder:
        tag.Shoulder = True
    baseline_xy, baseline_shoulder, _baseline_equality = _readback(
        app, view, tag, entity, datum=datum, label=label
    )
    if shoulder and baseline_shoulder != "shouldered":
        raise RuntimeError(f"{label}: native datum shoulder did not persist")
    draw.ClearSelection2(True)
    if not draw.EditRebuild3():
        raise RuntimeError(f"{label}: native datum rebuild failed")
    body_count, adjacent_face_count = _validate_source_edge(
        app, view, entity, source_path, radius_m=radius_m, label=label
    )
    actual_xy, actual_shoulder, attachment_equality = _readback(
        app, view, tag, entity, datum=datum, label=label
    )
    if actual_shoulder != baseline_shoulder:
        raise RuntimeError(f"{label}: native datum shoulder changed on rebuild")
    stability_error_m = math.dist(actual_xy, baseline_xy)
    if stability_error_m > stability_tolerance_m:
        raise RuntimeError(
            f"datum {datum} native position did not persist ({label}): "
            f"{actual_xy}; baseline={baseline_xy}, "
            f"stability_error={stability_error_m:.6g} m, "
            f"stability_limit={stability_tolerance_m:.6g} m"
        )
    span = _telemetry.trace.get_current_span()
    for key, value in {
        "source_path": str(source_path), "radius_m": radius_m,
        "native_baseline_xy_m": baseline_xy, "native_actual_xy_m": actual_xy,
        "stability_error_m": stability_error_m,
        "stability_tolerance_m": stability_tolerance_m,
        "adjacent_face_count": adjacent_face_count, "body_count": body_count,
        "attachment_equality": attachment_equality,
        "shoulder_state": actual_shoulder, "datum": datum,
    }.items():
        span.set_attribute(key, value)
    return tag
