"""EXPERIMENT ONLY: native finite-face counter-spring clamp calibration.

Run only through verify:calibrate_summing_clamp on the throwaway branch. The
parent owns the COM seat; this child never acquires it and never writes YAML.
The saved counter lengths seed an outer native-pose/torque equilibrium refit.
The provisional gooseneck gap is only the coordinate system of its copied
native screw. Neither it nor the spring's axial bounding box is an acceptance
criterion. All reported contacts use the actual trimmed native faces/solids.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import traceback
from dataclasses import asdict, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _config  # noqa: E402
import _telemetry  # noqa: E402
import counter_spring_stock_geom as stock  # noqa: E402
import gooseneck_geom as goose  # noqa: E402
import spring_mount_geom as mounts  # noqa: E402
from _assembly import component_transform, place_components_batch  # noqa: E402
from _common import _early_bound, check, force_rebuild, run_build  # noqa: E402
from _cwm import put_component_pose  # noqa: E402
from _native_spring_contact import native_component_interference  # noqa: E402
from _transforms import ROT_Y_180, euler_from_rows  # noqa: E402
from cone_pivot_post_installation import SUMMING_Z  # noqa: E402
from diagnostics._seat_search import solve_component_contact  # noqa: E402
from diagnostics.calibrate_spring_seats import (  # noqa: E402
    _allowance_mm,
    _build_counter_variant,
    _close_active_part,
    _close_all,
    _owned_titles,
    _pose_record,
    _seated,
)

ROOT = Path(__file__).resolve().parents[3]
PARTS = ROOT / "cad/out/sldprt"
PRESETS = ("neutral", "square")
IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
ROLE_PARTS = {role: f"summing-clamp-experiment-{role}" for role in ("tube", "plug", "screw")}
SEED_GAP = goose.SPRING_SCREW_CLAMPED_GAP_MM
HEAD_X = goose.ARM_END_X - SEED_GAP
# Identity tolerances, never contact/placement allowances.
IDENTITY_MM = 1e-5
IDENTITY_AREA_MM2 = 1e-4


def _values(raw, count, label):
    if not isinstance(raw, (tuple, list)) or len(raw) != count:
        raise RuntimeError(f"{label}: expected {count} native values, got {raw!r}")
    values = [float(x) for x in raw]
    if not all(math.isfinite(x) for x in values):
        raise RuntimeError(f"{label}: non-finite native values")
    return values


def _solids(model):
    result = _early_bound(model, "IPartDoc").GetBodies2(0, False)
    if not isinstance(result, (tuple, list)) or not result:
        raise RuntimeError("part has no native solids")
    solids = [_early_bound(raw, "IBody2") for raw in result]
    if any(body is None or body.GetType() != 0 for body in solids):
        raise RuntimeError("part returned a non-solid body")
    return solids


def _face_rows(body):
    faces = body.GetFaces()
    if not isinstance(faces, (tuple, list)) or not faces:
        raise RuntimeError("native body has no faces")
    result = []
    for index, raw in enumerate(faces):
        face = _early_bound(raw, "IFace2")
        surface = _early_bound(face.GetSurface(), "ISurface")
        if surface is None:
            raise RuntimeError("native face has no surface")
        area = float(face.GetArea()) * 1e6
        if not math.isfinite(area) or area <= 0.0:
            raise RuntimeError("native face has invalid area")
        row = {"index": index, "area_mm2": area, "kind": "other"}
        if surface.IsPlane() is True:
            row.update(kind="plane", parameters_si=_values(surface.PlaneParams, 6, "plane"))
        elif surface.IsCylinder() is True:
            row.update(kind="cylinder", parameters_si=_values(surface.CylinderParams, 7, "cylinder"))
        result.append((face, row))
    return result


def _plane(row, x_mm, area_mm2=None):
    if row["kind"] != "plane":
        return False
    p = row["parameters_si"]
    return (
        abs(abs(p[0]) - 1.0) < 1e-10
        and abs(p[1]) < 1e-10 and abs(p[2]) < 1e-10
        and abs(p[3] * 1000.0 - x_mm) < IDENTITY_MM
        and (area_mm2 is None or abs(row["area_mm2"] - area_mm2) < IDENTITY_AREA_MM2)
    )


def _cylinder(row, radius_mm):
    if row["kind"] != "cylinder":
        return False
    p = row["parameters_si"]
    return (
        abs(abs(p[3]) - 1.0) < 1e-10
        and abs(p[4]) < 1e-10 and abs(p[5]) < 1e-10
        and abs(p[1] * 1000.0 - goose.ARM_Y) < IDENTITY_MM
        and abs(p[2]) * 1000.0 < IDENTITY_MM
        and abs(p[6] * 1000.0 - radius_mm) < IDENTITY_MM
    )


def _select_face(body, role):
    plug_area = math.pi * (goose.PLUG_DIA**2 - goose.SCREW_TAP_MINOR_DIA**2) / 4.0
    head_area = math.pi * (goose.SCREW_HEAD_DIA**2 - goose.SCREW_THREAD_MAJOR_DIA**2) / 4.0
    tube_area = math.pi * (goose.TUBE_DIA**2 - (goose.TUBE_DIA - 2 * goose.WALL_T)**2) / 4.0
    predicates = {
        "plug": lambda row: _plane(row, goose.ARM_END_X, plug_area),
        "head": lambda row: _plane(row, HEAD_X, head_area),
        "tube": lambda row: _plane(row, goose.ARM_END_X, tube_area),
        "shank": lambda row: _cylinder(row, goose.SCREW_THREAD_MAJOR_DIA / 2.0),
    }
    matches = [(face, row) for face, row in _face_rows(body) if predicates[role](row)]
    if len(matches) != 1:
        raise RuntimeError(f"{role}: expected one exact native face, got {len(matches)}")
    return matches[0]


def _extreme_x(body, direction):
    result = body.GetExtremePoint(float(direction), 0.0, 0.0)
    if not isinstance(result, tuple) or len(result) != 4 or result[0] is not True:
        raise RuntimeError(f"native extreme point failed: {result!r}")
    return _values(result[1:], 3, "extreme point")[0] * 1000.0


def _body_record(body):
    name = body.Name  # IBody2 get/put property, VT_BSTR; never a method.
    if type(name) is not str or not name:
        raise RuntimeError("native body identity is unreadable")
    mass = _values(body.GetMassProperties(1.0), 12, "body mass properties")
    if mass[3] <= 0.0:
        raise RuntimeError("native solid has no positive volume")
    return {
        "name": name,
        "volume_mm3": mass[3] * 1e9,
        "mass_properties_si_density_1": mass,
        "faces": [row for _, row in _face_rows(body)],
    }


def _persist(model, entity):
    extension = _early_bound(model.Extension, "IModelDocExtension")
    reference = extension.GetPersistReference3(entity)
    if not isinstance(reference, (tuple, list, bytes)) or not reference:
        raise RuntimeError("native persistent identity unavailable")
    return bytes(int(value) & 255 for value in reference).hex()


async def _extract_goose(adapter, report):
    """Copy the actual final three bodies; never redraw a head, slot or plug."""
    with _telemetry.span("clamp.extract_native_bodies"):
        check("open native gooseneck", await adapter.open_model(str(PARTS / "gooseneck.SLDPRT")))
        source = _early_bound(adapter.currentModel, "IModelDoc2")
        copied = {}
        try:
            bodies = _solids(source)
            if len(bodies) != 3:
                raise RuntimeError(f"expected tube/plug/screw, got {len(bodies)} native bodies")
            for body in bodies:
                rows = _face_rows(body)
                head_area = math.pi * (goose.SCREW_HEAD_DIA**2 - goose.SCREW_THREAD_MAJOR_DIA**2) / 4.0
                if any(_plane(row, HEAD_X, head_area) for _, row in rows):
                    role = "screw"
                elif any(_cylinder(row, goose.PLUG_DIA / 2.0) for _, row in rows):
                    role = "plug"
                else:
                    role = "tube"
                if role in copied:
                    raise RuntimeError(f"ambiguous native body role: {role}")
                face_role = "head" if role == "screw" else role
                face, face_row = _select_face(body, face_role)
                record = _body_record(body)
                record.update(body_persist_hex=_persist(source, body), contact_face={
                    **face_row, "persist_hex": _persist(source, face),
                })
                if role == "screw":
                    _select_face(body, "shank")
                    lo, hi = _extreme_x(body, -1), _extreme_x(body, 1)
                    if abs(lo - (HEAD_X - goose.SCREW_HEAD_T)) > IDENTITY_MM:
                        raise RuntimeError("native screw head thickness/station mismatch")
                    if abs(hi - HEAD_X - 14.0) > IDENTITY_MM:
                        raise RuntimeError("native screw is not 14 mm underhead")
                    slot_floor = HEAD_X - goose.SCREW_HEAD_T + goose.SCREW_SLOT_DEPTH
                    if not any(_plane(row, slot_floor) for _, row in rows):
                        raise RuntimeError("actual native screw slot floor is missing")
                    record.update(extreme_x_mm=[lo, hi], underhead_length_mm=hi - HEAD_X,
                                  slot_floor_x_mm=slot_floor)
                copy = _early_bound(body.Copy(), "IBody2")
                if copy is None:
                    raise RuntimeError(f"{role}: native body copy failed")
                copied[role] = copy
                report["source_bodies"][role] = record
            if set(copied) != set(ROLE_PARTS):
                raise RuntimeError("native source role census incomplete")
        finally:
            _close_active_part(adapter)
        for role, copy in copied.items():
            check(f"create {role} fixture part", await adapter.create_part())
            try:
                part = _early_bound(adapter.currentModel, "IPartDoc")
                # swCreateFeatureBodyCheck=1: validate, but do not simplify topology.
                feature = part.CreateFeatureFromBody3(copy, False, 1)
                if feature is None:
                    raise RuntimeError(f"{role}: native body import failed")
                await force_rebuild(adapter)
                solids = _solids(adapter.currentModel)
                if len(solids) != 1:
                    raise RuntimeError(f"{role}: copied fixture must be one solid")
                got = _body_record(solids[0])
                wanted = report["source_bodies"][role]
                if not math.isclose(got["volume_mm3"], wanted["volume_mm3"], rel_tol=1e-10, abs_tol=1e-7):
                    raise RuntimeError(f"{role}: native copy volume changed")
                before = sorted(row["area_mm2"] for row in wanted["faces"])
                after = sorted(row["area_mm2"] for row in got["faces"])
                if len(before) != len(after) or any(abs(a-b) > IDENTITY_AREA_MM2 for a,b in zip(before, after, strict=True)):
                    raise RuntimeError(f"{role}: native copy face topology changed")
                _select_face(solids[0], "head" if role == "screw" else role)
                # Fixture solids are worker-local; no production properties/export.
                path = PARTS / f"{ROLE_PARTS[role]}.SLDPRT"
                check(f"save {role} fixture", await adapter.save_file(str(path)))
                report["copied_bodies"][role] = got
            finally:
                _close_active_part(adapter)


def _matrix(rows, position):
    return [x for row in rows for x in row] + [x / 1000.0 for x in position] + [1.0, 0.0, 0.0, 0.0]


class Fixture:
    def __init__(self, adapter, names, evidence):
        self.adapter = adapter
        self.names = names
        self.model = _early_bound(adapter.currentModel, "IModelDoc2")
        self.assembly = _early_bound(adapter.currentModel, "IAssemblyDoc")
        self.extension = _early_bound(self.model.Extension, "IModelDocExtension")
        self.expected = {role: component_transform(adapter, name) for role, name in names.items()}
        self.evidence = evidence
        evidence["components"] = dict(names)
        self.allowance = _allowance_mm()
        self.resolution = float(_config.machine("springs", "calibration_resolution_mm"))
        self.guard = float(_config.machine("springs", "native_distance_guard_mm"))
        if not all(math.isfinite(x) and x > 0 for x in (self.resolution, self.guard)):
            raise ValueError("calibration resolution and distance guard must be positive")
        evidence["numerical_policy"] = {
            "boolean_stability_mm": self.allowance,
            "calibration_resolution_mm": self.resolution,
            "native_distance_guard_mm": self.guard,
            "finite_face_distance_limit_mm": self.guard + self.allowance + self.resolution,
        }
        self.distance_limit = self.guard + self.allowance + self.resolution
        self.trials = {"tilt": 0, "head": 0, "seat_iterations": 0, "native_predicates": 0, "distance_queries": 0}
        self.faces = {}
        evidence["faces"] = {}
        for role, body_role in (("plug", "plug"), ("head", "screw"), ("shank", "screw")):
            component = self.component(body_role)
            document = _early_bound(component.GetModelDoc2(), "IModelDoc2")
            if document is None:
                raise RuntimeError(f"{role}: fixture document unavailable")
            solids = _solids(document)
            if len(solids) != 1:
                raise RuntimeError(f"{role}: ambiguous fixture solid")
            face, row = _select_face(solids[0], role)
            corresponding = _early_bound(component.GetCorrespondingEntity(face), "IFace2")
            if corresponding is None:
                raise RuntimeError(f"{role}: face did not map to assembly context")
            self.faces[role] = corresponding
            evidence["faces"][role] = {
                **row, "component": names[body_role], "body_name": solids[0].Name,
                "part_face_persist_hex": _persist(document, face),
                "assembly_face_persist_hex": _persist(self.model, corresponding),
            }

    def component(self, role):
        result = _early_bound(self.assembly.GetComponentByName(self.names[role]), "IComponent2")
        if result is None:
            raise RuntimeError(f"missing fixture component {role}")
        return result

    def assert_poses(self):
        for role, target in self.expected.items():
            actual = component_transform(self.adapter, self.names[role])
            if len(actual) != 16 or max(abs(a-b) for a,b in zip(actual, target, strict=True)) > 1e-12:
                raise RuntimeError(f"{role}: actual fixture transform disagrees with requested pose")

    def put(self, targets):
        # Same waypoint protection as _seat_search: native Transform2 can ignore
        # sub-nanometre changes. Only grounded disposable fixture parts move.
        for role, target in targets.items():
            waypoint = list(target)
            waypoint[11] += 0.001
            put_component_pose(self.adapter, self.names[role], waypoint)
            put_component_pose(self.adapter, self.names[role], target)
            self.expected[role] = list(target)
        if self.extension.Rebuild(4) is not True:  # swUpdateMates, VT_BOOL
            raise RuntimeError("native fixture mate-only rebuild failed")
        self.assert_poses()

    def shift(self, role, direction, amount):
        target = list(self.expected[role])
        for index, value in enumerate(direction):
            target[9 + index] += value * amount / 1000.0
        self.put({role: target})

    def state(self, role):
        self.trials["native_predicates"] += 1
        result = native_component_interference(
            self.adapter, self.names["counter"], self.names[role], label=f"clamp spring/{role}"
        )
        self.assert_poses()
        return asdict(result)

    def distance(self, first, second):
        self.trials["distance_queries"] += 1
        raw = self.model.ClosestDistance(first, second)
        if not isinstance(raw, tuple) or len(raw) != 3:
            raise RuntimeError(f"malformed native distance {raw!r}")
        distance = float(raw[0]) * 1000.0
        p = _values(raw[1], 3, "distance point 1")
        q = _values(raw[2], 3, "distance point 2")
        if not math.isfinite(distance) or distance < 0.0:
            raise RuntimeError("native finite-face distance has no solution")
        if abs(math.dist(p, q) * 1000.0 - distance) > self.guard:
            raise RuntimeError("native distance disagrees with closest-point readback")
        self.assert_poses()
        return {"distance_mm": distance, "point1_mm": [v*1000 for v in p], "point2_mm": [v*1000 for v in q]}

    def face_distance(self, role):
        row = self.distance(self.faces[role], self.component("counter"))
        body_role = "plug" if role == "plug" else "screw"
        transform = self.expected[body_role]
        if role != "shank":
            local_x = goose.ARM_END_X if role == "plug" else HEAD_X
            world_x = transform[9] * 1000.0 - local_x
            if abs(row["point1_mm"][0] - world_x) > self.guard:
                raise RuntimeError(f"{role}: closest point is not on the transformed clamp face")
        return row

    def seat(self, moving, fixed, direction):
        result = solve_component_contact(
            self.adapter, self.names[moving], self.names[fixed], direction,
            mounts.MIN_CLEARANCE_MM / 2.0,
            label=f"clamp {moving}/{fixed}", locate_only=True,
        )
        self.trials["seat_iterations"] += result.iterations
        self.shift(moving, direction, result.clear_offset_mm + self.allowance)
        return asdict(result)

    def require_contact(self, role):
        result = self.face_distance(role)
        if result["distance_mm"] > self.distance_limit:
            raise RuntimeError(f"{role}: finite face not in contact ({result!r}); a shank/body contact is insufficient")
        return result


def _rotated_seed(seed, travel):
    # travel is arc length at the upper eye about the fixed lower boss anchor.
    # It is a conditioned tilt parameter in mm, NOT a translated calibration row.
    anchor = mounts.COUNTER_ANCHOR_XY
    radius = math.dist(anchor, seed.upper_eye_xy)
    angle = travel / radius
    c, s = math.cos(angle), math.sin(angle)
    def turn(point):
        x, y = point[0] - anchor[0], point[1] - anchor[1]
        return anchor[0] + c*x + s*y, anchor[1] - s*x + c*y
    ux, uy = seed.axis_xy
    return replace(seed, lower_eye_xy=turn(seed.lower_eye_xy), upper_eye_xy=turn(seed.upper_eye_xy),
                   centre_xy=turn(seed.centre_xy), axis_xy=(c*ux+s*uy, -s*ux+c*uy))


def _tilt_trial(fixture, seed, travel):
    fixture.trials["tilt"] += 1
    pose = _rotated_seed(seed, travel)
    ux, uy = pose.axis_xy
    y = pose.upper_eye_xy[1] + mounts.counter_upper_support_offset(pose.axis_xy) - goose.ARM_Y
    origin = [mounts.COLUMN_X, y, SUMMING_Z]
    open_origin = [mounts.COLUMN_X + goose.SPRING_SCREW_OPEN_GAP_MM - SEED_GAP, y, SUMMING_Z]
    fixture.put({
        "counter": _matrix(pose.rotation_rows, [*pose.centre_xy, SUMMING_Z]),
        "plug": _matrix(ROT_Y_180, origin), "tube": _matrix(ROT_Y_180, origin),
        "screw": _matrix(ROT_Y_180, open_origin),
    })
    lower = fixture.seat("counter", "boss", (-ux, -uy, 0.0))
    lower_delta = lower["clear_offset_mm"] + fixture.allowance
    dx, dy = -ux*lower_delta, -uy*lower_delta
    pose = replace(pose, centre_xy=(pose.centre_xy[0]+dx, pose.centre_xy[1]+dy),
                   lower_eye_xy=(pose.lower_eye_xy[0]+dx, pose.lower_eye_xy[1]+dy),
                   upper_eye_xy=(pose.upper_eye_xy[0]+dx, pose.upper_eye_xy[1]+dy))
    # Translate the open, exact native screw in Y. Its finite cylindrical face
    # is checked independently, so touching its head cannot count as seating.
    upper = fixture.seat("screw", "counter", (0.0, -1.0, 0.0))
    y = fixture.expected["screw"][10] * 1000.0
    fixture.put({role: _matrix(ROT_Y_180, [mounts.COLUMN_X, y, SUMMING_Z]) for role in ("tube", "plug")})
    shank = fixture.require_contact("shank")
    open_head = fixture.face_distance("head")
    if open_head["distance_mm"] <= fixture.distance_limit:
        raise RuntimeError("8 mm installation position does not leave the finite head clear")
    state = fixture.state("plug")
    result = {"parameter_mm": travel, "state": state["state"], "native": state,
              "pose": _pose_record(pose), "gooseneck_origin_y_mm": y,
              "lower": lower, "upper": upper, "shank": shank, "open_head": open_head}
    if state["state"] == "clear":
        result["plug_face"] = fixture.face_distance("plug")
    fixture.evidence["last_tilt_trial"] = result
    return result


def _bisect(evaluate, overlap, clear, resolution):
    if overlap["state"] != "interfering" or clear["state"] != "clear":
        raise RuntimeError("native root requires an actual overlap/clear bracket")
    if overlap["parameter_mm"] >= clear["parameter_mm"]:
        raise RuntimeError("native bracket direction is reversed")
    for _ in range(64):
        lo, hi = overlap["parameter_mm"], clear["parameter_mm"]
        if hi - lo <= resolution:
            return {"overlap": overlap, "clear": clear, "width_mm": hi-lo}
        trial = evaluate((lo+hi)/2.0)
        if trial["state"] == "interfering":
            overlap = trial
        else:
            clear = trial
    raise RuntimeError("native clamp root did not converge in 64 bisections")


def _plug_root(fixture, seed):
    with _telemetry.span("clamp.solve_tilt_and_seats"):
        evaluate = lambda travel: _tilt_trial(fixture, seed, travel)
        first = evaluate(0.0)
        # March in 0.1 mm upper-eye arc steps; do not leap across a finite solid
        # and mistake a second clear side for an absent collision interval.
        direction = -1.0 if first["state"] == "clear" else 1.0
        previous = first
        for index in range(1, 41):
            trial = evaluate(direction * index * 0.1)
            if trial["state"] != previous["state"]:
                overlap, clear = (trial, previous) if direction < 0 else (previous, trial)
                bracket = _bisect(evaluate, overlap, clear, fixture.resolution)
                fixture.evidence["plug_bracket"] = bracket
                landed = evaluate(bracket["clear"]["parameter_mm"] + fixture.allowance)
                if landed["state"] != "clear":
                    raise RuntimeError("plug boundary landing is not natively clear")
                landed["plug_face"] = fixture.require_contact("plug")
                fixture.evidence["plug_landed"] = landed
                return landed
            previous = trial
        raise RuntimeError("finite plug contact not bracketed within +/-4 mm upper-eye arc")


def _close_screw(fixture):
    with _telemetry.span("clamp.close_native_screw"):
        open_transform = list(fixture.expected["screw"])
        def evaluate(gap):
            fixture.trials["head"] += 1
            target = list(open_transform)
            target[9] = (mounts.COLUMN_X + gap - SEED_GAP) / 1000.0
            fixture.put({"screw": target})
            native = fixture.state("screw")
            result = {"parameter_mm": gap, "state": native["state"], "native": native}
            if native["state"] == "clear":
                result["head_face"] = fixture.face_distance("head")
            fixture.evidence["last_head_trial"] = result
            return result
        first = evaluate(goose.SPRING_SCREW_OPEN_GAP_MM)
        if first["state"] != "clear":
            raise RuntimeError("open native screw interferes with the spring")
        previous = first
        # First native collision from the open side, not a guessed eye width.
        for index in range(1, 81):
            trial = evaluate(goose.SPRING_SCREW_OPEN_GAP_MM - index * 0.1)
            if trial["state"] == "interfering":
                bracket = _bisect(evaluate, trial, previous, fixture.resolution)
                fixture.evidence["head_bracket"] = bracket
                gap = bracket["clear"]["parameter_mm"] + fixture.allowance
                landed = evaluate(gap)
                if landed["state"] != "clear":
                    raise RuntimeError("screw closure landing is not natively clear")
                fixture.evidence["head_landed"] = landed
                fixture.require_contact("head")
                return gap
            previous = trial
        raise RuntimeError("native under-head contact not bracketed between 8 and 0 mm gap")


def _positive_controls(fixture, final_gap):
    """Exercise the finite-face channels independently of shank bearing."""
    controls = {}
    original = {key: list(value) for key, value in fixture.expected.items()}
    try:
        for face_role, body_role, direction in (("head", "screw", 1.0), ("plug", "plug", -1.0)):
            at_contact = fixture.face_distance(face_role)
            fixture.shift(body_role, (direction, 0.0, 0.0), 0.05)
            withdrawn = fixture.face_distance(face_role)
            native = fixture.state(body_role)
            if native["state"] != "clear" or withdrawn["distance_mm"] < 0.04:
                raise RuntimeError(f"{face_role}: finite-face withdrawal positive control failed")
            controls[face_role] = {"contact": at_contact, "withdrawn_0_05_mm": withdrawn, "native": native}
            fixture.put(original)
        face_gap = fixture.distance(fixture.faces["plug"], fixture.faces["head"])
        if abs(face_gap["distance_mm"] - final_gap) > fixture.guard:
            raise RuntimeError("independent native face-to-face gap disagrees with axial placement")
        fixture.shift("screw", (1.0, 0.0, 0.0), 0.05)
        shifted_gap = fixture.distance(fixture.faces["plug"], fixture.faces["head"])
        if abs(shifted_gap["distance_mm"] - face_gap["distance_mm"] - 0.05) > fixture.guard:
            raise RuntimeError("finite-face gap translation readback failed")
        controls["face_gap"] = {"closed": face_gap, "screw_withdrawn_0_05_mm": shifted_gap}
    finally:
        fixture.put(original)
    return controls


async def _calibrate_length(adapter, preset, length, refit, evidence):
    seed = mounts.counter_pose(length)
    force = mounts.counter_force_n(length)
    if not math.isfinite(force) or force > mounts.COUNTER_MAXIMUM_LOAD_N:
        raise RuntimeError(f"{preset}: proposed installed force exceeds catalog maximum")
    evidence.update(preset=preset, inside_length_mm=length,
                    force_n=force, seed=_pose_record(seed))
    variant = f"counter-spring-calib-clamp-{preset}-{refit}"
    evidence["native_variant"] = f"cad/out/sldprt/{variant}.SLDPRT"
    with _telemetry.span("clamp.build_native_counter", preset=preset, refit=refit):
        await _build_counter_variant(adapter, variant, length)
    titles = []
    fixture = None
    try:
        check("create native finite clamp fixture", await adapter.create_assembly())
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        roles = ["boss", "counter", "tube", "plug", "screw"]
        specifications = [
            {"part": "boss-hook", "position": [*mounts.COUNTER_ANCHOR_XY, SUMMING_Z],
             "rotation": [0.0, 0.0, 0.0], "rows": IDENTITY, "ground": True},
            {"part": variant, "position": [*seed.centre_xy, SUMMING_Z],
             "rotation": euler_from_rows(seed.rotation_rows), "rows": seed.rotation_rows, "ground": True},
        ]
        for role in roles[2:]:
            specifications.append({"part": ROLE_PARTS[role], "position": [mounts.COLUMN_X, 0.0, SUMMING_Z],
                                   "rotation": [0.0, 180.0, 0.0], "rows": ROT_Y_180, "ground": True})
        names = await place_components_batch(adapter, specifications, label=f"{preset} finite clamp fixture")
        titles = _owned_titles(adapter, model, names)
        fixture = Fixture(adapter, dict(zip(roles, names, strict=True)), evidence)
        landed = _plug_root(fixture, seed)
        gap = _close_screw(fixture)
        with _telemetry.span("clamp.certify_finite_contacts", preset=preset) as span:
            evidence["positive_controls"] = _positive_controls(fixture, gap)
            ux, uy = landed["pose"]["axis_xy"]
            lower_verify = solve_component_contact(adapter, fixture.names["counter"], fixture.names["boss"],
                                                   (-ux, -uy, 0.0), mounts.MIN_CLEARANCE_MM / 2.0,
                                                   label=f"{preset} final lower", locate_only=True)
            fixture.trials["seat_iterations"] += lower_verify.iterations
            if not _seated(f"{preset} final lower", lower_verify, fixture.allowance):
                raise RuntimeError("final lower hook is no longer seated")
            evidence["lower_verify"] = asdict(lower_verify)
            contacts = {role: fixture.require_contact(role) for role in ("plug", "head", "shank")}
            overlaps = {role: fixture.state(role) for role in ("boss", "tube", "plug", "screw")}
            if any(row["state"] != "clear" or row["volume_mm3"] != 0.0 for row in overlaps.values()):
                raise RuntimeError(f"final spring/anchor overlap is not measured zero: {overlaps!r}")
            # Intentionally DO NOT run all-component interference: screw/plug
            # threaded engagement is modeled as overlapping thread envelopes.
            evidence.update(final_contacts=contacts, final_native_overlap=overlaps,
                            final_component_transforms=fixture.expected,
                            measured_clamp_gap_mm=evidence["positive_controls"]["face_gap"]["closed"]["distance_mm"],
                            counts=fixture.trials)
            for key, value in fixture.trials.items():
                span.set_attribute(key, value)
            span.set_attribute("clamp_gap_mm", gap)
            actual = component_transform(adapter, fixture.names["counter"])
            if math.dist([x*1000 for x in actual[9:11]], landed["pose"]["centre_xy"]) > fixture.resolution:
                raise RuntimeError("reported counter pose differs from final native placement")
            eye_x = stock.end_centers_mm(length)[1][0]
            centre = tuple(value * 1000.0 for value in actual[9:11])
            axis = tuple(actual[:2])
            native_pose = mounts.SpringPose(
                length_mm=length,
                lower_eye_xy=tuple(centre[i] - axis[i] * eye_x for i in range(2)),
                upper_eye_xy=tuple(centre[i] + axis[i] * eye_x for i in range(2)),
                axis_xy=axis, centre_xy=centre, clocking=seed.clocking,
            )
            return {
                "pose": _pose_record(native_pose), "gooseneck_origin_y_mm": landed["gooseneck_origin_y_mm"],
                "upper_eye_x_mm": native_pose.upper_eye_xy[0],
                "clamp_gap_mm": evidence["measured_clamp_gap_mm"],
                "screw_axial_displacement_from_seed_mm": gap - SEED_GAP,
                "final_distance_mm": {"lower": lower_verify.seed_distance_mm,
                                      "upper": contacts["shank"]["distance_mm"],
                                      "plug_face": contacts["plug"]["distance_mm"],
                                      "under_head_face": contacts["head"]["distance_mm"]},
            }
    finally:
        if fixture is not None:
            evidence["counts"] = fixture.trials
        _close_all(adapter, titles)


def _required_length(pose_record, channel_moment):
    pose = mounts.SpringPose(**pose_record)
    arm = -pose.moment_arm_mm
    if not math.isfinite(arm) or arm <= 0.0:
        raise RuntimeError("measured counter pose cannot oppose the channel torque")
    force = channel_moment / arm
    if not mounts.COUNTER_INITIAL_TENSION_N <= force <= mounts.COUNTER_MAXIMUM_LOAD_N:
        raise RuntimeError(f"native pose requires non-catalog counter force {force!r}")
    length = stock.validate_length_mm(
        stock.FREE_LENGTH_MM
        + (force - mounts.COUNTER_INITIAL_TENSION_N) / mounts.COUNTER_RATE_N_PER_MM
    )
    return length, force, arm


async def _calibrate_preset(adapter, preset, table, evidence):
    amplitudes = [float(value) for value in table[preset]["amplitudes_mm"]]
    if not amplitudes or any(not math.isfinite(a) or a < 0.0 for a in amplitudes):
        raise ValueError(f"{preset}: invalid channel amplitudes")
    channel_moment = mounts.solve_bank_balance(amplitudes).channel_moment_n_mm
    if not math.isfinite(channel_moment) or channel_moment <= 0.0:
        raise RuntimeError(f"{preset}: channel torque must be positive and finite")
    length = stock.validate_length_mm(float(table[preset]["counter"]["pose"]["length_mm"]))
    evidence.update(seed_inside_length_mm=length, channel_moment_n_mm=channel_moment,
                    amplitudes_mm=amplitudes, refits=[], counts={})
    tolerance = _allowance_mm() / 2.0
    previous_required = None
    with _telemetry.span("clamp.refit_torque_equilibrium", preset=preset) as span:
        for index in range(8):
            iteration = {"refit_index": index}
            evidence["refits"].append(iteration)
            row = await _calibrate_length(adapter, preset, length, index, iteration)
            required, force, arm = _required_length(row["pose"], channel_moment)
            actual_force = mounts.counter_force_n(length)
            if actual_force > mounts.COUNTER_MAXIMUM_LOAD_N:
                raise RuntimeError(f"{preset}: installed force exceeds catalog maximum")
            residual = required - length
            endpoints = iteration["plug_bracket"]
            endpoint_lengths = [
                _required_length(endpoints[side]["pose"], channel_moment)[0]
                for side in ("overlap", "clear")
            ]
            balance = {
                "channel_moment_n_mm": channel_moment, "counter_moment_arm_mm": arm,
                "counter_force_n": actual_force, "required_counter_force_n": force,
                "required_inside_length_mm": required, "length_residual_mm": residual,
                "torque_residual_n_mm": channel_moment - actual_force * arm,
                "length_tolerance_mm": tolerance,
                "required_length_change_mm": None if previous_required is None else required - previous_required,
                "native_bracket_required_length_spread_mm": abs(endpoint_lengths[1] - endpoint_lengths[0]),
                "plug_bracket_width_mm": endpoints["width_mm"],
                "head_bracket_width_mm": iteration["head_bracket"]["width_mm"],
            }
            iteration["balance"] = balance
            for name, count in iteration["counts"].items():
                evidence["counts"][name] = evidence["counts"].get(name, 0) + count
            span.set_attribute("refit_count", index + 1)
            span.set_attribute("length_residual_mm", residual)
            span.set_attribute("torque_residual_n_mm", balance["torque_residual_n_mm"])
            if abs(residual) <= tolerance:
                evidence.update(refit_count=index + 1, final_balance=balance)
                row["balance"] = balance
                return row
            previous_required, length = required, required
    raise RuntimeError(f"{preset}: native pose/length torque refit did not converge in 8 iterations")


def _checkpoint(output, report):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(output)


async def calibrate(adapter, output):
    report = {
        "schema_version": 1, "status": "started", "presets": list(PRESETS), "completed_presets": [],
        "counters": {}, "evidence": {}, "source_bodies": {}, "copied_bodies": {},
        "provisional_seed_gap_mm": SEED_GAP, "open_installation_gap_mm": goose.SPRING_SCREW_OPEN_GAP_MM,
        "length_policy": "old length is seed only; refit native pose and catalog preload to channel torque",
        "contact_policy": "zero measured native spring overlap; finite face distances and native overlap/clear brackets",
        "boolean_stability_mm": _allowance_mm(),
        "intentional_overlap": "screw/plug thread envelopes; not spring interference",
        "temporary_solids": [f"cad/out/sldprt/{name}.SLDPRT" for name in ROLE_PARTS.values()],
    }
    _checkpoint(output, report)
    try:
        table = _config.machine("springs", "presets")
        await _extract_goose(adapter, report)
        _checkpoint(output, report)
        for preset in PRESETS:
            evidence = report["evidence"][preset] = {}
            with _telemetry.span("clamp.calibrate_preset", preset=preset):
                report["counters"][preset] = await _calibrate_preset(adapter, preset, table, evidence)
            report["completed_presets"].append(preset)
            _checkpoint(output, report)
        report["status"] = "completed"
        return {"report": str(output)}
    except BaseException:
        report["status"] = "failed"
        report["error"] = traceback.format_exc()
        raise
    finally:
        _checkpoint(output, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "cad/out/reports/summing-clamp-calibration.json")
    args = parser.parse_args()
    # _cached_com_action is the sole seat owner. No --write mode exists.
    return run_build(lambda adapter: calibrate(adapter, args.output.resolve()))


if __name__ == "__main__":
    raise SystemExit(main())
