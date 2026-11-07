r"""Create the curated machinist drawing for the pinion lift rod.

A plain 1/4 in bearing rod, crowned at its back end, with the MHA-DT-30 pin hole
match-drilled at assembly near its flat front end (U36).  The 1:1 side view
carries everything the lathe needs -- the bearing diameter and its mate, the
body length, the crown and the (overall) -- plus the bearing finish; a 5:1
detail of the front end carries the pin hole and its station from the front
face.  VIEW B, the rod turned square to its two set-screw flats' plane
(rule-23 retention, owner ruling 2026-11-07 (MHA-DT-00 rubric sample, PR
#2248)), carries their lengths, their stations off the crown rim and the
across-flat size.  A bare 1:1 end view, projected right of the side view,
carries no size: it is VIEW B's arrow parent, because VIEW B's line of sight
lies in the end view's plane and not in the side view's.  The diameter stays
on the side view (drawing-guidelines.md rule 11 (turned parts read like the
lathe); machinist review r1, #1013).

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_pinion_lift_rod.py dt-pinion-lift-rod
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound, _read_member
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_finish import add_surface_finish
from _drawing_leader_notes import add_leader_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
import dt_pinion_cam_spec
import dt_pinion_lift_rod_spec
from dt_pinion_lever_geometry import ROD_PIN_HOLE_FROM_END
from dt_pinion_lift_rod_spec import (
    ACROSS_FLAT_CALLOUT,
    BACK_FLAT_EDGE_FROM_RIM,
    BACK_FLAT_LEN,
    CAP_SAG,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_DIMENSIONS,
    FLAT_NORMAL_LOCAL,
    FLATS_VIEW,
    FRONT_FLAT_EDGE_FROM_RIM,
    FRONT_FLAT_LEN,
    PIN_HOLE_CALLOUT,
    ROD_DIA,
    ROD_DIA_CALLOUT,
    ROD_LEN,
    SURFACE_FINISHES,
)

# The rod spec restates the cam's print grades and screw (the cam spec reads
# the rod spec, so the rod spec cannot read it back); prove them here, where
# both import, before the flats they size reach the sheet.
_CAM_RESTATED = {
    "unit": (dt_pinion_lift_rod_spec.CAM_UNIT, dt_pinion_cam_spec.UNIT),
    "length places": (
        dt_pinion_lift_rod_spec.CAM_LENGTH_PLACES,
        dt_pinion_cam_spec.LENGTH_PLACES,
    ),
    "tap station places": (
        dt_pinion_lift_rod_spec.CAM_SET_SCREW_Z_PLACES,
        dt_pinion_cam_spec.SET_SCREW_Z_PLACES,
    ),
    "screw major max": (
        dt_pinion_lift_rod_spec.CAM_SET_SCREW_MAJOR_MAX,
        dt_pinion_cam_spec.SET_SCREW_MAJOR_MAX_MM,
    ),
    "screw pitch": (
        dt_pinion_lift_rod_spec.CAM_SET_SCREW_PITCH,
        dt_pinion_cam_spec.SET_SCREW_PITCH_MM,
    ),
}
_CAM_DRIFT = {
    name: pair
    for name, pair in _CAM_RESTATED.items()
    if (
        abs(pair[0] - pair[1]) > 1e-9
        if isinstance(pair[0], float)
        else pair[0] != pair[1]
    )
}
if _CAM_DRIFT:
    raise AssertionError(
        f"dt_pinion_lift_rod_spec's restated MHA-DT-23 values drifted: {_CAM_DRIFT}"
    )


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_pinion_lift_rod"]
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
# The crown adds CAP_SAG past the nominal length, so the side view's bounding
# box (and its centre) span ROD_LEN + CAP_SAG.
HALF_SPAN = (ROD_LEN + CAP_SAG) / 2000.0
RIGHT_CENTER = (0.200, 0.215)
# Under VIEW B, left of the title block (the 1:2 pictorial spans ~0.072 x
# 0.042).
ISO_CENTER = (0.140, 0.088)
ISO_NOTE_XY = (0.110, 0.060)
DETAIL_CENTER = (0.335, 0.132)
DETAIL_SCALE = (5, 1)
DETAIL_RADIUS_MM = 7.0
# The label anchors at its top centre. Above the circle it sat on the outline
# and crowded the pin-hole callout (r7 slice3 eye-pass), so it goes in the
# clear band between the circle (x <= 0.370) and the right border (0.419).
DETAIL_LABEL_XY = (0.391, 0.150)

# VIEW B: the named FLATS_VIEW, square to the set-screw flats' plane at 1:1
# under the side view, flats up and the crown end left as on the side view.
# Its sizes all sit above the rod: the lengths on the flats and the two
# stations stacked over them off the crown rim.  The one across-flat size
# sits off the crown end.
#
# Its viewing arrow (round-6 review #1).  VIEW B looks along the flats
# (FLAT_NORMAL_LOCAL x Z), which is the side view's own line of sight turned
# 180 - ROD_PHASE_DEG about the rod axis.  No arrow in the side view's plane
# can name that direction: any such arrow would look along +-Y and see the
# flats nearly face-on.  The end view from the flat front end (*Back, third
# angle right of the side view, unlabelled, sheet x = model -X, y = +Y) holds
# that line of sight in its plane, so it carries the B arrow parallel to the
# flats.  The arrow comes from the eye's side and points at the rod's centre.
# Projected straight along that arrow, the view would lay the flat end left
# and the flats down.  VIEW B keeps the side view's crown-left, flats-up
# reading, so it is turned 180 deg and says so.  It prints no clocking
# angle: the cams are staked on the flats before the pin hole is
# match-drilled, so the sheet does not control that angle.
END_CENTER = (0.340, RIGHT_CENTER[1])
VIEW_LETTER = "B"
VIEW_LETTER_HEIGHT = 0.005  # draw_dt_cone_tip_block's arrow letters
# The eye's direction from the rod in the end view's sheet axes: the
# FLATS_VIEW toward-viewer row (-Z) x n = (n_y, -n_x, 0), mapped through
# *Back's sheet x = -X.
VIEW_B_EYE = (-FLAT_NORMAL_LOCAL[1], -FLAT_NORMAL_LOCAL[0])
_ARROW_TIP_R = ROD_DIA * SHEET_SCALE[0] / 2000.0 + 0.0015
_ARROW_LENGTH = 0.010
VIEW_B_ARROW_TIP = (
    END_CENTER[0] + VIEW_B_EYE[0] * _ARROW_TIP_R,
    END_CENTER[1] + VIEW_B_EYE[1] * _ARROW_TIP_R,
)
VIEW_B_ARROW_TAIL = (
    VIEW_B_ARROW_TIP[0] + VIEW_B_EYE[0] * _ARROW_LENGTH,
    VIEW_B_ARROW_TIP[1] + VIEW_B_EYE[1] * _ARROW_LENGTH,
)
# The leader leaves the letter's left side at mid-height
# (draw_dt_cone_tip_block VIEW_C_LEADER_DX), so the letter's upper-left sits
# half a height above the tail.  The build reads the leader back and slides
# the letter by any miss.
VIEW_B_LETTER_XY = (
    VIEW_B_ARROW_TAIL[0] + 0.0005,
    VIEW_B_ARROW_TAIL[1] + VIEW_LETTER_HEIGHT / 2.0,
)
VIEW_ARROW_ANGLE_TOL_DEG = 1.0
FLATS_CENTER = (0.190, 0.140)
FLATS_LABEL = f"VIEW {VIEW_LETTER}\nROTATED 180°"
FLATS_LABEL_XY = (0.178, 0.130)
_FLATS_TOP = FLATS_CENTER[1] + ROD_DIA * SHEET_SCALE[0] / 2000.0


def _flats_view_x(z_mm: float) -> float:
    """Sheet x of the part station ``z_mm`` (from the flat front end) in VIEW B."""
    return FLATS_CENTER[0] + HALF_SPAN - z_mm * SHEET_SCALE[0] / 1000.0


_RIM_X = _flats_view_x(ROD_LEN)
_BACK_FLAT_X = _flats_view_x(ROD_LEN - BACK_FLAT_EDGE_FROM_RIM)
_FRONT_FLAT_X = _flats_view_x(ROD_LEN - FRONT_FLAT_EDGE_FROM_RIM)
FLATS_KEEP = {
    # Each length right of its short flat (which runs screen-right from its
    # rim-side edge), clear of that edge's station witness.
    "BackFlatLen": (_BACK_FLAT_X + BACK_FLAT_LEN / 1000.0 + 0.008, _FLATS_TOP + 0.009),
    "FrontFlatLen": (_FRONT_FLAT_X + FRONT_FLAT_LEN / 1000.0 + 0.008, _FLATS_TOP + 0.009),
    # The short station's bare value outside its 15 mm span, left of the
    # crown, its right end ~8 mm short of the rim witness (round-6 review #4:
    # the witness ran through the old "FROM CROWN RIM" words).
    "BackFlatFromRim": (_RIM_X - 0.013, _FLATS_TOP + 0.017),
    "FrontFlatFromRim": ((_RIM_X + _FRONT_FLAT_X) / 2.0, _FLATS_TOP + 0.023),
    # Round-6 review #4: the 6 mm span is shorter than its text, so a text
    # centred on the span was struck by its own dimension line and both
    # witnesses.  The text (value, its one callout line under it) stands
    # below the lower witness (y ~0.137) on its own dimension line, which
    # runs down to it ~11 mm left of the crown apex.  R7 review #1: the
    # offset-text leader instead crossed the callout and ended in open space.
    # The callout line (~80 mm) spans x ~0.04..0.12, above the 1:2 isometric's
    # top (y ~0.109).
    "AcrossFlat": (_RIM_X - 0.012, FLATS_CENTER[1] - 0.013),
}

# The rod's flank in the *Right view: the bearing finish leader drops onto it.
ROD_FLANK_Y = RIGHT_CENTER[1] + ROD_DIA * SHEET_SCALE[0] / 2000.0

# In the *Right view the part's +Z (crowned back end) points screen-left, so
# the flat front end (z 0) is the RIGHT silhouette edge.  The diameter and its
# mate hang above the rod, right of the finish symbol and left of Detail A's
# circle, high enough that the callout lines clear the rod; the body length
# and the (overall) stack below it, the overall outermost (rule 10).
RIGHT_KEEP = {
    "RodDia": (RIGHT_CENTER[0] - 0.005, ROD_FLANK_Y + 0.026),
    "RodBody": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.020),
    "RodOverall": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.032),
    "CapR": (RIGHT_CENTER[0] - HALF_SPAN - 0.012, RIGHT_CENTER[1] + 0.024),
}
DETAIL_KEEP = {
    # r7 eye-pass: the callout once ran over the DETAIL A label and past the
    # right border; with the label right of the circle and VIEW B's stations
    # in the field left of the detail, it sits above the circle (top y
    # 0.167), right of the side view's front-end witness (x 0.2995).
    "PinHoleDia": (DETAIL_CENTER[0] + 0.010, DETAIL_CENTER[1] + 0.051),
    # Below the fence (bottom y 0.0975) and OUTSIDE the witness lines (hole
    # axis 0.335, front end 0.355): between them the text was struck by both.
    "PinHoleZ": (DETAIL_CENTER[0] + 0.047, DETAIL_CENTER[1] - 0.045),
}
DIMENSION_CALLOUTS = {
    # Below the value: SolidWorks stores a multi-line ABOVE callout but prints
    # none of it (r2 layout audit text-unmatched; draw_dt_cone_gear_shaft).
    "RodDia": ROD_DIA_CALLOUT,
    # The match-drill and its mate only: MHA-DT-00 names the hole in its step.
    "PinHoleDia": PIN_HOLE_CALLOUT,
    # The one across-flat size names the cams it seats.  The stations (off
    # the crown rim) and the pin station (off the flat end) carry no words:
    # their extension lines land on that rim and that end (round-6 review #3).
    "AcrossFlat": ACROSS_FLAT_CALLOUT,
}


def _front_end_detail(adapter: Any, side: Any) -> Any:
    """A native 5:1 detail of the rod's front end, where the pin hole sits."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(side, "IView")
    if not drawing.ActivateView(view_name(adapter, side)):
        raise RuntimeError("failed to activate front-end detail parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        side,
        (0.0, 0.0, ROD_PIN_HOLE_FROM_END / 1000.0),
        label="front-end detail centre",
    )
    radius = DETAIL_RADIUS_MM * SHEET_SCALE[0] / 1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create front-end detail fence")
    detail = drawing.CreateDetailViewAt4(
        *DETAIL_CENTER,
        0.0,
        0,  # swDetViewSTANDARD
        *DETAIL_SCALE,
        "A",
        1,  # swDetCircleCIRCLE
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError("failed to create front-end detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("front-end detail has invalid bounds")
    target = [
        position[axis] + DETAIL_CENTER[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position front-end detail")
    draw.EditRebuild3()
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*DETAIL_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError("failed to position front-end detail label")
    draw.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"front-end detail label did not persist: {actual}")
    return detail


def _show_as_reference(
    adapter: Any, annotations: list[Any], names: frozenset[str]
) -> None:
    """Parenthesize each named linear dimension: (199.5), a reference.

    Through the prefix/suffix channel: ShowParenthesis read back True on the
    r2 sheet yet printed a bare 199.5.  Each name must be on the view once.
    """
    for name in sorted(names):
        found = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(found) != 1:
            raise RuntimeError(
                f"expected one {name} on the side view, found {len(found)}"
            )
        set_reference_dimension(adapter, found[0], label=f"MHA-DT-17 {name}")


def _view_b_arrow(adapter: Any, end: Any) -> None:
    """VIEW B's lettered viewing arrow on the end view, parallel to the flats.

    A letter note whose straight leader is the arrow (draw_dt_cone_tip_block:
    the native projected-view arrow is not switchable through the API).  The
    leader leaves the letter's near side, so the leader is read back and the
    letter slid by any miss until the arrow lies along VIEW_B_EYE.
    """
    label = f"view {VIEW_LETTER} viewing arrow"
    note = add_leader_note(
        adapter,
        VIEW_LETTER,
        text_xy=VIEW_B_LETTER_XY,
        attach_xy=VIEW_B_ARROW_TIP,
        view=end,
        label=label,
        height=VIEW_LETTER_HEIGHT,
    )
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    want = math.atan2(-VIEW_B_EYE[1], -VIEW_B_EYE[0])

    def leader_start() -> tuple[float, float]:
        points = [float(value) for value in annotation.GetLeaderPointsAtIndex(0) or ()]
        if len(points) < 6 or math.dist((points[-3], points[-2]), VIEW_B_ARROW_TIP) > 0.001:
            raise RuntimeError(f"{label} tip moved: leader {points}")
        return points[0], points[1]

    def miss_deg(start: tuple[float, float]) -> float:
        got = math.atan2(VIEW_B_ARROW_TIP[1] - start[1], VIEW_B_ARROW_TIP[0] - start[0])
        return abs(math.degrees((got - want + math.pi) % (2.0 * math.pi) - math.pi))

    start = leader_start()
    if miss_deg(start) > VIEW_ARROW_ANGLE_TOL_DEG:
        x, y, z = (float(value) for value in annotation.GetPosition())
        dx, dy = VIEW_B_ARROW_TAIL[0] - start[0], VIEW_B_ARROW_TAIL[1] - start[1]
        if not annotation.SetPosition2(x + dx, y + dy, z):
            raise RuntimeError(f"failed to align the {label}")
        rebuild_drawing(adapter, label=f"align {label}")
        start = leader_start()
        if miss_deg(start) > VIEW_ARROW_ANGLE_TOL_DEG:
            raise RuntimeError(
                f"{label} is {miss_deg(start):.1f} deg off the flats: leader from {start}"
            )
    _telemetry.info(
        f"{label}: leader {start[0]:.5f},{start[1]:.5f} -> "
        f"{VIEW_B_ARROW_TIP[0]:.5f},{VIEW_B_ARROW_TIP[1]:.5f}"
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-lift-rod source", await adapter.open_model(str(SOURCE)))
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
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Lift Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion lift rod; eccentric cam rod; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    # Third-angle right of the side view, at its height: the flat front end.
    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=(1, 1))
    # The part's named view square to the flats' plane (build_dt_pinion_lift_rod
    # _name_flats_view), placed like a standard one (draw_dt_cone_pivot_post).
    flats = place_view(adapter, str(SOURCE), FLATS_VIEW, *FLATS_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (right, end, flats, iso):
        set_hidden_lines_removed(adapter, view)

    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="rod side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    detail = _front_end_detail(adapter, right)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="front-end detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    flats_annotations = curate_view_dimensions(
        adapter,
        flats,
        keep=FLATS_KEEP,
        view_label="set-screw flats",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*right_annotations, *detail_annotations, *flats_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _show_as_reference(adapter, right_annotations, DRAWING_REFERENCE_DIMENSIONS)
    if not auto_center_marks(adapter, detail, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the pin hole")

    # drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the flank turns in the pivot blocks' bores -- the one running
    # surface.  A cylinder carries no model edge along its side, so the pick
    # is a SILHOUETTE entity.
    add_surface_finish(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] - 0.045, ROD_FLANK_Y),
        symbol_xy=(RIGHT_CENTER[0] - 0.045, ROD_FLANK_Y + 0.020),
        control=surface_finish_by_key(SURFACE_FINISHES, "bearing"),
        label="lift rod bearing finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,  # the pivot-block size; the default read oversized
    )

    _view_b_arrow(adapter, end)
    add_note(adapter, FLATS_LABEL, *FLATS_LABEL_XY)
    # Under the 1:2 isometric (x ~0.104-0.176, bottom y ~0.067).
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Lift Rod Manufacturing Drawing",
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
