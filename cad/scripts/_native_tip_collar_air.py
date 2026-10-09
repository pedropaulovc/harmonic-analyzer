"""Finite saved-body BACK-arc clamp and manufactured shadow-aware P1 air.

Only checked temporary copies are transformed/clipped; saved geometry and
operational mates are never actuated. Source envelopes include every collar
clock and manufactured limit. Native tooth/flat/bore relief is NOT a reserve.
"""
from __future__ import annotations

import math
from typing import Any

import _telemetry
import cone_line
import dt_tip_collar_air as air
from _common import _early_bound, double_array

GEAR_COMPONENT = "dt-cylinder-gear-20"
NATIVE_RESOLUTION_MM = air.collar.NATIVE_CONTACT_RESOLUTION_MM


def _solid(raw: Any, label: str) -> Any:
    body = _early_bound(raw, "IBody2")
    if body is None or int(body.GetType()) != 0:
        raise RuntimeError(f"{label}: native geometry is not a solid")
    faults = body.Check3
    if faults is not None and int(_early_bound(faults, "IFaultEntity").Count) != 0:
        raise RuntimeError(f"{label}: native solid has faults")
    return body


def _extreme(body, direction, label):
    result = body.GetExtremePoint(*direction)
    if not isinstance(result, tuple) or len(result) != 4 or result[0] is not True:
        raise RuntimeError(f"{label}: native extreme point unavailable: {result!r}")
    point = tuple(float(value) * 1000.0 for value in result[1:])
    if not all(math.isfinite(value) for value in point):
        raise RuntimeError(f"{label}: native extreme point is non-finite")
    return point


def _array(transform, label):
    if transform is None:
        raise RuntimeError(f"{label}: native transform is missing")
    values = tuple(float(value) for value in transform.ArrayData)
    if len(values) != 16 or not all(math.isfinite(value) for value in values) or abs(values[12]-1.0) > 1e-9:
        raise RuntimeError(f"{label}: invalid/scaled native transform")
    axes = tuple(values[i:i+3] for i in (0, 3, 6))
    if any(abs(sum(x*y for x, y in zip(a, b, strict=True))-(1.0 if i == j else 0.0)) > 1e-8
           for i, a in enumerate(axes) for j, b in enumerate(axes)):
        raise RuntimeError(f"{label}: native rotation is not orthonormal")
    determinant = (axes[0][0]*(axes[1][1]*axes[2][2]-axes[1][2]*axes[2][1])
                   - axes[0][1]*(axes[1][0]*axes[2][2]-axes[1][2]*axes[2][0])
                   + axes[0][2]*(axes[1][0]*axes[2][1]-axes[1][1]*axes[2][0]))
    if abs(determinant-1.0) > 1e-8:
        raise RuntimeError(f"{label}: native rotation is reflected")
    return values


def _component(assembly, name, count):
    raw = assembly.GetComponentByName(name)
    if raw is None:
        raise RuntimeError(f"collar air: component {name!r} is missing")
    component = _early_bound(raw, "IComponent2")
    result = component.GetBodies3(0)
    if not isinstance(result, tuple) or len(result) != 2 or len(result[0] or ()) != count:
        raise RuntimeError(f"collar air: {name} does not have {count} actual configured solids")
    transform = _early_bound(component.Transform2, "IMathTransform")
    _array(transform, name)
    return component, [_solid(body, name) for body in result[0]], transform


def _copy(body, label, *transforms):
    copied = _solid(body.Copy2(False), label)
    for transform in transforms:
        if copied.ApplyTransform(transform) is not True:
            raise RuntimeError(f"{label}: native temporary-body transform failed")
    return copied


def _clip(modeler, body, south, north, label, *, axial_index=1):
    """Exact native slab intersection. Both operands are disposable copies."""
    if axial_index not in (1, 2) or not all(math.isfinite(v) for v in (south, north)) or north <= south:
        raise RuntimeError(f"{label}: invalid clipping slab")
    transverse_axes = [i for i in range(3) if i != axial_index]
    transverse = max(abs(_extreme(body, tuple(sign if k == index else 0.0 for k in range(3)), label)[index])
                     for index in transverse_axes for sign in (-1.0, 1.0)) + 1.0
    centre = [0.0, 0.0, 0.0]
    centre[axial_index] = south/1000.0
    axis = [0.0, 0.0, 0.0]
    axis[axial_index] = 1.0
    tool = _solid(modeler.CreateBodyFromBox3(double_array([
        *centre, *axis, 2.0*transverse/1000.0, 2.0*transverse/1000.0, (north-south)/1000.0,
    ])), label)
    target = _copy(body, label)
    try:
        result = target.Operations2(15901, tool, 0)  # SWBODYINTERSECT
    finally:
        target = tool = None  # Native operation consumes BOTH operands.
    if not isinstance(result, tuple) or len(result) != 2 or result[1] != 0 or not result[0]:
        raise RuntimeError(f"{label}: native tier intersection failed: {result!r}")
    return [_solid(value, label) for value in result[0]]


def _transform(utility, requested, label):
    transform = _early_bound(utility.CreateTransform(double_array(requested)), "IMathTransform")
    observed = _array(transform, label)
    if max(abs(a-b) for a, b in zip(observed, requested, strict=True)) > 1e-10:
        raise RuntimeError(f"{label}: native transform changed the requested rotation")
    return transform


def _swing_transform(utility, angle_deg):
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    pivot = cone_line.cone_station(cone_line.PIVOT_STATION)
    x, _y, z = (value/1000.0 for value in pivot)
    requested = (c, 0.0, -s, 0.0, 1.0, 0.0, s, 0.0, c,
                 x-x*c-z*s, 0.0, z+x*s-z*c, 1.0, 0.0, 0.0, 0.0)
    return _transform(utility, requested, "collar air native p1 transform")


def _faces(body):
    values = body.GetFaces()
    if not isinstance(values, (tuple, list)) or not values:
        raise RuntimeError("collar clamp: actual finite faces are missing")
    return [_early_bound(face, "IFace2") for face in values]


def _cylinders(body, radius, axis, label):
    found = []
    for face in _faces(body):
        surface = _early_bound(face.GetSurface(), "ISurface")
        if surface is None:
            raise RuntimeError(f"{label}: native surface is missing")
        if surface.IsCylinder() is not True:
            continue
        params = tuple(float(value) for value in surface.CylinderParams)
        if len(params) != 7 or not all(math.isfinite(value) for value in params):
            raise RuntimeError(f"{label}: invalid actual cylinder parameters")
        origin = tuple(value*1000.0 for value in params[:3])
        direction = params[3:6]
        measured_radius = params[6]*1000.0
        if abs(measured_radius-radius) > NATIVE_RESOLUTION_MM:
            continue
        length = math.sqrt(sum(value*value for value in direction))
        if abs(length-1.0) > 1e-8:
            raise RuntimeError(f"{label}: native cylinder axis is not unit")
        cosine = sum(a*b for a, b in zip(direction, axis, strict=True))
        if abs(abs(cosine)-1.0) > 1e-8:
            raise RuntimeError(f"{label}: actual cylinder axis is misoriented")
        if cosine < 0.0:
            direction = tuple(-value for value in direction)
        found.append((face, origin, direction, measured_radius))
    if not found:
        raise RuntimeError(f"{label}: actual retained cylinder is missing")
    return found


def _closest(face, point, label):
    result = face.GetClosestPointOn(*(value/1000.0 for value in point))
    if not isinstance(result, (tuple, list)) or len(result) != 5 or not all(math.isfinite(float(v)) for v in result):
        raise RuntimeError(f"{label}: finite native closest point is unavailable/non-finite")
    return tuple(float(value)*1000.0 for value in result[:3])


def _planes(body, label):
    for face in _faces(body):
        surface = _early_bound(face.GetSurface(), "ISurface")
        if surface is None:
            raise RuntimeError(f"{label}: native surface is missing")
        if surface.IsPlane() is not True:
            continue
        params = tuple(float(value) for value in surface.PlaneParams)
        if len(params) != 6 or not all(math.isfinite(value) for value in params):
            raise RuntimeError(f"{label}: invalid actual plane parameters")
        normal = params[:3]
        if abs(sum(v*v for v in normal)-1.0) > 1e-8:
            raise RuntimeError(f"{label}: native plane normal is not unit")
        point = tuple(v*1000.0 for v in params[3:])
        yield face, normal, sum(a*b for a, b in zip(normal, point, strict=True))


def _installed_clamp(utility, ring, screw, collar_transform, shaft_body, shaft_transform):
    """Native part-local → root → actual shaft → +Y shaft-frame control."""
    inverse = _early_bound(shaft_transform.Inverse(), "IMathTransform")
    _array(inverse, "collar clamp actual shaft inverse")
    swizzle = _transform(utility, (1.0, 0.0, 0.0, 0.0, 0.0, -1.0,
                                  0.0, 1.0, 0.0, 0.0, 0.0, 0.0,
                                  1.0, 0.0, 0.0, 0.0), "collar clamp shaft frame")
    ring = _copy(ring, "finite loaded collar", collar_transform, inverse, swizzle)
    screw = _copy(screw, "finite loaded screw", collar_transform, inverse, swizzle)
    journal = _copy(shaft_body, "finite loaded shaft", swizzle)
    r = air.collar.BORE_DIA/2.0
    bores = _cylinders(ring, air.collar.BORE_MODEL_DIA_MM/2.0, (0.0, 1.0, 0.0), "actual collar bore")
    rounds = _cylinders(journal, r, (0.0, 1.0, 0.0), "actual terminal round BACK arc")
    south = air.shaft.FRONT_STUB + air.SOUTH_STATION_MM
    witnesses = []
    for station in (south+air.collar.EDGE_BREAK+2.0*NATIVE_RESOLUTION_MM,
                    south+air.collar.WIDTH-air.collar.EDGE_BREAK-2.0*NATIVE_RESOLUTION_MM):
        requested = (-r, station, 0.0)
        shaft_point = min((_closest(face, requested, "shaft finite BACK arc") for face, *_ in rounds),
                          key=lambda value: math.dist(value, requested))
        candidate = min(((math.dist(point := _closest(face, shaft_point, "bore finite BACK arc"), shaft_point),
                          point, origin, axis, radius) for face, origin, axis, radius in bores),
                        key=lambda value: value[0])
        witnesses.append(air.collar.BackArcWitness(shaft_point, candidate[1], candidate[2], candidate[3], r, candidate[4]))
    dogs = _cylinders(screw, air.collar.DOG_DIA/2.0, (1.0, 0.0, 0.0), "actual complete ground dog")
    dog_face, dog_origin, dog_axis, dog_radius = dogs[0]
    tips = []
    for face, normal, plane in _planes(screw, "actual ground dog tip"):
        cosine = sum(a*b for a, b in zip(normal, dog_axis, strict=True))
        if abs(abs(cosine)-1.0) > 1e-8:
            continue
        t = (plane-sum(a*b for a, b in zip(normal, dog_origin, strict=True)))/cosine
        centre = tuple(dog_origin[k]+t*dog_axis[k] for k in range(3))
        if math.dist(_closest(face, centre, "finite dog centre"), centre) > NATIVE_RESOLUTION_MM:
            continue  # Socket annulus is not the ground dog face.
        edge = _closest(face, (centre[0], centre[1]+10.0, centre[2]), "finite dog face radius")
        radius = math.dist(edge, centre)
        if dog_radius-air.collar.DOG_EDGE_BREAK-NATIVE_RESOLUTION_MM <= radius <= dog_radius+NATIVE_RESOLUTION_MM:
            tips.append((face, centre))
    if len(tips) != 1:
        raise RuntimeError("collar clamp: actual ground dog tip cannot be identified uniquely")
    _tip_face, dog_centre = tips[0]
    positive = _extreme(screw, dog_axis, "dog toward retained stock")
    negative = _extreme(screw, tuple(-v for v in dog_axis), "dog opposite retained stock")
    forward = sum((positive[k]-dog_centre[k])*dog_axis[k] for k in range(3))
    backward = sum((dog_centre[k]-negative[k])*dog_axis[k] for k in range(3))
    force = dog_axis if forward > backward else tuple(-v for v in dog_axis)
    flats = []
    expected_offset = air.collar.TERMINAL_FLAT_AF_MM-r
    for face, normal, plane in _planes(journal, "actual terminal flat"):
        if abs(abs(normal[0])-1.0) > 1e-8:
            continue
        offset = plane/normal[0]
        if abs(offset-expected_offset) > NATIVE_RESOLUTION_MM:
            continue
        point = _closest(face, dog_centre, "finite terminal flat contact")
        if math.dist(point, dog_centre) <= NATIVE_RESOLUTION_MM:
            flats.append((face, offset))
    if len(flats) != 1:
        raise RuntimeError("collar clamp: dog tip is not on the actual finite terminal flat")
    face, offset = flats[0]
    start = _closest(face, (offset, -1000.0, dog_centre[2]), "terminal flat south end")[1]
    end = _closest(face, (offset, 1000.0, dog_centre[2]), "terminal flat north end")[1]
    record = air.collar.validate_installed_clamp_pose(
        back_arc_witnesses=tuple(witnesses), dog_tip_centre_mm=dog_centre,
        dog_axis_to_socket=force, dog_radius_mm=dog_radius,
        flat_offset_mm=offset, flat_half_chord_mm=math.sqrt(r*r-offset*offset),
        flat_axial_limits_mm=(start, end),
    )
    record["actual_dog_tip_mm"] = dog_centre
    record["actual_dog_axis_to_socket"] = force
    _telemetry.info(f"Finite saved-body signed collar BACK-arc/whole-DOG law: {record}")
    return record


def measure(adapter: Any, *, collar_component: str, shaft_component: str, installed, bank_thrust):
    """Read actual saved solids and refuse missing installed/source authorities."""
    proof = air.full_sweep_proof(installed=installed, bank_thrust=bank_thrust)
    assembly = _early_bound(adapter.currentModel, "IAssemblyDoc")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    collar, collar_bodies, collar_transform = _component(assembly, collar_component, 2)
    _shaft, shaft_bodies, shaft_transform = _component(assembly, shaft_component, 1)
    gear, gear_bodies, gear_transform = _component(assembly, GEAR_COMPONENT, 1)
    pose = _array(collar_transform, "installed collar")
    axis = (math.sin(math.radians(cone_line.INCLINE_DEG)), 0.0, math.cos(math.radians(cone_line.INCLINE_DEG)))
    flat = (math.cos(math.radians(cone_line.INCLINE_DEG)), 0.0, -math.sin(math.radians(cone_line.INCLINE_DEG)))
    station = cone_line.cone_station(air.SOUTH_STATION_MM)
    expected_origin = tuple(station[k]+air.collar.INSTALLED_BORE_AXIS_OFFSET_MM*flat[k] for k in range(3))
    if (max(abs(pose[9+k]*1000.0-expected_origin[k]) for k in range(3)) > NATIVE_RESOLUTION_MM
            or max(abs(pose[3+k]-axis[k]) for k in range(3)) > 1e-8):
        raise RuntimeError("collar air: saved collar is not the nonconcentric loaded source pose")
    result = model.ClosestDistance(collar, gear)
    if not isinstance(result, tuple) or len(result) != 3:
        raise RuntimeError(f"collar air: malformed native ClosestDistance: {result!r}")
    distance = float(result[0])*1000.0
    points = tuple(tuple(float(value)*1000.0 for value in point) for point in result[1:])
    if not math.isfinite(distance) or distance <= 0.0 or any(len(point) != 3 or not all(math.isfinite(v) for v in point) for point in points):
        raise RuntimeError(f"collar air: actual component pair has no positive native air: {result!r}")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    modeler = _early_bound(adapter.swApp.GetModeler(), "IModeler")
    if utility is None or modeler is None:
        raise RuntimeError("collar air: native math utility/modeler unavailable")
    rings, screws = [], []
    for body in collar_bodies:
        y_min = _extreme(body, (0.0, -1.0, 0.0), "collar part-local positive control")[1]
        (rings if abs(y_min) <= NATIVE_RESOLUTION_MM else screws).append(body)
    if len(rings) != 1 or len(screws) != 1:
        raise RuntimeError("collar air: part-local actual ring/screw cannot be identified")
    loaded = _installed_clamp(utility, rings[0], screws[0], collar_transform, shaft_bodies[0], shaft_transform)
    ring_north = _extreme(rings[0], (0.0, 1.0, 0.0), "whole ring partition control")[1]
    if abs(ring_north-air.collar.WIDTH) > NATIVE_RESOLUTION_MM:
        raise RuntimeError("collar air: native ring material escapes the complete local-Y partition")
    parts = {
        "nose": _clip(modeler, rings[0], -1.0, air.PARTITION_STATION_MM, "collar nose"),
        "body": _clip(modeler, rings[0], air.PARTITION_STATION_MM, air.collar.WIDTH+1.0, "collar body"),
        "screw": screws,
    }
    fixed_parts = {tier.name: [] for tier in air.DRUM_TIERS}
    # The source nonnegative-Z support dominance is checked against ALL actual
    # configured bank solids, not inferred from just the nearest component.
    for number in range(1, air.bank.COUNT+1):
        _component_obj, bodies, transform = _component(assembly, f"dt-cylinder-gear-{number}", 1)
        body = bodies[0]
        z_south = _extreme(body, (0.0, 0.0, -1.0), f"bank {number} whole material")[2]
        z_north = _extreme(body, (0.0, 0.0, 1.0), f"bank {number} whole material")[2]
        if abs(z_south) > NATIVE_RESOLUTION_MM or abs(z_north-air.drum.OVERALL_THICKNESS) > NATIVE_RESOLUTION_MM:
            raise RuntimeError(f"bank {number}: actual material escapes the complete tooth/cam shadow partition")
        bore_radius = air.drum.BORE_DIA/2.0
        bore_faces = _cylinders(body, bore_radius, (0.0, 0.0, 1.0), f"bank {number} actual running bore")
        for station_z in (air.DRUM_BORE_END_BREAK_MAX_MM,
                          air.drum.OVERALL_THICKNESS-air.DRUM_BORE_END_BREAK_MAX_MM):
            requested = (bore_radius, 0.0, station_z)
            residual = min(math.dist(_closest(face, requested, f"bank {number} finite bore span"), requested)
                           for face, *_ in bore_faces)
            if residual > NATIVE_RESOLUTION_MM:
                raise RuntimeError(f"bank {number}: actual finite running-bore contact span is too short")
        for name, south, north in (("tooth_face", -1.0, air.drum.FACE_WIDTH),
                                  ("cam", air.drum.FACE_WIDTH, air.drum.OVERALL_THICKNESS+1.0)):
            for clipped in _clip(modeler, body, south, north, f"bank {number} {name}", axial_index=2):
                fixed_parts[name].append(_copy(clipped, f"placed bank {number} {name}", transform))
    minimum, governing, gear_support = math.inf, None, {}
    swing_angle, swept_key, swing, swept_bodies = None, None, None, None
    with _telemetry.span("verify.tip_collar_j19_air") as sp:
        for row in proof:
            normal = row["normal"]
            if swing_angle != row["angle_deg"]:
                swing_angle = row["angle_deg"]
                swing = _swing_transform(utility, swing_angle)
            moving_key = (swing_angle, row["tier"])
            if swept_key != moving_key:
                swept_key = moving_key
                swept_bodies = [_copy(body, "swept collar tier", collar_transform, swing)
                                for body in parts[row["tier"]]]
            measured_collar = min(sum(a*b for a, b in zip(_extreme(
                body, tuple(-v for v in normal), "swept collar tier",
            ), normal, strict=True)) for body in swept_bodies)
            key = (row["drum_tier"], normal)
            if key not in gear_support:
                gear_support[key] = max(sum(a*b for a, b in zip(_extreme(body, normal, "bank native material support"), normal, strict=True))
                                        for body in fixed_parts[row["drum_tier"]])
            measured = measured_collar-gear_support[key]
            a = math.radians(row["angle_deg"])
            swept_flat = (math.cos(a)*flat[0]+math.sin(a)*flat[2], flat[1], -math.sin(a)*flat[0]+math.cos(a)*flat[2])
            loaded_shift = air.collar.INSTALLED_BORE_AXIS_OFFSET_MM*sum(x*y for x, y in zip(swept_flat, normal, strict=True))
            nominal = row["nominal_mm"]
            if measured-loaded_shift < nominal-NATIVE_RESOLUTION_MM:
                raise RuntimeError(f"collar/bank native shadow tier undercuts source enclosure: {row}, measured={measured}")
            relief = max(0.0, measured-loaded_shift-nominal)
            worst = measured-loaded_shift-relief-sum(row["closure_mm"].values())
            if not math.isfinite(worst) or worst <= 0.0:
                raise RuntimeError(f"collar/bank native booked air closes: {worst}")
            if worst < minimum:
                minimum, governing = worst, {**row, "measured_mm":measured, "loaded_nominal_shift_mm":loaded_shift,
                                            "native_relief_discount_mm":relief, "worst_mm":worst}
        record = {"closest_distance_mm":distance, "closest_points_mm":points,
                  "loaded_clamp":loaded, "minimum_booked_air_mm":minimum,
                  "governing":governing, "interval_material_pair_certificates":len(proof)}
        sp.set_attribute("tip_collar_j19.closest_mm", distance)
        sp.set_attribute("tip_collar_j19.booked_min_mm", minimum)
        sp.set_attribute("tip_collar_j19.interval_count", len(proof))
        _telemetry.info(f"Measured saved collar/bank shadow-aware full-source P1 air: {record}")
    return record
