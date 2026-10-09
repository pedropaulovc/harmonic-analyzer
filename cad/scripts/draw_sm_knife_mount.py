r"""Create the curated machinist drawing for the knife-mount bearing block.

A machined, heat-treated steel block (24 wide x ~29.6 tall x 14 deep) with a
single Ø12 bore.  The bore is the knife-edge bearing: the summing-lever
trunnion's top vertex rides its upper inner wall in line contact (ch18 p.42:
unpainted hardened steel, close bore -- 2026-09-02 user re-read).  Every face
and the bore are real edges, so
the block dimensions ride the auto-imported profile marks (block + bore) with the
depth added across the right-view section.  The two MHA-VN-051 dowel holes
print their 2X reamed Ø (with its band and press callout) and a position
frame under it, Ø0.13 to A, carrying the datum feature symbol B for the pair,
at their BASIC span in the top view, and their flat-floor depth in section
A-A, cut from the top view through the tap and dowel axes (policy rule 7: the
floor is hidden in the front view, so it is dimensioned where the cut shows
it).  The bore carries a composite position frame to the top seat (datum A)
and the dowel pattern, its centre a BASIC height under A; the #6-32 tap a
position frame to the same A|B.

Run with SolidWorks open::

    uv run python cad\scripts\draw_sm_knife_mount.py sm-knife-mount
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from sm_knife_mount_spec import DRAWING_REFERENCE_PRECISION, GEOMETRIC_TOLERANCES_MM

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_frame_datum_feature,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    assert_frame_datums_defined,
    assert_imported_precision,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_arc_endpoints_to_center,
    set_basic_dimension,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_leaders import set_near_side_diameter
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from build_sm_knife_mount import BORE_CENTRE_DEPTH
from sm_knife_mount_spec import (
    BLK_BOT,
    BLK_HALF_X,
    BLK_TOP,
    BORE_CY,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIN_HOLE_CALLOUT,
    PIN_HOLE_PAIR_CALLOUT,
    PIN_HOLE_DEPTH,
    PIN_HOLE_DIA,
    PIN_HOLE_SPAN,
    PIN_HOLE_X,
    R_BORE,
    STUD_TAP_DIA,
    SUPPORT_Z_THICK,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    remove_notes_matching,
)


SPEC = DRAWINGS_BY_NAME["sm_knife_mount"]
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
# SolidWorks' own descriptive thread note; the tap's hole callout states the tap.
TAPPED_HOLE_NOTE = "Tapped Hole"
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym

SHEET_SCALE = (2.0, 1.0)
_BLOCK_CY = (BLK_TOP + BLK_BOT) / 2.0  # block centre height (model mm)

FRONT_CENTER = (0.115, 0.140)
RIGHT_CENTER = (0.220, 0.140)
TOP_CENTER = (0.115, 0.235)
ISO_CENTER = (0.345, 0.210)
# Section A-A stands right of the right view and under the isometric, clear
# of the title block (x > 0.216 below y 0.066): the block spans sheet y
# 0.0955..0.1545 at 2:1 and its label hangs under it.
SECTION_CENTER = (0.300, 0.125)
# The cutting line (model z = 0, through the tap and dowel axes) runs this
# far past each block face in the top view.
SECTION_LINE_OVERRUN_MM = 2.5
SECTION_LINE_MODEL_MM = (
    (-(BLK_HALF_X + SECTION_LINE_OVERRUN_MM), BLK_TOP, 0.0),
    (BLK_HALF_X + SECTION_LINE_OVERRUN_MM, BLK_TOP, 0.0),
)


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - _BLOCK_CY) * SHEET_SCALE[0] / 1000.0


def _section_y(model_y_mm: float) -> float:
    """Sheet y of a model y in section A-A (it looks along -Z, as the front)."""
    return SECTION_CENTER[1] + (model_y_mm - _BLOCK_CY) * SHEET_SCALE[0] / 1000.0


def _sheet_x(model_x_mm: float) -> float:
    """Sheet x of a model x in the front and top views (shared column)."""
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


# The 29.62 height's dimension line stands at sheet x 0.055, 36 mm off the
# block's -X face, and the bore's Ø and THRU sit in the band between them,
# 10.6 mm right of that line and 8.6 mm off the face: the 5ff8fba5d render
# ran the height line (then x 0.063) 3.62 mm through the Ø (text 58.5..75.3
# mm).  BORE_DIA_TEXT_HALF_WIDTH is half that render's block.
BORE_DIA_TEXT_HALF_WIDTH = 0.0084
FRONT_KEEP = {
    "BlockWidth": (FRONT_CENTER[0], _front_y(BLK_BOT) - 0.016),
    "BlockHeight": (FRONT_CENTER[0] - 0.060, FRONT_CENTER[1]),
    "BoreDia": (FRONT_CENTER[0] - 0.041, _front_y(BORE_CY) + 0.026),
}
# The dowel hole's floor depth stands right of the section, level with the
# middle of the hole, its witness lines off the cut top seat and hole floor.
SECTION_KEEP = {
    "PinHoleDepth": (
        SECTION_CENTER[0] + (BLK_HALF_X + 8.0) * SHEET_SCALE[0] / 1000.0,
        _section_y(BLK_TOP - PIN_HOLE_DEPTH / 2.0),
    ),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
TOP_HALF_Z = SUPPORT_Z_THICK / 2.0 * SHEET_SCALE[0] / 1000.0
# The dowel hole's Ø and its three callout lines park in the open band right
# of the top view (policy rule 8: callout text outside the silhouette, no text
# on a line).  SolidWorks hangs the block left of its text position by half
# the widest line plus the shoulder's overhang and runs the shoulder under the
# last line; both are measured on the dda9a33a8 farm render (3.5 mm text,
# "PRESS MHA-VN-05x DOWEL TO FLOOR" 84.5 wide, shoulder 1.6 past it and 12.86
# under the text position).  The shoulder's near end stands 6 mm right of the
# block's +X face and 10 mm below the hole centre, so the leader reaches the
# hole's lower-right rim at ~33 degrees, clear of its centre mark's arm.
PIN_CALLOUT_HALF_WIDTH = 0.04225
PIN_CALLOUT_SHOULDER_OVERHANG = 0.0016
PIN_CALLOUT_SHOULDER_DROP = 0.01286
PIN_CALLOUT_SHOULDER_START = (_sheet_x(BLK_HALF_X) + 0.006, TOP_CENTER[1] - 0.010)
# The pair's BASIC 12.700 span runs above the top view, between the hole axes.
PIN_SPAN_TEXT_XY = (TOP_CENTER[0], TOP_CENTER[1] + TOP_HALF_Z + 0.010)
TOP_KEEP = {
    "PinHoleDia": (
        PIN_CALLOUT_SHOULDER_START[0]
        + PIN_CALLOUT_SHOULDER_OVERHANG
        + PIN_CALLOUT_HALF_WIDTH,
        PIN_CALLOUT_SHOULDER_START[1] + PIN_CALLOUT_SHOULDER_DROP,
    ),
}
DIMENSION_CALLOUTS = {
    "BoreDia": "THRU",
    "PinHoleDia": PIN_HOLE_CALLOUT,
}
# The pair's count rides ABOVE its Ø (the pd-latch-hook-bracket PAIR_CALLOUT
# precedent), the process lines below it.
CALLOUTS_ABOVE = {"PinHoleDia": PIN_HOLE_PAIR_CALLOUT}
# The pair's position frame hangs under that callout's shoulder, its left
# edge on the shoulder's near end, on its own leader to the same hole; the
# bore's frame stands ~30 mm lower.  Printed: 29.4 x 7.0 mm, sheet x
# 146.6..176.0, y 212.0..219.0 (farm run 20261009T171439353Z).
PIN_FRAME_XY = (
    PIN_CALLOUT_SHOULDER_START[0] + PIN_CALLOUT_SHOULDER_OVERHANG,
    PIN_CALLOUT_SHOULDER_START[1] - 0.006,
)
PIN_FRAME_SIZE = (0.0294, 0.0070)
# Datum B's symbol hangs under that frame, at the middle of its width (Y14.5
# attaches a pattern's datum feature symbol to the frame under its nX
# callout), in the open band above the bore's two-tier frame (top 188.6 mm).
# The position is the letter box's bottom middle (datum A printed its 7 mm
# box upward from it); 5 mm of stem stand between the box and the frame.
DATUM_TAG_BOX = 0.007
PIN_DATUM_B_XY = (
    PIN_FRAME_XY[0] + PIN_FRAME_SIZE[0] / 2.0,
    PIN_FRAME_XY[1] - PIN_FRAME_SIZE[1] - 0.005 - DATUM_TAG_BOX,
)
# The #6-32 bottoming tap is stated once, on its Hole Wizard callout in the
# top view (fr-top-frame's KEEPER TAP precedent), not in a note.  The
# process rides its own row over the native drill and thread rows: three
# 4.3 mm rows, the widest ("#6-32 UNC-2B" and its depth) ~52 mm at the dowel
# callout's 2.73 mm a character.  The block parks in the band between the
# top view and the front view's datum-A tag (its top at y 0.1951), left of
# that tag (x >= 0.1115), so the leader climbs steeply to the tap's lower
# rim: ~14 mm over the part against a 12 mm approach from the view's lower
# edge, a ~2 mm detour (_layout_audit.LEADER_DETOUR_PROVISIONAL_M is 10).
TAP_CALLOUT_PROCESS = "BOTTOMING TAP\n"
TAP_CALLOUT_HALF_WIDTH = 0.026
TAP_CALLOUT_HALF_HEIGHT = 0.0065
TAP_CALLOUT_XY = (_sheet_x(-BLK_HALF_X) - 0.022, TOP_CENTER[1] - TOP_HALF_Z - 0.014)
# The tap's position frame hangs under its callout block, on its own leader
# to the tap.  The two leaders land on the tap's two lower rims (model x
# side): the callout's on the lower-left, nearer its block, the frame's on
# the lower-right, so the frame's leader, climbing from the frame's right
# end, stays right of the callout's.  Both on the lower-left rim, it crossed
# the callout's 2 mm short of the tip (leader-crosses-leader, farm run
# 20261009T164113078Z).
TAP_FRAME_XY = (TAP_CALLOUT_XY[0], TAP_CALLOUT_XY[1] - TAP_CALLOUT_HALF_HEIGHT - 0.007)
TAP_CALLOUT_RIM_SIDE = -1.0
TAP_FRAME_RIM_SIDE = 1.0
# The bore's two-tier frame stands above the block's upper-right corner,
# right of the datum-A tag; its BASIC height under A runs down the block's
# right side.
BORE_FRAME_XY = (FRONT_CENTER[0] + 0.035, _front_y(BLK_TOP) + 0.019)
BORE_BASIC_TEXT_XY = (
    _sheet_x(BLK_HALF_X) + 0.012,
    _front_y(BLK_TOP - BORE_CENTRE_DEPTH / 2.0),
)

RIGHT_HALF_Z = SUPPORT_Z_THICK / 2.0 * SHEET_SCALE[0] / 1000.0
RIGHT_HALF_Y = (BLK_TOP - BLK_BOT) / 2.0 * SHEET_SCALE[0] / 1000.0


def _set_sheet_precision(display: Any, *, label: str) -> None:
    """Give one sheet-added dimension the places the part's spec owns
    (``DRAWING_REFERENCE_PRECISION``, the draw_fr_top_frame precedent)."""
    places = DRAWING_REFERENCE_PRECISION[label]
    display = _early_bound(display, "IDisplayDimension")
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    applied = int(display.GetPrimaryPrecision2())
    if applied != places:
        raise RuntimeError(
            f"{label}: asked for {places} decimal places, dimension reads {applied}"
        )


def _sheet_dimension_mm(display: Any) -> float:
    """The value a sheet-added dimension measures, mm."""
    native = _early_bound(display, "IDisplayDimension")
    return (
        abs(float(_early_bound(native.GetDimension2(0), "IDimension").SystemValue))
        * 1000.0
    )


def _look_section_along_minus_z(adapter: Any, section: Any) -> None:
    """Point section A-A's sight line along -Z, so it reads as the front view.

    The direction is read from the section's own projection (the
    draw_dt_cone_swing_platform section C-C idiom): with screen-right r and
    screen-up u the sight line is u x r, which runs along -z exactly when
    model +x's sheet-x sign times model +y's sheet-y sign is positive.  Then
    the dowel hole stands right of the tap axis, beside SECTION_KEEP's depth.
    """
    cut = _early_bound(section.GetSection(), "IDrSection")

    def x_direction() -> float:
        base = model_point_in_view(
            adapter, section, (0.0, 0.0, 0.0), label="A-A origin"
        )
        east = model_point_in_view(adapter, section, (0.001, 0.0, 0.0), label="A-A +x")
        up = model_point_in_view(adapter, section, (0.0, 0.001, 0.0), label="A-A +y")
        return (east[0] - base[0]) * (up[1] - base[1])

    if x_direction() < 0.0:
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="section A-A looks along -Z")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("section A-A cut direction did not persist")
    direction = x_direction()
    if not direction > 0.0:
        raise RuntimeError(
            f"section A-A still looks along +Z (sign product {direction})"
        )


def _tap_lower_rim(adapter: Any, top: Any, x_side: float) -> tuple[float, float]:
    """The #6-32 tap's drill rim at 45 deg on model ``x_side``, below its
    centre in the top view: picked on whichever side of the cutting line
    model -Z/+Z projects below it."""
    rim_mm = STUD_TAP_DIA / 2.0 / math.sqrt(2.0)
    return min(
        (
            model_point_in_view(
                adapter,
                top,
                (x_side * rim_mm / 1000.0, BLK_TOP / 1000.0, side * rim_mm / 1000.0),
                label=f"knife-hanger tap rim x{x_side:+.0f} z{side:+.0f}",
            )
            for side in (1.0, -1.0)
        ),
        key=lambda point: point[1],
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open knife-mount source", await adapter.open_model(str(SOURCE)))
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
            0: "Knife-Mount Bearing Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "knife mount; hardened steel bearing block; knife-edge bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # Section A-A cuts the top view on z = 0 through the tap and dowel axes:
    # the blind dowel hole's floor is hidden in the front view (policy rule 7),
    # so its depth is dimensioned on the cut.
    section_ends = [
        model_point_in_view(
            adapter,
            top,
            tuple(value / 1000.0 for value in point),
            label=f"section A-A line end {index}",
        )
        for index, point in enumerate(SECTION_LINE_MODEL_MM)
    ]
    section = create_section_view(
        adapter,
        top,
        line_start=section_ends[0],
        line_end=section_ends[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(2, 1),
        label="dowel and tap axis section",
    )
    _look_section_along_minus_z(adapter, section)
    set_hidden_lines_removed(adapter, section)
    # The bore only reads in the front view; show it dashed in the projected
    # right/top views so the orthographic set carries the thru-hole the
    # isometric implies (blind-review finding: HLR left them empty rectangles).
    set_hidden_lines_removed(adapter, iso)
    for view in (front, right, top):
        set_hidden_lines_visible(adapter, view)

    # The dowel hole's floor depth (section A-A) is imported before its
    # profile's Ø and station (top), the MHA-PD-018 section-before-end order.
    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            section,
            keep=SECTION_KEEP,
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            top,
            keep=TOP_KEEP,
            view_label="top",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Places and the ream band are authored on the part; the sheet only proves
    # the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    # SolidWorks pins its own raw "#6-32 Tapped Hole" note to a view that
    # imports from the tapped part (the dda9a33a8 render put it on the top
    # view, through the dowel callout).  The tap is stated once, on its hole
    # callout below (rule 6), so every such note goes.  Which views receive
    # one is SolidWorks' choice (draw_fr_top_frame._auto_tapped_hole_notes),
    # so the count is logged, not gated; finalize_drawing then proves none is
    # left.
    removed_tap_notes = remove_notes_matching(adapter, TAPPED_HOLE_NOTE)
    _telemetry.info(f"removed {removed_tap_notes} automatic tapped-hole note(s)")
    tap_rim = _tap_lower_rim(adapter, top, TAP_CALLOUT_RIM_SIDE)
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=tap_rim,
        callout_xy=TAP_CALLOUT_XY,
        label="knife-hanger screw bottoming tap",
        process=TAP_CALLOUT_PROCESS,
    )
    # One arrow on the bore's near (upper-left) rim, its leader short from
    # the text on the left; native, the Ø line ran rim to rim through the
    # centre and across the view to a shoulder left of it.
    bore_dia = [a for a in annotations if dimension_name(adapter, a) == "BoreDia"]
    if len(bore_dia) != 1:
        raise RuntimeError(f"expected one BoreDia dimension, found {len(bore_dia)}")
    set_near_side_diameter(bore_dia[0], "knife-bore diameter")
    # The template centre-marks every hole as each view is placed (the top
    # view's two holes and section A-A carry marks no call asked for), so an
    # explicit AutoInsertCenterMarks2 on the front view printed the bore's
    # mark twice (DetailItem346/352 at one point; #913).  Prove the one mark.
    marks = (
        _early_bound(front, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )
    if len(marks) != 1:
        raise RuntimeError(f"expected one knife-bore centre mark, found {len(marks)}")

    # Block depth (14): dimension the right view's flat front/back faces.
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - RIGHT_HALF_Z, RIGHT_CENTER[1]),
        p1=(RIGHT_CENTER[0] + RIGHT_HALF_Z, RIGHT_CENTER[1]),
        text_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] - RIGHT_HALF_Y - 0.014),
        label="block-depth overall",
    )

    # The dowel pair's span: hole axis to hole axis, picked on each hole's
    # outer rim at 45 deg, clear of the bore's hidden lines at x +/-6.
    pin_rim_mm = PIN_HOLE_DIA / 2.0 / math.sqrt(2.0)
    span_picks = [
        max(
            (
                model_point_in_view(
                    adapter,
                    top,
                    (
                        side * (PIN_HOLE_X + pin_rim_mm) / 1000.0,
                        BLK_TOP / 1000.0,
                        z_side * pin_rim_mm / 1000.0,
                    ),
                    label=f"dowel hole rim x{side:+.0f} z{z_side:+.0f}",
                )
                for z_side in (1.0, -1.0)
            ),
            key=lambda point: point[1],
        )
        for side in (-1.0, 1.0)
    ]
    span = add_edge_dimension(
        adapter,
        top,
        p0=span_picks[0],
        p1=span_picks[1],
        text_xy=PIN_SPAN_TEXT_XY,
        label="dowel hole span",
        orientation="horizontal",
    )
    set_arc_endpoints_to_center(adapter, span, label="dowel hole span")
    if abs(_sheet_dimension_mm(span) - PIN_HOLE_SPAN) > 1e-5:
        raise RuntimeError(
            f"dowel hole span measures {_sheet_dimension_mm(span):g}, "
            f"expected {PIN_HOLE_SPAN:g} mm"
        )
    _set_sheet_precision(span, label="dowel hole span")
    set_basic_dimension(adapter, span, label="dowel hole span")

    # Datum A = the block top seat (clamped to the top-frame casting underside;
    # carries the #6-32 knife-hanger-screw tap and the MHA-VN-051 dowel
    # holes); datum B = the dowel pair, its symbol on the position frame
    # under their 2X Ø (a tag on the dimension attaches to nothing, farm run
    # 20261009T155421516Z).  Ra 1.6
    # (MACHINED_UM) on the bore's working upper wall, tagged on the bore rim
    # (a real circular edge).
    add_datum_feature(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], _front_y(BLK_TOP)),
        symbol_xy=(FRONT_CENTER[0], _front_y(BLK_TOP) + 0.018),
        datum="A",
        label="block top seat",
    )
    # The pair: ⌖Ø0.13 to A at their BASIC span, the frame on the +X hole's
    # lower outer rim, where the 2X Ø callout's own leader lands; datum B is
    # the symbol on that frame (add_frame_datum_feature: the frame's datum
    # identifier read "B" back and printed nothing, run 20261009T171439353Z).
    pin_frame_rim = min(
        (
            model_point_in_view(
                adapter,
                top,
                (
                    (PIN_HOLE_X + pin_rim_mm) / 1000.0,
                    BLK_TOP / 1000.0,
                    z_side * pin_rim_mm / 1000.0,
                ),
                label=f"dowel hole frame rim z{z_side:+.0f}",
            )
            for z_side in (1.0, -1.0)
        ),
        key=lambda point: point[1],
    )
    pin_frame = add_feature_control_frame(
        adapter,
        top,
        edge_xy=pin_frame_rim,
        frame_xy=PIN_FRAME_XY,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["dowel hole pattern position"],
        datums=("A",),
        diameter=True,
        label="dowel hole pattern position",
    )
    add_frame_datum_feature(
        adapter,
        top,
        pin_frame,
        datum="B",
        symbol_xy=PIN_DATUM_B_XY,
        label="dowel hole pattern datum B",
    )
    # The bore: Ø0.20 located to A|B, its orientation refined to Ø0.05 to
    # the same A|B (composite; tolerance-gdt-assessment §5.4).  Its centre
    # is BASIC under A; across, it sits on the pattern's centre plane.
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], _front_y(BORE_CY) + R_BORE * SHEET_SCALE[0] / 1000.0),
        frame_xy=BORE_FRAME_XY,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["knife-bore position"],
        datums=("A", "B"),
        diameter=True,
        label="knife-bore position",
        composite_lower=(
            GEOMETRIC_TOLERANCES_MM["knife-bore orientation refinement"],
            ("A", "B"),
        ),
    )
    bore_basic = add_edge_dimension(
        adapter,
        front,
        p0=(_sheet_x(0.6 * BLK_HALF_X), _front_y(BLK_TOP)),
        p1=(_sheet_x(R_BORE), _front_y(BORE_CY)),
        text_xy=BORE_BASIC_TEXT_XY,
        label="knife-bore centre from top seat",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(
        adapter, bore_basic, label="knife-bore centre from top seat"
    )
    if abs(_sheet_dimension_mm(bore_basic) - BORE_CENTRE_DEPTH) > 1e-5:
        raise RuntimeError(
            f"knife-bore centre measures {_sheet_dimension_mm(bore_basic):g} under "
            f"the top seat, expected {BORE_CENTRE_DEPTH:g} mm"
        )
    _set_sheet_precision(bore_basic, label="knife-bore centre from top seat")
    set_basic_dimension(adapter, bore_basic, label="knife-bore centre from top seat")
    # The #6-32 tap: Ø0.10 to A|B, the screw axis the crossbar's clearance
    # hole floats round (build_sm_summing_assembly's knife-hanger stack).
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=_tap_lower_rim(adapter, top, TAP_FRAME_RIM_SIDE),
        frame_xy=TAP_FRAME_XY,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["knife-hanger tap position"],
        datums=("A", "B"),
        diameter=True,
        label="knife-hanger tap position",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + R_BORE * SHEET_SCALE[0] / 1000.0, _front_y(BORE_CY)),
        symbol_xy=(FRONT_CENTER[0] + 0.052, _front_y(BORE_CY) - 0.020),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_bore"),
        label="knife bore finish",
        # The fleet's finish height (62 of 75 finishes): the document default
        # is the dimension height, and Ra 1.6 printed twice the sheet's notes.
        char_height=0.0025,
    )
    # Every datum a frame names is printed (A on the front view, B on the
    # pattern frame), so no frame references a datum the sheet never names.
    assert_frame_datums_defined(
        (front, right, top, section), label="sm-knife-mount frame datums"
    )

    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.175)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Knife-Mount Bearing Block Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=(TAPPED_HOLE_NOTE,),
        expected_redundant_notes=0,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
