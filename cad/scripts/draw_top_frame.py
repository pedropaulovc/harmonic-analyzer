r"""Create the curated machinist drawing for the green-painted top-frame casting.

The SLDPRT remains authoritative.  This recipe supplies only the ring's views,
profile dimensions, datum-controlled bores, and manufacturing notes; every shared sheet/template,
import, curation, and export behavior lives in ``_drawing_common``.

The finished envelope is 446.2 x 276.2 x 47.3 over the corner bosses, with a
428.2 x 262.0 rectangular rail outside profile around the 359.8 x 186.0 clear
window, a 36.5-tall webbed ring band, four Ø52.2 corner bosses bored Ø25.5 to
clamp the columns, a Ø17 gooseneck bore through the east-rail hub, and an
integral crossbar carrying two Ø13.49 hanger-stud holes.  The side-facing
tapped holes (#8-32 side screws and keeper feet, 1/4-20 set screw) stay in
the notes. The sheet runs 1:2; the front elevation drops to 1:4 and the
pictorial isometric to 1:10.

The sheet is split into two columns that never share ink: graphics on the
left (plan on top, front elevation directly beneath it on the same
centreline, pictorial in the bottom corner beside it) and one note column on
the right carrying notes 1-5, notes 6-10 and the inspection block stacked in
reading order between the top border and the title block.

Run with SolidWorks open::

    uv run python cad\scripts\draw_top_frame.py top-frame
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_top_frame import (
    BORE_DIA,
    BOSS_DIA,
    COLUMN_X,
    FRONT_COLUMN_Z,
    SIDE_TAP_DRILL_DIA,
    TOP_SCREW_SEAT_Z,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["top_frame"]
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

SHEET_SCALE = (1.0, 2.0)  # 1:2 whole sheet (446.2 mm envelope over the bosses)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]  # 0.5

# Plan extents including the proud corner bosses (the straight rails alone
# stop at x +/-214.1 / z +/-131.0): x +/-223.1 -> 446.2 and z +/-138.1 ->
# 276.2 envelope; the boss stack is 47.3 tall around the 36.5 rail band.
PLAN_HALF_X = COLUMN_X + BOSS_DIA / 2.0  # 223.1
PLAN_HALF_Z = abs(FRONT_COLUMN_Z) + BOSS_DIA / 2.0  # 138.1


PLAN_HALF_W = PLAN_HALF_X * VIEW_SCALE / 1000.0  # 0.11155 sheet metres
PLAN_HALF_D = PLAN_HALF_Z * VIEW_SCALE / 1000.0  # 0.06905 sheet metres

# The note column starts beyond the plan and its right-side leaders. Dense
# 2 mm lettering keeps the longest prescribed line inside the inner border.
NOTE_COLUMN_X = 0.308
NOTE_CHAR_HEIGHT = 0.002

# Views. The plan defines the outside profile and hole pattern; the front
# elevation establishes the cutting plane through one complete corner stack.
TOP_CENTER = (0.136, 0.178)
FRONT_CENTER = (0.136, 0.085)
SECTION_CENTER = (0.340, 0.090)
ISO_CENTER = (0.052, 0.053)
ISO_SCALE = (1, 10)

TOP_VIEW_NOTE_XY = (0.132, 0.104)
FRONT_VIEW_NOTE_XY = (0.130, 0.070)
SECTION_VIEW_NOTE_XY = (0.305, 0.052)
ISO_VIEW_NOTE_XY = (0.028, 0.033)

# Note column, read top to bottom.
MANUFACTURING_NOTES_XY = (NOTE_COLUMN_X, 0.263)
MANUFACTURING_NOTES_B_XY = (NOTE_COLUMN_X, 0.191)


# Per-view survivors of the marked-dimension import. The section owns the
# recessed cap seat because it is internal in both ordinary orthographic views.
TOP_KEEP = {
    "Width": (TOP_CENTER[0], TOP_CENTER[1] + PLAN_HALF_D + 0.011),
    "Depth": (TOP_CENTER[0] - PLAN_HALF_W - 0.005, TOP_CENTER[1]),
}
SECTION_KEEP = {
    "CapRecessDia": (SECTION_CENTER[0] - 0.040, SECTION_CENTER[1] + 0.020),
    "CapRecessDepth": (SECTION_CENTER[0] + 0.040, SECTION_CENTER[1] + 0.010),
}
DIMENSION_CALLOUTS = {
    "CapRecessDia": "4X CAP SKIRT RECESS; FIT MHA-133",
    "CapRecessDepth": "CAP MOUTH CLEARANCE; CAP SEATS ON TUBE END",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open top-frame source", await adapter.open_model(str(SOURCE)))
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
            "Manufacturing Notes B",
            "Top View Note",
            "Front View Note",
            "Section View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Manufacturing Notes B",
            "Top View Note",
            "Front View Note",
            "Section View Note",
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
            0: "Top Frame Ring Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "top frame; webbed gray iron ring casting; column bores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceInteger(542, 0, 1):
        raise RuntimeError("failed to set end-only section cutting line")
    if extension.GetUserPreferenceInteger(542, 0) != 1:
        raise RuntimeError("section cutting-line style did not persist")

    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 4))
    cut_x = model_point_in_view(
        adapter,
        front,
        (COLUMN_X / 1000.0, 0.0, 0.0),
        label="top-frame corner-section axis",
    )[0]
    section = create_section_view(
        adapter,
        front,
        line_start=(cut_x, FRONT_CENTER[1] - 0.030),
        line_end=(cut_x, FRONT_CENTER[1] + 0.030),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(1, 4),
        label="top-frame corner section",
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (top, front):
        set_hidden_lines_visible(adapter, view)
    for view in (section, iso):
        set_hidden_lines_removed(adapter, view)

    top_dimensions = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    section_dimensions = curate_view_dimensions(
        adapter, section, keep=SECTION_KEEP, view_label="section A-A"
    )
    set_dimension_callouts(
        adapter, [*top_dimensions, *section_dimensions], DIMENSION_CALLOUTS
    )
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError(
            "failed to add ASME center marks to the ring bores and stud holes"
        )

    tap_edge = model_point_in_view(
        adapter,
        section,
        (
            COLUMN_X / 1000.0,
            SIDE_TAP_DRILL_DIA / 2000.0,
            (-TOP_SCREW_SEAT_Z + BORE_DIA) / 1000.0,
        ),
        label="top-frame cross-tap longitudinal edge",
    )
    add_native_hole_callout(
        adapter,
        section,
        edge_xy=tap_edge,
        callout_xy=(SECTION_CENTER[0] + 0.045, SECTION_CENTER[1] - 0.025),
        label="4X upper column-retention bottoming taps",
    )

    add_property_linked_note(
        adapter,
        "Manufacturing Notes",
        *MANUFACTURING_NOTES_XY,
        char_height=NOTE_CHAR_HEIGHT,
    )
    add_property_linked_note(
        adapter,
        "Manufacturing Notes B",
        *MANUFACTURING_NOTES_B_XY,
        char_height=NOTE_CHAR_HEIGHT,
    )
    add_property_linked_note(adapter, "Top View Note", *TOP_VIEW_NOTE_XY)
    add_property_linked_note(adapter, "Front View Note", *FRONT_VIEW_NOTE_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_VIEW_NOTE_XY)
    add_property_linked_note(adapter, "Section View Note", *SECTION_VIEW_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Top Frame Ring Manufacturing Drawing",
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
