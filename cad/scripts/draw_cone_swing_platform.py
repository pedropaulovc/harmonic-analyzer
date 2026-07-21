r"""Create the curated machinist drawing for the cone swing platform.

The SLDPRT remains authoritative.  This recipe supplies only the platform's
views, the wedge envelope dimensions, and the machining notes; every shared
sheet/template, import, curation, and export behavior lives in ``_drawing_common``.

The platform is a black-oxide 1/4 in steel plate: an asymmetric wedge (214 long,
21.5 -> 57 wide) with a Ø6.76 pivot hole at the narrow tip, an open lock notch
through the west edge, and rounded plan corners.  The sheet runs 1:2; the
isometric drops to 1:4.

Run with SolidWorks open::

    uv run python cad\scripts\draw_cone_swing_platform.py cone-swing-platform
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
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cone_swing_platform"]
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

SHEET_SCALE = (1.0, 2.0)   # 1:2 whole sheet (214 mm plate)

# Sheet layout (meters).  The plan (top) is the main view (the wedge, ~28 x 107
# at 1:2); the isometric (1:4) sits to its right.
TOP_CENTER = (0.105, 0.178)
ISO_CENTER = (0.330, 0.175)

# Per-view survivors of the marked-dimension import: the wedge envelope only.
# The narrow (north) end reads 21.5, the wide (south) end 57, the length 214.
# The plan sits high enough that the SouthEdge callout at the wide (bottom) end
# clears the lower-left note block.
TOP_KEEP = {
    "PlateLenDim": (0.048, 0.178),
    "NorthEdge": (0.105, 0.245),
    "SouthEdge": (0.105, 0.116),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-swing-platform source", await adapter.open_model(str(SOURCE)))
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
            "Plan View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Plan View Note",
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
            0: "Cone Swing Platform Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone swing platform; wedge plate; pivot; lock notch",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (top, iso):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the pivot hole")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.100)
    add_property_linked_note(adapter, "Plan View Note", 0.040, 0.036)
    add_property_linked_note(adapter, "Isometric View Note", 0.290, 0.108)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Swing Platform Manufacturing Drawing",
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
