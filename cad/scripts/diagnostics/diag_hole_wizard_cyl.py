"""Live probe: Hole Wizard on a CYLINDRICAL face (radial cross-hole).

The crankshaft's Ø5 taper-pin cross-hole is radial through a plain cylinder --
no planar face carries the drill axis, so ``_holes.wizard_holes`` (planar-face
placement) cannot author it. The UI supports wizard holes on cylindrical faces
via a 3D-sketch position; this probe asks whether the COM path does too:

1. Cylinder Ø12 x 40 (axis +Y). Select its cylindrical FACE object.
2. ``CreateDefinition(25)`` -> ``InitializeHole(drilled #9, through-all)`` ->
   ``CreateFeature`` (the proven through-hole path from _holes.py).
3. Inspect the placement sketch (2D or 3D profile?), move the auto point to
   the target station (0, 20, R) on the face, rebuild.
4. Volume gate: a Ø4.978 diametral through-hole in a Ø12 shaft removes the
   perpendicular cylinder-cylinder intersection volume, integrated numerically
   (no closed form needed).

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/diag_hole_wizard_cyl.py

Nothing is saved; the document is discarded.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

from _common import check, run_build  # noqa: E402
from _holes import NUMBER_DRILL_MM, SW_FM_HOLE_WZD, _STD_ANSI_INCH, _flag  # noqa: E402
import _telemetry  # noqa: E402

R_SHAFT = 6.0  # Ø12 shaft
H_SHAFT = 40.0
HOLE_Y = 20.0  # cross-hole station (mid-height)
DIA = NUMBER_DRILL_MM["#9"]  # 4.978 -- the crankshaft pin drill


def _cross_hole_volume(r_hole: float, r_shaft: float, n: int = 20001) -> float:
    """Perpendicular drill through the full shaft, axes intersecting:
    V = integral_-r^r 2*sqrt(R^2-x^2) * 2*sqrt(r^2-x^2) dx (numeric)."""
    total = 0.0
    dx = 2.0 * r_hole / (n - 1)
    for i in range(n):
        x = -r_hole + i * dx
        w = 0.5 if i in (0, n - 1) else 1.0
        total += w * 2.0 * math.sqrt(max(r_shaft**2 - x * x, 0.0)) * \
            2.0 * math.sqrt(max(r_hole**2 - x * x, 0.0))
    return total * dx


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    if not res.is_success:
        raise RuntimeError(f"mass props failed: {res.error}")
    return float(res.data.volume)


def _cyl_face(model):
    """The shaft's cylindrical face object (largest non-planar face)."""
    body = (model.GetBodies2(0, False) or [None])[0]
    _flag(body, "IBody2")
    best = None
    for f in body.GetFaces() or []:
        _flag(f, "IFace2")
        surf = f.GetSurface()
        _flag(surf, "ISurface")
        if not surf.IsCylinder():
            continue
        if best is None or f.GetArea() > best.GetArea():
            best = f
    return best


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    check("create_sketch base", await adapter.create_sketch("Top"))
    check("circle", await adapter.add_circle(0.0, 0.0, R_SHAFT))
    check("exit", await adapter.exit_sketch())
    check("extrude shaft", await adapter.create_extrusion(
        ExtrusionParameters(depth=H_SHAFT)))
    v0 = await _volume(adapter)
    _telemetry.info(f"shaft volume {v0:.1f} mm^3")

    model = adapter.currentModel
    _flag(model, "IModelDoc2")
    fm = model.FeatureManager
    _flag(fm, "IFeatureManager")

    face = _cyl_face(model)
    if face is None:
        raise RuntimeError("cylindrical face not found")
    model.ClearSelection2(True)
    if not face.Select2(False, 0):
        raise RuntimeError("cylindrical face Select2 failed")
    _telemetry.info("cylindrical face selected; creating through #9 wizard hole")

    data = fm.CreateDefinition(SW_FM_HOLE_WZD)
    _flag(data, "IWizardHoleFeatureData2")
    data.InitializeHole(2, _STD_ANSI_INCH, 24, "#9", 1)  # drilled number, thru
    feat = fm.CreateFeature(data)
    if feat is None:
        raise RuntimeError("CreateFeature on cylindrical face returned None")
    _flag(feat, "IFeature")
    _telemetry.success(f"wizard feature created on cylinder: {feat.Name}")

    # Inspect the placement sketch: 2D ProfileFeature or a 3D profile?
    sub = feat.GetFirstSubFeature()
    place = None
    while sub is not None:
        _flag(sub, "IFeature")
        tname = str(sub.GetTypeName2())
        sk = sub.GetSpecificFeature2() if "Profile" in tname else None
        npts = -1
        if sk is not None:
            _flag(sk, "ISketch")
            npts = len(sk.GetSketchPoints2() or [])
            is3d = bool(sk.Is3D())
            _telemetry.info(
                f"subfeature {sub.Name}: type={tname} points={npts} 3d={is3d}")
            if npts == 1:
                place = (sub, sk, is3d)
        else:
            _telemetry.info(f"subfeature {sub.Name}: type={tname}")
        sub = sub.GetNextSubFeature()
    if place is None:
        raise RuntimeError("placement sketch (1 point) not found")

    sub, sk, is3d = place
    pt = (sk.GetSketchPoints2() or [None])[0]
    _flag(pt, "ISketchPoint")
    _telemetry.info(
        f"auto point at sketch ({pt.X * 1000:.3f}, {pt.Y * 1000:.3f}, "
        f"{pt.Z * 1000:.3f}) in {'3D' if is3d else '2D'} sketch")

    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
            str(sub.Name), "SKETCH", 0, 0, 0, False, 0, null_callout(), 0):
        raise RuntimeError(f"cannot select placement sketch {sub.Name}")
    model.EditSketch()
    if is3d:
        # 3D sketch: point coords ARE model coords -- pin the station directly
        # on the face at (0, HOLE_Y, R).
        pt.SetCoords(0.0, HOLE_Y / 1000.0, R_SHAFT / 1000.0)
    else:
        xform = sk.ModelToSketchTransform
        _flag(xform, "IMathTransform")
        import pythoncom
        from win32com.client import VARIANT

        mu = adapter.swApp.GetMathUtility()
        _flag(mu, "IMathUtility")
        arr = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8,
                      [0.0, HOLE_Y / 1000.0, R_SHAFT / 1000.0])
        mpt = mu.CreatePoint(arr)
        _flag(mpt, "IMathPoint")
        spt = mpt.MultiplyTransform(xform)
        _flag(spt, "IMathPoint")
        sx, sy, sz = list(spt.ArrayData)[:3]
        pt.SetCoords(sx, sy, sz)
    model.EditSketch()
    model.EditRebuild3()

    v1 = await _volume(adapter)
    expect = _cross_hole_volume(DIA / 2.0, R_SHAFT)
    removed = v0 - v1
    _telemetry.info(
        f"cross-hole removed {removed:.2f} mm^3 (analytic diametral {expect:.2f})")
    if abs(removed - expect) > 0.05 * expect:
        raise RuntimeError(
            f"cross-hole volume off: removed {removed:.2f}, expected {expect:.2f}"
            " -- placement or drill direction wrong")
    _telemetry.success("cylindrical-face wizard cross-hole PASSES")
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
