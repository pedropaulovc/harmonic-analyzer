"""Saved cylinder-bank retention readback, without moving production components.

The native witness binds the continuous printed-tolerance enclosure in
``cylinder_bank_layout.SOUTH_DISC_CLEARANCE`` to actual saved solids. Only
checked temporary body copies are posed at the shared ENGAGED pinion station.
The top-level witness checks finite ring/cam cylinders and installed seating;
it is not a motion simulation or a sampled replacement for that enclosure.
"""
from __future__ import annotations

import math
from pathlib import PureWindowsPath
from typing import Any, Literal

import _config
import _telemetry
import ch_connecting_rod_spec as rod
import cone_line as line
import cylinder_bank_layout as bank
import dt_arbor_pedestal_spec as pedestal
import dt_crank_drive_gear_spec as drive
import dt_cylinder_end_disc_spec as disc
import dt_cylinder_gear_shaft_spec as shaft
import dt_cylinder_gear_spec as gear
import dt_vn_cylinder_bank_spring_spec as spring
import pinion_rig_layout as rig
import pinion_rig_park_geometry as park
from _com import _early_bound
from _native_tip_collar_air import (
    NATIVE_RESOLUTION_MM,
    _array,
    _closest,
    _copy,
    _cylinders,
    _extreme,
    _faces,
    _solid,
    _transform,
)

_IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
_Z = (0.0, 0.0, 1.0)


def _near(actual: float, expected: float, label: str) -> float:
    if not math.isfinite(actual) or abs(actual - expected) > NATIVE_RESOLUTION_MM:
        raise RuntimeError(f"bank retention: {label}: {actual!r} != {expected!r} mm")
    return actual


def _vector(actual, expected, label):
    for index, (read, want) in enumerate(zip(actual, expected, strict=True)):
        _near(read, want, f"{label}[{index}]")


def _inventory(assembly, assembly_kind: Literal["drive_train", "top_assembly"]):
    raw = assembly.GetComponents(assembly_kind == "drive_train")
    if not isinstance(raw, (tuple, list)) or not raw:
        raise RuntimeError("bank retention: actual saved component inventory unavailable")
    found = {}
    for value in raw:
        component = _early_bound(value, "IComponent2")
        path = component.GetPathName()
        if type(path) is not str or not path:
            raise RuntimeError("bank retention: actual component path unavailable")
        stem = PureWindowsPath(path).stem
        found.setdefault(stem, []).append(component)
    return found


def _family(found, stem, count):
    values = found.get(stem, ())
    if len(values) != count:
        raise RuntimeError(
            f"bank retention: expected {count} actual {stem} instance(s), got {len(values)}"
        )
    return values


def _body(component):
    label = component.Name2
    result = component.GetBodies3(0)  # swSolidBody; configured assembly-context solids
    if not isinstance(result, tuple) or len(result) != 2 or len(result[0] or ()) != 1:
        raise RuntimeError(f"bank retention: {label}: expected one actual configured solid")
    if tuple(result[1] or ()) != (1,):  # swNormalBody_e, not assembly-cut swUserBody_e
        raise RuntimeError(f"bank retention: {label}: assembly-modified body cannot share part metrology")
    body = _solid(result[0][0], label)
    transform = _early_bound(component.GetTotalTransform(False), "IMathTransform")
    pose = _array(transform, label)
    return body, transform, pose


def _source_key(component):
    path, configuration = component.GetPathName(), component.ReferencedConfiguration
    if type(path) is not str or not path or type(configuration) is not str:
        raise RuntimeError("bank retention: configured native part identity unavailable")
    return path.casefold(), configuration


def _origin(pose):
    return tuple(value * 1000.0 for value in pose[9:12])


def _world(pose, point):
    return tuple(
        pose[9 + k] * 1000.0 + sum(point[j] * pose[3 * j + k] for j in range(3))
        for k in range(3)
    )


def _pose(pose, origin, axes, label):
    _vector(_origin(pose), origin, f"{label} origin")
    if max(abs(a - b) for a, b in zip(pose[:9], axes, strict=True)) > 1e-8:
        raise RuntimeError(f"bank retention: {label}: saved rotation differs from its spec pose")


def _axis(pose, axis, label):
    if max(abs(a - b) for a, b in zip(pose[6:9], axis, strict=True)) > 1e-8:
        raise RuntimeError(f"bank retention: {label}: saved axial direction differs from its spec")


def _span(body, index, low, high, label):
    negative = tuple(-1.0 if k == index else 0.0 for k in range(3))
    positive = tuple(-value for value in negative)
    return (
        _near(_extreme(body, negative, label)[index], low, f"{label} south"),
        _near(_extreme(body, positive, label)[index], high, f"{label} north"),
    )


def _plane(body, station, point_xy, label):
    """Read the actual finite axial seating face, not only a transform datum."""
    for face in _faces(body):
        surface = _early_bound(face.GetSurface(), "ISurface")
        if surface is None:
            raise RuntimeError(f"bank retention: {label}: native surface unavailable")
        if surface.IsPlane() is not True:
            continue
        params = tuple(float(value) for value in (surface.PlaneParams or ()))
        if len(params) != 6 or not all(math.isfinite(value) for value in params):
            raise RuntimeError(f"bank retention: {label}: native plane data unavailable")
        if max(abs(params[0]), abs(params[1]), abs(abs(params[2]) - 1.0)) > 1e-8:
            continue
        if abs(params[5] * 1000.0 - station) > NATIVE_RESOLUTION_MM:
            continue
        point = (*point_xy, station)
        if math.dist(_closest(face, point, label), point) <= NATIVE_RESOLUTION_MM:
            return
    raise RuntimeError(f"bank retention: {label}: actual finite seating plane missing")


def _finite_cylinder(body, radius, centre_xy, south, north, label, *, axial_index=2):
    """Require the full finite native cylinder, not an untrimmed surface radius.

    Two complete circular boundaries and only an optional straight seam rule
    out a slotted/partial bore or a cam whose cylinder is axially shortened.
    GetCurve MUST precede GetCurveParams2 (the SDK's documented contract).
    No approximate face area or phase sampling is used as a continuity proof.
    """
    transverse = tuple(k for k in range(3) if k != axial_index)
    axis = tuple(1.0 if k == axial_index else 0.0 for k in range(3))
    candidates = _cylinders(body, radius, axis, label)
    if len(candidates) != 1:
        raise RuntimeError(f"bank retention: {label}: expected one unbroken cylinder face")
    face, origin, _direction, _radius = candidates[0]
    _vector(tuple(origin[k] for k in transverse), centre_xy, f"{label} axis")
    edges = face.GetEdges()
    if not isinstance(edges, (tuple, list)) or not edges:
        raise RuntimeError(f"bank retention: {label}: finite cylinder edges unavailable")
    circles = []
    for raw in edges:
        edge = _early_bound(raw, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if curve is None:
            raise RuntimeError(f"bank retention: {label}: native edge curve unavailable")
        params = tuple(float(value) for value in (edge.GetCurveParams2() or ()))
        # The last three doubles encode packed integers, not floating values.
        if len(params) != 11 or not all(math.isfinite(value) for value in params[:8]):
            raise RuntimeError(f"bank retention: {label}: native edge bounds unavailable")
        endpoints = tuple(tuple(value * 1000.0 for value in params[i:i + 3]) for i in (0, 3))
        if curve.IsCircle() is True:
            circle = tuple(float(value) for value in (curve.CircleParams or ()))
            if len(circle) != 7 or not all(math.isfinite(value) for value in circle):
                raise RuntimeError(f"bank retention: {label}: native circle data unavailable")
            _vector(tuple(circle[k] * 1000.0 for k in transverse), centre_xy, f"{label} circle centre")
            _near(circle[6] * 1000.0, radius, f"{label} circle radius")
            if max(*(abs(circle[3 + k]) for k in transverse), abs(abs(circle[3 + axial_index]) - 1.0)) > 1e-8:
                raise RuntimeError(f"bank retention: {label}: circular boundary is tilted")
            if abs(params[7] - params[6] - math.tau) > 1e-8:
                raise RuntimeError(f"bank retention: {label}: circular boundary is only an arc")
            _vector(endpoints[0], endpoints[1], f"{label} closed circle")
            z = circle[axial_index] * 1000.0
            _near(endpoints[0][axial_index], z, f"{label} circle plane")
            circles.append(z)
        elif curve.IsLine() is True:
            # A periodic cylindrical face may expose its straight seam once or
            # twice. No other trims (holes, slots, scallops) are admitted.
            ends_xy = tuple(tuple(point[k] for k in transverse) for point in endpoints)
            _vector(*ends_xy, f"{label} straight seam")
            _near(math.dist(ends_xy[0], centre_xy), radius, f"{label} seam radius")
            for actual, expected in zip(sorted(point[axial_index] for point in endpoints), (south, north), strict=True):
                _near(actual, expected, f"{label} seam end")
        else:
            raise RuntimeError(f"bank retention: {label}: unexpected trim in continuous cylinder")
    if len(circles) != 2:
        raise RuntimeError(f"bank retention: {label}: two complete end circles not found")
    for actual, expected in zip(sorted(circles), (south, north), strict=True):
        _near(actual, expected, f"{label} finite end")
    return {"radius_mm": _radius, "south_mm": min(circles), "north_mm": max(circles)}


def _annulus(body, outer, bore, thickness, label):
    axial = _span(body, 2, 0.0, thickness, label)
    for index in (0, 1):
        _span(body, index, -outer / 2.0, outer / 2.0, label)
    outside = _finite_cylinder(body, outer / 2.0, (0.0, 0.0), 0.0, thickness, f"{label} outside")
    inside = _finite_cylinder(body, bore / 2.0, (0.0, 0.0), 0.0, thickness, f"{label} bore")
    for station in (0.0, thickness):
        _plane(body, station, (0.0, -(outer + bore) / 4.0), f"{label} annular face")
    return {"od_mm": 2.0 * outside["radius_mm"], "bore_mm": 2.0 * inside["radius_mm"],
            "thickness_mm": axial[1] - axial[0]}


def _material(component):
    model = _early_bound(component.GetModelDoc2(), "IModelDoc2")
    part = _early_bound(model, "IPartDoc")
    if model is None or part is None:
        raise RuntimeError("bank retention: saved disc part is not resolved for material readback")
    config = component.ReferencedConfiguration
    if type(config) is not str:
        raise RuntimeError("bank retention: disc referenced configuration unavailable")
    configurations = model.GetConfigurationNames()
    if (not isinstance(configurations, (tuple, list)) or not configurations
            or any(type(name) is not str for name in configurations)
            or config not in configurations):
        raise RuntimeError("bank retention: saved disc configuration inventory unavailable/mismatched")
    # IPartDoc's documented sole-default contract requires the empty name.
    # Multi-configuration parts must query the occurrence's exact saved config,
    # not whichever configuration its shared model document happens to show.
    query_config = "" if len(configurations) == 1 else config
    result = part.GetMaterialPropertyName2(query_config)
    if not isinstance(result, tuple) or len(result) != 2:
        raise RuntimeError("bank retention: GetMaterialPropertyName2 did not return material/database")
    material, database = result
    expected = _config.parts("dt-cylinder-end-disc")["material"]
    if type(material) is not str or material != expected or type(database) is not str or not database:
        raise RuntimeError(f"bank retention: saved disc material {result!r} is not {expected!r}")
    return material


def _distance(model, first, second, label):
    result = model.ClosestDistance(first, second)
    if not isinstance(result, tuple) or len(result) != 3:
        raise RuntimeError(f"bank retention: {label}: native ClosestDistance unavailable: {result!r}")
    distance = float(result[0]) * 1000.0
    points = tuple(tuple(float(value) * 1000.0 for value in point) for point in result[1:])
    if (not math.isfinite(distance) or distance <= NATIVE_RESOLUTION_MM
            or any(len(point) != 3 or not all(math.isfinite(v) for v in point) for point in points)):
        raise RuntimeError(f"bank retention: {label}: no positive native separation: {result!r}")
    _near(math.dist(*points), distance, f"{label} closest-point distance")
    return distance


def _separating_air(first, second, normal, label):
    """Positive support-plane gap excludes intersection AND nested solids."""
    maximum_first = sum(a * b for a, b in zip(_extreme(first, normal, label), normal, strict=True))
    minimum_second = sum(a * b for a, b in zip(
        _extreme(second, tuple(-v for v in normal), label), normal, strict=True,
    ))
    air = minimum_second - maximum_first
    if not math.isfinite(air) or air <= NATIVE_RESOLUTION_MM:
        raise RuntimeError(f"bank retention: {label}: native separating plane closes: {air}")
    return air


def _ring_witness(found, gears):
    rings = _family(found, "ch-connecting-rod", _config.active_count())
    ring_records = []
    checked_parts = set()
    for component in rings:
        body, _transform_obj, pose = _body(component)
        key = _source_key(component)
        if key not in checked_parts:
            _finite_cylinder(body, rod.RING_BORE_DIA / 2.0, (0.0, 0.0),
                             -rod.RING_THICKNESS / 2.0, rod.RING_THICKNESS / 2.0,
                             "connecting-rod running bore")
            checked_parts.add(key)
        if max(abs(pose[6]), abs(pose[7]), abs(abs(pose[8]) - 1.0)) > 1e-8:
            raise RuntimeError("bank retention: saved ring axis is not parallel to the bank")
        centre = _origin(pose)
        nearest = min(gears, key=lambda item: abs(centre[2] - item["cam_centre"][2]))
        radial = math.dist(centre[:2], nearest["cam_centre"][:2])
        # The saved home pose is concentric; the analytic proof separately pays
        # all running float and eccentricity/size extremes throughout rotation.
        _near(radial, 0.0, "saved ring/cam concentricity")
        ring_z = sorted(_world(pose, (0.0, 0.0, z))[2]
                        for z in (-rod.RING_THICKNESS / 2.0, rod.RING_THICKNESS / 2.0))
        axial_air = min(ring_z[0] - nearest["cam_south"], nearest["cam_north"] - ring_z[1])
        if axial_air <= NATIVE_RESOLUTION_MM:
            raise RuntimeError(f"bank retention: saved ring leaves its closed cam slot: {axial_air}")
        ring_records.append((nearest["station"], radial, axial_air))
    if len({row[0] for row in ring_records}) != len(rings):
        raise RuntimeError("bank retention: multiple saved rod rings occupy the same cam station")
    return {
        "ring_count": len(rings),
        "ring_cam_radial_error_max_mm": max(row[1] for row in ring_records),
        "ring_slot_air_min_mm": min(row[2] for row in ring_records),
    }


def measure(
    adapter: Any, *, assembly_kind: Literal["drive_train", "top_assembly"]
) -> dict[str, Any]:
    """Certify active saved dt-drive-train, or its instances in the saved top.

    Called by the existing saved-assembly soundness battery after its one shared
    rebuild. Reads configured solids, not recipe dimensions pretending to be
    metrology. No save, selection, mate/configuration edit or production put.
    """
    with _telemetry.span("verify.bank_retention", assembly_kind=assembly_kind) as sp:
        assembly = _early_bound(adapter.currentModel, "IAssemblyDoc")
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        found = _inventory(assembly, assembly_kind)
        disc_component, = _family(found, "dt-cylinder-end-disc", 1)
        spring_component, = _family(found, "dt-vn-cylinder-bank-spring", spring.COUNT)
        arbor_component, = _family(found, "dt-cylinder-gear-shaft", 1)
        pedestals = _family(found, "dt-arbor-pedestal", 2)
        disc_body, disc_transform, disc_pose = _body(disc_component)
        _pose(disc_pose, (line.X_DRUM, line.Y_DRIVE, bank.SOUTH_DISC_Z[0]), _IDENTITY, "single south disc")
        disc_dimensions = _annulus(disc_body, disc.WASHER_OD, disc.WASHER_BORE, disc.WASHER_THICK, "saved brass disc")
        material = _material(disc_component)
        spring_body, _spring_transform, spring_pose = _body(spring_component)
        _pose(spring_pose, (line.X_DRUM, line.Y_DRIVE, bank.BANK_SPRING_Z[0]), _IDENTITY, "north spring")
        spring_dimensions = _annulus(spring_body, spring.OD, spring.ID, spring.MODEL_HEIGHT, "saved spring envelope")
        arbor_body, _arbor_transform, arbor_pose = _body(arbor_component)
        _pose(arbor_pose, (line.X_DRUM, line.Y_DRIVE, bank.ARBOR_SOUTH_Z),
              (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, -1.0, 0.0), "stationary cylinder arbor")
        arbor_tips = _span(arbor_body, 1, -bank.ARBOR_DOME_HEIGHT,
                           bank.ARBOR_LENGTH + bank.ARBOR_DOME_HEIGHT, "arbor dome tips")
        arbor_cylinder = _finite_cylinder(arbor_body, shaft.SHAFT_DIA / 2.0, (0.0, 0.0), 0.0,
                         bank.ARBOR_LENGTH, "arbor bearing / dome roots", axial_index=1)
        pedestal_origins_z = []
        for component, z, axes, outer_z in zip(
            sorted(pedestals, key=lambda item: _origin(_array(
                _early_bound(item.GetTotalTransform(False), "IMathTransform"), "pedestal order"))[2]),
            (bank.FRONT_PEDESTAL_ORIGIN_Z, bank.BACK_PEDESTAL_ORIGIN_Z),
            (_IDENTITY, (-1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, -1.0)),
            (bank.ARBOR_SOUTH_Z, bank.ARBOR_SOUTH_Z + bank.ARBOR_LENGTH), strict=True,
        ):
            body, _pedestal_transform, pose = _body(component)
            _pose(pose, (line.X_DRUM, line.Y_BASE_TOP, z), axes, "arbor pedestal")
            pedestal_origins_z.append(_origin(pose)[2])
            _near(_world(pose, (0.0, pedestal.BORE_HEIGHT, pedestal.STRAP_ROOT_Z))[2],
                  outer_z, "pedestal outer face / arbor dome root")
            bore_faces = _cylinders(body, pedestal.BORE_DIA / 2.0, _Z, "pedestal bearing bore")
            for _face, bore_origin, *_ in bore_faces:
                _vector(bore_origin[:2], (0.0, pedestal.BORE_HEIGHT), "pedestal bearing axis")
            seat_radius = (max(pedestal.BORE_DIA, disc.WASHER_BORE, spring.ID) / 2.0
                           + min(pedestal.TOP_RADIUS, disc.WASHER_OD / 2.0, spring.OD / 2.0)) / 2.0
            for station in (pedestal.STRAP_ROOT_Z, pedestal.STRAP_INNER_Z):
                _plane(body, station, (0.0, pedestal.BORE_HEIGHT - seat_radius), "pedestal strap seat")
            # The apex tapped hole interrupts the TOP of this bore. Read the
            # finite lower bearing generatrix at both strap ends instead.
            for station in (pedestal.STRAP_ROOT_Z, pedestal.STRAP_INNER_Z):
                point = (0.0, pedestal.BORE_HEIGHT - pedestal.BORE_DIA / 2.0, station)
                _near(min(math.dist(_closest(face, point, "pedestal finite bearing"), point)
                          for face, *_ in bore_faces), 0.0, "pedestal full-depth arbor support")
        # These specific instances close both ends of the preloaded bank. This
        # is a retention inventory, not the retired blanket assembly-count gate.
        gears = []
        active_count = _config.active_count()
        full_bank = active_count == bank.COUNT
        checked_parts = set()
        for component in _family(found, "dt-cylinder-gear", active_count):
            body, _gear_transform, pose = _body(component)
            _axis(pose, (0.0, 0.0, -1.0), "cylinder gear")
            origin = _origin(pose)
            station = round((origin[2] - gear.FACE_WIDTH / 2.0 - bank.STATION_Z0) / bank.BANK_PITCH)
            if station not in range(active_count):
                raise RuntimeError("bank retention: saved cylinder gear is outside the bank")
            _vector(origin, (line.X_DRUM, line.Y_DRIVE, bank.station_z(station) + gear.FACE_WIDTH / 2.0),
                    "cylinder gear station")
            # All occurrences are normal (not assembly-cut) bodies. Inspect a
            # configured source's finite geometry once, then every saved pose.
            key = _source_key(component)
            if key not in checked_parts:
                _span(body, 2, 0.0, gear.OVERALL_THICKNESS, "saved cylinder gear")
                _finite_cylinder(body, gear.CAM_DIA / 2.0, (0.0, gear.ECCENTRICITY),
                                 gear.FACE_WIDTH, gear.OVERALL_THICKNESS, "saved eccentric cam")
                gear_bores = _cylinders(body, gear.BORE_DIA / 2.0, _Z, "saved gear arbor bore")
                for _face, bore_origin, *_ in gear_bores:
                    _vector(bore_origin[:2], (0.0, 0.0), "saved gear bore axis")
                for station_z in (0.0, gear.OVERALL_THICKNESS):
                    _plane(body, station_z, (0.0, -seat_radius), "bank end bearing face")
                checked_parts.add(key)
            gears.append({"station": station,
                          "cam_centre": _world(pose, (0.0, gear.ECCENTRICITY,
                                                      (gear.FACE_WIDTH + gear.OVERALL_THICKNESS) / 2.0)),
                          "cam_south": origin[2] - gear.OVERALL_THICKNESS,
                          "cam_north": origin[2] - gear.FACE_WIDTH,
                          "north": origin[2]})
        if {row["station"] for row in gears} != set(range(active_count)):
            raise RuntimeError("bank retention: an active saved cylinder-bank station is missing or duplicated")
        gears.sort(key=lambda row: row["station"])
        _near(gears[0]["cam_south"], bank.SOUTH_DISC_Z[1], "disc / gear 0 seat")
        if full_bank:
            _near(gears[-1]["north"], bank.BANK_SPRING_Z[0], "gear 19 / north spring seat")
        _near(_origin(spring_pose)[2] + spring.MODEL_HEIGHT, bank.BACK_STRAP_INNER_Z,
              "north spring / adjustable strap seat")
        gear64_component, = _family(found, "dt-crank-drive-gear", 1)
        gear64_body, gear64_transform, gear64_pose = _body(gear64_component)
        gear64_south = (drive.LAYOUT_CENTRE_STATION + line.GEAR_AXIS_SHIFT
                        + drive.CENTRE_SHIFT_NORTH - drive.FACE_WIDTH / 2.0)
        _vector(_origin(gear64_pose), line.cone_station(gear64_south), "64T engaged shaft station")
        _axis(gear64_pose, (line.SIN_I, 0.0, line.COS_I), "64T engaged shaft")
        pinion_component, = _family(found, "dt-alignment-pinion", 1)
        pinion_body, _pinion_transform, pinion_pose = _body(pinion_component)
        _pose(pinion_pose, (park.APINION_X, park.APINION_Y, rig.DRUM_FRONT_Z), _IDENTITY,
              "saved parked alignment pinion")
        utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
        if utility is None:
            raise RuntimeError("bank retention: native math utility unavailable")
        angle = park.ENGAGED_SWING_RAD
        c, s = math.cos(angle), math.sin(angle)
        engaged = _transform(utility, (c, s, 0.0, -s, c, 0.0, 0.0, 0.0, 1.0,
                            park.ENGAGED_APINION_XY[0] / 1000.0,
                            park.ENGAGED_APINION_XY[1] / 1000.0,
                            rig.DRUM_FRONT_Z / 1000.0, 1.0, 0.0, 0.0, 0.0), "ENGAGED pinion witness")
        placed_disc = _copy(disc_body, "saved disc witness", disc_transform)
        placed_gear64 = _copy(gear64_body, "64T witness", gear64_transform)
        placed_pinion = _copy(pinion_body, "ENGAGED pinion witness", engaged)
        cone_air = _distance(model, placed_disc, placed_gear64, "disc / 64T ENGAGED")
        pinion_air = _distance(model, placed_disc, placed_pinion, "disc / alignment pinion ENGAGED")
        cone_plane_air = _separating_air(
            placed_gear64, placed_disc, (line.COS_I, 0.0, -line.SIN_I), "disc / 64T ENGAGED",
        )
        radial = tuple(park.ENGAGED_APINION_XY[k] - (line.X_DRUM, line.Y_DRIVE)[k] for k in range(2))
        radial_length = math.hypot(*radial)
        pinion_plane_air = _separating_air(
            placed_disc, placed_pinion, (*tuple(value / radial_length for value in radial), 0.0),
            "disc / alignment pinion ENGAGED",
        )
        proof = disc.installed_clearance_budget(sum(bank.DATUM_CHAIN_STACK.values()))
        record = {"disc_count": 1, "disc_od_mm": disc_dimensions["od_mm"],
                  "disc_bore_mm": disc_dimensions["bore_mm"], "disc_thickness_mm": disc_dimensions["thickness_mm"],
                  "disc_material": material, "north_spring_count": spring.COUNT,
                  "pedestal_count": len(pedestals), "bank_station_count": len(gears),
                  "disc_south_z_mm": _origin(disc_pose)[2],
                  "north_spring_z_mm": [_origin(spring_pose)[2], _origin(spring_pose)[2] + spring_dimensions["thickness_mm"]],
                  "pedestal_origins_z_mm": pedestal_origins_z,
                  "arbor_dome_root_z_mm": [_world(arbor_pose, (0.0, arbor_cylinder[end], 0.0))[2]
                                          for end in ("south_mm", "north_mm")],
                  "arbor_tip_z_mm": [_world(arbor_pose, (0.0, end, 0.0))[2] for end in arbor_tips],
                  "native_gear_source_count": len(checked_parts),
                  "disc_64t_native_air_mm": cone_air,
                  "disc_engaged_pinion_native_air_mm": pinion_air,
                  "disc_64t_native_plane_air_mm": cone_plane_air,
                  "disc_engaged_pinion_native_plane_air_mm": pinion_plane_air,
                  "continuous_64t_worst_mm": proof["cone worst"],
                  "continuous_pinion_worst_mm": proof["engaged pinion worst"],
                  "continuous_retaining_land_mm": proof["retaining land"]}
        record.update({
            "assembly_kind": assembly_kind,
            "coverage": "full-bank" if full_bank else "partial-bank",
            "missing_bank_stations": list(range(active_count, bank.COUNT)),
            "north_bank_seat": "measured" if full_bank else "absent-stations",
        })
        if assembly_kind == "top_assembly":
            record.update(_ring_witness(found, gears))
        for name, value in record.items():
            sp.set_attribute(f"bank_retention.{name}", value)
        _telemetry.info(f"Saved native cylinder-bank retention (ENGAGED temporary-body witness): {record}")
        return record
