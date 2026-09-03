r"""Create the curated machinist drawing for the lever-bank spacer bushing.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
stationary spacer on the fulcrum shaft carries no datums, no feature-control
frames and no roughness symbols -- the reamed bore keeps its fit band on the
model dimension and the callout says REAM.

The side view is SECTION A-A, cut through the end view's centre, so the OD,
the bore and the length all read on one longitudinal view with the bore as
visible (hatched) geometry -- a turned part dimensioned as it sits in the
lathe (policy rule 7). The end view carries the cutting line and its centre
marks and nothing else (machinist review 2026-09-02: both diameters were
leader-piled on the end view and the bore leader crossed the OD dimension).
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
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from lever_bushing_spec import LENGTH, OUTER_DIA
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["lever_bushing"]
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
END_CENTER = (0.080, 0.205)
END_RADIUS = OUTER_DIA * SHEET_SCALE[0] / 2000.0  # 24 mm on the sheet
SECTION_CENTER = (
    END_CENTER[0] + (OUTER_DIA + LENGTH) * SHEET_SCALE[0] / 1000.0 + 0.045,
    END_CENTER[1],
)
ISO_CENTER = (0.315, 0.205)
# The cutting line runs vertically through the end view's centre, 8 mm past
# the OD each way, so the section shows the axis horizontal (the cut-line
# direction stays vertical in the section; the bushing axis is its depth).
SECTION_LINE = (
    (END_CENTER[0], END_CENTER[1] + END_RADIUS + 0.008),
    (END_CENTER[0], END_CENTER[1] - END_RADIUS - 0.008),
)

# Every marked dimension reads on the section, as offsets from the section's
# projected geometry centre (the bushing is origin-centred): OD as a linear
# diameter to the right, the reamed bore as a linear diameter to the left
# (its two-line REAM callout has 40 mm of clear sheet before the end view),
# the length above. The end view keeps nothing -- SolidWorks inserts each
# marked model dimension into ONE view, so the section is curated and the
# end view is never asked (draw_pinion_bracket, 2026-09-02 seat build).
END_KEEP: dict[str, tuple[float, float]] = {}
SECTION_KEEP_OFFSETS = {
    "OuterDia": (0.032, 0.0),
    "BoreDia": (-0.032, 0.0),
    "Depth": (0.0, END_RADIUS + 0.012),
}
# Bore and length tolerances live on the source model; the bore callout
# carries the process (Harvey #13: say drill or ream).
DIMENSION_CALLOUTS: dict[str, str] = {"BoreDia": "REAM THRU"}
# The reamed bore is the one fitted feature (band on the model dimension):
# three decimals say "hold it"; everything else stays at the two-place block
# tolerance.
DIMENSION_PRECISION = {"BoreDia": 3}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open lever-bushing source", await adapter.open_model(str(SOURCE)))
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
            0: "Lever Bushing Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "lever bushing; turned spacer; brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(4, 1))
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
        scale=(4, 1),
        label="bushing axial section",
    )
    # Hidden lines stay ON in every orthographic view (Harvey #30 / Lipton).
    for view in (end, section):
        set_hidden_lines_visible(adapter, view)

    # The section's mirror is SolidWorks' choice, so the dimension positions
    # are laid out from the PROJECTED model origin (the bushing's centre), not
    # from the requested view position.
    centre = model_point_in_view(
        adapter, section, (0.0, 0.0, 0.0), label="section centre"
    )
    section_keep = {
        name: (centre[0] + dx, centre[1] + dy)
        for name, (dx, dy) in SECTION_KEEP_OFFSETS.items()
    }
    section_annotations = curate_view_dimensions(
        adapter, section, keep=section_keep, view_label="section"
    )
    set_dimension_callouts(adapter, section_annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, section_annotations, DIMENSION_PRECISION)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to end view")

    # x=0.020: the anchor is the text's left edge, so the ink starts here,
    # clear of the 12.7 mm zone margin the audit enforces.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.095)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Lever Bushing Manufacturing Drawing",
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
