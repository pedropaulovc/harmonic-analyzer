r"""Create the curated machinist drawing for the pen square rod.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
length of drawn square bar carries no datums and no feature-control frames --
its slide fit is the band on the model section, plus one roughness symbol on
the face that slides in the v-block; the wire hole says DRILL on its callout.
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
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from pen_rod_spec import ROD_LENGTH, SURFACE_FINISHES, WIRE_HOLE_DIA, WIRE_HOLE_Y
from solidworks_mcp.adapters.solidworks.drawing import (
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
TOP_VIEW_SCALE = 4.0
FRONT_CENTER = (0.070, 0.150)
RIGHT_CENTER = (0.140, 0.150)
TOP_CENTER = (0.070, 0.245)
ISO_CENTER = (0.340, 0.195)

FRONT_KEEP = {
    "Length": (FRONT_CENTER[0] - 0.030, FRONT_CENTER[1]),
    # x offset -0.034 (the Depth spelling below), NOT the view centre: Section
    # measures the 5 mm square across, so at 1:1 its two extension lines land
    # 4.7 mm apart (measured x=0.0679 and x=0.0726) while the toleranced text
    # renders 24.5 mm wide. Centred on FRONT_CENTER[0] the text spanned
    # 0.0580..0.0820, so BOTH extension lines ran through it and struck out
    # "+0.00/-0.05". text_xy is the text CENTRE, so -0.034 puts the run at
    # 0.0238..0.0483: clear of the left extension line by 19.6 mm and of the
    # drawn border rule (gray, x=~0.0126) by ~11.2 mm. No gate sees this -- a
    # dimension exposes no GetExtent, so only the render shows it.
    "Section": (
        FRONT_CENTER[0] - 0.034,
        FRONT_CENTER[1] - ROD_LENGTH / 2000.0 - 0.012,
    ),
}
TOP_KEEP = {
    "Depth": (TOP_CENTER[0] - 0.034, TOP_CENTER[1]),
}
# No-oversize bands on both functional slide dimensions live on the source model.
DIMENSION_CALLOUTS: dict[str, str] = {}
TOP_DIMENSION_CALLOUTS: dict[str, str] = {}


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
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines stay ON in every orthographic view (Harvey #30 / Lipton):
    # the right view shows the #47 wire hole through the section.
    for view in (front, right, top):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, top_annotations, TOP_DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the wire hole")

    front_bottom = (FRONT_CENTER[0], FRONT_CENTER[1] - ROD_LENGTH / 2000.0)
    front_side = (FRONT_CENTER[0] - 0.0025, FRONT_CENTER[1])
    hole_center_y = front_bottom[1] + WIRE_HOLE_Y / 1000.0
    hole_bottom = (FRONT_CENTER[0], hole_center_y - WIRE_HOLE_DIA / 2000.0)
    hole_side = (FRONT_CENTER[0] + WIRE_HOLE_DIA / 2000.0, hole_center_y)

    add_edge_dimension(
        adapter,
        front,
        p0=front_bottom,
        p1=hole_bottom,
        text_xy=(FRONT_CENTER[0] + 0.032, FRONT_CENTER[1] + 0.030),
        label="wire-hole length location",
    )
    # Locate the wire hole ACROSS the square section too: the native callout gives
    # only the drill size, so without this the cross-hole could sit off-centre and
    # still satisfy every shown dimension. Left slide face -> hole (line-to-circle,
    # so the value is to the hole centre) reads 2.50 of the 5.00 section = centred.
    add_edge_dimension(
        adapter,
        front,
        p0=front_side,
        p1=hole_side,
        text_xy=(FRONT_CENTER[0] - 0.030, hole_center_y + 0.020),
        label="wire-hole centerline location",
    )
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=hole_side,
        callout_xy=(FRONT_CENTER[0] + 0.034, hole_center_y + 0.017),
        label="pen-rod wire hole",
        process="#47 DRILL",
    )

    # The slide face is the one running surface (the rod slides in the v-block
    # guide), so it alone carries a roughness symbol. It sits RIGHT of the rod
    # and BELOW the right view, reaching back up-left to the slide face: the
    # leader leaves the triangle tip AT the anchor and the ~46 mm body draws
    # up-RIGHT of it, so a target up-LEFT keeps the leader clear of the body.
    # y=0.068 keeps the run under the right view (its box starts at y=0.090,
    # and a leader through a view it does not annotate fails the crossing
    # gate) and above the notes.
    add_surface_finish(
        adapter,
        front,
        edge_xy=(front_side[0], FRONT_CENTER[1] - 0.050),
        symbol_xy=(0.170, 0.068),
        control=surface_finish_by_key(SURFACE_FINISHES, "slide_face"),
        label="pen-rod slide face finish",
    )

    # 0.015, centred in the corridor between the drawn frame rule (x~0.0128)
    # and the title block's left edge (0.2658). Measured on the 2026-07-16
    # sheet: the title block did NOT translate with the re-centred frame
    # (Codex #334 re-anchored its right rules onto the border instead), so the
    # corridor is governed by the block's unmoved left edge. The note is now
    # far shorter than that corridor, but the anchor still reads as centred.
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
