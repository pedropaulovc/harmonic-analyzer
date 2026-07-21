r"""Create the curated machinist drawing for the cast-iron top-frame ring.

The SLDPRT remains authoritative.  This recipe supplies only the ring's views,
overall + bore dimensions, and casting notes; every shared sheet/template,
import, curation, and export behavior lives in ``_drawing_common``.

The ring is a green gray-iron casting: a 416 x 246 rectangular ring (22 wide
rails, 41 tall) with four Ø48 corner bosses bored Ø25.5 to clamp the columns,
plus a Ø17 gooseneck bore through one rail.  The sheet runs 1:2; the isometric
drops to 1:4.

Run with SolidWorks open::

    uv run python cad\scripts\draw_top_frame.py top-frame
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
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_top_frame import OUTER_X, OUTER_Z
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["top_frame"]
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

SHEET_SCALE = (1.0, 2.0)   # 1:2 whole sheet (416 mm ring)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]  # 0.5

# Sheet layout (meters).  The plan (top) is the sole ortho view: the ring is a
# flat 41-tall band, so a front view adds only its thin edge (the two-plate step
# it would show on a solid part is absent here) while crowding the sheet -- the
# thicknesses live in note 2 and the isometric (1:4) shows the depth in 3D.
TOP_CENTER = (0.135, 0.175)
ISO_CENTER = (0.345, 0.150)


# Per-view survivors of the marked-dimension import.  The overall footprint, one
# corner clamp bore (Ø25.5) and the gooseneck bore (Ø17) are kept; the pitch,
# rail width and boss OD are in the notes.  Width sits above the plan, Depth to
# its right (both keyed off the real outer envelope so they clear the sheet
# border); the two bore callouts stay tight to their west-side bores, above the
# lower-left note block.
TOP_KEEP = {
    "Width": (TOP_CENTER[0], TOP_CENTER[1] + OUTER_Z * VIEW_SCALE / 1000.0 + 0.012),
    "Depth": (TOP_CENTER[0] + OUTER_X * VIEW_SCALE / 1000.0 + 0.016, TOP_CENTER[1]),
    "C0Dia": (0.052, 0.135),
    "Dia": (0.052, 0.190),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open top-frame source", await adapter.open_model(str(SOURCE)))
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
            "Top View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Top View Note",
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
            0: "Top Frame Ring Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "top frame; ring; gray iron casting; column bores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (top, iso):
        set_hidden_lines_removed(adapter, view)

    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    # Bore Ø25.5 clamps the Ø25.4 column (0.1 slip); gooseneck Ø17. Two decimals
    # on the clamp bore, one on the round gooseneck.
    set_dimension_precision(adapter, top_annotations, {"C0Dia": 1, "Dia": 0})
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the ring bores")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.100)
    add_property_linked_note(adapter, "Top View Note", 0.040, 0.034)
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.095)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Top Frame Ring Manufacturing Drawing",
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
