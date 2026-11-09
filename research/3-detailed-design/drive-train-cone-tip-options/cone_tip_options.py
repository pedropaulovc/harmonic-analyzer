"""Cone-tip options for MHA-DT-03/-04 (main a8441605f geometry), labelled in inches.

Side views to scale; x = 0 at the T018 big-end (south) face, tip to the right. Geometry is
read from cad/scripts on main through dump_geometry.py; block_air.py supplies the block and
bushing air to the drum bank. Usage, from the repo root:
uv run --no-project --with matplotlib python cone_tip_options.py geometry.json air.json out.png
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
with open(sys.argv[2], encoding="utf-8") as f:
    AIR = json.load(f)
OUT = sys.argv[3]

IN = 25.4
FLOOR, TARGET = 0.060 * IN, 0.080 * IN  # rule 17, inch sheets
BORE_PLUS = 0.0018 * IN  # MHA-DT-03 D-bore band upper (+.0018)
REAM_PLUS = 0.0005 * IN  # shop table: reamed hole +.0005/0

SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#b8b7b0"
STEEL, STEEL_E = "#e4e3de", "#6b6a65"
BRASS, BRASS_E = "#f2d27a", "#9a6a00"  # C36000: T030-T120, tip bushing
BRONZE, BRONZE_E = "#d9a24a", "#7a5212"  # C67500 manganese bronze: T006-T024, tip parts
BLOCK, BLOCK_E = "#77766f", "#2f2e2b"
INTEGRAL_E = "#1d5aa3"  # blue outline = part with integral teeth
SOLDER = "#2b2a28"
CONTACT = "#1baf7a"
BAD, GOOD, WARN = "#d03b3b", "#0c8a0c", "#b8860b"

W = GEO["face_width"]
G = {int(k): v for k, v in GEO["gears"].items()}
SOUTH_T018 = GEO["T006_NORTH_FACE_STATION"] - 3 * W  # x origin, cone station
ENDS = [
    e - GEO["front_stub"] - SOUTH_T018 for e in GEO["section_ends"]
]  # DT-04 land ends
DIAS = GEO["section_dias"]
AF = GEO["section_flat_af"]
X = {30: -2 * W, 24: -W, 18: 0.0, 12: W, 6: 2 * W}
T006_N = 3 * W
COLLAR0 = GEO["TIP_COLLAR_START_STATION"] - SOUTH_T018
COLLAR1 = GEO["TIP_COLLAR_END_STATION"] - SOUTH_T018
BLOCK_S0 = GEO["TIP_BLOCK_SOUTH_FACE_STATION"] - SOUTH_T018
BLOCK_N0 = GEO["TIP_BLOCK_NORTH_FACE_STATION"] - SOUTH_T018
CUP_RIM = GEO["ADJUSTER_CUP_RIM_STATION"] - SOUTH_T018
TIP = GEO["T006_TIP_STATION"] - SOUTH_T018
CONTACT_ZONE = (2.2, 5.3)  # from each band's big-end face; v45 GLB measurement

# ---- proposed tip end (options A, B, C) ---------------------------------------------------
STEM = 1 / 16 * IN  # T006 spigot / T012 seat and the pivot
SPIGOT = 1 / 8 * IN  # option A arbor into DT-04
SOCKET = (
    0.190 * IN
)  # option C1: depth of the T006 spigot's socket in DT-04's Ø.250 land
BUSH_D, BUSH_L = (
    0.225 * IN,
    0.160 * IN,
)  # brass bushing, pressed on the pivot against T006
END_PLAY = 0.010 * IN
BLOCK_GAP = 0.200 * IN  # T006 north face to the moved block's south face
BLOCK_DEPTH = 0.430 * IN  # 1.5D of 1/4-28 past both mouth countersinks
BLOCK_S = T006_N + BLOCK_GAP
BLOCK_N = BLOCK_S + BLOCK_DEPTH
END_FACE = T006_N + BUSH_L + END_PLAY
PIVOT_END = END_FACE + 0.120 * IN
SCREW_MINOR = (0.250 - 1.22687 / 28) * IN  # 1/4-28 external basic minor

web = lambda t, bore: (G[t]["root_min"] - bore) / 2.0
N = {
    "t006_web_main": web(6, G[6]["bore"] + BORE_PLUS),
    "t012_web_main": web(12, G[12]["bore"] + BORE_PLUS),
    "t006_web_116": web(6, STEM + BORE_PLUS),
    "t012_web_reamed_116": web(12, STEM + REAM_PLUS),
    "t012_web_d_116": web(12, STEM + BORE_PLUS),
    "stem_under_t006_root": (G[6]["root_min"] - STEM) / 2.0,
    "spigot_wall_to_flat": (AF[1] - DIAS[1] / 2.0) - (SPIGOT + REAM_PLUS) / 2.0,
    "socket_wall_to_flat": (AF[2] - DIAS[2] / 2.0) - (STEM + REAM_PLUS) / 2.0,
    "t018_web_reamed_116": web(18, STEM + REAM_PLUS),
    "c1_spigot_len": SOCKET + 2 * W,
    "drill_rod_wall": (DIAS[3] - (DIAS[4] + REAM_PLUS)) / 2.0,
    "bushing_wall": (BUSH_D - STEM - REAM_PLUS) / 2.0,
    "end_screw_wall": (SCREW_MINOR - STEM - REAM_PLUS) / 2.0,
    "block_move": BLOCK_S0 - BLOCK_S,
    "block_air_now": AIR["block_air_now"],
    "block_air_moved": AIR["block_air_at_gap"],
    "bushing_air": AIR["bushing_air"],
    "collar_body_air_nominal": AIR["collar_nominal_air_by_tier"]["body"],
    "collar_body_air_worst": AIR["collar_worst_air_by_tier"]["body"],
    "collar_nose_air_nominal": AIR["collar_nominal_air_by_tier"]["nose"],
    "collar_nose_air_worst": AIR["collar_worst_air_by_tier"]["nose"],
}
h = (G[12]["od"] - G[6]["root_min"]) / 2.0
N["t012_shoulder_over_t006_root"] = h
N["runout_quarter_cutter"] = math.sqrt(h * (2 * 3.175 - h))
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
    return s[1:] if s.startswith("0.") else s.replace("-0.", "-.")


def rect(ax, x0, x1, dia, fc, ec, lw=0.9, ls="-", z=2, hatch=None):
    ax.add_patch(
        Rectangle(
            (x0, -dia / 2),
            x1 - x0,
            dia,
            fc=fc,
            ec=ec,
            lw=lw,
            ls=ls,
            zorder=z,
            hatch=hatch,
        )
    )


def gear(ax, t, fc, ec, bore=None, integral=False, z=3, flat=None):
    """Gear cut on the axial plane: the bore is open, so the shaft or spigot inside shows.

    `flat` is the axis-to-flat distance of a D-bore; the section plane is drawn through the
    flat on the lower half.
    """
    x0 = X[t]
    od, root = G[t]["od"], G[t]["root_min"]
    edge = INTEGRAL_E if integral else ec
    lw = 1.6 if integral else 0.9
    if bore:
        lower = flat if flat is not None else bore / 2
        bands = ((bore / 2, od / 2), (-od / 2, -lower))
    else:
        bands = ((-od / 2, od / 2),)
    for y0, y1 in bands:
        ax.add_patch(Rectangle((x0, y0), W, y1 - y0, fc=fc, ec=edge, lw=lw, zorder=z))
    for y0 in (root / 2, -od / 2):  # tooth band, hatched
        ax.add_patch(
            Rectangle(
                (x0, y0),
                W,
                (od - root) / 2,
                fc="none",
                ec=ec,
                lw=0,
                hatch="||||",
                zorder=z + 0.1,
            )
        )
    for s in (1, -1):
        ax.plot([x0, x0 + W], [s * root / 2] * 2, color=ec, lw=0.5, zorder=z + 0.2)
    c0, c1 = CONTACT_ZONE
    ax.plot(
        [x0 + c0, x0 + c1],
        [od / 2 + 0.45] * 2,
        color=CONTACT,
        lw=2.6,
        solid_capstyle="butt",
        zorder=z + 1,
    )
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


def solder_face(ax, x, dia, inner=0.0):
    for s in (1, -1):
        ax.plot(
            [x, x],
            [s * inner, s * dia / 2],
            color=SOLDER,
            lw=2.4,
            zorder=6,
            solid_capstyle="butt",
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
        zorder=9,
        arrowprops={
            "arrowstyle": "<->",
            "color": INK2,
            "lw": 0.6,
            "shrinkA": 0,
            "shrinkB": 0,
        },
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


def frame(ax, title, verdict, mark, xlim=(-17, 46), ylim=(-19.0, 15.5)):
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, loc="left", fontsize=11.5, fontweight="bold", pad=22)
    ax.text(
        0.0,
        1.015,
        verdict,
        transform=ax.transAxes,
        fontsize=8.0,
        va="bottom",
        ha="left",
        bbox={
            "boxstyle": "round,pad=0.3",
            "fc": SURFACE,
            "ec": {"bad": BAD, "good": GOOD, "warn": WARN}[mark],
            "lw": 1.2,
        },
    )


def tip_block(ax, south, north, adjuster):
    """MHA-DT-21 side view, truncated below; pinch screw seen end-on above the axis."""
    top = 52.578 - 38.1
    ax.add_patch(
        Rectangle(
            (south, -15.0),
            north - south,
            top + 15.0,
            fc=BLOCK,
            ec=BLOCK_E,
            lw=1.0,
            zorder=2.4,
        )
    )
    ax.plot(
        [south, north],
        [-15.0, -15.0],
        color=SURFACE,
        lw=2.5,
        ls=(0, (3, 2)),
        zorder=2.45,
    )
    mid = (south + north) / 2
    ax.add_patch(
        Circle((mid, 8.89), 1.42, fc="#d6d5cf", ec=BLOCK_E, lw=0.8, zorder=2.7)
    )
    ax.plot([mid - 1.0, mid + 1.0], [8.89, 8.89], color=BLOCK_E, lw=0.8, zorder=2.8)
    if adjuster == "cup":  # VN-55 #10-32 x 3/8 cup set screw
        a0, a1, d = CUP_RIM, CUP_RIM + 9.525, 4.826
        rect(ax, a0, a1, d, "#cfcec8", BLOCK_E, lw=0.7, z=2.55)
        ax.add_patch(
            Polygon(
                [[a0, 1.3], [a0 + 1.21, 0.55], [a0 + 1.21, -0.55], [a0, -1.3]],
                closed=True,
                fc=SURFACE,
                ec=BLOCK_E,
                lw=0.6,
                zorder=2.65,
            )
        )
        return
    rect(
        ax, END_FACE, north, 6.35, "#cfcec8", BLOCK_E, lw=0.7, z=2.55
    )  # 1/4-28 end screw
    rect(
        ax,
        END_FACE,
        PIVOT_END + 0.3,
        STEM + 0.3,
        "none",
        INK2,
        lw=0.6,
        ls=(0, (2, 1.2)),
        z=2.7,
    )
    ax.add_patch(
        Polygon(
            [
                [north, -4.6],
                [north + 1.3, -4.6],
                [north + 2.8, -2.6],
                [north + 3.2, 0],
                [north + 2.8, 2.6],
                [north + 1.3, 4.6],
                [north, 4.6],
            ],
            closed=True,
            fc=BLOCK,
            ec=BLOCK_E,
            lw=0.9,
            zorder=2.6,
        )
    )  # domed slotted head, outboard
    ax.plot([north + 1.6, north + 3.2], [0, 0], color="#efeee9", lw=1.0, zorder=2.7)


def tip_end(ax):
    """Pivot, pressed brass bushing, moved block and end screw (options A, B, C)."""
    rect(ax, T006_N, PIVOT_END, STEM, BRONZE, INTEGRAL_E, lw=1.6, z=3.2)
    rect(ax, T006_N, T006_N + BUSH_L, BUSH_D, BRASS, BRASS_E, z=3.4)
    tip_block(ax, BLOCK_S, BLOCK_N, "end")
    ax.add_patch(
        Rectangle(
            (BLOCK_S0, -15.0),
            BLOCK_N0 - BLOCK_S0,
            52.578 - 38.1 + 15.0,
            fc="none",
            ec=MUTED,
            lw=0.8,
            ls=(0, (3, 2)),
            zorder=2.3,
        )
    )  # today's block, ghosted
    ax.annotate(
        "",
        xy=(BLOCK_S, -17.6),
        xytext=(BLOCK_S0, -17.6),
        zorder=9,
        arrowprops={"arrowstyle": "->", "color": INK2, "lw": 0.8},
    )
    ax.text(
        BLOCK_S0 + 0.5,
        -17.6,
        f"DT-21 moves\n{inch(N['block_move'], 2)} south",
        ha="left",
        va="center",
        fontsize=7.0,
        color=INK2,
    )


def dt04(ax, end):
    rect(ax, -17, ENDS[1], DIAS[1], STEEL, STEEL_E)
    if end > ENDS[1]:
        rect(ax, ENDS[1], ENDS[2], DIAS[2], STEEL, STEEL_E)
        rect(ax, ENDS[2], min(end, ENDS[3]), DIAS[3], STEEL, STEEL_E)


FL = {
    i: AF[i] - DIAS[i] / 2 for i in (1, 2, 3, 4)
}  # axis to the flat of each DT-04 land


def draw_c1(ax):
    """C1 in section: DT-04 ends at T024's north face; T006's spigot runs into its socket."""
    dt04(ax, ENDS[1])
    rect(ax, ENDS[1], X[18], DIAS[2], STEEL, STEEL_E)  # Ø.250 land to T024's north face
    rect(
        ax, X[18] - SOCKET, X[18], STEM + REAM_PLUS + 0.25, SURFACE, INK2, lw=0.6, z=2.5
    )  # reamed socket in DT-04's Ø.250 land
    gear(ax, 30, BRASS, BRASS_E, bore=DIAS[1], flat=FL[1])
    gear(ax, 24, BRONZE, BRONZE_E, bore=DIAS[2], flat=FL[2])
    gear(ax, 18, BRONZE, BRONZE_E, bore=STEM)
    gear(ax, 12, BRONZE, BRONZE_E, bore=STEM)
    rect(ax, X[18] - SOCKET, X[6], STEM, BRONZE, INTEGRAL_E, lw=1.2, z=3.25)  # spigot
    gear(ax, 6, BRONZE, BRONZE_E, integral=True)
    solder_face(ax, X[18], G[18]["od"] - 0.6, DIAS[2] / 2)
    solder_face(ax, X[12], G[12]["od"] - 0.6, STEM / 2)
    solder_face(ax, X[6], G[6]["od"] - 0.4, STEM / 2)


def draw_c2(ax):
    """C2 in section: DT-04 ends inside T018; T006's short spigot stops at T012's south face."""
    dt04(ax, ENDS[3])
    gear(ax, 30, BRASS, BRASS_E, bore=DIAS[1], flat=FL[1])
    gear(ax, 24, BRONZE, BRONZE_E, bore=DIAS[2], flat=FL[2])
    gear(ax, 18, BRONZE, BRONZE_E, bore=DIAS[3], flat=FL[3])
    gear(ax, 12, BRONZE, BRONZE_E, bore=STEM)
    rect(
        ax, X[12], X[6], STEM, BRONZE, INTEGRAL_E, lw=1.2, z=3.25
    )  # T006 spigot in T012
    gear(ax, 6, BRONZE, BRONZE_E, integral=True)
    solder_face(ax, X[12], G[12]["od"] - 0.6, DIAS[3] / 2)
    solder_face(ax, X[6], G[6]["od"] - 0.4, STEM / 2)


fig = plt.figure(figsize=(17, 43.5), dpi=150, facecolor=SURFACE)
gs = GridSpec(
    6,
    2,
    figure=fig,
    height_ratios=[1, 1, 1, 1.55, 0.62, 1.45],
    hspace=0.30,
    wspace=0.06,
    left=0.025,
    right=0.985,
    top=0.92,
    bottom=0.02,
)
fig.text(
    0.025,
    0.99,
    "Cone tip (T006–T024): main today vs options, with the exceptions each one still needs",
    fontsize=15,
    fontweight="bold",
    va="top",
)
fig.text(
    0.025,
    0.982,
    "Side views to scale, cut on the axial plane so DT-04 and the spigot show inside the gears; every value in inches. x = 0 at the T018 big-end face, tip to the right; the lower half is cut through each D flat. Geometry from main a8441605f "
    "(MHA-DT-03/-04/-20/-21, VN-54/-55).\n"
    f"Green bars: where the 120T cylinder gear touches each band ({inch(CONTACT_ZONE[0])}–{inch(CONTACT_ZONE[1])} from its big-end face, v45 GLB). "
    "Fill = material: manganese bronze C67500 for T006–T024 and new tip parts (main's tip specification),\n"
    "brass C36000 from T030 and for the bushing, steel for DT-04 and the screws. Blue outline = part with integral teeth. "
    "Black strokes = soft-solder joints. Dashed = bores, seats and today's block position.\n"
    "Owner direction (2026-11-09): T006's web is best effort (rule 17), and soft solder may carry the tip's drive torque, which is minimal "
    "(rule 23 otherwise excludes solder). Both are recorded as owner exceptions below.\n"
    "Real tip (book pp.17–21, engineerguy video 4 at 6:36–6:39): a small brass bushing fixed on the pivot turns with the cone and bears on a "
    "long end screw through a black split block, locked by a side pinch screw.",
    fontsize=8.6,
    color=INK2,
    va="top",
    linespacing=1.45,
)

# ---------------- Panel 1: main today
ax = fig.add_subplot(gs[0, 0])
frame(
    ax,
    "1 · Main today (v47)",
    "Nine tip exceptions, four of them waiting on #1649",
    "bad",
)
dt04(ax, ENDS[3])
rect(ax, ENDS[3], TIP, DIAS[4], STEEL, STEEL_E, z=3.6)
gear(ax, 30, BRASS, BRASS_E, bore=DIAS[1], flat=FL[1])
for t, land in ((24, 2), (18, 3), (12, 4), (6, 4)):
    gear(ax, t, BRONZE, BRONZE_E, bore=G[t]["bore"], flat=FL[land])
rect(ax, COLLAR0, COLLAR0 + 3.5, 6.35, STEEL, STEEL_E, z=3.4)
rect(ax, COLLAR0 + 3.5, COLLAR1, 16.764, STEEL, STEEL_E, z=3.4)
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
tip_block(ax, BLOCK_S0, BLOCK_N0, "cup")
centreline(ax, -17, 44)
note(
    ax,
    (16.5, 1.0),
    (-16.5, -12.4),
    f"T006 Ø.031 D-bore: web {inch(N['t006_web_main'], 4)} (RV-01, RV-04)",
    "bad",
)
note(
    ax,
    (10.0, 2.0),
    (-3, 12.8),
    f"T012 web {inch(N['t012_web_main'], 4)} (RV-03)",
    "warn",
)
note(
    ax,
    (30.0, 0.4),
    (16, -16.4),
    "Ø.031 land, L/D 43, flat .017 (DT-04 RV-01, RV-02)",
    "bad",
)
note(ax, (28.5, 8.4), (20, 12.8), "VN-54: made part on a VN number", "bad")
note(
    ax,
    (CUP_RIM + 0.6, 0.0),
    (43.5, -7.5),
    "tip in VN-55's cup;\n1.0D thread (DT-00 DT-03)",
    None,
    ha="right",
)
dim(ax, ENDS[3], TIP, -8.6, f"terminal land {inch(TIP - ENDS[3], 2)}")

# ---------------- Panel 2: webs per option
ax = fig.add_subplot(gs[0, 1])
ax.set_title(
    "2 · Webs under T006 and T012, by option (rule 17, best effort)",
    loc="left",
    fontsize=11.5,
    fontweight="bold",
    pad=22,
)
ax.text(
    0.0,
    1.015,
    "Only a T006 with no bore has a web worth the name. A, B, C1 and C2 all cut T006 solid with its own spigot or arbor.",
    transform=ax.transAxes,
    fontsize=8.0,
    va="bottom",
    ha="left",
    bbox={"boxstyle": "round,pad=0.3", "fc": SURFACE, "ec": GOOD, "lw": 1.2},
)
bars = [
    ("Main / #1649 A, D, F", N["t006_web_main"], N["t012_web_main"]),
    ("#1649 E (1/16 land)", N["t006_web_116"], N["t012_web_d_116"]),
    ("C1 long spigot", None, N["t012_web_reamed_116"]),
    ("C2 soldering jig", None, N["t012_web_reamed_116"]),
    ("A tip arbor", None, N["t012_web_reamed_116"]),
    ("B planed arbor", None, None),
]
for i, (lab, w6, w12) in enumerate(bars):
    y = len(bars) - 1 - i
    for dy, w, col, name in ((0.18, w6, BRONZE, "T006"), (-0.18, w12, BRASS, "T012")):
        if w is None:
            ax.text(
                0.002,
                y + dy,
                f"{name}: solid, no bore",
                va="center",
                fontsize=7.4,
                color=GOOD,
            )
            continue
        ax.barh(y + dy, w / IN, height=0.32, color=col, ec=BRONZE_E, lw=0.6)
        ax.text(
            w / IN + 0.002,
            y + dy,
            f"{name} web {inch(w, 4)}",
            va="center",
            fontsize=7.4,
            color=BAD if w < FLOOR else (WARN if w < TARGET else INK2),
        )
    ax.text(-0.004, y, lab, ha="right", va="center", fontsize=8.6, fontweight="bold")
for x, lab, col in ((0.060, "floor .060", BAD), (0.080, "target .080", WARN)):
    ax.axvline(x, color=col, lw=0.9, ls=(0, (4, 2)))
    ax.text(x, len(bars) - 0.35, lab, color=col, fontsize=7.4, ha="center", va="bottom")
ax.set_xlim(-0.075, 0.13)
ax.set_ylim(-0.7, len(bars) + 0.1)
ax.set_yticks([])
ax.set_xlabel("web at the printed worst case, in", fontsize=8)
ax.set_xticks([0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12])
ax.set_xticklabels(["0", ".02", ".04", ".06", ".08", ".10", ".12"])
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)

# ---------------- Panel 3: Option C1 (long spigot)
ax = fig.add_subplot(gs[1, 0])
frame(
    ax,
    "3 · Option C1 (recommended): gears cut alone, cluster on T006's long spigot",
    "A fit centres the cluster: T006's Ø.0625 spigot runs through T012 and T018 into a socket in DT-04; solder only drives",
    "good",
)
draw_c1(ax)
tip_end(ax)
centreline(ax, -17, 44)
note(
    ax,
    (X[18] - SOCKET / 2, 0.5),
    (-16.5, -15.4),
    f"socket Ø.0625 × {inch(SOCKET, 2)} reamed in DT-04's Ø.250 land:\n"
    f"wall to the T024 flat {inch(N['socket_wall_to_flat'], 4)} (rule 17 minor)",
    "warn",
)
note(
    ax,
    (17.2, -1.6),
    (-16.5, -18.6),
    f"T006 part: spigot {inch(N['c1_spigot_len'], 2)} long, 6 leaves, pivot; Ø.0625 sits "
    f"{inch(N['stem_under_t006_root'], 4)} under the root",
    "warn",
)
note(
    ax,
    (10.0, 0.4),
    (-16.5, 13.4),
    f"T012, T018 reamed Ø.0625: T012 web {inch(N['t012_web_reamed_116'], 4)} (RV-03, new value),"
    f" T018 web {inch(N['t018_web_reamed_116'], 3)}",
    "warn",
)
note(
    ax,
    (X[18], 4.6),
    (-3.0, 10.4),
    "T024 | T018 | T012 | T006 sweated face to face;\nT024 keeps its flat and drives",
    "warn",
)
note(
    ax,
    (BLOCK_S + 1.0, 3.2),
    (26.0, -13.0),
    f"bushing, 1/4-28 end screw (wall {inch(N['end_screw_wall'])}),\nblock {inch(BLOCK_DEPTH, 2)} deep: as A",
    None,
)

# ---------------- Panel 4: Option C2 (soldering jig)
ax = fig.add_subplot(gs[1, 1])
frame(
    ax,
    "4 · Option C2: gears cut alone, cluster trued by a soldering jig",
    "DT-04 only loses its Ø.031 land; T006's short spigot centres T012, and a jig holds the pair true to T018 while solder sets",
    "warn",
)
draw_c2(ax)
for t in (18, 12, 6):  # jig bore steps on the tooth tips
    rect(
        ax,
        X[t],
        X[t] + W,
        G[t]["od"] + 1.2,
        "none",
        WARN,
        lw=0.9,
        ls=(0, (3, 1.6)),
        z=7,
    )
tip_end(ax)
centreline(ax, -17, 44)
note(
    ax,
    (X[12] + 2.0, G[12]["od"] / 2 + 0.6),
    (-16.5, 13.4),
    "soldering jig: stepped bore on the T018, T012, T006 tooth tips,\nphasing pin through lined-up tooth spaces (needs its own drawing)",
    "warn",
)
note(
    ax,
    (X[12], 3.2),
    (-16.5, -15.4),
    "nothing fits T012 or T006 to DT-04: their run-out\nis whatever the jig holds while the solder sets",
    "warn",
)
note(
    ax,
    (17.2, -1.6),
    (-16.5, -18.6),
    f"T006 part: spigot .27, 6 leaves, pivot; T012 web {inch(N['t012_web_reamed_116'], 4)}; T018 keeps its flat",
    None,
)
note(
    ax,
    (BLOCK_S + 1.0, 3.2),
    (26.0, -13.0),
    "same bushing, moved block\nand end screw as C1",
    None,
)

# ---------------- Panel 4: Option A


def arbor(ax, one_piece):
    dt04(ax, ENDS[1])
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
    gear(ax, 30, BRASS, BRASS_E, bore=DIAS[1], flat=FL[1])
    rect(ax, ENDS[1], ENDS[2], DIAS[2], BRONZE, INTEGRAL_E, lw=1.6, z=2.2)
    rect(ax, ENDS[2], ENDS[3], DIAS[3], BRONZE, INTEGRAL_E, lw=1.6, z=2.2)
    rect(ax, ENDS[3], X[6], STEM, BRONZE, INTEGRAL_E, lw=1.6, z=2.2)
    gear(ax, 24, BRONZE, BRONZE_E, bore=DIAS[2], flat=FL[2])
    if one_piece:
        for t in (18, 12, 6):
            gear(ax, t, BRONZE, BRONZE_E, integral=True)
        for t in (
            12,
            6,
        ):  # planing relief at each big-end face, inside the untouched zone
            for y0 in (G[t]["root_min"] / 2 - 0.55, -G[t]["root_min"] / 2):
                ax.add_patch(
                    Rectangle(
                        (X[t], y0),
                        1.5,
                        0.55,
                        fc=SURFACE,
                        ec=INTEGRAL_E,
                        lw=0.6,
                        zorder=4,
                    )
                )
    else:
        gear(ax, 18, BRONZE, BRONZE_E, bore=DIAS[3], flat=FL[3])
        gear(ax, 12, BRONZE, BRONZE_E, bore=STEM)
        gear(ax, 6, BRONZE, BRONZE_E, integral=True)
        solder_face(ax, X[6], G[6]["od"] - 0.4, STEM / 2)
    tip_end(ax)
    centreline(ax, -17, 44)
    dim(ax, ENDS[1] - 8.0, ENDS[1], -9.4, "Ø.125 spigot,\n.31 deep")


ax = fig.add_subplot(gs[2, 0])
frame(
    ax,
    "5 · Option A: T006 cut on a bronze tip arbor",
    "Fewer soldered joints, one more part: the arbor replaces DT-04's lands 2–4 and is bonded into its Ø.375 land",
    "good",
)
arbor(ax, one_piece=False)
note(
    ax,
    (-11.0, 0.8),
    (-16.5, -15.6),
    f"spigot bonded LOCTITE 638 in a reamed Ø.125 hole;\nwall to DT-04's flat {inch(N['spigot_wall_to_flat'])}",
    "good",
)
note(
    ax,
    (10.0, 0.4),
    (-16.5, 13.4),
    f"T012 reamed Ø.0625 on the arbor, sweated to T006:\nweb {inch(N['t012_web_reamed_116'], 4)} (RV-03, new value)",
    "warn",
)
note(
    ax, (3.4, 2.9), (11.0, 10.6), "T018, T024 keep their flats,\nnow on the arbor", None
)
note(
    ax,
    (BLOCK_S + 1.0, 3.2),
    (26.0, -13.0),
    "same bushing, moved block\nand end screw as C1",
    None,
)

# ---------------- Panel 5: Option B
ax = fig.add_subplot(gs[2, 1])
frame(
    ax,
    "6 · Option B: one-piece T006–T018 arbor, T012 and T006 planed",
    "No joints in the tip; needs a shaper or the lathe used as one, which a reviewer may refuse under rule 16",
    "warn",
)
arbor(ax, one_piece=True)
note(
    ax,
    (3.4, 4.4),
    (-16.5, 13.4),
    f"T018 milled: T012's OD {inch(G[12]['od'])} is under T018's root {inch(G[18]['root_min'])}",
    "good",
)
note(
    ax,
    (8.0, 2.6),
    (8.0, 10.6),
    "T012, T006 planed with form tools; .06 relief groove\nat each big-end face, inside the untouched .087",
    "warn",
)
note(
    ax,
    (12.0, -3.4),
    (-6.0, -15.6),
    "18 tooth spaces planed;\nindex 6 and 12 from one 72-hole plate",
    None,
)


# ---------------- Panels 7, 8: where DT-04 and T006's spigot meet (C1, C2)
def junction(ax, title, verdict, mark, draw):
    frame(ax, title, verdict, mark, xlim=(-7.6, 15.6), ylim=(-9.6, 9.6))
    draw(ax)
    centreline(ax, -7.6, 15.6)
    for t in ax.texts:  # gear labels off the zoomed window; keep the verdict box
        if t.get_transform() is not ax.transAxes:
            t.set_clip_on(True)


def vdim(ax, x, y0, y1):
    ax.annotate(
        "",
        xy=(x, y0),
        xytext=(x, y1),
        zorder=9,
        arrowprops={
            "arrowstyle": "<->",
            "color": INK,
            "lw": 0.7,
            "shrinkA": 0,
            "shrinkB": 0,
        },
    )


ax = fig.add_subplot(gs[3, 0])
junction(
    ax,
    "7 · C1 detail: T006's spigot in DT-04's socket",
    "The spigot ends .19 inside DT-04's Ø.250 land, under T024: a reamed fit, not the solder, centres the cluster",
    "good",
    draw_c1,
)
vdim(ax, X[18] - SOCKET / 2, -(STEM + REAM_PLUS) / 2, -FL[2])
dim(ax, X[18] - SOCKET, X[18], 2.5, f"socket {inch(SOCKET, 2)}", fs=6.8)
note(
    ax,
    (X[18] - SOCKET / 2, -1.7),
    (-7.3, -8.3),
    f"socket Ø.0625 reamed in DT-04's Ø.250 land;\nspigot slip fit, locates only;\nwall to the flat {inch(N['socket_wall_to_flat'], 4)} (rule 17 minor)",
    "warn",
    fs=7.2,
)
note(
    ax,
    (-1.2, 2.2),
    (5.6, 8.6),
    "DT-04 ends at T024's north face;\nT024 rides the Ø.250 land on its flat",
    None,
    fs=7.2,
)
note(
    ax,
    (4.6, 0.25),
    (5.6, 6.6),
    f"T018, T012 reamed Ø.0625 on the spigot;\nwebs {inch(N['t018_web_reamed_116'], 3)} and {inch(N['t012_web_reamed_116'], 4)}",
    None,
    fs=7.2,
)
note(
    ax,
    (X[18], -4.2),
    (4.2, -7.8),
    "T024 | T018 face sweated:\nthis joint carries the torque",
    "warn",
    fs=7.2,
)

ax = fig.add_subplot(gs[3, 1])
junction(
    ax,
    "8 · C2 detail: the spigot never reaches DT-04",
    f"DT-04's Ø.125 land stops {inch(X[12] - ENDS[3])} short of the spigot; only the T018 | T012 solder face links them",
    "warn",
    draw_c2,
)
dim(ax, ENDS[3], X[12], -1.4, f"gap {inch(X[12] - ENDS[3])}", fs=6.8)
note(
    ax,
    (ENDS[3] - 0.6, 1.0),
    (5.6, 8.6),
    "DT-04's Ø.125 land, T018 on its flat\n(as main, less the Ø.031 tip land)",
    None,
    fs=7.2,
)
note(
    ax,
    (X[12] + 1.2, 0.3),
    (8.4, 6.6),
    "T006's .27 spigot fills\nT012's bore only",
    None,
    fs=7.2,
)
note(
    ax,
    (X[12], -2.6),
    (-7.3, -8.3),
    "nothing fits T012 or T006 to DT-04: the jig sets their\nrun-out, and the T018 | T012 solder face holds it",
    "warn",
    fs=7.2,
)

# ---------------- Panel 9: cutter run-out
ax = fig.add_subplot(gs[4, 0])
R = 3.175
reach = N["runout_quarter_cutter"]
ax.set_title(
    "9 · Why T006 is cut before T012 joins it (A, C1 and C2)",
    loc="left",
    fontsize=11.5,
    fontweight="bold",
    pad=22,
)
ax.text(
    0.0,
    1.015,
    f"T012 stands {inch(h)} above T006's root. A Ø1/4 cutter reaches full depth only {inch(reach)} from that shoulder; "
    f"contact starts {inch(CONTACT_ZONE[0])} from it.",
    transform=ax.transAxes,
    fontsize=8.0,
    va="bottom",
    ha="left",
    bbox={"boxstyle": "round,pad=0.3", "fc": SURFACE, "ec": BAD, "lw": 1.2},
)
ax.set_xlim(-1.5, 24)
ax.set_ylim(-3.5, 12.5)
ax.set_aspect("equal")
ax.set_anchor("W")
ax.axis("off")
ax.add_patch(
    Rectangle((0, 0), W, G[12]["od"] / 2, fc=BRONZE, ec=BRONZE_E, lw=0.9, zorder=2)
)
ax.add_patch(
    Rectangle((W, 0), W, G[6]["od"] / 2, fc=BRONZE, ec=INTEGRAL_E, lw=1.4, zorder=2)
)
ax.plot(
    [W, 2 * W],
    [G[6]["root_min"] / 2] * 2,
    color=INK2,
    lw=0.7,
    ls=(0, (2, 1.2)),
    zorder=3,
)
ax.text(
    2 * W + 0.2, G[6]["root_min"] / 2, "T006 root", fontsize=7, va="center", color=INK2
)
ax.add_patch(
    Circle(
        (W + reach, G[6]["root_min"] / 2 + R),
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
    [W + CONTACT_ZONE[0], W + CONTACT_ZONE[1]],
    [G[6]["od"] / 2 + 0.35] * 2,
    color=CONTACT,
    lw=2.6,
    solid_capstyle="butt",
    zorder=5,
)
centreline(ax, -1.5, 2 * W + 1)
dim(ax, W, W + reach, -0.9, f"{inch(reach)} > {inch(CONTACT_ZONE[0])}")
ax.text(
    W / 2, G[12]["od"] / 2 + 0.5, "T012", ha="center", fontsize=8, fontweight="bold"
)
ax.text(
    1.5 * W, G[6]["od"] / 2 + 1.0, "T006", ha="center", fontsize=8, fontweight="bold"
)
ax.text(
    W + reach,
    G[6]["root_min"] / 2 + 2 * R + 0.3,
    "Ø1/4 cutter at full depth,\nclosest it can come",
    ha="center",
    fontsize=7,
    color=BAD,
)
ax = fig.add_subplot(gs[4, 1])
ax.axis("off")
ax.text(
    0.0,
    1.0,
    "Order of work for option C1\n"
    f"1  Turn the T006 blank between centres: {inch(N['c1_spigot_len'], 2)} of Ø.0625 spigot (L/D {N['c1_spigot_len'] / STEM:.0f}, steady or\n"
    "    tailstock support), the leaf blank, and the Ø.0625 pivot.\n"
    "2  Cut T006 with the DT6-FORM1 fly cutter; it runs off over the spigot and pivot. Press the bushing on.\n"
    "3  Ream T018 and T012 Ø.0625, then cut each alone on a Ø.0625 mandrel. Ream DT-04's socket Ø.0625 × .19.\n"
    "4  Thread T018 and T012 onto T006's spigot; pin-phase them through lined-up tooth spaces; sweat.\n"
    "5  Put T024 on DT-04's flat, push the spigot home in the socket, phase T018 to T024, sweat that face.\n"
    "    Reheat to take it apart.\n"
    "6  Set end play at the end screw; tighten the pinch screw.\n"
    f"T006 sits inside T012's root ({inch(G[6]['od'])} < {inch(G[12]['root_min'])}), so T012 never blocks T006's cutter once T006 is done.\n"
    "C2 differs at 3–5: T018 keeps its D-bore on DT-04's Ø.125 land, and the jig, not the shaft, trues T012 and T006.",
    transform=ax.transAxes,
    fontsize=7.4,
    va="top",
    color=INK,
    linespacing=1.4,
    bbox={"boxstyle": "round,pad=0.4", "fc": SURFACE, "ec": MUTED, "lw": 0.8},
)

# ---------------- Table: exceptions per option
ax = fig.add_subplot(gs[5, :])
ax.axis("off")
ax.set_title(
    "10 · Owner exceptions after each option (tip-related only; IDs as on main)",
    loc="left",
    fontsize=11.5,
    fontweight="bold",
    pad=10,
)
cols = ["", "Retired", "Still needed", "New or changed", "Parts that change"]
rows = [
    [
        "Main today",
        "—",
        "DT-03 RV-01 (D-bore), RV-02 (no process word), RV-03 (T012 .0797),\nRV-04 (T006 .0256); DT-04 RV-01 (land), RV-02 (tailstock);\nVN-54 RV-01; DT-21 RV-01; DT-00 DT-03 (VN-55 1.0D)",
        "—",
        "—",
    ],
    [
        "C1 (recommended)",
        "DT-03 RV-01, RV-04; DT-04 RV-01, RV-02;\nVN-54 RV-01; DT-00 DT-03",
        "DT-03 RV-02 (T024–T120 D-bores);\nDT-21 RV-01 and DT-20 RV-03 (callout places,\nre-scoped to the moved holes)",
        f"DT-03 RV-03 → T012 web {inch(N['t012_web_reamed_116'], 4)}; new DT-00: solder on\nthe T024-T018-T012-T006 drive joints (rule 23);\nnew DT-04 socket wall {inch(N['socket_wall_to_flat'], 4)} and end-screw\nwall {inch(N['end_screw_wall'])} (both rule 17 minor)",
        "DT-04 ends at its Ø.250 land, socket added;\nT006 a part; T012, T018 round bores; VN-54, VN-55\nout; end screw, bushing in; DT-21 moved; DT-20 hole",
    ],
    [
        "C2",
        "DT-03 RV-01, RV-04; DT-04 RV-01, RV-02;\nVN-54 RV-01; DT-00 DT-03",
        "DT-03 RV-02 (T018–T120 D-bores);\nDT-21 RV-01; DT-20 RV-03",
        f"DT-03 RV-03 → T012 web {inch(N['t012_web_reamed_116'], 4)}; new DT-00: solder on\nthe T018-T012-T006 drive joints (rule 23);\nnew end screw: wall {inch(N['end_screw_wall'])} (rule 17 minor); jig drawing",
        "DT-04 loses its tip land; T006 a part; T012 round\nbore; VN-54, VN-55 out; end screw, bushing in;\nDT-21 moved; DT-20 hole; new soldering jig",
    ],
    [
        "A",
        "DT-03 RV-01, RV-04; DT-04 RV-01, RV-02;\nVN-54 RV-01; DT-00 DT-03",
        "DT-03 RV-02; DT-21 RV-01; DT-20 RV-03",
        f"DT-03 RV-03 → T012 web {inch(N['t012_web_reamed_116'], 4)};\nnew DT-00: solder on the T012-T006 joint;\nnew end screw wall {inch(N['end_screw_wall'])}",
        "as C2, plus the arbor; DT-04 ends at its Ø.375 land",
    ],
    [
        "B",
        "DT-03 RV-01, RV-03, RV-04; DT-04 RV-01, RV-02;\nVN-54 RV-01; DT-00 DT-03",
        "DT-03 RV-02; DT-21 RV-01; DT-20 RV-03",
        f"new end screw wall {inch(N['end_screw_wall'])};\npossible rule 16 acceptance for planing",
        "as A; T012, T018 configurations retire into the arbor",
    ],
    [
        "#1649 A (drill-rod tip)",
        "DT-04 RV-02",
        "DT-03 RV-01, RV-02, RV-03, RV-04; VN-54 RV-01;\nDT-21 RV-01; DT-00 DT-03",
        f"DT-04 RV-01 → rod socket wall {inch(N['drill_rod_wall'])} (below the floor)",
        "DT-04, new drill-rod tip",
    ],
    [
        "#1649 E (1/16 land)",
        "DT-04 RV-02 (if L/D 21 turns unsupported)",
        "DT-03 RV-01, RV-02; DT-04 RV-01; VN-54 RV-01;\nDT-21 RV-01; DT-00 DT-03",
        f"RV-04 → T006 web {inch(N['t006_web_116'], 4)} (worse than today);\nRV-03 → {inch(N['t012_web_d_116'], 4)}",
        "DT-03, DT-04",
    ],
    [
        "#1649 F, soldered",
        "DT-03 RV-01 (no D on T006, T012)",
        "DT-03 RV-02, RV-03, RV-04; DT-04 RV-01, RV-02;\nVN-54 RV-01; DT-21 RV-01; DT-00 DT-03",
        "new DT-00: solder on T006, T012 to the land",
        "DT-03, DT-04",
    ],
]
tb = ax.table(
    cellText=rows,
    colLabels=cols,
    loc="upper center",
    cellLoc="left",
    colLoc="left",
    colWidths=[0.11, 0.19, 0.25, 0.23, 0.22],
)
tb.auto_set_font_size(False)
tb.set_fontsize(7.8)
tb.scale(1, 3.9)
for (r, c), cell in tb.get_celld().items():
    cell.set_edgecolor(MUTED)
    cell.set_linewidth(0.6)
    if r == 0:
        cell.set_text_props(fontweight="bold")
        cell.set_facecolor("#efeee9")
    if c == 0 and r > 0:
        cell.set_text_props(fontweight="bold")
    if r == 2:
        cell.set_facecolor("#eef6ee")
fig.text(
    0.025,
    0.01,
    "Sources: cad/scripts and cad/config on main a8441605f; issue #1649; drawing-guidelines.md rules 4, 16, 17, 18, 20, 21, 23; book pp.17–21; "
    "engineerguy video 4 (6:36–6:39); contact zone measured on v45 gltf/dt-drive-train.glb (cone stations unchanged since). Proposal only, not in CAD.",
    fontsize=7.6,
    color=INK2,
)
fig.savefig(OUT, dpi=150, facecolor=SURFACE)
print("wrote", OUT)
