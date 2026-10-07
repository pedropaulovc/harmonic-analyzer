r"""Create the drawing for the rocker arm hub filing stud (MHA-CH-006-TL-05)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_text,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from ch_rocker_arm_tl_filing_stud_spec import (
    DIMENSION_TEXT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    TAIL_END,
    THREAD_END,
)
from draw_dt_cone_pivot_post_tl_cap_jaw_button import _move_dimension
from solidworks_mcp.adapters.solidworks.drawing import delete_view, iter_views, place_view

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_filing_stud"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 69 mm stud: 2:1 keeps the four steps legible on one turned profile.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
# One turned profile (axis horizontal, thread right) carries every size: the
# axial sizes from the seat face, each diameter beside its own step. The end
# view only donates the sketch diameters and is deleted.
PROFILE_CENTER = (0.170, 0.170)
# The view centres on the model box (tail end to thread end).
SEAT_X = PROFILE_CENTER[0] + (TAIL_END - THREAD_END) / 2.0 * _S
DONOR_CENTER = (0.330, 0.100)
ISO_CENTER = (0.330, 0.190)
ISO_NOTE_XY = (0.295, 0.240)
NOTES_XY = (0.020, 0.075)
_ABOVE = PROFILE_CENTER[1] + 0.040
_BELOW = PROFILE_CENTER[1] - 0.040
PROFILE_KEEP = {
    "TailEnd": (SEAT_X - TAIL_END / 2.0 * _S, _ABOVE),
    "ThreadEnd": (SEAT_X + THREAD_END / 2.0 * _S, _ABOVE),
    "HeadLength": (SEAT_X - 0.012, _BELOW),
    "BodyLength": (SEAT_X + 0.016, _BELOW),
}
DONOR_KEEP = {
    "TailDia": (0.300, 0.060),
    "HeadDia": (0.360, 0.060),
    "BodyDia": (0.300, 0.140),
    "ThreadDia": (0.360, 0.140),
}
PROFILE_DIAMETER_XY = {
    "TailDia": (SEAT_X - 0.060, PROFILE_CENTER[1] + 0.022),
    "HeadDia": (SEAT_X - 0.020, PROFILE_CENTER[1] + 0.024),
    "BodyDia": (SEAT_X + 0.008, PROFILE_CENTER[1] + 0.022),
    "ThreadDia": (SEAT_X + 0.062, PROFILE_CENTER[1] + 0.034),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open filing-stud source", await adapter.open_model(str(SOURCE)))
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
            0: "Rocker Arm Hub Filing Stud Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm hub filing stud; turned 4140; MHA-CH-006-TL-05",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    donor = place_view(adapter, str(SOURCE), "*Right", *DONOR_CENTER, scale=VIEW_SCALE)
    profile = place_view(adapter, str(SOURCE), "*Front", *PROFILE_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (donor, profile):
        set_hidden_lines_removed(adapter, view)

    donor_annotations = curate_view_dimensions(
        adapter,
        donor,
        keep=DONOR_KEEP,
        view_label="diameter donor",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="turned profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    diameters = [
        _move_dimension(
            adapter,
            annotation,
            profile,
            PROFILE_DIAMETER_XY[dimension_name(adapter, annotation)],
            source_view=donor,
        )
        for annotation in donor_annotations
    ]
    donor_name = view_name(adapter, donor)
    delete_view(adapter, donor)
    if any(view_name(adapter, view) == donor_name for view in iter_views(adapter)):
        raise RuntimeError("failed to delete the empty diameter donor view")

    annotations = [*diameters, *profile_annotations]
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_text(adapter, annotations, DIMENSION_TEXT)
    add_view_centerline(
        adapter, profile, face_xy=PROFILE_CENTER, label="stud turning axis"
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Hub Filing Stud Drawing",
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
