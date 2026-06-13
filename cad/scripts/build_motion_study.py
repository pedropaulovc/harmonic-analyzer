r"""Phase F (artifact B): the OPERATION simulation -- a throwaway SOLIDWORKS
Motion study that opens the static, fully-defined harmonic-analyzer.SLDASM and
drives the whole device from a single crank motor, with the channel/counter
springs as real force elements and the two amplifying wires as motion
couplings. It NEVER re-saves the .SLDASM (artifact A stays fully-defined on
disk; this study lives only in the dirtied in-memory doc + an exported video).

Pipeline (see plan from-other-conversation-current-tender-meteor.md, Part 3):

  1. open harmonic-analyzer.SLDASM (the 4 subs inserted rigid + fixed).
  2. for the 3 MOVING subs (channel/drive-train/output; frame stays fixed):
     float -> ground the rigid pose at identity with 3 coincident plane mates
     -> set_component_solving FLEXIBLE, so their internal mates solve with the
     parent and a top-level motor/cam/spring reaches the parts inside them.
  3. suppress the internal DRIVER dims that pin the DOF Motion must control:
       * drive-train: the single crank-angle driver (frees the whole gear train)
       * channel:     the per-rocker spin + per-rod swing drivers (frees the
                      rocker->rod cam followers); the 20 amplitude-bar slides
                      stay pinned (they are coefficient settings)
       * output:      the 4 compliant-chain snapshot drivers (summing-lever,
                      magnifying-lever, magnifying-wheel rocks + pen-rod travel);
                      the platen + clamp settings stay pinned
     -- all via suppress_mate(component=<sub>), resolved inside the sub doc,
     never saving the sub.
  4. add 20 cross-assembly CAM concentrics: each channel connecting-rod ring
     bore rides its drive-train cylinder-gear eccentric lobe (the coupling that
     turns crank rotation into the per-channel rocker oscillation).
  5. crank MOTOR: a rotary constant-speed motor on the crankshaft axis -- the
     one physical input that runs the device.
  6. 21 SPRING force elements: 20 channel springs + 1 counter spring, k from
     k = G*d^4 / (8*D^3*n), G(steel) = 79.3 GPa, geometry per part script.
  7. the TWO WIRES as motion couplings: WIRE 1 vertical-rod/fixture -> wheel hub
     (Ø20), WIRE 2 wheel rim (Ø100) -> pen-rod, 5x amplification.
  8. gravity (-Y); Calculate(); export an .mp4; sample the pen-marker tip over a
     crank revolution and compare to the synthesized harmonic curve.

Basic Motion (physical_simulation) is the licensed solver on this 3DEXPERIENCE
Makers seat -- MotionAnalysis is NOT licensed here. Basic Motion solves motors,
springs, gravity and contact, which is what this study needs.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_motion_study.py [stage]

``stage`` (default ``kinematic``) gates how far the build runs so the heavy
solve can be brought up incrementally:
    flex       -> flexible + suppress only (no motor/solve)
    kinematic  -> + cam concentrics + crank motor + Calculate + pen sample
    springs    -> + 21 spring force elements
    full       -> + the two wires + gravity + video + harmonic-curve compare
"""

from __future__ import annotations

import math
import sys

from _common import (
    OUT_PNG, OUT_SLDASM, _flag, _read_member, check, coincident_mate, log,
    named_ref, run_build,
)

# ---- study constants --------------------------------------------------------
ASM = "harmonic-analyzer"
MOVING_SUBS = ("drive-train-1", "channel-1", "output-1")  # frame-1 stays fixed
FRAME_SUB = "frame-1"

CRANK_RPM = 20.0          # gentle: 1 rev / 3 s at 20 RPM
DURATION_S = 6.0          # two crank revolutions
N_CHANNELS = 20

# swMateType_e
COINCIDENT, CONCENTRIC, DISTANCE, ANGLE = 0, 1, 5, 6
_MATE_NAME = {0: "COINCIDENT", 1: "CONCENTRIC", 4: "TANGENT", 5: "DISTANCE",
              6: "ANGLE", 9: "CAMFOLLOWER", 10: "GEAR", 13: "RACKPINION",
              16: "LOCK"}

RIGID, FLEXIBLE = "rigid", "flexible"

# Spring stiffness k = G*d^4 / (8*D^3*n); steel shear modulus.
G_STEEL = 79.3e9  # Pa
# channel spring: wire d 1.0, OD 6.5 -> mean D 5.5, active coils n 28, free 32mm
CH_SPRING = dict(d=1.0, D=5.5, n=28.0, free_mm=32.0)
# counter spring: wire d 1.8, OD 12.5 -> mean D 10.7, n 165, free body 315mm
CT_SPRING = dict(d=1.8, D=10.7, n=165.0, free_mm=315.0)


def _k_helical(d_mm: float, D_mm: float, n: float) -> float:
    """Linear rate (N/m) of a helical compression/extension spring."""
    d, D = d_mm / 1000.0, D_mm / 1000.0
    return G_STEEL * d**4 / (8.0 * D**3 * n)


# ---- nested-component helpers (GetComponentByName fails on 'sub/part') -------
def _components(adapter, model=None):
    model = model or adapter.currentModel
    return adapter._attempt(lambda: model.GetComponents(False), default=None) or []


def _find_comps(adapter, needle, model=None):
    """All components whose Name2 contains ``needle`` (dispatch, name)."""
    out = []
    for c in _components(adapter, model):
        _flag(c, "IComponent2")
        nm = str(_read_member(c, "Name2"))
        if needle in nm:
            out.append((c, nm))
    return out


def _find_one(adapter, needle, model=None):
    hits = _find_comps(adapter, needle, model)
    return hits[0] if hits else (None, None)


def _sub_model(adapter, sub_name):
    comp, _ = _find_one(adapter, sub_name)
    if comp is None:
        raise RuntimeError(f"sub component not found: {sub_name}")
    model = adapter._attempt(lambda: comp.GetModelDoc2(), default=None)
    if model is None:
        raise RuntimeError(f"GetModelDoc2 returned None for {sub_name}")
    return comp, model


def _mate_parts(adapter, mate):
    """Distinct PART names a mate references (planes/origins -> None, skipped)."""
    parts = []
    n = int(adapter._attempt(lambda: mate.GetMateEntityCount(), default=0))
    for i in range(n):
        me = adapter._attempt(lambda k=i: mate.MateEntity(k), default=None)
        if me is None:
            continue
        _flag(me, "IMateEntity2")
        rc = adapter._attempt(lambda e=me: e.ReferenceComponent2, default=None)
        if rc is None:
            rc = adapter._attempt(lambda e=me: e.ReferenceComponent, default=None)
        if rc is not None:
            _flag(rc, "IComponent2")
            parts.append(str(_read_member(rc, "Name2")))
    return parts


def _mate_value(adapter, mate, mtype):
    if mtype not in (DISTANCE, ANGLE):
        return None
    dd = adapter._attempt(lambda: mate.DisplayDimension2(0), default=None)
    if dd is None:
        return None
    _flag(dd, "IDisplayDimension")
    dim = adapter._attempt(lambda: dd.GetDimension2(0), default=None)
    if dim is None:
        dim = adapter._attempt(lambda: dd.GetDimension(), default=None)
    if dim is None:
        return None
    _flag(dim, "IDimension")
    return adapter._attempt(lambda: dim.Value, default=None)


def _iter_mates(adapter, model):
    """Yield (feature, mate, name, mtype, parts, value) for MODEL's mate group."""
    _flag(model, "IModelDoc2")
    feat = _read_member(model, "FirstFeature")
    for _ in range(50000):
        if not feat:
            break
        _flag(feat, "IFeature")
        if _read_member(feat, "GetTypeName2") == "MateGroup":
            sub = _read_member(feat, "GetFirstSubFeature")
            for _ in range(50000):
                if not sub:
                    break
                _flag(sub, "IFeature")
                name = str(_read_member(sub, "Name"))
                mate = adapter._attempt(lambda s=sub: s.GetSpecificFeature2(), default=None)
                if mate is not None:
                    _flag(mate, "IMate2")
                    mtype = int(adapter._attempt(lambda m=mate: m.Type, default=-1))
                    parts = _mate_parts(adapter, mate)
                    val = _mate_value(adapter, mate, mtype)
                    yield sub, mate, name, mtype, parts, val
                sub = _read_member(sub, "GetNextSubFeature")
        feat = _read_member(feat, "GetNextFeature")


def _single_part(parts):
    """The lone PART name when a mate references exactly one part, else None."""
    uniq = sorted(set(parts))
    return uniq[0] if len(uniq) == 1 else None


# ---- stage 2: float + ground + flex -----------------------------------------
async def _flex_subs(adapter):
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters, SetComponentSolvingParameters,
    )
    asm = adapter.currentModel
    for sub in MOVING_SUBS:
        check(f"float {sub}", await adapter.float_component(ComponentRefParameters(name=sub)))
        for plane in ("Front Plane", "Top Plane", "Right Plane"):
            await coincident_mate(
                adapter, named_ref(f"{plane}@{sub}", "PLANE"),
                named_ref(plane, "PLANE"), label=f"ground {sub} {plane}")
        adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
        check(f"flexible {sub}", await adapter.set_component_solving(
            SetComponentSolvingParameters(name=sub, solving=FLEXIBLE)))
        comp, _ = _find_one(adapter, sub)
        solving = int(adapter._attempt(lambda c=comp: c.Solving, default=-1))
        log(f"  {sub} Solving={solving} (1=flexible)")
    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)


# ---- stage 3: suppress the driver dims inside each sub -----------------------
async def _suppress_in_sub(adapter, sub_name, predicate, label):
    """Suppress every mate in SUB_NAME's doc matching PREDICATE(name,mtype,parts,val)."""
    from solidworks_mcp.adapters.base import SuppressMateParameters
    _, model = _sub_model(adapter, sub_name)
    targets = []
    for _f, _m, name, mtype, parts, val in _iter_mates(adapter, model):
        if predicate(name, mtype, parts, val):
            targets.append(name)
    log(f"  {label}: {len(targets)} mates to suppress in {sub_name}: {targets}")
    saved = adapter.currentModel
    try:
        adapter.currentModel = model
        for name in targets:
            check(f"suppress {name}@{sub_name}",
                  await adapter.suppress_mate(SuppressMateParameters(
                      name=name, suppress=True, component=sub_name)))
    finally:
        adapter.currentModel = saved
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    return targets


def _dump_sub_mates(adapter, sub_name):
    """Log every mate in a sub doc -- ground truth for the suppress predicates."""
    _, model = _sub_model(adapter, sub_name)
    log(f"  --- mates in {sub_name} ---")
    for _f, _m, name, mtype, parts, val in _iter_mates(adapter, model):
        single = _single_part(parts)
        vstr = ""
        if val is not None and mtype == DISTANCE:
            vstr = f" val={val * 1000.0:.2f}mm"
        elif val is not None and mtype == ANGLE:
            vstr = f" val={math.degrees(val):.2f}deg"
        log(f"    {name:16s} {_MATE_NAME.get(mtype, mtype)!s:11s} "
            f"single={single} parts={sorted(set(parts))}{vstr}")


async def _suppress_drivers(adapter):
    # Ground truth first (cheap, and documents what the predicates act on).
    for sub in MOVING_SUBS:
        _dump_sub_mates(adapter, sub)

    # drive-train: the crank-angle driver -- the lone distance/angle mate that
    # references crank-handle (a single part). Frees the whole gear train.
    await _suppress_in_sub(
        adapter, "drive-train-1",
        lambda nm, mt, parts, val: mt in (DISTANCE, ANGLE)
        and _single_part(parts) is not None
        and _single_part(parts).startswith("crank-handle"),
        "crank driver")

    # channel: single-part distance drivers on rocker-arm / connecting-rod
    # (spin + ring X/Y/Z + rod swing) -- free the cam followers. Keep the
    # amplitude-bar slides (coefficient settings) and all 2-part structural
    # axials + concentrics.
    await _suppress_in_sub(
        adapter, "channel-1",
        lambda nm, mt, parts, val: mt == DISTANCE
        and _single_part(parts) is not None
        and _single_part(parts).startswith(("rocker-arm", "connecting-rod")),
        "channel rocker/rod drivers")

    # output: the 4 compliant-chain snapshot drivers. summing-lever /
    # magnifying-lever / magnifying-wheel ANGLE rocks + the pen-rod travel
    # DISTANCE (the largest pen-rod distance == its Y position ~398 mm; the
    # small slide-depth/across stay pinned).
    await _suppress_in_sub(
        adapter, "output-1",
        lambda nm, mt, parts, val: mt == ANGLE
        and _single_part(parts) is not None
        and _single_part(parts).startswith(
            ("summing-lever", "magnifying-lever", "magnifying-wheel")),
        "output rock snapshots")
    await _suppress_in_sub(
        adapter, "output-1",
        lambda nm, mt, parts, val: mt == DISTANCE
        and _single_part(parts) is not None
        and _single_part(parts).startswith("pen-rod")
        and val is not None and val * 1000.0 > 200.0,
        "pen-rod travel snapshot")


# ---- stage 4: 20 cross-assembly cam concentrics -----------------------------
def _largest_cyl_face(adapter, comp, target_r_mm=None):
    """GetCorrespondingEntity for a cylindrical face on COMP's part.

    Ranks by |radius - target_r_mm| when target given (the cam lobe is the
    Ø50.8 face, r 25.4; the gear bore is r 4.76), else by area.
    """
    part = adapter._attempt(lambda: comp.GetModelDoc2(), default=None)
    if part is None:
        return None
    bodies = adapter._attempt(lambda: part.GetBodies2(0, False), default=None)
    if bodies is None:
        return None
    if not isinstance(bodies, (list, tuple)):
        bodies = [bodies]
    cyls = []  # (rank_key, radius, face)
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
                    area = float(adapter._attempt(lambda f=face: f.GetArea(), default=0.0))
                    if p is not None:
                        radius = float(p[6]) * 1000.0
                        if target_r_mm is None:
                            key = -area
                        else:
                            key = abs(radius - target_r_mm)
                        cyls.append((key, radius, area, face))
            face = adapter._attempt(lambda f=face: f.GetNextFace(), default=None)
    if not cyls:
        return None
    cyls.sort(key=lambda c: c[0])
    best = cyls[0]
    log(f"    cyl face r={best[1]:.2f}mm area={best[2] * 1e6:.0f}mm^2")
    return adapter._attempt(lambda: comp.GetCorrespondingEntity(best[3]), default=None)


async def _add_cam_concentrics(adapter):
    """One concentric per channel: connecting-rod ring bore <-> cam lobe OD.

    The connecting rod ring (r ~25.5 bore) rides the cylinder-gear eccentric
    lobe (Ø50.8, r 25.4). Concentric on the two cylindrical faces makes the
    ring centre orbit with the lobe -> the crank rotation becomes the channel's
    rocker oscillation. Faces resolved by GetCorrespondingEntity (nesting- and
    flexible-agnostic).
    """
    from solidworks_mcp.adapters.base import AddMateParameters
    rods = sorted(_find_comps(adapter, "connecting-rod"), key=lambda t: t[1])
    gears = sorted(_find_comps(adapter, "cylinder-gear"), key=lambda t: t[1])
    log(f"  cam coupling: {len(rods)} rods, {len(gears)} gears")
    made = 0
    for i, ((rod_c, rod_n), (gear_c, gear_n)) in enumerate(zip(rods, gears)):
        ring_face = _largest_cyl_face(adapter, rod_c, target_r_mm=25.5)
        lobe_face = _largest_cyl_face(adapter, gear_c, target_r_mm=25.4)
        if ring_face is None or lobe_face is None:
            log(f"    ch{i:02d}: face missing (ring={ring_face}, lobe={lobe_face})")
            continue
        adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))
        adapter._attempt(lambda f=ring_face: f.Select4(True, None))
        adapter._attempt(lambda f=lobe_face: f.Select4(True, None))
        res = await adapter.add_mate(AddMateParameters(
            mate_type="concentric", entities=[], alignment="closest"))
        adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))
        if res.is_success:
            made += 1
        else:
            log(f"    ch{i:02d} cam concentric failed: {res.error}")
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    log(f"  cam concentrics created: {made}/{len(rods)}")
    return made


# ---- stage 5: crank motor ---------------------------------------------------
async def _add_crank_motor(adapter):
    from solidworks_mcp.adapters.base import MateEntityRef, MotionMotorParameters
    cs_comp, cs_name = _find_one(adapter, "crankshaft")
    if cs_comp is None:
        raise RuntimeError("crankshaft component not found")
    log(f"  crank motor on {cs_name}")
    res = check("add_motor crank", await adapter.add_motor(MotionMotorParameters(
        motor_type="rotary",
        entity=MateEntityRef(entity_type="FACE", component=cs_name),
        speed=CRANK_RPM, study_name="")))
    return res


# ---- pen sampling -----------------------------------------------------------
def _comp_xform(adapter, comp):
    t = _read_member(comp, "Transform2")
    return [float(v) for v in _read_member(t, "ArrayData")]


def _world(a, local_mm):
    r, t = a[0:9], a[9:12]
    return [sum(local_mm[i] * r[i * 3 + k] for i in range(3)) + t[k] * 1000.0
            for k in range(3)]


async def _sample_pen(adapter, study_name=""):
    from solidworks_mcp.adapters.base import MotionTimeParameters
    samples = []
    steps = 24
    for s in range(steps + 1):
        t = DURATION_S * s / steps
        check(f"set_time {t:.2f}", await adapter.set_motion_time(
            MotionTimeParameters(time=t, study_name=study_name)))
        marker, _ = _find_one(adapter, "pen-marker")
        if marker is None:
            log("    pen-marker not found")
            break
        tip = _world(adapter, _comp_xform(adapter, marker), [0.0, 0.0, 0.0])
        samples.append((t, tip))
        log(f"    t={t:5.2f}s pen tip=({tip[0]:.2f},{tip[1]:.2f},{tip[2]:.2f})")
    if samples:
        ys = [p[1][1] for _t, p in samples]
        log(f"  pen-tip Y span = {max(ys) - min(ys):.3f} mm "
            f"(0 => the pen never moved)")
    return samples


# ---- main -------------------------------------------------------------------
async def build(adapter):
    stage = sys.argv[1] if len(sys.argv) > 1 else "kinematic"
    order = {"flex": 0, "kinematic": 1, "springs": 2, "full": 3}
    if stage not in order:
        raise RuntimeError(f"unknown stage {stage!r}; pick {sorted(order)}")
    level = order[stage]
    log(f"stage = {stage} (level {level})")

    asm_path = str((OUT_SLDASM / f"{ASM}.SLDASM").resolve())
    check("open harmonic-analyzer", await adapter.open_model(asm_path))
    log(f"opened {asm_path}")

    await _flex_subs(adapter)
    await _suppress_drivers(adapter)
    if level < 1:
        log("stage flex complete (no motor/solve)")
        return {}

    await _add_cam_concentrics(adapter)
    check("ensure_motion_addin", await adapter.ensure_motion_addin())
    from solidworks_mcp.adapters.base import MotionStudyParameters, MotionStudyRefParameters
    made = check("create_motion_study", await adapter.create_motion_study(
        MotionStudyParameters(name="", study_type="physical_simulation",
                              duration=DURATION_S, activate=True)))
    log(f"  study {made['name']!r}")
    await _add_crank_motor(adapter)

    # springs / wires / gravity layered in later stages (see _springs/_wires).
    if level >= 2:
        from build_motion_study_springs import add_springs  # noqa: F401
        await add_springs(adapter)
    if level >= 3:
        from build_motion_study_springs import add_wires_gravity
        await add_wires_gravity(adapter)

    check("calculate_motion", await adapter.calculate_motion(
        MotionStudyRefParameters(name="")))
    samples = await _sample_pen(adapter)

    artefacts = {}
    if level >= 3 and samples:
        from solidworks_mcp.adapters.base import MotionExportParameters
        vid = (OUT_PNG.parent / f"{ASM}-operation.mp4").resolve()
        res = await adapter.export_motion_video(MotionExportParameters(
            file_path=str(vid), study_name="", frames_per_second=25.0))
        if res.is_success:
            log(f"  video {res.data['bytes']} bytes -> {vid}")
            artefacts["video"] = str(vid)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
