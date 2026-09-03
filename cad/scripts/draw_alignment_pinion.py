r"""Create the curated manufacturing drawing for the alignment pinion drum (42T).

Follows the batch gear-drawing pattern (see ``draw_cylinder_gear``), adapted for
a long drum: the *Front end view is the parent of DETAIL B (3:1), which carries
the bore callout so its leader lands unmistakably on the 8 mm bore rather than
on the 22 mm tooth ring, and of SECTION A-A (cut face only, through the axis),
which shows the bore along the whole 143 mm drum and carries the face length --
42 teeth projected edge-on over 143 mm were a black band. Drawn 1:1; no
isometric (a long thin drum is fully described by the end view and the
section).

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
gear is not on the GD&T allowlist and this drum is pressed onto its arbor, so
it carries no datums, no feature-control frames and no roughness symbols --
the title block's general tolerances govern everything but the reamed bore,
whose press band rides the model dimension.
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
    create_detail_view,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import show_only_cut_face
from alignment_pinion_spec import BORE_CALLOUT, FACE_WIDTH, OUTSIDE_DIA
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["alignment_pinion"]
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
VIEW_SCALE = (1, 1)
FRONT_CENTER = (0.150, 0.185)  # toothed end view (parent of A-A and B)

# SECTION A-A: vertical cut through the axis, cut face only, in the long drum
# profile's place; a plain adjacent note states the 143.2 face length without
# relying on an imported edge dimension.
SECTION_HALF_LINE = OUTSIDE_DIA / 2000.0 + 0.008
SECTION_LINE = (
    (FRONT_CENTER[0], FRONT_CENTER[1] - SECTION_HALF_LINE),
    (FRONT_CENTER[0], FRONT_CENTER[1] + SECTION_HALF_LINE),
)
SECTION_CENTER = (0.245, 0.205)
SECTION_NOTE = f"SECTION A-A\nFACE LENGTH {FACE_WIDTH:.1f}"
SECTION_NOTE_XY = (
    SECTION_CENTER[0],
    SECTION_CENTER[1] + OUTSIDE_DIA / 2000.0 + 0.012,
)

# DETAIL B (3:1): the whole 22 mm end view, enlarged below-right of the
# section.  The shifted section leaves room for the complete detail and its
# generated two-line caption above the title-block field.
DETAIL_RADIUS = OUTSIDE_DIA / 2000.0 + 0.0015
DETAIL_CENTER = (0.360, 0.140)
DETAIL_SCALE = (3, 1)
DETAIL_KEEP = {
    "ArborBoreDia": (DETAIL_CENTER[0] - 0.064, DETAIL_CENTER[1] - 0.020),
}
# Light press under the arbor's Ø8 journal; the 7.96..7.98 band is on the
# model dimension (build_alignment_pinion), so the callout names the process
# and the fit instruction, and three decimals say "hold it".
DIMENSION_CALLOUTS = {"ArborBoreDia": BORE_CALLOUT}
DIMENSION_PRECISION = {"ArborBoreDia": 3}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open alignment-pinion source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
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
            0: "Alignment Pinion Drum Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "alignment pinion; brass drum; 42T; zeroing drive",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    # Hidden lines stay ON in the orthographic view (policy rule 7).
    set_hidden_lines_visible(adapter, front)

    # DETAIL B claims the bore (draw_pinion_arbor: the detail is curated and
    # the end view is never asked, so no other view can consume the mark).
    detail = create_detail_view(
        adapter,
        front,
        center=FRONT_CENTER,
        radius=DETAIL_RADIUS,
        view_xy=DETAIL_CENTER,
        detail_label="B",
        scale=DETAIL_SCALE,
        label="end view detail",
    )
    detail_annotations = curate_view_dimensions(
        adapter, detail, keep=DETAIL_KEEP, view_label="detail"
    )
    set_dimension_callouts(adapter, detail_annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, detail_annotations, DIMENSION_PRECISION)
    # The end view is never asked for model items (the pinion_arbor
    # precedent): it carries only its centre mark and the A-A / B marks.
    for view, label in ((front, "drum bore"), (detail, "detail bore")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center mark to {label}")

    section = create_section_view(
        adapter,
        front,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="drum",
    )
    show_only_cut_face(adapter, section, label="drum")
    if add_note(adapter, SECTION_NOTE, *SECTION_NOTE_XY) is None:
        raise RuntimeError("failed to add alignment-pinion section geometry note")

    add_property_linked_note(adapter, "Gear Data", 0.018, 0.262)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.018, 0.085)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Alignment Pinion Drum Manufacturing Drawing",
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
