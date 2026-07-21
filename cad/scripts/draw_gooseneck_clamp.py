r"""Create the curated machinist drawing for the gooseneck clamp block.

The SLDPRT remains authoritative.  This recipe supplies only the clamp's views,
the block envelope + bore dimensions, and the manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in ``_drawing_common``.

The clamp is a small green gray-iron block (30 wide x 29 tall x 24 deep) with a
vertical Ø16.5 bore the Ø16 gooseneck post slides in, pinched by a side-entry
square-head screw.  The sheet runs 2:1 (the block is only 30 mm); the isometric
carries an explicit 1:1 override so it stays clear of the title block.  Third
angle: the top view (the bore circle) sits above the front view.

Run with SolidWorks open::

    uv run python cad\scripts\draw_gooseneck_clamp.py gooseneck-clamp
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_gooseneck_clamp import BLOCK_HALF_X, BLOCK_HEIGHT
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["gooseneck_clamp"]
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

SHEET_SCALE = (2.0, 1.0)   # 2:1 whole sheet (30 mm block)
_M = SHEET_SCALE[0] / 1000.0  # model mm -> sheet meters

# Sheet layout (meters).  Front view (30 wide x 29 tall block face, carrying the
# square screw head and the hidden bore channel) is the main view; the top view
# (the Ø16.5 bore as a circle) sits above it (third angle); the isometric drops
# to 1:1 on the right.
FRONT_CENTER = (0.110, 0.120)
TOP_CENTER = (0.110, 0.208)
ISO_CENTER = (0.345, 0.150)

# Per-view survivors of the marked-dimension import.  BlockProfile's Width/Height
# live on the Front sketch -> the front view; BoreProfile's BoreDia lives on the
# Top sketch -> the top view.  Width below the front, Height to its left, the
# bore Ø leadered to the upper-right of the top view.
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], FRONT_CENTER[1] - BLOCK_HEIGHT / 2.0 * _M - 0.011),
    "Height": (FRONT_CENTER[0] - BLOCK_HALF_X * _M - 0.014, FRONT_CENTER[1]),
}
TOP_KEEP = {
    "BoreDia": (TOP_CENTER[0] + BLOCK_HALF_X * _M + 0.014, TOP_CENTER[1] + 0.012),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open gooseneck-clamp source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Gooseneck Clamp Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "gooseneck clamp; gray iron block; post bore; pinch screw",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently auto-scale,
    # which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, top)
    set_hidden_lines_removed(adapter, iso)
    # The front view carries the bore channel as greyed hidden lines behind the
    # square head, so both read.
    set_hidden_lines_visible(adapter, front)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    # The bore is a single-decimal 16.5 slip fit on the Ø16 post; two decimals
    # would read as false precision.
    set_dimension_precision(adapter, top_annotations, {"BoreDia": 1})
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the clamp bore")

    # 0.082 (was 0.071): machinist round 1 grew the notes block by two lines
    # (~10.6 mm at ~5.3 mm/line) and its bottom crossed the sheet zone border
    # by 9.3 mm -- raise the anchor so the block clears the border again.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.082)
    add_property_linked_note(adapter, "Isometric View Note", 0.322, 0.108)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Gooseneck Clamp Manufacturing Drawing",
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
