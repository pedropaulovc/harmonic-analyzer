r"""Create the curated machinist drawing for the pen square rod.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
length of drawn square bar carries no datums, no feature-control frames and
no roughness symbol -- its slide fit is the band on the model section and the
drawn faces pass as received. The wire hole is located along the rod on the
front view; its size (#47 DRILL on the callout) and its 2.50 centring across
the section read in DETAIL A at 4:1, where a 2.5 mm span is legible (policy
rule 7: a feature too small to dimension at the sheet scale gets a detail;
machinist review 2026-09-02: the 2.50 crowded the top view's 5.00).
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
    create_detail_view,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
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
TOP_VIEW_SCALE = 4.0
FRONT_CENTER = (0.070, 0.150)
RIGHT_CENTER = (0.140, 0.150)
TOP_CENTER = (0.070, 0.245)
ISO_CENTER = (0.340, 0.195)

# DETAIL A (4:1): a circle around the wire hole on the front view -- 6 mm
# radius takes in the hole and both rod faces -- enlarged right of the right
# view and left of the isometric, under the top view's row. At 4:1 the
# 5 mm section reads 20 mm across and the O1.99 hole 8 mm, so the 2.50
# centring dimension and the hole callout both fit legibly.
DETAIL_RADIUS = 0.006
DETAIL_CENTER = (0.195, 0.175)
DETAIL_SCALE = (4, 1)
WIRE_HOLE_CENTER_NOTE = f"HOLE CL {ROD_SECTION / 2.0:.2f} FROM FACE"

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

    # Curate the front and top model dimensions. DETAIL A receives only the
    # selection-free centring note; its derived geometry exposes no model edges
    # through SolidWorks, so the native hole callout stays on the main front.
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
    hole_center_y = front_bottom[1] + WIRE_HOLE_Y / 1000.0
    hole_bottom = (FRONT_CENTER[0], hole_center_y - WIRE_HOLE_DIA / 2000.0)

    # Along the rod: bottom face -> hole (line-to-circle, so the value is to
    # the hole centre), on the front view where the bottom face is.
    add_edge_dimension(
        adapter,
        front,
        p0=front_bottom,
        p1=hole_bottom,
        text_xy=(FRONT_CENTER[0] + 0.032, FRONT_CENTER[1] + 0.030),
        label="wire-hole length location",
    )

    # DETAIL A around the hole, enlarged 4:1. The hole centre and the rod's
    # slide face are projected from the MODEL into the detail (the detail is
    # positioned on its circle centre, but the projection is exact).
    detail = create_detail_view(
        adapter,
        front,
        center=(FRONT_CENTER[0], hole_center_y),
        radius=DETAIL_RADIUS,
        view_xy=DETAIL_CENTER,
        detail_label="A",
        scale=DETAIL_SCALE,
        label="wire hole detail",
    )
    hole_cx, hole_cy = model_point_in_view(
        adapter, detail, (0.0, WIRE_HOLE_Y / 1000.0, 0.0), label="detail hole centre"
    )
    wire_hole_edge = visible_circle_edge(adapter, front, WIRE_HOLE_DIA)
    # Across the section, the hole axis is 2.50 from either 5.00 slide face.
    # State that controlling value beside DETAIL A instead of dimensioning a
    # short derived-view edge that is not stable across SolidWorks seats.
    wire_hole_center_note_xy = (
        hole_cx - 0.005,
        hole_cy + DETAIL_RADIUS * DETAIL_SCALE[0] + 0.010,
    )
    if (
        add_note(
            adapter,
            WIRE_HOLE_CENTER_NOTE,
            *wire_hole_center_note_xy,
        )
        is None
    ):
        raise RuntimeError("failed to add wire-hole centerline location note")
    # The derived detail exposes no model edge for the hole. Keep the native
    # size/process callout on the front-view model rim, beside the hole.
    add_native_hole_callout(
        adapter,
        front,
        edge=wire_hole_edge,
        callout_xy=(FRONT_CENTER[0] + 0.028, hole_center_y - 0.006),
        label="pen-rod wire hole",
        process="#47 DRILL",
    )

    # No roughness symbol: the drawn-bar faces pass as received (rule 5).

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
