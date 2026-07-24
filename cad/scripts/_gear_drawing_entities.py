"""Fast source-model topology helpers for the curated gear drawings.

Dense gear projections make drawing-view visible-entity enumeration extremely
expensive. Resolve annotation faces from the referenced part instead; SolidWorks
can select those model entities directly through ``IView.SelectEntity``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from _common import _early_bound
from _drawing_common import referenced_model_faces


@dataclass(frozen=True)
class GearModelFaces:
    bore: Any
    end: Any
    tooth_tip: Any | None


def _face_vertex_radii(adapter: Any, face: Any) -> list[float]:
    radii: list[float] = []
    edges = adapter._attempt(lambda: face.GetEdges(), default=None) or ()
    for raw_edge in edges:
        edge = _early_bound(raw_edge, "IEdge", "GetStartVertex", "GetEndVertex")
        for vertex in (edge.GetStartVertex(), edge.GetEndVertex()):
            if vertex is None:
                continue
            point = _early_bound(vertex, "IVertex", "GetPoint").GetPoint()
            radii.append(math.hypot(float(point[0]), float(point[1])) * 1000.0)
    return radii


def gear_model_faces(
    adapter: Any,
    view: Any,
    bore_diameter_mm: float,
    *,
    label: str,
    tooth_tip_diameter_mm: float | None = None,
) -> GearModelFaces:
    """Resolve gear faces from the source part in one COM walk.

    Drawing-view visible-entity enumeration forces hidden-line resolution of
    every tooth.  Source-model faces select directly through ``IView`` and let
    the bore, axial end and optional tooth-tip controls share one traversal.
    """
    faces = referenced_model_faces(adapter, view, label=label)
    bore_radius = bore_diameter_mm / 2.0
    tip_radius = None if tooth_tip_diameter_mm is None else tooth_tip_diameter_mm / 2.0
    bore = None
    end = None
    # The final modeling operations own the bore and axial end faces. Walk
    # backward and stop as soon as both identities are proven; do not classify
    # hundreds of patterned tooth faces.
    for raw_face in reversed(faces):
        face = _early_bound(raw_face, "IFace2", "GetEdges")
        surface = face.GetSurface()
        if surface is None:
            continue
        surface = _early_bound(surface, "ISurface")
        if end is None and surface.IsPlane():
            end = face
        if bore is None and surface.IsCylinder():
            radius_mm = float(surface.CylinderParams[6]) * 1000.0
            if abs(radius_mm - bore_radius) <= 0.01:
                bore = face
        if bore is not None and end is not None:
            break

    tooth_tip = None
    if tip_radius is not None:
        # A patterned gear starts with one tooth's root/fillet/flank/tip face
        # group. Check only that bounded seed neighborhood. A tip face has all
        # boundary vertices on the requested outside radius; flank and fillet
        # faces span inward and cannot pass this predicate.
        for raw_face in faces[:32]:
            face = _early_bound(raw_face, "IFace2", "GetEdges")
            radii = _face_vertex_radii(adapter, face)
            if radii and max(abs(radius - tip_radius) for radius in radii) <= 0.05:
                tooth_tip = face
                break

    if bore is None:
        raise RuntimeError(f"{label}: no bore face at radius {bore_radius:.4f} mm")
    if end is None:
        raise RuntimeError(f"{label}: no planar end face")
    if tip_radius is not None and tooth_tip is None:
        raise RuntimeError(f"{label}: no tooth-tip face at radius {tip_radius:.4f} mm")
    return GearModelFaces(bore=bore, end=end, tooth_tip=tooth_tip)
