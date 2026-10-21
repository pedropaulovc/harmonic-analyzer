"""Static installed air around the summing receiver's 8.20 -> 9.40 addition.

The tested temporary material is a CONSERVATIVE SUPERSET, not the entire
lever slab and not a swept/tolerance certificate. Intersect the configured
lever with local Z [-68, -66.8], then subtract the invariant coefficient
plate, pivot cylinder and spring pad. The actual rib slants, R0.4 end fill,
and blind drill relief therefore survive unchanged. Unchanged -X summation
web in this interval is deliberately retained: removing its curved footprint
would needlessly reconstruct a second recipe. Positive air for this superset
proves positive air for the addition; NO intended-contact exemption applies.

The filled plate/pad tools cannot erase new rib material in a spring hole:
the complete hole column is beyond the preserved rib reach. The knife prism
is inside the invariant cylinder; the middle/opposite ribs and anchor boss
are outside this Z strip. Only copies are transformed/consumed. No document,
configuration, feature suppression, component pose or motion state is edited.
"""

from __future__ import annotations

import math
from pathlib import PureWindowsPath
from typing import Any

import _config
import _telemetry
import sm_summing_lever_spec as lever
from _com import _early_bound, _read_member
from _hole_spec import blind_cut_dia_mm
from _native_spring_contact import _component_solids, _transformed_body_copy
from solidworks_mcp.adapters.com_variant import double_array

OLD_DEPTH_MM = 8.20
NEW_DEPTH_MM = 9.40
OUTER_Z_MM = -lever.PLATE_L / 2.0
OLD_INNER_Z_MM = OUTER_Z_MM + OLD_DEPTH_MM
NEW_INNER_Z_MM = OUTER_Z_MM + NEW_DEPTH_MM
NATIVE_RESOLUTION_MM = 1e-5  # Readback resolution, NOT a fit/overlap allowance.
MATERIAL_SCOPE = "actual_strip_minus_invariant_plate_cylinder_pad_superset"
CLAIM = "current_collapsed_configuration_static_only_not_swept_or_tolerance_proof"

# Every occurrence, not just station 0 or the closest whole-component pair.
# Horizontal magnifying 'lever' is a rod. Its vertical rod and wire are distinct.
CHANNEL_FAMILIES = (
    "ch-vn-channel-spring-installed",
    "ch-vn-spring-hook",
    "ch-anchor-jam-nut",
    "ch-channel-lever",
    "ch-connecting-rod",
)
FIXED_COUNTS = {
    "sm-summing-lever": 1,
    "sm-vn-counter-spring": 1,
    "sm-vn-boss-hook": 1,
    "sm-vn-boss-hook-jam-nut": 1,
    "sm-knife-mount": 2,
    "mg-magnifying-bracket": 1,
    "mg-vn-magnifying-bracket-screw": 2,
    "mg-magnifying-lever": 1,
    "mg-magnifying-vertical-rod": 1,
    "mg-vn-lever-wire": 1,
    "mg-magnifying-clamp": 1,
    "mg-vn-thumb-screw": 2,
    "mg-output-fixture": 1,
}


def _solid(raw: Any, label: str) -> Any:
    body = _early_bound(raw, "IBody2")
    if body is None or body.GetType() != 0:
        raise RuntimeError(f"{label}: native solid unavailable")
    faults = body.Check3
    if faults is not None and int(_early_bound(faults, "IFaultEntity").Count) != 0:
        raise RuntimeError(f"{label}: native solid has faults")
    return body


def _copy(body: Any, label: str) -> Any:
    return _solid(body.Copy(), label)


def _volume(body: Any, label: str) -> float:
    values = body.GetMassProperties(1.0)
    if not isinstance(values, (tuple, list)) or len(values) != 12:
        raise RuntimeError(f"{label}: native mass properties unavailable")
    volume = float(values[3]) * 1e9
    if not math.isfinite(volume) or volume <= 0.0:
        raise RuntimeError(f"{label}: native solid volume is not positive: {volume!r}")
    return volume


def _operation(target: Any, tool: Any, operation: int, label: str) -> list[Any]:
    """Consume only temporary operands; failed native Booleans NEVER mean clear."""
    try:
        result = target.Operations2(operation, tool, 0)
    finally:
        target = tool = None  # Operations2 invalidates BOTH inputs, even on failure.
    if not isinstance(result, tuple) or len(result) != 2:
        raise RuntimeError(f"{label}: malformed native Boolean result")
    bodies, status = result
    if operation == 15901 and status in (5, 1067) and not bodies:
        return []  # Documented DisjointBodies / NoIntersect, not BooleanFail.
    if status != 0:
        raise RuntimeError(f"{label}: native Boolean failed (status={status})")
    return [_solid(raw, label) for raw in bodies or ()]


def _extreme(body: Any, axis: int, sign: int, label: str) -> float:
    direction = tuple(float(sign) if k == axis else 0.0 for k in range(3))
    result = body.GetExtremePoint(*direction)
    if not isinstance(result, tuple) or len(result) != 4 or result[0] is not True:
        raise RuntimeError(f"{label}: native extreme point unavailable")
    point = tuple(float(value) * 1000.0 for value in result[1:])
    if not all(math.isfinite(value) for value in point):
        raise RuntimeError(f"{label}: non-finite native extreme point")
    return point[axis]


def _box(modeler: Any, low: tuple, high: tuple, label: str) -> Any:
    if any(not math.isfinite(v) for v in (*low, *high)) or any(
        b <= a for a, b in zip(low, high, strict=True)
    ):
        raise RuntimeError(f"{label}: invalid native clipping box")
    values = (
        (low[0] + high[0]) / 2000.0,
        (low[1] + high[1]) / 2000.0,
        low[2] / 1000.0,
        0.0, 0.0, 1.0,
        (high[0] - low[0]) / 1000.0,
        (high[1] - low[1]) / 1000.0,
        (high[2] - low[2]) / 1000.0,
    )
    return _solid(modeler.CreateBodyFromBox3(double_array(values)), label)


def _dimension(component: Any, feature_name: str, name: str, expected: float) -> Any:
    feature = _early_bound(component.FeatureByName(feature_name), "IFeature")
    if feature is None:
        raise RuntimeError(f"receiver strip: missing {feature_name}")
    dimension = _early_bound(feature.Parameter(name), "IDimension")
    value = float(dimension.SystemValue) * 1000.0 if dimension is not None else math.nan
    if not math.isfinite(value) or abs(value - expected) > NATIVE_RESOLUTION_MM:
        raise RuntimeError(f"receiver strip: {feature_name}.{name} is {value}, expected {expected}")
    return feature


def _assert_receiver(component: Any) -> None:
    # Read the occurrence's feature, never GetModelDoc2's possibly different config.
    feature = _dimension(component, "EdgeRibBack", "RibDepth", NEW_DEPTH_MM)
    caps = []
    for raw in feature.GetFaces() or ():
        face = _early_bound(raw, "IFace2")
        surface = _early_bound(face.GetSurface(), "ISurface")
        if surface is None:
            raise RuntimeError("receiver strip: native receiver surface unavailable")
        if not surface.IsPlane():
            continue
        values = tuple(float(value) for value in surface.PlaneParams)
        if len(values) != 6 or not all(math.isfinite(value) for value in values):
            raise RuntimeError("receiver strip: invalid native receiver plane")
        if abs(values[0]) < 1e-7 and abs(values[1]) < 1e-7 and abs(abs(values[2]) - 1.0) < 1e-7:
            caps.append(values[5] * 1000.0)
    if not any(abs(z - NEW_INNER_Z_MM) <= NATIVE_RESOLUTION_MM for z in caps) or any(
        min(abs(z - NEW_INNER_Z_MM), abs(z - OUTER_Z_MM)) > NATIVE_RESOLUTION_MM for z in caps
    ):
        raise RuntimeError(f"receiver strip: wrong native receiver caps: {caps!r}")
    _dimension(component, "CoefficientsPlate", "PlateThickness", lever.PLATE_T)
    _dimension(component, "CylinderProfile", "CylDia", 2.0 * lever.CYL_R)
    _dimension(component, "SpringPadProfile", "SpringPadWidth", lever.SPRING_PAD_W)
    _dimension(component, "SpringPadProfile", "SpringSeatThickness", lever.SPRING_SEAT_T)
    _dimension(component, "EdgeRibBackProfile", "EdgeRibBackEndTopX", lever.RIB_PLATE_REACH)
    if lever.RIB_PLATE_REACH + lever.RIB_END_R >= lever.HOLE_X - blind_cut_dia_mm(lever.HOLE_SPEC) / 2.0:
        raise RuntimeError("receiver strip: filled invariant tools reach the hole field")


def _added_material(modeler: Any, bodies: list[Any]) -> list[Any]:
    """Native actual strip minus ONLY known unchanged volume; keep -X web."""
    low = tuple(min(_extreme(b, k, -1, "receiver bounds") for b in bodies) - 1.0 for k in (0, 1))
    high = tuple(max(_extreme(b, k, 1, "receiver bounds") for b in bodies) + 1.0 for k in (0, 1))
    pieces = []
    for body in bodies:
        pieces.extend(_operation(
            _copy(body, "receiver strip"),
            _box(modeler, (*low, OLD_INNER_Z_MM), (*high, NEW_INNER_Z_MM), "receiver strip"),
            15901, "receiver strip",
        ))
    if not pieces:
        raise RuntimeError("receiver strip: actual new material unavailable")
    z0, z1 = OLD_INNER_Z_MM - 1.0, NEW_INNER_Z_MM + 1.0
    # Exact unchanged source prisms. Extend axially beyond the strip to avoid
    # coincident end tools. Never subtract a whole rib/profile bounding slab.
    tools = [
        _box(modeler, (0.0, -lever.PLATE_T / 2.0, z0),
             (lever.PLATE_W, lever.PLATE_T / 2.0, z1), "invariant coefficient plate"),
        _solid(modeler.CreateBodyFromCyl(double_array((
            0.0, 0.0, z0 / 1000.0, 0.0, 0.0, 1.0,
            lever.CYL_R / 1000.0, (z1 - z0) / 1000.0,
        ))), "invariant pivot cylinder"),
        _box(modeler, (lever.PLATE_W - lever.SPRING_PAD_W, lever.PLATE_T / 2.0 - lever.SPRING_SEAT_T, z0),
             (lever.PLATE_W, lever.PLATE_T / 2.0, z1), "invariant spring pad"),
    ]
    for tool in tools:
        remaining = []
        for body in pieces:
            # A disjoint CUT still consumes its inputs. Keep a fresh copy only
            # for that documented case; all other nonzero statuses are fatal.
            target, cutter = _copy(body, "receiver subtraction"), _copy(tool, "receiver subtraction")
            try:
                result = target.Operations2(15902, cutter, 0)  # SWBODYCUT
            finally:
                target = cutter = None
            if not isinstance(result, tuple) or len(result) != 2:
                raise RuntimeError("receiver strip: malformed native subtraction")
            values, status = result
            if status in (5, 1067) and not values:
                remaining.append(_copy(body, "disjoint receiver subtraction"))
            elif status != 0:
                raise RuntimeError(f"receiver strip: native subtraction failed (status={status})")
            else:
                remaining.extend(_solid(raw, "receiver subtraction") for raw in values or ())
        pieces = remaining
    if not pieces or sum(_volume(b, "receiver added material") for b in pieces) <= 0.0:
        raise RuntimeError("receiver strip: subtraction erased the actual rib addition")
    observed = (min(_extreme(b, 2, -1, "receiver strip extent") for b in pieces),
                max(_extreme(b, 2, 1, "receiver strip extent") for b in pieces))
    if max(abs(a - b) for a, b in zip(observed, (OLD_INNER_Z_MM, NEW_INNER_Z_MM), strict=True)) > NATIVE_RESOLUTION_MM:
        raise RuntimeError(f"receiver strip: wrong actual added-strip bounds: {observed!r}")
    return pieces


def _instances(assembly: Any, count: int) -> dict[str, list[Any]]:
    expected = {**dict.fromkeys(CHANNEL_FAMILIES, count), **FIXED_COUNTS}
    found: dict[str, list[Any]] = {family: [] for family in expected}
    components = assembly.GetComponents(False)  # Includes configured nested leaves.
    if not isinstance(components, (tuple, list)) or not components:
        raise RuntimeError("receiver strip: configured nested components unavailable")
    names = set()
    for raw in components:
        component = _early_bound(raw, "IComponent2")
        if component is None:
            raise RuntimeError("receiver strip: native component unavailable")
        name = str(_read_member(component, "Name2") or "")
        source = _read_member(component, "GetPathName")
        if not name or not isinstance(source, str) or not source or name in names:
            raise RuntimeError("receiver strip: missing/duplicate configured occurrence identity")
        names.add(name)
        stem = PureWindowsPath(source).stem.casefold()
        family = "ch-vn-channel-spring-installed" if stem.startswith("ch-vn-channel-spring-installed-stretch") else stem
        if family in found:
            if bool(_read_member(component, "IsSuppressed")):
                raise RuntimeError(f"receiver strip: required occurrence suppressed: {name}")
            found[family].append(component)
    for family, wanted in expected.items():
        found[family].sort(key=lambda c: str(_read_member(c, "Name2")))
        if len(found[family]) != wanted:
            raise RuntimeError(f"receiver strip: missing coverage for {family}: {len(found[family])}, expected {wanted}")
    return found


def _distance(model: Any, first: Any, second: Any, label: str) -> tuple[float, tuple]:
    result = model.ClosestDistance(first, second)
    if not isinstance(result, tuple) or len(result) != 3:
        raise RuntimeError(f"{label}: malformed native ClosestDistance")
    distance = float(result[0]) * 1000.0
    points = []
    for raw in result[1:]:
        if not isinstance(raw, (tuple, list)) or len(raw) != 3:
            raise RuntimeError(f"{label}: missing native distance witnesses")
        points.append(tuple(float(v) * 1000.0 for v in raw))
    if not math.isfinite(distance) or distance <= 0.0 or not all(math.isfinite(v) for p in points for v in p):
        raise RuntimeError(f"{label}: added strip has no positive static native air: {result!r}")
    if abs(math.dist(*points) - distance) > NATIVE_RESOLUTION_MM:
        raise RuntimeError(f"{label}: native distance/witness disagreement")
    return distance, tuple(points)


def assert_receiver_added_strip(adapter: Any, asm_name: str) -> list[dict[str, Any]]:
    """Require zero overlap AND positive air for every listed installed pair.

    Existing lever/knife/bracket/thread contacts are not measured as air: only
    the new-strip superset participates. No whole-part allowed-pair cap can
    exempt a collision or zero-distance contact here. Returned/logged witnesses
    are in machine mm, at the actual current saved configuration and pose.
    """
    if asm_name != "ha-harmonic-analyzer":
        raise ValueError("receiver strip requires the integrated ha-harmonic-analyzer")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    if model.IsExploded() is not False:
        raise RuntimeError("receiver strip: requires the collapsed installed configuration")
    count = _config.active_count()
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise RuntimeError("receiver strip: invalid configured channel coverage")
    assembly = _early_bound(adapter.currentModel, "IAssemblyDoc")
    found = _instances(assembly, count)
    receiver = found["sm-summing-lever"][0]
    _assert_receiver(receiver)
    receiver_name = str(_read_member(receiver, "Name2"))
    bodies, transform = _component_solids(assembly, receiver_name, "receiver strip")
    if len(bodies) != 1:
        raise RuntimeError("receiver strip: expected the one actual configured lever solid")
    modeler = _early_bound(adapter.swApp.GetModeler(), "IModeler")
    if modeler is None:
        raise RuntimeError("receiver strip: native modeler unavailable")
    added = [_solid(_transformed_body_copy(body, transform, "installed receiver strip"), "installed receiver strip")
             for body in _added_material(modeler, bodies)]
    records = []
    for family, instances in found.items():
        if family == "sm-summing-lever":
            continue
        for component in instances:
            name = str(_read_member(component, "Name2"))
            label = f"receiver strip / {name}"
            solids, pose = _component_solids(assembly, name, label)
            placed = [_solid(_transformed_body_copy(body, pose, label), label) for body in solids]
            overlap, closest, witnesses = 0.0, math.inf, None
            for strip in added:
                for fixed in placed:
                    intersections = _operation(_copy(strip, label), _copy(fixed, label), 15901, label)
                    overlap += sum(_volume(body, label) for body in intersections)
                    if overlap != 0.0:
                        raise RuntimeError(f"{label}: added material intersects ({overlap:.17g} mm^3); no allowed-pair exemption")
                    distance, points = _distance(model, strip, fixed, label)
                    if distance < closest:
                        closest, witnesses = distance, points
            record = {"receiver": receiver_name, "neighbor": name, "family": family,
                      "overlap_mm3": overlap, "closest_distance_mm": closest,
                      "closest_points_mm": witnesses, "material_scope": MATERIAL_SCOPE,
                      "local_strip_z_mm": (OLD_INNER_Z_MM, NEW_INNER_Z_MM), "claim": CLAIM}
            _telemetry.info(f"receiver added-strip static air: {record}")
            records.append(record)
    return records
