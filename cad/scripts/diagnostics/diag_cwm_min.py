r"""Diagnostic: CopyWithMates2 does not carry a copied component's FREE-DOF pose
into the copy. This is EXPECTED SolidWorks behavior, NOT a bug -- it is kept as a
documented gotcha and a control experiment.

CONCLUSION (investigated 2026-07-09/10, SW 2024 SP3 + SW 2026 SP2 via a raw
pywin32 run and an early-bound C# Interop port): when a copied component is
UNDER-CONSTRAINED, the value of its free DOF is not defined by mates, so
CopyWithMates2 has nothing to preserve there -- it re-solves and the free DOF
lands wherever the solver puts it (deterministically, but NOT at the seed's
value). Fully-constrain the copy and it lands exactly on pose. So there is no
defect: an unconstrained position was never defined, and moving it is within
spec. The practical lesson for the build: a component copied with a free DOF will
NOT inherit the seed's pose along that DOF -- fully-mate it, or place it
explicitly with a Transform2 put (which is what the pipeline does).

The smallest slice that shows it: ONE part with ZERO features (an empty part --
just its default planes), TWO mates to the assembly root planes (coincident Top
+ distance Front, which remove 5 of 6 DOF and leave exactly ONE free DOF -- the
in-plane slide along the two planes' intersection line; all rotations, including
spin about the axis, are constrained -- confirmed by --pin, where a single
translational Right-plane mate fully defines the part), ONE CopyWithMates2 call
with the distance slot re-valued one step over. The floating copy lands at the
right distance but ~8.5-9.5 mm off along the FREE in-plane direction, where the
seed sat exactly on its (arbitrary) value. A raw Transform2 put to the intended
pose then survives EditRebuild3.

    seed after mates           org=(   0.000,   0.000, -20.000)  ON-POSE
    copy post-CopyWithMates2   org=(   9.488,  -0.000, -45.000)  free DOF re-placed
    copy post-put+rebuild      org=(   0.000,   0.000, -45.000)  ON-POSE (explicit put)

IT IS THE FREE DOF, not API usage. The copy's distance mate IS re-valued the
documented way -- Repeat=false + NewEntityToMateTo set to the assembly's own root
planes (the same planes the seed mates to). Its mates come out correct
(coincident + distance, referencing the root, err=0). The off-pose landing is NOT
a mate-authoring failure; CopyWithMates2 simply resolves the copy's UNCONSTRAINED
in-plane slide to a station of its own choosing instead of the seed's.

    --pin is the NEGATIVE CONTROL. It adds a third mate (Right-plane coincident)
    that removes the free slide, so the copy is FULLY defined. The very same
    CopyWithMates2 call then lands the copy EXACTLY on pose. So the off-pose
    landing is specific to an under-constrained copy; a fully-mated copy is placed
    correctly -- the evidence it is expected behavior, not breakage.

Do NOT read into the bool return. CopyWithMates2 returns False on this call --
but it ALSO returns False on the --pin copy that lands perfectly on pose, and on
SolidWorks' OWN documented profile-center example (Copy_Component_With_Profile_
Center_Mate) recreated on SW 2026 SP2. So on this build its return value is not a
reliable success/failure signal; only the resulting Transform2 / DOF status is.

The auto-fixed first component is a SEPARATE confound, off by default. The first
component added to an assembly is AUTO-FIXED; a distance mate on a fixed
component conflicts with the fix (the part can't move to satisfy it), so
SolidWorks flags that mate over-defined -- spurious "mates over-defined /
corrupted" errors unrelated to CopyWithMates2. This repro FLOATS the seed by
default (UnfixComponent) to remove that noise; --fixed-seed keeps the auto-fix to
demonstrate the artifact (seed reads fully-defined-because-pinned, its Distance
mate errors, and the seed's mate stays `closest` while the copy's is `aligned`,
so the copy's distance also resolves on the other side, z -45 vs -50).

NOT reproduced here (separate open question): the original symptom that started
this investigation was a Transform2 put REVERTING after rebuild on a large
multi-loop assembly. This minimal case shows the opposite (the put holds), so it
does NOT capture that behavior -- if anything is still worth chasing, it is the
revert at scale, not this expected free-DOF placement.

pywin32 only -- NO repo imports. SolidWorks must already be open; the script
creates its own throwaway documents, closes only those, and saves nothing except
the tiny part in %TEMP%.

Run:  uv run python cad\scripts\diagnostics\diag_cwm_min.py [--visible] [--pin] [--fixed-seed]

--visible uses a one-extrude cylinder instead of the empty part, so the copy can
be seen (and screenshotted) in the viewport.
--pin adds the Right-plane mate (negative control: no free DOF => copy on pose).
--fixed-seed keeps the first component auto-fixed (see the confound above).

Reproduce by hand in the SolidWorks UI
--------------------------------------
The script mirrors these exact steps -- do them by hand to see it live (menu
paths are SW 2024-2026; they may vary slightly by version):

1. New part. For a VISIBLE copy, sketch a circle (R 5 mm) on the Front plane and
   extrude it ~10 mm into a small cylinder. (An empty part -- default planes only,
   zero features -- reproduces it too, just nothing to look at.) Save it, e.g.
   %TEMP%\cwm_min.SLDPRT.
2. New assembly. Insert > Component, and drop that part in ONCE (position doesn't
   matter).
3. FLOAT it: right-click the component in the tree > Float. The first component is
   FIXED by default, and a distance mate on a fixed part throws a spurious
   "over-defined" error on that mate -- the confound this repro isolates. (Skip
   this step to SEE that artifact: the distance mate goes red and the component
   reads fully-defined because it is pinned, not mate-constrained.)
4. Add two mates to the ASSEMBLY's own reference planes, leaving the in-plane
   slide free:
     a. Coincident: part Top plane  <-> assembly Top plane.
     b. Distance:   part Front plane <-> assembly Front plane, value 20 mm.
   The component is now UNDER-DEFINED -- a free slide along the plane
   intersection (it shows a "(-)" prefix in the tree).
5. Copy with Mates: select the component, then Insert > Component > Copy with
   Mates. Step through each mate. For the DISTANCE mate you must RE-SELECT its
   reference (the assembly Front plane -- the same plane the seed uses; picking it
   again is required, editing the value alone is not enough) and set the NEW value
   one step over, e.g. 45 mm. Keep the other mate's reference as-is. Place one
   copy, then close the PropertyManager.
6. RESULT: the copy sits at the right DISTANCE but is ~8-9 mm off to the SIDE of
   the seed along the free direction -- because that direction is unconstrained.
   Switch to a Front view (look straight down the cylinder axis): seed and copy
   show as two offset circles instead of one concentric circle.
7. NEGATIVE CONTROL: redo it but first add a third mate pinning the slide
   (Coincident: part Right plane <-> assembly Right plane) so the component is
   fully defined. Now the Copy with Mates copy lands exactly on the seed's axis.
   (Or place the under-defined case explicitly: drag the copy onto the axis /
   Move Component to the intended pose; it holds through a rebuild, Ctrl-Q.)

LATE-BOUND PROBE: this script drives SolidWorks through its own
``GetObject``/``Dispatch`` (or a raw ``adapter.currentModel``), NOT the makepy
wrapper, so its ``[out]`` params land in the ``VT_BYREF`` VARIANTs passed in
rather than in the return tuple. That is the OPPOSITE of the build path, where
``_common._early_bound`` guarantees an early-bound object and the outs ride the
return tuple. Both are correct for their binding -- mixing them is the trap that
reads as "no data" instead of failing. See memory/sw-assembly-mate-diagnostics-api.md.
"""

from __future__ import annotations

import os
import sys
import tempfile

import pythoncom
from win32com.client import VARIANT, dynamic

COIN, DIST = 0, 5        # swMateType_e
CLOSEST = 2              # swMateAlign_e
Z0, STEP = 0.020, 0.025  # seed dim value / ladder step (m)
NULL = VARIANT(pythoncom.VT_DISPATCH, None)  # bare None marshals VT_NULL

# swConstrainedStatus_e -> label
_CS = {1: "unknown-constraint", 2: "under-defined", 3: "fully-defined",
       4: "OVER-DEFINED", 5: "NO-SOLUTION", 6: "INVALID-SOLUTION",
       7: "autosolve-off"}


def flag(obj, *names):
    obj._FlagAsMethod(*names)
    return obj


def new_part(sw, path: str, visible: bool) -> str:
    """A throwaway part in %TEMP%: 0 features, or one extruded circle."""
    part = flag(sw.NewPart(), "SaveAs3", "GetTitle", "ClearSelection2")
    if visible:
        flag(part.Extension, "SelectByID2").SelectByID2(
            "Front Plane", "PLANE", 0, 0, 0, False, 0, NULL, 0)
        skm = flag(part.SketchManager, "InsertSketch", "CreateCircleByRadius")
        skm.InsertSketch(True)
        skm.CreateCircleByRadius(0, 0, 0, 0.005)
        skm.InsertSketch(True)
        flag(part.FeatureManager, "FeatureExtrusion2").FeatureExtrusion2(
            True, False, False, 0, 0, 0.010, 0, False, False, False, False,
            0, 0, False, False, False, False, True, True, True, 0, 0, False)
        part.ClearSelection2(True)
    # SaveAs3's return is NOT a success flag (0 on a successful write);
    # delete-then-check-exists is the real gate. A prior run's doc may still
    # hold the file lock -- close it first (the title is the basename).
    if os.path.exists(path):
        sw.CloseDoc(os.path.splitext(os.path.basename(path))[0])
        sw.CloseDoc(os.path.basename(path))
        os.remove(path)
    part.SaveAs3(path, 0, 1)
    if not os.path.exists(path):
        raise RuntimeError(f"SaveAs3 produced no file: {path}")
    return part.GetTitle()


def mate(asm, refs, mtype, d=0.0):
    asm.ClearSelection2(True)
    for name in refs:
        if not asm.Extension.SelectByID2(name, "PLANE", 0, 0, 0, True, 1,
                                         NULL, 0):
            raise RuntimeError(f"select failed: {name}")
    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    if asm.AddMate5(mtype, CLOSEST, False, d, d, d, 0, 0, 0, 0, 0,
                    False, False, 0, err) is None:
        raise RuntimeError(f"AddMate5 failed ({err.value}): {refs}")
    asm.ClearSelection2(True)


def plane_entity(asm, name):
    """The assembly's own root plane, as an entity for NewEntityToMateTo."""
    if not asm.Extension.SelectByID2(name, "PLANE", 0, 0, 0, False, 0, NULL, 0):
        raise RuntimeError(f"select failed: {name}")
    ent = flag(asm.SelectionManager, "GetSelectedObject6").GetSelectedObject6(1, -1)
    asm.ClearSelection2(True)
    if ent is None:
        raise RuntimeError(f"no entity for {name}")
    return ent


def report(tag, comp, want) -> bool:
    a = comp.Transform2.ArrayData
    p = [a[9] * 1000, a[10] * 1000, a[11] * 1000]
    ok = (max(abs(p[k] - want[k]) for k in range(3)) < 0.05
          and abs(a[0] - 1.0) < 1e-3 and abs(a[1]) < 1e-3)
    print(f"  {tag:26s} org=({p[0]:8.3f},{p[1]:8.3f},{p[2]:8.3f})"
          f" xrow=({a[0]:+.3f},{a[1]:+.3f})  {'ON-POSE' if ok else 'WANDER'}")
    return ok


def whats_wrong(ext) -> list[str]:
    """Best-effort list of 'name(type) err=code warn=bool' for problem mates."""
    feats = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)
    codes = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)
    warns = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)
    try:
        ext.GetWhatsWrong(feats, codes, warns)
    except Exception as exc:  # noqa: BLE001 -- diagnostic, never fatal
        return [f"<GetWhatsWrong n/a: {exc}>"]
    fs = feats.value or []
    cs = codes.value or []
    ws = warns.value or []
    out = []
    for i, f in enumerate(fs):
        try:
            name = f.Name
            typ = flag(f, "GetTypeName2").GetTypeName2()
        except Exception:  # noqa: BLE001
            name, typ = "?", "?"
        code = cs[i] if i < len(cs) else "?"
        warn = ws[i] if i < len(ws) else "?"
        out.append(f"{name}({typ}) err={code} warn={warn}")
    return out


def status(ext, when, seed, copy=None):
    print(f"  --- status: {when} ---")
    for label, c in (("seed", seed), ("copy", copy)):
        if c is None:
            continue
        print(f"    {label} component : {_CS.get(c.GetConstrainedStatus(), '?'):18s}"
              f" fixed={c.IsFixed()}")
    ww = whats_wrong(ext)
    print(f"    WhatsWrong     : {', '.join(ww) if ww else '(none)'}")


def main() -> int:
    visible = "--visible" in sys.argv
    fixed_seed = "--fixed-seed" in sys.argv
    pin = "--pin" in sys.argv
    sw = flag(dynamic.Dispatch("SldWorks.Application"),
              "NewPart", "NewAssembly", "CloseDoc", "GetMathUtility")
    path = os.path.join(tempfile.gettempdir(), "cwm_min.SLDPRT")
    titles = [new_part(sw, path, visible)]
    try:
        asm = flag(sw.NewAssembly(), "AddComponent5", "AddMate5",
                   "EditRebuild3", "ClearSelection2", "GetComponents",
                   "GetTitle", "CopyWithMates2", "UnfixComponent")
        ext = flag(asm.Extension, "SelectByID2", "GetWhatsWrong")
        title = asm.GetTitle()
        titles.insert(0, title)  # assembly closes first
        comp = flag(asm.AddComponent5(path, 0, "", False, "", 0.0, 0.0, -Z0),
                    "IsFixed", "GetConstrainedStatus", "Select2")
        # The first component is auto-fixed. Float it (default) so its distance
        # mate does not conflict with the fix -- see the module docstring.
        if not fixed_seed:
            comp.Select2(False, 0)
            asm.UnfixComponent()
            asm.ClearSelection2(True)
        print(f"  seed: fixed={comp.IsFixed()} "
              f"({'auto-fix kept (--fixed-seed)' if fixed_seed else 'floated'})")
        name = comp.Name2
        # mates on the component: Top-coincident, Front-distance (+ Right-coincident
        # with --pin, which removes the free slide => the negative control).
        mate(asm, [f"Top Plane@{name}@{title}", "Top Plane"], COIN)
        mate(asm, [f"Front Plane@{name}@{title}", "Front Plane"], DIST, Z0)
        if pin:
            mate(asm, [f"Right Plane@{name}@{title}", "Right Plane"], COIN)
        seed = comp.Transform2.ArrayData  # the reference: solved seed pose
        report("seed after mates", comp, [seed[9] * 1000, seed[10] * 1000,
                                          seed[11] * 1000])
        status(ext, "seed only, before CopyWithMates2", comp)
        before = {c.Name2 for c in asm.GetComponents(True)}
        # Documented usage: Repeat=false + NewEntityToMateTo set to the assembly's
        # own root planes (the same planes the seed mates to), so a re-valued
        # distance mate is authored correctly on the copy.
        plane_names = ["Top Plane", "Front Plane"] + (["Right Plane"] if pin else [])
        values = [0.0, Z0 + STEP] + ([0.0] if pin else [])
        n = len(plane_names)
        ents = [plane_entity(asm, nm)._oleobj_ for nm in plane_names]
        ok = asm.CopyWithMates2(
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH,
                    [comp._oleobj_]),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [False] * n),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, ents),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, values),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [False] * n),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [False] * n),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [False] * n),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I4, [0] * n),
        )
        # NOTE: `ok` is False here even in the --pin case that lands the copy
        # perfectly on pose -- the bool return is NOT a reliable signal.
        print(f"  CopyWithMates2 returned {ok}"
              " (unreliable -- False even on a successful --pin copy)")
        comps = {c.Name2: c for c in asm.GetComponents(True)}
        copy = flag(comps[(set(comps) - before).pop()],
                    "IsFixed", "GetConstrainedStatus")
        # expected: the seed's solved pose, one STEP further on its side
        want = [seed[9] * 1000, seed[10] * 1000, (seed[11] - STEP) * 1000]
        on_pose = report("copy post-CopyWithMates2", copy, want)
        status(ext, "after CopyWithMates2", comp, copy)
        z_parked = copy.Transform2.ArrayData[11] * 1000
        if abs(z_parked - want[2]) > 0.05:
            # Second divergence flavor (seen with --fixed-seed): the COPIED dim
            # solves with a different plane-side/offset than the seed's authored
            # mate, so even its constrained direction lands off the seed-derived
            # station.
            print(f"  NB copied dim solved z={z_parked:.3f} vs seed-derived"
                  f" {want[2]:.3f} -- the copy's distance resolves on a"
                  " different side than the seed's")
            want[2] = z_parked  # the put heals only the FREE directions
        target = list(seed)
        target[11] = want[2] / 1000
        copy.Transform2 = flag(sw.GetMathUtility(),
                               "CreateTransform").CreateTransform(
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, target))
        if not asm.EditRebuild3():
            print("  !! EditRebuild3 returned False")
        held = report("copy post-put+rebuild", copy, want)
        status(ext, "after put + rebuild", comp, copy)
        print(f"VERDICT: {'no wander (copy on pose)' if on_pose else 'copy PARKS OFF-POSE'},"
              f" {'put holds' if held else 'put REVERTED'}"
              f"{' [--pin control]' if pin else ''}")
        return 0
    finally:
        for t in titles:
            sw.CloseDoc(t)


if __name__ == "__main__":
    sys.exit(main())
