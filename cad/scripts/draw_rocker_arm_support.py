r"""Create the curated machinist drawing for the rocker-arm support.

The SLDPRT remains authoritative.  This recipe supplies only the support's
views, dimension layout, hole table, and casting/machining notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The support is a green-painted gray-iron casting: a trapezoidal wall with a
square window cut from both faces (leaving a central web), a rounded/chamfered
window rim, and four 9/16-12 UNC tapped holes up through the foot.  The sheet
runs 1:1; the isometric carries a 1:2 override.

Run with SolidWorks open::

    uv run python cad\scripts\draw_rocker_arm_support.py rocker-arm-support
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    curate_view_dimensions,
    finalize_drawing,
    insert_hole_table,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_rocker_arm_support import BOSS_DEPTH, HOLES, WIDE
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["rocker_arm_support"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 2.0)

# Sheet layout (meters).  A 177.8 mm casting with four views does not fit an
# ASME B sheet at 1:1 (measured: the notes column and the trapezoid view
# collided and the hole table clipped the border), so the whole sheet runs
# 1:2.  Third angle: taper (right view) beside the window face, foot (bottom
# view, the tapping setup) below it, aligned in X.
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]
FRONT_CENTER = (0.075, 0.200)
RIGHT_CENTER = (0.155, 0.200)
BOTTOM_CENTER = (0.075, 0.115)
ISO_CENTER = (0.360, 0.210)

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position (meters).
FRONT_KEEP = {
    "Depth": (0.075, 0.252),      # 177.8 overall width (extrude span), above
    "WinWidth": (0.075, 0.235),   # 165.1 window square, inside the opening
    "WinHeight": (0.024, 0.200),
    "CavWidth": (0.075, 0.172),   # 127 cavity square, seen through the window
    "CavDepth": (0.052, 0.200),
}
RIGHT_KEEP = {
    "WallHeight": (0.182, 0.200),  # 177.8 wall height, right of the taper
    "FootSpan": (0.155, 0.147),    # 63.5 foot section, below the view
    "TopSpan": (0.155, 0.252),     # 16.93 top section, above the view
}

HOLE_TABLE_ANCHOR = (0.284, 0.135)


# 9/16-12 tap drill (the modeled hole) — the edge pick must land ON the rim.
_TAP_DRILL_DIA_MM = 12.30376


def _bottom_sheet_xy(hole_xz: tuple[float, float]) -> tuple[float, float]:
    """Sheet pick point ON a foot hole's rim (model X, Z in mm), bottom view."""
    x_mm, z_mm = hole_xz
    return (
        BOTTOM_CENTER[0] + x_mm * VIEW_SCALE / 1000.0,
        BOTTOM_CENTER[1] + (z_mm + _TAP_DRILL_DIA_MM / 2.0) * VIEW_SCALE / 1000.0,
    )


_NOTES = (
    "UNLESS OTHERWISE SPECIFIED:",
    (
        "1. DIMENSIONS ARE IN MILLIMETRES.\n"
        "   INTERPRET PER ASME Y14.5."
    ),
    (
        "2. GRAY-IRON CASTING: AS-CAST\n"
        "   SURFACES +/-0.8; MACHINED\n"
        "   SURFACES +/-0.25; HOLE CENTRES\n"
        "   +/-0.20; ANGLES +/-1.0 DEG. MAY\n"
        "   BE MILLED FROM SOLID CLASS 30\n"
        "   BAR (NO DRAFT IS MODELLED)."
    ),
    (
        "3. REMOVE BURRS AND BREAK SHARP\n"
        "   EDGES 0.3 MAX."
    ),
    (
        "4. MACHINE THE FOOT BOTTOM FACE\n"
        "   FLAT 0.10, Ra 3.2 (DATUM A -\n"
        "   THE MOUNTING SEAT)."
    ),
    (
        "5. 4X TAPPED HOLES 9/16-12 UNC-2B\n"
        "   THRU THE 6.35 THICK FOOT LAND;\n"
        "   TAP FROM THE FOOT BOTTOM FACE\n"
        "   (DATUM A). SEE HOLE TABLE;\n"
        "   ORIGIN AT THE FOOT CORNER.\n"
        "   TABLE THREAD DEPTH 0.000 MEANS\n"
        "   TAPPED THRU."
    ),
    (
        "6. WINDOW RIM: CHAMFER 1.27 X 45\n"
        "   DEG ALL AROUND, BOTH FACES AND\n"
        "   SLANT SURROUNDS."
    ),
    (
        "7. INNER FRAME CORNERS: FILLET\n"
        "   R12.7, 4 PLACES."
    ),
    (
        "8. CENTRAL WEB 6.35 THICK, CENTRED\n"
        "   (WINDOW CUT FROM BOTH FACES).\n"
        "   WINDOW AND CAVITY SQUARES ARE\n"
        "   CENTRED BOTH WAYS ON THE WALL."
    ),
    (
        "9. FINISH: MACHINE GREEN ENAMEL;\n"
        "   MASK DATUM A AND TAPPED HOLES."
    ),
)


def _manufacturing_notes() -> str:
    return "\n".join(_NOTES)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-arm-support source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=("Number", "Material Specification", "Finish", "Quantity"),
    )
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker-Arm Support Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker-arm support; manufacturing drawing; casting",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 2))
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (front, right, bottom, iso):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    if not auto_center_marks(adapter, bottom, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to bottom view")

    # Foot corner datum + the four tapped holes: the native hole table carries
    # every X/Y station and the 9/16-12 tap callout.
    insert_hole_table(
        adapter,
        bottom,
        datum_xy=(
            BOTTOM_CENTER[0] - BOSS_DEPTH / 2.0 * VIEW_SCALE / 1000.0,
            BOTTOM_CENTER[1] - WIDE * VIEW_SCALE / 1000.0,
        ),
        hole_points=tuple(_bottom_sheet_xy(hole) for hole in HOLES),
        anchor_xy=HOLE_TABLE_ANCHOR,
        label="rocker-arm-support",
    )

    add_note(adapter, "\n".join(_NOTES[:5]), 0.014, 0.090)
    add_note(adapter, "\n".join(_NOTES[5:]), 0.150, 0.090)
    add_note(adapter, "FOOT SEAT - DATUM A (SEE NOTE 4)", 0.122, 0.112)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker-Arm Support Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
