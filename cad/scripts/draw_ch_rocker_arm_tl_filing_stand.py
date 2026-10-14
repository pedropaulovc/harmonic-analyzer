r"""Create the drawing for the rocker arm filing stand (MHA-CH-006-TL-12).

The loose set at its S5 stations: a plan (``*Front``, looking down on the
bench) carries the block outline and the pedestal diameter, and the elevation
(``*Bottom``, third-angle below it, +Z up) the block height and the pedestal's
reference length with its step over the blocks.
"""

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
import ch_rocker_arm_tl_filing_stand_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_filing_stand_spec import (
    BLOCK_COUNT_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PEDESTAL_DIA_CALLOUT,
    PEDESTAL_LENGTH_CALLOUT,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_filing_stand"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# The set spans the 336 blank: 1:2 fits it across the sheet with both views
# stacked left of the isometric.
SHEET_SCALE = (1.0, 2.0)
VIEW_SCALE = (1, 2)
# Plan: blocks at sheet x 0.066-0.076 and 0.224-0.234, y 0.2055-0.2245.
PLAN_CENTER = (0.150, 0.215)
# Elevation: bench line at y 0.1424, block tops 0.1574.
ELEVATION_CENTER = (0.150, 0.150)
ISO_CENTER = (0.340, 0.185)
ISO_SCALE = (1, 4)
ISO_NOTE_XY = (0.300, 0.235)
PLAN_KEEP = {
    # The left block carries the 2X outline sizes.
    "BlockLength": (0.071, 0.236),
    "BlockWidth": (0.045, 0.215),
    "PedestalDia": (0.185, 0.245),
}
ELEVATION_KEEP = {
    "BlockHeight": (0.045, 0.150),
    # Right of the pedestal, in the open middle; the step callout below it.
    "PedestalLength": (0.175, 0.153),
}
CALLOUTS_ABOVE = {
    "BlockLength": BLOCK_COUNT_CALLOUT,
    "BlockWidth": BLOCK_COUNT_CALLOUT,
    "BlockHeight": BLOCK_COUNT_CALLOUT,
}
CALLOUTS_BELOW = {
    "PedestalLength": PEDESTAL_LENGTH_CALLOUT,
    "PedestalDia": PEDESTAL_DIA_CALLOUT,
}


part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME",))

for side, centre_x in (
    ("left", -part_spec.BLOCK_OUTER_X + part_spec.BLOCK_LENGTH / 2.0),
    ("right", part_spec.BLOCK_OUTER_X - part_spec.BLOCK_LENGTH / 2.0),
):
    requirement(
        f"{side}_end_block_top",
        kind="face",
        faces=(
            PlanarFace((0.0, 0.0, 1.0), part_spec.BLOCK_HEIGHT, contains_x_mm=centre_x),
        ),
        requirements=("height", "length", "width"),
        fields={
            "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
            "plane": (
                {"frame": "model", "axis": "z", "value": part_spec.BLOCK_HEIGHT},
                ("BLOCK_HEIGHT",),
            ),
            "height": (limits(part_spec.BLOCK_HEIGHT, 1), ("BLOCK_HEIGHT",)),
            "height_nominal": (part_spec.BLOCK_HEIGHT, ("BLOCK_HEIGHT",)),
            "length": (
                limits(part_spec.BLOCK_LENGTH, 1),
                ("BLOCK_LENGTH", "BLOCK_OUTER_X", ("ch_rocker_arm_spec", "ROD_TIP_X")),
            ),
            "length_nominal": (part_spec.BLOCK_LENGTH, ("BLOCK_LENGTH",)),
            "width": (limits(part_spec.BLOCK_WIDTH, 1), ("BLOCK_WIDTH",)),
            "width_nominal": (part_spec.BLOCK_WIDTH, ("BLOCK_WIDTH",)),
        },
        precision={"height": 1, "length": 1, "width": 1},
    )

requirement(
    "pedestal_top",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.PEDESTAL_LENGTH),),
    requirements=("height", "dia"),
    fields={
        "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.PEDESTAL_LENGTH},
            ("PEDESTAL_LENGTH",),
        ),
        # The held size: the pedestal top's height over the end-block tops.
        "height": (
            limits(part_spec.STEP, 2, part_spec.STEP_BAND),
            (
                "STEP",
                "STEP_BAND",
                ("ch_rocker_arm_spec", "HUB_LENGTH"),
                ("ch_rocker_arm_spec", "HUB_LENGTH_BAND"),
            ),
        ),
        "height_nominal": (part_spec.STEP, ("STEP", "RAW_THICKNESS")),
        "height_from": (
            "end_block_tops",
            (("draw_ch_rocker_arm_tl_filing_stand", "build"),),
        ),
        "length_ref": (part_spec.PEDESTAL_LENGTH, ("PEDESTAL_LENGTH",)),
        "dia": (
            limits(part_spec.PEDESTAL_DIA, 2),
            ("PEDESTAL_DIA", ("ch_rocker_arm_spec", "HUB_DIA_MIN")),
        ),
        "dia_nominal": (part_spec.PEDESTAL_DIA, ("PEDESTAL_DIA",)),
    },
    precision={"height": 2, "dia": 2},
)


def _one(adapter: Any, annotations: list[Any], name: str) -> Any:
    matches = [a for a in annotations if dimension_name(adapter, a) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
    return matches[0]


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open filing-stand source", await adapter.open_model(str(SOURCE)))
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
            0: "Rocker Arm Filing Stand Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm S5 filing stand; two end blocks and a hub pedestal; MHA-CH-006-TL-12",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=VIEW_SCALE)
    elevation = place_view(
        adapter, str(SOURCE), "*Bottom", *ELEVATION_CENTER, scale=VIEW_SCALE
    )
    # finalize_drawing shades the pictorial isometric with edges; set it HLR
    # first so the shading is applied to a precision view, not the default.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (plan, elevation, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            plan,
            keep=PLAN_KEEP,
            view_label="plan",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            elevation,
            keep=ELEVATION_KEEP,
            view_label="elevation",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # The pedestal length is reference: its step over the blocks governs.
    set_reference_dimension(
        adapter,
        _one(adapter, annotations, "PedestalLength"),
        label="filing-stand PedestalLength",
    )
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Filing Stand Drawing",
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
