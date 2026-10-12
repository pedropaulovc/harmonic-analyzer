r"""Create the curated machinist drawing for the crank handle.

A turned, ebonized oak pear grip (book ch. 11).  User ruling 2026-09-29: the
brass ferrule MHA-DT-034 and the steel butt cup MHA-DT-035 are separate parts, so
this sheet prints only the oak -- a tenon for the ferrule at the crank end, a
flared waist, an S-curve swell to the Ø21 max, and a domed butt whose end
round crests on a flat oak end flush with the cup bonded into its
counterbore (user rulings 2026-09-30, concept v4; turned clear of the cup
after the local review of fbf82ad96).

After the MHA-DT-008 machinist review (user ruling 2026-09-29) the sheet is plain:
no datums, feature-control frames or basic dimensions -- the grip is turned to
its arcs within a contour allowance stated in the note.  The longitudinal
section A-A, taken on the end view's vertical centre line, is the handle's
length view (drawing-guidelines.md rule 11 (turned parts read like the lathe)): it shows the counterbore step on cut edges and
carries every profile dimension, since the profile sketches on the Front plane
the section lies in.  The end view stands on the section's axis and carries the
reamed bore.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_crank_handle.py dt-crank-handle
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _section_axis import create_section_axis_centerline, position_section_caption
from _session import run_build
import _telemetry
from dt_crank_handle_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HANDLE_MAX_DIA,
    OAK_END_X,
    REFERENCE_DIMENSIONS,
    SHOULDER_X,
    TENON_DIA,
    TENON_X0,
)


SPEC = DRAWINGS_BY_NAME["dt_crank_handle"]
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

SHEET_SCALE = (2.0, 1.0)

# The section lays the handle axis horizontal, tenon at the left and butt at
# the right (the part's +X to the right, as MHA-DT-035's section showed), centred
# on the oak's extent.  The end view stands on the same axis height.
FRONT_BBOX_CX = (TENON_X0 + OAK_END_X) / 2.0
FRONT_CENTER = (0.150, 0.178)
RIGHT_CENTER = (0.300, FRONT_CENTER[1])
ISO_CENTER = (0.365, 0.240)
CAPTION_XY = (0.215, 0.114)

TENON_R = TENON_DIA / 2.0
END_R = HANDLE_MAX_DIA * SHEET_SCALE[0] / 2000.0


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + (model_x_mm - FRONT_BBOX_CX) * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + model_y_mm * SHEET_SCALE[0] / 1000.0


FRONT_KEEP = {
    # The oak overall from the tenon end face, the one faced end.
    "OverallLength": (0.150, 0.128),
    "TenonLength": (_front_x((TENON_X0 + SHOULDER_X) / 2.0), 0.212),
    "TenonDia": (0.068, 0.178),
    "PeakStation": (0.150, 0.242),
    "CounterboreDepth": (0.202, 0.222),
    "CounterboreDia": (0.232, 0.178),
}
RIGHT_KEEP = {
    "PivotBoreDia": (0.362, 0.165),
}
# Every band renders from its model dimension; the callout retains only
# process intent.
DIMENSION_CALLOUTS = {
    "PivotBoreDia": "THRU - REAM",
}
CUT_START = (RIGHT_CENTER[0], RIGHT_CENTER[1] - END_R - 0.006)
CUT_END = (RIGHT_CENTER[0], RIGHT_CENTER[1] + END_R + 0.006)
async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-handle source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Handle Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank handle; turned oak pear grip; ferrule tenon and cup counterbore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    front = create_section_view(
        adapter,
        right,
        line_start=CUT_START,
        line_end=CUT_END,
        view_xy=FRONT_CENTER,
        section_label="A",
        scale=(2, 1),
        label="crank handle longitudinal section",
    )
    position_section_caption(adapter, front, CAPTION_XY, label="crank handle")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)
    front.SetDisplayTangentEdges2(0)
    if int(front.GetDisplayTangentEdges2()) != 0:
        raise RuntimeError("failed to hide crank-handle tangent edges")
    front.UpdateViewDisplayGeometry()

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="longitudinal section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    imported = [*front_annotations, *right_annotations]
    set_dimension_callouts(adapter, imported, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, imported, DRAWING_PRECISION_BY_NAME)
    front_by_name = {dimension_name(adapter, a): a for a in front_annotations}
    # The tenon and the counterbore are fitted to the ferrule and cup (the
    # to-suit note), so their sizes print as references.
    for name in sorted(REFERENCE_DIMENSIONS):
        set_reference_dimension(
            adapter,
            front_by_name[name],
            label=f"MHA-DT-008 {name}",
            diameter=name.endswith("Dia"),
        )
    create_section_axis_centerline(
        adapter, front, length_mm=OAK_END_X - TENON_X0, label="crank handle axis"
    )
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to crank-handle end view")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.086)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.205)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Handle Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
