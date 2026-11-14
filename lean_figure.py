"""Owner figure: the phasing comb's lean, and two ways to stop it (#2734).

Run from the worktree root: uv run python C:/farm-runs/comb/lean_figure.py
All geometry in mm, to scale, from the comb spec and the cone-gear profiles.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle
from mpl_toolkits.axes_grid1.inset_locator import inset_axes, mark_inset

sys.path.insert(0, "cad/scripts")
import dt_cone_gear_tl_phasing_comb_spec as s  # noqa: E402

OUT = Path("C:/Users/pedro/Downloads/dfm-v48-decisions/comb-lean-options.png")
T = s.SHEET_THICK
SEAT = sum(s.SEAT_EDGE_MM) / 2.0  # T030 blade edge radius, on the root
TOP = SEAT + s.SHEET_HEIGHT
D006 = s.BLADE_DEPTH_MM[6]
GREY, BLUE, RED, GREEN = "0.55", "#1f5fbf", "#c0392b", "#1e8449"


def worst_phase(teeth: int, lean_deg: float) -> float:
    """Worst pitch-arc phase of a bonded gear with the sheet leaned by
    ``lean_deg`` about its T030 root contact (the spec's own windows)."""
    worst = 0.0
    lean = math.radians(lean_deg)
    depth = s.BLADE_DEPTH_MM[teeth]
    for corner, edge, mid, sheet in s._conditions(teeth, depth):
        for sign in (-1, 1):
            try:
                low, high = s._window(
                    teeth,
                    corner,
                    edge + depth * (1 - math.cos(lean)),
                    mid + sign * depth * math.sin(lean),
                    sheet / math.cos(lean),
                )
            except ValueError:
                continue
            if high > low:
                worst = max(worst, high, -low)
    return worst * s.pitch_radius_mm(teeth)


def geometric_lean_deg() -> float:
    """How far the nominal sheet can lean in T030's space about its root
    contact before its face meets a flank."""
    radii, gaps = s._gap_table(30, 0)
    r0 = radii[0]
    return math.degrees(
        min(
            math.atan((r * math.sin(g) - T / 2) / (r - r0))
            for r, g in zip(radii[1:], gaps[1:], strict=True)
        )
    )


def gear_xy(teeth: int, centre_deg: float = 90.0) -> list[tuple[float, float]]:
    """Outline of ``teeth``'s gear (printed corner 0), one space centred on
    ``centre_deg``."""
    radii, gaps = s._gap_table(teeth, 0)
    pitch = 2 * math.pi / teeth
    c0 = math.radians(centre_deg)
    pts: list[tuple[float, float]] = []
    for k in range(teeth):
        c = c0 + k * pitch
        for r, g in zip(reversed(radii), reversed(gaps), strict=True):
            pts.append((r * math.cos(c - g), r * math.sin(c - g)))
        for r, g in zip(radii, gaps, strict=True):
            pts.append((r * math.cos(c + g), r * math.sin(c + g)))
    return pts


def strip(y0: float, y1: float, lean_deg: float, pivot=(0.0, SEAT)):
    """The sheet seen end-on, from y0 up to y1, leaned about ``pivot``."""
    a = math.radians(lean_deg)
    corners = [(-T / 2, y0), (T / 2, y0), (T / 2, y1), (-T / 2, y1)]
    out = []
    for x, y in corners:
        dx, dy = x - pivot[0], y - pivot[1]
        out.append(
            (
                pivot[0] + dx * math.cos(a) + dy * math.sin(a),
                pivot[1] - dx * math.sin(a) + dy * math.cos(a),
            )
        )
    return out


def draw_gears(ax, *, light=False):
    ax.add_patch(
        Polygon(gear_xy(30), closed=True, fc="0.93", ec="0.25", lw=0.8, zorder=1)
    )
    for teeth in (24, 18, 12, 6):
        ax.add_patch(
            Polygon(
                gear_xy(teeth),
                closed=True,
                fc="none",
                ec="0.7" if teeth != 6 else "0.25",
                lw=0.6 if teeth != 6 else 0.8,
                ls="--" if teeth != 6 else "-",
                zorder=1,
            )
        )


lean_geo = geometric_lean_deg()
p1 = {t: worst_phase(t, 1.0) for t in (6, 12)}
pg = {t: worst_phase(t, lean_geo) for t in (6, 12)}
p0 = {t: worst_phase(t, 0.0) for t in (6, 12)}
p05 = worst_phase(6, 0.5)
book = s.BOND_CLOCK_TOLERANCE_MM
print(f"lean geo {lean_geo:.1f} deg; T006 0:{p0[6]:.3f} 1:{p1[6]:.3f} geo:{pg[6]:.3f}")

fig = plt.figure(figsize=(18, 16), dpi=150)
gs = fig.add_gridspec(4, 2, height_ratios=[1.25, 0.32, 1.0, 0.22], hspace=0.12, wspace=0.12)


def caption(cell, text):
    cap = fig.add_subplot(cell)
    cap.axis("off")
    cap.text(0.0, 1.0, text, fontsize=10, va="top", transform=cap.transAxes)

fig.suptitle(
    "MHA-DT-03-TL-02 phasing comb: a thin flat sheet can tip sideways in T030's tooth space\n"
    "and that moves the small gears it sets. Looking along the cone axis, to scale (mm).",
    fontsize=14,
    y=0.985,
)

# --- Panel 1: flat sheet leaning ------------------------------------------------
ax = fig.add_subplot(gs[0, 0])
draw_gears(ax)
for lean, colour, label in (
    (0.0, GREY, "upright (today's proof)"),
    (1.0, BLUE, "tipped 1 deg"),
    (lean_geo, RED, f"tipped {lean_geo:.0f} deg (T030's space limit)"),
):
    ax.add_patch(
        Polygon(
            strip(SEAT - D006, TOP, lean),
            closed=True,
            fc=colour,
            ec=colour,
            alpha=0.55 if lean else 0.35,
            lw=0.8,
            zorder=3,
            label=label,
        )
    )
ax.plot(0, SEAT, "ko", ms=4, zorder=4)
ax.annotate(
    "sheet rests on T030's tooth-space floor here;\nnothing stops it tipping about this line",
    xy=(0, SEAT),
    xytext=(-12.5, 11.5),
    fontsize=8.5,
    arrowprops=dict(arrowstyle="->", lw=0.8),
)
ax.annotate(
    "T006 (smallest gear, solid outline):\nits blade swings sideways with the tip",
    xy=(0, SEAT - D006),
    xytext=(-12.5, -8.3),
    fontsize=8.5,
    arrowprops=dict(arrowstyle="->", lw=0.8),
)
ax.text(-12.5, 15.2, "T030 (shaded); T024, T018, T012 dashed", fontsize=8.5)
ax.set_xlim(-13, 13)
ax.set_ylim(-9, 16.5)
ax.set_aspect("equal")
ax.legend(loc="lower right", fontsize=8.5)
ax.set_title("1. Today's flat sheet", fontsize=12, loc="left")
ins = inset_axes(ax, width="36%", height="36%", loc="upper right", borderpad=0.6)
draw_gears(ins)
for lean, colour in ((0.0, GREY), (1.0, BLUE), (lean_geo, RED)):
    ins.add_patch(
        Polygon(strip(SEAT - D006, TOP, lean), closed=True, fc=colour, ec=colour, alpha=0.5)
    )
ins.set_xlim(-2.3, 2.3)
ins.set_ylim(-0.6, 3.4)
ins.set_aspect("equal")
ins.set_xticks([])
ins.set_yticks([])
ins.set_title("T006, enlarged", fontsize=8)
mark_inset(ax, ins, loc1=3, loc2=4, fc="none", ec="0.5", lw=0.6)
caption(
    gs[1, 0],
    f"How far T006 can end up from where it should be (along its pitch circle):\n"
    f"  upright {p0[6]:.2f} mm; tipped 1 deg {p1[6]:.2f} mm; tipped {lean_geo:.0f} deg {pg[6]:.2f} mm.\n"
    f"  The machine's accuracy budget allows {book:.2f} mm today; even half a degree is over\n"
    f"  ({p05:.2f} mm). A person holding a shim cannot hold it square to a fraction of a degree.",
)

# --- Panel 2: option (a), one bent tab on T030's tips ---------------------------
ax = fig.add_subplot(gs[0, 1])
draw_gears(ax)
radii, gaps = s._gap_table(30, 0)
r_tip, g_tip = radii[-1], gaps[-1]
pitch = 2 * math.pi / 30
c = math.pi / 2
a1, a2 = c - (pitch - g_tip), c - (pitch + g_tip)  # tooth 1 outer, tooth 2 inner (right side)
P1 = (r_tip * math.cos(a1), r_tip * math.sin(a1))
P2 = (r_tip * math.cos(a2), r_tip * math.sin(a2))
slope = (P2[1] - P1[1]) / (P2[0] - P1[0])
y_bend = P1[1] + (T / 2 - P1[0]) * slope
droop = math.degrees(math.atan(-slope))
L_tab = 3.0
ux, uy = math.cos(math.atan(slope)), math.sin(math.atan(slope))
nx, ny = -uy, ux
tab = [
    (T / 2, y_bend),
    (T / 2 + L_tab * ux, y_bend + L_tab * uy),
    (T / 2 + L_tab * ux + T * nx, y_bend + L_tab * uy + T * ny),
    (T / 2 + T * nx, y_bend + T * ny),
]
blade_edge = SEAT + 0.15
ax.add_patch(Polygon(strip(blade_edge - D006, TOP, 0.0), closed=True, fc=GREEN, ec=GREEN, alpha=0.45, zorder=3))
ax.add_patch(Polygon(tab, closed=True, fc=GREEN, ec="k", lw=0.8, alpha=0.9, zorder=4))
ax.plot(*zip(P1, P2), "ko", ms=4, zorder=5)
ax.annotate(
    f"tab bent about {90 + droop:.0f} deg, lying on\nthe tips of the next two T030 teeth",
    xy=((P1[0] + P2[0]) / 2, (P1[1] + P2[1]) / 2 + 0.3),
    xytext=(2.5, 12.8),
    fontsize=8.5,
    arrowprops=dict(arrowstyle="->", lw=0.8),
)
ax.annotate(
    "press here, on the tab",
    xy=(T / 2 + 1.7 * ux, y_bend + 1.7 * uy + T),
    xytext=(5.5, 10.2),
    fontsize=8.5,
    color=GREEN,
    arrowprops=dict(arrowstyle="->", lw=1.0, color=GREEN),
)
ax.annotate(
    "the blade beside the tab still drops into\nthe space but no longer touches its floor",
    xy=(0, blade_edge),
    xytext=(-12.5, 11.5),
    fontsize=8.5,
    arrowprops=dict(arrowstyle="->", lw=0.8),
)
ax.set_xlim(-13, 13)
ax.set_ylim(-9, 16.5)
ax.set_aspect("equal")
ax.set_title("2. Option (a): the same sheet with one bent tab", fontsize=12, loc="left")
span = math.dist(P1, P2)
caption(
    gs[1, 1],
    f"The tab's two resting points are {span:.1f} mm apart, so the sheet now stands at the\n"
    f"bend angle. A bend held to +/-1 deg (a hand bend in a vise, checked with a square)\n"
    f"leaves T006 up to {p1[6]:.2f} mm out, so the budget figure would rise from {book:.2f} to\n"
    f"about 0.53 mm; the machine's accuracy budget still closes up to about 1.2 mm.\n"
    f"Catch: the tooth-tip edges are deburred (up to .010 in); an uneven deburr under the\n"
    f"two resting points tips the sheet too ({span:.1f} mm lever), so those two tips must be\n"
    f"left as cut. Same .020 brass; no change of stock.",
)

# --- Panel 2b: flat pattern of option (a) ---------------------------------------
ax = fig.add_subplot(gs[2, 0])
pts = s.profile_points_mm()
blade_hi = 3.3
tab_lo, tab_hi = 3.8, 6.3
slit = 0.4
bend_h = y_bend - SEAT
tab_bottom = bend_h - L_tab
outline = []
for x, y in pts:
    outline.append((x, y))
# Insert the tab into the T030 level's bottom edge (seat line, y = 0).
south_bottom = pts.index((0.0, 0.0))
step_x = s.BLADE_START_MM[24]
new = []
for i, (x, y) in enumerate(outline):
    new.append((x, y))
    if i == south_bottom:
        new += [
            (tab_lo - slit, 0.0),
            (tab_lo - slit, bend_h),
            (tab_lo, bend_h),
            (tab_lo, tab_bottom),
            (tab_hi, tab_bottom),
            (tab_hi, bend_h),
            (tab_hi + slit, bend_h),
            (tab_hi + slit, 0.0),
        ]
ax.add_patch(Polygon(new, closed=True, fc="#e8d9a8", ec="k", lw=0.9))
ax.plot([tab_lo, tab_hi], [bend_h, bend_h], "k--", lw=1.0)
ax.text((tab_lo + tab_hi) / 2, bend_h + 0.35, "bend line", ha="center", fontsize=8.5)
ax.annotate(
    "tab: bent toward the viewer\nafter cutting",
    xy=((tab_lo + tab_hi) / 2, tab_bottom + 0.6),
    xytext=(8.0, -4.2),
    fontsize=8.5,
    arrowprops=dict(arrowstyle="->", lw=0.8),
)
ax.annotate(
    "T030 blade (both sides of the tab)",
    xy=(1.6, 0.0),
    xytext=(-1.5, -5.0),
    fontsize=8.5,
    arrowprops=dict(arrowstyle="->", lw=0.8),
)
ax.add_patch(
    Rectangle(
        (-s.BLADE_INSET, -7.5),
        s.FACE_WIDTH,
        14.5,
        fc="none",
        ec=GREY,
        ls=":",
        lw=1.0,
    )
)
ax.text(-s.BLADE_INSET + 0.2, 6.2, "T030's tooth width", fontsize=8, color="0.4")
for t in s.BONDED_TEETH:
    x0, _x1 = s.blade_x_mm(t)
    if x0 < 16:
        ax.text(x0 + 0.3, -s.BLADE_DEPTH_MM[t] - 0.9, s.gear_tag(t), fontsize=8)
ax.text(0.3, 0.4, "T030", fontsize=8)
ax.set_xlim(-2, 17)
ax.set_ylim(-5.5, 7.5)
ax.set_aspect("equal")
ax.set_title("2b. Option (a) cut flat, before its one bend (side view, T030 end)", fontsize=12, loc="left")
caption(gs[3, 0], "Two short slits free the tab; it is bent along the dashed line. The tab sits inside\nT030's tooth width (dotted), between two lengths of the T030 blade.")

# --- Panel 3: option (b), U arm into T030's opposite space ----------------------
ax = fig.add_subplot(gs[2, 1])
south = [s._south_face_mm(t) - s.BLADE_INSET for t in s.GEARS]
for t, x0 in zip(s.GEARS, south, strict=True):
    rt = s.tip_radius_limits_mm(t)[1]
    ax.add_patch(Rectangle((x0, -rt), s.FACE_WIDTH, 2 * rt, fc="0.9", ec="0.3", lw=0.8))
    ax.text(x0 + s.FACE_WIDTH / 2, rt + 0.4, s.gear_tag(t), ha="center", fontsize=8)
for k, teeth in enumerate((36, 42)):
    rt = (teeth / 30) * s.tip_radius_limits_mm(30)[1]
    x0 = -s.BLADE_INSET - (k + 1) * s.FACE_WIDTH
    ax.add_patch(Rectangle((x0, -rt), s.FACE_WIDTH, 2 * rt, fc="0.95", ec="0.6", lw=0.6))
    ax.text(x0 + s.FACE_WIDTH / 2, rt + 0.4, f"T{teeth:03d}", ha="center", fontsize=8, color="0.4")
end_x = south[-1] + s.FACE_WIDTH
ax.add_patch(Rectangle((end_x, -1.6), 9.0, 3.2, fc="0.85", ec="0.3", lw=0.8, hatch="//"))
ax.text(end_x + 4.5, 2.1, "MHA-DT-37 pivot end\n(length schematic)", ha="center", fontsize=8)
# Flat comb on top, as now.
top_comb = [(x, SEAT + y) for x, y in s.profile_points_mm()]
ax.add_patch(Polygon(top_comb, closed=True, fc=BLUE, alpha=0.35, ec=BLUE))
# U arm: from the comb's north end, round past the pivot end, back under to T030.
r_root = s.root_radius_mm(30, 0)
arm_out = end_x + 12.0
u = [
    (s.SHEET_LENGTH, SEAT + s.SHEET_HEIGHT),
    (arm_out, SEAT + s.SHEET_HEIGHT),
    (arm_out, -(r_root + s.SHEET_HEIGHT)),
    (0.0, -(r_root + s.SHEET_HEIGHT)),
    (0.0, -r_root),
    (s.BLADE_START_MM[24], -r_root),
    (s.BLADE_START_MM[24], -(r_root + 2.0)),
    (arm_out - 2.0, -(r_root + 2.0)),
    (arm_out - 2.0, SEAT + s.SHEET_HEIGHT - 2.0),
    (s.SHEET_LENGTH, SEAT + s.SHEET_HEIGHT - 2.0),
]
ax.add_patch(Polygon(u, closed=True, fc=BLUE, alpha=0.18, ec=BLUE, ls="--"))
ax.add_patch(Rectangle((end_x + 1.0, -5.0), 12.0, 10.0, fc=RED, alpha=0.18, ec=RED))
ax.text(
    end_x + 7.0,
    -9.6,
    "step 2C: a hand holds MHA-DT-37\nhome right here; the U arm\nwould have to pass through it",
    ha="center",
    fontsize=8.5,
    color=RED,
)
ax.annotate(
    "second blade: drops into T030's tooth space\ndirectly opposite (30 teeth, so a space faces a space)",
    xy=(2.0, -r_root),
    xytext=(-15.0, -17.5),
    fontsize=8.5,
    arrowprops=dict(arrowstyle="->", lw=0.8),
)
lean_u = math.degrees((2 * (0.283 - s.SHEET_LIMITS_MM[0] / 2)) / (2 * r_root))
ax.set_title("3. Option (b): one flat sheet cut as a U that also reaches T030's opposite side (side view)", fontsize=12, loc="left")
caption(
    gs[3, 1],
    f"The two T030 blades are {2 * r_root:.1f} mm apart, so the sheet can tip only about "
    f"{lean_u:.1f} deg (T006 about {worst_phase(6, lean_u):.2f} mm).\n"
    "But the U must go round the cone's tip end, where step 2C's hand holds MHA-DT-37 home; "
    "and the stack must be reachable from below.",
)
ax.axhline(0, color="0.5", lw=0.5, ls="-.")
ax.set_xlim(-16, 66)
ax.set_ylim(-20, 17)
ax.set_aspect("equal")
ax.set_xticks([])
ax.set_yticks([])

for a in fig.axes:
    if a is not ins:
        a.tick_params(labelsize=8)
OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, bbox_inches="tight")
print(OUT)
