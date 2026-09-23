"""EXPERIMENT ONLY: native finite-face counter-spring clamp calibration.

Run only through verify:calibrate_summing_clamp on the throwaway branch. The
parent owns the COM seat; this child never acquires it and never writes YAML.
On the submitter, ``--apply-report`` merges the completed preset reports' counter
seats into springs.yaml (no COM): with the eye bearing on the tube's OD corner,
X and Y are coupled, and only this fixture solves them together.
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
from _common import (  # noqa: E402
    SPRING_BLACK,
    _early_bound,
    apply_color,
    apply_material,
    check,
    force_rebuild,
    run_build,
    save_part_and_images,
)
from _cwm import put_component_pose  # noqa: E402
from _native_spring_contact import native_component_interference  # noqa: E402
from _stock_fastener import _blank_recipe_references  # noqa: E402
from _transforms import ROT_Y_180, euler_from_rows  # noqa: E402
from cone_pivot_post_installation import SUMMING_Z  # noqa: E402
from diagnostics._seat_search import solve_component_contact  # noqa: E402
from diagnostics.calibrate_spring_seats import (  # noqa: E402
    _allowance_mm,
    _close_active_part,
    _close_all,
    _owned_titles,
    _pose_record,
    _seated,
)
from diagnostics.diag_build_1330K524 import build_1330K524  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
PARTS = ROOT / "cad/out/sldprt"
PRESETS = ("neutral", "square")
IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
ROLE_PARTS = {role: f"summing-clamp-experiment-{role}" for role in ("tube", "plug", "screw")}
SEED_GAP = goose.SPRING_SCREW_CLAMPED_GAP_MM
HEAD_X = goose.ARM_END_X - SEED_GAP
# The arm end is the plug face AND the coplanar tube end face. The 1.75-turn eye
# is widest at radii beyond the plug, so it meets the tube rim first (r3: the
# plug-only root drove the eye 0.504 mm into the tube, 0.503 mm3).
ARM_END_FACES = ("plug", "tube")
FACE_BODY = {"plug": "plug", "tube": "tube", "head": "screw", "shank": "screw"}
# Identity tolerances, never contact/placement allowances.
IDENTITY_MM = 1e-5
IDENTITY_AREA_MM2 = 1e-4


async def _build_counter_variant(adapter, name: str, length_mm: float) -> None:
    check("create_part", await adapter.create_part())
    try:
        await build_1330K524(adapter, None, length_mm=length_mm)
    finally:
        if hasattr(adapter, "_mcm_com_map"):
            delattr(adapter, "_mcm_com_map")
    _blank_recipe_references(adapter)
    await force_rebuild(adapter)
    await apply_material(adapter, str(_config.parts("counter-spring")["material"]))
    await apply_color(adapter, SPRING_BLACK)
    await save_part_and_images(adapter, name, [])
    _close_active_part(adapter)


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


def _persist(model, entity, evidence):
    extension = _early_bound(model.Extension, "IModelDocExtension")
    reference = extension.GetPersistReference3(entity)
    evidence["raw_type"] = f"{type(reference).__module__}.{type(reference).__qualname__}"
    try:
        evidence["raw_length"] = len(reference)
    except TypeError:
        evidence["raw_length"] = None
    try:
        if reference is None or isinstance(reference, str):
            raise ValueError("reference is not a native byte sequence")
        # Match probe_face_identity's iterable-byte conversion: a native array
        # need not be one of a hardcoded set of Python container classes.
        encoded = bytes((int(value) & 0xFF) for value in reference)
        if not encoded:
            raise ValueError("reference byte sequence is empty")
    except (TypeError, ValueError, OverflowError) as exc:
        evidence["raw_repr"] = repr(reference)
        raise RuntimeError(f"native persistent identity unavailable: {evidence!r}") from exc
    evidence["byte_count"] = len(encoded)
    return encoded.hex()


def _face_identity(adapter, model, face, body, evidence):
    """Positive-control a face PID and prove its round-tripped native owner."""
    import pythoncom
    from win32com.client import VARIANT

    capture = evidence["capture"] = {}
    identity = _persist(model, face, capture)
    extension = _early_bound(model.Extension, "IModelDocExtension")
    # Explicit BYTE SAFEARRAY input; the ErrorCode OUT rides the return tuple.
    reference = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_UI1, bytes.fromhex(identity))
    answer = extension.GetObjectByPersistReference3(reference)
    evidence["roundtrip_return_type"] = type(answer).__name__
    if not isinstance(answer, (tuple, list)) or len(answer) != 2:
        raise RuntimeError(f"face PID roundtrip returned an invalid shape: {answer!r}")
    resolved, state = answer
    evidence["roundtrip_state"] = state
    if type(state) is not int or state != 0 or resolved is None:
        raise RuntimeError(f"face PID roundtrip failed: state={state!r}, object_missing={resolved is None}")
    resolved_face = _early_bound(resolved, "IFace2")
    app = _early_bound(adapter.swApp, "ISldWorks")
    same_face = app.IsSame(face, resolved_face)
    evidence["same_face"] = same_face
    if type(same_face) is not int or same_face != 1:  # swObjectSame
        raise RuntimeError(f"face PID resolved a different native face: {same_face!r}")
    owner = _early_bound(resolved_face.GetBody(), "IBody2")
    if owner is None or body is None:
        raise RuntimeError("face PID owner body is unavailable")
    same_body = app.IsSame(body, owner)
    evidence["same_owner_body"] = same_body
    evidence["owner_body_name"] = owner.Name
    if type(same_body) is not int or same_body != 1:
        raise RuntimeError(f"face PID resolved into a different native body: {same_body!r}")
    return identity


async def _extract_goose(adapter, report):
    """Copy the actual final three bodies; never redraw a head, slot or plug."""
    with _telemetry.span("clamp.extract_native_bodies"):
        check("open native gooseneck", await adapter.open_model(str(PARTS / "gooseneck.SLDPRT")))
        source = _early_bound(adapter.currentModel, "IModelDoc2")
        copied = {}
        identified = {}
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
                if role in identified:
                    raise RuntimeError(f"ambiguous native body role: {role}")
                face_role = "head" if role == "screw" else role
                face, face_row = _select_face(body, face_role)
                record = _body_record(body)
                record["contact_face"] = dict(face_row)
                report["source_bodies"][role] = record
                identified[role] = (body, face)
            if set(identified) != set(ROLE_PARTS):
                raise RuntimeError("native source role census incomplete")
            # Preserve the complete geometry census before any identity probe.
            # A face PID is the positive control; its proven native owner is
            # sufficient body identity. A body PID is diagnostic, not required.
            for role, (body, face) in identified.items():
                record = report["source_bodies"][role]
                control = record["face_identity_control"] = {}
                record["contact_face"]["persist_hex"] = _face_identity(
                    adapter, source, face, body, control
                )
                body_probe = record["body_pid_diagnostic"] = {}
                try:
                    body_probe["persist_hex"] = _persist(source, body, body_probe)
                except Exception as exc:
                    body_probe["error"] = repr(exc)
                if role == "screw":
                    _select_face(body, "shank")
                    lo, hi = _extreme_x(body, -1), _extreme_x(body, 1)
                    if abs(lo - (HEAD_X - goose.SCREW_HEAD_T)) > IDENTITY_MM:
                        raise RuntimeError("native screw head thickness/station mismatch")
                    if abs(hi - HEAD_X - 14.0) > IDENTITY_MM:
                        raise RuntimeError("native screw is not 14 mm underhead")
                    slot_floor = HEAD_X - goose.SCREW_HEAD_T + goose.SCREW_SLOT_DEPTH
                    if not any(_plane(row, slot_floor) for row in record["faces"]):
                        raise RuntimeError("actual native screw slot floor is missing")
                    record.update(extreme_x_mm=[lo, hi], underhead_length_mm=hi - HEAD_X,
                                  slot_floor_x_mm=slot_floor)
                copy = _early_bound(body.Copy(), "IBody2")
                if copy is None:
                    raise RuntimeError(f"{role}: native body copy failed")
                copied[role] = copy
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


def _world_point(local_mm, transform):
    return [
        sum(local_mm[j] * transform[3*j+i] for j in range(3)) + transform[9+i] * 1000.0
        for i in range(3)
    ]


def _local_point(world_mm, transform):
    delta = [world_mm[i] - transform[9+i] * 1000.0 for i in range(3)]
    return [sum(delta[i] * transform[3*j+i] for i in range(3)) for j in range(3)]


def _face_point(face, local_mm):
    # IFace2 (not ISurface): METHOD, three R8 inputs, VARIANT xyzuv result.
    point = _values(face.GetClosestPointOn(*(v / 1000.0 for v in local_mm)), 5, "finite face projection")
    return [v * 1000.0 for v in point[:3]]


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
        self.part_contexts = {}
        self.part_faces = {}
        self.witnesses = {}
        evidence["witness_sources"] = {}
        evidence["native_part_body_census"] = {}
        for body_role in ("counter", "plug", "tube", "screw"):
            document = _early_bound(self.component(body_role).GetModelDoc2(), "IModelDoc2")
            solids = _solids(document)
            if body_role != "counter" and len(solids) != 1:
                raise RuntimeError(f"{body_role}: copied fixture part needs one native solid")
            bodies = []
            census = evidence["native_part_body_census"][body_role] = []
            for index, body in enumerate(solids):
                face_rows = _face_rows(body)
                faces = [face for face, _ in face_rows]
                properties = _values(body.GetMassProperties(1.0), 12, "witness body mass")
                volume = properties[3]
                if volume <= 0.0:
                    raise RuntimeError(f"{body_role}: witness body has no positive native volume")
                bodies.append({"body": body, "index": index, "volume_si": volume, "faces": faces,
                               "mass_properties_si": properties,
                               "face_areas_mm2": [row["area_mm2"] for _, row in face_rows]})
                census.append({"index": index, "name": body.Name, "volume_mm3": volume * 1e9,
                               "face_count": len(faces), "mass_properties_si_density_1": properties})
            self.part_contexts[body_role] = {"document": document, "bodies": bodies}
        self.counter_faces = [
            face for body in self.part_contexts["counter"]["bodies"] for face in body["faces"]
        ]
        evidence["faces"] = {}
        for role, body_role in FACE_BODY.items():
            component = self.component(body_role)
            document = _early_bound(component.GetModelDoc2(), "IModelDoc2")
            if document is None:
                raise RuntimeError(f"{role}: fixture document unavailable")
            solids = _solids(document)
            if len(solids) != 1:
                raise RuntimeError(f"{role}: ambiguous fixture solid")
            face, row = _select_face(solids[0], role)
            self.part_faces[role] = face
            corresponding = _early_bound(component.GetCorrespondingEntity(face), "IFace2")
            if corresponding is None:
                raise RuntimeError(f"{role}: face did not map to assembly context")
            self.faces[role] = corresponding
            record = evidence["faces"][role] = {
                **row, "component": names[body_role], "body_name": solids[0].Name,
            }
            part_control = record["part_face_identity_control"] = {}
            record["part_face_persist_hex"] = _face_identity(
                adapter, document, face, solids[0], part_control
            )
            assembly_control = record["assembly_face_identity_control"] = {}
            assembly_body = _early_bound(corresponding.GetBody(), "IBody2")
            record["assembly_face_persist_hex"] = _face_identity(
                adapter, self.model, corresponding, assembly_body, assembly_control
            )
        evidence["finite_trim_controls"] = self._trim_controls()

    def _trim_controls(self):
        controls = {}
        for role, local_x, inner, outer in (
            ("plug", goose.ARM_END_X, goose.SCREW_TAP_MINOR_DIA / 2.0, goose.PLUG_DIA / 2.0),
            ("tube", goose.ARM_END_X, goose.TUBE_DIA / 2.0 - goose.WALL_T, goose.TUBE_DIA / 2.0),
            ("head", HEAD_X, goose.SCREW_THREAD_MAJOR_DIA / 2.0, goose.SCREW_HEAD_DIA / 2.0),
        ):
            rows = {}
            for name, radius, expected in (("hole", 0.0, inner), ("outside", outer + 1.0, outer)):
                input_point = [local_x, goose.ARM_Y + radius, 0.0]
                point = _face_point(self.part_faces[role], input_point)
                measured = math.hypot(point[1] - goose.ARM_Y, point[2])
                if abs(point[0] - local_x) > IDENTITY_MM or abs(measured - expected) > IDENTITY_MM:
                    raise RuntimeError(f"{role}: IFace2 projection did not respect annulus {name} trim: {point!r}")
                rows[name] = {"input_local_mm": input_point, "point_local_mm": point,
                              "expected_radius_mm": expected, "measured_radius_mm": measured}
            controls[role] = rows
        return controls

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

    def _witness_poses(self, role):
        self.assert_poses()
        body_role = FACE_BODY[role]
        # Read the native transforms, not the requested placement dictionary.
        return {name: component_transform(self.adapter, self.names[name]) for name in (body_role, "counter")}

    def _record_invariance(self, kind, body_role, baseline, current, relative, proof_keys):
        """Record, never refuse: these kernel re-evaluation differences are
        diagnostics only (see commit body for the measured magnitude)."""
        bucket = self.evidence.setdefault("invariance_observations", {}).setdefault(kind, {
            "samples": 0,
            "max_abs_delta": 0.0,
            "max_relative_delta": 0.0,
            "worst": None,
            "units": {"body_volume": "mm3", "face_area": "mm2"}[kind],
        })
        delta = current - baseline
        bucket["samples"] += 1
        bucket["max_abs_delta"] = max(bucket["max_abs_delta"], abs(delta))
        if bucket["worst"] is None or abs(relative) > bucket["max_relative_delta"]:
            bucket["worst"] = {
                "body_role": body_role,
                **proof_keys,
                "baseline": baseline,
                "current": current,
                "delta": delta,
                "relative_delta": relative,
            }
        bucket["max_relative_delta"] = max(bucket["max_relative_delta"], abs(relative))

    def _geometry_diagnostic(self, body_role, face, body, properties, source_proof, stage, triggering_proof=None):
        """Record native observations before refusal; never repair or re-pose."""
        baseline = body["mass_properties_si"]
        record = {
            "stage": stage, "body_role": body_role, "component": self.names[body_role],
            "api_context": "part IComponent2.GetModelDoc2/IPartDoc.GetBodies2; current IFace2.GetBody",
            "owner_body_index": body["index"], "relative_guard": 1e-12, "absolute_guard": 0.0,
            "baseline_mass_properties_si_density_1": baseline,
            "failing_mass_properties_si_density_1": properties,
            "baseline_volume_mm3": baseline[3] * 1e9, "failing_volume_mm3": properties[3] * 1e9,
            "volume_delta_mm3": (properties[3] - baseline[3]) * 1e9,
            "volume_relative_delta": (properties[3] - baseline[3]) / baseline[3],
            "source_face_proof": source_proof,
            "triggering_current_face_proof": triggering_proof,
        }
        self.evidence.setdefault("local_geometry_guard_diagnostics", []).append(record)

        def capture(key, operation):
            try:
                record[key] = operation()
            except Exception as exc:
                record[key] = {"diagnostic_error": repr(exc)}

        app = _early_bound(self.adapter.swApp, "ISldWorks")
        context = self.part_contexts[body_role]
        owner = _early_bound(face.GetBody(), "IBody2")
        capture("actual_component_transforms", lambda: {
            name: component_transform(self.adapter, component) for name, component in self.names.items()
        })
        capture("same_census_owner", lambda: app.IsSame(body["body"], owner))
        capture("repeated_owner_mass_properties_si_density_1", lambda: [
            _values(owner.GetMassProperties(1.0), 12, "repeated owner mass") for _ in range(3)
        ])
        capture("census_object_mass_properties_si_density_1", lambda: [
            _values(body["body"].GetMassProperties(1.0), 12, "census body mass") for _ in range(3)
        ])

        def areas():
            same = [app.IsSame(candidate, face) for candidate in body["faces"]]
            values = [float(face.GetArea()) * 1e6 for _ in range(3)]
            return {
                "same_census_faces": same, "current_area_mm2_repeated": values,
                "baseline_area_mm2_matches": [
                    area for state, area in zip(same, body["face_areas_mm2"], strict=True)
                    if type(state) is int and state == 1
                ],
                "source_area_mm2": None if source_proof is None else source_proof["area_mm2"],
                "delta_from_source_mm2": None if source_proof is None else values[0] - source_proof["area_mm2"],
            }
        capture("face_area", areas)

        def part_identity():
            proof = {}
            proof["persist_hex"] = _face_identity(self.adapter, context["document"], face, owner, proof)
            return proof
        capture("current_part_face_identity", part_identity)
        capture("fresh_part_body_census", lambda: [
            {"index": index, "name": candidate.Name, "same_as_owner": app.IsSame(candidate, owner),
             "mass_properties_si_density_1": _values(candidate.GetMassProperties(1.0), 12, "fresh part mass")}
            for index, candidate in enumerate(_solids(context["document"]))
        ])

        def assembly_context():
            mapped = _early_bound(self.component(body_role).GetCorrespondingEntity(face), "IFace2")
            if mapped is None:
                raise RuntimeError("diagnostic face did not map to assembly context")
            mapped_owner = _early_bound(mapped.GetBody(), "IBody2")
            if mapped_owner is None:
                raise RuntimeError("diagnostic assembly face has no owner")
            row = {"api_context": "IComponent2.GetCorrespondingEntity(IFace2).GetBody",
                   "same_as_part_owner": app.IsSame(mapped_owner, owner),
                   "mass_properties_si_density_1_repeated": [
                       _values(mapped_owner.GetMassProperties(1.0), 12, "assembly owner mass") for _ in range(3)
                   ],
                   "face_area_mm2_repeated": [float(mapped.GetArea()) * 1e6 for _ in range(3)]}
            identity = row["identity"] = {}
            row["persist_hex"] = _face_identity(self.adapter, self.model, mapped, mapped_owner, identity)
            return row
        capture("mapped_assembly_context", assembly_context)

    def _face_proof(self, body_role, face):
        context = self.part_contexts[body_role]
        owner = _early_bound(face.GetBody(), "IBody2")
        if owner is None:
            raise RuntimeError(f"{body_role}: witness face has no native owner")
        app = _early_bound(self.adapter.swApp, "ISldWorks")
        matches = []
        for candidate in context["bodies"]:
            same = app.IsSame(candidate["body"], owner)
            if type(same) is not int or same not in (0, 1):
                raise RuntimeError(f"{body_role}: native body-census identity is undetermined: {same!r}")
            if same == 1:
                matches.append(candidate)
        if len(matches) != 1:
            raise RuntimeError(f"{body_role}: witness owner must match exactly one native body-census member")
        body = matches[0]
        properties = _values(owner.GetMassProperties(1.0), 12, "witness owner mass")
        volume = properties[3]
        proof = {"owner_body_index": body["index"], "owner_census_count": len(context["bodies"])}
        proof["persist_hex"] = _face_identity(
            self.adapter, context["document"], face, body["body"], proof
        )
        proof["area_mm2"] = float(face.GetArea()) * 1e6
        proof["body_volume_si"] = volume
        proof["body_mass_properties_si_density_1"] = properties
        proof["baseline_body_volume_si"] = body["volume_si"]
        proof["body_volume_delta_si"] = volume - body["volume_si"]
        proof["body_volume_relative_delta"] = (volume - body["volume_si"]) / body["volume_si"]
        self._record_invariance(
            "body_volume", body_role, body["volume_si"], volume,
            proof["body_volume_relative_delta"],
            {"component": self.names[body_role], "owner_body_index": body["index"],
             "persist_hex": proof["persist_hex"]},
        )
        return proof

    def _on_face(self, face, point):
        projected = _face_point(face, point)
        repeated = _face_point(face, projected)
        if math.dist(projected, repeated) > self.resolution:
            raise RuntimeError("native finite-face projection failed membership roundtrip")
        return projected

    def _raw_witness(self, role, raw, poses):
        body_role = FACE_BODY[role]
        clamp_face = self.part_faces[role]
        # Native Measure may return the cylinder axis: follow the documented
        # face-distance example and project the OTHER entity's point instead.
        clamp_seed = raw["point2_mm"] if role == "shank" else raw["point1_mm"]
        clamp_point = self._on_face(clamp_face, _local_point(clamp_seed, poses[body_role]))
        source = _local_point(raw["point2_mm"], poses["counter"])
        candidates = [(math.dist(point, source), face, point) for face in self.counter_faces
                      for point in [_face_point(face, source)]]
        _, spring_face, spring_point = min(candidates, key=lambda value: value[0])
        spring_point = self._on_face(spring_face, spring_point)
        return {
            "faces": (clamp_face, spring_face), "local_points_mm": (clamp_point, spring_point),
            "owner_bodies": tuple(_early_bound(face.GetBody(), "IBody2") for face in (clamp_face, spring_face)),
            "proofs": (self._face_proof(body_role, clamp_face), self._face_proof("counter", spring_face)),
            "source_actual_transforms": poses, "source_raw_distance": raw,
        }

    def _transport_witness(self, role, witness, poses):
        body_role = FACE_BODY[role]
        points, proofs, changes = [], [], []
        for name, face, owner, local, original in zip(
            (body_role, "counter"), witness["faces"], witness["owner_bodies"],
            witness["local_points_mm"], witness["proofs"], strict=True
        ):
            proof = self._face_proof(name, face)
            same_owner = _early_bound(self.adapter.swApp, "ISldWorks").IsSame(
                owner, _early_bound(face.GetBody(), "IBody2")
            )
            if type(same_owner) is not int or same_owner != 1:
                raise RuntimeError(f"{role}: transported witness changed its original native owner")
            proof["same_source_owner_body"] = same_owner
            proof["source_area_mm2"] = original["area_mm2"]
            proof["area_delta_mm2"] = proof["area_mm2"] - original["area_mm2"]
            proof["area_relative_delta"] = (proof["area_mm2"] - original["area_mm2"]) / original["area_mm2"]
            self._record_invariance(
                "face_area", name, original["area_mm2"], proof["area_mm2"],
                proof["area_relative_delta"],
                {"component": self.names[name], "owner_body_index": proof["owner_body_index"],
                 "persist_hex": proof["persist_hex"]},
            )
            if proof["persist_hex"] != original["persist_hex"]:
                body = self.part_contexts[name]["bodies"][proof["owner_body_index"]]
                self._geometry_diagnostic(
                    name, face, body, proof["body_mass_properties_si_density_1"], original,
                    "face_identity_or_area_invariance", triggering_proof=proof,
                )
                raise RuntimeError(f"{role}: native witness face identity invariance guard failed")
            projected = self._on_face(face, local)
            if math.dist(projected, local) > self.resolution:
                raise RuntimeError(f"{role}: transported local witness lost native finite-face membership")
            points.append(_world_point(projected, poses[name]))
            proofs.append(proof)
            changes.append(math.dist(projected, local))
        self.assert_poses()
        return {
            "distance_mm": math.dist(*points), "point1_mm": points[0], "point2_mm": points[1],
            "distance_kind": "native_finite_witness_upper_bound",
            "actual_component_transforms": poses, "face_proofs": proofs,
            "reprojection_change_mm": changes,
        }

    def face_distance(self, role, *, certify=False):
        raw = self.distance(self.faces[role], self.component("counter"))
        body_role = FACE_BODY[role]
        poses = self._witness_poses(role)
        if role != "shank":
            local_x = goose.ARM_END_X if role in ARM_END_FACES else HEAD_X
            world_x = poses[body_role][9] * 1000.0 - local_x
            if abs(raw["point1_mm"][0] - world_x) > self.guard:
                raise RuntimeError(f"{role}: closest point is not on the transformed clamp face")
        previous = self.witnesses.get(role)
        candidates = []
        if previous is not None:
            candidates.append((self._transport_witness(role, previous, poses), previous))
        if certify or raw["distance_mm"] <= self.distance_limit:
            source = self._raw_witness(role, raw, poses)
            candidates.append((self._transport_witness(role, source, poses), source))
        if not candidates:
            return {**raw, "distance_kind": "raw_closest_distance"}
        result, chosen = min(candidates, key=lambda value: value[0]["distance_mm"])
        if chosen is not previous and result["distance_mm"] <= self.distance_limit:
            record = {key: value for key, value in chosen.items() if key not in ("faces", "owner_bodies")}
            sources = self.evidence["witness_sources"].setdefault(role, [])
            chosen["source_index"] = len(sources)
            record["source_index"] = chosen["source_index"]
            sources.append(record)
            self.witnesses[role] = chosen
        result["source_index"] = chosen.get("source_index")
        result["raw_closest_distance"] = raw
        discrepancy = raw["distance_mm"] - result["distance_mm"]
        if discrepancy > self.guard:
            _telemetry.warn(
                f"{role}: ClosestDistance exceeds certified native finite witness upper bound",
                raw_distance_mm=raw["distance_mm"], witness_upper_bound_mm=result["distance_mm"],
                discrepancy_mm=discrepancy,
            )
        return result

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
        result = self.face_distance(role, certify=True)
        if result["distance_mm"] > self.distance_limit:
            raise RuntimeError(f"{role}: finite face not in contact ({result!r}); a shank/body contact is insufficient")
        body_role = FACE_BODY[role]
        native = self.state(body_role)
        if native["state"] != "clear" or native["volume_mm3"] != 0.0:
            raise RuntimeError(f"{role}: finite witness has nonzero or uncertified native overlap: {native!r}")
        result["native_overlap"] = native
        return result

    def arm_end_state(self):
        """The arm end is one clamp surface: interfering if EITHER body is."""
        rows = {role: self.state(role) for role in ARM_END_FACES}
        state = "interfering" if any(row["state"] != "clear" for row in rows.values()) else "clear"
        return {"state": state, **rows}

    def arm_end_contact(self):
        """Certify the arm-end face(s) the eye bears on; the rest must be clear."""
        faces = {role: self.face_distance(role, certify=True) for role in ARM_END_FACES}
        rooting = [role for role, row in faces.items() if row["distance_mm"] <= self.distance_limit]
        if not rooting:
            raise RuntimeError(f"no arm-end face in contact: {faces!r}")
        contacts = {role: self.require_contact(role) for role in rooting}
        return {"rooting_faces": rooting, "faces": faces, "contacts": contacts}

    def all_clear(self, label):
        """Every clamp body natively clear of the spring, not only the one rooted."""
        rows = {role: self.state(role) for role in ("boss", *ARM_END_FACES, "screw")}
        if any(row["state"] != "clear" or row["volume_mm3"] != 0.0 for row in rows.values()):
            raise RuntimeError(f"{label}: spring overlaps a clamp body: {rows!r}")
        return rows


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
    open_head_raw = open_head.get("raw_closest_distance", open_head)
    if min(open_head["distance_mm"], open_head_raw["distance_mm"]) <= fixture.distance_limit:
        raise RuntimeError("8 mm installation position does not leave the finite head clear")
    state = fixture.arm_end_state()
    result = {"parameter_mm": travel, "state": state["state"], "native": state,
              "pose": _pose_record(pose), "gooseneck_origin_y_mm": y,
              "lower": lower, "upper": upper, "shank": shank, "open_head": open_head}
    if state["state"] == "clear":
        result["arm_end_faces"] = {role: fixture.face_distance(role) for role in ARM_END_FACES}
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


def _arm_end_root(fixture, seed):
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
                fixture.evidence["arm_end_bracket"] = bracket
                landed = evaluate(bracket["clear"]["parameter_mm"] + fixture.allowance)
                if landed["state"] != "clear":
                    raise RuntimeError("arm-end boundary landing is not natively clear")
                landed["arm_end_contact"] = fixture.arm_end_contact()
                landed["all_bodies"] = fixture.all_clear("arm-end landing")
                fixture.evidence["arm_end_landed"] = landed
                return landed
            previous = trial
        raise RuntimeError("finite arm-end contact not bracketed within +/-4 mm upper-eye arc")


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
                landed["all_bodies"] = fixture.all_clear("screw closure landing")
                return gap
            previous = trial
        raise RuntimeError("native under-head contact not bracketed between 8 and 0 mm gap")


# A face-normal contact opens by the full withdrawal: keep 0.04 of 0.05 mm.
FACE_NORMAL_WITHDRAWAL_FLOOR_MM = 0.04
FACE_NORMAL_WITHDRAWAL_MM = (0.05,)
# The arm end can bear on a CORNER (r4: the eye wire wraps the tube's OD edge),
# where an axial withdrawal opens only by |n_x| of it. Prove separation without
# assuming the contact normal: clear, past the contact limit, strictly opening.
EDGE_WITHDRAWAL_MM = (0.05, 0.10)


def _withdrawal_refusal(face_role, withdrawals, distance_limit):
    """Why a finite-face withdrawal failed to prove separation, or None."""
    for row in withdrawals:
        if row["native"]["state"] != "clear" or row["native"]["volume_mm3"] != 0.0:
            return f"native overlap after {row['withdrawn_mm']} mm withdrawal"
    # An upper bound alone cannot prove separation: take the smaller of the
    # certified witness and the independent raw distance channel.
    opened = [min(row["distance"]["distance_mm"], row["distance"]["raw_closest_distance"]["distance_mm"])
              for row in withdrawals]
    if face_role not in ARM_END_FACES:
        if min(opened) < FACE_NORMAL_WITHDRAWAL_FLOOR_MM:
            return f"face-normal withdrawal opened only {opened!r} mm"
        return None
    if opened[0] <= distance_limit:
        return f"withdrawal did not leave the contact limit: {opened!r} mm"
    if any(later <= earlier for earlier, later in zip(opened, opened[1:])):
        return f"withdrawal distance did not strictly increase: {opened!r} mm"
    return None


def _positive_controls(fixture, final_gap, rooting_faces):
    """Exercise the finite-face channels independently of shank bearing."""
    # Held in the evidence while it fills, so a refused control still reports
    # what it measured in the failed report.
    controls = fixture.evidence["positive_controls"] = {}
    original = {key: list(value) for key, value in fixture.expected.items()}
    arm_end = [(role, FACE_BODY[role], -1.0) for role in rooting_faces]
    try:
        for face_role, body_role, direction in (("head", "screw", 1.0), *arm_end):
            row = controls[face_role] = {"contact": fixture.require_contact(face_role), "withdrawals": []}
            steps = EDGE_WITHDRAWAL_MM if face_role in ARM_END_FACES else FACE_NORMAL_WITHDRAWAL_MM
            for amount in steps:
                fixture.put(original)
                fixture.shift(body_role, (direction, 0.0, 0.0), amount)
                row["withdrawals"].append({
                    "withdrawn_mm": amount,
                    "distance": fixture.face_distance(face_role, certify=True),
                    "native": fixture.state(body_role),
                })
            refusal = _withdrawal_refusal(face_role, row["withdrawals"], fixture.distance_limit)
            if refusal is not None:
                raise RuntimeError(f"{face_role}: finite-face withdrawal positive control failed: {refusal}")
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
        landed = _arm_end_root(fixture, seed)
        gap = _close_screw(fixture)
        with _telemetry.span("clamp.certify_finite_contacts", preset=preset) as span:
            rooting = landed["arm_end_contact"]["rooting_faces"]
            evidence["positive_controls"] = _positive_controls(fixture, gap, rooting)
            ux, uy = landed["pose"]["axis_xy"]
            lower_verify = solve_component_contact(adapter, fixture.names["counter"], fixture.names["boss"],
                                                   (-ux, -uy, 0.0), mounts.MIN_CLEARANCE_MM / 2.0,
                                                   label=f"{preset} final lower", locate_only=True)
            fixture.trials["seat_iterations"] += lower_verify.iterations
            if not _seated(f"{preset} final lower", lower_verify, fixture.allowance):
                raise RuntimeError("final lower hook is no longer seated")
            evidence["lower_verify"] = asdict(lower_verify)
            contacts = {role: fixture.require_contact(role) for role in (*rooting, "head", "shank")}
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
                "eye_centre_from_arm_end_mm": native_pose.upper_eye_xy[0] - mounts.GOOSENECK_END_X,
                "arm_end_rooting_faces": rooting,
                "clamp_gap_mm": evidence["measured_clamp_gap_mm"],
                "screw_axial_displacement_from_seed_mm": gap - SEED_GAP,
                "final_distance_mm": {"lower": lower_verify.seed_distance_mm,
                                      "upper": contacts["shank"]["distance_mm"],
                                      **{f"{role}_face": contacts[role]["distance_mm"] for role in rooting},
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
            endpoints = iteration["arm_end_bracket"]
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
                "arm_end_bracket_width_mm": endpoints["width_mm"],
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


async def calibrate(adapter, preset, output):
    if preset not in PRESETS:
        raise ValueError(f"unsupported clamp calibration preset: {preset!r}")
    report = {
        "schema_version": 1, "status": "started", "presets": [preset], "completed_presets": [],
        "counters": {}, "evidence": {}, "source_bodies": {}, "copied_bodies": {},
        "provisional_seed_gap_mm": SEED_GAP, "open_installation_gap_mm": goose.SPRING_SCREW_OPEN_GAP_MM,
        "length_policy": "old length is seed only; refit native pose and catalog preload to channel torque",
        "contact_policy": "zero measured native spring overlap; finite face distances and native overlap/clear brackets",
        "boolean_stability_mm": _allowance_mm(),
        "intentional_overlap": "screw/plug thread envelopes; not spring interference",
        "temporary_solids": [f"cad/out/sldprt/{name}.SLDPRT" for name in ROLE_PARTS.values()],
    }
    _checkpoint(output, report)
    failure = None
    try:
        table = _config.machine("springs", "presets")
        await _extract_goose(adapter, report)
        _checkpoint(output, report)
        evidence = report["evidence"][preset] = {}
        with _telemetry.span("clamp.calibrate_preset", preset=preset):
            report["counters"][preset] = await _calibrate_preset(adapter, preset, table, evidence)
        report["completed_presets"].append(preset)
        _checkpoint(output, report)
        report["status"] = "completed"
        return {"report": str(output)}
    except BaseException as exc:
        failure = exc
        report["status"] = "failed"
        report["error"] = traceback.format_exc()
        # Failed declared outputs are not published to the success cache. Put
        # the complete census/brackets in immutable task.log once, not per trial.
        try:
            _telemetry.error(
                "CLAMP_CALIBRATION_FAILED_REPORT_JSON "
                + json.dumps(report, allow_nan=False)
            )
        except BaseException as logging_failure:
            exc.add_note(f"failed to log calibration report: {logging_failure!r}")
        raise
    finally:
        try:
            _checkpoint(output, report)
        except BaseException as checkpoint_failure:
            if failure is None:
                raise
            failure.add_note(f"failed to checkpoint calibration report: {checkpoint_failure!r}")


COUNTER_EYE_TOLERANCE_MM = 1e-4  # presets vs committed gooseneck_geom (r5 spread 4e-5)


def apply_reports(paths):
    """Merge completed clamp reports' counter seats into springs.yaml.

    The seat fixture lowers the gooseneck in Y alone, but the calibrated eye's X
    is held by the tube's OD corner, which moves with Y (spring-seats-r4 found
    the separating end of its bracket interfering). Each counter row here was
    certified on the lower hook, shank, arm end, under-head face and zero
    overlap on every clamp body, at a torque-refit length. Channel seats are
    untouched: they do not depend on the gooseneck."""
    import yaml

    from diagnostics.calibrate_spring_seats import SPRINGS_YAML

    rows = {}
    for path in paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("status") != "completed":
            raise SystemExit(f"--apply-report merges completed reports only; {path} is {report.get('status')!r}")
        for preset, row in report["counters"].items():
            if preset in rows:
                raise SystemExit(f"--apply-report: preset {preset!r} appears in more than one report")
            error = row["pose"]["upper_eye_xy"][0] - mounts.COUNTER_UPPER_EYE_X
            if abs(error) > COUNTER_EYE_TOLERANCE_MM:
                raise SystemExit(
                    f"--apply-report: {preset} upper eye is {error:+.6f} mm off the committed "
                    "gooseneck_geom eye centre; calibrate against the committed geometry first"
                )
            rows[preset] = {
                "pose": row["pose"],
                "gooseneck_origin_y_mm": row["gooseneck_origin_y_mm"],
                "final_distance_mm": {key: row["final_distance_mm"][key] for key in ("lower", "upper")},
            }
    missing = sorted(set(_config.machine("springs", "presets")) - set(rows))
    if missing:
        raise SystemExit(f"--apply-report must cover every configured preset; missing {missing}")
    text = SPRINGS_YAML.read_text(encoding="utf-8")
    document = yaml.safe_load(text)
    for preset, row in rows.items():
        document["springs"]["presets"][preset]["counter"] = row
    header = "\n".join(line for line in text.splitlines() if line.startswith("#"))
    body = yaml.safe_dump(document, sort_keys=False, allow_unicode=False, width=88)
    SPRINGS_YAML.write_text(header + "\n" + body, encoding="utf-8", newline="\n")
    print(f"--apply-report wrote {SPRINGS_YAML} counters {sorted(rows)}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=PRESETS)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--apply-report", type=Path, nargs="+",
                        help="merge completed preset reports' counter seats into springs.yaml; no COM")
    args = parser.parse_args()
    if args.apply_report:
        if args.preset or args.output:
            parser.error("--apply-report merges existing reports; --preset/--output are COM-run flags")
        return apply_reports([path.resolve() for path in args.apply_report])
    if args.preset is None:
        parser.error("--preset is required for a calibration run")
    output = args.output or ROOT / f"cad/out/reports/summing-clamp-calibration-{args.preset}.json"
    # _cached_com_action is the sole seat owner. No --write mode exists.
    return run_build(lambda adapter: calibrate(adapter, args.preset, output.resolve()))


if __name__ == "__main__":
    raise SystemExit(main())
