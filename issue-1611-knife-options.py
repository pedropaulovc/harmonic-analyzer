"""Issue #1611 owner pack: MHA-SM-03 knife edge -- load, contact stress,
budget need and the options, drawn to scale.

Run from a clean origin/main worktree's cad/scripts (the spec modules are
imported, never copied):

    uv run python C:/Users/pedro/Downloads/dfm-v48-decisions/issue-1611-knife-options.py

Inputs read live:
  sm_summing_lever_spec  hex 8.080 x 10.268, ridge R.004 MAX, stub 21.717,
                         spring row Z, knife seat Z stations
  sm_knife_mount_spec    bore R 5.9944 (+.0015/0 in on dia), block .55 deep
  error_budget.py        knife load cases (closed_form.knife) and the knife
                         rolling-resistance sweep (issue-1611-knife-sweep.json,
                         written by issue-1611-knife-sweep.py)
Material constants are handbook values, flagged in the table printout.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Polygon, Rectangle  # noqa: E402

sys.path.insert(0, ".")
import error_budget as eb  # noqa: E402
import sm_knife_mount_spec as M  # noqa: E402
import sm_summing_lever_spec as L  # noqa: E402

OUT = Path(r"C:\Users\pedro\Downloads\dfm-v48-decisions")
IN = 25.4

# ---------------------------------------------------------------- load ----
report = eb.build_report(eb.load_budget())
knife = report["closed_form"]["knife"]
case = knife["maximum_conservative_knife_load_case"]
c = knife["load_cases"][case]
F_CH, F_CO = c["channel_force_sum_N"], c["counter_force_N"]
F_TOT = c["conservative_knife_load_N"]
# Split between the two mounts by statics: the 20 channel springs at their
# taps (equal shares), the counter spring at the boss (local Z 0), each
# ridge bearing at its stub's mid-length.
z_taps = [L.HOLE_Z_FIRST + i * L.CHANNEL_PITCH for i in range(L.HOLE_COUNT)]
zp, zm = L.KNIFE_SEAT_Z_PLUS, L.KNIFE_SEAT_Z_MINUS
span = zp - zm
r_plus = (sum(F_CH / len(z_taps) * (z - zm) for z in z_taps) + F_CO * (0 - zm)) / span
r_minus = F_TOT - r_plus
F_MOUNT = max(r_plus, r_minus)
LEN = M.SUPPORT_Z_THICK  # ridge length bearing in one .55 block
W = F_MOUNT / LEN  # N/mm

# ------------------------------------------------------------- contact ----
R_EDGE = L.KNIFE_RIDGE_R
R_BORE = M.R_BORE
SEAT = dict(name="MHA-SM-02 4140 HT", E=205e3, nu=0.29, Y=(655.0, 900.0))
# Y for a soft edge: hardness-based estimate Y ~ H/3 (H = 9.81 HB MPa) where
# no yield is published for contact; steels use catalogue yields.
EDGES = [
    ("A", "gray iron (Dura-Bar G2, class 40)\n180-302 HB, as machined", 117e3, 0.26, 9.81 * 180 / 3, R_EDGE),
    ("A0", "1018 cold-finished (the print\nalso allows it), 126 HB", 205e3, 0.29, 370.0, R_EDGE),
    ("B1", "4140 HT whole lever\n28-32 HRC as supplied", 205e3, 0.29, 655.0, R_EDGE),
    ("B2", "O1 strip, shop torch + 400 F oven\n~60 HRC", 210e3, 0.29, 1900.0, R_EDGE),
    ("C1", "bought M2 HSS strip\n~63-65 HRC, ground", 220e3, 0.30, 2500.0, R_EDGE),
    ("C2", "bought 1/8 dowel pin as edge\n(R.0625 roll, not R.004)", 205e3, 0.29, 1900.0, 0.125 * IN / 2),
]


def hertz(E1, nu1, E2, nu2, r_edge, w):
    estar = 1.0 / ((1 - nu1**2) / E1 + (1 - nu2**2) / E2)
    rprime = 1.0 / (1.0 / r_edge - 1.0 / R_BORE)
    p0 = math.sqrt(w * estar / (math.pi * rprime))
    b = math.sqrt(4 * w * rprime / (math.pi * estar))
    return estar, rprime, p0, b


rows = []
for key, label, E, nu, Y, r in EDGES:
    estar, rp, p0, b = hertz(E, nu, SEAT["E"], SEAT["nu"], r, W)
    if Y < SEAT["Y"][0]:
        y_soft, soft = Y, "lever edge"
    elif Y == SEAT["Y"][0]:
        y_soft, soft = Y, "equal"
    else:
        y_soft, soft = SEAT["Y"][0], "seat"
    shake = 2.0 * y_soft  # line contact elastic shakedown, Tresca 4k (#2334)
    onset = 1.79 * y_soft  # first yield, von Mises, line contact
    if p0 > shake:  # beds in until the shakedown pressure carries the load
        rp_bed = W * estar / (math.pi * shake**2)
        b_use = math.sqrt(4 * W * rp_bed / (math.pi * estar))
        state = "beds in, then elastic"
    else:
        b_use = b
        state = "first-load micro-yield, then elastic" if p0 > onset else "elastic"
    rows.append(dict(key=key, label=label, p0=p0, b_um=b * 1e3, b_used_um=b_use * 1e3,
                     soft=soft, onset=onset, shake=shake, state=state, r=r))

sweep = json.load(open(OUT / "issue-1611-knife-sweep.json"))
# pair gate crossing (expected worst coefficient = 2.0): refined runs
# 0.009 -> 1.968, 0.0095 -> 2.022 (same code, same seed)
F_CEIL = 0.009 + 0.0005 * (2.0 - 1.9681) / (2.0220 - 1.9681)
D_THETA = math.radians(0.5)
L_PEND = 200.0
swings = lambda f: D_THETA * L_PEND / (4.0 * f)  # noqa: E731  full swings 1 deg -> 0.5 deg

print(f"knife load case {case}: channels {F_CH:.1f} N + counter {F_CO:.1f} N = {F_TOT:.1f} N")
print(f"mount split: +Z {r_plus:.1f} N, -Z {r_minus:.1f} N; per mount max {F_MOUNT:.1f} N over {LEN:.2f} mm = {W:.2f} N/mm")
for r in rows:
    print(f"{r['key']:7s} p0 {r['p0']:7.0f} MPa  b {r['b_um']:5.2f} um (used {r['b_used_um']:5.2f})  softer {r['soft']:10s} onset {r['onset']:5.0f} shake {r['shake']:5.0f}  {r['state']}")
print(f"budget ceiling f = {F_CEIL * 1e3:.2f} um; swings at 5 um {swings(0.005):.0f}, at ceiling {swings(F_CEIL):.0f}")
print("rock (nominal, t=0): drawn", M.free_rock_deg(0.0))

# ------------------------------------------------------------- geometry ----
HW, HH = L.HEX_W / 2, L.HEX_H
RIDGE_Y = HH / 2  # lever axis at (0, 0)
BORE_C = RIDGE_Y - R_BORE  # ridge on the bore crown (springs pull it up)
BLK_TOP = RIDGE_Y + M.BORE_CROWN_DEPTH
BLK_BOT = BLK_TOP - M.BLOCK_HEIGHT_PRINTED
SQ = 0.1875 * IN  # 3/16 square strip
DIAG = SQ * math.sqrt(2)


def hex_pts():
    return [(0, RIDGE_Y), (HW, HH / 4), (HW, -HH / 4), (0, -RIDGE_Y), (-HW, -HH / 4), (-HW, HH / 4)]


def strip_stub_pts():
    """Hex stub after the 90 deg vee that seats the strip's lower half."""
    apex = RIDGE_Y - DIAG
    y_side = apex + HW  # vee wall meets the hex side face
    return [(-HW, y_side), (0, apex), (HW, y_side), (HW, -HH / 4), (0, -RIDGE_Y), (-HW, -HH / 4)], apex


def mount(ax):
    ax.add_patch(Rectangle((-M.BLK_HALF_X, BLK_BOT), 2 * M.BLK_HALF_X, M.BLOCK_HEIGHT_PRINTED,
                           fc="#cdb98f", ec="k", lw=0.8, zorder=1))
    ax.add_patch(Circle((0, BORE_C), R_BORE, fc="white", ec="k", lw=0.8, zorder=2))
    ax.text(0, BLK_BOT + 1.0, "MHA-SM-02, 4140 HT 28-32 HRC\nbore Ø.4720 +.0015/0 reamed",
            ha="center", va="bottom", fontsize=6.5)


def end_view(ax, title, which):
    mount(ax)
    if which == "drawn":
        ax.add_patch(Polygon(hex_pts(), closed=True, fc="#3f7f5f", ec="k", lw=0.8, zorder=3))
        ax.text(0, -0.6, "hex knife\nlever metal", ha="center", va="center", fontsize=6.5, color="w", zorder=4)
        ax.annotate(f"ridge R.004 MAX\n{L.RIDGE_ANGLE_DEG:.1f}° included", (0.0, RIDGE_Y), (5.5, 11.0),
                    fontsize=6.5, arrowprops=dict(arrowstyle="->", lw=0.6), zorder=5)
        ax.text(0, BLK_BOT - 1.0, f"free rock {M.free_rock_deg(0.0):.1f}° nominal", ha="center", va="top", fontsize=6.5)
    elif which == "strip":
        pts, apex = strip_stub_pts()
        ax.add_patch(Polygon(pts, closed=True, fc="#3f7f5f", ec="k", lw=0.8, zorder=3))
        sq = [(0, RIDGE_Y), (DIAG / 2, RIDGE_Y - DIAG / 2), (0, apex), (-DIAG / 2, RIDGE_Y - DIAG / 2)]
        ax.add_patch(Polygon(sq, closed=True, fc="#8a8f99", ec="k", lw=0.8, zorder=4))
        ax.plot(*zip(*hex_pts(), hex_pts()[0]), ls=":", lw=0.6, color="k", zorder=5)
        ax.annotate("3/16 sq. hardened strip,\ncorner up = the edge (90°)", (0.0, RIDGE_Y), (4.2, 11.0),
                    fontsize=6.5, arrowprops=dict(arrowstyle="->", lw=0.6), zorder=6)
        ax.annotate("bonded in a 90° vee\n(dotted: drawn hex)", (-1.8, apex + 1.8), (-12.5, 9.0),
                    fontsize=6.5, arrowprops=dict(arrowstyle="->", lw=0.6), zorder=6)
        rock = min(M.free_rock_deg(0.0, shoulder_drop=RIDGE_Y - (apex + HW)),
                   M.free_rock_deg(0.0, hex_w=DIAG, shoulder_drop=DIAG / 2))
        ax.text(0, BLK_BOT - 1.0, f"free rock {rock:.1f}° nominal (drawn {M.free_rock_deg(0.0):.1f}°)", va="top",
                ha="center", fontsize=6.5)
    ax.set_title(title, fontsize=9)
    ax.set_xlim(-14, 14)
    ax.set_ylim(BLK_BOT - 4.0, BLK_TOP + 0.5)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.plot([-10, -5], [BLK_TOP - 1.2] * 2, "k", lw=1.5)
    ax.text(-7.5, BLK_TOP - 0.9, "5 mm", ha="center", fontsize=6)


def side_view(ax, title, strip):
    z0 = L.PLATE_Z_PLUS
    z1 = L.HEX_Z_OUTER_PLUS
    ax.add_patch(Rectangle((z0 - 18, -L.CYL_R), 18, 2 * L.CYL_R, fc="#3f7f5f", ec="k", lw=0.8))
    ax.text(z0 - 9, 0, "MHA-SM-03\npivot body\n(Ø1.00)", ha="center", va="center", fontsize=6.5, color="w")
    ax.add_patch(Rectangle((z0, -HH / 2), z1 - z0, HH, fc="#3f7f5f", ec="k", lw=0.8, zorder=2))
    zc, d = L.KNIFE_SEAT_Z_PLUS, M.SUPPORT_Z_THICK
    bore_top, bore_bot = RIDGE_Y, RIDGE_Y - 2 * R_BORE
    for ylo, yhi in ((bore_top, BLK_TOP), (BLK_BOT, bore_bot)):
        ax.add_patch(Rectangle((zc - d / 2, ylo), d, yhi - ylo, fc="#cdb98f", ec="k", lw=0.8,
                               hatch="///", zorder=3))
    ax.plot([zc - d / 2, zc + d / 2], [bore_bot] * 2, "k", lw=0.6, zorder=3)
    if strip:
        apex = RIDGE_Y - DIAG
        ax.add_patch(Rectangle((z0 + 0.5, RIDGE_Y - DIAG / 2), z1 - z0 - 1.0, DIAG / 2,
                               fc="#8a8f99", ec="k", lw=0.8, zorder=4))
        ax.add_patch(Rectangle((z0 + 0.5, apex), z1 - z0 - 1.0, DIAG / 2, fc="none", ec="k",
                               lw=0.6, ls="--", zorder=4))
        ax.annotate("strip .84 long per stub", (z0 + 4, RIDGE_Y), (z0 - 14, 15.5), fontsize=6.5,
                    arrowprops=dict(arrowstyle="->", lw=0.6))
    else:
        ax.annotate("edge cut in the lever metal\n(knife = the stub's top corner)", (z0 + 4, RIDGE_Y),
                    (z0 - 17, 15.5), fontsize=6.5, arrowprops=dict(arrowstyle="->", lw=0.6))
    ax.annotate("", (z0, -9.5), (z1, -9.5), arrowprops=dict(arrowstyle="<->", lw=0.6))
    ax.text(z1 + 2, -12.6, f"stub {L.HEX_DEPTH / IN:.3f} in long;\nthe .55 block puts "
            f"{M.SUPPORT_Z_THICK:.2f} mm of ridge in contact", ha="right", va="top", fontsize=6.5)
    ax.set_title(title, fontsize=9)
    ax.set_xlim(z0 - 19, z1 + 3)
    ax.set_ylim(BLK_BOT - 8.0, BLK_TOP + 1)
    ax.set_aspect("equal")
    ax.axis("off")


def contact_zoom(ax):
    """The modelled R.004 round on the bore crown, with each pairing's
    loaded contact width (half-width b, Hertz, or after bedding in)."""
    s = 1e3  # mm -> um
    th = [i / 200 * math.pi for i in range(201)]
    rr = R_EDGE * s
    ax.plot([rr * math.cos(t) for t in th], [-rr + rr * math.sin(t) for t in th], color="#3f7f5f", lw=2)
    # bore crown (concave, radius 5994 um) drawn across +-60 um
    xs = [x for x in range(-60, 61)]
    ax.plot(xs, [R_BORE * s - math.sqrt((R_BORE * s) ** 2 - x * x) for x in xs], color="#a08850", lw=2)
    ax.text(48, 4, "bore crown\n(MHA-SM-02)", fontsize=6.5, color="#7a6230")
    ax.text(-60, -55, "knife ridge R.004\n(0.1016 mm round)", fontsize=6.5, color="#3f7f5f")
    b_a = rows[0]["b_used_um"]
    ax.plot([-b_a, b_a], [0.0, 0.0], color="r", lw=5, solid_capstyle="butt")
    ax.annotate(f"A's loaded band, 2b = {2 * b_a:.1f} µm", (b_a, 0.0), (12, -22), fontsize=6.5, color="r",
                arrowprops=dict(arrowstyle="->", lw=0.6, color="r"))
    lines = [f"{r['key']}: 2b = {2 * r['b_used_um']:.1f} µm" for r in rows[:5]]
    ax.text(18, 40, "loaded contact width\n" + "\n".join(lines), va="top", fontsize=6.5)
    ax.set_title(f"Contact at one mount ({F_MOUNT:.0f} N on .55 in)", fontsize=9)
    ax.set_xlim(-65, 65)
    ax.set_ylim(-60, 50)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.plot([-60, -40], [44, 44], "k", lw=1.5)
    ax.text(-50, 46, "20 µm", ha="center", fontsize=6)


def coupon(ax):
    ax.set_title("D: coupon (#2334 pendulum), schematic", fontsize=9)
    # block turned over and clamped: the reamed bore's lowest line is the seat;
    # the hex knife rests ridge-down on it, the weight hangs from its ends.
    ax.add_patch(Rectangle((-12.7, -9.0), 25.4, 22.0, fc="#cdb98f", ec="k", lw=0.8))
    ax.add_patch(Circle((0, 0), 6.0, fc="white", ec="k", lw=0.8))
    hy = -6.0 + HH / 2  # hex centre, ridge on the bore bottom
    ax.add_patch(Polygon([(0, hy - HH / 2), (HW, hy - HH / 4), (HW, hy + HH / 4), (0, hy + HH / 2),
                          (-HW, hy + HH / 4), (-HW, hy - HH / 4)], closed=True, fc="#3f7f5f", ec="k", lw=0.8))
    ax.plot([0, 0], [hy, -36], "k", lw=1.0, ls=(0, (4, 2)))
    ax.plot([0, 6.3], [-6.0, -36], "k:", lw=0.6)
    ax.add_patch(Rectangle((-4, -40), 8, 8, fc="#666", ec="k"))
    ax.text(5, -40, "7 kg, centre of mass\n200 mm below the ridge\n(≈ one mount's 68 N)", fontsize=6.5)
    ax.text(-30, 31.5, "4140 HT block (offcut of the MHA-SM-02 bar),\nreamed .4724, turned over and clamped;\n"
            "hex knife ~1.5 long cut from the lever bar's\noffcut, ridge down, .55 of it in the block;\n"
            "stirrup from the knife's ends (dashed)", fontsize=6.5, va="top")
    ax.text(-30, -14, "start at 1°, count full\nswings until 0.5°;\n"
            "then 1000 rocks by hand\nand look for a flat\nwith a loupe", fontsize=6.5, va="top")
    ax.set_xlim(-31, 28)
    ax.set_ylim(-44, 32)
    ax.set_aspect("equal")
    ax.axis("off")


def swing_chart(ax):
    fs = [x / 10 for x in range(15, 201)]
    ax.plot(fs, [swings(f / 1000) for f in fs], "k", lw=1.2)
    ax.axvspan(1.5, 5.0, color="#cfe8cf")
    ax.axvspan(5.0, F_CEIL * 1e3, color="#f5e7b5")
    ax.axvspan(F_CEIL * 1e3, 20, color="#f3c9c4")
    for f, txt in ((5.0, "budget's assumed 0.005 mm"), (F_CEIL * 1e3, f"budget limit {F_CEIL:.4f} mm")):
        n = swings(f / 1000)
        ax.plot([f, f], [0, n], "k:", lw=0.8)
        ax.plot([1.5, f], [n, n], "k:", lw=0.8)
        ax.text(f + 0.3, n + 6, f"{n:.0f} swings\n{txt}", fontsize=6.5)
    ax.text(2.0, 260, "pass:\nbudget as\nwritten", fontsize=7)
    ax.text(5.4, 160, "closes;\nraise the\nnumber", fontsize=7)
    ax.text(12.5, 160, "pair gate fails:\nfit the hard strip (C1)", fontsize=7)
    ax.set_xlabel("knife rolling resistance f (µm)", fontsize=8)
    ax.set_ylabel("full swings from 1° to 0.5°", fontsize=8)
    ax.set_xlim(1.5, 20)
    ax.set_ylim(0, 300)
    ax.tick_params(labelsize=7)
    ax.set_title("What the coupon count means (error_budget.py, origin/main)", fontsize=9)


def contact_chart(ax):
    keys = [r["key"] for r in rows]
    y = list(range(len(rows)))[::-1]
    ax.barh(y, [r["b_used_um"] for r in rows], color=["#3f7f5f", "#6f9f6f", "#b08d57", "#8a8f99", "#8a8f99", "#bbbbbb"])
    ax.axvline(5.0, color="k", ls=":", lw=0.8)
    ax.axvline(F_CEIL * 1e3, color="r", ls="--", lw=0.8)
    ax.text(5.1, len(rows) - 0.45, "assumed f", fontsize=6.5)
    ax.text(F_CEIL * 1e3 + 0.1, len(rows) - 0.45, "budget limit", fontsize=6.5, color="r")
    for yi, r in zip(y, rows):
        ax.text(r["b_used_um"] + 0.15, yi,
                f"p0 {r['p0'] / 1000:.2f} GPa vs {r['shake'] / 1000:.2f} limit ({r['soft']} softer): {r['state']}",
                va="center", fontsize=6.2)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{r['key']}  {r['label'].replace(chr(10), ' ').split(',')[0].split(' (')[0]}" for r in rows], fontsize=6.5)
    ax.set_xlim(0, 22)
    ax.set_xlabel("contact half-width b (µm) = most rolling resistance could be if the contact acted as a rigid foot", fontsize=7)
    ax.tick_params(axis="x", labelsize=7)
    ax.set_title(f"Edge on the 4140 HT seat at {F_MOUNT:.0f} N per mount ({W:.2f} N/mm), Hertz", fontsize=9)


fig = plt.figure(figsize=(19, 11))
gs = fig.add_gridspec(3, 4, height_ratios=[1.15, 0.85, 1.0], hspace=0.28, wspace=0.12)
end_view(fig.add_subplot(gs[0, 0]), "A0 / A / B1: knife cut in the lever (as drawn)", "drawn")
end_view(fig.add_subplot(gs[0, 1]), "B2 / C1: hard strip set in each stub", "strip")
contact_zoom(fig.add_subplot(gs[0, 2]))
coupon(fig.add_subplot(gs[0, 3]))
side_view(fig.add_subplot(gs[1, 0]), "side view, rear stub in its mount (A0 / A / B1)", False)
side_view(fig.add_subplot(gs[1, 1]), "side view, rear stub in its mount (B2 / C1)", True)
ax_t = fig.add_subplot(gs[1, 2:])
ax_t.axis("off")
ax_t.text(0.0, 1.0,
          f"Load on the knife (error_budget.py worst stationary case '{case}'):\n"
          f"  20 channel springs {F_CH:.1f} N + counter spring {F_CO:.1f} N = {F_TOT:.1f} N, all pulling the ridge up into the bore crown\n"
          f"  split by statics: rear (+Z) mount {r_plus:.1f} N, front (-Z) mount {r_minus:.1f} N, on {M.SUPPORT_Z_THICK:.2f} mm of ridge each\n\n"
          f"What the budget needs: knife.rolling_resistance_mm is assumed 0.005 mm (no source; 'until measured').\n"
          f"  Sweeping it in error_budget.py: the knife term spends its 0.45 % allowance at 0.0101 mm, but the\n"
          f"  pair-consistency gate (expected worst coefficient 2.0 %) fails first, at {F_CEIL:.4f} mm.\n\n"
          f"Options: A0 leave the print silent | A name gray iron, edges as machined, not hardened |\n"
          f"  B1 whole lever 4140 HT | B2 O1 strips hardened in the shop | C1 bought HSS strips | D coupon first\n"
          f"  (C2, a bought dowel as the edge, rolls on R.0625 instead of R.004: it changes the knife's geometry)",
          va="top", fontsize=8.2, family="monospace")
contact_chart(fig.add_subplot(gs[2, 0:2]))
swing_chart(fig.add_subplot(gs[2, 2:]))
fig.suptitle("#1611  MHA-SM-03 summing lever knife edge: what it carries, what the budget needs, and the options "
             "(to scale except the coupon sketch; numbers from origin/main specs)", fontsize=11)
out = OUT / "issue-1611-knife-options.png"
fig.savefig(out, dpi=110, bbox_inches="tight")
print(out)
