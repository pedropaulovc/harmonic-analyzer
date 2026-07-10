r"""Standalone MINIMAL repro: CopyWithMates2 parks an under-constrained copy
off its mates' pose.

The smallest slice that shows it (measured 2026-07-09, SW 2024 SP3; re-confirmed
2026-07-10 on SW 2026 SP2 via an early-bound C# Interop port): ONE part with
ZERO features (an empty part -- just its default planes), TWO mates to the
assembly root planes (coincident Top + distance Front, leaving in-plane slide +
spin free), ONE CopyWithMates2 call with the distance slot re-valued one step
over. The floating copy lands at the right distance but PARKED ~8.5-9.5 mm off
along the free in-plane direction -- deterministically, where the seed sat
exactly on pose. A raw Transform2 put to the intended pose then survives
EditRebuild3 (no revert at this scale; reverts were only ever observed on a
large multi-loop assembly).

By default the SEED IS FLOATED (its auto-fix removed) -- see below -- so the
run isolates the pure CopyWithMates2 free-DOF wander with NO mate errors.

    seed after mates           org=(   0.000,   0.000, -20.000)  ON-POSE
    copy post-CopyWithMates2   org=(   9.488,  -0.000, -45.000)  WANDER   <- parks off, free dir
    copy post-put+rebuild      org=(   0.000,   0.000, -45.000)  ON-POSE  <- put heals, holds

WHY FLOAT THE SEED (the confound this isolates). The first component added to an
assembly is AUTO-FIXED by SolidWorks. A DISTANCE mate on a fixed component
conflicts with the fix (the part can't move to satisfy it), so SolidWorks flags
that mate over-defined -- a spurious "mates are over-defined / corrupted" error
that has nothing to do with CopyWithMates2. `--fixed-seed` keeps the auto-fix to
demonstrate that artifact:
  * seed reads FULLY-DEFINED (it is pinned, not mate-constrained) and never wanders;
  * the seed's Distance mate reports an ERROR (fix vs. distance-mate conflict);
  * the copy's mates come out `aligned` while the seed's stay `closest`
    (CopyWithMates2 does NOT preserve the alignment mode), so the copy's distance
    also resolves on the OTHER side (solved z -45 vs seed-derived -50).
Floating the seed makes both instances floating + under-defined, removes every
mate error, and leaves ONLY the wander -- which is also the realistic case (a
copied part is never the fixed one).

pywin32 only -- NO repo imports, suitable for a vendor ticket. SolidWorks must
already be open; the script creates its own throwaway documents, closes only
those, and saves nothing except the tiny part in %TEMP%.

Run:  uv run python cad\scripts\diagnostics\diag_cwm_min.py [--visible] [--fixed-seed]

--visible uses a one-extrude cylinder instead of the empty part, so the parked
copy can be seen (and screenshotted) in the viewport.
--fixed-seed keeps the first component auto-fixed (see the confound above).
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
        mate(asm, [f"Top Plane@{name}@{title}", "Top Plane"], COIN)
        mate(asm, [f"Front Plane@{name}@{title}", "Front Plane"], DIST, Z0)
        seed = comp.Transform2.ArrayData  # the reference: solved seed pose
        report("seed after mates", comp, [seed[9] * 1000, seed[10] * 1000,
                                          seed[11] * 1000])
        status(ext, "seed only, before CopyWithMates2", comp)
        before = {c.Name2 for c in asm.GetComponents(True)}
        n = 2  # both mates are external (root-plane refs); slot 1 = the dim
        asm.CopyWithMates2(
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH,
                    [comp._oleobj_]),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [True] * n),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, [None] * n),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [0.0, Z0 + STEP]),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [False] * n),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [False] * n),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [False] * n),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I4, [0] * n),
        )
        comps = {c.Name2: c for c in asm.GetComponents(True)}
        copy = flag(comps[(set(comps) - before).pop()],
                    "IsFixed", "GetConstrainedStatus")
        # expected: the seed's solved pose, one STEP further on its side
        want = [seed[9] * 1000, seed[10] * 1000, (seed[11] - STEP) * 1000]
        parked = report("copy post-CopyWithMates2", copy, want)
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
        print(f"VERDICT: {'no wander' if parked else 'copy PARKS OFF-POSE'},"
              f" {'put holds' if held else 'put REVERTED'}")
        return 0
    finally:
        for t in titles:
            sw.CloseDoc(t)


if __name__ == "__main__":
    sys.exit(main())
