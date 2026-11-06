r"""Create the drawing for the oblique-trammel jig's end bracket (MHA-CH-06-TL-28).

One part, two off (the title block's quantity). A 2.71 x 1/2 x 1 in flat at
2:1. The plan (the *Front view, looking down on the top face) carries a tag at
each of the six taps, the hole table's origin at its inner-end / -Y-side
corner, the length under it and the stock width right of it. Under the plan a
native hole table locates every tap from that corner, gives each tag group's
size once and names the part whose holes the group matches by its drawing
number (drawing-guidelines.md rules 4, 7 and 10: every hole carries a mate, so
a tagged table, not a dimension per station; #2046: the KP08 block is
MHA-CH-06-TL-VN-56). The end view, projected right of the plan, carries the
stock thickness; the shaded isometric rides top right at 1:1, clear of the
title block. No datums (rule 5).

The KP08 stations print in inch in the table like every other row (owner
ruling 2026-11-06, superseding ruling 4B / exception RV-01, which printed
them in exact millimetres a native hole table cannot carry). One numbered
note, linked from the B group's MATCHES cell by ``SEE NOTE 1``, gives the
KP08's catalogue bolt spacing as a millimetre REF; no dimension mixes units.
At the table's three places the stations stay inside the KP08's float
(``TABLE_POSITION_RADIUS``) and every wall holds rule 17. The part keeps its
native ±0.13 mm band on those two model dimensions (the spec feeds the whole
jig's keys); the generated X LOC that prints it stands hidden and the sheet
prints each station bare under the title block's .XXX band (``x_loc_texts``).

Each tap drill runs THRU and each thread prints its .450 MIN full-thread depth
from its screw's face, the bar taps' FAR SIDE (owner ruling 2026-11-05: the
hand traveler).

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
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
    remove_notes_matching,
    view_name,
)
from solidworks_mcp.adapters.sw_type_info import constant

import _config
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
from _drawing_dimensions import assert_imported_precision
from _drawing_edges import visible_view_entities
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_tables import insert_hole_table
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_oblique_end_bracket_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _printed_limits import limits
from _supplier_dimensions import supplier_reference_dimension
from ch_rocker_arm_tl_oblique_end_bracket_spec import (
    BAR_SCREW,
    BAR_TAP_DRILL,
    BAR_TAP_X,
    BAR_THREAD_CALLOUT,
    BRACKET_LENGTH,
    BRACKET_THICK,
    BRACKET_WIDTH,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_DIMENSIONS,
    FULL_THREAD_DEPTH,
    HALF_WIDTH,
    HOLE_ROW_Y,
    KP08_TAP_DRILL,
    KP08_TAP_X,
    KP08_THREAD,
    KP08_THREAD_CALLOUT,
    STOCK_CALLOUTS,
    STOCK_FRACTION_DENOMINATORS,
    TAP_CALLOUT_PLACES,
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
# edge, four bar taps): the plan outline spans sheet x 96.1..233.9, y
# 179.8..205.2; the end view projects right of it on its centreline (third
# angle). The 1/2 x 1 bar on edge makes the end view 50.8 wide (outline x
# 267.6..318.4), so the 1:1 iso stands 20 further right, its note under it,
# all above the title block (x 216 on, up to y 70) and under the 267 border.
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
# view at run time. In the plan model +X runs right and +Y up; sheet lengths
# are halved at 2:1. A keep point is its text block's centre; SolidWorks hangs
# the dimension line about TEXT_DROP below a one-line block (base bar
# readback).
_H = BRACKET_THICK
_L = BRACKET_LENGTH
_HW = HALF_WIDTH
STACK_FIRST = 8.0 / _S  # the length's line off the plan's -Y side
TEXT_DROP = 2.7 / _S
SIDE_LANE = 8.0 / _S  # first side-dimension line off the part
LENGTH_LANE = -_HW - STACK_FIRST


def plan_sheet(x: float, y: float) -> tuple[float, float]:
    """Sheet xy (m) of a plan model point: the view centres on its outline."""
    return (
        PLAN_CENTER[0] + (x - _L / 2.0) * _S / 1000.0,
        PLAN_CENTER[1] + y * _S / 1000.0,
    )


# The plan keeps only the overall length (under it) and the stock width
# (right of it); the hole table locates every tap.
PLAN_KEEP: dict[str, tuple[float, float, float]] = {
    "BracketLength": (_L / 2.0, LENGTH_LANE + TEXT_DROP, _H),
    "BracketWidth": (_L + SIDE_LANE + 1.0, 0.0, _H),
}
# The end view (*Right): the thickness beside its span, off the -Y side.
END_KEEP: dict[str, tuple[float, float, float]] = {
    "BracketThick": (_L, -_HW - SIDE_LANE, _H / 2.0),
}

# --- Hole table ---------------------------------------------------------------
# The taps, in model X order: (kind, X). Two tag groups, one per size: the
# four base-bar #8-32 taps and the two KP08 #6-32 taps.
TABLE_HOLES: tuple[tuple[str, float], ...] = tuple(
    sorted([("bar", x) for x in BAR_TAP_X] + [("kp08", x) for x in KP08_TAP_X],
           key=lambda hole: hole[1])
)
TAP_DRILLS = {"bar": BAR_TAP_DRILL, "kp08": KP08_TAP_DRILL}
TAP_THREADS = {"bar": BAR_SCREW, "kp08": KP08_THREAD}
# What follows each thread depth: MIN, and the bar taps' FAR SIDE (they are
# threaded from the bottom; the plan looks at the top).
THREAD_CALLOUTS = {"bar": BAR_THREAD_CALLOUT, "kp08": KP08_THREAD_CALLOUT}
# The origin: the faced inner end (X 0) and the -Y side face, the corner every
# station is a DRO absolute from (rule 10).
TABLE_ORIGIN_MODEL = (0.0, -_HW, _H)
# Each tag group's mate by its full drawing number from the registry
# (rule 4; #2046), the KP08's catalogue code after it with the link to the
# spacing note (owner ruling 2026-11-06).
BASE_BAR_NUMBER = _config.parts("ch-rocker-arm-tl-oblique-base-bar")["number"]
PILLOW_BLOCK_NUMBER = _config.parts("ch-rocker-arm-tl-vn-oblique-pillow-block")["number"]
MATE_NUMBERS = {"bar": BASE_BAR_NUMBER, "kp08": PILLOW_BLOCK_NUMBER}
KP08_NOTE_LINK = "SEE NOTE 1"
MATE_CELLS = {
    "bar": BASE_BAR_NUMBER,
    "kp08": f"{PILLOW_BLOCK_NUMBER}\n(KP08) {KP08_NOTE_LINK}",
}
# The KP08's catalogue bolt spacing (the spec proves the taps' span is it),
# a millimetre REF in one numbered note: the uxcell block is a metric part.
KP08_SPACING_MM = KP08_TAP_X[1] - KP08_TAP_X[0]
KP08_SPACING_NOTE = f"1. B1 TO B2: {KP08_SPACING_MM:.2f} mm REF, KP08 CATALOGUE SPACING"
# Upper left of the note (sheet m): right of the table (x 199), above the
# title block (y 70), left of and under the iso and its note (x 348, y 155).
KP08_SPACING_NOTE_XY = (0.225, 0.095)
MATE_COLUMN = "MATCHES HOLES OF"
SIZE_COLUMN = "SIZE"


def _inch(mm: float, places: int) -> str:
    """``mm`` in inch at ``places``, leading zero dropped (ASME Y14.5)."""
    return f"{mm / 25.4:.{places}f}".lstrip("0")


def _printed(model: float, places: int) -> float:
    """The millimetres of ``model`` printed at ``places`` inch decimals."""
    return round(round(model / 25.4, places) * 25.4, 9)


def size_text(kind: str) -> str:
    """One tag group's size, printed once in its merged SIZE cell: the tap
    drill THRU, then the thread and its full-thread depth from its face. The
    title block's THREADS row owns the UNC class (rule 2)."""
    drill = _inch(_printed(TAP_DRILLS[kind], TAP_CALLOUT_PLACES), TAP_CALLOUT_PLACES)
    depth = _inch(FULL_THREAD_DEPTH, TAP_CALLOUT_PLACES)
    thread = TAP_THREADS[kind].lstrip("#")
    return (
        f"<MOD-DIAM>{drill} THRU ALL\n"
        f"{thread} UNC <HOLE-DEPTH>{depth} {THREAD_CALLOUTS[kind]}"
    )


# The table stands under the plan's length, its top-left corner here (sheet
# m), left of the title block (x 216) and the end view's thickness (x 267).
HOLE_TABLE_ANCHOR = (0.020, 0.158)
# Column widths (sheet m), 3.5 mm text at ~2.5 mm a glyph (fr_harmonic_base's
# "SEE NOTE 1" prints 24.7), by the finished table's columns (hidden ones
# included): TAG, the custom X LOC, Y LOC, then the custom SIZE ("8-32 UNC
# <depth>.450 MIN FAR SIDE", 27 glyphs) and MATCHES HOLES OF
# ("MHA-CH-06-TL-VN-56", 18) columns.
# The generated table: TAG, X LOC, Y LOC, SIZE. The finished one inserts a
# custom X LOC after the generated one and the custom SIZE and MATCHES HOLES
# OF after the generated SIZE, then hides the generated X LOC (r1: the KP08
# rows print the part's native band, ".548 ±.005", restating the title
# block) and the generated SIZE (it restates the thread class).
NATIVE_COLUMNS = {"x": 1, "y": 2, "size": 3}
FINISHED_COLUMNS = {"x": 1, "y": 3, "size": 4}
_X_LOC = 2
_SIZE = 5
_MATE = 6
_HIDDEN = (FINISHED_COLUMNS["x"], FINISHED_COLUMNS["size"])
X_LOC_COLUMN = "X LOC"
HOLE_TABLE_WIDTHS = {
    0: 0.013, _X_LOC: 0.019, FINISHED_COLUMNS["y"]: 0.019, _SIZE: 0.078, _MATE: 0.050
}
_INSERT_COLUMN_AFTER = 3  # swTableItemInsertPosition_After
_INSERT_COLUMN_DEFAULT_WIDTH = 0  # swInsertColumn_DefaultWidth
_TABLE_SIZE_CAN_CHANGE = 0  # swTableRowColChange_TableSizeCanChange
_TABLE_LOCATION_TOLERANCE_MM = 0.02
# Inch sheets drop the leading zero (ASME Y14.5; draw_fr_rocker_arm_support).
HOLE_TABLE_LEADING_ZERO = "swLeadingZero_DoNotShow"

# Each tag stands above the plan's +Y side, right of its hole, on a leader to
# the hole's rim. The closest holes stand 6.69 apart (13.4 sheet mm), a
# two-glyph tag ~6 sheet mm wide.
HOLE_TAG_DX = 2.0
HOLE_TAG_Y = _HW + 3.5

# --- The table's printed limits ------------------------------------------------
# Every station prints .XXX with the title block's band, the KP08 stations
# included (provisional, module docstring). The spec proves both patterns'
# float and the walls at its exact-millimetre KP08 band; here the KP08
# stations' rounded inch limits reach a little further, so the float and the
# walls are re-proved with that extra excursion.
_PLACES = part_spec.HOLE_PLACES
_UNIT = part_spec.UNIT


def _limits(model: float, places: int) -> list[float]:
    """A general-band dimension's acceptance limits on the inch sheet: the
    title block's band about the value printed at ``places``."""
    return limits(model, places, unit=_UNIT)


def _excursion(model: float) -> float:
    low, high = _limits(model, _PLACES)
    return max(model - low, high - model)


TABLE_POSITION_RADIUS = max(
    math.hypot(_excursion(x), _excursion(HOLE_ROW_Y)) for _kind, x in TABLE_HOLES
)
if not (
    part_spec.KP08_SCREW_FLOAT > TABLE_POSITION_RADIUS
    and part_spec.BAR_SCREW_FLOAT > TABLE_POSITION_RADIUS
):
    raise AssertionError("an end bracket table station overruns its screw's float")
_KP08_EXTRA = max(_excursion(x) for x in KP08_TAP_X) - part_spec.KP08_TAP_BAND
if min(part_spec.WALLS_MM.values()) - max(_KP08_EXTRA, 0.0) < part_spec.WALL_TARGET:
    raise AssertionError("an end bracket wall falls under rule 17 at the table's limits")

part_metadata(
    precision_sources=(
        "DRAWING_PRECISION_BY_NAME",
        "HOLE_PLACES",
        "TAP_CALLOUT_PLACES",
        ("_drawing_tables", "insert_hole_table"),
    )
)

_INTO_BRACKET = ([0.0, 0.0, -1.0], ("__frame__",))


def _stock_limits(model: float, band: float) -> list[float]:
    """An as-bought size's supplier band about its nominal."""
    return [round(model - band, 12), round(model + band, 12)]


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

# The -Y side face: the table origin's Y datum, the row's station.
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
            ("HOLE_ROW_Y", "HOLE_PLACES"),
        ),
        "height_nominal": (part_spec.HOLE_ROW_Y, ("HOLE_ROW_Y",)),
        "height_from": _FROM_LOW_SIDE,
    }


_MATE_SOURCES = (
    ("draw_ch_rocker_arm_tl_oblique_end_bracket", "MATE_COLUMN"),
    ("draw_ch_rocker_arm_tl_oblique_end_bracket", "MATE_NUMBERS"),
)

for _index, _x in enumerate(part_spec.BAR_TAP_X, start=1):
    _drill = _printed(part_spec.BAR_TAP_DRILL, TAP_CALLOUT_PLACES)
    requirement(
        f"bar_tap_{_index}",
        kind="hole",
        faces=(CylinderFace(part_spec.BAR_TAP_DRILL, contains_x_mm=_x),),
        requirements=("thread", "dia", "station", "height", "thru", "note"),
        fields={
            # Entered and threaded from the bar (bottom) face; the drill runs THRU.
            "at": ([_x, 0.0, 0.0], ("BAR_TAP_X", "BAR_TAP_FACE")),
            "axis": ([0.0, 0.0, 1.0], ("BAR_TAP_FACE",)),
            "thread": (
                f"{part_spec.BAR_SCREW} UNC-{part_spec.BAR_TAP_SPEC.thread_class}",
                ("BAR_TAP_SPEC", "BAR_SCREW"),
            ),
            "tap_drill_mm": (part_spec.BAR_TAP_DRILL, ("BAR_TAP_SPEC",)),
            # The table's SIZE prints the tap drill to three places (.136).
            "dia": (
                limits(_drill, TAP_CALLOUT_PLACES, part_spec.DRILLED_BAND),
                ("BAR_TAP_DRILL", "DRILLED_BAND"),
            ),
            "nominal_dia": (_drill, ("BAR_TAP_DRILL",)),
            "thru": (True, ("BAR_TAP_SPEC",)),
            # A table X LOC from the inner end: base bar 1's bracket holes.
            "station": (
                _limits(_x, _PLACES),
                (
                    "BAR_TAP_X",
                    "HOLE_PLACES",
                    ("ch_rocker_arm_tl_vn_oblique_leadscrew_spec", "BRACKET_BAR_HOLES_X"),
                ),
            ),
            "station_nominal": (_x, ("BAR_TAP_X",)),
            **_row_fields(),
            "note": (
                f"{MATE_COLUMN} {MATE_NUMBERS['bar']}",
                (*_MATE_SOURCES, "BAR_PATTERN_ALLOWANCE", "POSITION_RADIUS"),
            ),
        },
        precision={"dia": TAP_CALLOUT_PLACES, "station": _PLACES, "height": _PLACES},
    )

for _index, _x in enumerate(part_spec.KP08_TAP_X, start=1):
    _drill = _printed(part_spec.KP08_TAP_DRILL, TAP_CALLOUT_PLACES)
    requirement(
        f"kp08_tap_{_index}",
        kind="hole",
        faces=(CylinderFace(part_spec.KP08_TAP_DRILL, contains_x_mm=_x),),
        requirements=("thread", "dia", "station", "height", "thru", "note"),
        fields={
            # Entered and threaded from the KP08 (top) face; the drill runs THRU.
            "at": ([_x, 0.0, part_spec.BRACKET_THICK], ("KP08_TAP_X", "KP08_TAP_FACE")),
            "axis": _INTO_BRACKET,
            "thread": (
                f"{part_spec.KP08_THREAD} UNC-{part_spec.KP08_TAP_SPEC.thread_class}",
                ("KP08_TAP_SPEC", "KP08_THREAD"),
            ),
            "tap_drill_mm": (part_spec.KP08_TAP_DRILL, ("KP08_TAP_SPEC",)),
            "dia": (
                limits(_drill, TAP_CALLOUT_PLACES, part_spec.DRILLED_BAND),
                ("KP08_TAP_DRILL", "DRILLED_BAND"),
            ),
            "nominal_dia": (_drill, ("KP08_TAP_DRILL",)),
            "thru": (True, ("KP08_TAP_SPEC",)),
            # A table X LOC from the inner end: the KP08's 42 bolt spacing at
            # the table's .XXX (provisional, module docstring).
            "station": (
                _limits(_x, _PLACES),
                (
                    "KP08_TAP_X",
                    "HOLE_PLACES",
                    ("ch_rocker_arm_tl_vn_oblique_leadscrew_spec", "BRACKET_KP08_HOLES_X"),
                    ("ch_rocker_arm_tl_vn_oblique_leadscrew_spec", "KP08_BOLT_SPACING"),
                ),
            ),
            "station_nominal": (_x, ("KP08_TAP_X",)),
            **_row_fields(),
            "note": (
                f"{MATE_COLUMN} {MATE_NUMBERS['kp08']}",
                (*_MATE_SOURCES, "KP08_PATTERN_ALLOWANCE", "POSITION_RADIUS"),
            ),
        },
        precision={"dia": TAP_CALLOUT_PLACES, "station": _PLACES, "height": _PLACES},
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


def _activate_view(adapter: Any, view: Any, *, label: str) -> None:
    """Make ``view`` the active view (a note lands in the active view)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} view {name!r}")


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


def _drop_hole_table_leading_zeros(adapter: Any) -> None:
    """Set the drawing's hole-table leading-zero option before the table exists."""
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    preference = constant("swDetailingLeadingZero")
    option = constant("swDetailingHoleTable")
    value = constant(HOLE_TABLE_LEADING_ZERO)
    if not extension.SetUserPreferenceInteger(preference, option, value):
        raise RuntimeError("failed to drop the hole table's leading zeros")
    if int(extension.GetUserPreferenceInteger(preference, option)) != value:
        raise RuntimeError("hole-table leading-zero option did not persist")


def _hole_rims(view: Any) -> tuple[Any, ...]:
    """The visible top-face rim of each tap, in ``TABLE_HOLES`` order."""
    circles: list[tuple[float, float, float, float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label="end bracket plan rims"):
        edge = _early_bound(raw_edge, "IEdge")
        raw_curve = edge.GetCurve()
        if raw_curve is None:
            continue
        curve = _early_bound(raw_curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        circles.append((params[0], params[1], params[2], params[6], edge))
    rims: list[Any] = []
    for kind, x in TABLE_HOLES:
        radius = TAP_DRILLS[kind] / 2.0
        matches = [
            edge
            for cx, cy, cz, r, edge in circles
            if abs(cx - x) <= 0.02
            and abs(cy) <= 0.02
            and abs(cz - _H) <= 0.02
            and abs(r - radius) <= 0.02
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"end bracket {kind} tap at {x:g} mm has {len(matches)} visible "
                f"top rims of r {radius:g}; circles={[c[:4] for c in circles]!r}"
            )
        rims.append(matches[0])
    return tuple(rims)


_THREAD_KIND = {TAP_THREADS[kind].lstrip("#"): kind for kind in TAP_THREADS}


def _cell(table: Any, row: int, column: int) -> str:
    """A cell's displayed text, hidden columns counted in the index."""
    return str(table.DisplayedText2(row, column, True) or "").replace("\r", "").strip()


def table_groups(
    rows: list[tuple[int, str, str, float]],
) -> dict[str, tuple[int, int]]:
    """Each tap kind's (first, last) table row: one tag letter, contiguous rows,
    the kind's every station once."""
    groups: dict[str, list[tuple[int, str, float]]] = {}
    for row, tag, kind, x in rows:
        groups.setdefault(kind, []).append((row, tag, x))
    spans: dict[str, tuple[int, int]] = {}
    for kind, members in groups.items():
        indices = [row for row, _tag, _x in members]
        letters = {re.sub(r"\d+$", "", tag) for _row, tag, _x in members}
        stations = sorted(x for _row, _tag, x in members)
        expected = sorted(x for k, x in TABLE_HOLES if k == kind)
        if (
            len(letters) != 1
            or indices != list(range(indices[0], indices[0] + len(indices)))
            or stations != expected
        ):
            raise RuntimeError(f"end bracket hole-table group {kind} is not one tag run: {members!r}")
        spans[kind] = (indices[0], indices[-1])
    if set(spans) != set(TAP_DRILLS):
        raise RuntimeError(f"end bracket hole table lacks a tap group: {sorted(spans)}")
    return spans

# The KP08 taps' model dimensions carry the part's native ±0.13 mm band
# (owner ruling 4), which the generated X LOC prints in inch beside the value
# (".548 ±.005" on one seat, ".548±.01" on another: fix round 2 CAD). That
# column stands hidden and the sheet prints the value bare (review round 1:
# the band restated the title block), so the title block governs every row;
# the module guard above proves the fit at that band. The visible generated
# column (Y LOC) must print bare.
_LOCATION = re.compile(r"^(-?\d*\.\d+|-?\d+)(?:\s*±\s*(\d*\.\d+))?$")


def _location(cell: str, *, label: str, bare: bool) -> re.Match[str]:
    match = _LOCATION.match(cell.strip())
    if match is None:
        raise RuntimeError(f"end bracket hole-table {label} is unparseable: {cell!r}")
    if bare and match[2] is not None:
        raise RuntimeError(f"end bracket hole-table {label} prints a band: {cell!r}")
    return match


def location_mm(cell: str, *, label: str, bare: bool = False) -> float:
    """A LOC cell's value in mm; ``bare`` cells must print no band."""
    return float(_location(cell, label=label, bare=bare)[1]) * 25.4


def location_text(cell: str, *, label: str) -> str:
    """A LOC cell's printed value without its band."""
    return _location(cell, label=label, bare=False)[1]


def _table_rows(
    table: Any, columns: dict[str, int] = NATIVE_COLUMNS
) -> list[tuple[int, str, str, float]]:
    """(row, tag, kind, model X) per generated row, each bound to one station."""
    rows: list[tuple[int, str, str, float]] = []
    for row in range(1, int(table.RowCount)):
        tag = _cell(table, row, 0)
        size = _cell(table, row, columns["size"])
        kinds = {kind for thread, kind in _THREAD_KIND.items() if thread in size}
        x_mm = location_mm(_cell(table, row, columns["x"]), label=f"row {row} X LOC")
        y_mm = location_mm(_cell(table, row, columns["y"]), label=f"row {row} Y LOC", bare=True)
        station = [x for kind, x in TABLE_HOLES if abs(x - x_mm) <= _TABLE_LOCATION_TOLERANCE_MM]
        if abs(y_mm - HOLE_ROW_Y) > _TABLE_LOCATION_TOLERANCE_MM:
            raise RuntimeError(f"end bracket hole-table row {row} Y LOC is {y_mm:g} mm")
        if len(kinds) != 1 or len(station) != 1:
            raise RuntimeError(f"end bracket hole-table row {row} unbound: {tag!r} {size!r} {x_mm:g}")
        rows.append((row, tag, kinds.pop(), station[0]))
    return rows


def x_loc_texts(
    rows: list[tuple[int, str, str, float]], cells: dict[int, str]
) -> dict[int, str]:
    """Each row's custom X LOC: the generated cell's value without its band,
    which must be the model station printed at .XXX."""
    texts: dict[int, str] = {}
    for row, _tag, _kind, x in rows:
        text = location_text(cells[row], label=f"row {row} X LOC")
        if text != _inch(x, _PLACES):
            raise RuntimeError(f"end bracket hole-table row {row} X LOC {text!r} is not {x:g} mm")
        texts[row] = text
    return texts


def _insert_column(table: Any, after: int, title: str) -> None:
    if table.InsertColumn2(
        _INSERT_COLUMN_AFTER, after, title, _INSERT_COLUMN_DEFAULT_WIDTH
    ) is not True:
        raise RuntimeError(f"end bracket hole table refused the {title} column")
    if table.SetColumnTitle2(after + 1, title, False) is not True:
        raise RuntimeError(f"end bracket hole-table {title} title did not set")


def _write_cell(table: Any, row: int, column: int, text: str) -> None:
    if table.IsCellTextEditable(row, column) is not True:
        raise RuntimeError(f"end bracket hole-table cell {row},{column} is locked")
    table.SetText2(row, column, False, text)


@_telemetry.traced("drawing.end_bracket.hole_table")
def _finish_hole_table(adapter: Any, table: Any) -> dict[str, str]:
    """Sort the rows by tag, print each X LOC without a band, write each
    group's size and mate once in merged custom cells and hide the generated
    X LOC and SIZE columns; return tag -> kind."""
    # Tag order groups each size's rows (table_groups proves it either way).
    sorted_ok = _early_bound(table, "IHoleTableAnnotation").Sort(0, True)
    rebuild_drawing(adapter, label="end bracket hole-table sort")
    rows = _table_rows(table)
    _telemetry.info(f"end bracket hole table sorted={sorted_ok!r}: {rows!r}")
    spans = table_groups(rows)
    x_texts = x_loc_texts(
        rows, {row: _cell(table, row, NATIVE_COLUMNS["x"]) for row, *_rest in rows}
    )
    _insert_column(table, NATIVE_COLUMNS["x"], X_LOC_COLUMN)
    _insert_column(table, FINISHED_COLUMNS["size"], SIZE_COLUMN)
    _insert_column(table, _SIZE, MATE_COLUMN)
    for row, text in x_texts.items():
        _write_cell(table, row, _X_LOC, text)
    texts = {
        kind: {_SIZE: size_text(kind), _MATE: MATE_CELLS[kind]} for kind in spans
    }
    for kind, (first, last) in spans.items():
        for column, text in texts[kind].items():
            _write_cell(table, first, column, text)
            if last > first and table.MergeCells(first, column, last, column) is not True:
                raise RuntimeError(f"end bracket hole table refused to merge {kind} {column}")
    for column, width in HOLE_TABLE_WIDTHS.items():
        actual = float(table.SetColumnWidth(column, width, _TABLE_SIZE_CAN_CHANGE))
        if abs(actual - width) > 1e-6:
            raise RuntimeError(f"end bracket hole-table column {column} width: {actual!r}")
    for column in _HIDDEN:
        table.SetColumnHidden(column, True)  # VT_VOID, not success.
    rebuild_drawing(adapter, label="end bracket hole-table columns")
    for column in _HIDDEN:
        if table.ColumnHidden(column) is not True:
            raise RuntimeError(f"end bracket hole table kept its generated column {column}")
    _check_hole_table(table, rows, spans, texts, x_texts)
    return {tag: kind for _row, tag, kind, _x in rows}


def _glyphless(text: str) -> str:
    """Compare cell text with its symbols however SolidWorks reads them back."""
    for symbol in ("<MOD-DIAM>", "<HOLE-DEPTH>", "\u00d8", "\u2300", "\u21a7"):
        text = text.replace(symbol, "")
    return re.sub(r"\s+", " ", text).strip()


def _check_hole_table(
    table: Any,
    rows: list[tuple[int, str, str, float]],
    spans: dict[str, tuple[int, int]],
    texts: dict[str, dict[int, str]],
    x_texts: dict[int, str],
) -> None:
    """Read the finished table back: generated rows unchanged, each row's
    custom X LOC, each group's size and mate in its first row, the headers.
    (MergeCells' True is the merge proof: early-bound IsCellMerged raises
    Type mismatch on its out parameters, r1 CAD retry.)"""
    if _table_rows(table, FINISHED_COLUMNS) != rows:
        raise RuntimeError("end bracket hole-table rows changed under the custom columns")
    for column, title in ((_X_LOC, X_LOC_COLUMN), (_SIZE, SIZE_COLUMN), (_MATE, MATE_COLUMN)):
        if _cell(table, 0, column).upper() != title:
            raise RuntimeError(f"end bracket hole-table header {column}: {_cell(table, 0, column)!r}")
    for row, text in x_texts.items():
        if _cell(table, row, _X_LOC) != text:
            raise RuntimeError(f"end bracket hole-table row {row} X LOC: {_cell(table, row, _X_LOC)!r}")
    for kind, (first, _last) in spans.items():
        for column, text in texts[kind].items():
            printed = _cell(table, first, column)
            if _glyphless(printed) != _glyphless(text):
                raise RuntimeError(
                    f"end bracket hole-table {kind} cell {column}: {printed!r} != {text!r}"
                )
    _telemetry.info(
        "end bracket hole table: "
        + repr([[_cell(table, r, c) for c in range(_MATE + 1)] for r in range(int(table.RowCount))])
    )


def _place_hole_tags(view: Any, tags: dict[str, str], rows: dict[str, float], on_plan) -> None:
    """Move each native tag above the plan, right of its hole, on a leader to
    its rim."""
    moved: set[str] = set()
    for raw in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.GetType()) != 6:  # swNote
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        tag = str(note.GetText()).strip()
        if tag not in tags:
            continue
        if tag in moved:
            raise RuntimeError(f"duplicate end bracket hole tag {tag}")
        x = rows[tag]
        if annotation.SetLeader3(1, 0, True, False, False, False) != 0:
            raise RuntimeError(f"failed to give end bracket hole tag {tag} a leader")
        if not annotation.SetPosition2(*on_plan((x + HOLE_TAG_DX, HOLE_TAG_Y, _H)), 0.0):
            raise RuntimeError(f"failed to place end bracket hole tag {tag}")
        points = tuple(float(v) for v in annotation.GetLeaderPointsAtIndex(0) or ())
        centre = on_plan((x, 0.0, _H))
        reach = TAP_DRILLS[tags[tag]] * _S / 2000.0 + 0.0005
        if len(points) < 6 or math.dist(points[-3:-1], centre) > reach:
            raise RuntimeError(f"end bracket hole tag {tag} leader misses its hole: {points!r}")
        moved.add(tag)
    if moved != set(tags):
        raise RuntimeError(f"end bracket hole tags missing on the plan: {sorted(set(tags) - moved)}")
    _telemetry.info(f"end bracket hole tags placed: {sorted(moved)}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open end bracket source", await adapter.open_model(str(SOURCE)))
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
    # Places are authored on the part; the sheet only proves the import kept
    # them, then writes the stock references.
    assert_imported_precision(
        adapter,
        annotations,
        {name: DRAWING_PRECISION_BY_NAME[name] for name in (*PLAN_KEEP, *END_KEEP)},
    )
    _stock_references(adapter, annotations)

    if not auto_center_marks(adapter, plan, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the plan")

    _drop_hole_table_leading_zeros(adapter)
    table = insert_hole_table(
        adapter,
        plan,
        datum_xy=on_plan(TABLE_ORIGIN_MODEL),
        hole_points=tuple(on_plan((x, 0.0, _H)) for _kind, x in TABLE_HOLES),
        hole_entities=_hole_rims(plan),
        # X LOC = the station from the inner end; Y LOC = the row from the
        # -Y side face, both at .XXX. _table_rows binds every printed row to
        # its station (the shared check cannot read the KP08 rows' band).
        anchor_xy=HOLE_TABLE_ANCHOR,
        basic_locations=False,
        label="end bracket taps",
        unit=_UNIT,
        location_places=_PLACES,
    )
    tags = _finish_hole_table(adapter, table)
    stations = {tag: x for _row, tag, _kind, x in _table_rows(table, FINISHED_COLUMNS)}
    _place_hole_tags(plan, tags, stations, on_plan)

    # The property-linked blocks land in the active view: the plan.
    _activate_view(adapter, plan, label="plan")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    _add_spacing_note(adapter)
    # SolidWorks pins its own "... Tapped Hole" note to the plan per tap
    # feature; the table owns the taps, so they go (draw_fr_rocker_arm_support).
    removed = remove_notes_matching(adapter, "Tapped Hole")
    _telemetry.info(f"removed {removed} automatic tapped-hole label(s)")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Oblique Trammel End Bracket Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=0,
    )


def _add_spacing_note(adapter: Any) -> None:
    """Note 1, the KP08's catalogue spacing REF, read back where it stands."""
    note = add_note(adapter, KP08_SPACING_NOTE, *KP08_SPACING_NOTE_XY)
    if note is None:
        raise RuntimeError("end bracket KP08 spacing note did not insert")
    note = _early_bound(note, "INote")
    text = str(note.GetText() or "")
    position = tuple(float(v) for v in _early_bound(note.GetAnnotation(), "IAnnotation").GetPosition())
    if text != KP08_SPACING_NOTE or math.dist(position[:2], KP08_SPACING_NOTE_XY) > 1e-6:
        raise RuntimeError(f"end bracket KP08 spacing note reads {text!r} at {position!r}")
    _telemetry.info(f"end bracket KP08 spacing note at {position!r}: {text!r}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
