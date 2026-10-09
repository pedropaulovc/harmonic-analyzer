"""Native model-linked toothspace ink on a proved physical stock-form flank.

This narrow paper-drive seam owns drawing/source edge correspondence and
geometry readback, not cutter equations, inspection grades or manufacture.
The caller supplies the actual source profile, certified pin, phase, allowed
physical end faces and seed/pattern feature identities. An arrow count or a
nearby OD/root edge cannot substitute for that semantic proof.
"""

from __future__ import annotations

import math
from typing import Any
import struct

from _common import _early_bound
from _drawing_common import add_property_linked_callout, model_point_in_view, property_link
from paper_drive_stock_inspection import GaugeContact, toothspace_gauge_contact_mm
from stock_form_cutter import StockFormProfile


def _vector(raw: Any, count: int, label: str) -> tuple[float, ...]:
    if raw is None:
        raise RuntimeError(f"{label}: no native numerical array")
    values = tuple(raw)
    if len(values) != count or any(
        type(value) not in (int, float) or not math.isfinite(value) for value in values
    ):
        raise RuntimeError(f"{label}: invalid native numerical array")
    return tuple(float(value) for value in values)


def _rotate(point: tuple[float, float], angle: float) -> tuple[float, float]:
    c, s = math.cos(angle), math.sin(angle)
    return c * point[0] - s * point[1], s * point[0] + c * point[1]




def _source_edge(
    adapter: Any, view: Any, drawing_edge: Any, tooth_features: tuple[str, ...]
) -> Any:
    """Prove the source-body roundtrip and an actual named tooth-cut face."""
    app = _early_bound(adapter.swApp, "ISldWorks")
    native_view = _early_bound(view, "IView")
    reference = native_view.ReferencedDocument
    if reference is None:
        raise RuntimeError("toothspace callout: no referenced source part")
    model = _early_bound(reference, "IModelDoc2")
    if int(model.GetType()) != 1:
        raise RuntimeError("toothspace callout: referenced source is not a part")
    part = _early_bound(reference, "IPartDoc")
    raw_bodies = part.GetBodies2(0, False)
    if raw_bodies is None:
        raise RuntimeError("toothspace callout: no source solid body array")
    bodies = tuple(raw_bodies)
    if len(bodies) != 1 or bodies[0] is None or int(_early_bound(bodies[0], "IBody2").GetType()) != 0:
        raise RuntimeError("toothspace callout: expected one genuine source solid")
    raw_extension = model.Extension
    if raw_extension is None:
        raise RuntimeError("toothspace callout: no source document extension")
    canonical = _early_bound(raw_extension, "IModelDocExtension").GetCorrespondingEntity2(drawing_edge)
    if canonical is None:
        raise RuntimeError("toothspace callout: selected edge has no source correspondence")
    roundtrip = native_view.GetCorrespondingEntity(canonical)
    if roundtrip is None or int(app.IsSame(roundtrip, drawing_edge)) != 1:
        raise RuntimeError("toothspace callout: source/view edge roundtrip differs")
    edge = _early_bound(canonical, "IEdge")
    body = edge.GetBody()
    if body is None or int(app.IsSame(body, bodies[0])) != 1:
        raise RuntimeError("toothspace callout: selected edge belongs to another body")
    wanted = []
    for name in tooth_features:
        feature = part.FeatureByName(name)
        if feature is None:
            raise RuntimeError(f"toothspace callout: missing authored tooth feature {name!r}")
        wanted.append(feature)
    raw_faces = edge.GetTwoAdjacentFaces2()
    if raw_faces is None:
        raise RuntimeError("toothspace callout: edge has no adjacent faces")
    faces = tuple(raw_faces)
    if len(faces) != 2 or any(face is None for face in faces):
        raise RuntimeError("toothspace callout: expected two genuine adjacent faces")
    if int(app.IsSame(faces[0], faces[1])) != 0:
        raise RuntimeError("toothspace callout: adjacent face identity is duplicate or unknown")
    authored = False
    for raw_face in faces:
        face = _early_bound(raw_face, "IFace2")
        face_body = face.GetBody()
        if face_body is None or int(app.IsSame(face_body, bodies[0])) != 1:
            raise RuntimeError("toothspace callout: adjacent face belongs to another body")
        feature = face.GetFeature()
        if feature is None:
            raise RuntimeError("toothspace callout: adjacent face has no source feature")
        if any(int(app.IsSame(feature, expected)) == 1 for expected in wanted):
            authored = True
    if not authored:
        raise RuntimeError("toothspace callout: edge is not on the declared tooth-cut feature family")
    return edge


def _validate_flank_edge(
    edge: Any, profile: StockFormProfile, contact: GaugeContact,
    rotate_rad: float, axial_stations_mm: tuple[float, ...],
) -> None:
    """Match actual trimmed endpoints, interior contact and native tangent."""
    raw_curve = edge.GetCurve()
    if raw_curve is None:
        raise RuntimeError("toothspace callout: native flank edge has no curve")
    curve = _early_bound(raw_curve, "ICurve")
    if curve.IsCircle() is True or curve.IsLine() is True:
        raise RuntimeError("toothspace callout: an OD/root circle or straight edge is not a formed flank")
    raw_parameters = edge.GetCurveParams3()
    if raw_parameters is None:
        raise RuntimeError("toothspace callout: native flank edge has no trimmed parameters")
    parameters = _early_bound(raw_parameters, "ICurveParamData")
    u0, u1 = float(parameters.UMinValue), float(parameters.UMaxValue)
    if not math.isfinite(u0) or not math.isfinite(u1) or u0 == u1:
        raise RuntimeError("toothspace callout: native flank has no finite parameter extent")
    low, high = min(u0, u1), max(u0, u1)
    actual_ends = (
        _vector(parameters.StartPoint, 3, "flank start"),
        _vector(parameters.EndPoint, 3, "flank end"),
    )
    # The solver's centre enclosure already contains the core's geometry
    # charge. Take the maximum, not a duplicate sum of that same error.
    error_mm = 1e-6 + max(2.0 * profile.geometry_error_bound_mm, contact.center_radius_error_bound_mm)
    error_m = error_mm / 1000.0
    pure_ends = tuple(
        _rotate(profile.flank_point(parameter), rotate_rad)
        for parameter in (profile.flank_parameter_min, profile.flank_parameter_max)
    )
    point = _rotate(contact.flank_point_mm, rotate_rad)
    station = None
    closest = None
    for z in axial_stations_mm:
        expected = (point[0] / 1000.0, point[1] / 1000.0, z / 1000.0)
        candidate = _vector(curve.GetClosestPointOn(*expected), 5, "flank closest point")
        if math.dist(candidate[:3], expected) <= error_m and low < candidate[3] < high:
            station, closest = z, candidate
            break
    if station is None or closest is None:
        raise RuntimeError("toothspace callout: edge misses the actual supported finite-flank gauge contact")
    expected_ends = tuple((x / 1000.0, y / 1000.0, station / 1000.0) for x, y in pure_ends)
    if not any(
        all(math.dist(actual_ends[index], expected_ends[order[index]]) <= error_m for index in (0, 1))
        for order in ((0, 1), (1, 0))
    ):
        raise RuntimeError("toothspace callout: native edge endpoints are not the declared finite flank")
    evaluated = _vector(curve.Evaluate2(closest[3], 1), 7, "flank point and first derivative")
    # Evaluate2's final double packs two LONGs; the low LONG is success=1.
    if struct.unpack("<ii", struct.pack("<d", evaluated[6]))[0] != 1:
        raise RuntimeError("toothspace callout: native curve evaluation failed")
    if math.dist(evaluated[:3], closest[:3]) > error_m:
        raise RuntimeError("toothspace callout: native curve parameter readback changed")
    derivative = evaluated[3:6]
    length = math.sqrt(math.fsum(value * value for value in derivative))
    if length <= 0.0:
        raise RuntimeError("toothspace callout: native flank has no tangent")
    actual_tangent = tuple(value / length for value in derivative)
    angle = profile.template.half_space_base_angle_rad + contact.parameter + rotate_rad
    expected_tangent = (math.cos(angle), math.sin(angle), 0.0)
    curvature_radius = profile.template.base_radius_mm * contact.parameter
    if curvature_radius <= 0.0:
        raise RuntimeError("toothspace callout: actual supported flank has no resolved curvature radius")
    angle_error = 2.0 * error_mm / curvature_radius + 64.0 * math.ulp(1.0)
    if min(
        math.dist(actual_tangent, expected_tangent),
        math.dist(actual_tangent, tuple(-value for value in expected_tangent)),
    ) > angle_error:
        raise RuntimeError("toothspace callout: native tangent is not the physical formed flank")


def add_toothspace_callout(
    adapter: Any, view: Any, *, profile: StockFormProfile,
    actual_pin_diameter_mm: float, rotate_rad: float,
    axial_stations_mm: tuple[float, ...], tooth_features: tuple[str, ...],
    property_name: str, note_xy: tuple[float, float],
) -> Any:
    """One model-linked indicator arrow; reject wrong geometry/body/feature."""
    if not isinstance(profile, StockFormProfile) or profile.helix_angle_deg != 0.0:
        raise ValueError("toothspace callout requires the actual straight finite stock profile")
    if not math.isfinite(rotate_rad) or not axial_stations_mm or any(
        not math.isfinite(station) for station in axial_stations_mm
    ):
        raise ValueError("toothspace callout requires finite physical end-face stations")
    if not tooth_features or any(type(name) is not str or not name for name in tooth_features):
        raise ValueError("toothspace callout requires explicit source tooth-feature identities")
    contact = toothspace_gauge_contact_mm(profile, actual_pin_diameter_mm)
    x, y = _rotate(contact.flank_point_mm, rotate_rad)
    edge_xy = model_point_in_view(
        adapter, view, (x / 1000.0, y / 1000.0, axial_stations_mm[0] / 1000.0),
        label="physical finite-flank toothspace contact",
    )
    note = add_property_linked_callout(
        adapter, view, property_name=property_name, edge_xy=edge_xy, note_xy=note_xy,
    )
    native_note = _early_bound(note, "INote")
    source = _early_bound(view, "IView").ReferencedDocument
    if source is None:
        raise RuntimeError("toothspace callout: no source for linked inspection ink")
    source_text = _early_bound(source, "IModelDoc2").GetCustomInfoValue("", property_name)
    if type(source_text) is not str or not source_text:
        raise RuntimeError("toothspace callout: source inspection property is absent")
    if native_note.PropertyLinkedText != property_link(property_name):
        raise RuntimeError("toothspace callout: native ink is not linked to the source property")
    resolved_text = native_note.GetText()
    if type(resolved_text) is not str or resolved_text.replace("\r\n", "\n") != source_text.replace("\r\n", "\n"):
        raise RuntimeError("toothspace callout: resolved native ink differs from the source inspection property")
    raw_annotation = native_note.GetAnnotation()
    if raw_annotation is None:
        raise RuntimeError("toothspace callout: no native annotation readback")
    annotation = _early_bound(raw_annotation, "IAnnotation")
    raw_attached = annotation.GetAttachedEntities3()
    raw_types = annotation.GetAttachedEntityTypes()
    if raw_attached is None or raw_types is None:
        raise RuntimeError("toothspace callout: no native attachment readback")
    attached, types = tuple(raw_attached), tuple(raw_types)
    if len(attached) != 1 or attached[0] is None or types != (1,):
        raise RuntimeError("toothspace callout: expected exactly one actual EDGE attachment")
    if annotation.IsDangling() is not False or int(annotation.GetLeaderCount()) != 1:
        raise RuntimeError("toothspace callout: native edge/leader attachment is dangling")
    source_edge = _source_edge(adapter, view, attached[0], tooth_features)
    _validate_flank_edge(source_edge, profile, contact, rotate_rad, axial_stations_mm)
    return note
