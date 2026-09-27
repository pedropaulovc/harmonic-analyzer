"""Offline pinion-cluster option probe (pinioncluster, 2026-09-23).

Runs ONE option per process: `python pinion_cluster_probe.py <option>`.
Overlays text-substituted copies of the geometry modules and a copy of
build_drive_train_assembly.py whose module-level `raise AssertionError(` is
rewritten to a recorder, so EVERY failing import-time assert is listed (not just
the first).  Then computes the clearances the module does not assert: the
uncut strap vs cam collar over the whole engage path, the rear pivot-block
axial overlap, pivot-block webs, strap webs and cam walls at the printed bands.
No COM, no CAD edit in the worktree (overlay lives in a temp dir).
"""

from __future__ import annotations

import builtins
import contextlib
import io
import json
import math
import re
import shutil
import sys
import tempfile
from pathlib import Path

SRC = Path("C:/src/wt-pinion-scratch/cad/scripts")

# option -> {module: {NAME: python-expression}}
BASE_FIX = {}
OPTIONS: dict[str, dict[str, dict[str, str]]] = {
    # Integrated scratch head as-is (controls + bracket 22552a23 + review-first 32T).
    "S0_as_merged": {},
    # Integrated head with the bracket's own BOSS_Z 1.7 (review-first's 3.0 dropped).
    "S1_boss17": {"pinion_cam_geometry": {"BOSS_Z": "1.7"}},
    # reviewfirst closing row on the integrated head, no bracket move.
    "S2_rf_cam_only": {
        "pinion_cam_geometry": {"BOSS_Z": "1.7", "CAM_OD": "12.52"},
        "pinion_pivot_block_spec": {"LIFT_BORE_RISE": "1.8561911789147132 - 1.1"},
    },
}


def _sub(text: str, name: str, expr: str) -> str:
    pat = re.compile(rf"^{re.escape(name)} = .*$", re.M)
    if not pat.search(text):
        raise SystemExit(f"no assignment for {name}")
    return pat.sub(lambda _m: f"{name} = {expr}  # PROBE OVERRIDE", text, count=1)


def main(option: str, overrides: dict[str, dict[str, str]]) -> dict:
    root = Path(tempfile.mkdtemp(prefix="pcprobe-")) / "cad"
    shutil.copytree(SRC.parent / "config", root / "config")
    tmp = root / "scripts"
    shutil.copytree(SRC, tmp, ignore=shutil.ignore_patterns("__pycache__", "diagnostics"))
    shutil.copytree(SRC / "diagnostics", tmp / "diagnostics", ignore=shutil.ignore_patterns("__pycache__"))
    for mod, subs in overrides.items():
        text = (SRC / f"{mod}.py").read_text(encoding="utf8")
        for name, expr in subs.items():
            text = _sub(text, name, expr)
        (tmp / f"{mod}.py").write_text(text, encoding="utf8")
    asm = (SRC / "build_drive_train_assembly.py").read_text(encoding="utf8")
    for name, expr in overrides.get("build_drive_train_assembly", {}).items():
        asm = _sub(asm, name, expr)
    asm = asm.replace("raise AssertionError(", "_PROBE_FAIL(")
    (tmp / "build_drive_train_assembly.py").write_text(asm, encoding="utf8")
    fails: list[str] = []

    def _probe_fail(*args):
        fails.append(" ".join(str(a) for a in args))
        return AssertionError(*args)

    builtins._PROBE_FAIL = _probe_fail
    sys.path[:0] = [str(tmp)]
    err = None
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            import build_drive_train_assembly as a  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
        a = sys.modules.get("build_drive_train_assembly")
    out: dict = {"option": option, "overrides": overrides, "assert_failures": fails, "import_error": err}
    if a is None:
        return out
    import pinion_bracket_geometry as bg  # noqa: PLC0415
    import pinion_cam_geometry as cg  # noqa: PLC0415
    import pinion_pivot_block_spec as pb  # noqa: PLC0415

    g = a.__dict__
    PV = (a.PIVOT_X, a.PIVOT_Y)
    AR = (a.APINION_X, a.APINION_Y)
    RC = cg.CAM_OD / 2.0
    E = cg.ECC
    R_END = bg.R_END

    def rot(p, b, c=PV):
        x, y = p[0] - c[0], p[1] - c[1]
        return (c[0] + x * math.cos(b) - y * math.sin(b), c[1] + x * math.sin(b) + y * math.cos(b))

    def cam_c(ar):
        return (a.LIFT_X + E * math.sin(ar), a.LIFT_Y - E * math.cos(ar))

    def seg_dist(p, s0, s1):
        dx, dy = s1[0] - s0[0], s1[1] - s0[1]
        t = max(0.0, min(1.0, ((p[0] - s0[0]) * dx + (p[1] - s0[1]) * dy) / (dx * dx + dy * dy)))
        return math.hypot(p[0] - s0[0] - t * dx, p[1] - s0[1] - t * dy)

    def strap_air(ar, b):
        return seg_dist(cam_c(ar), PV, rot(AR, b)) - R_END - RC

    def pin_gap(ar, b):
        c = rot(a._FPIN_C, b)
        n = rot((a._SPR_N[0] + PV[0], a._SPR_N[1] + PV[1]), b)
        n = (n[0] - PV[0], n[1] - PV[1])
        cc = cam_c(ar)
        dx, dy = cc[0] - c[0], cc[1] - c[1]
        return abs(dx * (-n[1]) - dy * (-n[0])) - (a.FPIN_DIA + cg.CAM_OD) / 2.0

    def root(fn, lo, hi):
        flo = fn(lo)
        for _ in range(80):
            mid = (lo + hi) / 2
            fm = fn(mid)
            if (fm > 0) == (flo > 0):
                lo, flo = mid, fm
            else:
                hi = mid
        return (lo + hi) / 2

    AE = math.radians(a.CAM_ENGAGE_ROTATION_DEG)
    PHI = a._PHI_ENG
    path = []
    for i in range(1001):
        ar = AE * i / 1000
        b = 0.0 if pin_gap(ar, 0.0) > 0 else root(lambda bb: pin_gap(ar, bb), 0.0, PHI * 1.5)
        path.append((ar, b, strap_air(ar, b)))
    pmin = min(path, key=lambda t: t[2])
    rect = min(strap_air(AE * i / 200, PHI * j / 40) for i in range(201) for j in range(41))
    # z bands
    strap_z = [(a.STRAP_Z_INNER[0] - bg.THICKNESS, a.STRAP_Z_INNER[0]), (a.STRAP_Z_INNER[1], a.STRAP_Z_INNER[1] + bg.THICKNESS)]
    cam_z = [(z0, z0 + cg.CAM_LEN) for z0 in a.CAM_Z0]
    boss_z = [(z0 + cg.BOSS_Z - cg.BOSS_DIA / 2, z0 + cg.BOSS_Z + cg.BOSS_DIA / 2) for z0 in a.CAM_Z0]
    boss_strap_axial = [s[0] - bz[1] for s, bz in zip(strap_z, boss_z, strict=True)]
    # boss tip vs strap if its z band overlaps the strap
    boss_reach = E + RC + cg.BOSS_PROUD
    boss_path_air = min(
        seg_dist((a.LIFT_X + boss_reach * math.sin(ar), a.LIFT_Y - boss_reach * math.cos(ar)), PV, rot(AR, b)) - R_END
        for ar, b, _ in path
    )
    rear_block_air = a.BLOCK_BACK_Z0 - strap_z[1][1]
    front_block_air = strap_z[0][0] - (a.BLOCK_FRONT_Z0 + a.BLOCK_DEPTH)
    # pivot block webs (block local: pivot bore at (-h, 0), lift at (+h, H))
    h, H = pb.BORE_HALF_SPACING, pb.LIFT_BORE_RISE
    sr = pb.SCREW_HOLE_DIA / 2
    hr = a.BSCREW_HEAD_DIA / 2
    block = {
        "bore_to_bore_web": math.hypot(2 * h, H) - pb.BORE_DIA,
        "pivot_bore_to_screw_web": pb.SCREW_HALF_SPACING - h - pb.BORE_DIA / 2 - sr,
        "lift_bore_to_screw_web": math.hypot(pb.SCREW_HALF_SPACING - h, H) - pb.BORE_DIA / 2 - sr,
        "screw_hole_to_end_web": pb.BLOCK_WIDTH / 2 - pb.SCREW_HALF_SPACING - sr,
        "screw_head_rim": pb.BLOCK_WIDTH / 2 - pb.SCREW_HALF_SPACING - hr,
        "lift_bore_top_web": pb.BLOCK_TOP_Y - H - pb.BORE_DIA / 2,
        "lift_bore_bottom_web": pb.BORE_UP + H - pb.BORE_DIA / 2,
        "pivot_bore_top_web": pb.BLOCK_TOP_Y - pb.BORE_DIA / 2,
        "screw_hole_dia": pb.SCREW_HOLE_DIA,
        "head_dia": a.BSCREW_HEAD_DIA,
    }
    # cam wall: nominal, printed bands (OD+-0.05 dia, ECC+-0.05, bore max 6.375), and +-0.10 bands
    wall_nom = cg.CAM_OD / 2 - cg.BORE / 2 - E
    wall_p05 = (cg.CAM_OD - 0.05) / 2 - 6.375 / 2 - (E + 0.05)
    wall_p10 = (cg.CAM_OD - 0.10) / 2 - 6.375 / 2 - (E + 0.10)
    # strap webs
    seat_rect_web = math.hypot(R_END - bg.PIN_SEAT, -bg.PIN_DROP - bg.PIN_BORE / 2) - bg.PIVOT_BORE / 2
    strap = {
        "arbor_bore_end_wall": R_END - bg.ARBOR_BORE / 2,
        "pivot_bore_end_wall": R_END - bg.PIVOT_BORE / 2,
        "pin_seat_face_web": (bg.THICKNESS - bg.PIN_BORE) / 2,
        "pin_seat_to_pivot_bore_true_web": seat_rect_web,
        "pin_seat_to_pivot_bore_module_metric": math.hypot(R_END - bg.PIN_SEAT, bg.PIN_DROP) - bg.PIN_BORE / 2 - bg.PIVOT_BORE / 2,
    }
    out.update(
        anchors={k: g.get(k) for k in (
            "APINION_X", "APINION_Y", "PIVOT_X", "PIVOT_Y", "LIFT_X", "LIFT_Y", "STRAP_LEAN_DEG",
            "BLOCK_X", "BLOCK_BACK_Z0", "BLOCK_FRONT_Z0", "SPRING_X", "SPRING_HOLE_X", "SPRING_Z")},
        linkage={
            "park_gap": a._PARK_GAP,
            "need_lift": a._NEED_LIFT,
            "cam_reach_past_touch": (a.FPIN_DIA + cg.CAM_OD) / 2 - a._D_ENG,
            "cam_engage_rotation_deg": a.CAM_ENGAGE_ROTATION_DEG,
            "lever_engaged_tilt_deg": a.LEVER_ENGAGED_TILT_DEG,
            "engage_swing_deg": math.degrees(PHI),
            "pin_tip_reserve_engaged": a._FPIN_TIP_S - a._S_CAM_ENG,
            "s_cam_park": a._S_CAM,
            "lever_arbor_stub_clear": a._LEV_STUB_D - (a.ARBOR_DIA + max(a.LEVER_ROD_DIA, a.LEVER_ROD_TIP_DIA)) / 2,
        },
        strap_vs_collar={
            "park_air": strap_air(0.0, 0.0),
            "engaged_air": strap_air(AE, PHI),
            "path_min_air": pmin[2],
            "path_min_at_cam_deg": math.degrees(pmin[0]),
            "rect_min_air_any_cam_any_swing": rect,
            "collar_strap_axial_overlap": [max(0.0, min(s[1], c[1]) - max(s[0], c[0])) for s, c in zip(strap_z, cam_z, strict=True)],
            "boss_to_strap_axial_air": boss_strap_axial,
            "boss_tip_path_min_air_if_z_overlaps": boss_path_air,
        },
        sweeps={
            "boss_sweep_vs_base": a.LIFT_Y - a._CAM_SWEEP_R - a.Y_BASE_TOP,
            "collar_sweep_vs_spring_foot": a.LIFT_Y - a._COLLAR_SWEEP_R - a.SPRING_FOOT_TOP,
            "sweep_vs_pivot_shaft": math.hypot(a.PIVOT_X - a.LIFT_X, a.PIVOT_Y - a.LIFT_Y) - a._CAM_SWEEP_R - 3.175,
            "lever_hub_bottom_vs_base": a.LIFT_Y - 6.5 - a.Y_BASE_TOP,
            "spring_screw_head_vs_lift_rod": (a.SPRING_HOLE_X - a.FSCREW_HEAD_DIA / 2) - (a.LIFT_X + 3.175),
        },
        axial={"rear_block_air": rear_block_air, "front_block_air": front_block_air, "strap_z": strap_z, "cam_z": cam_z},
        pivot_block=block,
        cam={"wall_nom": wall_nom, "wall_worst_pm05": wall_p05, "wall_worst_pm10": wall_p10, "od": cg.CAM_OD, "ecc": E,
             "lift_bore_rise": pb.LIFT_BORE_RISE, "bore_half_spacing": h},
        strap=strap,
        base_required={
            "block_screw_xz": [list(t) for t in a._BLOCK_SCREW_XZ],
            "block_screw_xz_base_has": [list(t) for t in a.BASE_BLOCK_XZ],
            "foot_screw_xz": [list(t) for t in a._FOOT_SCREW_XZ],
            "foot_screw_xz_base_has": [list(t) for t in a.BASE_FOOT_XZ],
            "mechanism_z_shift": a.MECHANISM_Z_SHIFT,
        },
    )
    return out


if __name__ == "__main__":
    opt = sys.argv[1]
    spec = OPTIONS.get(opt)
    if spec is None:
        spec = json.loads(Path(sys.argv[2]).read_text())
    print(json.dumps(main(opt, spec), indent=1, default=str))
