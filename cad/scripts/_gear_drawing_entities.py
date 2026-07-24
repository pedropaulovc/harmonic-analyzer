"""Fast source-model topology helpers for the curated gear drawings.

Dense gear projections make drawing-view visible-entity enumeration extremely
expensive. Resolve annotation faces from the referenced part instead; SolidWorks
can select those model entities directly through ``IView.SelectEntity``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import _telemetry
from _common import _early_bound
from _drawing_common import referenced_model_faces


_SOURCE_FACE_SCAN_LIMIT = 512
_AXIAL_NORMAL_TOLERANCE = 1e-6
_RADIUS_TOLERANCE_MM = 0.01


@dataclass(frozen=True)
class GearModelFaces:
    bore: Any
    end: Any
    tooth_tip: Any | None


def _face_vertex_points(adapter: Any, face: Any) -> list[tuple[float, float, float]]:
    points: list[tuple[float, float, float]] = []
    edges = adapter._attempt(lambda: face.GetEdges(), default=None) or ()
    for raw_edge in edges:
        edge = _early_bound(raw_edge, "IEdge", "GetStartVertex", "GetEndVertex")
        for vertex in (edge.GetStartVertex(), edge.GetEndVertex()):
            if vertex is None:
                continue
            point = _early_bound(vertex, "IVertex", "GetPoint").GetPoint()
            points.append(tuple(float(value) for value in point[:3]))
    return points


@_telemetry.traced("drawing.gear_model_faces", label_param="label")
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
    if len(faces) > _SOURCE_FACE_SCAN_LIMIT:
        raise RuntimeError(
            f"{label}: {len(faces)} source faces exceed the bounded "
            f"classification limit {_SOURCE_FACE_SCAN_LIMIT}"
        )
    bore_radius = bore_diameter_mm / 2.0
    tip_radius = None if tooth_tip_diameter_mm is None else tooth_tip_diameter_mm / 2.0
    bore = None
    axial_ends: list[tuple[float, Any]] = []
    tooth_tips: list[tuple[float, Any]] = []
    # The gear axis is +Z in every source part. The standard *Right drawing
    # projection looks along X and has +Y at the top, so the source face nearest
    # (0, +outside-radius, mid-face Z) is the visible top tooth-tip envelope.
    for raw_face in reversed(faces):
        face = _early_bound(
            raw_face,
            "IFace2",
            "GetArea",
            "GetClosestPointOn",
            "GetEdges",
        )
        surface = face.GetSurface()
        if surface is None:
            continue
        surface = _early_bound(surface, "ISurface")
        if surface.IsPlane():
            plane = tuple(float(value) for value in surface.PlaneParams)
            if len(plane) >= 3 and abs(abs(plane[2]) - 1.0) <= _AXIAL_NORMAL_TOLERANCE:
                area = float(
                    adapter._attempt(lambda f=face: f.GetArea(), default=0.0) or 0.0
                )
                axial_ends.append((area, face))
            continue
        if not surface.IsCylinder():
            continue
        radius_mm = float(surface.CylinderParams[6]) * 1000.0
        if bore is None and abs(radius_mm - bore_radius) <= _RADIUS_TOLERANCE_MM:
            bore = face
        if tip_radius is None or abs(radius_mm - tip_radius) > _RADIUS_TOLERANCE_MM:
            continue
        points = _face_vertex_points(adapter, face)
        if not points:
            continue
        z_mid = (
            min(point[2] for point in points) + max(point[2] for point in points)
        ) / 2.0
        target = (0.0, tip_radius / 1000.0, z_mid)
        closest = adapter._attempt(
            lambda f=face, p=target: f.GetClosestPointOn(*p), default=None
        )
        if closest is None or len(closest) < 3:
            continue
        distance = math.dist(target, tuple(float(value) for value in closest[:3]))
        tooth_tips.append((distance, face))

    end = max(axial_ends, key=lambda candidate: candidate[0])[1] if axial_ends else None
    tooth_tip = (
        min(tooth_tips, key=lambda candidate: candidate[0])[1] if tooth_tips else None
    )

    if bore is None:
        raise RuntimeError(f"{label}: no bore face at radius {bore_radius:.4f} mm")
    if end is None:
        raise RuntimeError(f"{label}: no planar end face")
    if tip_radius is not None and tooth_tip is None:
        raise RuntimeError(f"{label}: no tooth-tip face at radius {tip_radius:.4f} mm")
    return GearModelFaces(bore=bore, end=end, tooth_tip=tooth_tip)
