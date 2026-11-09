"""Cone-tip options against the 2026-11-08 machinist-review rubric (main a8441605f, v47 geometry).

Side views to scale (mm); x = 0 at the T018 big-end (south) face, tip to the right.
Geometry is read from cad/scripts on main (dt_cone_gear_spec, dt_cone_gear_shaft_spec,
dt_vn_cone_tip_collar_spec, dt_cone_tip_block_spec); see the review's "Reproducing" section.
Usage: uv run --no-project --with matplotlib python cone_tip_options.py geometry.json out.png
"""

import json
import math
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Circle, Polygon, Rectangle

with open(sys.argv[1], encoding="utf-8") as f:
    GEO = json.load(f)
OUT = sys.argv[2]

IN = 25.4
FLOOR, TARGET = 0.060 * IN, 0.080 * IN  # rule 17, inch sheets
BORE_PLUS = 0.0018 * IN  # MHA-DT-03 bore band upper (+.0018)
REAM_PLUS = 0.0005 * IN  # shop table: reamed hole +.0005/0

SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#b8b7b0"
STEEL, STEEL_E = "#e4e3de", "#6b6a65"
BRASS, BRASS_E = "#f2d27a", "#9a6a00"  # C36000: T030-T120, tip bushing
BRONZE, BRONZE_E = "#d9a24a", "#7a5212"  # C67500 manganese bronze: T006-T024, arbors
BLOCK, BLOCK_E = "#77766f", "#2f2e2b"
INTEGRAL_E = "#1d5aa3"  # blue outline = part with integral teeth
CONTACT = "#1baf7a"
BAD, GOOD, WARN = "#d03b3b", "#0c8a0c", "#b8860b"

W = GEO["face_width"]
G = {int(k): v for k, v in GEO["gears"].items()}
SOUTH_T018 = GEO["T006_NORTH_FACE_STATION"] - 3 * W  # x origin, cone station
ENDS = [
    e - GEO["front_stub"] - SOUTH_T018 for e in GEO["section_ends"]
]  # DT-04 land ends, sketch x
DIAS = GEO["section_dias"]
AF = GEO["section_flat_af"]
X = {30: -2 * W, 24: -W, 18: 0.0, 12: W, 6: 2 * W}
T006_N = 3 * W
COLLAR0 = GEO["TIP_COLLAR_START_STATION"] - SOUTH_T018
COLLAR1 = GEO["TIP_COLLAR_END_STATION"] - SOUTH_T018
BLOCK_S = GEO["TIP_BLOCK_SOUTH_FACE_STATION"] - SOUTH_T018
BLOCK_N = GEO["TIP_BLOCK_NORTH_FACE_STATION"] - SOUTH_T018
CUP_RIM = GEO["ADJUSTER_CUP_RIM_STATION"] - SOUTH_T018
TIP = GEO["T006_TIP_STATION"] - SOUTH_T018
CONTACT_ZONE = (2.2, 5.3)  # from each band's big-end face; v45 GLB measurement

# ---- numbers the figure and the review quote --------------------------------------------
STEM = 1 / 16 * IN  # proposed T012 seat and pivot on the arbor
SPIGOT = 1 / 8 * IN
web = lambda t, bore: (G[t]["root_min"] - bore) / 2.0
N = {
    "t006_web_now": web(6, G[6]["bore"] + BORE_PLUS),
    "t012_web_now": web(12, G[12]["bore"] + BORE_PLUS),
    "t006_max_bore": G[6]["root_min"] - 2 * FLOOR,
    "t012_max_bore": G[12]["root_min"] - 2 * FLOOR,
    "t012_web_stem": web(12, STEM + BORE_PLUS),
    "t006_web_116": web(6, STEM + BORE_PLUS),
    "stem_under_t006_root": (G[6]["root_min"] - STEM) / 2.0,
    "spigot_wall_to_flat": (AF[1] - DIAS[1] / 2.0) - (SPIGOT + REAM_PLUS) / 2.0,
    "drill_rod_wall": (DIAS[3] - (GEO["section_dias"][4] + REAM_PLUS)) / 2.0,
    "bushing_wall": (5.0 - STEM) / 2.0,
}
for t, nb in ((24, 18), (18, 12), (12, 6)):
    h = (
        G[t]["od"] - G[nb]["root_min"]
    ) / 2.0  # neighbour shoulder above this band's root
    N[f"shoulder_{nb}"] = h
    N[f"runout_{nb}_r3175"] = math.sqrt(h * (2 * 3.175 - h)) if h < 3.175 else 3.175
with open(OUT.replace(".png", ".numbers.json"), "w", encoding="utf-8") as f:
    json.dump(N, f, indent=1)

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "text.color": INK,
        "axes.edgecolor": MUTED,
    }
)


def inch(mm, places=3):
    s = f"{mm / IN:.{places}f}"
    return s[1:] if s.startswith("0.") else s


def rect(ax, x0, x1, dia, fc, ec, lw=0.9, ls="-", z=2, hatch=None, y0=None):
    y = -dia / 2 if y0 is None else y0
    ax.add_patch(
        Rectangle(
            (x0, y), x1 - x0, dia, fc=fc, ec=ec, lw=lw, ls=ls, zorder=z, hatch=hatch
        )
    )


def gear(ax, t, fc, ec, bore=None, integral=False, z=3, label=True, x0=None, flat=None):
    x0 = X[t] if x0 is None else x0
    od, root = G[t]["od"], G[t]["root_min"]
    edge = INTEGRAL_E if integral else ec
    lw = 1.6 if integral else 0.9
    rect(ax, x0, x0 + W, od, fc, edge, lw=lw, z=z)
    for s in (1, -1):  # tooth band, hatched
        ax.add_patch(
            Rectangle(
                (x0, s * root / 2 if s > 0 else -od / 2),
                W,
                (od - root) / 2,
                fc="none",
                ec=ec,
                lw=0,
                hatch="||||",
                zorder=z + 0.1,
            )
        )
    ax.plot([x0, x0 + W], [root / 2, root / 2], color=ec, lw=0.5, zorder=z + 0.2)
    ax.plot([x0, x0 + W], [-root / 2, -root / 2], color=ec, lw=0.5, zorder=z + 0.2)
    if bore:
        for s in (1, -1):
            ax.plot(
                [x0, x0 + W],
                [s * bore / 2] * 2,
                color=INK2,
                lw=0.6,
                ls=(0, (2, 1.4)),
                zorder=z + 0.3,
            )
    if flat is not None:
        ax.plot(
            [x0, x0 + W],
            [flat, flat],
            color=INK2,
            lw=0.5,
            ls=(0, (1, 1.2)),
            zorder=z + 0.3,
        )
    c0, c1 = CONTACT_ZONE
    ax.plot(
        [x0 + c0, x0 + c1],
        [od / 2 + 0.45] * 2,
        color=CONTACT,
        lw=2.6,
        solid_capstyle="butt",
        zorder=z + 1,
    )
    if label:
        ax.text(
            x0 + W / 2,
            od / 2 + 1.1,
            f"T{t:03d}",
            ha="center",
            va="bottom",
            fontsize=8.2,
            fontweight="bold",
            zorder=9,
        )


def centreline(ax, x0, x1):
    ax.plot([x0, x1], [0, 0], color=INK2, lw=0.6, ls=(0, (8, 2, 1.5, 2)), zorder=8)


def note(ax, xy, xytext, text, mark=None, fs=7.6, ha="left"):
    color = {"bad": BAD, "good": GOOD, "warn": WARN, None: MUTED}[mark]
    prefix = {"bad": "✗ ", "good": "✓ ", "warn": "! ", None: ""}[mark]
    ax.annotate(
        prefix + text,
        xy=xy,
        xytext=xytext,
        fontsize=fs,
        ha=ha,
        va="center",
        zorder=10,
        arrowprops={
            "arrowstyle": "-",
            "color": INK2,
            "lw": 0.55,
            "shrinkA": 0,
            "shrinkB": 1.5,
        },
        bbox={"boxstyle": "round,pad=0.28", "fc": SURFACE, "ec": color, "lw": 0.9},
    )


def dim(ax, x0, x1, y, text, fs=7.0):
    ax.annotate(
        "",
        xy=(x0, y),
        xytext=(x1, y),
        arrowprops={
            "arrowstyle": "<->",
            "color": INK2,
            "lw": 0.6,
            "shrinkA": 0,
            "shrinkB": 0,
        },
        zorder=9,
    )
    ax.text(
        (x0 + x1) / 2,
        y - 0.35,
        text,
        ha="center",
        va="top",
        fontsize=fs,
        color=INK2,
        zorder=9,
    )


def frame(ax, title, verdict, mark, xlim=(-17, 52), ylim=(-19.0, 15.5)):
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, loc="left", fontsize=11.5, fontweight="bold", pad=22)
    col = {"bad": BAD, "good": GOOD, "warn": WARN}[mark]
    ax.text(
        0.0,
        1.015,
        verdict,
        transform=ax.transAxes,
        fontsize=8.0,
        va="bottom",
        ha="left",
        bbox={"boxstyle": "round,pad=0.3", "fc": SURFACE, "ec": col, "lw": 1.2},
    )


def tip_block(ax, adjuster):
    """MHA-DT-21 side view, truncated below; slit from the top; pinch screw seen end-on."""
    top = 52.578 - 38.1
    ax.add_patch(
        Rectangle(
            (BLOCK_S, -15.0),
            BLOCK_N - BLOCK_S,
            top + 15.0,
            fc=BLOCK,
            ec=BLOCK_E,
            lw=1.0,
            zorder=2.4,
        )
    )
    ax.plot(
        [BLOCK_S, BLOCK_N],
        [-15.0, -15.0],
        color=SURFACE,
        lw=2.5,
        ls=(0, (3, 2)),
        zorder=2.45,
    )
    mid = (BLOCK_S + BLOCK_N) / 2
    ax.add_patch(
        Circle((mid, 8.89), 1.42, fc="#d6d5cf", ec=BLOCK_E, lw=0.8, zorder=2.7)
    )  # #4-40 pinch
    ax.plot([mid - 1.0, mid + 1.0], [8.89, 8.89], color=BLOCK_E, lw=0.8, zorder=2.8)
    if adjuster == "cup":  # VN-55 #10-32 x 3/8
        a0, a1, d = CUP_RIM, CUP_RIM + 9.525, 4.826
    else:  # long 1/4-28 end screw
        a0, a1, d = END_FACE, BLOCK_N, 6.35
    rect(ax, a0, min(a1, BLOCK_N), d, "#cfcec8", BLOCK_E, lw=0.7, z=2.55)
    for s in (1, -1):
        ax.plot(
            [max(a0, BLOCK_S), min(a1, BLOCK_N)],
            [s * d / 2] * 2,
            color="#efeee9",
            lw=0.6,
            ls=(0, (2, 1.4)),
            zorder=2.6,
        )
    if adjuster == "cup":
        rect(ax, BLOCK_N, a1, d, "#cfcec8", BLOCK_E, lw=0.7, z=2.55)
        ax.add_patch(
            Polygon(
                [[a0, 1.3], [a0 + 1.21, 0.55], [a0 + 1.21, -0.55], [a0, -1.3]],
                closed=True,
                fc=SURFACE,
                ec=BLOCK_E,
                lw=0.6,
                zorder=2.65,
            )
        )  # cup
    else:
        ax.add_patch(
            Polygon(
                [
                    [BLOCK_N, -4.6],
                    [BLOCK_N + 1.3, -4.6],
                    [BLOCK_N + 2.8, -2.6],
                    [BLOCK_N + 3.2, 0],
                    [BLOCK_N + 2.8, 2.6],
                    [BLOCK_N + 1.3, 4.6],
                    [BLOCK_N, 4.6],
                ],
                closed=True,
                fc=BLOCK,
                ec=BLOCK_E,
                lw=0.9,
                zorder=2.6,
            )
        )
        ax.plot(
            [BLOCK_N + 1.6, BLOCK_N + 3.2], [0, 0], color="#efeee9", lw=1.0, zorder=2.7
        )  # slot


END_FACE = T006_N + 4.4  # option A/B: end-screw inner face (bushing 4 mm + .4 end play)
PIVOT_END = END_FACE + 4.0

fig = plt.figure(figsize=(17, 23.0), dpi=150, facecolor=SURFACE)
gs = GridSpec(
    4,
    2,
    figure=fig,
    height_ratios=[1, 1, 1, 0.62],
    hspace=0.30,
    wspace=0.06,
    left=0.025,
    right=0.985,
    top=0.885,
    bottom=0.03,
)
fig.text(
    0.025,
    0.983,
    "Cone tip (T006–T024): main as of 2026-11-09 vs options, judged by the 2026-11-08 machinist-review rubric",
    fontsize=15,
    fontweight="bold",
    va="top",
)
fig.text(
    0.025,
    0.968,
    "Side views to scale (mm), x = 0 at the T018 big-end face, tip to the right. Geometry from main a8441605f (MHA-DT-03/-04/-21, VN-54/-55); "
    "the inch sheets print the same model.\nGreen bars: where the 120T cylinder gear touches each band (2.2–5.3 mm from its big-end face, v45 GLB). "
    "Fill = material: manganese bronze C67500 for T006–T024 and new tip parts (main's material_tip_specification),\n"
    "brass C36000 from T030, steel for DT-04 and the screws. Blue outline = part with integral teeth. Dashed = bores and hidden seats.\n"
    f"Rule 17 (inch sheets): every machined wall or web ≥ .060 in ({FLOOR:.2f} mm) floor, .080 in target, at the printed worst case. "
    "\nRule 23: a joint carrying drive torque is held by a key or flat with axial capture, a cross or taper pin, or a press or bonded fit; solder and a plain set screw never count.\n"
    "Real tip (book pp.17–21, engineerguy video 4 at 6:36–6:39): a small brass bushing fixed on the pivot turns with the cone and bears on a long end screw "
    "through a black split block, locked by a side pinch screw. Nothing like VN-54.",
    fontsize=8.6,
    color=INK2,
    va="top",
    linespacing=1.45,
)

# ---------------- Panel 1: main today
ax = fig.add_subplot(gs[0, 0])
frame(
    ax,
    "1 · Main today (v47 inch sheets)",
    "Ships only under owner exceptions RV-01/RV-04 (DT-03) and RV-01/RV-02 (DT-04), all pending #1649",
    "bad",
)
rect(ax, -17, ENDS[1], DIAS[1], STEEL, STEEL_E)
rect(ax, ENDS[1], ENDS[2], DIAS[2], STEEL, STEEL_E)
rect(ax, ENDS[2], ENDS[3], DIAS[3], STEEL, STEEL_E)
rect(ax, ENDS[3], TIP, DIAS[4], STEEL, STEEL_E, z=3.6)
gear(ax, 30, BRASS, BRASS_E, bore=DIAS[1])
for t in (24, 18, 12, 6):
    gear(ax, t, BRONZE, BRONZE_E, bore=G[t]["bore"])
rect(ax, COLLAR0, COLLAR0 + 3.5, 6.35, STEEL, STEEL_E, z=3.4)
rect(ax, COLLAR0 + 3.5, COLLAR1, 16.764, STEEL, STEEL_E, z=3.4)
ax.add_patch(
    Rectangle(
        (COLLAR0 + 7.5 - 1.09, 0.3),
        2.18,
        8.08,
        fc="#c9c8c2",
        ec=STEEL_E,
        lw=0.6,
        zorder=3.5,
    )
)
ax.text(
    (COLLAR0 + 3.5 + COLLAR1) / 2,
    -4.6,
    "VN-54\nØ.660 × .453\nsteel collar,\n2-56 set screw\non the flat",
    ha="center",
    va="center",
    fontsize=6.8,
    color=INK2,
    zorder=4,
)
tip_block(ax, "cup")
centreline(ax, -17, 50)
note(
    ax,
    (16.5, 1.0),
    (-16.5, -12.4),
    f"T006 bore Ø.031 D: web {inch(N['t006_web_now'], 4)} MIN, under the .060 floor (RV-04)",
    "bad",
)
note(
    ax,
    (10.0, 2.0),
    (-3, 12.8),
    f"T012 web {inch(N['t012_web_now'], 4)} MIN, just under the .080 target (RV-03)",
    "warn",
)
note(
    ax,
    (30.0, 0.4),
    (26, -14.4),
    "Ø.031 land, L/D 43, flat AF .017 (RV-01, RV-02)",
    "bad",
)
note(
    ax, (28.5, 8.4), (27, 12.8), "VN-54: made part with a VN number; review OFF", "bad"
)
note(
    ax,
    (CUP_RIM + 0.6, 0.0),
    (49.5, -6.5),
    "tip runs in VN-55's\ncup point",
    None,
    ha="right",
)
dim(ax, ENDS[3], TIP, -8.6, f"terminal land {inch(TIP - ENDS[3], 2)} long")

# ---------------- Panel 2: rule 17 chart
ax = fig.add_subplot(gs[0, 1])
ax.set_title(
    "2 · Why no option may bore T006 (rule 17)",
    loc="left",
    fontsize=11.5,
    fontweight="bold",
    pad=22,
)
ax.text(
    0.0,
    1.015,
    "A bore needs root − 2 × .060 in of web. T006's root leaves less than nothing, so T006 must be solid with its shaft.",
    transform=ax.transAxes,
    fontsize=8.0,
    va="bottom",
    ha="left",
    bbox={"boxstyle": "round,pad=0.3", "fc": SURFACE, "ec": BAD, "lw": 1.2},
)
rows = [6, 12, 18, 24]
for i, t in enumerate(rows):
    y = 3 - i
    root = G[t]["root_min"]
    mx = root - 2 * FLOOR
    ax.barh(y + 0.18, root, height=0.32, color=BRONZE, ec=BRONZE_E, lw=0.6)
    ax.barh(
        y - 0.18, max(mx, 0), height=0.32, color=CONTACT if mx > 0 else BAD, alpha=0.75
    )
    ax.text(
        -0.25, y, f"T{t:03d}", ha="right", va="center", fontsize=9, fontweight="bold"
    )
    ax.text(
        root + 0.12,
        y + 0.18,
        f"root Ø{inch(root, 4)} MIN",
        va="center",
        fontsize=7.6,
        color=INK2,
    )
    ax.text(
        max(mx, 0) + 0.12,
        y - 0.18,
        (
            f"largest bore {inch(mx, 4)}"
            if mx > 0
            else "largest bore negative: none possible"
        ),
        va="center",
        fontsize=7.6,
        color=INK2 if mx > 0 else BAD,
    )
    bore_now = G[t]["bore"] + BORE_PLUS
    ax.plot([bore_now, bore_now], [y - 0.4, y + 0.4], color=INK, lw=1.4)
    ax.text(
        bore_now, y + 0.42, "main", ha="center", va="bottom", fontsize=6.6, color=INK
    )
for x, lab in ((STEM + BORE_PLUS, "Ø1/16 (A)"),):
    ax.plot([x, x], [2 - 0.4, 2 + 0.4], color=INTEGRAL_E, lw=1.4)
    ax.text(x, 2 - 0.45, lab, ha="center", va="top", fontsize=6.6, color=INTEGRAL_E)
ax.set_xlim(-1.4, 14.5)
ax.set_ylim(-2.4, 3.9)
ax.set_yticks([])
ax.set_xlabel("diameter, mm (bore at its printed maximum)", fontsize=8)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.text(
    0.99,
    0.02,
    f"#1649 (A) drill-rod tip, (D) broach, (E) 1/16 land, (F) round pinned bore all keep a bore in T006.\n"
    f"At 1/16 in the T006 web would be {inch(N['t006_web_116'], 4)}; at today's .031 it is {inch(N['t006_web_now'], 4)}.\n"
    f"(A) also leaves {inch(N['drill_rod_wall'], 3)} wall round the rod in DT-04's Ø.125 land.",
    transform=ax.transAxes,
    ha="right",
    va="bottom",
    fontsize=7.6,
    color=INK2,
    bbox={"boxstyle": "round,pad=0.35", "fc": SURFACE, "ec": MUTED, "lw": 0.8},
)


def arbor_common(ax, one_piece):
    """DT-04 shortened to its Ø.375 land; the bronze tip arbor plugs into it."""
    rect(ax, -17, ENDS[1], DIAS[1], STEEL, STEEL_E)
    rect(
        ax,
        ENDS[1] - 8.0,
        ENDS[1],
        SPIGOT,
        BRONZE,
        INTEGRAL_E,
        lw=0.9,
        ls=(0, (2, 1.2)),
        z=2.3,
    )
    gear(ax, 30, BRASS, BRASS_E, bore=DIAS[1])
    rect(ax, ENDS[1], ENDS[2], DIAS[2], BRONZE, INTEGRAL_E, lw=1.6, z=2.2)
    rect(ax, ENDS[2], ENDS[3], DIAS[3], BRONZE, INTEGRAL_E, lw=1.6, z=2.2)
    rect(ax, ENDS[3], X[6], STEM, BRONZE, INTEGRAL_E, lw=1.6, z=2.2)
    rect(ax, T006_N, PIVOT_END, STEM, BRONZE, INTEGRAL_E, lw=1.6, z=3.2)
    gear(ax, 24, BRONZE, BRONZE_E, bore=DIAS[2], flat=AF[2] - DIAS[2] / 2)
    if one_piece:
        for t in (18, 12, 6):
            gear(ax, t, BRONZE, BRONZE_E, integral=True)
        for t in (
            12,
            6,
        ):  # planing relief at the big-end face, inside the untouched 2.2
            for s in (1, -1):
                ax.add_patch(
                    Rectangle(
                        (X[t], s * G[t]["root_min"] / 2 - (0.55 if s > 0 else 0)),
                        1.5,
                        0.55,
                        fc=SURFACE,
                        ec=INTEGRAL_E,
                        lw=0.6,
                        zorder=4,
                    )
                )
    else:
        gear(ax, 18, BRONZE, BRONZE_E, bore=DIAS[3], flat=AF[3] - DIAS[3] / 2)
        gear(ax, 12, BRONZE, BRONZE_E, bore=STEM)
        gear(ax, 6, BRONZE, BRONZE_E, integral=True)
    rect(
        ax, T006_N, T006_N + 4.0, 5.0, BRASS, BRASS_E, z=3.4
    )  # bushing, fixed on the pivot
    rect(
        ax,
        END_FACE,
        PIVOT_END + 0.4,
        STEM + 0.25,
        "none",
        INK2,
        lw=0.6,
        ls=(0, (2, 1.2)),
        z=2.7,
    )
    tip_block(ax, "end")
    rect(
        ax, END_FACE, BLOCK_S, 6.35, "#cfcec8", BLOCK_E, lw=0.7, z=2.5, hatch="////"
    )  # exposed thread
    centreline(ax, -17, 50)
    dim(ax, ENDS[1] - 8.0, ENDS[1], -9.4, "Ø.125 spigot,\n.31 deep")


# ---------------- Panel 3: Option A
ax = fig.add_subplot(gs[1, 0])
frame(
    ax,
    "3 · Option A (recommended): T006 cut on a bronze tip arbor",
    "No bored T006, no Ø.031 land, no VN-54. Lathe + mill + dividing head; uses the custom T006 fly cutter main already specifies",
    "good",
)
arbor_common(ax, one_piece=False)
note(
    ax,
    (17.2, -1.6),
    (2.0, -18.4),
    f"T006 integral: no bore, no web; stem and pivot Ø.0625 sit {inch(N['stem_under_t006_root'], 4)}\n"
    "under its root, so the fly cutter runs off both sides. Cut T006 before T012 goes on",
    "good",
)
note(
    ax,
    (10.5, 0.6),
    (-16.5, 13.4),
    f"T012 on a Ø.0625 seat: web {inch(N['t012_web_stem'], 4)} MIN\n(floor .060, under the .080 target: state it on the sheet)",
    "warn",
)
note(
    ax,
    (-11.0, 0.8),
    (-16.5, -15.2),
    f"spigot bonded LOCTITE 638 in a reamed Ø.125 hole;\nwall to DT-04's flat {inch(N['spigot_wall_to_flat'], 3)}",
    "good",
)
note(
    ax,
    (T006_N + 2.0, 2.4),
    (21.0, 12.6),
    "brass bushing pressed on the pivot,\nturns with the cone, thrusts on the end screw",
    "good",
)
note(
    ax,
    (31.5, 3.2),
    (26.0, -12.4),
    "long 1/4-28 end screw, Ø.063 pivot hole; pinch slit\nlocks it. DT-21 grows south to about .43 for 1.5D",
    "warn",
)
note(
    ax, (3.4, 2.9), (14.5, 9.2), "T018, T024 keep their flats,\nnow on the arbor", None
)

# ---------------- Panel 4: Option B
ax = fig.add_subplot(gs[1, 1])
frame(
    ax,
    "4 · Option B: one-piece T006–T018 arbor, T012 and T006 planed",
    "Period, no joints in the tip. Needs a shaper or the lathe used as one; rule 16 route is arguable for a first-timer",
    "warn",
)
arbor_common(ax, one_piece=True)
note(
    ax,
    (3.4, 4.4),
    (-16.5, 13.4),
    f"T018 can still be milled: its neighbours stand\nbelow its root (T012 OD {inch(G[12]['od'], 3)} < root {inch(G[18]['root_min'], 3)})",
    "good",
)
note(
    ax,
    (8.0, 2.6),
    (8.0, 12.6),
    "T012 and T006 planed with form tools; 1.5 mm relief\ngroove at each big-end face, inside the untouched 2.2 mm",
    "warn",
)
note(
    ax,
    (12.0, -3.4),
    (-5.0, -15.4),
    "18 tooth spaces planed (not 36):\nindex 6 and 12 from one 72-hole plate",
    None,
)
note(
    ax,
    (31.5, 3.2),
    (30.0, -15.4),
    "same tip end, bushing and\nspigot joint as option A",
    None,
)

# ---------------- Panel 5: cutter run-out
ax = fig.add_subplot(gs[2, 0])
R = 3.175  # a 1/4 in cutter; a fly cutter's swing is larger and worse
h = N["shoulder_6"]
reach = math.sqrt(h * (2 * R - h)) if h < R else R
ax.set_title(
    "5 · Why T012 must be off the arbor while T006 is cut (option A)",
    loc="left",
    fontsize=11.5,
    fontweight="bold",
    pad=22,
)
ax.text(
    0.0,
    1.015,
    f"T012 stands {inch(h, 3)} in above T006's root. A Ø1/4 cutter reaches full depth only {reach:.1f} mm from that shoulder; "
    "contact starts 2.2 mm from it.",
    transform=ax.transAxes,
    fontsize=8.0,
    va="bottom",
    ha="left",
    bbox={"boxstyle": "round,pad=0.3", "fc": SURFACE, "ec": BAD, "lw": 1.2},
)
ax.set_xlim(-1.5, 40)
ax.set_ylim(-3.5, 12.5)
ax.set_aspect("equal")
ax.axis("off")
x12, x6 = 0.0, W
ax.add_patch(
    Rectangle((x12, 0), W, G[12]["od"] / 2, fc=BRONZE, ec=BRONZE_E, lw=0.9, zorder=2)
)
ax.add_patch(
    Rectangle((x6, 0), W, G[6]["od"] / 2, fc=BRONZE, ec=INTEGRAL_E, lw=1.4, zorder=2)
)
ax.plot(
    [x6, x6 + W],
    [G[6]["root_min"] / 2] * 2,
    color=INK2,
    lw=0.7,
    ls=(0, (2, 1.2)),
    zorder=3,
)
ax.text(
    x6 + W + 0.2, G[6]["root_min"] / 2, "T006 root", fontsize=7, va="center", color=INK2
)
ax.add_patch(
    Circle(
        (x6 + reach, G[6]["root_min"] / 2 + R),
        R,
        fc=BAD,
        alpha=0.13,
        ec=BAD,
        lw=0.9,
        ls=(0, (3, 2)),
        zorder=4,
    )
)
ax.plot(
    [x6 + 2.2, x6 + 5.3],
    [G[6]["od"] / 2 + 0.35] * 2,
    color=CONTACT,
    lw=2.6,
    solid_capstyle="butt",
    zorder=5,
)
centreline(ax, -1.5, x6 + W + 1)
dim(ax, x6, x6 + reach, -0.9, f"{reach:.1f} > 2.2")
ax.text(
    x12 + W / 2,
    G[12]["od"] / 2 + 0.5,
    "T012",
    ha="center",
    fontsize=8,
    fontweight="bold",
)
ax.text(
    x6 + W / 2, G[6]["od"] / 2 + 1.0, "T006", ha="center", fontsize=8, fontweight="bold"
)
ax.text(
    x6 + reach,
    G[6]["root_min"] / 2 + 2 * R + 0.3,
    "Ø1/4 cutter at full depth,\nclosest it can come",
    ha="center",
    fontsize=7,
    color=BAD,
)
ax.text(
    17.0,
    12.0,
    "Order of work for option A\n"
    "1  Turn the arbor between centres: spigot, Ø.250 and\n"
    "    Ø.125 seats, Ø.0625 seat, T006 blank, Ø.0625 pivot.\n"
    "2  Cut T006 with the DT6-FORM1 fly cutter. It runs off\n"
    "    over the Ø.0625 seat and pivot: nothing larger is on\n"
    "    the arbor yet.\n"
    "3  Mill the T018 and T024 flats.\n"
    "4  Cut T012 on its own mandrel, then slide T012, T018,\n"
    "    T024 on. T006 sits inside T012's root\n"
    f"    ({inch(G[6]['od'], 3)} < {inch(G[12]['root_min'], 3)}), so T012 never blocks T006 again.\n"
    "Option B leaves T012 on the arbor, so T012 and T006 are\n"
    "planed. T018 is still milled: the T024 that would block it\n"
    "is a separate gear.",
    fontsize=7.9,
    va="top",
    color=INK,
    linespacing=1.4,
    bbox={"boxstyle": "round,pad=0.4", "fc": SURFACE, "ec": MUTED, "lw": 0.8},
)

# ---------------- Panel 6: rejected
ax = fig.add_subplot(gs[2, 1])
ax.axis("off")
ax.set_title(
    "6 · Rejected under the current rubric",
    loc="left",
    fontsize=11.5,
    fontweight="bold",
    pad=22,
)
rej = [
    (
        "Keep main (#1649 C)",
        f"T006 web {inch(N['t006_web_now'], 4)} < .060 floor; Ø.031 × 1.32 land and .017 flat; VN-54 has no historical counterpart. Ships only by exception.",
    ),
    (
        "#1649 A: drill-rod tip in DT-04",
        f"T006 stays bored (web {inch(N['t006_web_now'], 4)}); {inch(N['drill_rod_wall'], 3)} wall round the rod in the Ø.125 land; still needs VN-54 to hold T006/T012.",
    ),
    (
        "#1649 D, E, F: broach, 1/16 land, round pinned bore",
        f"Every one keeps a bore in T006 (no legal bore exists). E gives a {inch(N['t006_web_116'], 4)} web; F cannot pin a .031 shaft.",
    ),
    (
        "#1649 B: 6-leaf pinion wire",
        "Clock pinion wire is a cycloidal leaf form, not DT6-FORM1's 20° profile against the 120T drum; no 48DP stock found. Unverified, not pursued.",
    ),
    (
        "v45 review option C: separate gears sweated into a cluster",
        "Rule 23: solder never counts on a drive-torque joint. T006 also still needs a spigot bore or a spigot; a spigot is option A.",
    ),
    (
        "Bond T012–T018 to the stem instead of flats",
        "Rule 23 allows it, but the 2026-09-28 ruling phases every gear by one flat and keeps the cone stack unbonded. Owner call (see review).",
    ),
]
y = 0.97
for head, body in rej:
    ax.text(
        0.0,
        y,
        "✗ " + head,
        transform=ax.transAxes,
        fontsize=9.0,
        fontweight="bold",
        color=BAD,
        va="top",
    )
    ax.text(
        0.03,
        y - 0.045,
        body,
        transform=ax.transAxes,
        fontsize=8.1,
        color=INK2,
        va="top",
        wrap=True,
    )
    y -= 0.165

# ---------------- Table
ax = fig.add_subplot(gs[3, :])
ax.axis("off")
cols = [
    "",
    "T006 (rule 17)",
    "Cutting route (rule 16)",
    "Tip retention (rule 23)",
    "Owner rulings it touches",
    "Parts that change",
]
rows = [
    [
        "Main today",
        f"bored, web {inch(N['t006_web_now'], 4)}",
        "Ø.031 land with tailstock;\nmicro D-flat and D-bores",
        "D-flats; VN-54 set screw\non the .017 flat",
        "keeps U40 and 09-28\nthrough RV-01..04",
        "—",
    ],
    [
        "A (recommended)",
        "integral, no web",
        "lathe, mill, dividing head,\nDT6-FORM1 fly cutter",
        "T006 integral; T012-T024 on\nflats; spigot bonded LOCTITE 638",
        "retires U40; keeps 09-28\n(T012 flat on Ø.0625)",
        "new tip arbor; DT-04 ends at Ø.375 land;\nVN-54, VN-55 out; end screw + bushing in;\nDT-21 1/4-28 and deeper",
    ],
    [
        "B",
        "integral, no web",
        "as A, plus a shaper or the\nlathe planing T012 and T006",
        "T006-T018 integral; T024 flat;\nspigot bonded LOCTITE 638",
        "retires U40; T012 and T018\nlose their flats",
        "as A; T012 and T018 configurations\nretire into the arbor",
    ],
    [
        "#1649 A/D/E/F",
        "bored, < .060",
        "as listed in #1649",
        "unchanged (VN-54)",
        "U40 or 09-28",
        "DT-04 and/or DT-03",
    ],
]
tb = ax.table(
    cellText=rows,
    colLabels=cols,
    loc="upper center",
    cellLoc="left",
    colLoc="left",
    colWidths=[0.09, 0.09, 0.17, 0.2, 0.16, 0.29],
)
tb.auto_set_font_size(False)
tb.set_fontsize(8.0)
tb.scale(1, 3.2)
for (r, c), cell in tb.get_celld().items():
    cell.set_edgecolor(MUTED)
    cell.set_linewidth(0.6)
    if r == 0:
        cell.set_text_props(fontweight="bold")
        cell.set_facecolor("#efeee9")
    if c == 0 and r > 0:
        cell.set_text_props(fontweight="bold")
fig.text(
    0.025,
    0.012,
    "Sources: cad/scripts and cad/config on main a8441605f; issue #1649; drawing-guidelines.md rules 4, 16, 17, 21, 23; book pp.17–21; engineerguy video 4 (6:36–6:39); "
    "contact zone measured on v45 gltf/dt-drive-train.glb (cone stations unchanged since). Proposal only, not in CAD.",
    fontsize=7.6,
    color=INK2,
)
fig.savefig(OUT, dpi=150, facecolor=SURFACE)
print("wrote", OUT)
print(json.dumps(N, indent=1))
