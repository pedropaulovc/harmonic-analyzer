r"""Fast inner-loop rig: prove ONE channel's motion linkage before scaling to
20 + integrating the whole device. Opens in seconds (a handful of parts) vs the
~5 min full-assembly load, so the joint recipe can be iterated quickly.

Artifact A pins each moving part to ground as a static POSE (the real
rod<->rocker + rod<->cam revolutes are deferred to the motion study -- see
build_channel_assembly._pin_design_pose). This rig builds the REAL linkage from
scratch at one channel's design pose and drives it from the cam:

    cam (cylinder-gear, motor on its bore; eccentric lobe orbits)
      -> concentric(rod ring bore <-> cam lobe OD)         [cam drives rod]
      -> coincident(rod pin axis <-> rocker rod-bore axis) [rod drives rocker]
      -> rocker rocks about the pivot-shaft
      -> tangent(rocker R800 arc <-> bar foot notch)        [amplitude tap]
      -> bar drives the lever via coincident(lever bar-pin <-> bar top-pin)
      -> channel-lever rocks about the fulcrum-shaft.

Stages (arg, default ``rod``):
    rod    -> cam + rod + rocker only (concentric chain; the reliable core)
    full   -> + bar + lever (adds the tangent amplitude tap)

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_one_channel_motion.py [stage]
"""

from __future__ import annotations

import math
import sys

from build_channel_assembly import (
    ARM_MID_DZ, ARM_PIVOT_LOCAL_Y, CAM_DZ, PIVOT,
    RING_CENTER, SHAFT_R, rot_z_rows, solve_default_state,
    z_station,
)
from _common import (
    _flag,
    _read_member,
    check,
    log,
    run_build,
)
from _assembly import (
    bore_axis_ref,
    coincident_mate,
    concentric_mate,
    named_ref,
    place_component,
)

# drive-train cam (build_drive_train_assembly / build_cylinder_gear)
X_DRUM, Y_DRIVE, Z_DRUM0, Z_PITCH = -47.5, 126.8, -67.1, 7.0568
DRUM_FACE = 3.0
GEAR_PHASE_DEG = 1.5
CAM_R = 25.4  # cam lobe OD radius (Ø50.8)

CAM_RPM = 30.0
DURATION_S = 4.0


def _comp_xform(adapter, comp):
    t = _read_member(comp, "Transform2")
    return [float(v) for v in _read_member(t, "ArrayData")]


def _rot_angle(a0, a1):
    def cols(a):
        return ((a[0], a[1], a[2]), (a[3], a[4], a[5]), (a[6], a[7], a[8]))
    c0, c1 = cols(a0), cols(a1)
    tr = sum(c1[k][i] * c0[k][i] for k in range(3) for i in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (tr - 1.0) / 2.0))))


def _find(adapter, needle):
    for c in (adapter._attempt(lambda: adapter.currentModel.GetComponents(False),
                               default=None) or []):
        _flag(c, "IComponent2")
        if needle in str(_read_member(c, "Name2")):
            return c, str(_read_member(c, "Name2"))
    return None, None


def _cyl_face(adapter, comp, target_r_mm):
    """GetCorrespondingEntity for the cylindrical face nearest TARGET_R_MM."""
    part = adapter._attempt(lambda: comp.GetModelDoc2(), default=None)
    bodies = adapter._attempt(lambda: part.GetBodies2(0, False), default=None)
    if bodies is None:
        return None
    if not isinstance(bodies, (list, tuple)):
        bodies = [bodies]
    best = None
    for body in bodies:
        if body is None:
            continue
        _flag(body, "IBody2")
        face = adapter._attempt(lambda b=body: b.GetFirstFace(), default=None)
        for _ in range(200000):
            if not face:
                break
            _flag(face, "IFace2")
            surf = adapter._attempt(lambda f=face: f.GetSurface(), default=None)
            if surf is not None:
                _flag(surf, "ISurface")
                if bool(adapter._attempt(lambda s=surf: s.IsCylinder(), default=False)):
                    p = adapter._attempt(lambda s=surf: s.CylinderParams, default=None)
                    if p is not None:
                        r = float(p[6]) * 1000.0
                        key = abs(r - target_r_mm)
                        if best is None or key < best[0]:
                            best = (key, r, face)
            face = adapter._attempt(lambda f=face: f.GetNextFace(), default=None)
    if best is None:
        return None
    log(f"    cyl face r={best[1]:.2f}mm (target {target_r_mm})")
    return adapter._attempt(lambda: comp.GetCorrespondingEntity(best[2]), default=None)


async def _concentric_faces(adapter, face_a, face_b, label):
    from solidworks_mcp.adapters.base import AddMateParameters
    adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))
    ok_a = bool(adapter._attempt(lambda: face_a.Select4(True, None), default=False))
    ok_b = bool(adapter._attempt(lambda: face_b.Select4(True, None), default=False))
    res = await adapter.add_mate(AddMateParameters(
        mate_type="concentric", entities=[], alignment="closest"))
    adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))
    log(f"  {label}: select=({ok_a},{ok_b}) -> {res.is_success} "
        f"{'' if res.is_success else res.error}")
    return res


async def build(adapter):
    from solidworks_mcp.adapters.base import (
        MateEntityRef, MotionMotorParameters,
        MotionStudyParameters, MotionStudyRefParameters, MotionTimeParameters,
    )
    stage = sys.argv[1] if len(sys.argv) > 1 else "rod"
    log(f"stage={stage}")
    state = solve_default_state()
    j = 0
    zj = z_station(j)
    z_mid = zj + ARM_MID_DZ
    t = math.radians(state["arm_tilt"])
    arm_dx = ARM_PIVOT_LOCAL_Y * math.sin(t)
    arm_dy = ARM_PIVOT_LOCAL_Y * math.cos(t)

    check("create_assembly", await adapter.create_assembly())

    # Fixed structure: pivot-shaft, fulcrum-shaft, and the cam (cylinder-gear)
    # whose bore is pinned by a concentric to an assembly axis so only its spin
    # is free for the motor.
    pivot = await place_component(
        adapter, "pivot-shaft", [PIVOT[0], PIVOT[1], 0.0], [0, 0, 0],
        [[1, 0, 0], [0, 1, 0], [0, 0, 1]], label="pivot-shaft")
    cam = await place_component(
        adapter, "cylinder-gear",
        [X_DRUM, Y_DRIVE, zj - DRUM_FACE / 2.0], [0, 0, GEAR_PHASE_DEG],
        rot_z_rows(GEAR_PHASE_DEG), ground=False, label="cam (cylinder-gear)")
    rod = await place_component(
        adapter, "connecting-rod", [RING_CENTER[0], RING_CENTER[1], zj + CAM_DZ],
        [0, 0, state["rod_tilt"]], rot_z_rows(state["rod_tilt"]),
        ground=False, label="connecting-rod")
    rocker = await place_component(
        adapter, "rocker-arm",
        [PIVOT[0] + arm_dx, PIVOT[1] - arm_dy, z_mid],
        [0, 0, state["arm_tilt"]], rot_z_rows(state["arm_tilt"]),
        ground=False, label="rocker-arm")

    asm = adapter.currentModel
    pivot_w = (-PIVOT[0], PIVOT[1])
    pivot_od = [pivot_w[0] + SHAFT_R, pivot_w[1], 0.0]

    # cam: pin its bore to an assembly axis at the (mirrored) cam centre +
    # a Z plane, so only its spin is free for the motor.
    from _common import name_bore_axis
    cam_world_x = -X_DRUM  # mirrored
    axis_name = await name_bore_axis(
        adapter, "Right Plane", cam_world_x, "Top Plane", Y_DRIVE, "cam axis")
    await coincident_mate(
        adapter, named_ref(axis_name, "AXIS"), named_ref(f"Axis2@{cam}", "AXIS"),
        label="cam bore <-> assembly axis")
    await coincident_mate(
        adapter, named_ref("Front Plane", "PLANE"),
        named_ref(f"Front Plane@{cam}", "PLANE"),
        label="cam Z plane", verify=None)

    # rocker revolute: pivot-shaft OD <-> Axis1@rocker; Z via Front planes.
    await concentric_mate(
        adapter, bore_axis_ref(pivot_od), named_ref(f"Axis1@{rocker}", "AXIS"),
        label="rocker pivot revolute", verify=(rocker, _org(adapter, rocker)))

    # cam drives rod: rod ring axis (Axis1) <-> cam lobe axis (Axis3). Two
    # named axes -> coincident (coaxial); fast + mirror-agnostic, no face walk
    # (the geared part has ~thousands of faces and the lobe face will not select
    # through the nested/flexible sub anyway -- see build_cylinder_gear).
    await coincident_mate(
        adapter, named_ref(f"Axis1@{rod}", "AXIS"),
        named_ref(f"Axis3@{cam}", "AXIS"), label="cam lobe <-> rod ring")

    # rod drives rocker: rod pin axis <-> rocker rod-bore axis (two axes ->
    # coincident; AddMate rejects concentric on two axes).
    await coincident_mate(
        adapter, named_ref(f"Axis2@{rod}", "AXIS"),
        named_ref(f"Axis2@{rocker}", "AXIS"), label="rod pin <-> rocker bore")

    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
    log(f"  after joints: rocker status "
        f"{adapter._attempt(lambda: _find(adapter, 'rocker-arm')[0].GetConstrainedStatus(), default=-1)}")

    # motor on the cam bore; solve; sample the rocker rotation.
    check("ensure_motion_addin", await adapter.ensure_motion_addin())
    made = check("create_motion_study", await adapter.create_motion_study(
        MotionStudyParameters(name="", study_type="physical_simulation",
                              duration=DURATION_S, activate=True)))
    log(f"  study {made['name']!r}")
    cam_c, cam_n = _find(adapter, "cylinder-gear")
    # Motor on the cam BORE axis by name (Axis2) -- selecting a face on this
    # geared part walks ~thousands of tooth faces (~10 min, live-caught).
    check("add_motor cam", await adapter.add_motor(MotionMotorParameters(
        motor_type="rotary",
        entity=MateEntityRef(entity_type="AXIS", name=f"Axis2@{cam_n}"),
        speed=CAM_RPM, study_name="")))
    check("calculate_motion", await adapter.calculate_motion(
        MotionStudyRefParameters(name="")))

    base = None
    for time_s in (0.0, 0.5, 1.0, 1.5, 2.0):
        check(f"set_time {time_s}", await adapter.set_motion_time(
            MotionTimeParameters(time=time_s, study_name="")))
        rk, _ = _find(adapter, "rocker-arm")
        a = _comp_xform(adapter, rk)
        base = base or a
        log(f"    t={time_s}: rocker rock = {_rot_angle(base, a):.2f} deg")
    return {}


def _org(adapter, name):
    a = __import__("_common", fromlist=["component_transform"]).component_transform(adapter, name)
    return [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]


if __name__ == "__main__":
    sys.exit(run_build(build))
