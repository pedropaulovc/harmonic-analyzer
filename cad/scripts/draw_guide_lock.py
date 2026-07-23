r"""Create the curated machinist drawing for the platen guide lock plate.

The SLDPRT remains authoritative.  This recipe supplies only the guide-lock
views, dimension layout, hole callout, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 4:1 (the plate is 22 x 19 x 2); the isometric carries an
explicit 2:1 override so it stays clear of the title block.  A flat plate
needs only the face view (front), one thickness view (right) and the iso.

Run with SolidWorks open::

    uv run python cad\scripts\draw_guide_lock.py guide-lock
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_view_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_basic_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME

from guide_lock_spec import (
    HOLE_DIA_MM,
    HOLE_XY,
    LOCK_HEIGHT,
    LOCK_THICK,
    LOCK_WIDTH,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["guide_lock"]
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

SHEET_SCALE = (4.0, 1.0)

# Sheet layout (meters).  The front view's model bbox is 22 x 19 (the plate
# face); at 4:1 the view is 88 x 76 mm.  Third angle: the right view (the
# 2-thick strip section) sits to its right; the isometric rides top-right.
FRONT_CENTER = (0.120, 0.150)
RIGHT_CENTER = (0.230, 0.150)
ISO_CENTER = (0.340, 0.200)


def _sheet_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (4:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - LOCK_WIDTH / 2.0) * SHEET_SCALE[0] / 1000.0


def _sheet_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (4:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - LOCK_HEIGHT / 2.0) * SHEET_SCALE[0] / 1000.0


# Handy picks derived from the layout above.
LEFT_EDGE_X = _sheet_x(0.0)
BOTTOM_EDGE_Y = _sheet_y(0.0)
HOLE_R_SHEET = HOLE_DIA_MM * SHEET_SCALE[0] / 2000.0
HOLE_Y_SHEET = _sheet_y(HOLE_XY[0][1])
HOLE_1_X_SHEET = _sheet_x(HOLE_XY[0][0])
HOLE_2_X_SHEET = _sheet_x(HOLE_XY[1][0])
# The right view is seen along -X, so model +Z points screen-LEFT: the z=0
# screw-entry face (datum A) is the section's right-hand silhouette edge.
DATUM_FACE_X = RIGHT_CENTER[0] + LOCK_THICK * SHEET_SCALE[0] / 2000.0

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  Width stacks below the front view (under the hole locators),
# Height sits to its left, the strip thickness rides above the right view.
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], 0.088),
    "Height": (0.064, FRONT_CENTER[1]),
}
RIGHT_KEEP = {"Depth": (RIGHT_CENTER[0], 0.196)}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    drawing_model, sheet = new_project_drawing(
        adapter,
        category=SPEC.category,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Guide Lock Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "guide lock; manufacturing drawing; #4 clearance",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    read_required_view_properties(
        adapter,
        front,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    # The right view shows the 2-thick strip edge-on; HLV exposes the screw
    # holes' through extents.
    set_hidden_lines_visible(adapter, right)

    # No callout/precision overrides: the imported Width/Height/Depth read
    # fine at the document default, and the hole size ships as a native
    # wizard callout below.
    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    # Hole locators as BASIC dimensions off the datum edges (position tolerance
    # is carried by the FCF below): each hole's X from the left edge (datum C)
    # and the shared 2.5 band height from the guide-side edge (datum B).
    hole_1_x = add_edge_dimension(
        adapter,
        front,
        p0=(LEFT_EDGE_X, FRONT_CENTER[1] + 0.010),
        p1=(HOLE_1_X_SHEET, HOLE_Y_SHEET + HOLE_R_SHEET),
        text_xy=(0.088, 0.104),
        label="hole-1 X location",
    )
    set_basic_dimension(adapter, hole_1_x, label="hole-1 X location")
    hole_2_x = add_edge_dimension(
        adapter,
        front,
        p0=(LEFT_EDGE_X, FRONT_CENTER[1] + 0.020),
        p1=(HOLE_2_X_SHEET, HOLE_Y_SHEET + HOLE_R_SHEET),
        text_xy=(0.112, 0.096),
        label="hole-2 X location",
    )
    set_basic_dimension(adapter, hole_2_x, label="hole-2 X location")
    hole_band_y = add_edge_dimension(
        adapter,
        front,
        p0=(FRONT_CENTER[0] - 0.014, BOTTOM_EDGE_Y),
        p1=(HOLE_1_X_SHEET - HOLE_R_SHEET, HOLE_Y_SHEET),
        text_xy=(0.056, 0.118),
        label="hole band height",
    )
    set_basic_dimension(adapter, hole_band_y, label="hole band height")

    # Native datum/GD&T/surface annotations.  Right view is the 2-thick strip
    # section: its z=0 screw-entry face (against the guide rail) is datum A.
    add_datum_feature(
        adapter,
        right,
        edge_xy=(DATUM_FACE_X, RIGHT_CENTER[1] + 0.006),
        symbol_xy=(DATUM_FACE_X + 0.016, RIGHT_CENTER[1] + 0.024),
        datum="A",
        label="lock rail-mating face",
    )
    # The standoff MUST be perpendicular to the attached edge: this is the
    # plate's horizontal bottom edge, so the symbol offsets in Y. An X offset
    # runs ALONG the edge, leaving zero room for the attachment triangle, which
    # then renders inside the box on top of the letter (measured: a symbol at
    # bottom-edge height put the triangle in the "B"'s bowl).
    #
    # X=0.156 drops it into the one pocket the locator chain leaves: the
    # 22.00/18.00 dimension lines (y 0.0851/0.0932) span only x 0.076..0.164 and
    # the 4.00 (y 0.1013) stops at x=0.096, so x 0.148..0.164 is clear from the
    # 18.00 line up to the plate edge -- an 18.6 mm gap, centred here. The 7.1 mm
    # box hangs 8 mm below the edge, clearing the 18.00 line by 3.7 mm.
    add_datum_feature(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + 0.036, BOTTOM_EDGE_Y),
        symbol_xy=(FRONT_CENTER[0] + 0.036, BOTTOM_EDGE_Y - 0.008),
        datum="B",
        label="lock guide-side edge",
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=(LEFT_EDGE_X, FRONT_CENTER[1] + 0.018),
        symbol_xy=(LEFT_EDGE_X - 0.016, FRONT_CENTER[1] + 0.018),
        datum="C",
        label="lock end edge",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(HOLE_2_X_SHEET + HOLE_R_SHEET, HOLE_Y_SHEET),
        frame_xy=(0.176, 0.134),
        characteristic="position",
        # Fixed-fastener stack (codex machinist review): close-fit Ø3.048 over
        # the #4 screws' Ø2.845 majors leaves ~Ø0.20 of position TOTAL across
        # the plate + rail pair, so this plate's share is Ø0.10 -- Ø0.20 here
        # would consume the whole stack alone.
        tolerance="0.10",
        datums=("A", "B", "C"),
        diameter=True,
        quantity="2X",
        label="screw-hole position",
    )
    add_feature_control_frame(
        adapter,
        right,
        # Pick on datum face A CLEAR of the screw-hole band.  Seen edge-on in
        # the right view the Ø3.048 holes read as hidden edges at y = 0.122 +-
        # 0.0061 (0.1159..0.1281 sheet); a pick at the old -0.022 (=0.128)
        # landed on the hole-edge/datum-face intersection, so the FCF could
        # attach to the hole edge instead.  -0.006 sits above the band (like
        # the +0.006/+0.030 datum and finish picks), on a clean face point.
        edge_xy=(DATUM_FACE_X, RIGHT_CENTER[1] - 0.006),
        frame_xy=(0.248, 0.124),
        characteristic="flatness",
        tolerance="0.10",
        label="rail-mating face flatness",
    )
    # The bent leader elbows at the text's LEFT end, so the text must start just
    # RIGHT of the hole it points at or the tail rakes back across the view: the
    # old (0.094, 0.198) centred the ~45 mm wide "2X Ø3.05 THRU ALL" so its
    # elbow fell at x=0.071, left of hole 1 at x=0.093, and the tail ran as one
    # long diagonal down across the whole plate face. Centred at 0.117 the text
    # starts at ~0.094 and the tail drops nearly vertically into the bore.
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=(HOLE_1_X_SHEET, HOLE_Y_SHEET + HOLE_R_SHEET),
        callout_xy=(0.117, 0.196),
        label="guide-lock screw holes",
    )
    # x=0.020: the note anchor IS the text's left edge, so the ink starts here.
    # The 0.0127 margin ISheet::GetZoneMargin declares and the re-centred border
    # rule (~0.0126) now agree; 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.315, 0.160)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Guide Lock Manufacturing Drawing",
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
