r"""Minimal isolated repro: a CopyWithMates2 copy CARRYING a GEAR mate parks
SPUN off the seed -- the stored-phase wander that disqualified copying the
mesh in the drive-train cylinder ladder (diag_cwm_cylinder.py measured it at
9.1229 deg on the production assembly, both copies, rebuild-stable).

This is the GEAR-mate flavor of the free-DOF landing documented in
diag_cwm_min.py: a gear mate couples rotation INCREMENTS, it never defines
absolute phase, so the copy's spin is positionally unconstrained and the
solver parks it at a station of its own choosing -- NOT at the seed's phase,
even though the copy inherits the seed's transform and its mates come out
value-identical. Measured here (SW 2026 SP2), and what makes the gear case
nastier than the plain free-DOF case:

* The park angle is a CONSTANT: 9.1229 deg -- the EXACT angle the production
  drive-train probe measured (diag_cwm_cylinder.py, 122-component assembly,
  different ratios 120:6 vs 1:2, different geometry, both copies). The
  wander is a solver constant, not context. (Curiously close to the
  8.5-9.5 mm translation park of diag_cwm_min -- same family.)
* GetConstrainedStatus is NO GUARD: geared to a FIXED partner, the seed here
  reads FULLY-DEFINED -- and its copy still parks 9.1229 deg off. The folk
  rule "only copy fully-constrained seeds" (every vendor demo) does not
  protect a gear mate's phase, because no mate ever defines it.
* The park is REBUILD-STABLE (a rebuild never moves a free DOF), so nothing
  downstream self-heals; the phase recorded against the copy's mesh partner
  is simply wrong by the park angle.
* A raw Transform2 put of the phase DOES land and DOES hold through a plain
  EditRebuild3 in this minimal case (nothing re-solves a free DOF). What a
  put cannot do is fix the RELATIONSHIP the copied mate recorded at copy
  time, and in production the correction paths that re-solve the coupling
  (drag, transient drivers, the kinematics sweep) turn the partner TRAIN
  through the mesh -- with per-station ratios, cranking every
  already-placed gear differentially.

The remedy this script demonstrates (the production recipe shipped in
build_drive_train_assembly.py): DELETE the copied gear mate (nothing then
stores any spin state), PUT the copy at the design phase (holds -- exactly
the diag_cwm_min case), and author a FRESH gear mate, which records the
correct phase from the CURRENT pose and carries its ratio natively.

Measured trace (default variant)::

    seed after mates             org=(0, 0, -20)  spin-off-seed= 0.0000 deg
    copy post-CopyWithMates2     org=(0, 0, -45)  spin-off-seed= 9.1229 deg
    copy post-rebuild            org=(0, 0, -45)  spin-off-seed= 9.1229 deg
    copy post-put+rebuild        org=(0, 0, -45)  spin-off-seed= 0.0000 deg
    copy delete+put+fresh-mesh   org=(0, 0, -45)  spin-off-seed= 0.0000 deg

Smallest slice that shows it (found by stripping the cylinder-ladder probe):
ONE part document with ZERO solid bodies and a single reference axis
(Top-plane x Right-plane intersection -- 1 feature), inserted THREE times:

    A  fixed at the origin      the seed's arbor + mesh partner (no mates)
    C  fixed one step over      the COPY's mesh partner (no mates)
    B  the seed                 3 mates: coaxial to A's axis + one root
                                Front-plane distance (spin the ONLY free
                                DOF) + a 1:2 GEAR mate to A's axis

One CopyWithMates2 call copies B with the distance slot re-valued one step
and the GEAR slot re-pointed at C's axis (Repeat=false + NewEntityToMateTo
-- each production station meshes a DIFFERENT partner; same wizard path).
The copy lands translation-exact and SPUN off the seed; the spin survives a
rebuild; a raw phase put lands and holds through a plain rebuild but cannot
rewrite the mesh relationship the copied mate recorded; delete-put-remesh
heals it for real and HOLDS.

pywin32 only -- NO repo imports, deliberately (the diag_cwm_min.py
convention): the script must run unmodified on any machine with pywin32 --
a vendor ticket, a clean seat -- so it cannot import ``_telemetry``, and
its printed measurement trace IS its machine-readable output (the exemption
AGENTS.md's log-don't-print rule reserves for stdout a caller consumes).
SolidWorks must already be open; the script creates its own throwaway
documents, closes only those, and saves nothing except the tiny part in
%TEMP%.

Run:  uv run python cad\scripts\diagnostics\diag_cwm_gear_min.py [--visible]

--visible adds a cylinder (R5 x 10 mm) and a small off-centre marker boss to
the part so the phase is visible in the viewport (the marker points +X on
the seed; the copy's marker sits rotated by the wander angle).

Reproduce by hand in the SolidWorks UI (Copy with Mates menu)
-------------------------------------------------------------
Use --visible geometry so the phase can be seen. Menu paths are SW 2024-2026.

1. New part. Sketch a circle (R 5 mm) on the Front plane, extrude 10 mm.
   Sketch a small circle (R 1 mm) at (x=+3 mm, y=0) on the cylinder's front
   face, extrude 2 mm -- the phase MARKER. (The script's default variant
   shows the same numbers with zero solids and just a reference axis; the
   marker only makes it visible.) Save as %TEMP%\cwm_gear_min.SLDPRT.
2. New assembly. Insert the part THREE times: A at the origin, C ~40 mm to
   the side, B anywhere. Leave A auto-fixed; right-click C > Fix.
3. Mate B (the seed):
     a. Coincident: B's axis (View > Hide/Show > Axes; or the cylinder
        face) <-> A's axis. B is now coaxial with A.
     b. Distance: B's Front plane <-> the ASSEMBLY's Front plane, 20 mm.
     c. Gear mate (Mate > Mechanical > Gear): B's axis <-> A's axis,
        ratio 1:2. NOTE: because A is fixed, B now reads FULLY DEFINED in
        the tree (no "(-)") -- yet its phase was never positionally
        defined. Its marker points +X.
4. Copy with Mates: select B, Insert > Component > Copy with Mates. Step
   through the mates: keep the coaxial reference (A's axis), set the
   DISTANCE to 45 mm (re-select the assembly Front plane), and for the GEAR
   mate RE-SELECT the partner as C's axis. Place one copy.
5. RESULT: the copy sits at the right distance, coaxial as asked -- but its
   MARKER is rotated ~9.1 deg away from the seed's (+X). Ctrl-Q: it stays
   rotated. The mesh phase recorded against C is wrong by that angle, and
   the fully-defined-looking seed did not prevent it.
6. The trap: there is no in-place fix. Dragging the copy to phase (Move
   Component with rotate) is refused -- the gear mate couples it to the
   fixed C; on a free train the drag turns every coupled gear instead. And
   editing the gear mate re-records nothing.
7. The remedy (what the production build does): DELETE the copy's gear
   mate, rotate the copy so its marker matches the seed (Move Component --
   now free, it stays), then add a FRESH gear mate to C's axis. Ctrl-Q:
   the phase holds -- a fresh mate records the CURRENT pose as its phase.

LATE-BOUND PROBE: this script drives SolidWorks through its own
``GetObject``/``Dispatch`` (or a raw ``adapter.currentModel``), NOT the makepy
wrapper, so its ``[out]`` params land in the ``VT_BYREF`` VARIANTs passed in
rather than in the return tuple. That is the OPPOSITE of the build path, where
``_common._early_bound`` guarantees an early-bound object and the outs ride the
return tuple. Both are correct for their binding -- mixing them is the trap that
reads as "no data" instead of failing. See memory/sw-assembly-mate-diagnostics-api.md.
"""

from __future__ import annotations

import math
import os
import sys
import tempfile

import pythoncom
from win32com.client import VARIANT, dynamic

COIN, DIST, GEAR = 0, 5, 10  # swMateType_e
CLOSEST = 2                  # swMateAlign_e
Z0, STEP = 0.020, 0.025      # seed axial dim / ladder step (m)
X_C = 0.040                  # partner C station (m)
RATIO = (1.0, 2.0)           # gear ratio numerator:denominator
NULL = VARIANT(pythoncom.VT_DISPATCH, None)  # bare None marshals VT_NULL

_CS = {1: "unknown-constraint", 2: "under-defined", 3: "fully-defined",
       4: "OVER-DEFINED", 5: "NO-SOLUTION", 6: "INVALID-SOLUTION",
       7: "autosolve-off"}


def flag(obj, *names):
    obj._FlagAsMethod(*names)
    return obj


def new_part(sw, path: str, visible: bool) -> str:
    """A throwaway part in %TEMP%: ONE reference axis (Top x Right = the
    Z axis), zero solids -- or, with --visible, plus a cylinder and an
    off-centre phase marker."""
    part = flag(sw.NewPart(), "SaveAs3", "GetTitle", "ClearSelection2",
                "InsertAxis2")
    ext = flag(part.Extension, "SelectByID2")
    ext.SelectByID2("Top Plane", "PLANE", 0, 0, 0, False, 0, NULL, 0)
    ext.SelectByID2("Right Plane", "PLANE", 0, 0, 0, True, 0, NULL, 0)
    if not part.InsertAxis2(True):
        raise RuntimeError("InsertAxis2 failed (Top x Right)")
    part.ClearSelection2(True)
    if visible:
        skm = flag(part.SketchManager, "InsertSketch", "CreateCircleByRadius")
        fm = flag(part.FeatureManager, "FeatureExtrusion2")
        ext.SelectByID2("Front Plane", "PLANE", 0, 0, 0, False, 0, NULL, 0)
        skm.InsertSketch(True)
        skm.CreateCircleByRadius(0, 0, 0, 0.005)
        skm.InsertSketch(True)
        fm.FeatureExtrusion2(
            True, False, False, 0, 0, 0.010, 0, False, False, False, False,
            0, 0, False, False, False, False, True, True, True, 0, 0, False)
        part.ClearSelection2(True)
        ext.SelectByID2("Front Plane", "PLANE", 0, 0, 0, False, 0, NULL, 0)
        skm.InsertSketch(True)
        skm.CreateCircleByRadius(0.003, 0, 0, 0.001)  # phase marker at +X
        skm.InsertSketch(True)
        fm.FeatureExtrusion2(
            True, False, True, 0, 0, 0.012, 0, False, False, False, False,
            0, 0, False, False, False, False, True, True, True, 0, 0, False)
        part.ClearSelection2(True)
    if os.path.exists(path):  # a prior run's doc may hold the file lock
        sw.CloseDoc(os.path.splitext(os.path.basename(path))[0])
        sw.CloseDoc(os.path.basename(path))
        os.remove(path)
    part.SaveAs3(path, 0, 1)  # return is NOT a success flag (0 on success)
    if not os.path.exists(path):
        raise RuntimeError(f"SaveAs3 produced no file: {path}")
    return part.GetTitle()


def select(asm, name: str, typ: str, append: bool):
    if not asm.Extension.SelectByID2(name, typ, 0, 0, 0, append, 1, NULL, 0):
        raise RuntimeError(f"select failed: {typ} {name}")


def mate(asm, refs, mtype, d=0.0, ratio=(0.0, 0.0)):
    """refs = [(name, type), ...]; gear ratio only read for GEAR mates."""
    asm.ClearSelection2(True)
    for name, typ in refs:
        select(asm, name, typ, True)
    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    if asm.AddMate5(mtype, CLOSEST, False, d, d, d, ratio[0], ratio[1],
                    0, 0, 0, False, False, 0, err) is None:
        raise RuntimeError(f"AddMate5 failed ({err.value}): {refs}")
    asm.ClearSelection2(True)


def entity(asm, name: str, typ: str):
    """A live entity for a NewEntityToMateTo slot."""
    asm.ClearSelection2(True)
    if not asm.Extension.SelectByID2(name, typ, 0, 0, 0, False, 0, NULL, 0):
        raise RuntimeError(f"select failed: {typ} {name}")
    ent = flag(asm.SelectionManager, "GetSelectedObject6").GetSelectedObject6(1, -1)
    asm.ClearSelection2(True)
    if ent is None:
        raise RuntimeError(f"no entity for {name}")
    return ent


def spin_deg(a, b) -> float:
    """Rotation angle (deg) between two array16 rotation blocks."""
    tr = sum(a[r * 3 + c] * b[r * 3 + c] for r in range(3) for c in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (tr - 1.0) / 2.0))))


def report(tag, comp, want_org, seed_rot) -> tuple[bool, float]:
    a = comp.Transform2.ArrayData
    p = [a[9] * 1000, a[10] * 1000, a[11] * 1000]
    dorg = max(abs(p[k] - want_org[k]) for k in range(3))
    dspin = spin_deg(seed_rot, a)
    print(f"  {tag:30s} org=({p[0]:8.3f},{p[1]:8.3f},{p[2]:8.3f})"
          f" org-err={dorg:7.3f}mm  spin-off-seed={dspin:8.4f}deg")
    return dorg < 0.05, dspin


def fix_component(asm, comp):
    flag(comp, "Select2").Select2(False, 0)
    asm.FixComponent()
    asm.ClearSelection2(True)


def delete_mate(asm, name: str):
    asm.ClearSelection2(True)
    if not asm.Extension.SelectByID2(name, "MATE", 0, 0, 0, False, 0, NULL, 0):
        raise RuntimeError(f"select failed: MATE {name}")
    if not flag(asm.Extension, "DeleteSelection2").DeleteSelection2(0):
        flag(asm, "EditDelete").EditDelete()
    asm.ClearSelection2(True)


def main() -> int:
    visible = "--visible" in sys.argv
    sw = flag(dynamic.Dispatch("SldWorks.Application"),
              "NewPart", "NewAssembly", "CloseDoc", "GetMathUtility")
    path = os.path.join(tempfile.gettempdir(), "cwm_gear_min.SLDPRT")
    titles = [new_part(sw, path, visible)]
    try:
        asm = flag(sw.NewAssembly(), "AddComponent5", "AddMate5",
                   "EditRebuild3", "ClearSelection2", "GetComponents",
                   "GetTitle", "CopyWithMates2", "FixComponent")
        title = asm.GetTitle()
        titles.insert(0, title)  # assembly closes first

        def insert(x, z):
            return flag(asm.AddComponent5(path, 0, "", False, "", x, 0.0, z),
                        "IsFixed", "GetConstrainedStatus", "Select2")

        a = insert(0.0, 0.0)          # auto-fixed: arbor + seed mesh partner
        c = insert(X_C, 0.0)          # the COPY's mesh partner
        fix_component(asm, c)
        b = insert(0.0, -Z0)          # the seed
        na, nc, nb = a.Name2, c.Name2, b.Name2
        print(f"  A={na} fixed={a.IsFixed()}  C={nc} fixed={c.IsFixed()}"
              f"  B={nb} (seed)")
        # The seed slice: coaxial on A + one root-plane axial dim => spin is
        # the ONLY free DOF; then the 1:2 gear mate to A's axis. Tree order
        # of these three mates = the CopyWithMates2 slot order.
        mate(asm, [(f"Axis1@{nb}@{title}", "AXIS"),
                   (f"Axis1@{na}@{title}", "AXIS")], COIN)
        mate(asm, [(f"Front Plane@{nb}@{title}", "PLANE"),
                   ("Front Plane", "PLANE")], DIST, Z0)
        mate(asm, [(f"Axis1@{nb}@{title}", "AXIS"),
                   (f"Axis1@{na}@{title}", "AXIS")], GEAR, ratio=RATIO)
        seed = list(b.Transform2.ArrayData)
        seed_rot = seed[0:9]
        seed_org = [seed[9] * 1000, seed[10] * 1000, seed[11] * 1000]
        print(f"  seed status: {_CS.get(b.GetConstrainedStatus(), '?')}"
              " (geared to a FIXED partner it reads fully-defined --"
              " yet no mate defines its phase)")
        report("seed after mates", b, seed_org, seed_rot)

        before = {x.Name2 for x in asm.GetComponents(True)}
        # Copy B: distance slot re-valued one step, GEAR slot re-pointed at
        # C's axis (every production station meshes a DIFFERENT partner) --
        # Repeat=false + NewEntityToMateTo, the documented wizard path.
        ents = [entity(asm, f"Axis1@{na}@{title}", "AXIS")._oleobj_,
                entity(asm, "Front Plane", "PLANE")._oleobj_,
                entity(asm, f"Axis1@{nc}@{title}", "AXIS")._oleobj_]
        ok = asm.CopyWithMates2(
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, [b._oleobj_]),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [False] * 3),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, ents),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [0.0, Z0 + STEP, 0.0]),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [False] * 3),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [False] * 3),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [False] * 3),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I4, [0] * 3),
        )
        print(f"  CopyWithMates2 returned {ok} (unreliable -- judge the model)")
        comps = {x.Name2: x for x in asm.GetComponents(True)}
        copy = flag(comps[(set(comps) - before).pop()],
                    "IsFixed", "GetConstrainedStatus")
        # The copy stays coaxial with A and marches one STEP along the axis.
        want = [seed_org[0], seed_org[1], seed_org[2] - STEP * 1000]
        on1, spin1 = report("copy post-CopyWithMates2", copy, want, seed_rot)
        if abs(copy.Transform2.ArrayData[11] * 1000 - want[2]) > 0.05:
            want[2] = copy.Transform2.ArrayData[11] * 1000  # side flip: keep
            print(f"  NB copied dim solved z={want[2]:.3f} -- other side than"
                  " seed-derived; phase is the subject here, not the side")
        if not asm.EditRebuild3():
            print("  !! EditRebuild3 returned False")
        _, spin2 = report("copy post-rebuild", copy, want, seed_rot)

        # Measurement: a raw put of the PHASE with the copied mesh still
        # present. Measured: it lands AND holds through a plain EditRebuild3
        # (nothing re-solves a free DOF) -- but it cannot rewrite the
        # relationship the copied mate recorded, and production correction
        # paths that re-solve the coupling (drag/drivers/kinematics) turn
        # the partner train instead. Hence the fresh-mesh remedy below.
        mu = flag(sw.GetMathUtility(), "CreateTransform")
        target = list(seed_rot) + [want[0] / 1000, want[1] / 1000,
                                   want[2] / 1000] + list(seed[12:16])
        copy.Transform2 = mu.CreateTransform(
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, target))
        _, spin_put = report("copy post-phase-put", copy, want, seed_rot)
        asm.EditRebuild3()
        _, spin3 = report("copy post-put+rebuild", copy, want, seed_rot)

        # The remedy (the production recipe): delete the copied gear mate --
        # nothing then stores spin state -- put the phase (holds), author a
        # FRESH gear mate to C, which records the phase from the CURRENT
        # pose. GearMate1 = the authored seed mesh, GearMate2 = the copy's.
        delete_mate(asm, "GearMate2")
        copy.Transform2 = mu.CreateTransform(
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, target))
        mate(asm, [(f"Axis1@{copy.Name2}@{title}", "AXIS"),
                   (f"Axis1@{nc}@{title}", "AXIS")], GEAR, ratio=RATIO)
        asm.EditRebuild3()
        on4, spin4 = report("copy delete+put+fresh-mesh", copy, want, seed_rot)

        wandered = spin1 > 0.01
        stable = abs(spin2 - spin1) < 0.01
        healed = on4 and spin4 < 0.01
        print(f"VERDICT: copy {'PARKS OFF-PHASE by %.4f deg' % spin1 if wandered else 'lands on phase'},"
              f" {'REBUILD-STABLE' if stable else 'unstable'};"
              f" phase put {'holds' if spin3 < 0.01 else 'REVERTED'}"
              f" (spin {spin3:.4f}) but cannot rewrite the recorded mesh;"
              f" delete+put+fresh-mesh {'HEALS and HOLDS' if healed else 'FAILED'}")
        return 0
    finally:
        for t in titles:
            sw.CloseDoc(t)


if __name__ == "__main__":
    sys.exit(main())
