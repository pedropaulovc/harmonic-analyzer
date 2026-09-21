r"""Create the curated machinist drawing for the gooseneck counter-spring post.

The SLDPRT remains authoritative. Sheet 1 defines the formed tube and post with
an elevation, enlarged post end, and standard isometric. Sheet 2 carries the
longitudinal arm/joint section that exposes the separate brazed plug and captive
slotted screw; every displayed size is imported from the model.

The external calibration envelope stays unchanged: Ø16 tube, R51 bend, 50.80
arm run, 8 mm exposed shank and Ø12 head. The package is explicitly 1:3 at
sheet level, with 2:1 end, 1:1 joint-section and 1:4 isometric overrides.

Run with SolidWorks open::

    uv run python cad\scripts\draw_gooseneck.py gooseneck
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    create_blank_drawing_sheets,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimensions,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import place_view

from gooseneck_geom import ARM_END_X, ARM_Y, BEND_R, SCREW_HEAD_T, SCREW_SHANK_LEN
from gooseneck_spec import (
    DRAWING_PRECISION_BY_NAME,
    ELEVATION_DIMENSIONS,
    END_DIMENSIONS,
    JOINT_DIMENSIONS,
    PLUG_FIT_CALLOUT,
    SCREW_CALLOUT,
    TAP_CALLOUT,
)

SPEC = DRAWINGS_BY_NAME["gooseneck"]
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

SHEET_SCALE = (1.0, 3.0)
SHEET_NAMES = ("FORM + POST", "ARM-END FABRICATION")

# Measured sheet-space layout (metres). Sheet 1 keeps the 493 mm elevation at
# 1:3, enlarges the post end to 2:1, and raises the 1:4 standard isometric above
# its caption. Sheet 2 gives the 112 mm arm/joint section a useful 1:1 scale.
FRONT_CENTER = (0.195, 0.140)
END_CENTER = (0.060, 0.205)
ISO_CENTER = (0.350, 0.195)
JOINT_PARENT_CENTER = (0.345, 0.140)
JOINT_CENTER = (0.140, 0.190)

FRONT_KEEP = {
    "LegLength": (0.145, 0.135),
    "BendRadius": (0.230, 0.205),
    "ArmRun": (0.155, 0.220),
}
END_KEEP = {
    "TubeDia": (0.095, 0.215),
    "TubeBoreDia": (0.095, 0.190),
}
JOINT_KEEP = {
    "PlugDia": (0.100, 0.230),
    "TapMinorDia": (0.100, 0.210),
    "PlugDepth": (0.145, 0.240),
    "ScrewShankDia": (0.205, 0.205),
    "UnderHeadLength": (0.145, 0.165),
    "ScrewHeadDia": (0.070, 0.185),
    "HeadThickness": (0.080, 0.145),
    "SlotDepth": (0.215, 0.235),
    "ExposedShank": (0.155, 0.145),
    "SlotWidth": (0.215, 0.215),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open gooseneck source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
            "Joint View Note",
            "Elevation View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
            "Joint View Note",
            "Elevation View Note",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="gooseneck package")
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Gooseneck Post Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "gooseneck; plated tube; brazed plug; captive spring screw",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    ddoc = _early_bound(drawing_model, "IDrawingDoc")

    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate gooseneck form sheet")
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 3))
    end = place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (front, end):
        set_hidden_lines_removed(adapter, view)
    front_dimensions = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="elevation",
        dimensions_by_feature=ELEVATION_DIMENSIONS,
    )
    end_dimensions = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="post end",
        dimensions_by_feature=END_DIMENSIONS,
    )
    add_property_linked_note(adapter, "End View Note", 0.025, 0.165)
    add_property_linked_note(adapter, "Elevation View Note", 0.160, 0.022)
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.120)

    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate gooseneck fabrication sheet")
    parent = place_view(
        adapter, str(SOURCE), "*Front", *JOINT_PARENT_CENTER, scale=(1, 3)
    )
    set_hidden_lines_removed(adapter, parent)
    screw_tip_x = ARM_END_X - SCREW_SHANK_LEN - SCREW_HEAD_T
    line_start = model_point_in_view(
        adapter,
        parent,
        (screw_tip_x / 1000.0, ARM_Y / 1000.0, 0.0),
        label="joint section screw-head end",
    )
    line_end = model_point_in_view(
        adapter,
        parent,
        (-BEND_R / 1000.0, ARM_Y / 1000.0, 0.0),
        label="joint section bend end",
    )
    joint = create_section_view(
        adapter,
        parent,
        line_start=line_start,
        line_end=line_end,
        view_xy=JOINT_CENTER,
        section_label="A",
        scale=(1, 1),
        partial=True,
        label="arm and brazed end joint",
    )
    set_hidden_lines_removed(adapter, joint)
    joint_dimensions = curate_view_dimensions(
        adapter,
        joint,
        keep=JOINT_KEEP,
        view_label="arm joint section",
        dimensions_by_feature=JOINT_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter,
        joint_dimensions,
        {
            "PlugDia": PLUG_FIT_CALLOUT,
            "TapMinorDia": TAP_CALLOUT,
            "ScrewShankDia": SCREW_CALLOUT,
        },
        location="above",
    )
    set_reference_dimensions(adapter, joint_dimensions, ("PlugDia",))
    add_property_linked_note(adapter, "Joint View Note", 0.080, 0.105)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.245, 0.220)

    assert_imported_precision(
        adapter,
        [*front_dimensions, *end_dimensions, *joint_dimensions],
        DRAWING_PRECISION_BY_NAME,
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Gooseneck Post Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
