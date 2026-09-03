r"""Create the curated machinist drawing for the pen square rod.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
length of drawn square bar carries no datums, feature-control frames, surface
finish symbols or owned machining tolerance because its faces pass as received.
The main front view locates the #47 through hole 145 along the rod and explicitly
centres it across the 5 mm square section; its size remains a native associative
Hole Wizard callout. The top view confirms the through hole, while the isometric
supplies shape context without a redundant right or empty detail view.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from pen_rod_spec import ROD_LENGTH, ROD_SECTION, WIRE_HOLE_DIA, WIRE_HOLE_Y
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pen_rod"]
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

SHEET_SCALE = (1.0, 1.0)
FRONT_CENTER = (0.070, 0.150)
TOP_CENTER = (0.070, 0.245)
ISO_CENTER = (0.340, 0.195)

FRONT_BOTTOM = (FRONT_CENTER[0], FRONT_CENTER[1] - ROD_LENGTH / 2000.0)
WIRE_HOLE_CENTER_Y = FRONT_BOTTOM[1] + WIRE_HOLE_Y / 1000.0
# Keep both annotations right of the longitudinal dimensions. The native
# callout sits above the hole so its leader crosses the 145 lane above that
# dimension's upper endpoint; the selection-free centring note sits below it.
WIRE_HOLE_CALLOUT_XY = (0.165, WIRE_HOLE_CENTER_Y + 0.018)
WIRE_HOLE_CENTER_NOTE_XY = (0.120, WIRE_HOLE_CENTER_Y - 0.022)
WIRE_HOLE_CENTER_NOTE = f"HOLE CENTERED ACROSS {ROD_SECTION:g} SQ SECTION"

FRONT_KEEP = {
    "Length": (FRONT_CENTER[0] - 0.030, FRONT_CENTER[1]),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-rod source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Top View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen rod; square brass slide rod; wire hole",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines stay ON in both orthographic views (Harvey #30 / Lipton):
    # the top view confirms that the #47 hole passes through the square stock.
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

    # Only overall length is imported from the model. The square drawn-stock
    # size is governed once by the manufacturing note, not repeated as a
    # machined dimension.
    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the wire hole")

    hole_bottom = (
        FRONT_CENTER[0],
        WIRE_HOLE_CENTER_Y - WIRE_HOLE_DIA / 2000.0,
    )

    # Along the rod: bottom face -> hole (line-to-circle, so the value is to
    # the hole centre), on the front view where the bottom face is.
    add_edge_dimension(
        adapter,
        front,
        p0=FRONT_BOTTOM,
        p1=hole_bottom,
        text_xy=(FRONT_CENTER[0] + 0.032, FRONT_CENTER[1] + 0.030),
        label="wire-hole length location",
    )

    wire_hole_edge = visible_circle_edge(adapter, front, WIRE_HOLE_DIA)
    # The transverse location is explicit beside the main front view without
    # selecting a short view edge or creating a derived detail view.
    if (
        add_note(
            adapter,
            WIRE_HOLE_CENTER_NOTE,
            *WIRE_HOLE_CENTER_NOTE_XY,
        )
        is None
    ):
        raise RuntimeError("failed to add wire-hole centerline location note")
    # Place the native associative callout above and well right of both
    # longitudinal dimension lanes. Its leader reaches the hole above the
    # 145 mm dimension endpoint instead of crossing either extension line.
    add_native_hole_callout(
        adapter,
        front,
        edge=wire_hole_edge,
        callout_xy=WIRE_HOLE_CALLOUT_XY,
        label="pen-rod wire hole",
        process="#47 DRILL",
    )

    # The stock note owns the square size and as-received-face requirement;
    # no duplicate width dimension or roughness symbol is added.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.015, 0.058)
    add_property_linked_note(adapter, "Top View Note", 0.036, 0.266)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Rod Manufacturing Drawing",
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
