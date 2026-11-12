"""Comparison figure for the gear-train purchase decision (#2356).

Draws, to scale in inches, the cone stack and one cylinder gear as designed
(route A, every gear cut in the shop) beside the same parts built from
catalogue gears (route B), and the three routes' costs. Gear sizes come from
the CAD specs; catalogue sizes and prices are the rows read live on
2026-11-12 (see README.md beside this script).

    uv run python research/3-detailed-design/gear-train-purchase-options/compare_routes.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "cad" / "scripts"))

import dt_cone_gear_spec  # noqa: E402
import dt_cylinder_gear_spec  # noqa: E402

MM = 25.4
FACE = dt_cone_gear_spec.FACE_WIDTH / MM
DP = float(dt_cone_gear_spec.DIAMETRAL_PITCH)
TEETH = dt_cone_gear_spec.CONE_TEETH

# Catalogue brass 48DP 20 deg gears, face .125 (Boston Y48xx / McMaster
# 7880K): hub diameter and the cheapest price read; None = no vendor lists
# the count; "bore" = the stock bore is already larger than the design bore.
CATALOGUE = {
    6: None, 12: "bore", 18: "bore", 24: (0.38, 32.20), 30: (0.44, 50.81),
    36: (0.50, 38.18), 42: (0.57, 70.37), 48: (0.63, 59.98), 54: (0.69, 110.50),
    60: (0.69, 110.67), 66: (0.75, 126.71), 72: (0.75, 127.70), 78: None,
    84: (0.82, 144.46), 90: None, 96: (0.88, 157.87), 102: None, 108: None,
    114: None, 120: (0.75, 171.00),
}  # fmt: skip
STOCK_FACE = 0.125
BRASS, BOUGHT, MADE, STEEL = "#c9a227", "#4f81bd", "#c9a227", "#8c8c8c"

# Route totals, USD before shipping and tax, C67500 rod (quotation) excluded.
ROUTES = (
    ("A\nmake every gear\n(as designed)", (("cutters x11", 1379.13), ("arbors, broach kit,\npress, small tools", 516.20), ("bar stock", 521.58))),
    ("B\nbuy catalogue gears,\nmake the rest", (("cutters x7 (+2)", 895.97), ("arbors, broach kit,\npress, small tools", 516.20), ("bar stock", 460.39), ("14 cone gears", 1239.32), ("20 x 120T donors", 3420.00))),
    ("C\nroute A + one bought\n120T rolling master", (("cutters x11", 1379.13), ("arbors, broach kit,\npress, small tools", 516.20), ("bar stock", 521.58), ("1 x Y48120", 171.00))),
)  # fmt: skip


def _stack(ax, bought: bool) -> None:
    for index, teeth in enumerate(reversed(TEETH)):
        x = index * FACE
        radius = (teeth + 2) / DP / 2.0
        row = CATALOGUE[teeth]
        if bought and isinstance(row, tuple):
            hub = row[0] / 2.0
            ax.add_patch(
                Rectangle(
                    (x, -radius), STOCK_FACE, 2 * radius, fc=BOUGHT, ec="k", lw=0.4
                )
            )
            ax.add_patch(
                Rectangle(
                    (x + STOCK_FACE, -hub),
                    FACE - STOCK_FACE,
                    2 * hub,
                    fc="#9db7d8",
                    ec="k",
                    lw=0.4,
                )
            )
        else:
            ax.add_patch(
                Rectangle((x, -radius), FACE, 2 * radius, fc=MADE, ec="k", lw=0.4)
            )
            if bought and teeth != 6:
                note = "no\nstock" if row is None else "bore"
                ax.text(
                    x + FACE / 2,
                    radius + 0.06,
                    note,
                    ha="center",
                    va="bottom",
                    fontsize=5.5,
                    rotation=90,
                )
        if teeth % 30 == 0 or teeth in (6, 12):
            ax.text(
                x + FACE / 2,
                -radius - 0.08,
                f"T{teeth:03d}",
                ha="center",
                va="top",
                fontsize=6,
            )
    ax.plot([-0.4, len(TEETH) * FACE + 0.3], [0, 0], color="k", lw=0.5, ls="-.")
    ax.set_xlim(-0.5, len(TEETH) * FACE + 0.4)
    ax.set_ylim(-1.75, 1.75)
    ax.set_aspect("equal")
    ax.axis("off")


def _cylinder(ax, bought: bool) -> None:
    spec = dt_cylinder_gear_spec
    od = spec.OUTSIDE_DIA / MM / 2.0
    disc = spec.FACE_WIDTH / MM
    cam_r = spec.CAM_DIA / MM / 2.0
    throw = spec.ECCENTRICITY / MM
    total = spec.OVERALL_THICKNESS / MM
    ax.add_patch(
        Rectangle(
            (0, -od),
            0.125 if bought else disc,
            2 * od,
            fc=BOUGHT if bought else MADE,
            ec="k",
            lw=0.5,
        )
    )
    start = 0.125 if bought else disc
    ax.add_patch(
        Rectangle(
            (start, throw - cam_r),
            total - start,
            2 * cam_r,
            fc="#e0c56e" if bought else MADE,
            ec="k",
            lw=0.5,
            hatch="//" if bought else None,
        )
    )
    ax.plot([-0.25, 0.6], [0, 0], color="k", lw=0.5, ls="-.")
    ax.annotate(
        "",
        xy=(0.45, throw),
        xytext=(0.45, 0),
        arrowprops={"arrowstyle": "<->", "lw": 0.6},
    )
    ax.text(
        0.48,
        throw / 2,
        f"throw\n{throw:.4f}"[:12].replace("0.", "."),
        fontsize=6,
        va="center",
    )
    label = (
        "bought 120T ring (face .125, hub cut off,\nbore .3125 reamed to .3760)\n"
        "+ separate cam, bonded or soldered,\nclocked to a tooth: a new joint x20"
        if bought
        else f"one piece: {spec.TEETH}T disc {disc:.3f} +\nintegral cam, bore {spec.BORE_DIA / MM:.4f}"
    )
    ax.text(0.9, 0.0, label, fontsize=6.5, va="center")
    ax.set_xlim(-0.3, 3.2)
    ax.set_ylim(-1.45, 1.45)
    ax.set_aspect("equal")
    ax.axis("off")


def main() -> Path:
    fig = plt.figure(figsize=(15, 9.5), dpi=140)
    grid = fig.add_gridspec(
        2, 3, width_ratios=(2.5, 1.6, 1.6), hspace=0.22, wspace=0.12
    )
    for row, bought in enumerate((False, True)):
        ax = fig.add_subplot(grid[row, 0])
        _stack(ax, bought)
        ax.set_title(
            "Route B: catalogue gears (blue), face .125 on turned-down hubs;\nmade gears (brass) where no stock exists or the stock bore is too big"
            if bought
            else "Routes A and C: cone stack as designed and as the original:\n20 full-face gears (.2934), face to face",
            fontsize=8.5,
            loc="left",
        )
        ax = fig.add_subplot(grid[row, 1])
        _cylinder(ax, bought)
        ax.set_title("cylinder gear, x20\n", fontsize=8.5, loc="left")
    ax = fig.add_subplot(grid[:, 2])
    colours = ("#7f7f7f", "#bfbfbf", BRASS, BOUGHT, "#9db7d8")
    for column, (name, parts) in enumerate(ROUTES):
        bottom = 0.0
        for (label, cost), colour in zip(parts, colours):
            ax.bar(
                column,
                cost,
                bottom=bottom,
                color=colour,
                edgecolor="k",
                lw=0.4,
                width=0.62,
            )
            if cost > 150:
                ax.text(
                    column,
                    bottom + cost / 2,
                    f"{label}\n${cost:,.0f}",
                    ha="center",
                    va="center",
                    fontsize=6,
                )
            bottom += cost
        ax.text(
            column,
            bottom + 60,
            f"${bottom:,.0f}",
            ha="center",
            fontsize=9,
            weight="bold",
        )
    ax.set_xticks(range(len(ROUTES)), [name for name, _ in ROUTES], fontsize=7)
    ax.set_ylabel(
        "USD, before shipping and tax; C67500 rod (quotation) not included", fontsize=7
    )
    ax.set_ylim(0, 7300)
    ax.tick_params(axis="y", labelsize=7)
    ax.set_title("Purchases by route (prices read live 2026-11-12)", fontsize=8.5)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.suptitle(
        "Gear train, make or buy (#2356): side views to scale (inches) and cost",
        fontsize=11,
    )
    out = HERE / "gear-train-routes.png"
    fig.savefig(out, bbox_inches="tight")
    return out


if __name__ == "__main__":
    print(main())
