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
    curate_view_dimensions,
    finalize_drawing,
    insert_hole_table,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_rocker_arm_support import BOSS_DEPTH, HALF_Y, HOLES, WIDE
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    remove_notes_matching,
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
# Dropped from 0.210: the isometric's outline ran 6.8 mm into the top zone band.
# It cannot shrink to buy the room -- it already runs at the 1:2 sheet scale, and
# a view at any other scale would need a label this part declares no property for.
ISO_CENTER = (0.360, 0.201)

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position (meters).
FRONT_KEEP = {
    "Depth": (0.075, 0.252),      # 177.8 overall width (extrude span), above
    "WinWidth": (0.075, 0.235),   # 165.1 window square, inside the opening
    # Both window dims INSIDE the opening: outside the view a 165.1 vertical
    # reads as an overall height and contradicts the 177.8 wall height.
    #
    # The two VERTICAL dims sit in symmetric lanes either side of centre rather
    # than 14 mm apart at x=0.042/0.056, where their now-horizontal ~15 mm texts
    # printed as one string ("165.10127.00"). Each text lands inside the 127
    # cavity (x 0.0433..0.1068) -- the only region of this view with no outline
    # through it -- leaving a ~19 mm gap between them; their dimension lines stay
    # clear of the two horizontal dims' texts, which are centred on x=0.075.
    "WinHeight": (0.058, 0.200),
    "CavWidth": (0.075, 0.172),   # 127 cavity square, seen through the window
    "CavDepth": (0.092, 0.200),
}
RIGHT_KEEP = {
    "WallHeight": (0.182, 0.200),  # 177.8 wall height, right of the taper
    "FootSpan": (0.155, 0.147),    # 63.5 foot section, below the view
    "TopSpan": (0.155, 0.252),     # 16.93 top section, above the view
}

# Top-left anchor (meters); the table grows down and RIGHT. It is ~145 mm wide,
# so x=0.284 ran its right edge 9.7 mm past the 0.4191 margin -- 0.270 leaves
# ~4 mm there while still clearing the notes block (which ends at x~0.246).
# y drops with the isometric above it (see ISO_CENTER): the table top must stay
# below the iso's lower edge, and its bottom (~74 mm) clears both the audit's
# title-block keep-out (64 mm) and the block's drawn top rule (~68 mm).
HOLE_TABLE_ANCHOR = (0.270, 0.130)


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
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
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
        # The standoff must be PERPENDICULAR to the edge. This edge is the right
        # view's horizontal bottom (the mounting seat), so it needs a Y offset:
        # at the edge's own y the attachment triangle had nowhere to go and drew
        # INSIDE the box, its apex striking through the "A". The x-offset alone
        # runs ALONG the edge and buys no room. (datum C below is the pattern.)
        # x stays at 0.210 to clear the 63.50 FootSpan callout at (0.155, 0.147).
        symbol_xy=(0.210, datum_a_edge[1] - 0.012),
        datum="A",
        label="support mounting seat",
    )
    add_datum_feature(
        adapter,
        bottom,
        edge_xy=datum_b_edge,
        # Three constraints leave only a narrow window here.
        #   x: the tag DRAWS LEFT of its anchor (measured ~7.6 mm wide, its right
        #      edge on the anchor, leader running right to the face). The former
        #      -0.014 offset from the view's left edge at x=0.0306 put it far
        #      into the margin. 0.027 leaves its edge at 0.0194: clear of the
        #      12.7 mm zone margin (~0.0127, which the re-centred frame rule now
        #      matches) by ~6.7 mm, and still ~3.6 mm short of the view.
        #   y: at the edge's mid-height the tag landed ON the hole table's origin
        #      indicator, whose "Y" label and axis arrow occupy x 0.0165..0.0194
        #      up to y=0.1205; y=0.131 lifts it clear into empty sheet.
        symbol_xy=(0.027, 0.131),
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
    # x=0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame rule
    # now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)

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
