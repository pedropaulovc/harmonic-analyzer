r"""Create the manufacturing drawing for the transgear arm plate (MHA-PD-019).

The plan is ``*Front``, looking at the REAR face: the outline from the bore
axis K (the end radius, the bar width, the top corners, the kink), the
reamed bore with its finish, both screw holes with their countersinks, and
the hole positions from the bore (the countersink Ø from the blanked
``CountersinkReference`` sketch round the +X hole, shown in this view only:
the drill callout leads to the -X hole from the upper left, the countersink
callout to the +X hole from the upper right).  The back view (``*Back``, the
mounting face) carries the notch face's two corner heights, the only view
where that edge is a solid line.  Section A-A cuts the plan on the bore axis
along Y -- the plane of the revolved hub and boss -- so the thickness over
the arm, the notch depth and the hub face's station (a baseline from the
mounting face), the hub-to-boss length and both diameters print on solid
cut edges, and the hub and boss thrust faces carry their finish.

Every kept dimension's text point is a model point (mm) projected through
its view, so the placement holds whichever way SolidWorks orients the
section.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _drawing_hidden_sketches as hidden_sketches
import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    create_section_view,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _surface_finish import surface_finish_by_key
from pd_transgear_arm_plate_geometry import (
    BORE_DIA,
    BOSS_FACE_Z,
    EDGE_MINUS_X,
    EDGE_PLUS_X,
    END_R,
    FRONT_FACE_Z,
    HUB_FACE_Z,
    KINK,
    NOTCH_LEFT,
    NOTCH_RIGHT,
    REAR_FACE_Z,
    SCREW_HOLES,
    TOP_LEFT,
    TOP_RIGHT,
    arm_upper_edge_y,
)
from pd_transgear_arm_plate_spec import (
    BORE_CALLOUT,
    CSK_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HOLE_COUNT_CALLOUT,
    ISO_VIEW_SCALE,
    SCREW_HOLE_CALLOUT,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pd_transgear_arm_plate"]
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

# The plate is 56 x 32 in plan and 29 deep: at 2:1 the plan, the back view
# and section A-A stand side by side above the title block (x > 0.216 below
# y 0.066), the isometric in the upper right.  The section stands far enough
# right that its hub Ø clears the back view's notch height, and the
# isometric's caption starts right of the section's over-arm wall and ends
# inside the border (x 0.419).
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
PLAN_CENTER = (0.080, 0.165)
BACK_CENTER = (0.206, PLAN_CENTER[1])
SECTION_CENTER = (0.326, PLAN_CENTER[1])
ISO_CENTER = (0.390, 0.225)
ISO_NOTE_XY = (0.353, 0.180)

_TOP = TOP_LEFT[1]  # the plate's highest point (the top edge's -X corner)
_SECTION_TOP = arm_upper_edge_y(0.0)
_BOTTOM = -END_R
_Z_PLAN = BOSS_FACE_Z

# The cutting line: along Y on the bore axis, past both ends of the plate.
SECTION_LINE_OVERRUN_MM = 3.0
SECTION_LINE_MODEL = (
    (0.0, _BOTTOM - SECTION_LINE_OVERRUN_MM, _Z_PLAN),
    (0.0, _SECTION_TOP + SECTION_LINE_OVERRUN_MM, _Z_PLAN),
)

# Per-view survivors of the marked-dimension import, each at the MODEL point
# (mm) its text stands on.  Plan: positions stack above the top edge,
# nearest first, the first row clear of the cutting line's arrow and letter
# (they reach about 5 above the section's top edge); the heights from K
# stand outboard of each side, the hole height's wide toleranced text wholly
# between the edge and the top-corner height's dimension line.
PLAN_ROWS = tuple(_SECTION_TOP + 8.0 + 5.0 * row for row in range(3))
PLAN_KEEP: dict[str, tuple[float, float, float]] = {
    "ScrewHoleX2": (SCREW_HOLES[1][0] / 2.0, PLAN_ROWS[0], _Z_PLAN),
    "ScrewHoleX1": (SCREW_HOLES[0][0] / 2.0, PLAN_ROWS[1], _Z_PLAN),
    "Width": ((EDGE_MINUS_X + EDGE_PLUS_X) / 2.0, PLAN_ROWS[2], _Z_PLAN),
    "KinkY": (EDGE_MINUS_X - 5.0, KINK[1] / 2.0, _Z_PLAN),
    "TopLeftY": (EDGE_MINUS_X - 11.0, TOP_LEFT[1] / 2.0, _Z_PLAN),
    "ScrewHoleY": (EDGE_PLUS_X + 9.5, SCREW_HOLES[0][1] / 2.0, _Z_PLAN),
    "TopRightY": (EDGE_PLUS_X + 19.0, TOP_RIGHT[1] / 2.0, _Z_PLAN),
    "EndR": (0.7071 * END_R + 6.0, -0.7071 * END_R - 6.0, _Z_PLAN),
    "BoreDia": (EDGE_MINUS_X - 4.0, _BOTTOM - 6.0, _Z_PLAN),
    "ScrewHoleDia": (EDGE_MINUS_X - 8.0, _TOP + 8.0, _Z_PLAN),
    "CskDia": (EDGE_PLUS_X + 8.0, _TOP + 8.0, _Z_PLAN),
}
# Back view (the mounting face): the notch face's corner heights, outboard.
BACK_KEEP: dict[str, tuple[float, float, float]] = {
    "NotchLeftY": (EDGE_MINUS_X - 4.0, NOTCH_LEFT[1] / 2.0, FRONT_FACE_Z),
    "NotchRightY": (EDGE_PLUS_X + 4.0, NOTCH_RIGHT[1] / 2.0, FRONT_FACE_Z),
}
# Section A-A (x = 0): the stations along Z are a baseline from the mounting
# face (the face that seats on the arm), stacked above the plate nearest
# first -- the rear face, the front face, the hub face -- and the overall
# hub-to-boss length stands alone below, clear of the view's caption.  The
# diameters stand beyond the hub and boss faces, outboard of the faces'
# finish symbols.
SECTION_KEEP: dict[str, tuple[float, float, float]] = {
    "ThicknessOverArm": (0.0, _SECTION_TOP + 5.0, REAR_FACE_Z / 2.0),
    "NotchDepth": (0.0, _SECTION_TOP + 11.0, FRONT_FACE_Z / 2.0),
    "HubFaceToMounting": (0.0, _SECTION_TOP + 17.0, HUB_FACE_Z / 2.0),
    "HubToBoss": (0.0, _BOTTOM - 5.0, (HUB_FACE_Z + BOSS_FACE_Z) / 2.0),
    "HubDia": (0.0, 0.0, HUB_FACE_Z - 16.0),
    "BossDia": (0.0, 0.0, BOSS_FACE_Z + 17.0),
}
DIMENSION_CALLOUTS = {
    "BoreDia": BORE_CALLOUT,
    "ScrewHoleDia": SCREW_HOLE_CALLOUT,
    "CskDia": CSK_CALLOUT,
}
CALLOUTS_ABOVE = {
    "ScrewHoleDia": HOLE_COUNT_CALLOUT,
    "CskDia": HOLE_COUNT_CALLOUT,
}
# The bore finish symbol stands below the end round, clear of the bore
# callout (lower left) and the end radius (lower right).
BORE_FINISH_MODEL = (0.0, _BOTTOM - 9.0, _Z_PLAN)
FINISH_CHAR_HEIGHT = 0.0025
# The thrust faces' finish symbols, on section A-A where each face is
# edge-on: the pick lands on the face's line inside the bore (the bore's
# far-half end edge, which bounds the face) and the symbol stands beyond the
# face, inside the diameters' extension lines.  A symbol reaches about 1
# left and 7.5 right of its point (model mm at 2:1, the Ra text running
# right): the hub's stands far enough out that its text clears the hub face.
# Model points, mm.
FINISH_SYMBOL_REACH = (1.0, 7.5)
_THRUST_PICK_Y = -BORE_DIA / 4.0
_ModelPoint = tuple[float, float, float]
FACE_FINISHES: dict[str, tuple[_ModelPoint, _ModelPoint]] = {
    "hub_face": (
        (0.0, _THRUST_PICK_Y, HUB_FACE_Z),
        (0.0, _THRUST_PICK_Y, HUB_FACE_Z - 9.5),
    ),
    "boss_face": (
        (0.0, _THRUST_PICK_Y, BOSS_FACE_Z),
        (0.0, _THRUST_PICK_Y, BOSS_FACE_Z + 4.0),
    ),
}


def _sheet_xy(
    adapter: Any, view: Any, point_mm: _ModelPoint, label: str
) -> tuple[float, float]:
    """Project a model point (mm) onto the sheet through ``view``."""
    return model_point_in_view(
        adapter, view, tuple(value / 1000.0 for value in point_mm), label=label
    )


def _sheet_keep(
    adapter: Any, view: Any, keep: dict[str, _ModelPoint], label: str
) -> dict[str, tuple[float, float]]:
    """Project each kept dimension's model text point onto the sheet."""
    return {
        name: _sheet_xy(adapter, view, point, f"{label} {name}")
        for name, point in keep.items()
    }


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-arm-plate source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
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
            0: "Transgear Arm Plate Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear arm plate; machined steel bar",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=VIEW_SCALE)
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=VIEW_SCALE)
    line = [
        model_point_in_view(
            adapter,
            plan,
            tuple(value / 1000.0 for value in point),
            label="section line",
        )
        for point in SECTION_LINE_MODEL
    ]
    section = create_section_view(
        adapter,
        plan,
        line_start=line[0],
        line_end=line[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="plate section on the bore axis",
    )
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_VIEW_SCALE
    )
    for view in (plan, back, section, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        annotation
        for view, keep, label in (
            (plan, PLAN_KEEP, "plan"),
            (back, BACK_KEEP, "back"),
            (section, SECTION_KEEP, "section A-A"),
        )
        for annotation in hidden_sketches.curate_view_dimensions(
            adapter,
            view,
            keep=_sheet_keep(adapter, view, keep, label),
            view_label=label,
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    ]
    # Decimal places and the explicit bands are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    for view, label in ((plan, "plan"), (back, "back")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME centre marks to the {label} view")

    add_surface_finish(
        adapter,
        plan,
        symbol_xy=model_point_in_view(
            adapter,
            plan,
            tuple(value / 1000.0 for value in BORE_FINISH_MODEL),
            label="bore finish symbol",
        ),
        control=surface_finish_by_key(SURFACE_FINISHES, "transgear_arm_plate_bore"),
        label="arm-plate bore finish",
        entity=visible_circle_edge(adapter, plan, BORE_DIA),
        char_height=FINISH_CHAR_HEIGHT,
    )
    for key, label in (
        ("hub_face", "arm-plate hub face finish"),
        ("boss_face", "arm-plate boss face finish"),
    ):
        pick, symbol = FACE_FINISHES[key]
        add_surface_finish(
            adapter,
            section,
            edge_xy=_sheet_xy(adapter, section, pick, f"{label} pick"),
            symbol_xy=_sheet_xy(adapter, section, symbol, f"{label} symbol"),
            control=surface_finish_by_key(SURFACE_FINISHES, key),
            label=label,
            char_height=FINISH_CHAR_HEIGHT,
        )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        spec=SPEC,
        pdf_title="Transgear Arm Plate Manufacturing Drawing",
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
