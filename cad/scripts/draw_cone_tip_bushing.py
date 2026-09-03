r"""Create the curated machinist drawing for the cone-tip spacer bushing.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): no
datums, no feature-control frames, no bands and no roughness symbol -- the
drilled bore says DRILL on the callout and the title block's DRILLED HOLES
row governs it; the length is at the block's .XX (machinist review
2026-09-02: an axial spacer in an adjuster-screw take-up stack).

The side view is SECTION A-A, cut through the end view's centre, so the OD,
the bore and the length all read on one longitudinal view with the axis
horizontal and the bore as visible (hatched) geometry -- a turned part
dimensioned as it sits in the lathe (policy rule 7). The end view carries the
cutting line and its centre marks and nothing else (the review found the OD
dimension crowding the tiny bore's leaders on the end view).
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
    create_section_view,
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
from cone_tip_bushing_spec import BORE_DIA, LENGTH, OUTER_DIA
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cone_tip_bushing"]
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

# O6 x 4 is tiny: 8:1 puts the end-view circle at O48 on the sheet, matching
# the lever-bushing print's read (O12 at 4:1). The part is extruded from the
# Top plane (axis along Y), so the circular end view is *Top; the section cut
# vertically through it shows the axis horizontal.
SHEET_SCALE = (8.0, 1.0)
END_CENTER = (0.085, 0.190)
END_RADIUS = OUTER_DIA * SHEET_SCALE[0] / 2000.0  # 24 mm on the sheet
SECTION_CENTER = (0.200, 0.190)
ISO_CENTER = (0.315, 0.205)
# The cutting line runs vertically through the end view's centre, 8 mm past
# the OD each way, so the section shows the axis horizontal (the cut-line
# direction stays vertical in the section; the bushing axis is its depth).
SECTION_LINE = (
    (END_CENTER[0], END_CENTER[1] + END_RADIUS + 0.008),
    (END_CENTER[0], END_CENTER[1] - END_RADIUS - 0.008),
)

# Every marked dimension reads on the section, as offsets from the section's
# projected geometry centre (the sleeve runs y 0..LENGTH, so the centre is
# mid-length on the axis): OD as a linear diameter to the right, the drilled
# bore as a linear diameter to the left (its two-line DRILL callout has ~30
# mm of clear sheet before the end view), the length above. The end view
# keeps nothing -- SolidWorks inserts each marked model dimension into ONE
# view, so the section is curated and the end view is never asked
# (draw_pinion_bracket, 2026-09-02 seat build).
END_KEEP: dict[str, tuple[float, float]] = {}
SECTION_KEEP_OFFSETS = {
    "ODDim": (0.036, 0.0),
    "BoreDiaDim": (-0.036, 0.0),
    "Depth": (0.0, END_RADIUS + 0.012),
}
# The bore callout carries the process (Harvey #13: say drill or ream); the
# title block's DRILLED HOLES row governs its size, so it prints the block's
# two decimals like every other dimension.
DIMENSION_CALLOUTS = {
    "BoreDiaDim": "DRILL THRU (1/32 IN)",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-tip-bushing source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Tip Bushing Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone tip bushing; turned spacer; brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Top", *END_CENTER, scale=(8, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(8, 1))
    set_hidden_lines_removed(adapter, iso)
    # SECTION A-A through the bushing axis: the bore becomes visible geometry,
    # so no diameter is dimensioned to a hidden line (policy rule 7).
    section = create_section_view(
        adapter,
        end,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(8, 1),
        label="bushing axial section",
    )
    # Hidden lines stay ON in every orthographic view (Harvey #30 / Lipton).
    for view in (end, section):
        set_hidden_lines_visible(adapter, view)

    # The section's mirror is SolidWorks' choice, so the dimension positions
    # are laid out from the PROJECTED mid-length axis point, not from the
    # requested view position.
    centre = model_point_in_view(
        adapter, section, (0.0, LENGTH / 2000.0, 0.0), label="section centre"
    )
    section_keep = {
        name: (centre[0] + dx, centre[1] + dy)
        for name, (dx, dy) in SECTION_KEEP_OFFSETS.items()
    }
    section_annotations = curate_view_dimensions(
        adapter, section, keep=section_keep, view_label="section"
    )
    set_dimension_callouts(adapter, section_annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to end view")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.022, 0.095)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Bushing Manufacturing Drawing",
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
