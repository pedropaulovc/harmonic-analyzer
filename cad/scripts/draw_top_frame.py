r"""Create the curated machinist drawing for the green-painted top-frame casting.

The SLDPRT remains authoritative.  This recipe supplies only native model
dimensions, associative hole callouts, and the views of the casting; shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.  The top view carries the ring, web, boss, socket, and
crossbar dimensions.  Section A-A carries the recessed cap-seat dimensions and
the cross-tap callout.

The sheet is split into two columns that never share ink: graphics on the left
(plan on top, front elevation beneath it, section beside it, and the pictorial
isometric in the lower corner) with only short property-linked view labels and
one concise part fact in the right column.

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
    set_high_quality_shaded_with_edges,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_top_frame import (
    BAR_X0,
    BORE_DIA,
    BOSS_DIA,
    COLUMN_X,
    FRONT_COLUMN_Z,
    GOOSENECK_BORE_DIA,
    GOOSENECK_X,
    GOOSENECK_Z,
    HALF_H,
    KEEPER_TAP_SPEC,
    KEEPER_TAP_X,
    KEEPER_TAP_Z_FRONT,
    OUTER_X,
    SET_POCKET_DEPTH,
    SET_TAP_SPEC,
    SIDE_TAP_DRILL_DIA,
    STUD_HOLE_DIA,
    STUD_Z_FRONT,
    TAP_DRILL_MM,
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
TOP_CENTER = (0.170, 0.178)
FRONT_CENTER = (0.170, 0.085)
SECTION_CENTER = (0.340, 0.090)
ISO_CENTER = (0.052, 0.053)
ISO_SCALE = (1, 10)

TOP_VIEW_NOTE_XY = (0.166, 0.104)
FRONT_VIEW_NOTE_XY = (0.166, 0.070)
SECTION_VIEW_NOTE_XY = (0.305, 0.052)
ISO_VIEW_NOTE_XY = (0.028, 0.033)

# Note column, read top to bottom.
MANUFACTURING_NOTES_XY = (NOTE_COLUMN_X, 0.263)


# Per-view survivors of the marked-dimension import.  The top view owns the
# plan envelope, web, boss/socket, and crossbar geometry.  Section A-A owns the
# recessed cap seat because it is internal in both ordinary orthographic views.
TOP_KEEP = {
    "Width": (TOP_CENTER[0], TOP_CENTER[1] + PLAN_HALF_D + 0.011),
    "Depth": (0.048, TOP_CENTER[1]),
    "WinWidth": (TOP_CENTER[0], TOP_CENTER[1] + PLAN_HALF_D + 0.021),
    "WinDepth": (0.038, TOP_CENTER[1] + 0.030),
    "WebOuterWidth": (TOP_CENTER[0] + 0.020, TOP_CENTER[1] + 0.016),
    "WebOuterDepth": (0.028, TOP_CENTER[1] - 0.021),
    "WebInnerWidth": (TOP_CENTER[0] + 0.020, TOP_CENTER[1] - 0.016),
    "WebInnerDepth": (0.018, TOP_CENTER[1] - 0.042),
    "B0X": (0.300, TOP_CENTER[1] + 0.052),
    "B0Z": (0.300, TOP_CENTER[1] + 0.036),
    "C0Dia": (TOP_CENTER[0] + PLAN_HALF_W + 0.020, TOP_CENTER[1] + 0.026),
    "B0Dia": (TOP_CENTER[0] + PLAN_HALF_W + 0.020, TOP_CENTER[1] - 0.026),
    "HubDia": (TOP_CENTER[0] - 0.030, TOP_CENTER[1] + 0.026),
    "RibWidth": (0.100, TOP_CENTER[1] + 0.020),
    "PocketRun": (0.100, TOP_CENTER[1] + 0.004),
    "PocketRise": (0.100, TOP_CENTER[1] - 0.012),
    "SetTapZ": (0.100, TOP_CENTER[1] - 0.028),
    "GnX": (0.100, TOP_CENTER[1] + 0.052),
    "GnZ": (0.100, TOP_CENTER[1] + 0.036),
    "BarAnchorX": (0.120, TOP_CENTER[1] + 0.052),
    "BarAnchorZ": (0.120, TOP_CENTER[1] + 0.036),
    "BarFootSpan": (TOP_CENTER[0] - 0.030, TOP_CENTER[1] + 0.012),
    "GussetRunE": (TOP_CENTER[0] - 0.030, TOP_CENTER[1] - 0.012),
    "BarSideE": (TOP_CENTER[0] - 0.030, TOP_CENTER[1] - 0.026),
    "StudFrontX": (0.070, TOP_CENTER[1] + 0.020),
    "StudFrontZ": (0.070, TOP_CENTER[1] + 0.004),
    "StudRearX": (0.070, TOP_CENTER[1] - 0.012),
    "StudRearZ": (0.070, TOP_CENTER[1] - 0.028),
    "KeeperFrontX": (0.260, TOP_CENTER[1] + 0.020),
    "KeeperFrontZ": (0.260, TOP_CENTER[1] + 0.004),
    "KeeperRearX": (0.260, TOP_CENTER[1] - 0.012),
    "KeeperRearZ": (0.260, TOP_CENTER[1] - 0.028),
}
SECTION_KEEP = {
    "BossTopExtent": (SECTION_CENTER[0] + 0.060, SECTION_CENTER[1] + 0.032),
    "BossBottomExtent": (SECTION_CENTER[0] + 0.060, SECTION_CENTER[1] - 0.032),
    "HubBossExtent": (SECTION_CENTER[0] - 0.060, SECTION_CENTER[1] - 0.032),
    "RingHeight": (SECTION_CENTER[0] + 0.040, SECTION_CENTER[1] - 0.012),
    "CapRecessDia": (SECTION_CENTER[0] - 0.040, SECTION_CENTER[1] + 0.020),
    "CapRecessDepth": (SECTION_CENTER[0] + 0.040, SECTION_CENTER[1] + 0.010),
}
DIMENSION_CALLOUTS = {
    "WebOuterWidth": "WEB RING OUTER WIDTH",
    "WebOuterDepth": "WEB RING OUTER DEPTH",
    "WebInnerWidth": "WEB RING INNER WIDTH",
    "WebInnerDepth": "WEB RING INNER DEPTH",
    "B0X": "4X COLUMN SOCKET CENTRES X; NATIVE HALF-PITCH",
    "B0Z": "4X COLUMN SOCKET CENTRES Z; NATIVE HALF-PITCH",
    "C0Dia": "4X CORNER BOSS OD",
    "B0Dia": "4X COLUMN SOCKET; FIT MHA-083 TUBE; SEE SOURCE FIT LIMITS",
    "HubDia": "UNDERSIDE GOOSENECK HUB BOSS OD",
    "HubBossExtent": "GOOSENECK HUB BOSS AXIAL EXTENT",
    "RibWidth": "GOOSENECK HUB RIB WIDTH",
    "PocketRun": "GOOSENECK SET-SCREW POCKET",
    "PocketRise": "GOOSENECK SET-SCREW POCKET",
    "SetTapZ": "GOOSENECK SET-SCREW TAP CENTRE Z",
    "GnX": "GOOSENECK BORE CENTRE X",
    "GnZ": "GOOSENECK BORE CENTRE Z",
    "BarAnchorX": "INTEGRAL CROSSBAR CENTRE X",
    "BarAnchorZ": "INTEGRAL CROSSBAR CENTRE Z",
    "BarFootSpan": "INTEGRAL CROSSBAR FOOT SPAN",
    "GussetRunE": "4X CROSSBAR-JUNCTION GUSSET LEG",
    "BarSideE": "INTEGRAL CROSSBAR CLEAR SPAN",
    "StudFrontX": "FRONT HANGER HOLE CENTRE X",
    "StudFrontZ": "FRONT HANGER HOLE CENTRE Z",
    "StudRearX": "REAR HANGER HOLE CENTRE X",
    "StudRearZ": "REAR HANGER HOLE CENTRE Z",
    "KeeperFrontX": "FRONT KEEPER TAP CENTRE X",
    "KeeperFrontZ": "FRONT KEEPER TAP CENTRE Z",
    "KeeperRearX": "REAR KEEPER TAP CENTRE X",
    "KeeperRearZ": "REAR KEEPER TAP CENTRE Z",
    "BossTopExtent": "4X BOSS TOP EXTENT",
    "BossBottomExtent": "4X BOSS BOTTOM EXTENT",
    "RingHeight": "WEB RING HEIGHT",
    "CapRecessDia": (
        "4X CAP SKIRT RECESS; FIT MHA-133 / 9275K141 CAP; SEE SOURCE FIT LIMITS"
    ),
    "CapRecessDepth": "CAP SEAT; CAP SEATS ON TUBE END",
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
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
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
        process="BOTTOMING TAP",
    )
    stud_edge = model_point_in_view(
        adapter,
        top,
        (
            (BAR_X0 + 11.0) / 1000.0,
            HALF_H / 1000.0,
            (STUD_Z_FRONT + STUD_HOLE_DIA / 2.0) / 1000.0,
        ),
        label="top-frame hanger-stud hole edge",
    )
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=stud_edge,
        callout_xy=(TOP_CENTER[0] - 0.092, TOP_CENTER[1] - 0.047),
        label="2X hanger-stud clearance holes",
        process="DRILL",
    )
    keeper_edge = model_point_in_view(
        adapter,
        top,
        (
            KEEPER_TAP_X / 1000.0,
            HALF_H / 1000.0,
            (KEEPER_TAP_Z_FRONT + TAP_DRILL_MM[KEEPER_TAP_SPEC.size] / 2.0) / 1000.0,
        ),
        label="top-frame fulcrum-keeper tap edge",
    )
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=keeper_edge,
        callout_xy=(TOP_CENTER[0] + 0.085, TOP_CENTER[1] + 0.045),
        label="2X fulcrum-keeper blind taps",
        process="TAP",
    )
    gooseneck_edge = model_point_in_view(
        adapter,
        top,
        (
            GOOSENECK_X / 1000.0,
            HALF_H / 1000.0,
            (GOOSENECK_Z + GOOSENECK_BORE_DIA / 2.0) / 1000.0,
        ),
        label="top-frame gooseneck bore edge",
    )
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=gooseneck_edge,
        callout_xy=(TOP_CENTER[0] - 0.105, TOP_CENTER[1] + 0.040),
        label="gooseneck post clearance bore",
        process="DRILL",
    )
    set_tap_edge = model_point_in_view(
        adapter,
        iso,
        (
            -(OUTER_X - SET_POCKET_DEPTH) / 1000.0,
            TAP_DRILL_MM[SET_TAP_SPEC.size] / 2000.0,
            GOOSENECK_Z / 1000.0,
        ),
        label="top-frame gooseneck set-tap edge",
    )
    add_native_hole_callout(
        adapter,
        iso,
        edge_xy=set_tap_edge,
        callout_xy=(ISO_CENTER[0] + 0.050, ISO_CENTER[1] + 0.035),
        label="gooseneck set-screw blind tap",
        process="TAP",
    )

    add_property_linked_note(
        adapter,
        "Manufacturing Notes",
        *MANUFACTURING_NOTES_XY,
        char_height=NOTE_CHAR_HEIGHT,
    )
    add_property_linked_note(adapter, "Top View Note", *TOP_VIEW_NOTE_XY)
    add_property_linked_note(adapter, "Front View Note", *FRONT_VIEW_NOTE_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_VIEW_NOTE_XY)
    add_property_linked_note(adapter, "Section View Note", *SECTION_VIEW_NOTE_XY)
    # Hole callouts, center marks, and linked notes can invalidate an earlier
    # HLV transition.  Reassert the orthographic display state after curation.
    for view in (top, front):
        set_hidden_lines_visible(adapter, view)
    set_high_quality_shaded_with_edges(adapter, iso, label="top-frame isometric")

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
