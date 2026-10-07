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
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from ch_rocker_arm_tl_filing_button_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    REFERENCE_DIMENSIONS,
)
from draw_dt_cone_pivot_post_tl_cap_jaw_button import _move_dimension
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_filing_button"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A O10.2 x 4 washer-like button. Codex rounds 4-5: two diameters in the
# face view cross at the centre, and a bore sized on the edge view ends on
# hidden lines. So the face view keeps only the bore (seen true there), and
# the O.D. moves onto the edge view (rule b) beside the thickness. A section
# cannot host them: the diameters belong to the profile circle, and a moved
# circle diameter does not land in a section (run 20261007T173820652Z).
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
FACE_CENTER = (0.110, 0.180)
EDGE_CENTER = (0.200, 0.180)
ISO_CENTER = (0.310, 0.180)
ISO_NOTE_XY = (0.275, 0.240)
NOTES_XY = (0.020, 0.075)
FACE_KEEP = {
    "DiscDia": (0.165, 0.115),  # donor spot only
    "BoreDia": (0.060, 0.240),
}
EDGE_XY = {"DiscDia": (0.165, 0.180)}
EDGE_KEEP = {
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

    annotations = []
    for annotation in curate_view_dimensions(
        adapter,
        face,
        keep=FACE_KEEP,
        view_label="face view",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    ):
        name = dimension_name(adapter, annotation)
        if name in EDGE_XY:
            annotation = _move_dimension(
                adapter, annotation, edge, EDGE_XY[name], source_view=face
            )
        annotations.append(annotation)
    annotations += curate_view_dimensions(
        adapter,
        edge,
        keep=EDGE_KEEP,
        view_label="edge view",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    if not auto_center_marks(adapter, face, holes=True, size=0.0025):
        raise RuntimeError("failed to add the center mark to the button face view")
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
