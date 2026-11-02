r"""Create the curated machinist drawing for the pen hanger.

The SLDPRT remains authoritative.  This recipe supplies only the hanger's views,
the placement of its imported model dimensions, the hanger-screw hole callout,
and the property-linked notes; sheet/template and export behavior lives in
``_drawing_common``.  Dimension import and curation live in
``_drawing_dimension_import``; places and bands are authored on the part.

The pen hanger is a black tapered steel strap (11 gauge, .63 -> .48 wide,
6.69 tall; decimal-inch sheet) with two open U guide plates brazed across its
front face; the pen rod
hangs in both slots.  The front view (1:1, ``*Back``: looking at the strap's
front face and the plates from the machine front, as note 1 names it) carries
the strap outline, the screw-hole station, the upper plate's drop and the
plates' sheet-stock thickness (a reference); section A-A (2:1) cuts the strap
just above the upper plate and looks down onto its U, carrying the slot (its
depth and the plate's reach both from the plate's free end), its corner
radius, the strap's sheet-stock thickness (a reference), the plate's overhang
past the strap (a reference) and its in-line callout; the shaded isometric
(1:1) fills the right of the sheet.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pn_pen_hanger.py pn-pen-hanger
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_detail_projection import settle_detail_projection
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leader_notes import add_leader_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
from pn_pen_hanger_spec import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    GUIDE_PLATE_T,
    GUIDE_PLATE_WIDTH,
    GUIDE_PLATE_YS,
    PLATE_FRONT_Z,
    REFERENCE_DIMENSIONS,
    SCREW_HOLE_DIA,
    SCREW_HOLE_XY,
    SLOT_BOTTOM_Z,
    STRAP_BOT_X,
    STRAP_BOT_Y,
    STRAP_TOP_X,
    STRAP_Z,
    UPPER_PLATE_LOCATION_CALLOUT,
    UPPER_PLATE_OVERHANG,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pn_pen_hanger"]
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

SHEET_SCALE = (1.0, 1.0)  # the 6.69-tall strap fits the sheet at full size
FRONT_SCALE = (1, 1)
SECTION_SCALE = (2, 1)  # the slot's .002 band and its corner radius need room
# At 1:1 the strap's edges, slots and plates read in the empty right half of
# the sheet (the 1:2 iso read as a silhouette).  No drawing-view-only
# lighting exists, so the part's own colour (BAR_STEEL, not PANEL_BLACK:
# build_pn_pen_hanger) is what keeps the shaded faces lighter than the edges.
ISO_SCALE = (1, 1)
_FRONT_M_PER_MM = FRONT_SCALE[0] / FRONT_SCALE[1] / 1000.0
_SECTION_M_PER_MM = SECTION_SCALE[0] / SECTION_SCALE[1] / 1000.0

# Model extents (local mm) of the front (X-Y) silhouette.
_X = (min(STRAP_TOP_X[0], STRAP_BOT_X[0]), max(STRAP_TOP_X[1], GUIDE_PLATE_WIDTH / 2.0))
_Y = (STRAP_BOT_Y, 0.0)
_CX = (_X[0] + _X[1]) / 2.0
_CY = (_Y[0] + _Y[1]) / 2.0
_HALF_PLATE = GUIDE_PLATE_WIDTH / 2.0


def _strap_x_at(y_mm: float) -> tuple[float, float]:
    """The tapered strap's (left, right) edges (local x) at local height y."""
    t = y_mm / STRAP_BOT_Y
    return (
        STRAP_TOP_X[0] + (STRAP_BOT_X[0] - STRAP_TOP_X[0]) * t,
        STRAP_TOP_X[1] + (STRAP_BOT_X[1] - STRAP_TOP_X[1]) * t,
    )


_UPPER_TOP_Y = GUIDE_PLATE_YS[1] + GUIDE_PLATE_T

# Section A-A: a horizontal cutting plane just above the upper plate, looking
# down (-y) onto it: the strap's cut is hatched and the plate's U prints
# below it as visible outline (the lower plate, alike and in line, hides
# behind it).  The plane clears the plate's top face by SECTION_ABOVE_PLATE,
# so the heavy cutting line does not overprint the 1.5 plate on the 1:1
# front view, yet stays close enough that the strap edge it cuts reads the
# plate's overhang at the plate to the printed place (guarded below).
SECTION_ABOVE_PLATE = 0.8
SECTION_Y = _UPPER_TOP_Y + SECTION_ABOVE_PLATE
_STRAP_CUT_X = _strap_x_at(SECTION_Y)
_SECTION_X = (min(_STRAP_CUT_X[0], -_HALF_PLATE), max(_STRAP_CUT_X[1], _HALF_PLATE))
_SECTION_Z = (PLATE_FRONT_Z, STRAP_Z[1])
_SX = (_SECTION_X[0] + _SECTION_X[1]) / 2.0
_SZ = (_SECTION_Z[0] + _SECTION_Z[1]) / 2.0
# The plate's +x edge past the strap's cut edge, which the section prints as
# a reference: the same .XX value as the overhang at the plate's top face.
_OVERHANG_AT_CUT = _HALF_PLATE - _STRAP_CUT_X[1]
if round(_OVERHANG_AT_CUT / 25.4, DRAWING_REFERENCE_PRECISION) != round(
    UPPER_PLATE_OVERHANG / 25.4, DRAWING_REFERENCE_PRECISION
):
    raise AssertionError(
        "section A-A sits too far above the plate to read its overhang"
    )
# The cutting line overruns that silhouette so each arrow's letter (5.5 mm
# wide, 15-20 mm under the line on the 20261014T002650255Z sheet) stands
# clear of the slanted strap edge below it: about 1.5 mm on the +x side,
# and on the -x side 1.6 mm from the strap edge and 1.3 mm from the
# StrapTaperDx extension line beyond it.
SECTION_LINE_OVERRUN = 3.5
SECTION_LINE_MODEL_MM = (
    (_SECTION_X[1] + SECTION_LINE_OVERRUN, SECTION_Y, 0.0),
    (_SECTION_X[0] - SECTION_LINE_OVERRUN, SECTION_Y, 0.0),
)

# Sheet layout (meters).  The tall front view hugs the left margin (its
# stacked top dimensions under the border, its bottom pair over its label);
# the screw-hole callout sits right of its top, in the gap before section
# A-A; the section stands right of the callout with its width rows and native
# caption stacked below it and the slot width's text block parked right of
# it, the notes under the caption clear of the title block; the isometric to
# the right.
FRONT_CENTER = (0.075, 0.150)
SECTION_CENTER = (0.230, 0.195)
# The 1:1 iso is about 42 wide x 158 tall on the sheet (twice the 1:2 view's
# 21 x 76 on the 20261014T010321468Z sheet): centred at y 0.166 it spans
# y 0.087..0.245, under the top border (0.267) and above its note; its left
# edge (x 0.341) stands 40 mm right of the slot width's text block (x 0.298).
ISO_CENTER = (0.362, 0.166)
# The note's top-left: its ~60 mm line (x 0.340..0.400) sits under the iso
# and 12 mm above the title block's top edge (y 0.065 for x >= 0.216).
ISO_NOTE_XY = (0.340, 0.080)
NOTES_XY = (0.110, 0.094)
# Text centre: the leader leaves the hole's rim on the sheet-right side and
# drops gently right, crossing only the strap's tapered edge and the
# StrapTaperDx extension line beside it -- no dimension line lies there.
CALLOUT_XY = (0.137, 0.215)
# The native Hole Wizard Ø variable of the #8 close clearance callout.
SCREW_HOLE_CALLOUT_PRECISION = {"hw-diam": 3}
# Under the front view's StrapTaperDx row (its text at y 0.045).
FRONT_NOTE_XY = (0.030, 0.034)


def _fx(model_x_mm: float) -> float:
    # *Back looks along +z at the strap front: model +x prints to the LEFT.
    return FRONT_CENTER[0] - (model_x_mm - _CX) * _FRONT_M_PER_MM


def _fy(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - _CY) * _FRONT_M_PER_MM


def _ax(model_x_mm: float) -> float:
    # Section A-A looks down (-y) with the strap back face up: model +x prints
    # to the LEFT, as in the front view above it.
    return SECTION_CENTER[0] - (model_x_mm - _SX) * _SECTION_M_PER_MM


def _az(model_z_mm: float) -> float:
    # The strap back face (z 0) at the top, the plate front at the bottom.
    return SECTION_CENTER[1] + (model_z_mm - _SZ) * _SECTION_M_PER_MM


# Front view: the screw-hole station and the strap's top run stacked above it
# (the station's value left of the origin corner, outside the run's extension
# lines); the hole height, the upper plate's drop and the strap's rise stacked
# left, shortest nearest; the lower plate's thickness at the bottom left, its
# value under the plate, far from section A-A's cutting line just above the
# upper plate; the strap's bottom width and its taper under the view, so the
# taper's long extension line drops from the top outer corner outside the
# tapered edge instead of running down through the strap.
FRONT_KEEP = {
    "ScrewX": (_fx(0.0) - 0.006, _fy(0.0) + 0.010),
    "StrapTopRun": (_fx(STRAP_TOP_X[0] / 2.0), _fy(0.0) + 0.020),
    "ScrewY": (_fx(_X[1]) - 0.008, _fy(SCREW_HOLE_XY[1] / 2.0)),
    "UpperPlateDrop": (_fx(_X[1]) - 0.018, _fy(_UPPER_TOP_Y / 2.0)),
    "StrapRise": (_fx(_X[1]) - 0.030, _fy(_CY)),
    # The 1.5 span holds no text, so SolidWorks shelves the two-row block
    # just left of the dimension line, centred on the keep's height
    # (20261014T024823419Z: keep 4 under the foot put the block at
    # y 0.0554..0.0661, x 0.0232..0.0507, its "(1.5)" struck by the StrapRise
    # foot extension line at y 0.065 and the 170.0 arrowhead).  Keep 9 under
    # the foot drops the ~10.7 mm block to about y 0.050..0.061: its top
    # ~4 mm under that extension line and the 170.0 arrowhead, its shelf
    # ~2 mm under the StrapBotWidth row (y 0.0522), whose line starts at
    # x 0.058, ~7 mm right of the block.  The line stays 12 mm left of the
    # plate edge; its downward tail to the shelf crosses no other line.
    "PlateThick": (_fx(_X[1]) - 0.012, _fy(STRAP_BOT_Y) - 0.009),
    "StrapBotWidth": (_fx(0.0), _fy(STRAP_BOT_Y) - 0.010),
    "StrapTaperDx": (
        _fx((STRAP_TOP_X[0] + STRAP_BOT_X[0]) / 2.0),
        _fy(STRAP_BOT_Y) - 0.020,
    ),
}
# Section A-A: the U's widths stacked under its plate front, rows 9 mm apart
# (drawing-guidelines.md rule 14): the slot nearest,
# the arm next (its value left of the U), the plate width outermost with its
# value centred between the plate's extension lines, which no other line
# reaches -- the slot's extension lines stop at the slot row, the arm's at
# the arm row.  The plate edges' extension lines run past the inner rows
# OUTSIDE their spans, so no extension line crosses a dimension line.  The
# slot width's 10 mm span cannot hold its banded value and fit callout, so
# its text is offset onto a leader, right of the section beyond every
# extension line (SLOT_WIDTH_TEXT_XY).  On the left, the slot depth and,
# outside it, the plate reach, both from the plate's free end (the plate is
# cut as its own blank before brazing): shortest nearest, so the slot
# bottom's extension line stops short of the reach's dimension line.  The
# strap stock thickness right of the strap end; the corner radius's text
# up-right of the -x corner it is attached to, so its leader leaves the arc
# outward through the arm and crosses no other ink.
_PLATE_FRONT_SHEET_Y = _az(PLATE_FRONT_Z)
# Dimension-line rows below the plate front.  A single-line value prints
# with its centre 2.7 mm above its line (native sheet run
# 20261013T234201871Z: 2.5 and 10.0 each read 2.7-2.8 mm above).
SECTION_ROW_Y = {
    "SlotWidth": _PLATE_FRONT_SHEET_Y - 0.0065,
    "ArmWidth": _PLATE_FRONT_SHEET_Y - 0.0155,
    "PlateWidth": _PLATE_FRONT_SHEET_Y - 0.0245,
}
_VALUE_ABOVE_LINE = 0.0027
# The slot width's position fixes its dimension line before its text is
# offset; its banded value stacks two rows, so its centre stands about 5 mm
# above its line (the 20261013T234201871Z block centre stood 10.5 mm above
# with two callout rows under the value).
_BANDED_VALUE_ABOVE_LINE = 0.005
SECTION_KEEP = {
    "SlotWidth": (_ax(0.0), SECTION_ROW_Y["SlotWidth"] + _BANDED_VALUE_ABOVE_LINE),
    "ArmWidth": (
        _ax(_HALF_PLATE) - 0.006,
        SECTION_ROW_Y["ArmWidth"] + _VALUE_ABOVE_LINE,
    ),
    "PlateWidth": (_ax(0.0), SECTION_ROW_Y["PlateWidth"] + _VALUE_ABOVE_LINE),
    "SlotDepth": (
        _ax(_HALF_PLATE) - 0.008,
        _az((PLATE_FRONT_Z + SLOT_BOTTOM_Z) / 2.0),
    ),
    "PlateReach": (
        _ax(_HALF_PLATE) - 0.020,
        _az((PLATE_FRONT_Z + STRAP_Z[0]) / 2.0),
    ),
    "StrapThick": (_ax(_SECTION_X[0]) + 0.008, _az((STRAP_Z[0] + STRAP_Z[1]) / 2.0)),
    # "2X R.08 MAX" (~30 mm) is wider than the 24.5 mm EACH SLOT row that set
    # the block's width on the 20261024T091056564Z sheet, so the centre moves
    # 4 mm right of the bare radius's and the left end keeps ~4 mm off the
    # plate's -x edge.
    "SlotCornerR": (_ax(-_HALF_PLATE) + 0.019, _az(SLOT_BOTTOM_Z) + 0.012),
}
# The slot width's offset text block (value, band and two callout rows,
# about 49 x 15 mm, positioned by its centre): its left end 4 mm right of
# the section's rightmost ink (the strap end), centred just below the slot
# row so the leader runs nearly level to the dimension line, crossing only
# the plate's -x extension line.
_SLOT_TEXT_HALF_WIDTH = 0.0245
SLOT_WIDTH_TEXT_XY = (
    _ax(_SECTION_X[0]) + 0.004 + _SLOT_TEXT_HALF_WIDTH,
    SECTION_ROW_Y["SlotWidth"] - 0.004,
)
# The strap stock's offset text block ("(.1196)" over 11 GA SHEET, about
# 30 x 8 mm, positioned by its centre): its two rows cannot sit in the 6 mm
# span, so the block stands level with the strap, its left end 4 mm right of
# the dimension line (8 mm right of the strap end), and the leader runs level
# to that line, crossing nothing.
_STRAP_THICK_TEXT_HALF_WIDTH = 0.015
STRAP_THICK_TEXT_XY = (
    SECTION_KEEP["StrapThick"][0] + 0.004 + _STRAP_THICK_TEXT_HALF_WIDTH,
    SECTION_KEEP["StrapThick"][1],
)
# The native SECTION A-A / SCALE 2 : 1 caption's top centre, under the plate
# width row.
SECTION_CAPTION_XY = (SECTION_CENTER[0], SECTION_ROW_Y["PlateWidth"] - 0.012)
# The overhang reference (rule 10): picked on the strap's cut edge at mid
# thickness and on the plate's +x edge 7 mm ahead of its back, clear of the
# plate-back extension line.  Its row 6 mm above the strap back face; its
# value left of the plate edge's extension line (the 2.5 mm span holds no
# text), as the arm width's sits.  The plate edge's extension line rises past
# the strap foot, where the plate reach's root extension line leaves the same
# edge (rule 14: conventional).
OVERHANG_PICK_Z = ((STRAP_Z[0] + STRAP_Z[1]) / 2.0, STRAP_Z[0] - 7.0)
_OVERHANG_ROW_Y = _az(STRAP_Z[1]) + 0.006
OVERHANG_TEXT_XY = (_ax(_HALF_PLATE) - 0.0085, _OVERHANG_ROW_Y + _VALUE_ABOVE_LINE)
# The in-line callout (rule 10) on section A-A, where the plate shows in
# plan: the leader tip on the plate's -x edge midway between the slot bottom
# and the plate front; the text top-left 13 mm right of that edge, between
# the corner radius's text above and the slot width's block below, so the
# leader runs nearly level and crosses nothing.
UPPER_PLATE_NOTE_TIP = (_ax(-_HALF_PLATE), _az((SLOT_BOTTOM_Z + PLATE_FRONT_Z) / 2.0))
UPPER_PLATE_NOTE_XY = (UPPER_PLATE_NOTE_TIP[0] + 0.013, UPPER_PLATE_NOTE_TIP[1] + 0.006)


def _create_section(adapter: Any, front: Any) -> Any:
    """Section A-A just above the upper plate, looking down onto it."""
    line = [
        model_point_in_view(
            adapter,
            front,
            tuple(value / 1000.0 for value in point),
            label="section A-A cutting line",
        )
        for point in SECTION_LINE_MODEL_MM
    ]
    section = create_section_view(
        adapter,
        front,
        line_start=line[0],
        line_end=line[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SECTION_SCALE,
        label="upper guide plate section",
    )
    native = _early_bound(section, "IView")
    cut = _early_bound(native.GetSection(), "IDrSection")
    # The plate lies below the cut: it must print as visible outline beyond
    # it, so the section may not be a surface cut only.  R2026x declares the
    # setter void; only the getter is tested.
    if bool(cut.GetDisplayOnlySurfaceCut()):
        cut.SetDisplayOnlySurfaceCut(False)
        rebuild_drawing(adapter, label="hanger section shows the plate below")
        if bool(cut.GetDisplayOnlySurfaceCut()):
            raise RuntimeError("hanger section A-A hides the plate beyond the cut")
    ratio = tuple(float(value) for value in native.ScaleRatio)
    if not math.isclose(ratio[0] / ratio[1], SECTION_SCALE[0] / SECTION_SCALE[1]):
        raise RuntimeError(f"hanger section A-A scale did not persist: {ratio}")
    _orient_section(adapter, native, cut)
    # A section shows no hidden lines (rule 9); set before centring so the
    # display change cannot shift the placed ink.
    set_hidden_lines_removed(adapter, section)
    _centre_section(adapter, native)
    return section


def _section_axes(
    adapter: Any, native: Any
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Sheet directions of model -x and +z (1 mm each) in section A-A."""
    native.UpdateViewDisplayGeometry()
    origin, minus_x, plus_z = model_points_in_view(
        adapter,
        native,
        (
            (0.0, SECTION_Y / 1000.0, 0.0),
            (-0.001, SECTION_Y / 1000.0, 0.0),
            (0.0, SECTION_Y / 1000.0, 0.001),
        ),
        label="hanger section A-A axes",
        names=("origin", "minus x", "plus z"),
    )
    return (
        (minus_x[0] - origin[0], minus_x[1] - origin[1]),
        (plus_z[0] - origin[0], plus_z[1] - origin[1]),
    )


def _orient_section(adapter: Any, native: Any, cut: Any) -> None:
    """Look down on the U: model -x to sheet right, the strap back face up.

    Looking along -y with +z up puts -x on the right, a right-handed pair on
    the sheet; a left-handed pair is the cut looking UP, so the cut direction
    is reversed.  The view then turns until -x reads right (draw_fr_top_frame
    ``_orient_cut_section``).
    """
    right, up = _section_axes(adapter, native)
    if right[0] * up[1] - right[1] * up[0] < 0.0:
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="hanger section reversed")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("hanger section A-A cut direction did not persist")
        right, up = _section_axes(adapter, native)
    native.Angle = float(native.Angle) - math.atan2(right[1], right[0])
    rebuild_drawing(adapter, label="hanger section turned")
    right, up = _section_axes(adapter, native)
    tolerance = 1e-7
    if (
        right[0] <= 0.0
        or abs(right[1]) > tolerance
        or up[1] <= 0.0
        or abs(up[0]) > tolerance
    ):
        raise RuntimeError(
            f"hanger section A-A is not looking down on the U: {right=}, {up=}"
        )
    _telemetry.info(f"hanger section A-A angle={float(native.Angle):.6f} rad")


def _centre_section(adapter: Any, native: Any) -> None:
    """Land the section's silhouette centre on SECTION_CENTER.

    Placed by projection, not by outline: whatever the outline of a cut-only
    section boxes, every SECTION_KEEP position is computed from where the
    cut face's own centre projects.  ``SetViewPosition`` moves the ink by the
    difference from the Position it reads (draw_pd_transgear_thumbnut).
    """
    anchor = (_SX / 1000.0, SECTION_Y / 1000.0, _SZ / 1000.0)
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        projected = model_point_in_view(
            adapter, native, anchor, label=f"hanger section A-A centre, pass {attempt}"
        )
        if math.dist(projected, SECTION_CENTER) <= 1e-4:
            break
        position = tuple(float(value) for value in native.Position)
        moved = [
            position[axis] + SECTION_CENTER[axis] - projected[axis] for axis in (0, 1)
        ]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to re-centre hanger section A-A")
        rebuild_drawing(adapter, label="hanger section re-centred")
    settle_detail_projection(
        adapter,
        native,
        anchor,
        ink_xy=SECTION_CENTER,
        tolerance_xy=(0.0005, 0.0005),
        label="hanger section A-A",
    )


def _add_overhang_reference(adapter: Any, section: Any) -> None:
    """The upper plate's +x edge past the strap's cut edge, as a reference.

    Both ends are real edges of section A-A (the strap's hatched cut and the
    plate's outline below it); the value is read back before it is
    parenthesized, so a pick that resolved to a neighbouring line fails the
    build instead of printing a wrong number.
    """
    label = "upper plate overhang reference"
    strap_edge, plate_edge = model_points_in_view(
        adapter,
        section,
        (
            (_STRAP_CUT_X[1] / 1000.0, SECTION_Y / 1000.0, OVERHANG_PICK_Z[0] / 1000.0),
            (_HALF_PLATE / 1000.0, _UPPER_TOP_Y / 1000.0, OVERHANG_PICK_Z[1] / 1000.0),
        ),
        label=label,
        names=("strap cut edge", "plate +x edge"),
    )
    display = _early_bound(
        add_edge_dimension(
            adapter,
            section,
            p0=strap_edge,
            p1=plate_edge,
            text_xy=OVERHANG_TEXT_XY,
            label=label,
            orientation="horizontal",
        ),
        "IDisplayDimension",
    )
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue)) * 1000.0
    if abs(measured_mm - _OVERHANG_AT_CUT) > 1e-4:
        raise RuntimeError(
            f"{label} measured {measured_mm:g}, expected {_OVERHANG_AT_CUT:g}"
        )
    set_reference_dimension(adapter, display.GetAnnotation(), label=label)
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError(f"{label} precision did not persist")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-hanger source", await adapter.open_model(str(SOURCE)))
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
            "Front View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Front View Note",
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
            0: "Pen Hanger Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen hanger; tapered strap; two open U pen-rod guide plates",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # *Back looks at the strap's front face from the machine front: the plates
    # face the reader and note 1's FRONT FACE is the face the view shows.
    front = place_view(adapter, str(SOURCE), "*Back", *FRONT_CENTER, scale=FRONT_SCALE)
    set_hidden_lines_removed(adapter, front)
    section = _create_section(adapter, front)
    position_section_caption(
        adapter, section, SECTION_CAPTION_XY, label="hanger section A-A"
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The iso too: a new view already reads Shaded With Edges, so
    # finalize_drawing's SetDisplayMode4 is a no-op that leaves the view at
    # draft quality (farm c0b95549c readback).  From HLR the shading call
    # really changes the mode and takes precision.
    set_hidden_lines_removed(adapter, iso)

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
    ]
    # Offset the slot width's and the strap stock's text while each is still
    # the bare value: its dimension line stays put, and the callout rows added
    # next grow the parked block, not the span between its extension lines.
    offset_dimension_text(
        adapter,
        annotations,
        {"SlotWidth": SLOT_WIDTH_TEXT_XY, "StrapThick": STRAP_THICK_TEXT_XY},
    )
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # The strap's and the guide plates' thickness is the sheet stock's, each
    # printed as a reference (no band) over its SHEET STOCK callout row.
    references = [
        (dimension_name(adapter, item), item)
        for item in annotations
        if dimension_name(adapter, item) in REFERENCE_DIMENSIONS
    ]
    if sorted(name for name, _ in references) != sorted(REFERENCE_DIMENSIONS):
        raise RuntimeError(
            f"expected one native stock thickness each: {sorted(REFERENCE_DIMENSIONS)}"
        )
    for name, item in references:
        set_reference_dimension(adapter, item, label=f"{name} stock thickness")
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _add_overhang_reference(adapter, section)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the hanger-screw hole")

    # Pick the hole's rim on its sheet-right side (model -x under *Back), not
    # the hole centre: the leader leaves toward CALLOUT_XY without crossing
    # the dimensions stacked left of the strap.
    screw_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=(
            _fx(SCREW_HOLE_XY[0] - SCREW_HOLE_DIA / 2.0),
            _fy(SCREW_HOLE_XY[1]),
        ),
        callout_xy=CALLOUT_XY,
        label="hanger-screw clearance hole",
        process="DRILL",
    )
    # The #15 drill's Ø prints .XXX (+.004/0 from the title block).
    set_hole_callout_precision(
        screw_callout, SCREW_HOLE_CALLOUT_PRECISION, label="hanger-screw clearance hole"
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Front View Note", *FRONT_NOTE_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    # Rule 10: the upper plate's lateral station is the lower plate's, said
    # on section A-A where the plate shows in plan beside its overhang.
    add_leader_note(
        adapter,
        UPPER_PLATE_LOCATION_CALLOUT,
        text_xy=UPPER_PLATE_NOTE_XY,
        attach_xy=UPPER_PLATE_NOTE_TIP,
        label="upper guide plate in line with the lower",
        view=section,
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Hanger Manufacturing Drawing",
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
