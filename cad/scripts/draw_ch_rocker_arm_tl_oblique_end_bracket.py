r"""Create the drawing for the oblique-trammel jig's end bracket (MHA-CH-06-TL-28).

One part, two off (the title block's quantity). A 2.71 x 1/2 x 1 in flat at
2:1: the plan (the *Front view, looking down on the top face) carries the
two hole stations from the inner end and the length, all stacked below it,
the row's station from the -Y side face (left), the stock width (right) and
one native callout per hole over it, each leader on its own hole; the end
view, projected right of the plan, carries the stock thickness and section
A-A's cutting line; section A-A, cut along the hole row and placed under the
plan, draws both faces' threads solid and carries two part-owned LIMIT
dimensions for their independent full-thread depths. Each plan callout
identifies its thread and refers to those limits; the first alone states
#29 DRILL THRU for BOTH HOLES, retaining the native drill-diameter token.
The shaded isometric rides top right at 1:1. The KP08's 42 mm bolt span
prints exact millimetres, labelled mm. No hand-formatted depth substitutes
for either native dimension or its model-owned limits.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_arm_tl_oblique_end_bracket.py ch-rocker-arm-tl-oblique-end-bracket
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
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
from _drawing_dimension_import import import_cosmetic_threads
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
)
from _drawing_hidden_sketches import curate_view_dimensions, part_sketches_shown
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_sections import create_section_view
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _section_axis import position_section_caption
import _telemetry
import ch_rocker_arm_tl_oblique_end_bracket_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _printed_limits import limits
from _drawing_metric_vendor import print_imported_metric_dimensions
from _supplier_dimensions import supplier_reference_dimension
from ch_rocker_arm_tl_oblique_callouts import set_callout_lengths_to_three_places
from ch_rocker_arm_tl_oblique_end_bracket_spec import (
    BAR_TAP_SPEC,
    BAR_THREAD_DEPTH,
    BAR_THREAD_DEPTH_DIMENSION,
    BAR_THREAD_REFERENCE,
    BAR_THREAD_LIMITS,
    BRACKET_LENGTH,
    BRACKET_THICK,
    BRACKET_WIDTH,
    CALLOUTS_BELOW,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HALF_WIDTH,
    HOLE_ROW_Y,
    HOLE_X,
    KP08_TAP_SPEC,
    KP08_THREAD_DEPTH,
    KP08_THREAD_DEPTH_DIMENSION,
    KP08_THREAD_REFERENCE,
    KP08_THREAD_LIMITS,
    MATE_CALLOUT,
    METRIC_DIMENSIONS,
    ROW_CALLOUT,
    STOCK_CALLOUTS,
    STOCK_FRACTION_DENOMINATORS,
    TAP_CALLOUT_PLACES,
    TAP_DRILL,
    THREAD_MAJOR,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_end_bracket"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# The 68.9 bracket at 2:1 (ruling A′: flush with the 1/2 x 6 bar's column
# edge; PR2's two holes): the plan outline spans sheet x 96.1..233.9; the end
# view projects right of it on its centreline (third angle). The 1/2 x 1 bar
# on edge makes the end view 50.8 wide (outline x 267.6..318.4), so the 1:1
# iso stands 20 further right, its note under it, all above the title block
# (x 216 on, up to y 70) and under the 267 border. The two hole callouts
# stand in two tiers a layout-audit row pitch apart (c4-r8: at 6 the audit
# merged stacked blocks), both up-left of their holes so they clear the end
# view; the plan drops 4 to keep the top tier under the border.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
ISO_SCALE = (1, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
PLAN_CENTER = (0.165, 0.1925)
END_CENTER = (0.293, PLAN_CENTER[1])
ISO_CENTER = (0.378, 0.195)
ISO_NOTE_XY = (0.350, 0.155)
ISO_HALF = (0.030, 0.025)  # the iso's half extents (sheet m)

# Every text position is a MODEL point (mm) off the part, mapped onto its
# view at run time (draw_ch_rocker_arm_tl_oblique_feed_lever). In the plan
# model +X runs right and +Y up; text sizes are sheet mm halved at 2:1.
# A keep point is its text block's centre; SolidWorks hangs the dimension
# line about TEXT_DROP below a one-line block and TWO_LINE_DROP below a
# two-line one (base bar readback), so every station's text sits on the
# part side of its line under the plan.
_H = BRACKET_THICK
_L = BRACKET_LENGTH
_HW = HALF_WIDTH
STACK_FIRST = 8.0 / _S
STACK_LANE = 6.0 / _S  # ASME Y14.5's 6 sheet mm between one-line lanes
TEXT_DROP = 2.7 / _S
TWO_LINE_DROP = 5.6 / _S
TEXT_GAP = 2.5 / _S  # a text's clearance from the line it sits beside
EXT_OVERSHOOT = 1.5 / _S  # an extension line's run past its dimension line
SIDE_LANE = 8.0 / _S  # first side-dimension line off the part
# One 3.5 mm capital's advance: the c4-r2 readback measured 2.43 .. 2.74
# sheet mm ("MATCHES KP08 BLOCK HOLES" the widest); take the widest.
GLYPH = 2.75 / _S
ROW_PITCH = 5.56 / _S  # text rows (_oblique_block_drawing)
# The layout audit reads two blocks stacked closer than its 5.66 mm row pitch
# as one ([merged-blocks], c4-r8).
STACK_PITCH = 5.66 / _S


def text_half(text: str) -> float:
    """Half the widest line of ``text`` (model mm)."""
    return max(len(line) for line in text.split("\n")) * GLYPH / 2.0


def text_half_high(rows: int) -> float:
    """Half a ``rows``-line block's height (model mm), 3.5 mm glyphs."""
    return ((rows - 1) * ROW_PITCH + 3.5 / _S) / 2.0


# A two-line block's far edge from its own line, plus the gap to the next.
MATE_LANE = TWO_LINE_DROP + text_half_high(2) + TEXT_GAP
# c4-r3: the row's station dimension line ran 6.35 sheet mm past the -Y side.
ROW_TAIL = 6.35 / _S
# The dimension lines below the plan, nearest first, shortest span nearest:
# the first block clears the row station's line tail, each next one the line
# above it; the length's one-line block clears the last station's line.
STATION_ORDER = ("KP08Tap1X", "KP08Tap2X")
_FIRST_LANE = -_HW - ROW_TAIL - TEXT_GAP - (TWO_LINE_DROP + text_half_high(2))
STATION_LANES = tuple(_FIRST_LANE - i * MATE_LANE for i in range(len(STATION_ORDER)))
LENGTH_LANE = STATION_LANES[-1] - (TEXT_GAP + TEXT_DROP + text_half_high(1))


def plan_sheet(x: float, y: float) -> tuple[float, float]:
    """Sheet xy (m) of a plan model point: the view centres on its outline."""
    return (
        PLAN_CENTER[0] + (x - _L / 2.0) * _S / 1000.0,
        PLAN_CENTER[1] + y * _S / 1000.0,
    )


_ROW_TEXT = "\n".join((f"{HOLE_ROW_Y / 25.4:.3f}".lstrip("0"), ROW_CALLOUT))
_ROW_ROWS = _ROW_TEXT.count("\n") + 1


def _outboard_left(mate: str) -> float:
    """Centre X of a station block standing left of the inner end's line."""
    return -(TEXT_GAP + text_half(mate))


_STATIONS = dict.fromkeys(STATION_ORDER, MATE_CALLOUT)
# The plan. Every station is a DRO absolute from the inner end carrying its
# mate on a second line. The blocks are wider than their spans, so each
# stands left of the inner end's extension line, where none of the other
# stations' extension lines (at X 13.925 and 55.925) pass (c4-r3: stacks
# over the plan crowded the tap callouts off their holes).
# Left of the plan: the row's station from the -Y side face, its three-line
# block between its own extension lines. Right of it: the stock width.
PLAN_KEEP: dict[str, tuple[float, float, float]] = {
    **{
        name: (
            _outboard_left(_STATIONS[name]),
            STATION_LANES[lane] + TWO_LINE_DROP,
            _H,
        )
        for lane, name in enumerate(STATION_ORDER)
    },
    "BracketLength": (_L / 2.0, LENGTH_LANE + TEXT_DROP, _H),
    "HoleRowY": (-(SIDE_LANE + TEXT_GAP + text_half(_ROW_TEXT)), -HOLE_ROW_Y / 2.0, _H),
    "BracketWidth": (_L + SIDE_LANE + 1.0, 0.0, _H),
}
# The end view (*Right): the thickness beside its span, off the -Y side.
END_KEEP: dict[str, tuple[float, float, float]] = {
    "BracketThick": (_L, -_HW - SIDE_LANE, _H / 2.0),
}

# Section A-A: the plane of the hole row (model y 0), its cutting line drawn
# across the end view (where it is the view's mid-height line; on the plan it
# would run along the row's and the width's own lines) from SECTION_OVERRUN
# below the bottom face to as far above the top. Removed under the plan at
# the sheet scale, +Z up, its centre (mid-length, mid-height) on
# SECTION_CENTER: its top 10 under the plan's lowest text (sheet y 0.142),
# its foot 15 over the title block's top; the caption under it, left of the
# title block. Independent top/bottom full-thread LIMIT dimensions stand
# left/right of the section, each on a native OffsetText leader.
SECTION_LABEL = "A"
SECTION_OVERRUN = 2.0
SECTION_LINE_MODEL_MM = (
    (_L, 0.0, -SECTION_OVERRUN),
    (_L, 0.0, _H + SECTION_OVERRUN),
)
SECTION_ANCHOR_MODEL_MM = (_L / 2.0, 0.0, _H / 2.0)
SECTION_CENTER = (PLAN_CENTER[0], 0.106)
SECTION_CAPTION_XY = (PLAN_CENTER[0], 0.074)
DEPTH_LANE = SIDE_LANE / 2.0
SECTION_KEEP: dict[str, tuple[float, float, float]] = {
    BAR_THREAD_DEPTH_DIMENSION: (_L + DEPTH_LANE, 0.0, BAR_THREAD_DEPTH / 2.0),
    KP08_THREAD_DEPTH_DIMENSION: (-DEPTH_LANE, 0.0, _H - KP08_THREAD_DEPTH / 2.0),
}
SECTION_TEXT = {
    BAR_THREAD_DEPTH_DIMENSION: (
        _L + DEPTH_LANE + TEXT_GAP
        + text_half(CALLOUTS_BELOW[BAR_THREAD_DEPTH_DIMENSION]), 0.0, _H / 2.0,
    ),
    KP08_THREAD_DEPTH_DIMENSION: (
        -DEPTH_LANE - TEXT_GAP
        - text_half(CALLOUTS_BELOW[KP08_THREAD_DEPTH_DIMENSION]), 0.0, _H / 2.0,
    ),
}
_TEXT_SETTLE_M = 0.0005

# One native callout per hole over the plan, its count dropped (c4-r3: a 2X
# callout's leader lands on one hole only, leaving the other's thread to a
# guess). Each leader runs from its shelf's near end to its hole's centre;
# both callouts stand up-left of their holes, the outer hole's a tier higher
# so its leader passes over the inner hole's block and no leader crosses
# another, a callout or a line (every station hangs under the plan). The
# tiers clear the +Y side by 10.4 sheet mm and stand a block plus the audit's
# row pitch apart (c4-r8). Each tuple: the hole's X, the text block's centre
# (model X, Y) and the side (-1 left) whose upper rim the edge pick takes.
# The larger callout has the native drill row plus a thread identity and a
# section pointer. The other identifies its own hole but does not repeat
# the one through-drilling requirement.
THREAD_LIMIT_CALLOUT = "BOTH FACES: SECTION A-A"
DRILL_PROCESS = "#29 DRILL"
CALLOUT_ROWS = 3
CALLOUT_GLYPHS = len("#29 DRILL Ø.136 THRU ALL; BOTH HOLES")
_TIER_PITCH = 2.0 * text_half_high(CALLOUT_ROWS) + STACK_PITCH + 0.1
TAP_TIERS = tuple(
    _HW + 5.0 + text_half_high(CALLOUT_ROWS) + 0.2 + k * _TIER_PITCH
    for k in range(len(HOLE_X))
)


def _tap_callout(
    x: float, tier: int, side: int, run: float
) -> tuple[float, tuple[float, float], int]:
    """A callout ``run`` past its hole on ``side``, its shelf's near end there."""
    half = CALLOUT_GLYPHS * GLYPH / 2.0
    return x, (x + side * (run + half), TAP_TIERS[tier]), side


TAP_CALLOUTS: tuple[tuple[float, tuple[float, float], int], ...] = (
    # A 2.5 sheet mm shelf run keeps the full block 10.116 mm inside the border.
    _tap_callout(HOLE_X[0], 0, -1, TEXT_GAP),
    _tap_callout(HOLE_X[1], 1, -1, 3.0),
)


def tap_edge_model(x: float, side: int) -> tuple[float, float, float]:
    """A point on the hole's upper rim, on the side its leader comes from."""
    radius = TAP_DRILL / 2.0
    return (x + side * 0.6 * radius, 0.8 * radius, _H)


part_metadata(
    precision_sources=(
        "DRAWING_PRECISION_BY_NAME",
        ("_drawing_hole_callout", "add_native_hole_callout"),
    )
)

_INTO_BRACKET = ([0.0, 0.0, -1.0], ("__frame__",))
_PLACES = part_spec.ROW_PLACES
_UNIT = part_spec.UNIT


def _limits(model: float, places: int) -> list[float]:
    """A general-band dimension's acceptance limits on the inch sheet: the
    title block's band about the value printed at ``places``."""
    return limits(model, places, unit=_UNIT)


def _stock_limits(model: float, band: float) -> list[float]:
    """An as-bought size's supplier band about its nominal."""
    return [round(model - band, 12), round(model + band, 12)]


def _printed(model: float, places: int) -> float:
    """The millimetres of ``model`` printed at ``places`` inch decimals."""
    return round(round(model / 25.4, places) * 25.4, 9)


_FROM_LOW_SIDE = (
    "bracket_low_side",
    (("draw_ch_rocker_arm_tl_oblique_end_bracket", "build"),),
)

# The bottom face, on the base bar's top.
requirement(
    "bar_seat",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("thickness", "length", "width"),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "thickness": (
            _stock_limits(part_spec.BRACKET_THICK, part_spec.THICK_STOCK_BAND),
            ("BRACKET_THICK", "THICK_STOCK_BAND"),
        ),
        "thickness_nominal": (part_spec.BRACKET_THICK, ("BRACKET_THICK",)),
        "length": (
            _limits(part_spec.BRACKET_LENGTH, part_spec.LENGTH_PLACES),
            ("BRACKET_LENGTH", "LENGTH_PLACES"),
        ),
        "length_nominal": (part_spec.BRACKET_LENGTH, ("BRACKET_LENGTH",)),
        "width": (
            _stock_limits(part_spec.BRACKET_WIDTH, part_spec.WIDTH_STOCK_BAND),
            ("BRACKET_WIDTH", "WIDTH_STOCK_BAND"),
        ),
        "width_nominal": (part_spec.BRACKET_WIDTH, ("BRACKET_WIDTH",)),
    },
    precision={
        "thickness": part_spec.STOCK_PLACES,
        "length": part_spec.LENGTH_PLACES,
        "width": part_spec.STOCK_PLACES,
    },
)

# The -Y side face: the datum the row's station measures from.
requirement(
    "bracket_low_side",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), part_spec.HALF_WIDTH),),
    requirements=(),
    fields={
        "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "y", "value": -part_spec.HALF_WIDTH},
            ("HALF_WIDTH",),
        ),
    },
)


def _row_fields() -> dict[str, tuple[Any, tuple[Any, ...]]]:
    return {
        "height": (
            _limits(part_spec.HOLE_ROW_Y, _PLACES),
            ("HOLE_ROW_Y", "ROW_PLACES"),
        ),
        "height_nominal": (part_spec.HOLE_ROW_Y, ("HOLE_ROW_Y",)),
        "height_from": _FROM_LOW_SIDE,
    }


_HOLE_PLACES = part_spec.HOLE_PLACES
_HOLE_BAND = (part_spec.HOLE_BAND, -part_spec.HOLE_BAND)
for _index, _x in enumerate(part_spec.HOLE_X, start=1):
    _drill = _printed(part_spec.TAP_DRILL, TAP_CALLOUT_PLACES)
    requirement(
        f"tap_{_index}",
        kind="hole",
        faces=(CylinderFace(part_spec.TAP_DRILL, contains_x_mm=_x),),
        requirements=("thread", "dia", "station", "height", "thru", "note"),
        fields={
            # Drilled THRU from the top; threaded from both faces.
            "at": ([_x, 0.0, part_spec.BRACKET_THICK], ("HOLE_X", "KP08_TAP_FACE")),
            "axis": _INTO_BRACKET,
            "thread": (
                f"{part_spec.SCREW} UNC-{part_spec.KP08_TAP_SPEC.thread_class}",
                ("KP08_TAP_SPEC", "BAR_TAP_SPEC", "SCREW"),
            ),
            "tap_drill_mm": (part_spec.TAP_DRILL, ("KP08_TAP_SPEC",)),
            "dia": (
                limits(_drill, TAP_CALLOUT_PLACES, part_spec.DRILLED_BAND),
                ("TAP_DRILL", "DRILLED_BAND"),
            ),
            "nominal_dia": (_drill, ("TAP_DRILL",)),
            "thru": (True, ("KP08_TAP_SPEC",)),
            # A DRO absolute from the inner end: the KP08's 42 bolt spacing,
            # exact millimetres with its own band (owner ruling 4).
            "station": (
                limits(_x, _HOLE_PLACES, _HOLE_BAND),
                (
                    "HOLE_X",
                    "HOLE_PLACES",
                    "HOLE_BAND",
                    ("ch_rocker_arm_tl_vn_oblique_leadscrew_spec", "BRACKET_HOLES_X"),
                    ("ch_rocker_arm_tl_vn_oblique_leadscrew_spec", "KP08_BOLT_SPACING"),
                ),
            ),
            "station_nominal": (_x, ("HOLE_X",)),
            **_row_fields(),
            # prechips has no per-face thread-depth field. This cited note
            # carries both independently model-owned section LIMIT bands.
            "note": (
                f"{MATE_CALLOUT}; FULL THREAD "
                f"{part_spec.KP08_THREAD_LIMITS[0]:.3f} TO "
                f"{part_spec.KP08_THREAD_LIMITS[1]:.3f} mm FROM THE TOP FACE AND "
                f"{part_spec.BAR_THREAD_LIMITS[0]:.3f} TO "
                f"{part_spec.BAR_THREAD_LIMITS[1]:.3f} mm FROM THE BOTTOM FACE",
                (
                    "MATE_CALLOUT",
                    "KP08_PATTERN_ALLOWANCE",
                    "BAR_PATTERN_ALLOWANCE",
                    "POSITION_RADIUS",
                    "KP08_THREAD_LIMITS",
                    "BAR_THREAD_LIMITS",
                    "BAR_THREAD_REFERENCE",
                    "KP08_THREAD_REFERENCE",
                ),
            ),
        },
        precision={
            "dia": TAP_CALLOUT_PLACES,
            "station": _HOLE_PLACES,
            "height": _PLACES,
        },
    )


def _view_mapper(adapter: Any, view: Any):
    """Return model point (mm) -> sheet xy (m) through the view's transform."""
    transform = _early_bound(
        _early_bound(view, "IView").ModelToViewTransform, "IMathTransform"
    )
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")

    def to_sheet(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        point = _early_bound(
            math_utility.CreatePoint(double_array([c / 1000.0 for c in model_mm])),
            "IMathPoint",
        )
        data = _early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData
        return float(data[0]), float(data[1])

    return to_sheet


def _metres(point_mm: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(value / 1000.0 for value in point_mm)


def _section_axes(
    adapter: Any, native: Any
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Sheet directions of model +X and +Z (1 mm each) in section A-A, read
    behind the projection barrier (draw_ch_rocker_arm_tl_oblique_carrier
    ``_section_axes``)."""
    native.UpdateViewDisplayGeometry()
    x, y, z = SECTION_ANCHOR_MODEL_MM
    origin, plus_x, plus_z = model_points_in_view(
        adapter,
        native,
        (_metres((x, y, z)), _metres((x + 1.0, y, z)), _metres((x, y, z + 1.0))),
        label="end bracket section A-A axes",
        names=("origin", "plus x", "plus z"),
    )
    return (
        (plus_x[0] - origin[0], plus_x[1] - origin[1]),
        (plus_z[0] - origin[0], plus_z[1] - origin[1]),
    )


def _orient_section(adapter: Any, section: Any) -> None:
    """Turn section A-A until model +Z runs up the sheet, keeping the cut
    direction SolidWorks gives it (draw_ch_rocker_arm_tl_oblique_carrier
    ``_orient_section``: a reversed section imported nothing, jig-r4). +X
    then reads right or left; SECTION_KEEP is projected either way, and the
    log says which."""
    native = _early_bound(section, "IView")
    _right, up = _section_axes(adapter, native)
    native.Angle = float(native.Angle) + math.pi / 2.0 - math.atan2(up[1], up[0])
    rebuild_drawing(adapter, label="end bracket section turned")
    right, up = _section_axes(adapter, native)
    tolerance = 1e-7
    if (
        up[1] <= 0.0
        or abs(up[0]) > tolerance
        or abs(right[1]) > tolerance
        or abs(right[0]) <= tolerance
    ):
        raise RuntimeError(f"end bracket section A-A is not +Z up: {right=}, {up=}")
    _telemetry.info(
        f"end bracket section A-A angle={float(native.Angle):.6f} rad, "
        f"+X reads {'right' if right[0] > 0.0 else 'left'} (cut not reversed)"
    )


def _centre_section(adapter: Any, section: Any) -> None:
    """Land the cut's centre (mid-length, mid-height) on SECTION_CENTER: a
    section's Position is its cut-plane origin, not its outline's centre
    (draw_ch_rocker_arm_tl_oblique_carrier ``_centre_section``)."""
    native = _early_bound(section, "IView")
    anchor = _metres(SECTION_ANCHOR_MODEL_MM)
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        projected = model_point_in_view(
            adapter, native, anchor, label=f"end bracket section A-A centre, pass {attempt}"
        )
        if math.dist(projected, SECTION_CENTER) <= 1e-4:
            break
        position = tuple(float(value) for value in native.Position)
        moved = [
            position[axis] + SECTION_CENTER[axis] - projected[axis] for axis in (0, 1)
        ]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to re-centre end bracket section A-A")
        rebuild_drawing(adapter, label="end bracket section re-centred")
    settle_detail_projection(
        adapter,
        native,
        anchor,
        ink_xy=SECTION_CENTER,
        tolerance_xy=(0.0005, 0.0005),
        label="end bracket section A-A",
    )


def _section(adapter: Any, end: Any) -> Any:
    """Section A-A along the hole row, cut from the end view, +Z up, centred."""
    line = model_points_in_view(
        adapter,
        end,
        [_metres(point) for point in SECTION_LINE_MODEL_MM],
        label="end bracket section A-A line",
        names=("below", "above"),
    )
    section = create_section_view(
        adapter,
        end,
        line_start=line[0],
        line_end=line[1],
        view_xy=SECTION_CENTER,
        section_label=SECTION_LABEL,
        scale=VIEW_SCALE,
        label="bottom thread depth section",
    )
    _orient_section(adapter, section)
    # A section shows no hidden lines (rule 9), set before centring so the
    # display change cannot shift the ink.
    set_hidden_lines_removed(adapter, section)
    _centre_section(adapter, section)
    return section


def _require_thread_depths(section: Any) -> None:
    """Both imported LIMIT dimensions belong to their own face's source."""
    view = _early_bound(section, "IView")
    expected = {
        BAR_THREAD_DEPTH_DIMENSION: (
            BAR_THREAD_REFERENCE, "BarTaps", BAR_THREAD_DEPTH, BAR_THREAD_LIMITS,
        ),
        KP08_THREAD_DEPTH_DIMENSION: (
            KP08_THREAD_REFERENCE, "KP08Taps", KP08_THREAD_DEPTH, KP08_THREAD_LIMITS,
        ),
    }
    model = _early_bound(view.ReferencedDocument, "IModelDoc2")
    found = set()
    for raw in view.GetDisplayDimensions() or ():
        display = _early_bound(raw, "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        full_name = str(dimension.FullName)
        name, owner, *_ = full_name.split("@")
        if name not in expected or name in found:
            raise RuntimeError(f"section A-A has an unexpected dimension {full_name}")
        reference, feature_name, nominal, limits_mm = expected[name]
        if owner != reference:
            raise RuntimeError(f"{full_name}: wrong full-thread source")
        raw_taps = _early_bound(model, "IPartDoc").FeatureByName(feature_name)
        if raw_taps is None:
            raise RuntimeError(f"section A-A's part has no {feature_name}")
        wizard = _early_bound(
            _early_bound(raw_taps, "IFeature").GetDefinition(), "IWizardHoleFeatureData2"
        )
        actual = float(dimension.SystemValue) * 1000.0
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        endpoints = (
            actual + float(tolerance.GetMinValue()) * 1000.0,
            actual + float(tolerance.GetMaxValue()) * 1000.0,
        )
        if (
            int(wizard.ThreadEndCondition) != 0
            or abs(float(wizard.ThreadDepth) * 1000.0 - nominal) > 1e-4
            or abs(actual - nominal) > 1e-4
            or int(tolerance.Type) != 3
            or int(display.GetPrimaryTolPrecision2()) != 3
            or any(abs(got - want) > 1e-4 for got, want in zip(endpoints, limits_mm))
        ):
            raise RuntimeError(f"{full_name}: native full-thread LIMITS lost: {endpoints}")
        found.add(name)
    if found != set(expected):
        raise RuntimeError(f"section A-A missing full-thread LIMIT dimensions: {found}")


# Section A-A draws both faces' threads (machinist review 0c3ed35988: it drew
# only the top thread, dashed, and no bottom thread). SolidWorks prints a
# section's thread annotation dashed, as a hidden thread, so every thread in
# the cut moves onto a visible thin continuous layer of its own
# (draw_pn_pen_v_block._section_thread_on_visible_layer). The cut runs on
# both holes' axes, so each hole shows its top and its bottom thread. Farm
# 84d5991d45 and 26bb still drew no bottom thread: every view imported
# BarTaps' own thread annotations hidden (Visible 3, no display) while
# KP08Taps' drew, so the part carries a native cosmetic thread on each
# finished bore's bottom edge (build_..._end_bracket, BarFaceThread) and the
# settled section must draw each one, both sides, from the bottom face to
# BAR_THREAD_DEPTH, where the depth's witness lands.
SECTION_THREAD_LAYER = "TAP-THREAD-SECTION"
SECTION_THREAD_INSTANCES = len(HOLE_X) * len(("BarFaceThread", "KP08Taps"))
_COSMETIC_THREAD_ANNOTATION = 1  # swAnnotationType_e.swCosmeticThread
_THREAD_LINE_TOL_M = 0.00025


def _thread_annotation_lines(
    section: Any,
) -> tuple[list[tuple[float, float, float, float]], list[tuple[str, int, int]]]:
    """Every visible cosmetic thread's drawn lines in section A-A (sheet m),
    and each thread annotation's (name, Visible, line count) for the log."""
    lines: list[tuple[float, float, float, float]] = []
    states: list[tuple[str, int, int]] = []
    for raw_annotation in _early_bound(section, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != _COSMETIC_THREAD_ANNOTATION:
            continue
        visible = int(annotation.Visible)
        drawn: list[tuple[float, float, float, float]] = []
        raw_data = annotation.GetDisplayData()
        if raw_data is not None:
            data = _early_bound(raw_data, "IDisplayData")
            for index in range(int(data.GetLineCount())):
                # GetLineAtIndex2 -> [color, lineType, _, _, start[3], end[3]].
                raw = [float(value) for value in data.GetLineAtIndex2(index)]
                drawn.append((raw[4], raw[5], raw[7], raw[8]))
        states.append((str(annotation.GetName() or ""), visible, len(drawn)))
        if visible == 1:
            lines.extend(drawn)
    return lines, states


def _covers(
    lines: list[tuple[float, float, float, float]],
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    """True when drawn segments along ``start``..``end`` cover it and one of
    them ends at ``end`` (the thread's drawn end, where the depth lands)."""
    length = math.dist(start, end)
    if length <= 0.0:
        return False
    ux, uy = (end[0] - start[0]) / length, (end[1] - start[1]) / length

    def along(point: tuple[float, float]) -> tuple[float, float]:
        dx, dy = point[0] - start[0], point[1] - start[1]
        return dx * ux + dy * uy, abs(dx * uy - dy * ux)

    spans: list[tuple[float, float]] = []
    ends_at_end = False
    for x0, y0, x1, y1 in lines:
        (s0, off0), (s1, off1) = along((x0, y0)), along((x1, y1))
        if max(off0, off1) > _THREAD_LINE_TOL_M:
            continue
        spans.append((min(s0, s1), max(s0, s1)))
        if min(abs(s0 - length), abs(s1 - length)) <= _THREAD_LINE_TOL_M:
            ends_at_end = True
    reach = _THREAD_LINE_TOL_M
    for low, high in sorted(spans):
        if low > reach:
            break
        reach = max(reach, high)
    return ends_at_end and reach >= length - _THREAD_LINE_TOL_M


@_telemetry.traced("drawing.end_bracket.require_threads_drawn")
def _require_threads_drawn(adapter: Any, section: Any) -> None:
    """Both sides of both face threads must draw to their native depth."""
    lines, states = _thread_annotation_lines(section)
    missing = []
    for face, start_z, end_z in (
        ("bottom", 0.0, BAR_THREAD_DEPTH),
        ("top", _H, _H - KP08_THREAD_DEPTH),
    ):
        for x in HOLE_X:
            for side in (-1.0, 1.0):
                radius_x = x + side * THREAD_MAJOR / 2.0
                start = model_point_in_view(
                    adapter, section, _metres((radius_x, 0.0, start_z)),
                    label=f"section A-A {face} thread face",
                )
                end = model_point_in_view(
                    adapter, section, _metres((radius_x, 0.0, end_z)),
                    label=f"section A-A {face} thread end",
                )
                if not _covers(lines, start, end):
                    missing.append((face, round(radius_x, 3)))
    if missing:
        raise RuntimeError(f"section A-A missing thread lines {missing}; {states!r}")


def _section_threads_on_visible_layer(adapter: Any, section: Any) -> None:
    """Import section A-A's cosmetic threads, both faces' on both holes, and
    print them thin and solid; the layer's state and every thread
    annotation's layer are read back."""
    seeds, instances = import_cosmetic_threads(adapter, section)
    if instances < SECTION_THREAD_INSTANCES:
        raise RuntimeError(
            f"section A-A shows {instances} cosmetic-thread instances ({seeds} "
            f"seeds), not both faces' threads on both holes "
            f"({SECTION_THREAD_INSTANCES})"
        )
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(SECTION_THREAD_LAYER)
    if layer is None:
        # COLORREF black, swLineCONTINUOUS (0), swLW_THIN (0).
        if (
            int(
                manager.AddLayer(
                    SECTION_THREAD_LAYER, "section A-A tap threads", 0, 0, 0
                )
            )
            != 1
        ):
            raise RuntimeError(f"failed to add layer {SECTION_THREAD_LAYER}")
        layer = manager.GetLayer(SECTION_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = True
    if not bool(layer.Visible) or int(layer.Style) != 0 or int(layer.Width) != 0:
        raise RuntimeError(
            f"layer {SECTION_THREAD_LAYER} reads visible={layer.Visible!r}, style "
            f"{layer.Style!r}, width {layer.Width!r}; wanted visible thin continuous"
        )
    moved = 0
    for raw_annotation in _early_bound(section, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != _COSMETIC_THREAD_ANNOTATION:
            continue
        annotation.Layer = SECTION_THREAD_LAYER
        if str(annotation.Layer or "") != SECTION_THREAD_LAYER:
            raise RuntimeError(f"a cosmetic thread refused layer {SECTION_THREAD_LAYER}")
        moved += 1
    if moved < 2:
        raise RuntimeError(
            f"section A-A lists {moved} cosmetic-thread annotations to layer, "
            "not one for each face's thread"
        )
    rebuild_drawing(adapter, label=f"cosmetic threads to {SECTION_THREAD_LAYER}")
    _telemetry.info(
        f"section A-A cosmetic threads: seeds/instances={(seeds, instances)!r}, "
        f"{moved} on {SECTION_THREAD_LAYER}"
    )
    _require_threads_drawn(adapter, section)


@_telemetry.traced("drawing.end_bracket.offset_depth_text")
def _offset_depth_text(
    adapter: Any, annotations: list[Any], text_xy: dict[str, tuple[float, float]]
) -> None:
    """Offset both independent full-thread limit blocks clear of their lines."""
    offset_dimension_text(adapter, annotations, text_xy)
    found = set()
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in text_xy:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        position = annotation.GetPosition()
        if (
            name in found
            or not bool(display.OffsetText)
            or position is None
            or math.dist(position[:2], text_xy[name]) > _TEXT_SETTLE_M
        ):
            raise RuntimeError(f"section A-A {name}: limit text not at {text_xy[name]}")
        found.add(name)
    if found != set(text_xy):
        raise RuntimeError(f"section A-A lost limit dimensions: {found}")


def _omit_tap_thread_class(display: Any, *, label: str) -> None:
    """The title block owns UNC class; the callout retains native identity."""
    omit_title_block_thread_class(display, label=label)
    native = _early_bound(display, "IDisplayDimension")
    resolved = [str(native.GetText(part) or "") for part in (1, 2, 3, 4)]
    classes = {BAR_TAP_SPEC.thread_class, KP08_TAP_SPEC.thread_class}
    if any(cls in text for text in resolved for cls in classes):
        raise RuntimeError(f"{label}: callout still prints its class: {resolved!r}")


_COUNT = re.compile(r"<NUM_INST>X\s*")
_PRINTED_COUNT = re.compile(r"^\s*\d+X\s", re.MULTILINE)


def single_hole_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Drop the instance count: this callout's leader names one hole."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected hole-callout parts: {definitions!r}")
    counts = [part for part, text in definitions.items() for _ in _COUNT.finditer(text)]
    if len(counts) != 1:
        raise RuntimeError(f"hole callout lacks one instance count: {definitions!r}")
    (part,) = counts
    return {**definitions, part: _COUNT.sub("", definitions[part], count=1)}


def thread_limit_definitions(
    definitions: dict[int, str], *, include_drill: bool
) -> dict[int, str]:
    """Keep native identity/diameter tokens; depths belong to section LIMITS."""
    updated = single_hole_definitions(definitions)
    thread_parts = [
        part for part, text in updated.items()
        if "<hw-thread>" in text and "<HOLE-DEPTH><hw-threaddepth>" in text
    ]
    drill_parts = [
        part for part, text in updated.items()
        if "<MOD-DIAM>" in text and "THRU ALL" in text
    ]
    if (
        len(thread_parts) != 1 or len(drill_parts) != 1
        or sum(text.count("<hw-threaddepth>") for text in updated.values()) != 1
    ):
        raise RuntimeError(f"unexpected opposed-thread native callout: {definitions!r}")
    thread_part, drill_part = thread_parts[0], drill_parts[0]
    if thread_part == drill_part:
        raise RuntimeError("thread and drill must have independent callout rows")
    updated[thread_part] = updated[thread_part].replace(
        "<HOLE-DEPTH><hw-threaddepth>", f"\n{THREAD_LIMIT_CALLOUT}", 1
    )
    updated[drill_part] = (
        f"{DRILL_PROCESS} {updated[drill_part]}; BOTH HOLES" if include_drill else ""
    )
    return updated


@_telemetry.traced("drawing.end_bracket.single_hole_callout")
def _call_out_one_hole(display: Any, *, label: str, include_drill: bool) -> None:
    """State native thread identity and exactly one shared through-drill row."""
    native = _early_bound(display, "IDisplayDimension")

    def read(parts: tuple[int, ...]) -> dict[int, str]:
        return {
            part: str(native.GetText(part) or "").replace("\r", "") for part in parts
        }

    definitions = read((5, 6, 7, 8))
    updated = thread_limit_definitions(definitions, include_drill=include_drill)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = read((5, 6, 7, 8))
    resolved = read((1, 2, 3, 4))
    if (
        persisted != updated
        or any(_PRINTED_COUNT.search(text) for text in resolved.values())
        or sum(text.count(THREAD_LIMIT_CALLOUT) for text in resolved.values()) != 1
    ):
        raise RuntimeError(
            f"{label}: callout prints a count or misses the section pointer: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )
    _telemetry.info(f"{label}: {resolved!r}")


def _activate_view(adapter: Any, view: Any, *, label: str) -> None:
    """Make ``view`` the active view (a note lands in the active view)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} view {name!r}")


# SolidWorks pins its own "#8-32 Tapped Hole" note per tap feature and view,
# and the cut's cosmetic-thread import regroups them: farm 0c3 swept two from
# the plan, 84d (both faces' threads imported into A-A) one. The count is
# SolidWorks' bookkeeping, not the sheet's contract; finalize bounds it by
# the features that carry such a note: the two tap features (BarTaps,
# KP08Taps) and the part's bottom cosmetic threads (BarFaceThread1/2, whose
# callout text is the same "#8-32 Tapped Hole"). The contract is what the
# settled sheet says: each hole's callout states its thread and points at
# A-A, and no note anywhere repeats a thread.
TAP_FEATURES = ("BarTaps", "KP08Taps")
BAR_FACE_THREADS = tuple(f"BarFaceThread{k}" for k in range(1, len(HOLE_X) + 1))
REDUNDANT_THREAD_NOTES = range(1, len(TAP_FEATURES) + len(BAR_FACE_THREADS) + 1)
_THREAD_TEXT = part_spec.SCREW.lstrip("#")  # "8-32"


def callout_states_its_thread(resolved: list[str]) -> bool:
    """Each hole names its thread and the independent section LIMIT bands."""
    text = "\n".join(resolved)
    return (
        f"{_THREAD_TEXT} UNC" in text
        and text.count(THREAD_LIMIT_CALLOUT) == 1
        and "<hw-threaddepth>" not in text
    )


def stray_thread_notes(texts: list[str]) -> list[str]:
    """Notes that state a thread: the callouts own every thread statement."""
    return [
        text
        for text in texts
        if "TAPPED HOLE" in text.upper() or _THREAD_TEXT in text
    ]


def _require_threads_stated_by_callouts_only(
    adapter: Any, callouts: list[tuple[str, Any]]
) -> None:
    """After the final rebuild: both callouts still state their thread, and no
    note on the sheet (any view, or the sheet itself) repeats one."""
    drill_rows = []
    for label, display in callouts:
        native = _early_bound(display, "IDisplayDimension")
        resolved = [
            str(native.GetText(part) or "").replace("\r", "") for part in (1, 2, 3, 4)
        ]
        if not callout_states_its_thread(resolved):
            raise RuntimeError(
                f"{label}: settled callout lost its thread: {resolved!r}"
            )
        drill_rows.extend(
            row for text in resolved for row in text.splitlines() if "THRU" in row
        )
    if (
        len(callouts) != len(HOLE_X)
        or len(drill_rows) != 1
        or DRILL_PROCESS not in drill_rows[0]
        or "THRU ALL" not in drill_rows[0]
        or "BOTH HOLES" not in drill_rows[0]
    ):
        raise RuntimeError(f"expected one #29 DRILL THRU for both holes: {drill_rows}")
    texts: list[str] = []
    node = _early_bound(adapter.currentModel, "IDrawingDoc").GetFirstView()  # sheet
    while node is not None:
        view = _early_bound(node, "IView")
        texts += [
            str(_early_bound(note, "INote").GetText() or "")
            for note in (view.GetNotes() or ())
        ]
        node = view.GetNextView()
    if stray := stray_thread_notes(texts):
        raise RuntimeError(f"the sheet still repeats a thread in notes: {stray!r}")


_STOCK_SIZES = {"BracketWidth": BRACKET_WIDTH, "BracketThick": BRACKET_THICK}


def _stock_references(adapter: Any, annotations: list[Any]) -> None:
    """The as-bought width and thickness print as REF stock fractions over
    STOCK (#290, draw_mg_magnifying_lever's rod stock)."""
    by_name: dict[str, list[Any]] = {}
    for item in annotations:
        by_name.setdefault(dimension_name(adapter, item), []).append(item)
    for name, size in _STOCK_SIZES.items():
        matches = by_name.get(name, [])
        if len(matches) != 1:
            raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
        display = _early_bound(
            _early_bound(matches[0], "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        supplier_reference_dimension(
            adapter,
            display,
            label=f"end bracket stock {name}",
            units="in",
            precision=DRAWING_PRECISION_BY_NAME[name],
            expected_mm=size,
            fraction_denominator=STOCK_FRACTION_DENOMINATORS[name],
            callout=STOCK_CALLOUTS[name],
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open end bracket source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
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
            0: "Rocker Oblique Trammel End Bracket Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker oblique trammel end bracket; aluminum flat bar; MHA-CH-06-TL-28",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Right", *END_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (plan, end, iso):
        set_hidden_lines_removed(adapter, view)

    on_plan = _view_mapper(adapter, plan)
    on_end = _view_mapper(adapter, end)
    # The plan shows the hidden HoleRowReference sketch, whose .250 it prints.
    annotations = [
        *curate_view_dimensions(
            adapter,
            plan,
            keep={name: on_plan(xyz) for name, xyz in PLAN_KEEP.items()},
            view_label="end bracket plan",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            end,
            keep={name: on_end(xyz) for name, xyz in END_KEEP.items()},
            view_label="end bracket end",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # BarThreadReference lies in A-A's cutting plane, saved hidden: a derived
    # view takes it from the part as it stands when it is cut and selects it
    # through its base view, so the section is cut and curated while the part
    # shows it (draw_fr_nameplate's SectionReference).
    with part_sketches_shown(
        adapter,
        source_model,
        (BAR_THREAD_REFERENCE, KP08_THREAD_REFERENCE),
        label="section A-A full-thread references",
        base_view=end,
    ):
        section = _section(adapter, end)
        annotations += curate_view_dimensions(
            adapter,
            section,
            keep={
                name: model_point_in_view(
                    adapter, section, _metres(xyz), label=f"section A-A {name} text"
                )
                for name, xyz in SECTION_KEEP.items()
            },
            view_label="end bracket section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    position_section_caption(
        adapter, section, SECTION_CAPTION_XY, label="end bracket section A-A"
    )
    _require_thread_depths(section)
    # Both faces' threads drawn solid in the cut; the depth's witness leaves
    # the bottom thread's drawn end (BAR_THREAD_WITNESS_X).
    _section_threads_on_visible_layer(adapter, section)
    # Places are authored on the part; the sheet only proves the import kept
    # them, then writes the mate callouts and the stock references.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    print_imported_metric_dimensions(
        adapter,
        annotations,
        {
            name: places
            for (_feature, name), (places, _band) in METRIC_DIMENSIONS.items()
        },
    )
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    # The depth's text, rows and all, off its line onto its leader.
    _offset_depth_text(
        adapter,
        annotations,
        {
            name: model_point_in_view(
                adapter, section, _metres(xyz), label=f"section A-A {name} text"
            )
            for name, xyz in SECTION_TEXT.items()
        },
    )
    _stock_references(adapter, annotations)

    if not auto_center_marks(adapter, plan, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the plan")
    callouts: list[tuple[str, Any]] = []
    for index, (x, (text_x, text_y), side) in enumerate(TAP_CALLOUTS):
        label = f"screw hole at {x:.3f} mm"
        callout = add_native_hole_callout(
            adapter,
            plan,
            edge_xy=on_plan(tap_edge_model(x, side)),
            callout_xy=on_plan((text_x, text_y, _H)),
            label=label,
        )
        # Format native length variables before the second callout's
        # redundant drill/depth rows are removed.
        set_callout_lengths_to_three_places(callout, label=label)
        _call_out_one_hole(
            callout, label=label, include_drill=index == 0
        )
        _omit_tap_thread_class(callout, label=label)
        callouts.append((label, callout))

    # The property-linked blocks land in the active view: the plan.
    _activate_view(adapter, plan, label="plan")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Oblique Trammel End Bracket Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks' own "... Tapped Hole" notes repeat what each callout
        # states: swept, at most one per thread feature (REDUNDANT_THREAD_NOTES),
        # and the settled sheet proves none survives and both callouts do.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=REDUNDANT_THREAD_NOTES,
        settled_checks=(
            lambda: _require_threads_stated_by_callouts_only(adapter, callouts),
            lambda: _require_thread_depths(section),
            lambda: _require_threads_drawn(adapter, section),
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
