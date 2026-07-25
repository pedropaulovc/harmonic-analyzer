r"""Create the curated machinist drawing for the output fixture collar.

The SLDPRT remains authoritative.  This recipe supplies only the collar's
views, diameter/station dimensions, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The output fixture is a small brass collar (Ø10 x 8) that slides the trace's
vertical placement on the Ø5 output rod: a coaxial Ø5.2 slip bore and a Ø2.26
cross hole (#4-40 tap drill) for the clamp screw / lever-wire tie.  The collar
is tiny, so the sheet runs 3:1; the isometric drops to 2:1.

Run with SolidWorks open::

    uv run python cad\scripts\draw_output_fixture.py output-fixture
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    auto_center_marks,
    DrawingOutputs,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import (
    place_view,
)


SPEC = DRAWINGS_BY_NAME["output_fixture"]
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

SHEET_SCALE = (3.0, 1.0)   # 3:1 whole sheet (Ø10 collar)

# Sheet layout (meters).  The side (front) view carries the cross hole + height;
# the end (top) view above it carries the two concentric diameters; the
# isometric (2:1) sits to the right.
FRONT_CENTER = (0.120, 0.130)
TOP_CENTER = (0.120, 0.210)
ISO_CENTER = (0.340, 0.175)

# Per-view survivors of the marked-dimension import.  The end (top) view carries
# the collar OD + rod bore; the side (front) view carries the cross-hole
# diameter and its mid-height station.  The keep union == the marked set.
TOP_KEEP = frozenset({"CollarDiaDim", "RodBoreDiaDim"})
FRONT_KEEP = frozenset({"CrossHoleDiaDim"})


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open output-fixture source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
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
            0: "Output Fixture Collar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "output fixture; brass collar; rod bore; cross hole",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently auto-scale,
    # which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(3, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(3, 1))
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")
    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    if not auto_center_marks(adapter, top, holes=True):
        raise RuntimeError("failed to add ASME center marks to the end view")
    if not auto_center_marks(adapter, front, holes=True):
        raise RuntimeError("failed to add ASME center mark to the cross hole")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.078)
    add_property_linked_note(adapter, "End View Note", 0.170, 0.246)
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.112)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Output Fixture Collar Manufacturing Drawing",
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
