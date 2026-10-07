r"""Create the drawing for the rocker arm hub filing button (MHA-CH-006-TL-04)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    create_section_view,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from ch_rocker_arm_tl_filing_button_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    REFERENCE_DIMENSIONS,
)
from draw_dt_cone_pivot_post_tl_cap_jaw_button import _move_dimension
from solidworks_mcp.adapters.solidworks.drawing import (
    delete_view,
    iter_views,
    place_view,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_filing_button"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A O10.2 x 4 washer-like button. Rule (b) plus codex round 5 (the bore
# must not be dimensioned on hidden edges): the face view stays as the
# parent of a full section A-A through the axis, and every size moves onto
# that section -- the diameters donated by the face view, the thickness by
# an edge view that is then deleted. O.D. left, bore right, thickness above,
# so no two dimension lines meet.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
FACE_CENTER = (0.110, 0.180)
EDGE_CENTER = (0.200, 0.080)
SECTION_CENTER = (0.200, 0.180)
SECTION_LINE = ((0.110, 0.212), (0.110, 0.148))
ISO_CENTER = (0.310, 0.180)
ISO_NOTE_XY = (0.275, 0.240)
NOTES_XY = (0.020, 0.075)
FACE_KEEP = {
    "DiscDia": (0.060, 0.240),
    "BoreDia": (0.165, 0.115),
}
EDGE_KEEP = {
    "DiscThick": (0.200, 0.120),
}
SECTION_XY = {
    "DiscDia": (0.165, 0.180),
    "BoreDia": (0.235, 0.180),
    "DiscThick": (0.200, 0.235),
}

async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open filing-button source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Arm Hub Filing Button Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm hub filing button; hardened lapped O1; MHA-CH-006-TL-04",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    face = place_view(adapter, str(SOURCE), "*Front", *FACE_CENTER, scale=VIEW_SCALE)
    edge = place_view(adapter, str(SOURCE), "*Right", *EDGE_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (face, edge):
        set_hidden_lines_removed(adapter, view)
    section = create_section_view(
        adapter,
        face,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="filing button axial section",
    )

    donors = (
        (face, FACE_KEEP, "face view"),
        (edge, EDGE_KEEP, "thickness donor"),
    )
    annotations = []
    for donor, keep, donor_label in donors:
        for annotation in curate_view_dimensions(
            adapter,
            donor,
            keep=keep,
            view_label=donor_label,
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ):
            annotations.append(
                _move_dimension(
                    adapter,
                    annotation,
                    section,
                    SECTION_XY[dimension_name(adapter, annotation)],
                    source_view=donor,
                )
            )
    edge_name = view_name(adapter, edge)
    delete_view(adapter, edge)
    if any(view_name(adapter, view) == edge_name for view in iter_views(adapter)):
        raise RuntimeError("failed to delete the empty thickness donor view")
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one filing-button {name} reference dimension")
        set_reference_dimension(adapter, matches[0], label=f"filing button {name}")
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Hub Filing Button Drawing",
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
