"""Finite saved-body shadow-aware P1 air for the cone tip (dt_cone_tip_air).

Owner decision C1 keyed (2026-11-09, PR #1992): the bushing on T006's pivot,
the end screw's proud end and MHA-DT-21's south face, each against G19's
tooth and cam tiers over the P1 sweep.  Only checked temporary copies are
transformed/clipped; saved geometry and operational mates are never
actuated.  Native tooth/flat/bore relief is NOT a reserve.  The generic COM
readers here (solids, extreme points, transforms, clipping) are shared with
_native_bank_retention.
"""

from __future__ import annotations

import math
from typing import Any

import _telemetry
import cone_line
import dt_cone_tip_air as air
from _com import _early_bound
from solidworks_mcp.adapters.com_variant import double_array

GEAR_COMPONENT = "dt-cylinder-gear-20"
NATIVE_RESOLUTION_MM = 1e-5  # metrology roundoff, not a printed fit grade.
SWBODYINTERSECT = 15901


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
    if (
        len(values) != 16
        or not all(math.isfinite(value) for value in values)
        or abs(values[12] - 1.0) > 1e-9
    ):
        raise RuntimeError(f"{label}: invalid/scaled native transform")
    axes = tuple(values[i : i + 3] for i in (0, 3, 6))
    if any(
        abs(sum(x * y for x, y in zip(a, b, strict=True)) - (1.0 if i == j else 0.0))
        > 1e-8
        for i, a in enumerate(axes)
        for j, b in enumerate(axes)
    ):
        raise RuntimeError(f"{label}: native rotation is not orthonormal")
    determinant = (
        axes[0][0] * (axes[1][1] * axes[2][2] - axes[1][2] * axes[2][1])
        - axes[0][1] * (axes[1][0] * axes[2][2] - axes[1][2] * axes[2][0])
        + axes[0][2] * (axes[1][0] * axes[2][1] - axes[1][1] * axes[2][0])
    )
    if abs(determinant - 1.0) > 1e-8:
        raise RuntimeError(f"{label}: native rotation is reflected")
    return values


def _component(assembly, name, count):
    raw = assembly.GetComponentByName(name)
    if raw is None:
        raise RuntimeError(f"tip air: component {name!r} is missing")
    component = _early_bound(raw, "IComponent2")
    result = component.GetBodies3(0)
    if (
        not isinstance(result, tuple)
        or len(result) != 2
        or len(result[0] or ()) != count
    ):
        raise RuntimeError(
            f"tip air: {name} does not have {count} actual configured solids"
        )
    transform = _early_bound(component.Transform2, "IMathTransform")
    _array(transform, name)
    return component, [_solid(body, name) for body in result[0]], transform


def _copy(body, label, *transforms):
    copied = _solid(body.Copy2(False), label)
    for transform in transforms:
        if copied.ApplyTransform(transform) is not True:
            raise RuntimeError(f"{label}: native temporary-body transform failed")
    return copied


def _intersect(body, tool, label, *, allow_empty=False):
    """Native intersection of two disposable operands (both consumed)."""
    target = _copy(body, label)
    try:
        result = target.Operations2(SWBODYINTERSECT, tool, 0)
    finally:
        target = tool = None  # Native operation consumes BOTH operands.
    if allow_empty and (not isinstance(result, tuple) or not result[0]):
        return []
    if (
        not isinstance(result, tuple)
        or len(result) != 2
        or result[1] != 0
        or not result[0]
    ):
        raise RuntimeError(f"{label}: native intersection failed: {result!r}")
    return [_solid(value, label) for value in result[0]]


def _clip(modeler, body, south, north, label, *, axial_index=1):
    """Exact native slab intersection. Both operands are disposable copies."""
    if (
        axial_index not in (1, 2)
        or not all(math.isfinite(v) for v in (south, north))
        or north <= south
    ):
        raise RuntimeError(f"{label}: invalid clipping slab")
    transverse_axes = [i for i in range(3) if i != axial_index]
    transverse = (
        max(
            abs(
                _extreme(
                    body, tuple(sign if k == index else 0.0 for k in range(3)), label
                )[index]
            )
            for index in transverse_axes
            for sign in (-1.0, 1.0)
        )
        + 1.0
    )
    centre = [0.0, 0.0, 0.0]
    centre[axial_index] = south / 1000.0
    axis = [0.0, 0.0, 0.0]
    axis[axial_index] = 1.0
    tool = _solid(
        modeler.CreateBodyFromBox3(
            double_array(
                [
                    *centre,
                    *axis,
                    2.0 * transverse / 1000.0,
                    2.0 * transverse / 1000.0,
                    (north - south) / 1000.0,
                ]
            )
        ),
        label,
    )
    return _intersect(body, tool, label)


def _drum_shadow(modeler, body, radius, label):
    """The part of a placed body standing over a drum circle (a vertical
    cylinder about the drum axis), or [] where none does."""
    z_low = _extreme(body, (0.0, 0.0, -1.0), label)[2] - 1.0
    z_high = _extreme(body, (0.0, 0.0, 1.0), label)[2] + 1.0
    tool = _solid(
        modeler.CreateBodyFromCyl(
            double_array(
                [
                    cone_line.X_DRUM / 1000.0,
                    cone_line.Y_DRIVE / 1000.0,
                    z_low / 1000.0,
                    0.0,
                    0.0,
                    1.0,
                    radius / 1000.0,
                    (z_high - z_low) / 1000.0,
                ]
            )
        ),
        label,
    )
    return _intersect(body, tool, label, allow_empty=True)


def _transform(utility, requested, label):
    transform = _early_bound(
        utility.CreateTransform(double_array(requested)), "IMathTransform"
    )
    observed = _array(transform, label)
    if max(abs(a - b) for a, b in zip(observed, requested, strict=True)) > 1e-10:
        raise RuntimeError(f"{label}: native transform changed the requested rotation")
    return transform


def _swing_transform(utility, angle_deg):
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    pivot = cone_line.cone_station(cone_line.PIVOT_STATION)
    x, _y, z = (value / 1000.0 for value in pivot)
    requested = (
        c,
        0.0,
        -s,
        0.0,
        1.0,
        0.0,
        s,
        0.0,
        c,
        x - x * c - z * s,
        0.0,
        z + x * s - z * c,
        1.0,
        0.0,
        0.0,
        0.0,
    )
    return _transform(utility, requested, "tip air native p1 transform")


def _faces(body):
    values = body.GetFaces()
    if not isinstance(values, (tuple, list)) or not values:
        raise RuntimeError("tip air: actual finite faces are missing")
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
        origin = tuple(value * 1000.0 for value in params[:3])
        direction = params[3:6]
        measured_radius = params[6] * 1000.0
        if abs(measured_radius - radius) > NATIVE_RESOLUTION_MM:
            continue
        length = math.sqrt(sum(value * value for value in direction))
        if abs(length - 1.0) > 1e-8:
            raise RuntimeError(f"{label}: native cylinder axis is not unit")
        cosine = sum(a * b for a, b in zip(direction, axis, strict=True))
        if abs(abs(cosine) - 1.0) > 1e-8:
            raise RuntimeError(f"{label}: actual cylinder axis is misoriented")
        if cosine < 0.0:
            direction = tuple(-value for value in direction)
        found.append((face, origin, direction, measured_radius))
    if not found:
        raise RuntimeError(f"{label}: actual retained cylinder is missing")
    return found


def _closest(face, point, label):
    result = face.GetClosestPointOn(*(value / 1000.0 for value in point))
    if (
        not isinstance(result, (tuple, list))
        or len(result) != 5
        or not all(math.isfinite(float(v)) for v in result)
    ):
        raise RuntimeError(
            f"{label}: finite native closest point is unavailable/non-finite"
        )
    return tuple(float(value) * 1000.0 for value in result[:3])


def _closest_distance(model, component, gear, name):
    result = model.ClosestDistance(component, gear)
    if not isinstance(result, tuple) or len(result) != 3:
        raise RuntimeError(
            f"tip air: malformed native ClosestDistance for {name}: {result!r}"
        )
    distance = float(result[0]) * 1000.0
    points = tuple(
        tuple(float(value) * 1000.0 for value in point) for point in result[1:]
    )
    if (
        not math.isfinite(distance)
        or distance <= 0.0
        or any(
            len(point) != 3 or not all(math.isfinite(v) for v in point)
            for point in points
        )
    ):
        raise RuntimeError(
            f"tip air: {name}/G19 has no positive native air: {result!r}"
        )
    return distance, points


def _bank_tiers(assembly, modeler):
    """Every placed bank gear's tooth and cam tiers, as placed copies."""
    fixed_parts = {tier.name: [] for tier in air.DRUM_TIERS}
    # The source nonnegative-Z support dominance is checked against ALL actual
    # configured bank solids, not inferred from just the nearest component.
    for number in range(1, air.bank.COUNT + 1):
        _component_obj, bodies, transform = _component(
            assembly, f"dt-cylinder-gear-{number}", 1
        )
        body = bodies[0]
        z_south = _extreme(body, (0.0, 0.0, -1.0), f"bank {number} whole material")[2]
        z_north = _extreme(body, (0.0, 0.0, 1.0), f"bank {number} whole material")[2]
        if (
            abs(z_south) > NATIVE_RESOLUTION_MM
            or abs(z_north - air.drum.OVERALL_THICKNESS) > NATIVE_RESOLUTION_MM
        ):
            raise RuntimeError(
                f"bank {number}: actual material escapes the complete tooth/cam shadow partition"
            )
        bore_radius = air.drum.BORE_DIA / 2.0
        bore_faces = _cylinders(
            body, bore_radius, (0.0, 0.0, 1.0), f"bank {number} actual running bore"
        )
        for station_z in (
            air.DRUM_BORE_END_BREAK_MAX_MM,
            air.drum.OVERALL_THICKNESS - air.DRUM_BORE_END_BREAK_MAX_MM,
        ):
            requested = (bore_radius, 0.0, station_z)
            residual = min(
                math.dist(
                    _closest(face, requested, f"bank {number} finite bore span"),
                    requested,
                )
                for face, *_ in bore_faces
            )
            if residual > NATIVE_RESOLUTION_MM:
                raise RuntimeError(
                    f"bank {number}: actual finite running-bore contact span is too short"
                )
        for name, south, north in (
            ("tooth_face", -1.0, air.drum.FACE_WIDTH),
            ("cam", air.drum.FACE_WIDTH, air.drum.OVERALL_THICKNESS + 1.0),
        ):
            for clipped in _clip(
                modeler, body, south, north, f"bank {number} {name}", axial_index=2
            ):
                fixed_parts[name].append(
                    _copy(clipped, f"placed bank {number} {name}", transform)
                )
    return fixed_parts


def measure(
    adapter: Any,
    *,
    bushing_component: str,
    end_screw_component: str,
    block_component: str,
):
    """Read the saved solids against the printed-tolerance tip air stack."""
    proof = air.full_sweep_proof()
    assembly = _early_bound(adapter.currentModel, "IAssemblyDoc")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    gear, _gear_bodies, _gear_transform = _component(assembly, GEAR_COMPONENT, 1)
    sources = {}
    closest = {}
    for tier, name in (
        ("bushing", bushing_component),
        ("screw end", end_screw_component),
        (air.BLOCK_TIER, block_component),
    ):
        component, bodies, transform = _component(assembly, name, 1)
        sources[tier] = (bodies, transform)
        closest[tier] = _closest_distance(model, component, gear, name)
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    modeler = _early_bound(adapter.swApp.GetModeler(), "IModeler")
    if utility is None or modeler is None:
        raise RuntimeError("tip air: native math utility/modeler unavailable")
    fixed_parts = _bank_tiers(assembly, modeler)
    tier_radius = {tier.name: tier.radius_mm for tier in air.DRUM_TIERS}
    minimum, governing, gear_support = math.inf, None, {}
    swing_angle, swept_key, swing, swept_bodies = None, None, None, None
    with _telemetry.span("verify.cone_tip_g19_air") as sp:
        for row in proof:
            if not row["nominal_shadow"]:
                # Only the tolerance-shifted block stands over this tier; the
                # saved nominal block stands over none, so the source proof
                # alone carries the row.
                continue
            normal = row["normal"]
            if swing_angle != row["angle_deg"]:
                swing_angle = row["angle_deg"]
                swing = _swing_transform(utility, swing_angle)
            moving_key = (swing_angle, row["tier"])
            if swept_key != moving_key:
                swept_key = moving_key
                bodies, transform = sources[row["tier"]]
                swept_bodies = [
                    _copy(body, f"swept tip {row['tier']}", transform, swing)
                    for body in bodies
                ]
            measured_bodies = swept_bodies
            if row["tier"] == air.BLOCK_TIER:
                measured_bodies = [
                    clipped
                    for body in swept_bodies
                    for clipped in _drum_shadow(
                        modeler,
                        body,
                        tier_radius[row["drum_tier"]],
                        f"tip block over G19 {row['drum_tier']}",
                    )
                ]
                if not measured_bodies:
                    raise RuntimeError(
                        f"tip air: the saved block stands over no drum where the source does: {row}"
                    )
            measured_tip = min(
                sum(
                    a * b
                    for a, b in zip(
                        _extreme(
                            body,
                            tuple(-v for v in normal),
                            "swept tip tier",
                        ),
                        normal,
                        strict=True,
                    )
                )
                for body in measured_bodies
            )
            key = (row["drum_tier"], normal)
            if key not in gear_support:
                gear_support[key] = max(
                    sum(
                        a * b
                        for a, b in zip(
                            _extreme(body, normal, "bank native material support"),
                            normal,
                            strict=True,
                        )
                    )
                    for body in fixed_parts[row["drum_tier"]]
                )
            measured = measured_tip - gear_support[key]
            nominal = row["nominal_mm"]
            if measured < nominal - NATIVE_RESOLUTION_MM:
                raise RuntimeError(
                    f"tip/bank native shadow tier undercuts source enclosure: {row}, measured={measured}"
                )
            relief = max(0.0, measured - nominal)
            worst = measured - relief - sum(row["closure_mm"].values())
            if not math.isfinite(worst) or worst <= 0.0:
                raise RuntimeError(f"tip/bank native booked air closes: {worst}")
            if worst < minimum:
                minimum, governing = (
                    worst,
                    {
                        **row,
                        "measured_mm": measured,
                        "native_relief_discount_mm": relief,
                        "worst_mm": worst,
                    },
                )
        record = {
            "closest_distance_mm": {tier: value[0] for tier, value in closest.items()},
            "closest_points_mm": {tier: value[1] for tier, value in closest.items()},
            "minimum_booked_air_mm": minimum,
            "governing": governing,
            "interval_material_pair_certificates": len(proof),
        }
        for tier, (distance, _points) in closest.items():
            sp.set_attribute(
                f"cone_tip_g19.{tier.replace(' ', '_')}_closest_mm", distance
            )
        sp.set_attribute("cone_tip_g19.booked_min_mm", minimum)
        sp.set_attribute("cone_tip_g19.interval_count", len(proof))
        _telemetry.info(
            f"Measured saved cone tip/bank shadow-aware full-source P1 air: {record}"
        )
    return record
