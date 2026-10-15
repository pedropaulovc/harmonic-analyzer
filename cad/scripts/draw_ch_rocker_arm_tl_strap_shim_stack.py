r"""Create the drawing for the rocker arm's strap shim stack (MHA-CH-006-TL-11)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

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
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_strap_shim_stack_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_strap_shim_stack_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    REFERENCE_DIMENSIONS,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_strap_shim_stack"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 20 x 12 x 2.7 stack: 4:1 keeps the shim pack's edge legible.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
# The footprint (looking down on the bearing face) carries length and width;
# the edge view below it (third angle) the piece and the pack; the shaded
# isometric to the right.
FACE_CENTER = (0.130, 0.185)
EDGE_CENTER = (0.130, 0.105)
ISO_CENTER = (0.310, 0.175)
ISO_NOTE_XY = (0.275, 0.235)
FACE_KEEP = {
    "StackLength": (0.130, 0.228),
    # Far enough left that the callout clears the length's extension line.
    "StackWidth": (0.050, 0.185),
}
# Neither thickness fits its text between its extension lines: the piece's
# text sits above the view's top extension line (callout above, so the
# dimension line meets the value first), the pack's below the bottom one,
# in line with it. Both sit right of the view: outside text runs away from the
# view along its shelf, and on the left the pack's callout left the sheet.
EDGE_KEEP = {
    "StripThick": (0.200, 0.122),
    "ShimThick": (0.200, 0.088),
}
CALLOUTS_ABOVE = {"StripThick": "FLAT STOCK AS SUPPLIED"}
CALLOUTS_BELOW = {
    "StackWidth": "UNDER THE ARM STRAP",
    # The mate and the fit-up acceptance as a GO/NO-GO pair: the pack is
    # chosen at setup until the stack bears on the rocker blank's strap face,
    # but no higher: with the strap snug the raw blank ends still bear on the
    # riser blocks, so an over-height pack cannot bow the span.
    "ShimThick": (
        "SHIM AT SETUP TO BEAR ON MHA-CH-006 STRAP FACE: "
        f"{part_spec.FIT_UP_FEELER_NO_GO:.2f} FEELER NO-GO\n"
        "BLANK ENDS ON MHA-CH-006-TL-10: "
        f"{part_spec.FIT_UP_FEELER_NO_GO:.2f} FEELER NO-GO"
    ),
}


part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME",))

requirement(
    "work_seat",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.STACK_HEIGHT),),
    requirements=("length", "width"),
    fields={
        "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.STACK_HEIGHT},
            ("STACK_HEIGHT",),
        ),
        "height_nominal": (part_spec.STACK_HEIGHT, ("STACK_HEIGHT",)),
        "length": (limits(part_spec.STACK_LENGTH, 1), ("STACK_LENGTH",)),
        "length_nominal": (part_spec.STACK_LENGTH, ("STACK_LENGTH",)),
        "width": (limits(part_spec.STACK_WIDTH, 1), ("STACK_WIDTH", "S4_STATIONS")),
        "width_nominal": (part_spec.STACK_WIDTH, ("STACK_WIDTH",)),
    },
    precision={"length": 1, "width": 1},
)

requirement(
    "riser_seat",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("length", "width"),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "length": (limits(part_spec.STACK_LENGTH, 1), ("STACK_LENGTH",)),
        "width": (limits(part_spec.STACK_WIDTH, 1), ("STACK_WIDTH",)),
    },
    precision={"length": 1, "width": 1},
)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open strap shim stack source", await adapter.open_model(str(SOURCE)))
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
            0: "Rocker Strap Shim Stack Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker strap shim stack; O1 flat on steel shim; MHA-CH-006-TL-11",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    face = place_view(adapter, str(SOURCE), "*Front", *FACE_CENTER, scale=VIEW_SCALE)
    edge = place_view(adapter, str(SOURCE), "*Bottom", *EDGE_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (face, edge, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            face,
            keep=FACE_KEEP,
            view_label="bearing face",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            edge,
            keep=EDGE_KEEP,
            view_label="edge view",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # Both thicknesses are LINEAR references (the plural helper forces a Ø).
    for name in REFERENCE_DIMENSIONS:
        matches = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(
                f"expected one strap shim stack {name} reference dimension"
            )
        set_reference_dimension(adapter, matches[0], label=f"strap shim stack {name}")
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW, location="below")
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Strap Shim Stack Drawing",
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
