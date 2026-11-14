"""Owner figure: the cone built standing up, with a U comb clipped over its
tip (#2734, owner reply 2026-11-13). To scale (mm) from the comb, cone-gear,
shaft and tip specs; run from the worktree root.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle

sys.path.insert(0, "cad/scripts")
import dt_cone_gear_tl_phasing_comb_spec as s  # noqa: E402
import dt_cone_tip_bushing_spec as bushing  # noqa: E402
import dt_cone_tip_gear_spec as tip  # noqa: E402

OUT = Path("C:/Users/pedro/Downloads/dfm-v48-decisions/comb-upright-u.png")
T = s.SHEET_THICK
SEAT = sum(s.SEAT_EDGE_MM) / 2.0
FW = s.FACE_WIDTH
FEELER = s.STACK_FEELER
ARM = s.SHEET_HEIGHT  # arm width, as today's sheet height
BLUE, GREY, RED, GREEN = "#1f5fbf", "0.55", "#c0392b", "#1e8449"
LEAN_DEG, T006_ERR, T012_ERR = 0.39, 0.50, 0.41  # u_model.py, clamped U, float as a circle
BOOK_NOW = s.BOND_CLOCK_TOLERANCE_MM


def tip_r(teeth: int) -> float:
    return s.tip_radius_limits_mm(teeth)[1] if teeth <= 30 else (teeth + 2) * 0.5291667 / 2


# Axial stations, z up from T030's lower face (= T036's upper face).
z_south = {30: 0.0, 24: FW + FEELER}
for a, b in ((24, 18), (18, 12), (12, 6)):
    z_south[b] = z_south[a] + FW
TIP_TOP = z_south[6] + FW
PIVOT_TOP = TIP_TOP + tip.PIVOT_LENGTH_MM
BUSH_TOP = TIP_TOP + bushing.LENGTH
BRIDGE_LOW = PIVOT_TOP + 3.0
BRIDGE_HIGH = BRIDGE_LOW + 6.0
SHAFT_END = z_south[18] - 0.4


def near_arm_edge() -> list[tuple[float, float]]:
    """Inner (stepped) edge of the near arm, bottom to top, x negative."""
    pts = [(-SEAT, 0.0)]
    for teeth in s.GEARS[1:]:
        z = s.BLADE_START_MM[teeth] + s.BLADE_INSET
        prev = pts[-1][0]
        pts += [(prev, z), (-(SEAT - s.BLADE_DEPTH_MM[teeth]), z)]
    top = s.SHEET_LENGTH + s.BLADE_INSET
    clear = bushing.OUTER_DIA / 2 + 1.0
    pts += [(pts[-1][0], top), (-clear, top), (-clear, BRIDGE_LOW)]
    return pts


def u_outline() -> list[tuple[float, float]]:
    inner = near_arm_edge()
    out = [(-(SEAT + ARM), 0.0)] + inner
    out += [(SEAT, BRIDGE_LOW), (SEAT, 0.0), (SEAT + ARM, 0.0), (SEAT + ARM, BRIDGE_HIGH), (-(SEAT + ARM), BRIDGE_HIGH)]
    return out


def gear_xy(teeth: int, centre_deg: float = 90.0):
    radii, gaps = s._gap_table(teeth, 0)
    pitch = 2 * math.pi / teeth
    c0 = math.radians(centre_deg)
    pts = []
    for k in range(teeth):
        c = c0 + k * pitch
        for r, g in zip(reversed(radii), reversed(gaps), strict=True):
            pts.append((r * math.cos(c - g), r * math.sin(c - g)))
        for r, g in zip(radii, gaps, strict=True):
            pts.append((r * math.cos(c + g), r * math.sin(c + g)))
    return pts


fig = plt.figure(figsize=(18, 13), dpi=150)
gs = fig.add_gridspec(2, 3, height_ratios=[1.0, 0.30], width_ratios=[1.25, 1.0, 0.9], hspace=0.05, wspace=0.18)
fig.suptitle(
    'Owner: "what if cone is assembled standing on its side like a pyramid"\n'
    "MHA-DT-03-TL-02 as one flat U, clipped over the standing cone's tip. To scale (mm).",
    fontsize=14,
    y=0.99,
)


def caption(cell, text):
    cap = fig.add_subplot(cell)
    cap.axis("off")
    cap.text(0.0, 1.0, text, fontsize=10, va="top", transform=cap.transAxes)


# --- 1. Side view, standing ------------------------------------------------------
ax = fig.add_subplot(gs[0, 0])
ax.add_patch(Rectangle((-4.7625, -22.0), 9.525, 22.0 + SHAFT_END, fc="0.8", ec="0.4", lw=0.6))
ax.add_patch(Rectangle((-3.175, FW, ), 6.35, SHAFT_END - FW, fc="0.8", ec="0.4", lw=0.6))
for k, teeth in enumerate((36, 42)):
    r = tip_r(teeth)
    ax.add_patch(Rectangle((-r, -(k + 1) * FW), 2 * r, FW, fc="0.93", ec="0.5", lw=0.7))
    ax.text(r + 0.5, -(k + 0.5) * FW, f"T{teeth:03d} (keyed)", fontsize=8, va="center", color="0.4")
ax.text(0, -22.6, "T048 ... T120 and the journal below, held upright in soft vise jaws", ha="center", fontsize=8.5, va="top")
for teeth in s.GEARS:
    r = tip_r(teeth)
    ax.add_patch(Rectangle((-r, z_south[teeth]), 2 * r, FW, fc="0.88" if teeth == 30 else "#f2e6c2", ec="0.3", lw=0.8))
    ax.text(r + 0.5, z_south[teeth] + FW / 2, s.gear_tag(teeth) + (" (keyed)" if teeth == 30 else " (bonded)"), fontsize=8, va="center")
ax.add_patch(Rectangle((-tip.STEM_DIA_MM / 2, TIP_TOP), tip.STEM_DIA_MM, tip.PIVOT_LENGTH_MM, fc="#f2e6c2", ec="0.3", lw=0.6))
ax.add_patch(Rectangle((-bushing.OUTER_DIA / 2, TIP_TOP), bushing.OUTER_DIA, bushing.LENGTH, fc="#e0c98f", ec="0.3", lw=0.6))
ax.text(bushing.OUTER_DIA / 2 + 0.5, TIP_TOP + bushing.LENGTH / 2, "MHA-DT-38 on MHA-DT-37's pivot", fontsize=8, va="center")
ax.add_patch(Polygon(u_outline(), closed=True, fc=BLUE, alpha=0.35, ec=BLUE, lw=1.0, zorder=5))
for x in (-(SEAT + ARM / 2), SEAT + ARM / 2):
    ax.annotate("", xy=(x, 0.1), xytext=(x, -3.5), arrowprops=dict(arrowstyle="->", color=BLUE))
ax.text(-(SEAT + ARM + 1.0), 1.5, "both arms stand\non T036's top face", ha="right", fontsize=8.5, color=BLUE)
ax.text(0, BRIDGE_HIGH + 1.2, "U comb, one flat sheet, clipped over the tip", ha="center", fontsize=9, color=BLUE)
ax.annotate("", xy=(-SEAT, 3.5), xytext=(-SEAT - 3.5, 3.5), arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.5))
ax.annotate("", xy=(SEAT, 3.5), xytext=(SEAT + 3.5, 3.5), arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.5))
ax.text(-29.5, -9.0, "the U grips T030 lightly\nacross: both T030 blades\nheld on T030's tooth-space\nfloor", ha="left", fontsize=8.5, color=GREEN)
for z, label in ((z_south[24] + FW / 2, "gravity: T024 sits\non the feeler on T030"), (z_south[12], "T018, T012 and\nMHA-DT-37 stack\ndown on T024")):
    ax.annotate(label, xy=(-1.5, z), xytext=(-29.5, z + 6), fontsize=8.5, arrowprops=dict(arrowstyle="->", lw=0.7))
ax.annotate("", xy=(-27, 40), xytext=(-27, 50), arrowprops=dict(arrowstyle="-|>", lw=2, color="0.3"))
ax.text(-27.5, 45, "g", fontsize=12, ha="right", va="center")
ax.set_xlim(-30, 22)
ax.set_ylim(-24, BRIDGE_HIGH + 3)
ax.set_aspect("equal")
ax.set_title("1. Side view: cone standing on its big end, tip up", fontsize=12, loc="left")

# --- 2. End view down the axis -----------------------------------------------------
ax = fig.add_subplot(gs[0, 1])
ax.add_patch(Polygon(gear_xy(30), closed=True, fc="0.9", ec="0.25", lw=0.8))
for teeth in (24, 18, 12, 6):
    ax.add_patch(Polygon(gear_xy(teeth), closed=True, fc="none", ec="0.6", lw=0.5, ls="--"))
for sign in (1, -1):
    y0 = sign * SEAT
    y1 = sign * (SEAT + ARM)
    ax.add_patch(Rectangle((-T / 2, min(y0, y1)), T, abs(y1 - y0), fc=BLUE, ec=BLUE, alpha=0.8, zorder=4))
    ax.annotate("", xy=(0.9, y0), xytext=(0.9, y0 + sign * 3.0), arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.4))
ax.add_patch(Rectangle((-T / 2, -SEAT), T, 2 * SEAT, fc=BLUE, ec="none", alpha=0.18, zorder=3))
ax.text(1.4, SEAT + 3.6, "blade 1: a T030 tooth\nspace beside the key", fontsize=8.5)
ax.text(1.4, -SEAT - 4.6, "blade 2: the opposite\nT030 space", fontsize=8.5)
ax.annotate(
    f"{2 * SEAT:.1f} mm apart: the U can turn\nat most about {LEAN_DEG:.1f} deg",
    xy=(-0.4, 0),
    xytext=(-13.0, -2.0),
    fontsize=9,
    arrowprops=dict(arrowstyle="->", lw=0.7),
)
ax.text(-13.0, 12.6, "Seen from above, the U is edge-on;\nits bridge passes over the tip (pale).", fontsize=8.5)
ax.set_xlim(-14, 14)
ax.set_ylim(-15, 15)
ax.set_aspect("equal")
ax.set_title("2. Looking down the axis", fontsize=12, loc="left")

# --- 3. Flat pattern -----------------------------------------------------------------
ax = fig.add_subplot(gs[0, 2])
ax.add_patch(Polygon(u_outline(), closed=True, fc="#d9dde3", ec="k", lw=1.0))
ax.annotate("", xy=(-SEAT, -2.0), xytext=(SEAT, -2.0), arrowprops=dict(arrowstyle="<->", lw=0.8))
ax.text(0, -3.4, f"{2 * SEAT:.2f} gap at the T030 blades", ha="center", fontsize=8.5, va="top")
ax.annotate("", xy=(SEAT + ARM + 1.5, 0), xytext=(SEAT + ARM + 1.5, BRIDGE_HIGH), arrowprops=dict(arrowstyle="<->", lw=0.8))
ax.text(SEAT + ARM + 2.2, BRIDGE_HIGH / 2, f"{BRIDGE_HIGH:.0f}", fontsize=8.5, va="center")
ax.annotate("", xy=(-(SEAT + ARM), BRIDGE_HIGH + 1.5), xytext=(SEAT + ARM, BRIDGE_HIGH + 1.5), arrowprops=dict(arrowstyle="<->", lw=0.8))
ax.text(0, BRIDGE_HIGH + 2.2, f"{2 * (SEAT + ARM):.0f}", ha="center", fontsize=8.5)
ax.text(-SEAT + 0.6, 10, "stepped blades:\nT024, T018,\nT012, T006", fontsize=8)
ax.text(SEAT - 0.6, 20, "plain\narm", fontsize=8, ha="right")
ax.set_xlim(-16, 19)
ax.set_ylim(-8, BRIDGE_HIGH + 5)
ax.set_aspect("equal")
ax.set_title("3. The part: cut from one flat sheet, no bend", fontsize=12, loc="left")

caption(
    gs[1, 0],
    "Standing it up: the journal goes in soft vise jaws (or a block with\n"
    "a 1/2 in hole). T024 sits on the feeler under its own weight; T018,\n"
    "T012 and MHA-DT-37 stack down onto T024, so no hand holds them\n"
    "(step 2C goes): push MHA-DT-37 home once, then let go. Squeeze-out\n"
    "runs down onto the waxed feeler and T030 face as today, and down the\n"
    "teeth, so the comb's blades get the same wax. Air under MHA-DT-37's\n"
    "spigot now rises out through the glue instead of staying put.",
)
caption(
    gs[1, 1],
    f"How far each small gear can end up out (pitch circle):\n"
    f"T006 about {T006_ERR:.2f} mm, T012 {T012_ERR:.2f} mm (today's flat\n"
    f"sheet held perfectly upright: 0.48). The accuracy-budget\n"
    f"figure moves from {BOOK_NOW:.3f} to about 0.51 mm; the budget\n"
    "closes up to 1.0 mm. The light grip matters: a loose U\n"
    "slides sideways up to 0.6 mm and T006 could be 1.2 mm out.",
)
caption(
    gs[1, 2],
    "Sturdy: the blades must stay about .020 thick (the\n"
    "spaces are 0.57 mm wide at the floor; a .025 blade\n"
    "rides higher and does worse).\n"
    "Stiffness comes from the material: steel is\n"
    "about 1.9x stiffer than brass at the same .020,\n"
    "whatever the temper. Blue-tempered spring steel\n"
    "(or full-hard stainless) also springs back from a\n"
    "knock instead of taking a set, and holds the grip.",
)
for a in fig.axes:
    a.tick_params(labelsize=8)
OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, bbox_inches="tight")
print(OUT, f"bridge {BRIDGE_HIGH:.1f} high, overall {2 * (SEAT + ARM):.1f} wide")
