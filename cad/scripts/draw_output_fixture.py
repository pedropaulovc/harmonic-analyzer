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
    DrawingOutputs,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from output_fixture_spec import COLLAR_DIA, COLLAR_HEIGHT, CROSS_HOLE_TAP
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
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
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]

# Sheet layout (meters).  The side (front) view carries the cross hole, the
# collar length and the hole station; the end (top) view above it carries the
# two concentric diameters; the isometric (2:1) sits to the right.
FRONT_CENTER = (0.120, 0.130)
TOP_CENTER = (0.120, 0.210)
ISO_CENTER = (0.340, 0.175)
# The caption is centred directly below the isometric.  Its former low sheet
# position visually labelled the side view instead.
ISOMETRIC_NOTE_XY = (ISO_CENTER[0] - 0.035, ISO_CENTER[1] - 0.027)

# Side-view silhouette (sheet meters): the collar is Ø10 wide by 8 tall.
_SIDE_HALF_W = COLLAR_DIA * VIEW_SCALE / 2000.0
_SIDE_HALF_H = COLLAR_HEIGHT * VIEW_SCALE / 2000.0

# Per-view survivors of the marked-dimension import.  The end (top) view carries
# the collar OD + rod bore; the side (front) view carries the collar length
# (left), the cross-hole station from the bottom faced end (right) and the
# cross-hole diameter callout (below right).  The keep union == the marked set.
TOP_KEEP = {
    "CollarDiaDim": (0.070, 0.238),
    "RodBoreDiaDim": (0.185, 0.210),
}
FRONT_KEEP = {
    "CollarHeightDim": (FRONT_CENTER[0] - _SIDE_HALF_W - 0.014, FRONT_CENTER[1]),
    "CrossHeight": (
        FRONT_CENTER[0] + _SIDE_HALF_W + 0.014,
        FRONT_CENTER[1] - _SIDE_HALF_H / 2.0,
    ),
    # Callout text low and right so its leader clears the CrossHeight lane.
    "CrossHoleDiaDim": (0.150, 0.088),
}
# The callout says the process (Harvey #13); the rod bore's slip-fit band
# rides the model dimension, so it prints natively beside the reamed Ø.  The
# cross hole is drilled through both walls and tapped on the entry wall only
# -- said once, at the feature, not in a note.
DIMENSION_CALLOUTS = {
    "RodBoreDiaDim": "REAM THRU",
    "CrossHoleDiaDim": f"DRILL THRU BOTH WALLS; TAP {CROSS_HOLE_TAP} ENTRY WALL ONLY",
}


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
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines ON in every orthographic view: the side view shows the rod
    # bore through the body, the end view the cross hole through both walls.
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    set_dimension_callouts(
        adapter, [*top_annotations, *front_annotations], DIMENSION_CALLOUTS
    )
    # The rod bore is the one fitted feature (reamed, band on the model
    # dimension): three decimals say "hold it"; everything else stays at the
    # two-place block tolerance.
    set_dimension_precision(
        adapter, [*top_annotations, *front_annotations], {"RodBoreDiaDim": 3}
    )
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the end view")
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the cross hole")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.078)
    add_property_linked_note(adapter, "End View Note", 0.170, 0.246)
    add_property_linked_note(adapter, "Isometric View Note", *ISOMETRIC_NOTE_XY)

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
