r"""Create the manufacturing drawing for the transgear arm plate (MHA-PD-19).

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

The knob bore is the plate origin; screw stations, top corners and notch
corners come from ``pd_transgear_arm_plate_geometry`` at the current reducer
centre. The print imports those model dimensions rather than restating a
historical bore offset.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)

import _config
from _check import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edges import scan_view_edges
from _drawing_finish import add_surface_finish
from _drawing_gdt import PmiDrawingPlacement, project_part_pmi
import _drawing_hidden_sketches as hidden_sketches
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _native_projected_zone import require_saved_projected_gtols
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from pd_paper_drive_assembly_steps import matched_locator_notes
from pd_transgear_arm_plate_geometry import (
    LOCATOR_SITES_MM,
    LOCATOR_HOLE_DIA_MM,
    BORE_DIA,
    BOSS_DIA,
    BOSS_FACE_Z,
    EDGE_MINUS_X,
    EDGE_PLUS_X,
    END_R,
    FRONT_FACE_Z,
    HUB_DIA,
    HUB_FACE_Z,
    KINK,
    KINK_RIGHT,
    NOTCH_LEFT,
    NOTCH_RIGHT,
    REAR_FACE_Z,
    SCREW_HOLE_DIA,
    SCREW_HOLES,
    TOP_LEFT,
    TOP_RIGHT,
    arm_upper_edge_y,
)
from pd_transgear_arm_plate_spec import (
    LOCATOR_CALLOUT,
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    PROJECTED_ZONE_NOTE,
    BORE_CALLOUT,
    CSK_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HOLE_COUNT_CALLOUT,
    ISO_VIEW_SCALE,
    SCREW_HOLE_CALLOUT,
    SURFACE_FINISHES,
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

# The plate is 62 x 38 in plan and 29 deep: at 2:1 the plan, the back view
# and section A-A stand side by side above the title block (x > 0.216 below
# y 0.066). The section stands far enough right that its hub diameter clears
# the back view's notch height and its boss diameter ends inside the border
# (x 0.419), which leaves no room beside it for the isometric: that stands
# in the lower strip between the notes and the title block, its caption
# above it, under the back view's edge dimensions.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
# 12 mm lower than run 20261010T001620278Z, whose top frame row and locator
# callout printed above the border; section A-A's caption still clears the
# title block (it reached y 0.085).
PLAN_CENTER = (0.080, 0.153)
BACK_CENTER = (0.218, PLAN_CENTER[1])
SECTION_CENTER = (0.343, PLAN_CENTER[1])
# 3 mm lower than before #2034: the 15:150 plate stands 6.4 taller, so the
# back view's edge dimensions reach 3 mm nearer the isometric's caption.
ISO_CENTER = (0.180, 0.042)
ISO_NOTE_XY = (0.150, 0.078)
# Bottom left, under the plan view's bore frame (its bottom y 0.081), left
# of the isometric.
NOTES_XY = (0.014, 0.075)
# Characters per line that keep the block left of the isometric.
NOTES_WIDTH = 50
NOTES_TEXT = "\n".join((
    matched_locator_notes(
        _config.parts("pd-transgear-arm")["number"],
        _config.parts("pd-transgear-arm-plate")["number"],
        on_arm=False,
        width=NOTES_WIDTH,
    ),
    PROJECTED_ZONE_NOTE,
))

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
# Rows 4 apart (8 mm on the sheet: 4.4 mm air between 3.6 mm texts) keep the
# locator's witness lines under the locator diameter's shoulder (at 5 apart
# a top row rose through it: farm run 20261009T224545531Z,
# shoulder-crosses-line). The width stands under the centre view instead:
# across the top it was the one dimension line the reamed-hole leader had
# to cross (machinist review of the r3 sheets).
PLAN_ROWS = tuple(_SECTION_TOP + 8.0 + 4.0 * row for row in range(3))
PLAN_KEEP: dict[str, tuple[float, float, float]] = {
    "ScrewHoleX2": (SCREW_HOLES[1][0] / 2.0, PLAN_ROWS[0], _Z_PLAN),
    "ScrewHoleX1": (SCREW_HOLES[0][0] / 2.0, PLAN_ROWS[1], _Z_PLAN),
    "KinkY": (EDGE_MINUS_X - 5.0, KINK[1] / 2.0, _Z_PLAN),
    "TopLeftY": (EDGE_MINUS_X - 11.0, TOP_LEFT[1] / 2.0, _Z_PLAN),
    "KinkRightY": (EDGE_PLUS_X + 5.0, KINK_RIGHT[1] / 2.0, _Z_PLAN),
    "ScrewHoleY": (EDGE_PLUS_X + 9.5, SCREW_HOLES[0][1] / 2.0, _Z_PLAN),
    "TopRightY": (EDGE_PLUS_X + 19.0, TOP_RIGHT[1] / 2.0, _Z_PLAN),
    "EndR": (0.7071 * END_R + 6.0, -0.7071 * END_R - 6.0, _Z_PLAN),
    "BoreDia": (EDGE_MINUS_X - 4.0, _BOTTOM - 6.0, _Z_PLAN),
    "ScrewHoleDia": (EDGE_MINUS_X - 6.0, _TOP + 8.0, _Z_PLAN),
    "CskDia": (EDGE_PLUS_X + 8.0, _TOP + 8.0, _Z_PLAN),
    "LocatorX1": (LOCATOR_SITES_MM[0][0] / 2.0, PLAN_ROWS[2], _Z_PLAN),
    # High enough that its callout lines clear the screw-hole callout; three
    # short lines keep its left edge inside the border. Its leader runs down
    # to locator 1 left of every location dimension line.
    "LocatorDia1": (EDGE_MINUS_X - 4.5, _TOP + 23.75, _Z_PLAN),
}
# Back view (the mounting face): the notch face's corner heights, outboard,
# and both side edges from K below the end round, clear of every leader.
BACK_KEEP: dict[str, tuple[float, float, float]] = {
    "EdgeLeftX": (EDGE_MINUS_X / 2.0, _BOTTOM - 7.0, 0.0),
    "EdgeRightX": (EDGE_PLUS_X / 2.0, _BOTTOM - 7.0, 0.0),
    "NotchLeftY": (EDGE_MINUS_X - 4.0, NOTCH_LEFT[1] / 2.0, FRONT_FACE_Z),
    "NotchRightY": (EDGE_PLUS_X + 4.0, NOTCH_RIGHT[1] / 2.0, FRONT_FACE_Z),
    "LocatorY1": (EDGE_MINUS_X - 8.0, LOCATOR_SITES_MM[0][1] / 2.0, 0.0),
    "LocatorY2": (EDGE_PLUS_X + 8.0, LOCATOR_SITES_MM[1][1] / 2.0, 0.0),
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
    "LocatorDia1": LOCATOR_CALLOUT,
}
CALLOUTS_ABOVE = {
    "ScrewHoleDia": HOLE_COUNT_CALLOUT,
    "CskDia": HOLE_COUNT_CALLOUT,
}
# The bore finish symbol stands below the end round, left of the bore axis:
# clear of the bore callout (lower left), the end radius (lower right) and
# the bore's projected-axis frame, whose leader rises right of this one.
BORE_FINISH_MODEL = (-9.0, _BOTTOM - 9.0, _Z_PLAN)
FINISH_CHAR_HEIGHT = 0.0025
# Position frames, sheet metres. A frame's xy is its top-left corner; it is
# about 59 mm wide with a projected zone (44 mm without), and its leader
# leaves the end nearer the feature through a 6.3 mm shoulder (measured on
# run 20261009T214031408Z). The frames stand in three rows above the back
# view, which mirrors X, so its hole frames sit outboard of their own holes
# (no crossing) and the two through-bore locator leaders drop between the
# hole leaders. The plan carries no frame: each countersink is coaxial with
# its hole (note 3).
FRAME_ROWS = (0.262, 0.250, 0.238)
# The back view's holes and locators stand where they did on run
# 20261009T214031408Z plus _BACK_FEATURE_SHIFT (the view moved right and
# now centres on K), so each frame keeps its leader's measured run.
_BACK_FEATURE_SHIFT = 0.01875
FRAME_XY = {
    "plate_hole_1_position": (0.228 + _BACK_FEATURE_SHIFT, FRAME_ROWS[2]),
    "plate_hole_2_position": (0.1174 + _BACK_FEATURE_SHIFT, FRAME_ROWS[2]),
    "plate_locator_1_position": (0.2098 + _BACK_FEATURE_SHIFT, FRAME_ROWS[0]),
    "plate_locator_2_position": (0.2183 + _BACK_FEATURE_SHIFT, FRAME_ROWS[1]),
}
# The thrust faces' finish symbols, on section A-A where each face is
# edge-on: the pick lands on the face's own cut edge, midway across the
# annulus between the bore and the face's diameter (not at the bore mouth,
# where it read as a note on the diameter beside it), and the symbol stands
# level with it beyond the face, inside the diameters' extension lines.  A
# symbol reaches about 1 left and 7.5 right of its point (model mm at 2:1,
# the Ra text running right): the hub's stands far enough out that its text
# clears the hub face. Model points, mm.
FINISH_SYMBOL_REACH = (1.0, 7.5)
_ModelPoint = tuple[float, float, float]


def _annulus_mid_y(face_dia: float) -> float:
    """Below the axis, midway across a thrust face's annulus."""
    return -(BORE_DIA + face_dia) / 4.0


FACE_FINISHES: dict[str, tuple[_ModelPoint, _ModelPoint]] = {
    "hub_face": (
        (0.0, _annulus_mid_y(HUB_DIA), HUB_FACE_Z),
        (0.0, _annulus_mid_y(HUB_DIA), HUB_FACE_Z - 9.5),
    ),
    "boss_face": (
        (0.0, _annulus_mid_y(BOSS_DIA), BOSS_FACE_Z),
        (0.0, _annulus_mid_y(BOSS_DIA), BOSS_FACE_Z + 4.0),
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
    # These are the same native feature datums and circular zones authored
    # on the part, not +/- positions retyped on a drawing. The drill mouths
    # and the through locator bores' rims on the Front sketch (z = 0) are
    # visible in *Back; the plan (*Front) carries datum C's clock edge.
    plan_edges = scan_view_edges(plan, label="plate rear-face locating PMI")
    back_edges = scan_view_edges(back, label="plate mounting-face drill PMI")
    placements = {
        # Above section A-A's station stack (its top text reaches y 0.2365),
        # so the tag's horizontal leader to the mounting face's extension
        # runs clear of the HubFaceToMounting text.
        "datum:A": PmiDrawingPlacement(
            section, (0.300, 0.244),
            attachment_xy=_sheet_xy(
                adapter, section, (0.0, SCREW_HOLES[0][1], 0.0),
                "plate mounting datum",
            ),
        ),
        "datum:B": PmiDrawingPlacement(
            plan, (0.037, 0.108),
            edge_entity=visible_circle_edge(adapter, plan, BORE_DIA),
        ),
        # C is the vertical +X side face, square to the X hole coordinates.
        # The tag stands 11 mm below the top corner so its horizontal leader
        # lands on that side face, not on the sloping top edge (machinist
        # review 2026-10-11 read the corner landing as the sloped face).
        "datum:C": PmiDrawingPlacement(
            plan, (0.128, 0.190),
            edge_entity=plan_edges.exact_line_through(
                (EDGE_PLUS_X, (TOP_RIGHT[1] + NOTCH_RIGHT[1]) / 2.0, REAR_FACE_Z),
                label="plate +X clock edge",
            ).edge,
        ),
        **{
            f"plate_hole_{index}_position": PmiDrawingPlacement(
                back, FRAME_XY[f"plate_hole_{index}_position"],
                edge_entity=back_edges.circle_at(
                    (x, y, 0.0), SCREW_HOLE_DIA / 2.0,
                    axis=(0.0, 0.0, 1.0), label=f"plate hole {index} position",
                ).edge,
            )
            for index, (x, y) in enumerate(SCREW_HOLES, 1)
        },
        # Below the end radius's text and right of the bore finish symbol.
        "knob_projected_axis": PmiDrawingPlacement(
            plan, (0.085, 0.088),
            edge_entity=visible_circle_edge(adapter, plan, BORE_DIA),
        ),
        **{
            f"plate_locator_{index}_position": PmiDrawingPlacement(
                back, FRAME_XY[f"plate_locator_{index}_position"],
                edge_entity=back_edges.circle_at(
                    (x, y, 0.0), LOCATOR_HOLE_DIA_MM / 2.0,
                    axis=(0.0, 0.0, 1.0), label=f"plate locator {index} position",
                ).edge,
            ) for index, (x, y) in enumerate(LOCATOR_SITES_MM, 1)
        },
    }
    project_part_pmi(
        adapter, placements=placements, datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS, label="plate actual-bore locating frame",
    )
    if add_note(adapter, NOTES_TEXT, *NOTES_XY) is None:
        raise RuntimeError("failed to add the plate's matched-pair notes")
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

    artefacts = await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Arm Plate Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )
    require_saved_projected_gtols(
        adapter, artefacts["drawing"], GEOMETRIC_CONTROLS,
        label="saved transgear arm plate drawing projected axes",
    )
    return artefacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
