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
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    insert_hole_table,
    remove_notes_matching,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_rocker_arm_support import BOSS_DEPTH, HALF_Y, HOLES, WIDE
from solidworks_mcp.adapters.solidworks.drawing import (
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
    # Both window dims INSIDE the opening: outside the view a 165.1 vertical
    # reads as an overall height and contradicts the 177.8 wall height.
    "WinHeight": (0.042, 0.200),
    "CavWidth": (0.075, 0.172),   # 127 cavity square, seen through the window
    "CavDepth": (0.056, 0.200),
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
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
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
    for view in (front, bottom, iso):
        set_hidden_lines_removed(adapter, view)
    # The taper view carries the internal story: greyed hidden lines show the
    # central web band and cavity floor, so "window cut from both faces,
    # leaving the web" is visible rather than prose-only.
    set_hidden_lines_visible(adapter, right)
    removed_thread_notes = remove_notes_matching(adapter, "9/16-12")
    _telemetry.info(
        f"removed {removed_thread_notes} redundant automatic thread note(s)"
    )

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

    # Native datum reference frame, flatness/position controls, and Ra symbol
    # replace former notes 4 and 6. The bottom view supplies the hole-table DRF.
    datum_a_edge = (
        RIGHT_CENTER[0],
        RIGHT_CENTER[1] - HALF_Y * VIEW_SCALE / 1000.0,
    )
    datum_b_edge = (
        BOTTOM_CENTER[0] - BOSS_DEPTH / 2.0 * VIEW_SCALE / 1000.0,
        BOTTOM_CENTER[1],
    )
    datum_c_edge = (
        BOTTOM_CENTER[0],
        BOTTOM_CENTER[1] - WIDE * VIEW_SCALE / 1000.0,
    )
    add_datum_feature(
        adapter,
        right,
        edge_xy=datum_a_edge,
        symbol_xy=(0.210, datum_a_edge[1]),
        datum="A",
        label="support mounting seat",
    )
    add_datum_feature(
        adapter,
        bottom,
        edge_xy=datum_b_edge,
        symbol_xy=(datum_b_edge[0] - 0.014, BOTTOM_CENTER[1]),
        datum="B",
        label="support seat side",
    )
    add_datum_feature(
        adapter,
        bottom,
        edge_xy=datum_c_edge,
        symbol_xy=(BOTTOM_CENTER[0], datum_c_edge[1] - 0.012),
        datum="C",
        label="support seat end",
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=datum_a_edge,
        frame_xy=(0.205, 0.175),
        characteristic="flatness",
        tolerance="0.10",
        label="support mounting-seat flatness",
    )
    add_feature_control_frame(
        adapter,
        bottom,
        edge_xy=_bottom_sheet_xy(HOLES[0]),
        frame_xy=(0.120, 0.090),
        characteristic="position",
        tolerance="0.40",
        datums=("A", "B", "C"),
        diameter=True,
        quantity="4X",
        label="support hole-pattern position",
    )
    add_surface_finish(
        adapter,
        right,
        edge_xy=datum_a_edge,
        symbol_xy=(0.225, 0.145),
        roughness_ra="3.2",
        label="support mounting-seat finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.014, 0.060)

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
