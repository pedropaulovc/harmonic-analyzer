r"""Create the simplicity-policy drawing for the 42T alignment-pinion drum.

The end view owns the tooth-tip envelope and matched arbor bore.  The aligned
profile owns the full tooth-face width, and the standard isometric supplies
pictorial clarity without replacing either manufacturing view.
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
    add_surface_finish,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _surface_finish import surface_finish_by_key
from alignment_pinion_spec import (
    ARBOR_DIAMETRAL_INTERFERENCE_MM,
    BORE_DIA,
    DRAWING_PRECISION_BY_NAME,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
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
FRONT_SCALE = (2, 1)
PROFILE_SCALE = (1, 1)
ISO_SCALE = (1, 2)
FRONT_CENTER = (0.150, 0.165)
RIGHT_CENTER = (0.285, 0.165)
ISO_CENTER = (0.350, 0.215)
GEAR_DATA_POS = (0.018, 0.262)
ISOMETRIC_NOTE_POS = (0.330, 0.262)
MANUFACTURING_NOTES_POS = (0.018, 0.095)


FRONT_KEEP = {
    "ArborBoreDia": (0.085, 0.155),
    "OutsideDia": (0.150, 0.210),
}
RIGHT_KEEP = {
    "FaceWidth": (RIGHT_CENTER[0], 0.125),
}
MIN_INTERFERENCE, MAX_INTERFERENCE = ARBOR_DIAMETRAL_INTERFERENCE_MM
BORE_CALLOUT = (
    "THRU; BORE LIMITS AND MATCHED FIT BOTH APPLY\n"
    "MATCH TO MEASURED MHA-102 PINION ARBOR\n"
    f"{MIN_INTERFERENCE:.3f}-{MAX_INTERFERENCE:.3f} "
    "DIAMETRAL INTERFERENCE"
)
DIMENSION_CALLOUTS = {
    "ArborBoreDia": BORE_CALLOUT,
    "FaceWidth": "FULL TOOTH FACE",
}


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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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

    front = place_view(
        adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=FRONT_SCALE
    )
    right = place_view(
        adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=PROFILE_SCALE
    )
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE
    )
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="toothed end"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="full tooth face"
    )
    annotations = [*front_annotations, *right_annotations]
    set_dimension_callouts(
        adapter, front_annotations, {"ArborBoreDia": BORE_CALLOUT}, location="above"
    )
    set_dimension_callouts(
        adapter, right_annotations, {"FaceWidth": "FULL TOOTH FACE"}
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to drum bore")
    bore_edge = visible_circle_edge(adapter, front, BORE_DIA)

    add_surface_finish(
        adapter,
        front,
        symbol_xy=(0.190, 0.135),
        control=surface_finish_by_key(SURFACE_FINISHES, "drum_bore"),
        label="drum bore finish",
        entity=bore_edge,
        leader_attach_xy=(
            FRONT_CENTER[0],
            FRONT_CENTER[1] - BORE_DIA * FRONT_SCALE[0] / FRONT_SCALE[1] / 2000.0,
        ),
        char_height=0.0025,
    )

    add_property_linked_note(adapter, "Gear Data", *GEAR_DATA_POS, char_height=0.0025)
    add_property_linked_note(
        adapter,
        "Isometric View Note",
        *ISOMETRIC_NOTE_POS,
        char_height=0.0025,
    )
    add_property_linked_note(
        adapter,
        "Manufacturing Notes",
        *MANUFACTURING_NOTES_POS,
        char_height=0.0025,
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Alignment Pinion Drum Manufacturing Drawing",
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
