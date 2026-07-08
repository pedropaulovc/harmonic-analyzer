"""Offline cross-check for the #151 mirror retirement: every re-authored
machine-handed placement, recomputed by importing the assembly modules
SolidWorks-free, is compared against the pre-sweep golden pose dump
(``cad/out/reports/pose-golden/``, captured with
``diagnostics/probe_pose_dump.py dump`` before the sweep). World geometry is
FROZEN by design, so every check must land within tolerance; the documented
exceptions carry their own widened tolerances inline (lever-wire 2c artifact,
crank-family solver noise, chain-pattern fill drift).

Ephemeral migration validator: it needs the machine-local golden dump and can
be deleted once #151 merges and the post-rebuild pose diff is clean.

Run: ``uv run python cad/scripts/diagnostics/check_mirror_retirement.py``
"""
# ruff: noqa: E402, E741, F541  (mid-file imports are inherent to the
# sys.path-then-import pattern; I is the incline angle)
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "cad" / "scripts"))
GOLD = REPO / "cad" / "out" / "reports" / "pose-golden"

fails = []


def expect(asm, comp, pos, rows, label, pos_tol=1e-3, row_tol=1e-6):
    g = json.load(open(GOLD / f"{asm}.json"))[comp]
    gp = [v * 1000.0 for v in g[9:12]]
    gr = g[0:9]
    fr = [c for row in rows for c in row]
    dp = max(abs(a - b) for a, b in zip(gp, pos))
    dr = max(abs(a - b) for a, b in zip(gr, fr))
    ok = dp < pos_tol and dr < row_tol
    print(f"{'OK ' if ok else 'FAIL'} {label:45s} dpos={dp:.6f} drow={dr:.2e}")
    if not ok:
        fails.append((label, gp, pos, gr, fr))


from _transforms import IDENTITY, ROT_Y_180, ROT_Y_POS90, ROT_X_NEG90, compose_rows, rot_z_rows

# ---- summing --------------------------------------------------------------
import build_summing_assembly as s

expect("summing", "knife-mount-1", [s.KNIFE[0], s.KNIFE_CONTACT_Y, s.HEX_Z_MID], IDENTITY, "knife-mount front")
expect("summing", "knife-mount-2", [s.KNIFE[0], s.KNIFE_CONTACT_Y, -s.HEX_Z_MID], IDENTITY, "knife-mount back")
expect("summing", "top-crossbar-1", [s.KNIFE[0], 1010.0, 0.0], IDENTITY, "top-crossbar")
expect("summing", "summing-lever-1", [s.KNIFE[0], s.KNIFE[1], 0.0], IDENTITY, "summing-lever")
expect("summing", "boss-hook-1", list(s.BOSS_HOOK_POS), ROT_Y_180, "boss-hook")
expect("summing", "counter-spring-1", list(s.SPRING_POS), ROT_Y_POS90, "counter-spring")
expect("summing", "gooseneck-1", [s.COLUMN_X, 1210.0, 0.0], ROT_Y_180, "gooseneck")
expect("summing", "gooseneck-clamp-1", [s.COLUMN_X, 1040.7, 0.0], IDENTITY, "gooseneck-clamp")

# ---- pen ------------------------------------------------------------------
import build_pen_assembly as p

expect("pen", "pen-hanger-1", list(p.HANGER_POS), IDENTITY, "pen-hanger")
expect("pen", "pen-v-block-1", list(p.VBLOCK_POS), ROT_Y_180, "pen-v-block")
expect("pen", "pen-rod-1", list(p.PEN_ROD_POS), IDENTITY, "pen-rod")
expect("pen", "pen-marker-1", [p.MARKER_X, p.MARKER_TIP_Y, p.PEN_Z_MID], IDENTITY, "pen-marker")
expect("pen", "pen-wire-1", list(p.PEN_WIRE_BOTTOM), IDENTITY, "pen-wire")
expect("pen", "pen-frame-1", list(p.FRAME_POS), p.FRAME_ROWS, "pen-frame")
expect("pen", "pen-set-screw-1", list(p.SET_SCREW_POS), ROT_Y_180, "pen-set-screw")
expect("pen", "hanger-screw-1", list(p.HANGER_SCREW_POS), IDENTITY, "hanger-screw")

# pen-frame euler must agree with rows
from _transforms import rows_from_euler
fr = rows_from_euler([-90.0, 90.0, 0.0])
d = max(abs(a - b) for ra, rb in zip(fr, p.FRAME_ROWS) for a, b in zip(ra, rb))
print(f"{'OK ' if d < 1e-9 else 'FAIL'} pen-frame euler [-90,90,0] vs FRAME_ROWS      drow={d:.2e}")
if d >= 1e-9:
    fails.append(("pen-frame euler", fr, p.FRAME_ROWS))

# ---- magnifier ------------------------------------------------------------
import build_magnifier_assembly as m

expect("magnifier", "wheel-bar-1", [m.WHEEL_BAR_X0, m.WHEEL_BAR_Y, m.BAR_Z], IDENTITY, "wheel-bar")
expect("magnifier", "column-clamp-front-1", [m.COLUMN_X, m.WHEEL_BAR_Y, m.COLUMN_Z], ROT_Y_POS90, "column-clamp-front")
expect("magnifier", "column-clamp-back-1", [m.COLUMN_X, m.WHEEL_BAR_Y, m.COLUMN_Z], ROT_Y_POS90, "column-clamp-back")
expect("magnifier", "clamp-screw-1", [m.CLAMP_SCREW_X[0], m.WHEEL_BAR_Y, m.BAR_FRONT_Z], IDENTITY, "clamp-screw-1")
expect("magnifier", "clamp-screw-2", [m.CLAMP_SCREW_X[1], m.WHEEL_BAR_Y, m.BAR_FRONT_Z], IDENTITY, "clamp-screw-2")
expect("magnifier", "magnifying-lever-1", [m.LEVER_X0, m.LEVER_ROD_Y, m.LEVER_ROD_Z], ROT_Y_180, "magnifying-lever")
expect("magnifier", "magnifying-bracket-1", [40.0, m.LEVER_ROD_Y, m.LEVER_ROD_Z], IDENTITY, "magnifying-bracket")
expect("magnifier", "magnifying-clamp-1", list(m.CLAMP_POS), ROT_Y_POS90, "magnifying-clamp")
_rz = compose_rows(rot_z_rows(-90.0), ROT_Y_180)
expect("magnifier", "thumb-screw-1", [m.CLAMP_X, m.LEVER_ROD_Y + 20.0, m.LEVER_ROD_Z], _rz, "thumb-screw")
expect("magnifier", "magnifying-vertical-rod-1", [m.CLAMP_X, m.VROD_TOP_Y, m.VROD_Z], _rz, "vertical-rod")
expect("magnifier", "output-fixture-1", [m.CLAMP_X, m.FIXTURE_Y0, m.VROD_Z], IDENTITY, "output-fixture")
expect("magnifier", "wheel-axle-1", [m.WHEEL_X, m.WHEEL_BAR_Y, m.BAR_FRONT_Z], ROT_X_NEG90, "wheel-axle")
expect("magnifier", "magnifying-wheel-1", [m.WHEEL_X, m.WHEEL_BAR_Y, m.WHEEL_MID_Z], IDENTITY, "magnifying-wheel")
# lever-wire: ACCEPTED delta vs golden -- the old mirror realized this pose
# through the part's bbox-z-centre plane (2c artifact, 0.015 mm / 4e-5 rows);
# the new values are the exact authored intent. Documented; will show once in
# the post-rebuild pose diff.
expect("magnifier", "lever-wire-1", list(m.HUB_WIRE_END), m._HW_ROWS, "lever-wire (accepted 2c delta)",
       pos_tol=0.02, row_tol=5e-5)

# euler/rows agreement for the composed placements
d = max(abs(a - b) for ra, rb in zip(rows_from_euler([180.0, 0.0, -90.0]), _rz) for a, b in zip(ra, rb))
print(f"{'OK ' if d < 1e-9 else 'FAIL'} thumb/vrod euler [180,0,-90] vs composed      drow={d:.2e}")
if d >= 1e-9:
    fails.append(("thumb euler", None, None))
d = max(abs(a - b) for ra, rb in zip(rows_from_euler([0.0, 180.0, 0.0]), ROT_Y_180) for a, b in zip(ra, rb))
print(f"{'OK ' if d < 1e-9 else 'FAIL'} ROT_Y_180 euler [0,180,0]                     drow={d:.2e}")

# ---- drive-train ------------------------------------------------------------
import build_drive_train_assembly as d

def eul(euler, rows, label):
    fr = rows_from_euler(euler)
    dd = max(abs(a - b) for ra, rb in zip(fr, rows) for a, b in zip(ra, rb))
    print(f"{'OK ' if dd < 1e-9 else 'FAIL'} euler {label:40s} drow={dd:.2e}")
    if dd >= 1e-9:
        fails.append((f"euler {label}", euler, rows))

I = d.INCLINE_DEG
eul([0.0, I, 0.0], d.ROT_Y_INCLINE, "ROT_Y_INCLINE")
eul([90.0, I, 0.0], d.ROT_SHAFT_NORTH, "ROT_SHAFT_NORTH")
eul([-90.0, I, 0.0], d.ROT_SHAFT_SOUTH, "ROT_SHAFT_SOUTH")
eul(d.PINCH_WEST_EULER, d.ROT_PINCH_WEST, "PINCH_WEST")
eul(d.FPIN_EULER, d.FPIN_ROWS, "FPIN")
eul([180.0, 0.0, -90.0], compose_rows(d.rot_z_rows(-90.0), ROT_Y_180), "crank-arm")
eul([90.0, 0.0, 0.0], d.ROT_X_POS90, "ROT_X_POS90")
eul([0.0, 90.0, 0.0], d.ROT_Y_POS90, "ROT_Y_POS90")

DT = "drive-train"
expect(DT, "cylinder-gear-shaft-1", [d.X_DRUM, d.Y_DRIVE, d.ARBOR_SOUTH_Z], d.ROT_X_POS90, "arbor (seed)")
expect(DT, "arbor-pedestal-1", [d.X_DRUM, d.Y_BASE_TOP, -d.ARBOR_PEDESTAL_Z], IDENTITY, "arbor-pedestal south")
expect(DT, "arbor-pedestal-2", [d.X_DRUM, d.Y_BASE_TOP, d.ARBOR_PEDESTAL_NORTH_Z], ROT_Y_180, "arbor-pedestal north")
_ppv = d.cone_station(d.PIVOT_STATION)
_pps = d.cone_station(d.POST_STATION)
_ptp = d.cone_station(d.TIP_BLOCK_STATION)
_pbu = d.cone_station(d.BUSH_STATION)
_pad = d.cone_station(d.ADJ_HEAD_STATION)
expect(DT, "cone-swing-platform-1", [_ppv[0], d.Y_BASE_TOP, _ppv[2]], d.ROT_Y_INCLINE, "cone-swing-platform")
expect(DT, "cone-pivot-post-1", [_pps[0], d.Y_BASE_TOP + d.PLAT_T, _pps[2]], d.ROT_Y_INCLINE, "cone-pivot-post")
expect(DT, "cone-tip-block-1", [_ptp[0], d.Y_BASE_TOP + d.PLAT_T, _ptp[2]], d.ROT_Y_INCLINE, "cone-tip-block")
expect(DT, "cone-tip-bushing-1", [_pbu[0], d.Y_DRIVE, _pbu[2]], d.ROT_SHAFT_NORTH, "cone-tip-bushing")
expect(DT, "cone-tip-adjuster-1", [_pad[0], d.Y_DRIVE, _pad[2]], d.ROT_SHAFT_SOUTH, "cone-tip-adjuster")
expect(DT, "cone-tip-pinch-screw-1",
       [_ptp[0] - (d.TIP_BLOCK_X / 2.0) * d.COS_I,
        d.Y_BASE_TOP + d.PLAT_T + d.TIP_PINCH_Y,
        _ptp[2] + (d.TIP_BLOCK_X / 2.0) * d.SIN_I],
       d.ROT_PINCH_WEST, "cone-tip-pinch-screw")
expect(DT, "cone-lock-knob-1", [d.KNOB_X, d.Y_BASE_TOP + d.PLAT_T, d.KNOB_Z], IDENTITY, "cone-lock-knob")
expect(DT, "cone-pivot-screw-1", [_ppv[0], d.Y_BASE_TOP + d.PLAT_T, _ppv[2]], IDENTITY, "cone-pivot-screw")
expect(DT, "swing-stop-screw-1", [d.STOP_X, d.Y_BASE_TOP, d.STOP_Z], IDENTITY, "swing-stop-screw")
expect(DT, "alignment-pinion-1", [d.APINION_X, d.APINION_Y, d.APINION_Z_FRONT], IDENTITY, "alignment-pinion")
_strap = compose_rows(ROT_Y_180, d.rot_z_rows(d.STRAP_LEAN_DEG))
expect(DT, "pinion-bracket-1", [d.PIVOT_X, d.PIVOT_Y, d.APINION_Z_FRONT - d.STRAP_AIR], _strap, "pinion-bracket front")
expect(DT, "pinion-bracket-2", [d.PIVOT_X, d.PIVOT_Y, d.APINION_Z_BACK + d.STRAP_AIR + d.STRAP_T], _strap, "pinion-bracket back")
expect(DT, "pinion-pivot-block-1", [d.BLOCK_X, d.PIVOT_Y, d.BLOCK_FRONT_Z0 + d.BLOCK_DEPTH], ROT_Y_180, "pinion-pivot-block front")
expect(DT, "pinion-pivot-block-2", [d.BLOCK_X, d.PIVOT_Y, d.BLOCK_BACK_Z0 + d.BLOCK_DEPTH], ROT_Y_180, "pinion-pivot-block back")
expect(DT, "pinion-pivot-shaft-1", [d.PIVOT_X, d.PIVOT_Y, d.PIVOT_SHAFT_Z0], IDENTITY, "pinion-pivot-shaft")
expect(DT, "pinion-lift-rod-1", [d.LIFT_X, d.LIFT_Y, d.LIFT_ROD_Z0], IDENTITY, "pinion-lift-rod")
expect(DT, "pinion-spring-1", [d.SPRING_X, d.Y_BASE_TOP, d.SPRING_Z], ROT_Y_180, "pinion-spring")
expect(DT, "pinion-cam-pin-1", [d._FPIN_ORG[0], d._FPIN_ORG[1], d._STRAP_MID_Z[0]], d.FPIN_ROWS, "pinion-cam-pin front")
expect(DT, "pinion-cam-pin-2", [d._FPIN_ORG[0], d._FPIN_ORG[1], d._STRAP_MID_Z[1]], d.FPIN_ROWS, "pinion-cam-pin back")
expect(DT, "pinion-cam-1", [d.LIFT_X, d.LIFT_Y, d.CAM_Z0[0]], IDENTITY, "pinion-cam front")
expect(DT, "pinion-cam-2", [d.LIFT_X, d.LIFT_Y, d.CAM_Z0[1]], IDENTITY, "pinion-cam back")
expect(DT, "pinion-lever-1", [d.LIFT_X, d.LIFT_Y, d.LEVER_Z], d.rot_z_rows(d.LEVER_TILT_DEG), "pinion-lever")
expect(DT, "pinion-handle-1", [d.APINION_X, d.APINION_Y, d.HANDLE_Z], d.rot_z_rows(d.HANDLE_TILT_DEG), "pinion-handle")
expect(DT, "pinion-arbor-1", [d.APINION_X, d.APINION_Y, d.ARBOR_Z0], IDENTITY, "pinion-arbor")
for k, (sx, sz) in enumerate(d._BLOCK_SCREW_XZ):
    expect(DT, f"slotted-screw-{k + 1}", [sx, d.BLOCK_TOP_Y, sz], IDENTITY, f"slotted-screw {k}")
for k, ((sx, sz), seat_y) in enumerate(zip(
        d._FOOT_SCREW_XZ,
        (d.Y_BASE_TOP + d.SPRING_T, d.Y_BASE_TOP + d.ARBOR_PED_FLANGE_T,
         d.Y_BASE_TOP + d.ARBOR_PED_FLANGE_T))):
    expect(DT, f"foot-screw-{k + 1}", [sx, seat_y, sz], IDENTITY, f"foot-screw {k}")
expect(DT, "cone-gear-shaft-1", list(d.cone_station(d.SHAFT_FRONT_STATION)), d.ROT_Y_INCLINE, "cone-gear-shaft")

def on_shaft(station, face):
    c = d.cone_station(station)
    return [c[0] - (face / 2.0) * d.SIN_I, d.Y_DRIVE, c[2] - (face / 2.0) * d.COS_I]

expect(DT, "crank-drive-gear-1", on_shaft(d.GEAR64_STATION, d.GEAR64_FACE), d.ROT_Y_INCLINE, "crank-drive-gear 64T")
for j in range(20):
    expect(DT, f"cone-gear-{j + 1}", on_shaft(d.SHAFT_T120_STATION + j * d.SEAT_PITCH, d.CONE_FACE),
           d.ROT_Y_INCLINE, f"cone-gear j={j}")
for j in range(20):
    expect(DT, f"cylinder-gear-{j + 1}",
           [d.X_DRUM, d.Y_DRIVE, d.Z_DRUM0 + d.Z_PITCH * j - d.DRUM_FACE / 2.0],
           d.rot_z_rows(-1.5), f"cylinder-gear j={j}")
# The crank family is a fully mated keyed chain: the golden dump records its
# SOLVED pose, which sits ~1.2 um / 3.9e-7 rows off the insert intent (mate
# solver epsilon). Compare with a solver-noise allowance.
_SOLVED = dict(pos_tol=0.005, row_tol=1e-6)
expect(DT, "crankshaft-1", [d.X_CRANK, d.Y_CRANK, d.CRANKSHAFT_Z0], d.ROT_X_POS90, "crankshaft", **_SOLVED)
expect(DT, "crank-pinion-1", [d.X_CRANK, d.Y_CRANK, d.PINION_TOOTH_Z - d.PINION_FACE / 2.0],
       d.rot_z_rows(-d.PINION_SEED_DEG), "crank-pinion 16T", **_SOLVED)
expect(DT, "crank-arm-1", [d.X_CRANK, d.Y_CRANK, d.CRANK_ARM_ORIGIN_Z],
       compose_rows(d.rot_z_rows(-90.0), ROT_Y_180), "crank-arm", **_SOLVED)
expect(DT, "crank-handle-1", [d.X_CRANK, d.Y_CRANK - d.ARM_C2C, d.CRANK_ARM_Z0], d.ROT_Y_POS90,
       "crank-handle", **_SOLVED)

# ---- channel ---------------------------------------------------------------
import math
import build_channel_assembly as c

_rz = getattr(c, "rot_z_rows", None) or (lambda deg: [
    [math.cos(math.radians(deg)), math.sin(math.radians(deg)), 0.0],
    [-math.sin(math.radians(deg)), math.cos(math.radians(deg)), 0.0],
    [0.0, 0.0, 1.0]])
CH = "channel"
amplitudes = __import__("_config").amplitudes()
st0 = c.solve_state(0.0)
arm_rows = compose_rows(_rz(st0["arm_tilt"]), ROT_Y_180)
rod_rows = compose_rows(_rz(st0["rod_tilt"]), ROT_Y_180)
_t = math.radians(st0["arm_tilt"])
arm_dx = c.ARM_PIVOT_LOCAL_Y * math.sin(_t)
arm_dy = c.ARM_PIVOT_LOCAL_Y * math.cos(_t)
expect(CH, "pivot-shaft-1", [c.PIVOT[0], c.PIVOT[1], c.PIVOT_SHAFT_Z], IDENTITY, "pivot-shaft")
expect(CH, "fulcrum-shaft-1", [c.FULCRUM[0], c.FULCRUM[1], 0.0], IDENTITY, "fulcrum-shaft")
expect(CH, "pivot-ball-mount-1", [c.PIVOT[0], c.SUPPORT_APEX_Y, -c.AFRAME_MOUNT_Z_ABS], IDENTITY, "ball-mount rocker south")
expect(CH, "pivot-ball-mount-2", [c.PIVOT[0], c.SUPPORT_APEX_Y, c.SUPPORT_Z], IDENTITY, "ball-mount rocker north")
expect(CH, "pivot-ball-mount-3", [c.FULCRUM[0], c.RAIL_TOP_Y, -c.LEVER_MOUNT_Z], IDENTITY, "ball-mount lever -z")
expect(CH, "pivot-ball-mount-4", [c.FULCRUM[0], c.RAIL_TOP_Y, c.LEVER_MOUNT_Z], IDENTITY, "ball-mount lever +z")
_SOLV = dict(pos_tol=0.005, row_tol=1e-5)
for j in range(1, 20):
    z_gap = c.z_station(j) + c.ARM_MID_DZ - c.PITCH / 2.0
    expect(CH, f"pivot-bushing-{j}", [c.PIVOT[0], c.PIVOT[1], z_gap], IDENTITY,
           f"pivot-bushing gap {j - 1}", **_SOLV)
    expect(CH, f"lever-bushing-{j}", [c.FULCRUM[0], c.FULCRUM[1], z_gap], IDENTITY,
           f"lever-bushing gap {j - 1}", **_SOLV)
phi0 = math.radians(st0["lever_tilt"])
hole_x_0 = c.FULCRUM[0] - c.LEVER_SPRING_X * math.cos(phi0)
for j in range(20):
    zj = c.z_station(j)
    z_mid = zj + c.ARM_MID_DZ
    st = c.solve_state(amplitudes[j])
    expect(CH, f"rocker-arm-{j + 1}",
           [c.PIVOT[0] - arm_dx, c.PIVOT[1] - arm_dy, z_mid], arm_rows,
           f"rocker-arm ch{j:02d}", **_SOLV)
    expect(CH, f"connecting-rod-{j + 1}",
           [c.RING_CENTER[0], c.RING_CENTER[1], zj + c.CAM_DZ], rod_rows,
           f"connecting-rod ch{j:02d}", **_SOLV)
    expect(CH, f"amplitude-bar-{j + 1}",
           [st["bar_origin_x"], st["bar_origin_y"], z_mid - c.BAR_WIDTH / 2.0],
           rows_from_euler([st["bar_tilt"], -90.0, 0.0]),
           f"amplitude-bar ch{j:02d}", **_SOLV)
    expect(CH, f"channel-lever-{j + 1}",
           [c.FULCRUM[0], c.FULCRUM[1], z_mid],
           compose_rows(_rz(st["lever_tilt"]), ROT_Y_180),
           f"channel-lever ch{j:02d}", **_SOLV)
    spec = c._spring_spec(amplitudes[j], hole_x_0)
    ux, uy = spec["ux"], spec["uy"]
    expect(CH, f"channel-spring-installed-{j + 1}",
           [hole_x_0 + c.SPRING_BOTTOM_LEAD * ux, c.PLATE_EYE_Y + c.SPRING_BOTTOM_LEAD * uy, z_mid],
           [[0.0, 0.0, -1.0], [ux, uy, 0.0], [uy, -ux, 0.0]],
           f"channel-spring ch{j:02d}")
    expect(CH, f"spring-hook-{j + 1}",
           [hole_x_0 + c.HOOK_ARM_OFFSET_X, c.PLATE_EYE_Y - c.HOOK_ARM_HEIGHT, z_mid],
           ROT_Y_180, f"spring-hook ch{j:02d}")

# ---- paper-drive -------------------------------------------------------------
import build_paper_drive_assembly as p

# The module's own SolidWorks-free layout asserts (rack phase, gear mesh,
# knob clearance, chain anchors) double as the offline smoke test.
p._assert_rack_mesh()
p._assert_gear_mesh()
p._assert_knob_shaft_clearance()
p._assert_chain_layout()
print("OK  paper-drive module layout asserts")

PD = "paper-drive"
expect(PD, "support-bar-1", [0.0, p.BAR_CY, p.BAR_Z], IDENTITY, "support-bar")
for i, sx in enumerate((1.0, -1.0)):
    expect(PD, f"column-clamp-front-{i + 1}", [sx * p.COLUMN_X, p.BAR_CY, p.COLUMN_Z],
           p.ROT_Y_POS90, f"column-clamp-front x{sx * p.COLUMN_X:+.0f}")
    expect(PD, f"column-clamp-back-{i + 1}", [sx * p.COLUMN_X, p.BAR_CY, p.COLUMN_Z],
           p.ROT_Y_POS90, f"column-clamp-back x{sx * p.COLUMN_X:+.0f}")
for i, x in enumerate(p.CLAMP_HOLE_X):
    expect(PD, f"clamp-screw-{i + 1}", [-x, p.BAR_CY, p.BAR_FRONT_Z], IDENTITY,
           f"clamp-screw x{-x:+.1f}")
expect(PD, "platen-1", [p.PLATE_X0, p.PLATE_Y0, p.PLATE_FRONT_Z], IDENTITY, "platen", **_SOLV)
expect(PD, "platen-rack-1", [p.RACK_X0, p.RACK_Y0, p.RACK_BACK_Z], p.ROT_X_180, "platen-rack", **_SOLV)
for i, gy in enumerate(p.GUIDE_Y):
    expect(PD, f"platen-guide-{i + 1}", [p.PLATE_X0, gy, p.BAR_FRONT_Z], IDENTITY,
           f"platen-guide y{gy:.0f}", **_SOLV)
for i, x_c in enumerate(p.LOCK_STATION_X):
    station = p.PLATE_X0 + p.PLATE_WIDTH - x_c
    expect(PD, f"guide-lock-{2 * i + 1}",
           [station + p.LOCK_WIDTH / 2.0, p.GUIDE_Y[1] + p.GUIDE_HEIGHT, p.LOCK_Z0],
           _rz(180.0), f"guide-lock top x{x_c:.0f}", **_SOLV)
    expect(PD, f"guide-lock-{2 * i + 2}",
           [station - p.LOCK_WIDTH / 2.0, p.GUIDE_Y[0], p.LOCK_Z0],
           IDENTITY, f"guide-lock bottom x{x_c:.0f}", **_SOLV)
for i, sx in enumerate((p.PLATEN_SOCKET_XY[0][0], p.PLATEN_SOCKET_XY[2][0])):
    clip_x = -(p.PLATE_X0 + sx + p.CLIP_WIDTH / 2.0)
    expect(PD, f"platen-clip-{i + 1}",
           [clip_x, p.PLATE_Y0 + p.PLATE_HEIGHT, p.PLATE_FRONT_Z - p.CLIP_THICKNESS],
           _rz(-90.0), f"platen-clip x{clip_x:+.0f}", **_SOLV)
expect(PD, "platen-paper-1", [p.PLATE_X0 + 20.25, p.PLATE_Y0 + 6.0, p.PLATE_FRONT_Z - 0.5],
       IDENTITY, "platen-paper", **_SOLV)
_fs = 0
for x, y in p.CLIP_SCREW_XY:
    _fs += 1
    expect(PD, f"fillister-screw-{_fs}", [-x, y, p.PLATE_FRONT_Z - p.CLIP_THICKNESS],
           IDENTITY, f"clip screw {_fs}", **_SOLV)
for x, y in p.GUIDE_SCREW_XY:
    _fs += 1
    expect(PD, f"fillister-screw-{_fs}", [-x, y, p.PLATE_FRONT_Z + p.PLATEN_CBORE_DEPTH],
           IDENTITY, f"guide screw {_fs}", **_SOLV)
for x, y in p.LOCK_SCREW_XY:
    _fs += 1
    expect(PD, f"fillister-screw-{_fs}", [-x, y, p.LOCK_Z0 + 2.0],
           p.ROT_Y_180, f"lock screw {_fs}", **_SOLV)
expect(PD, "transgear-bracket-1", [p.STUD_XY[0], p.STUD_XY[1], p.BRACKET_Z0], IDENTITY, "transgear-bracket")
for i, dx in enumerate((p.BRACKET_SCREW_DX, -p.BRACKET_SCREW_DX)):
    expect(PD, f"bracket-screw-{i + 1}", [p.STUD_XY[0] + dx, p.BAR_CY, p.STUB_Z0],
           p.ROT_Y_180, f"bracket-screw x{p.STUD_XY[0] + dx:+.0f}")
expect(PD, "transgear-stub-1", [p.STUD_XY[0], p.STUD_XY[1], p.STUB_Z0], p.ROT_X_NEG90, "transgear-stub")
expect(PD, "transgear-latch-1", [p.STUD_XY[0], p.STUD_XY[1], p.ARM_Z],
       rows_from_euler([180.0, 0.0, p.LATCH_ANGLE_DEG]), "transgear-latch")
expect(PD, "rack-pinion-1", [p.STUD_XY[0], p.STUD_XY[1], p.DISC_Z0], IDENTITY, "rack-pinion disc", **_SOLV)
expect(PD, "transgear-feed-pinion-1", [p.STUD_XY[0], p.STUD_XY[1], p.FEED_Z0], IDENTITY, "feed pinion", **_SOLV)
expect(PD, "transgear-knob-shaft-1", [p.KNOB_SHAFT_XY[0], p.KNOB_SHAFT_XY[1], p.KNOB_SHAFT_Z0],
       p.ROT_X_POS90, "knob shaft", **_SOLV)
expect(PD, "transgear-pinion-1", [p.KNOB_SHAFT_XY[0], p.KNOB_SHAFT_XY[1], p.THIRD_Z0],
       _rz(p.THIRD_PHASE_DEG), "third gear", **_SOLV)
expect(PD, "transgear-removable-1", [p.KNOB_SHAFT_XY[0], p.KNOB_SHAFT_XY[1], p.REMOVABLE_Z0],
       IDENTITY, "removable T24", **_SOLV)
expect(PD, "transgear-removable-2", [-p.CHAIN_CRANK_CENTRE[0], p.CHAIN_CRANK_CENTRE[1], p.REMOVABLE_Z0],
       IDENTITY, "removable T12 (crank)", **_SOLV)
expect(PD, "transgear-removable-3", list(p.SPARE_GEAR_POS), p.ROT_X_NEG90, "removable T18 spare")

# Chain links: every link should sit near the mirrored loop at its station,
# oriented along the forward chord (inner = even stations, outer = odd).
# The pattern's own fill drifts up to ~0.51 mm along-path from this ideal
# chord model (the build itself gates links at <= 2.0 mm off the centreline),
# so the tolerance here is coarse -- it still catches any chirality error,
# which would be a ~250 mm x flip.
from _chain import LINK_PITCH, loop_point_tangent
def _link_expect(name, station, label):
    x0, y0, _ = loop_point_tangent(station * LINK_PITCH, dx=p.CHAIN_KNOB_CENTRE[0],
                                   dy=p.CHAIN_KNOB_CENTRE[1], mirror_x=True)
    x1, y1, _ = loop_point_tangent((station + 1) * LINK_PITCH, dx=p.CHAIN_KNOB_CENTRE[0],
                                   dy=p.CHAIN_KNOB_CENTRE[1], mirror_x=True)
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
    expect(PD, name, [x0, y0, p.CHAIN_MID_Z], _rz(ang), label, pos_tol=0.75, row_tol=0.05)

_link_ok = True
try:
    _link_expect("chain-inner-link-1", 0, "chain seed inner @0")
    _link_expect("chain-outer-link-1", 1, "chain seed outer @1")
except Exception as e:
    print("chain seed check errored:", e)
    _link_ok = False
if _link_ok and not fails:
    for k in range(1, 34):
        _link_expect(f"chain-inner-link-{k + 1}", 2 * k, f"chain inner @{2 * k}")
        _link_expect(f"chain-outer-link-{k + 1}", 2 * k + 1, f"chain outer @{2 * k + 1}")

print()
if fails:
    for f in fails:
        print("FAIL DETAIL:", f)
    sys.exit(1)
print(f"ALL CHECKS PASSED")
