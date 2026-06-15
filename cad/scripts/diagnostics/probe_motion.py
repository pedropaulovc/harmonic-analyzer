r"""GATING PROBE for Phase F (motion study): does the full Motion pipeline
work end-to-end on the drive-train alone?

drive-train.SLDASM is fully-defined (its crank-angle DRIVER #1 pins the one
free DOF). This probe:
  1. finds + suppresses that crank driver (a Distance mate touching the
     crank-handle) so the crank regains 1 DOF -> the gear train is free;
  2. ensures the SOLIDWORKS Motion add-in, creates a MotionAnalysis study,
     adds a rotary motor on the crankshaft axis;
  3. Calculate(); scrubs SetTime across a revolution and reads cylinder-gear-1
     (a cam) -- if the cam rotates, a motor drives the meshed train and the
     sampling-by-transform technique works (the foundation of Phase F).

This de-risks the costly driver-renaming + full rebuilds before committing.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_motion.py
"""

from __future__ import annotations

import math
import sys

from _common import OUT_SLDASM, check, component_transform, log, run_build, _flag, _read_member


def _mates(adapter):
    """(name, mate_type, [component names]) for every mate in the MateGroup."""
    model = adapter.currentModel
    _flag(model, "IModelDoc2")
    out = []
    feat = _read_member(model, "FirstFeature")
    for _ in range(8000):
        if not feat:
            break
        _flag(feat, "IFeature")
        if _read_member(feat, "GetTypeName2") == "MateGroup":
            sub = _read_member(feat, "GetFirstSubFeature")
            for _ in range(8000):
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
    model = adapter.currentModel
    for c in adapter._attempt(lambda: model.GetComponents(True), default=None) or []:
        _flag(c, "IComponent2")
        if comp_substr in str(_read_member(c, "Name2")):
            if bool(_read_member(c, "IsFixed")):
                return "FIXED"
            s = int(adapter._attempt(lambda x=c: x.GetConstrainedStatus(), default=-1))
            return {2: "UNDER(2)", 3: "FULLY(3)", 4: "OVER(4)"}.get(s, f"s={s}")
    return "??"


def _cam_angle(adapter, name):
    """Rotation of cylinder-gear-1 about Z (deg) from its transform's R11/R21."""
    a = component_transform(adapter, name)
    return math.degrees(math.atan2(a[1], a[0]))


async def build(adapter):
    from solidworks_mcp.adapters.base import (
        MateEntityRef, MotionMotorParameters, MotionStudyParameters,
        MotionStudyRefParameters, MotionTimeParameters, SuppressMateParameters,
    )

    path = str((OUT_SLDASM / "drive-train.SLDASM").resolve())
    check("open drive-train", await adapter.open_model(path))

    # --- 1. find + suppress the crank driver (Distance mate on crank-handle) ---
    DISTANCE = 5
    driver = None
    for name, mtype, comps in _mates(adapter):
        if mtype == DISTANCE and any("crank-handle" in c for c in comps):
            driver = name
            log(f"crank driver = {name} (type {mtype}, comps {comps})")
            break
    if driver is None:
        log("crank driver NOT found; dumping distance mates:")
        for name, mtype, comps in _mates(adapter):
            if mtype == DISTANCE:
                log(f"  {name}: {comps}")
        raise RuntimeError("crank driver not found")

    log(f"crankshaft status before suppress: {_status(adapter, 'crankshaft')}")
    check("suppress crank driver",
          await adapter.suppress_mate(SuppressMateParameters(name=driver, suppress=True)))
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False))
    log(f"crankshaft status after  suppress: {_status(adapter, 'crankshaft')}  (want UNDER(2))")

    # --- 2. Motion add-in + study + rotary motor on the crankshaft axis ---
    check("ensure_motion_addin", await adapter.ensure_motion_addin())
    made = check("create_motion_study",
                 await adapter.create_motion_study(
                     MotionStudyParameters(name="", study_type="physical_simulation",
                                           duration=2.0, activate=True)))
    study = made["name"]
    log(f"study created: {study!r}")
    # 30 RPM -> 1 rev in 2 s (the study duration), so SetTime(t) maps t*180 deg.
    check("add_motor",
          await adapter.add_motor(MotionMotorParameters(
              motor_type="rotary",
              entity=MateEntityRef(entity_type="AXIS", name="Axis1@crankshaft-1@drive-train"),
              speed=30.0, component="crankshaft-1")))

    # --- 3. solve + sample the cam rotation ---
    check("calculate_motion", await adapter.calculate_motion(MotionStudyRefParameters(name="")))
    samples = []
    for t in (0.0, 0.5, 1.0, 1.5, 2.0):
        check(f"set_time {t}", await adapter.set_motion_time(MotionTimeParameters(time=t, study_name="")))
        ang = _cam_angle(adapter, "cylinder-gear-1")
        samples.append((t, ang))
        log(f"  t={t}: cylinder-gear-1 angle = {ang:.2f} deg")
    spread = max(a for _, a in samples) - min(a for _, a in samples)
    log(f"cam angle spread over the run = {spread:.2f} deg  (0 => nothing moved)")
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
