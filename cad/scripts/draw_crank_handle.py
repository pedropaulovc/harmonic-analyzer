r"""Create the curated machinist drawing for the crank handle.

A turned, ebonized oak pear grip (book ch. 11).  User ruling 2026-09-29: the
brass ferrule MHA-150 and the flanged steel butt cup MHA-153 are separate
parts, so this sheet prints only the oak -- a tenon for the ferrule at the
crank end, a waisted neck, a smooth twin-arc swell to the Ø21 max, and a
trimmed butt with a counterbore for the cup.

After the MHA-022 machinist review (user ruling 2026-09-29) the sheet is plain:
no datums, feature-control frames or basic dimensions -- the grip is turned to
its arcs within a contour allowance stated in the note.  The longitudinal
section A-A, taken on the end view's vertical centre line, is the handle's
length view (policy rule 7): it shows the counterbore step on cut edges and
carries every profile dimension, since the profile sketches on the Front plane
the section lies in.  The end view stands on the section's axis and carries the
reamed bore.

Run with SolidWorks open::

    uv run python cad\scripts\draw_crank_handle.py crank-handle
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_property_linked_note,
    assert_imported_precision,
    create_section_view,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _section_axis import create_section_axis_centerline, position_section_caption
from crank_handle_spec import (
    COUNTERBORE_R,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    HANDLE_MAX_DIA,
    PIVOT_BORE_DIA,
    REFERENCE_DIMENSIONS,
    SHOULDER_X,
    TENON_DIA,
    TENON_X0,
    TRIM_R,
    TRIM_X,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["crank_handle"]
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
# the right (the part's +X to the right, as MHA-153's section showed), centred
# on the oak's extent.  The end view stands on the same axis height.
FRONT_BBOX_CX = (TENON_X0 + TRIM_X) / 2.0
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
    "WoodLength": (0.155, 0.128),
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
# The reference overall runs from the tenon's end face to the butt face, each
# picked on its cut edge midway up the wood.
OVERALL_P0 = (_front_x(TENON_X0), _front_y((TENON_R + PIVOT_BORE_DIA / 2.0) / 2.0))
OVERALL_P1 = (_front_x(TRIM_X), _front_y((TRIM_R + COUNTERBORE_R) / 2.0))
OVERALL_TEXT_XY = (0.150, 0.112)


def _set_reference_precision(adapter: Any, display: Any, label: str) -> None:
    """Give the one SHEET-derived dimension its spec-authored decimal places.

    ``SetPrecision3`` reports rejection through its return status rather than
    by raising, so the side effect is read back (the draw_crank_arm pattern).
    """
    places = DRAWING_REFERENCE_PRECISION[label]
    display = _early_bound(display, "IDisplayDimension")
    adapter._attempt(
        lambda: display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    )
    applied = adapter._attempt(display.GetPrimaryPrecision2)
    if applied != places:
        raise RuntimeError(
            f"{label}: sheet dimension prints {applied} decimal places, not {places}"
        )


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
            adapter, front_by_name[name], label=f"MHA-022 {name}", diameter=True
        )
    create_section_axis_centerline(
        adapter, front, length_mm=TRIM_X - TENON_X0, label="crank handle axis"
    )
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to crank-handle end view")

    # Tenon end to butt face, a reference for stock cut-off (MHA-022 review:
    # the 48.7 wood length alone read like an overall).
    overall = add_edge_dimension(
        adapter,
        front,
        p0=OVERALL_P0,
        p1=OVERALL_P1,
        text_xy=OVERALL_TEXT_XY,
        label="overall length reference",
        orientation="horizontal",
    )
    set_reference_dimension(
        adapter,
        _early_bound(overall, "IDisplayDimension").GetAnnotation(),
        label="overall length reference",
    )
    _set_reference_precision(adapter, overall, "overall length reference")

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
