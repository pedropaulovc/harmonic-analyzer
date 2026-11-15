"""Issue #2434 owner-pack figure: how the MHA-MS-00 stick registers.

To-scale views from the origin/main specs (rocker MHA-CH-06, bar MHA-CH-01,
stick MHA-MS-01, stop MHA-MS-02/03) plus the error-budget sweep saved by
issue-2434-budget-sweep.py. Run from cad/scripts of an origin/main worktree:
    uv run --frozen python <this file>
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Polygon, Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path.cwd()))
_spec = importlib.util.spec_from_file_location("reg", HERE / "issue-2434-registration.py")
reg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reg)

import ch_amplitude_bar_spec as bar  # noqa: E402
import ch_rocker_arm_spec as arm  # noqa: E402
import _rocker_interface as ri  # noqa: E402
import channel_kinematics as ck  # noqa: E402
import ms_stick_spec as stick  # noqa: E402
import ms_stop_spec as stop  # noqa: E402
import sh_vn_thumb_screw_spec as thumb  # noqa: E402
from _config import machine  # noqa: E402

P = reg.P
OX, OY = reg.OX, reg.OY
PITCH = float(machine("channels", "station_pitch_mm"))
OFFSET = round(sum(r["offset_mm"] for r in reg.rows) / len(reg.rows), 2)  # 2.74
SHIFT = OFFSET  # option 1 moves every graduation this far toward the 0 end
budget = json.loads((HERE / "issue-2434-budget-sweep.json").read_text())

STEEL, BRASS, BAR, EDGE = "#c9ced6", "#e3c46a", "#9aa3ad", "#222"


def L(p):  # machine -> pivot-relative mm
    return (p[0] - OX, p[1] - OY)


def rocker_outline():
    """Lifting half of the rocker strap, pivot-relative, plus a stub of the other half."""
    pts = []
    n = 120
    for i in range(n + 1):  # top edge from x=-30 to the tip corner
        x = -30.0 + (reg.T[0] - OX + 30.0) * i / n
        pts.append((x, reg.top_y(x + OX) - OY))
    pts.append(L(reg.B))
    rb = ri.R_BOTTOM
    ab = arm._ALPHA_BOT
    bx = rb * math.sin(ab)
    for i in range(n + 1):  # bottom arc back from its end to x=-30
        x = bx - (bx + 30.0) * i / n
        pts.append((x, (reg.ACY - math.sqrt(rb * rb - x * x)) - OY))
    return pts


def bar_poly(d, height=34.0):
    s = ck.solve_state(d)
    beta = -math.radians(s["bar_tilt"])
    up = (math.sin(beta), math.cos(beta))
    inn = (-math.cos(beta), math.sin(beta))
    o = (s["bar_origin_x"] - OX, s["bar_origin_y"] - OY)
    w = bar.BAR_WIDTH
    return [o, (o[0] + w * inn[0], o[1] + w * inn[1]),
            (o[0] + w * inn[0] + height * up[0], o[1] + w * inn[1] + height * up[1]),
            (o[0] + height * up[0], o[1] + height * up[1])]


def stick_frame(d):
    row = reg.stick_reading(d)
    E = (row["E_x_from_pivot"] + OX, reg.top_y(row["E_x_from_pivot"] + OX))
    _, _, theta, u = reg._end_corners(E[0])
    n = (-u[1], u[0])
    E = L(E)
    return row, E, u, n


def at(E, u, n, s, t):
    return (E[0] + s * u[0] + t * n[0], E[1] + s * u[1] + t * n[1])


def draw_stick(ax, d, engraving_shift, label_ticks=True, stop_on=True):
    row, E, u, n = stick_frame(d)
    th = stick.BODY_THICKNESS
    ls = stick.BODY_LENGTH
    ax.add_patch(Polygon([at(E, u, n, 0, 0), at(E, u, n, ls, 0), at(E, u, n, ls, th),
                          at(E, u, n, 0, th)], fc=BRASS, ec=EDGE, lw=0.6, zorder=4))
    # graduations: 10 tick at the end margin (+ shift), reading r at s(r)
    for k in range(0, 101):
        r = k / 10.0
        s = stick.SCALE_END_MARGIN + engraving_shift + (10.0 - r) * P
        if s > ls:
            continue
        tl = 1.6 if k % 10 else 2.6
        if k == 5 * 1:
            tl = 2.1
        ax.plot(*zip(at(E, u, n, s, th), at(E, u, n, s, th - tl * 0.6)), color=EDGE,
                lw=0.35 if k % 10 else 0.7, zorder=5)
        if label_ticks and k % 10 == 0:
            ax.text(*at(E, u, n, s, th + 1.4), f"{k // 10}", fontsize=6, ha="center", clip_on=True,
                    va="bottom", rotation=math.degrees(math.atan2(u[1], u[0])), zorder=6)
    if not stop_on:
        return row, E, u, n
    # the stop: reading face at the stick distance chord + e from the 10 end
    s0 = row["reading"]  # as-drawn reading; face station along the stick:
    sf = stick.SCALE_END_MARGIN + (10.0 - s0) * P
    roof_top = th + stop.ROOF_THICKNESS
    floor_bot = -(stop.WINDOW_HEIGHT - th) - stop.FLOOR_THICKNESS
    blk = [at(E, u, n, sf, floor_bot), at(E, u, n, sf + stop.BLOCK_LENGTH, floor_bot),
           at(E, u, n, sf + stop.BLOCK_LENGTH, roof_top - stop.ROOF_END_CHAMFER),
           at(E, u, n, sf + stop.BLOCK_LENGTH - stop.ROOF_END_CHAMFER, roof_top),
           at(E, u, n, sf + stop.ROOF_END_CHAMFER, roof_top),
           at(E, u, n, sf, roof_top - stop.ROOF_END_CHAMFER)]
    ax.add_patch(Polygon(blk, fc="#b08d3c", ec=EDGE, lw=0.6, alpha=0.85, zorder=6))
    # thumbscrew under the floor (in use the screw is DOWN)
    sc = sf + stop.THUMB_AXIS_X
    exposed = thumb.OVERALL_LEN - thumb.HEAD_STACK_LEN - stop.FLOOR_THICKNESS
    h0 = floor_bot - max(exposed, 0.5)
    ax.add_patch(Polygon([at(E, u, n, sc - 1.4, floor_bot), at(E, u, n, sc + 1.4, floor_bot),
                          at(E, u, n, sc + 1.4, h0), at(E, u, n, sc - 1.4, h0)],
                         fc="#888", ec=EDGE, lw=0.4, zorder=6))
    ax.add_patch(Polygon([at(E, u, n, sc - thumb.HEAD_DIA / 2, h0), at(E, u, n, sc + thumb.HEAD_DIA / 2, h0),
                          at(E, u, n, sc + thumb.HEAD_DIA / 2, h0 - thumb.HEAD_STACK_LEN),
                          at(E, u, n, sc - thumb.HEAD_DIA / 2, h0 - thumb.HEAD_STACK_LEN)],
                         fc="#aaa", ec=EDGE, lw=0.4, zorder=6))
    return row, E, u, n


def draw_rocker(ax):
    ax.add_patch(Polygon(rocker_outline(), fc=STEEL, ec=EDGE, lw=0.7, zorder=1))
    ax.add_patch(Circle((0, 0), arm.HUB_DIA / 2, fc="#aeb4bd", ec=EDGE, lw=0.5, zorder=2))
    ax.add_patch(Circle((0, 0), arm.PIVOT_HOLE_DIA / 2, fc="white", ec=EDGE, lw=0.5, zorder=3))
    ax.plot([0, 0], [-14, 34], color="#c33", lw=0.6, ls="-.", zorder=7)


def side_view(ax, d):
    draw_rocker(ax)
    ax.add_patch(Polygon(bar_poly(d, 44), fc=BAR, ec=EDGE, lw=0.6, zorder=3))
    row, E, u, n = draw_stick(ax, d, SHIFT)
    return row, E, u, n


fig = plt.figure(figsize=(18, 14), dpi=130)
gs = fig.add_gridspec(3, 4, height_ratios=[1.0, 1.0, 1.0], hspace=0.38, wspace=0.25)
fig.suptitle("Issue #2434: what the MHA-MS-00 measuring stick and its stop register on "
             "(to scale, origin/main specs at 7388ca8e3e)", fontsize=14, weight="bold", y=0.93)
ARW = dict(arrowstyle="->", lw=0.7)

# --- Panel 1: whole lifting half, option 1 at d = 44 ------------------------
D = 44.0
ax = fig.add_subplot(gs[0, :])
row, E, u, n = side_view(ax, D)
r1 = (D + row["offset_mm"] - SHIFT) / P
ax.set_title(f"1  Michelson's registration (options 1 and 2), bar at station d = {D:.0f} mm, crank at home "
             f"(rockers level). Option-1 stick: stop clamped at {r1:.2f} (d/14.2 = {D / P:.2f})",
             fontsize=10.5, loc="left")
cE = at(E, u, n, 0, stick.BODY_THICKNESS)
ax.annotate("stick's 10 end touches\nthe bar's outboard face", xy=cE, xytext=(-30, 36), fontsize=8.5,
            arrowprops=ARW, zorder=9)
ax.text(6, 44, "MHA-CH-01 bar", fontsize=8.5)
ax.annotate("MHA-MS-01 stick, graduations UP,\nlaid on the rocker's top edge, 10 end inboard",
            xy=at(E, u, n, 70, 3), xytext=(85, 38), fontsize=8.5, arrowprops=ARW)
sf = stick.SCALE_END_MARGIN + (10.0 - row["reading"]) * P
ax.annotate("stop (MHA-MS-02 + -03): its inboard end face\nbears on the rocker's outer tip land",
            xy=L(reg.B), xytext=(165, -27), fontsize=8.5, arrowprops=ARW, zorder=9)
ax.annotate("thumbscrew DOWN in use\n(the parked pose has it up)", xy=at(E, u, n, sf + stop.THUMB_AXIS_X, -16),
            xytext=(200, 2), fontsize=8.5, arrowprops=ARW)
ax.text(30, -1, "MHA-CH-06 rocker arm (lifting half)", fontsize=8.5, zorder=8)
ax.annotate("pivot axis = station 0", xy=(0, -5), xytext=(-33, -27), fontsize=8.5, color="#c33",
            arrowprops=dict(arrowstyle="->", lw=0.7, color="#c33"))
y_dim = -17
tx = reg.T[0] - OX
ax.annotate("", xy=(0, y_dim), xytext=(tx, y_dim), arrowprops=dict(arrowstyle="<->", lw=0.6))
ax.text(tx / 2 + 8, y_dim - 6.5, f"tip corner {tx:.2f} from the pivot; top edge R{ri.CURVE_RADIUS:.1f}; "
        f"tip land {arm.TIP_FACE:.2f} deep, square to the edge", fontsize=8, ha="center")
ax.set_xlim(-36, 262)
ax.set_ylim(-32, 50)
ax.set_aspect("equal")
ax.set_xlabel("mm from the rocker pivot axis, along the rocker (lifting side)", fontsize=8)
ax.tick_params(labelsize=7)

# --- Panel 2: zoom at the tip -------------------------------------------------
ax = fig.add_subplot(gs[1, 0])
side_view(ax, D)
ax.set_xlim(134, 170)
ax.set_ylim(-6, 32)
ax.set_aspect("equal")
ax.set_title("2  At the tip: the stop face meets\nthe land's LOWER corner", fontsize=9.5, loc="left")
Bp = L(reg.B)
ax.plot(*Bp, "o", color="#c33", ms=4, zorder=10)
ax.annotate(f"contact {row['land_corner_depth_below_stick_mm']:.1f} under the stick:\nthe land leans "
            f"{math.degrees(reg.ALPHA):.1f}°,\nthe stick only {row['theta_deg']:.1f}°", xy=Bp,
            xytext=(149, -4), fontsize=7.5, arrowprops=dict(arrowstyle="->", lw=0.6), zorder=10)
ax.annotate("reading edge: the block's end\nwhere the roof lies on the\ngraduated face (no parallax)",
            xy=at(E, u, n, sf, stick.BODY_THICKNESS), xytext=(135, 27.5), fontsize=7,
            arrowprops=dict(arrowstyle="->", lw=0.6), zorder=10)
ax.tick_params(labelsize=7)

# --- Panel 3: zoom at the bar -------------------------------------------------
ax = fig.add_subplot(gs[1, 1])
side_view(ax, D)
ax.set_xlim(D - 10, D + 20)
ax.set_ylim(2, 30)
ax.set_aspect("equal")
ax.set_title("3  At the bar: the 10 end's top\nedge touches first", fontsize=9.5, loc="left")
ax.plot(*cE, "o", color="#c33", ms=4, zorder=10)
ax.annotate(f"10-end land: {stick.SCALE_END_MARGIN:.2f} as drawn,\n{stick.SCALE_END_MARGIN + SHIFT:.2f} in option 1",
            xy=at(E, u, n, stick.SCALE_END_MARGIN + SHIFT, stick.BODY_THICKNESS), xytext=(D + 4, 25),
            fontsize=7.5, arrowprops=dict(arrowstyle="->", lw=0.6), zorder=10)
ax.text(D + 1, 4, f"bottom corner stands\n{row['bottom_corner_gap_to_bar_mm']:.2f} off the bar", fontsize=7.5,
        zorder=10)
ax.tick_params(labelsize=7)

# --- Panel 4: end view at the bar --------------------------------------------
ax = fig.add_subplot(gs[1, 2])
t_arm = arm.ARM_THICKNESS
for j in (-1, 0, 1):
    z = j * PITCH
    ax.add_patch(Rectangle((z - t_arm / 2, -16), t_arm, 16, fc=STEEL, ec=EDGE, lw=0.5))
    if j:
        ax.add_patch(Rectangle((z - bar.BAR_DEPTH / 2, -2.4), bar.BAR_DEPTH, 20, fc=BAR, ec=EDGE, lw=0.5))
        ax.text(z, 18.5, "neighbour\nbar, set\nfarther out", ha="center", fontsize=7)
ax.add_patch(Rectangle((-stick.BODY_WIDTH / 2, 0), stick.BODY_WIDTH, stick.BODY_THICKNESS, fc=BRASS,
                       ec=EDGE, lw=0.6, zorder=4))
gap = 2 * PITCH - bar.BAR_DEPTH
side = (gap - stick.BODY_WIDTH) / 2
ax.annotate("", xy=(-PITCH + bar.BAR_DEPTH / 2, 8), xytext=(PITCH - bar.BAR_DEPTH / 2, 8),
            arrowprops=dict(arrowstyle="<->", lw=0.6))
ax.text(0, 9, f"{gap:.2f}", ha="center", fontsize=8)
ax.text(0, 3.6, f"stick {stick.BODY_WIDTH:.2f}", ha="center", fontsize=7)
ax.text(0, -23.5, f"{side:.2f} clear each side; the rocker under the\nstick is "
        f"{t_arm:.2f} thick ({PITCH:.2f} pitch)", ha="center", fontsize=7.5)
ax.set_xlim(-13, 13)
ax.set_ylim(-27, 27)
ax.set_yticks([])
ax.set_aspect("equal")
ax.set_title("4  Looking along the rocker at the\nbar: the stick fits flat between\nneighbouring bars",
             fontsize=9.5, loc="left")
ax.tick_params(labelsize=7)

# --- Panel 5: what the builder sees at zero, options 1 and 2 ------------------
ax = fig.add_subplot(gs[1, 3])
ax.set_title("5  The zero setting (HA-00 step 6C)\nas the builder sees the stick", fontsize=9.5, loc="left")
for yb, title, set_r in ((9, f"option 1 (scale moved {SHIFT:.2f}):\nstop face on 0", 0.0),
                          (-11, "option 2 (stick as drawn):\nstop face on the 0.2 tick", 0.2)):
    ax.add_patch(Rectangle((-24, yb), 48, 4, fc=BRASS, ec=EDGE, lw=0.6))
    for k in range(-16, 17):
        xs = k / 10 * P
        if -24 < xs < 24:
            ax.plot([xs, xs], [yb + 4, yb + 4 - (2.2 if k % 10 == 0 else (1.7 if k % 5 == 0 else 1.1))],
                    color=EDGE, lw=0.5)
            if k % 10 == 0:
                ax.text(xs, yb + 4.4, str(k // 10), fontsize=7.5, ha="center")
    xf = set_r * P
    ax.add_patch(Rectangle((xf - stop.BLOCK_LENGTH, yb - 2.3), stop.BLOCK_LENGTH, 8.6, fc="#b08d3c",
                           ec=EDGE, lw=0.6, alpha=0.8))
    ax.annotate("", xy=(xf, yb + 4), xytext=(xf, yb + 7.5), arrowprops=dict(arrowstyle="->", lw=0.8, color="#c33"))
    ax.text(-23, yb - 7.5, title, fontsize=7.5)
ax.text(-23, -27, "the bar then stands 0.07 behind (1) or\n0.03 past (2) the pivot. 10 end is to the right.",
        fontsize=7.3)
ax.set_xlim(-25, 25)
ax.set_ylim(-29, 19)
ax.set_aspect("equal")
ax.axis("off")

# --- Panel 6: by-eye sighting --------------------------------------------------
ax = fig.add_subplot(gs[2, 0])
ax.set_title("6  Option 3, by eye: read the tick\nabove the hidden tip corner", fontsize=9.5, loc="left")
ax.add_patch(Rectangle((-t_arm / 2, -9), t_arm, 9, fc=STEEL, ec=EDGE, lw=0.5))
ax.add_patch(Rectangle((-stick.BODY_WIDTH / 2, 0), stick.BODY_WIDTH, stick.BODY_THICKNESS, fc=BRASS,
                       ec=EDGE, lw=0.6))
ax.plot([stick.BODY_WIDTH / 2 - 1.8, stick.BODY_WIDTH / 2], [stick.BODY_THICKNESS] * 2, color=EDGE, lw=2.2)
ax.text(stick.BODY_WIDTH / 2 - 2.5, stick.BODY_THICKNESS + 0.6, "ticks run to\nthis edge", fontsize=7)
ax.plot(0, 0, "o", color="#c33", ms=4)
ax.annotate("rocker tip corner,\nunder the stick", xy=(0, 0), xytext=(-8.5, -6.5), fontsize=7, color="#c33",
            arrowprops=dict(arrowstyle="->", lw=0.6, color="#c33"))
ax.annotate("", xy=(0, 0.05), xytext=(stick.BODY_WIDTH / 2, stick.BODY_THICKNESS),
            arrowprops=dict(arrowstyle="<->", lw=0.6, color="#c33"))
ax.text(-8.5, -14.8, f"the corner is {stick.BODY_THICKNESS:.1f} below and {stick.BODY_WIDTH / 2:.1f} across\n"
        "from the ticks: 10° off square moves the\nreading 0.5; reading 1/5 of a 1.42 step\n"
        "adds 0.14. Estimate ±0.5 mm, NOT measured.", fontsize=7.2)
ax.text(-8.5, 0.8, "looking along\nthe rocker", fontsize=7, color="#555")
ax.set_xlim(-9, 9)
ax.set_ylim(-16, 7)
ax.set_aspect("equal")
ax.axis("off")

# --- Panel 6b: budget bars ------------------------------------------------------
axb = fig.add_subplot(gs[2, 1])
tols = sorted(float(k) for k in budget)
maes = [budget[str(t)]["combined"]["mae"] for t in tols]
own = [budget[str(t)]["station_setting"]["mae"] for t in tols]
tot = [budget[str(t)]["total_mae"] for t in tols]
cols = ["#4a8" if not budget[str(t)]["violations"] else "#c44" for t in tols]
xs = range(len(tols))
axb.bar(xs, maes, color=cols, label="all part/setup scatter combined")
axb.bar(xs, own, color="#234", width=0.35, label="bar setting alone")
axb.set_xticks(list(xs), [f"±{t:g}" for t in tols])
axb.axhline(0.30, color="k", lw=0.8, ls="--")
axb.text(-0.45, 0.305, "scatter target 0.30", fontsize=7)
for x, m, t in zip(xs, maes, tot):
    axb.text(x, m + 0.008, f"{m:.3f}\n(total {t:.2f})", ha="center", fontsize=6.5)
axb.set_ylim(0, 0.45)
axb.set_xlabel("per-bar setting error, mm (budget today: ±0.25)", fontsize=8)
axb.set_ylabel("coefficient error, MAE % of full scale", fontsize=8)
axb.set_title("6b  What the setting error costs\n(error_budget.py; red = budget fails)", fontsize=9.5,
              loc="left")
axb.legend(fontsize=6.5, loc="upper left")
axb.tick_params(labelsize=7)

# --- Panel 7: adds a feature: zero lines on the rocker top edge ---------------
ax = fig.add_subplot(gs[2, 2])
ax.set_title("7  Option 4 [ADDS A FEATURE to all\n20 MHA-CH-06]: two scribed zero lines", fontsize=9.5,
             loc="left")
draw_rocker(ax)
ax.add_patch(Polygon(bar_poly(0.0, 16), fc=BAR, ec=EDGE, lw=0.6, zorder=3, alpha=0.55))
for xs_ in (-bar.BAR_WIDTH / 2, bar.BAR_WIDTH / 2):
    y = reg.top_y(xs_ + OX) - OY
    ax.plot([xs_, xs_], [y - 4.0, y + 0.02], color="#c33", lw=1.6, zorder=8)
ax.text(-14.5, -13.5, f"light scribe lines across the top edge (and\nover onto the side), {bar.BAR_WIDTH:.2f} apart, "
        "centred on\nthe pivot; bar at 0 = bar between them", fontsize=7)
ax.text(4.5, 13, "bar at 0\n(see-through)", fontsize=7)
ax.set_xlim(-15, 15)
ax.set_ylim(-15, 20)
ax.set_aspect("equal")
ax.tick_params(labelsize=7)

# --- Panel 8: do nothing -------------------------------------------------------
axd = fig.add_subplot(gs[2, 3])
off = json.loads((HERE / "issue-2434-common-offset.json").read_text())
names = ["all_ones", "rect_half", "gaussian_a0p1", "alternating", "pair_1_20"]
labels = ["all 20\nat 1", "square\nhalf", "gaussian", "alter-\nnating", "two\nbars"]
base = [off["0.0"][k]["mae"] for k in names]
bad = [off["-2.74"][k]["mae"] for k in names]
xx = range(len(names))
axd.bar([x - 0.2 for x in xx], base, width=0.4, color="#4a8", label="bars where READOUT thinks\n(as-built residual)")
axd.bar([x + 0.2 for x in xx], bad, width=0.4, color="#c44", label=f"all bars {OFFSET:.2f} mm nearer the pivot")
for x, b in zip(xx, bad):
    axd.text(x + 0.2, b + 0.2, f"{b:.1f}", ha="center", fontsize=7)
axd.set_xticks(list(xx), labels)
axd.set_ylabel("coefficient error, MAE % FS (nominal machine)", fontsize=8)
axd.set_title("8  Option 5, do nothing: stop used the\n1898 way, READOUT's table read as printed",
              fontsize=9.5, loc="left")
axd.legend(fontsize=6.5, loc="upper left")
axd.tick_params(labelsize=7)

out = HERE / "issue-2434-stick-registration.png"
fig.savefig(out, bbox_inches="tight")
print(out, "offset", OFFSET, "r1", r1)
