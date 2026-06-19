r"""GATING PROBE for Phase F artifact B (CORRECTED approach): drive a flexible
subassembly's internals from a top-level motor, WITHOUT dissolving.

Background: the earlier dissolve probe proved DissolveSubAssembly is destructive
-- it deletes the driving-dim mates that reference each sub's origin planes (329
comps, only 142/300+ mates survived, crank driver gone). The canonical path is
FLEXIBLE subassemblies: "the mates in a flexible subassembly are solved
simultaneously with the mates of the parent assembly" (SolidWorks help), and
Basic Motion uses that same solver, so a flexible sub's parts animate.

The one obstacle is freeing the pinned crank DOF: that driver mate lives INSIDE
the drive-train sub, and the adapter's suppress_mate resolves names only in the
top-level tree. FIX: retarget suppression at the sub's already-loaded model doc
(comp.GetModelDoc2()), suppress there, restore -- never saving the sub.

This probe (built FRESH, frame fixed, nothing saved):
  1. insert frame (fixed) + drive-train (grounded to the parent origin by 3
     coincident plane mates), make drive-train FLEXIBLE;
  2. find the crank driver in the SUB model, suppress it via the retarget trick,
     rebuild -> crankshaft regains its DOF;
  3. add a rotary motor on the crankshaft axis (full nested path), Calculate(),
     scrub SetTime, read a cylinder-gear (cam). If it sweeps, a top-level motor
     drives a flexible sub's internals -- the foundation of the non-destructive
     artifact-B build.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_flex_motion.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    OUT_SLDASM,
    _flag,
    _read_member,
    check,
    log,
    run_build,
)
from _assembly import (
    coincident_mate,
    component_transform,
    named_ref,
)

RIGID, FLEXIBLE = 0, 1
FULLY_RESOLVED = 2


def _sub_path(name: str) -> str:
    return str((OUT_SLDASM / f"{name}.SLDASM").resolve())


def _assembly_title(adapter) -> str:
    from solidworks_mcp.adapters.solidworks.assembly import _assembly_title as _t
    return _t(adapter)


def _components(adapter, model=None):
    # GetComponents(False) = ALL components incl. nested (True = top-level only,
    # which misses parts inside a flexible sub).
    model = model or adapter.currentModel
    return adapter._attempt(lambda: model.GetComponents(False), default=None) or []


def _find_comp(adapter, needle, model=None):
    for c in _components(adapter, model):
        _flag(c, "IComponent2")
        nm = str(_read_member(c, "Name2"))
        if needle in nm:
            return c, nm
    return None, None


def _set_flexible(adapter, comp_name):
    from solidworks_mcp.adapters.solidworks.assembly import _select_component
    asm = adapter.currentModel
    adapter._attempt(lambda: asm.ClearSelection2(True), default=None)
    bare = comp_name.split("@", 1)[0].split("/")[-1]
    ok = _select_component(adapter, bare, 0, False)
    res = adapter._attempt(
        lambda: asm.CompConfigProperties5(FULLY_RESOLVED, FLEXIBLE, True, False, "", False, False),
        default=None)
    adapter._attempt(lambda: asm.ClearSelection2(True), default=None)
    log(f"  make flexible {bare!r}: select={ok} CompConfigProperties5={res}")


def _solving(adapter, comp):
    return int(adapter._attempt(lambda: comp.Solving, default=-99))


def _mates(adapter, model):
    """(name, mate_type, [component names]) for every mate in MODEL's MateGroup."""
    _flag(model, "IModelDoc2")
    out = []
    feat = _read_member(model, "FirstFeature")
    for _ in range(20000):
        if not feat:
            break
        _flag(feat, "IFeature")
        if _read_member(feat, "GetTypeName2") == "MateGroup":
            sub = _read_member(feat, "GetFirstSubFeature")
            for _ in range(20000):
                if not sub:
                    break
                _flag(sub, "IFeature")
                name = str(_read_member(sub, "Name"))
                mate = adapter._attempt(lambda s=sub: s.GetSpecificFeature2(), default=None)
                comps, mtype = [], -1
                if mate is not None:
                    _flag(mate, "IMate2")
                    mtype = int(adapter._attempt(lambda m=mate: m.Type, default=-1))
                    n = int(adapter._attempt(lambda m=mate: m.GetMateEntityCount(), default=0))
                    for i in range(n):
                        me = adapter._attempt(lambda m=mate, k=i: m.MateEntity(k), default=None)
                        if me is None:
                            continue
                        _flag(me, "IMateEntity2")
                        rc = adapter._attempt(lambda e=me: e.ReferenceComponent, default=None)
                        if rc is not None:
                            _flag(rc, "IComponent2")
                            comps.append(str(_read_member(rc, "Name2")))
                out.append((name, mtype, comps))
                sub = _read_member(sub, "GetNextSubFeature")
        feat = _read_member(feat, "GetNextFeature")
    return out


def _status(adapter, comp_substr):
    for c in _components(adapter):
        _flag(c, "IComponent2")
        if comp_substr in str(_read_member(c, "Name2")):
            if bool(_read_member(c, "IsFixed")):
                return "FIXED"
            s = int(adapter._attempt(lambda x=c: x.GetConstrainedStatus(), default=-1))
            return {2: "UNDER(2)", 3: "FULLY(3)", 4: "OVER(4)"}.get(s, f"s={s}")
    return "??"


def _z_angle(adapter, name):
    a = component_transform(adapter, name)
    return math.degrees(math.atan2(a[1], a[0]))


def _comp_xform(adapter, comp):
    """Transform2 ArrayData straight off a component dispatch (rotation in
    [0:9] as column-major basis images, translation metres in [9:12])."""
    t = _read_member(comp, "Transform2")
    return [float(v) for v in _read_member(t, "ArrayData")]


def _rot_angle(a0, a1):
    """Magnitude (deg) of the relative rotation between two Transform2 arrays.

    R columns are the world images of local +X/+Y/+Z (a[0:3], a[3:6], a[6:9]).
    R_rel = R1 * R0^T; angle = acos((trace(R_rel) - 1) / 2). Captures rotation
    about ANY axis, unlike atan2 about Z only.
    """
    def cols(a):
        return ((a[0], a[1], a[2]), (a[3], a[4], a[5]), (a[6], a[7], a[8]))
    c0, c1 = cols(a0), cols(a1)
    # trace(R1 * R0^T) = sum over i,j of R1[i][j]*R0[i][j] = dot of basis images.
    trace = sum(c1[k][i] * c0[k][i] for k in range(3) for i in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1.0) / 2.0))))


def _crank_axis_face(adapter, comp):
    """Map the crankshaft's main cylindrical face into assembly context.

    Iterate the part's solid bodies, collect cylindrical faces (radius + area +
    axis direction logged for diagnostics), pick the largest by area, and return
    ``IComponent2.GetCorrespondingEntity(face)`` -- the assembly-context entity a
    rotary motor can use for its Location/DirectionReference.
    """
    part = adapter._attempt(lambda: comp.GetModelDoc2(), default=None)
    if part is None:
        return None
    bodies = adapter._attempt(lambda: part.GetBodies2(0, False), default=None)  # 0=swSolidBody
    if bodies is None:
        return None
    if not isinstance(bodies, (list, tuple)):
        bodies = [bodies]
    cyls = []  # (area, radius, axis_tuple, face)
    for body in bodies:
        if body is None:
            continue
        _flag(body, "IBody2")
        face = adapter._attempt(lambda b=body: b.GetFirstFace(), default=None)
        for _ in range(100000):
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
                        axis = (float(p[3]), float(p[4]), float(p[5]))
                        radius = float(p[6]) * 1000.0
                        cyls.append((area, radius, axis, face))
            face = adapter._attempt(lambda f=face: f.GetNextFace(), default=None)
    if not cyls:
        return None
    cyls.sort(key=lambda c: c[0], reverse=True)
    for area, radius, axis, _f in cyls[:6]:
        log(f"  cyl face: r={radius:.2f}mm area={area * 1e6:.1f}mm^2 "
            f"axis=({axis[0]:.2f},{axis[1]:.2f},{axis[2]:.2f})")
    best_face = cyls[0][3]
    return adapter._attempt(lambda: comp.GetCorrespondingEntity(best_face), default=None)


def _entity_path(name2: str, feature: str, title: str) -> str:
    """Build a SelectByID entity ref for a feature in a (nested) component.

    Name2 'drive-train-1/crankshaft-1' -> 'Axis1@crankshaft-1@drive-train-1@title'
    """
    parts = name2.split("/")
    return f"{feature}@" + "@".join(reversed(parts)) + f"@{title}"


async def build(adapter):
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters, InsertComponentParameters, MotionStudyParameters, MotionStudyRefParameters,
        MotionTimeParameters, SuppressMateParameters,
    )

    check("create_assembly", await adapter.create_assembly())
    fr = check("insert frame", await adapter.insert_component(
        InsertComponentParameters(file_path=_sub_path("frame"),
                                  position=[0, 0, 0], rotation=[0, 0, 0])))
    if not fr.get("fixed"):
        await adapter.fix_component(ComponentRefParameters(name=fr["name"]))
    dt = check("insert drive-train", await adapter.insert_component(
        InsertComponentParameters(file_path=_sub_path("drive-train"),
                                  position=[0, 0, 0], rotation=[0, 0, 0])))
    dt_name = dt["name"]  # e.g. 'drive-train-1'
    asm = adapter.currentModel
    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)

    # Ground the sub to the parent origin (3 coincident plane mates) so its rigid
    # placement is fixed at identity while internals stay free. Done BEFORE
    # flexible so the mates land on the rigid sub frame.
    for plane in ("Front Plane", "Top Plane", "Right Plane"):
        await coincident_mate(
            adapter, named_ref(f"{plane}@{dt_name}", "PLANE"),
            named_ref(plane, "PLANE"), label=f"ground drive-train {plane}")
    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)

    _set_flexible(adapter, dt_name)
    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
    comp, _ = _find_comp(adapter, "drive-train")
    log(f"drive-train Solving after flexible = {_solving(adapter, comp)} (1=flex)")
    log(f"crank-drive-gear status: {_status(adapter, 'crank-drive-gear')}")
    log(f"cylinder-gear-1 status: {_status(adapter, 'cylinder-gear-1')}")

    # --- find the crank driver INSIDE the sub model, suppress via retarget -----
    sub_model = adapter._attempt(lambda c=comp: c.GetModelDoc2(), default=None)
    if sub_model is None:
        raise RuntimeError("could not get drive-train sub model doc")
    DISTANCE = 5
    driver = None
    for name, mtype, comps in _mates(adapter, sub_model):
        if mtype == DISTANCE and any("crank-handle" in c for c in comps):
            driver = name
            log(f"crank driver (in sub) = {name} comps={comps}")
            break
    if driver is None:
        raise RuntimeError("crank driver not found in drive-train sub model")

    log(f"crankshaft before suppress: {_status(adapter, 'crankshaft')}")
    saved = adapter.currentModel
    try:
        adapter.currentModel = sub_model
        check("suppress crank driver (in sub doc)",
              await adapter.suppress_mate(SuppressMateParameters(name=driver, suppress=True)))
    finally:
        adapter.currentModel = saved
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    log(f"crankshaft after ForceRebuild3(False): {_status(adapter, 'crankshaft')}")
    adapter._attempt(lambda: adapter.currentModel.EditRebuild3(), default=None)
    log(f"crankshaft after EditRebuild3:        {_status(adapter, 'crankshaft')}  (want UNDER(2))")

    # --- select the crank rotation axis via GetCorrespondingEntity --------------
    # Research verdict: stop hand-building SelectByID2 name strings for parts
    # nested in a flexible sub (the @-chain is malformed for multi-level nesting
    # and SelectByID2 silently falls back to the top-level feature). Instead map
    # a CYLINDRICAL FACE from the crankshaft PART doc into assembly context with
    # IComponent2.GetCorrespondingEntity -- nesting- and flexible-state-agnostic,
    # and a cylindrical face fully defines a rotary motor's axis. Re-fetch the
    # component AFTER the rebuild (a pre-rebuild pointer can report stale state).
    cs_comp, cs_name = _find_comp(adapter, "crankshaft")
    if cs_comp is None:
        raise RuntimeError("crankshaft component not found after rebuild")
    inner = cs_name.split("/")[-1]
    face_ent = _crank_axis_face(adapter, cs_comp)
    if face_ent is None:
        raise RuntimeError("no cylindrical face found on the crankshaft part")

    check("ensure_motion_addin", await adapter.ensure_motion_addin())
    made = check("create_motion_study", await adapter.create_motion_study(
        MotionStudyParameters(name="", study_type="physical_simulation",
                              duration=2.0, activate=True)))
    log(f"study: {made['name']!r}")

    # Build the rotary motor inline (throwaway probe): the clean PR-M4 API will
    # take a component-face ref, but the gate question here is only "does a
    # top-level motor drive a flexible sub's internals". Mirror _add_motor_impl
    # but feed it the corresponding entity directly.
    from solidworks_mcp.adapters.solidworks.motion import (
        _FEAT_ROTARY_MOTOR, _motion_manager, _resolve_study, _selected_object,
    )
    mgr = _motion_manager(adapter)
    study = _resolve_study(adapter, mgr, "")
    data = adapter._attempt(lambda: study.CreateDefinition(_FEAT_ROTARY_MOTOR), default=None)
    if data is None:
        raise RuntimeError("CreateDefinition failed for rotary motor")
    adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))
    sel_ok = bool(adapter._attempt(lambda: face_ent.Select4(False, None), default=False))
    sel = _selected_object(adapter) or face_ent
    log(f"  corresponding-face Select4 -> {sel_ok}")
    adapter._attempt(lambda: setattr(data, "DirectionReference", sel))
    adapter._attempt(lambda: setattr(data, "Location", sel))
    adapter._attempt(lambda: setattr(data, "RelativeComponent", cs_comp))
    adapter._attempt(lambda: data.ConstantSpeedMotor(30.0))  # RPM
    motor = adapter._attempt(lambda: study.CreateFeature(data), default=None)
    adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))
    if motor is None:
        raise RuntimeError("CreateFeature failed for rotary motor")
    log(f"  motor created: {_read_member(motor, 'Name')}")
    check("calculate_motion", await adapter.calculate_motion(MotionStudyRefParameters(name="")))

    # Sample the cam by reading its Transform2 off the dispatch (the nested
    # by-name GetComponentByName lookup does not resolve 'sub/part'). Measure the
    # full relative rotation from t=0 so rotation about ANY axis is captured.
    cam, cam_name = _find_comp(adapter, "cylinder-gear-1")
    base = None
    samples = []
    for t in (0.0, 0.5, 1.0, 1.5, 2.0):
        check(f"set_time {t}", await adapter.set_motion_time(MotionTimeParameters(time=t, study_name="")))
        cam, _ = _find_comp(adapter, "cylinder-gear-1")  # re-fetch each frame
        a = _comp_xform(adapter, cam)
        base = base or a
        ang = _rot_angle(base, a)
        samples.append((t, ang))
        log(f"  t={t}: cylinder-gear-1 rotation from t0 = {ang:.2f} deg")
    spread = max(s for _, s in samples)
    log(f"cam rotation over the run = {spread:.2f} deg  (0 => nothing moved)")
    log("GATE: " + ("PASS - flexible-sub internals DO animate from a top motor"
                    if spread > 1.0 else "FAIL - cam did not move"))
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
