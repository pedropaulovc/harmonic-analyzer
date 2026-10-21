"""Behavioral doubles for the pre-save native receiver/profile certificates.

No SolidWorks session is started: Main owns real-seat validation. These doubles
model exact circular trims, finite face witnesses and sketch association points.
"""
from __future__ import annotations

import math
from types import SimpleNamespace as NS

import pytest

import build_sm_summing_lever as lever
from magnifying_bracket_joint_layout import cone_notch_closest_advance


def _m(point):
    return tuple(value / 1000 for value in point)


def _surface(kind, params):
    return NS(IsCylinder=lambda: kind == "cylinder", IsCone=lambda: kind == "cone",
              IsPlane=lambda: kind == "plane", CylinderParams=params,
              ConeParams2=params, PlaneParams=params)


def _ring(x, z, radius):
    curve = NS(IsCircle=lambda: True, CircleParams=(*_m((x, 0, z)), 0, 0, 1, radius / 1000))
    return NS(GetCurve=lambda: curve, GetStartVertex=lambda: None, GetEndVertex=lambda: None)


def _receiver(monkeypatch):
    monkeypatch.setattr(lever, "_early_bound", lambda obj, _interface: obj)
    logs = []
    monkeypatch.setattr(lever._telemetry, "info", logs.append)
    monkeypatch.setattr(lever._telemetry, "success", logs.append)
    entry = lever.LEVER_HOLE_POINTS[0][2]
    shoulder = entry + lever.DRILL_DEPTH
    rear = entry + lever.RECEIVER_RIB_T
    radius = lever.TAP_DRILL_DIA / 2
    hole_faces = []
    for x, _y, _z in lever.LEVER_HOLE_POINTS:
        for kind in ("cylinder", "cone"):
            params = (*_m((x, 0, shoulder)), 0, 0, 1, radius / 1000)
            if kind == "cone":
                params += (math.atan(radius / lever.DRILL_POINT_DEPTH), 1, 0, 0)
            surface = _surface(kind, params)
            edges = [_ring(x, shoulder, radius)]
            if kind == "cylinder":
                edges.append(_ring(x, entry, radius))
            else:
                tip = NS(GetPoint=lambda x=x: _m((x, 0, shoulder + lever.DRILL_POINT_DEPTH)))
                edges.append(NS(GetCurve=lambda: NS(IsCircle=lambda: False),
                                GetStartVertex=lambda tip=tip: tip, GetEndVertex=lambda: None))
            hole_faces.append(NS(kind=kind, x=x, GetSurface=lambda s=surface: s,
                                 GetEdges=lambda e=edges: e,
                                 GetFeature=lambda: NS(Name="BracketMountingTaps")))
    outside = []
    for label, plane in (
        ("entry", (0, 0, 1, 0, 0, entry / 1000)),
        ("cap", (0, 0, 1, 0, 0, rear / 1000)),
        ("underside", (0, 1, 0, 0, -lever.PLATE_T / 2000, 0)),
        ("other", (1, 0, 0, 0.2, 0, 0)),
    ):
        surface = _surface("plane", plane)
        outside.append(NS(label=label, GetSurface=lambda s=surface: s,
                          GetFeature=lambda: NS(Name="Casting")))
    calls = []

    def closest(hole, face):
        calls.append((hole.x, hole.kind, face.label))
        assert face.label != "entry", "intentional hole mouth must be excluded"
        advance = 0 if hole.kind == "cylinder" else cone_notch_closest_advance(
            lever.RECEIVER_RIB_T - lever.DRILL_DEPTH, lever.PLATE_T / 2, radius)
        radial = radius * (1 - advance / lever.DRILL_POINT_DEPTH)
        a = (hole.x, -radial, shoulder + advance)
        b = (hole.x, -lever.PLATE_T / 2, rear)
        if face.label == "other":
            b = (hole.x + 20, a[1], a[2])
        return math.dist(a, b) / 1000, _m(a), _m(b)

    feature = NS(GetFaces=lambda: hole_faces)
    body = NS(GetFaces=lambda: hole_faces + outside)
    model = NS(FeatureByName=lambda name: feature if name == "BracketMountingTaps" else None,
               GetBodies2=lambda *_: (body,), ClosestDistance=closest)
    return NS(currentModel=model), hole_faces, outside, calls, logs


def test_both_holes_cylinders_and_cones_use_finite_faces(monkeypatch):
    adapter, _holes, _outside, calls, logs = _receiver(monkeypatch)
    lever._assert_receiver_trimmed_wall(adapter)
    assert {(x, kind) for x, kind, _ in calls} == {
        (point[0], kind) for point in lever.LEVER_HOLE_POINTS for kind in ("cylinder", "cone")}
    assert len(calls) == 12
    assert sum("wall=" in line for line in logs) == 8


@pytest.mark.parametrize("fault", ["axis", "radius", "shoulder", "tip", "missing", "extra"])
def test_native_hole_shape_mismatch_fails(monkeypatch, fault):
    adapter, holes, _outside, _calls, _logs = _receiver(monkeypatch)
    face = holes[0]
    surface = face.GetSurface()
    if fault in ("axis", "radius"):
        params = list(surface.CylinderParams)
        params[3 if fault == "axis" else 6] += 0.001
        surface.CylinderParams = params
    elif fault == "shoulder":
        face.GetEdges = lambda: [_ring(face.x, -70, lever.TAP_DRILL_DIA / 2)]
    elif fault == "tip":
        cone = holes[1]
        cone.GetEdges = lambda: [_ring(cone.x, lever.LEVER_HOLE_POINTS[0][2] + lever.DRILL_DEPTH,
                                              lever.TAP_DRILL_DIA / 2)]
    elif fault == "missing":
        holes.pop()
    else:
        holes.append(holes[0])
    with pytest.raises(RuntimeError):
        lever._assert_receiver_trimmed_wall(adapter)


@pytest.mark.parametrize("fault", ["infinite", "failed", "nan", "wrong_corner", "missing_cap"])
def test_native_wall_failure_is_not_a_scalar_guard_fallback(monkeypatch, fault):
    adapter, _holes, outside, _calls, _logs = _receiver(monkeypatch)
    original = adapter.currentModel.ClosestDistance
    if fault == "missing_cap":
        outside[:] = [face for face in outside if face.label != "cap"]
    else:
        def closest(hole, face):
            distance, a, b = original(hole, face)
            if face.label != "underside":
                return distance, a, b
            if fault == "failed":
                return -1, a, b
            if fault == "nan":
                return math.nan, a, b
            if fault == "infinite":
                b = (a[0], -lever.PLATE_T / 2000, a[2])
                return math.dist(a, b), a, b
            # Correct scalar length, wrong finite corner: reject the witness.
            return distance, (a[0] + .001, a[1], a[2]), (b[0] + .001, b[1], b[2])
        adapter.currentModel.ClosestDistance = closest
    with pytest.raises(RuntimeError):
        lever._assert_receiver_trimmed_wall(adapter)


def _profile(monkeypatch):
    monkeypatch.setattr(lever, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(lever._telemetry, "success", lambda _message: None)
    def point(x, y, z=0):
        return NS(X=x / 1000, Y=y / 1000, Z=z / 1000)
    lines = []
    for vx in (lever.RIB_PLATE_REACH, lever.TIP_X):
        tx = lever.ARC_R**2 / vx
        ty = lever.ARC_R * math.sqrt(1 - lever.ARC_R**2 / vx**2)
        for sign in (-1, 1):
            start, end = point(vx, 0), point(tx, sign * ty)
            lines.append(NS(GetType=lambda: 0, GetStartPoint2=lambda p=start: p,
                            GetEndPoint2=lambda p=end: p))
    segments = lines + [NS(GetType=lambda: 1), NS(GetType=lambda: 1)]
    dimension = NS(SystemValue=lever.RIB_PLATE_REACH / 1000,
                   ReferencePoints=[NS(ArrayData=_m((lever.RIB_PLATE_REACH, 0, 0))),
                                    NS(ArrayData=(0, 0, 0)), NS(ArrayData=(0, 0, 0))])
    feature = NS(GetSpecificFeature2=lambda: NS(GetSketchSegments=lambda: segments),
                 Parameter=lambda name: dimension if name == "MidRibLeftX" else None)
    adapter = NS(currentModel=NS(FeatureByName=lambda _name: feature))
    return adapter, segments, dimension


def test_native_distance_exception_propagates(monkeypatch):
    adapter, _holes, _outside, _calls, _logs = _receiver(monkeypatch)
    def failed(*_args):
        raise RuntimeError("native distance dispatch failure")
    adapter.currentModel.ClosestDistance = failed
    with pytest.raises(RuntimeError, match="native distance dispatch failure"):
        lever._assert_receiver_trimmed_wall(adapter)


def test_original_native_tangents_and_associative_vertex(monkeypatch):
    adapter, _segments, _dimension = _profile(monkeypatch)
    lever._assert_middle_rib_profile(adapter)


@pytest.mark.parametrize("fault", ["stack", "endpoint", "value", "reference"])
def test_fictitious_middle_profile_or_dimension_fails(monkeypatch, fault):
    adapter, segments, dimension = _profile(monkeypatch)
    if fault == "stack":
        segments.pop()
    elif fault == "endpoint":
        segments[0].GetStartPoint2().X += .001
    elif fault == "value":
        dimension.SystemValue += .001
    else:
        dimension.ReferencePoints[0].ArrayData = (.03036, 0, 0)
    with pytest.raises(RuntimeError):
        lever._assert_middle_rib_profile(adapter)
