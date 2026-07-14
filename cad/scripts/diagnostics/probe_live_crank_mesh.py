r"""Minimal-pair probe of the 16T x 64T crank mesh: place ONLY the two built
parts at the assembly's exact design transforms in a throwaway assembly, run
interference detection, and read each patch's LOCATION (temp-body bbox) --
the discriminator for tip-vs-root / slice-ridge / flank contact. Also saves
mesh close-up screenshots. (~1 min of seat time vs an 8 min assembly build;
NB ``sw.connect`` closes all open documents.)

Run (SolidWorks open, parts built)::

    uv run python cad\scripts\diagnostics\probe_live_crank_mesh.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import _common  # noqa: F401  -- diagnostics import shim
from _common import _early_bound, _read_member, check, log, run_build  # noqa: E402
from _assembly import component_transform, place_component  # noqa: E402

import build_drive_train_assembly as dta  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "out" / "png" / "diag-crank-mesh"


def _spin_off_z(rows: list[float], seed_deg: float) -> float:
    sd = math.radians(-seed_deg)
    return math.degrees(math.atan2(
        math.cos(sd) * rows[1] - math.sin(sd) * rows[0],
        math.cos(sd) * rows[0] + math.sin(sd) * rows[1],
    ))


def _spin_off_u(rows: list[float]) -> float:
    u = (dta.SIN_I, 0.0, dta.COS_I)
    exd = (dta.COS_I, 0.0, -dta.SIN_I)
    c = rows[0:3]
    cross = (
        exd[1] * c[2] - exd[2] * c[1],
        exd[2] * c[0] - exd[0] * c[2],
        exd[0] * c[1] - exd[1] * c[0],
    )
    return math.degrees(math.atan2(
        sum(x * a for x, a in zip(cross, u)),
        sum(e * a for e, a in zip(exd, c)),
    ))


async def build(adapter) -> dict[str, str]:
    check("create_assembly", await adapter.create_assembly())
    g0 = dta.cone_station(dta.GEAR64_STATION)
    await place_component(
        adapter, "crank-drive-gear",
        [g0[0] - dta.GEAR64_FACE / 2.0 * dta.SIN_I, dta.Y_DRIVE,
         g0[2] - dta.GEAR64_FACE / 2.0 * dta.COS_I],
        [0.0, dta.INCLINE_DEG, 0.0], dta.ROT_Y_INCLINE,
        ground=True, label="64T at design",
    )
    await place_component(
        adapter, "crank-pinion",
        [dta.X_CRANK, dta.Y_CRANK, dta.PINION_TOOTH_Z - dta.PINION_FACE / 2.0],
        [0.0, 0.0, -dta.PINION_SEED_DEG], dta.rot_z_rows(-dta.PINION_SEED_DEG),
        ground=True, label="16T at design",
    )

    # Read back the placed spins (paranoia: both grounded, must be exact).
    a16 = component_transform(adapter, "crank-pinion-1")
    a64 = component_transform(adapter, "crank-drive-gear-1")
    phi16 = _spin_off_z(a16, dta.PINION_SEED_DEG)
    phi64 = _spin_off_u(a64)
    log(f"pinion spin off design: {phi16:+.4f} deg (about +z)")
    log(f"64T    spin off design: {phi64:+.4f} deg (about +u)")
    log(f"equivalent seed error: {-(phi16 + 4.0 * phi64):+.4f} deg")
    o16 = [v * 1000.0 for v in a16[9:12]]
    o64 = [v * 1000.0 for v in a64[9:12]]
    log(f"pinion origin {o16} (design [{dta.X_CRANK}, {dta.Y_CRANK}, "
        f"{dta.PINION_TOOTH_Z - dta.PINION_FACE / 2.0}])")
    log(f"64T    origin {o64}")

    # Interference patches with locations.
    asm = _early_bound(
        adapter.currentModel, "IAssemblyDoc",
        "ToolsCheckInterference", "InterferenceDetectionManager",
    )
    adapter._attempt(lambda: asm.ToolsCheckInterference(), default=None)
    mgr = _read_member(asm, "InterferenceDetectionManager")
    mgr = _early_bound(mgr, "IInterferenceDetectionMgr", "GetInterferences")
    mgr.TreatCoincidenceAsInterference = False
    mgr.TreatSubAssembliesAsComponents = True
    mgr.IncludeMultibodyPartInterferences = True
    # Transparent parts leave the interference volumes visible in red --
    # the screenshots below ARE the SW interference picture.
    mgr.MakeInterferingPartsTransparent = True
    mgr.CreateFastenersFolder = False
    mgr.UseTransform = False
    hits = list(adapter._attempt(lambda: mgr.GetInterferences(), default=None) or [])
    log(f"{len(hits)} interference(s)")
    ux, uz = dta.SIN_I, dta.COS_I
    g0 = dta.cone_station(dta.GEAR64_STATION)
    patch_boxes: list[list[float]] = []
    for i, itf in enumerate(hits):
        itf = _early_bound(itf, "IInterference", "GetInterferenceBody")
        names = [str(_read_member(c, "Name2"))
                 for c in list(_read_member(itf, "Components") or [])]
        vol = float(_read_member(itf, "Volume") or 0.0) * 1e9
        body = adapter._attempt(lambda: itf.GetInterferenceBody(), default=None)
        box = adapter._attempt(lambda: body.GetBodyBox(), default=None) if body is not None else None
        if box is None:
            log(f"[{i}] {' & '.join(names)}: {vol:.3f} mm^3 (no body box)")
            continue
        mm = [float(v) * 1000.0 for v in box]
        patch_boxes.append(mm)
        cx, cy, cz = ((mm[0] + mm[3]) / 2, (mm[1] + mm[4]) / 2, (mm[2] + mm[5]) / 2)
        r_crank = math.hypot(cx - dta.X_CRANK, cy - dta.Y_CRANK)
        rel = (cx - g0[0], cy - dta.Y_DRIVE, cz - g0[2])
        s64 = rel[0] * ux + rel[2] * uz
        rad = (rel[0] - s64 * ux, rel[1], rel[2] - s64 * uz)
        r_cone = math.sqrt(sum(v * v for v in rad))
        az = math.degrees(math.atan2(cy - dta.Y_CRANK, cx - dta.X_CRANK))
        log(f"[{i}] {' & '.join(names)}: {vol:.3f} mm^3")
        log(f"     bbox x {mm[0]:.2f}..{mm[3]:.2f}  y {mm[1]:.2f}..{mm[4]:.2f}"
            f"  z {mm[2]:.2f}..{mm[5]:.2f}")
        log(f"     centre ({cx:.2f}, {cy:.2f}, {cz:.2f})  r_from_crank"
            f" {r_crank:.3f} (tip16 {dta.R16 + dta.ADD16:.3f}, root16"
            f" {dta.R16 - 1.157 * dta.ADD16:.3f})")
        log(f"     r_from_cone {r_cone:.3f} (tip64 {dta.R64 + dta.ADD16:.3f},"
            f" root64 {dta.R64 - 1.157 * dta.ADD16:.3f})  s64 {s64:+.3f}"
            f" (face +-{dta.GEAR64_FACE / 2.0})  az_from_crank {az:.1f} deg"
            f" (contact az {180.0 + dta.ALPHA16:.1f})")

    # Screenshots. The interference volumes stay highlighted (parts
    # transparent) until mgr.Done(), so these ARE the SW interference
    # picture. Front view (gears face-on), zoom-to-fit for the wide shot,
    # then a tight zoom on the union of the measured patch bboxes (falls
    # back to the theoretical contact point when there are no patches).
    OUT.mkdir(parents=True, exist_ok=True)
    mdl = _early_bound(
        adapter.currentModel, "IModelDoc2",
        "ViewZoomTo2", "ViewZoomtofit2", "ShowNamedView2", "SaveBMP",
    )
    adapter._attempt(lambda: mdl.ShowNamedView2("*Front", 1), default=None)
    adapter._attempt(lambda: mdl.ViewZoomtofit2(), default=None)
    ok = adapter._attempt(
        lambda: mdl.SaveBMP(str(OUT / "mesh-wide.bmp"), 1600, 1200), default=False)
    log(f"screenshot {OUT / 'mesh-wide.bmp'}: {'OK' if ok else 'FAILED'}")
    if patch_boxes:
        lo = [min(b[i] for b in patch_boxes) for i in range(3)]
        hi = [max(b[i + 3] for b in patch_boxes) for i in range(3)]
    else:
        c_az = math.radians(180.0 + dta.ALPHA16)
        cx = dta.X_CRANK + dta.R16 * math.cos(c_az)
        cy = dta.Y_CRANK + dta.R16 * math.sin(c_az)
        lo = [cx, cy, dta.PINION_TOOTH_Z]
        hi = list(lo)
    pad = 8.0
    adapter._attempt(lambda: mdl.ViewZoomTo2(
        (lo[0] - pad) / 1000.0, (lo[1] - pad) / 1000.0, (lo[2] - pad) / 1000.0,
        (hi[0] + pad) / 1000.0, (hi[1] + pad) / 1000.0, (hi[2] + pad) / 1000.0,
    ), default=None)
    ok = adapter._attempt(
        lambda: mdl.SaveBMP(str(OUT / "mesh-tight.bmp"), 1600, 1200), default=False)
    log(f"screenshot {OUT / 'mesh-tight.bmp'}: {'OK' if ok else 'FAILED'}")
    adapter._attempt(lambda: mgr.Done(), default=None)
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
