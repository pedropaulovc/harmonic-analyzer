"""#1038 S5a evidence: the K5 keeper relief, one corner (front-west), to scale.

Run from the slice worktree:  uv run --frozen python C:/farm-runs/repitch-s5a/keeper_relief_sketch.py
Every number is read from the pure modules (no SolidWorks).
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "cad" / "scripts"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, Rectangle, Wedge

import build_fr_top_frame as b
import ch_fulcrum_keeper_spec as k
import fr_top_frame_spec as s

R = b.BOSS_DIA / 2.0
d = s.KEEPER_BOSS_RELIEF_FROM_SOCKET
cx, cz = b.COLUMN_X, b.FRONT_COLUMN_Z  # front-west socket
# local coordinates: u = x - COLUMN_X (across the rail, +u = west/outer), v = z - FRONT_COLUMN_Z (toward mid-rail)
tip = b.KEEPER_FOOT_TIP_Z_FRONT - cz
tap = b.KEEPER_TAP_Z_FRONT - cz
lug_inner = k.KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM[0]
foot_u0 = b.KEEPER_TAP_X - cx - k.KEEPER_WIDTH / 2.0
foot_u1 = foot_u0 + k.KEEPER_WIDTH
old_off = 75.057
old_tip = k.FULCRUM_KEEPER_CENTRE_Z - old_off - k.FOOT_TIP_X - cz
old_inner = k.FULCRUM_KEEPER_CENTRE_Z - (old_off - k.LUG_HALF_T) - cz
half_rail = b.RAIL_W_SIDE / 2.0
inner_v = cz * 0 + (-b.INNER_Z - cz)  # front rail's window face
web = b.WEB_T / 2.0
recess = b.CAP_RECESS_DIAMETER / 2.0
bore = b.BORE_DIA / 2.0
band = s.PRINTED_LINEAR_BAND_MM[2]

fig, axes = plt.subplots(2, 2, figsize=(19, 13), gridspec_kw={"height_ratios": [2.2, 1]})


def plan(ax, relieved, tip_v, inner_face_v, title):
    ax.set_title(title, fontsize=11, loc="left")
    # faced top: west rail strip + front rail (all u within the rail and left to the window)
    ax.add_patch(Rectangle((-half_rail, -R - 4), 2 * half_rail, 60 + R + 4, fc="#dfe7ea", ec="none"))
    ax.add_patch(Rectangle((-75, -R - 4), 75 - half_rail, inner_v + R + 4, fc="#dfe7ea", ec="none"))
    ax.plot([-half_rail, -half_rail], [inner_v, 56], "k", lw=1)  # window rim of the west rail
    ax.plot([-75, -half_rail], [inner_v, inner_v], "k", lw=1)  # window rim of the front rail
    ax.plot([half_rail, half_rail], [math.sqrt(R * R - half_rail**2), 56], "k", lw=1)  # outer rim
    for w in (-web, web):
        ax.plot([w, w], [math.sqrt(R * R - web * web), 56], color="#888", lw=0.8, ls="--")
    if relieved:
        a = math.degrees(math.acos(d / R))
        ax.add_patch(Wedge((0, 0), R, 90 + a, 90 - a + 360, fc="#b9c6cc", ec="none"))
        hc = s.KEEPER_BOSS_RELIEF_HALF_CHORD
        ax.add_patch(Polygon([(-hc, d), (hc, d), (0, 0)], fc="#b9c6cc", ec="none"))
        th = [math.radians(t) for t in range(int(90 - a + 0.5) - 360, int(90 + a) + 1 - 360 + 360)]
        arc = [math.radians(90 + a + i * (360 - 2 * a) / 200) for i in range(201)]
        ax.plot([R * math.cos(t) for t in arc], [R * math.sin(t) for t in arc], "k", lw=1.3)
        ax.plot([-hc, hc], [d, d], "k", lw=1.6)
        ax.add_patch(Circle((0, 0), R, fc="none", ec="#999", lw=0.7, ls=":"))
        ax.annotate(f"relief step: chord {d:.3f} (.67 in) from the socket axis\n"
                    f"{s.KEEPER_BOSS_RELIEF_DEPTH:.3f} off the barrel edge, proud .18 only",
                    (hc * 0.6, d), (26, 2), arrowprops=dict(arrowstyle="->"), fontsize=9)
        for sign, c in ((1, "#c00"), (-1, "#c00")):
            ax.plot([-R, R], [d + sign * band, d + sign * band], color=c, lw=0.6, ls=":")
    else:
        ax.add_patch(Circle((0, 0), R, fc="#b9c6cc", ec="k", lw=1.3))
    ax.add_patch(Circle((0, 0), recess, fc="white", ec="k", lw=1))
    ax.add_patch(Circle((0, 0), bore, fc="white", ec="#666", lw=0.8))
    # keeper: lug + outward foot (toward the socket)
    ax.add_patch(Rectangle((foot_u0, tip_v), k.KEEPER_WIDTH, inner_face_v - tip_v,
                           fc="#f2c14e", ec="#7a5a00", lw=1.2, alpha=0.85))
    lug_outer = inner_face_v - 2 * k.LUG_HALF_T
    ax.plot([foot_u0, foot_u1], [lug_outer, lug_outer], color="#7a5a00", lw=0.8)
    tap_v = tip_v + (k.FOOT_TIP_X - k.SCREW_X)
    ax.add_patch(Circle((b.KEEPER_TAP_X - cx, tap_v), b.KEEPER_TAP_THREAD_MAJOR_DIA / 2.0, fc="white", ec="k", lw=1))
    ax.annotate("#2-56 keeper tap", (b.KEEPER_TAP_X - cx, tap_v), (26, 40), arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.annotate("keeper foot (MHA-CH-07), .55 wide", (foot_u1, tip_v + 9), (26, 47), arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.annotate("cap recess dia 1.083", (recess * 0.7, -recess * 0.7), (26, -18), arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.annotate("window corner\n(front rail window face,\nINNER_Z 92.964)", (-half_rail, inner_v), (-74, 50), arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.text(-72, -8, "front rail: faced top\n(one plane with the west rail's)", fontsize=9, color="#345")
    ax.text(-half_rail + 1, 50, "west rail\nfaced top", fontsize=9, color="#345")
    ax.text(-50, 34, "window (open)", fontsize=9, color="#777")
    ax.set_xlim(-76, 100)
    ax.set_ylim(-R - 4, 56)
    ax.set_aspect("equal")
    ax.invert_yaxis()
    ax.set_xlabel("across the rail from the socket axis, mm (+ = west / outer face)")
    ax.set_ylabel("along the rail from the socket axis toward mid-rail, mm")


plan(axes[0][0], False, old_tip, old_inner,
     f"BEFORE  pitch 7.0565: foot tip {old_tip:.3f} from the socket axis, barrel edge {R:.3f}\n"
     f"foot to boss +{old_tip - R:.3f} (floor 1.0)")
ax = axes[0][0]
plan(axes[0][1], True, tip, lug_inner,
     f"AFTER  pitch 7.62 + K5 relief: foot tip {tip:.3f}, step {d:.3f}\n"
     f"foot to step +{b.KEEPER_FOOT_BOSS_MARGINS[0]:.3f} nominal (floor 1.0), "
     f"+{b.KEEPER_FOOT_PRINTED_BOSS_MARGINS[0]:.3f} at printed limits (floor > 0)\n"
     f"without the relief {tip - R:.3f}")
ax = axes[0][1]
ax.annotate(f"foot passes the window face by {inner_v - tip:.3f}:\nstill on the front rail's faced flange\n"
            f"(step to window face {b.KEEPER_FOOT_CORNER_FLANGE_MARGIN:.3f} at limits)",
            (foot_u0, (tip + inner_v) / 2), (-74, 30), arrowprops=dict(arrowstyle="->"), fontsize=9, color="#900")
ax.annotate(f"foot edge to outer rim break {b.KEEPER_FOOT_PRINTED_FLAT_TOP_SIDE_MARGIN:.3f}\nat printed limits",
            (foot_u1, tip + 13), (26, 30), arrowprops=dict(arrowstyle="->"), fontsize=9)


def section(ax, relieved, tip_v, title):
    """Section on the socket axis plane, looking across the rail: v right, y up."""
    ax.set_title(title, fontsize=11, loc="left")
    top, rail, under, bottom = b.HALF_H + b.BOSS_ABOVE, b.HALF_H, -b.HALF_H, -b.HALF_H - b.BOSS_BELOW
    inboard_top = d if relieved else R
    solid = [(-R, bottom), (-R, top), (-recess, top), (-recess, b.CAP_RECESS_FLOOR_Y), (-bore, b.CAP_RECESS_FLOOR_Y),
             (-bore, bottom)]
    ax.add_patch(Polygon(solid, fc="#b9c6cc", ec="k", lw=1, hatch="///"))
    right = [(bore, bottom), (bore, b.CAP_RECESS_FLOOR_Y), (recess, b.CAP_RECESS_FLOOR_Y), (recess, top),
             (inboard_top, top), (inboard_top, rail), (56, rail), (56, under), (R, under), (R, bottom)]
    ax.add_patch(Polygon(right, fc="#b9c6cc", ec="k", lw=1, hatch="///"))
    if relieved:
        ax.add_patch(Polygon([(d, rail), (d, top), (R, top), (R, rail)], fc="none", ec="#999", lw=0.8, ls=":"))
        ax.annotate(f"wall to the cap recess\n{d - recess:.3f} nominal, {b.KEEPER_RELIEF_CAP_RECESS_WALL:.3f} at limits\n(target .080 = {b.WALL_TARGET_MM:.3f})",
                    ((d + recess) / 2, top), (-22, top + 9), arrowprops=dict(arrowstyle="->"), fontsize=9)
    # keeper foot on the rail top
    ax.add_patch(Rectangle((tip_v, rail), k.FOOT_TIP_X + k.LUG_HALF_T, k.FOOT_H, fc="#f2c14e", ec="#7a5a00", alpha=0.85))
    tap_v = tip_v + (k.FOOT_TIP_X - k.SCREW_X)
    depth = b.KEEPER_TAP_SPEC.depth_mm
    ax.add_patch(Rectangle((tap_v - 0.9, rail - depth), 1.8, depth, fc="white", ec="k", lw=0.8))
    ax.plot([-R - 3, 58], [b.SCREW_AXIS_Y, b.SCREW_AXIS_Y], color="#06c", lw=0.7, ls="-.")
    ax.text(40, b.SCREW_AXIS_Y - 3.2, "cross-screw axis", fontsize=8, color="#06c")
    ax.plot([0, 0], [bottom - 3, top + 3], color="k", lw=0.6, ls="-.")
    ax.text(-R, top + 0.8, "boss top (machined)", fontsize=8)
    ax.text(40, rail + 0.8, "faced rail top", fontsize=8)
    ax.set_xlim(-R - 5, 60)
    ax.set_ylim(bottom - 5, top + 16)
    ax.set_aspect("equal")
    ax.set_xlabel("along the rail from the socket axis, mm")
    ax.set_ylabel("height about the rail mid-plane, mm")


section(axes[1][0], False, old_tip, "BEFORE  section on the socket axis plane (along the rail)")
section(axes[1][1], True, tip, "AFTER  section: the proud .18 machined off inboard of the chord; floor = faced rail top")
fig.suptitle("#1038 re-pitch, slice S5a: MHA-FR-02 front-west corner boss, keeper foot and the K5 relief "
             "(to scale, mm; dotted red = step at .67 +/-.01)", fontsize=12)
fig.tight_layout()
out = Path("C:/farm-runs/repitch-s5a/keeper-relief-before-after.png")
fig.savefig(out, dpi=130)
print(out)
